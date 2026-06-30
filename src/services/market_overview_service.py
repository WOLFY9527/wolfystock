# -*- coding: utf-8 -*-
"""Market overview data service with short-lived cache and audit logging."""

from __future__ import annotations

import copy
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence
from zoneinfo import ZoneInfo

from data_provider.coinbase_public_provider import (
    COINBASE_PUBLIC_PROVIDER_ID,
    COINBASE_PUBLIC_PROVIDER_NAME,
    COINBASE_PUBLIC_SOURCE_TIER,
    COINBASE_PUBLIC_TRUST_LEVEL,
    COINBASE_PUBLIC_VENUE,
)
from src.contracts.source_confidence import coerce_source_confidence_contract
from src.services.cn_hk_connect_flow_provider import AuthorizedCnHkConnectFlowCacheProvider
from src.services.cn_hk_flow_contracts import (
    CnHkFlowProviderUnavailable,
    build_authorized_cn_hk_connect_flow_snapshot,
)
from src.services.cn_provider_health_service import CNProviderHealthService
from src.services.data_source_router import CapabilityResolver, DataSourceRouteRequest, DataSourceRouter
from src.services.data_source_router_diagnostics import build_data_source_route_diagnostic_snapshot
from src.services.execution_log_service import ExecutionLogService
from src.services.fx_commodities_contracts import FX_COMMODITY_DELAYED_PROXY_SYMBOLS
from src.services.futures_contracts import list_futures_contracts
from src.services.investor_signal_model import build_consumer_safe_investor_signal
from src.services.liquidity_monitor_service import LiquidityMonitorService
from src.services.market_data_quality import build_consumer_data_quality_state
from src.services.market_breadth_readiness_service import (
    build_market_breadth_readiness_contract,
)
from src.services.consumer_issue_labels import build_consumer_issues, sanitize_consumer_reason_payload
from src.services.market_data_source_registry import resolve_source_label
from src.services.market_rotation_radar_service import MarketRotationRadarService
from src.services.official_macro_source_registry import get_official_macro_source_for_transport_source
from src.services.official_macro_transport import (
    FED_LIQUIDITY_FRED_SERIES_IDS,
    MacroObservation,
    OfficialMacroTransportError,
    USD_PRESSURE_FRED_SERIES_IDS,
    classify_official_macro_exception,
    fetch_fred_observation_points,
    fetch_treasury_daily_rate_observation_points,
    fred_runtime_config_probe,
)
from src.services.official_macro_liquidity_cache_contracts import (
    build_official_cn_money_market_cache_bundle,
    build_official_fed_liquidity_cache_bundle,
    build_official_us_rates_cache_bundle,
    build_official_usd_pressure_cache_bundle,
    official_cn_money_market_series_id,
    official_us_rates_series_id,
    official_usd_pressure_series_id,
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
from src.services.us_breadth_contracts import (
    US_BREADTH_MISSING_PROVIDER_REASON,
    US_BREADTH_SYMBOLS,
    build_us_breadth_missing_authority_diagnostic,
    representative_sample_breadth_metadata,
)
from src.services.polygon_us_breadth_provider import (
    POLYGON_HIGH_LOW_HISTORY_UNAVAILABLE_REASON,
    POLYGON_US_BREADTH_AUTHORITY_BASIS,
    POLYGON_US_BREADTH_SOURCE,
    POLYGON_US_BREADTH_SOURCE_LABEL,
    POLYGON_US_BREADTH_SOURCE_TIER,
    POLYGON_US_BREADTH_SOURCE_TYPE,
    POLYGON_US_BREADTH_TRUST_LEVEL,
    POLYGON_US_BREADTH_UNIVERSE,
    diagnostic_summary as polygon_us_breadth_diagnostic_summary,
    run_polygon_us_breadth_activation,
)
from src.services.provider_evidence_snapshot import build_provider_evidence_snapshot
from src.services.research_readiness_contract import build_research_readiness_v1
from src.services.market_overview_yfinance_transport import (
    fetch_yfinance_quote_history_frame,
    fetch_yfinance_spy_atr_history_frame,
)
from src.services.market_cache import MARKET_CACHE_TTLS, REFRESH_WARNING, market_cache
from src.services.market_intelligence_trust_gate import (
    evaluate_market_intelligence_trust,
    evaluate_market_intelligence_trust_from_sources,
)
from src.services.market_decision_semantics import derive_market_decision_semantics
from src.services.market_intelligence_actionability import build_market_actionability_frame
from src.services.market_intelligence_evidence import build_market_intelligence_evidence_frame
from src.services.market_regime_decision_engine import build_market_regime_decision
from src.services.market_regime_synthesis_adapter import (
    build_liquidity_impulse_synthesis_payload,
    build_market_regime_synthesis_payload,
)
from src.services.reason_code_vocabulary import classify_reason_codes
from src.services.rotation_state_evidence import build_rotation_state_evidence
from src.services.rotation_radar_quote_provider import get_rotation_radar_quote_provider
from src.services.vix_metadata import normalize_vix_panel_metadata, normalize_vix_quote_metadata
from src.storage import DatabaseManager

PanelPayload = Dict[str, Any]
CN_TZ = timezone(timedelta(hours=8))
US_EASTERN_TZ = ZoneInfo("America/New_York")
FALLBACK_WARNING = "备用示例数据，不代表当前行情"
INSUFFICIENT_MARKET_DATA_WARNING = "当前真实数据不足，市场温度仅供界面演示"
MARKET_OVERVIEW_BRIEFING_SCHEMA_VERSION = "market_overview_briefing_v1"
MARKET_OVERVIEW_BRIEFING_NO_ADVICE_DISCLOSURE = "仅供市场结构观察与研究整理，不用于个性化决策或执行。"
MARKET_RESEARCH_READINESS_REQUIRED_EVIDENCE = ("macro", "liquidity", "technical")
OFFICIAL_MACRO_UNAVAILABLE_WARNING = "部分官方宏观指标暂不可用"
OFFICIAL_DAILY_FRESHNESS_POLICY_ID = "official_daily_us_weekday_t_plus_1"
OFFICIAL_WEEKLY_FED_LIQUIDITY_FRESHNESS_POLICY_ID = "official_weekly_fed_liquidity_t_plus_7"
OFFICIAL_USD_PRESSURE_FRESHNESS_POLICY_ID = "official_h10_weekly_batch_t_plus_7"
OFFICIAL_DAILY_FRESHNESS_DETAIL_KEYS = (
    "officialObservationDate",
    "officialAsOf",
    "freshnessPolicy",
    "calendarAssumption",
    "maxAcceptedLagDays",
    "maxAcceptedBusinessLagDays",
    "calendarLagDays",
    "businessLagDays",
    "freshnessDecision",
    "staleReason",
)
OFFICIAL_DAILY_FRESHNESS_POLICIES = {
    "VIXCLS": {
        "freshnessPolicy": OFFICIAL_DAILY_FRESHNESS_POLICY_ID,
        "calendarAssumption": "US/Eastern weekdays; holidays not modeled",
        "maxAcceptedLagDays": 4,
        "maxAcceptedBusinessLagDays": 2,
    },
    "DGS2": {
        "freshnessPolicy": OFFICIAL_DAILY_FRESHNESS_POLICY_ID,
        "calendarAssumption": "US/Eastern weekdays; holidays not modeled",
        "maxAcceptedLagDays": 4,
        "maxAcceptedBusinessLagDays": 2,
    },
    "DGS10": {
        "freshnessPolicy": OFFICIAL_DAILY_FRESHNESS_POLICY_ID,
        "calendarAssumption": "US/Eastern weekdays; holidays not modeled",
        "maxAcceptedLagDays": 4,
        "maxAcceptedBusinessLagDays": 2,
    },
    "DGS30": {
        "freshnessPolicy": OFFICIAL_DAILY_FRESHNESS_POLICY_ID,
        "calendarAssumption": "US/Eastern weekdays; holidays not modeled",
        "maxAcceptedLagDays": 4,
        "maxAcceptedBusinessLagDays": 2,
    },
    "T10Y2Y": {
        "freshnessPolicy": OFFICIAL_DAILY_FRESHNESS_POLICY_ID,
        "calendarAssumption": "US/Eastern weekdays; holidays not modeled",
        "maxAcceptedLagDays": 4,
        "maxAcceptedBusinessLagDays": 2,
    },
    "T10Y3M": {
        "freshnessPolicy": OFFICIAL_DAILY_FRESHNESS_POLICY_ID,
        "calendarAssumption": "US/Eastern weekdays; holidays not modeled",
        "maxAcceptedLagDays": 4,
        "maxAcceptedBusinessLagDays": 2,
    },
    "DTWEXBGS": {
        "freshnessPolicy": OFFICIAL_USD_PRESSURE_FRESHNESS_POLICY_ID,
        "calendarAssumption": "Federal Reserve H.10 weekly Monday release; daily rows through prior Friday; holidays not modeled",
        "maxAcceptedLagDays": 10,
        "maxAcceptedBusinessLagDays": 7,
    },
    "SOFR": {
        "freshnessPolicy": OFFICIAL_DAILY_FRESHNESS_POLICY_ID,
        "calendarAssumption": "US/Eastern weekdays; holidays not modeled",
        "maxAcceptedLagDays": 4,
        "maxAcceptedBusinessLagDays": 2,
    },
    "DFF": {
        "freshnessPolicy": OFFICIAL_DAILY_FRESHNESS_POLICY_ID,
        "calendarAssumption": "US/Eastern weekdays; holidays not modeled",
        "maxAcceptedLagDays": 4,
        "maxAcceptedBusinessLagDays": 2,
    },
    "BAMLH0A0HYM2": {
        "freshnessPolicy": OFFICIAL_DAILY_FRESHNESS_POLICY_ID,
        "calendarAssumption": "US/Eastern weekdays; holidays not modeled",
        "maxAcceptedLagDays": 4,
        "maxAcceptedBusinessLagDays": 2,
    },
    "RRPONTSYD": {
        "freshnessPolicy": OFFICIAL_DAILY_FRESHNESS_POLICY_ID,
        "calendarAssumption": "US/Eastern weekdays; holidays not modeled",
        "maxAcceptedLagDays": 4,
        "maxAcceptedBusinessLagDays": 2,
    },
    "WALCL": {
        "freshnessPolicy": OFFICIAL_WEEKLY_FED_LIQUIDITY_FRESHNESS_POLICY_ID,
        "calendarAssumption": "US/Eastern weekdays; holidays not modeled",
        "maxAcceptedLagDays": 10,
        "maxAcceptedBusinessLagDays": 7,
    },
    "WTREGEN": {
        "freshnessPolicy": OFFICIAL_WEEKLY_FED_LIQUIDITY_FRESHNESS_POLICY_ID,
        "calendarAssumption": "US/Eastern weekdays; holidays not modeled",
        "maxAcceptedLagDays": 10,
        "maxAcceptedBusinessLagDays": 7,
    },
    "WRESBAL": {
        "freshnessPolicy": OFFICIAL_WEEKLY_FED_LIQUIDITY_FRESHNESS_POLICY_ID,
        "calendarAssumption": "US/Eastern weekdays; holidays not modeled",
        "maxAcceptedLagDays": 10,
        "maxAcceptedBusinessLagDays": 7,
    },
}
OFFICIAL_OVERLAY_FAILURE_REASONS = {
    "not_configured",
    "cache_miss",
    "transport_error",
    "http_error",
    "timeout",
    "missing_api_key",
    "disabled_config",
    "empty_response",
    "stale_official_row",
    "parse_error",
    "missing_series",
    "refresh_not_attempted",
    "budget_exhausted",
}
MARKET_TEMPERATURE_REQUIRED_RELIABLE_INPUT_COUNT = 5
MARKET_TEMPERATURE_REQUIRED_RELIABLE_PANEL_COUNT = 3
MARKET_TEMPERATURE_MIN_COVERAGE = 0.25
MARKET_OVERVIEW_EVIDENCE_CONTRACT_VERSION = "market_overview_evidence.v1"
MARKET_OVERVIEW_OFFICIAL_MACRO_READINESS_CONTRACT_VERSION = "market_overview_official_macro_readiness.v1"
MARKET_OVERVIEW_OFFICIAL_MACRO_READINESS_LABELS = {
    "vix_pressure": "VIX / 波动率官方上下文",
    "usd_pressure": "美元官方上下文",
    "us_rates_pressure": "美债利率官方上下文",
    "fed_liquidity": "美联储流动性官方上下文",
    "cn_money_market_rates": "中国货币市场官方上下文",
}
MARKET_OVERVIEW_CONSUMER_EVIDENCE_KEYS = (
    "contractVersion",
    "diagnosticOnly",
    "scoreReliabilityAllowed",
    "cardKey",
    "endpoint",
    "source",
    "sourceLabel",
    "sourceType",
    "asOf",
    "updatedAt",
    "freshness",
    "isFallback",
    "isStale",
    "isPartial",
    "isSynthetic",
    "isUnavailable",
    "isFromSnapshot",
    "isRefreshing",
    "providerHealth",
    "confidenceWeight",
    "coverage",
    "degradationReason",
    "capReason",
    "sourceAuthorityAllowed",
    "scoreContributionAllowed",
    "observationOnly",
    "reasonFamilies",
)
MARKET_OVERVIEW_ENDPOINTS = {
    "indices": "/api/v1/market-overview/indices",
    "sentiment": "/api/v1/market-overview/sentiment",
    "funds_flow": "/api/v1/market-overview/funds-flow",
    "macro": "/api/v1/market-overview/macro",
    "crypto": "/api/v1/market/crypto",
    "market_sentiment": "/api/v1/market/sentiment",
    "cn_indices": "/api/v1/market/cn-indices",
    "cn_breadth": "/api/v1/market/cn-breadth",
    "cn_flows": "/api/v1/market/cn-flows",
    "sector_rotation": "/api/v1/market/sector-rotation",
    "us_breadth": "/api/v1/market/us-breadth",
    "rates": "/api/v1/market/rates",
    "fx_commodities": "/api/v1/market/fx-commodities",
    "temperature": "/api/v1/market/temperature",
    "market_briefing": "/api/v1/market/briefing",
    "futures": "/api/v1/market/futures",
    "cn_short_sentiment": "/api/v1/market/cn-short-sentiment",
}


def project_market_overview_consumer_evidence_snapshot(raw_snapshot: Any) -> Dict[str, Any]:
    if not isinstance(raw_snapshot, Mapping):
        return {}

    projection: Dict[str, Any] = {}
    for key in MARKET_OVERVIEW_CONSUMER_EVIDENCE_KEYS:
        if key == "providerHealth":
            continue
        if key in raw_snapshot:
            projection[key] = copy.deepcopy(raw_snapshot.get(key))

    provider_health = raw_snapshot.get("providerHealth")
    if isinstance(provider_health, Mapping) and "status" in provider_health:
        projection["providerHealth"] = {"status": copy.deepcopy(provider_health.get("status"))}
    elif "providerHealth" in raw_snapshot and raw_snapshot.get("providerHealth") is None:
        projection["providerHealth"] = None
    projection["dataQuality"] = build_consumer_data_quality_state(raw_snapshot)
    return sanitize_consumer_reason_payload(projection)


def _market_briefing_quality_seed(payload: Mapping[str, Any]) -> Dict[str, Any]:
    freshness_payload = payload.get("sourceFreshnessEvidence")
    if isinstance(freshness_payload, Mapping):
        seed = {
            "freshness": freshness_payload.get("freshness"),
            "isFallback": freshness_payload.get("isFallback"),
            "isPartial": freshness_payload.get("isPartial"),
            "isUnavailable": freshness_payload.get("isUnavailable"),
        }
        if freshness_payload.get("isStale") is not None:
            seed["isStale"] = freshness_payload.get("isStale")
        return seed
    return {
        "freshness": payload.get("freshness"),
        "isFallback": payload.get("isFallback"),
        "isStale": payload.get("isStale"),
        "isPartial": payload.get("isPartial"),
        "isUnavailable": payload.get("isUnavailable"),
    }


def _market_briefing_data_quality_summary(state: str) -> str:
    summaries = {
        "ready": "当前摘要可用于市场结构观察。",
        "delayed": "部分输入存在延迟，当前摘要仅保留观察用途。",
        "cached": "部分输入来自缓存或最近可用数据，当前摘要仅保留结构观察。",
        "partial": "关键输入仍不完整，当前摘要仅保留结构观察。",
        "no_evidence": "当前缺少足够输入，摘要仅保留结构观察。",
        "unavailable": "新鲜输入暂不可用，摘要仅保留结构观察。",
    }
    return summaries.get(state, "当前摘要仅保留市场结构观察。")


def _market_briefing_freshness_status(seed: Mapping[str, Any]) -> Dict[str, str]:
    state = str(seed.get("freshness") or "").strip().lower() or "unknown"
    labels = {
        "live": "更新正常",
        "fresh": "更新正常",
        "cached": "使用缓存",
        "delayed": "更新延迟",
        "stale": "数据过期",
        "partial": "部分输入缺失",
        "fallback": "已降级到最近可用输入",
        "mock": "当前输入不可用",
        "synthetic": "当前输入不可用",
        "unavailable": "新鲜输入暂不可用",
        "error": "新鲜输入暂不可用",
        "unknown": "输入状态待确认",
    }
    messages = {
        "live": "主要输入已按当前节奏更新，可继续做结构观察。",
        "fresh": "主要输入已按当前节奏更新，可继续做结构观察。",
        "cached": "部分摘要来自缓存输入，请把结论视为结构观察。",
        "delayed": "部分输入存在延迟，请先把摘要视为观察线索。",
        "stale": "部分输入已经过期，请等待更新后再加强判断。",
        "partial": "关键输入仍不完整，请先把摘要视为观察线索。",
        "fallback": "当前摘要使用最近可用输入维持结构观察，不代表实时状态。",
        "mock": "当前缺少可用新鲜输入，请等待后续更新。",
        "synthetic": "当前缺少可用新鲜输入，请等待后续更新。",
        "unavailable": "新鲜输入暂不可用，请等待后续更新。",
        "error": "当前无法确认新鲜输入，请等待后续更新。",
        "unknown": "当前输入状态仍在确认中，请保持观察。",
    }
    return {
        "state": state,
        "label": labels.get(state, "输入状态待确认"),
        "message": messages.get(state, "当前输入状态仍在确认中，请保持观察。"),
    }


def _market_briefing_section_keys(payload: Mapping[str, Any]) -> List[str]:
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    if not items:
        return []
    if payload.get("isReliable"):
        defaults = [
            "usRiskAppetite",
            "cnMoneyEffect",
            "macroPressure",
            "liquidity",
            "riskWatch",
        ]
    else:
        defaults = [
            "marketReadiness",
            "fallbackUsage",
            "nextWatch",
        ]
    if len(items) <= len(defaults):
        return defaults[: len(items)]
    return [*defaults, *[f"summarySection{index}" for index in range(len(defaults) + 1, len(items) + 1)]]


def _market_briefing_degraded_inputs(
    payload: Mapping[str, Any],
    *,
    data_quality_state: str,
    freshness_status: Mapping[str, str],
) -> List[Dict[str, str]]:
    degraded: List[Dict[str, str]] = []
    if data_quality_state != "ready":
        status = "unavailable" if data_quality_state in {"unavailable", "no_evidence"} else "degraded"
        degraded.append(
            {
                "section": "marketSummary",
                "status": status,
                "label": "摘要输入需要复核" if status == "degraded" else "摘要输入暂不可用",
                "message": _market_briefing_data_quality_summary(data_quality_state),
            }
        )
    fallback_count = int(payload.get("fallbackInputCount") or 0)
    if fallback_count > 0:
        degraded.append(
            {
                "section": "recentInputs",
                "status": "degraded",
                "label": "最近可用输入仍在使用",
                "message": "部分摘要仍依赖缓存或最近可用输入，请把结论视为结构观察。",
            }
        )
    if payload.get("temperatureAvailable") is False:
        degraded.append(
            {
                "section": "temperatureConclusion",
                "status": "unavailable",
                "label": "更强方向判断已收敛",
                "message": "当前缺少足够可靠证据，因此不提升为更强的市场方向判断。",
            }
        )
    if not degraded and freshness_status.get("state") in {"delayed", "stale", "partial", "fallback", "unavailable", "error"}:
        degraded.append(
            {
                "section": "inputFreshness",
                "status": "degraded",
                "label": "输入时效需要复核",
                "message": str(freshness_status.get("message") or "当前输入时效需要复核。"),
            }
        )
    return degraded


def _with_market_briefing_typed_contract(payload: Dict[str, Any]) -> Dict[str, Any]:
    quality_seed = _market_briefing_quality_seed(payload)
    data_quality = build_consumer_data_quality_state(quality_seed)
    freshness_status = _market_briefing_freshness_status(quality_seed)
    section_keys = _market_briefing_section_keys(payload)
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    payload["schemaVersion"] = MARKET_OVERVIEW_BRIEFING_SCHEMA_VERSION
    payload["marketSummarySections"] = [
        {
            "key": section_keys[index] if index < len(section_keys) else f"summarySection{index + 1}",
            "title": str(item.get("title") or ""),
            "message": str(item.get("message") or ""),
            "severity": str(item.get("severity") or "neutral"),
            "category": str(item.get("category") or "risk"),
            **({"confidence": float(item.get("confidence"))} if item.get("confidence") is not None else {}),
        }
        for index, item in enumerate(items)
        if isinstance(item, Mapping)
    ]
    payload["dataQuality"] = {
        **data_quality,
        "summary": _market_briefing_data_quality_summary(str(data_quality.get("state") or "no_evidence")),
    }
    payload["freshnessStatus"] = freshness_status
    payload["degradedInputs"] = _market_briefing_degraded_inputs(
        payload,
        data_quality_state=str(data_quality.get("state") or "no_evidence"),
        freshness_status=freshness_status,
    )
    payload["noAdviceDisclosure"] = MARKET_OVERVIEW_BRIEFING_NO_ADVICE_DISCLOSURE
    payload["observationOnly"] = True
    payload["decisionGrade"] = False
    return payload

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
    "authorized_licensed_feed": 1.0,
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
    "polygon_us_grouped_daily": "authorized_licensed_feed",
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
    "polygon_us_grouped_daily": "Polygon grouped daily US equities",
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
CN_INDICES_OBSERVATION_PROVIDER_TIMEOUT_SECONDS = 1.0
CN_INDICES_AKSHARE_OBSERVATION_TIMEOUT_SECONDS = 1.0
MARKET_OVERVIEW_OBSERVATION_ROUTE_REJECTED_REASON = "market_overview_observation_route_rejected"
MARKET_OVERVIEW_OBSERVATION_AUTHORITY_REJECTED_REASON = "market_overview_observation_authority_claim_rejected"
MARKET_OVERVIEW_OBSERVATION_METADATA_MISSING_REASON = "market_overview_observation_metadata_missing"
MARKET_OVERVIEW_OBSERVATION_INVALID_METADATA_REASON = "market_overview_observation_invalid_metadata"
MARKET_OVERVIEW_OBSERVATION_ALLOWED_FRESHNESS = frozenset({"delayed", "cached", "stale", "unavailable", "t_plus_1_or_delayed"})
MARKET_OVERVIEW_OBSERVATION_AUTHORITY_FRESHNESS = frozenset({"fresh", "live", "realtime"})
MARKET_OVERVIEW_OBSERVATION_AUTHORITY_TRUST_LEVELS = frozenset(
    {
        "reliable",
        "reliable_realtime",
        "score_grade",
        "decision_grade",
        "reliable_for_filings_metadata",
    }
)
MARKET_TEMPERATURE_SOURCE_AUTHORITY_REJECTED_REASON = "source_authority_router_rejected"
MARKET_TEMPERATURE_PROXY_CONTEXT_REASON = "proxy_context_only"
MARKET_TEMPERATURE_PROVIDER_ABSENT_REASON = "provider_absent"
MARKET_TEMPERATURE_PROXY_CONTEXT_SOURCES = frozenset(
    {
        "yahoo",
        "yfinance",
        "yfinance_proxy",
        "yfinance_current_baseline",
        "yahooquery",
    }
)
MARKET_TEMPERATURE_PROXY_CONTEXT_SOURCE_TYPES = frozenset(
    {"public_api", "public_proxy", "proxy_public", "unofficial_proxy", "unofficial_public_api"}
)
MARKET_TEMPERATURE_HK_INDEX_SYMBOLS = frozenset({"HSI", "HSTECH", "HSI.HK", "HSTECH.HK"})
MARKET_TEMPERATURE_SCORE_DRIVING_SYMBOLS = {
    "indices": frozenset({"000001.SH", "399001.SZ", "399006.SZ", "000300.SH", "HSI", "HSTECH", "HSI.HK", "HSTECH.HK"}),
    "breadth": frozenset({"ADV_RATIO", "LIMIT_UP", "LIMIT_DOWN"}),
    "flows": frozenset({"CN_ETF", "NORTHBOUND"}),
    "rates": frozenset({"VIX", "US10Y", "DR007", "SHIBOR"}),
    "fx": frozenset({"USD_TWI", "DXY", "USDCNH", "WTI", "GOLD"}),
    "futures": frozenset({"ES", "NQ", "YM", "RTY"}),
    "sentiment": frozenset({"FGI"}),
    "crypto": frozenset({"BTC", "ETH", "BNB"}),
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


def _normalize_official_series_id(value: Any) -> str:
    text = str(value or "").strip()
    if ":" in text:
        text = text.rsplit(":", 1)[-1]
    return text.upper()


def _parse_official_observation_date(value: Any) -> Optional[Any]:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except Exception:
            try:
                return datetime.strptime(text[:10], "%Y-%m-%d").date()
            except Exception:
                return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(US_EASTERN_TZ).date()
    return parsed.date()


def _us_weekday_lag_days(observation_date: Any, current_date: Any) -> int:
    if current_date <= observation_date:
        return 0
    cursor = observation_date
    lag = 0
    while cursor < current_date:
        cursor = cursor + timedelta(days=1)
        if cursor.weekday() < 5:
            lag += 1
    return lag


def _official_daily_freshness_details(
    series_id: Any,
    as_of: Any,
    *,
    official_observation_date: Any = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    normalized_series = _normalize_official_series_id(series_id)
    policy = OFFICIAL_DAILY_FRESHNESS_POLICIES.get(normalized_series)
    if not policy:
        return {}
    observation_date = (
        _parse_official_observation_date(official_observation_date)
        or _parse_official_observation_date(as_of)
    )
    if observation_date is None:
        details: Dict[str, Any] = {
            "freshnessPolicy": str(policy["freshnessPolicy"]),
            "calendarAssumption": str(policy["calendarAssumption"]),
            "maxAcceptedLagDays": int(policy["maxAcceptedLagDays"]),
            "maxAcceptedBusinessLagDays": int(policy["maxAcceptedBusinessLagDays"]),
            "freshnessDecision": "stale_official_row",
            "staleReason": "official observation date missing or malformed",
        }
        if as_of:
            details["officialAsOf"] = str(as_of)
        return details
    current = (now or datetime.now(CN_TZ)).astimezone(US_EASTERN_TZ)
    current_date = current.date()
    calendar_lag_days = max(0, (current_date - observation_date).days)
    business_lag_days = _us_weekday_lag_days(observation_date, current_date)
    max_calendar_lag = int(policy["maxAcceptedLagDays"])
    max_business_lag = int(policy["maxAcceptedBusinessLagDays"])
    accepted = calendar_lag_days <= max_calendar_lag and business_lag_days <= max_business_lag
    details: Dict[str, Any] = {
        "officialObservationDate": observation_date.isoformat(),
        "freshnessPolicy": str(policy["freshnessPolicy"]),
        "calendarAssumption": str(policy["calendarAssumption"]),
        "maxAcceptedLagDays": max_calendar_lag,
        "maxAcceptedBusinessLagDays": max_business_lag,
        "calendarLagDays": calendar_lag_days,
        "businessLagDays": business_lag_days,
        "freshnessDecision": "accepted" if accepted else "stale_official_row",
    }
    if as_of:
        details["officialAsOf"] = str(as_of)
    if not accepted:
        details["staleReason"] = (
            f"official row lag {calendar_lag_days} calendar days and "
            f"{business_lag_days} US weekdays exceeded "
            f"{max_calendar_lag} calendar day / {max_business_lag} US weekday policy"
        )
    return details


def _official_daily_detail_payload(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        key: value[key]
        for key in OFFICIAL_DAILY_FRESHNESS_DETAIL_KEYS
        if key in value and value[key] not in {None, ""}
    }


def get_freshness_status(
    as_of: Any,
    category: str,
    source: str,
    is_fallback: bool,
    *,
    source_type: str = "",
    series_id: Any = None,
    official_observation_date: Any = None,
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
    official_daily_details = (
        _official_daily_freshness_details(
            series_id,
            as_of,
            official_observation_date=official_observation_date,
            now=current,
        )
        if source_type_key == "official_public"
        else {}
    )

    daily_categories = {"equity_index", "breadth", "flows", "sentiment"}
    if official_daily_details and source_type_key == "official_public":
        freshness = "delayed" if official_daily_details["freshnessDecision"] == "accepted" else "stale"
    elif category_key == "macro_rate" and source_type_key == "official_public":
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

    result = {
        "freshness": freshness,
        "isFallback": False,
        "isStale": freshness == "stale",
        "delayMinutes": delay_minutes,
        "warning": "数据可能已过期，请以交易所/券商行情为准" if freshness == "stale" else None,
    }
    if official_daily_details:
        result.update(official_daily_details)
    return result


class MarketOverviewService:
    """Fetch market overview panels from public sources, with cached payloads."""

    CACHE_TTL_SECONDS = 300
    MARKET_COLD_START_TIMEOUT_SECONDS = 2.0
    YFINANCE_PROXY_AGGREGATE_BUDGET_SECONDS = 1.8
    OFFICIAL_MACRO_AGGREGATE_BUDGET_SECONDS = 1.8
    OFFICIAL_MACRO_CALL_TIMEOUT_SECONDS = 0.9
    OFFICIAL_MACRO_TREASURY_FALLBACK_TIMEOUT_CAP_SECONDS = 0.25
    OFFICIAL_MACRO_CRITICAL_FRED_TIMEOUT_FLOOR_SECONDS = 0.2
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

    def __init__(
        self,
        *,
        cn_hk_connect_flow_provider: Optional[Callable[[], Any]] = None,
    ) -> None:
        self._official_macro_micro_cache: Dict[str, tuple[float, List[MacroObservation]]] = {}
        self._official_macro_overlay_diagnostics: Dict[str, str] = {}
        self._official_macro_overlay_diagnostic_details: Dict[str, Dict[str, Any]] = {}
        self._quote_request_memo: Optional[Dict[str, tuple[bool, Any]]] = None
        self._cn_hk_connect_flow_provider = (
            cn_hk_connect_flow_provider
            if cn_hk_connect_flow_provider is not None
            else AuthorizedCnHkConnectFlowCacheProvider()
        )

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
    OFFICIAL_RATE_CONTEXT_SERIES = {
        "US10Y2Y": ("T10Y2Y", "10Y-2Y 利差", "bp", "US"),
        "US10Y3M": ("T10Y3M", "10Y-3M 利差", "bp", "US"),
    }
    OFFICIAL_OVERLAY_SERIES_BY_SYMBOL = {
        "VIX": "VIXCLS",
        "US2Y": "DGS2",
        "US10Y": "DGS10",
        "US30Y": "DGS30",
        "US10Y2Y": "T10Y2Y",
        "US10Y3M": "T10Y3M",
    }
    OFFICIAL_MACRO_CRITICAL_FRED_SERIES_IDS = ("DGS10", "DGS30")
    STATIC_FALLBACK_ACTIVATION_SYMBOLS = {"CN00Y"}
    OFFICIAL_MACRO_SERIES = {
        "FEDFUNDS": ("DFF", "Fed Funds", "%", "US"),
        "CPI": ("CPIAUCSL", "CPI", "YoY %", "US"),
        "PPI": ("PPIACO", "PPI", "YoY %", "US"),
        "CREDIT": ("BAMLH0A0HYM2", "Credit spreads", "bps", None),
    }
    FED_LIQUIDITY_SERIES = {
        "FED_ASSETS": ("WALCL", "Fed total assets", "USD mn", "US"),
        "FED_RRP": ("RRPONTSYD", "Overnight reverse repo", "USD bn", "US"),
        "TGA": ("WTREGEN", "Treasury General Account", "USD mn", "US"),
        "RESERVES": ("WRESBAL", "Reserve balances", "USD mn", "US"),
    }
    USD_PRESSURE_SERIES = {
        "USD_TWI": ("DTWEXBGS", "Trade-weighted USD", "idx", "US"),
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
    CN_INDEX_SYMBOL_ALIASES = {
        "000001.SS": "000001.SH",
        "sh000001": "000001.SH",
        "000300.SS": "000300.SH",
        "HSI.HK": "HSI",
        "HSTECH.HK": "HSTECH",
    }
    AKSHARE_CN_INDEX_SYMBOLS = {
        "sh000001": "000001.SH",
        "sz399001": "399001.SZ",
        "sz399006": "399006.SZ",
        "sh000688": "000688.SH",
        "sh000016": "000016.SH",
        "sh000300": "000300.SH",
    }
    AKSHARE_CN_INDEX_EXPECTED_SYMBOLS = tuple(AKSHARE_CN_INDEX_SYMBOLS.values())

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
        return self._with_breadth_readiness(
            self._classified_snapshot(
                cache_key="cn_breadth",
                panel_name="ChinaBreadthCard",
                endpoint_url="/api/v1/market/cn-breadth",
                fetcher=self._fetch_cn_breadth_snapshot,
                fallback_factory=self._fallback_cn_breadth_snapshot,
                actor=actor,
            ),
            "CN",
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
        authority_state: Dict[str, Mapping[str, Any]] = {}

        def fetcher() -> Dict[str, Any]:
            payload = self._fetch_us_breadth_snapshot()
            diagnostic = payload.get("authorityDiagnostics")
            if isinstance(diagnostic, Mapping):
                authority_state["diagnostic"] = dict(diagnostic)
            return payload

        def fallback_factory() -> Dict[str, Any]:
            return self._fallback_us_breadth_snapshot(
                authority_diagnostic=authority_state.get("diagnostic")
            )

        return self._with_request_quote_memo(
            lambda: self._with_breadth_readiness(
                self._classified_snapshot(
                    cache_key="us_breadth",
                    panel_name="UsBreadthCard",
                    endpoint_url="/api/v1/market/us-breadth",
                    fetcher=fetcher,
                    fallback_factory=fallback_factory,
                    actor=actor,
                ),
                "US",
            )
        )

    def _with_breadth_readiness(self, payload: Dict[str, Any], market: str) -> Dict[str, Any]:
        return {
            **payload,
            "breadthReadiness": build_market_breadth_readiness_contract(
                market_snapshots={market: payload}
            ),
        }

    def get_rates(self, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._classified_snapshot(
            cache_key="rates",
            panel_name="RatesCard",
            endpoint_url="/api/v1/market/rates",
            fetcher=self._fetch_rates_snapshot,
            fallback_factory=self._fallback_rates_snapshot,
            actor=actor,
        )

    def prewarm_official_macro_cache(self) -> Dict[str, Dict[str, Any]]:
        """Refresh official macro panels through the existing Market Overview cache path."""
        return {
            "rates": self._cached_payload(
                "rates",
                self._fetch_rates_snapshot,
                self._fallback_rates_snapshot,
            ),
            "macro": self._cached_payload(
                "macro",
                self._fetch_macro,
                lambda: self._fallback_overview_panel(
                    "macro",
                    "MacroIndicatorsCard",
                    "数据源刷新超时，当前显示备用快照",
                ),
            ),
        }

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
            market_regime_synthesis = self._build_market_regime_synthesis_payload(inputs)
            liquidity_impulse_synthesis = self._build_liquidity_impulse_synthesis_payload(inputs)
            payload = {
                "source": source,
                "updatedAt": _now_iso(),
                "scores": scores,
                "marketRegimeSynthesis": market_regime_synthesis,
                "marketDecisionSemantics": self._build_market_decision_semantics_payload(
                    market_regime_synthesis,
                    liquidity_impulse_synthesis,
                    inputs,
                ),
                "regimeSummary": self._build_regime_summary_payload(
                    market_regime_synthesis,
                    inputs,
                ),
                **trust,
            }
            payload["marketActionabilityFrame"] = build_market_actionability_frame(
                payload,
                inputs=inputs,
                liquidity_impulse_synthesis=liquidity_impulse_synthesis,
            )
            payload["marketIntelligenceEvidenceFrame"] = build_market_intelligence_evidence_frame(
                payload,
                inputs=inputs,
                liquidity_impulse_synthesis=liquidity_impulse_synthesis,
            )
            if not trust["isReliable"]:
                payload["warning"] = INSUFFICIENT_MARKET_DATA_WARNING
                payload["fallbackUsed"] = True
                payload["isFallback"] = trust["reliableInputCount"] == 0
                payload["freshness"] = "fallback" if trust["reliableInputCount"] == 0 else "stale"
                payload.update(self._market_temperature_disabled_state_meta(trust))
                payload["marketActionabilityFrame"] = build_market_actionability_frame(
                    payload,
                    inputs=inputs,
                    liquidity_impulse_synthesis=liquidity_impulse_synthesis,
                )
                payload["marketIntelligenceEvidenceFrame"] = build_market_intelligence_evidence_frame(
                    payload,
                    inputs=inputs,
                    liquidity_impulse_synthesis=liquidity_impulse_synthesis,
                )
            elif trust["fallbackInputCount"]:
                payload["warning"] = "部分指标来自备用数据，评分仅使用真实数据。"
                payload["fallbackUsed"] = True
                payload["marketActionabilityFrame"] = build_market_actionability_frame(
                    payload,
                    inputs=inputs,
                    liquidity_impulse_synthesis=liquidity_impulse_synthesis,
                )
                payload["marketIntelligenceEvidenceFrame"] = build_market_intelligence_evidence_frame(
                    payload,
                    inputs=inputs,
                    liquidity_impulse_synthesis=liquidity_impulse_synthesis,
                )
            return payload

        def fallback_factory() -> Dict[str, Any]:
            inputs = self._fallback_market_temperature_inputs()
            trust = self._market_temperature_trust(
                inputs,
                self._summarize_market_temperature_confidence(inputs),
            )
            market_regime_synthesis = self._build_market_regime_synthesis_payload(inputs)
            liquidity_impulse_synthesis = self._build_liquidity_impulse_synthesis_payload(inputs)
            payload = {
                "source": "fallback",
                "updatedAt": _now_iso(),
                "scores": self._insufficient_market_temperature_scores(),
                "marketRegimeSynthesis": market_regime_synthesis,
                "marketDecisionSemantics": self._build_market_decision_semantics_payload(
                    market_regime_synthesis,
                    liquidity_impulse_synthesis,
                    inputs,
                ),
                "regimeSummary": self._build_regime_summary_payload(
                    market_regime_synthesis,
                    inputs,
                ),
                "warning": INSUFFICIENT_MARKET_DATA_WARNING,
                "fallbackUsed": True,
                "isFallback": True,
                "freshness": "fallback",
                **trust,
                **self._market_temperature_disabled_state_meta(trust),
            }
            payload["marketActionabilityFrame"] = build_market_actionability_frame(
                payload,
                inputs=inputs,
                liquidity_impulse_synthesis=liquidity_impulse_synthesis,
            )
            payload["marketIntelligenceEvidenceFrame"] = build_market_intelligence_evidence_frame(
                payload,
                inputs=inputs,
                liquidity_impulse_synthesis=liquidity_impulse_synthesis,
            )
            return payload

        started_at = time.monotonic()
        payload = self._cached_payload("temperature", fetcher, fallback_factory)
        payload = self._with_market_meta(payload, self._category_for_cache_key("temperature"))
        payload = self._with_market_research_readiness(payload)
        payload["providerHealth"] = self._provider_health(payload, "temperature", duration_ms=int((time.monotonic() - started_at) * 1000), error_summary=_compact_error_summary(payload.get("lastError")))
        payload = self._with_evidence_snapshot(payload, self._category_for_cache_key("temperature"))
        payload = self._with_consumer_issues(payload)
        return payload

    @staticmethod
    def _market_research_missing_evidence(payload: Mapping[str, Any]) -> List[str]:
        missing: List[str] = []

        def _append(value: str) -> None:
            if value not in missing:
                missing.append(value)

        if not payload.get("temperatureAvailable"):
            _append("macro")
        if not payload.get("conclusionAllowed"):
            _append("liquidity")
        if payload.get("insufficientReliableInputs"):
            _append("technical")

        summary = payload.get("regimeSummary") if isinstance(payload.get("regimeSummary"), Mapping) else {}
        for key in ("blockers", "confidenceCaps", "nextWatchItems"):
            rows = summary.get(key)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, Mapping):
                    continue
                row_key = str(row.get("key") or "").lower()
                if "liquidity" in row_key:
                    _append("liquidity")
                if "macro" in row_key or "official_macro" in row_key:
                    _append("macro")
                if "rotation" in row_key or "breadth" in row_key or "technical" in row_key:
                    _append("technical")

        freshness_evidence = (
            payload.get("sourceFreshnessEvidence")
            if isinstance(payload.get("sourceFreshnessEvidence"), Mapping)
            else {}
        )
        freshness = str(freshness_evidence.get("freshness") or payload.get("freshness") or "").lower()
        if freshness in {"fallback", "stale", "synthetic", "mock", "unavailable", "error", "unknown"}:
            _append("freshness")
        if str(payload.get("sourceTier") or "").lower() in {"unavailable", "synthetic", "static_fallback"}:
            _append("source_authority")
        return missing

    def _with_market_research_readiness(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        conclusion_allowed = bool(payload.get("conclusionAllowed"))
        score_cap = self._clean_number(payload.get("scoreCap"))
        if score_cap is None:
            score_cap = 1.0 if conclusion_allowed else 0.0
        freshness_evidence = (
            payload.get("sourceFreshnessEvidence")
            if isinstance(payload.get("sourceFreshnessEvidence"), Mapping)
            else {}
        )
        freshness = freshness_evidence.get("freshness") or payload.get("freshness") or "unknown"
        missing = self._market_research_missing_evidence(payload)
        source_tier = payload.get("sourceTier") or payload.get("sourceType")
        trust_level = payload.get("trustLevel")
        evidence = [
            {
                "domain": domain,
                "source": "market_intelligence_trust_gate",
                "sourceType": source_tier,
                "sourceTier": source_tier,
                "trustLevel": trust_level,
                "freshness": freshness,
                "sourceAuthorityAllowed": conclusion_allowed,
                "scoreContributionAllowed": conclusion_allowed,
                "observationOnly": not conclusion_allowed,
                "scoreCap": score_cap,
                "isFallback": bool(payload.get("isFallback") or (payload.get("fallbackUsed") and not conclusion_allowed)),
                "isStale": bool(payload.get("isStale")),
                "isSynthetic": str(freshness).lower() in {"synthetic", "mock"},
                "isUnavailable": bool(payload.get("isUnavailable")),
            }
            for domain in MARKET_RESEARCH_READINESS_REQUIRED_EVIDENCE
        ]
        readiness = build_research_readiness_v1(
            {
                "requiredEvidence": list(MARKET_RESEARCH_READINESS_REQUIRED_EVIDENCE),
                "missingEvidence": missing,
                "evidence": evidence,
                "sourceAuthorityAllowed": conclusion_allowed,
                "scoreContributionAllowed": conclusion_allowed,
                "scoreCap": score_cap,
                "freshness": freshness,
                "noAdviceBoundary": True,
                "consumerActionBoundary": "no_advice",
                "debugRef": "market:temperature",
            }
        )
        return {**payload, "researchReadiness": readiness}

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
                "sourceAuthorityDiagnostics": self._build_market_briefing_source_authority_diagnostics(inputs),
                **briefing_trust,
            }
            if not briefing_trust["isReliable"]:
                payload["warning"] = "当前真实数据不足，暂不生成强市场判断。"
                payload["fallbackUsed"] = True
                payload["isFallback"] = trust["reliableInputCount"] == 0
                payload["freshness"] = "fallback" if trust["reliableInputCount"] == 0 else "stale"
                payload.update(self._market_temperature_disabled_state_meta(briefing_trust))
            elif trust["fallbackInputCount"]:
                payload["warning"] = "部分解读已排除备用数据。"
                payload["fallbackUsed"] = True
            return payload

        def fallback_factory() -> Dict[str, Any]:
            inputs = self._fallback_market_temperature_inputs()
            trust = self._market_briefing_trust(
                inputs,
                self._summarize_market_temperature_confidence(inputs),
            )
            scores = self._insufficient_market_temperature_scores()
            return {
                "source": "fallback",
                "updatedAt": _now_iso(),
                "items": self._build_market_briefing_items(inputs, scores, "fallback", trust),
                "sourceAuthorityDiagnostics": self._build_market_briefing_source_authority_diagnostics(inputs),
                "warning": "当前真实数据不足，暂不生成强市场判断。",
                "fallbackUsed": True,
                "isFallback": True,
                "freshness": "fallback",
                **trust,
                **self._market_temperature_disabled_state_meta(trust),
            }

        started_at = time.monotonic()
        payload = self._cached_payload("market_briefing", fetcher, fallback_factory)
        payload = self._with_market_meta(payload, self._category_for_cache_key("market_briefing"))
        payload["providerHealth"] = self._provider_health(payload, "market_briefing", duration_ms=int((time.monotonic() - started_at) * 1000), error_summary=_compact_error_summary(payload.get("lastError")))
        payload = self._with_evidence_snapshot(payload, self._category_for_cache_key("market_briefing"))
        payload = _with_market_briefing_typed_contract(payload)
        payload = self._with_consumer_issues(payload)
        return payload

    @staticmethod
    def _with_consumer_issues(payload: Dict[str, Any]) -> Dict[str, Any]:
        freshness_evidence = payload.get("sourceFreshnessEvidence")
        freshness_payload = freshness_evidence if isinstance(freshness_evidence, Mapping) else {}
        freshness = str(freshness_payload.get("freshness") or payload.get("freshness") or "").lower()
        freshness_issue = None
        if freshness in {"fallback", "stale", "cached", "delayed", "partial"}:
            freshness_issue = "freshness_blocked:fallback"
        elif freshness in {"unavailable", "error", "unknown"}:
            freshness_issue = "freshness_blocked:unavailable"
        payload["consumerIssues"] = build_consumer_issues(
            freshness_issue,
            payload.get("disabledReason"),
            payload.get("unavailableReason"),
            payload.get("researchReadiness"),
            payload.get("evidenceSnapshot"),
            payload.get("dataQuality"),
        )
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

    def get_market_regime_decision(self, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            inputs = self._get_market_temperature_input_snapshot()
            input_source = "market_temperature_input_snapshot"
        except Exception:
            inputs = self._fallback_market_temperature_inputs()
            input_source = "fallback_market_temperature_inputs"
        payload = build_market_regime_decision(inputs)
        payload["updatedAt"] = _now_iso()
        payload["inputSource"] = input_source
        return payload

    def _build_market_regime_synthesis_payload(self, inputs: Mapping[str, Any]) -> Dict[str, Any]:
        return build_market_regime_synthesis_payload(inputs)

    def _build_liquidity_impulse_synthesis_payload(self, inputs: Mapping[str, Any]) -> Dict[str, Any]:
        return build_liquidity_impulse_synthesis_payload(inputs)

    def _build_regime_summary_payload(
        self,
        market_regime_synthesis: Mapping[str, Any],
        inputs: Mapping[str, Any],
    ) -> Dict[str, Any]:
        primary_regime = str(market_regime_synthesis.get("primaryRegime") or "data_insufficient")
        synthesis_confidence = self._clean_number(market_regime_synthesis.get("confidence")) or 0.0
        liquidity_signal_raw = self._extract_regime_summary_liquidity_signal(inputs)
        liquidity_signal = (
            self._consumer_safe_capital_flow_signal(liquidity_signal_raw)
            if isinstance(liquidity_signal_raw, Mapping)
            else None
        )
        official_macro_readiness = self._consumer_safe_official_macro_readiness(
            self._extract_regime_summary_official_macro_readiness(inputs)
        )
        rotation_rollup = self._normalize_regime_summary_rotation_rollup(
            self._extract_regime_summary_rotation_rollup(inputs)
        )

        drivers: List[Dict[str, Any]] = []
        blockers: List[Dict[str, Any]] = []
        contradictions: List[Dict[str, Any]] = []
        confidence_caps: List[Dict[str, Any]] = []
        next_watch_items: List[Dict[str, Any]] = []

        if primary_regime and primary_regime != "data_insufficient":
            drivers.append(
                self._regime_summary_entry(
                    f"market_regime:{primary_regime}",
                    self._regime_summary_market_regime_label(primary_regime),
                    self._regime_summary_synthesis_detail(market_regime_synthesis),
                )
            )
            if primary_regime == "term_premium_or_inflation_scare":
                drivers.append(
                    self._regime_summary_entry(
                        "macro:term_premium_or_inflation_scare",
                        "宏观框架偏通胀/期限溢价压力",
                        "温度合成提示油价、利率与通胀再定价仍可能回头压制风险资产。",
                    )
                )

        for gap in market_regime_synthesis.get("dataGaps") or []:
            if not isinstance(gap, Mapping):
                continue
            gap_key = str(gap.get("key") or "market_gap")
            gap_label = str(gap.get("label") or gap_key)
            gap_reason = str(gap.get("reason") or "需要更多确认")
            next_watch_items.append(
                self._regime_summary_entry(
                    f"watch:{gap_key}",
                    gap_label,
                    gap_reason,
                )
            )

        if not liquidity_signal:
            blockers.append(
                self._regime_summary_entry(
                    "liquidity_signal_missing",
                    "Liquidity capitalFlowSignal 缺失",
                    "缺少现成的流动性观察信号，暂不把温度合成提升为更强的资金主线判断。",
                )
            )
            confidence_caps.append(
                self._regime_summary_entry(
                    "liquidity_signal_missing",
                    "流动性信号缺失",
                    "缺少 capitalFlowSignal 时只能保持 mixed / no-clear-edge。",
                )
            )
            next_watch_items.append(
                self._regime_summary_entry(
                    "watch:capital_flow_signal",
                    "等待 Liquidity capitalFlowSignal",
                    "确认资金更偏向成长、油气还是防御资产。",
                )
            )
        if not rotation_rollup:
            blockers.append(
                self._regime_summary_entry(
                    "rotation_rollup_missing",
                    "Rotation rotationFamilyRollup 缺失",
                    "缺少主题家族轮动观察，无法确认风险偏好是否已经扩散或转向防御。",
                )
            )
            confidence_caps.append(
                self._regime_summary_entry(
                    "rotation_rollup_missing",
                    "轮动家族信号缺失",
                    "缺少 rotationFamilyRollup 时不能下更强的风格结论。",
                )
            )
            next_watch_items.append(
                self._regime_summary_entry(
                    "watch:rotation_family_rollup",
                    "等待 Rotation family rollup",
                    "确认 AI / 软件 / 半导体 / 防御家族谁在真实领涨。",
                )
            )

        if liquidity_signal:
            likely_destination = str(liquidity_signal.get("likelyDestination") or "no_clear_edge")
            if likely_destination and likely_destination != "no_clear_edge":
                drivers.append(
                    self._regime_summary_entry(
                        f"liquidity:{likely_destination}",
                        self._regime_summary_destination_label(likely_destination),
                        str(liquidity_signal.get("explanation") or "流动性观察信号支持当前主线。"),
                    )
                )
            if str(liquidity_signal.get("freshness") or "") in {"stale", "fallback", "unavailable", "error"}:
                blockers.append(
                    self._regime_summary_entry(
                        "liquidity_signal_degraded",
                        "Liquidity 信号已降级",
                        f"当前流动性信号 freshness={liquidity_signal.get('freshness')}，只能保持观察态。",
                    )
                )
                confidence_caps.append(
                    self._regime_summary_entry(
                        "liquidity_signal_degraded",
                        "流动性信号 freshness 降级",
                        "stale / fallback / unavailable 信号不会被提升为 score-grade 结论。",
                    )
                )
            if liquidity_signal.get("observationOnly") is True:
                confidence_caps.append(
                    self._regime_summary_entry(
                        "liquidity_signal_observation_only",
                        "Liquidity 信号仅观察态",
                        "capitalFlowSignal 本身不授予 authority 或 score 权限，因此 summary 只能给出 capped confidence。",
                    )
                )
            for raw_code in liquidity_signal.get("contradictionCodes") or []:
                contradictions.append(
                    self._regime_summary_entry(
                        f"liquidity_contradiction:{raw_code}",
                        "流动性信号存在冲突",
                        str(raw_code),
                    )
                )
            qqq_iwm_watch_item = self._regime_summary_qqq_iwm_proxy_watch_item(liquidity_signal)
            if qqq_iwm_watch_item:
                next_watch_items.append(qqq_iwm_watch_item)

        if official_macro_readiness:
            readiness_status = str(official_macro_readiness.get("status") or "missing")
            if readiness_status == "ready":
                drivers.append(
                    self._regime_summary_entry(
                        "official_macro_readiness:ready",
                        "官方宏观缓存上下文已就绪",
                        str(official_macro_readiness.get("detail") or "官方宏观缓存证据可作为观察上下文，但不授予 source authority 或 score 权限。"),
                    )
                )
            else:
                next_watch_items.append(
                    self._regime_summary_entry(
                        "watch:official_macro_readiness",
                        "等待官方宏观上下文补齐",
                        str(official_macro_readiness.get("detail") or "官方宏观 readiness 仍不完整，只能作为下一步观察项。"),
                    )
                )

        rotation_state_map = self._regime_summary_rotation_state_map(rotation_rollup)
        for family_id, row in rotation_state_map.items():
            signal = row.get("themeFlowSignal") if isinstance(row.get("themeFlowSignal"), Mapping) else {}
            state = str(signal.get("themeFlowState") or "")
            if state in {"leading", "broadening", "rotating"}:
                drivers.append(
                    self._regime_summary_entry(
                        f"rotation:{family_id}",
                        self._regime_summary_family_label(row, family_id),
                        str(signal.get("explanation") or f"{family_id} family shows {state}."),
                    )
                )
            if str(signal.get("freshness") or "") in {"stale", "fallback", "unavailable", "error"}:
                confidence_caps.append(
                    self._regime_summary_entry(
                        f"rotation_degraded:{family_id}",
                        f"{self._regime_summary_family_label(row, family_id)} freshness 降级",
                        f"rotation family freshness={signal.get('freshness')}，只能保持观察态。",
                    )
                )
            breadth_context = self._regime_summary_rotation_breadth_context(row, family_id)
            if breadth_context.get("status") == "confirmed":
                drivers.append(
                    self._regime_summary_entry(
                        f"rotation_breadth:{family_id}",
                        f"{self._regime_summary_family_label(row, family_id)} quote-breadth proxy",
                        str(breadth_context.get("detail") or ""),
                    )
                )
            else:
                next_watch_items.append(
                    self._regime_summary_entry(
                        f"watch:rotation_breadth:{family_id}",
                        f"观察 {self._regime_summary_family_label(row, family_id)} quote-breadth proxy",
                        str(breadth_context.get("detail") or ""),
                    )
                )

        for entry in market_regime_synthesis.get("counterEvidence") or []:
            if not isinstance(entry, Mapping):
                continue
            contradictions.append(
                self._regime_summary_entry(
                    f"counter:{entry.get('key') or 'market_regime'}",
                    str(entry.get("label") or "Counter evidence"),
                    str(entry.get("detail") or "现有主判断仍有反向证据。"),
                )
            )

        growth_destination = bool(liquidity_signal and str(liquidity_signal.get("likelyDestination") or "") == "growth_ai_software_semis")
        oil_destination = bool(liquidity_signal and str(liquidity_signal.get("likelyDestination") or "") == "oil")
        ai_positive = self._regime_summary_family_state(rotation_state_map, "ai") in {"leading", "broadening"}
        software_positive = self._regime_summary_family_state(rotation_state_map, "software") in {"leading", "broadening"}
        semis_mixed = self._regime_summary_family_state(rotation_state_map, "semiconductors") == "mixed"
        energy_positive = self._regime_summary_family_state(rotation_state_map, "energy") in {"leading", "rotating", "broadening"}
        defensive_positive = self._regime_summary_family_state(rotation_state_map, "defensive") in {"leading", "broadening"}
        broad_positive_count = sum(
            1
            for row in rotation_rollup
            if isinstance(row, Mapping)
            and str(((row.get("themeFlowSignal") or {}) if isinstance(row.get("themeFlowSignal"), Mapping) else {}).get("themeFlowState") or "") in {"leading", "broadening"}
        )
        semis_software_conflict = growth_destination and semis_mixed and software_positive
        if semis_software_conflict:
            contradictions.append(
                self._regime_summary_entry(
                    "rotation_conflict:semiconductors_vs_software",
                    "半导体分化与软件修复并存",
                    "成长链内部没有形成一致共振，半导体分化与 SaaS 修复同时出现。",
                )
            )
            confidence_caps.append(
                self._regime_summary_entry(
                    "rotation_conflict:semiconductors_vs_software",
                    "成长内部轮动分化",
                    "半导体与软件没有形成一致强化，confidence 需要继续下调。",
                )
            )
            next_watch_items.append(
                self._regime_summary_entry(
                    "watch:semis_breadth_confirmation",
                    "观察半导体广度能否修复",
                    "确认半导体是否由分化转回 broadening / leading。",
                )
            )

        risk_on_like = primary_regime in {"risk_on_liquidity_expansion", "goldilocks_soft_landing", "china_policy_divergence"}
        risk_off_like = primary_regime in {"risk_off_deleveraging", "credit_or_funding_stress", "dollar_squeeze", "rates_shock_duration_pressure"}
        missing_or_blocked_signals = not liquidity_signal or not rotation_rollup
        degraded_signal_present = any(
            item.get("key") in {
                "liquidity_signal_degraded",
                "rotation_rollup_missing",
                "liquidity_signal_missing",
            }
            or str(item.get("key") or "").startswith("rotation_degraded:")
            for item in [*blockers, *confidence_caps]
        )

        summary_label = "mixed_no_clear_edge"
        if missing_or_blocked_signals or degraded_signal_present or semis_software_conflict:
            summary_label = "mixed_no_clear_edge"
        elif oil_destination or primary_regime == "term_premium_or_inflation_scare" or energy_positive:
            summary_label = "inflation_oil_pressure"
        elif risk_off_like and defensive_positive:
            summary_label = "risk_off_defensive"
        elif risk_on_like and growth_destination and ai_positive and not semis_software_conflict:
            summary_label = "risk_on_growth_led"
        elif risk_on_like and broad_positive_count >= 2:
            summary_label = "risk_on_broad"
        elif market_regime_synthesis.get("liquidityImpulse", 0) and float(market_regime_synthesis.get("liquidityImpulse") or 0.0) > 0.2:
            summary_label = "liquidity_positive"
        elif risk_off_like or float(market_regime_synthesis.get("liquidityImpulse") or 0.0) < -0.2:
            summary_label = "liquidity_negative"

        confidence_value = min(0.62, max(0.0, synthesis_confidence))
        if summary_label == "risk_on_growth_led":
            confidence_value = min(confidence_value, 0.58)
        elif summary_label == "risk_on_broad":
            confidence_value = min(confidence_value, 0.54)
        elif summary_label == "risk_off_defensive":
            confidence_value = min(confidence_value, 0.5)
        elif summary_label in {"liquidity_positive", "liquidity_negative"}:
            confidence_value = min(confidence_value, 0.48)
        elif summary_label == "inflation_oil_pressure":
            confidence_value = min(confidence_value, 0.44)
            confidence_caps.append(
                self._regime_summary_entry(
                    "oil_leadership_needs_inflation_confirmation",
                    "油价主线仍需通胀确认",
                    "油气领涨不等于全面 risk-on，仍需确认利率与通胀是否重新施压。",
                )
            )
            next_watch_items.append(
                self._regime_summary_entry(
                    "watch:oil_vs_rates",
                    "观察油价与利率是否再度同步上行",
                    "若油价继续走强且利率反弹，需重新评估 inflation scare。",
                )
            )
        else:
            confidence_value = min(confidence_value, 0.34)
        if missing_or_blocked_signals:
            confidence_value = min(confidence_value, 0.28)
        if contradictions:
            confidence_value = min(confidence_value, 0.42)
        if degraded_signal_present:
            confidence_value = min(confidence_value, 0.32)
        confidence_value = round(max(0.0, confidence_value), 2)

        explanation = self._regime_summary_explanation(
            summary_label=summary_label,
            primary_regime=primary_regime,
            liquidity_signal=liquidity_signal,
            contradictions=contradictions,
            blockers=blockers,
        )

        return {
            "label": summary_label,
            "title": self._regime_summary_title(summary_label),
            "diagnosticOnly": True,
            "observationOnly": True,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "notInvestmentAdvice": True,
            "drivers": self._dedupe_regime_summary_entries(drivers),
            "blockers": self._dedupe_regime_summary_entries(blockers),
            "contradictions": self._dedupe_regime_summary_entries(contradictions),
            "confidence": {
                "value": confidence_value,
                "label": self._regime_summary_confidence_label(confidence_value),
            },
            "confidenceCaps": self._dedupe_regime_summary_entries(confidence_caps),
            "nextWatchItems": self._dedupe_regime_summary_entries(next_watch_items),
            "explanation": explanation,
            **({"officialMacroReadiness": official_macro_readiness} if official_macro_readiness else {}),
        }

    def _market_temperature_liquidity_context(self) -> Dict[str, Any]:
        try:
            payload = LiquidityMonitorService().get_liquidity_monitor()
        except Exception:
            return {}
        if not isinstance(payload, Mapping):
            return {}

        context: Dict[str, Any] = {}
        signal = payload.get("capitalFlowSignal")
        if isinstance(signal, Mapping):
            context["capitalFlowSignal"] = self._consumer_safe_capital_flow_signal(signal)
        readiness = self._project_official_macro_readiness_from_liquidity_payload(payload)
        if readiness:
            context["officialMacroReadiness"] = readiness
        return context

    def _market_temperature_capital_flow_signal(self) -> Optional[Dict[str, Any]]:
        signal = self._market_temperature_liquidity_context().get("capitalFlowSignal")
        return dict(signal) if isinstance(signal, Mapping) else None

    def _market_temperature_rotation_family_rollup(self) -> List[Dict[str, Any]]:
        try:
            payload = MarketRotationRadarService(
                quote_provider=get_rotation_radar_quote_provider(),
                use_shared_cache=True,
            ).get_rotation_radar()
        except Exception:
            return []
        summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
        rows = summary.get("rotationFamilyRollup")
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
            return []
        result: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            signal = row.get("themeFlowSignal")
            consumer_signal = self._consumer_safe_rotation_signal(signal) if isinstance(signal, Mapping) else {}
            result.append(
                {
                    "familyId": str(row.get("familyId") or ""),
                    "familyName": str(row.get("familyName") or ""),
                    "themeIds": [str(item) for item in row.get("themeIds") or [] if str(item or "").strip()],
                    "themeNames": [str(item) for item in row.get("themeNames") or [] if str(item or "").strip()],
                    "leaderThemeIds": [str(item) for item in row.get("leaderThemeIds") or [] if str(item or "").strip()],
                    "themeCount": int(row.get("themeCount") or 0),
                    "signalThemeCount": int(row.get("signalThemeCount") or 0),
                    "averageRotationScore": round(float(row.get("averageRotationScore") or 0.0), 2),
                    "averageConfidence": round(float(row.get("averageConfidence") or 0.0), 2),
                    "themeFlowSignal": consumer_signal,
                }
            )
        return result

    def _normalize_regime_summary_rotation_rollup(
        self,
        rotation_rollup: Sequence[Mapping[str, Any]],
    ) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for row in rotation_rollup:
            if not isinstance(row, Mapping):
                continue
            signal = row.get("themeFlowSignal")
            result.append(
                {
                    "familyId": str(row.get("familyId") or ""),
                    "familyName": str(row.get("familyName") or ""),
                    "themeIds": [str(item) for item in row.get("themeIds") or [] if str(item or "").strip()],
                    "themeNames": [str(item) for item in row.get("themeNames") or [] if str(item or "").strip()],
                    "leaderThemeIds": [str(item) for item in row.get("leaderThemeIds") or [] if str(item or "").strip()],
                    "themeCount": int(row.get("themeCount") or 0),
                    "signalThemeCount": int(row.get("signalThemeCount") or 0),
                    "averageRotationScore": round(float(row.get("averageRotationScore") or 0.0), 2),
                    "averageConfidence": round(float(row.get("averageConfidence") or 0.0), 2),
                    "themeFlowSignal": self._consumer_safe_rotation_signal(signal) if isinstance(signal, Mapping) else {},
                }
            )
        return result

    def _consumer_safe_capital_flow_signal(self, signal: Mapping[str, Any]) -> Dict[str, Any]:
        safe_signal = build_consumer_safe_investor_signal(signal)
        safe_signal.update(
            {
                "confidence": str(signal.get("confidence") or safe_signal.get("confidenceLabel") or "low"),
                "isFallback": bool(signal.get("isFallback")),
                "isStale": bool(signal.get("isStale")),
                "isPartial": bool(signal.get("isPartial")),
                "likelyDestination": str(signal.get("likelyDestination") or "no_clear_edge"),
                "sourceAssetPressure": [
                    {
                        "asset": str(item.get("asset") or ""),
                        "pressure": str(item.get("pressure") or ""),
                        "freshness": str(item.get("freshness") or ""),
                        "isFallback": bool(item.get("isFallback")),
                        "isStale": bool(item.get("isStale")),
                        "isPartial": bool(item.get("isPartial")),
                    }
                    for item in signal.get("sourceAssetPressure") or []
                    if isinstance(item, Mapping)
                ],
                "contradictionSignals": [str(item) for item in signal.get("contradictionSignals") or [] if str(item or "").strip()],
                "explanation": str(signal.get("explanation") or ""),
            }
        )
        return safe_signal

    def _project_official_macro_readiness_from_liquidity_payload(
        self,
        payload: Mapping[str, Any],
    ) -> Optional[Dict[str, Any]]:
        raw_items: List[Dict[str, Any]] = []
        indicators = payload.get("indicators")
        if isinstance(indicators, Sequence) and not isinstance(indicators, (str, bytes, bytearray)):
            for indicator in indicators:
                if not isinstance(indicator, Mapping):
                    continue
                item = self._official_macro_readiness_item_from_indicator(indicator)
                if item:
                    raw_items.append(item)

        if not raw_items:
            synthesis = payload.get("liquidityImpulseSynthesis")
            if isinstance(synthesis, Mapping):
                raw_items.extend(self._official_macro_readiness_items_from_synthesis(synthesis))

        if not raw_items:
            return None
        return self._consumer_safe_official_macro_readiness({"items": raw_items})

    def _official_macro_readiness_item_from_indicator(
        self,
        indicator: Mapping[str, Any],
    ) -> Optional[Dict[str, Any]]:
        key = self._official_macro_readiness_item_key(indicator.get("key"))
        if key not in MARKET_OVERVIEW_OFFICIAL_MACRO_READINESS_LABELS:
            return None

        diagnostics = indicator.get("coverageDiagnostics") if isinstance(indicator.get("coverageDiagnostics"), Mapping) else {}
        evidence = indicator.get("evidence") if isinstance(indicator.get("evidence"), Mapping) else {}
        cache_bundle = diagnostics.get("cacheBundleDiagnostics") if isinstance(diagnostics.get("cacheBundleDiagnostics"), Mapping) else {}
        if not cache_bundle and isinstance(evidence.get("cacheBundleDiagnostics"), Mapping):
            cache_bundle = evidence.get("cacheBundleDiagnostics") or {}

        missing_inputs = [
            str(item)
            for item in diagnostics.get("missingInputs") or []
            if str(item or "").strip()
        ]
        real_source_available = bool(
            diagnostics.get("realSourceAvailable")
            or cache_bundle.get("realSourceAvailable")
            or cache_bundle.get("readinessEligible")
        )
        score_allowed = bool(
            diagnostics.get("scoreContributionAllowed")
            or cache_bundle.get("scoreContributionAllowed")
            or indicator.get("includedInScore")
        )
        freshness = self._official_macro_readiness_freshness(
            diagnostics.get("freshness")
            or indicator.get("freshness")
            or evidence.get("freshness")
            or cache_bundle.get("freshness")
        )
        degraded = bool(
            indicator.get("isFallback")
            or indicator.get("isStale")
            or indicator.get("isUnavailable")
            or evidence.get("isFallback")
            or evidence.get("isStale")
            or evidence.get("isUnavailable")
            or str(indicator.get("status") or "").lower() in {"unavailable", "error"}
            or freshness in {"fallback", "stale", "unavailable", "error"}
        )

        if real_source_available and score_allowed and not missing_inputs and not degraded:
            status = "ready"
        elif real_source_available or score_allowed:
            status = "partial"
        else:
            status = "missing"

        return {
            "key": key,
            "status": status,
            "freshness": freshness,
        }

    def _official_macro_readiness_items_from_synthesis(
        self,
        synthesis: Mapping[str, Any],
    ) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for list_name, default_status in (
            ("dominantDrivers", "ready"),
            ("dataGaps", "missing"),
            ("counterEvidence", "partial"),
        ):
            rows = synthesis.get(list_name)
            if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
                continue
            for row in rows:
                if not isinstance(row, Mapping):
                    continue
                key = self._official_macro_readiness_item_key(row.get("key"))
                if key not in MARKET_OVERVIEW_OFFICIAL_MACRO_READINESS_LABELS:
                    continue
                status = default_status
                if default_status == "ready" and row.get("scoreContributionAllowed") is False:
                    status = "partial"
                result.append(
                    {
                        "key": key,
                        "status": status,
                        "freshness": self._official_macro_readiness_freshness(row.get("freshness")),
                    }
                )
        return result

    def _consumer_safe_official_macro_readiness(
        self,
        readiness: Mapping[str, Any] | None,
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(readiness, Mapping):
            return None

        safe_items: List[Dict[str, Any]] = []
        raw_items = readiness.get("items")
        if isinstance(raw_items, Sequence) and not isinstance(raw_items, (str, bytes, bytearray)):
            for raw_item in raw_items:
                if not isinstance(raw_item, Mapping):
                    continue
                safe_items.append(self._consumer_safe_official_macro_readiness_item(raw_item))

        if safe_items:
            ready_count = sum(1 for item in safe_items if item["status"] == "ready")
            partial_count = sum(1 for item in safe_items if item["status"] == "partial")
            missing_count = sum(1 for item in safe_items if item["status"] == "missing")
            if ready_count and not partial_count and not missing_count:
                status = "ready"
            elif ready_count or partial_count:
                status = "partial"
            else:
                status = "missing"
        else:
            ready_count = max(0, int(self._clean_number(readiness.get("readyCount")) or 0))
            partial_count = max(0, int(self._clean_number(readiness.get("partialCount")) or 0))
            missing_count = max(0, int(self._clean_number(readiness.get("missingCount")) or 0))
            status = self._official_macro_readiness_status(readiness.get("status"))
            if status == "unknown":
                if ready_count and not partial_count and not missing_count:
                    status = "ready"
                elif ready_count or partial_count:
                    status = "partial"
                else:
                    status = "missing"

        return {
            "contractVersion": MARKET_OVERVIEW_OFFICIAL_MACRO_READINESS_CONTRACT_VERSION,
            "diagnosticOnly": True,
            "observationOnly": True,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "status": status,
            "readyCount": ready_count,
            "partialCount": partial_count,
            "missingCount": missing_count,
            "items": safe_items,
            "detail": self._official_macro_readiness_detail(
                status=status,
                ready_count=ready_count,
                partial_count=partial_count,
                missing_count=missing_count,
            ),
        }

    def _consumer_safe_official_macro_readiness_item(
        self,
        item: Mapping[str, Any],
    ) -> Dict[str, Any]:
        key = self._official_macro_readiness_item_key(item.get("key"))
        status = self._official_macro_readiness_status(item.get("status"))
        if status == "unknown":
            status = "missing"
        return {
            "key": key,
            "label": MARKET_OVERVIEW_OFFICIAL_MACRO_READINESS_LABELS.get(key, "官方宏观上下文"),
            "status": status,
            "freshness": self._official_macro_readiness_freshness(item.get("freshness")),
            "diagnosticOnly": True,
            "observationOnly": True,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "reason": self._official_macro_readiness_reason(status),
        }

    @staticmethod
    def _official_macro_readiness_item_key(value: Any) -> str:
        raw = str(value or "").strip()
        if ":" in raw:
            raw = raw.rsplit(":", 1)[-1]
        return raw if raw in MARKET_OVERVIEW_OFFICIAL_MACRO_READINESS_LABELS else "official_macro_context"

    @staticmethod
    def _official_macro_readiness_status(value: Any) -> str:
        status = str(value or "").strip().lower()
        if status in {"ready", "partial", "missing"}:
            return status
        if status in {"unavailable", "error", "fallback", "stale"}:
            return "missing"
        return "unknown"

    @staticmethod
    def _official_macro_readiness_freshness(value: Any) -> str:
        freshness = str(value or "").strip().lower()
        if freshness in {"live", "fresh", "cached", "delayed", "partial", "stale", "fallback", "unavailable", "error"}:
            return freshness
        return "unknown"

    @staticmethod
    def _official_macro_readiness_reason(status: str) -> str:
        if status == "ready":
            return "official_macro_context_ready"
        if status == "partial":
            return "official_macro_partial_coverage"
        return "official_macro_missing_or_ambiguous"

    @staticmethod
    def _official_macro_readiness_detail(
        *,
        status: str,
        ready_count: int,
        partial_count: int,
        missing_count: int,
    ) -> str:
        if status == "ready":
            return f"官方宏观上下文已有 {ready_count} 个就绪观察项；该投影仅解释 readiness，不授予 authority 或 score 权限。"
        if status == "partial":
            return (
                "官方宏观上下文仍有缺口："
                f"ready={ready_count}, partial={partial_count}, missing={missing_count}；"
                "仅作为下一步观察项。"
            )
        return "官方宏观上下文缺失或不可判定；仅保留解释性观察，不参与结论升级。"

    def _consumer_safe_rotation_signal(self, signal: Mapping[str, Any]) -> Dict[str, Any]:
        safe_signal = build_consumer_safe_investor_signal(signal)
        safe_signal.update(
            {
                "confidence": round(float(signal.get("confidence") or 0.0), 2) if self._clean_number(signal.get("confidence")) is not None else 0.0,
                "isFallback": bool(signal.get("isFallback")),
                "isStale": bool(signal.get("isStale")),
                "isPartial": bool(signal.get("isPartial")),
                "explanation": str(signal.get("explanation") or ""),
            }
        )
        breadth_evidence = self._consumer_safe_rotation_breadth_evidence(signal.get("breadthEvidence"))
        if breadth_evidence:
            safe_signal["breadthEvidence"] = breadth_evidence
        return safe_signal

    def _consumer_safe_rotation_breadth_evidence(self, value: Any) -> Dict[str, Any]:
        evidence: Dict[str, Any] = {
            "diagnosticOnly": True,
            "observationOnly": True,
            "authorityGrant": False,
            "scoreContributionAllowed": False,
        }
        if isinstance(value, str):
            text = self._safe_rotation_breadth_text(value)
            if not text:
                return {}
            evidence["text"] = text
            return evidence
        if not isinstance(value, Mapping):
            return {}

        observed_members = self._optional_nonnegative_int(value.get("observedMembers"))
        configured_members = self._optional_nonnegative_int(value.get("configuredMembers"))
        coverage_percent = self._optional_percent(value.get("coveragePercent"))
        percent_up = self._optional_percent(value.get("percentUp"))
        outperforming = self._optional_percent(value.get("percentOutperformingBenchmark"))
        if not any(
            item is not None
            for item in (
                observed_members,
                configured_members,
                coverage_percent,
                percent_up,
                outperforming,
            )
        ):
            return {}
        if observed_members is not None:
            evidence["observedMembers"] = observed_members
        if configured_members is not None:
            evidence["configuredMembers"] = configured_members
        if coverage_percent is not None:
            evidence["coveragePercent"] = coverage_percent
        if percent_up is not None:
            evidence["percentUp"] = percent_up
        if outperforming is not None:
            evidence["percentOutperformingBenchmark"] = outperforming
        return evidence

    def _regime_summary_rotation_breadth_context(
        self,
        row: Mapping[str, Any],
        family_id: str,
    ) -> Dict[str, str]:
        signal = row.get("themeFlowSignal") if isinstance(row.get("themeFlowSignal"), Mapping) else {}
        evidence = signal.get("breadthEvidence") if isinstance(signal, Mapping) else None
        family_label = self._regime_summary_family_label(row, family_id)
        base_detail = f"{family_label} quote-breadth proxy is observation-only context; it is not real fund flow or score-grade evidence."
        if not isinstance(signal, Mapping) or not evidence:
            return {
                "status": "watch",
                "detail": f"{base_detail} Existing Rotation breadth evidence is missing, so breadth stays a next-watch item.",
            }
        if not isinstance(evidence, Mapping):
            return {
                "status": "watch",
                "detail": f"{base_detail} Rotation breadth evidence is malformed, so breadth stays a next-watch item.",
            }

        state = str(signal.get("themeFlowState") or "")
        reason_codes = {str(item or "") for item in signal.get("reasonCodes") or []}
        contradiction_codes = [str(item or "") for item in signal.get("contradictionCodes") or [] if str(item or "")]
        evidence_text = str(evidence.get("text") or "").strip()
        metrics = self._rotation_breadth_evidence_metrics(evidence)
        weak_reasons = self._rotation_breadth_weak_reasons(
            evidence=evidence,
            signal=signal,
            state=state,
            reason_codes=reason_codes,
            contradiction_codes=contradiction_codes,
            evidence_text=evidence_text,
        )
        metric_detail = self._rotation_breadth_metric_detail(metrics)
        if weak_reasons:
            reason_text = "、".join(weak_reasons)
            detail = f"{base_detail} Breadth is not confirming yet ({reason_text})."
            if metric_detail:
                detail = f"{detail} {metric_detail}"
            elif evidence_text:
                detail = f"{detail} {evidence_text}"
            return {"status": "watch", "detail": detail}

        detail = f"{base_detail} Breadth confirms the existing Rotation {state or 'state'} context."
        if metric_detail:
            detail = f"{detail} {metric_detail}"
        elif evidence_text:
            detail = f"{detail} {evidence_text}"
        return {"status": "confirmed", "detail": detail}

    def _rotation_breadth_evidence_metrics(self, evidence: Mapping[str, Any]) -> Dict[str, Optional[float]]:
        return {
            "observedMembers": self._clean_number(evidence.get("observedMembers")),
            "configuredMembers": self._clean_number(evidence.get("configuredMembers")),
            "coveragePercent": self._clean_number(evidence.get("coveragePercent")),
            "percentUp": self._clean_number(evidence.get("percentUp")),
            "percentOutperformingBenchmark": self._clean_number(evidence.get("percentOutperformingBenchmark")),
        }

    def _rotation_breadth_weak_reasons(
        self,
        *,
        evidence: Mapping[str, Any],
        signal: Mapping[str, Any],
        state: str,
        reason_codes: set[str],
        contradiction_codes: Sequence[str],
        evidence_text: str,
    ) -> List[str]:
        reasons: List[str] = []
        metrics = self._rotation_breadth_evidence_metrics(evidence)
        if not evidence_text and not any(value is not None for value in metrics.values()):
            reasons.append("missing breadth metrics")
        if state not in {"leading", "broadening", "rotating"}:
            reasons.append("rotation state not confirming")
        if contradiction_codes:
            reasons.append("contradictory rotation evidence")
        if bool(signal.get("isPartial")) or "partial_source" in reason_codes:
            reasons.append("partial rotation coverage")
        coverage_percent = metrics["coveragePercent"]
        percent_up = metrics["percentUp"]
        outperforming = metrics["percentOutperformingBenchmark"]
        observed_members = metrics["observedMembers"]
        configured_members = metrics["configuredMembers"]
        if coverage_percent is not None and coverage_percent < 50.0:
            reasons.append("low breadth coverage")
        if percent_up is not None and percent_up < 55.0:
            reasons.append("weak percent-up breadth")
        if outperforming is not None and outperforming < 50.0:
            reasons.append("weak benchmark-outperformance breadth")
        if observed_members is not None and observed_members < 3:
            reasons.append("too few observed members")
        if (
            observed_members is not None
            and configured_members is not None
            and configured_members > 0
            and observed_members / configured_members < 0.5
        ):
            reasons.append("incomplete member coverage")
        if evidence_text and any(marker in evidence_text.lower() for marker in ("不足", "insufficient", "missing", "partial", "no clear edge")):
            reasons.append("breadth text is not confirming")
        return list(dict.fromkeys(reasons))

    @staticmethod
    def _rotation_breadth_metric_detail(metrics: Mapping[str, Optional[float]]) -> str:
        parts: List[str] = []
        observed = metrics.get("observedMembers")
        configured = metrics.get("configuredMembers")
        if observed is not None and configured is not None:
            parts.append(f"observed members {int(observed)}/{int(configured)}")
        coverage = metrics.get("coveragePercent")
        if coverage is not None:
            parts.append(f"coverage {coverage:.1f}%")
        percent_up = metrics.get("percentUp")
        if percent_up is not None:
            parts.append(f"percent-up {percent_up:.1f}%")
        outperforming = metrics.get("percentOutperformingBenchmark")
        if outperforming is not None:
            parts.append(f"outperforming-benchmark {outperforming:.1f}%")
        return "; ".join(parts) + "." if parts else ""

    @staticmethod
    def _safe_rotation_breadth_text(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        lowered = text.lower()
        forbidden_markers = (
            "provider",
            "routing",
            "router",
            "admin",
            "cache",
            "payload",
            "raw",
            "internal",
            "secret",
            "token",
            "api_key",
            "apikey",
            "credential",
            "http",
        )
        if any(marker in lowered for marker in forbidden_markers):
            return ""
        return text[:240]

    @staticmethod
    def _optional_nonnegative_int(value: Any) -> Optional[int]:
        number = MarketOverviewService._clean_number(value)
        if number is None or number < 0:
            return None
        return int(number)

    @staticmethod
    def _optional_percent(value: Any) -> Optional[float]:
        number = MarketOverviewService._clean_number(value)
        if number is None or number < 0 or number > 100:
            return None
        return round(number, 2)

    @staticmethod
    def _extract_regime_summary_liquidity_signal(inputs: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        direct = inputs.get("capitalFlowSignal")
        if isinstance(direct, Mapping):
            return dict(direct)
        flows = inputs.get("flows")
        if isinstance(flows, Mapping) and isinstance(flows.get("capitalFlowSignal"), Mapping):
            return dict(flows.get("capitalFlowSignal"))
        return None

    @staticmethod
    def _extract_regime_summary_official_macro_readiness(inputs: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        direct = inputs.get("officialMacroReadiness")
        if isinstance(direct, Mapping):
            return dict(direct)
        flows = inputs.get("flows")
        if isinstance(flows, Mapping) and isinstance(flows.get("officialMacroReadiness"), Mapping):
            return dict(flows.get("officialMacroReadiness"))
        return None

    @staticmethod
    def _extract_regime_summary_rotation_rollup(inputs: Mapping[str, Any]) -> List[Dict[str, Any]]:
        direct = inputs.get("rotationFamilyRollup")
        if isinstance(direct, Sequence) and not isinstance(direct, (str, bytes, bytearray)):
            return [dict(item) for item in direct if isinstance(item, Mapping)]
        sectors = inputs.get("sectors")
        if isinstance(sectors, Mapping):
            nested = sectors.get("rotationFamilyRollup")
            if isinstance(nested, Sequence) and not isinstance(nested, (str, bytes, bytearray)):
                return [dict(item) for item in nested if isinstance(item, Mapping)]
        return []

    @staticmethod
    def _regime_summary_rotation_state_map(rotation_rollup: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
        return {
            str(row.get("familyId") or "").lower(): dict(row)
            for row in rotation_rollup
            if isinstance(row, Mapping) and str(row.get("familyId") or "").strip()
        }

    @staticmethod
    def _regime_summary_family_state(rotation_state_map: Mapping[str, Mapping[str, Any]], family_id: str) -> str:
        row = rotation_state_map.get(family_id)
        if not isinstance(row, Mapping):
            return ""
        signal = row.get("themeFlowSignal")
        if not isinstance(signal, Mapping):
            return ""
        return str(signal.get("themeFlowState") or "")

    @staticmethod
    def _regime_summary_qqq_iwm_proxy_watch_item(liquidity_signal: Mapping[str, Any]) -> Optional[Dict[str, str]]:
        if str(liquidity_signal.get("likelyDestination") or "") != "growth_ai_software_semis":
            return None

        rows = liquidity_signal.get("sourceAssetPressure")
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
            return None

        pressure_by_asset: Dict[str, str] = {}
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            asset = str(row.get("asset") or "").strip().lower()
            pressure_value = row.get("pressure")
            if not asset or not isinstance(pressure_value, str):
                continue
            pressure_by_asset[asset] = pressure_value.strip().lower()

        qqq_pressure = pressure_by_asset.get("qqq_institutional_proxy")
        iwm_pressure = pressure_by_asset.get("iwm_industry_proxy")
        if qqq_pressure != "absorbing" or iwm_pressure not in {"lagging", "balanced"}:
            return None

        return MarketOverviewService._regime_summary_entry(
            "watch:qqq_iwm_proxy_confirmation",
            "观察 QQQ / IWM proxy 能否确认成长吸收",
            "QQQ institutional proxy is absorbing while IWM industry proxy is lagging/balanced; this is a quote-derived proxy observation, not real fund flow, and stays next-watch only.",
        )

    @staticmethod
    def _regime_summary_entry(key: str, label: str, detail: str) -> Dict[str, str]:
        return {"key": str(key), "label": str(label), "detail": str(detail)}

    @staticmethod
    def _dedupe_regime_summary_entries(entries: Sequence[Mapping[str, Any]]) -> List[Dict[str, str]]:
        result: List[Dict[str, str]] = []
        seen: set[str] = set()
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            key = str(entry.get("key") or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(
                {
                    "key": key,
                    "label": str(entry.get("label") or key),
                    "detail": str(entry.get("detail") or ""),
                }
            )
        return result

    @staticmethod
    def _regime_summary_confidence_label(value: float) -> str:
        if value <= 0:
            return "blocked"
        if value < 0.5:
            return "low"
        if value < 0.75:
            return "medium"
        return "high"

    @staticmethod
    def _regime_summary_title(label: str) -> str:
        mapping = {
            "risk_on_growth_led": "风险偏好回升，成长主线领跑",
            "risk_on_broad": "风险偏好扩散，广度在改善",
            "risk_off_defensive": "防御偏好占优",
            "liquidity_positive": "流动性环境偏正面",
            "liquidity_negative": "流动性环境偏负面",
            "inflation_oil_pressure": "油价与通胀压力需要警惕",
            "mixed_no_clear_edge": "信号分化，暂无明确优势",
        }
        return mapping.get(label, "信号分化，暂无明确优势")

    @staticmethod
    def _regime_summary_market_regime_label(primary_regime: str) -> str:
        mapping = {
            "risk_on_liquidity_expansion": "市场主合成偏 risk-on / 流动性扩张",
            "goldilocks_soft_landing": "市场主合成偏 soft landing",
            "risk_off_deleveraging": "市场主合成偏 risk-off / 去杠杆",
            "rates_shock_duration_pressure": "市场主合成偏利率久期压力",
            "dollar_squeeze": "市场主合成偏美元挤压",
            "credit_or_funding_stress": "市场主合成偏信用/融资压力",
            "term_premium_or_inflation_scare": "市场主合成偏通胀/期限溢价压力",
            "china_policy_divergence": "市场主合成偏中美政策分化",
            "data_insufficient": "市场主合成数据不足",
        }
        return mapping.get(primary_regime, primary_regime)

    @staticmethod
    def _regime_summary_destination_label(destination: str) -> str:
        mapping = {
            "growth_ai_software_semis": "资金更偏向 AI / 软件 / 半导体成长链",
            "oil": "资金转向油气 / 通胀敏感资产",
            "defensives": "资金更偏向防御资产",
            "no_clear_edge": "资金暂未形成明确主线",
        }
        return mapping.get(destination, destination)

    @staticmethod
    def _regime_summary_family_label(row: Mapping[str, Any], family_id: str) -> str:
        return str(row.get("familyName") or family_id)

    @staticmethod
    def _regime_summary_synthesis_detail(market_regime_synthesis: Mapping[str, Any]) -> str:
        bullets = market_regime_synthesis.get("narrativeBullets")
        if isinstance(bullets, Sequence) and not isinstance(bullets, (str, bytes, bytearray)):
            for bullet in bullets:
                text = str(bullet or "").strip()
                if text:
                    return text
        return "沿用现有 Market Regime synthesis 作为主方向框架。"

    @staticmethod
    def _regime_summary_explanation(
        *,
        summary_label: str,
        primary_regime: str,
        liquidity_signal: Optional[Mapping[str, Any]],
        contradictions: Sequence[Mapping[str, Any]],
        blockers: Sequence[Mapping[str, Any]],
    ) -> str:
        if summary_label == "risk_on_growth_led":
            return "现有温度合成偏向 risk-on，且资金与轮动观察都指向 AI / 成长主线，但由于这些信号仍是 observation-only，结论保持 capped confidence。"
        if summary_label == "risk_on_broad":
            return "现有温度合成偏向 risk-on，轮动家族出现 broadening，说明风险偏好不只集中在单一主线，但仍需更多真实信号确认。"
        if summary_label == "risk_off_defensive":
            return "现有温度合成与轮动观察都偏向防御资产，说明市场更像在降低风险暴露；不过 summary 仍不授予任何交易级 authority。"
        if summary_label == "liquidity_positive":
            return "现有温度合成显示流动性背景偏正面，但还没有足够明确的家族轮动共振，因此只保留温和正向判断。"
        if summary_label == "liquidity_negative":
            return "现有温度合成更像流动性收缩或防御回摆，风险资产扩张缺少足够确认，因此保持负向但非交易级结论。"
        if summary_label == "inflation_oil_pressure":
            return "油气与通胀敏感资产正在吸引注意力，说明 rate-cut 友好背景仍可能被油价和通胀重新约束，因此 confidence 必须继续下调。"
        if contradictions:
            return "成长、流动性与轮动家族之间存在分化信号，当前更适合维持 mixed / no-clear-edge，而不是强行给出单一路径。"
        if blockers:
            return "现有温度合成提供了方向线索，但关键的流动性或轮动观察信号缺失/降级，因此 fail closed 到 mixed / no-clear-edge。"
        if primary_regime == "data_insufficient":
            return "主合成本身已经是数据不足，regimeSummary 继续保持混合观察态。"
        return "现有温度合成没有得到足够一致的流动性与轮动确认，因此保持 mixed / no-clear-edge。"

    def _build_market_decision_semantics_payload(
        self,
        market_regime_synthesis: Mapping[str, Any],
        liquidity_impulse_synthesis: Mapping[str, Any],
        inputs: Mapping[str, Any],
    ) -> Dict[str, Any]:
        rotation_summary = self._build_market_decision_rotation_summary(inputs)
        try:
            return derive_market_decision_semantics(
                market_regime_synthesis,
                liquidity_impulse_synthesis,
                rotation_summary,
            ).to_dict()
        except Exception:
            payload = derive_market_decision_semantics({}, {}, None).to_dict()
            payload["dataGaps"] = [
                *payload.get("dataGaps", []),
                {
                    "surface": "market_decision_semantics",
                    "key": "market_decision_semantics:projection",
                    "label": "Market Decision Semantics",
                    "reason": "semantic_projection_failed",
                },
            ]
            return payload

    def _build_market_decision_rotation_summary(self, inputs: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        panel = inputs.get("sectors")
        if not isinstance(panel, Mapping):
            return None
        items = panel.get("items")
        if not isinstance(items, Sequence):
            return None
        candidates = [item for item in items if isinstance(item, Mapping) and (item.get("symbol") or item.get("label") or item.get("name"))]
        if not candidates:
            return None
        allowed = [item for item in candidates if self._market_decision_rotation_item_allowed(item)]
        selected = allowed[0] if allowed else candidates[0]
        selected_allowed = self._market_decision_rotation_item_allowed(selected)
        score = self._clean_number(selected.get("rotationScore"))
        if score is None:
            score = self._clean_number(selected.get("value"))
        if score is None:
            score = self._clean_number(selected.get("price"))
        source_tier = selected.get("sourceTier") or selected.get("sourceType")
        degradation_reasons = selected.get("degradationReasons")
        data_gaps = [
            {
                "key": f"rotation:{selected.get('symbol') or selected.get('label') or selected.get('name')}",
                "label": str(selected.get("label") or selected.get("name") or selected.get("symbol") or "Rotation"),
                "reason": str(reason),
            }
            for reason in (degradation_reasons if isinstance(degradation_reasons, Sequence) and not isinstance(degradation_reasons, (str, bytes, bytearray)) else [])
            if reason
        ]
        if not selected_allowed and not data_gaps:
            reason = selected.get("sourceAuthorityReason") or selected.get("rankExclusionReason") or selected.get("degradationReason") or "rotation_non_scoring"
            data_gaps.append({
                "key": f"rotation:{selected.get('symbol') or selected.get('label') or selected.get('name')}",
                "label": str(selected.get("label") or selected.get("name") or selected.get("symbol") or "Rotation"),
                "reason": str(reason),
            })
        return {
            "id": selected.get("symbol") or selected.get("id") or selected.get("name"),
            "label": selected.get("label") or selected.get("name") or selected.get("symbol"),
            "rotationScore": score,
            "confidence": self._clean_number(selected.get("confidence") or selected.get("scoreCap")),
            "stage": selected.get("stage") or selected.get("rankingLane"),
            "changePercent": self._clean_number(selected.get("changePercent") or selected.get("change")),
            "source": selected.get("source") or panel.get("source"),
            "sourceTier": source_tier,
            "trustLevel": selected.get("trustLevel") or panel.get("trustLevel"),
            "freshness": selected.get("freshness") or panel.get("freshness"),
            "sourceAuthorityAllowed": bool(selected_allowed),
            "scoreContributionAllowed": bool(selected_allowed),
            "evidenceQuality": "score_grade" if selected_allowed else "taxonomy_only" if selected.get("taxonomyOnly") else "degraded_proxy",
            "dataGaps": data_gaps,
        }

    @staticmethod
    def _market_decision_rotation_item_allowed(item: Mapping[str, Any]) -> bool:
        if item.get("sourceAuthorityAllowed") is not True:
            return False
        if item.get("scoreContributionAllowed") is not True:
            return False
        if item.get("rankEligible") is False or item.get("headlineEligible") is False:
            return False
        if item.get("taxonomyOnly") is True or item.get("observationOnly") is True:
            return False
        return True

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
        if cache_key == self.OVERVIEW_SENTIMENT_CACHE_KEY:
            status = self._resolve_overview_sentiment_status(snapshot, error_message=error_message)
            if status == "failure":
                raw_response = {"cache": "stale_or_fallback", "error": error_message}
            elif snapshot.get("isRefreshing"):
                raw_response = {"cache": "stale_refreshing"}
            else:
                raw_response = {"cache": "hit_or_refreshed"}
        elif error_message:
            status = "failure"
            snapshot["error_message"] = error_message
            raw_response: Dict[str, Any] = {"cache": "stale_or_fallback", "error": error_message}
        elif snapshot.get("isRefreshing"):
            raw_response = {"cache": "stale_refreshing"}
        else:
            raw_response = {"cache": "hit_or_refreshed"}

        if cache_key == self.OVERVIEW_SENTIMENT_CACHE_KEY and error_message:
            snapshot["error_message"] = error_message

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
        snapshot["consumerEvidenceSnapshot"] = project_market_overview_consumer_evidence_snapshot(
            snapshot.get("evidenceSnapshot")
        )
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

    def _resolve_overview_sentiment_status(
        self,
        snapshot: Dict[str, Any],
        *,
        error_message: Optional[str],
    ) -> str:
        has_usable_value = self._has_usable_market_values(snapshot)
        source = str(snapshot.get("source") or "").strip().lower()
        freshness = str(snapshot.get("freshness") or "").strip().lower()
        has_degraded_state = bool(
            error_message
            or snapshot.get("refreshError")
            or snapshot.get("isPartial")
            or snapshot.get("isStale")
            or snapshot.get("isFallback")
            or snapshot.get("isFromSnapshot")
            or freshness in {"partial", "stale", "fallback", "error"}
            or source in {"fallback", "mock"}
        )
        if has_usable_value:
            return "partial" if has_degraded_state else "success"
        if snapshot.get("isUnavailable") or source in {"unavailable", "fallback", "mock"} or freshness in {"unavailable", "fallback", "error"}:
            return "unavailable"
        if error_message or snapshot.get("refreshError"):
            return "failure"
        return "success"

    def _has_usable_market_values(self, snapshot: Mapping[str, Any]) -> bool:
        items = snapshot.get("items")
        if not isinstance(items, list):
            return False
        for item in items:
            if not isinstance(item, Mapping):
                continue
            if self._clean_number(item.get("value")) is not None or self._clean_number(item.get("price")) is not None:
                return True
        return False

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
        if cache_key == "crypto":
            snapshot["providerHealth"]["venueObservations"] = self._crypto_venue_observations(snapshot)
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
        if cache_key == "cn_indices":
            snapshot["providerHealth"]["observationProviders"] = self._cn_indices_observation_provider_health()
            observation_coverage = snapshot.pop("observationCoverage", None)
            if observation_coverage is None:
                observation_coverage = {"akshare": self._build_akshare_cn_index_observation_coverage()}
            if isinstance(observation_coverage, dict) and observation_coverage:
                snapshot["providerHealth"]["observationCoverage"] = observation_coverage
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

    def _crypto_venue_observations(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "coinbase": self._coinbase_venue_observation_sidecar(snapshot),
        }

    @staticmethod
    def _build_market_overview_observation_route_request(
        *,
        market: str,
        asset_type: str,
        use_case: str,
        capability: str,
        symbol: Optional[str] = None,
        product_id: Optional[str] = None,
    ) -> DataSourceRouteRequest:
        return DataSourceRouteRequest(
            market=market,
            asset_type=asset_type,
            use_case=use_case,
            capability=capability,
            freshness_need="delayed",
            scoring_allowed=False,
            symbol=symbol,
            product_id=product_id,
            allow_network=False,
            reproducibility_required=False,
        )

    @staticmethod
    def _market_overview_observation_authority_claim_reason_codes(raw_payload: Mapping[str, Any]) -> tuple[str, ...]:
        reason_codes: List[str] = []
        if raw_payload.get("observationOnly") is False or raw_payload.get("scoreContributionAllowed") is True:
            reason_codes.append("scoring_authority_claim")
        freshness = str(raw_payload.get("freshness") or "").strip().lower()
        if freshness in MARKET_OVERVIEW_OBSERVATION_AUTHORITY_FRESHNESS:
            reason_codes.append("live_authority_claim")
        trust_level = str(raw_payload.get("trustLevel") or "").strip().lower()
        if trust_level in MARKET_OVERVIEW_OBSERVATION_AUTHORITY_TRUST_LEVELS:
            reason_codes.append("trust_authority_claim")
        return tuple(dict.fromkeys(reason_codes))

    @staticmethod
    def _market_overview_observation_route_reason_codes(
        *,
        raw_payload: Mapping[str, Any],
        candidate,
        allowed_freshness: Optional[Sequence[str]] = None,
    ) -> tuple[str, ...]:
        reason_codes = list(MarketOverviewService._market_overview_observation_authority_claim_reason_codes(raw_payload))
        if raw_payload.get("providerId") not in {None, "", candidate.provider_id}:
            reason_codes.append("provider_id_mismatch")
        if raw_payload.get("source") not in {None, "", candidate.provider_id}:
            reason_codes.append("source_mismatch")
        source_type = str(raw_payload.get("sourceType") or "").strip().lower()
        if source_type and source_type != str(candidate.source_type).strip().lower():
            reason_codes.append("source_type_mismatch")
        source_tier = str(raw_payload.get("sourceTier") or "").strip().lower()
        if source_tier and source_tier != str(candidate.source_tier).strip().lower():
            reason_codes.append("source_tier_mismatch")
        trust_level = str(raw_payload.get("trustLevel") or "").strip().lower()
        if trust_level and trust_level != str(candidate.trust_level).strip().lower():
            reason_codes.append("trust_level_mismatch")
        if allowed_freshness is not None:
            freshness = str(raw_payload.get("freshness") or "").strip().lower()
            if freshness and freshness not in {item.lower() for item in allowed_freshness}:
                reason_codes.append("invalid_freshness")
        return tuple(dict.fromkeys(reason_codes))

    @staticmethod
    def _market_overview_observation_candidate(
        provider_id: str,
        capability: str,
    ):
        return (
            CapabilityResolver.route_candidate(provider_id, capability)
            or CapabilityResolver.route_candidate(provider_id, "quote")
            or CapabilityResolver.route_candidate(provider_id, "companyfacts")
        )

    def _coinbase_venue_observation_sidecar(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        route_request = self._build_market_overview_observation_route_request(
            market="crypto",
            asset_type="crypto",
            use_case="venue_observation",
            capability="venue_ticker",
            product_id="BTC-USD",
        )
        route_plan = DataSourceRouter.resolve(route_request)
        eligible_provider_ids = {candidate.provider_id for candidate in route_plan.observation_candidates}
        candidate = self._market_overview_observation_candidate("coinbase_public", "venue_ticker")
        if candidate is None or "coinbase_public" not in eligible_provider_ids:
            reason_codes = route_plan.reason_codes.get("coinbase_public") or ("provider_not_eligible_for_observation_route",)
            return self._rejected_coinbase_venue_observation_sidecar(
                snapshot=snapshot,
                reason=MARKET_OVERVIEW_OBSERVATION_ROUTE_REJECTED_REASON,
                reason_codes=reason_codes,
            )

        raw_records = [
            record
            for record in self._coinbase_venue_observation_records()
            if isinstance(record, dict)
        ]
        if not raw_records:
            return {
                "providerName": COINBASE_PUBLIC_PROVIDER_NAME,
                "providerId": COINBASE_PUBLIC_PROVIDER_ID,
                "source": COINBASE_PUBLIC_PROVIDER_ID,
                "venue": COINBASE_PUBLIC_VENUE,
                "sourceTier": COINBASE_PUBLIC_SOURCE_TIER,
                "trustLevel": COINBASE_PUBLIC_TRUST_LEVEL,
                "freshness": "unavailable",
                "observationOnly": True,
                "scoreContributionAllowed": False,
                "productId": None,
                "symbol": None,
                "baseCurrency": None,
                "quoteCurrency": None,
                "asOf": None,
                "updatedAt": snapshot.get("updatedAt") or snapshot.get("last_update") or _now_iso(),
                "degradationReason": "observation_unavailable",
                "sourceRef": f"{COINBASE_PUBLIC_PROVIDER_ID}:fixture_only",
                "records": [],
            }

        accepted_records = []
        rejected_reason_codes: List[str] = []
        for record in raw_records:
            normalized_record = self._normalize_coinbase_venue_observation_record(record)
            validation_payload = {
                **normalized_record,
                **record,
            }
            record_reason_codes = self._market_overview_observation_route_reason_codes(
                raw_payload=validation_payload,
                candidate=candidate,
                allowed_freshness=MARKET_OVERVIEW_OBSERVATION_ALLOWED_FRESHNESS,
            )
            if record_reason_codes:
                rejected_reason_codes.extend(record_reason_codes)
                continue
            accepted_records.append(normalized_record)

        if not accepted_records:
            return self._rejected_coinbase_venue_observation_sidecar(
                snapshot=snapshot,
                reason=MARKET_OVERVIEW_OBSERVATION_AUTHORITY_REJECTED_REASON if rejected_reason_codes else MARKET_OVERVIEW_OBSERVATION_INVALID_METADATA_REASON,
                reason_codes=tuple(dict.fromkeys(rejected_reason_codes)) or ("observation_metadata_missing",),
                raw_payload=raw_records[0],
            )

        primary = accepted_records[0]
        as_of = primary.get("asOf") or primary.get("updatedAt")
        freshness = str(primary.get("freshness") or "").strip().lower()
        if not freshness:
            freshness = get_freshness_status(
                as_of or primary.get("updatedAt"),
                "crypto",
                COINBASE_PUBLIC_PROVIDER_ID,
                False,
                source_type=COINBASE_PUBLIC_SOURCE_TIER,
            )["freshness"]
        if freshness not in MARKET_OVERVIEW_OBSERVATION_ALLOWED_FRESHNESS:
            return self._rejected_coinbase_venue_observation_sidecar(
                snapshot=snapshot,
                reason=MARKET_OVERVIEW_OBSERVATION_AUTHORITY_REJECTED_REASON,
                reason_codes=("invalid_freshness", "live_authority_claim"),
                raw_payload=primary,
            )
        return {
            "providerName": primary.get("providerName") or COINBASE_PUBLIC_PROVIDER_NAME,
            "providerId": primary.get("providerId") or COINBASE_PUBLIC_PROVIDER_ID,
            "source": primary.get("source") or COINBASE_PUBLIC_PROVIDER_ID,
            "venue": primary.get("venue") or COINBASE_PUBLIC_VENUE,
            "sourceTier": primary.get("sourceTier") or COINBASE_PUBLIC_SOURCE_TIER,
            "trustLevel": primary.get("trustLevel") or COINBASE_PUBLIC_TRUST_LEVEL,
            "freshness": freshness,
            "observationOnly": True,
            "scoreContributionAllowed": False,
            "productId": primary.get("productId"),
            "symbol": primary.get("symbol"),
            "baseCurrency": primary.get("baseCurrency"),
            "quoteCurrency": primary.get("quoteCurrency"),
            "asOf": as_of,
            "updatedAt": primary.get("updatedAt") or as_of or snapshot.get("updatedAt") or snapshot.get("last_update") or _now_iso(),
            "degradationReason": primary.get("degradationReason"),
            "sourceRef": primary.get("sourceRef") or f"{COINBASE_PUBLIC_PROVIDER_ID}:fixture_only",
            "records": accepted_records,
        }

    def _rejected_coinbase_venue_observation_sidecar(
        self,
        *,
        snapshot: Dict[str, Any],
        reason: str,
        reason_codes: Sequence[str],
        raw_payload: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        raw = dict(raw_payload or {})
        return {
            "providerName": COINBASE_PUBLIC_PROVIDER_NAME,
            "providerId": COINBASE_PUBLIC_PROVIDER_ID,
            "source": COINBASE_PUBLIC_PROVIDER_ID,
            "venue": COINBASE_PUBLIC_VENUE,
            "sourceTier": COINBASE_PUBLIC_SOURCE_TIER,
            "trustLevel": COINBASE_PUBLIC_TRUST_LEVEL,
            "freshness": "unavailable",
            "observationOnly": True,
            "scoreContributionAllowed": False,
            "productId": raw.get("productId"),
            "symbol": raw.get("symbol"),
            "baseCurrency": raw.get("baseCurrency"),
            "quoteCurrency": raw.get("quoteCurrency"),
            "asOf": raw.get("asOf"),
            "updatedAt": raw.get("updatedAt") or snapshot.get("updatedAt") or snapshot.get("last_update") or _now_iso(),
            "degradationReason": reason,
            "routeRejectedReasonCodes": list(dict.fromkeys(reason_codes)),
            "sourceRef": raw.get("sourceRef") or f"{COINBASE_PUBLIC_PROVIDER_ID}:fixture_only",
            "records": [],
        }

    def _normalize_coinbase_venue_observation_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return {
            **record,
            "providerName": record.get("providerName") or COINBASE_PUBLIC_PROVIDER_NAME,
            "providerId": record.get("providerId") or COINBASE_PUBLIC_PROVIDER_ID,
            "source": record.get("source") or COINBASE_PUBLIC_PROVIDER_ID,
            "venue": record.get("venue") or COINBASE_PUBLIC_VENUE,
            "sourceTier": record.get("sourceTier") or COINBASE_PUBLIC_SOURCE_TIER,
            "trustLevel": record.get("trustLevel") or COINBASE_PUBLIC_TRUST_LEVEL,
            "observationOnly": True,
            "scoreContributionAllowed": False,
        }

    def _coinbase_venue_observation_records(self) -> List[Dict[str, Any]]:
        # Coinbase stays fixture-only until explicitly wired; tests may inject parsed records here.
        return []

    def _cn_indices_observation_provider_health(self) -> List[Dict[str, Any]]:
        routed: List[Dict[str, Any]] = []
        for entry in CNProviderHealthService().get_snapshot(
            timeout_seconds=CN_INDICES_OBSERVATION_PROVIDER_TIMEOUT_SECONDS
        ):
            routed.append(self._guard_cn_indices_observation_provider_entry(entry.to_dict()))
        return routed

    def _guard_cn_indices_observation_provider_entry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        provider_id = str(payload.get("providerId") or "").strip().lower()
        provider_route = {
            "pytdx": ("cn_realtime_quote", "usable_with_caution", "unofficial_public_api"),
            "akshare": ("cn_market_stats", "weak", "unofficial_public_api"),
            "baostock": ("cn_history_daily", "usable_with_caution", "third_party_free_api"),
        }.get(provider_id)
        if provider_route is None:
            return payload

        capability, expected_trust_level, expected_source_tier = provider_route
        route_request = self._build_market_overview_observation_route_request(
            market="CN",
            asset_type="equity",
            use_case="market_observation",
            capability=capability,
            symbol="000001.SZ",
        )
        route_plan = DataSourceRouter.resolve(route_request)
        eligible_provider_ids = {candidate.provider_id for candidate in route_plan.observation_candidates}
        candidate = self._market_overview_observation_candidate(provider_id, capability)
        provider_reason_codes = route_plan.reason_codes.get(provider_id) or ("provider_not_eligible_for_observation_route",)
        if candidate is None or provider_id not in eligible_provider_ids:
            return self._rejected_cn_indices_observation_provider_entry(
                payload,
                candidate=candidate,
                route_plan=route_plan,
                reason=MARKET_OVERVIEW_OBSERVATION_ROUTE_REJECTED_REASON,
                reason_codes=provider_reason_codes,
            )

        reason_codes = list(self._market_overview_observation_authority_claim_reason_codes(payload))
        if str(payload.get("sourceType") or "").strip().lower() != "public_proxy":
            reason_codes.append("source_type_mismatch")
        if str(payload.get("sourceTier") or "").strip().lower() != expected_source_tier:
            reason_codes.append("source_tier_mismatch")
        if str(payload.get("trustLevel") or "").strip().lower() != expected_trust_level:
            reason_codes.append("trust_level_mismatch")
        if provider_id == "baostock":
            freshness_expectation = str(payload.get("freshnessExpectation") or "").strip().lower()
            if freshness_expectation not in {"t_plus_1_or_delayed", "t+1_or_delayed"}:
                reason_codes.append("invalid_freshness_expectation")
        if reason_codes:
            return self._rejected_cn_indices_observation_provider_entry(
                payload,
                candidate=candidate,
                route_plan=route_plan,
                reason=MARKET_OVERVIEW_OBSERVATION_AUTHORITY_REJECTED_REASON,
                reason_codes=tuple(dict.fromkeys(reason_codes)),
            )

        normalized = dict(payload)
        normalized["sourceType"] = "public_proxy"
        normalized["sourceTier"] = expected_source_tier
        normalized["trustLevel"] = expected_trust_level
        normalized["observationOnly"] = True
        normalized["scoreContributionAllowed"] = False
        return normalized

    def _rejected_cn_indices_observation_provider_entry(
        self,
        payload: Dict[str, Any],
        *,
        candidate,
        route_plan,
        reason: str,
        reason_codes: Sequence[str],
    ) -> Dict[str, Any]:
        normalized = dict(payload)
        if candidate is not None:
            normalized["sourceType"] = candidate.source_type
            normalized["sourceTier"] = candidate.source_tier
            normalized["trustLevel"] = candidate.trust_level
            normalized["freshnessExpectation"] = candidate.freshness_expectation
        normalized["observationOnly"] = True
        normalized["scoreContributionAllowed"] = False
        normalized["providerAvailable"] = False
        normalized["healthStatus"] = "rejected"
        normalized["cacheRequired"] = bool(route_plan.cache_required)
        normalized["backgroundRefreshRecommended"] = bool(route_plan.background_refresh_required)
        normalized["degradationReason"] = reason
        normalized["missingProviderReason"] = (
            f"{reason}:{'|'.join(dict.fromkeys(reason_codes))}"
            if reason_codes
            else reason
        )
        return normalized

    def _normalize_akshare_cn_index_observation_records(
        self,
        rows: Any,
        *,
        attempted_at: str,
    ) -> List[Dict[str, Any]]:
        freshness = self._akshare_cn_index_observation_freshness(attempted_at)
        normalized: List[Dict[str, Any]] = []
        seen_symbols: set[str] = set()
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            provider_symbol = str(row.get("code") or "").strip().lower()
            canonical_symbol = self.AKSHARE_CN_INDEX_SYMBOLS.get(provider_symbol)
            if not canonical_symbol or canonical_symbol in seen_symbols:
                continue
            seen_symbols.add(canonical_symbol)
            normalized.append({
                "providerName": "akshare",
                "providerSymbol": provider_symbol,
                "canonicalSymbol": canonical_symbol,
                "sourceType": "public_proxy",
                "sourceTier": "unofficial_public_api",
                "trustLevel": "weak",
                "observationOnly": True,
                "scoreContributionAllowed": False,
                "freshness": freshness,
                "asOf": attempted_at,
                "updatedAt": attempted_at,
                "providerTimestampAvailable": False,
            })
        return normalized

    def _akshare_cn_index_observation_freshness(self, attempted_at: str) -> str:
        freshness = get_freshness_status(
            attempted_at,
            "equity_index",
            "akshare",
            False,
            source_type="public_proxy",
        )["freshness"]
        if freshness in {"live", "fresh"}:
            return "delayed"
        if freshness == "cached":
            parsed_attempted_at = _parse_market_time(attempted_at)
            if parsed_attempted_at and parsed_attempted_at.date() == datetime.now(CN_TZ).date():
                return "delayed"
            return "stale"
        if freshness in {"delayed", "stale", "unavailable"}:
            return freshness
        return "unavailable"

    def _fetch_akshare_cn_index_observation_rows(self, timeout_seconds: float) -> Any:
        from data_provider.akshare_fetcher import AkshareFetcher

        fetcher = AkshareFetcher()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(fetcher.get_main_indices, "cn")
            try:
                return future.result(timeout=max(0.1, float(timeout_seconds)))
            except FutureTimeoutError as exc:
                future.cancel()
                raise TimeoutError("akshare cn index observation timed out") from exc

    def _build_akshare_cn_index_observation_coverage(self) -> Dict[str, Any]:
        attempted_at = _now_iso()
        expected_symbols = list(self.AKSHARE_CN_INDEX_EXPECTED_SYMBOLS)
        base = {
            "providerName": "akshare",
            "sourceType": "public_proxy",
            "sourceTier": "unofficial_public_api",
            "trustLevel": "weak",
            "observationOnly": True,
            "scoreContributionAllowed": False,
            "asOf": attempted_at,
            "updatedAt": attempted_at,
            "attemptedAt": attempted_at,
            "coverageCount": 0,
            "matchedCanonicalSymbols": [],
            "missingExpectedSymbols": expected_symbols,
            "partialCoverageReason": None,
            "degradationReason": None,
            "providerTimestampAvailable": False,
        }
        try:
            rows = self._fetch_akshare_cn_index_observation_rows(
                CN_INDICES_AKSHARE_OBSERVATION_TIMEOUT_SECONDS
            )
        except (ImportError, ModuleNotFoundError):
            return {
                **base,
                "freshness": "unavailable",
                "degradationReason": "akshare_not_installed",
            }
        except TimeoutError:
            return {
                **base,
                "freshness": "unavailable",
                "degradationReason": "akshare_fetch_timeout",
            }
        except Exception:
            return {
                **base,
                "freshness": "unavailable",
                "degradationReason": "akshare_fetch_failed",
            }

        records = self._normalize_akshare_cn_index_observation_records(rows, attempted_at=attempted_at)
        if not records:
            return {
                **base,
                "freshness": "unavailable",
                "degradationReason": "empty_response",
            }

        matched_symbols = [record["canonicalSymbol"] for record in records]
        missing_symbols = [symbol for symbol in self.AKSHARE_CN_INDEX_EXPECTED_SYMBOLS if symbol not in matched_symbols]
        degradation_reason = "partial_coverage" if missing_symbols else None
        coverage = {
            **base,
            "freshness": records[0]["freshness"],
            "coverageCount": len(matched_symbols),
            "matchedCanonicalSymbols": matched_symbols,
            "missingExpectedSymbols": missing_symbols,
            "partialCoverageReason": degradation_reason,
            "degradationReason": degradation_reason,
        }
        return self._guard_akshare_cn_index_observation_coverage(coverage)

    def _guard_akshare_cn_index_observation_coverage(self, coverage: Dict[str, Any]) -> Dict[str, Any]:
        route_request = self._build_market_overview_observation_route_request(
            market="CN",
            asset_type="equity",
            use_case="market_observation",
            capability="cn_market_stats",
            symbol="000001.SZ",
        )
        route_plan = DataSourceRouter.resolve(route_request)
        eligible_provider_ids = {candidate.provider_id for candidate in route_plan.observation_candidates}
        candidate = self._market_overview_observation_candidate("akshare", "cn_market_stats")
        if candidate is None or "akshare" not in eligible_provider_ids:
            reason_codes = route_plan.reason_codes.get("akshare") or ("provider_not_eligible_for_observation_route",)
            return self._rejected_akshare_cn_index_observation_coverage(
                coverage,
                reason=MARKET_OVERVIEW_OBSERVATION_ROUTE_REJECTED_REASON,
                reason_codes=reason_codes,
            )

        reason_codes = self._market_overview_observation_route_reason_codes(
            raw_payload=coverage,
            candidate=candidate,
            allowed_freshness=MARKET_OVERVIEW_OBSERVATION_ALLOWED_FRESHNESS,
        )
        if reason_codes:
            return self._rejected_akshare_cn_index_observation_coverage(
                coverage,
                reason=MARKET_OVERVIEW_OBSERVATION_AUTHORITY_REJECTED_REASON,
                reason_codes=reason_codes,
            )
        normalized = dict(coverage)
        normalized["sourceType"] = "public_proxy"
        normalized["sourceTier"] = "unofficial_public_api"
        normalized["trustLevel"] = "weak"
        normalized["observationOnly"] = True
        normalized["scoreContributionAllowed"] = False
        return normalized

    def _rejected_akshare_cn_index_observation_coverage(
        self,
        coverage: Dict[str, Any],
        *,
        reason: str,
        reason_codes: Sequence[str],
    ) -> Dict[str, Any]:
        attempted_at = str(coverage.get("attemptedAt") or coverage.get("updatedAt") or coverage.get("asOf") or _now_iso())
        return {
            "providerName": "akshare",
            "sourceType": "public_proxy",
            "sourceTier": "unofficial_public_api",
            "trustLevel": "weak",
            "observationOnly": True,
            "scoreContributionAllowed": False,
            "asOf": coverage.get("asOf") or attempted_at,
            "updatedAt": coverage.get("updatedAt") or attempted_at,
            "attemptedAt": attempted_at,
            "freshness": "unavailable",
            "coverageCount": 0,
            "matchedCanonicalSymbols": [],
            "missingExpectedSymbols": list(self.AKSHARE_CN_INDEX_EXPECTED_SYMBOLS),
            "partialCoverageReason": reason,
            "degradationReason": reason,
            "providerTimestampAvailable": False,
            "routeRejectedReasonCodes": list(dict.fromkeys(reason_codes)),
        }

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
                return self._mark_local_fallback_payload(cached)
            persistent = self._load_persistent_snapshot(cache_key)
            if persistent:
                return persistent
            return fallback_factory()

        payload = self._market_cache.get_or_refresh(
            cache_key,
            ttl_seconds,
            store_success,
            fallback_factory=fallback,
            allow_stale=True,
            background_refresh=True,
            cold_start_timeout_seconds=self.MARKET_COLD_START_TIMEOUT_SECONDS,
        )
        return self._align_official_macro_runtime_payload(cache_key, payload)

    def _align_official_macro_runtime_payload(self, cache_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if cache_key not in {"macro", "rates", "volatility"}:
            return payload
        if self._is_fallback_only_market_snapshot(payload):
            return payload
        if not isinstance(payload.get("items"), list):
            return payload
        if self._official_macro_payload_has_required_authority(cache_key, payload):
            return payload

        official_points = self._official_macro_points(
            include_policy_and_inflation=cache_key == "macro",
            include_credit_stress=cache_key == "macro",
            include_fed_liquidity=cache_key == "macro",
            include_usd_pressure=cache_key == "macro",
        )
        if cache_key == "volatility":
            return self._align_official_macro_volatility_payload(payload, official_points)
        if cache_key == "rates":
            return self._align_official_macro_rates_payload(payload, official_points)
        return self._align_official_macro_macro_payload(payload, official_points)

    def _align_official_macro_volatility_payload(
        self,
        payload: Dict[str, Any],
        official_points: Dict[str, List[MacroObservation]],
    ) -> Dict[str, Any]:
        official_vix, official_vix_failure = self._official_macro_overlay_item(
            "VIX",
            "VIX",
            official_points.get("VIXCLS", []),
            series_id="VIXCLS",
            unit="pts",
            change_scale=1.0,
        )
        if not official_vix and not official_vix_failure:
            return payload

        items: List[Any] = []
        replaced_vix = False
        for raw in payload.get("items", []):
            if not isinstance(raw, dict) or str(raw.get("symbol") or "") != "VIX":
                items.append(raw)
                continue
            replaced_vix = True
            items.append(
                official_vix
                if official_vix
                else self._with_official_overlay_failure(raw, official_vix_failure, series_id="VIXCLS")
            )
        if official_vix and not replaced_vix:
            items.insert(0, official_vix)
        aligned = {**payload, "items": items}
        if official_vix:
            self._mark_official_macro_runtime_payload(aligned)
        return aligned

    def _align_official_macro_rates_payload(
        self,
        payload: Dict[str, Any],
        official_points: Dict[str, List[MacroObservation]],
    ) -> Dict[str, Any]:
        item_map = {
            str(item.get("symbol") or ""): item
            for item in payload.get("items", [])
            if isinstance(item, dict)
        }
        official_available = False
        for symbol in ("US2Y", "US10Y", "US30Y"):
            series_id, label, unit, market = self.OFFICIAL_RATE_SERIES[symbol]
            official_item, official_failure = self._official_macro_overlay_item(
                symbol,
                label,
                official_points.get(series_id, []),
                series_id=series_id,
                unit=unit,
                market=market,
            )
            if official_item:
                item_map[symbol] = official_item
                official_available = True
            elif symbol in item_map and official_failure:
                item_map[symbol] = self._with_official_overlay_failure(
                    item_map[symbol],
                    official_failure,
                    series_id=series_id,
                )

        official_sofr, official_sofr_failure = self._official_macro_overlay_item(
            "SOFR",
            "SOFR",
            official_points.get("SOFR", []),
            series_id="SOFR",
            unit="%",
            market="US",
        )
        if official_sofr:
            item_map["SOFR"] = official_sofr
            official_available = True
        elif "SOFR" in item_map and official_sofr_failure:
            item_map["SOFR"] = self._with_official_overlay_failure(
                item_map["SOFR"],
                official_sofr_failure,
                series_id="SOFR",
            )

        for symbol, (series_id, label, unit, market) in self.OFFICIAL_RATE_CONTEXT_SERIES.items():
            official_item, official_failure = self._official_macro_overlay_item(
                symbol,
                label,
                official_points.get(series_id, []),
                series_id=series_id,
                unit=unit,
                market=market,
                value_scale=100.0,
                change_scale=100.0,
            )
            if official_item:
                item_map[symbol] = official_item
                official_available = True
            elif symbol in item_map and official_failure:
                item_map[symbol] = self._with_official_overlay_failure(
                    item_map[symbol],
                    official_failure,
                    series_id=series_id,
                )

        aligned = {
            **payload,
            "items": self._ordered_runtime_items(
                payload,
                item_map,
                ("US2Y", "US10Y", "US30Y", "US10Y2Y", "US10Y3M", "SOFR"),
            ),
        }
        if official_available:
            self._mark_official_macro_runtime_payload(aligned)
        return aligned

    def _align_official_macro_macro_payload(
        self,
        payload: Dict[str, Any],
        official_points: Dict[str, List[MacroObservation]],
    ) -> Dict[str, Any]:
        item_map = {
            str(item.get("symbol") or ""): item
            for item in payload.get("items", [])
            if isinstance(item, dict)
        }
        official_available = False
        for panel_symbol, (series_id, label, unit, market) in self.OFFICIAL_RATE_SERIES.items():
            official_item, official_failure = self._official_macro_overlay_item(
                panel_symbol,
                label,
                official_points.get(series_id, []),
                series_id=series_id,
                unit=unit,
                market=market,
            )
            if official_item:
                item_map[panel_symbol] = official_item
                official_available = True
            elif panel_symbol in item_map and official_failure:
                item_map[panel_symbol] = self._with_official_overlay_failure(
                    item_map[panel_symbol],
                    official_failure,
                    series_id=series_id,
                )

        for symbol, label, series_id, unit, kwargs in (
            ("SOFR", "SOFR", "SOFR", "%", {"market": "US"}),
            ("VIX", "VIX", "VIXCLS", "pts", {"change_scale": 1.0}),
            ("FEDFUNDS", "Fed Funds", "DFF", "%", {"market": "US"}),
            ("CREDIT", "Credit spreads", "BAMLH0A0HYM2", "bps", {"value_scale": 100.0, "change_scale": 100.0}),
        ):
            official_item, official_failure = self._official_macro_overlay_item(
                symbol,
                label,
                official_points.get(series_id, []),
                series_id=series_id,
                unit=unit,
                **kwargs,
            )
            if official_item:
                if symbol == "CREDIT":
                    official_item["observationOnly"] = True
                    official_item["includedInScore"] = False
                item_map[symbol] = official_item
                official_available = True
            elif symbol in item_map and official_failure:
                item_map[symbol] = self._with_official_overlay_failure(
                    item_map[symbol],
                    official_failure,
                    series_id=series_id,
                )

        for symbol, (series_id, label, unit, market) in self.OFFICIAL_RATE_CONTEXT_SERIES.items():
            official_item, official_failure = self._official_macro_overlay_item(
                symbol,
                label,
                official_points.get(series_id, []),
                series_id=series_id,
                unit=unit,
                market=market,
                value_scale=100.0,
                change_scale=100.0,
            )
            if official_item:
                item_map[symbol] = official_item
                official_available = True
            elif symbol in item_map and official_failure:
                item_map[symbol] = self._with_official_overlay_failure(
                    item_map[symbol],
                    official_failure,
                    series_id=series_id,
                )

        fed_items = self._official_fed_liquidity_items(official_points)
        if fed_items:
            item_map.update(fed_items)
            official_available = official_available or any(
                not bool(item.get("isUnavailable")) for item in fed_items.values()
            )
        usd_pressure_items = self._official_usd_pressure_items(official_points)
        if usd_pressure_items:
            item_map.update(usd_pressure_items)
            official_available = official_available or any(
                not bool(item.get("isUnavailable")) for item in usd_pressure_items.values()
            )

        ordered_symbols = (
            "US2Y",
            "US10Y",
            "US30Y",
            "SOFR",
            "US10Y2Y",
            "US10Y3M",
            "VIX",
            "USD_TWI",
            "DXY",
            "GOLD",
            "OIL",
            "FEDFUNDS",
            "CPI",
            "PPI",
            "CREDIT",
            "FED_ASSETS",
            "FED_RRP",
            "TGA",
            "RESERVES",
        )
        aligned = {**payload, "items": self._ordered_runtime_items(payload, item_map, ordered_symbols)}
        if official_available:
            self._mark_official_macro_runtime_payload(aligned)
        return aligned

    def _official_fed_liquidity_items(
        self,
        official_points: Dict[str, List[MacroObservation]],
    ) -> Dict[str, Dict[str, Any]]:
        items: Dict[str, Dict[str, Any]] = {}
        failures: Dict[str, str] = {}

        for symbol, (series_id, label, unit, market) in self.FED_LIQUIDITY_SERIES.items():
            official_item, official_failure = self._official_macro_overlay_item(
                symbol,
                label,
                official_points.get(series_id, []),
                series_id=series_id,
                unit=unit,
                market=market,
                change_scale=1.0,
            )
            if official_item:
                freshness_evidence = get_freshness_status(
                    official_item.get("asOf"),
                    "macro_rate",
                    str(official_item.get("source") or ""),
                    False,
                    source_type=str(official_item.get("sourceType") or ""),
                    series_id=series_id,
                    official_observation_date=official_item.get("officialObservationDate") or official_item.get("officialAsOf"),
                )
                items[symbol] = {
                    **official_item,
                    "fedLiquidityComponent": True,
                    "requiredProviderClass": "official_public.fed_liquidity",
                    "providerAttempted": True,
                    "providerClass": "official_daily",
                    "officialOverlayAttempted": True,
                    "officialOverlayAvailable": True,
                    "officialOverlayFailureReason": None,
                    "activationHint": "official_daily_overlay_active",
                    "sourceTier": "official_public",
                    "trustLevel": "reliable",
                    "freshness": freshness_evidence.get("freshness") or "unavailable",
                    "sourceFreshnessEvidence": freshness_evidence,
                }
                continue

            reason = (
                official_failure
                or self._official_macro_overlay_diagnostics.get(series_id)
                or "missing_series"
            )
            failures[symbol] = reason
            unavailable = self._official_macro_unavailable_item(
                symbol,
                label,
                series_id,
                unit=unit,
                market=market,
            )
            unavailable.update(
                {
                    "fedLiquidityComponent": True,
                    "requiredProviderClass": "official_public.fed_liquidity",
                    "providerAttempted": True,
                    "providerClass": "official_daily",
                    "officialOverlayAttempted": True,
                    "officialOverlayAvailable": False,
                    "officialOverlayFailureReason": reason,
                    "activationHint": "official_fed_liquidity_missing_fail_closed",
                    "officialSeriesId": series_id,
                    "sourceTier": "official_public",
                    "trustLevel": "unavailable",
                    "freshness": "unavailable",
                    "sourceAuthorityAllowed": False,
                    "scoreContributionAllowed": False,
                    "sourceAuthorityReason": reason,
                    "routeRejectedReasonCodes": [reason],
                }
            )
            items[symbol] = unavailable

        if not items:
            return {}

        cache_bundle = build_official_fed_liquidity_cache_bundle(list(items.values()))
        group_ready = bool(cache_bundle.get("scoreContributionAllowed"))
        reason_codes = [str(code) for code in cache_bundle.get("reasonCodes") or []]
        if not reason_codes and failures:
            reason_codes = sorted(set(failures.values()))
        for symbol, item in items.items():
            item["cacheBundleDiagnostics"] = copy.deepcopy(cache_bundle)
            item["externalProviderCalls"] = False
            item["cacheOnly"] = True
            if group_ready:
                item.update(
                    {
                        "sourceAuthorityAllowed": True,
                        "scoreContributionAllowed": True,
                        "sourceAuthorityReason": None,
                        "routeRejectedReasonCodes": [],
                    }
                )
                continue
            if not item.get("isUnavailable"):
                authority_reason = str(cache_bundle.get("degradationReason") or "fed_liquidity_partial_coverage")
                if authority_reason == "fed_liquidity_required_series_missing_or_stale":
                    authority_reason = "fed_liquidity_partial_coverage"
                item.update(
                    {
                        "sourceAuthorityAllowed": False,
                        "scoreContributionAllowed": False,
                        "sourceAuthorityReason": authority_reason,
                        "routeRejectedReasonCodes": reason_codes or ["fed_liquidity_partial_coverage"],
                    }
                )
        return items

    def _official_usd_pressure_items(
        self,
        official_points: Dict[str, List[MacroObservation]],
    ) -> Dict[str, Dict[str, Any]]:
        items: Dict[str, Dict[str, Any]] = {}

        for symbol, (series_id, label, unit, market) in self.USD_PRESSURE_SERIES.items():
            official_item, official_failure = self._official_macro_overlay_item(
                symbol,
                label,
                official_points.get(series_id, []),
                series_id=series_id,
                unit=unit,
                market=market,
                change_scale=1.0,
            )
            if official_item:
                freshness_evidence = get_freshness_status(
                    official_item.get("asOf"),
                    "macro_rate",
                    str(official_item.get("source") or ""),
                    False,
                    source_type=str(official_item.get("sourceType") or ""),
                    series_id=series_id,
                    official_observation_date=official_item.get("officialObservationDate") or official_item.get("officialAsOf"),
                )
                items[symbol] = {
                    **official_item,
                    "usdPressureComponent": True,
                    "requiredProviderClass": "official_public.usd_pressure",
                    "providerAttempted": True,
                    "providerClass": "official_daily",
                    "officialOverlayAttempted": True,
                    "officialOverlayAvailable": True,
                    "officialOverlayFailureReason": None,
                    "activationHint": "official_usd_pressure_overlay_active",
                    "sourceTier": "official_public",
                    "trustLevel": "reliable",
                    "freshness": freshness_evidence.get("freshness") or "unavailable",
                    "sourceFreshnessEvidence": freshness_evidence,
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                    "sourceAuthorityReason": None,
                    "routeRejectedReasonCodes": [],
                }
                continue

            reason = (
                official_failure
                or self._official_macro_overlay_diagnostics.get(series_id)
                or "usd_pressure_missing_series"
            )
            if reason == "stale_official_row":
                reason = "official_usd_pressure_stale"
            unavailable = self._official_macro_unavailable_item(
                symbol,
                label,
                series_id,
                unit=unit,
                market=market,
            )
            unavailable.update(
                {
                    "usdPressureComponent": True,
                    "requiredProviderClass": "official_public.usd_pressure",
                    "providerAttempted": True,
                    "providerClass": "official_daily",
                    "officialOverlayAttempted": True,
                    "officialOverlayAvailable": False,
                    "officialOverlayFailureReason": reason,
                    "activationHint": "official_usd_pressure_missing_fail_closed",
                    "officialSeriesId": series_id,
                    "sourceTier": "official_public",
                    "trustLevel": "unavailable",
                    "freshness": "unavailable",
                    "sourceAuthorityAllowed": False,
                    "scoreContributionAllowed": False,
                    "sourceAuthorityReason": reason,
                    "routeRejectedReasonCodes": [reason],
                }
            )
            items[symbol] = unavailable

        if items:
            cache_bundle = build_official_usd_pressure_cache_bundle(list(items.values()))
            ready = bool(cache_bundle.get("scoreGradeEvidenceAllowed"))
            reason_codes = [str(code) for code in cache_bundle.get("reasonCodes") or []]
            for item in items.values():
                item["cacheBundleDiagnostics"] = copy.deepcopy(cache_bundle)
                item["externalProviderCalls"] = False
                item["cacheOnly"] = True
                item["readinessEligible"] = ready
                item["scoreGradeEvidenceAllowed"] = ready
                item["cacheSafeOfficialEvidenceAllowed"] = ready
                if ready:
                    item["sourceAuthorityAllowed"] = True
                    item["scoreContributionAllowed"] = True
                    item["sourceAuthorityReason"] = None
                    item["routeRejectedReasonCodes"] = []
                    continue
                reason = str(item.get("sourceAuthorityReason") or cache_bundle.get("degradationReason") or "usd_pressure_readiness_not_eligible")
                item["sourceAuthorityAllowed"] = False
                item["scoreContributionAllowed"] = False
                item["sourceAuthorityReason"] = reason
                item["routeRejectedReasonCodes"] = list(dict.fromkeys([*list(item.get("routeRejectedReasonCodes") or []), *reason_codes]))

        return items

    @staticmethod
    def _ordered_runtime_items(
        payload: Dict[str, Any],
        item_map: Dict[str, Dict[str, Any]],
        official_symbols: tuple[str, ...],
    ) -> List[Dict[str, Any]]:
        ordered: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for raw in payload.get("items", []):
            if not isinstance(raw, dict):
                continue
            symbol = str(raw.get("symbol") or "")
            item = item_map.get(symbol)
            if item is None:
                continue
            ordered.append(item)
            seen.add(symbol)
        for symbol in official_symbols:
            if symbol in item_map and symbol not in seen:
                ordered.append(item_map[symbol])
                seen.add(symbol)
        return ordered

    def _mark_official_macro_runtime_payload(self, payload: Dict[str, Any]) -> None:
        payload["source"] = "mixed"
        payload["sourceLabel"] = self._source_label("mixed")
        payload["isFallback"] = False
        payload["fallbackUsed"] = any(
            bool(item.get("isFallback") or item.get("isUnavailable"))
            for item in payload.get("items", [])
            if isinstance(item, dict)
        )
        if payload["fallbackUsed"]:
            payload["warning"] = payload.get("warning") or OFFICIAL_MACRO_UNAVAILABLE_WARNING

    def _official_macro_payload_has_required_authority(self, cache_key: str, payload: Dict[str, Any]) -> bool:
        required_groups = {
            "volatility": ({"VIX", "VIXCLS"},),
            "rates": ({"US2Y"}, {"US10Y"}, {"US30Y"}, {"SOFR"}),
            "macro": (
                {"VIX", "VIXCLS"},
                {"US2Y"},
                {"US10Y"},
                {"US30Y"},
                {"SOFR"},
                {"USD_TWI"},
                {"FED_ASSETS"},
                {"FED_RRP"},
                {"TGA"},
                {"RESERVES"},
            ),
        }.get(cache_key)
        items = payload.get("items")
        if not required_groups or not isinstance(items, list):
            return False
        return all(
            any(
                isinstance(item, dict)
                and str(item.get("symbol") or "") in symbol_group
                and self._official_macro_runtime_item_has_authority(item, payload)
                for item in items
            )
            for symbol_group in required_groups
        )

    @staticmethod
    def _official_macro_runtime_item_has_authority(item: Dict[str, Any], payload: Dict[str, Any]) -> bool:
        source_type = str(item.get("sourceType") or payload.get("sourceType") or "").lower()
        source = str(item.get("source") or payload.get("source") or "").lower()
        freshness = str(item.get("freshness") or payload.get("freshness") or "").lower()
        if source_type != "official_public" or source not in {"fred", "treasury"}:
            return False
        if freshness not in {"live", "cached", "delayed"}:
            return False
        if bool(item.get("isFallback") or item.get("fallbackUsed") or item.get("isUnavailable") or item.get("isPartial")):
            return False
        if item.get("sourceAuthorityAllowed") is False:
            return False
        if item.get("scoreContributionAllowed") is False:
            return False
        return _has_valid_market_value(item)

    @classmethod
    def _local_fallback_last_successful_at(cls, payload: Dict[str, Any]) -> Any:
        for key in ("asOf", "updatedAt", "last_update", "last_refresh_at", "timestamp", "lastSuccessfulAt"):
            value = payload.get(key)
            if value:
                return value
        items = payload.get("items")
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                for key in ("asOf", "updatedAt", "last_update", "last_refresh_at", "timestamp", "lastSuccessfulAt"):
                    value = item.get(key)
                    if value:
                        return value
        return None

    @classmethod
    def _mark_local_fallback_payload(cls, cached: Dict[str, Any]) -> Dict[str, Any]:
        payload = copy.deepcopy(cached)
        last_successful_at = cls._local_fallback_last_successful_at(payload)
        payload["fallbackUsed"] = True
        payload["isStale"] = True
        payload["freshness"] = "stale"
        if last_successful_at:
            payload["lastSuccessfulAt"] = last_successful_at
        freshness_evidence = payload.get("sourceFreshnessEvidence")
        if not isinstance(freshness_evidence, dict):
            freshness_evidence = {}
        payload["sourceFreshnessEvidence"] = {
            **freshness_evidence,
            "freshness": "stale",
            "isStale": True,
            "isFallback": bool(freshness_evidence.get("isFallback")),
        }
        items = payload.get("items")
        if isinstance(items, list):
            payload["items"] = [
                cls._mark_local_fallback_item(item) if isinstance(item, dict) else item
                for item in items
            ]
        return payload

    @staticmethod
    def _mark_local_fallback_item(item: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            **item,
            "isStale": True,
            "freshness": "stale",
        }
        freshness_evidence = payload.get("sourceFreshnessEvidence")
        if isinstance(freshness_evidence, dict):
            payload["sourceFreshnessEvidence"] = {
                **freshness_evidence,
                "freshness": "stale",
                "isStale": True,
                "isFallback": bool(freshness_evidence.get("isFallback")),
            }
        return payload

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
        if has_error and items:
            return "partial"
        if real_items and fallback_items:
            return "partial"
        if payload.get("isFallback") or freshness in {"fallback", "mock"} or source in {"fallback", "mock"}:
            return "fallback"
        if payload.get("fallbackUsed") and real_items:
            return "partial"
        if payload.get("isPartial") or freshness == "partial":
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
        updated_at = payload.get("updatedAt") or payload.get("last_update") or payload.get("last_refresh_at")
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
        normalized_provider_snapshot = self._market_overview_provider_evidence_snapshot(payload, category, evidence)
        normalized_source_label = normalized_provider_snapshot.get("sourceLabel")
        if (
            str(normalized_provider_snapshot.get("source") or "").strip().lower() == "mixed"
            and str(normalized_source_label or "").strip().lower() == "mixed"
        ):
            normalized_source_label = self._source_label("mixed")
        evidence.update(
            {
                "contractVersion": MARKET_OVERVIEW_EVIDENCE_CONTRACT_VERSION,
                "diagnosticOnly": True,
                "cardKey": self._evidence_snapshot_card_key(payload, category),
                "endpoint": self._evidence_snapshot_endpoint(payload, category),
                "source": normalized_provider_snapshot.get("source") or evidence.get("source"),
                "sourceLabel": normalized_source_label or evidence.get("sourceLabel"),
                "asOf": normalized_provider_snapshot.get("asOf") or evidence.get("asOf"),
                "freshness": normalized_provider_snapshot.get("freshness") or evidence.get("freshness"),
                "isFallback": bool(normalized_provider_snapshot.get("isFallback")),
                "isStale": bool(normalized_provider_snapshot.get("isStale")),
                "isPartial": bool(normalized_provider_snapshot.get("isPartial")),
                "isSynthetic": bool(normalized_provider_snapshot.get("isSynthetic")),
                "isUnavailable": bool(normalized_provider_snapshot.get("isUnavailable")),
                "updatedAt": updated_at,
                "isFromSnapshot": bool(payload.get("isFromSnapshot")),
                "isRefreshing": bool(payload.get("isRefreshing")),
                "providerHealth": {
                    "status": self._evidence_snapshot_provider_status(payload),
                },
            }
        )
        evidence["coverage"] = round(float(evidence["coverage"]), 2) if isinstance(evidence.get("coverage"), (int, float)) else evidence.get("coverage")
        evidence["confidenceWeight"] = round(float(evidence["confidenceWeight"]), 2)
        score_gate_meta = self._evidence_snapshot_score_gate_meta(payload)
        if score_gate_meta.get("degradationReason") is None:
            score_gate_meta["degradationReason"] = evidence.get("degradationReason")
        if score_gate_meta.get("capReason") is None:
            score_gate_meta["capReason"] = evidence.get("capReason")
        evidence.update(score_gate_meta)
        if evidence.get("observationOnly") is None:
            evidence["observationOnly"] = bool(normalized_provider_snapshot.get("observationOnly"))
        evidence["scoreReliabilityAllowed"] = self._evidence_snapshot_score_reliability_allowed(payload, evidence)
        evidence["reasonFamilies"] = self._evidence_snapshot_reason_families(evidence, payload)
        return evidence

    def _market_overview_provider_evidence_snapshot(
        self,
        payload: Mapping[str, Any],
        category: str,
        evidence: Mapping[str, Any],
    ) -> Dict[str, Any]:
        inputs = self._market_overview_provider_evidence_inputs(payload, evidence)
        indicator = {
            "key": self._evidence_snapshot_card_key(payload, category),
            "label": self._evidence_snapshot_card_key(payload, category),
            "status": self._market_overview_provider_evidence_status(evidence),
            "freshness": evidence.get("freshness"),
            "asOf": evidence.get("asOf"),
            "source": evidence.get("source"),
            "sourceLabel": evidence.get("sourceLabel"),
            "fallbackInputCount": 1 if bool(evidence.get("isFallback")) else 0,
            "staleInputCount": 1 if bool(evidence.get("isStale")) else 0,
            "partialInputCount": 1 if bool(evidence.get("isPartial")) else 0,
            "syntheticInputCount": 1 if bool(evidence.get("isSynthetic")) else 0,
            "unavailableInputCount": 1 if bool(evidence.get("isUnavailable")) else 0,
            "inputs": inputs,
        }
        return build_provider_evidence_snapshot([indicator])

    def _market_overview_provider_evidence_inputs(
        self,
        payload: Mapping[str, Any],
        evidence: Mapping[str, Any],
    ) -> List[Dict[str, Any]]:
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        normalized_inputs = [
            self._market_overview_provider_evidence_input(item, evidence)
            for item in items
            if isinstance(item, Mapping)
        ]
        normalized_inputs = [
            item
            for item in normalized_inputs
            if any(
                item.get(key) not in (None, "", False)
                for key in ("source", "sourceLabel", "asOf", "freshness", "isFallback", "isStale", "isUnavailable")
            )
        ]
        if normalized_inputs:
            return normalized_inputs
        return [
            self._market_overview_provider_evidence_input(
                payload,
                evidence,
                default_confidence=evidence.get("confidenceWeight"),
                default_coverage=evidence.get("coverage"),
            )
        ]

    def _market_overview_provider_evidence_input(
        self,
        value: Mapping[str, Any],
        evidence: Mapping[str, Any],
        *,
        default_confidence: Any = None,
        default_coverage: Any = None,
    ) -> Dict[str, Any]:
        source = str(value.get("source") or evidence.get("source") or "").strip()
        source_label = value.get("sourceLabel") or evidence.get("sourceLabel") or self._source_label(source)
        freshness = str(value.get("freshness") or evidence.get("freshness") or "").strip().lower() or "unavailable"
        source_type = (
            str(value.get("sourceType") or "").strip()
            or str(evidence.get("sourceType") or "").strip()
            or _infer_source_type(source)
        )
        is_fallback = bool(
            value.get("isFallback")
            or value.get("fallbackUsed")
            or source.lower() in {"fallback", "mock"}
            or freshness in {"fallback", "mock"}
        )
        is_stale = bool(value.get("isStale") or freshness == "stale")
        is_partial = bool(value.get("isPartial") or freshness == "partial")
        is_unavailable = bool(
            value.get("isUnavailable")
            or source.lower() == "unavailable"
            or freshness in {"unavailable", "error"}
        )
        is_synthetic = bool(
            value.get("isSynthetic")
            or freshness in {"synthetic", "mock"}
            or source_type == "synthetic_fixture"
        )

        normalized_item = {
            **dict(value),
            "source": source,
            "freshness": freshness,
            "sourceType": source_type,
            "isFallback": is_fallback,
        }
        confidence_weight = self._clean_number(value.get("confidenceWeight"))
        if confidence_weight is None and default_confidence is not None:
            confidence_weight = self._clean_number(default_confidence)
        if confidence_weight is None:
            confidence_weight = self._base_evidence_item_confidence(normalized_item)

        coverage = self._clean_number(value.get("coverage"))
        if coverage is None and default_coverage is not None:
            coverage = self._clean_number(default_coverage)
        if coverage is None:
            coverage = 0.0 if (is_fallback or is_unavailable or not _has_valid_market_value(normalized_item)) else 1.0

        payload = {
            "source": source,
            "sourceLabel": source_label,
            "sourceType": source_type,
            "freshness": freshness,
            "asOf": value.get("asOf") or evidence.get("asOf"),
            "confidenceWeight": max(0.0, min(1.0, float(confidence_weight or 0.0))),
            "coverage": max(0.0, min(1.0, float(coverage or 0.0))),
            "isFallback": is_fallback,
            "isStale": is_stale,
            "isPartial": is_partial,
            "isSynthetic": is_synthetic,
            "isUnavailable": is_unavailable,
        }
        return payload

    @staticmethod
    def _market_overview_provider_evidence_status(evidence: Mapping[str, Any]) -> str:
        if bool(evidence.get("isUnavailable")):
            return "unavailable"
        if bool(evidence.get("isPartial")):
            return "partial"
        freshness = str(evidence.get("freshness") or "").strip().lower()
        if freshness:
            return freshness
        return "live"

    def _evidence_snapshot_card_key(self, payload: Mapping[str, Any], category: str) -> str:
        provider_health = payload.get("providerHealth") if isinstance(payload.get("providerHealth"), Mapping) else {}
        card_key = (
            payload.get("cardKey")
            or provider_health.get("card")
            or payload.get("cacheKey")
            or payload.get("panelKey")
            or category
        )
        return str(card_key or category)

    def _evidence_snapshot_endpoint(self, payload: Mapping[str, Any], category: str) -> Optional[str]:
        endpoint = payload.get("endpoint")
        if endpoint:
            return str(endpoint)
        card_key = self._evidence_snapshot_card_key(payload, category)
        return MARKET_OVERVIEW_ENDPOINTS.get(card_key)

    def _evidence_snapshot_provider_status(self, payload: Mapping[str, Any]) -> str:
        provider_health = payload.get("providerHealth") if isinstance(payload.get("providerHealth"), Mapping) else {}
        status = str(provider_health.get("status") or "").strip().lower()
        if status:
            return status
        return self._provider_health_status(dict(payload))

    @classmethod
    def _evidence_snapshot_score_reliability_allowed(
        cls,
        payload: Mapping[str, Any],
        evidence: Mapping[str, Any],
    ) -> bool:
        freshness = str(evidence.get("freshness") or "").strip().lower()
        provider_health = evidence.get("providerHealth") if isinstance(evidence.get("providerHealth"), Mapping) else {}
        provider_status = str(provider_health.get("status") or "").strip().lower()
        if evidence.get("scoreContributionAllowed") is not True:
            return False
        if evidence.get("sourceAuthorityAllowed") is False:
            return False
        if evidence.get("observationOnly") is True:
            return False
        if not freshness or freshness in {"cached", "delayed", "fallback", "stale", "partial", "unavailable", "mock", "error"}:
            return False
        if any(
            bool(evidence.get(key))
            for key in ("isFallback", "isStale", "isPartial", "isSynthetic", "isUnavailable", "isFromSnapshot", "isRefreshing")
        ):
            return False
        if provider_status and provider_status != "live":
            return False
        candidate_freshnesses = cls._evidence_snapshot_candidate_freshnesses(payload)
        if any(state in {"cached", "delayed", "fallback", "stale", "partial", "unavailable", "mock", "error"} for state in candidate_freshnesses):
            return False
        return True

    def _evidence_snapshot_score_gate_meta(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        candidates = self._evidence_snapshot_gate_candidates(payload)
        source = str(payload.get("source") or "").strip()
        payload_source_type = str(payload.get("sourceType") or "").strip()
        source_type = (
            payload_source_type
            or self._evidence_snapshot_candidate_source_type(candidates)
            or _infer_source_type(source)
        )
        score_contribution_allowed = self._evidence_snapshot_gate_flag(
            payload,
            candidates,
            "scoreContributionAllowed",
        )
        source_authority_allowed = self._evidence_snapshot_gate_flag(
            payload,
            candidates,
            "sourceAuthorityAllowed",
        )
        observation_only = self._evidence_snapshot_observation_only(
            payload,
            candidates,
            score_contribution_allowed,
        )
        degradation_reason = self._evidence_snapshot_gate_reason(
            payload,
            candidates,
            score_contribution_allowed=score_contribution_allowed,
            source_authority_allowed=source_authority_allowed,
        )
        cap_reason = self._evidence_snapshot_cap_reason(payload, candidates)
        return {
            "sourceType": source_type,
            "sourceAuthorityAllowed": source_authority_allowed,
            "scoreContributionAllowed": score_contribution_allowed,
            "observationOnly": observation_only,
            "degradationReason": degradation_reason,
            "capReason": cap_reason,
        }

    @staticmethod
    def _evidence_snapshot_gate_candidates(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        candidates: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            candidates.append(item)
            cache_bundle = item.get("cacheBundleDiagnostics")
            if isinstance(cache_bundle, dict):
                candidates.append(
                    {
                        **cache_bundle,
                        "sourceType": cache_bundle.get("sourceType") or item.get("sourceType"),
                        "degradationReason": cache_bundle.get("degradationReason") or item.get("degradationReason"),
                        "sourceAuthorityReason": item.get("sourceAuthorityReason"),
                    }
                )
        return candidates

    @staticmethod
    def _evidence_snapshot_candidate_source_type(candidates: Sequence[Mapping[str, Any]]) -> str:
        source_types = [
            str(candidate.get("sourceType") or "").strip()
            for candidate in candidates
            if str(candidate.get("sourceType") or "").strip()
        ]
        if not source_types:
            return ""
        unique_source_types = list(dict.fromkeys(source_types))
        if len(unique_source_types) == 1:
            return unique_source_types[0]
        return unique_source_types[0]

    @staticmethod
    def _evidence_snapshot_gate_flag(
        payload: Mapping[str, Any],
        candidates: Sequence[Mapping[str, Any]],
        key: str,
    ) -> Optional[bool]:
        if key in payload:
            return bool(payload.get(key))
        values = [candidate.get(key) for candidate in candidates if key in candidate]
        if any(value is True for value in values):
            return True
        if any(value is False for value in values):
            return False
        return None

    @staticmethod
    def _evidence_snapshot_observation_only(
        payload: Mapping[str, Any],
        candidates: Sequence[Mapping[str, Any]],
        score_contribution_allowed: Optional[bool],
    ) -> Optional[bool]:
        if "observationOnly" in payload:
            return bool(payload.get("observationOnly"))
        values = [candidate.get("observationOnly") for candidate in candidates if "observationOnly" in candidate]
        if any(value is True for value in values):
            return True
        if score_contribution_allowed is True:
            return False
        if any(value is False for value in values):
            return False
        return None

    @staticmethod
    def _evidence_snapshot_gate_reason(
        payload: Mapping[str, Any],
        candidates: Sequence[Mapping[str, Any]],
        *,
        score_contribution_allowed: Optional[bool],
        source_authority_allowed: Optional[bool],
    ) -> Optional[str]:
        explicit_payload_reason = (
            payload.get("degradationReason")
            or payload.get("fallbackReason")
        )
        if explicit_payload_reason:
            return str(explicit_payload_reason)
        if score_contribution_allowed is None and source_authority_allowed is None:
            return None
        if score_contribution_allowed is True and source_authority_allowed is not False:
            return None
        for key in ("degradationReason", "sourceAuthorityReason", "excludeReason"):
            for candidate in candidates:
                reason = candidate.get(key)
                if reason:
                    return str(reason)
        return None

    @staticmethod
    def _evidence_snapshot_cap_reason(
        payload: Mapping[str, Any],
        candidates: Sequence[Mapping[str, Any]],
    ) -> Optional[str]:
        explicit_payload_cap = payload.get("capReason")
        if explicit_payload_cap:
            return str(explicit_payload_cap)
        for candidate in candidates:
            cap_reason = candidate.get("capReason")
            if cap_reason:
                return str(cap_reason)
        return None

    @classmethod
    def _evidence_snapshot_reason_families(
        cls,
        evidence: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> List[Dict[str, Any]]:
        reason_families: List[Dict[str, Any]] = []
        seen_families: set[str] = set()

        for field in ("degradationReason", "capReason"):
            raw_code = evidence.get(field)
            if raw_code is None:
                continue
            normalized_code = str(raw_code).strip()
            if not normalized_code:
                continue
            for classification in classify_reason_codes([normalized_code]):
                entry = {
                    "rawCode": classification.raw_code,
                    "family": classification.family,
                    "scope": classification.scope,
                    "sourceField": field,
                }
                seen_families.add(str(entry["family"]))
                reason_families.append(entry)

        freshness = str(evidence.get("freshness") or "").strip().lower()
        candidate_freshnesses = cls._evidence_snapshot_candidate_freshnesses(payload)
        derived_entries = []
        if not freshness and not candidate_freshnesses:
            derived_entries.append(
                {
                    "rawCode": "freshness_missing",
                    "family": "missing_freshness",
                    "scope": "freshness",
                    "sourceField": "freshness",
                }
            )
        elif candidate_freshnesses.intersection({"cached", "delayed"}) and evidence.get("scoreReliabilityAllowed") is not True:
            derived_entries.append(
                {
                    "rawCode": "delayed" if "delayed" in candidate_freshnesses else "cached",
                    "family": "cached_delayed_only",
                    "scope": "freshness",
                    "sourceField": "freshness",
                }
            )

        for key, family in (
            ("isFallback", "fallback"),
            ("isStale", "stale"),
            ("isPartial", "partial"),
            ("isUnavailable", "unavailable"),
            ("isSynthetic", "synthetic"),
        ):
            if bool(evidence.get(key)):
                if key == "isFallback" and bool(evidence.get("isUnavailable")):
                    continue
                derived_entries.append(
                    {
                        "rawCode": key,
                        "family": family,
                        "scope": "freshness",
                        "sourceField": key,
                    }
                )

        if evidence.get("sourceAuthorityAllowed") is False and not bool(evidence.get("isUnavailable")):
            derived_entries.append(
                {
                    "rawCode": "source_authority_blocked",
                    "family": "source_authority_blocked",
                    "scope": "score_gate",
                    "sourceField": "sourceAuthorityAllowed",
                }
            )
        if (
            bool(evidence.get("observationOnly"))
            and evidence.get("scoreContributionAllowed") is False
            and not bool(evidence.get("isUnavailable"))
        ):
            derived_entries.append(
                {
                    "rawCode": "observation_only_source",
                    "family": "observation_only_source",
                    "scope": "score_gate",
                    "sourceField": "observationOnly",
                }
            )

        for entry in derived_entries:
            family_key = str(entry["family"])
            if family_key in seen_families:
                continue
            seen_families.add(family_key)
            reason_families.append(entry)
        return reason_families

    @classmethod
    def _evidence_snapshot_candidate_freshnesses(cls, payload: Mapping[str, Any]) -> set[str]:
        freshness_values = {str(payload.get("freshness") or "").strip().lower()}
        candidates = cls._evidence_snapshot_gate_candidates(dict(payload))
        for candidate in candidates:
            freshness_values.add(str(candidate.get("freshness") or "").strip().lower())
            source_freshness = candidate.get("sourceFreshnessEvidence")
            if isinstance(source_freshness, Mapping):
                freshness_values.add(str(source_freshness.get("freshness") or "").strip().lower())
        return {value for value in freshness_values if value}

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
        if not preserved_freshness and payload.get("isPartial"):
            preserved_freshness = {
                "freshness": payload.get("freshness") or "partial",
                "isFallback": bool(payload.get("isFallback")),
                "isStale": bool(payload.get("isStale")),
                "isPartial": True,
                "isUnavailable": bool(payload.get("isUnavailable")),
                "warning": payload.get("warning"),
            }
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

    def _source_activation_meta(self, item: Dict[str, Any]) -> Dict[str, Any]:
        source = str(item.get("source") or "").lower()
        symbol = str(item.get("symbol") or "")
        source_type = str(item.get("sourceType") or _infer_source_type(source)).lower()
        source_tier = str(item.get("sourceTier") or "").lower()
        is_fallback = bool(item.get("isFallback") or item.get("fallbackUsed"))
        is_unavailable = bool(item.get("isUnavailable"))
        overlay_configured = symbol in self.OFFICIAL_OVERLAY_SERIES_BY_SYMBOL
        overlay_attempted = bool(item.get("officialOverlayAttempted")) if "officialOverlayAttempted" in item else overlay_configured
        overlay_available = (
            bool(item.get("officialOverlayAvailable"))
            if "officialOverlayAvailable" in item
            else bool(overlay_attempted and source_type == "official_public" and not is_unavailable)
        )
        provider_class = str(item.get("providerClass") or self._provider_class_for_item(item)).strip()
        failure_reason = self._normalize_official_overlay_failure_reason(item.get("officialOverlayFailureReason"))
        if failure_reason is None:
            if overlay_attempted and not overlay_available:
                failure_reason = "refresh_not_attempted"
            elif not overlay_attempted:
                failure_reason = "not_configured"
        provider_attempted = (
            bool(item.get("providerAttempted"))
            if "providerAttempted" in item
            else self._provider_attempted_for_item(
                source=source,
                source_type=source_type,
                source_tier=source_tier,
                provider_class=provider_class,
                overlay_attempted=overlay_attempted,
                symbol=symbol,
                is_fallback=is_fallback,
            )
        )
        activation_hint = str(item.get("activationHint") or "").strip() or self._activation_hint_for_item(
            provider_class=provider_class,
            overlay_attempted=overlay_attempted,
            overlay_available=overlay_available,
            failure_reason=str(failure_reason or ""),
        )
        return {
            "providerAttempted": provider_attempted,
            "officialOverlayAttempted": overlay_attempted,
            "officialOverlayAvailable": overlay_available,
            "officialOverlayFailureReason": failure_reason,
            "providerClass": provider_class,
            "activationHint": activation_hint,
            **self._official_macro_authority_meta(
                item,
                source_type=source_type,
                provider_class=provider_class,
                failure_reason=failure_reason,
            ),
        }

    @staticmethod
    def _official_macro_authority_meta(
        item: Dict[str, Any],
        *,
        source_type: str,
        provider_class: str,
        failure_reason: Optional[str],
    ) -> Dict[str, Any]:
        if source_type != "official_public" or provider_class != "official_daily":
            return {}

        freshness = str(item.get("freshness") or "").strip().lower()
        is_authoritative = bool(
            freshness in {"live", "cached", "delayed"}
            and not bool(item.get("isFallback"))
            and not bool(item.get("isUnavailable"))
            and not bool(item.get("isPartial"))
            and _has_valid_market_value(item)
        )
        explicit_authority = item.get("sourceAuthorityAllowed") if "sourceAuthorityAllowed" in item else None
        source_authority_allowed = is_authoritative if explicit_authority is None else bool(explicit_authority and is_authoritative)
        source_authority_reason = (
            None
            if source_authority_allowed
            else (
                item.get("sourceAuthorityReason")
                or failure_reason
                or item.get("degradationReason")
                or ("stale_official_row" if freshness == "stale" else "official_macro_unavailable")
            )
        )

        explicit_score_allowed = item.get("scoreContributionAllowed") if "scoreContributionAllowed" in item else None
        score_contribution_allowed = bool(source_authority_allowed and not item.get("observationOnly"))
        if explicit_score_allowed is not None:
            score_contribution_allowed = bool(score_contribution_allowed and explicit_score_allowed)

        return {
            "sourceAuthorityAllowed": source_authority_allowed,
            "scoreContributionAllowed": score_contribution_allowed,
            "sourceAuthorityRouteRejected": False,
            "sourceAuthorityReason": source_authority_reason,
            "routeRejectedReasonCodes": list(item.get("routeRejectedReasonCodes") or []),
        }

    @staticmethod
    def _normalize_official_overlay_failure_reason(reason: Any) -> Optional[str]:
        normalized = str(reason or "").strip().lower()
        if not normalized:
            return None
        aliases = {
            "not_attempted": "refresh_not_attempted",
            "official_overlay_stale": "stale_official_row",
        }
        normalized = aliases.get(normalized, normalized)
        if normalized in OFFICIAL_OVERLAY_FAILURE_REASONS:
            return normalized
        return "transport_error"

    def _provider_class_for_item(self, item: Dict[str, Any]) -> str:
        source = str(item.get("source") or "").lower()
        source_type = str(item.get("sourceType") or _infer_source_type(source)).lower()
        symbol = str(item.get("symbol") or "")
        if source_type == "official_public":
            return "official_daily"
        if source_type == "exchange_public":
            return "exchange_public"
        if source_type == "broker_authorized":
            return "broker_authorized"
        if (
            symbol in self.STATIC_FALLBACK_ACTIVATION_SYMBOLS
            or bool(item.get("isFallback") or item.get("fallbackUsed"))
            or source in {"fallback", "mock", "synthetic"}
            or source_type in {"fallback_static", "synthetic_fixture", "static_fallback"}
        ):
            return "static" if _has_valid_market_value(item) else "fallback"
        if source in {"unavailable", "missing"} or bool(item.get("isUnavailable")) or source_type == "missing":
            return "fallback"
        return "proxy"

    def _provider_attempted_for_item(
        self,
        *,
        source: str,
        source_type: str,
        source_tier: str,
        provider_class: str,
        overlay_attempted: bool,
        symbol: str,
        is_fallback: bool,
    ) -> bool:
        if provider_class in {"official_daily", "exchange_public", "broker_authorized", "proxy"}:
            return True
        if overlay_attempted:
            return True
        if symbol in self.STATIC_FALLBACK_ACTIVATION_SYMBOLS:
            return False
        if is_fallback or source in {"fallback", "mock", "synthetic"} or source_type in {"fallback_static", "synthetic_fixture"}:
            return False
        return bool(source or source_type or source_tier)

    @staticmethod
    def _activation_hint_for_item(
        *,
        provider_class: str,
        overlay_attempted: bool,
        overlay_available: bool,
        failure_reason: str,
    ) -> str:
        if provider_class == "official_daily" and overlay_attempted and overlay_available:
            return "official_daily_overlay_active"
        if overlay_attempted and not overlay_available:
            if failure_reason in {"official_overlay_stale", "stale_official_row"}:
                return (
                    "official_overlay_stale_using_proxy"
                    if provider_class == "proxy"
                    else "official_overlay_stale_using_static_fallback"
                )
            return (
                "official_overlay_unavailable_using_proxy"
                if provider_class == "proxy"
                else "official_overlay_unavailable_using_static_fallback"
            )
        if provider_class == "proxy":
            return "proxy_only_no_official_overlay"
        if provider_class == "static":
            return "static_fallback_no_provider"
        if provider_class == "exchange_public":
            return "exchange_public_provider_active"
        if provider_class == "broker_authorized":
            return "broker_authorized_provider_active"
        return "provider_unavailable"

    def _with_item_meta(self, item: Dict[str, Any], category: str, panel: Dict[str, Any]) -> Dict[str, Any]:
        source = str(item.get("source") or panel.get("source") or "mixed")
        is_fallback = bool(item.get("isFallback") or item.get("fallbackUsed") or source.lower() in {"fallback", "mock"})
        as_of = item.get("asOf") or item.get("last_update") or item.get("updatedAt") or panel.get("asOf") or panel.get("updatedAt")
        updated_at = item.get("updatedAt") or panel.get("updatedAt") or _now_iso()
        official_series_id = (
            item.get("officialOverlaySeriesId")
            or item.get("officialSeriesId")
            or item.get("sourceId")
        )
        freshness = get_freshness_status(
            as_of,
            category,
            source,
            is_fallback,
            source_type=item.get("sourceType") or panel.get("sourceType") or "",
            series_id=official_series_id,
            official_observation_date=item.get("officialObservationDate") or item.get("officialAsOf"),
        )
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
        official_freshness_details = (
            _official_daily_detail_payload(freshness)
            or _official_daily_detail_payload(item.get("officialFreshnessDetails"))
        )
        if official_freshness_details:
            normalized["officialFreshnessDetails"] = official_freshness_details
            for key, value in official_freshness_details.items():
                normalized.setdefault(key, value)
            source_evidence = dict(normalized.get("sourceFreshnessEvidence") or {})
            source_evidence.update({
                "source": normalized.get("source"),
                "sourceLabel": normalized.get("sourceLabel"),
                "asOf": normalized.get("asOf"),
                "freshness": normalized.get("freshness"),
                "isFallback": bool(normalized.get("isFallback")),
                "isStale": bool(normalized.get("isStale")),
                "isPartial": bool(normalized.get("isPartial")),
                "isUnavailable": bool(normalized.get("isUnavailable")),
                **official_freshness_details,
            })
            normalized["sourceFreshnessEvidence"] = source_evidence
        normalized = normalize_vix_quote_metadata(normalized)
        normalized = {**normalized, **self._source_trust_meta(normalized)}
        return {**normalized, **self._source_activation_meta(normalized)}

    def _fetch_indices(self) -> PanelPayload:
        return self._quote_panel("IndexTrendsCard", self.INDEX_SYMBOLS)

    def _fetch_volatility(self) -> PanelPayload:
        items = self._quote_items(self.VOL_SYMBOLS)
        official_vix, official_vix_failure = self._official_macro_overlay_item(
            "VIX",
            "VIX",
            self._official_macro_points().get("VIXCLS", []),
            series_id="VIXCLS",
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
        elif official_vix_failure:
            items = [
                self._with_official_overlay_failure(item, official_vix_failure, series_id="VIXCLS")
                if str(item.get("symbol") or "") == "VIX"
                else item
                for item in items
            ]
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
        payload = normalize_vix_panel_metadata(payload)
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
            "status": "partial" if snapshot.get("isPartial") else "success",
            "error_message": snapshot.get("error"),
            "refreshError": snapshot.get("refreshError"),
            "warning": snapshot.get("warning"),
            "source": snapshot.get("source"),
            "sourceLabel": snapshot.get("sourceLabel"),
            "freshness": snapshot.get("freshness"),
            "isFallback": bool(snapshot.get("isFallback") or snapshot.get("fallback_used") or snapshot.get("fallbackUsed")),
            "isStale": snapshot.get("isStale"),
            "isPartial": snapshot.get("isPartial"),
            "isUnavailable": snapshot.get("isUnavailable"),
            "isRefreshing": snapshot.get("isRefreshing"),
            "isFromSnapshot": snapshot.get("isFromSnapshot"),
            "lastSuccessfulAt": snapshot.get("lastSuccessfulAt"),
            "degradationReason": snapshot.get("degradationReason"),
            "fallbackReason": snapshot.get("fallbackReason"),
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
            "error": None,
            "refreshError": provider_error,
            "warning": "情绪指标部分可用，请结合来源与时效观察。" if provider_error else None,
            "fallback_used": False,
            "source": payload["source"],
            "sourceLabel": self._source_label(payload["source"]),
            "isPartial": bool(provider_error),
            "degradationReason": "provider_refresh_failed" if provider_error else None,
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
            "ETF": ("ETF flow proxy", "SPY", "B USD"),
            "INSTITUTIONAL": ("Institutional pressure proxy", "QQQ", "B USD"),
            "INDUSTRY": ("Industry breadth proxy", "IWM", "score"),
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
                "sourceType": "unofficial_public_api",
                "observationOnly": True,
                "sourceAuthorityAllowed": False,
                "scoreContributionAllowed": False,
                "sourceAuthorityReason": "quote_derived_etf_flow_proxy",
            })
        return {
            **self._success_panel("FundsFlowCard", items),
            "source": "yfinance_proxy",
            "sourceType": "unofficial_public_api",
            "observationOnly": True,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "sourceAuthorityReason": "quote_derived_etf_flow_proxy",
        }

    def _fetch_macro(self) -> PanelPayload:
        official_points = self._official_macro_points(
            include_policy_and_inflation=True,
            include_credit_stress=True,
            include_fed_liquidity=True,
            include_usd_pressure=True,
        )
        item_map = {
            str(item.get("symbol") or ""): item
            for item in self._quote_items(self.MACRO_SYMBOLS)
        }
        for panel_symbol, (series_id, label, unit, market) in self.OFFICIAL_RATE_SERIES.items():
            official_item, official_failure = self._official_macro_overlay_item(
                panel_symbol,
                label,
                official_points.get(series_id, []),
                series_id=series_id,
                unit=unit,
                market=market,
            )
            if official_item:
                item_map[panel_symbol] = official_item
            elif panel_symbol in item_map and official_failure:
                item_map[panel_symbol] = self._with_official_overlay_failure(
                    item_map[panel_symbol],
                    official_failure,
                    series_id=series_id,
                )
        official_sofr = self._official_macro_item("SOFR", "SOFR", official_points.get("SOFR", []), unit="%", market="US")
        if official_sofr:
            item_map["SOFR"] = official_sofr
        for panel_symbol, (series_id, label, unit, market) in self.OFFICIAL_RATE_CONTEXT_SERIES.items():
            official_item, official_failure = self._official_macro_overlay_item(
                panel_symbol,
                label,
                official_points.get(series_id, []),
                series_id=series_id,
                unit=unit,
                market=market,
                value_scale=100.0,
                change_scale=100.0,
            )
            if official_item:
                item_map[panel_symbol] = official_item
            elif panel_symbol in item_map and official_failure:
                item_map[panel_symbol] = self._with_official_overlay_failure(
                    item_map[panel_symbol],
                    official_failure,
                    series_id=series_id,
                )
        official_vix, official_vix_failure = self._official_macro_overlay_item(
            "VIX",
            "VIX",
            official_points.get("VIXCLS", []),
            series_id="VIXCLS",
            unit="pts",
            change_scale=1.0,
        )
        if official_vix:
            item_map["VIX"] = official_vix
        elif "VIX" in item_map and official_vix_failure:
            item_map["VIX"] = self._with_official_overlay_failure(
                item_map["VIX"],
                official_vix_failure,
                series_id="VIXCLS",
            )
        else:
            item_map.setdefault("VIX", self._official_macro_unavailable_item("VIX", "VIX", "VIXCLS", unit="pts"))
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
        item_map.update(self._official_fed_liquidity_items(official_points))
        item_map.update(self._official_usd_pressure_items(official_points))
        item_map.setdefault("SOFR", self._official_macro_unavailable_item("SOFR", "SOFR", "SOFR", unit="%", market="US"))
        for symbol, (series_id, label, unit, market) in self.OFFICIAL_MACRO_SERIES.items():
            if symbol == "CREDIT" and symbol in item_map:
                continue
            item_map.setdefault(symbol, self._official_macro_unavailable_item(symbol, label, series_id, unit=unit, market=market))
        ordered_symbols = [
            "US2Y",
            "US10Y",
            "US30Y",
            "SOFR",
            "US10Y2Y",
            "US10Y3M",
            "VIX",
            "USD_TWI",
            "DXY",
            "GOLD",
            "OIL",
            "FEDFUNDS",
            "CPI",
            "PPI",
            "CREDIT",
            "FED_ASSETS",
            "FED_RRP",
            "TGA",
            "RESERVES",
        ]
        items = [item_map[symbol] for symbol in ordered_symbols if symbol in item_map]
        payload = self._success_panel("MacroIndicatorsCard", items)
        payload["source"] = "mixed"
        payload["sourceLabel"] = self._source_label("mixed")
        payload["fallbackUsed"] = any(bool(item.get("isFallback") or item.get("isUnavailable")) for item in items)
        if payload["fallbackUsed"]:
            payload["warning"] = OFFICIAL_MACRO_UNAVAILABLE_WARNING
        return payload

    def _fetch_cn_indices_snapshot(self) -> Dict[str, Any]:
        try:
            live_quotes = self._fetch_sina_cn_index_quotes()
        except Exception:
            return self._fallback_cn_indices_snapshot()

        fallback = self._fallback_cn_indices_snapshot()

        merged_items = []
        live_count = 0
        for fallback_item in fallback.get("items", []):
            symbol = str(fallback_item.get("symbol") or "")
            canonical_symbol = self._canonical_cn_index_symbol(symbol)
            quote = live_quotes.get(canonical_symbol)
            if quote:
                live_count += 1
                merged_items.append({
                    **fallback_item,
                    **quote,
                    "symbol": canonical_symbol,
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
        is_partial = live_count != len(merged_items)
        source = "sina" if not is_partial else "mixed"
        payload = {
            "source": source,
            "sourceLabel": self._source_label(source),
            "updatedAt": updated_at,
            "asOf": max((str(item.get("asOf") or "") for item in merged_items), default=updated_at) or updated_at,
            "items": merged_items,
            "fallbackUsed": is_partial,
            "warning": FALLBACK_WARNING if is_partial else None,
        }
        if is_partial:
            payload["freshness"] = "partial"
            payload["isPartial"] = True
        return payload

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

    def _canonical_cn_index_symbol(self, symbol: Any) -> str:
        normalized_symbol = str(symbol or "").strip()
        return self.CN_INDEX_SYMBOL_ALIASES.get(normalized_symbol, normalized_symbol)

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
        return self._with_breadth_readiness(payload, "CN")

    def _fetch_us_breadth_snapshot(self) -> Dict[str, Any]:
        polygon_activation = run_polygon_us_breadth_activation()
        authority_diagnostic = self._polygon_us_breadth_authority_diagnostic(polygon_activation)
        if (
            polygon_activation.get("sourceAuthorityAllowed")
            and polygon_activation.get("scoreContributionAllowed")
            and polygon_activation.get("comparisonBasis") == "previous_close"
        ):
            return self._polygon_us_breadth_snapshot(polygon_activation, authority_diagnostic)

        representative_meta = representative_sample_breadth_metadata()
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
                "sourceType": "unofficial_proxy",
                "isFallback": False,
                **representative_meta,
            })
        if not quote_items:
            return self._fallback_us_breadth_snapshot(authority_diagnostic=authority_diagnostic)

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
        payload = {
            "source": "yfinance_proxy",
            "sourceLabel": "Yahoo Finance",
            "sourceType": "unofficial_proxy",
            "updatedAt": updated_at,
            "asOf": updated_at,
            "freshness": "delayed",
            "warning": (
                "US breadth missing/unavailable: official or authorized breadth "
                "provider is not configured; showing representative sector ETF proxy only."
            ),
            "explanation": (
                "US breadth missing/unavailable; sector ETF and relative-pressure rows "
                "are representative observations, not full-market breadth."
            ),
            "authorityDiagnostics": authority_diagnostic,
            **representative_meta,
            "items": [
                {
                    **item,
                    **representative_meta,
                    "updatedAt": updated_at,
                    "asOf": updated_at,
                    "source": item.get("source") or "computed",
                    "sourceLabel": item.get("sourceLabel") or "系统计算",
                    "sourceType": item.get("sourceType") or "unofficial_proxy",
                    "isFallback": False,
                }
                for item in items
            ],
            "fallbackUsed": False,
        }
        return self._with_breadth_readiness(payload, "US")

    def _polygon_us_breadth_authority_diagnostic(
        self,
        activation: Mapping[str, Any],
    ) -> Dict[str, Any]:
        diagnostic = polygon_us_breadth_diagnostic_summary(activation)
        reason_codes = list(diagnostic.get("reasonCodes") or [])
        reason = reason_codes[0] if reason_codes else None
        if reason == US_BREADTH_MISSING_PROVIDER_REASON:
            return {
                **build_us_breadth_missing_authority_diagnostic(),
                **diagnostic,
                "reason": US_BREADTH_MISSING_PROVIDER_REASON,
            }
        return {
            **diagnostic,
            "reason": reason,
            "sourceLabel": POLYGON_US_BREADTH_SOURCE_LABEL,
            "sourceTier": POLYGON_US_BREADTH_SOURCE_TIER,
            "trustLevel": POLYGON_US_BREADTH_TRUST_LEVEL,
            "authorityBasis": POLYGON_US_BREADTH_AUTHORITY_BASIS,
            "universe": POLYGON_US_BREADTH_UNIVERSE,
        }

    def _polygon_us_breadth_snapshot(
        self,
        activation: Mapping[str, Any],
        authority_diagnostic: Mapping[str, Any],
    ) -> Dict[str, Any]:
        updated_at = _now_iso()
        as_of = str(activation.get("asOf") or activation.get("observationDate") or updated_at)
        fulfilled_metrics = list(activation.get("fulfilledMetrics") or [])
        missing_metrics = list(activation.get("missingMetrics") or [])
        reason_codes = list(activation.get("reasonCodes") or [])
        metric_coverage_ratio = round(len(fulfilled_metrics) / max(1, len(fulfilled_metrics) + len(missing_metrics)), 3)
        high_low_symbols = {"NEW_HIGHS", "NEW_LOWS", "HIGH_LOW_RATIO"}
        high_low_fulfilled = high_low_symbols.issubset(set(fulfilled_metrics))
        high_low_unavailable_reason = next(
            (
                str(reason)
                for reason in reason_codes
                if str(reason).startswith("polygon_high_low")
            ),
            POLYGON_HIGH_LOW_HISTORY_UNAVAILABLE_REASON,
        )
        score_contribution_allowed = bool(
            activation.get("scoreContributionAllowed")
            and activation.get("comparisonBasis") == "previous_close"
        )
        source_authority_allowed = bool(activation.get("sourceAuthorityAllowed") and score_contribution_allowed)
        broad_market_claim_allowed = bool(
            activation.get("broadMarketClaimAllowed")
            and set(US_BREADTH_SYMBOLS).issubset(set(fulfilled_metrics))
        )
        source_meta = {
            "breadthClaimType": "computed_authorized_polygon_grouped_daily_breadth",
            "breadthClaimScope": "computed_polygon_ad_high_low" if high_low_fulfilled else "advance_decline_only",
            "breadthCompleteness": "computed_high_low_available" if high_low_fulfilled else "partial_ad_only",
            "representativeSample": False,
            "officialExchangePublishedBreadth": False,
            "fullBreadthAuthority": False,
            "broadMarketClaimAllowed": broad_market_claim_allowed,
            "observationOnly": False,
            "sourceAuthorityAllowed": source_authority_allowed,
            "scoreContributionAllowed": score_contribution_allowed,
            "sourceAuthorityReason": None,
            "sourceAuthorityRouteRejected": False,
            "routeRejectedReasonCodes": reason_codes,
            "source": POLYGON_US_BREADTH_SOURCE,
            "sourceLabel": POLYGON_US_BREADTH_SOURCE_LABEL,
            "sourceType": POLYGON_US_BREADTH_SOURCE_TYPE,
            "sourceTier": POLYGON_US_BREADTH_SOURCE_TIER,
            "trustLevel": POLYGON_US_BREADTH_TRUST_LEVEL,
            "authorityBasis": POLYGON_US_BREADTH_AUTHORITY_BASIS,
            "universe": POLYGON_US_BREADTH_UNIVERSE,
            "coverageCount": activation.get("coverageCount"),
            "coverageThreshold": activation.get("coverageThreshold"),
            "previousObservationDate": activation.get("previousObservationDate"),
            "comparisonBasis": activation.get("comparisonBasis"),
            "previousCoverageCount": activation.get("previousCoverageCount"),
            "comparisonCoverageCount": activation.get("comparisonCoverageCount"),
            "highLowLookbackSessions": activation.get("highLowLookbackSessions"),
            "highLowEligibleCount": activation.get("highLowEligibleCount"),
            "highLowEligibleThreshold": activation.get("highLowEligibleThreshold"),
            "metricCoverageRatio": metric_coverage_ratio,
            "highLowUnavailableReason": None if high_low_fulfilled else high_low_unavailable_reason,
            "sourceFreshnessEvidence": {
                "freshness": "delayed",
                "isFallback": False,
                "isStale": False,
                "isPartial": bool(missing_metrics),
                "isUnavailable": False,
                "observationDate": activation.get("observationDate"),
                "previousObservationDate": activation.get("previousObservationDate"),
                "comparisonBasis": activation.get("comparisonBasis"),
                "freshnessPolicy": "polygon_grouped_daily_eod_recent_completed_us_weekday",
                "highLowLookbackSessions": activation.get("highLowLookbackSessions"),
                "highLowEligibleCount": activation.get("highLowEligibleCount"),
                "highLowEligibleThreshold": activation.get("highLowEligibleThreshold"),
            },
        }
        metrics = activation.get("metrics") if isinstance(activation.get("metrics"), Mapping) else {}
        detail = "Computed from Polygon grouped daily adjusted US equities, OTC excluded"
        items = [
            self._polygon_us_breadth_metric_item(
                "Advancers",
                "ADVANCERS",
                metrics.get("advancers"),
                "stocks",
                as_of,
                updated_at,
                source_meta,
                detail=detail,
            ),
            self._polygon_us_breadth_metric_item(
                "Decliners",
                "DECLINERS",
                metrics.get("decliners"),
                "stocks",
                as_of,
                updated_at,
                source_meta,
                detail=detail,
            ),
            self._polygon_us_breadth_metric_item(
                "Unchanged",
                "UNCHANGED",
                metrics.get("unchanged"),
                "stocks",
                as_of,
                updated_at,
                source_meta,
                detail=detail,
            ),
            self._polygon_us_breadth_metric_item(
                "Advance/Decline Ratio",
                "ADVANCE_DECLINE_RATIO",
                metrics.get("advanceDeclineRatio"),
                "ratio",
                as_of,
                updated_at,
                source_meta,
                detail=detail,
            ),
        ]
        for label, symbol, unit, value_key in (
            ("New Highs", "NEW_HIGHS", "stocks", "newHighs"),
            ("New Lows", "NEW_LOWS", "stocks", "newLows"),
            ("High/Low Ratio", "HIGH_LOW_RATIO", "ratio", "highLowRatio"),
        ):
            items.append(
                self._polygon_us_breadth_metric_item(
                    label,
                    symbol,
                    metrics.get(value_key),
                    unit,
                    as_of,
                    updated_at,
                    source_meta,
                    detail=detail,
                )
            )
        payload = {
            **source_meta,
            "updatedAt": updated_at,
            "asOf": as_of,
            "observationDate": activation.get("observationDate"),
            "previousObservationDate": activation.get("previousObservationDate"),
            "comparisonBasis": activation.get("comparisonBasis"),
            "previousCoverageCount": activation.get("previousCoverageCount"),
            "comparisonCoverageCount": activation.get("comparisonCoverageCount"),
            "highLowLookbackSessions": activation.get("highLowLookbackSessions"),
            "highLowEligibleCount": activation.get("highLowEligibleCount"),
            "highLowEligibleThreshold": activation.get("highLowEligibleThreshold"),
            "freshness": "delayed",
            "coverage": metric_coverage_ratio,
            "isPartial": bool(missing_metrics),
            "isFallback": False,
            "fallbackUsed": False,
            "warning": (
                "US breadth uses computed Polygon grouped-daily AD and 52-week high/low metrics; "
                "broad-market authority remains disabled because this is not official NYSE/Nasdaq published breadth."
                if high_low_fulfilled
                else "US breadth uses computed Polygon grouped-daily AD metrics; "
                "52-week high/low breadth is unavailable because strict historical coverage gates did not pass."
            ),
            "explanation": (
                "This is computed from Polygon's authorized grouped daily US equity feed "
                "with adjusted prices and OTC excluded; it is not official NYSE/Nasdaq "
                "published breadth."
            ),
            "authorityDiagnostics": dict(authority_diagnostic),
            "fulfilledMetrics": fulfilled_metrics,
            "missingMetrics": missing_metrics,
            "missingMetricReasons": {
                symbol: high_low_unavailable_reason
                for symbol in ("NEW_HIGHS", "NEW_LOWS", "HIGH_LOW_RATIO")
                if symbol in missing_metrics
            },
            "items": items,
        }
        return self._with_breadth_readiness(payload, "US")

    def _polygon_us_breadth_metric_item(
        self,
        label: str,
        symbol: str,
        value: Any,
        unit: str,
        as_of: str,
        updated_at: str,
        source_meta: Mapping[str, Any],
        *,
        detail: str,
    ) -> Dict[str, Any]:
        numeric_value = self._clean_number(value)
        if numeric_value is None:
            return self._polygon_unavailable_breadth_metric_item(label, symbol, as_of, updated_at, source_meta)
        item = self._breadth_metric_item(
            label,
            symbol,
            numeric_value,
            unit,
            as_of,
            updated_at,
            POLYGON_US_BREADTH_SOURCE,
            POLYGON_US_BREADTH_SOURCE_LABEL,
            POLYGON_US_BREADTH_SOURCE_TYPE,
            detail=detail,
        )
        return {
            **item,
            **source_meta,
            "scoreContributionAllowed": bool(source_meta.get("scoreContributionAllowed")),
            "sourceAuthorityAllowed": bool(source_meta.get("sourceAuthorityAllowed")),
            "sourceAuthorityReason": None,
            "sourceFreshnessEvidence": {
                **dict(source_meta.get("sourceFreshnessEvidence") or {}),
                "isPartial": False,
            },
        }

    def _polygon_unavailable_breadth_metric_item(
        self,
        label: str,
        symbol: str,
        as_of: str,
        updated_at: str,
        source_meta: Mapping[str, Any],
    ) -> Dict[str, Any]:
        reason = str(source_meta.get("highLowUnavailableReason") or POLYGON_HIGH_LOW_HISTORY_UNAVAILABLE_REASON)
        item = self._unavailable_item(
            label,
            symbol,
            "History unavailable",
            updated_at,
            detail="52-week high/low breadth requires bounded historical grouped-daily lookback.",
        )
        return {
            **item,
            **dict(source_meta),
            "source": POLYGON_US_BREADTH_SOURCE,
            "sourceLabel": POLYGON_US_BREADTH_SOURCE_LABEL,
            "sourceType": POLYGON_US_BREADTH_SOURCE_TYPE,
            "sourceTier": POLYGON_US_BREADTH_SOURCE_TIER,
            "trustLevel": POLYGON_US_BREADTH_TRUST_LEVEL,
            "authorityBasis": POLYGON_US_BREADTH_AUTHORITY_BASIS,
            "universe": POLYGON_US_BREADTH_UNIVERSE,
            "asOf": as_of,
            "updatedAt": updated_at,
            "isFallback": False,
            "isUnavailable": True,
            "observationOnly": True,
            "broadMarketClaimAllowed": False,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "sourceAuthorityReason": reason,
            "routeRejectedReasonCodes": [reason],
            "degradationReason": reason,
            "sourceFreshnessEvidence": {
                "freshness": "unavailable",
                "isFallback": False,
                "isStale": False,
                "isPartial": False,
                "isUnavailable": True,
                "comparisonBasis": source_meta.get("comparisonBasis"),
                "warning": "52-week high/low breadth history unavailable",
            },
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
        try:
            provider_payload = self._cn_hk_connect_flow_provider()
            return build_authorized_cn_hk_connect_flow_snapshot(provider_payload)
        except CnHkFlowProviderUnavailable:
            raise
        except Exception as exc:
            raise CnHkFlowProviderUnavailable("malformed_payload") from exc

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
            official_item, official_failure = self._official_macro_overlay_item(
                symbol,
                label,
                official_points.get(series_id, []),
                series_id=series_id,
                unit=unit,
                market=market,
            )
            if official_item:
                items.append(official_item)
                official_count += 1
            elif symbol in fallback_items:
                items.append(
                    self._with_official_overlay_failure(
                        fallback_items[symbol],
                        official_failure,
                        series_id=series_id,
                    )
                )
        for symbol, (series_id, label, unit, market) in self.OFFICIAL_RATE_CONTEXT_SERIES.items():
            official_item, official_failure = self._official_macro_overlay_item(
                symbol,
                label,
                official_points.get(series_id, []),
                series_id=series_id,
                unit=unit,
                market=market,
                value_scale=100.0,
                change_scale=100.0,
            )
            if official_item:
                items.append(official_item)
                official_count += 1
            elif symbol in fallback_items:
                items.append(
                    self._with_official_overlay_failure(
                        fallback_items[symbol],
                        official_failure,
                        series_id=series_id,
                    )
                )
        official_sofr = self._official_macro_item("SOFR", "SOFR", official_points.get("SOFR", []), unit="%", market="US")
        if official_sofr:
            items.append(official_sofr)
        else:
            items.append(self._official_macro_unavailable_item("SOFR", "SOFR", "SOFR", unit="%", market="US"))
        for symbol in ("CN10Y", "DR007", "SHIBOR", "LPR"):
            if symbol in fallback_items:
                items.append(fallback_items[symbol])

        return {
            **fallback,
            "source": "mixed" if official_count > 0 or official_sofr else fallback.get("source", "fallback"),
            "sourceLabel": (
                self._source_label("mixed")
                if official_count > 0 or official_sofr
                else fallback.get("sourceLabel", self._source_label("fallback"))
            ),
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
                "sourceTier": theme.get("sourceTier"),
                "trustLevel": theme.get("trustLevel"),
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
                "sourceAuthorityAllowed": bool(theme.get("sourceAuthorityAllowed")) if "sourceAuthorityAllowed" in theme else None,
                "scoreContributionAllowed": bool(theme.get("scoreContributionAllowed")) if "scoreContributionAllowed" in theme else None,
                "sourceAuthorityReason": theme.get("sourceAuthorityReason"),
                "sourceAuthorityRouteRejected": bool(theme.get("sourceAuthorityRouteRejected")) if "sourceAuthorityRouteRejected" in theme else None,
                "routeRejectedReasonCodes": copy.deepcopy(theme.get("routeRejectedReasonCodes") or []),
                "rankEligible": bool(theme.get("rankEligible")) if "rankEligible" in theme else None,
                "headlineEligible": bool(theme.get("headlineEligible")) if "headlineEligible" in theme else None,
                "rankingLane": theme.get("rankingLane"),
                "rankExclusionReason": theme.get("rankExclusionReason"),
                "observationOnly": bool(theme.get("observationOnly")) if "observationOnly" in theme else None,
                "taxonomyOnly": bool(theme.get("taxonomyOnly")) if "taxonomyOnly" in theme else None,
                "scoreCap": self._clean_number(theme.get("scoreCap")),
                "rankingTrust": copy.deepcopy(theme.get("rankingTrust")) if isinstance(theme.get("rankingTrust"), dict) else None,
                "degradationReasons": copy.deepcopy(theme.get("degradationReasons") or []),
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
        include_fed_liquidity: bool = False,
        include_usd_pressure: bool = False,
        budget_seconds: Optional[float] = None,
    ) -> Dict[str, List[MacroObservation]]:
        points: Dict[str, List[MacroObservation]] = {}
        diagnostics: Dict[str, str] = {}
        diagnostic_details: Dict[str, Dict[str, Any]] = {}
        provider_attempt_details: Dict[str, List[Dict[str, Any]]] = {}
        fetched_at = time.monotonic()
        fred_series_ids = ["VIXCLS", "DGS10", "DGS30", "DGS2", "SOFR", "T10Y2Y", "T10Y3M"]
        if include_policy_and_inflation:
            fred_series_ids.extend(["DFF", "CPIAUCSL", "PPIACO"])
        if include_credit_stress:
            fred_series_ids.append("BAMLH0A0HYM2")
        if include_fed_liquidity:
            fred_series_ids.extend(FED_LIQUIDITY_FRED_SERIES_IDS)
        if include_usd_pressure:
            fred_series_ids.extend(USD_PRESSURE_FRED_SERIES_IDS)
        for series_id in fred_series_ids:
            cached_points = self._cached_official_macro_series(series_id, fetched_at)
            if cached_points:
                freshness_reason = self._official_macro_row_failure_reason(series_id, cached_points)
                if freshness_reason is None:
                    points[series_id] = cached_points
                else:
                    self._record_official_macro_diagnostic(
                        diagnostics,
                        series_id,
                        freshness_reason,
                        diagnostic_details=diagnostic_details,
                        details=self._official_macro_failure_details(
                            series_id,
                            freshness_reason,
                            provider_name=self._provider_name_for_series(series_id),
                            source_id=self._source_id_for_series(series_id),
                            attempted_at=_now_iso(),
                            timeout_seconds=self.OFFICIAL_MACRO_CALL_TIMEOUT_SECONDS,
                            freshness_details=self._official_macro_freshness_details(series_id, cached_points),
                        ),
                    )
            else:
                self._record_official_macro_diagnostic(
                    diagnostics,
                    series_id,
                    "cache_miss",
                    diagnostic_details=diagnostic_details,
                    details=self._official_macro_failure_details(
                        series_id,
                        "cache_miss",
                        provider_name=self._provider_name_for_series(series_id),
                        source_id=self._source_id_for_series(series_id),
                        attempted_at=_now_iso(),
                    ),
                )

        deadline = self._deadline_after(
            self.OFFICIAL_MACRO_AGGREGATE_BUDGET_SECONDS
            if budget_seconds is None
            else budget_seconds
        )
        treasury_series_ids = {"DGS2", "DGS10", "DGS30"}
        initial_missing_treasury_series_ids = {
            series_id for series_id in treasury_series_ids if series_id not in points
        }
        attempted_fred_series: set[str] = set()
        fred_refresh_disabled_reason: str | None = None
        fred_refresh_disabled_details: Dict[str, Any] | None = None
        critical_fred_series_ids = set(self.OFFICIAL_MACRO_CRITICAL_FRED_SERIES_IDS)

        def critical_fred_timeout_floor() -> float:
            return min(
                float(self.OFFICIAL_MACRO_CALL_TIMEOUT_SECONDS),
                float(self.OFFICIAL_MACRO_CRITICAL_FRED_TIMEOUT_FLOOR_SECONDS),
            )

        def record_provider_attempt(
            series_id: str,
            reason: str,
            *,
            provider_name: str,
            source_id: str,
            attempted_at: str | None = None,
            timeout_seconds: float | None = None,
            exception: Exception | None = None,
            transport_details: Any = None,
            freshness_details: Any = None,
        ) -> None:
            details = self._official_macro_failure_details(
                series_id,
                reason,
                provider_name=provider_name,
                source_id=source_id,
                attempted_at=attempted_at or _now_iso(),
                timeout_seconds=timeout_seconds,
                exception=exception,
                transport_details=transport_details,
                freshness_details=freshness_details,
            )
            details["reason"] = str(reason or "").strip().lower()
            safe_detail = self._sanitize_official_macro_provider_attempt_detail(details, series_id=series_id)
            if safe_detail:
                provider_attempt_details.setdefault(series_id, []).append(safe_detail)

        def attach_provider_attempt_details() -> None:
            for series_id, attempts in provider_attempt_details.items():
                if series_id not in diagnostics or len(attempts) < 2:
                    continue
                details = dict(diagnostic_details.get(series_id) or {})
                details["providerAttemptDetails"] = list(attempts)
                diagnostic_details[series_id] = self._sanitize_official_macro_failure_details(
                    details,
                    series_id=series_id,
                )

        def treasury_failure_can_be_primary(series_id: str) -> bool:
            return series_id not in points and series_id not in diagnostics

        def fetch_fred_series(series_id: str, *, timeout_cap: float | None = None) -> None:
            nonlocal fred_refresh_disabled_reason, fred_refresh_disabled_details
            attempted_fred_series.add(series_id)
            timeout = self._deadline_timeout(
                deadline,
                self.OFFICIAL_MACRO_CALL_TIMEOUT_SECONDS if timeout_cap is None else timeout_cap,
            )
            if timeout is None:
                self._record_official_macro_diagnostic(
                    diagnostics,
                    series_id,
                    "budget_exhausted",
                    diagnostic_details=diagnostic_details,
                    details=self._official_macro_failure_details(
                        series_id,
                        "budget_exhausted",
                        provider_name="fred",
                        source_id=f"fred:{series_id}",
                        attempted_at=_now_iso(),
                    ),
                )
                return
            fred_error_reason: str | None = None
            fred_error_details: Dict[str, Any] | None = None
            try:
                series_points = fetch_fred_observation_points(
                    series_id,
                    limit=self._official_macro_history_limit(series_id),
                    timeout=timeout,
                )
            except Exception as exc:
                series_points = []
                fred_error_reason = self._official_macro_exception_reason(exc)
                fred_error_details = self._official_macro_failure_details(
                    series_id,
                    fred_error_reason,
                    provider_name="fred",
                    source_id=f"fred:{series_id}",
                    attempted_at=_now_iso(),
                    timeout_seconds=timeout,
                    exception=exc,
                    transport_details=getattr(exc, "diagnostics", None),
                )
                if fred_error_reason in {"missing_api_key", "disabled_config"}:
                    fred_refresh_disabled_reason = fred_error_reason
                    fred_refresh_disabled_details = dict(fred_error_details or {})
                record_provider_attempt(
                    series_id,
                    fred_error_reason,
                    provider_name="fred",
                    source_id=f"fred:{series_id}",
                    attempted_at=_now_iso(),
                    timeout_seconds=timeout,
                    exception=exc,
                    transport_details=fred_error_details,
                )
                self._record_official_macro_diagnostic(
                    diagnostics,
                    series_id,
                    fred_error_reason,
                    diagnostic_details=diagnostic_details,
                    details=fred_error_details,
                )
            if series_points:
                freshness_reason = self._official_macro_row_failure_reason(series_id, series_points)
                if freshness_reason is None:
                    self._store_official_macro_points({series_id: series_points}, fetched_at)
                    points[series_id] = series_points
                    diagnostics.pop(series_id, None)
                    diagnostic_details.pop(series_id, None)
                else:
                    record_provider_attempt(
                        series_id,
                        freshness_reason,
                        provider_name=self._provider_name_for_series(series_id, series_points[0].source_id if series_points else None),
                        source_id=series_points[0].source_id if series_points else f"fred:{series_id}",
                        attempted_at=_now_iso(),
                        timeout_seconds=timeout,
                        freshness_details=self._official_macro_freshness_details(series_id, series_points),
                    )
                    self._record_official_macro_diagnostic(
                        diagnostics,
                        series_id,
                        freshness_reason,
                        diagnostic_details=diagnostic_details,
                        details=self._official_macro_failure_details(
                            series_id,
                            freshness_reason,
                            provider_name=self._provider_name_for_series(series_id, series_points[0].source_id if series_points else None),
                            source_id=series_points[0].source_id if series_points else f"fred:{series_id}",
                            attempted_at=_now_iso(),
                            freshness_details=self._official_macro_freshness_details(series_id, series_points),
                        ),
                    )
            elif fred_error_reason is None:
                record_provider_attempt(
                    series_id,
                    "empty_response",
                    provider_name="fred",
                    source_id=f"fred:{series_id}",
                    attempted_at=_now_iso(),
                    timeout_seconds=timeout,
                )
                self._record_official_macro_diagnostic(
                    diagnostics,
                    series_id,
                    "empty_response",
                    diagnostic_details=diagnostic_details,
                    details=self._official_macro_failure_details(
                        series_id,
                        "empty_response",
                        provider_name="fred",
                        source_id=f"fred:{series_id}",
                        attempted_at=_now_iso(),
                        timeout_seconds=timeout,
                    ),
                )

        if "VIXCLS" not in points:
            fetch_fred_series("VIXCLS")

        if fred_refresh_disabled_reason is not None:
            for series_id in fred_series_ids:
                if series_id not in points:
                    self._record_official_macro_diagnostic(
                        diagnostics,
                        series_id,
                        fred_refresh_disabled_reason,
                        diagnostic_details=diagnostic_details,
                        details=self._official_macro_failure_details(
                            series_id,
                            fred_refresh_disabled_reason,
                            provider_name="fred",
                            source_id=f"fred:{series_id}",
                            attempted_at=_now_iso(),
                            transport_details=fred_refresh_disabled_details,
                        ),
                    )
            self._official_macro_overlay_diagnostics = diagnostics
            attach_provider_attempt_details()
            self._official_macro_overlay_diagnostic_details = diagnostic_details
            return points

        def fred_timeout_cap_for_series(series_id: str) -> float:
            if series_id not in critical_fred_series_ids:
                return float(self.OFFICIAL_MACRO_CALL_TIMEOUT_SECONDS)
            remaining_critical = [
                critical_series_id
                for critical_series_id in self.OFFICIAL_MACRO_CRITICAL_FRED_SERIES_IDS
                if critical_series_id not in points and critical_series_id not in attempted_fred_series
            ]
            if len(remaining_critical) <= 1:
                return float(self.OFFICIAL_MACRO_CALL_TIMEOUT_SECONDS)
            remaining_budget = self._deadline_remaining(deadline)
            if remaining_budget <= 0:
                return float(self.OFFICIAL_MACRO_CALL_TIMEOUT_SECONDS)
            fair_share = remaining_budget / float(len(remaining_critical))
            floor = critical_fred_timeout_floor()
            if floor > 0 and remaining_budget >= floor:
                return min(
                    float(self.OFFICIAL_MACRO_CALL_TIMEOUT_SECONDS),
                    max(floor, fair_share),
                )
            return min(
                float(self.OFFICIAL_MACRO_CALL_TIMEOUT_SECONDS),
                fair_share,
            )

        for index, series_id in enumerate(fred_series_ids):
            if series_id in points and points[series_id]:
                continue
            if series_id in attempted_fred_series:
                continue
            timeout_cap = fred_timeout_cap_for_series(series_id)
            timeout = self._deadline_timeout(deadline, timeout_cap)
            if timeout is None:
                for remaining_series_id in fred_series_ids[index:]:
                    if remaining_series_id not in points and remaining_series_id not in attempted_fred_series:
                        self._record_official_macro_diagnostic(
                            diagnostics,
                            remaining_series_id,
                            "budget_exhausted",
                            diagnostic_details=diagnostic_details,
                            details=self._official_macro_failure_details(
                                remaining_series_id,
                                "budget_exhausted",
                                provider_name="fred",
                                source_id=f"fred:{remaining_series_id}",
                                attempted_at=_now_iso(),
                            ),
                        )
                break
            fetch_fred_series(series_id, timeout_cap=timeout_cap)
            if fred_refresh_disabled_reason is not None:
                for remaining_series_id in fred_series_ids[index + 1:]:
                    if remaining_series_id not in points:
                        self._record_official_macro_diagnostic(
                            diagnostics,
                            remaining_series_id,
                            fred_refresh_disabled_reason,
                            diagnostic_details=diagnostic_details,
                            details=self._official_macro_failure_details(
                                remaining_series_id,
                                fred_refresh_disabled_reason,
                                provider_name="fred",
                                source_id=f"fred:{remaining_series_id}",
                                attempted_at=_now_iso(),
                                transport_details=fred_refresh_disabled_details,
                            ),
                        )
                break

        missing_treasury_series_ids = {
            series_id for series_id in initial_missing_treasury_series_ids if series_id not in points
        }
        treasury_attempt_series_ids = set(initial_missing_treasury_series_ids)
        if treasury_attempt_series_ids:
            treasury_timeout_cap = min(
                float(self.OFFICIAL_MACRO_CALL_TIMEOUT_SECONDS),
                float(self.OFFICIAL_MACRO_TREASURY_FALLBACK_TIMEOUT_CAP_SECONDS),
                self._deadline_remaining(deadline),
            )
            timeout = self._deadline_timeout(deadline, treasury_timeout_cap)
        else:
            timeout = None
        if timeout is not None:
            treasury_error_reason: str | None = None
            treasury_error_details: Dict[str, Any] | None = None
            try:
                treasury_points = fetch_treasury_daily_rate_observation_points(limit=2, timeout=timeout)
            except Exception as exc:
                treasury_points = {}
                treasury_error_reason = self._official_macro_exception_reason(exc)
                treasury_error_details = self._official_macro_failure_details(
                    "DGS10",
                    treasury_error_reason,
                    provider_name="treasury",
                    source_id="treasury:daily_treasury_yield_curve",
                    attempted_at=_now_iso(),
                    timeout_seconds=timeout,
                    exception=exc,
                    transport_details=getattr(exc, "diagnostics", None),
                )
            self._store_official_macro_points(
                {
                    series_id: series_points
                    for series_id, series_points in treasury_points.items()
                    if series_id not in points
                },
                fetched_at,
            )
            for series_id in sorted(treasury_attempt_series_ids):
                series_points = treasury_points.get(series_id, [])
                if series_points:
                    freshness_reason = self._official_macro_row_failure_reason(series_id, series_points)
                    if freshness_reason is None:
                        if series_id not in points:
                            points[series_id] = list(series_points)
                            diagnostics.pop(series_id, None)
                            diagnostic_details.pop(series_id, None)
                    else:
                        record_provider_attempt(
                            series_id,
                            freshness_reason,
                            provider_name="treasury",
                            source_id=series_points[0].source_id if series_points else "treasury:daily_treasury_yield_curve",
                            attempted_at=_now_iso(),
                            timeout_seconds=timeout,
                            freshness_details=self._official_macro_freshness_details(series_id, series_points),
                        )
                        if treasury_failure_can_be_primary(series_id):
                            self._record_official_macro_diagnostic(
                                diagnostics,
                                series_id,
                                freshness_reason,
                                diagnostic_details=diagnostic_details,
                                details=self._official_macro_failure_details(
                                    series_id,
                                    freshness_reason,
                                    provider_name="treasury",
                                    source_id=series_points[0].source_id if series_points else "treasury:daily_treasury_yield_curve",
                                    attempted_at=_now_iso(),
                                    freshness_details=self._official_macro_freshness_details(series_id, series_points),
                                ),
                            )
                elif series_id in treasury_points:
                    record_provider_attempt(
                        series_id,
                        "empty_response",
                        provider_name="treasury",
                        source_id="treasury:daily_treasury_yield_curve",
                        attempted_at=_now_iso(),
                        timeout_seconds=timeout,
                    )
                    if treasury_failure_can_be_primary(series_id):
                        self._record_official_macro_diagnostic(
                            diagnostics,
                            series_id,
                            "empty_response",
                            diagnostic_details=diagnostic_details,
                            details=self._official_macro_failure_details(
                                series_id,
                                "empty_response",
                                provider_name="treasury",
                                source_id="treasury:daily_treasury_yield_curve",
                                attempted_at=_now_iso(),
                                timeout_seconds=timeout,
                            ),
                        )
                elif treasury_error_reason is not None:
                    record_provider_attempt(
                        series_id,
                        treasury_error_reason,
                        provider_name="treasury",
                        source_id="treasury:daily_treasury_yield_curve",
                        attempted_at=_now_iso(),
                        timeout_seconds=timeout,
                        transport_details=treasury_error_details,
                    )
                    if treasury_failure_can_be_primary(series_id):
                        self._record_official_macro_diagnostic(
                            diagnostics,
                            series_id,
                            treasury_error_reason,
                            diagnostic_details=diagnostic_details,
                            details=self._official_macro_failure_details(
                                series_id,
                                treasury_error_reason,
                                provider_name="treasury",
                                source_id="treasury:daily_treasury_yield_curve",
                                attempted_at=_now_iso(),
                                timeout_seconds=timeout,
                                transport_details=treasury_error_details,
                            ),
                        )
                else:
                    record_provider_attempt(
                        series_id,
                        "missing_series",
                        provider_name="treasury",
                        source_id="treasury:daily_treasury_yield_curve",
                        attempted_at=_now_iso(),
                        timeout_seconds=timeout,
                    )
                    if treasury_failure_can_be_primary(series_id):
                        self._record_official_macro_diagnostic(
                            diagnostics,
                            series_id,
                            "missing_series",
                            diagnostic_details=diagnostic_details,
                            details=self._official_macro_failure_details(
                                series_id,
                                "missing_series",
                                provider_name="treasury",
                                source_id="treasury:daily_treasury_yield_curve",
                                attempted_at=_now_iso(),
                                timeout_seconds=timeout,
                            ),
                        )
        else:
            for series_id in missing_treasury_series_ids:
                self._record_official_macro_diagnostic(
                    diagnostics,
                    series_id,
                    "budget_exhausted",
                    diagnostic_details=diagnostic_details,
                    details=self._official_macro_failure_details(
                        series_id,
                        "budget_exhausted",
                        provider_name="treasury",
                        source_id="treasury:daily_treasury_yield_curve",
                        attempted_at=_now_iso(),
                    ),
                )
        attach_provider_attempt_details()
        self._official_macro_overlay_diagnostics = diagnostics
        self._official_macro_overlay_diagnostic_details = diagnostic_details
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

    @staticmethod
    def _official_macro_exception_reason(exc: Exception) -> str:
        return classify_official_macro_exception(exc)

    def _official_macro_failure_details(
        self,
        series_id: str,
        reason: str,
        *,
        provider_name: str | None = None,
        source_id: str | None = None,
        attempted_at: str | None = None,
        timeout_seconds: float | None = None,
        exception: Exception | None = None,
        transport_details: Any = None,
        freshness_details: Any = None,
    ) -> Dict[str, Any]:
        details = self._sanitize_official_macro_failure_details(transport_details, series_id=series_id)
        details.update(_official_daily_detail_payload(freshness_details))
        resolved_provider = provider_name or details.get("providerName") or self._provider_name_for_series(series_id, source_id)
        details["providerName"] = str(resolved_provider)
        details["requestedSeries"] = str(series_id)
        details.setdefault("attemptedAt", attempted_at or _now_iso())
        endpoint_host = self._official_macro_endpoint_host(str(details.get("providerName") or ""))
        if endpoint_host:
            details.setdefault("endpointHost", endpoint_host)
        if str(details.get("providerName") or "") == "fred":
            config_probe = fred_runtime_config_probe()
            details.setdefault("configPresent", bool(config_probe["configPresent"]))
            details.setdefault("apiKeyPresent", bool(config_probe["apiKeyPresent"]))
        if timeout_seconds is not None:
            try:
                details.setdefault("timeoutSeconds", round(float(timeout_seconds), 3))
            except (TypeError, ValueError):
                pass
        if exception is not None:
            status_code = getattr(exception, "status_code", None) or getattr(exception, "code", None)
            if status_code is not None:
                try:
                    details.setdefault("httpStatus", int(status_code))
                except (TypeError, ValueError):
                    pass
            exception_class = self._official_macro_exception_class(exception)
            if exception_class:
                details.setdefault("exceptionClass", exception_class)
            exception_chain = self._official_macro_exception_chain(exception)
            if exception_chain:
                details.setdefault("exceptionChain", exception_chain)
        return self._sanitize_official_macro_failure_details(details, series_id=series_id)

    @staticmethod
    def _provider_name_for_series(series_id: str, source_id: str | None = None) -> str:
        source_prefix = str(source_id or "").split(":", 1)[0].strip().lower()
        if source_prefix:
            return source_prefix
        if str(series_id or "").upper() in {"DGS2", "DGS10", "DGS30"}:
            return "fred"
        return "fred"

    @staticmethod
    def _source_id_for_series(series_id: str) -> str:
        return f"fred:{str(series_id or '').upper()}"

    @staticmethod
    def _official_macro_endpoint_host(provider_name: str) -> str | None:
        normalized = str(provider_name or "").strip().lower()
        if normalized == "fred":
            return "api.stlouisfed.org"
        if normalized == "treasury":
            return "home.treasury.gov"
        return None

    @staticmethod
    def _official_macro_exception_class(exc: Exception) -> str | None:
        if isinstance(exc, OfficialMacroTransportError):
            diagnostic_class = str(exc.diagnostics.get("exceptionClass") or "").strip()
            if diagnostic_class:
                return diagnostic_class
            if exc.__cause__ is None:
                return None
            exc = exc.__cause__  # type: ignore[assignment]
        reason = getattr(exc, "reason", None)
        if reason is not None and not isinstance(reason, str):
            return type(reason).__name__
        return type(exc).__name__

    @staticmethod
    def _sanitize_official_macro_failure_details(details: Any, *, series_id: str) -> Dict[str, Any]:
        if not isinstance(details, dict):
            details = {}
        safe: Dict[str, Any] = {}
        for key in (
            "configPresent",
            "apiKeyPresent",
            "endpointHost",
            "providerName",
            "caBundleSource",
            "httpStatus",
            "timeoutSeconds",
            "exceptionClass",
            "exceptionChain",
            "requestedSeries",
            "attemptedAt",
            "providerAttemptDetails",
            "officialObservationDate",
            "officialAsOf",
            "freshnessPolicy",
            "calendarAssumption",
            "maxAcceptedLagDays",
            "maxAcceptedBusinessLagDays",
            "calendarLagDays",
            "businessLagDays",
            "freshnessDecision",
            "staleReason",
        ):
            if key not in details:
                continue
            value = details.get(key)
            if key in {"configPresent", "apiKeyPresent"}:
                safe[key] = bool(value)
            elif key == "httpStatus":
                try:
                    safe[key] = int(value)
                except (TypeError, ValueError):
                    continue
            elif key == "timeoutSeconds":
                try:
                    safe[key] = round(float(value), 3)
                except (TypeError, ValueError):
                    continue
            elif key in {"maxAcceptedLagDays", "maxAcceptedBusinessLagDays", "calendarLagDays", "businessLagDays"}:
                try:
                    safe[key] = int(value)
                except (TypeError, ValueError):
                    continue
            elif key == "caBundleSource":
                source = str(value or "").strip().lower()
                if source in {"env", "certifi", "system"}:
                    safe[key] = source
            elif key == "exceptionChain":
                chain = MarketOverviewService._sanitize_exception_chain(value)
                if chain:
                    safe[key] = chain
            elif key == "providerAttemptDetails":
                attempts = MarketOverviewService._sanitize_official_macro_provider_attempt_details(
                    value,
                    series_id=series_id,
                )
                if attempts:
                    safe[key] = attempts
            else:
                text = str(value or "").strip()
                if text:
                    safe[key] = text
        safe["requestedSeries"] = str(series_id)
        return safe

    @staticmethod
    def _sanitize_official_macro_provider_attempt_details(
        value: Any,
        *,
        series_id: str,
    ) -> List[Dict[str, Any]]:
        if not isinstance(value, (list, tuple)):
            return []
        attempts: List[Dict[str, Any]] = []
        for item in value:
            attempt = MarketOverviewService._sanitize_official_macro_provider_attempt_detail(
                item,
                series_id=series_id,
            )
            if attempt:
                attempts.append(attempt)
        return attempts

    @staticmethod
    def _sanitize_official_macro_provider_attempt_detail(
        details: Any,
        *,
        series_id: str,
    ) -> Dict[str, Any]:
        if not isinstance(details, dict):
            return {}
        safe: Dict[str, Any] = {}
        for key in (
            "providerName",
            "requestedSeries",
            "reason",
            "endpointHost",
            "caBundleSource",
            "httpStatus",
            "timeoutSeconds",
            "exceptionClass",
            "exceptionChain",
            "attemptedAt",
            "configPresent",
            "apiKeyPresent",
            "officialObservationDate",
            "officialAsOf",
            "freshnessPolicy",
            "calendarAssumption",
            "maxAcceptedLagDays",
            "maxAcceptedBusinessLagDays",
            "calendarLagDays",
            "businessLagDays",
            "freshnessDecision",
            "staleReason",
        ):
            if key not in details:
                continue
            value = details.get(key)
            if key in {"configPresent", "apiKeyPresent"}:
                safe[key] = bool(value)
            elif key == "httpStatus":
                try:
                    safe[key] = int(value)
                except (TypeError, ValueError):
                    continue
            elif key == "timeoutSeconds":
                try:
                    safe[key] = round(float(value), 3)
                except (TypeError, ValueError):
                    continue
            elif key in {"maxAcceptedLagDays", "maxAcceptedBusinessLagDays", "calendarLagDays", "businessLagDays"}:
                try:
                    safe[key] = int(value)
                except (TypeError, ValueError):
                    continue
            elif key == "caBundleSource":
                source = str(value or "").strip().lower()
                if source in {"env", "certifi", "system"}:
                    safe[key] = source
            elif key == "exceptionChain":
                chain = MarketOverviewService._sanitize_exception_chain(value)
                if chain:
                    safe[key] = chain
            elif key == "reason":
                reason = str(value or "").strip().lower()
                safe[key] = (
                    reason
                    if reason == "success" or reason in OFFICIAL_OVERLAY_FAILURE_REASONS
                    else "transport_error"
                )
            else:
                text = str(value or "").strip()
                if text:
                    safe[key] = text
        safe["requestedSeries"] = str(series_id)
        provider_name = str(safe.get("providerName") or "").strip()
        reason = str(safe.get("reason") or "").strip()
        if not provider_name or not reason:
            return {}
        return safe

    @staticmethod
    def _sanitize_exception_chain(value: Any) -> List[str]:
        if isinstance(value, (list, tuple)):
            raw_values = [str(item or "").strip() for item in value]
        else:
            text = str(value or "").strip()
            raw_values = [part.strip() for part in text.replace("->", ",").split(",")]
        chain: List[str] = []
        for item in raw_values:
            if not item:
                continue
            token = item.split(":", 1)[0].strip()
            if not token or not token[0].isalpha():
                continue
            if not all(char.isalnum() or char in {".", "_"} for char in token):
                continue
            if not (
                "Error" in token
                or "Exception" in token
                or "Timeout" in token
                or "Warning" in token
                or token == "URLError"
            ):
                continue
            if token not in chain:
                chain.append(token)
        return chain

    @staticmethod
    def _official_macro_exception_chain(exc: Exception) -> List[str]:
        chain: List[str] = []
        current: Exception | None = exc
        while current is not None:
            name = type(current).__name__
            if not chain or chain[-1] != name:
                chain.append(name)
            next_exc: Exception | None = None
            if isinstance(current, OfficialMacroTransportError):
                cause = current.__cause__
                if isinstance(cause, Exception):
                    next_exc = cause
            if next_exc is None:
                cause = current.__cause__
                if isinstance(cause, Exception):
                    next_exc = cause
            if next_exc is None:
                context = current.__context__
                if isinstance(context, Exception):
                    next_exc = context
            if next_exc is None and hasattr(current, "reason") and isinstance(getattr(current, "reason"), Exception):
                next_exc = getattr(current, "reason")
            current = next_exc
        return chain

    @staticmethod
    def _official_macro_freshness_details(
        series_id: str,
        observations: List[MacroObservation],
    ) -> Dict[str, Any]:
        latest = observations[0] if observations else None
        if latest is None:
            return {}
        return _official_daily_freshness_details(
            series_id,
            latest.as_of or latest.date,
            official_observation_date=latest.date,
        )

    def _official_macro_row_failure_reason(self, series_id: str, observations: List[MacroObservation]) -> Optional[str]:
        if not observations:
            return self._official_macro_overlay_diagnostics.get(series_id)
        latest = observations[0]
        if latest.value is None:
            return self._official_macro_overlay_diagnostics.get(series_id) or "empty_response"
        freshness = get_freshness_status(
            latest.as_of or latest.date,
            "macro_rate",
            str(latest.source_id or "").split(":", 1)[0],
            False,
            source_type=str(latest.source_type or ""),
            series_id=series_id,
            official_observation_date=latest.date,
        )
        if freshness["freshness"] == "stale":
            return "stale_official_row"
        if freshness["freshness"] in {"fallback", "mock", "unavailable", "error"}:
            return self._official_macro_overlay_diagnostics.get(series_id) or "empty_response"
        return None

    def _record_official_macro_diagnostic(
        self,
        diagnostics: Dict[str, str],
        series_id: str,
        reason: str,
        *,
        diagnostic_details: Dict[str, Dict[str, Any]] | None = None,
        details: Any = None,
    ) -> None:
        normalized_reason = str(reason or "").strip().lower()
        if not normalized_reason:
            return
        if normalized_reason == "not_attempted":
            normalized_reason = "refresh_not_attempted"
        current_reason = str(diagnostics.get(series_id) or "").strip().lower()
        if current_reason == "not_attempted":
            current_reason = "refresh_not_attempted"
        if current_reason == "stale_official_row":
            return
        replaceable_reasons = {
            "",
            "cache_miss",
            "refresh_not_attempted",
            "budget_exhausted",
            "empty_response",
            "missing_series",
            "transport_error",
            "parse_error",
        }
        if normalized_reason == "stale_official_row" or current_reason in replaceable_reasons:
            diagnostics[series_id] = normalized_reason
            if diagnostic_details is not None:
                safe_details = self._sanitize_official_macro_failure_details(details, series_id=series_id)
                if safe_details:
                    diagnostic_details[series_id] = safe_details

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

    def _official_macro_overlay_item(
        self,
        symbol: str,
        label: str,
        observations: List[MacroObservation],
        *,
        series_id: str,
        unit: str,
        market: Optional[str] = None,
        value_scale: float = 1.0,
        change_scale: float = 100.0,
    ) -> tuple[Optional[Dict[str, Any]], str | None]:
        item = self._official_macro_item(
            symbol,
            label,
            observations,
            unit=unit,
            market=market,
            value_scale=value_scale,
            change_scale=change_scale,
        )
        if item is None:
            failure_reason = self._normalize_official_overlay_failure_reason(
                self._official_macro_overlay_diagnostics.get(series_id)
            ) or "empty_response"
            return None, failure_reason
        freshness = get_freshness_status(
            item.get("asOf"),
            "macro_rate",
            str(item.get("source") or ""),
            False,
            source_type=str(item.get("sourceType") or ""),
            series_id=series_id,
            official_observation_date=item.get("officialObservationDate") or item.get("officialAsOf"),
        )
        if freshness["freshness"] in {"stale", "fallback", "mock", "unavailable", "error"}:
            freshness_details = (
                _official_daily_detail_payload(freshness)
                or _official_daily_detail_payload(item.get("officialFreshnessDetails"))
            )
            self._official_macro_overlay_diagnostics.setdefault(series_id, "stale_official_row")
            self._official_macro_overlay_diagnostic_details.setdefault(
                series_id,
                self._official_macro_failure_details(
                    series_id,
                    "stale_official_row",
                    provider_name=self._provider_name_for_series(series_id, item.get("sourceId")),
                    source_id=str(item.get("sourceId") or f"fred:{series_id}"),
                    attempted_at=_now_iso(),
                    freshness_details=freshness_details,
                ),
            )
            return None, "stale_official_row"
        item.update({
            "providerAttempted": True,
            "providerClass": "official_daily",
            "officialOverlayAttempted": True,
            "officialOverlayAvailable": True,
            "officialOverlayFailureReason": None,
            "officialOverlaySeriesId": series_id,
            "officialOverlaySourceId": item.get("sourceId"),
            "activationHint": "official_daily_overlay_active",
        })
        return item, None

    def _with_official_overlay_failure(
        self,
        item: Dict[str, Any],
        reason: str | None,
        *,
        series_id: str | None = None,
    ) -> Dict[str, Any]:
        failure_reason = self._normalize_official_overlay_failure_reason(reason) or "empty_response"
        fallback_item = bool(item.get("isFallback") or item.get("fallbackUsed")) or str(item.get("source") or "").lower() in {
            "fallback",
            "mock",
            "synthetic",
        }
        fallback_suffix = "static_fallback" if fallback_item else "proxy"
        activation_hint = (
            f"official_overlay_stale_using_{fallback_suffix}"
            if failure_reason in {"official_overlay_stale", "stale_official_row"}
            else f"official_overlay_unavailable_using_{fallback_suffix}"
        )
        failure_details = (
            self._official_macro_overlay_diagnostic_details.get(series_id)
            if series_id
            else None
        )
        if series_id and not failure_details:
            failure_details = self._official_macro_failure_details(
                series_id,
                failure_reason,
                provider_name=self._provider_name_for_series(series_id),
                source_id=f"fred:{series_id}",
                attempted_at=_now_iso(),
            )
        return {
            **item,
            "officialOverlayAttempted": True,
            "officialOverlayAvailable": False,
            "officialOverlayFailureReason": failure_reason,
            **({"officialOverlaySeriesId": series_id, "officialOverlaySourceId": f"fred:{series_id}"} if series_id else {}),
            **({"officialOverlayFailureDetails": failure_details} if failure_details else {}),
            "activationHint": activation_hint,
        }

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
        freshness_details = _official_daily_freshness_details(
            latest.symbol,
            latest.as_of or latest.date,
            official_observation_date=latest.date,
        )
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
            "officialSeriesId": latest.symbol,
            "officialObservationDate": latest.date,
            "officialAsOf": latest.as_of,
            "isFallback": False,
            "risk_direction": self._risk_direction(change_percent),
            "hover_details": [source_label, f"Official as of {latest.as_of}"] if latest.as_of else [source_label],
        }
        if freshness_details:
            item["officialFreshnessDetails"] = freshness_details
            item["freshnessPolicy"] = freshness_details.get("freshnessPolicy")
            item["maxAcceptedLagDays"] = freshness_details.get("maxAcceptedLagDays")
            item["maxAcceptedBusinessLagDays"] = freshness_details.get("maxAcceptedBusinessLagDays")
            item["calendarAssumption"] = freshness_details.get("calendarAssumption")
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
        updated_at = _now_iso()
        items = [
            self._unavailable_item("CN breadth missing/unavailable", "CN_BREADTH_UNAVAILABLE", "未接入", updated_at, detail="A-share breadth provider is not configured or unavailable"),
            self._unavailable_item("Advance / decline", "ADVANCE_DECLINE_UNAVAILABLE", "未接入", updated_at),
            self._unavailable_item("New highs / lows", "HIGH_LOW_UNAVAILABLE", "未接入", updated_at),
            self._unavailable_item("Volume breadth", "VOLUME_BREADTH_UNAVAILABLE", "未接入", updated_at),
        ]
        payload = {
            "source": "unavailable",
            "sourceLabel": "未接入",
            "sourceType": "missing",
            "updatedAt": updated_at,
            "asOf": updated_at,
            "freshness": "unavailable",
            "fallbackUsed": True,
            "isFallback": True,
            "warning": "CN breadth missing/unavailable: breadth provider is not configured or unavailable.",
            "explanation": "CN breadth is missing/unavailable; no fallback breadth score or market participation metric is fabricated.",
            "items": [
                {
                    **item,
                    "source": "unavailable",
                    "sourceLabel": "未接入",
                    "sourceType": "missing",
                    "freshness": "unavailable",
                    "isFallback": True,
                    "isUnavailable": True,
                }
                for item in items
            ],
        }
        return self._with_breadth_readiness(payload, "CN")

    def _fallback_us_breadth_snapshot(
        self,
        *,
        authority_diagnostic: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        updated_at = _now_iso()
        diagnostic = dict(authority_diagnostic or build_us_breadth_missing_authority_diagnostic())
        diagnostic_reason_codes = [
            str(code)
            for code in diagnostic.get("reasonCodes") or []
            if str(code or "").strip()
        ]
        unavailable_reason = str(
            diagnostic.get("reason")
            or (diagnostic_reason_codes[0] if diagnostic_reason_codes else None)
            or US_BREADTH_MISSING_PROVIDER_REASON
        )
        route_rejected_reason_codes = list(dict.fromkeys(diagnostic_reason_codes or [unavailable_reason]))
        configured_provider_unavailable = bool(
            diagnostic.get("credentialsPresent") or diagnostic.get("providerConstructed")
        )
        warning = (
            "US breadth missing/unavailable: configured authorized breadth provider is unavailable."
            if configured_provider_unavailable
            else "US breadth missing/unavailable: official or authorized breadth provider is not configured."
        )
        unavailable_detail = (
            "Configured authorized US market breadth provider is unavailable"
            if configured_provider_unavailable
            else "Official or authorized US market breadth provider is not configured"
        )
        missing_meta = {
            "breadthClaimType": "missing_unavailable_breadth",
            "representativeSample": False,
            "broadMarketClaimAllowed": False,
            "observationOnly": True,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "sourceAuthorityReason": unavailable_reason,
            "sourceAuthorityRouteRejected": False,
            "routeRejectedReasonCodes": route_rejected_reason_codes,
            "sourceType": "missing",
            "sourceTier": "official_or_authorized_licensed_feed",
            "trustLevel": "unavailable",
            "degradationReason": unavailable_reason,
            "sourceFreshnessEvidence": {
                "freshness": "unavailable",
                "isUnavailable": True,
                "isFallback": True,
                "warning": warning,
            },
        }
        items = [
            self._unavailable_item("US breadth missing/unavailable", "US_BREADTH_UNAVAILABLE", "未接入", updated_at, detail=unavailable_detail),
            self._unavailable_item("Advance / decline", "ADVANCE_DECLINE_UNAVAILABLE", "未接入", updated_at),
            self._unavailable_item("52W high / low", "HIGH_LOW_UNAVAILABLE", "未接入", updated_at),
        ]
        payload = {
            "source": "unavailable",
            "sourceLabel": "未接入",
            "sourceType": "missing",
            "updatedAt": updated_at,
            "asOf": updated_at,
            "freshness": "unavailable",
            "fallbackUsed": True,
            "isFallback": True,
            "warning": warning,
            "authorityDiagnostics": diagnostic,
            **missing_meta,
            "items": [{**item, **missing_meta} for item in items],
        }
        return self._with_breadth_readiness(payload, "US")

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
        macro = self._temperature_panel(
            "macro",
            lambda: self._cached_payload(
                "macro",
                self._fetch_macro,
                lambda: self._fallback_overview_panel("macro", "MacroIndicatorsCard", "数据源刷新超时，当前显示备用快照"),
            ),
            lambda: self._fallback_overview_panel("macro", "MacroIndicatorsCard", "数据源刷新超时，当前显示备用快照"),
            deadline=deadline,
        )
        fed_liquidity_items = self._official_fed_liquidity_score_grade_temperature_items(macro)
        if fed_liquidity_items:
            rates["items"] = [*rates.get("items", []), *fed_liquidity_items]
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
        usd_pressure_items = [
            self._guard_market_temperature_score_input(dict(item), panel_key="fx")
            for item in macro.get("items", [])
            if isinstance(item, dict)
            and str(item.get("symbol") or "") in self.USD_PRESSURE_SERIES
        ]
        if usd_pressure_items:
            existing_symbols = {
                str(item.get("symbol") or "")
                for item in fx.get("items", [])
                if isinstance(item, dict)
            }
            fx["items"] = [
                *fx.get("items", []),
                *[
                    item
                    for item in usd_pressure_items
                    if str(item.get("symbol") or "") not in existing_symbols
                ],
            ]
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
        liquidity_context = self._market_temperature_liquidity_context()
        capital_flow_signal = liquidity_context.get("capitalFlowSignal")
        if capital_flow_signal:
            flows["capitalFlowSignal"] = copy.deepcopy(capital_flow_signal)
        official_macro_readiness = liquidity_context.get("officialMacroReadiness")
        if official_macro_readiness:
            flows["officialMacroReadiness"] = copy.deepcopy(official_macro_readiness)
        rotation_family_rollup = self._market_temperature_rotation_family_rollup()
        if rotation_family_rollup:
            sectors["rotationFamilyRollup"] = copy.deepcopy(rotation_family_rollup)
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
            **({"capitalFlowSignal": capital_flow_signal} if capital_flow_signal else {}),
            **({"officialMacroReadiness": official_macro_readiness} if official_macro_readiness else {}),
            **({"rotationFamilyRollup": rotation_family_rollup} if rotation_family_rollup else {}),
            "fallback_notice": True,
        }

    def _official_fed_liquidity_score_grade_temperature_items(self, macro: Mapping[str, Any]) -> List[Dict[str, Any]]:
        raw_items = macro.get("items") if isinstance(macro.get("items"), list) else []
        fed_items = [
            dict(item)
            for item in raw_items
            if isinstance(item, dict) and str(item.get("symbol") or "") in self.FED_LIQUIDITY_SERIES
        ]
        if not fed_items:
            return []

        cache_bundle = build_official_fed_liquidity_cache_bundle(fed_items)
        if not bool(cache_bundle.get("scoreContributionAllowed")):
            return []

        items_by_symbol = {str(item.get("symbol") or ""): item for item in fed_items}
        ordered: List[Dict[str, Any]] = []
        for symbol in self.FED_LIQUIDITY_SERIES:
            item = items_by_symbol.get(symbol)
            if item is None:
                return []
            normalized = {
                **item,
                "cacheBundleDiagnostics": copy.deepcopy(cache_bundle),
                "requiredProviderClass": "official_public.fed_liquidity",
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "sourceAuthorityReason": None,
                "routeRejectedReasonCodes": [],
                "externalProviderCalls": False,
                "cacheOnly": True,
            }
            normalized.setdefault("sourceTier", "official_public")
            normalized.setdefault("trustLevel", "score_grade")
            ordered.append(normalized)
        return ordered

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
        items = [
            self._with_temperature_input_meta(self._with_item_meta(item, category, panel), category)
            for item in panel.get("items", [])
            if isinstance(item, dict)
        ]
        if key == "rates":
            items = self._with_official_us_rates_readiness_items(items)
            items = self._with_cn_money_market_readiness_items(items)
        elif key in {"macro", "fx"}:
            items = self._with_official_usd_pressure_readiness_items(items)
        panel["items"] = [
            self._guard_market_temperature_score_input(item, panel_key=key)
            for item in items
        ]
        return self._with_temperature_input_meta(panel, category)

    @staticmethod
    def _with_official_us_rates_readiness_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rate_rows = [
            item
            for item in items
            if isinstance(item, dict) and official_us_rates_series_id(item) is not None
        ]
        if not rate_rows:
            return items

        cache_bundle = build_official_us_rates_cache_bundle(rate_rows)
        bundle_ready = bool(cache_bundle.get("readinessEligible"))
        eligible_series = {str(series_id) for series_id in cache_bundle.get("eligibleSeries") or []}
        reason = str(cache_bundle.get("degradationReason") or "us_rates_readiness_not_eligible")
        route_codes = [str(code) for code in cache_bundle.get("reasonCodes") or []]
        next_items: List[Dict[str, Any]] = []
        for item in items:
            series_id = official_us_rates_series_id(item)
            if series_id is None:
                next_items.append(item)
                continue
            row_eligible = bundle_ready and series_id in eligible_series
            normalized = {
                **item,
                "cacheBundleDiagnostics": copy.deepcopy(cache_bundle),
                "requiredProviderClass": "official_public.us_treasury_curve",
                "readinessEligible": row_eligible,
                "scoreGradeEvidenceAllowed": row_eligible,
                "cacheSafeOfficialEvidenceAllowed": row_eligible,
                "externalProviderCalls": False,
                "cacheOnly": True,
            }
            if row_eligible:
                normalized["sourceAuthorityAllowed"] = True
                normalized["scoreContributionAllowed"] = True
                normalized["sourceAuthorityReason"] = None
                normalized["routeRejectedReasonCodes"] = []
            else:
                row_reason = str(item.get("sourceAuthorityReason") or reason)
                normalized["sourceAuthorityAllowed"] = False
                normalized["scoreContributionAllowed"] = False
                normalized["sourceAuthorityReason"] = row_reason
                normalized["routeRejectedReasonCodes"] = list(
                    dict.fromkeys([*(str(code) for code in item.get("routeRejectedReasonCodes") or []), *route_codes])
                )
                normalized["excluded"] = True
                normalized["excludeReason"] = row_reason
                normalized["confidenceWeight"] = 0.0
            next_items.append(normalized)
        return next_items

    @staticmethod
    def _with_official_usd_pressure_readiness_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        usd_rows = [
            item
            for item in items
            if isinstance(item, dict) and official_usd_pressure_series_id(item) is not None
        ]
        if not usd_rows:
            return items

        cache_bundle = build_official_usd_pressure_cache_bundle(usd_rows)
        readiness_eligible = bool(cache_bundle.get("readinessEligible"))
        reason = str(cache_bundle.get("degradationReason") or "usd_pressure_readiness_not_eligible")
        route_codes = [str(code) for code in cache_bundle.get("reasonCodes") or []]
        next_items: List[Dict[str, Any]] = []
        for item in items:
            series_id = official_usd_pressure_series_id(item)
            if series_id is None:
                next_items.append(item)
                continue
            normalized = {
                **item,
                "cacheBundleDiagnostics": copy.deepcopy(cache_bundle),
                "requiredProviderClass": "official_public.usd_pressure",
                "readinessEligible": readiness_eligible,
                "scoreGradeEvidenceAllowed": readiness_eligible,
                "cacheSafeOfficialEvidenceAllowed": readiness_eligible,
                "externalProviderCalls": False,
                "cacheOnly": True,
            }
            if readiness_eligible:
                normalized["sourceAuthorityAllowed"] = True
                normalized["scoreContributionAllowed"] = True
                normalized["sourceAuthorityReason"] = None
                normalized["routeRejectedReasonCodes"] = []
            else:
                row_reason = str(item.get("sourceAuthorityReason") or reason)
                normalized["sourceAuthorityAllowed"] = False
                normalized["scoreContributionAllowed"] = False
                normalized["sourceAuthorityReason"] = row_reason
                normalized["routeRejectedReasonCodes"] = list(
                    dict.fromkeys([*(str(code) for code in item.get("routeRejectedReasonCodes") or []), *route_codes])
                )
                normalized["excluded"] = True
                normalized["excludeReason"] = row_reason
                normalized["confidenceWeight"] = 0.0
            next_items.append(normalized)
        return next_items

    @staticmethod
    def _with_cn_money_market_readiness_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cn_rows = [
            item
            for item in items
            if isinstance(item, dict) and official_cn_money_market_series_id(item) is not None
        ]
        if not cn_rows:
            return items

        cache_bundle = build_official_cn_money_market_cache_bundle(cn_rows)
        readiness_eligible = bool(cache_bundle.get("readinessEligible"))
        reason = str(
            cache_bundle.get("degradationReason")
            or "cn_money_market_readiness_not_eligible"
        )
        route_codes = [str(code) for code in cache_bundle.get("reasonCodes") or []]
        next_items: List[Dict[str, Any]] = []
        for item in items:
            series_id = official_cn_money_market_series_id(item)
            if series_id is None:
                next_items.append(item)
                continue
            normalized = {
                **item,
                "cacheBundleDiagnostics": copy.deepcopy(cache_bundle),
                "requiredProviderClass": "official_public.cn_money_market_rates",
                "readinessEligible": readiness_eligible and series_id in {"DR007", "SHIBOR_ON"},
                "scoreGradeEvidenceAllowed": readiness_eligible and series_id in {"DR007", "SHIBOR_ON"},
                "cacheSafeOfficialEvidenceAllowed": readiness_eligible and series_id in {"DR007", "SHIBOR_ON"},
                "externalProviderCalls": False,
                "cacheOnly": True,
            }
            if readiness_eligible and series_id in {"DR007", "SHIBOR_ON"}:
                normalized["sourceAuthorityAllowed"] = True
                normalized["scoreContributionAllowed"] = True
                normalized["sourceAuthorityReason"] = None
                normalized["routeRejectedReasonCodes"] = []
            else:
                normalized["sourceAuthorityAllowed"] = False
                normalized["scoreContributionAllowed"] = False
                normalized["sourceAuthorityReason"] = reason
                normalized["routeRejectedReasonCodes"] = route_codes
                normalized["excluded"] = True
                normalized["excludeReason"] = reason
                normalized["confidenceWeight"] = 0.0
            next_items.append(normalized)
        return next_items

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

    def _guard_market_temperature_score_input(
        self,
        item: Dict[str, Any],
        *,
        panel_key: str,
    ) -> Dict[str, Any]:
        if not self._is_market_temperature_score_input(panel_key, item):
            return item

        route_request = self._build_market_temperature_route_request(panel_key, item)
        route_snapshot = build_data_source_route_diagnostic_snapshot(route_request).to_dict()
        source = str(item.get("source") or "").strip().lower()
        source_type = str(item.get("sourceType") or _infer_source_type(source)).strip().lower()
        source_authority_allowed = bool(source) and source not in {"fallback", "mock", "missing", "unavailable"}
        source_authority_allowed = bool(source_authority_allowed and not item.get("isFallback") and not item.get("isUnavailable"))
        source_authority_route_rejected = False
        source_authority_reason: Optional[str] = None
        route_rejected_reason_codes: List[str] = []
        score_contribution_allowed = bool(not item.get("excluded") and float(item.get("confidenceWeight") or 0.0) > 0)

        if item.get("sourceAuthorityAllowed") is False or item.get("scoreContributionAllowed") is False:
            source_authority_allowed = False
            score_contribution_allowed = False
            source_authority_reason = str(
                item.get("sourceAuthorityReason")
                or item.get("degradationReason")
                or item.get("excludeReason")
                or MARKET_TEMPERATURE_PROVIDER_ABSENT_REASON
            )
            route_rejected_reason_codes = [str(code) for code in item.get("routeRejectedReasonCodes") or []]
        elif not source_authority_allowed:
            score_contribution_allowed = False
            source_authority_reason = MARKET_TEMPERATURE_PROVIDER_ABSENT_REASON
        elif (
            source in MARKET_TEMPERATURE_PROXY_CONTEXT_SOURCES
            or source_type in MARKET_TEMPERATURE_PROXY_CONTEXT_SOURCE_TYPES
        ):
            source_authority_allowed = False
            score_contribution_allowed = False
            source_authority_reason = MARKET_TEMPERATURE_PROXY_CONTEXT_REASON
        else:
            provider_key = self._market_temperature_route_provider_key(source)
            forbidden_provider_ids = {
                str(provider.get("providerId") or "").strip().lower()
                for provider in route_snapshot.get("forbiddenProviders", [])
                if isinstance(provider, dict)
            }
            if provider_key and provider_key in forbidden_provider_ids:
                source_authority_allowed = False
                score_contribution_allowed = False
                source_authority_route_rejected = True
                source_authority_reason = MARKET_TEMPERATURE_SOURCE_AUTHORITY_REJECTED_REASON
                route_rejected_reason_codes = list(
                    route_snapshot.get("reasonCodes", {}).get(provider_key)
                    or ("provider_not_eligible_for_scoring_route",)
                )

        normalized = {
            **item,
            "sourceAuthorityAllowed": bool(source_authority_allowed),
            "scoreContributionAllowed": bool(score_contribution_allowed),
            "sourceAuthorityRouteRejected": bool(source_authority_route_rejected),
            "sourceAuthorityReason": source_authority_reason,
            "routeRejectedReasonCodes": list(dict.fromkeys(route_rejected_reason_codes)),
            "sourceAuthorityRouter": route_snapshot,
        }
        if source_authority_route_rejected:
            normalized["isReliable"] = False
            normalized["excluded"] = True
            normalized["excludeReason"] = MARKET_TEMPERATURE_SOURCE_AUTHORITY_REJECTED_REASON
            normalized["confidenceWeight"] = 0.0
        return normalized

    def _build_market_briefing_source_authority_diagnostics(self, inputs: Mapping[str, Any]) -> Dict[str, Any]:
        diagnostics: List[Dict[str, Any]] = []
        total_input_count = 0
        authoritative_input_count = 0
        route_rejected_input_count = 0

        for panel_key in ("indices", "breadth", "flows", "sectors", "rates", "fx", "futures", "sentiment", "crypto"):
            panel = inputs.get(panel_key)
            if not isinstance(panel, Mapping):
                continue
            panel_items = panel.get("items") if isinstance(panel.get("items"), list) else []
            for raw_item in panel_items:
                if not isinstance(raw_item, dict):
                    continue
                total_input_count += 1
                item = self._guard_market_briefing_evidence_input(dict(raw_item), panel_key=panel_key)
                if item.get("sourceAuthorityAllowed"):
                    authoritative_input_count += 1
                    continue
                if item.get("sourceAuthorityRouteRejected"):
                    route_rejected_input_count += 1
                diagnostics.append(
                    {
                        "panelKey": panel_key,
                        "key": item.get("key") or item.get("symbol") or item.get("name"),
                        "symbol": item.get("symbol"),
                        "name": item.get("name"),
                        "source": item.get("source"),
                        "sourceType": item.get("sourceType"),
                        "freshness": item.get("freshness"),
                        "sourceAuthorityAllowed": bool(item.get("sourceAuthorityAllowed")),
                        "scoreContributionAllowed": bool(item.get("scoreContributionAllowed")),
                        "sourceAuthorityRouteRejected": bool(item.get("sourceAuthorityRouteRejected")),
                        "sourceAuthorityReason": item.get("sourceAuthorityReason"),
                        "routeRejectedReasonCodes": list(item.get("routeRejectedReasonCodes") or []),
                        "sourceAuthorityRouter": item.get("sourceAuthorityRouter"),
                    }
                )

        return {
            "useCase": "market_briefing",
            "totalInputCount": total_input_count,
            "authoritativeInputCount": authoritative_input_count,
            "nonAuthoritativeInputCount": total_input_count - authoritative_input_count,
            "routeRejectedInputCount": route_rejected_input_count,
            "items": diagnostics,
        }

    def _guard_market_briefing_evidence_input(
        self,
        item: Dict[str, Any],
        *,
        panel_key: str,
    ) -> Dict[str, Any]:
        route_request = self._build_market_briefing_route_request(panel_key, item)
        route_snapshot = build_data_source_route_diagnostic_snapshot(route_request).to_dict()
        source = str(item.get("source") or "").strip().lower()
        source_type = str(item.get("sourceType") or _infer_source_type(source)).strip().lower()
        source_authority_allowed = bool(source) and source not in {"fallback", "mock", "missing", "unavailable"}
        source_authority_allowed = bool(source_authority_allowed and not item.get("isFallback") and not item.get("isUnavailable"))
        source_authority_route_rejected = False
        source_authority_reason: Optional[str] = None
        route_rejected_reason_codes: List[str] = []
        score_contribution_allowed = bool(item.get("scoreContributionAllowed"))

        if not source_authority_allowed:
            score_contribution_allowed = False
            source_authority_reason = MARKET_TEMPERATURE_PROVIDER_ABSENT_REASON
        elif (
            source in MARKET_TEMPERATURE_PROXY_CONTEXT_SOURCES
            or source_type in MARKET_TEMPERATURE_PROXY_CONTEXT_SOURCE_TYPES
        ):
            source_authority_allowed = False
            score_contribution_allowed = False
            source_authority_reason = MARKET_TEMPERATURE_PROXY_CONTEXT_REASON
        else:
            provider_key = self._market_temperature_route_provider_key(source)
            forbidden_provider_ids = {
                str(provider.get("providerId") or "").strip().lower()
                for provider in route_snapshot.get("forbiddenProviders", [])
                if isinstance(provider, dict)
            }
            if provider_key and provider_key in forbidden_provider_ids:
                source_authority_allowed = False
                score_contribution_allowed = False
                source_authority_route_rejected = True
                source_authority_reason = MARKET_TEMPERATURE_SOURCE_AUTHORITY_REJECTED_REASON
                route_rejected_reason_codes = list(
                    route_snapshot.get("reasonCodes", {}).get(provider_key)
                    or ("provider_not_eligible_for_authority_route",)
                )

        return {
            **item,
            "sourceAuthorityAllowed": bool(source_authority_allowed),
            "scoreContributionAllowed": bool(score_contribution_allowed),
            "sourceAuthorityRouteRejected": bool(source_authority_route_rejected),
            "sourceAuthorityReason": source_authority_reason,
            "routeRejectedReasonCodes": list(dict.fromkeys(route_rejected_reason_codes)),
            "sourceAuthorityRouter": route_snapshot,
        }

    @staticmethod
    def _is_market_temperature_score_input(panel_key: str, item: Mapping[str, Any]) -> bool:
        if panel_key == "sectors":
            return _has_valid_market_value(dict(item))
        score_symbols = MARKET_TEMPERATURE_SCORE_DRIVING_SYMBOLS.get(panel_key)
        if not score_symbols:
            return False
        symbol = str(item.get("symbol") or item.get("key") or "").strip().upper()
        return symbol in score_symbols

    def _build_market_temperature_route_request(
        self,
        panel_key: str,
        item: Mapping[str, Any],
    ) -> DataSourceRouteRequest:
        symbol = str(item.get("symbol") or item.get("key") or "").strip() or None
        freshness_need = str(item.get("freshness") or "").strip().lower() or "live"
        market = "US"
        asset_type = "equity"
        capability = "quote"
        product_id = None

        if panel_key == "indices":
            market = "HK" if symbol in MARKET_TEMPERATURE_HK_INDEX_SYMBOLS else "CN"
            asset_type = "equity_index"
        elif panel_key in {"breadth", "flows"}:
            market = "CN"
            asset_type = "equity"
            capability = "breadth"
        elif panel_key == "rates":
            if symbol == "VIX":
                asset_type = "volatility"
                capability = "volatility"
            elif symbol in {"DR007", "SHIBOR"}:
                market = "CN"
                asset_type = "macro_rate"
                capability = "macro_rate"
            else:
                asset_type = "macro_rate"
                capability = "macro_rate"
        elif panel_key == "fx":
            if symbol in {"USD_TWI", "DXY", "USDCNH"}:
                market = "forex"
                asset_type = "forex"
            else:
                market = "global"
                asset_type = "commodity"
        elif panel_key == "futures":
            asset_type = "equity_index"
        elif panel_key == "sentiment":
            asset_type = "sentiment"
            capability = "sentiment"
        elif panel_key == "crypto":
            market = "crypto"
            asset_type = "crypto"
            capability = "crypto_ticker"
            product_id = f"{symbol}-USD" if symbol else None

        return DataSourceRouteRequest(
            market=market,
            asset_type=asset_type,
            use_case="market_temperature",
            capability=capability,
            freshness_need=freshness_need,
            scoring_allowed=True,
            symbol=symbol,
            product_id=product_id,
            allow_network=False,
            reproducibility_required=False,
        )

    def _build_market_briefing_route_request(
        self,
        panel_key: str,
        item: Mapping[str, Any],
    ) -> DataSourceRouteRequest:
        symbol = str(item.get("symbol") or item.get("key") or "").strip() or None
        freshness_need = str(item.get("freshness") or "").strip().lower() or "live"
        market = "US"
        asset_type = "equity"
        capability = "quote"
        product_id = None

        if panel_key == "indices":
            market = "HK" if symbol in MARKET_TEMPERATURE_HK_INDEX_SYMBOLS else "CN"
            asset_type = "equity_index"
            capability = "index_quote"
        elif panel_key in {"breadth", "flows"}:
            market = "CN"
            asset_type = "equity"
            capability = "breadth"
        elif panel_key == "rates":
            capability = "macro_rate"
            if symbol == "VIX":
                market = "US"
                asset_type = "volatility"
                capability = "volatility"
            elif symbol in {"DR007", "SHIBOR", "LPR", "CN10Y"}:
                market = "CN"
                asset_type = "macro_rate"
            else:
                market = "US"
                asset_type = "macro_rate"
        elif panel_key == "fx":
            capability = "fx"
            if symbol in {"USD_TWI", "DXY", "USDCNH", "USDJPY", "EURUSD"}:
                market = "forex"
                asset_type = "forex"
            else:
                market = "global"
                asset_type = "commodity"
        elif panel_key == "futures":
            capability = "futures"
            asset_type = "equity_index"
            if symbol in {"CN00Y"}:
                market = "CN"
            elif symbol in {"HSI_F"}:
                market = "HK"
            elif symbol in {"NQ", "ES", "YM", "RTY"}:
                market = "US"
            else:
                market = "global"
        elif panel_key == "sentiment":
            asset_type = "sentiment"
            capability = "sentiment"
        elif panel_key == "crypto":
            market = "crypto"
            asset_type = "crypto"
            capability = "crypto_ticker"
            product_id = f"{symbol}-USD" if symbol else None

        return DataSourceRouteRequest(
            market=market,
            asset_type=asset_type,
            use_case="market_briefing",
            capability=capability,
            freshness_need=freshness_need,
            scoring_allowed=False,
            symbol=symbol,
            product_id=product_id,
            allow_network=False,
            reproducibility_required=False,
        )

    @staticmethod
    def _market_temperature_route_provider_key(source: str) -> Optional[str]:
        if source in {"akshare", "akshare_existing_baseline"}:
            return "akshare"
        if source in {"pytdx", "pytdx_existing_baseline"}:
            return "pytdx_existing_baseline"
        return source or None

    def _market_temperature_input_confidence(self, meta: Dict[str, Any], category: str = "") -> float:
        if bool(meta.get("sourceAuthorityRouteRejected")):
            return 0.0
        if meta.get("sourceAuthorityAllowed") is False and meta.get("scoreContributionAllowed") is False:
            return 0.0
        return self._market_data_confidence(meta, category)

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
                    confidence = self._market_temperature_input_confidence(
                        item if isinstance(item, dict) else {},
                        self._category_for_cache_key(key),
                    )
                    confidences.append(confidence)
                    if confidence > 0:
                        reliable_count += 1
                    else:
                        fallback_count += 1
                        excluded_count += 1
                continue
            if isinstance(panel, dict):
                confidence = self._market_temperature_input_confidence(
                    panel,
                    self._category_for_cache_key(key),
                )
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
                    isinstance(item, dict) and self._market_temperature_input_confidence(item, category) > 0
                    for item in panel_items
                ):
                    reliable_panel_count += 1
                continue
            if self._market_temperature_input_confidence(panel, category) > 0:
                reliable_panel_count += 1

        reliable_count = int(trust.get("reliableInputCount") or 0)
        fallback_count = int(trust.get("fallbackInputCount") or 0)
        total_count = reliable_count + fallback_count
        raw_coverage = reliable_count / total_count if total_count else 0.0
        panel_factor = min(1.0, reliable_panel_count / 3.0) if reliable_panel_count else 0.0
        item_factor = min(1.0, reliable_count / 5.0) if reliable_count else 0.0
        raw_confidence = float(trust.get("confidence") or 0.0)
        trust_gate_coverage = raw_coverage
        if (
            reliable_count >= MARKET_TEMPERATURE_REQUIRED_RELIABLE_INPUT_COUNT
            and reliable_panel_count >= MARKET_TEMPERATURE_REQUIRED_RELIABLE_PANEL_COUNT
            and raw_confidence > MARKET_TEMPERATURE_MIN_COVERAGE
        ):
            trust_gate_coverage = max(trust_gate_coverage, min(panel_factor, item_factor))
        confidence = round(min(raw_confidence, raw_coverage, panel_factor, item_factor), 2)
        has_required_reliable_inputs = bool(
            trust.get("isReliable")
            and reliable_count >= MARKET_TEMPERATURE_REQUIRED_RELIABLE_INPUT_COUNT
            and reliable_panel_count >= MARKET_TEMPERATURE_REQUIRED_RELIABLE_PANEL_COUNT
            and raw_coverage >= MARKET_TEMPERATURE_MIN_COVERAGE
        )
        trust_gate = self._market_intelligence_trust_gate(inputs, coverage=trust_gate_coverage)
        temperature_available = bool(has_required_reliable_inputs and trust_gate["isReliable"])
        conclusion_allowed = bool(temperature_available and trust_gate["conclusionAllowed"])
        insufficient_reliable_inputs = not has_required_reliable_inputs
        disabled_reason = None
        if not temperature_available:
            if insufficient_reliable_inputs:
                disabled_reason = "insufficient_reliable_inputs"
            elif not trust_gate["conclusionAllowed"]:
                disabled_reason = "strong_conclusion_blocked"
            else:
                disabled_reason = "trust_gate_capped"
        return {
            **trust,
            "confidence": round(min(confidence, float(trust_gate["scoreCap"])), 2),
            "isReliable": temperature_available,
            "temperatureAvailable": temperature_available,
            "insufficientReliableInputs": insufficient_reliable_inputs,
            "reliablePanelCount": reliable_panel_count,
            "requiredReliablePanelCount": MARKET_TEMPERATURE_REQUIRED_RELIABLE_PANEL_COUNT,
            "requiredReliableInputCount": MARKET_TEMPERATURE_REQUIRED_RELIABLE_INPUT_COUNT,
            "disabledReason": disabled_reason,
            "unavailableReason": disabled_reason,
            "trustLevel": trust_gate["trustLevel"],
            "sourceTier": trust_gate["sourceTier"],
            "degradationReasons": trust_gate["degradationReasons"],
            "scoreCap": trust_gate["scoreCap"],
            "conclusionAllowed": conclusion_allowed,
        }

    @staticmethod
    def _market_temperature_disabled_state_meta(trust: Dict[str, Any]) -> Dict[str, Any]:
        if trust.get("temperatureAvailable"):
            return {}
        reliable_count = int(trust.get("reliableInputCount") or 0)
        freshness = "fallback" if reliable_count <= 0 else "partial"
        disabled_reason = trust.get("disabledReason") or "insufficient_reliable_inputs"
        return {
            "temperatureAvailable": False,
            "disabledReason": disabled_reason,
            "unavailableReason": trust.get("unavailableReason") or disabled_reason,
            "insufficientReliableInputs": bool(trust.get("insufficientReliableInputs", True)),
            "sourceFreshnessEvidence": {
                "freshness": freshness,
                "isFallback": reliable_count <= 0,
                "isPartial": reliable_count > 0,
                "warning": INSUFFICIENT_MARKET_DATA_WARNING,
            },
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
                    if self._market_temperature_input_confidence(item, category) > 0:
                        source_payloads.append(dict(item))
                    else:
                        degraded_payloads.append(dict(item))
                continue
            if self._is_trust_gate_stale_input(panel):
                degradation_reasons.append("stale_source")
            if self._market_temperature_input_confidence(panel, category) > 0:
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
                if isinstance(item, dict) and self._market_temperature_input_confidence(
                    item,
                    self._category_for_cache_key(key),
                ) > 0
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
        dxy_change = self._item_change(inputs.get("fx", {}).get("items", []), "USD_TWI")
        if dxy_change is None:
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
            if not self._temperature_score_contribution_allowed(item):
                continue
            if symbols is not None and str(item.get("symbol")) not in symbols:
                continue
            value = self._clean_number(item.get("changePercent", item.get("change_pct")))
            if value is not None:
                values.append(value)
        return sum(values) / len(values) if values else None

    def _item_value(self, items: List[Dict[str, Any]], symbol: str) -> Optional[float]:
        for item in items:
            if not self._temperature_score_contribution_allowed(item):
                continue
            if str(item.get("symbol")) == symbol:
                return self._clean_number(item.get("value", item.get("price")))
        return None

    def _item_change(self, items: List[Dict[str, Any]], symbol: str) -> Optional[float]:
        for item in items:
            if not self._temperature_score_contribution_allowed(item):
                continue
            if str(item.get("symbol")) == symbol:
                return self._clean_number(item.get("changePercent", item.get("change_pct", item.get("change"))))
        return None

    @staticmethod
    def _temperature_score_contribution_allowed(item: Mapping[str, Any]) -> bool:
        return item.get("scoreContributionAllowed") is not False

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
                proxy_item = self._quote_proxy_item(symbol, label, unit, updated_at)
                items.append(proxy_item or self._quote_unavailable_item(label, symbol, unit, updated_at))
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

    def _quote_proxy_item(self, symbol: str, label: str, unit: str, updated_at: str) -> Dict[str, Any] | None:
        if symbol != "SPX":
            return None
        try:
            quote = self._latest_quote("SPY")
        except Exception:
            return None
        change_pct = quote.get("change_pct")
        return {
            "symbol": symbol,
            "label": "S&P 500 proxy (SPY ETF)",
            "value": quote.get("value"),
            "unit": "USD",
            "change_pct": change_pct,
            "changePercent": change_pct,
            "risk_direction": self._risk_direction(change_pct),
            "trend": quote.get("trend", []),
            "source": "yfinance_proxy",
            "sourceLabel": self._source_label("yfinance_proxy"),
            "sourceType": "unofficial_proxy",
            "updatedAt": updated_at,
            "asOf": quote.get("asOf") or updated_at,
            "proxyFor": symbol,
            "proxySymbol": "SPY",
            "proxyLabel": label,
            "isProxy": True,
            "isFallback": False,
            "proxyFallback": True,
            "warning": "Official SPX quote unavailable; showing SPY ETF proxy.",
            "degradationReason": "official_index_unavailable_using_etf_proxy",
        }

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
                {
                    "symbol": "ETF",
                    "label": "ETF flow proxy",
                    "value": 0.0,
                    "unit": "B USD",
                    "change_pct": 0.0,
                    "trend": [0.0, 0.0],
                    "observationOnly": True,
                    "sourceAuthorityAllowed": False,
                    "scoreContributionAllowed": False,
                    "sourceAuthorityReason": "static_etf_flow_proxy_fallback",
                },
                {
                    "symbol": "INSTITUTIONAL",
                    "label": "Institutional pressure proxy",
                    "value": 0.0,
                    "unit": "B USD",
                    "change_pct": 0.0,
                    "trend": [0.0, 0.0],
                    "observationOnly": True,
                    "sourceAuthorityAllowed": False,
                    "scoreContributionAllowed": False,
                    "sourceAuthorityReason": "static_etf_flow_proxy_fallback",
                },
                {
                    "symbol": "INDUSTRY",
                    "label": "Industry breadth proxy",
                    "value": 0.0,
                    "unit": "score",
                    "change_pct": 0.0,
                    "trend": [0.0, 0.0],
                    "observationOnly": True,
                    "sourceAuthorityAllowed": False,
                    "scoreContributionAllowed": False,
                    "sourceAuthorityReason": "static_etf_flow_proxy_fallback",
                },
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
