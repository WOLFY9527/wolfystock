# -*- coding: utf-8 -*-
"""Market overview data service with short-lived cache and audit logging."""

from __future__ import annotations

import copy
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from src.contracts.source_confidence import coerce_source_confidence_contract
from src.services.execution_log_service import ExecutionLogService
from src.services.fx_commodities_contracts import FX_COMMODITY_DELAYED_PROXY_SYMBOLS
from src.services.futures_contracts import list_futures_contracts
from src.services.market_data_source_registry import resolve_source_label
from src.services.market_rotation_radar_service import MarketRotationRadarService
from src.services.official_macro_source_registry import get_official_macro_source_for_transport_source
from src.services.official_macro_transport import (
    MacroObservation,
    fetch_fred_observation_points,
    fetch_treasury_daily_rate_observation_points,
)
from src.services.market_overview_binance_transport import (
    fetch_binance_funding_row,
    fetch_binance_kline_history_rows,
    fetch_binance_ticker_snapshot,
)
from src.services.market_overview_sentiment_transport import (
    fetch_alternative_fear_greed_payload,
    fetch_cnn_fear_greed_payload,
)
from src.services.market_overview_sina_transport import fetch_sina_cn_index_rows
from src.services.market_overview_tickflow_breadth_provider import (
    fetch_tickflow_cn_breadth_snapshot,
)
from src.services.market_overview_yfinance_transport import (
    fetch_yfinance_quote_history_frame,
    fetch_yfinance_spy_atr_history_frame,
)
from src.services.market_cache import MARKET_CACHE_TTLS, REFRESH_WARNING, market_cache
from src.services.market_intelligence_trust_gate import (
    evaluate_market_intelligence_trust,
    evaluate_market_intelligence_trust_from_sources,
)
from src.services.rotation_state_evidence import build_rotation_state_evidence
from src.services.rotation_radar_quote_provider import get_rotation_radar_quote_provider
from src.storage import DatabaseManager

PanelPayload = Dict[str, Any]
CN_TZ = timezone(timedelta(hours=8))
FALLBACK_WARNING = "备用示例数据，不代表当前行情"
INSUFFICIENT_MARKET_DATA_WARNING = "当前真实数据不足，市场温度仅供界面演示"
OFFICIAL_MACRO_UNAVAILABLE_WARNING = "部分官方宏观指标暂不可用"

CONFIDENCE_BY_FRESHNESS = {
    "live": 1.0,
    "delayed": 0.8,
    "cached": 0.6,
    "stale": 0.3,
    "fallback": 0.0,
    "mock": 0.0,
    "error": 0.0,
}

SOURCE_TYPE_CONFIDENCE = {
    "official_api": 1.0,
    "official_public": 1.0,
    "exchange_public": 1.0,
    "public_api": 0.9,
    "unofficial_public_api": 0.7,
    "unofficial_proxy": 0.7,
    "public_proxy": 0.7,
    "proxy_public": 0.7,
    "computed_from_real": 0.6,
}

FALLBACK_SOURCE_TOKENS = ("fallback", "mock", "static", "sample", "synthetic")

SOURCE_TYPE_BY_SOURCE = {
    "sina": "public_api",
    "binance": "exchange_public",
    "binance_ws": "exchange_public",
    "yahoo": "unofficial_public_api",
    "yfinance": "unofficial_public_api",
    "yfinance_proxy": "unofficial_public_api",
    "eastmoney": "public_api",
    "fred": "official_public",
    "tickflow": "public_api",
    "alternative": "public_api",
    "alternative_me": "public_api",
    "cnn": "public_api",
    "computed": "computed_from_real",
    "treasury": "official_public",
}

SOURCE_LABELS = {
    "eastmoney": resolve_source_label("eastmoney"),
    "fred": "FRED",
    "sina": resolve_source_label("sina"),
    "tickflow": "TickFlow",
    "treasury": "US Treasury",
    "yahoo": resolve_source_label("yahoo"),
    "yfinance": resolve_source_label("yfinance"),
    "yfinance_proxy": resolve_source_label("yfinance_proxy"),
    "binance": resolve_source_label("binance"),
    "binance_ws": resolve_source_label("binance_ws"),
    "alternative": resolve_source_label("alternative"),
    "alternative_me": resolve_source_label("alternative_me"),
    "cnn": resolve_source_label("cnn"),
    "computed": "系统计算",
    "mixed": "多来源",
    "cached": resolve_source_label("cached"),
    "fallback": resolve_source_label("fallback"),
    "mock": resolve_source_label("mock"),
    "public": "公开数据",
    "unavailable": resolve_source_label("unavailable"),
}

PROVIDER_HEALTH_STATUSES = {
    "live",
    "cache",
    "stale",
    "fallback",
    "partial",
    "unavailable",
    "error",
    "refreshing",
}


def _has_valid_market_value(meta: Dict[str, Any]) -> bool:
    if isinstance(meta.get("items"), list) and meta["items"]:
        return True
    for key in ("value", "price", "change", "changePercent", "change_pct", "sentimentScore"):
        value = meta.get(key)
        if isinstance(value, (int, float)) and math.isfinite(value):
            return True
    return False


def _infer_source_type(source: str, explicit: Any = None) -> str:
    if explicit:
        return str(explicit)
    return SOURCE_TYPE_BY_SOURCE.get(source.lower(), "public_api" if source else "")


def classify_market_payload_reliability(payload: Dict[str, Any], category: str = "") -> Dict[str, Any]:
    """Classify market payload/item trust consistently for coverage and scoring."""
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    if items:
        item_results = [classify_market_payload_reliability(item, category=category) for item in items if isinstance(item, dict)]
        real_count = sum(1 for result in item_results if result["isReliable"])
        fallback_count = sum(1 for result in item_results if result["kind"] in {"fallback", "stale", "error"})
        if real_count and fallback_count:
            kind = "mixed"
        elif real_count:
            kind = "real"
        elif any(result["kind"] == "stale" for result in item_results):
            kind = "stale"
        elif any(result["kind"] == "error" for result in item_results):
            kind = "error"
        else:
            kind = "fallback"
        confidence = sum(result["confidenceWeight"] for result in item_results) / len(item_results) if item_results else 0.0
        return {
            "kind": kind,
            "isReliable": real_count > 0,
            "excluded": real_count == 0,
            "excludeReason": None if real_count > 0 else kind,
            "confidenceWeight": round(confidence, 2),
            "sourceType": str(payload.get("sourceType") or ""),
            "realItemCount": real_count,
            "fallbackItemCount": fallback_count,
        }

    source = str(payload.get("source") or "").lower()
    source_label = str(payload.get("sourceLabel") or "").lower()
    freshness = str(payload.get("freshness") or "").lower()
    source_type = _infer_source_type(source, payload.get("sourceType"))
    has_error = bool(payload.get("error") or payload.get("lastError"))
    is_fallback = bool(payload.get("isFallback") or payload.get("fallbackUsed") or payload.get("fallback_used"))
    fallback_source = any(token in source or token in source_label for token in FALLBACK_SOURCE_TOKENS)
    has_value = _has_valid_market_value(payload)

    if has_error and not has_value:
        return {"kind": "error", "isReliable": False, "excluded": True, "excludeReason": "error", "confidenceWeight": 0.0, "sourceType": source_type}
    if freshness == "stale" or payload.get("isStale"):
        return {"kind": "stale", "isReliable": False, "excluded": True, "excludeReason": "stale", "confidenceWeight": 0.0, "sourceType": source_type}
    if freshness in {"fallback", "mock"} or is_fallback or fallback_source or source_type == "computed_from_fallback":
        return {"kind": "fallback", "isReliable": False, "excluded": True, "excludeReason": "fallback", "confidenceWeight": 0.0, "sourceType": source_type}
    if not has_value:
        return {"kind": "error", "isReliable": False, "excluded": True, "excludeReason": "no_value", "confidenceWeight": 0.0, "sourceType": source_type}
    if category == "sentiment" and payload.get("change_pct") is not None and payload.get("change") is None:
        return {"kind": "error", "isReliable": False, "excluded": True, "excludeReason": "legacy_sentiment_panel_family", "confidenceWeight": 0.0, "sourceType": source_type}
    if freshness in {"live", "cached", "delayed"} and source_type in SOURCE_TYPE_CONFIDENCE:
        return {
            "kind": "real",
            "isReliable": True,
            "excluded": False,
            "excludeReason": None,
            "confidenceWeight": SOURCE_TYPE_CONFIDENCE[source_type],
            "sourceType": source_type,
        }
    return {"kind": "fallback", "isReliable": False, "excluded": True, "excludeReason": "unknown_source", "confidenceWeight": 0.0, "sourceType": source_type}


def _now_iso() -> str:
    return datetime.now(CN_TZ).isoformat(timespec="seconds")


def _compact_error_summary(error: Any) -> Optional[str]:
    text = str(error or "").strip()
    if not text:
        return None
    lowered = text.lower()
    if "timeout" in lowered or "timed out" in lowered or "超时" in lowered:
        return "数据源请求超时"
    if (
        "permission" in lowered
        or "forbidden" in lowered
        or "denied" in lowered
        or "tickflow_not_configured" in lowered
        or "tickflow_permission_unavailable" in lowered
    ):
        return "数据源暂不可用"
    if "unavailable" in lowered or "provider_down" in lowered or "down" in lowered or "不可用" in lowered:
        return "数据源暂不可用"
    if "rate" in lowered and "limit" in lowered:
        return "数据源限流"
    return "数据源刷新失败"


def _fallback_reason_code(error: Any) -> Optional[str]:
    text = str(error or "").strip()
    if not text:
        return None
    lowered = text.lower()
    if "tickflow_not_configured" in lowered:
        return "tickflow_not_configured"
    if "tickflow_permission_unavailable" in lowered:
        return "tickflow_permission_unavailable"
    if "tickflow_market_stats_empty" in lowered:
        return "tickflow_market_stats_empty"
    if "tickflow_market_stats_malformed" in lowered:
        return "tickflow_market_stats_malformed"
    if "tickflow_timeout" in lowered:
        return "tickflow_timeout"
    if "tickflow_unavailable" in lowered:
        return "tickflow_unavailable"
    if "timeout" in lowered or "timed out" in lowered or "超时" in lowered:
        return "provider_timeout"
    if "permission" in lowered or "forbidden" in lowered or "denied" in lowered:
        return "provider_permission_unavailable"
    if "unavailable" in lowered or "provider_down" in lowered or "down" in lowered or "不可用" in lowered:
        return "provider_unavailable"
    return "provider_refresh_failed"


def _parse_market_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=CN_TZ)
    return parsed.astimezone(CN_TZ)


