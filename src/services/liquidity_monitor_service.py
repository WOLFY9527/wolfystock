# -*- coding: utf-8 -*-
"""Cache-only advisory liquidity monitor service."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional

from src.contracts.source_confidence import (
    SOURCE_CONFIDENCE_CONTRACT_VERSION,
    coerce_source_confidence_contract,
    evaluate_market_intelligence_trust_from_sources,
)
from src.services.liquidity_impulse_synthesis_adapter import build_liquidity_impulse_synthesis_payload
from src.services.data_source_router import DataSourceRouteRequest, DataSourceRouter
from src.services.market_cache import MarketCache, market_cache
from src.services.market_data_source_registry import project_source_provenance, resolve_source_type
from src.services.market_overview_binance_transport import fetch_binance_funding_row
from src.services.market_overview_yfinance_transport import fetch_yfinance_quote_history_frame
from src.services.vix_metadata import normalize_vix_quote_metadata
from src.storage import DatabaseManager


CN_TZ = timezone(timedelta(hours=8))
ADVISORY_DISCLOSURE = "仅用于观察市场流动性环境，非买卖建议，不触发扫描、回测或组合动作。"
FRESHNESS_ORDER = {"live": 0, "cached": 1, "delayed": 2, "stale": 3, "fallback": 4, "mock": 5, "error": 6, "unavailable": 7}
EVIDENCE_FRESHNESS_ORDER = {**FRESHNESS_ORDER, "fresh": 0, "partial": 2.5, "synthetic": 5}
RELIABLE_FRESHNESS = {"live", "cached", "delayed"}
POSSIBLE_WEIGHT = 49
CRYPTO_FUNDING_BACKFILL_MAX_AGE = timedelta(hours=12)
SOURCE_CONFIDENCE_BY_TYPE = {
    "official_public": 1.0,
    "exchange_public": 1.0,
    "public_proxy": 0.8,
    "unofficial_proxy": 0.7,
    "cache_snapshot": 0.6,
    "fallback_static": 0.4,
    "synthetic_fixture": 0.2,
    "delayed_fixture": 0.4,
    "malformed_fixture": 0.0,
    "disabled_live_stub": 0.0,
    "missing": 0.0,
}
SOURCE_TYPE_FRESHNESS_FLOOR = {
    "fallback_static": "fallback",
    "synthetic_fixture": "mock",
    "delayed_fixture": "delayed",
    "malformed_fixture": "unavailable",
    "disabled_live_stub": "unavailable",
    "missing": "unavailable",
}
OFFICIAL_PANEL_REQUIRED_SYMBOL_GROUPS = {
    "volatility": ({"VIX", "VIXCLS"},),
    "rates": ({"US2Y"}, {"US10Y"}, {"US30Y"}),
    "macro": ({"VIX", "VIXCLS"}, {"US2Y"}, {"US10Y"}, {"US30Y"}, {"USD_TWI"}),
}
LIQUIDITY_SCORE_ROUTE_REJECTED_REASON = "source_authority_router_rejected"
LIQUIDITY_SCORE_ROUTE_PROVIDER_ALIASES = {
    "pytdx": "pytdx_existing_baseline",
    "yahoo": "yfinance_current_baseline",
    "yfinance": "yfinance_current_baseline",
    "yfinance_proxy": "yfinance_current_baseline",
}
LIQUIDITY_SCORE_ROUTE_REQUESTS = {
    "crypto_spot_momentum": {
        "market": "crypto",
        "assetType": "crypto",
        "capability": "crypto_ticker",
        "freshnessNeed": "live",
        "productId": "BTC-USD",
    },
    "vix_pressure": {
        "market": "US",
        "assetType": "index",
        "capability": "quote",
        "freshnessNeed": "delayed",
        "symbol": "VIX",
    },
    "usd_pressure": {
        "market": "forex",
        "assetType": "forex",
        "capability": "quote",
        "freshnessNeed": "delayed",
        "symbol": "DXY",
    },
    "us_rates_pressure": {
        "market": "US",
        "assetType": "rates",
        "capability": "macro_rate",
        "freshnessNeed": "delayed",
        "symbol": "US10Y",
    },
    "fed_liquidity": {
        "market": "US",
        "assetType": "macro",
        "capability": "fed_liquidity",
        "freshnessNeed": "delayed",
        "symbol": "WALCL",
    },
    "us_etf_flow_proxy": {
        "market": "US",
        "assetType": "fund",
        "capability": "etf_flow",
        "freshnessNeed": "delayed",
        "symbol": "ETF",
    },
    "us_breadth_proxy": {
        "market": "US",
        "assetType": "equity",
        "capability": "breadth",
        "freshnessNeed": "delayed",
        "symbol": "SPY",
    },
}

LIQUIDITY_INDICATOR_REQUIRED_INPUTS = {
    "crypto_spot_momentum": ("BTC", "ETH", "BNB"),
    "crypto_funding": ("BTC_FUNDING", "ETH_FUNDING"),
    "vix_pressure": ("VIX",),
    "usd_pressure": ("USD_TWI",),
    "us_rates_pressure": ("US2Y", "US10Y", "US30Y", "SOFR", "US10Y2Y", "US10Y3M"),
    "fed_liquidity": ("FED_ASSETS", "FED_RRP", "TGA", "RESERVES"),
    "us_etf_flow_proxy": ("ETF",),
    "us_breadth_proxy": ("SECTORS_UP", "SECTORS_DOWN", "RSP_SPY", "IWM_SPY", "QQQ_SPY"),
    "cn_hk_index_context": ("000001.SH", "399001.SZ", "HSI.HK", "HSTECH.HK", "CN00Y"),
    "cn_hk_flows": ("NORTHBOUND", "SOUTHBOUND", "CN_ETF", "MARGIN_BALANCE", "MAINLAND_MAIN"),
    "cn_money_market_rates": ("DR007", "SHIBOR"),
    "futures_premarket": ("NQ", "ES", "YM", "RTY"),
}

LIQUIDITY_INPUT_ALIASES = {
    "VIXCLS": "VIX",
}
EVIDENCE_INPUT_METADATA_FIELDS = (
    "sourceTier",
    "trustLevel",
    "observationOnly",
    "sourceAuthorityAllowed",
    "scoreContributionAllowed",
    "sourceAuthorityReason",
    "sourceAuthorityRouteRejected",
    "routeRejectedReasonCodes",
    "officialSeriesId",
    "officialObservationDate",
    "officialAsOf",
)

LIQUIDITY_INDICATOR_ACTIVATION_HINTS = {
    "crypto_spot_momentum": "Binance 现货输入 fresh 时可直接计分；缺少 BTC / ETH / BNB 时保持不可用。",
    "crypto_funding": "仅在现有 Binance Futures funding 回填和 BTC / ETH 现货上下文可用时激活。",
    "vix_pressure": "现有宏观 / 波动率快照可用时激活；yfinance proxy 会被 trust gate 限制为延迟或部分。",
    "usd_pressure": "官方 FRED trade-weighted USD 证据新鲜且授权时可计分；缺少 DTWEXBGS 时仅保留观察态。",
    "us_rates_pressure": "官方利率快照优先；没有 US2Y / US10Y / US30Y / SOFR 时只能退化为代理或不可用。",
    "fed_liquidity": "官方 FRED Fed liquidity 组需要 WALCL / RRPONTSYD / WTREGEN / WRESBAL 全量新鲜官方行；部分覆盖仅作观测。",
    "us_etf_flow_proxy": "激活现有 `funds_flow` snapshot 或 Market Overview 的 SPY / QQQ / IWM proxy；缺少 ETF 条目时保持不可用。",
    "us_breadth_proxy": "激活现有 sector ETF breadth proxy；需要 SECTORS_UP、SECTORS_DOWN 和相对强弱代理。",
    "cn_hk_index_context": "CN / HK 指数上下文只能来自现有快照，缺少可用指数条目时保持不可用。",
    "cn_hk_flows": "No audited CN/HK flow provider；只有非 fallback 的 `cn_flows` 快照才会参与评分。",
    "cn_money_market_rates": "仅在 `rates` 或 `macro` 快照里有 DR007 / SHIBOR 时激活，缺失则保持观测态。",
    "futures_premarket": "现有 futures snapshot 或延迟 proxy 可用时才激活；没有真实期货快照时保持不可用。",
}

LIQUIDITY_INDICATOR_PROVIDER_ACTIVATION = {
    "crypto_spot_momentum": {
        "requiredProviderClass": "exchange_public.crypto_spot",
        "paidDataLikelyRequired": False,
        "observationOnly": False,
        "proxyOnly": False,
        "scoreContributionAllowed": True,
    },
    "crypto_funding": {
        "requiredProviderClass": "exchange_public.crypto_funding",
        "paidDataLikelyRequired": False,
        "observationOnly": True,
        "proxyOnly": False,
        "scoreContributionAllowed": False,
    },
    "vix_pressure": {
        "requiredProviderClass": "official_public.vix_or_volatility",
        "paidDataLikelyRequired": False,
        "observationOnly": False,
        "proxyOnly": True,
        "scoreContributionAllowed": True,
        "requiresRealSourceForScore": True,
    },
    "usd_pressure": {
        "requiredProviderClass": "official_public.usd_pressure",
        "paidDataLikelyRequired": False,
        "observationOnly": False,
        "proxyOnly": True,
        "scoreContributionAllowed": True,
        "requiresRealSourceForScore": True,
    },
    "us_rates_pressure": {
        "requiredProviderClass": "official_public.us_treasury_curve",
        "paidDataLikelyRequired": False,
        "observationOnly": False,
        "proxyOnly": True,
        "scoreContributionAllowed": True,
        "requiresRealSourceForScore": True,
    },
    "fed_liquidity": {
        "requiredProviderClass": "official_public.fed_liquidity",
        "paidDataLikelyRequired": False,
        "observationOnly": False,
        "proxyOnly": False,
        "scoreContributionAllowed": True,
        "requiresRealSourceForScore": True,
    },
    "us_etf_flow_proxy": {
        "requiredProviderClass": "authorized.us_etf_flow",
        "paidDataLikelyRequired": True,
        "observationOnly": False,
        "proxyOnly": True,
        "scoreContributionAllowed": True,
        "requiresRealSourceForScore": True,
    },
    "us_breadth_proxy": {
        "requiredProviderClass": "official_or_authorized.us_market_breadth",
        "paidDataLikelyRequired": True,
        "observationOnly": False,
        "proxyOnly": True,
        "scoreContributionAllowed": True,
        "requiresRealSourceForScore": True,
    },
    "cn_hk_index_context": {
        "requiredProviderClass": "official_public.cn_hk_index_snapshot",
        "paidDataLikelyRequired": False,
        "observationOnly": True,
        "proxyOnly": False,
        "scoreContributionAllowed": False,
    },
    "cn_hk_flows": {
        "requiredProviderClass": "authorized.cn_hk_connect_flow",
        "paidDataLikelyRequired": True,
        "observationOnly": True,
        "proxyOnly": False,
        "scoreContributionAllowed": False,
    },
    "cn_money_market_rates": {
        "requiredProviderClass": "official_public.cn_money_market_rates",
        "paidDataLikelyRequired": False,
        "observationOnly": True,
        "proxyOnly": False,
        "scoreContributionAllowed": False,
    },
    "futures_premarket": {
        "requiredProviderClass": "exchange_or_broker_authorized.index_futures",
        "paidDataLikelyRequired": True,
        "observationOnly": True,
        "proxyOnly": True,
        "scoreContributionAllowed": False,
    },
}


@dataclass(frozen=True)
class PanelState:
    key: str
    payload: Dict[str, Any]
    source: str
    freshness: str
    as_of: Optional[str]
    updated_at: Optional[str]
    is_fallback: bool
    is_stale: bool


class LiquidityMonitorService:
    """Build a removable advisory liquidity monitor from existing cached market surfaces."""

    def __init__(
        self,
        *,
        cache: MarketCache = market_cache,
        db: Optional[DatabaseManager] = None,
    ) -> None:
        self.cache = cache
        self.db = db or DatabaseManager.get_instance()
        self._external_provider_calls_used = False

    def get_liquidity_monitor(self) -> Dict[str, Any]:
        self._external_provider_calls_used = False
        panels = {
            key: self._read_panel(key)
            for key in ("crypto", "volatility", "rates", "macro", "fx_commodities", "funds_flow", "us_breadth", "cn_indices", "cn_breadth", "cn_flows", "futures")
        }
        indicators = [
            self._crypto_spot_indicator(panels["crypto"]),
            self._crypto_funding_indicator(panels["crypto"]),
            self._vix_indicator(panels["volatility"], panels["macro"]),
            self._usd_pressure_indicator(panels["macro"]),
            self._us_rates_indicator(panels["rates"], panels["macro"]),
            self._fed_liquidity_indicator(panels["macro"]),
            self._us_etf_flow_indicator(panels["funds_flow"]),
            self._us_breadth_indicator(panels["us_breadth"]),
            self._cn_hk_index_indicator(panels["cn_indices"]),
            self._cn_hk_flows_indicator(panels["cn_flows"], panels["cn_breadth"]),
            self._cn_money_rates_indicator(panels["rates"]),
            self._futures_indicator(panels["futures"]),
        ]

        included = [item for item in indicators if item["includedInScore"]]
        included_weight = sum(int(item["scoreWeight"]) for item in included)
        confidence = min(0.95, round(included_weight / POSSIBLE_WEIGHT, 2)) if POSSIBLE_WEIGHT else 0.0
        score_value = 50 + sum(int(item["scoreContribution"]) for item in included)
        reliable_indicator_count = len(included)

        if reliable_indicator_count < 3 or confidence < 0.25:
            score_value = 50
            regime = "unavailable"
        else:
            regime = self._regime(score_value)

        available_freshness = [str(item["freshness"]) for item in indicators if item["status"] != "unavailable"]
        available_as_of = [str(item["updatedAt"] or "") for item in indicators if item["status"] != "unavailable" and item.get("updatedAt")]

        return {
            "endpoint": "/api/v1/market/liquidity-monitor",
            "generatedAt": self._now().isoformat(timespec="seconds"),
            "score": {
                "value": max(0, min(100, int(round(score_value)))),
                "regime": regime,
                "confidence": confidence,
                "includedIndicatorCount": reliable_indicator_count,
                "possibleIndicatorWeight": POSSIBLE_WEIGHT,
                "includedIndicatorWeight": included_weight,
            },
            "freshness": {
                "status": self._weakest_freshness(available_freshness) if available_freshness else "unavailable",
                "weakestIndicatorFreshness": self._weakest_freshness(available_freshness) if available_freshness else "unavailable",
                "latestAsOf": max(available_as_of) if available_as_of else None,
            },
            "indicators": indicators,
            "liquidityImpulseSynthesis": self._build_liquidity_impulse_synthesis_payload(indicators),
            "advisoryDisclosure": ADVISORY_DISCLOSURE,
            "sourceMetadata": {
                "externalProviderCalls": self._external_provider_calls_used,
                "providerRuntimeChanged": False,
                "marketCacheMutation": False,
            },
        }

    @staticmethod
    def _build_liquidity_impulse_synthesis_payload(indicators: List[Dict[str, Any]]) -> Dict[str, Any]:
        return build_liquidity_impulse_synthesis_payload(indicators)

    def _read_panel(self, key: str) -> PanelState:
        cache_candidate = self._read_market_cache_candidate(key)
        snapshot_candidate = self._read_market_overview_snapshot_candidate(key)
        if key in OFFICIAL_PANEL_REQUIRED_SYMBOL_GROUPS and cache_candidate is not None and snapshot_candidate is not None:
            return self._select_preferred_official_panel_candidate(key, cache_candidate, snapshot_candidate)
        if cache_candidate is not None:
            return cache_candidate
        if snapshot_candidate is not None:
            return snapshot_candidate
        return self._build_panel_state(key, {}, expired=False, from_snapshot=False)

    def _read_market_cache_candidate(self, key: str) -> Optional[PanelState]:
        entry = self.cache.get(key)
        if not entry or not isinstance(entry.data, dict):
            return None
        return self._build_panel_state(
            key,
            copy.deepcopy(entry.data),
            expired=entry.expires_at <= self._now(),
            from_snapshot=False,
        )

    def _read_market_overview_snapshot_candidate(self, key: str) -> Optional[PanelState]:
        snapshot = self.db.get_market_overview_snapshot(f"market_overview:{key}")
        payload = copy.deepcopy(snapshot.get("payload") or {}) if isinstance(snapshot, dict) else {}
        if not isinstance(payload, dict) or not payload:
            return None
        return self._build_panel_state(key, payload, expired=False, from_snapshot=True)

    def _build_panel_state(
        self,
        key: str,
        payload: Dict[str, Any],
        *,
        expired: bool,
        from_snapshot: bool,
    ) -> PanelState:
        if from_snapshot:
            payload = self._normalize_market_overview_snapshot_payload(key, payload)
        source = str(payload.get("source") or "unavailable")
        freshness = str(payload.get("freshness") or ("fallback" if payload.get("isFallback") or payload.get("fallbackUsed") else "unavailable"))
        payload_source_type = str(payload.get("sourceType") or "").lower()
        item_freshness_floor = self._panel_item_freshness_floor(payload)
        has_non_fallback_official_snapshot_rows = (
            from_snapshot and source == "mixed" and self._snapshot_has_non_fallback_official_rows(payload)
        )
        panel_fallback_flag = bool(payload.get("isFallback") or payload.get("fallbackUsed")) and not has_non_fallback_official_snapshot_rows
        freshness = self._freshness_with_source_type(
            freshness,
            payload_source_type,
            is_fallback=panel_fallback_flag,
            is_stale=bool(payload.get("isStale")),
        )
        if item_freshness_floor:
            freshness = self._weakest_freshness([freshness, item_freshness_floor])
        is_fallback = bool(
            panel_fallback_flag
            or source in {"fallback", "mock", "unavailable"}
            or freshness in {"fallback", "mock"}
        )
        if has_non_fallback_official_snapshot_rows:
            is_fallback = False
        if source == "mock":
            freshness = "mock"
        elif freshness == "mock":
            source = "mock"
        if expired:
            freshness = "stale"
        is_stale = freshness == "stale"
        updated_at = self._text(payload.get("updatedAt") or payload.get("last_update") or payload.get("last_refresh_at"))
        as_of = self._text(payload.get("asOf") or payload.get("last_update") or payload.get("last_refresh_at") or updated_at)
        return PanelState(
            key=key,
            payload=payload,
            source=source,
            freshness=freshness,
            as_of=as_of,
            updated_at=updated_at,
            is_fallback=is_fallback,
            is_stale=is_stale,
        )

    def _select_preferred_official_panel_candidate(
        self,
        key: str,
        cache_candidate: PanelState,
        snapshot_candidate: PanelState,
    ) -> PanelState:
        snapshot_has_usable_official_rows = self._panel_has_usable_official_rows(key, snapshot_candidate)
        cache_has_usable_official_rows = (
            not cache_candidate.is_stale
            and self._panel_has_usable_official_rows(key, cache_candidate)
        )
        if snapshot_has_usable_official_rows and not cache_has_usable_official_rows:
            return snapshot_candidate
        if cache_has_usable_official_rows and not snapshot_has_usable_official_rows:
            return cache_candidate
        if snapshot_has_usable_official_rows and cache_has_usable_official_rows:
            return snapshot_candidate if self._panel_candidate_is_newer(snapshot_candidate, cache_candidate) else cache_candidate
        return cache_candidate

    def _panel_candidate_is_newer(self, candidate: PanelState, baseline: PanelState) -> bool:
        candidate_time = self._panel_candidate_time(candidate)
        baseline_time = self._panel_candidate_time(baseline)
        if candidate_time is None:
            return False
        if baseline_time is None:
            return True
        return candidate_time > baseline_time

    def _panel_candidate_time(self, panel: PanelState) -> Optional[datetime]:
        return self._parse_time(panel.as_of or panel.updated_at)

    def _panel_has_usable_official_rows(self, key: str, panel: PanelState) -> bool:
        items = panel.payload.get("items")
        groups = OFFICIAL_PANEL_REQUIRED_SYMBOL_GROUPS.get(key)
        if not isinstance(items, list) or not groups:
            return False
        return all(self._panel_has_usable_official_symbol_group(panel, items, group) for group in groups)

    def _panel_has_usable_official_symbol_group(
        self,
        panel: PanelState,
        items: List[Any],
        group: set[str],
    ) -> bool:
        for raw in items:
            if not isinstance(raw, dict):
                continue
            symbol = str(raw.get("symbol") or "")
            if symbol not in group:
                continue
            if self._item_source_type(raw, panel) != "official_public":
                continue
            if self._item_freshness(raw, panel) not in RELIABLE_FRESHNESS:
                continue
            if not self._is_non_fallback_official_row(raw, panel.payload):
                continue
            if not self._is_required_official_symbol_usable(symbol, raw, panel):
                continue
            return True
        return False

    def _is_required_official_symbol_usable(self, symbol: str, item: Dict[str, Any], panel: PanelState) -> bool:
        if symbol in {"US2Y", "US10Y", "US30Y"}:
            return self._is_yield_item_usable(item, panel)
        return self._is_vix_item_usable(item, panel)

    def _normalize_market_overview_snapshot_payload(self, key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if key not in {"rates", "macro", "volatility"}:
            return payload
        raw_items = payload.get("items")
        if not isinstance(raw_items, list):
            return payload

        official_freshness_values: List[str] = []
        normalized_items: List[Any] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                normalized_items.append(raw)
                continue
            item = raw
            if self._is_non_fallback_official_row(item, payload):
                freshness = str(item.get("freshness") or "").lower()
                if freshness not in FRESHNESS_ORDER:
                    derived = self._derive_official_macro_freshness(item, payload)
                    if derived:
                        item["freshness"] = derived
                        item["isStale"] = derived == "stale"
                        freshness = derived
                if freshness in RELIABLE_FRESHNESS or freshness == "stale":
                    official_freshness_values.append(freshness)
            normalized_items.append(item)

        payload["items"] = normalized_items
        if not official_freshness_values:
            return payload

        panel_freshness = str(payload.get("freshness") or "").lower()
        normalized_freshness = self._weakest_freshness(official_freshness_values)
        if panel_freshness not in RELIABLE_FRESHNESS | {"stale"} or (
            normalized_freshness == "stale" and panel_freshness != "stale"
        ):
            payload["freshness"] = normalized_freshness
        if str(payload.get("source") or "").lower() == "mixed" and payload.get("fallbackUsed"):
            payload["isFallback"] = False
        return payload

    def _snapshot_has_non_fallback_official_rows(self, payload: Dict[str, Any]) -> bool:
        items = payload.get("items")
        if not isinstance(items, list):
            return False
        return any(isinstance(item, dict) and self._is_non_fallback_official_row(item, payload) for item in items)

    def _is_non_fallback_official_row(self, item: Dict[str, Any], payload: Dict[str, Any]) -> bool:
        source_type = str(item.get("sourceType") or payload.get("sourceType") or "").lower()
        source = str(item.get("source") or payload.get("source") or "").lower()
        is_fallback = bool(item.get("isFallback") or item.get("fallbackUsed") or source in {"fallback", "mock", "unavailable"})
        return source_type == "official_public" and source in {"fred", "treasury"} and not is_fallback

    def _derive_official_macro_freshness(self, item: Dict[str, Any], payload: Dict[str, Any]) -> Optional[str]:
        as_of = self._parse_time(item.get("asOf") or item.get("updatedAt") or payload.get("asOf") or payload.get("updatedAt"))
        if as_of is None:
            return None
        current = self._now().astimezone(CN_TZ)
        days_old = max(0, (current.date() - as_of.date()).days)
        return "delayed" if days_old <= 3 else "stale"

    def _crypto_spot_indicator(self, panel: PanelState) -> Dict[str, Any]:
        breadth = self._extract_crypto_breadth(panel)
        if breadth is None:
            return self._indicator("crypto_spot_momentum", "Crypto 现货动量", panel, "unavailable", 0, 6, False, "BTC / ETH / BNB 缓存不足")
        signal = self._direction_from_counts(int(breadth["advancers"]), int(breadth["decliners"]))
        status = "live" if int(breadth["count"]) == 3 and breadth["freshness"] in {"live", "cached"} else "partial"
        return self._indicator(
            "crypto_spot_momentum",
            "Crypto 现货动量",
            panel,
            status,
            6 if signal > 0 else -6 if signal < 0 else 0,
            6,
            True,
            f"{int(breadth['advancers'])}/{int(breadth['count'])} 上涨 | 均值 {float(breadth['avg_change']):+.2f}%",
            freshness=str(breadth["freshness"]),
            evidence=self._indicator_evidence(
                status=status,
                freshness=str(breadth["freshness"]),
                inputs=[
                    self._source_confidence_input_from_item(
                        item,
                        panel,
                        key=str(item.get("symbol") or ""),
                        label=str(item.get("label") or item.get("symbol") or ""),
                    )
                    for item, _ in breadth["entries"]
                ],
                expected_input_count=3,
            ),
        )

    def _crypto_funding_indicator(self, panel: PanelState) -> Dict[str, Any]:
        items = [item for item in self._reliable_items(panel, None) if str(item.get("symbol") or "").endswith("_FUNDING") and self._numeric(item.get("value")) is not None]
        funding_panel = panel
        if not items:
            fetched_panel = self._fetch_live_crypto_funding_panel(panel)
            if fetched_panel is not None:
                funding_panel = fetched_panel
            items = [
                item
                for item in self._reliable_items(funding_panel, None)
                if str(item.get("symbol") or "").endswith("_FUNDING") and self._numeric(item.get("value")) is not None
            ]
        if not items:
            message = "Binance Futures funding 暂不可用"
            if not self._has_live_crypto_context(panel):
                message = "缺少 BTC/ETH 现货上下文，未触发实时 funding 查询"
            elif funding_panel is not panel and funding_panel.freshness == "stale":
                message = "Binance Futures funding 数据过期"
            unavailable_freshness = "unavailable" if funding_panel.freshness in RELIABLE_FRESHNESS else funding_panel.freshness
            return self._indicator(
                "crypto_funding",
                "Crypto Funding",
                funding_panel,
                "unavailable",
                0,
                0,
                False,
                message,
                freshness=unavailable_freshness,
            )
        avg_value = sum(float(self._numeric(item.get("value")) or 0.0) for item in items) / len(items)
        freshness = self._weakest_freshness([self._item_freshness(item, funding_panel) for item in items])
        values = [
            f"{str(item.get('symbol') or '').replace('_FUNDING', '')} {float(self._numeric(item.get('value')) or 0.0):+.4f}%"
            for item in items
        ]
        source_meta = project_source_provenance(
            source=items[0].get("source") or funding_panel.source,
            source_type=items[0].get("sourceType"),
            source_label=items[0].get("sourceLabel"),
            freshness=freshness,
            is_fallback=bool(items[0].get("isFallback") or items[0].get("fallbackUsed") or funding_panel.is_fallback),
            is_stale=bool(items[0].get("isStale") or funding_panel.is_stale),
        )
        source_label = source_meta["sourceLabel"]
        source_type = source_meta["sourceType"]
        direct_backfill = funding_panel.key == "crypto_funding_live" or any(
            str(item.get("degradationReason") or "") == "direct_provider_backfill"
            for item in items
        )
        status = "live" if len(items) >= 2 and freshness == "live" and not direct_backfill else "partial"
        return self._indicator(
            "crypto_funding",
            "Crypto Funding",
            funding_panel,
            status,
            0,
            0,
            False,
            f"{' | '.join(values)} | 均值 {avg_value:+.4f}% | 来源 {source_label} | 类型 {source_type}",
            freshness=freshness,
            evidence=self._indicator_evidence(
                status=status,
                freshness=freshness,
                inputs=[
                    self._source_confidence_input_from_item(
                        item,
                        funding_panel,
                        key=str(item.get("symbol") or ""),
                        label=str(item.get("label") or item.get("symbol") or ""),
                    )
                    for item in items
                ],
                expected_input_count=2,
            ),
        )

    def _vix_indicator(self, panel: PanelState, macro_panel: PanelState) -> Dict[str, Any]:
        selected = self._preferred_symbol_item((panel, macro_panel), {"VIX", "VIXCLS"}, validator=self._is_vix_item_usable)
        if selected is not None:
            panel, item = selected
        else:
            item = None
        if item is None:
            proxy_panel = self._fetch_macro_proxy_panel(
                "volatility_proxy",
                [{"symbol": "VIX", "label": "VIX", "ticker": "^VIX", "unit": "pts"}],
            )
            if proxy_panel is not None:
                panel = proxy_panel
                item = self._first_reliable_item(panel, {"VIX"})
        if item is None:
            return self._indicator(
                "vix_pressure",
                "VIX / 波动率压力",
                panel,
                "unavailable",
                0,
                8,
                False,
                self._summary_with_metadata(
                    "未读取到可靠 VIX",
                    source="yfinance_proxy",
                    source_label="Yahoo Finance",
                    source_type="unofficial_proxy",
                    reason=self._panel_unavailable_reason(panel, "VIX 代理不可用"),
                ),
            )
        item = normalize_vix_quote_metadata(
            {
                **item,
                "source": item.get("source") or panel.source,
                "sourceLabel": item.get("sourceLabel") or panel.payload.get("sourceLabel"),
                "sourceType": item.get("sourceType") or panel.payload.get("sourceType"),
                "freshness": self._item_freshness(item, panel),
            }
        )
        change = self._change_value(item)
        value = self._numeric(item.get("value") or item.get("price"))
        contribution = 0
        if change is not None and change < 0:
            contribution = 8
        elif change is not None and change > 0:
            contribution = -8
        elif value is not None and value <= 16:
            contribution = 8
        elif value is not None and value >= 25:
            contribution = -8
        freshness = str(item.get("freshness") or self._item_freshness(item, panel))
        source_type = self._item_source_type(item, panel)
        status = (
            "live"
            if freshness in {"live", "cached"}
            and str(item.get("source") or panel.source) != "yfinance_proxy"
            and source_type != "official_public"
            else "partial"
        )
        return self._indicator(
            "vix_pressure",
            "VIX / 波动率压力",
            panel,
            status,
            contribution,
            8,
            True,
            self._summary_with_metadata(self._signed_percent_text(change), item=item, freshness=freshness),
            freshness=freshness,
            evidence=self._indicator_evidence(
                status=status,
                freshness=freshness,
                inputs=[
                    self._source_confidence_input_from_item(
                        item,
                        panel,
                        key=str(item.get("symbol") or "VIX"),
                        label=str(item.get("label") or "VIX"),
                    )
                ],
                expected_input_count=1,
            ),
        )

    def _usd_pressure_indicator(self, macro_panel: PanelState) -> Dict[str, Any]:
        official_components = self._extract_official_usd_pressure_components(macro_panel)
        score_grade_components = [
            component
            for component in official_components
            if self._usd_pressure_component_score_grade(component)
        ]
        if score_grade_components:
            components = score_grade_components
            positive = sum(1 for component in components if float(component["signal"]) > 0)
            negative = sum(1 for component in components if float(component["signal"]) < 0)
            direction = self._direction_from_counts(positive, negative)
            summary = " | ".join(
                f"{component['label']} {self._signed_percent_text(float(component['change']))}"
                for component in components
            )
            freshness = self._weakest_freshness([str(component["freshness"]) for component in components])
            return self._indicator(
                "usd_pressure",
                "USD Pressure / 美元压力",
                macro_panel,
                "live",
                -6 if direction > 0 else 6 if direction < 0 else 0,
                6,
                True,
                self._summary_with_component_metadata(summary, components, freshness=freshness),
                freshness=freshness,
                evidence=self._indicator_evidence(
                    status="live",
                    freshness=freshness,
                    inputs=[
                        self._source_confidence_input_from_component(component)
                        for component in components
                    ],
                    expected_input_count=len(LIQUIDITY_INDICATOR_REQUIRED_INPUTS["usd_pressure"]),
                ),
            )

        official_components = official_components or [self._missing_official_usd_pressure_component(macro_panel)]
        freshness = self._weakest_freshness([str(component.get("freshness") or "unavailable") for component in official_components])
        reason = (
            self._text(official_components[0].get("sourceAuthorityReason"))
            or self._text(official_components[0].get("degradationReason"))
            or "usd_pressure_missing_series"
        )
        evidence = self._indicator_evidence(
            status="unavailable",
            freshness=freshness,
            inputs=[
                self._source_confidence_input_from_component(component)
                for component in official_components
            ],
            expected_input_count=len(LIQUIDITY_INDICATOR_REQUIRED_INPUTS["usd_pressure"]),
        )
        evidence["degradationReason"] = reason
        return self._indicator(
            "usd_pressure",
            "USD Pressure / 美元压力",
            macro_panel,
            "unavailable",
            0,
            6,
            False,
            self._summary_with_component_metadata(
                "DTWEXBGS 官方美元压力证据暂不可用",
                official_components,
                freshness=freshness,
            ),
            freshness=freshness,
            evidence=evidence,
        )

    def _us_rates_indicator(self, panel: PanelState, macro_panel: PanelState) -> Dict[str, Any]:
        primary_panel = panel
        panels: tuple[PanelState, ...] = (primary_panel, macro_panel)
        components = self._extract_us_rates_components(panels)
        credit_observation = self._extract_credit_stress_observation(macro_panel)
        yield_components = [component for component in components if component["kind"] == "yield"]
        if len(yield_components) < 2:
            proxy_panel = self._fetch_macro_proxy_panel(
                "rates_proxy",
                [
                    {"symbol": "US10Y", "label": "10Y yield", "ticker": "^TNX", "unit": "%", "value_scale": 10.0, "market": "US"},
                    {"symbol": "US30Y", "label": "30Y yield", "ticker": "^TYX", "unit": "%", "value_scale": 10.0, "market": "US"},
                ],
            )
            if proxy_panel is not None:
                panel = proxy_panel
                panels = (primary_panel, proxy_panel, macro_panel)
                components = self._extract_us_rates_components(panels)
                yield_components = [component for component in components if component["kind"] == "yield"]
        if not components:
            return self._indicator(
                "us_rates_pressure",
                "US Rates / 利率压力",
                panel,
                "unavailable",
                0,
                6,
                False,
                self._summary_with_metadata(
                    "仅在可靠利率缓存存在时启用",
                    source="yfinance_proxy",
                    source_label="Yahoo Finance",
                    source_type="proxy_public",
                    reason=self._panel_unavailable_reason(panel, "US rates 代理不可用"),
                ),
            )
        positive = sum(1 for component in components if component["kind"] == "yield" and float(component["signal"]) > 0)
        negative = sum(1 for component in components if component["kind"] == "yield" and float(component["signal"]) < 0)
        direction = self._direction_from_counts(positive, negative)
        summary = " | ".join(
            f"{component['symbol']} {self._signed_percent_text(float(component['change']))}"
            for component in components
            if component["kind"] == "yield"
        )
        curve_parts = [
            f"{component['symbol']} {self._signed_number_text(float(component['value']))}{component['unit']}"
            for component in components
            if component["kind"] == "curve"
        ]
        observation_parts = [
            f"{component['symbol']} {self._signed_number_text(float(component['value']))}{component['unit']}"
            for component in components
            if component["kind"] == "observation"
        ]
        if curve_parts:
            summary = f"{summary} | {' | '.join(curve_parts)}" if summary else " | ".join(curve_parts)
        if observation_parts:
            summary = f"{summary} | {' | '.join(observation_parts)}" if summary else " | ".join(observation_parts)
        if credit_observation is not None:
            credit_summary = f"CREDIT {self._signed_number_text(float(credit_observation['value']))}{credit_observation['unit']}"
            summary = f"{summary} | {credit_summary}" if summary else credit_summary
        freshness = self._weakest_freshness([str(component["freshness"]) for component in components])
        status = (
            "live"
            if len(yield_components) >= 2
            and freshness in {"live", "cached"}
            and all(str(component.get("source") or "") != "yfinance_proxy" for component in yield_components)
            and all(str(component.get("sourceType") or "") != "official_public" for component in yield_components)
            else "partial"
        )
        return self._indicator(
            "us_rates_pressure",
            "US Rates / 利率压力",
            panel,
            status,
            6 if direction > 0 else -6 if direction < 0 else 0,
            6,
            True,
            self._summary_with_component_metadata(summary, components, freshness=freshness),
            freshness=freshness,
            evidence=self._indicator_evidence(
                status=status,
                freshness=freshness,
                inputs=(
                    [self._source_confidence_input_from_component(component) for component in components]
                    + (
                        [self._source_confidence_input_from_component(credit_observation)]
                        if credit_observation is not None
                        else []
                    )
                ),
                expected_input_count=max(2, len(yield_components)) if components else 2,
            ),
        )

    def _fed_liquidity_indicator(self, panel: PanelState) -> Dict[str, Any]:
        components = self._extract_fed_liquidity_components(panel)
        score_grade_components = [
            component
            for component in components
            if self._fed_liquidity_component_score_grade(component)
        ]
        all_required_ready = len(score_grade_components) == len(LIQUIDITY_INDICATOR_REQUIRED_INPUTS["fed_liquidity"])
        if not components:
            return self._indicator(
                "fed_liquidity",
                "Fed Liquidity / 美联储流动性",
                panel,
                "unavailable",
                0,
                6,
                False,
                self._summary_with_metadata(
                    "缺少 WALCL / RRPONTSYD / WTREGEN / WRESBAL 官方 FRED 证据",
                    source="fred",
                    source_label="FRED",
                    source_type="official_public",
                    reason=self._panel_unavailable_reason(panel, "fed_liquidity_official_rows_missing"),
                ),
            )

        positive = 0
        negative = 0
        summary_parts: list[str] = []
        for component in score_grade_components if all_required_ready else components:
            change = self._numeric(component.get("change"))
            if change is None:
                change = self._numeric(component.get("changePercent"))
            if change is not None:
                signal = self._fed_liquidity_signal(component["symbol"], change)
                if signal > 0:
                    positive += 1
                elif signal < 0:
                    negative += 1
            freshness_note = str(component.get("freshness") or "unavailable")
            summary_parts.append(
                f"{component['symbol']} {self._signed_percent_text(change)} ({freshness_note})"
            )

        direction = self._direction_from_counts(positive, negative)
        contribution = 6 if direction > 0 else -6 if direction < 0 else 0
        freshness = self._weakest_freshness([str(component.get("freshness") or "unavailable") for component in components])
        status = "live" if all_required_ready else "partial"
        included = all_required_ready
        degradation_reason = None if all_required_ready else "fed_liquidity_required_series_missing_or_stale"
        evidence_inputs = [
            self._source_confidence_input_from_component(component)
            for component in components
        ]
        evidence = self._indicator_evidence(
            status=status,
            freshness=freshness,
            inputs=evidence_inputs,
            expected_input_count=len(LIQUIDITY_INDICATOR_REQUIRED_INPUTS["fed_liquidity"]),
        )
        if degradation_reason:
            evidence["degradationReason"] = degradation_reason

        return self._indicator(
            "fed_liquidity",
            "Fed Liquidity / 美联储流动性",
            panel,
            status,
            contribution,
            6,
            included,
            self._summary_with_component_metadata(" | ".join(summary_parts), components, freshness=freshness),
            freshness=freshness,
            evidence=evidence,
        )

    def _us_etf_flow_indicator(self, panel: PanelState) -> Dict[str, Any]:
        item = self._first_reliable_item(panel, {"ETF"})
        if item is None:
            return self._indicator("us_etf_flow_proxy", "US ETF 资金代理", panel, "unavailable", 0, 5, False, "仅在可靠 funds-flow 缓存存在时启用")
        value = self._numeric(item.get("value"))
        contribution = 5 if (value or 0) > 0 else -5 if (value or 0) < 0 else 0
        freshness = self._item_freshness(item, panel)
        return self._indicator(
            "us_etf_flow_proxy",
            "US ETF 资金代理",
            panel,
            "partial",
            contribution,
            5,
            True,
            self._signed_number_text(value),
            freshness=freshness,
            evidence=self._indicator_evidence(
                status="partial",
                freshness=freshness,
                inputs=[
                    self._source_confidence_input_from_item(
                        item,
                        panel,
                        key=str(item.get("symbol") or "ETF"),
                        label=str(item.get("label") or "ETF"),
                    )
                ],
                expected_input_count=1,
            ),
        )

    def _us_breadth_indicator(self, panel: PanelState) -> Dict[str, Any]:
        breadth = self._extract_us_breadth_components(panel)
        if breadth is None:
            return self._indicator("us_breadth_proxy", "US Broadth / 广度代理", panel, "unavailable", 0, 6, False, "仅在可靠 breadth 缓存存在时启用")
        direction = self._direction_from_counts(int(breadth["positive_votes"]), int(breadth["negative_votes"]))
        summary_parts = [f"{int(breadth['up_value'])}/{int(breadth['down_value'])}"]
        summary_parts.extend(
            f"{proxy['label']} {self._signed_percent_text(float(proxy['value']))}"
            for proxy in breadth["proxies"]
        )
        status = "live" if len(breadth["proxies"]) >= 2 and str(breadth["freshness"]) in {"live", "cached"} else "partial"
        breadth_inputs = [
            self._source_confidence_input_from_item(
                item,
                panel,
                key=str(item.get("symbol") or ""),
                label=str(item.get("label") or item.get("symbol") or ""),
            )
            for item in (breadth.get("up_item"), breadth.get("down_item"))
            if isinstance(item, dict)
        ]
        breadth_inputs.extend(
            self._source_confidence_input_from_component(proxy)
            for proxy in breadth["proxies"]
        )
        return self._indicator(
            "us_breadth_proxy",
            "US 广度代理",
            panel,
            status,
            6 if direction > 0 else -6 if direction < 0 else 0,
            6,
            True,
            " | ".join(summary_parts),
            freshness=str(breadth["freshness"]),
            evidence=self._indicator_evidence(
                status=status,
                freshness=str(breadth["freshness"]),
                inputs=breadth_inputs,
                expected_input_count=max(2, len(breadth_inputs)) if breadth_inputs else 2,
            ),
        )

    def _cn_hk_index_indicator(self, panel: PanelState) -> Dict[str, Any]:
        items = [item for item in self._reliable_items(panel, None) if str(item.get("market") or "") in {"CN", "HK"} and self._change_value(item) is not None]
        if not items:
            return self._indicator("cn_hk_index_context", "CN/HK 指数环境", panel, "unavailable", 0, 0, False, "缺少可靠指数快照")
        avg_change = sum(float(self._change_value(item)) for item in items) / len(items)
        status = "live" if len(items) >= 4 and panel.source != "mixed" else "partial"
        freshness = self._weakest_freshness([self._item_freshness(item, panel) for item in items])
        return self._indicator("cn_hk_index_context", "CN/HK 指数环境", panel, status, 0, 0, False, f"均值 {avg_change:+.2f}%", freshness=freshness)

    def _cn_hk_flows_indicator(self, panel: PanelState, breadth_panel: PanelState) -> Dict[str, Any]:
        if panel.is_fallback or panel.freshness in {"fallback", "mock", "error", "unavailable"}:
            return self._indicator("cn_hk_flows", "CN/HK 资金流", panel, "unavailable", 0, 6, False, "Phase 1 仅在非 fallback 真实流量数据存在时启用")
        extracted = self._extract_cn_flow_components(panel, breadth_panel)
        if extracted is None:
            return self._indicator("cn_hk_flows", "CN/HK 资金流", panel, "unavailable", 0, 6, False, "缺少真实 northbound / ETF flow")
        direction = self._direction_from_counts(int(extracted["positive_votes"]), int(extracted["negative_votes"]))
        summary_parts = [
            f"{component['label']} {self._signed_number_text(float(component['value']))}"
            for component in extracted["flows"]
        ]
        if extracted["breadth_summary"]:
            summary_parts.append(str(extracted["breadth_summary"]))
        status = "live" if len(extracted["flows"]) >= 2 and str(extracted["freshness"]) in {"live", "cached"} else "partial"
        return self._indicator(
            "cn_hk_flows",
            "CN/HK 资金流",
            panel,
            status,
            6 if direction > 0 else -6 if direction < 0 else 0,
            6,
            False,
            " | ".join(summary_parts),
            freshness=str(extracted["freshness"]),
            evidence=self._indicator_evidence(
                status=status,
                freshness=str(extracted["freshness"]),
                inputs=[
                    self._source_confidence_input_from_component(flow)
                    for flow in extracted["flows"]
                ],
                expected_input_count=max(2, len(extracted["flows"])) if extracted["flows"] else 2,
            ),
        )

    def _cn_money_rates_indicator(self, panel: PanelState) -> Dict[str, Any]:
        dr007 = self._first_reliable_item(panel, {"DR007"})
        shibor = self._first_reliable_item(panel, {"SHIBOR"})
        if dr007 is None and shibor is None:
            return self._indicator("cn_money_market_rates", "CN 货币市场利率", panel, "unavailable", 0, 0, False, "Phase 1 仅观察，不单独计分")
        available = [item for item in (dr007, shibor) if item is not None]
        avg_change = sum(float(self._change_value(item) or 0.0) for item in available) / len(available)
        freshness = self._weakest_freshness([self._item_freshness(item, panel) for item in available])
        return self._indicator(
            "cn_money_market_rates",
            "CN 货币市场利率",
            panel,
            "partial",
            0,
            0,
            False,
            f"均值 {avg_change:+.2f}%",
            freshness=freshness,
            evidence=self._indicator_evidence(
                status="partial",
                freshness=freshness,
                inputs=[
                    self._source_confidence_input_from_item(
                        item,
                        panel,
                        key=str(item.get("symbol") or ""),
                        label=str(item.get("label") or item.get("symbol") or ""),
                    )
                    for item in available
                ],
                expected_input_count=2,
            ),
        )

    def _futures_indicator(self, panel: PanelState) -> Dict[str, Any]:
        if panel.is_fallback or panel.freshness in {"fallback", "mock", "error", "unavailable"}:
            return self._indicator("futures_premarket", "期货 / 盘前方向", panel, "unavailable", 0, 0, False, "Phase 1 fallback-only，不参与判断")
        items = self._reliable_items(panel, {"NQ", "ES", "YM", "RTY", "CN00Y", "HSI_F"})
        if not items:
            return self._indicator("futures_premarket", "期货 / 盘前方向", panel, "unavailable", 0, 0, False, "缺少可靠期货快照")
        avg_change = sum(float(self._change_value(item) or 0.0) for item in items) / len(items)
        freshness = self._weakest_freshness([self._item_freshness(item, panel) for item in items])
        return self._indicator(
            "futures_premarket",
            "期货 / 盘前方向",
            panel,
            "partial",
            0,
            0,
            False,
            f"均值 {avg_change:+.2f}%",
            freshness=freshness,
            evidence=self._indicator_evidence(
                status="partial",
                freshness=freshness,
                inputs=[
                    self._source_confidence_input_from_item(
                        item,
                        panel,
                        key=str(item.get("symbol") or ""),
                        label=str(item.get("label") or item.get("symbol") or ""),
                    )
                    for item in items
                ],
                expected_input_count=max(2, len(items)) if items else 2,
            ),
        )

    def _indicator(
        self,
        key: str,
        label: str,
        panel: PanelState,
        status: str,
        contribution: int,
        weight: int,
        included: bool,
        summary: str,
        *,
        freshness: Optional[str] = None,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        evidence = evidence or self._indicator_evidence(
            status=status,
            freshness=freshness or panel.freshness or "unavailable",
            panel=panel,
            label=label,
        )
        diagnostics = self._indicator_coverage_diagnostics(
            key,
            label,
            status=status,
            included=included,
            score_contribution=contribution,
            evidence=evidence,
            panel=panel,
        )
        return {
            "key": key,
            "label": label,
            "status": status,
            "freshness": freshness or panel.freshness or "unavailable",
            "includedInScore": diagnostics["contributesToScore"],
            "scoreContribution": diagnostics["scoreContribution"],
            "scoreWeight": weight,
            "summary": summary,
            "updatedAt": panel.as_of or panel.updated_at,
            "evidence": evidence,
            "coverageDiagnostics": diagnostics,
        }

    def _first_reliable_item(self, panel: PanelState, symbols: Optional[set[str]]) -> Optional[Dict[str, Any]]:
        items = self._reliable_items(panel, symbols)
        return items[0] if items else None

    def _preferred_symbol_item(
        self,
        panels: Iterable[PanelState],
        symbols: set[str],
        *,
        validator: Optional[Callable[[Dict[str, Any], PanelState], bool]] = None,
    ) -> Optional[tuple[PanelState, Dict[str, Any]]]:
        candidates: List[tuple[tuple[int, int, int], PanelState, Dict[str, Any]]] = []
        for panel_index, panel in enumerate(panels):
            for item in self._reliable_items(panel, symbols):
                if validator is not None and not validator(item, panel):
                    continue
                source_type = self._item_source_type(item, panel)
                source = str(item.get("source") or panel.source or "").lower()
                freshness = self._item_freshness(item, panel)
                candidates.append(
                    (
                        (
                            0 if source_type == "official_public" else 1,
                            FRESHNESS_ORDER.get(freshness, 99),
                            panel_index if source not in {"yahoo", "yfinance", "yfinance_proxy"} else panel_index + 1,
                        ),
                        panel,
                        item,
                    )
                )
        if not candidates:
            return None
        candidates.sort(key=lambda entry: entry[0])
        _, panel, item = candidates[0]
        return panel, item

    def _reliable_symbol_map(self, panel: PanelState, symbols: Optional[set[str]] = None) -> Dict[str, Dict[str, Any]]:
        return {
            str(item.get("symbol") or ""): item
            for item in self._reliable_items(panel, symbols)
            if str(item.get("symbol") or "")
        }

    def _extract_crypto_breadth(self, panel: PanelState) -> Optional[Dict[str, Any]]:
        symbols = self._reliable_symbol_map(panel, {"BTC", "ETH", "BNB"})
        entries = []
        for symbol in ("BTC", "ETH", "BNB"):
            item = symbols.get(symbol)
            if item is None:
                continue
            change = self._change_value(item)
            if change is None:
                continue
            entries.append((item, change))
        if len(entries) < 2:
            return None
        advancers = sum(1 for _, change in entries if change > 0)
        decliners = sum(1 for _, change in entries if change < 0)
        freshness = self._weakest_freshness([self._item_freshness(item, panel) for item, _ in entries])
        avg_change = sum(change for _, change in entries) / len(entries)
        return {
            "count": len(entries),
            "advancers": advancers,
            "decliners": decliners,
            "avg_change": avg_change,
            "freshness": freshness,
            "entries": entries,
        }

    def _extract_usd_pressure_components(self, fx_panel: PanelState, rates_panel: PanelState) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        specs = [
            ("DXY", "DXY", fx_panel, False),
            ("DXY", "DXY", rates_panel, False),
            ("USDCNH", "USD/CNH", fx_panel, False),
            ("USDJPY", "USD/JPY", fx_panel, False),
            ("EURUSD", "EUR/USD", fx_panel, True),
        ]
        seen: set[str] = set()
        for symbol, label, panel, invert in specs:
            if symbol in seen:
                continue
            item = self._first_reliable_item(panel, {symbol})
            if item is None:
                continue
            change = self._change_value(item)
            if change is None:
                continue
            seen.add(symbol)
            items.append(
                {
                    "symbol": symbol,
                    "label": label,
                    "change": change,
                    "signal": -change if invert else change,
                    "panel": panel,
                    **self._component_projection_meta(item, panel),
                }
            )
        return items

    def _extract_official_usd_pressure_components(self, macro_panel: PanelState) -> List[Dict[str, Any]]:
        raw_items = macro_panel.payload.get("items")
        if not isinstance(raw_items, list):
            return []

        components: list[Dict[str, Any]] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            symbol = str(raw.get("symbol") or "")
            official_series_id = str(raw.get("officialSeriesId") or raw.get("sourceId") or "")
            if symbol != "USD_TWI" and "DTWEXBGS" not in official_series_id:
                continue
            value = self._numeric(raw.get("value") if raw.get("value") is not None else raw.get("price"))
            change = self._change_value(raw)
            component = {
                "symbol": "USD_TWI",
                "key": "USD_TWI",
                "label": str(raw.get("label") or raw.get("name") or "Trade-weighted USD"),
                "value": value,
                "change": change,
                "signal": change if change is not None else 0.0,
                "unit": str(raw.get("unit") or ""),
                **self._component_projection_meta(raw, macro_panel),
            }
            if raw.get("sourceAuthorityAllowed") is False:
                component["sourceAuthorityAllowed"] = False
            if raw.get("scoreContributionAllowed") is False:
                component["scoreContributionAllowed"] = False
            if raw.get("sourceAuthorityReason"):
                component["sourceAuthorityReason"] = raw.get("sourceAuthorityReason")
                component["degradationReason"] = raw.get("sourceAuthorityReason")
            if raw.get("routeRejectedReasonCodes"):
                component["routeRejectedReasonCodes"] = list(raw.get("routeRejectedReasonCodes") or [])
            components.append(component)
        return components

    def _missing_official_usd_pressure_component(self, macro_panel: PanelState) -> Dict[str, Any]:
        as_of = macro_panel.as_of or macro_panel.updated_at or self._now().isoformat(timespec="seconds")
        return {
            "symbol": "USD_TWI",
            "key": "USD_TWI",
            "label": "Trade-weighted USD",
            "value": None,
            "change": None,
            "signal": 0.0,
            "unit": "idx",
            "source": "fred",
            "sourceLabel": "FRED Nominal Broad U.S. Dollar Index",
            "sourceType": "official_public",
            "asOf": as_of,
            "freshness": "unavailable",
            "isFallback": False,
            "isStale": False,
            "isPartial": False,
            "isUnavailable": True,
            "sourceTier": "official_public",
            "trustLevel": "unavailable",
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "sourceAuthorityReason": "usd_pressure_missing_series",
            "sourceAuthorityRouteRejected": False,
            "routeRejectedReasonCodes": ["usd_pressure_missing_series"],
            "officialSeriesId": "DTWEXBGS",
            "officialObservationDate": None,
            "officialAsOf": None,
            "degradationReason": "usd_pressure_missing_series",
        }

    @staticmethod
    def _usd_pressure_component_score_grade(component: Dict[str, Any]) -> bool:
        return bool(
            component.get("sourceType") == "official_public"
            and component.get("sourceAuthorityAllowed") is not False
            and component.get("scoreContributionAllowed") is not False
            and not component.get("isFallback")
            and not component.get("isUnavailable")
            and not component.get("isStale")
            and str(component.get("freshness") or "") in RELIABLE_FRESHNESS
            and LiquidityMonitorService._numeric(component.get("value")) is not None
            and LiquidityMonitorService._numeric(component.get("change")) is not None
            and str(component.get("officialSeriesId") or "") == "DTWEXBGS"
        )

    def _extract_us_rates_components(self, panels: Iterable[PanelState]) -> List[Dict[str, Any]]:
        panels = tuple(panels)
        items: List[Dict[str, Any]] = []
        for symbol in ("US2Y", "US10Y", "US30Y"):
            selected = self._preferred_symbol_item(panels, {symbol}, validator=self._is_yield_item_usable)
            if selected is None:
                continue
            panel, item = selected
            change = self._change_value(item)
            if change is None:
                continue
            items.append(
                {
                    "symbol": symbol,
                    "kind": "yield",
                    "change": change,
                    "signal": -change,
                    **self._component_projection_meta(item, panel),
                }
            )
        for symbol in ("SOFR",):
            selected = self._preferred_symbol_item(panels, {symbol}, validator=self._is_observation_item_usable)
            if selected is None:
                continue
            panel, item = selected
            value = self._numeric(item.get("value"))
            if value is None:
                continue
            items.append(
                {
                    "symbol": symbol,
                    "kind": "observation",
                    "value": value,
                    "unit": str(item.get("unit") or ""),
                    **self._component_projection_meta(item, panel),
                }
            )
        for symbol in ("US10Y2Y", "US10Y3M"):
            selected = self._preferred_symbol_item(panels, {symbol}, validator=self._is_observation_item_usable)
            if selected is None:
                continue
            panel, item = selected
            value = self._numeric(item.get("value"))
            if value is None:
                continue
            items.append(
                {
                    "symbol": symbol,
                    "kind": "curve",
                    "value": value,
                    "unit": str(item.get("unit") or ""),
                    **self._component_projection_meta(item, panel),
                }
            )
        return items

    def _extract_fed_liquidity_components(self, panel: PanelState) -> List[Dict[str, Any]]:
        raw_items = panel.payload.get("items")
        if not isinstance(raw_items, list):
            return []

        required_symbols = set(LIQUIDITY_INDICATOR_REQUIRED_INPUTS["fed_liquidity"])
        components: list[Dict[str, Any]] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            symbol = str(raw.get("symbol") or "")
            if symbol not in required_symbols:
                continue
            value = self._numeric(raw.get("value") if raw.get("value") is not None else raw.get("price"))
            change = self._change_value(raw)
            component = {
                "symbol": symbol,
                "key": symbol,
                "label": str(raw.get("label") or raw.get("name") or symbol),
                "value": value,
                "change": change,
                "unit": str(raw.get("unit") or ""),
                **self._component_projection_meta(raw, panel),
            }
            if raw.get("sourceAuthorityAllowed") is False:
                component["sourceAuthorityAllowed"] = False
            if raw.get("scoreContributionAllowed") is False:
                component["scoreContributionAllowed"] = False
            if raw.get("sourceAuthorityReason"):
                component["sourceAuthorityReason"] = raw.get("sourceAuthorityReason")
                component["degradationReason"] = raw.get("sourceAuthorityReason")
            if raw.get("routeRejectedReasonCodes"):
                component["routeRejectedReasonCodes"] = list(raw.get("routeRejectedReasonCodes") or [])
            components.append(component)
        return components

    @staticmethod
    def _fed_liquidity_component_score_grade(component: Dict[str, Any]) -> bool:
        return bool(
            component.get("sourceType") == "official_public"
            and component.get("sourceAuthorityAllowed") is not False
            and component.get("scoreContributionAllowed") is not False
            and not component.get("isFallback")
            and not component.get("isUnavailable")
            and not component.get("isStale")
            and str(component.get("freshness") or "") in RELIABLE_FRESHNESS
            and LiquidityMonitorService._numeric(component.get("value")) is not None
            and (
                LiquidityMonitorService._numeric(component.get("change")) is not None
                or LiquidityMonitorService._numeric(component.get("changePercent")) is not None
            )
        )

    @staticmethod
    def _fed_liquidity_signal(symbol: str, change: float) -> int:
        if symbol in {"FED_ASSETS", "RESERVES"}:
            return 1 if change > 0 else -1 if change < 0 else 0
        if symbol in {"FED_RRP", "TGA"}:
            return 1 if change < 0 else -1 if change > 0 else 0
        return 0

    def _extract_credit_stress_observation(self, panel: PanelState) -> Optional[Dict[str, Any]]:
        item = self._first_reliable_item(panel, {"CREDIT"})
        if item is None:
            return None
        if self._item_source_type(item, panel) != "official_public":
            return None
        source_id = str(item.get("sourceId") or "").upper()
        if source_id and "BAMLH0A0HYM2" not in source_id:
            return None
        value = self._numeric(item.get("value"))
        if value is None:
            return None
        return {
            "symbol": "CREDIT",
            "key": "CREDIT",
            "label": str(item.get("label") or "Credit spreads"),
            "value": value,
            "unit": str(item.get("unit") or ""),
            **self._component_projection_meta(item, panel),
        }

    def _extract_us_breadth_components(self, panel: PanelState) -> Optional[Dict[str, Any]]:
        symbol_map = self._reliable_symbol_map(panel, {"SECTORS_UP", "SECTORS_DOWN", "RSP_SPY", "IWM_SPY", "QQQ_SPY"})
        up = symbol_map.get("SECTORS_UP")
        down = symbol_map.get("SECTORS_DOWN")
        proxies = []
        positive_votes = 0
        negative_votes = 0
        if up is not None and down is not None:
            up_value = self._numeric(up.get("value"))
            down_value = self._numeric(down.get("value"))
            if up_value is not None and down_value is not None:
                if up_value > down_value:
                    positive_votes += 1
                elif up_value < down_value:
                    negative_votes += 1
            else:
                up = None
                down = None
        if up is None or down is None:
            up_value = None
            down_value = None
        freshness_values = [self._item_freshness(item, panel) for item in (up, down) if item is not None]
        for symbol, label in (("RSP_SPY", "RSP/SPY"), ("IWM_SPY", "IWM/SPY"), ("QQQ_SPY", "QQQ/SPY")):
            item = symbol_map.get(symbol)
            if item is None:
                continue
            value = self._change_value(item)
            if value is None:
                value = self._numeric(item.get("value"))
            if value is None:
                continue
            if value > 0:
                positive_votes += 1
            elif value < 0:
                negative_votes += 1
            freshness_values.append(self._item_freshness(item, panel))
            proxies.append({"symbol": symbol, "label": label, "value": value})
            proxies[-1].update(self._component_projection_meta(item, panel))
        if up_value is None or down_value is None:
            if not proxies:
                return None
            up_value = 0.0
            down_value = 0.0
        return {
            "up_value": up_value,
            "down_value": down_value,
            "up_item": up,
            "down_item": down,
            "proxies": proxies,
            "positive_votes": positive_votes,
            "negative_votes": negative_votes,
            "freshness": self._weakest_freshness(freshness_values),
        }

    def _extract_cn_flow_components(self, panel: PanelState, breadth_panel: PanelState) -> Optional[Dict[str, Any]]:
        flow_labels = {
            "NORTHBOUND": "北向",
            "SOUTHBOUND": "南向",
            "CN_ETF": "ETF",
            "MARGIN_BALANCE": "融资",
            "MAINLAND_MAIN": "主力",
        }
        symbol_map = self._reliable_symbol_map(panel, set(flow_labels))
        flows = []
        positive_votes = 0
        negative_votes = 0
        freshness_values: List[str] = []
        for symbol in ("NORTHBOUND", "SOUTHBOUND", "CN_ETF", "MARGIN_BALANCE", "MAINLAND_MAIN"):
            item = symbol_map.get(symbol)
            if item is None:
                continue
            value = self._numeric(item.get("value"))
            if value is None:
                continue
            if value > 0:
                positive_votes += 1
            elif value < 0:
                negative_votes += 1
            freshness_values.append(self._item_freshness(item, panel))
            flows.append({"symbol": symbol, "label": flow_labels[symbol], "value": value})
            flows[-1].update(self._component_projection_meta(item, panel))
        if not flows:
            return None
        breadth_summary = self._extract_cn_breadth_summary(breadth_panel)
        if breadth_summary is not None:
            freshness_values.append(str(breadth_summary["freshness"]))
        return {
            "flows": flows,
            "positive_votes": positive_votes,
            "negative_votes": negative_votes,
            "breadth_summary": breadth_summary["summary"] if breadth_summary is not None else None,
            "freshness": self._weakest_freshness(freshness_values),
        }

    def _component_projection_meta(self, item: Dict[str, Any], panel: PanelState) -> Dict[str, Any]:
        freshness = self._item_freshness(item, panel)
        metadata = {
            "source": item.get("source") or panel.source,
            "sourceLabel": item.get("sourceLabel") or panel.payload.get("sourceLabel"),
            "sourceType": item.get("sourceType") or panel.payload.get("sourceType"),
            "asOf": item.get("asOf") or item.get("updatedAt") or panel.as_of or panel.updated_at,
            "freshness": freshness,
            "isFallback": bool(item.get("isFallback") or item.get("fallbackUsed") or panel.is_fallback),
            "isStale": bool(item.get("isStale") or freshness == "stale" or panel.is_stale),
            "isPartial": bool(item.get("isPartial")),
            "isUnavailable": bool(item.get("isUnavailable")),
        }
        for field in EVIDENCE_INPUT_METADATA_FIELDS:
            if field in item:
                metadata[field] = copy.deepcopy(item.get(field))
        return metadata

    def _extract_cn_breadth_summary(self, panel: PanelState) -> Optional[Dict[str, Any]]:
        symbol_map = self._reliable_symbol_map(panel, {"EFFECT", "ADV_RATIO"})
        effect = symbol_map.get("EFFECT")
        adv_ratio = symbol_map.get("ADV_RATIO")
        if effect is None and adv_ratio is None:
            return None
        parts = []
        freshness_values = []
        if effect is not None:
            value = self._numeric(effect.get("value"))
            if value is not None:
                parts.append(f"EFFECT {value:.0f}")
                freshness_values.append(self._item_freshness(effect, panel))
        if adv_ratio is not None:
            value = self._numeric(adv_ratio.get("value"))
            if value is not None:
                parts.append(f"ADV_RATIO {value:.1f}%")
                freshness_values.append(self._item_freshness(adv_ratio, panel))
        if not parts:
            return None
        return {
            "summary": f"宽度 {' / '.join(parts)}",
            "freshness": self._weakest_freshness(freshness_values),
        }

    def _has_live_crypto_context(self, panel: PanelState) -> bool:
        symbols = {"BTC", "ETH", "BNB", "SOL"}
        return any(
            isinstance(item, dict) and str(item.get("symbol") or "") in symbols
            for item in panel.payload.get("items", [])
        )

    def _fetch_live_crypto_funding_panel(self, panel: PanelState) -> Optional[PanelState]:
        if not self._has_live_crypto_context(panel):
            return None
        self._external_provider_calls_used = True
        items: List[Dict[str, Any]] = []
        updated_at = self._now().isoformat(timespec="seconds")
        provenance = project_source_provenance(source="binance", freshness="live")
        current = self._now()
        for futures_symbol, short_symbol in (("BTCUSDT", "BTC"), ("ETHUSDT", "ETH")):
            try:
                row = fetch_binance_funding_row(futures_symbol)
            except Exception:
                continue
            funding_rate = self._numeric(row.get("lastFundingRate"))
            if funding_rate is None:
                continue
            as_of = self._timestamp_millis_to_iso(row.get("time")) or updated_at
            item_freshness = self._direct_backfill_freshness(as_of, max_age=CRYPTO_FUNDING_BACKFILL_MAX_AGE, now=current)
            funding_percent = round(funding_rate * 100, 4)
            items.append(
                {
                    "symbol": f"{short_symbol}_FUNDING",
                    "label": f"{short_symbol} Funding",
                    "value": funding_percent,
                    "change": funding_percent,
                    "changePercent": funding_percent,
                    "source": "binance",
                    "sourceLabel": provenance["sourceLabel"],
                    "sourceType": provenance["sourceType"],
                    "asOf": as_of,
                    "updatedAt": updated_at,
                    "freshness": item_freshness,
                    "isFallback": False,
                    "fallbackUsed": False,
                    "isStale": item_freshness == "stale",
                    "isPartial": item_freshness in RELIABLE_FRESHNESS,
                    "degradationReason": "direct_provider_backfill" if item_freshness in RELIABLE_FRESHNESS else "stale_source",
                }
            )
        if not items:
            return None
        latest_as_of = max(str(item.get("asOf") or updated_at) for item in items)
        panel_freshness = self._weakest_freshness(str(item.get("freshness") or "") for item in items)
        payload = {
            "source": "binance",
            "sourceLabel": provenance["sourceLabel"],
            "sourceType": provenance["sourceType"],
            "freshness": panel_freshness,
            "asOf": latest_as_of,
            "updatedAt": updated_at,
            "isFallback": False,
            "fallbackUsed": False,
            "items": items,
        }
        return PanelState(
            key="crypto_funding_live",
            payload=payload,
            source="binance",
            freshness=panel_freshness,
            as_of=latest_as_of,
            updated_at=updated_at,
            is_fallback=False,
            is_stale=panel_freshness == "stale",
        )

    def _fetch_macro_proxy_panel(self, key: str, specs: List[Dict[str, Any]]) -> Optional[PanelState]:
        if not specs:
            return None
        self._external_provider_calls_used = True
        provenance = project_source_provenance(source="yfinance_proxy", source_type="proxy_public", freshness="delayed")
        items = []
        for spec in specs:
            item = self._fetch_macro_proxy_item(spec)
            if item is not None:
                items.append(item)
        if not items:
            return None
        as_of_values = [str(item.get("asOf") or "") for item in items if item.get("asOf")]
        latest_as_of = max(as_of_values) if as_of_values else self._now().isoformat(timespec="seconds")
        payload = {
            "source": "yfinance_proxy",
            "sourceLabel": provenance["sourceLabel"],
            "sourceType": provenance["sourceType"],
            "freshness": "delayed",
            "asOf": latest_as_of,
            "updatedAt": latest_as_of,
            "isFallback": False,
            "fallbackUsed": False,
            "items": items,
        }
        return PanelState(
            key=key,
            payload=payload,
            source="yfinance_proxy",
            freshness="delayed",
            as_of=latest_as_of,
            updated_at=latest_as_of,
            is_fallback=False,
            is_stale=False,
        )

    def _fetch_macro_proxy_item(self, spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        ticker = str(spec.get("ticker") or "").strip()
        if not ticker:
            return None
        try:
            frame = fetch_yfinance_quote_history_frame(ticker)
        except Exception:
            return None
        closes = self._frame_column_values(frame, "Close")
        closes = [value for value in closes if value is not None]
        if not closes:
            return None
        latest_raw = closes[-1]
        previous_raw = closes[-2] if len(closes) > 1 else latest_raw
        value_scale = float(spec.get("value_scale") or 1.0)
        latest_value = latest_raw / value_scale if value_scale else latest_raw
        change_percent = ((latest_raw - previous_raw) / previous_raw * 100.0) if previous_raw else 0.0
        as_of = self._frame_last_as_of(frame) or self._now().isoformat(timespec="seconds")
        provenance = project_source_provenance(source="yfinance_proxy", source_type="proxy_public", freshness="delayed")
        item = {
            "symbol": spec["symbol"],
            "label": spec["label"],
            "value": round(latest_value, 3),
            "price": round(latest_value, 3),
            "unit": spec.get("unit"),
            "change": round(change_percent, 3),
            "changePercent": round(change_percent, 3),
            "source": "yfinance_proxy",
            "sourceLabel": provenance["sourceLabel"],
            "sourceType": provenance["sourceType"],
            "freshness": "delayed",
            "asOf": as_of,
            "updatedAt": as_of,
            "isFallback": False,
            "fallbackUsed": False,
        }
        market = self._text(spec.get("market"))
        if market:
            item["market"] = market
        return item

    @staticmethod
    def _direction_from_counts(positive: int, negative: int) -> int:
        if positive > negative:
            return 1
        if negative > positive:
            return -1
        return 0

    def _reliable_items(self, panel: PanelState, symbols: Optional[set[str]]) -> List[Dict[str, Any]]:
        if panel.freshness not in RELIABLE_FRESHNESS or panel.is_fallback or panel.is_stale:
            return []
        reliable: List[Dict[str, Any]] = []
        for raw in panel.payload.get("items", []):
            if not isinstance(raw, dict):
                continue
            symbol = str(raw.get("symbol") or "")
            if symbols and symbol not in symbols:
                continue
            if self._item_freshness(raw, panel) not in RELIABLE_FRESHNESS:
                continue
            if self._item_source_type(raw, panel) == "official_public":
                if self._change_value(raw) is None and self._numeric(raw.get("value") or raw.get("price")) is None:
                    continue
            reliable.append(raw)
        return reliable

    @staticmethod
    def _item_source_type(item: Dict[str, Any], panel: PanelState) -> str:
        return str(item.get("sourceType") or panel.payload.get("sourceType") or "").lower()

    def _item_freshness(self, item: Dict[str, Any], panel: PanelState) -> str:
        explicit = str(item.get("freshness") or "").lower()
        source = str(item.get("source") or panel.source or "").lower()
        source_type = self._item_source_type(item, panel)
        is_fallback = bool(item.get("isFallback") or item.get("fallbackUsed") or panel.is_fallback or source in {"fallback", "mock", "unavailable"})
        is_stale = bool(item.get("isStale") or panel.is_stale)
        source_type_floor = self._source_type_freshness_floor(source_type)
        if source == "mock" or explicit == "mock":
            return "mock"
        if is_fallback:
            return self._weakest_freshness([explicit, "fallback"])
        if source_type_floor in {"fallback", "mock", "unavailable"}:
            return self._weakest_freshness([explicit, source_type_floor])
        if is_stale:
            return self._weakest_freshness([explicit, "stale"])
        if explicit in FRESHNESS_ORDER:
            return explicit
        if source_type_floor:
            return source_type_floor
        if source == "yfinance_proxy":
            return "delayed"
        item_as_of = self._parse_time(item.get("asOf") or item.get("updatedAt"))
        panel_as_of = self._parse_time(panel.as_of or panel.updated_at)
        if item_as_of and panel_as_of:
            age_minutes = abs((panel_as_of - item_as_of).total_seconds()) / 60.0
            if age_minutes >= 240:
                return "stale"
            if age_minutes >= 10:
                return "delayed"
            if age_minutes >= 2:
                return "cached"
        return panel.freshness if panel.freshness in RELIABLE_FRESHNESS else "live"

    @staticmethod
    def _change_value(item: Dict[str, Any]) -> Optional[float]:
        for key in ("changePercent", "change_pct", "change"):
            if key in item:
                value = LiquidityMonitorService._numeric(item.get(key))
                if value is not None:
                    return value
        return None

    @staticmethod
    def _numeric(value: Any) -> Optional[float]:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value) if value == value else None
        if isinstance(value, str) and value.strip():
            try:
                return float(value.strip())
            except ValueError:
                return None
        return None

    @staticmethod
    def _text(value: Any) -> Optional[str]:
        text = str(value or "").strip()
        return text or None

    @staticmethod
    def _parse_time(value: Any) -> Optional[datetime]:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=CN_TZ)
        return parsed.astimezone(CN_TZ)

    @staticmethod
    def _frame_column_values(frame: Any, column: str) -> List[Optional[float]]:
        if frame is None:
            return []
        try:
            values = frame[column].tolist()
        except Exception:
            return []
        return [LiquidityMonitorService._numeric(value) for value in values]

    @staticmethod
    def _frame_last_as_of(frame: Any) -> Optional[str]:
        index = getattr(frame, "index", None)
        if index is None:
            return None
        try:
            if len(index) == 0:
                return None
            value = index[-1]
        except Exception:
            return None
        if hasattr(value, "to_pydatetime"):
            value = value.to_pydatetime()
        if isinstance(value, datetime):
            dt = value
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(CN_TZ).isoformat(timespec="seconds")
        parsed = LiquidityMonitorService._parse_time(value)
        return parsed.isoformat(timespec="seconds") if parsed else None

    def _summary_with_metadata(
        self,
        summary: str,
        *,
        item: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None,
        source_label: Optional[str] = None,
        source_type: Optional[str] = None,
        as_of: Optional[str] = None,
        freshness: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> str:
        item = item or {}
        resolved_source = self._text(item.get("source")) or self._text(source)
        resolved_source_label = self._text(item.get("sourceLabel")) or self._text(source_label)
        resolved_source_type = self._text(item.get("sourceType")) or self._text(source_type)
        resolved_as_of = self._text(item.get("asOf") or item.get("updatedAt")) or self._text(as_of)
        resolved_freshness = self._text(item.get("freshness")) or self._text(freshness)
        parts = [summary]
        if resolved_source_label or resolved_source:
            label = resolved_source_label or resolved_source or ""
            if resolved_source and resolved_source != label:
                label = f"{label} ({resolved_source})"
            parts.append(f"来源 {label}")
        if resolved_source_type:
            parts.append(f"类型 {resolved_source_type}")
        if resolved_as_of:
            parts.append(f"截至 {resolved_as_of}")
        if resolved_freshness:
            parts.append(f"新鲜度 {resolved_freshness}")
        if reason:
            parts.append(f"原因 {reason}")
        return " | ".join(part for part in parts if part)

    def _summary_with_component_metadata(
        self,
        summary: str,
        items: Iterable[Dict[str, Any]],
        *,
        freshness: Optional[str] = None,
    ) -> str:
        materialized = [item for item in items if isinstance(item, dict)]
        if not materialized:
            return self._summary_with_metadata(summary, freshness=freshness)

        source_types = [
            self._text(item.get("sourceType"))
            for item in materialized
            if self._text(item.get("sourceType"))
        ]
        if len(set(source_types)) <= 1:
            return self._summary_with_metadata(summary, item=materialized[0], freshness=freshness)

        source_labels: List[str] = []
        as_of_values: List[str] = []
        for item in materialized:
            source = self._text(item.get("source"))
            source_label = self._text(item.get("sourceLabel")) or source
            if source_label:
                display = source_label if not source or source == source_label else f"{source_label} ({source})"
                if display not in source_labels:
                    source_labels.append(display)
            as_of = self._text(item.get("asOf") or item.get("updatedAt"))
            if as_of and as_of not in as_of_values:
                as_of_values.append(as_of)

        return self._summary_with_metadata(
            summary,
            source_label=" / ".join(source_labels) if source_labels else None,
            source_type=" / ".join(dict.fromkeys(source_types)),
            as_of=max(as_of_values) if as_of_values else None,
            freshness=freshness,
        )

    def _panel_unavailable_reason(self, panel: PanelState, default: str) -> str:
        return self._text(panel.payload.get("warning")) or self._text(panel.payload.get("error")) or default

    def _indicator_evidence(
        self,
        *,
        status: str,
        freshness: str,
        inputs: Optional[List[Dict[str, Any]]] = None,
        panel: Optional[PanelState] = None,
        label: Optional[str] = None,
        expected_input_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        normalized_inputs = [dict(item) for item in (inputs or []) if isinstance(item, dict)]
        if not normalized_inputs and panel is not None:
            normalized_inputs.append(
                self._source_confidence_input_from_panel(
                    panel,
                    key=panel.key,
                    label=label or panel.key,
                    is_unavailable=status == "unavailable",
                    coverage=0.0 if status == "unavailable" else 1.0,
                )
            )

        observed_count = len(normalized_inputs)
        target_count = max(observed_count, int(expected_input_count or observed_count or 1))
        coverage = round(min(1.0, observed_count / target_count), 2) if target_count else 0.0
        unique_sources = list(dict.fromkeys(str(item.get("source") or "") for item in normalized_inputs if str(item.get("source") or "")))
        unique_labels = list(dict.fromkeys(str(item.get("sourceLabel") or "") for item in normalized_inputs if str(item.get("sourceLabel") or "")))
        as_of_values = [str(item.get("asOf") or "") for item in normalized_inputs if item.get("asOf")]
        weakest_freshness = self._weakest_evidence_freshness([str(item.get("freshness") or "") for item in normalized_inputs] or [freshness])
        confidence_values = [float(item.get("confidenceWeight") or 0.0) for item in normalized_inputs]
        confidence_weight = round(sum(confidence_values) / len(confidence_values), 2) if confidence_values else 0.0
        contract = coerce_source_confidence_contract(
            {
                "source": unique_sources[0] if len(unique_sources) == 1 else ("mixed" if unique_sources else "unavailable"),
                "sourceLabel": unique_labels[0] if len(unique_labels) == 1 else (" / ".join(unique_labels) if unique_labels else "未接入"),
                "asOf": max(as_of_values) if as_of_values else None,
                "freshness": weakest_freshness,
                "isFallback": any(bool(item.get("isFallback")) for item in normalized_inputs),
                "isStale": any(bool(item.get("isStale")) for item in normalized_inputs),
                "isPartial": status == "partial" or coverage < 1.0,
                "isUnavailable": status == "unavailable" or all(bool(item.get("isUnavailable")) for item in normalized_inputs),
                "confidenceWeight": confidence_weight,
                "coverage": 0.0 if status == "unavailable" else coverage,
                "degradationReason": self._indicator_degradation_reason(status, normalized_inputs),
            }
        ).to_dict()
        return {
            "contractVersion": SOURCE_CONFIDENCE_CONTRACT_VERSION,
            "source": contract["source"],
            "sourceLabel": contract["sourceLabel"],
            "asOf": contract["asOf"],
            "freshness": contract["freshness"],
            "isFallback": contract["isFallback"],
            "isStale": contract["isStale"],
            "isPartial": contract["isPartial"],
            "isUnavailable": contract["isUnavailable"],
            "coverage": contract["coverage"],
            "confidenceWeight": contract["confidenceWeight"],
            "degradationReason": contract["degradationReason"],
            "capReason": contract["capReason"],
            "inputs": normalized_inputs,
        }

    def _source_confidence_input_from_component(self, component: Dict[str, Any]) -> Dict[str, Any]:
        return self._source_confidence_input(
            key=str(component.get("symbol") or component.get("key") or ""),
            label=str(component.get("label") or component.get("symbol") or component.get("key") or ""),
            source=component.get("source"),
            source_label=component.get("sourceLabel"),
            source_type=component.get("sourceType"),
            as_of=component.get("asOf"),
            freshness=str(component.get("freshness") or "unavailable"),
            is_fallback=bool(component.get("isFallback")),
            is_stale=bool(component.get("isStale")),
            is_partial=bool(component.get("isPartial")),
            is_unavailable=bool(component.get("isUnavailable")),
            degradation_reason=self._text(component.get("degradationReason")),
            metadata=component,
        )

    def _source_confidence_input_from_item(
        self,
        item: Dict[str, Any],
        panel: PanelState,
        *,
        key: str,
        label: str,
        coverage: float = 1.0,
        is_unavailable: bool = False,
        is_partial: bool = False,
    ) -> Dict[str, Any]:
        freshness = self._item_freshness(item, panel)
        return self._source_confidence_input(
            key=key,
            label=label,
            source=item.get("source") or panel.source,
            source_label=item.get("sourceLabel") or panel.payload.get("sourceLabel"),
            source_type=item.get("sourceType") or panel.payload.get("sourceType"),
            as_of=item.get("asOf") or item.get("updatedAt") or panel.as_of or panel.updated_at,
            freshness=freshness,
            is_fallback=bool(item.get("isFallback") or item.get("fallbackUsed") or panel.is_fallback),
            is_stale=bool(item.get("isStale") or freshness == "stale" or panel.is_stale),
            is_partial=is_partial or bool(item.get("isPartial")),
            coverage=coverage,
            is_unavailable=is_unavailable,
            degradation_reason=self._text(item.get("degradationReason")),
            metadata=item,
        )

    def _source_confidence_input_from_panel(
        self,
        panel: PanelState,
        *,
        key: str,
        label: str,
        coverage: float,
        is_unavailable: bool,
    ) -> Dict[str, Any]:
        input_is_unavailable = is_unavailable and panel.freshness in {"unavailable", "error"} and panel.source in {"", "unavailable"}
        return self._source_confidence_input(
            key=key,
            label=label,
            source=panel.source,
            source_label=panel.payload.get("sourceLabel"),
            source_type=panel.payload.get("sourceType"),
            as_of=panel.as_of or panel.updated_at,
            freshness=panel.freshness,
            is_fallback=panel.is_fallback,
            is_stale=panel.is_stale,
            coverage=coverage,
            is_partial=not is_unavailable and coverage < 1.0,
            is_unavailable=input_is_unavailable,
            degradation_reason=self._panel_unavailable_reason(panel, "liquidity_input_unavailable") if is_unavailable else None,
            metadata=panel.payload,
        )

    def _source_confidence_input(
        self,
        *,
        key: str,
        label: str,
        source: Any,
        source_label: Any,
        source_type: Any,
        as_of: Any,
        freshness: str,
        is_fallback: bool = False,
        is_stale: bool = False,
        is_partial: bool = False,
        is_unavailable: bool = False,
        coverage: Optional[float] = None,
        degradation_reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        explicit_source_type = self._text(source_type)
        provenance = project_source_provenance(
            source=source,
            source_type=explicit_source_type or None,
            source_label=source_label,
            freshness=freshness,
            is_fallback=is_fallback,
            is_stale=is_stale,
        )
        resolved_source_type = explicit_source_type or provenance["sourceType"]
        resolved_source_label = self._text(source_label) or provenance["sourceLabel"]
        freshness = self._freshness_with_source_type(
            freshness,
            resolved_source_type,
            is_fallback=is_fallback,
            is_stale=is_stale,
        )
        is_fallback = is_fallback or freshness == "fallback"
        is_stale = is_stale or freshness == "stale"
        is_unavailable = is_unavailable or freshness == "unavailable"
        contract = coerce_source_confidence_contract(
            {
                "source": self._text(source) or "unavailable",
                "sourceLabel": resolved_source_label,
                "asOf": self._text(as_of),
                "freshness": self._source_confidence_freshness(freshness),
                "isFallback": is_fallback,
                "isStale": is_stale,
                "isPartial": is_partial,
                "isUnavailable": is_unavailable or freshness == "unavailable",
                "confidenceWeight": self._source_confidence_weight(resolved_source_type),
                "coverage": coverage,
                "degradationReason": degradation_reason,
            }
        ).to_dict()
        result = {
            "key": key,
            "label": label,
            "source": contract["source"],
            "sourceLabel": contract["sourceLabel"],
            "sourceType": resolved_source_type,
            "asOf": contract["asOf"],
            "freshness": contract["freshness"],
            "isFallback": contract["isFallback"],
            "isStale": contract["isStale"],
            "isPartial": contract["isPartial"],
            "isUnavailable": contract["isUnavailable"],
            "coverage": contract["coverage"],
            "confidenceWeight": contract["confidenceWeight"],
            "degradationReason": contract["degradationReason"],
            "capReason": contract["capReason"],
        }
        if metadata:
            for field in EVIDENCE_INPUT_METADATA_FIELDS:
                if field in metadata:
                    result[field] = copy.deepcopy(metadata.get(field))
        return result

    def _indicator_coverage_diagnostics(
        self,
        key: str,
        label: str,
        *,
        status: str,
        included: bool,
        score_contribution: int,
        evidence: Dict[str, Any],
        panel: PanelState,
    ) -> Dict[str, Any]:
        inputs = [dict(item) for item in evidence.get("inputs", []) if isinstance(item, dict)]
        required_inputs = self._indicator_required_inputs(key, inputs, panel)
        fulfilled_inputs = self._indicator_fulfilled_inputs(key, required_inputs, inputs, panel, status)
        missing_inputs = [item for item in required_inputs if item not in fulfilled_inputs]
        coverage = self._indicator_coverage(required_inputs, fulfilled_inputs, evidence, status)
        trust_sources = inputs or [self._source_confidence_input_from_panel(
            panel,
            key=panel.key,
            label=label,
            coverage=coverage if coverage > 0.0 else (0.0 if status == "unavailable" else 1.0),
            is_unavailable=status == "unavailable",
        )]
        trust = evaluate_market_intelligence_trust_from_sources(
            trust_sources,
            coverage=coverage,
            degradation_reasons=self._indicator_degradation_reasons(evidence),
        )
        activation = self._indicator_provider_activation(
            key,
            panel=panel,
            evidence=evidence,
            trust=trust,
        )
        should_cap = self._should_cap_indicator_score(status, trust, evidence)
        final_contribution = 0
        if included and activation["scoreContributionAllowed"] and trust["trustLevel"] not in {"weak", "unavailable"}:
            final_contribution = int(round(float(score_contribution) * float(trust["scoreCap"] if should_cap else 1.0)))
        activation_hint = self._indicator_activation_hint(
            key,
            label,
            missing_inputs=missing_inputs,
            fulfilled_inputs=fulfilled_inputs,
            trust=trust,
            activation=activation,
            panel=panel,
            evidence=evidence,
        )
        activation_cap_reason = self._indicator_activation_cap_reason(activation)
        cap_reason = self._indicator_cap_reason(trust, evidence, should_cap, activation_cap_reason)
        contributes_to_score = bool(
            included
            and activation["scoreContributionAllowed"]
            and trust["trustLevel"] not in {"weak", "unavailable"}
            and (final_contribution != 0 or score_contribution == 0)
        )
        degradation_reason = evidence.get("degradationReason")
        if not degradation_reason:
            degradation_reason = activation_cap_reason or (
                trust["degradationReasons"][0] if trust["degradationReasons"] else evidence.get("capReason")
            )
        return {
            "indicatorId": key,
            "indicatorName": label,
            "requiredInputs": list(required_inputs),
            "fulfilledInputs": fulfilled_inputs,
            "missingInputs": missing_inputs,
            "requiredProviderClass": activation["requiredProviderClass"],
            "configuredProviderAvailable": activation["configuredProviderAvailable"],
            "realSourceAvailable": activation["realSourceAvailable"],
            "proxyOnly": activation["proxyOnly"],
            "observationOnly": activation["observationOnly"],
            "scoreContributionAllowed": activation["scoreContributionAllowed"],
            "scoreExclusionReason": activation["scoreExclusionReason"],
            "requiredRealSourceForScore": activation["requiredRealSourceForScore"],
            "proxyObservationOnlyReason": activation["proxyObservationOnlyReason"],
            "missingProviderReason": activation["missingProviderReason"],
            "paidDataLikelyRequired": activation["paidDataLikelyRequired"],
            "sourceTier": trust["sourceTier"],
            "freshness": trust["freshness"],
            "trustLevel": trust["trustLevel"],
            "contributesToScore": contributes_to_score,
            "scoreContribution": final_contribution if contributes_to_score else 0,
            "capReason": cap_reason,
            "degradationReason": degradation_reason,
            "sourceAuthorityRouteRejected": activation["sourceAuthorityRouteRejected"],
            "sourceAuthorityReason": activation["sourceAuthorityReason"],
            "routeRejectedReasonCodes": activation["routeRejectedReasonCodes"],
            "activationHint": activation_hint,
        }

    def _indicator_provider_activation(
        self,
        key: str,
        *,
        panel: PanelState,
        evidence: Dict[str, Any],
        trust: Dict[str, Any],
    ) -> Dict[str, Any]:
        policy = LIQUIDITY_INDICATOR_PROVIDER_ACTIVATION.get(key, {})
        required_provider_class = self._text(policy.get("requiredProviderClass"))
        configured_provider_available = self._indicator_configured_provider_available(panel, evidence)
        real_source_available = self._indicator_real_source_available(key, panel, evidence, trust)
        proxy_only = bool(policy.get("proxyOnly")) and not real_source_available and self._indicator_has_proxy_input(panel, evidence)
        observation_only = bool(policy.get("observationOnly"))
        required_real_source_for_score = bool(policy.get("requiresRealSourceForScore"))
        proxy_score_allowlisted = bool(policy.get("allowProxyScoreContribution"))
        proxy_observation_only_reason = "proxy_only_missing_real_source" if proxy_only and not real_source_available else None
        score_exclusion_reason = None
        if observation_only:
            score_exclusion_reason = "observation_only"
        elif required_real_source_for_score and proxy_only and not proxy_score_allowlisted:
            score_exclusion_reason = "proxy_only_missing_real_source"
        elif key == "usd_pressure" and not real_source_available:
            score_exclusion_reason = "usd_pressure_missing_series"
        elif key == "fed_liquidity" and not real_source_available:
            score_exclusion_reason = "fed_liquidity_required_series_missing_or_stale"
        elif not bool(trust.get("conclusionAllowed")):
            score_exclusion_reason = "trust_gate_blocked"
        score_contribution_allowed = bool(
            policy.get("scoreContributionAllowed", True)
            and not observation_only
            and bool(trust.get("conclusionAllowed"))
            and score_exclusion_reason is None
        )
        source_authority_route_rejected = False
        source_authority_reason = None
        route_rejected_reason_codes: list[str] = []
        if score_contribution_allowed:
            source_authority_route = self._liquidity_score_source_authority_route(
                key,
                panel=panel,
                evidence=evidence,
            )
            source_authority_route_rejected = bool(source_authority_route["rejected"])
            source_authority_reason = self._text(source_authority_route.get("reason")) or None
            route_rejected_reason_codes = list(source_authority_route.get("reasonCodes") or [])
            if source_authority_route_rejected:
                score_contribution_allowed = False
                score_exclusion_reason = score_exclusion_reason or LIQUIDITY_SCORE_ROUTE_REJECTED_REASON
        missing_provider_reason = None
        if required_provider_class and not real_source_available:
            missing_provider_reason = f"requires_{required_provider_class}"
        return {
            "requiredProviderClass": required_provider_class,
            "configuredProviderAvailable": configured_provider_available,
            "realSourceAvailable": real_source_available,
            "proxyOnly": proxy_only,
            "observationOnly": observation_only,
            "scoreContributionAllowed": score_contribution_allowed,
            "scoreExclusionReason": score_exclusion_reason,
            "requiredRealSourceForScore": required_real_source_for_score,
            "proxyObservationOnlyReason": proxy_observation_only_reason,
            "missingProviderReason": missing_provider_reason,
            "paidDataLikelyRequired": bool(policy.get("paidDataLikelyRequired")),
            "sourceAuthorityRouteRejected": source_authority_route_rejected,
            "sourceAuthorityReason": source_authority_reason,
            "routeRejectedReasonCodes": route_rejected_reason_codes,
        }

    def _liquidity_score_source_authority_route(
        self,
        key: str,
        *,
        panel: PanelState,
        evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        route_request = self._build_liquidity_score_route_request(key)
        if route_request is None:
            return {"rejected": False, "reason": None, "reasonCodes": []}

        route_plan = DataSourceRouter.resolve(route_request)
        allowed_source_types = {
            self._text(source_type).lower()
            for source_type in route_plan.required_source_types
            if self._text(source_type)
        }
        rejected = False
        reason_codes: list[str] = []

        for authority in self._liquidity_score_route_authorities(panel, evidence):
            provider_id = self._liquidity_score_route_provider_id(authority["source"])
            if provider_id in route_plan.reason_codes:
                rejected = True
                reason_codes.extend(route_plan.reason_codes[provider_id])
            if authority["sourceType"] and authority["sourceType"] not in allowed_source_types:
                rejected = True
                reason_codes.append("source_type_not_score_grade")

        return {
            "rejected": rejected,
            "reason": LIQUIDITY_SCORE_ROUTE_REJECTED_REASON if rejected else None,
            "reasonCodes": list(dict.fromkeys(reason_codes)),
        }

    @staticmethod
    def _build_liquidity_score_route_request(key: str) -> DataSourceRouteRequest | None:
        spec = LIQUIDITY_SCORE_ROUTE_REQUESTS.get(key)
        if spec is None:
            return None

        return DataSourceRouteRequest(
            market=str(spec["market"]),
            asset_type=str(spec["assetType"]),
            use_case="liquidity_score",
            capability=str(spec["capability"]),
            freshness_need=str(spec["freshnessNeed"]),
            scoring_allowed=True,
            symbol=str(spec["symbol"]) if spec.get("symbol") else None,
            product_id=str(spec["productId"]) if spec.get("productId") else None,
            allow_network=False,
            reproducibility_required=False,
        )

    def _liquidity_score_route_authorities(
        self,
        panel: PanelState,
        evidence: Dict[str, Any],
    ) -> list[Dict[str, str]]:
        inputs = [item for item in evidence.get("inputs", []) if isinstance(item, dict)]
        authorities: list[Dict[str, str]] = []
        seen: set[tuple[str, str]] = set()

        if not inputs:
            source = self._text(panel.source).lower()
            explicit_source_type = self._text(panel.payload.get("sourceType")).lower()
            source_type = (
                resolve_source_type(source_type=explicit_source_type)
                if explicit_source_type
                else project_source_provenance(
                    source=panel.source,
                    source_type=panel.payload.get("sourceType"),
                    freshness=panel.freshness,
                    is_fallback=panel.is_fallback,
                    is_stale=panel.is_stale,
                    is_from_snapshot=self._panel_from_snapshot(panel),
                )["sourceType"]
            )
            source_type = self._text(source_type).lower()
            if source:
                authorities.append({"source": source, "sourceType": source_type})
            return authorities

        for item in inputs:
            source = self._text(item.get("source") or panel.source).lower()
            explicit_source_type = self._text(item.get("sourceType")).lower()
            source_type = (
                resolve_source_type(source_type=explicit_source_type)
                if explicit_source_type
                else project_source_provenance(
                    source=item.get("source") or panel.source,
                    source_type=item.get("sourceType"),
                    freshness=item.get("freshness") or panel.freshness,
                    is_fallback=bool(item.get("isFallback")),
                    is_stale=bool(item.get("isStale")),
                    is_from_snapshot=False,
                )["sourceType"]
            )
            source_type = self._text(source_type).lower()
            if not source:
                continue
            authority = (source, source_type)
            if authority in seen:
                continue
            seen.add(authority)
            authorities.append({"source": source, "sourceType": source_type})
        return authorities

    @staticmethod
    def _liquidity_score_route_provider_id(source: str) -> str:
        normalized = str(source or "").strip().lower()
        return LIQUIDITY_SCORE_ROUTE_PROVIDER_ALIASES.get(normalized, normalized)

    @staticmethod
    def _indicator_configured_provider_available(panel: PanelState, evidence: Dict[str, Any]) -> bool:
        source = str(panel.source or "").lower()
        if source and source != "unavailable":
            return True
        inputs = evidence.get("inputs")
        return bool(inputs)

    def _indicator_real_source_available(
        self,
        key: str,
        panel: PanelState,
        evidence: Dict[str, Any],
        trust: Dict[str, Any],
    ) -> bool:
        if key in {"crypto_spot_momentum", "crypto_funding"}:
            return (
                str(trust.get("sourceTier") or "") == "exchange_public"
                and self._indicator_source_seen(evidence, panel, {"binance", "binance_ws"})
            )
        if key == "fed_liquidity":
            inputs = [item for item in evidence.get("inputs", []) if isinstance(item, dict)]
            required = set(LIQUIDITY_INDICATOR_REQUIRED_INPUTS["fed_liquidity"])
            return (
                {self._indicator_input_key(item) for item in inputs if self._indicator_input_key(item)}
                == required
                and all(
                    str(item.get("sourceType") or "") == "official_public"
                    and item.get("sourceAuthorityAllowed") is not False
                    and item.get("scoreContributionAllowed") is not False
                    and not item.get("isUnavailable")
                    and not item.get("isStale")
                    and str(item.get("freshness") or "") in RELIABLE_FRESHNESS
                    for item in inputs
                )
            )
        if key == "usd_pressure":
            inputs = [item for item in evidence.get("inputs", []) if isinstance(item, dict)]
            return (
                {self._indicator_input_key(item) for item in inputs if self._indicator_input_key(item)}
                == set(LIQUIDITY_INDICATOR_REQUIRED_INPUTS["usd_pressure"])
                and all(
                    str(item.get("sourceType") or "") == "official_public"
                    and item.get("sourceAuthorityAllowed") is not False
                    and item.get("scoreContributionAllowed") is not False
                    and not item.get("isUnavailable")
                    and not item.get("isStale")
                    and str(item.get("freshness") or "") in RELIABLE_FRESHNESS
                    for item in inputs
                )
            )
        if key in {"vix_pressure", "us_rates_pressure", "cn_hk_index_context"}:
            return (
                str(trust.get("sourceTier") or "") == "official_public"
                and not self._indicator_has_proxy_input(panel, evidence)
            )
        return False

    @staticmethod
    def _indicator_has_proxy_input(panel: PanelState, evidence: Dict[str, Any]) -> bool:
        proxy_sources = {"yahoo", "yfinance", "yfinance_proxy"}
        proxy_source_types = {"public_proxy", "proxy_public", "unofficial_proxy", "unofficial_public_api"}
        inputs = [item for item in evidence.get("inputs", []) if isinstance(item, dict)]
        sources = {str(item.get("source") or "").lower() for item in inputs}
        source_types = {str(item.get("sourceType") or "").lower() for item in inputs}
        if not inputs:
            sources.add(str(panel.source or "").lower())
            source_types.add(str(panel.payload.get("sourceType") or "").lower())
        return bool((sources & proxy_sources) or (source_types & proxy_source_types))

    @staticmethod
    def _indicator_source_seen(evidence: Dict[str, Any], panel: PanelState, sources: set[str]) -> bool:
        observed = {str(panel.source or "").lower()}
        for item in evidence.get("inputs", []):
            if isinstance(item, dict):
                observed.add(str(item.get("source") or "").lower())
        return bool(observed & sources)

    @staticmethod
    def _indicator_activation_cap_reason(activation: Dict[str, Any]) -> Optional[str]:
        if activation.get("scoreContributionAllowed"):
            return None
        missing_reason = activation.get("missingProviderReason")
        if missing_reason:
            return str(missing_reason)
        if activation.get("observationOnly"):
            return "observation_only"
        return None

    def _indicator_required_inputs(self, key: str, inputs: List[Dict[str, Any]], panel: PanelState) -> tuple[str, ...]:
        required = LIQUIDITY_INDICATOR_REQUIRED_INPUTS.get(key)
        if required:
            return required
        if inputs:
            return tuple(self._indicator_input_key(item) for item in inputs if self._indicator_input_key(item))
        if panel.key:
            return (panel.key,)
        return (key,)

    def _indicator_fulfilled_inputs(
        self,
        indicator_key: str,
        required_inputs: tuple[str, ...],
        inputs: List[Dict[str, Any]],
        panel: PanelState,
        status: str,
    ) -> list[str]:
        required = set(required_inputs)
        seen: list[str] = []
        for item in inputs:
            input_key = self._indicator_input_key(item)
            if not input_key or input_key not in required or input_key in seen:
                continue
            if self._indicator_input_is_fulfilled(item):
                seen.append(input_key)
        if seen:
            return seen
        if status != "unavailable" and panel.key in required:
            return [panel.key]
        return []

    @staticmethod
    def _indicator_input_is_fulfilled(item: Dict[str, Any]) -> bool:
        if bool(item.get("isUnavailable")) or bool(item.get("isStale")):
            return False
        if str(item.get("freshness") or "").lower() in {"stale", "fallback", "mock", "unavailable", "error"}:
            return False
        return True

    def _indicator_coverage(
        self,
        required_inputs: tuple[str, ...],
        fulfilled_inputs: list[str],
        evidence: Dict[str, Any],
        status: str,
    ) -> float:
        explicit = self._numeric(evidence.get("coverage"))
        if explicit is not None:
            return round(max(0.0, min(1.0, explicit)), 2)
        if required_inputs:
            return round(min(1.0, len(fulfilled_inputs) / len(required_inputs)), 2)
        return 0.0 if status == "unavailable" else 1.0

    @staticmethod
    def _indicator_input_key(item: Dict[str, Any]) -> str:
        for key in ("key", "symbol", "label"):
            value = str(item.get(key) or "").strip()
            if value:
                return LIQUIDITY_INPUT_ALIASES.get(value, value)
        return ""

    def _indicator_activation_hint(
        self,
        key: str,
        label: str,
        *,
        missing_inputs: list[str],
        fulfilled_inputs: list[str],
        trust: Dict[str, Any],
        activation: Dict[str, Any],
        panel: PanelState,
        evidence: Dict[str, Any],
    ) -> str:
        hint = LIQUIDITY_INDICATOR_ACTIVATION_HINTS.get(key)
        parts: list[str] = []
        if hint:
            parts.append(hint)
        if activation.get("requiredProviderClass"):
            parts.append(f"requiredProviderClass={activation['requiredProviderClass']}")
        if activation.get("missingProviderReason"):
            parts.append(f"missingProviderReason={activation['missingProviderReason']}")
        if activation.get("paidDataLikelyRequired"):
            parts.append("paidDataLikelyRequired=True")
        if activation.get("requiredRealSourceForScore"):
            parts.append("requiredRealSourceForScore=True")
        if activation.get("scoreExclusionReason"):
            parts.append(f"scoreExclusionReason={activation['scoreExclusionReason']}")
        if activation.get("proxyObservationOnlyReason"):
            parts.append(f"proxyObservationOnlyReason={activation['proxyObservationOnlyReason']}")
        if activation.get("sourceAuthorityRouteRejected"):
            parts.append(f"sourceAuthorityReason={activation['sourceAuthorityReason']}")
        if activation.get("routeRejectedReasonCodes"):
            parts.append(
                "routeRejectedReasonCodes=" + ",".join(str(code) for code in activation["routeRejectedReasonCodes"])
            )
        if trust["trustLevel"] in {"weak", "unavailable"}:
            parts.append(f"trust gate={trust['trustLevel']} / {trust['sourceTier']}")
        if missing_inputs:
            parts.append(f"缺少: {', '.join(missing_inputs)}")
        elif fulfilled_inputs:
            parts.append(f"已激活: {', '.join(fulfilled_inputs)}")
        if activation.get("observationOnly"):
            parts.append("observationOnly=True")
        if activation.get("proxyOnly"):
            parts.append("proxyOnly=True")
        if not activation.get("scoreContributionAllowed"):
            parts.append("scoreContributionAllowed=False")
        if trust["freshness"] in {"stale", "fallback", "partial"}:
            parts.append(f"freshness={trust['freshness']}")
        if evidence.get("capReason"):
            parts.append(f"cap={evidence['capReason']}")
        if trust["scoreCap"] < 1.0:
            parts.append("score capped")
        if panel.source and panel.source != "unavailable":
            parts.append(f"source={panel.source}")
        if not parts:
            parts.append(f"{label} 暂无可用激活路径")
        return "；".join(parts)

    @staticmethod
    def _indicator_cap_reason(
        trust: Dict[str, Any],
        evidence: Dict[str, Any],
        should_cap: bool,
        activation_cap_reason: Optional[str],
    ) -> Optional[str]:
        if not should_cap:
            return evidence.get("capReason") or activation_cap_reason
        return (
            evidence.get("capReason")
            or (trust["degradationReasons"][0] if trust["degradationReasons"] else None)
            or activation_cap_reason
        )

    @staticmethod
    def _indicator_degradation_reasons(evidence: Dict[str, Any]) -> tuple[str, ...]:
        reasons: list[str] = []
        for key in ("degradationReason", "capReason"):
            value = str(evidence.get(key) or "").strip()
            if value and value not in reasons:
                reasons.append(value)
        return tuple(reasons)

    @staticmethod
    def _should_cap_indicator_score(status: str, trust: Dict[str, Any], evidence: Dict[str, Any]) -> bool:
        if trust["trustLevel"] in {"weak", "unavailable"}:
            return True
        if status in {"partial", "stale", "fallback"}:
            return True
        if str(evidence.get("freshness") or "").lower() in {"stale", "fallback", "mock"}:
            return True
        return False

    @staticmethod
    def _source_confidence_weight(source_type: str) -> float:
        return SOURCE_CONFIDENCE_BY_TYPE.get(str(source_type or "").lower(), 0.5)

    @staticmethod
    def _source_confidence_freshness(freshness: str) -> str:
        normalized = str(freshness or "").lower()
        if normalized == "mock":
            return "synthetic"
        if normalized == "error":
            return "unavailable"
        return normalized or "unknown"

    @staticmethod
    def _indicator_degradation_reason(status: str, inputs: List[Dict[str, Any]]) -> Optional[str]:
        explicit_reasons = [
            str(item.get("degradationReason") or "")
            for item in inputs
            if str(item.get("degradationReason") or "")
        ]
        if "direct_provider_backfill" in explicit_reasons:
            return "direct_provider_backfill"
        if any(bool(item.get("isFallback")) for item in inputs):
            return "fallback_source"
        if any(bool(item.get("isStale")) for item in inputs):
            return "stale_source"
        if status == "partial" or any(bool(item.get("isPartial")) for item in inputs):
            return "partial_coverage"
        if status == "unavailable" or any(bool(item.get("isUnavailable")) for item in inputs):
            return "unavailable_source"
        return None

    @staticmethod
    def _timestamp_millis_to_iso(value: Any) -> Optional[str]:
        millis = LiquidityMonitorService._numeric(value)
        if millis is None:
            return None
        return datetime.fromtimestamp(millis / 1000, tz=timezone.utc).astimezone(CN_TZ).isoformat(timespec="seconds")

    def _direct_backfill_freshness(self, as_of: Any, *, max_age: timedelta, now: datetime) -> str:
        parsed = self._parse_time(as_of)
        if parsed is None:
            return "unavailable"
        age = now.astimezone(CN_TZ) - parsed.astimezone(CN_TZ)
        if age > max_age:
            return "stale"
        return "live"

    @staticmethod
    def _source_type_freshness_floor(source_type: str) -> Optional[str]:
        return SOURCE_TYPE_FRESHNESS_FLOOR.get(str(source_type or "").lower())

    def _freshness_with_source_type(
        self,
        freshness: str,
        source_type: str,
        *,
        is_fallback: bool = False,
        is_stale: bool = False,
    ) -> str:
        values = [str(freshness or "").lower()]
        source_type_floor = self._source_type_freshness_floor(source_type)
        if source_type_floor:
            values.append(source_type_floor)
        if is_fallback:
            values.append("fallback")
        if is_stale:
            values.append("stale")
        return self._weakest_freshness(values)

    def _panel_item_freshness_floor(self, payload: Dict[str, Any]) -> Optional[str]:
        items = [item for item in payload.get("items", []) if isinstance(item, dict)]
        if not items:
            return None
        floors = [self._raw_item_freshness_floor(item, payload) for item in items]
        if any(floor is None for floor in floors):
            return None
        return self._weakest_freshness(str(floor or "") for floor in floors)

    def _raw_item_freshness_floor(self, item: Dict[str, Any], payload: Dict[str, Any]) -> Optional[str]:
        explicit = str(item.get("freshness") or "").lower()
        source = str(item.get("source") or payload.get("source") or "").lower()
        source_type = str(item.get("sourceType") or payload.get("sourceType") or "").lower()
        if source == "mock" or explicit == "mock":
            return "mock"
        if bool(item.get("isFallback") or item.get("fallbackUsed")) or source in {"fallback", "mock", "unavailable"}:
            return self._weakest_freshness([explicit, "fallback"])
        source_type_floor = self._source_type_freshness_floor(source_type)
        if source_type_floor in {"fallback", "mock", "unavailable"}:
            return self._weakest_freshness([explicit, source_type_floor])
        if bool(item.get("isStale")):
            return self._weakest_freshness([explicit, "stale"])
        return source_type_floor

    @staticmethod
    def _weakest_freshness(values: Iterable[str]) -> str:
        filtered = [value for value in values if value in FRESHNESS_ORDER]
        if not filtered:
            return "unavailable"
        return max(filtered, key=lambda value: FRESHNESS_ORDER.get(value, 99))

    @staticmethod
    def _weakest_evidence_freshness(values: Iterable[str]) -> str:
        filtered = [value for value in values if value in EVIDENCE_FRESHNESS_ORDER]
        if not filtered:
            return "unavailable"
        return max(filtered, key=lambda value: EVIDENCE_FRESHNESS_ORDER.get(value, 99))

    @staticmethod
    def _regime(score: int) -> str:
        if score >= 70:
            return "abundant"
        if score >= 56:
            return "supportive"
        if score >= 45:
            return "neutral"
        if score >= 30:
            return "tight"
        return "stress"

    @staticmethod
    def _signed_percent_text(value: Optional[float]) -> str:
        if value is None:
            return "待确认"
        return f"{value:+.2f}%"

    def _is_vix_item_usable(self, item: Dict[str, Any], _: PanelState) -> bool:
        if str(item.get("sourceType") or "").lower() != "official_public":
            return True
        return self._change_value(item) is not None or self._numeric(item.get("value") or item.get("price")) is not None

    def _is_yield_item_usable(self, item: Dict[str, Any], _: PanelState) -> bool:
        return self._change_value(item) is not None

    def _is_observation_item_usable(self, item: Dict[str, Any], _: PanelState) -> bool:
        return self._numeric(item.get("value")) is not None

    @staticmethod
    def _signed_number_text(value: Optional[float]) -> str:
        if value is None:
            return "待确认"
        return f"{value:+.2f}"

    @staticmethod
    def _now() -> datetime:
        return datetime.now(CN_TZ)