def get_freshness_status(
    as_of: Any,
    category: str,
    source: str,
    is_fallback: bool,
    *,
    source_type: str = "",
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Return normalized market data freshness metadata for UI trust labeling."""
    source_key = str(source or "").lower()
    current = (now or datetime.now(CN_TZ)).astimezone(CN_TZ)
    if source_key == "mock":
        return {
            "freshness": "mock",
            "isFallback": True,
            "isStale": False,
            "delayMinutes": 0,
            "warning": "模拟数据，不代表当前行情",
        }
    if is_fallback or source_key in {"fallback", "synthetic", "unavailable"}:
        return {
            "freshness": "fallback",
            "isFallback": True,
            "isStale": False,
            "delayMinutes": 0,
            "warning": FALLBACK_WARNING,
        }

    parsed_as_of = _parse_market_time(as_of) or current
    delay_minutes = max(0, int((current - parsed_as_of).total_seconds() // 60))
    category_key = str(category or "").lower()

    stale_minutes = {
        "crypto": 15,
        "futures": 30,
        "fx_commodity": 60,
        "macro_rate": 60,
    }
    live_minutes = {
        "crypto": 5,
        "futures": 5,
        "fx_commodity": 15,
        "macro_rate": 60,
        "equity_index": 15,
        "breadth": 15,
        "flows": 30,
        "sentiment": 24 * 60,
    }

    source_type_key = str(source_type or "").lower()
    delayed_public_quote_source = source_key == "yfinance_proxy" or source_type_key in {
        "unofficial_proxy",
        "public_proxy",
        "proxy_public",
    }

    daily_categories = {"equity_index", "breadth", "flows", "sentiment"}
    if category_key == "macro_rate" and source_type_key == "official_public":
        days_old = (current.date() - parsed_as_of.date()).days
        freshness = "delayed" if days_old <= 3 else "stale"
    elif delayed_public_quote_source and category_key in daily_categories:
        days_old = (current.date() - parsed_as_of.date()).days
        if days_old > 1 or (category_key == "sentiment" and days_old > 0):
            freshness = "stale"
        elif days_old == 0:
            freshness = "delayed"
        else:
            freshness = "cached"
    elif delayed_public_quote_source and category_key in {"macro_rate", "fx_commodity", "futures"}:
        stale_after = stale_minutes.get(category_key, 60)
        freshness = "stale" if delay_minutes > stale_after else "delayed"
    elif category_key in daily_categories:
        days_old = (current.date() - parsed_as_of.date()).days
        if days_old > 1 or (category_key == "sentiment" and days_old > 0):
            freshness = "stale"
        elif days_old == 0 and delay_minutes <= live_minutes[category_key]:
            freshness = "live"
        else:
            freshness = "cached"
    elif category_key == "futures" and source_type_key in {"unofficial_proxy", "public_proxy", "disabled_live_stub"}:
        freshness = "stale" if delay_minutes > stale_minutes["futures"] else "delayed"
    elif category_key == "macro_rate" and delay_minutes > stale_minutes["macro_rate"]:
        freshness = "cached" if parsed_as_of.date() == current.date() else "stale"
    else:
        stale_after = stale_minutes.get(category_key, 60)
        live_after = live_minutes.get(category_key, 15)
        freshness = "live" if delay_minutes <= live_after else "stale" if delay_minutes > stale_after else "delayed"

    return {
        "freshness": freshness,
        "isFallback": False,
        "isStale": freshness == "stale",
        "delayMinutes": delay_minutes,
        "warning": "数据可能已过期，请以交易所/券商行情为准" if freshness == "stale" else None,
    }


class MarketOverviewService:
    """Fetch market overview panels from public sources, with cached payloads."""

    CACHE_TTL_SECONDS = 300
    MARKET_COLD_START_TIMEOUT_SECONDS = 2.0
    YFINANCE_PROXY_AGGREGATE_BUDGET_SECONDS = 1.8
    OFFICIAL_MACRO_AGGREGATE_BUDGET_SECONDS = 1.8
    OFFICIAL_MACRO_CALL_TIMEOUT_SECONDS = 0.9
    OFFICIAL_MACRO_MICRO_CACHE_TTL_SECONDS = 15.0
    SENTIMENT_AGGREGATE_BUDGET_SECONDS = 1.8
    MARKET_TEMPERATURE_INPUT_BUDGET_SECONDS = 3.0
    TEMPERATURE_INPUT_SNAPSHOT_CACHE_KEY = "temperature_input_snapshot"
    CRYPTO_FANOUT_WORKERS = 4
    LEGACY_SHARED_SENTIMENT_CACHE_KEY = "sentiment"
    OVERVIEW_SENTIMENT_CACHE_KEY = "overview_sentiment"
    MARKET_SENTIMENT_CACHE_KEY = "market_sentiment"
    _cache: Dict[str, tuple[float, PanelPayload]] = {}
    _market_data_cache: Dict[str, Dict[str, Any]] = {}
    _market_cache = market_cache

    def __init__(self) -> None:
        self._official_macro_micro_cache: Dict[str, tuple[float, List[MacroObservation]]] = {}
        self._quote_request_memo: Optional[Dict[str, tuple[bool, Any]]] = None

    INDEX_SYMBOLS = {
        "SPX": ("S&P 500", "^GSPC"),
        "NASDAQ": ("NASDAQ Composite", "^IXIC"),
        "DJIA": ("Dow Jones Industrial Average", "^DJI"),
        "RUT": ("Russell 2000", "^RUT"),
        "CSI300": ("CSI 300", "000300.SS"),
        "SSE": ("Shanghai Composite", "000001.SS"),
        "SZSE": ("Shenzhen Component", "399001.SZ"),
    }
    VOL_SYMBOLS = {
        "VIX": ("VIX", "^VIX"),
        "VVIX": ("VVIX", "^VVIX"),
        "VXN": ("VXN", "^VXN"),
    }
    MACRO_SYMBOLS = {
        "US10Y": ("10Y yield", "^TNX", "%"),
        "US30Y": ("30Y yield", "^TYX", "%"),
        "DXY": ("US Dollar Index", "DX-Y.NYB", "idx"),
        "GOLD": ("Gold futures", "GC=F", "USD"),
        "OIL": ("WTI crude", "CL=F", "USD"),
    }
    FX_COMMODITY_PROXY_TICKERS = {
        "DXY": "DX-Y.NYB",
        "USDCNH": "CNH=X",
        "USDJPY": "JPY=X",
        "EURUSD": "EURUSD=X",
        "GOLD": "GC=F",
        "WTI": "CL=F",
        "BRENT": "BZ=F",
        "COPPER": "HG=F",
    }
    FUTURES_DELAYED_PROXY_TICKERS = {
        "NQ": "NQ=F",
        "ES": "ES=F",
        "YM": "YM=F",
        "RTY": "RTY=F",
    }
    OFFICIAL_RATE_SERIES = {
        "US2Y": ("DGS2", "US 2Y", "%", "US"),
        "US10Y": ("DGS10", "US 10Y", "%", "US"),
        "US30Y": ("DGS30", "US 30Y", "%", "US"),
    }
    OFFICIAL_MACRO_SERIES = {
        "FEDFUNDS": ("DFF", "Fed Funds", "%", "US"),
        "CPI": ("CPIAUCSL", "CPI", "YoY %", "US"),
        "PPI": ("PPIACO", "PPI", "YoY %", "US"),
        "CREDIT": ("BAMLH0A0HYM2", "Credit spreads", "bps", None),
    }
    US_SECTOR_ETFS = {
        "XLK": "Technology",
        "XLF": "Financials",
        "XLY": "Consumer Discretionary",
        "XLE": "Energy",
        "XLV": "Health Care",
        "XLI": "Industrials",
        "XLP": "Consumer Staples",
        "XLU": "Utilities",
        "XLB": "Materials",
        "XLRE": "Real Estate",
        "XLC": "Communication Services",
    }
    CN_SINA_SYMBOLS = {
        "000001.SH": "sh000001",
        "000001.SS": "sh000001",
        "sh000001": "sh000001",
        "399001.SZ": "sz399001",
        "399006.SZ": "sz399006",
        "000688.SH": "sh000688",
        "000300.SH": "sh000300",
        "000300.SS": "sh000300",
        "000905.SH": "sh000905",
        "000852.SH": "sh000852",
        "899050.BJ": "bj899050",
        "HSI": "rt_hkHSI",
        "HSTECH": "rt_hkHSTECH",
    }

    def get_indices(self, actor: Optional[Dict[str, Any]] = None) -> PanelPayload:
        return self._with_request_quote_memo(
            lambda: self._panel("indices", "IndexTrendsCard", "/api/v1/market-overview/indices", self._fetch_indices, actor)
        )

    def get_volatility(self, actor: Optional[Dict[str, Any]] = None) -> PanelPayload:
        return self._with_request_quote_memo(
            lambda: self._panel("volatility", "VolatilityCard", "/api/v1/market-overview/volatility", self._fetch_volatility, actor)
        )

    def get_sentiment(self, actor: Optional[Dict[str, Any]] = None) -> PanelPayload:
        return self._panel(
            self.OVERVIEW_SENTIMENT_CACHE_KEY,
            "MarketSentimentCard",
            "/api/v1/market-overview/sentiment",
            self._fetch_sentiment,
            actor,
        )

    def get_funds_flow(self, actor: Optional[Dict[str, Any]] = None) -> PanelPayload:
        return self._with_request_quote_memo(
            lambda: self._panel("funds_flow", "FundsFlowCard", "/api/v1/market-overview/funds-flow", self._fetch_funds_flow, actor)
        )

    def get_macro(self, actor: Optional[Dict[str, Any]] = None) -> PanelPayload:
        return self._with_request_quote_memo(
            lambda: self._panel("macro", "MacroIndicatorsCard", "/api/v1/market-overview/macro", self._fetch_macro, actor)
        )

    def get_crypto(self, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._market_snapshot(
            cache_key="crypto",
            panel_name="CryptoCard",
            endpoint_url="/api/v1/market/crypto",
            fetcher=self._fetch_crypto_market_snapshot,
            fallback_factory=self._fallback_crypto_market_snapshot,
            actor=actor,
        )

    def get_market_sentiment(self, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._market_snapshot(
            cache_key=self.MARKET_SENTIMENT_CACHE_KEY,
            panel_name="MarketSentimentCard",
            endpoint_url="/api/v1/market/sentiment",
            fetcher=self._fetch_market_sentiment_snapshot,
            fallback_factory=lambda: self._fallback_market_snapshot(self.MARKET_SENTIMENT_CACHE_KEY, "unavailable"),
            actor=actor,
        )

    def get_cn_indices(self, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._classified_snapshot(
            cache_key="cn_indices",
            panel_name="ChinaIndicesCard",
            endpoint_url="/api/v1/market/cn-indices",
            fetcher=self._fetch_cn_indices_snapshot,
            fallback_factory=self._fallback_cn_indices_snapshot,
            actor=actor,
        )

    def get_cn_breadth(self, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._classified_snapshot(
            cache_key="cn_breadth",
            panel_name="ChinaBreadthCard",
            endpoint_url="/api/v1/market/cn-breadth",
            fetcher=self._fetch_cn_breadth_snapshot,
            fallback_factory=self._fallback_cn_breadth_snapshot,
            actor=actor,
        )

    def get_cn_flows(self, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._classified_snapshot(
            cache_key="cn_flows",
            panel_name="ChinaFlowsCard",
            endpoint_url="/api/v1/market/cn-flows",
            fetcher=self._fetch_cn_flows_snapshot,
            fallback_factory=self._fallback_cn_flows_snapshot,
            actor=actor,
        )

    def get_sector_rotation(self, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._classified_snapshot(
            cache_key="sector_rotation",
            panel_name="SectorRotationCard",
            endpoint_url="/api/v1/market/sector-rotation",
            fetcher=self._fetch_sector_rotation_snapshot,
            fallback_factory=self._fallback_sector_rotation_snapshot,
            actor=actor,
        )

    def get_us_breadth(self, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._with_request_quote_memo(
            lambda: self._classified_snapshot(
                cache_key="us_breadth",
                panel_name="UsBreadthCard",
                endpoint_url="/api/v1/market/us-breadth",
                fetcher=self._fetch_us_breadth_snapshot,
                fallback_factory=self._fallback_us_breadth_snapshot,
                actor=actor,
            )
        )

    def get_rates(self, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._classified_snapshot(
            cache_key="rates",
            panel_name="RatesCard",
            endpoint_url="/api/v1/market/rates",
            fetcher=self._fetch_rates_snapshot,
            fallback_factory=self._fallback_rates_snapshot,
            actor=actor,
        )

    def get_fx_commodities(self, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._classified_snapshot(
            cache_key="fx_commodities",
            panel_name="FxCommoditiesCard",
            endpoint_url="/api/v1/market/fx-commodities",
            fetcher=self._fetch_fx_commodities_snapshot,
            fallback_factory=self._fallback_fx_commodities_snapshot,
            actor=actor,
        )

    def get_market_temperature(self, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        def fetcher() -> Dict[str, Any]:
            inputs = self._get_market_temperature_input_snapshot()
            trust = self._market_temperature_trust(
                inputs,
                self._summarize_market_temperature_confidence(inputs),
            )
            source = "computed" if trust["isReliable"] and not trust["fallbackInputCount"] else "mixed"
            if trust["reliableInputCount"] == 0:
                source = "fallback"
            scores = (
                self._compute_market_temperature_scores(self._real_market_temperature_inputs(inputs))
                if trust["isReliable"]
                else self._insufficient_market_temperature_scores()
            )
            payload = {
                "source": source,
                "updatedAt": _now_iso(),
                "scores": scores,
                **trust,
            }
            if not trust["isReliable"]:
                payload["warning"] = INSUFFICIENT_MARKET_DATA_WARNING
                payload["fallbackUsed"] = True
                payload["isFallback"] = trust["reliableInputCount"] == 0
                payload["freshness"] = "fallback" if trust["reliableInputCount"] == 0 else "stale"
            elif trust["fallbackInputCount"]:
                payload["warning"] = "部分指标来自备用数据，评分仅使用真实数据。"
                payload["fallbackUsed"] = True
            return payload

        def fallback_factory() -> Dict[str, Any]:
            inputs = self._fallback_market_temperature_inputs()
            trust = self._market_temperature_trust(
                inputs,
                self._summarize_market_temperature_confidence(inputs),
            )
            return {
                "source": "fallback",
                "updatedAt": _now_iso(),
                "scores": self._insufficient_market_temperature_scores(),
                "warning": INSUFFICIENT_MARKET_DATA_WARNING,
                "fallbackUsed": True,
                "isFallback": True,
                "freshness": "fallback",
                **trust,
            }

        started_at = time.monotonic()
        payload = self._cached_payload("temperature", fetcher, fallback_factory)
        payload = self._with_market_meta(payload, self._category_for_cache_key("temperature"))
        payload["providerHealth"] = self._provider_health(payload, "temperature", duration_ms=int((time.monotonic() - started_at) * 1000), error_summary=_compact_error_summary(payload.get("lastError")))
        payload = self._with_evidence_snapshot(payload, self._category_for_cache_key("temperature"))
        return payload

    def get_market_briefing(self, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        def fetcher() -> Dict[str, Any]:
            inputs = self._get_market_temperature_input_snapshot()
            trust = self._summarize_market_temperature_confidence(inputs)
            briefing_trust = self._market_briefing_trust(inputs, trust)
            source = "computed" if briefing_trust["isReliable"] and not trust["fallbackInputCount"] else "mixed"
            if trust["reliableInputCount"] == 0:
                source = "fallback"
            real_inputs = self._real_market_temperature_inputs(inputs)
            scores = self._compute_market_temperature_scores(real_inputs) if briefing_trust["isReliable"] else self._insufficient_market_temperature_scores()
            payload = {
                "source": source,
                "updatedAt": _now_iso(),
                "items": self._build_market_briefing_items(real_inputs if briefing_trust["isReliable"] else inputs, scores, source, briefing_trust),
                **briefing_trust,
            }
            if not briefing_trust["isReliable"]:
                payload["warning"] = "当前真实数据不足，暂不生成强市场判断。"
                payload["fallbackUsed"] = True
                payload["isFallback"] = trust["reliableInputCount"] == 0
                payload["freshness"] = "fallback" if trust["reliableInputCount"] == 0 else "stale"
            elif trust["fallbackInputCount"]:
                payload["warning"] = "部分解读已排除备用数据。"
                payload["fallbackUsed"] = True
            return payload

        def fallback_factory() -> Dict[str, Any]:
            inputs = self._fallback_market_temperature_inputs()
            trust = self._summarize_market_temperature_confidence(inputs)
            scores = self._insufficient_market_temperature_scores()
            return {
                "source": "fallback",
                "updatedAt": _now_iso(),
                "items": self._build_market_briefing_items(inputs, scores, "fallback", trust),
                "warning": "当前真实数据不足，暂不生成强市场判断。",
                "fallbackUsed": True,
                "isFallback": True,
                "freshness": "fallback",
                **trust,
            }

        started_at = time.monotonic()
        payload = self._cached_payload("market_briefing", fetcher, fallback_factory)
        payload = self._with_market_meta(payload, self._category_for_cache_key("market_briefing"))
        payload["providerHealth"] = self._provider_health(payload, "market_briefing", duration_ms=int((time.monotonic() - started_at) * 1000), error_summary=_compact_error_summary(payload.get("lastError")))
        payload = self._with_evidence_snapshot(payload, self._category_for_cache_key("market_briefing"))
        return payload

    def _get_market_temperature_input_snapshot(self) -> Dict[str, Any]:
        return self._market_cache.get_or_refresh(
            self.TEMPERATURE_INPUT_SNAPSHOT_CACHE_KEY,
            self._market_temperature_input_snapshot_ttl_seconds(),
            self._build_market_temperature_inputs,
            fallback_factory=None,
            allow_stale=False,
            background_refresh=False,
        )

    def get_futures(self, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        started_at = time.monotonic()
        payload = self._cached_payload(
            "futures",
            self._fetch_futures_snapshot,
            self._fallback_futures_snapshot,
        )
        payload.setdefault("source", "public")
        payload.setdefault("updatedAt", _now_iso())
        payload.setdefault("items", [])
        if not payload["items"]:
            payload = self._fallback_futures_snapshot()
        payload = self._with_market_meta(payload, "futures")
        payload["items"] = [self._with_item_meta(item, "futures", payload) for item in payload.get("items", [])]
        payload["providerHealth"] = self._provider_health(payload, "futures", duration_ms=int((time.monotonic() - started_at) * 1000), error_summary=_compact_error_summary(payload.get("lastError")))
        payload = self._with_evidence_snapshot(payload, "futures")
        return payload

    def get_cn_short_sentiment(self, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        started_at = time.monotonic()
        payload = self._cached_payload(
            "cn_short_sentiment",
            self._fetch_cn_short_sentiment_snapshot,
            self._fallback_cn_short_sentiment_snapshot,
        )
        payload.setdefault("source", "public")
        payload.setdefault("updatedAt", _now_iso())
        payload = self._with_market_meta(payload, self._category_for_cache_key("cn_short_sentiment"))
        payload["providerHealth"] = self._provider_health(payload, "cn_short_sentiment", duration_ms=int((time.monotonic() - started_at) * 1000), error_summary=_compact_error_summary(payload.get("lastError")))
        payload = self._with_evidence_snapshot(payload, self._category_for_cache_key("cn_short_sentiment"))
        return payload

    def _panel(
        self,
        cache_key: str,
        panel_name: str,
        endpoint_url: str,
        fetcher: Callable[[], PanelPayload],
        actor: Optional[Dict[str, Any]],
    ) -> PanelPayload:
        started_at = time.monotonic()
        status = "success"
        snapshot = self._cached_payload(
            cache_key,
            fetcher,
            lambda: self._fallback_overview_panel(cache_key, panel_name, "数据源刷新超时，当前显示备用快照"),
        )
        duration_ms = int((time.monotonic() - started_at) * 1000)
        error_message = _compact_error_summary(snapshot.get("lastError") or snapshot.get("error_message"))
        if error_message:
            status = "failure"
            snapshot["error_message"] = error_message
            raw_response: Dict[str, Any] = {"cache": "stale_or_fallback", "error": error_message}
        elif snapshot.get("isRefreshing"):
            raw_response = {"cache": "stale_refreshing"}
        else:
            raw_response = {"cache": "hit_or_refreshed"}

        snapshot["panel_name"] = panel_name
        snapshot["status"] = status
        snapshot.setdefault("last_refresh_at", snapshot.get("updatedAt") or _now_iso())
        snapshot.setdefault("updatedAt", snapshot["last_refresh_at"])
        snapshot.setdefault("source", "fallback" if snapshot.get("fallbackUsed") or snapshot.get("fallback_used") else "cached")
        snapshot.setdefault("items", [])
        snapshot = self._with_market_meta(snapshot, self._category_for_cache_key(cache_key))
        snapshot["items"] = [self._with_item_meta(item, self._category_for_cache_key(cache_key), snapshot) for item in snapshot.get("items", [])]
        snapshot["providerHealth"] = self._provider_health(snapshot, cache_key, duration_ms=duration_ms, error_summary=error_message)
        snapshot = self._with_evidence_snapshot(snapshot, self._category_for_cache_key(cache_key))
        raw_response.update(self._provider_log_meta(snapshot, cache_key, duration_ms=duration_ms, error_summary=error_message))
        log_session_id = ExecutionLogService().record_market_overview_fetch(
            panel_name=panel_name,
            endpoint_url=endpoint_url,
            status=status,
            fetch_timestamp=snapshot["last_refresh_at"],
            error_message=error_message,
            raw_response=raw_response if status == "failure" else {"response": snapshot, **raw_response},
            actor=actor,
        )
        snapshot["log_session_id"] = log_session_id
        return snapshot

    def _market_snapshot(
        self,
        cache_key: str,
        panel_name: str,
        endpoint_url: str,
        fetcher: Callable[[], Dict[str, Any]],
        fallback_factory: Callable[[], Dict[str, Any]],
        actor: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        started_at = time.monotonic()
        error_message = None
        status = "success"
        snapshot = self._cached_payload(cache_key, fetcher, fallback_factory)
        duration_ms = int((time.monotonic() - started_at) * 1000)
        if snapshot.get("lastError"):
            status = "failure"
            error_message = _compact_error_summary(snapshot.get("lastError"))
            snapshot["error"] = "更新失败：已回退到最近一次有效数据"
            if str(snapshot.get("source") or "").lower() not in {"fallback", "mock", "unavailable"}:
                snapshot["fallback_used"] = True
            raw_response: Dict[str, Any] = {"cache": "stale_or_fallback", "error": error_message}
        elif snapshot.get("isRefreshing"):
            raw_response = {"cache": "stale_refreshing"}
        else:
            raw_response = {"cache": "hit_or_refreshed"}

        snapshot.setdefault("last_update", _now_iso())
        snapshot.setdefault("updatedAt", snapshot["last_update"])
        snapshot.setdefault("error", error_message)
        snapshot.setdefault("fallback_used", bool(snapshot.get("fallbackUsed") or snapshot.get("isFallback")))
        snapshot = self._with_market_meta(snapshot, self._category_for_cache_key(cache_key))
        snapshot["items"] = [self._with_item_meta(item, self._category_for_cache_key(cache_key), snapshot) for item in snapshot.get("items", [])]
        snapshot["providerHealth"] = self._provider_health(snapshot, cache_key, duration_ms=duration_ms, error_summary=error_message)
        snapshot = self._with_evidence_snapshot(snapshot, self._category_for_cache_key(cache_key))
        raw_response.update(self._provider_log_meta(snapshot, cache_key, duration_ms=duration_ms, error_summary=error_message))
        log_session_id = ExecutionLogService().record_market_overview_fetch(
            panel_name=panel_name,
            endpoint_url=endpoint_url,
            status=status,
            fetch_timestamp=snapshot["last_update"],
            error_message=error_message,
            raw_response=raw_response if status == "failure" else {"response": snapshot, **raw_response},
            actor=actor,
        )
        snapshot["log_session_id"] = log_session_id
        return snapshot

    def _classified_snapshot(
        self,
        cache_key: str,
        panel_name: str,
        endpoint_url: str,
        fetcher: Callable[[], Dict[str, Any]],
        fallback_factory: Callable[[], Dict[str, Any]],
        actor: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        started_at = time.monotonic()
        status = "success"
        snapshot = self._cached_payload(cache_key, fetcher, fallback_factory)
        duration_ms = int((time.monotonic() - started_at) * 1000)
        error_message = _compact_error_summary(snapshot.get("lastError"))
        if error_message:
            status = "failure"
            snapshot["error"] = "更新失败：已回退到可用市场快照"
            raw_response: Dict[str, Any] = {"cache": "stale_or_fallback", "error": error_message}
        elif snapshot.get("isRefreshing"):
            raw_response = {"cache": "stale_refreshing"}
        else:
            raw_response = {"cache": "hit_or_refreshed"}

        snapshot.setdefault("panelName", panel_name)
        snapshot.setdefault("updatedAt", _now_iso())
        snapshot.setdefault("source", "fallback" if snapshot.get("fallbackUsed") else "mixed")
        snapshot.setdefault("items", [])
        snapshot = self._with_market_meta(snapshot, self._category_for_cache_key(cache_key))
        snapshot["items"] = [self._with_item_meta(item, self._category_for_cache_key(cache_key), snapshot) for item in snapshot.get("items", [])]
        snapshot["providerHealth"] = self._provider_health(snapshot, cache_key, duration_ms=duration_ms, error_summary=error_message)
        snapshot = self._with_evidence_snapshot(snapshot, self._category_for_cache_key(cache_key))
        raw_response.update(self._provider_log_meta(snapshot, cache_key, duration_ms=duration_ms, error_summary=error_message))
        log_session_id = ExecutionLogService().record_market_overview_fetch(
            panel_name=panel_name,
            endpoint_url=endpoint_url,
            status=status,
            fetch_timestamp=snapshot["updatedAt"],
            error_message=error_message,
            raw_response=raw_response if status == "failure" else {"response": snapshot, **raw_response},
            actor=actor,
        )
        snapshot["logSessionId"] = log_session_id
        return snapshot

    def _cached_payload(
        self,
        cache_key: str,
        fetcher: Callable[[], Dict[str, Any]],
        fallback_factory: Callable[[], Dict[str, Any]],
    ) -> Dict[str, Any]:
        ttl_seconds = self._ttl_for_cache_key(cache_key)

        def store_success() -> Dict[str, Any]:
            payload = fetcher()
            if self._is_fallback_only_market_snapshot(payload):
                raise RuntimeError("market provider unavailable")
            if not self._is_storable_market_snapshot(payload):
                raise RuntimeError("market provider returned no usable data")
            snapshot_payload = copy.deepcopy(payload)
            self._market_data_cache[cache_key] = snapshot_payload
            self._save_persistent_snapshot(cache_key, snapshot_payload)
            return payload

        def fallback() -> Dict[str, Any]:
            cached = self._market_data_cache.get(cache_key)
            if cached:
                payload = copy.deepcopy(cached)
                payload["fallbackUsed"] = True
                return payload
            persistent = self._load_persistent_snapshot(cache_key)
            if persistent:
                return persistent
            return fallback_factory()

        return self._market_cache.get_or_refresh(
            cache_key,
            ttl_seconds,
            store_success,
            fallback_factory=fallback,
            allow_stale=True,
            background_refresh=True,
            cold_start_timeout_seconds=self.MARKET_COLD_START_TIMEOUT_SECONDS,
        )

    def _snapshot_key(self, cache_key: str) -> str:
        return f"market_overview:{cache_key}"

    def _persistent_snapshot_lookup_keys(self, cache_key: str) -> List[str]:
        if cache_key in {self.OVERVIEW_SENTIMENT_CACHE_KEY, self.MARKET_SENTIMENT_CACHE_KEY}:
            return [cache_key, self.LEGACY_SHARED_SENTIMENT_CACHE_KEY]
        return [cache_key]

    @staticmethod
    def _is_market_sentiment_item(item: Dict[str, Any]) -> bool:
        return any(item.get(key) is not None for key in ("price", "change", "change_text"))

    @staticmethod
    def _is_overview_sentiment_item(item: Dict[str, Any]) -> bool:
        return any(item.get(key) is not None for key in ("value", "change_pct"))

    def _normalize_sentiment_snapshot_payload(self, cache_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if cache_key == self.MARKET_SENTIMENT_CACHE_KEY:
            return self._normalize_market_sentiment_snapshot_payload(payload)
        if cache_key == self.OVERVIEW_SENTIMENT_CACHE_KEY:
            return self._normalize_overview_sentiment_panel_payload(payload)
        return payload

    def _normalize_market_sentiment_snapshot_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        items = [item for item in payload.get("items", []) if isinstance(item, dict)]
        if items and all(self._is_market_sentiment_item(item) for item in items):
            return payload
        updated_at = payload.get("last_update") or payload.get("updatedAt") or payload.get("last_refresh_at") or _now_iso()
        if items and all(self._is_overview_sentiment_item(item) for item in items):
            return {
                "items": [
                    {
                        "symbol": item.get("symbol"),
                        "label": item.get("label") or item.get("symbol"),
                        "price": self._clean_number(item.get("value")),
                        "change": self._clean_number(item.get("change_pct")),
                        "change_text": item.get("change_text"),
                        "trend": item.get("trend") or [],
                        "hover_details": item.get("hover_details") or [],
                        "risk_direction": item.get("risk_direction"),
                        "unit": item.get("unit"),
                        "source": item.get("source"),
                        "last_update": item.get("last_update") or item.get("updatedAt") or updated_at,
                        "error": item.get("error"),
                    }
                    for item in items
                ],
                "last_update": updated_at,
                "updatedAt": payload.get("updatedAt") or updated_at,
                "error": payload.get("error") or payload.get("error_message"),
                "fallback_used": bool(payload.get("fallback_used") or payload.get("fallbackUsed") or payload.get("isFallback")),
                "source": payload.get("source") or "cached",
            }
        return {
            "items": [],
            "last_update": updated_at,
            "updatedAt": payload.get("updatedAt") or updated_at,
            "error": payload.get("error") or payload.get("error_message"),
            "scores": payload.get("scores"),
            "metrics": payload.get("metrics"),
            "fallback_used": bool(payload.get("fallback_used") or payload.get("fallbackUsed") or payload.get("isFallback")),
            "source": payload.get("source") or "cached",
        }

    def _normalize_overview_sentiment_panel_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        items = [item for item in payload.get("items", []) if isinstance(item, dict)]
        if items and all(self._is_overview_sentiment_item(item) for item in items):
            return payload
        updated_at = payload.get("last_refresh_at") or payload.get("updatedAt") or payload.get("last_update") or _now_iso()
        if items and all(self._is_market_sentiment_item(item) for item in items):
            return {
                "items": [
                    {
                        "symbol": item.get("symbol"),
                        "label": item.get("label") or item.get("symbol"),
                        "value": self._clean_number(item.get("price")),
                        "unit": item.get("unit"),
                        "change_pct": self._clean_number(item.get("change")),
                        "change_text": item.get("change_text"),
                        "risk_direction": item.get("risk_direction"),
                        "trend": item.get("trend") or [],
                        "hover_details": item.get("hover_details") or [],
                        "source": item.get("source"),
                    }
                    for item in items
                ],
                "last_refresh_at": updated_at,
                "updatedAt": payload.get("updatedAt") or updated_at,
                "error_message": payload.get("error"),
                "source": payload.get("source") or "cached",
            }
        return {
            "items": [],
            "last_refresh_at": updated_at,
            "updatedAt": payload.get("updatedAt") or updated_at,
            "error_message": payload.get("error") or payload.get("error_message"),
            "source": payload.get("source") or "cached",
        }

    def _is_storable_market_snapshot(self, payload: Dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return False
        if payload.get("error") and not payload.get("items"):
            return False
        if str(payload.get("source") or "").lower() == "error":
            return False
        if str(payload.get("freshness") or "").lower() == "error":
            return False
        items = payload.get("items")
        has_items = isinstance(items, list) and len(items) > 0
        has_value = any(payload.get(key) is not None for key in ("value", "price", "sentimentScore", "scores", "metrics"))
        return bool(has_items or has_value)

    def _is_fallback_only_market_snapshot(self, payload: Dict[str, Any]) -> bool:
        source = str(payload.get("source") or "").lower()
        freshness = str(payload.get("freshness") or "").lower()
        if payload.get("isFallback") or source in {"fallback", "mock", "unavailable"} or freshness in {"fallback", "mock"}:
            return True
        items = [item for item in payload.get("items", []) if isinstance(item, dict)]
        if not items:
            return False
        return all(
            item.get("isFallback")
            or item.get("fallbackUsed")
            or item.get("isUnavailable")
            or str(item.get("source") or "").lower() in {"fallback", "mock", "unavailable"}
            or str(item.get("freshness") or "").lower() in {"fallback", "mock", "unavailable", "error"}
            for item in items
        )

    def _save_persistent_snapshot(self, cache_key: str, payload: Dict[str, Any]) -> None:
        try:
            if os.environ.get("PYTEST_CURRENT_TEST") and os.environ.get("MARKET_OVERVIEW_SNAPSHOT_TEST_DB") != "1":
                return
            DatabaseManager.get_instance().save_market_overview_snapshot(
                key=self._snapshot_key(cache_key),
                payload=payload,
            )
        except Exception:
            return

    def _load_persistent_snapshot(self, cache_key: str) -> Optional[Dict[str, Any]]:
        try:
            if os.environ.get("PYTEST_CURRENT_TEST") and os.environ.get("MARKET_OVERVIEW_SNAPSHOT_TEST_DB") != "1":
                return None
            row = None
            for snapshot_cache_key in self._persistent_snapshot_lookup_keys(cache_key):
                row = DatabaseManager.get_instance().get_market_overview_snapshot(self._snapshot_key(snapshot_cache_key))
                if row and isinstance(row.get("payload"), dict):
                    break
        except Exception:
            return None
        if not row or not isinstance(row.get("payload"), dict):
            return None
        payload = copy.deepcopy(row["payload"])
        payload = self._normalize_sentiment_snapshot_payload(cache_key, payload)
        if not self._is_storable_market_snapshot(payload):
            return None
        last_successful_at = (
            payload.get("asOf")
            or payload.get("updatedAt")
            or payload.get("last_update")
            or payload.get("last_refresh_at")
            or row.get("as_of")
            or row.get("updated_at")
        )
        snapshot_was_fallback = bool(
            payload.get("isFallback")
            or payload.get("fallbackUsed")
            or payload.get("fallback_used")
            or str(payload.get("source") or "").lower() in {"fallback", "mock"}
            or str(row.get("source") or "").lower() in {"fallback", "mock"}
        )
        payload["isFromSnapshot"] = True
        payload["isStale"] = True
        payload["lastSuccessfulAt"] = last_successful_at
        payload["updatedAt"] = payload.get("updatedAt") or row.get("updated_at") or _now_iso()
        payload["asOf"] = payload.get("asOf") or last_successful_at
        payload["sourceLabel"] = payload.get("sourceLabel") or "Snapshot"
        payload["source"] = payload.get("source") or "cached"
        payload["freshness"] = "fallback" if snapshot_was_fallback else "stale"
        payload["isFallback"] = snapshot_was_fallback
        payload["fallbackUsed"] = bool(payload.get("fallbackUsed") or snapshot_was_fallback)
        payload["warning"] = "数据源刷新失败，当前显示最近成功快照"
        items = payload.get("items")
        if isinstance(items, list):
            payload["items"] = [
                {
                    **item,
                    "isFromSnapshot": True,
                    "isStale": True,
                    "freshness": "fallback" if (
                        item.get("isFallback")
                        or item.get("fallbackUsed")
                        or str(item.get("source") or "").lower() in {"fallback", "mock"}
                    ) else "stale",
                }
                if isinstance(item, dict)
                else item
                for item in items
            ]
        return payload

    def _fallback_market_snapshot(self, cache_key: str, source: str) -> Dict[str, Any]:
        cached = self._market_data_cache.get(cache_key)
        if cached:
            payload = dict(cached)
            payload["fallback_used"] = True
            return payload
        updated_at = _now_iso()
        return {
            "items": [],
            "last_update": updated_at,
            "updatedAt": updated_at,
            "asOf": updated_at,
            "error": None,
            "fallback_used": True,
            "fallbackUsed": True,
            "isFallback": True,
            "freshness": "fallback",
            "source": source,
            "sourceLabel": self._source_label(source),
        }

    def _fallback_crypto_market_snapshot(self) -> Dict[str, Any]:
        cached = self._market_data_cache.get("crypto")
        if cached:
            payload = dict(cached)
            payload["fallback_used"] = True
            payload["fallbackUsed"] = True
            return payload

        updated_at = _now_iso()
        fallback_items = [
            ("BTC", "Bitcoin", 75800.0, -0.2, [75220.0, 75640.0, 76110.0, 75800.0]),
            ("ETH", "Ethereum", 3120.0, -0.4, [3090.0, 3148.0, 3162.0, 3120.0]),
            ("SOL", "Solana", 143.2, 0.0, [140.0, 141.0, 142.0, 143.2]),
            ("BNB", "BNB", 590.0, 0.3, [584.0, 588.0, 586.0, 590.0]),
        ]
        return {
            "items": [
                {
                    "symbol": symbol,
                    "name": name,
                    "label": name,
                    "value": value,
                    "price": value,
                    "changePercent": change_percent,
                    "change": change_percent,
                    "sparkline": sparkline,
                    "trend": sparkline,
                    "unit": "USD",
                    "risk_direction": self._risk_direction(change_percent),
                    "source": "fallback",
                    "sourceLabel": "备用数据",
                    "updatedAt": updated_at,
                    "asOf": updated_at,
                    "last_update": updated_at,
                    "freshness": "fallback",
                    "isFallback": True,
                    "warning": "正在获取实时加密货币行情，当前显示备用快照",
                }
                for symbol, name, value, change_percent, sparkline in fallback_items
            ] + self._crypto_funding_unavailable_items(updated_at) + self._crypto_unavailable_context_items(updated_at),
            "last_update": updated_at,
            "updatedAt": updated_at,
            "asOf": updated_at,
            "error": None,
            "fallback_used": True,
            "fallbackUsed": True,
            "isFallback": True,
            "isRefreshing": True,
            "freshness": "fallback",
            "source": "fallback",
            "sourceLabel": "备用数据",
            "warning": "正在获取实时加密货币行情，当前显示备用快照",
        }

    def _ttl_for_cache_key(self, cache_key: str) -> int:
        ttl_key = {
            "cn_breadth": "breadth",
            "us_breadth": "breadth",
            "cn_flows": "flows",
            "fx_commodities": "fx_commodity",
            "cn_short_sentiment": "sentiment",
            self.OVERVIEW_SENTIMENT_CACHE_KEY: "sentiment",
            self.MARKET_SENTIMENT_CACHE_KEY: "sentiment",
        }.get(cache_key, cache_key)
        return MARKET_CACHE_TTLS.get(ttl_key, self.CACHE_TTL_SECONDS)

    def _market_temperature_input_snapshot_ttl_seconds(self) -> int:
        # Keep the shared bundle no fresher than the fastest-moving panel it contains.
        return min(
            self._ttl_for_cache_key("crypto"),
            self._ttl_for_cache_key("futures"),
            self._ttl_for_cache_key("cn_indices"),
            self._ttl_for_cache_key("cn_breadth"),
            self._ttl_for_cache_key("cn_flows"),
            self._ttl_for_cache_key("sector_rotation"),
            self._ttl_for_cache_key("rates"),
            self._ttl_for_cache_key("fx_commodities"),
            self._ttl_for_cache_key("volatility"),
            self._ttl_for_cache_key(self.MARKET_SENTIMENT_CACHE_KEY),
        )

    def _category_for_cache_key(self, cache_key: str) -> str:
        mapping = {
            "indices": "equity_index",
            "volatility": "futures",
            "crypto": "crypto",
            "sentiment": "sentiment",
            self.OVERVIEW_SENTIMENT_CACHE_KEY: "sentiment",
            self.MARKET_SENTIMENT_CACHE_KEY: "sentiment",
            "funds_flow": "flows",
            "macro": "macro_rate",
            "cn_indices": "equity_index",
            "cn_breadth": "breadth",
            "us_breadth": "breadth",
            "cn_flows": "flows",
            "sector_rotation": "sector_rotation",
            "rates": "macro_rate",
            "fx_commodities": "fx_commodity",
            "temperature": "sentiment",
            "market_briefing": "sentiment",
            "futures": "futures",
            "cn_short_sentiment": "sentiment",
        }
        return mapping.get(cache_key, "equity_index")

    def _source_label(self, source: Any) -> str:
        return SOURCE_LABELS.get(str(source or "").lower(), str(source or "公开数据"))

    @staticmethod
    def _deadline_after(seconds: float) -> float:
        return time.monotonic() + max(0.0, float(seconds))

    @staticmethod
    def _deadline_remaining(deadline: float) -> float:
        return max(0.0, deadline - time.monotonic())

    def _deadline_exhausted(self, deadline: float) -> bool:
        return self._deadline_remaining(deadline) <= 0

    def _deadline_timeout(self, deadline: float, per_call_timeout: float) -> Optional[float]:
        remaining = self._deadline_remaining(deadline)
        if remaining <= 0:
            return None
        return min(max(0.001, float(per_call_timeout)), remaining)

    def _with_request_quote_memo(self, callback: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
        if self._quote_request_memo is not None:
            return callback()
        self._quote_request_memo = {}
        try:
            return callback()
        finally:
            self._quote_request_memo = None

    def _provider_health_status(self, payload: Dict[str, Any]) -> str:
        source = str(payload.get("source") or "").lower()
        freshness = str(payload.get("freshness") or "").lower()
        items = [item for item in payload.get("items", []) if isinstance(item, dict)]
        fallback_items = [
            item for item in items
            if item.get("isFallback")
            or item.get("fallbackUsed")
            or item.get("isUnavailable")
            or str(item.get("source") or "").lower() in {"fallback", "mock", "unavailable"}
            or str(item.get("freshness") or "").lower() in {"fallback", "mock", "unavailable", "error"}
        ]
        real_items = [item for item in items if item not in fallback_items]
        has_error = bool(payload.get("lastError") or payload.get("refreshError") or payload.get("error"))
        if payload.get("isRefreshing") and (payload.get("lastError") or payload.get("refreshError")) and (payload.get("isStale") or payload.get("isFromSnapshot")):
            return "stale"
        if payload.get("isRefreshing"):
            return "refreshing"
        if source == "unavailable" or (not items and freshness in {"fallback", "error"}):
            return "unavailable"
        if has_error and (payload.get("isStale") or payload.get("isFromSnapshot")) and items:
            return "stale"
        if has_error and not items:
            return "error"
        if real_items and fallback_items:
            return "partial"
        if payload.get("isFallback") or freshness in {"fallback", "mock"} or source in {"fallback", "mock"}:
            return "fallback"
        if payload.get("fallbackUsed") and real_items:
            return "partial"
        if payload.get("isStale") or freshness == "stale":
            return "stale"
        if freshness in {"cached", "delayed"}:
            return "cache"
        if freshness == "live":
            return "live"
        return "cache"

    def _provider_health(
        self,
        payload: Dict[str, Any],
        cache_key: str,
        *,
        duration_ms: Optional[int],
        error_summary: Optional[str],
    ) -> Dict[str, Any]:
        source = str(payload.get("source") or "public")
        status = self._provider_health_status(payload)
        return {
            "provider": source,
            "status": status if status in PROVIDER_HEALTH_STATUSES else "cache",
            "asOf": payload.get("asOf"),
            "updatedAt": payload.get("updatedAt") or payload.get("last_update") or payload.get("last_refresh_at"),
            "latencyMs": duration_ms if isinstance(duration_ms, int) and duration_ms >= 0 else None,
            "errorSummary": error_summary,
            "isFallback": bool(payload.get("isFallback") or status == "fallback"),
            "isStale": bool(payload.get("isStale") or status == "stale"),
            "isRefreshing": bool(payload.get("isRefreshing") or status == "refreshing"),
            "sourceLabel": payload.get("sourceLabel") or self._source_label(source),
            "card": cache_key,
        }

    def _provider_log_meta(
        self,
        payload: Dict[str, Any],
        cache_key: str,
        *,
        duration_ms: Optional[int],
        error_summary: Optional[str],
    ) -> Dict[str, Any]:
        health = payload.get("providerHealth") if isinstance(payload.get("providerHealth"), dict) else self._provider_health(
            payload,
            cache_key,
            duration_ms=duration_ms,
            error_summary=error_summary,
        )
        status = str(health.get("status") or "")
        if error_summary:
            event_name = "MarketProviderRefreshFailed"
        elif status == "fallback":
            event_name = "MarketProviderFallbackUsed"
        elif status == "stale":
            event_name = "MarketSnapshotServedStale"
        elif status == "partial":
            event_name = "MarketProviderFallbackUsed"
        else:
            event_name = ""
        stale_age = payload.get("delayMinutes") if payload.get("isStale") else None
        return {
            "event_name": event_name or None,
            "card": cache_key,
            "provider": health.get("provider"),
            "source": health.get("provider"),
            "status": status,
            "duration_ms": duration_ms,
            "latency_ms": duration_ms,
            "stale_age_minutes": stale_age,
            "fallbackUsed": bool(payload.get("fallbackUsed") or health.get("isFallback")),
            "isStale": bool(payload.get("isStale") or health.get("isStale")),
            "error": error_summary,
        }

    def _with_evidence_snapshot(self, payload: Dict[str, Any], category: str) -> Dict[str, Any]:
        return {
            **payload,
            "evidenceSnapshot": self._build_evidence_snapshot(payload, category),
        }

    def _build_evidence_snapshot(self, payload: Dict[str, Any], category: str) -> Dict[str, Any]:
        source = str(payload.get("source") or "")
        coverage = self._evidence_snapshot_coverage(payload, category)
        contract = coerce_source_confidence_contract(
            {
                "source": source,
                "sourceLabel": payload.get("sourceLabel") or self._source_label(source),
                "asOf": payload.get("asOf") or payload.get("updatedAt") or payload.get("last_update") or payload.get("last_refresh_at"),
                "freshness": payload.get("freshness"),
                "isFallback": bool(payload.get("isFallback")),
                "isStale": bool(payload.get("isStale")),
                "isPartial": self._is_partial_evidence_snapshot(payload, coverage=coverage, category=category),
                "isUnavailable": self._is_unavailable_evidence_snapshot(payload),
                "confidenceWeight": self._evidence_snapshot_confidence_weight(payload, category),
                "coverage": coverage,
                "degradationReason": payload.get("fallbackReason"),
            }
        )
        evidence = contract.to_dict()
        evidence["coverage"] = round(float(evidence["coverage"]), 2) if isinstance(evidence.get("coverage"), (int, float)) else evidence.get("coverage")
        evidence["confidenceWeight"] = round(float(evidence["confidenceWeight"]), 2)
        return evidence

    def _evidence_snapshot_coverage(self, payload: Dict[str, Any], category: str) -> float:
        explicit_coverage = self._clean_number(payload.get("coverage"))
        if explicit_coverage is not None:
            return round(max(0.0, min(1.0, explicit_coverage)), 2)

        reliable_input_count = self._clean_number(payload.get("reliableInputCount"))
        fallback_input_count = self._clean_number(payload.get("fallbackInputCount"))
        excluded_input_count = self._clean_number(payload.get("excludedInputCount"))
        if any(value is not None for value in (reliable_input_count, fallback_input_count, excluded_input_count)):
            reliable = max(0.0, reliable_input_count or 0.0)
            fallback = max(0.0, fallback_input_count or 0.0)
            excluded = max(0.0, excluded_input_count or 0.0)
            total = reliable + fallback + excluded
            return round(reliable / total, 2) if total > 0 else 0.0

        items = [item for item in payload.get("items", []) if isinstance(item, dict)]
        if items:
            covered_item_count = sum(1 for item in items if self._is_covered_evidence_item(item))
            return round(covered_item_count / len(items), 2)

        if self._is_unavailable_evidence_snapshot(payload):
            return 0.0
        reliability = classify_market_payload_reliability(payload, category)
        return 1.0 if reliability["isReliable"] else 0.0

    def _evidence_snapshot_confidence_weight(self, payload: Dict[str, Any], category: str) -> float:
        explicit_confidence_weight = self._clean_number(payload.get("confidenceWeight"))
        if explicit_confidence_weight is not None:
            return max(0.0, min(1.0, explicit_confidence_weight))

        explicit_confidence = self._clean_number(payload.get("confidence"))
        if explicit_confidence is not None:
            return max(0.0, min(1.0, explicit_confidence))

        items = [item for item in payload.get("items", []) if isinstance(item, dict)]
        if items:
            return round(sum(self._base_evidence_item_confidence(item) for item in items) / len(items), 2)

        reliability = classify_market_payload_reliability(payload, category)
        return max(0.0, min(1.0, float(reliability["confidenceWeight"])))

    def _is_partial_evidence_snapshot(self, payload: Dict[str, Any], *, coverage: float, category: str) -> bool:
        if bool(payload.get("isPartial")):
            return True
        provider_health = payload.get("providerHealth") if isinstance(payload.get("providerHealth"), dict) else {}
        if str(provider_health.get("status") or "").lower() == "partial":
            return True
        if bool(payload.get("isFallback") or payload.get("isStale")) or self._is_unavailable_evidence_snapshot(payload):
            return False
        items = [item for item in payload.get("items", []) if isinstance(item, dict)]
        if items:
            reliable_item_count = sum(1 for item in items if self._market_data_confidence(item, category) > 0)
            return 0 < reliable_item_count < len(items)
        return 0.0 < coverage < 1.0

    def _is_unavailable_evidence_snapshot(self, payload: Dict[str, Any]) -> bool:
        source = str(payload.get("source") or "").lower()
        if source == "unavailable" or bool(payload.get("isUnavailable")):
            return True
        provider_health = payload.get("providerHealth") if isinstance(payload.get("providerHealth"), dict) else {}
        return str(provider_health.get("status") or "").lower() == "unavailable"

    @staticmethod
    def _is_covered_evidence_item(item: Dict[str, Any]) -> bool:
        source = str(item.get("source") or "").lower()
        freshness = str(item.get("freshness") or "").lower()
        if bool(item.get("isFallback") or item.get("fallbackUsed")):
            return False
        if source == "unavailable" or freshness in {"fallback", "mock", "unavailable", "error"}:
            return False
        return _has_valid_market_value(item)

    @staticmethod
    def _base_evidence_item_confidence(item: Dict[str, Any]) -> float:
        source = str(item.get("source") or "").lower()
        freshness = str(item.get("freshness") or "").lower()
        if bool(item.get("isFallback") or item.get("fallbackUsed")):
            return 0.0
        if source == "unavailable" or freshness in {"fallback", "mock", "unavailable", "error"}:
            return 0.0
        if not _has_valid_market_value(item):
            return 0.0
        source_type = _infer_source_type(source, item.get("sourceType"))
        return float(SOURCE_TYPE_CONFIDENCE.get(source_type, 0.0))

    @staticmethod
    def _preserved_freshness_meta(payload: Dict[str, Any]) -> Dict[str, Any]:
        value = payload.get("sourceFreshnessEvidence")
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _apply_preserved_freshness(
        freshness: Dict[str, Any],
        preserved: Dict[str, Any],
    ) -> Dict[str, Any]:
        explicit_freshness = str(preserved.get("freshness") or "").strip().lower()
        if not explicit_freshness:
            return freshness
        is_fallback = bool(preserved.get("isFallback"))
        is_stale = bool(preserved.get("isStale"))
        is_partial = bool(preserved.get("isPartial"))
        is_unavailable = bool(preserved.get("isUnavailable"))
        if is_unavailable and explicit_freshness in {"live", "fresh", "delayed", "cached"}:
            explicit_freshness = "unavailable"
        elif is_fallback and explicit_freshness in {"live", "fresh", "delayed", "cached", "partial"}:
            explicit_freshness = "fallback"
        elif is_stale and explicit_freshness in {"live", "fresh"}:
            explicit_freshness = "stale"
        elif is_partial and explicit_freshness in {"live", "fresh"}:
            explicit_freshness = "partial"
        return {
            **freshness,
            "freshness": explicit_freshness,
            "isFallback": bool(freshness.get("isFallback") or is_fallback or explicit_freshness in {"fallback", "mock"}),
            "isStale": bool(freshness.get("isStale") or is_stale or explicit_freshness == "stale"),
            "warning": preserved.get("warning") or freshness.get("warning"),
        }

    def _with_market_meta(self, payload: Dict[str, Any], category: str) -> Dict[str, Any]:
        source = str(payload.get("source") or ("fallback" if payload.get("fallbackUsed") or payload.get("fallback_used") else "mixed"))
        is_fallback = bool(payload.get("isFallback") or source.lower() in {"fallback", "mock"})
        updated_at = payload.get("updatedAt") or payload.get("last_update") or payload.get("last_refresh_at") or _now_iso()
        as_of = payload.get("asOf") or payload.get("last_update") or payload.get("last_refresh_at") or updated_at
        freshness = get_freshness_status(as_of, category, source, is_fallback, source_type=payload.get("sourceType") or "")
        preserved_freshness = self._preserved_freshness_meta(payload)
        if preserved_freshness:
            freshness = self._apply_preserved_freshness(freshness, preserved_freshness)
        raw_error = payload.get("refreshError") or payload.get("lastError") or payload.get("error")
        if payload.get("isFromSnapshot"):
            snapshot_freshness = str(payload.get("freshness") or "").lower()
            if snapshot_freshness in {"stale", "fallback", "mock", "error"}:
                freshness = {
                    **freshness,
                    "freshness": snapshot_freshness,
                    "isStale": True,
                    "isFallback": bool(is_fallback or snapshot_freshness in {"fallback", "mock"}),
                    "warning": payload.get("warning") or "数据源刷新失败，当前显示最近成功快照",
                }
        reliability = classify_market_payload_reliability({**payload, "source": source, "freshness": freshness["freshness"], "isFallback": freshness["isFallback"]}, category)
        fallback_reason = payload.get("fallbackReason") or _fallback_reason_code(raw_error)
        return {
            **payload,
            "source": source,
            "sourceLabel": payload.get("sourceLabel") or self._source_label(source),
            "sourceType": payload.get("sourceType") or reliability.get("sourceType"),
            "updatedAt": updated_at,
            "asOf": as_of,
            "freshness": freshness["freshness"],
            "isFallback": freshness["isFallback"],
            "isStale": bool(payload.get("isStale") or freshness["isStale"]),
            "isPartial": bool(payload.get("isPartial") or preserved_freshness.get("isPartial") or freshness["freshness"] == "partial"),
            "isUnavailable": bool(payload.get("isUnavailable") or preserved_freshness.get("isUnavailable") or freshness["freshness"] in {"unavailable", "error"}),
            "delayMinutes": freshness["delayMinutes"],
            "warning": payload.get("warning") or (REFRESH_WARNING if payload.get("lastError") else None) or freshness["warning"],
            "fallbackUsed": bool(payload.get("fallbackUsed") or freshness["isFallback"]),
            "fallbackReason": fallback_reason if (bool(payload.get("fallbackUsed") or freshness["isFallback"]) or bool(raw_error) or bool(payload.get("isStale"))) else None,
            "isRefreshing": bool(payload.get("isRefreshing")),
            "lastError": _compact_error_summary(payload.get("lastError")),
            "refreshError": _compact_error_summary(payload.get("refreshError") or payload.get("lastError")),
            "isFromSnapshot": bool(payload.get("isFromSnapshot")),
            "lastSuccessfulAt": payload.get("lastSuccessfulAt"),
        }

    def _source_degradation_reason(self, payload: Dict[str, Any], freshness: str) -> Optional[str]:
        explicit = payload.get("degradationReason") or payload.get("fallbackReason")
        if explicit:
            return str(explicit)
        if bool(payload.get("isUnavailable")) or freshness in {"unavailable", "error"}:
            return "unavailable_source"
        if bool(payload.get("isFallback") or payload.get("fallbackUsed")) or freshness in {"fallback", "mock"}:
            return "fallback_source"
        if bool(payload.get("isStale")) or freshness == "stale":
            return "stale_source"
        if bool(payload.get("isPartial")) or freshness == "partial":
            return "partial_coverage"
        if freshness in {"delayed", "cached"}:
            return "delayed_source"
        return None

    def _source_trust_meta(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        freshness = str(payload.get("freshness") or "").lower()
        degradation_reason = self._source_degradation_reason(payload, freshness)
        explicit_coverage = self._clean_number(payload.get("coverage"))
        coverage = (
            max(0.0, min(1.0, explicit_coverage))
            if explicit_coverage is not None
            else 0.0 if bool(payload.get("isUnavailable")) else 1.0 if _has_valid_market_value(payload) else 0.0
        )
        trust_payload = {
            **payload,
            "freshness": freshness,
            "coverage": coverage,
        }
        if degradation_reason:
            trust_payload["degradationReason"] = degradation_reason
        trust = evaluate_market_intelligence_trust(trust_payload)
        meta = {
            "sourceTier": trust["sourceTier"],
            "trustLevel": trust["trustLevel"],
            "degradationReasons": trust["degradationReasons"],
        }
        if degradation_reason:
            meta["degradationReason"] = degradation_reason
        return meta

    def _with_item_meta(self, item: Dict[str, Any], category: str, panel: Dict[str, Any]) -> Dict[str, Any]:
        source = str(item.get("source") or panel.get("source") or "mixed")
        is_fallback = bool(item.get("isFallback") or item.get("fallbackUsed") or source.lower() in {"fallback", "mock"})
        as_of = item.get("asOf") or item.get("last_update") or item.get("updatedAt") or panel.get("asOf") or panel.get("updatedAt")
        updated_at = item.get("updatedAt") or panel.get("updatedAt") or _now_iso()
        freshness = get_freshness_status(as_of, category, source, is_fallback, source_type=item.get("sourceType") or panel.get("sourceType") or "")
        preserved_freshness = self._preserved_freshness_meta(item)
        if preserved_freshness:
            freshness = self._apply_preserved_freshness(freshness, preserved_freshness)
        if item.get("isFromSnapshot") or panel.get("isFromSnapshot"):
            snapshot_freshness = str(item.get("freshness") or panel.get("freshness") or "").lower()
            if snapshot_freshness in {"stale", "fallback", "mock", "error"}:
                freshness = {
                    **freshness,
                    "freshness": snapshot_freshness,
                    "isStale": True,
                    "isFallback": bool(is_fallback or snapshot_freshness in {"fallback", "mock"}),
                    "warning": item.get("warning") or panel.get("warning") or "数据源刷新失败，当前显示最近成功快照",
                }
        reliability = classify_market_payload_reliability({**item, "source": source, "freshness": freshness["freshness"], "isFallback": freshness["isFallback"]}, category)
        normalized = {
            **item,
            "source": source,
            "sourceLabel": item.get("sourceLabel") or self._source_label(source),
            "sourceType": item.get("sourceType") or reliability.get("sourceType"),
            "updatedAt": updated_at,
            "asOf": as_of,
            "freshness": freshness["freshness"],
            "isFallback": freshness["isFallback"],
            "isStale": freshness["isStale"],
            "isPartial": bool(item.get("isPartial") or preserved_freshness.get("isPartial") or freshness["freshness"] == "partial"),
            "isUnavailable": bool(item.get("isUnavailable") or preserved_freshness.get("isUnavailable") or freshness["freshness"] in {"unavailable", "error"}),
            "delayMinutes": freshness["delayMinutes"],
            "warning": item.get("warning") or freshness["warning"],
            "isFromSnapshot": bool(item.get("isFromSnapshot") or panel.get("isFromSnapshot")),
        }
        return {**normalized, **self._source_trust_meta(normalized)}

    def _fetch_indices(self) -> PanelPayload:
        return self._quote_panel("IndexTrendsCard", self.INDEX_SYMBOLS)

    def _fetch_volatility(self) -> PanelPayload:
        items = self._quote_items(self.VOL_SYMBOLS)
        official_vix = self._official_macro_item(
            "VIX",
            "VIX",
            self._official_macro_points().get("VIXCLS", []),
            unit="pts",
            change_scale=1.0,
        )
        if official_vix:
            replaced_vix = False
            next_items = []
            for item in items:
                if str(item.get("symbol") or "") == "VIX":
                    next_items.append(official_vix)
                    replaced_vix = True
                else:
                    next_items.append(item)
            if not replaced_vix:
                next_items.insert(0, official_vix)
            items = next_items
        try:
            atr_item = self._atr_item()
        except Exception:
            atr_item = None
        if atr_item:
            items.append(atr_item)
        payload = self._success_panel("VolatilityCard", items)
        payload["source"] = "mixed" if official_vix else "yfinance"
        payload["sourceLabel"] = self._source_label(payload["source"])
        payload["fallbackUsed"] = False
        return payload

    def _fetch_sentiment(self) -> PanelPayload:
        snapshot = self._fetch_market_sentiment_snapshot()
        items = []
        for item in snapshot.get("items", []):
            price = self._clean_number(item.get("price"))
            change = self._clean_number(item.get("change"))
            items.append({
                "symbol": item.get("symbol"),
                "label": item.get("label") or item.get("symbol"),
                "value": price,
                "unit": item.get("unit"),
                "change_pct": change,
                "change_text": item.get("change_text"),
                "risk_direction": item.get("risk_direction") or self._risk_direction(change),
                "trend": item.get("trend") or [],
                "hover_details": item.get("hover_details") or [],
                "source": item.get("source") or snapshot.get("source"),
            })
        return {
            "panel_name": "MarketSentimentCard",
            "last_refresh_at": snapshot.get("last_update"),
            "status": "success",
            "error_message": snapshot.get("error"),
            "items": items,
        }

    def _fetch_crypto_market_snapshot(self) -> Dict[str, Any]:
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
        ticker_rows = fetch_binance_ticker_snapshot(symbols)
        history_map = self._fetch_binance_kline_histories(symbols)
        labels = {
            "BTCUSDT": ("BTC", "Bitcoin"),
            "ETHUSDT": ("ETH", "Ethereum"),
            "SOLUSDT": ("SOL", "Solana"),
            "BNBUSDT": ("BNB", "BNB"),
        }
        last_update = _now_iso()
        items = []
        for row in ticker_rows:
            symbol = str(row.get("symbol") or "")
            short_symbol, label = labels[symbol]
            price = self._clean_number(row.get("lastPrice")) or 0.0
            change = self._clean_number(row.get("priceChangePercent")) or 0.0
            quote_volume = self._clean_number(row.get("quoteVolume"))
            high = self._clean_number(row.get("highPrice"))
            low = self._clean_number(row.get("lowPrice"))
            range_percent = self._percent_change(low, high) if high is not None and low is not None else None
            trend = history_map.get(symbol) or [price]
            week_change = self._percent_change(trend[0], trend[-1]) if len(trend) > 1 else None
            items.append({
                "symbol": short_symbol,
                "label": label,
                "price": round(price, 2),
                "change": round(change, 2),
                "change_text": None,
                "trend": [round(value, 2) for value in trend],
                "hover_details": [
                    f"24H {self._signed_percent_text(change)}",
                    f"7D {self._signed_percent_text(week_change)}",
                    f"24H range {self._signed_percent_text(range_percent)}",
                    f"Quote volume {self._compact_usd(quote_volume)}",
                ],
                "risk_direction": self._risk_direction(change),
                "unit": "USD",
                "source": "binance",
                "last_update": last_update,
                "error": None,
            })
        funding_items = self._fetch_binance_funding_items(labels, last_update)
        items.extend(funding_items)
        funding_symbols = {item.get("symbol") for item in funding_items}
        items.extend([
            item for item in self._crypto_funding_unavailable_items(last_update)
            if item.get("symbol") not in funding_symbols
        ])
        items.extend(self._crypto_unavailable_context_items(last_update))
        return {
            "items": items,
            "last_update": last_update,
            "error": None,
            "fallback_used": False,
            "source": "binance",
        }

    def _fetch_binance_kline_histories(self, symbols: List[str]) -> Dict[str, List[float]]:
        if not symbols:
            return {}
        max_workers = min(self.CRYPTO_FANOUT_WORKERS, len(symbols))
        history_by_symbol: Dict[str, List[float]] = {}
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="market-crypto-kline") as executor:
            futures = {
                executor.submit(self._fetch_binance_kline_history, symbol): symbol
                for symbol in symbols
            }
            for future in as_completed(futures):
                symbol = futures[future]
                history_by_symbol[symbol] = future.result()
        return {
            symbol: history_by_symbol[symbol]
            for symbol in symbols
            if symbol in history_by_symbol
        }

    def _fetch_binance_funding_items(self, labels: Dict[str, tuple[str, str]], last_update: str) -> List[Dict[str, Any]]:
        if not labels:
            return []
        max_workers = min(self.CRYPTO_FANOUT_WORKERS, len(labels))
        items_by_symbol: Dict[str, Dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="market-crypto-funding") as executor:
            futures = {
                executor.submit(self._fetch_binance_funding_item, futures_symbol, short_symbol, label, last_update): futures_symbol
                for futures_symbol, (short_symbol, label) in labels.items()
            }
            for future in as_completed(futures):
                futures_symbol = futures[future]
                item = future.result()
                if item:
                    items_by_symbol[futures_symbol] = item
        return [
            items_by_symbol[futures_symbol]
            for futures_symbol in labels
            if futures_symbol in items_by_symbol
        ]

    def _fetch_binance_funding_item(
        self,
        futures_symbol: str,
        short_symbol: str,
        label: str,
        last_update: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            row = fetch_binance_funding_row(futures_symbol)
            funding_rate = self._clean_number(row.get("lastFundingRate"))
        except Exception:
            funding_rate = None
        if funding_rate is None:
            return None
        funding_percent = funding_rate * 100
        return {
            "symbol": f"{short_symbol}_FUNDING",
            "label": f"{short_symbol} Funding",
            "price": round(funding_percent, 4),
            "value": round(funding_percent, 4),
            "change": round(funding_percent, 4),
            "changePercent": round(funding_percent, 4),
            "change_text": f"{funding_percent:+.4f}%",
            "trend": [round(funding_percent, 4)],
            "hover_details": [f"{label} perpetual funding", "Binance Futures public endpoint"],
            "risk_direction": "increasing" if funding_percent > 0.01 else "neutral",
            "unit": "%",
            "source": "binance",
            "last_update": last_update,
            "error": None,
        }


    def _crypto_unavailable_context_items(self, updated_at: str) -> List[Dict[str, Any]]:
        return [
            self._unavailable_item("稳定币流动性", "STABLECOIN_LIQUIDITY", "未接入", updated_at, detail="Stablecoin liquidity：未接入"),
            self._unavailable_item("BTC Dominance", "BTC_DOMINANCE", "未接入", updated_at, detail="Dominance：未接入"),
        ]

    def _crypto_funding_unavailable_items(self, updated_at: str) -> List[Dict[str, Any]]:
        return [
            self._unavailable_item("BTC Funding", "BTC_FUNDING", "暂不可用", updated_at, detail="Bitcoin funding：暂不可用"),
            self._unavailable_item("ETH Funding", "ETH_FUNDING", "暂不可用", updated_at, detail="Ethereum funding：暂不可用"),
            self._unavailable_item("SOL Funding", "SOL_FUNDING", "暂不可用", updated_at, detail="Solana funding：暂不可用"),
            self._unavailable_item("BNB Funding", "BNB_FUNDING", "暂不可用", updated_at, detail="BNB funding：暂不可用"),
        ]

    def _fetch_market_sentiment_snapshot(self) -> Dict[str, Any]:
        provider_error = None
        deadline = self._deadline_after(self.SENTIMENT_AGGREGATE_BUDGET_SECONDS)
        timeout = self._deadline_timeout(deadline, self.SENTIMENT_AGGREGATE_BUDGET_SECONDS)
        if timeout is None:
            raise TimeoutError("sentiment provider deadline exceeded")
        try:
            payload = self._fetch_cnn_fear_greed_snapshot(timeout=timeout)
        except Exception as exc:
            provider_error = str(exc)
            if self._deadline_exhausted(deadline):
                raise TimeoutError("sentiment provider deadline exceeded") from exc
            timeout = self._deadline_timeout(deadline, self.SENTIMENT_AGGREGATE_BUDGET_SECONDS)
            if timeout is None:
                raise TimeoutError("sentiment provider deadline exceeded") from exc
            payload = self._fetch_alternative_fear_greed_snapshot(timeout=timeout)
            payload["source"] = "alternative_me"

        values = [item["value"] for item in payload["history"]]
        current = values[-1]
        previous_day = values[-2] if len(values) > 1 else current
        previous_week = values[0] if len(values) > 1 else current
        day_change = current - previous_day
        week_change = current - previous_week
        current_change_pct = self._percent_change(previous_day, current)
        trend = [round(value, 2) for value in values]
        last_update = _now_iso()

        items = [
            {
                "symbol": "FGI",
                "label": "Fear & Greed",
                "price": round(current, 2),
                "change": round(current_change_pct or 0.0, 2),
                "change_text": f"{day_change:+.0f} pts",
                "trend": trend,
                "hover_details": [
                    f"24H {day_change:+.0f} pts",
                    f"7D {week_change:+.0f} pts",
                ],
                "risk_direction": self._risk_direction(-(current_change_pct or 0.0)),
                "unit": "score",
                "source": payload["source"],
                "last_update": last_update,
                "error": None,
            },
            {
                "symbol": "DAY1",
                "label": "24H Delta",
                "price": round(day_change, 2),
                "change": round(current_change_pct or 0.0, 2),
                "change_text": f"{day_change:+.0f} pts",
                "trend": trend[-4:],
                "hover_details": [f"Current {round(current, 2):.0f}"],
                "risk_direction": self._risk_direction(-day_change),
                "unit": "pts",
                "source": payload["source"],
                "last_update": last_update,
                "error": None,
            },
            {
                "symbol": "DAY7",
                "label": "7D Delta",
                "price": round(week_change, 2),
                "change": round(self._percent_change(previous_week, current) or 0.0, 2),
                "change_text": f"{week_change:+.0f} pts",
                "trend": trend,
                "hover_details": [f"Provider {payload['source']}"],
                "risk_direction": self._risk_direction(-week_change),
                "unit": "pts",
                "source": payload["source"],
                "last_update": last_update,
                "error": None,
            },
        ]
        return {
            "items": items,
            "last_update": last_update,
            "error": provider_error,
            "fallback_used": False,
            "source": payload["source"],
        }

    def _fetch_cnn_fear_greed_snapshot(self, *, timeout: Optional[float] = None) -> Dict[str, Any]:
        payload = (
            fetch_cnn_fear_greed_payload(timeout=timeout)
            if timeout is not None
            else fetch_cnn_fear_greed_payload()
        )
        history_rows = payload.get("fear_and_greed_historical") or payload.get("fear_and_greed")
        if not isinstance(history_rows, list) or not history_rows:
            raise RuntimeError("CNN Fear & Greed payload unavailable")
        history = []
        for row in history_rows[-8:]:
            value = self._clean_number(row.get("score") if isinstance(row, dict) else None)
            if value is not None:
                history.append({"value": value})
        if len(history) < 2:
            raise RuntimeError("CNN Fear & Greed history unavailable")
        return {"history": history, "source": "cnn"}

    def _fetch_alternative_fear_greed_snapshot(self, *, timeout: Optional[float] = None) -> Dict[str, Any]:
        payload = (
            fetch_alternative_fear_greed_payload(timeout=timeout)
            if timeout is not None
            else fetch_alternative_fear_greed_payload()
        )
        rows = payload.get("data") or []
        history = []
        for row in reversed(rows):
            value = self._clean_number(row.get("value") if isinstance(row, dict) else None)
            if value is not None:
                history.append({"value": value})
        if len(history) < 2:
            raise RuntimeError("Alternative Fear & Greed history unavailable")
        return {"history": history, "source": "alternative_me"}

    def _fetch_binance_kline_history(self, symbol: str) -> List[float]:
        rows = fetch_binance_kline_history_rows(symbol)
        closes = []
        for row in rows:
            if isinstance(row, list) and len(row) >= 5:
                close_value = self._clean_number(row[4])
                if close_value is not None:
                    closes.append(close_value)
        if len(closes) < 2:
            raise RuntimeError(f"Binance kline history unavailable for {symbol}")
        return closes

    def _fetch_funds_flow(self) -> PanelPayload:
        symbols = {
            "ETF": ("ETF flows", "SPY", "B USD"),
            "INSTITUTIONAL": ("Institutional net flow", "QQQ", "B USD"),
            "INDUSTRY": ("Industry flow breadth", "IWM", "score"),
        }
        items = []
        for key, (label, ticker, unit) in symbols.items():
            try:
                quote = self._latest_quote(ticker)
            except Exception:
                quote = {"value": None, "change_pct": None, "trend": []}
            change_pct = quote.get("change_pct")
            volume = float(quote.get("volume") or 0)
            value = round((volume * float(change_pct or 0)) / 1_000_000_000, 2) if unit == "B USD" else round(float(change_pct or 0), 2)
            items.append({
                "symbol": key,
                "label": label,
                "value": value,
                "unit": unit,
                "change_pct": change_pct,
                "risk_direction": "decreasing" if value >= 0 else "increasing",
                "trend": quote.get("trend", []),
                "source": "yfinance_proxy",
            })
        return self._success_panel("FundsFlowCard", items)

    def _fetch_macro(self) -> PanelPayload:
        official_points = self._official_macro_points(include_policy_and_inflation=True, include_credit_stress=True)
        item_map = {
            str(item.get("symbol") or ""): item
            for item in self._quote_items(self.MACRO_SYMBOLS)
        }
        for panel_symbol, (series_id, label, unit, market) in self.OFFICIAL_RATE_SERIES.items():
            official_item = self._official_macro_item(panel_symbol, label, official_points.get(series_id, []), unit=unit, market=market)
            if official_item:
                item_map[panel_symbol] = official_item
        official_sofr = self._official_macro_item("SOFR", "SOFR", official_points.get("SOFR", []), unit="%", market="US")
        if official_sofr:
            item_map["SOFR"] = official_sofr
        official_vix = self._official_macro_item("VIX", "VIX", official_points.get("VIXCLS", []), unit="pts", change_scale=1.0)
        if official_vix:
            item_map["VIX"] = official_vix
        official_credit = self._official_macro_item(
            "CREDIT",
            "Credit spreads",
            official_points.get("BAMLH0A0HYM2", []),
            unit="bps",
            value_scale=100.0,
            change_scale=100.0,
        )
        if official_credit:
            official_credit["observationOnly"] = True
            official_credit["includedInScore"] = False
            item_map["CREDIT"] = official_credit
        official_fed_funds = self._official_macro_item("FEDFUNDS", "Fed Funds", official_points.get("DFF", []), unit="%", market="US")
        if official_fed_funds:
            item_map["FEDFUNDS"] = official_fed_funds
        official_cpi = self._official_macro_yoy_item("CPI", "CPI", official_points.get("CPIAUCSL", []), unit="YoY %", market="US")
        if official_cpi:
            item_map["CPI"] = official_cpi
        official_ppi = self._official_macro_yoy_item("PPI", "PPI", official_points.get("PPIACO", []), unit="YoY %", market="US")
        if official_ppi:
            item_map["PPI"] = official_ppi
        for symbol, (series_id, label, unit, market) in self.OFFICIAL_MACRO_SERIES.items():
            if symbol == "CREDIT" and symbol in item_map:
                continue
            item_map.setdefault(symbol, self._official_macro_unavailable_item(symbol, label, series_id, unit=unit, market=market))
        ordered_symbols = ["US2Y", "US10Y", "US30Y", "SOFR", "VIX", "DXY", "GOLD", "OIL", "FEDFUNDS", "CPI", "PPI", "CREDIT"]
        items = [item_map[symbol] for symbol in ordered_symbols if symbol in item_map]
        payload = self._success_panel("MacroIndicatorsCard", items)
        payload["source"] = "mixed"
        payload["sourceLabel"] = self._source_label("mixed")
        payload["fallbackUsed"] = any(bool(item.get("isFallback") or item.get("isUnavailable")) for item in items)
        if payload["fallbackUsed"]:
            payload["warning"] = OFFICIAL_MACRO_UNAVAILABLE_WARNING
        return payload

    def _fetch_cn_indices_snapshot(self) -> Dict[str, Any]:
        fallback = self._fallback_cn_indices_snapshot()
        try:
            live_quotes = self._fetch_sina_cn_index_quotes()
        except Exception:
            return fallback

        merged_items = []
        live_count = 0
        for fallback_item in fallback.get("items", []):
            symbol = str(fallback_item.get("symbol") or "")
            quote = live_quotes.get(symbol)
            if quote:
                live_count += 1
                merged_items.append({
                    **fallback_item,
                    **quote,
                    "label": quote.get("name") or fallback_item.get("label"),
                    "price": quote.get("value"),
                    "unit": "pts",
                    "market": fallback_item.get("market"),
                    "source": "sina",
                    "sourceLabel": "新浪财经",
                    "isFallback": False,
                    "warning": None,
                })
            else:
                merged_items.append(fallback_item)

        if live_count == 0:
            return fallback

        updated_at = _now_iso()
        source = "sina" if live_count == len(merged_items) else "mixed"
        return {
            "source": source,
            "sourceLabel": self._source_label(source),
            "updatedAt": updated_at,
            "asOf": max((str(item.get("asOf") or "") for item in merged_items), default=updated_at) or updated_at,
            "items": merged_items,
            "fallbackUsed": live_count != len(merged_items),
            "warning": FALLBACK_WARNING if live_count != len(merged_items) else None,
        }

    def _fetch_sina_cn_index_quotes(self) -> Dict[str, Dict[str, Any]]:
        rows = fetch_sina_cn_index_rows(sorted(set(self.CN_SINA_SYMBOLS.values())))
        quotes: Dict[str, Dict[str, Any]] = {}
        for canonical_symbol, sina_symbol in self.CN_SINA_SYMBOLS.items():
            if canonical_symbol in {"000001.SS", "sh000001", "000300.SS"}:
                continue
            row = rows.get(sina_symbol)
            if not row:
                continue
            quote = self._sina_cn_index_item(canonical_symbol, row)
            if quote:
                quotes[canonical_symbol] = quote
        return quotes

    def _sina_cn_index_item(self, canonical_symbol: str, row: List[str]) -> Optional[Dict[str, Any]]:
        if canonical_symbol in {"HSI", "HSTECH"}:
            return self._sina_hk_index_item(canonical_symbol, row)
        value = self._clean_number(row[3] if len(row) > 3 else None)
        previous = self._clean_number(row[2] if len(row) > 2 else None)
        open_price = self._clean_number(row[1] if len(row) > 1 else None)
        high = self._clean_number(row[4] if len(row) > 4 else None)
        low = self._clean_number(row[5] if len(row) > 5 else None)
        if value is None or previous is None:
            return None
        change = value - previous
        change_percent = self._percent_change(previous, value) or 0.0
        trade_date = row[30] if len(row) > 30 else ""
        trade_time = row[31] if len(row) > 31 else ""
        as_of = self._sina_as_of(trade_date, trade_time)
        trend = [price for price in (open_price, low, high, value) if price is not None]
        return {
            "name": row[0] or canonical_symbol,
            "symbol": canonical_symbol,
            "value": round(value, 3),
            "change": round(change, 3),
            "changePercent": round(change_percent, 3),
            "change_text": f"{change:+.2f}",
            "sparkline": trend[-4:] or [round(value, 3)],
            "trend": trend[-4:] or [round(value, 3)],
            "asOf": as_of,
        }

    def _sina_hk_index_item(self, canonical_symbol: str, row: List[str]) -> Optional[Dict[str, Any]]:
        value = self._clean_number(row[6] if len(row) > 6 else None)
        previous = self._clean_number(row[3] if len(row) > 3 else None)
        open_price = self._clean_number(row[2] if len(row) > 2 else None)
        high = self._clean_number(row[4] if len(row) > 4 else None)
        low = self._clean_number(row[5] if len(row) > 5 else None)
        change = self._clean_number(row[7] if len(row) > 7 else None)
        change_percent = self._clean_number(row[8] if len(row) > 8 else None)
        if value is None:
            return None
        if change is None and previous is not None:
            change = value - previous
        if change_percent is None and previous is not None:
            change_percent = self._percent_change(previous, value)
        trade_date = row[17] if len(row) > 17 else ""
        trade_time = row[18] if len(row) > 18 else ""
        as_of = self._sina_as_of(trade_date, trade_time)
        trend = [price for price in (open_price, low, high, value) if price is not None]
        names = {
            "HSI": "恒生指数",
            "HSTECH": "恒生科技",
        }
        return {
            "name": names.get(canonical_symbol, canonical_symbol),
            "symbol": canonical_symbol,
            "value": round(value, 3),
            "change": round(change or 0.0, 3),
            "changePercent": round(change_percent or 0.0, 3),
            "change_text": f"{(change or 0.0):+.2f}",
            "sparkline": trend[-4:] or [round(value, 3)],
            "trend": trend[-4:] or [round(value, 3)],
            "asOf": as_of,
        }

    def _sina_as_of(self, trade_date: str, trade_time: str) -> str:
        try:
            normalized_date = str(trade_date or "").strip().replace("/", "-")
            normalized_time = str(trade_time or "").strip()
            parsed = datetime.fromisoformat(f"{normalized_date}T{normalized_time}")
            return parsed.replace(tzinfo=CN_TZ).isoformat(timespec="seconds")
        except Exception:
            return _now_iso()

    def _fetch_cn_breadth_snapshot(self) -> Dict[str, Any]:
        snapshot = fetch_tickflow_cn_breadth_snapshot()
        source = str(snapshot.get("source") or "tickflow")
        source_label = snapshot.get("sourceLabel") or self._source_label(source)
        source_type = snapshot.get("sourceType") or _infer_source_type(source)
        updated_at = str(snapshot.get("updatedAt") or _now_iso())
        as_of = str(snapshot.get("asOf") or updated_at)
        adv_ratio = float(snapshot["advRatio"])
        explanation = self._cn_breadth_explanation(adv_ratio)
        detail = "TickFlow A-share market stats snapshot"

        return {
            "source": source,
            "sourceLabel": source_label,
            "sourceType": source_type,
            "updatedAt": updated_at,
            "asOf": as_of,
            "fallbackUsed": False,
            "isFallback": False,
            "warning": None,
            "explanation": explanation,
            "items": [
                self._breadth_metric_item("赚钱效应", "EFFECT", float(snapshot["effect"]), "score", as_of, updated_at, source, source_label, source_type, detail=detail, explanation=explanation),
                self._breadth_metric_item("上涨家数", "ADVANCERS", float(snapshot["advancers"]), "stocks", as_of, updated_at, source, source_label, source_type, detail=detail),
                self._breadth_metric_item("下跌家数", "DECLINERS", float(snapshot["decliners"]), "stocks", as_of, updated_at, source, source_label, source_type, detail=detail),
                self._breadth_metric_item("涨停家数", "LIMIT_UP", float(snapshot["limitUp"]), "stocks", as_of, updated_at, source, source_label, source_type, detail=detail),
                self._breadth_metric_item("跌停家数", "LIMIT_DOWN", float(snapshot["limitDown"]), "stocks", as_of, updated_at, source, source_label, source_type, detail=detail),
                self._breadth_metric_item("上涨比例", "ADV_RATIO", adv_ratio, "%", as_of, updated_at, source, source_label, source_type, detail=detail),
            ],
        }

    def _fetch_us_breadth_snapshot(self) -> Dict[str, Any]:
        quote_items: List[Dict[str, Any]] = []
        for ticker, label in self.US_SECTOR_ETFS.items():
            try:
                quote = self._latest_quote(ticker)
            except Exception:
                continue
            change_pct = self._clean_number(quote.get("change_pct"))
            value = self._clean_number(quote.get("value"))
            if change_pct is None or value is None:
                continue
            quote_items.append({
                "symbol": ticker,
                "label": label,
                "value": round(value, 3),
                "price": round(value, 3),
                "change": round(change_pct, 3),
                "changePercent": round(change_pct, 3),
                "change_text": self._signed_percent_text(change_pct),
                "sparkline": quote.get("trend", []),
                "trend": quote.get("trend", []),
                "unit": "USD",
                "risk_direction": self._risk_direction(change_pct),
                "hover_details": ["Sector ETF proxy"],
                "source": "yfinance_proxy",
                "sourceLabel": "Yahoo Finance",
                "isFallback": False,
            })
        if not quote_items:
            return self._fallback_us_breadth_snapshot()

        sorted_by_change = sorted(quote_items, key=lambda item: float(item.get("changePercent") or 0), reverse=True)
        sectors_up = sum(1 for item in quote_items if float(item.get("changePercent") or 0) > 0)
        sectors_down = sum(1 for item in quote_items if float(item.get("changePercent") or 0) < 0)
        strongest = sorted_by_change[0]
        weakest = sorted_by_change[-1]
        items = [
            self._computed_metric_item("Sectors Up", "SECTORS_UP", sectors_up, "sectors", detail="Sector ETF proxy"),
            self._computed_metric_item("Sectors Down", "SECTORS_DOWN", sectors_down, "sectors", detail="Sector ETF proxy"),
            self._computed_metric_item(f"Strongest {strongest['symbol']}", "STRONGEST_SECTOR", strongest["changePercent"], "%", detail=str(strongest["label"])),
            self._computed_metric_item(f"Weakest {weakest['symbol']}", "WEAKEST_SECTOR", weakest["changePercent"], "%", detail=str(weakest["label"])),
        ]
        items.extend(self._us_relative_pressure_items())
        items.extend(sorted_by_change)

        updated_at = _now_iso()
        return {
            "source": "yfinance_proxy",
            "sourceLabel": "Yahoo Finance",
            "updatedAt": updated_at,
            "asOf": updated_at,
            "items": [
                {
                    **item,
                    "updatedAt": updated_at,
                    "asOf": updated_at,
                    "source": item.get("source") or "computed",
                    "sourceLabel": item.get("sourceLabel") or "系统计算",
                    "isFallback": False,
                }
                for item in items
            ],
            "fallbackUsed": False,
            "warning": None,
        }

    def _us_relative_pressure_items(self) -> List[Dict[str, Any]]:
        pairs = [
            ("RSP_SPY", "RSP vs SPY", "RSP", "SPY"),
            ("IWM_SPY", "IWM vs SPY", "IWM", "SPY"),
            ("QQQ_SPY", "QQQ vs SPY", "QQQ", "SPY"),
        ]
        items = []
        for symbol, label, left, right in pairs:
            try:
                left_quote = self._latest_quote(left)
                right_quote = self._latest_quote(right)
            except Exception:
                continue
            left_change = self._clean_number(left_quote.get("change_pct"))
            right_change = self._clean_number(right_quote.get("change_pct"))
            if left_change is None or right_change is None:
                continue
            spread = left_change - right_change
            items.append(self._computed_metric_item(label, symbol, round(spread, 3), "%", detail="Relative 1D pressure proxy"))
        return items

    def _fetch_cn_flows_snapshot(self) -> Dict[str, Any]:
        return self._fallback_cn_flows_snapshot()

    def _fetch_sector_rotation_snapshot(self) -> Dict[str, Any]:
        radar_payload = MarketRotationRadarService(
            quote_provider=get_rotation_radar_quote_provider(),
            use_shared_cache=True,
        ).get_rotation_radar()
        return self._project_sector_rotation_snapshot(radar_payload)

    def _fetch_rates_snapshot(self) -> Dict[str, Any]:
        fallback = self._fallback_rates_snapshot()
        official_points = self._official_macro_points()
        fallback_items = {
            str(item.get("symbol") or ""): item
            for item in fallback.get("items", [])
            if isinstance(item, dict)
        }
        items: List[Dict[str, Any]] = []
        official_count = 0
        for symbol in ("US2Y", "US10Y", "US30Y"):
            series_id, label, unit, market = self.OFFICIAL_RATE_SERIES[symbol]
            official_item = self._official_macro_item(symbol, label, official_points.get(series_id, []), unit=unit, market=market)
            if official_item:
                items.append(official_item)
                official_count += 1
            elif symbol in fallback_items:
                items.append(fallback_items[symbol])
        if "US10Y2Y" in fallback_items:
            items.append(fallback_items["US10Y2Y"])
        if "US10Y3M" in fallback_items:
            items.append(fallback_items["US10Y3M"])
        official_sofr = self._official_macro_item("SOFR", "SOFR", official_points.get("SOFR", []), unit="%", market="US")
        if official_sofr:
            items.append(official_sofr)
        for symbol in ("CN10Y", "DR007", "SHIBOR", "LPR"):
            if symbol in fallback_items:
                items.append(fallback_items[symbol])

        if official_count == 0 and not official_sofr:
            return fallback

        return {
            **fallback,
            "source": "mixed",
            "sourceLabel": self._source_label("mixed"),
            "items": items,
            "fallbackUsed": any(bool(item.get("isFallback")) for item in items),
            "isFallback": False,
            "warning": FALLBACK_WARNING if any(bool(item.get("isFallback")) for item in items) else None,
        }

    def _project_sector_rotation_snapshot(self, radar_payload: Dict[str, Any]) -> Dict[str, Any]:
        themes = [
            theme for theme in radar_payload.get("themes", [])
            if isinstance(theme, dict)
        ]
        if not themes:
            return self._fallback_sector_rotation_snapshot()

        radar_metadata = radar_payload.get("metadata") if isinstance(radar_payload.get("metadata"), dict) else {}
        quote_provider_metadata = (
            radar_metadata.get("quoteProvider")
            if isinstance(radar_metadata.get("quoteProvider"), dict)
            else {}
        )
        observed_evidence_metadata = (
            radar_metadata.get("observedEvidence")
            if isinstance(radar_metadata.get("observedEvidence"), dict)
            else {}
        )
        updated_at = radar_payload.get("updatedAt") or radar_payload.get("generatedAt") or _now_iso()
        as_of = (
            radar_payload.get("asOf")
            or quote_provider_metadata.get("asOf")
            or observed_evidence_metadata.get("asOf")
            or updated_at
        )
        payload_source = str(radar_payload.get("source") or "computed")
        payload_source_label = radar_payload.get("sourceLabel") or self._source_label(payload_source)
        payload_freshness = radar_payload.get("freshness")
        payload_is_fallback = bool(radar_payload.get("isFallback"))
        payload_is_stale = bool(radar_payload.get("isStale"))
        payload_is_partial = bool(radar_payload.get("isPartial")) or any(bool(theme.get("isPartial")) for theme in themes)
        payload_is_unavailable = bool(radar_payload.get("isUnavailable")) or str(payload_freshness or "").lower() in {"unavailable", "error"}
        items: List[Dict[str, Any]] = []
        radar_snapshot = {
            "source": payload_source,
            "sourceLabel": payload_source_label,
            "updatedAt": updated_at,
            "asOf": as_of,
            "freshness": payload_freshness,
            "isFallback": payload_is_fallback,
            "isStale": payload_is_stale,
            "isPartial": payload_is_partial,
            "isUnavailable": payload_is_unavailable,
            "generatedAt": radar_payload.get("generatedAt") or updated_at,
            "warning": radar_payload.get("warning"),
        }

        for index, theme in enumerate(themes):
            rotation_score = self._clean_number(theme.get("rotationScore"))
            if rotation_score is None:
                continue
            name = str(theme.get("name") or theme.get("label") or theme.get("id") or "")
            symbol = str(theme.get("id") or theme.get("symbol") or name)
            relative_strength_source = theme.get("relativeStrength")
            relative_strength_pct = (
                self._clean_number(relative_strength_source.get("averageRelativeStrengthPercent"))
                if isinstance(relative_strength_source, dict)
                else self._clean_number(relative_strength_source)
            )
            explanation = self._sector_rotation_theme_explanation(theme)
            trend = self._sector_rotation_theme_trend(theme, rotation_score, relative_strength_pct)
            rotation_state_evidence = (
                copy.deepcopy(theme.get("rotationStateEvidence"))
                if isinstance(theme.get("rotationStateEvidence"), dict)
                else build_rotation_state_evidence(
                    theme,
                    {
                        "market": theme.get("market") or radar_payload.get("market") or "US",
                        "taxonomyVersion": "sector_rotation_taxonomy_v1",
                        "computedAt": theme.get("updatedAt") or updated_at,
                        "asOf": theme.get("asOf") or as_of,
                    },
                )
            )
            source_confidence = rotation_state_evidence.get("sourceConfidence") if isinstance(rotation_state_evidence, dict) else {}
            item_is_partial = bool(theme.get("isPartial"))
            item_is_unavailable = bool(theme.get("isUnavailable"))
            if isinstance(source_confidence, dict):
                item_is_partial = item_is_partial or bool(source_confidence.get("isPartial"))
                item_is_unavailable = item_is_unavailable or bool(source_confidence.get("isUnavailable"))
            item: Dict[str, Any] = {
                "name": name,
                "label": name,
                "symbol": symbol,
                "value": round(rotation_score, 3),
                "price": round(rotation_score, 3),
                "change": round(relative_strength_pct, 3) if relative_strength_pct is not None else None,
                "changePercent": round(relative_strength_pct, 3) if relative_strength_pct is not None else None,
                "change_text": self._signed_percent_text(relative_strength_pct) if relative_strength_pct is not None else "待确认",
                "sparkline": trend,
                "trend": trend,
                "unit": "score",
                "market": theme.get("market") or "US",
                "source": theme.get("source") or payload_source,
                "sourceLabel": theme.get("sourceLabel") or payload_source_label,
                "updatedAt": theme.get("updatedAt") or updated_at,
                "asOf": theme.get("asOf") or as_of,
                "freshness": theme.get("freshness") or payload_freshness,
                "isFallback": bool(theme.get("isFallback") or payload_is_fallback),
                "isStale": bool(theme.get("isStale") or payload_is_stale),
                "isPartial": item_is_partial,
                "isUnavailable": item_is_unavailable,
                "relativeStrength": round(rotation_score, 3),
                "rank": index + 1,
                "risk_direction": self._risk_direction(relative_strength_pct if relative_strength_pct is not None else 0.0),
                "hover_details": self._sector_rotation_theme_hover_details(theme, explanation),
                "rotationStateEvidence": rotation_state_evidence,
                "sourceFreshnessEvidence": {
                    "source": theme.get("source") or payload_source,
                    "sourceLabel": theme.get("sourceLabel") or payload_source_label,
                    "asOf": theme.get("asOf") or as_of,
                    "freshness": theme.get("freshness") or payload_freshness,
                    "isFallback": bool(theme.get("isFallback") or payload_is_fallback),
                    "isStale": bool(theme.get("isStale") or payload_is_stale),
                    "isPartial": item_is_partial,
                    "isUnavailable": item_is_unavailable,
                },
            }
            if explanation:
                item["explanation"] = explanation
            items.append(item)

        if not items:
            return self._fallback_sector_rotation_snapshot()

        return {
            "source": payload_source,
            "sourceLabel": payload_source_label,
            "updatedAt": updated_at,
            "asOf": as_of,
            "freshness": payload_freshness,
            "isFallback": payload_is_fallback,
            "isStale": payload_is_stale,
            "isPartial": payload_is_partial,
            "isUnavailable": payload_is_unavailable,
            "fallbackUsed": bool(radar_payload.get("fallbackUsed") or payload_is_fallback),
            "warning": radar_payload.get("warning"),
            "explanation": "Rotation Radar 主题轮动证据投影，分数用于观察相对强弱与覆盖状态。",
            "radarSnapshot": radar_snapshot,
            "sourceFreshnessEvidence": radar_snapshot,
            "items": items,
        }

    def _official_macro_points(
        self,
        *,
        include_policy_and_inflation: bool = False,
        include_credit_stress: bool = False,
        budget_seconds: Optional[float] = None,
    ) -> Dict[str, List[MacroObservation]]:
        points: Dict[str, List[MacroObservation]] = {}
        fetched_at = time.monotonic()
        fred_series_ids = ["DGS2", "DGS10", "DGS30", "VIXCLS", "SOFR"]
        if include_policy_and_inflation:
            fred_series_ids.extend(["DFF", "CPIAUCSL", "PPIACO"])
        if include_credit_stress:
            fred_series_ids.append("BAMLH0A0HYM2")
        for series_id in fred_series_ids:
            cached_points = self._cached_official_macro_series(series_id, fetched_at)
            if cached_points:
                points[series_id] = cached_points

        deadline = self._deadline_after(
            self.OFFICIAL_MACRO_AGGREGATE_BUDGET_SECONDS
            if budget_seconds is None
            else budget_seconds
        )
        treasury_series_ids = {"DGS2", "DGS10", "DGS30"}
        if any(series_id not in points for series_id in treasury_series_ids):
            timeout = self._deadline_timeout(deadline, self.OFFICIAL_MACRO_CALL_TIMEOUT_SECONDS)
        else:
            timeout = None
        if timeout is not None:
            try:
                treasury_points = fetch_treasury_daily_rate_observation_points(limit=2, timeout=timeout)
            except Exception:
                treasury_points = {}
            self._store_official_macro_points(treasury_points, fetched_at)
            for series_id in treasury_series_ids:
                series_points = treasury_points.get(series_id, [])
                if series_points:
                    points[series_id] = list(series_points)
        for series_id in fred_series_ids:
            if series_id in points and points[series_id]:
                continue
            timeout = self._deadline_timeout(deadline, self.OFFICIAL_MACRO_CALL_TIMEOUT_SECONDS)
            if timeout is None:
                break
            try:
                series_points = fetch_fred_observation_points(
                    series_id,
                    limit=self._official_macro_history_limit(series_id),
                    timeout=timeout,
                )
            except Exception:
                series_points = []
            if series_points:
                self._store_official_macro_points({series_id: series_points}, fetched_at)
                points[series_id] = series_points
        return points

    @staticmethod
    def _official_macro_history_limit(series_id: str) -> int:
        if series_id in {"CPIAUCSL", "PPIACO"}:
            return 13
        return 2

    def _cached_official_macro_series(self, series_id: str, now_monotonic: float) -> Optional[List[MacroObservation]]:
        cached = self._official_macro_micro_cache.get(series_id)
        if not cached:
            return None
        fetched_at, observations = cached
        if now_monotonic - fetched_at > float(self.OFFICIAL_MACRO_MICRO_CACHE_TTL_SECONDS):
            self._official_macro_micro_cache.pop(series_id, None)
            return None
        return list(observations)

    def _store_official_macro_points(self, points: Dict[str, List[MacroObservation]], fetched_at: float) -> None:
        for series_id, observations in points.items():
            if observations:
                self._official_macro_micro_cache[series_id] = (fetched_at, list(observations))

    def _official_macro_item(
        self,
        symbol: str,
        label: str,
        observations: List[MacroObservation],
        *,
        unit: str,
        market: Optional[str] = None,
        value_scale: float = 1.0,
        change_scale: float = 100.0,
    ) -> Optional[Dict[str, Any]]:
        latest = observations[0] if observations else None
        if latest is None or latest.value is None:
            return None
        previous = next(
            (point for point in observations[1:] if point.value is not None),
            None,
        )
        previous_value = previous.value if previous is not None else None
        change = None if previous_value is None else round((latest.value - previous_value) * change_scale, 3)
        change_percent = self._percent_change(previous_value, latest.value)
        scaled_value = round(latest.value * value_scale, 3)
        scaled_trend = [round(point.value * value_scale, 3) for point in reversed(observations) if point.value is not None]
        return self._official_macro_metric_item(
            symbol,
            label,
            latest,
            value=scaled_value,
            unit=unit,
            market=market,
            change=change,
            change_percent=change_percent,
            trend=scaled_trend,
        )

    def _official_macro_yoy_item(
        self,
        symbol: str,
        label: str,
        observations: List[MacroObservation],
        *,
        unit: str,
        market: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        latest = observations[0] if observations else None
        valid_points = [point for point in observations if point.value is not None]
        if latest is None or latest.value is None:
            return self._official_macro_unavailable_item(symbol, label, self._official_macro_source_id_for_symbol(symbol), unit=unit, market=market)
        latest_time = _parse_market_time(latest.as_of or latest.date)
        if latest_time is None:
            return self._official_macro_unavailable_item(
                symbol,
                label,
                latest.source_id,
                unit=unit,
                market=market,
                as_of=latest.as_of,
            )
        year_ago = next(
            (
                point
                for point in valid_points[1:]
                if point.value not in {None, 0}
                and (candidate_time := _parse_market_time(point.as_of or point.date)) is not None
                and (latest_time - candidate_time).days >= 330
            ),
            None,
        )
        if year_ago is None or year_ago.value in {None, 0}:
            return self._official_macro_unavailable_item(
                symbol,
                label,
                latest.source_id,
                unit=unit,
                market=market,
                as_of=latest.as_of,
            )
        yoy_value = ((latest.value / year_ago.value) - 1.0) * 100.0
        yoy_trend: List[float] = []
        for current_index in range(len(valid_points) - 1, -1, -1):
            current_point = valid_points[current_index]
            current_time = _parse_market_time(current_point.as_of or current_point.date)
            if current_point.value is None or current_time is None:
                continue
            comparison = next(
                (
                    point
                    for point in valid_points[current_index + 1:]
                    if point.value not in {None, 0}
                    and (comparison_time := _parse_market_time(point.as_of or point.date)) is not None
                    and (current_time - comparison_time).days >= 330
                ),
                None,
            )
            if comparison is None or comparison.value in {None, 0}:
                continue
            yoy_trend.append(round(((current_point.value / comparison.value) - 1.0) * 100.0, 3))
        return self._official_macro_metric_item(
            symbol,
            label,
            latest,
            value=round(yoy_value, 3),
            unit=unit,
            market=market,
            change=None,
            change_percent=None,
            trend=yoy_trend or [round(yoy_value, 3)],
        )

    def _official_macro_metric_item(
        self,
        symbol: str,
        label: str,
        latest: MacroObservation,
        *,
        value: float,
        unit: str,
        market: Optional[str],
        change: float | None,
        change_percent: float | None,
        trend: List[float],
    ) -> Dict[str, Any]:
        source_label = self._official_source_label(latest.source_id)
        item: Dict[str, Any] = {
            "name": label,
            "label": label,
            "symbol": symbol,
            "value": value,
            "price": value,
            "change": change,
            "changePercent": round(change_percent, 3) if change_percent is not None else None,
            "change_text": f"{change:+.2f}" if change is not None else "待确认",
            "sparkline": trend,
            "trend": trend,
            "unit": unit,
            "source": latest.source_id.split(":", 1)[0],
            "sourceId": latest.source_id,
            "sourceType": latest.source_type,
            "sourceLabel": source_label,
            "asOf": latest.as_of,
            "updatedAt": latest.as_of,
            "isFallback": False,
            "risk_direction": self._risk_direction(change_percent),
            "hover_details": [source_label, f"Official as of {latest.as_of}"] if latest.as_of else [source_label],
        }
        if market:
            item["market"] = market
        return item

    def _official_macro_unavailable_item(
        self,
        symbol: str,
        label: str,
        series_id: str,
        *,
        unit: str,
        market: Optional[str] = None,
        as_of: Optional[str] = None,
    ) -> Dict[str, Any]:
        source_id = series_id if ":" in series_id else f"fred:{series_id}"
        resolved_as_of = as_of or _now_iso()
        source_label = self._official_source_label(source_id)
        item: Dict[str, Any] = {
            "name": label,
            "label": label,
            "symbol": symbol,
            "value": None,
            "price": None,
            "change": None,
            "changePercent": None,
            "change_text": "待确认",
            "sparkline": [],
            "trend": [],
            "unit": unit,
            "source": source_id.split(":", 1)[0],
            "sourceId": source_id,
            "sourceType": "official_public",
            "sourceLabel": source_label,
            "asOf": resolved_as_of,
            "updatedAt": resolved_as_of,
            "isFallback": False,
            "isUnavailable": True,
            "warning": OFFICIAL_MACRO_UNAVAILABLE_WARNING,
            "risk_direction": "neutral",
            "hover_details": [source_label, OFFICIAL_MACRO_UNAVAILABLE_WARNING],
            "sourceFreshnessEvidence": {
                "freshness": "unavailable",
                "isUnavailable": True,
                "warning": OFFICIAL_MACRO_UNAVAILABLE_WARNING,
            },
        }
        if market:
            item["market"] = market
        return item

    def _official_macro_source_id_for_symbol(self, symbol: str) -> str:
        series = self.OFFICIAL_MACRO_SERIES.get(symbol)
        if series:
            return f"fred:{series[0]}"
        return ""

    def _sector_rotation_theme_trend(
        self,
        theme: Dict[str, Any],
        rotation_score: float,
        relative_strength_pct: Optional[float],
    ) -> List[float]:
        time_windows = theme.get("timeWindows") if isinstance(theme.get("timeWindows"), dict) else {}
        trend = [
            round(float(window.get("averageChangePercent")), 3)
            for key in ("5m", "15m", "60m", "1d")
            for window in [time_windows.get(key)]
            if isinstance(window, dict)
            and window.get("available")
            and isinstance(window.get("averageChangePercent"), (int, float))
            and math.isfinite(float(window.get("averageChangePercent")))
        ]
        if trend:
            return trend
        if relative_strength_pct is not None:
            return [round(relative_strength_pct, 3)]
        return [round(rotation_score, 3)]

    def _sector_rotation_theme_explanation(self, theme: Dict[str, Any]) -> Optional[str]:
        stage_explanation = str(theme.get("stageExplanation") or "").strip()
        if stage_explanation:
            return stage_explanation
        data_state_label = ""
        theme_detail = theme.get("themeDetail")
        if isinstance(theme_detail, dict):
            data_state_label = str(theme_detail.get("dataStateLabel") or "").strip()
        if data_state_label:
            return data_state_label
        evidence = theme.get("evidence")
        if isinstance(evidence, list):
            for entry in evidence:
                text = str(entry or "").strip()
                if text:
                    return text
        return None

    def _sector_rotation_theme_hover_details(
        self,
        theme: Dict[str, Any],
        explanation: Optional[str],
    ) -> List[str]:
        details: List[str] = []
        if explanation:
            details.append(explanation)
        proxy_quality = theme.get("proxyQuality")
        if isinstance(proxy_quality, dict):
            coverage_percent = self._clean_number(proxy_quality.get("coveragePercent"))
            if coverage_percent is not None:
                details.append(f"代理覆盖 {coverage_percent:.0f}%")
            proxy_explanation = str(proxy_quality.get("explanation") or "").strip()
            if proxy_explanation:
                details.append(proxy_explanation)
        theme_detail = theme.get("themeDetail")
        if isinstance(theme_detail, dict):
            data_state_label = str(theme_detail.get("dataStateLabel") or "").strip()
            if data_state_label:
                details.append(data_state_label)
        return details

    def _official_source_label(self, source_id: str) -> str:
        contract = get_official_macro_source_for_transport_source(source_id)
        if contract is not None:
            return contract.display_name
        return resolve_source_label(source_type="official_public")

    def _fetch_fx_commodities_snapshot(self) -> Dict[str, Any]:
        fallback = self._fallback_fx_commodities_snapshot()
        fallback_items = [
            item for item in fallback.get("items", [])
            if isinstance(item, dict)
        ]
        delayed_proxy_symbols = set(FX_COMMODITY_DELAYED_PROXY_SYMBOLS)
        updated_at = _now_iso()
        merged_items: List[Dict[str, Any]] = []
        proxy_as_of_values: List[str] = []
        proxy_count = 0
        deadline = self._deadline_after(self.YFINANCE_PROXY_AGGREGATE_BUDGET_SECONDS)

        for fallback_item in fallback_items:
            symbol = str(fallback_item.get("symbol") or "")
            ticker = self.FX_COMMODITY_PROXY_TICKERS.get(symbol)
            if symbol not in delayed_proxy_symbols or not ticker:
                merged_items.append(fallback_item)
                continue
            timeout = self._deadline_timeout(deadline, self.YFINANCE_PROXY_AGGREGATE_BUDGET_SECONDS)
            if timeout is None:
                merged_items.append(fallback_item)
                continue
            try:
                frame = fetch_yfinance_quote_history_frame(ticker, timeout=timeout)
                closes, as_of = self._history_frame_closes_and_as_of(frame, ticker)
            except Exception:
                merged_items.append(fallback_item)
                continue

            latest = closes[-1]
            previous = closes[-2] if len(closes) > 1 else latest
            change = latest - previous
            change_percent = ((latest - previous) / previous * 100) if previous else 0.0
            trend = [round(value, 3) for value in closes[-8:]]
            merged_items.append({
                **fallback_item,
                "value": round(latest, 3),
                "price": round(latest, 3),
                "change": round(change, 3),
                "changePercent": round(change_percent, 3),
                "change_text": f"{change:+.2f}",
                "sparkline": trend,
                "trend": trend,
                "source": "yfinance_proxy",
                "sourceLabel": self._source_label("yfinance_proxy"),
                "sourceType": "unofficial_proxy",
                "updatedAt": updated_at,
                "asOf": as_of or updated_at,
                "isFallback": False,
                "warning": None,
            })
            proxy_count += 1
            if as_of:
                proxy_as_of_values.append(as_of)

        if proxy_count == 0:
            return fallback

        partial = proxy_count != len(fallback_items)
        warning = "代理延迟数据，不代表实时/官方行情"
        if partial:
            warning = f"{warning}；部分品种仍为备用数据"
        return {
            "source": "mixed" if partial else "yfinance_proxy",
            "sourceLabel": self._source_label("mixed" if partial else "yfinance_proxy"),
            "sourceType": "unofficial_proxy",
            "updatedAt": updated_at,
            "asOf": min(proxy_as_of_values) if proxy_as_of_values else updated_at,
            "items": merged_items,
            "fallbackUsed": partial,
            "isFallback": False,
            "warning": warning,
            "explanation": fallback.get("explanation"),
        }

    def _fetch_futures_snapshot(self) -> Dict[str, Any]:
        fallback = self._fallback_futures_snapshot()
        fallback_items = [
            item for item in fallback.get("items", [])
            if isinstance(item, dict)
        ]
        delayed_proxy_symbols = {
            contract.symbol
            for contract in list_futures_contracts()
            if contract.delayed_proxy_eligible
            and contract.symbol in self.FUTURES_DELAYED_PROXY_TICKERS
        }
        updated_at = _now_iso()
        merged_items: List[Dict[str, Any]] = []
        proxy_as_of_values: List[str] = []
        proxy_count = 0
        deadline = self._deadline_after(self.YFINANCE_PROXY_AGGREGATE_BUDGET_SECONDS)

        for fallback_item in fallback_items:
            symbol = str(fallback_item.get("symbol") or "")
            ticker = self.FUTURES_DELAYED_PROXY_TICKERS.get(symbol)
            if symbol not in delayed_proxy_symbols or not ticker:
                merged_items.append(fallback_item)
                continue
            timeout = self._deadline_timeout(deadline, self.YFINANCE_PROXY_AGGREGATE_BUDGET_SECONDS)
            if timeout is None:
                merged_items.append(fallback_item)
                continue
            try:
                frame = fetch_yfinance_quote_history_frame(ticker, timeout=timeout)
                closes, as_of = self._history_frame_closes_and_as_of(frame, ticker)
            except Exception:
                merged_items.append(fallback_item)
                continue

            latest = closes[-1]
            previous = closes[-2] if len(closes) > 1 else latest
            change = latest - previous
            change_percent = ((latest - previous) / previous * 100) if previous else 0.0
            trend = [round(value, 3) for value in closes[-8:]]
            merged_items.append({
                **fallback_item,
                "value": round(latest, 3),
                "price": round(latest, 3),
                "change": round(change, 3),
                "changePercent": round(change_percent, 3),
                "change_text": f"{change:+.2f}",
                "sparkline": trend,
                "trend": trend,
                "source": "yfinance_proxy",
                "sourceLabel": self._source_label("yfinance_proxy"),
                "sourceType": "unofficial_proxy",
                "updatedAt": updated_at,
                "asOf": as_of or updated_at,
                "isFallback": False,
                "warning": None,
            })
            proxy_count += 1
            if as_of:
                proxy_as_of_values.append(as_of)

        if proxy_count == 0:
            return fallback

        partial = any(bool(item.get("isFallback")) for item in merged_items)
        warning = "代理延迟数据，不代表实时/官方行情"
        if partial:
            warning = f"{warning}；部分品种仍为备用数据"
        return {
            "source": "mixed" if partial else "yfinance_proxy",
            "sourceLabel": self._source_label("mixed" if partial else "yfinance_proxy"),
            "sourceType": "unofficial_proxy",
            "updatedAt": updated_at,
            "asOf": min(proxy_as_of_values) if proxy_as_of_values else updated_at,
            "items": merged_items,
            "fallbackUsed": False,
            "isFallback": False,
            "warning": warning,
        }

    def _fetch_cn_short_sentiment_snapshot(self) -> Dict[str, Any]:
        return self._fallback_cn_short_sentiment_snapshot()

    def _fallback_cn_indices_snapshot(self) -> Dict[str, Any]:
        items = [
            ("上证指数", "000001.SH", 3120.55, 12.30, 0.39, "CN", [3098, 3105, 3112, 3120.55]),
            ("深证成指", "399001.SZ", 9820.42, 52.18, 0.53, "CN", [9722, 9760, 9798, 9820.42]),
            ("创业板指", "399006.SZ", 1886.24, -6.15, -0.32, "CN", [1901, 1894, 1889, 1886.24]),
            ("科创50", "000688.SH", 827.35, 7.40, 0.90, "CN", [812, 818, 824, 827.35]),
            ("沪深300", "000300.SH", 3618.76, 18.86, 0.52, "CN", [3588, 3602, 3612, 3618.76]),
            ("中证500", "000905.SH", 5488.12, 11.42, 0.21, "CN", [5440, 5466, 5482, 5488.12]),
            ("中证1000", "000852.SH", 5626.77, -8.92, -0.16, "CN", [5660, 5642, 5631, 5626.77]),
            ("北证50", "899050.BJ", 853.40, 5.10, 0.60, "CN", [838, 846, 850, 853.40]),
            ("恒生指数", "HSI", 17680.30, 146.20, 0.83, "HK", [17410, 17520, 17610, 17680.30]),
            ("恒生科技", "HSTECH", 3668.18, 44.80, 1.24, "HK", [3590, 3622, 3650, 3668.18]),
            ("富时A50期货", "CN00Y", 12580.00, 38.00, 0.30, "Futures", [12420, 12488, 12542, 12580.00]),
        ]
        return self._card_snapshot([
            self._metric_item(name, symbol, value, change, change_pct, "pts", sparkline, market=market)
            for name, symbol, value, change, change_pct, market, sparkline in items
        ])

    def _fallback_cn_breadth_snapshot(self) -> Dict[str, Any]:
        items = [
            self._metric_item("赚钱效应", "EFFECT", 64, 4, 6.67, "score", [52, 58, 61, 64], explanation="上涨家数占优，市场赚钱效应较好。"),
            self._metric_item("上涨家数", "ADVANCERS", 3190, 260, 8.87, "stocks", [2800, 2960, 3120, 3190]),
            self._metric_item("下跌家数", "DECLINERS", 1780, -210, -10.55, "stocks", [2150, 1990, 1840, 1780]),
            self._metric_item("平盘家数", "UNCHANGED", 240, -12, -4.76, "stocks", [260, 252, 248, 240]),
            self._metric_item("涨停家数", "LIMIT_UP", 68, 11, 19.30, "stocks", [45, 51, 57, 68]),
            self._metric_item("跌停家数", "LIMIT_DOWN", 18, -6, -25.00, "stocks", [31, 26, 24, 18]),
            self._metric_item("创新高家数", "NEW_HIGH", 92, 18, 24.32, "stocks", [61, 72, 84, 92]),
            self._metric_item("创新低家数", "NEW_LOW", 36, -9, -20.00, "stocks", [52, 45, 40, 36]),
            self._metric_item("上涨比例", "ADV_RATIO", 63.2, 3.8, 6.40, "%", [55, 58, 61, 63.2]),
        ]
        return self._card_snapshot(items, explanation="上涨家数占优，市场赚钱效应较好。")

    def _fallback_us_breadth_snapshot(self) -> Dict[str, Any]:
        updated_at = _now_iso()
        return {
            "source": "unavailable",
            "sourceLabel": "未接入",
            "updatedAt": updated_at,
            "asOf": updated_at,
            "freshness": "fallback",
            "fallbackUsed": True,
            "isFallback": True,
            "warning": "Sector ETF breadth proxy 数据暂不可用",
            "items": [
                self._unavailable_item("数据暂不可用", "SECTOR_PROXY_UNAVAILABLE", "数据暂不可用", updated_at, detail="Sector ETF proxy 暂不可用"),
                self._unavailable_item("Advance / decline", "ADVANCE_DECLINE_UNAVAILABLE", "未接入", updated_at),
                self._unavailable_item("52W high / low", "HIGH_LOW_UNAVAILABLE", "未接入", updated_at),
            ],
        }

    def _fallback_cn_flows_snapshot(self) -> Dict[str, Any]:
        items = [
            self._metric_item("北向资金", "NORTHBOUND", 42.6, 18.2, 74.59, "亿 CNY", [12, 18, 24, 42.6], detail="5日 +118.4 亿"),
            self._metric_item("南向资金", "SOUTHBOUND", 28.4, 7.6, 36.54, "亿 HKD", [8, 14, 20, 28.4], detail="5日 +86.1 亿"),
            self._metric_item("主力资金", "MAINLAND_MAIN", -63.5, 22.0, 25.73, "亿 CNY", [-116, -98, -82, -63.5], detail="5日 -286.0 亿"),
            self._metric_item("ETF 净申购", "CN_ETF", 15.8, 4.2, 36.21, "亿 CNY", [4, 8, 12, 15.8], detail="5日 +52.7 亿"),
            self._metric_item("融资余额变化", "MARGIN_BALANCE", 31.2, 9.1, 41.18, "亿 CNY", [8, 17, 24, 31.2], detail="5日 +104.3 亿"),
        ]
        return self._card_snapshot(items)

    def _fallback_sector_rotation_snapshot(self) -> Dict[str, Any]:
        rows = [
            ("AI / 算力", "AI", 3.8, 91, 1, "CN", [0.4, 1.3, 2.6, 3.8], "AI 算力链领涨，风险偏好回升。"),
            ("半导体", "SEMI", 2.6, 86, 2, "CN", [0.1, 0.9, 1.8, 2.6], "国产替代与周期修复共振。"),
            ("港股科技", "HK_TECH", 2.1, 82, 3, "HK", [-0.2, 0.4, 1.3, 2.1], "互联网平台弹性强于大盘。"),
            ("机器人", "ROBOT", 1.8, 78, 4, "CN", [0.3, 0.7, 1.4, 1.8], "主题热度维持高位。"),
            ("资源/有色", "METALS", 1.4, 73, 5, "CN", [-0.1, 0.5, 1.0, 1.4], "铜价上行带动顺周期预期。"),
            ("低空经济", "LOW_ALT", 0.9, 66, 6, "CN", [-0.4, 0.1, 0.5, 0.9], "政策催化仍在扩散。"),
            ("金融", "FIN", 0.4, 58, 7, "CN", [0.1, 0.2, 0.3, 0.4], "权重板块稳定指数。"),
            ("消费", "CONS", -0.2, 46, 8, "CN", [0.3, 0.1, -0.1, -0.2], "需求修复仍需确认。"),
            ("医药", "HEALTH", -0.5, 42, 9, "CN", [-0.1, -0.2, -0.4, -0.5], "防御属性未明显占优。"),
            ("新能源", "NEV", -0.8, 37, 10, "CN", [-0.2, -0.5, -0.6, -0.8], "产能与价格压力仍约束估值。"),
            ("军工", "DEFENSE", -1.0, 34, 11, "CN", [-0.1, -0.3, -0.7, -1.0], "短线资金热度回落。"),
        ]
        items = []
        for name, symbol, change_pct, strength, rank, market, sparkline, explanation in rows:
            item = self._metric_item(name, symbol, strength, change_pct, change_pct, "RS", sparkline, market=market, explanation=explanation)
            item["relativeStrength"] = strength
            item["rank"] = rank
            items.append(item)
        return self._card_snapshot(items)

    def _fallback_rates_snapshot(self) -> Dict[str, Any]:
        items = [
            self._metric_item("US 2Y", "US2Y", 4.82, 3.0, 0.63, "%", [4.70, 4.74, 4.79, 4.82], market="US"),
            self._metric_item("US 10Y", "US10Y", 4.54, 5.0, 1.11, "%", [4.38, 4.45, 4.49, 4.54], market="US"),
            self._metric_item("US 30Y", "US30Y", 4.71, 4.0, 0.86, "%", [4.58, 4.63, 4.68, 4.71], market="US"),
            self._metric_item("10Y-2Y 利差", "US10Y2Y", -28, -2, -7.69, "bp", [-21, -24, -26, -28], market="US"),
            self._metric_item("10Y-3M 利差", "US10Y3M", -94, 4, 4.08, "bp", [-103, -101, -98, -94], market="US"),
            self._metric_item("中国10年国债收益率", "CN10Y", 2.35, -1.5, -0.63, "%", [2.42, 2.39, 2.37, 2.35], market="CN"),
            self._metric_item("DR007", "DR007", 1.86, -6.0, -3.13, "%", [2.01, 1.94, 1.90, 1.86], market="CN"),
            self._metric_item("SHIBOR", "SHIBOR", 1.72, -3.0, -1.71, "%", [1.82, 1.78, 1.75, 1.72], market="CN"),
            self._metric_item("LPR", "LPR", 3.45, 0.0, 0.0, "%", [3.45, 3.45, 3.45, 3.45], market="CN"),
        ]
        return self._card_snapshot(items, explanation="资金利率偏低，A股流动性环境相对友好。")

    def _fallback_fx_commodities_snapshot(self) -> Dict[str, Any]:
        items = [
            self._metric_item("DXY", "DXY", 105.2, 0.35, 0.33, "idx", [104.1, 104.6, 104.9, 105.2], explanation="美元走强时风险资产可能承压。"),
            self._metric_item("USD/CNH", "USDCNH", 7.24, 0.02, 0.28, "", [7.18, 7.20, 7.22, 7.24], explanation="人民币走弱时 A股/港股情绪可能受影响。"),
            self._metric_item("USD/JPY", "USDJPY", 156.4, 0.6, 0.39, "", [154.8, 155.3, 155.9, 156.4]),
            self._metric_item("EUR/USD", "EURUSD", 1.066, -0.003, -0.28, "", [1.075, 1.071, 1.068, 1.066]),
            self._metric_item("黄金", "GOLD", 2358.0, 18.6, 0.79, "USD", [2298, 2318, 2339, 2358], explanation="黄金上涨提示避险或降息预期。"),
            self._metric_item("WTI 原油", "WTI", 82.4, -0.7, -0.84, "USD", [84.0, 83.1, 82.8, 82.4]),
            self._metric_item("布伦特原油", "BRENT", 86.7, -0.5, -0.57, "USD", [88.1, 87.4, 87.0, 86.7]),
            self._metric_item("铜", "COPPER", 4.72, 0.08, 1.72, "USD/lb", [4.50, 4.58, 4.66, 4.72], explanation="铜上涨提示经济复苏预期。"),
        ]
        return self._card_snapshot(items, explanation="美元走强时风险资产可能承压；人民币走弱会压制 A股/港股情绪。")

    def _fallback_futures_snapshot(self) -> Dict[str, Any]:
        updated_at = _now_iso()
        rows = [
            ("纳指期货", "NQ", 18420.5, 65.2, 0.35, "US", "premarket", [18320, 18380, 18400, 18420.5]),
            ("标普500期货", "ES", 5238.25, 14.5, 0.28, "US", "premarket", [5208, 5218, 5229, 5238.25]),
            ("道指期货", "YM", 38980.0, 72.0, 0.19, "US", "premarket", [38820, 38890, 38930, 38980]),
            ("罗素2000期货", "RTY", 2094.6, -3.8, -0.18, "US", "premarket", [2108, 2102, 2098, 2094.6]),
            ("富时A50期货", "CN00Y", 12580.0, 38.0, 0.30, "CN", "day", [12420, 12488, 12542, 12580]),
            ("恒指期货", "HSI_F", 17712.0, 128.0, 0.73, "HK", "day", [17490, 17580, 17640, 17712]),
            ("日经期货", "NKY_F", 38620.0, -90.0, -0.23, "JP", "day", [38880, 38740, 38690, 38620]),
        ]
        return {
            "source": "fallback",
            "sourceLabel": "备用数据",
            "updatedAt": updated_at,
            "asOf": updated_at,
            "fallbackUsed": True,
            "isFallback": True,
            "warning": FALLBACK_WARNING,
            "items": [
                {
                    "name": name,
                    "symbol": symbol,
                    "value": value,
                    "change": change,
                    "changePercent": change_percent,
                    "market": market,
                    "session": session,
                    "sparkline": sparkline,
                    "source": "fallback",
                    "sourceLabel": "备用数据",
                    "updatedAt": updated_at,
                    "asOf": updated_at,
                    "isFallback": True,
                    "warning": FALLBACK_WARNING,
                }
                for name, symbol, value, change, change_percent, market, session, sparkline in rows
            ],
        }

    def _fallback_cn_short_sentiment_snapshot(self) -> Dict[str, Any]:
        metrics = {
            "limitUpCount": 68,
            "limitDownCount": 18,
            "failedLimitUpRate": 24.5,
            "maxConsecutiveLimitUps": 5,
            "yesterdayLimitUpPerformance": 2.8,
            "firstBoardCount": 42,
            "secondBoardCount": 12,
            "highBoardCount": 6,
            "twentyCmLimitUpCount": 9,
            "stRiskLevel": "normal",
        }
        score = self._compute_cn_short_sentiment_score(metrics)
        return {
            "source": "fallback",
            "sourceLabel": "备用数据",
            "updatedAt": _now_iso(),
            "fallbackUsed": True,
            "isFallback": True,
            "warning": FALLBACK_WARNING,
            "sentimentScore": score,
            "summary": self._build_cn_short_sentiment_summary(metrics, score),
            "metrics": metrics,
        }

    def _build_market_temperature_inputs(self, *, budget_seconds: Optional[float] = None) -> Dict[str, Any]:
        return self._with_request_quote_memo(
            lambda: self._build_market_temperature_inputs_from_internal_snapshots(budget_seconds=budget_seconds)
        )

    def _build_market_temperature_inputs_from_internal_snapshots(self, *, budget_seconds: Optional[float] = None) -> Dict[str, Any]:
        deadline = self._deadline_after(
            self.MARKET_TEMPERATURE_INPUT_BUDGET_SECONDS
            if budget_seconds is None
            else budget_seconds
        )
        indices = self._temperature_panel(
            "indices",
            lambda: self._cached_payload(
                "cn_indices",
                self._fetch_cn_indices_snapshot,
                self._fallback_cn_indices_snapshot,
            ),
            self._fallback_cn_indices_snapshot,
            deadline=deadline,
        )
        breadth = self._temperature_panel(
            "breadth",
            lambda: self._cached_payload(
                "cn_breadth",
                self._fetch_cn_breadth_snapshot,
                self._fallback_cn_breadth_snapshot,
            ),
            self._fallback_cn_breadth_snapshot,
            deadline=deadline,
        )
        flows = self._temperature_panel(
            "flows",
            lambda: self._cached_payload(
                "cn_flows",
                self._fetch_cn_flows_snapshot,
                self._fallback_cn_flows_snapshot,
            ),
            self._fallback_cn_flows_snapshot,
            deadline=deadline,
        )
        sectors = self._temperature_panel(
            "sectors",
            lambda: self._cached_payload(
                "sector_rotation",
                self._fetch_sector_rotation_snapshot,
                self._fallback_sector_rotation_snapshot,
            ),
            self._fallback_sector_rotation_snapshot,
            deadline=deadline,
        )
        rates = self._temperature_panel(
            "rates",
            lambda: self._cached_payload(
                "rates",
                self._fetch_rates_snapshot,
                self._fallback_rates_snapshot,
            ),
            self._fallback_rates_snapshot,
            deadline=deadline,
        )
        volatility = self._temperature_panel(
            "volatility",
            lambda: self._cached_payload(
                "volatility",
                self._fetch_volatility,
                lambda: self._fallback_overview_panel("volatility", "VolatilityCard", "数据源刷新超时，当前显示备用快照"),
            ),
            lambda: self._fallback_overview_panel("volatility", "VolatilityCard", "数据源刷新超时，当前显示备用快照"),
            deadline=deadline,
        )
        rates["items"] = [*rates.get("items", []), *volatility.get("items", [])]
        fx = self._temperature_panel(
            "fx",
            lambda: self._cached_payload(
                "fx_commodities",
                self._fetch_fx_commodities_snapshot,
                self._fallback_fx_commodities_snapshot,
            ),
            self._fallback_fx_commodities_snapshot,
            deadline=deadline,
        )
        futures = self._temperature_panel(
            "futures",
            lambda: self._cached_payload(
                "futures",
                self._fetch_futures_snapshot,
                self._fallback_futures_snapshot,
            ),
            self._fallback_futures_snapshot,
            deadline=deadline,
        )
        sentiment = self._temperature_panel(
            "sentiment",
            lambda: self._cached_payload(
                self.MARKET_SENTIMENT_CACHE_KEY,
                self._fetch_market_sentiment_snapshot,
                lambda: self._fallback_market_snapshot(self.MARKET_SENTIMENT_CACHE_KEY, "unavailable"),
            ),
            lambda: self._fallback_market_snapshot(self.MARKET_SENTIMENT_CACHE_KEY, "unavailable"),
            deadline=deadline,
        )
        crypto = self._temperature_panel(
            "crypto",
            lambda: self._cached_payload(
                "crypto",
                self._fetch_crypto_market_snapshot,
                self._fallback_crypto_market_snapshot,
            ),
            self._fallback_crypto_market_snapshot,
            deadline=deadline,
        )
        return {
            "indices": indices,
            "breadth": breadth,
            "flows": flows,
            "sectors": sectors,
            "rates": rates,
            "fx": fx,
            "futures": futures,
            "sentiment": sentiment,
            "crypto": crypto,
            "fallback_notice": True,
        }

    def _fallback_market_temperature_inputs(self) -> Dict[str, Any]:
        indices = self._fallback_cn_indices_snapshot()
        breadth = self._fallback_cn_breadth_snapshot()
        flows = self._fallback_cn_flows_snapshot()
        sectors = self._fallback_sector_rotation_snapshot()
        rates = self._fallback_rates_snapshot()
        fx = self._fallback_fx_commodities_snapshot()
        futures = self._fallback_futures_snapshot()
        sentiment = {
            "items": [
                self._metric_item("Fear & Greed", "FGI", 50, 0, 0, "score", [48, 49, 50, 50], explanation="备用情绪数据。")
            ],
            "fallbackUsed": True,
        }
        return {
            "indices": indices,
            "breadth": breadth,
            "flows": flows,
            "sectors": sectors,
            "rates": rates,
            "fx": fx,
            "futures": futures,
            "sentiment": sentiment,
            "crypto": self._fallback_crypto_market_snapshot(),
            "fallback_notice": True,
        }

    def _temperature_panel(
        self,
        key: str,
        fetcher: Callable[..., Dict[str, Any]],
        fallback_factory: Callable[[], Dict[str, Any]],
        *,
        deadline: Optional[float] = None,
    ) -> Dict[str, Any]:
        try:
            panel = (
                fallback_factory()
                if deadline is not None and self._deadline_exhausted(deadline)
                else fetcher()
            )
        except Exception:
            panel = fallback_factory()
        category = self._category_for_cache_key(key)
        panel = self._with_market_meta(dict(panel), category)
        panel["items"] = [
            self._with_temperature_input_meta(self._with_item_meta(item, category, panel), category)
            for item in panel.get("items", [])
            if isinstance(item, dict)
        ]
        return self._with_temperature_input_meta(panel, category)

    def _with_temperature_input_meta(self, meta: Dict[str, Any], category: str) -> Dict[str, Any]:
        reliability = classify_market_payload_reliability(meta, category=category)
        return {
            **meta,
            "key": meta.get("key") or meta.get("symbol") or meta.get("panelName"),
            "isReliable": reliability["isReliable"],
            "excluded": reliability["excluded"],
            "excludeReason": reliability["excludeReason"],
            "confidenceWeight": reliability["confidenceWeight"],
            "sourceType": meta.get("sourceType") or reliability.get("sourceType"),
        }

    def _summarize_market_temperature_confidence(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        confidences: List[float] = []
        reliable_count = 0
        fallback_count = 0
        excluded_count = 0
        for key in ("indices", "breadth", "flows", "sectors", "rates", "fx", "futures", "sentiment", "crypto"):
            if key not in inputs:
                continue
            panel = inputs.get(key) or {}
            panel_items = panel.get("items") if isinstance(panel, dict) else []
            if not isinstance(panel_items, list):
                panel_items = []
            if panel_items:
                for item in panel_items:
                    confidence = self._market_data_confidence(item if isinstance(item, dict) else {}, self._category_for_cache_key(key))
                    confidences.append(confidence)
                    if confidence > 0:
                        reliable_count += 1
                    else:
                        fallback_count += 1
                        excluded_count += 1
                continue
            if isinstance(panel, dict):
                confidence = self._market_data_confidence(panel, self._category_for_cache_key(key))
                confidences.append(confidence)
                if confidence > 0:
                    reliable_count += 1
                else:
                    fallback_count += 1
                    excluded_count += 1

        confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
        is_reliable = reliable_count >= 3 and confidence > 0
        return {
            "confidence": confidence,
            "reliableInputCount": reliable_count,
            "fallbackInputCount": fallback_count,
            "excludedInputCount": excluded_count,
            "isReliable": is_reliable,
        }

    def _market_temperature_trust(self, inputs: Dict[str, Any], trust: Dict[str, Any]) -> Dict[str, Any]:
        return self._market_briefing_trust(inputs, trust)

    def _market_briefing_trust(self, inputs: Dict[str, Any], trust: Dict[str, Any]) -> Dict[str, Any]:
        reliable_panel_count = 0
        total_panel_count = 0
        for key in ("indices", "breadth", "flows", "sectors", "rates", "fx", "futures", "sentiment", "crypto"):
            if key not in inputs:
                continue
            panel = inputs.get(key) or {}
            if not isinstance(panel, dict):
                continue
            total_panel_count += 1
            panel_items = panel.get("items") if isinstance(panel.get("items"), list) else []
            category = self._category_for_cache_key(key)
            if panel_items:
                if any(
                    isinstance(item, dict) and self._market_data_confidence(item, category) > 0
                    for item in panel_items
                ):
                    reliable_panel_count += 1
                continue
            if self._market_data_confidence(panel, category) > 0:
                reliable_panel_count += 1

        reliable_count = int(trust.get("reliableInputCount") or 0)
        fallback_count = int(trust.get("fallbackInputCount") or 0)
        total_count = reliable_count + fallback_count
        raw_coverage = reliable_count / total_count if total_count else 0.0
        panel_factor = min(1.0, reliable_panel_count / 3.0) if reliable_panel_count else 0.0
        item_factor = min(1.0, reliable_count / 5.0) if reliable_count else 0.0
        raw_confidence = float(trust.get("confidence") or 0.0)
        trust_gate_coverage = raw_coverage
        if reliable_count >= 5 and reliable_panel_count >= 3 and raw_confidence > 0.25:
            trust_gate_coverage = max(trust_gate_coverage, min(panel_factor, item_factor))
        confidence = round(min(raw_confidence, raw_coverage, panel_factor, item_factor), 2)
        is_reliable = bool(
            trust.get("isReliable")
            and reliable_count >= 5
            and reliable_panel_count >= 3
            and raw_coverage >= 0.25
        )
        trust_gate = self._market_intelligence_trust_gate(inputs, coverage=trust_gate_coverage)
        return {
            **trust,
            "confidence": round(min(confidence, float(trust_gate["scoreCap"])), 2),
            "isReliable": bool(is_reliable and trust_gate["isReliable"]),
            "trustLevel": trust_gate["trustLevel"],
            "sourceTier": trust_gate["sourceTier"],
            "degradationReasons": trust_gate["degradationReasons"],
            "scoreCap": trust_gate["scoreCap"],
            "conclusionAllowed": trust_gate["conclusionAllowed"],
        }

    def _market_intelligence_trust_gate(self, inputs: Dict[str, Any], *, coverage: float) -> Dict[str, Any]:
        source_payloads: List[Dict[str, Any]] = []
        degraded_payloads: List[Dict[str, Any]] = []
        degradation_reasons: List[str] = []
        for key in ("indices", "breadth", "flows", "sectors", "rates", "fx", "futures", "sentiment", "crypto"):
            panel = inputs.get(key)
            if not isinstance(panel, dict):
                continue
            category = self._category_for_cache_key(key)
            panel_items = panel.get("items") if isinstance(panel.get("items"), list) else []
            if panel_items:
                for item in panel_items:
                    if not isinstance(item, dict):
                        continue
                    if self._is_trust_gate_stale_input(item):
                        degradation_reasons.append("stale_source")
                    if self._market_data_confidence(item, category) > 0:
                        source_payloads.append(dict(item))
                    else:
                        degraded_payloads.append(dict(item))
                continue
            if self._is_trust_gate_stale_input(panel):
                degradation_reasons.append("stale_source")
            if self._market_data_confidence(panel, category) > 0:
                source_payloads.append(dict(panel))
            else:
                degraded_payloads.append(dict(panel))

        return evaluate_market_intelligence_trust_from_sources(
            source_payloads or degraded_payloads,
            coverage=coverage,
            degradation_reasons=degradation_reasons,
        )

    @staticmethod
    def _is_trust_gate_stale_input(value: Dict[str, Any]) -> bool:
        return bool(value.get("isStale")) or str(value.get("freshness") or "").lower() == "stale"

    def _real_market_temperature_inputs(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        filtered: Dict[str, Any] = {"fallback_notice": bool(inputs.get("fallback_notice"))}
        for key in ("indices", "breadth", "flows", "sectors", "rates", "fx", "futures", "sentiment", "crypto"):
            panel = inputs.get(key)
            if not isinstance(panel, dict):
                filtered[key] = {"items": []}
                continue
            next_panel = {**panel}
            items = panel.get("items") if isinstance(panel.get("items"), list) else []
            next_panel["items"] = [
                item for item in items
                if isinstance(item, dict) and self._market_data_confidence(item, self._category_for_cache_key(key)) > 0
            ]
            filtered[key] = next_panel
        return filtered

    @staticmethod
    def _market_data_confidence(meta: Dict[str, Any], category: str = "") -> float:
        reliability = classify_market_payload_reliability(meta, category=category)
        return float(reliability["confidenceWeight"]) if reliability["isReliable"] else 0.0

    def _insufficient_market_temperature_scores(self) -> Dict[str, Any]:
        description = "当前真实数据不足，市场温度仅供界面演示。"
        return {
            "overall": self._insufficient_temperature_score(description),
            "usRiskAppetite": self._insufficient_temperature_score(description),
            "cnMoneyEffect": self._insufficient_temperature_score(description),
            "macroPressure": self._insufficient_temperature_score(description),
            "liquidity": self._insufficient_temperature_score(description),
        }

    def _compute_market_temperature_scores(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        us_index_change = self._avg_change(inputs.get("futures", {}).get("items", []), {"NQ", "ES", "YM", "RTY"})
        vix_change = self._item_change(inputs.get("rates", {}).get("items", []), "VIX")
        fear_greed = self._item_value(inputs.get("sentiment", {}).get("items", []), "FGI")
        crypto_change = self._avg_change(inputs.get("crypto", {}).get("items", []), {"BTC", "ETH", "BNB"})
        etf_flow = self._item_value(inputs.get("flows", {}).get("items", []), "CN_ETF")
        us10y_change = self._item_change(inputs.get("rates", {}).get("items", []), "US10Y")
        dxy_change = self._item_change(inputs.get("fx", {}).get("items", []), "DXY")
        cn_index_change = self._avg_change(
            inputs.get("indices", {}).get("items", []),
            {"000001.SH", "399001.SZ", "399006.SZ", "000300.SH", "HSI", "HSTECH", "HSI.HK", "HSTECH.HK"},
        )
        adv_ratio = self._item_value(inputs.get("breadth", {}).get("items", []), "ADV_RATIO")
        limit_up = self._item_value(inputs.get("breadth", {}).get("items", []), "LIMIT_UP")
        limit_down = self._item_value(inputs.get("breadth", {}).get("items", []), "LIMIT_DOWN")
        northbound = self._item_value(inputs.get("flows", {}).get("items", []), "NORTHBOUND")
        usdcnh_change = self._item_change(inputs.get("fx", {}).get("items", []), "USDCNH")
        theme_change = self._avg_change(inputs.get("sectors", {}).get("items", [])[:3], None)
        oil_change = self._item_change(inputs.get("fx", {}).get("items", []), "WTI")
        gold_change = self._item_change(inputs.get("fx", {}).get("items", []), "GOLD")
        dr007_change = self._item_change(inputs.get("rates", {}).get("items", []), "DR007")
        shibor_change = self._item_change(inputs.get("rates", {}).get("items", []), "SHIBOR")

        us = 40
        us += 15 if (us_index_change or 0) > 0 else -8
        us += 15 if (vix_change or -1) < 0 else -10
        us += 15 if (fear_greed or 50) > 50 else -8
        us += 8 if (crypto_change or 0) > 0 else -4
        us += 10 if (etf_flow or 0) > 0 else -5
        us += 10 if (us10y_change or 1) < 0 else -8
        us += 10 if (dxy_change or 1) < 0 else -8

        cn = 35
        cn += 15 if (cn_index_change or 0) > 0 else -8
        cn += 20 if (adv_ratio or 0) > 55 else -10
        cn += 15 if (limit_up or 0) > (limit_down or 0) else -10
        cn += 10 if (northbound or 0) > 0 else -5
        cn += 10 if (usdcnh_change or 1) < 0 else -5
        cn += 10 if (theme_change or 0) > 0 else -5

        macro = 35
        macro += 15 if (us10y_change or 0) > 0 else -6
        macro += 15 if (dxy_change or 0) > 0 else -6
        macro += 15 if (vix_change or 0) > 0 else -6
        macro += 10 if (oil_change or 0) > 0 else -4
        macro += 8 if (gold_change or 0) > 1.5 else 3 if (gold_change or 0) > 0 else 0

        liquidity = 50
        liquidity += 10 if (etf_flow or 0) > 0 else -6
        liquidity += 10 if (dxy_change or 1) < 0 else -8
        liquidity += 10 if (us10y_change or 1) < 0 else -8
        liquidity += 10 if (dr007_change or 1) < 0 else -5
        liquidity += 10 if (shibor_change or 1) < 0 else -5
        liquidity += 10 if (northbound or 0) > 0 else -5
        liquidity += 5 if (crypto_change or 0) > 0 else -3

        us_value = self._clamp_score(us)
        cn_value = self._clamp_score(cn)
        macro_value = self._clamp_score(macro)
        liquidity_value = self._clamp_score(liquidity)
        overall_value = self._clamp_score(us_value * 0.3 + cn_value * 0.3 + liquidity_value * 0.2 + (100 - macro_value) * 0.2)
        return {
            "overall": self._temperature_score(overall_value, "风险偏好改善，但宏观压力仍需关注。"),
            "usRiskAppetite": self._temperature_score(us_value, "美股指数与风险情绪同步改善。"),
            "cnMoneyEffect": self._temperature_score(cn_value, "指数表现尚可，市场宽度决定赚钱效应。"),
            "macroPressure": self._pressure_score(macro_value, "美元、利率与波动率共同决定宏观压力。"),
            "liquidity": self._temperature_score(liquidity_value, "资金环境结合 ETF、利率、美元和跨境资金判断。"),
        }

    def _build_market_briefing_items(
        self,
        inputs: Dict[str, Any],
        scores: Dict[str, Any],
        source: str,
        trust: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        confidence = float((trust or {}).get("confidence", 0.0 if source != "computed" else 1.0))
        if trust and not trust.get("isReliable"):
            return [
                {
                    "title": "当前真实数据不足",
                    "message": "当前真实数据不足，暂不生成强市场判断。",
                    "severity": "warning",
                    "category": "risk",
                    "confidence": confidence,
                },
                {
                    "title": "备用数据已降级",
                    "message": "备用示例数据仅用于保持界面结构，不参与市场温度评分。",
                    "severity": "neutral",
                    "category": "risk",
                    "confidence": confidence,
                },
                {
                    "title": "等待真实行情源",
                    "message": "接入足够真实输入后，再恢复风险偏好、赚钱效应和流动性判断。",
                    "severity": "neutral",
                    "category": "risk",
                    "confidence": confidence,
                },
            ]
        items = [
            {
                "title": f"美股风险偏好{scores['usRiskAppetite']['label']}",
                "message": "主要股指期货与 Fear & Greed 改善时，风险偏好更偏进攻；若 VIX 或美元反向走强，需要降低追涨假设。",
                "severity": "positive" if scores["usRiskAppetite"]["value"] >= 60 else "neutral",
                "category": "us",
                "confidence": confidence,
            },
            {
                "title": f"A股赚钱效应{scores['cnMoneyEffect']['label']}",
                "message": "指数上涨、上涨家数占比和涨停跌停结构共同决定赚钱效应，结构性行情中需关注主题持续性。",
                "severity": "positive" if scores["cnMoneyEffect"]["value"] >= 60 else "neutral",
                "category": "cn",
                "confidence": confidence,
            },
            {
                "title": "宏观压力仍需关注" if scores["macroPressure"]["value"] >= 55 else "宏观压力相对平稳",
                "message": "美债收益率、美元指数、原油和黄金同步上行时，成长股估值与风险资产可能承压。",
                "severity": "warning" if scores["macroPressure"]["value"] >= 55 else "neutral",
                "category": "macro",
                "confidence": confidence,
            },
            {
                "title": f"流动性环境{scores['liquidity']['label']}",
                "message": "ETF 资金、DR007、SHIBOR、美债利率、DXY 与北向资金共同描述可交易流动性。",
                "severity": "positive" if scores["liquidity"]["value"] >= 60 else "neutral",
                "category": "liquidity",
                "confidence": confidence,
            },
            {
                "title": "风险提示",
                "message": "当前部分数据为备用源，仅供趋势参考。" if source != "computed" or inputs.get("fallback_notice") else "若美元、利率和波动率同步升温，应下调风险偏好判断。",
                "severity": "risk" if source != "computed" or inputs.get("fallback_notice") else "warning",
                "category": "risk",
                "confidence": confidence,
            },
        ]
        return items

    @staticmethod
    def _insufficient_temperature_score(description: str) -> Dict[str, Any]:
        return {
            "value": 50,
            "label": "数据不足",
            "trend": "stable",
            "description": description,
        }

    def _temperature_score(self, value: int, description: str) -> Dict[str, Any]:
        return {
            "value": value,
            "label": self._temperature_label(value),
            "trend": "improving" if value >= 61 else "stable" if value >= 46 else "cooling",
            "description": description,
        }

    def _pressure_score(self, value: int, description: str) -> Dict[str, Any]:
        return {
            "value": value,
            "label": "偏高" if value >= 61 else "中性偏高" if value >= 55 else self._temperature_label(value),
            "trend": "rising" if value >= 55 else "stable",
            "description": description,
        }

    @staticmethod
    def _temperature_label(value: int) -> str:
        if value <= 25:
            return "极冷"
        if value <= 45:
            return "偏冷"
        if value <= 60:
            return "中性"
        if value <= 75:
            return "偏暖"
        return "过热"

    @staticmethod
    def _clamp_score(value: float) -> int:
        return int(round(max(0, min(100, value))))

    def _avg_change(self, items: List[Dict[str, Any]], symbols: Optional[set[str]]) -> Optional[float]:
        values = []
        for item in items:
            if symbols is not None and str(item.get("symbol")) not in symbols:
                continue
            value = self._clean_number(item.get("changePercent", item.get("change_pct")))
            if value is not None:
                values.append(value)
        return sum(values) / len(values) if values else None

    def _item_value(self, items: List[Dict[str, Any]], symbol: str) -> Optional[float]:
        for item in items:
            if str(item.get("symbol")) == symbol:
                return self._clean_number(item.get("value", item.get("price")))
        return None

    def _item_change(self, items: List[Dict[str, Any]], symbol: str) -> Optional[float]:
        for item in items:
            if str(item.get("symbol")) == symbol:
                return self._clean_number(item.get("changePercent", item.get("change_pct", item.get("change"))))
        return None

    def _compute_cn_short_sentiment_score(self, metrics: Dict[str, Any]) -> int:
        score = 45
        score += 18 if metrics["limitUpCount"] > metrics["limitDownCount"] * 2 else -12
        score += 12 if metrics["failedLimitUpRate"] <= 25 else -15
        score += 10 if metrics["maxConsecutiveLimitUps"] >= 5 else -8
        score += 8 if metrics["yesterdayLimitUpPerformance"] > 0 else -8
        score += 7 if metrics["highBoardCount"] >= 5 else -4
        return self._clamp_score(score)

    def _build_cn_short_sentiment_summary(self, metrics: Dict[str, Any], score: int) -> str:
        if score >= 60 and metrics["limitUpCount"] > metrics["limitDownCount"]:
            return "涨停家数占优，炸板率可控，短线情绪偏暖。"
        if score <= 45:
            return "涨停偏少或炸板率偏高，短线接力风险偏高。"
        return "短线情绪中性，题材持续性仍需观察。"

    def _card_snapshot(self, items: List[Dict[str, Any]], explanation: Optional[str] = None) -> Dict[str, Any]:
        updated_at = _now_iso()
        payload: Dict[str, Any] = {
            "source": "fallback",
            "sourceLabel": "备用数据",
            "updatedAt": updated_at,
            "asOf": updated_at,
            "items": [self._mark_static_fallback_item(item, updated_at) for item in items],
            "fallbackUsed": True,
            "isFallback": True,
            "warning": FALLBACK_WARNING,
        }
        if explanation:
            payload["explanation"] = explanation
        return payload

    def _computed_metric_item(self, label: str, symbol: str, value: float, unit: str, detail: Optional[str] = None) -> Dict[str, Any]:
        numeric_value = float(value)
        return {
            "name": label,
            "label": label,
            "symbol": symbol,
            "value": round(numeric_value, 3),
            "price": round(numeric_value, 3),
            "change": round(numeric_value, 3),
            "changePercent": round(numeric_value, 3),
            "change_text": self._signed_percent_text(numeric_value) if unit == "%" else f"{numeric_value:.0f}",
            "sparkline": [round(numeric_value, 3)],
            "trend": [round(numeric_value, 3)],
            "unit": unit,
            "source": "yfinance_proxy",
            "sourceLabel": "Yahoo Finance",
            "isFallback": False,
            "risk_direction": self._risk_direction(numeric_value),
            "hover_details": [detail] if detail else [],
        }

    def _unavailable_item(
        self,
        label: str,
        symbol: str,
        message: str,
        updated_at: str,
        detail: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "name": label,
            "label": label,
            "symbol": symbol,
            "value": None,
            "price": None,
            "change": None,
            "changePercent": None,
            "change_text": message,
            "sparkline": [],
            "trend": [],
            "unit": "",
            "source": "unavailable",
            "sourceLabel": "未接入",
            "updatedAt": updated_at,
            "asOf": updated_at,
            "freshness": "fallback",
            "isFallback": True,
            "isUnavailable": True,
            "warning": message,
            "risk_direction": "neutral",
            "hover_details": [detail or message],
            "sourceFreshnessEvidence": {
                "freshness": "unavailable",
                "isUnavailable": True,
                "warning": message,
            },
        }

    def _mark_static_fallback_item(self, item: Dict[str, Any], updated_at: str) -> Dict[str, Any]:
        return {
            **item,
            "source": "fallback",
            "sourceLabel": "备用数据",
            "updatedAt": updated_at,
            "asOf": updated_at,
            "isFallback": True,
            "warning": FALLBACK_WARNING,
        }

    def _metric_item(
        self,
        name: str,
        symbol: str,
        value: float,
        change: float,
        change_percent: float,
        unit: str,
        sparkline: List[float],
        market: Optional[str] = None,
        detail: Optional[str] = None,
        explanation: Optional[str] = None,
    ) -> Dict[str, Any]:
        item: Dict[str, Any] = {
            "name": name,
            "label": name,
            "symbol": symbol,
            "value": value,
            "price": value,
            "change": change,
            "changePercent": change_percent,
            "change_text": f"{change:+.2f}",
            "sparkline": sparkline,
            "trend": sparkline,
            "unit": unit,
            "source": "fallback",
            "sourceLabel": "备用数据",
            "isFallback": True,
            "warning": FALLBACK_WARNING,
            "risk_direction": self._risk_direction(change_percent),
            "hover_details": [text for text in (detail, explanation) if text],
        }
        if market:
            item["market"] = market
        if explanation:
            item["explanation"] = explanation
        return item

    def _breadth_metric_item(
        self,
        name: str,
        symbol: str,
        value: float,
        unit: str,
        as_of: str,
        updated_at: str,
        source: str,
        source_label: str,
        source_type: str,
        *,
        detail: Optional[str] = None,
        explanation: Optional[str] = None,
    ) -> Dict[str, Any]:
        numeric_value = round(float(value), 3)
        item: Dict[str, Any] = {
            "name": name,
            "label": name,
            "symbol": symbol,
            "value": numeric_value,
            "price": numeric_value,
            "change": 0.0,
            "changePercent": 0.0,
            "change_text": self._signed_percent_text(numeric_value) if unit == "%" else f"{numeric_value:.0f}",
            "sparkline": [numeric_value],
            "trend": [numeric_value],
            "unit": unit,
            "source": source,
            "sourceLabel": source_label,
            "sourceType": source_type,
            "updatedAt": updated_at,
            "asOf": as_of,
            "isFallback": False,
            "warning": None,
            "risk_direction": self._breadth_risk_direction(symbol, numeric_value),
            "hover_details": [text for text in (detail, explanation) if text],
        }
        if explanation:
            item["explanation"] = explanation
        return item

    def _breadth_risk_direction(self, symbol: str, value: float) -> str:
        if symbol in {"ADVANCERS", "LIMIT_UP"}:
            return "increasing"
        if symbol in {"DECLINERS", "LIMIT_DOWN"}:
            return "decreasing"
        if value > 50:
            return "increasing"
        if value < 50:
            return "decreasing"
        return "neutral"

    def _cn_breadth_explanation(self, adv_ratio: float) -> str:
        if adv_ratio >= 60:
            return "上涨家数明显占优，TickFlow 市场广度偏强。"
        if adv_ratio >= 50:
            return "上涨家数略占优，TickFlow 市场广度中性偏强。"
        return "下跌家数占优，TickFlow 市场广度偏弱。"

    def _quote_panel(self, panel_name: str, symbols: Dict[str, tuple]) -> PanelPayload:
        items = self._quote_items(symbols)
        payload = self._success_panel(panel_name, items)
        as_of_values = [
            str(item.get("asOf"))
            for item in items
            if isinstance(item, dict)
            and item.get("asOf")
            and not item.get("isUnavailable")
            and not item.get("isFallback")
        ]
        updated_at = _now_iso()
        payload["source"] = "yfinance"
        payload["sourceLabel"] = self._source_label("yfinance")
        payload["sourceType"] = "unofficial_proxy"
        payload["updatedAt"] = updated_at
        payload["asOf"] = min(as_of_values) if as_of_values else updated_at
        payload["fallbackUsed"] = any(bool(item.get("isFallback") or item.get("isUnavailable")) for item in items)
        if payload["fallbackUsed"]:
            payload["warning"] = "部分 Yahoo Finance 行情暂不可用"
        return payload

    def _quote_items(self, symbols: Dict[str, tuple]) -> List[Dict[str, Any]]:
        items = []
        updated_at = _now_iso()
        for symbol, config in symbols.items():
            label, ticker = config[0], config[1]
            unit = config[2] if len(config) > 2 else "pts"
            try:
                quote = self._latest_quote(ticker)
            except Exception:
                items.append(self._quote_unavailable_item(label, symbol, unit, updated_at))
                continue
            value = quote.get("value")
            change_pct = quote.get("change_pct")
            items.append({
                "symbol": symbol,
                "label": label,
                "value": value,
                "unit": unit,
                "change_pct": change_pct,
                "changePercent": change_pct,
                "risk_direction": self._risk_direction(change_pct),
                "trend": quote.get("trend", []),
                "source": "yfinance",
                "sourceLabel": self._source_label("yfinance"),
                "sourceType": "unofficial_proxy",
                "updatedAt": updated_at,
                "asOf": quote.get("asOf") or updated_at,
            })
        return items

    def _quote_unavailable_item(self, label: str, symbol: str, unit: str, updated_at: str) -> Dict[str, Any]:
        message = "Yahoo Finance 行情暂不可用"
        return {
            "symbol": symbol,
            "label": label,
            "value": None,
            "price": None,
            "unit": unit,
            "change": None,
            "change_pct": None,
            "changePercent": None,
            "risk_direction": "neutral",
            "trend": [],
            "source": "yfinance",
            "sourceLabel": self._source_label("yfinance"),
            "sourceType": "unofficial_proxy",
            "updatedAt": updated_at,
            "asOf": updated_at,
            "freshness": "unavailable",
            "isUnavailable": True,
            "isFallback": False,
            "warning": message,
            "degradationReason": "provider_unavailable",
            "sourceFreshnessEvidence": {
                "freshness": "unavailable",
                "isUnavailable": True,
                "warning": message,
            },
        }

    def _latest_quote(self, ticker: str) -> Dict[str, Any]:
        if self._quote_request_memo is None:
            return self._latest_quote_uncached(ticker)
        if ticker in self._quote_request_memo:
            ok, cached = self._quote_request_memo[ticker]
            if ok:
                return copy.deepcopy(cached)
            raise cached
        try:
            quote = self._latest_quote_uncached(ticker)
        except Exception as exc:
            self._quote_request_memo[ticker] = (False, exc)
            raise
        self._quote_request_memo[ticker] = (True, copy.deepcopy(quote))
        return quote

    def _latest_quote_uncached(self, ticker: str) -> Dict[str, Any]:
        frame = fetch_yfinance_quote_history_frame(ticker)
        closes, as_of = self._history_frame_closes_and_as_of(frame, ticker)
        latest = closes[-1]
        previous = closes[-2] if len(closes) > 1 else latest
        change_pct = ((latest - previous) / previous * 100) if previous else 0.0
        volume = self._clean_number(frame["Volume"].tolist()[-1]) if "Volume" in frame else None
        quote = {
            "value": round(latest, 3),
            "change_pct": round(change_pct, 3),
            "trend": [round(value, 3) for value in closes[-8:]],
            "volume": volume,
        }
        if as_of:
            quote["asOf"] = as_of
        return quote

    def _history_frame_closes_and_as_of(self, frame: Any, ticker: str) -> tuple[List[float], Optional[str]]:
        if frame is None or frame.empty:
            raise RuntimeError(f"No market data returned for {ticker}")
        closes = [self._clean_number(value) for value in frame["Close"].tolist()]
        closes = [value for value in closes if value is not None]
        if len(closes) < 2:
            raise RuntimeError(f"Insufficient close prices returned for {ticker}")
        index = getattr(frame, "index", None)
        last_index = None
        if index is not None:
            try:
                last_index = index[-1]
            except Exception:
                last_index = None
        if hasattr(last_index, "to_pydatetime"):
            last_index = last_index.to_pydatetime()
        parsed_as_of = _parse_market_time(last_index)
        as_of = parsed_as_of.isoformat(timespec="seconds") if parsed_as_of else None
        return closes, as_of

    def _atr_item(self) -> Optional[Dict[str, Any]]:
        frame = fetch_yfinance_spy_atr_history_frame()
        if frame is None or frame.empty or len(frame) < 2:
            return None
        trs = []
        rows = frame.tail(15)
        prev_close = None
        for _, row in rows.iterrows():
            high = self._clean_number(row.get("High"))
            low = self._clean_number(row.get("Low"))
            close = self._clean_number(row.get("Close"))
            if high is None or low is None or close is None:
                continue
            tr = high - low if prev_close is None else max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
            prev_close = close
        if not trs:
            return None
        atr = sum(trs) / len(trs)
        return {
            "symbol": "ATR",
            "label": "SPY ATR(14)",
            "value": round(atr, 3),
            "unit": "pts",
            "risk_direction": "increasing" if atr > 8 else "neutral",
            "trend": [round(value, 3) for value in trs[-8:]],
            "source": "yfinance",
        }

    @staticmethod
    def _success_panel(panel_name: str, items: List[Dict[str, Any]]) -> PanelPayload:
        return {
            "panel_name": panel_name,
            "last_refresh_at": _now_iso(),
            "status": "success",
            "items": items,
        }

    def _fallback_overview_panel(self, cache_key: str, panel_name: str, error_message: str) -> PanelPayload:
        updated_at = _now_iso()
        return {
            "panel_name": panel_name,
            "last_refresh_at": updated_at,
            "updatedAt": updated_at,
            "asOf": updated_at,
            "status": "failure",
            "error_message": error_message,
            "warning": FALLBACK_WARNING,
            "source": "fallback",
            "fallbackUsed": True,
            "isFallback": True,
            "items": self._fallback_overview_items(cache_key, updated_at),
        }

    def _fallback_overview_items(self, cache_key: str, updated_at: str) -> List[Dict[str, Any]]:
        fallback_items: Dict[str, List[Dict[str, Any]]] = {
            "indices": [
                {"symbol": "SPX", "label": "S&P 500", "value": 5100.0, "unit": "pts", "change_pct": 0.0, "trend": [5080.0, 5100.0]},
                {"symbol": "NASDAQ", "label": "NASDAQ Composite", "value": 16100.0, "unit": "pts", "change_pct": 0.0, "trend": [16020.0, 16100.0]},
                {"symbol": "DJIA", "label": "Dow Jones Industrial Average", "value": 38600.0, "unit": "pts", "change_pct": 0.0, "trend": [38480.0, 38600.0]},
                {"symbol": "RUT", "label": "Russell 2000", "value": 2040.0, "unit": "pts", "change_pct": 0.0, "trend": [2030.0, 2040.0]},
            ],
            "volatility": [
                {"symbol": "VIX", "label": "VIX", "value": 15.0, "unit": "pts", "change_pct": 0.0, "trend": [15.4, 15.0]},
                {"symbol": "VVIX", "label": "VVIX", "value": 88.0, "unit": "pts", "change_pct": 0.0, "trend": [89.0, 88.0]},
                {"symbol": "VXN", "label": "VXN", "value": 18.0, "unit": "pts", "change_pct": 0.0, "trend": [18.5, 18.0]},
            ],
            "funds_flow": [
                {"symbol": "ETF", "label": "ETF flows", "value": 0.0, "unit": "B USD", "change_pct": 0.0, "trend": [0.0, 0.0]},
                {"symbol": "INSTITUTIONAL", "label": "Institutional net flow", "value": 0.0, "unit": "B USD", "change_pct": 0.0, "trend": [0.0, 0.0]},
                {"symbol": "INDUSTRY", "label": "Industry flow breadth", "value": 0.0, "unit": "score", "change_pct": 0.0, "trend": [0.0, 0.0]},
            ],
            "macro": [
                {"symbol": "US10Y", "label": "10Y yield", "value": 4.5, "unit": "%", "change_pct": 0.0, "trend": [4.48, 4.5]},
                {"symbol": "DXY", "label": "US Dollar Index", "value": 105.0, "unit": "idx", "change_pct": 0.0, "trend": [104.8, 105.0]},
                {"symbol": "GOLD", "label": "Gold futures", "value": 2300.0, "unit": "USD", "change_pct": 0.0, "trend": [2290.0, 2300.0]},
                {"symbol": "OIL", "label": "WTI crude", "value": 82.0, "unit": "USD", "change_pct": 0.0, "trend": [81.5, 82.0]},
            ],
        }
        return [
            {
                **item,
                "risk_direction": self._risk_direction(item.get("change_pct")),
                "source": "fallback",
                "sourceLabel": self._source_label("fallback"),
                "updatedAt": updated_at,
                "asOf": updated_at,
                "freshness": "fallback",
                "isFallback": True,
                "warning": FALLBACK_WARNING,
            }
            for item in fallback_items.get(cache_key, [])
        ]

    def _fallback_panel(self, panel_name: str, error_message: str) -> PanelPayload:
        return {
            "panel_name": panel_name,
            "last_refresh_at": _now_iso(),
            "status": "failure",
            "error_message": error_message,
            "items": [],
        }

    @staticmethod
    def _risk_direction(change_pct: Any) -> str:
        if change_pct is None:
            return "neutral"
        return "decreasing" if float(change_pct) >= 0 else "increasing"

    @staticmethod
    def _percent_change(previous: Optional[float], current: Optional[float]) -> Optional[float]:
        if previous in (None, 0) or current is None:
            return None
        return (float(current) - float(previous)) / float(previous) * 100

    @staticmethod
    def _signed_percent_text(value: Optional[float]) -> str:
        if value is None:
            return "N/A"
        return f"{value:+.2f}%"

    @staticmethod
    def _compact_usd(value: Optional[float]) -> str:
        if value is None:
            return "N/A"
        abs_value = abs(value)
        if abs_value >= 1_000_000_000:
            return f"${value / 1_000_000_000:.2f}B"
        if abs_value >= 1_000_000:
            return f"${value / 1_000_000:.2f}M"
        return f"${value:.0f}"

    @staticmethod
    def _clean_number(value: Any) -> Optional[float]:
        try:
            number = float(value)
        except Exception:
            return None
        if math.isnan(number) or math.isinf(number):
            return None
        return number
