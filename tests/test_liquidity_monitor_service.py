# -*- coding: utf-8 -*-
"""Tests for the cache-only liquidity monitor advisory service."""

from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

from api.v1.schemas.liquidity_monitor import LiquidityMonitorResponse
from src.services.cn_hk_flow_contracts import AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID
from src.services.cn_money_market_rates_contracts import (
    OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
)
from src.services.liquidity_monitor_service import LiquidityMonitorService, PanelState
from src.services.market_cache import MarketCache
from src.storage import DatabaseManager


CN_TZ = timezone(timedelta(hours=8))
REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests/fixtures/liquidity_monitor"
LIQUIDITY_MONITOR_SERVICE_PATH = REPO_ROOT / "src/services/liquidity_monitor_service.py"
FROZEN_GOLDEN_NOW = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ)
FROZEN_GOLDEN_NOW_ISO = FROZEN_GOLDEN_NOW.isoformat(timespec="seconds")
LIQUIDITY_GOLDEN_FIXTURE_NAMES = (
    "official_cached_macro_rates_context.json",
    "mixed_official_proxy_context.json",
    "missing_macro_rates_proxy_fallback_context.json",
    "credit_stress_observation_only_context.json",
    "delayed_proxy_fx_commodities_context.json",
    "provider_unavailable_stale_malformed_context.json",
)
FORBIDDEN_PUBLIC_TERMS = (
    "authorization",
    "bearer ",
    "cookie",
    "set-cookie",
    "session_id",
    "api_key",
    "access_token",
    "refresh_token",
    "password",
    "credential",
    "raw_provider_payload",
    "provider_payload",
    "stack_trace",
    "traceback",
    "http://",
    "https://",
)
FORBIDDEN_LIQUIDITY_MONITOR_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "yfinance",
)
FORBIDDEN_LIQUIDITY_MONITOR_CACHE_PATTERNS = (
    r"\bself\.cache\.get_or_refresh\(",
    r"\bmarket_cache\.get_or_refresh\(",
    r"\bself\.cache\.set\(",
    r"\bmarket_cache\.set\(",
)


class _FakeSeries:
    def __init__(self, values: list[Any]) -> None:
        self._values = values

    def tolist(self) -> list[Any]:
        return list(self._values)


class _FakeHistoryFrame:
    def __init__(self, closes: list[float], *, volumes: list[float] | None = None, index: list[datetime] | None = None) -> None:
        self._data: Dict[str, list[Any]] = {"Close": list(closes)}
        if volumes is not None:
            self._data["Volume"] = list(volumes)
        self.index = list(index or [])

    @property
    def empty(self) -> bool:
        return not self._data.get("Close")

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __getitem__(self, key: str) -> _FakeSeries:
        return _FakeSeries(self._data[key])


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _indicators_by_key(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {str(item["key"]): item for item in payload["indicators"]}


def _iter_strings(value: Any):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _iter_strings(item)
        return
    if isinstance(value, list):
        for item in value:
            yield from _iter_strings(item)
        return
    if isinstance(value, str):
        yield value


def _assert_no_sensitive_public_payload(value: Any) -> None:
    public_text = "\n".join(_iter_strings(value)).lower()
    for term in FORBIDDEN_PUBLIC_TERMS:
        assert term not in public_text


@pytest.fixture()
def isolated_db(tmp_path: Path):
    DatabaseManager.reset_instance()
    DatabaseManager(db_url=f"sqlite:///{tmp_path / 'liquidity-monitor.sqlite'}")
    yield DatabaseManager.get_instance()
    DatabaseManager.reset_instance()


@pytest.fixture(autouse=True)
def mock_macro_quote_transport():
    with patch(
        "src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame",
        return_value=_FakeHistoryFrame([]),
        create=True,
    ):
        yield


def _cache_entry(
    *,
    source: str,
    freshness: str,
    items: list[Dict[str, Any]],
    updated_at: str,
    as_of: str,
    is_fallback: bool = False,
    warning: str | None = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "source": source,
        "freshness": freshness,
        "items": items,
        "updatedAt": updated_at,
        "asOf": as_of,
        "isFallback": is_fallback,
        "fallbackUsed": is_fallback,
        "warning": warning,
    }
    return payload


def _official_vix_item(
    *,
    value: float = 18.22,
    change_percent: float = -4.66,
    as_of: str = FROZEN_GOLDEN_NOW_ISO,
    freshness: str = "cached",
    symbol: str = "VIX",
) -> Dict[str, Any]:
    observation_date = as_of.split("T", 1)[0]
    return {
        "symbol": symbol,
        "label": "VIX",
        "value": value,
        "changePercent": change_percent,
        "source": "fred",
        "sourceId": "fred:VIXCLS",
        "sourceType": "official_public",
        "sourceTier": "official_public",
        "sourceLabel": "FRED VIXCLS",
        "officialSeriesId": "VIXCLS",
        "officialObservationDate": observation_date,
        "officialAsOf": observation_date,
        "sourceAuthorityAllowed": True,
        "scoreContributionAllowed": True,
        "freshness": freshness,
        "asOf": as_of,
        "updatedAt": as_of,
        "sourceFreshnessEvidence": {
            "freshness": freshness,
            "freshnessPolicy": "official_daily_us_weekday_t_plus_1",
            "externalProviderCalls": False,
            "isFallback": False,
            "isStale": False,
            "isUnavailable": False,
        },
    }


FED_LIQUIDITY_SERIES_BY_SYMBOL = {
    "FED_ASSETS": "WALCL",
    "FED_RRP": "RRPONTSYD",
    "TGA": "WTREGEN",
    "RESERVES": "WRESBAL",
}
AUTHORIZED_US_BREADTH_SYMBOLS = (
    "ADVANCERS",
    "DECLINERS",
    "UNCHANGED",
    "ADVANCE_DECLINE_RATIO",
    "NEW_HIGHS",
    "NEW_LOWS",
    "HIGH_LOW_RATIO",
)
AUTHORIZED_US_BREADTH_LABELS = {
    "ADVANCERS": "Advancers",
    "DECLINERS": "Decliners",
    "UNCHANGED": "Unchanged",
    "ADVANCE_DECLINE_RATIO": "Advance / Decline Ratio",
    "NEW_HIGHS": "New Highs",
    "NEW_LOWS": "New Lows",
    "HIGH_LOW_RATIO": "High / Low Ratio",
}
AUTHORIZED_US_BREADTH_UNITS = {
    "ADVANCERS": "stocks",
    "DECLINERS": "stocks",
    "UNCHANGED": "stocks",
    "ADVANCE_DECLINE_RATIO": "ratio",
    "NEW_HIGHS": "stocks",
    "NEW_LOWS": "stocks",
    "HIGH_LOW_RATIO": "ratio",
}


def _fed_liquidity_macro_item(
    symbol: str,
    *,
    value: Any = 1.0,
    change_percent: float | None = 0.1,
    freshness: str = "cached",
    source_authority_allowed: bool = True,
    score_contribution_allowed: bool = True,
    is_stale: bool = False,
    is_unavailable: bool = False,
) -> Dict[str, Any]:
    series_id = FED_LIQUIDITY_SERIES_BY_SYMBOL[symbol]
    policy = (
        "official_daily_us_weekday_t_plus_1"
        if series_id == "RRPONTSYD"
        else "official_weekly_fed_liquidity_t_plus_7"
    )
    base_as_of = "2026-05-20T16:15:00+08:00"
    return {
        "symbol": symbol,
        "label": symbol,
        "value": value,
        "changePercent": change_percent,
        "source": "fred",
        "sourceId": f"fred:{series_id}",
        "sourceType": "official_public",
        "sourceLabel": f"FRED {series_id}",
        "sourceTier": "official_public",
        "trustLevel": "reliable",
        "officialSeriesId": series_id,
        "officialObservationDate": "2026-05-20",
        "officialAsOf": "2026-05-20",
        "sourceAuthorityAllowed": source_authority_allowed,
        "scoreContributionAllowed": score_contribution_allowed,
        "routeRejectedReasonCodes": [],
        "unit": "USD mn",
        "freshness": freshness,
        "asOf": base_as_of,
        "updatedAt": base_as_of,
        "isStale": is_stale,
        "isUnavailable": is_unavailable,
        "isFallback": False,
        "sourceFreshnessEvidence": {
            "freshness": freshness,
            "freshnessPolicy": policy,
            "externalProviderCalls": False,
            "isFallback": False,
            "isStale": is_stale,
            "isUnavailable": is_unavailable,
        },
    }


def _data036_official_rate_item(
    symbol: str,
    series_id: str,
    *,
    freshness: str = "cached",
    source_authority_allowed: bool = True,
    score_contribution_allowed: bool = True,
    is_stale: bool = False,
    include_freshness_evidence: bool = True,
) -> Dict[str, Any]:
    base_as_of = "2026-05-20T16:15:00+08:00"
    item: Dict[str, Any] = {
        "symbol": symbol,
        "label": symbol,
        "value": 1.0,
        "changePercent": 0.0,
        "source": "treasury" if series_id.startswith("DGS") else "fred",
        "sourceId": f"{'treasury' if series_id.startswith('DGS') else 'fred'}:{series_id}",
        "sourceType": "official_public",
        "sourceLabel": f"{'US Treasury' if series_id.startswith('DGS') else 'FRED'} {series_id}",
        "sourceTier": "official_public",
        "trustLevel": "reliable",
        "unit": "%",
        "freshness": freshness,
        "asOf": base_as_of,
        "updatedAt": base_as_of,
        "officialSeriesId": series_id,
        "officialObservationDate": "2026-05-20",
        "officialAsOf": "2026-05-20",
        "sourceAuthorityAllowed": source_authority_allowed,
        "scoreContributionAllowed": score_contribution_allowed,
        "routeRejectedReasonCodes": [],
        "isStale": is_stale,
        "isUnavailable": False,
        "isFallback": False,
    }
    if include_freshness_evidence:
        item["sourceFreshnessEvidence"] = {
            "freshness": freshness,
            "freshnessPolicy": "official_daily_us_weekday_t_plus_1",
            "externalProviderCalls": False,
            "isFallback": False,
            "isStale": is_stale,
            "isUnavailable": False,
        }
    if not source_authority_allowed or not score_contribution_allowed:
        item["sourceAuthorityReason"] = "source_authority_not_explicit"
        item["routeRejectedReasonCodes"] = ["source_authority_not_explicit"]
    return item


def _data036_official_credit_item() -> Dict[str, Any]:
    base_as_of = "2026-05-20T16:15:00+08:00"
    return {
        "symbol": "CREDIT",
        "label": "Credit spreads",
        "value": 1.0,
        "change": 0.0,
        "changePercent": 0.0,
        "source": "fred",
        "sourceId": "fred:BAMLH0A0HYM2",
        "sourceType": "official_public",
        "sourceLabel": "FRED ICE BofA US High Yield Index Option-Adjusted Spread",
        "sourceTier": "official_public",
        "trustLevel": "reliable",
        "officialSeriesId": "BAMLH0A0HYM2",
        "officialObservationDate": "2026-05-20",
        "officialAsOf": "2026-05-20",
        "unit": "bps",
        "freshness": "cached",
        "asOf": base_as_of,
        "updatedAt": base_as_of,
        "observationOnly": True,
        "includedInScore": False,
        "sourceAuthorityAllowed": True,
        "scoreContributionAllowed": False,
    }


def _seed_data036_official_risk_context(
    service: LiquidityMonitorService,
    *,
    include_vix: bool = True,
    missing_rate_series: str | None = None,
    stale_rate_series: str | None = None,
    cache_only_vix_without_authority_proof: bool = False,
    stale_vix: bool = False,
    stale_fed_liquidity: bool = False,
    include_credit: bool = True,
) -> None:
    base_as_of = "2026-05-20T16:15:00+08:00"
    macro_items: list[Dict[str, Any]] = []
    if include_vix:
        vix_freshness = "stale" if stale_vix else "cached"
        vix_item = _official_vix_item(
            value=1.0,
            change_percent=0.0,
            as_of=base_as_of,
            freshness=vix_freshness,
        )
        if stale_vix:
            vix_item["isStale"] = True
            vix_item["sourceFreshnessEvidence"]["isStale"] = True
        if cache_only_vix_without_authority_proof:
            vix_item.pop("sourceFreshnessEvidence", None)
            vix_item["sourceAuthorityAllowed"] = False
            vix_item["scoreContributionAllowed"] = False
            vix_item["sourceAuthorityReason"] = "source_authority_not_explicit"
            vix_item["routeRejectedReasonCodes"] = ["source_authority_not_explicit"]
        macro_items.append(vix_item)

    for symbol, series_id in (("US2Y", "DGS2"), ("US10Y", "DGS10"), ("US30Y", "DGS30")):
        if series_id == missing_rate_series:
            continue
        is_stale = series_id == stale_rate_series
        macro_items.append(
            _data036_official_rate_item(
                symbol,
                series_id,
                freshness="stale" if is_stale else "cached",
                is_stale=is_stale,
            )
        )

    for symbol in FED_LIQUIDITY_SERIES_BY_SYMBOL:
        macro_items.append(
            _fed_liquidity_macro_item(
                symbol,
                value=1.0,
                change_percent=0.0,
                freshness="stale" if stale_fed_liquidity else "cached",
                is_stale=stale_fed_liquidity,
            )
        )

    if include_credit:
        macro_items.append(_data036_official_credit_item())

    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="stale" if stale_vix or stale_rate_series or stale_fed_liquidity else "cached",
            items=macro_items,
            updated_at=base_as_of,
            as_of=base_as_of,
        ),
        ttl_seconds=30,
    )


def _authorized_us_breadth_item(
    symbol: str,
    value: Any,
    *,
    as_of: str,
    freshness: str = "delayed",
    source: str = "polygon_us_grouped_daily",
    source_type: str = "authorized_licensed_feed",
    source_tier: str = "authorized_licensed_feed",
    trust_level: str = "score_grade_when_configured",
    source_authority_allowed: bool = True,
    score_contribution_allowed: bool = True,
    source_authority_reason: str | None = None,
    route_rejected_reason_codes: list[str] | None = None,
    is_stale: bool = False,
    is_fallback: bool = False,
) -> Dict[str, Any]:
    return {
        "symbol": symbol,
        "label": AUTHORIZED_US_BREADTH_LABELS[symbol],
        "value": value,
        "source": source,
        "sourceLabel": "Polygon grouped daily US equities (computed breadth)",
        "sourceType": source_type,
        "sourceTier": source_tier,
        "trustLevel": trust_level,
        "sourceAuthorityAllowed": source_authority_allowed,
        "scoreContributionAllowed": score_contribution_allowed,
        "sourceAuthorityReason": source_authority_reason,
        "routeRejectedReasonCodes": list(route_rejected_reason_codes or []),
        "unit": AUTHORIZED_US_BREADTH_UNITS[symbol],
        "freshness": freshness,
        "asOf": as_of,
        "updatedAt": as_of,
        "isFallback": is_fallback,
        "isStale": is_stale,
        "isUnavailable": value is None,
    }


def _authorized_us_breadth_cache_payload(
    *,
    as_of: str,
    items: list[Dict[str, Any]],
    freshness: str = "delayed",
    source: str = "polygon_us_grouped_daily",
    source_type: str = "authorized_licensed_feed",
    source_tier: str = "authorized_licensed_feed",
    trust_level: str = "score_grade_when_configured",
    source_authority_allowed: bool = True,
    score_contribution_allowed: bool = True,
    source_authority_reason: str | None = None,
    route_rejected_reason_codes: list[str] | None = None,
    observation_only: bool = False,
    is_partial: bool = False,
    is_fallback: bool = False,
    fulfilled_metrics: list[str] | None = None,
    missing_metrics: list[str] | None = None,
) -> Dict[str, Any]:
    fulfilled = list(fulfilled_metrics or [])
    missing = list(missing_metrics or [])
    if not fulfilled and not missing:
        seen_symbols = {str(item.get("symbol") or "") for item in items if isinstance(item, dict)}
        fulfilled = [symbol for symbol in AUTHORIZED_US_BREADTH_SYMBOLS if symbol in seen_symbols]
        missing = [symbol for symbol in AUTHORIZED_US_BREADTH_SYMBOLS if symbol not in seen_symbols]
    codes = list(route_rejected_reason_codes or [])
    return {
        "source": source,
        "sourceLabel": "Polygon grouped daily US equities (computed breadth)",
        "sourceType": source_type,
        "sourceTier": source_tier,
        "trustLevel": trust_level,
        "freshness": freshness,
        "updatedAt": as_of,
        "asOf": as_of,
        "isFallback": is_fallback,
        "fallbackUsed": is_fallback,
        "representativeSample": False,
        "officialExchangePublishedBreadth": False,
        "fullBreadthAuthority": False,
        "breadthClaimType": "computed_authorized_polygon_grouped_daily_breadth",
        "comparisonBasis": "previous_close",
        "coverageCount": 12000,
        "coverageThreshold": 9600,
        "sourceAuthorityAllowed": source_authority_allowed,
        "scoreContributionAllowed": score_contribution_allowed,
        "sourceAuthorityReason": source_authority_reason,
        "routeRejectedReasonCodes": codes,
        "observationOnly": observation_only,
        "isPartial": is_partial,
        "fulfilledMetrics": fulfilled,
        "missingMetrics": missing,
        "authorityDiagnostics": {"reasonCodes": codes, "comparisonBasis": "previous_close"},
        "sourceFreshnessEvidence": {
            "freshness": freshness,
            "comparisonBasis": "previous_close",
            "isFallback": is_fallback,
            "isStale": freshness == "stale",
            "isPartial": is_partial,
            "isUnavailable": False,
        },
        "items": items,
    }


def _make_service(*, allow_external_provider_calls: bool = False) -> LiquidityMonitorService:
    return LiquidityMonitorService(
        cache=MarketCache(max_workers=1),
        db=DatabaseManager.get_instance(),
        allow_external_provider_calls=allow_external_provider_calls,
    )


def _activation(payload: Dict[str, Any], key: str) -> Dict[str, Any]:
    return _indicators_by_key(payload)[key]["coverageDiagnostics"]


def _coverage_contract(payload: Dict[str, Any]) -> Dict[str, Any]:
    contract = payload.get("coverageContract")
    assert isinstance(contract, dict)
    return contract


def _observation_evidence_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    return payload["observationEvidenceSnapshot"]


def _capital_flow_signal(payload: Dict[str, Any]) -> Dict[str, Any]:
    return payload["capitalFlowSignal"]


def _assert_activation_fields(diagnostics: Dict[str, Any]) -> None:
    for field in (
        "indicatorId",
        "requiredInputCount",
        "fulfilledInputCount",
        "missingInputCount",
        "scoreEligibleInputCount",
        "observationOnlyInputCount",
        "requiredProviderClass",
        "configuredProviderAvailable",
        "realSourceAvailable",
        "proxyOnly",
        "observationOnly",
        "scoreContributionAllowed",
        "scoreExclusionReason",
        "requiredRealSourceForScore",
        "proxyObservationOnlyReason",
        "missingProviderReason",
        "paidDataLikelyRequired",
        "activationHint",
        "sourceTier",
        "trustLevel",
        "freshness",
        "sourceAuthorityRouteRejected",
        "sourceAuthorityReason",
        "routeRejectedReasonCodes",
    ):
        assert field in diagnostics


def _save_market_overview_snapshot(
    db: DatabaseManager,
    *,
    key: str,
    payload: Dict[str, Any],
) -> None:
    db.save_market_overview_snapshot(key=f"market_overview:{key}", payload=payload)


def _raw_snapshot_payload(
    *,
    source: str,
    items: list[Dict[str, Any]],
    updated_at: str,
    as_of: str,
    freshness: str | None = None,
    fallback_used: bool = False,
    warning: str | None = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "source": source,
        "items": items,
        "updatedAt": updated_at,
        "asOf": as_of,
        "fallbackUsed": fallback_used,
    }
    if freshness is not None:
        payload["freshness"] = freshness
    if warning is not None:
        payload["warning"] = warning
    return payload


def _liquidity_monitor_imports() -> set[str]:
    tree = ast.parse(LIQUIDITY_MONITOR_SERVICE_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def _cache_only_liquidity_service_payload(build_seed) -> dict[str, Any]:
    service = _make_service()
    quote_map: dict[str, _FakeHistoryFrame] = {}
    build_seed(service, quote_map)
    with (
        patch.object(LiquidityMonitorService, "_now", return_value=FROZEN_GOLDEN_NOW),
        patch(
            "src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame",
            side_effect=lambda ticker: quote_map.get(ticker, _FakeHistoryFrame([])),
            create=True,
        ),
        patch(
            "src.services.liquidity_monitor_service.fetch_binance_funding_row",
            side_effect=RuntimeError("network disabled for golden fixtures"),
        ),
    ):
        return LiquidityMonitorResponse(**service.get_liquidity_monitor()).model_dump(exclude_none=True)


def _seed_official_cached_macro_rates_context(
    service: LiquidityMonitorService,
    quote_map: dict[str, _FakeHistoryFrame],
) -> None:
    del quote_map
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                _official_vix_item(),
                {
                    "symbol": "US2Y",
                    "label": "US 2Y",
                    "value": 4.62,
                    "changePercent": -0.22,
                    "source": "treasury",
                    "sourceId": "treasury:DGS2",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.31,
                    "changePercent": -0.31,
                    "source": "treasury",
                    "sourceId": "treasury:DGS10",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": 4.58,
                    "changePercent": -0.18,
                    "source": "treasury",
                    "sourceId": "treasury:DGS30",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "SOFR",
                    "label": "SOFR",
                    "value": 5.31,
                    "source": "fred",
                    "sourceId": "fred:SOFR",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED SOFR",
                    "unit": "%",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
            ],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "fx_commodities",
        _cache_entry(
            source="yahoo",
            freshness="live",
            items=[{"symbol": "DXY", "label": "DXY", "changePercent": 0.30, "value": 104.2}],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "us_breadth",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[
                {"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 8},
                {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 3},
            ],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "ETF", "label": "ETF flow proxy", "value": 1.2}],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )


def _seed_mixed_official_proxy_context(
    service: LiquidityMonitorService,
    quote_map: dict[str, _FakeHistoryFrame],
) -> None:
    del quote_map
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                _official_vix_item(),
                {
                    "symbol": "US2Y",
                    "label": "US 2Y",
                    "value": 4.62,
                    "changePercent": -0.22,
                    "source": "treasury",
                    "sourceId": "treasury:DGS2",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.31,
                    "changePercent": -0.31,
                    "source": "treasury",
                    "sourceId": "treasury:DGS10",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": 4.58,
                    "changePercent": -0.18,
                    "source": "treasury",
                    "sourceId": "treasury:DGS30",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
            ],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "fx_commodities",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {
                    "symbol": "DXY",
                    "label": "DXY",
                    "changePercent": 0.30,
                    "value": 104.2,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                }
            ],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "us_breadth",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 8},
                {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 3},
            ],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[{"symbol": "ETF", "label": "ETF flow proxy", "value": 1.2}],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )


def _seed_missing_macro_rates_proxy_fallback_context(
    service: LiquidityMonitorService,
    quote_map: dict[str, _FakeHistoryFrame],
) -> None:
    service.cache.set(
        "us_breadth",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[
                {"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 8},
                {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 3},
            ],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "ETF", "label": "ETF flow proxy", "value": 1.2}],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    quote_index = [
        datetime(2026, 5, 6, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 7, 16, 0, tzinfo=timezone.utc),
    ]
    quote_map.update(
        {
            "^VIX": _FakeHistoryFrame([18.0, 15.0], index=quote_index),
            "DX-Y.NYB": _FakeHistoryFrame([104.9, 104.2], index=quote_index),
            "^TNX": _FakeHistoryFrame([45.8, 44.9], index=quote_index),
            "^TYX": _FakeHistoryFrame([47.5, 46.9], index=quote_index),
        }
    )


def _seed_credit_stress_observation_only_context(
    service: LiquidityMonitorService,
    quote_map: dict[str, _FakeHistoryFrame],
) -> None:
    del quote_map
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                _official_vix_item(),
                {
                    "symbol": "US2Y",
                    "label": "US 2Y",
                    "value": 4.62,
                    "changePercent": -0.22,
                    "source": "treasury",
                    "sourceId": "treasury:DGS2",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.31,
                    "changePercent": -0.31,
                    "source": "treasury",
                    "sourceId": "treasury:DGS10",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": 4.58,
                    "changePercent": -0.18,
                    "source": "treasury",
                    "sourceId": "treasury:DGS30",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "SOFR",
                    "label": "SOFR",
                    "value": 5.31,
                    "source": "fred",
                    "sourceId": "fred:SOFR",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED SOFR",
                    "unit": "%",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "CREDIT",
                    "label": "Credit spreads",
                    "value": 341.0,
                    "change": 12.0,
                    "changePercent": 3.65,
                    "source": "fred",
                    "sourceId": "fred:BAMLH0A0HYM2",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED ICE BofA US High Yield Index Option-Adjusted Spread",
                    "unit": "bps",
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                    "observationOnly": True,
                    "includedInScore": False,
                },
            ],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "fx_commodities",
        _cache_entry(
            source="yahoo",
            freshness="live",
            items=[{"symbol": "DXY", "label": "DXY", "changePercent": 0.30, "value": 104.2}],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "us_breadth",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[
                {"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 8},
                {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 3},
            ],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "ETF", "label": "ETF flow proxy", "value": 1.2}],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )


def _seed_delayed_proxy_fx_commodities_context(
    service: LiquidityMonitorService,
    quote_map: dict[str, _FakeHistoryFrame],
) -> None:
    del quote_map
    service.cache.set(
        "volatility",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "changePercent": -2.5,
                    "value": 15.2,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                }
            ],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "fx_commodities",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {
                    "symbol": "DXY",
                    "label": "DXY",
                    "changePercent": -0.4,
                    "value": 104.2,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                }
            ],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "rates",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {
                    "symbol": "US10Y",
                    "label": "10Y yield",
                    "changePercent": -0.2,
                    "value": 4.1,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                },
                {
                    "symbol": "US30Y",
                    "label": "30Y yield",
                    "changePercent": -0.1,
                    "value": 4.6,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                },
            ],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "us_breadth",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 8},
                {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 3},
            ],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[{"symbol": "ETF", "label": "ETF flow proxy", "value": 1.2}],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )


def _seed_provider_unavailable_stale_malformed_context(
    service: LiquidityMonitorService,
    quote_map: dict[str, _FakeHistoryFrame],
) -> None:
    del quote_map
    stale_as_of = (FROZEN_GOLDEN_NOW - timedelta(hours=8)).isoformat(timespec="seconds")
    service.cache.set(
        "volatility",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[
                {"symbol": "VIX", "label": "VIX", "changePercent": "oops", "value": None},
                "malformed-entry",
            ],
            updated_at=stale_as_of,
            as_of=stale_as_of,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "rates",
        _cache_entry(
            source="yahoo",
            freshness="stale",
            items=[{"symbol": "US10Y", "label": "10Y yield", "changePercent": "nan", "value": "n/a"}],
            updated_at=stale_as_of,
            as_of=stale_as_of,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "fx_commodities",
        _cache_entry(
            source="mock",
            freshness="mock",
            is_fallback=True,
            items=[{"symbol": "DXY", "label": "DXY", "changePercent": -0.4, "value": 104.2}],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "cn_flows",
        _cache_entry(
            source="fallback",
            freshness="fallback",
            is_fallback=True,
            items=[{"symbol": "NORTHBOUND", "label": "北向资金", "value": 88.8}],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
            warning="备用快照",
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "futures",
        _cache_entry(
            source="fallback",
            freshness="fallback",
            is_fallback=True,
            items=[{"symbol": "NQ", "label": "纳指期货", "changePercent": 1.5, "value": 18420.0}],
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
            warning="备用快照",
        ),
        ttl_seconds=30,
    )


def test_liquidity_monitor_runtime_source_stays_cache_only() -> None:
    imported_modules = _liquidity_monitor_imports()
    forbidden_imports = sorted(
        module
        for module in imported_modules
        if any(
            module == prefix or module.startswith(prefix + ".")
            for prefix in FORBIDDEN_LIQUIDITY_MONITOR_IMPORT_PREFIXES
        )
    )
    source_text = LIQUIDITY_MONITOR_SERVICE_PATH.read_text(encoding="utf-8")

    assert not forbidden_imports, (
        "Liquidity Monitor must remain a cache-only advisory surface. Do not "
        "add direct provider SDK or raw HTTP imports here; extend it only via "
        f"existing MarketCache snapshots and metadata. Found {forbidden_imports}"
    )
    for pattern in FORBIDDEN_LIQUIDITY_MONITOR_CACHE_PATTERNS:
        assert re.search(pattern, source_text) is None, (
            "Liquidity Monitor must not refresh or mutate MarketCache. "
            "Preserve its existing cache-only/metadata semantics and keep "
            f"`{pattern}` out of liquidity_monitor_service.py"
        )


def test_default_liquidity_monitor_read_does_not_fetch_binance_funding(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "crypto",
        _cache_entry(
            source="binance",
            freshness="live",
            items=[
                {"symbol": "BTC", "label": "Bitcoin", "changePercent": 2.0, "value": 65000, "asOf": now},
                {"symbol": "ETH", "label": "Ethereum", "changePercent": 1.0, "value": 3200, "asOf": now},
                {"symbol": "BNB", "label": "BNB", "changePercent": 0.5, "value": 600, "asOf": now},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ)),
        patch("src.services.liquidity_monitor_service.fetch_binance_funding_row") as mock_funding,
        patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", return_value=_FakeHistoryFrame([]), create=True),
    ):
        payload = service.get_liquidity_monitor()

    funding = _indicators_by_key(payload)["crypto_funding"]

    mock_funding.assert_not_called()
    assert payload["sourceMetadata"]["externalProviderCalls"] is False
    assert funding["status"] == "unavailable"
    assert funding["includedInScore"] is False
    assert funding["scoreContribution"] == 0
    assert funding["evidence"]["isUnavailable"] is True
    assert "未触发实时 funding 查询" in funding["summary"]


def test_default_liquidity_monitor_read_does_not_fetch_yfinance_proxy_when_cache_missing(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()

    with (
        patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", return_value=_FakeHistoryFrame([18.0, 15.0]), create=True) as mock_proxy,
        patch("src.services.liquidity_monitor_service.fetch_binance_funding_row") as mock_funding,
    ):
        payload = service.get_liquidity_monitor()

    indicators = _indicators_by_key(payload)

    mock_proxy.assert_not_called()
    mock_funding.assert_not_called()
    assert payload["sourceMetadata"]["externalProviderCalls"] is False
    assert payload["score"]["regime"] == "unavailable"
    for key in ("vix_pressure", "us_rates_pressure", "crypto_funding"):
        indicator = indicators[key]
        assert indicator["status"] == "unavailable"
        assert indicator["includedInScore"] is False
        assert indicator["scoreContribution"] == 0
        assert indicator["evidence"]["isUnavailable"] is True
        assert indicator["coverageDiagnostics"]["contributesToScore"] is False


def test_default_liquidity_monitor_read_scores_authorized_fresh_cached_evidence_without_provider_calls(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "crypto",
        _cache_entry(
            source="binance",
            freshness="live",
            items=[
                {"symbol": "BTC", "label": "Bitcoin", "changePercent": 2.0, "value": 65000, "source": "binance", "sourceType": "exchange_public"},
                {"symbol": "ETH", "label": "Ethereum", "changePercent": 1.0, "value": 3200, "source": "binance", "sourceType": "exchange_public"},
                {"symbol": "BNB", "label": "BNB", "changePercent": 0.5, "value": 600, "source": "binance", "sourceType": "exchange_public"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "volatility",
        _cache_entry(
            source="fred",
            freshness="cached",
            items=[
                _official_vix_item(value=15.2, change_percent=-2.5, as_of=now)
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "rates",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {"symbol": "US2Y", "label": "US 2Y", "value": 4.62, "changePercent": -0.22, "source": "treasury", "sourceType": "official_public", "sourceLabel": "US Treasury", "unit": "%"},
                {"symbol": "US10Y", "label": "US 10Y", "value": 4.31, "changePercent": -0.31, "source": "treasury", "sourceType": "official_public", "sourceLabel": "US Treasury", "unit": "%"},
                {"symbol": "US30Y", "label": "US 30Y", "value": 4.58, "changePercent": -0.18, "source": "treasury", "sourceType": "official_public", "sourceLabel": "US Treasury", "unit": "%"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    with (
        patch("src.services.liquidity_monitor_service.fetch_binance_funding_row") as mock_funding,
        patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", return_value=_FakeHistoryFrame([]), create=True) as mock_proxy,
    ):
        payload = service.get_liquidity_monitor()

    indicators = _indicators_by_key(payload)

    mock_funding.assert_not_called()
    mock_proxy.assert_not_called()
    assert payload["sourceMetadata"]["externalProviderCalls"] is False
    assert indicators["crypto_spot_momentum"]["includedInScore"] is True
    assert indicators["vix_pressure"]["includedInScore"] is True
    assert indicators["us_rates_pressure"]["includedInScore"] is True
    assert payload["score"]["includedIndicatorCount"] == 3
    assert payload["score"]["regime"] != "unavailable"


def test_persistent_raw_macro_snapshot_prefers_official_vix_without_proxy_fetch(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    _save_market_overview_snapshot(
        isolated_db,
        key="macro",
        payload=_raw_snapshot_payload(
            source="mixed",
            freshness="cached",
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
            items=[
                _official_vix_item(symbol="VIXCLS", as_of=FROZEN_GOLDEN_NOW_ISO, freshness="delayed")
            ],
        ),
    )
    _save_market_overview_snapshot(
        isolated_db,
        key="volatility",
        payload=_raw_snapshot_payload(
            source="yfinance_proxy",
            freshness="delayed",
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 21.0,
                    "changePercent": 1.5,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                }
            ],
        ),
    )

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=FROZEN_GOLDEN_NOW),
        patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", create=True) as mock_fetch,
    ):
        indicator = service._vix_indicator(service._read_panel("volatility"), service._read_panel("macro"))

    mock_fetch.assert_not_called()
    assert indicator["includedInScore"] is True
    assert indicator["freshness"] == "delayed"
    assert indicator["status"] == "partial"
    assert "FRED VIXCLS" in indicator["summary"]
    assert "official_public" in indicator["summary"]
    assert "Yahoo Finance" not in indicator["summary"]


def test_persistent_raw_volatility_snapshot_prefers_official_vix_without_proxy_fetch(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    _save_market_overview_snapshot(
        isolated_db,
        key="volatility",
        payload=_raw_snapshot_payload(
            source="mixed",
            freshness="cached",
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
            items=[
                _official_vix_item(value=16.8, change_percent=-3.2, as_of=FROZEN_GOLDEN_NOW_ISO, freshness="delayed")
            ],
        ),
    )
    _save_market_overview_snapshot(
        isolated_db,
        key="macro",
        payload=_raw_snapshot_payload(
            source="yfinance_proxy",
            freshness="delayed",
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 21.0,
                    "changePercent": 1.5,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                }
            ],
        ),
    )

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=FROZEN_GOLDEN_NOW),
        patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", create=True) as mock_fetch,
    ):
        indicator = service._vix_indicator(service._read_panel("volatility"), service._read_panel("macro"))

    mock_fetch.assert_not_called()
    assert indicator["includedInScore"] is True
    assert indicator["freshness"] == "delayed"
    assert "FRED VIXCLS" in indicator["summary"]
    assert "Yahoo Finance" not in indicator["summary"]


def test_expired_proxy_volatility_cache_yields_to_newer_official_snapshot_without_proxy_refetch(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    stale_cache_as_of = "2026-05-15T12:00:00+08:00"
    fresh_snapshot_as_of = "2026-05-15T14:15:00+08:00"
    service.cache.set(
        "volatility",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 21.0,
                    "changePercent": 1.5,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                    "updatedAt": stale_cache_as_of,
                    "asOf": stale_cache_as_of,
                }
            ],
            updated_at=stale_cache_as_of,
            as_of=stale_cache_as_of,
        ),
        ttl_seconds=-1,
    )
    _save_market_overview_snapshot(
        isolated_db,
        key="volatility",
        payload=_raw_snapshot_payload(
            source="mixed",
            updated_at=fresh_snapshot_as_of,
            as_of=fresh_snapshot_as_of,
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 16.8,
                    "changePercent": -3.2,
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "updatedAt": fresh_snapshot_as_of,
                    "asOf": fresh_snapshot_as_of,
                }
            ],
        ),
    )

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=datetime(2026, 5, 15, 14, 20, tzinfo=CN_TZ)),
        patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", create=True) as mock_fetch,
    ):
        panel = service._read_panel("volatility")
        indicator = service._vix_indicator(panel, service._read_panel("macro"))

    mock_fetch.assert_not_called()
    assert panel.source == "mixed"
    assert panel.freshness == "delayed"
    assert panel.as_of == fresh_snapshot_as_of
    assert indicator["freshness"] == "delayed"
    assert "FRED VIXCLS" in indicator["summary"]
    assert "Yahoo Finance" not in indicator["summary"]


def test_mixed_raw_rates_snapshot_with_fallback_used_still_accepts_official_yields(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    _save_market_overview_snapshot(
        isolated_db,
        key="rates",
        payload=_raw_snapshot_payload(
            source="mixed",
            freshness="delayed",
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
            fallback_used=True,
            items=[
                {
                    "symbol": "US2Y",
                    "label": "US 2Y",
                    "value": 4.62,
                    "changePercent": -0.22,
                    "source": "treasury",
                    "sourceId": "treasury:DGS2",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.31,
                    "changePercent": -0.31,
                    "source": "treasury",
                    "sourceId": "treasury:DGS10",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": 4.58,
                    "changePercent": -0.18,
                    "source": "treasury",
                    "sourceId": "treasury:DGS30",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                },
                {
                    "symbol": "SOFR",
                    "label": "SOFR",
                    "value": 5.31,
                    "source": "fred",
                    "sourceId": "fred:SOFR",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED SOFR",
                    "unit": "%",
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "officialSeriesId": "SOFR",
                },
                {
                    "symbol": "US10Y2Y",
                    "label": "10Y-2Y 利差",
                    "value": -0.28,
                    "source": "fred",
                    "sourceId": "fred:T10Y2Y",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED",
                    "unit": "%",
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "officialSeriesId": "T10Y2Y",
                },
                {
                    "symbol": "US10Y3M",
                    "label": "10Y-3M 利差",
                    "value": -0.94,
                    "source": "fred",
                    "sourceId": "fred:T10Y3M",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED",
                    "unit": "%",
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                    "officialSeriesId": "T10Y3M",
                },
                {
                    "symbol": "LEGACY_FILLER",
                    "label": "legacy",
                    "value": 0.0,
                    "source": "fallback",
                    "sourceType": "fallback_static",
                    "isFallback": True,
                },
            ],
        ),
    )

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=FROZEN_GOLDEN_NOW),
        patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", create=True) as mock_fetch,
    ):
        rates_panel = service._read_panel("rates")
        reliable_symbols = {item["symbol"] for item in service._reliable_items(rates_panel, {"US2Y", "US10Y", "US30Y"})}
        indicator = service._us_rates_indicator(rates_panel, service._read_panel("macro"))

    mock_fetch.assert_not_called()
    assert rates_panel.is_fallback is False
    assert reliable_symbols == {"US2Y", "US10Y", "US30Y"}
    assert indicator["includedInScore"] is True
    assert indicator["freshness"] == "delayed"
    assert "US Treasury" in indicator["summary"]
    assert "official_public" in indicator["summary"]
    bundle = indicator["evidence"]["cacheBundleDiagnostics"]
    assert bundle["providerId"] == "official_public.us_rates"
    assert bundle["readinessEligible"] is True
    assert bundle["scoreGradeEvidenceAllowed"] is True
    assert bundle["cacheSafeOfficialEvidenceAllowed"] is True
    assert bundle["requiredSeries"] == ["DGS2", "DGS10", "DGS30"]
    assert bundle["fulfilledSeries"] == ["DGS2", "DGS10", "DGS30"]
    assert bundle["missingSeries"] == []
    assert bundle["contextSeries"] == ["SOFR", "US10Y2Y", "US10Y3M"]
    assert bundle["fulfilledContextSeries"] == ["SOFR", "US10Y2Y", "US10Y3M"]
    assert bundle["externalProviderCalls"] is False
    evidence_inputs = {str(item["key"]): item for item in indicator["evidence"]["inputs"]}
    assert evidence_inputs["SOFR"]["officialSeriesId"] == "SOFR"
    assert evidence_inputs["US10Y2Y"]["officialSeriesId"] == "T10Y2Y"
    assert evidence_inputs["US10Y3M"]["officialSeriesId"] == "T10Y3M"


def test_us_rates_readiness_diagnostics_fail_closed_for_budget_blocked_official_rows(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    as_of = "2026-05-20T10:00:00+08:00"
    service.cache.set(
        "rates",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "US2Y",
                    "label": "US 2Y",
                    "value": 4.62,
                    "changePercent": -0.22,
                    "source": "treasury",
                    "sourceId": "treasury:DGS2",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "sourceTier": "official_public",
                    "trustLevel": "reliable",
                    "freshness": "cached",
                    "unit": "%",
                    "updatedAt": as_of,
                    "asOf": as_of,
                    "officialSeriesId": "DGS2",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                },
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.31,
                    "changePercent": -0.31,
                    "source": "treasury",
                    "sourceId": "treasury:DGS10",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "sourceTier": "official_public",
                    "trustLevel": "reliable",
                    "freshness": "cached",
                    "unit": "%",
                    "updatedAt": as_of,
                    "asOf": as_of,
                    "officialSeriesId": "DGS10",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": 4.58,
                    "changePercent": -0.18,
                    "source": "treasury",
                    "sourceId": "treasury:DGS30",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "sourceTier": "official_public",
                    "trustLevel": "reliable",
                    "freshness": "cached",
                    "unit": "%",
                    "updatedAt": as_of,
                    "asOf": as_of,
                    "officialSeriesId": "DGS30",
                    "sourceAuthorityAllowed": False,
                    "scoreContributionAllowed": False,
                    "sourceAuthorityReason": "budget_exhausted",
                    "routeRejectedReasonCodes": ["budget_exhausted"],
                },
            ],
            updated_at=as_of,
            as_of=as_of,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["us_rates_pressure"]
    bundle = indicator["evidence"]["cacheBundleDiagnostics"]
    diagnostics = indicator["coverageDiagnostics"]

    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert diagnostics["scoreContributionAllowed"] is False
    assert diagnostics["scoreExclusionReason"] == "budget_exhausted"
    assert bundle["readinessEligible"] is False
    assert bundle["scoreGradeEvidenceAllowed"] is False
    assert bundle["budgetBlockedSeries"] == ["DGS30"]
    assert "budget_blocked_official_macro_route" in bundle["reasonCodes"]
    assert bundle["externalProviderCalls"] is False


def test_expired_proxy_rates_cache_yields_to_newer_official_snapshot_without_proxy_refetch(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    stale_cache_as_of = "2026-05-15T12:00:00+08:00"
    fresh_snapshot_as_of = "2026-05-15T14:14:00+08:00"
    service.cache.set(
        "rates",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {
                    "symbol": "US2Y",
                    "label": "US 2Y",
                    "value": 4.82,
                    "changePercent": 0.24,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                    "updatedAt": stale_cache_as_of,
                    "asOf": stale_cache_as_of,
                },
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.42,
                    "changePercent": 0.41,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                    "updatedAt": stale_cache_as_of,
                    "asOf": stale_cache_as_of,
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": 4.69,
                    "changePercent": 0.33,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                    "updatedAt": stale_cache_as_of,
                    "asOf": stale_cache_as_of,
                },
            ],
            updated_at=stale_cache_as_of,
            as_of=stale_cache_as_of,
        ),
        ttl_seconds=-1,
    )
    _save_market_overview_snapshot(
        isolated_db,
        key="rates",
        payload=_raw_snapshot_payload(
            source="mixed",
            updated_at=fresh_snapshot_as_of,
            as_of=fresh_snapshot_as_of,
            items=[
                {
                    "symbol": "US2Y",
                    "label": "US 2Y",
                    "value": 4.62,
                    "changePercent": -0.22,
                    "source": "treasury",
                    "sourceId": "treasury:DGS2",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "updatedAt": fresh_snapshot_as_of,
                    "asOf": fresh_snapshot_as_of,
                },
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.31,
                    "changePercent": -0.31,
                    "source": "treasury",
                    "sourceId": "treasury:DGS10",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "updatedAt": fresh_snapshot_as_of,
                    "asOf": fresh_snapshot_as_of,
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": 4.58,
                    "changePercent": -0.18,
                    "source": "treasury",
                    "sourceId": "treasury:DGS30",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "updatedAt": fresh_snapshot_as_of,
                    "asOf": fresh_snapshot_as_of,
                },
            ],
        ),
    )

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=datetime(2026, 5, 15, 14, 20, tzinfo=CN_TZ)),
        patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", create=True) as mock_fetch,
    ):
        panel = service._read_panel("rates")
        indicator = service._us_rates_indicator(panel, service._read_panel("macro"))

    mock_fetch.assert_not_called()
    assert panel.source == "mixed"
    assert panel.freshness == "delayed"
    assert panel.as_of == fresh_snapshot_as_of
    assert indicator["freshness"] == "delayed"
    assert "US2Y -0.22%" in indicator["summary"]
    assert "US10Y -0.31%" in indicator["summary"]
    assert "US30Y -0.18%" in indicator["summary"]
    assert "US Treasury" in indicator["summary"]
    assert "Yahoo Finance" not in indicator["summary"]


def test_raw_rates_snapshot_with_sofr_only_official_data_keeps_proxy_yields_observation_only(isolated_db: DatabaseManager) -> None:
    service = _make_service(allow_external_provider_calls=True)
    _save_market_overview_snapshot(
        isolated_db,
        key="rates",
        payload=_raw_snapshot_payload(
            source="mixed",
            freshness="delayed",
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
            items=[
                {
                    "symbol": "SOFR",
                    "label": "SOFR",
                    "value": 5.31,
                    "source": "fred",
                    "sourceId": "fred:SOFR",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED SOFR",
                    "unit": "%",
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                }
            ],
        ),
    )
    quote_index = [
        datetime(2026, 5, 6, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 7, 16, 0, tzinfo=timezone.utc),
    ]
    quote_map = {
        "^TNX": _FakeHistoryFrame([45.8, 44.9], index=quote_index),
        "^TYX": _FakeHistoryFrame([47.5, 46.9], index=quote_index),
    }

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=FROZEN_GOLDEN_NOW),
        patch(
            "src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame",
            side_effect=lambda ticker: quote_map.get(ticker, _FakeHistoryFrame([])),
            create=True,
        ),
    ):
        indicator = service._us_rates_indicator(service._read_panel("rates"), service._read_panel("macro"))

    assert service._external_provider_calls_used is True
    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert indicator["coverageDiagnostics"]["scoreContributionAllowed"] is False
    assert indicator["coverageDiagnostics"]["scoreExclusionReason"] == "proxy_only_missing_real_source"
    assert indicator["coverageDiagnostics"]["capReason"] == "partial_coverage"
    assert indicator["freshness"] == "delayed"
    assert "US10Y -1.97%" in indicator["summary"]
    assert "US30Y -1.26%" in indicator["summary"]
    assert "SOFR +5.31%" in indicator["summary"]
    assert "Yahoo Finance" in indicator["summary"]
    assert "FRED SOFR" in indicator["summary"]


def test_stale_raw_official_observation_is_marked_stale_and_excluded(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    stale_as_of = (FROZEN_GOLDEN_NOW - timedelta(days=4)).isoformat(timespec="seconds")
    _save_market_overview_snapshot(
        isolated_db,
        key="volatility",
        payload=_raw_snapshot_payload(
            source="mixed",
            freshness="cached",
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 24.0,
                    "changePercent": 2.1,
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "updatedAt": stale_as_of,
                    "asOf": stale_as_of,
                }
            ],
        ),
    )

    with patch.object(LiquidityMonitorService, "_now", return_value=FROZEN_GOLDEN_NOW):
        panel = service._read_panel("volatility")

    assert panel.payload["items"][0]["freshness"] == "stale"
    assert service._item_freshness(panel.payload["items"][0], panel) == "stale"
    assert service._reliable_items(panel, {"VIX"}) == []


def test_raw_official_snapshot_without_item_freshness_normalizes_to_delayed_without_fallback(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    snapshot_as_of = "2026-05-14T14:15:00+08:00"
    _save_market_overview_snapshot(
        isolated_db,
        key="volatility",
        payload=_raw_snapshot_payload(
            source="mixed",
            updated_at=snapshot_as_of,
            as_of=snapshot_as_of,
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 18.4,
                    "changePercent": -2.4,
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "updatedAt": snapshot_as_of,
                    "asOf": snapshot_as_of,
                }
            ],
        ),
    )

    with patch.object(LiquidityMonitorService, "_now", return_value=datetime(2026, 5, 15, 9, 0, tzinfo=CN_TZ)):
        panel = service._read_panel("volatility")

    assert panel.freshness == "delayed"
    assert panel.is_fallback is False
    assert panel.payload["items"][0]["freshness"] == "delayed"
    assert panel.payload["items"][0]["isStale"] is False
    assert service._reliable_items(panel, {"VIX"})[0]["symbol"] == "VIX"


def test_malformed_raw_official_observation_is_skipped_and_proxy_fallback_remains_available(isolated_db: DatabaseManager) -> None:
    service = _make_service(allow_external_provider_calls=True)
    _save_market_overview_snapshot(
        isolated_db,
        key="volatility",
        payload=_raw_snapshot_payload(
            source="mixed",
            freshness="cached",
            updated_at=FROZEN_GOLDEN_NOW_ISO,
            as_of=FROZEN_GOLDEN_NOW_ISO,
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": "n/a",
                    "changePercent": "oops",
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "updatedAt": FROZEN_GOLDEN_NOW_ISO,
                    "asOf": FROZEN_GOLDEN_NOW_ISO,
                }
            ],
        ),
    )
    quote_index = [
        datetime(2026, 5, 6, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 7, 16, 0, tzinfo=timezone.utc),
    ]

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=FROZEN_GOLDEN_NOW),
        patch(
            "src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame",
            return_value=_FakeHistoryFrame([18.0, 15.0], index=quote_index),
            create=True,
        ),
    ):
        panel = service._read_panel("volatility")
        indicator = service._vix_indicator(panel, service._read_panel("macro"))

    assert service._reliable_items(panel, {"VIX"}) == []
    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert indicator["coverageDiagnostics"]["scoreExclusionReason"] == "proxy_only_missing_real_source"
    assert indicator["freshness"] == "delayed"
    assert "Yahoo Finance" in indicator["summary"]
    assert "official_public" not in indicator["summary"]


def test_older_snapshot_does_not_override_fresher_cache_candidate(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    cache_as_of = "2026-05-15T14:20:00+08:00"
    older_snapshot_as_of = "2026-05-15T14:14:00+08:00"
    service.cache.set(
        "volatility",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 15.6,
                    "changePercent": -4.4,
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "freshness": "cached",
                    "updatedAt": cache_as_of,
                    "asOf": cache_as_of,
                }
            ],
            updated_at=cache_as_of,
            as_of=cache_as_of,
        ),
        ttl_seconds=300,
    )
    _save_market_overview_snapshot(
        isolated_db,
        key="volatility",
        payload=_raw_snapshot_payload(
            source="mixed",
            updated_at=older_snapshot_as_of,
            as_of=older_snapshot_as_of,
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 19.8,
                    "changePercent": 1.6,
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "updatedAt": older_snapshot_as_of,
                    "asOf": older_snapshot_as_of,
                }
            ],
        ),
    )

    with patch.object(LiquidityMonitorService, "_now", return_value=datetime(2026, 5, 15, 14, 20, tzinfo=CN_TZ)):
        panel = service._read_panel("volatility")

    assert panel.as_of == cache_as_of
    assert panel.freshness == "cached"
    assert panel.payload["items"][0]["value"] == 15.6
    assert panel.payload["items"][0]["changePercent"] == -4.4


@pytest.mark.parametrize(
    ("db_payload", "expected_source"),
    [
        (
            _raw_snapshot_payload(
                source="mixed",
                updated_at="2026-05-15T14:15:00+08:00",
                as_of="2026-05-15T14:15:00+08:00",
                items=[
                    {
                        "symbol": "VIX",
                        "label": "VIX",
                        "value": "n/a",
                        "changePercent": "oops",
                        "source": "fred",
                        "sourceId": "fred:VIXCLS",
                        "sourceType": "official_public",
                        "sourceLabel": "FRED VIXCLS",
                        "updatedAt": "2026-05-15T14:15:00+08:00",
                        "asOf": "2026-05-15T14:15:00+08:00",
                    }
                ],
            ),
            "mixed",
        ),
        (
            _raw_snapshot_payload(
                source="fallback",
                freshness="fallback",
                updated_at="2026-05-15T14:15:00+08:00",
                as_of="2026-05-15T14:15:00+08:00",
                fallback_used=True,
                items=[
                    {
                        "symbol": "VIX",
                        "label": "VIX",
                        "value": 22.1,
                        "changePercent": 2.2,
                        "source": "fallback",
                        "sourceType": "fallback_static",
                        "sourceLabel": "备用数据",
                        "isFallback": True,
                    }
                ],
            ),
            "mixed",
        ),
    ],
)
def test_malformed_or_fallback_only_snapshot_does_not_override_cache_candidate(
    isolated_db: DatabaseManager,
    db_payload: Dict[str, Any],
    expected_source: str,
) -> None:
    service = _make_service()
    cache_as_of = "2026-05-15T14:20:00+08:00"
    service.cache.set(
        "volatility",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 15.6,
                    "changePercent": -4.4,
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "freshness": "cached",
                    "updatedAt": cache_as_of,
                    "asOf": cache_as_of,
                }
            ],
            updated_at=cache_as_of,
            as_of=cache_as_of,
        ),
        ttl_seconds=300,
    )
    _save_market_overview_snapshot(isolated_db, key="volatility", payload=db_payload)

    with patch.object(LiquidityMonitorService, "_now", return_value=datetime(2026, 5, 15, 14, 20, tzinfo=CN_TZ)):
        panel = service._read_panel("volatility")

    assert panel.source == expected_source
    assert panel.as_of == cache_as_of
    assert panel.freshness == "cached"
    assert panel.payload["items"][0]["value"] == 15.6


def test_liquidity_monitor_metadata_declares_read_only_runtime_boundary(isolated_db: DatabaseManager) -> None:
    payload = _make_service().get_liquidity_monitor()

    assert payload["endpoint"] == "/api/v1/market/liquidity-monitor"
    assert payload["sourceMetadata"] == {
        "externalProviderCalls": False,
        "providerRuntimeChanged": False,
        "marketCacheMutation": False,
    }
    assert "不触发扫描、回测或组合动作" in payload["advisoryDisclosure"]


def test_liquidity_monitor_adds_observation_evidence_snapshot_with_read_only_contract(
    isolated_db: DatabaseManager,
) -> None:
    payload = _make_service().get_liquidity_monitor()
    snapshot = _observation_evidence_snapshot(payload)

    assert snapshot["diagnosticOnly"] is True
    assert snapshot["observationOnly"] is True
    assert snapshot["authorityGrant"] is False
    assert snapshot["decisionGrade"] is False
    assert snapshot["externalProviderCalls"] is False
    assert snapshot["providerRuntimeChanged"] is False
    assert snapshot["marketCacheMutation"] is False
    assert snapshot["indicatorCount"] == len(payload["indicators"])
    assert len(snapshot["indicatorEvidence"]) == len(payload["indicators"])
    assert snapshot["sourceConfidence"]["coverage"] == pytest.approx(0.0)
    assert snapshot["sourceConfidence"]["trustLevel"] == "unavailable"
    assert isinstance(snapshot["warnings"], list)
    assert isinstance(snapshot["missingInputs"], list)


def test_liquidity_monitor_observation_evidence_snapshot_remains_service_local_and_schema_filtered(
    isolated_db: DatabaseManager,
) -> None:
    del isolated_db
    service = _make_service()

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=FROZEN_GOLDEN_NOW),
        patch(
            "src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame",
            side_effect=RuntimeError("unexpected live quote call"),
            create=True,
        ),
        patch(
            "src.services.liquidity_monitor_service.fetch_binance_funding_row",
            side_effect=RuntimeError("unexpected live funding call"),
        ),
    ):
        raw_payload = service.get_liquidity_monitor()

    api_payload = LiquidityMonitorResponse(**raw_payload).model_dump(exclude_none=True)

    assert "observationEvidenceSnapshot" in raw_payload
    assert "observationEvidenceSnapshot" not in api_payload
    assert raw_payload["score"] == api_payload["score"]
    assert [item["key"] for item in raw_payload["indicators"]] == [item["key"] for item in api_payload["indicators"]]


def test_liquidity_monitor_observation_evidence_snapshot_preserves_proxy_fallback_stale_partial_and_missing_signals(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    quote_map: dict[str, _FakeHistoryFrame] = {}
    _seed_provider_unavailable_stale_malformed_context(service, quote_map)

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=FROZEN_GOLDEN_NOW),
        patch(
            "src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame",
            side_effect=lambda ticker: quote_map.get(ticker, _FakeHistoryFrame([])),
            create=True,
        ),
        patch(
            "src.services.liquidity_monitor_service.fetch_binance_funding_row",
            side_effect=RuntimeError("network disabled for evidence snapshot test"),
        ),
    ):
        payload = service.get_liquidity_monitor()

    snapshot = _observation_evidence_snapshot(payload)
    evidence_by_key = {item["key"]: item for item in snapshot["indicatorEvidence"]}

    assert snapshot["proxyInputCount"] >= 1
    assert snapshot["fallbackInputCount"] >= 1
    assert snapshot["staleInputCount"] >= 1
    assert snapshot["partialInputCount"] >= 1
    assert "syntheticInputCount" in snapshot
    assert snapshot["unavailableInputCount"] >= 1
    assert snapshot["missingInputCount"] >= 1
    assert "US2Y" in snapshot["missingInputs"]
    assert "DR007" in snapshot["missingInputs"]
    assert snapshot["sourceConfidence"]["trustLevel"] == "unavailable"
    assert "unavailable_source" in snapshot["sourceConfidence"]["degradationReasons"]

    vix_snapshot = evidence_by_key["vix_pressure"]
    assert vix_snapshot["diagnosticOnly"] is True
    assert vix_snapshot["observationOnly"] is True
    assert vix_snapshot["authorityGrant"] is False
    assert vix_snapshot["decisionGrade"] is False
    assert vix_snapshot["partialInputCount"] >= 1
    assert vix_snapshot["proxyInputCount"] >= 1
    assert any(item["source"] == "yfinance_proxy" for item in vix_snapshot["inputs"])

    rates_snapshot = evidence_by_key["us_rates_pressure"]
    assert rates_snapshot["staleInputCount"] >= 1
    assert rates_snapshot["proxyInputCount"] >= 1
    assert "US2Y" in rates_snapshot["missingInputs"]
    assert any("proxy_only_missing_real_source" in warning for warning in rates_snapshot["warnings"])

    cn_rates_snapshot = evidence_by_key["cn_money_market_rates"]
    assert cn_rates_snapshot["staleInputCount"] >= 1
    assert "DR007" in cn_rates_snapshot["missingInputs"]
    assert any("observation_only" in warning for warning in cn_rates_snapshot["warnings"])


def test_liquidity_monitor_observation_evidence_snapshot_preserves_indicator_level_metadata_parity(
    isolated_db: DatabaseManager,
) -> None:
    del isolated_db
    service = _make_service()
    quote_map: dict[str, _FakeHistoryFrame] = {}
    _seed_provider_unavailable_stale_malformed_context(service, quote_map)

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=FROZEN_GOLDEN_NOW),
        patch(
            "src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame",
            side_effect=lambda ticker: quote_map.get(ticker, _FakeHistoryFrame([])),
            create=True,
        ),
        patch(
            "src.services.liquidity_monitor_service.fetch_binance_funding_row",
            side_effect=RuntimeError("network disabled for evidence snapshot parity test"),
        ),
    ):
        payload = service.get_liquidity_monitor()

    snapshot = _observation_evidence_snapshot(payload)
    evidence_by_key = {item["key"]: item for item in snapshot["indicatorEvidence"]}

    assert snapshot["diagnosticOnly"] is True
    assert snapshot["observationOnly"] is True
    assert snapshot["authorityGrant"] is False
    assert snapshot["decisionGrade"] is False
    assert snapshot["externalProviderCalls"] is False
    assert snapshot["providerRuntimeChanged"] is False
    assert snapshot["marketCacheMutation"] is False

    vix_snapshot = evidence_by_key["vix_pressure"]
    assert vix_snapshot["source"] == "yfinance_proxy"
    assert vix_snapshot["freshness"] == "delayed"
    assert vix_snapshot["asOf"] == "2026-05-07T02:00:00+08:00"
    assert vix_snapshot["proxyOnly"] is True
    assert vix_snapshot["partialInputCount"] == 1
    assert vix_snapshot["warnings"] == [
        "proxy_only_missing_real_source",
        "requires_official_public.vix_or_volatility",
        "partial_coverage",
    ]

    rates_snapshot = evidence_by_key["us_rates_pressure"]
    assert rates_snapshot["source"] == "yahoo"
    assert rates_snapshot["freshness"] == "stale"
    assert rates_snapshot["asOf"] == "2026-05-07T02:00:00+08:00"
    assert rates_snapshot["proxyOnly"] is True
    assert rates_snapshot["staleInputCount"] == 1
    assert rates_snapshot["missingInputs"] == ["US2Y", "US10Y", "US30Y", "SOFR", "US10Y2Y", "US10Y3M"]
    assert rates_snapshot["warnings"] == [
        "proxy_only_missing_real_source",
        "requires_official_public.us_treasury_curve",
        "stale_source",
        "unavailable_source",
        "liquidity_input_unavailable",
    ]

    cn_flows_snapshot = evidence_by_key["cn_hk_flows"]
    assert cn_flows_snapshot["source"] == "fallback"
    assert cn_flows_snapshot["freshness"] == "fallback"
    assert cn_flows_snapshot["asOf"] == FROZEN_GOLDEN_NOW_ISO
    assert cn_flows_snapshot["fallbackInputCount"] == 1
    assert cn_flows_snapshot["coverageObservationOnly"] is True
    assert cn_flows_snapshot["requiredRealSourceForScore"] is False
    assert cn_flows_snapshot["missingInputs"] == [
        "NORTHBOUND",
        "SOUTHBOUND",
        "CN_ETF",
        "MARGIN_BALANCE",
        "MAINLAND_MAIN",
    ]
    assert cn_flows_snapshot["warnings"] == [
        "observation_only",
        "requires_authorized.cn_hk_connect_flow",
        "fallback_source",
        "unavailable_source",
        "备用快照",
    ]

    assert vix_snapshot["authorityGrant"] is False
    assert vix_snapshot["decisionGrade"] is False
    assert rates_snapshot["authorityGrant"] is False
    assert rates_snapshot["decisionGrade"] is False
    assert cn_flows_snapshot["authorityGrant"] is False
    assert cn_flows_snapshot["decisionGrade"] is False

    assert vix_snapshot["inputs"] == [
        {
            "key": "VIX",
            "label": "VIX",
            "source": "yfinance_proxy",
            "sourceLabel": "Yahoo Finance",
            "sourceType": "unofficial_proxy",
            "sourceClass": "unofficial_proxy",
            "asOf": "2026-05-07T02:00:00+08:00",
            "freshness": "delayed",
            "freshnessState": "delayed",
            "isFallback": False,
            "isStale": False,
            "isPartial": False,
            "isUnavailable": False,
            "isProxy": True,
            "proxyIdentity": None,
            "coverage": 1.0,
            "confidenceWeight": 0.7,
            "degradationReason": None,
            "unavailableReason": None,
            "capReason": None,
            "sourceAuthorityState": "proxy",
            "scoreAuthorityEligible": False,
        }
    ]
    assert rates_snapshot["inputs"] == [
        {
            "key": "rates",
            "label": "US Rates / 利率压力",
            "source": "yahoo",
            "sourceLabel": "Yahoo Finance",
            "sourceType": "unofficial_proxy",
            "sourceClass": "unofficial_proxy",
            "asOf": "2026-05-07T02:00:00+08:00",
            "freshness": "stale",
            "freshnessState": "stale",
            "isFallback": False,
            "isStale": True,
            "isPartial": False,
            "isUnavailable": False,
            "isProxy": True,
            "proxyIdentity": None,
            "coverage": 0.0,
            "confidenceWeight": 0.6,
            "degradationReason": "liquidity_input_unavailable",
            "unavailableReason": None,
            "capReason": "stale_source",
            "sourceAuthorityState": "proxy",
            "scoreAuthorityEligible": False,
        }
    ]
    assert cn_flows_snapshot["inputs"] == [
        {
            "key": "cn_flows",
            "label": "CN/HK 资金流",
            "source": "fallback",
            "sourceLabel": "备用数据",
            "sourceType": "fallback_static",
            "sourceClass": "fallback_static",
            "asOf": FROZEN_GOLDEN_NOW_ISO,
            "freshness": "fallback",
            "freshnessState": "fallback",
            "isFallback": True,
            "isStale": False,
            "isPartial": False,
            "isUnavailable": False,
            "isProxy": False,
            "proxyIdentity": None,
            "coverage": 0.0,
            "confidenceWeight": 0.4,
            "degradationReason": "备用快照",
            "unavailableReason": None,
            "capReason": "fallback_source",
            "sourceAuthorityState": "unknown",
            "scoreAuthorityEligible": False,
        }
    ]


def test_liquidity_coverage_contract_uses_required_input_denominator_and_family_counts(
    isolated_db: DatabaseManager,
) -> None:
    del isolated_db
    payload = _cache_only_liquidity_service_payload(_seed_official_cached_macro_rates_context)
    contract = _coverage_contract(payload)
    indicators = _indicators_by_key(payload)

    assert contract["denominatorKind"] == "required_inputs"
    assert contract["requiredFamilyCount"] == 12
    assert contract["requiredInputCount"] == 39
    assert contract["scoreWeightBudget"] == 49
    assert contract["scoreWeightIncluded"] == payload["score"]["includedIndicatorWeight"]
    assert payload["score"]["possibleIndicatorWeight"] == 49

    families = {item["indicatorId"]: item for item in contract["families"]}
    assert set(families) == set(indicators)
    assert sum(item["requiredInputCount"] for item in families.values()) == contract["requiredInputCount"]
    assert sum(item["fulfilledInputCount"] for item in families.values()) == contract["fulfilledInputCount"]
    assert sum(item["missingInputCount"] for item in families.values()) == contract["missingInputCount"]
    assert sum(item["scoreEligibleInputCount"] for item in families.values()) == contract["scoreEligibleInputCount"]
    assert sum(item["observationOnlyInputCount"] for item in families.values()) == contract["observationOnlyInputCount"]

    for key, indicator in indicators.items():
        diagnostics = indicator["coverageDiagnostics"]
        family = families[key]
        assert diagnostics["requiredInputCount"] == len(diagnostics["requiredInputs"])
        assert diagnostics["fulfilledInputCount"] == len(diagnostics["fulfilledInputs"])
        assert diagnostics["missingInputCount"] == len(diagnostics["missingInputs"])
        assert family["requiredInputCount"] == diagnostics["requiredInputCount"]
        assert family["fulfilledInputCount"] == diagnostics["fulfilledInputCount"]
        assert family["missingInputCount"] == diagnostics["missingInputCount"]
        assert family["scoreEligibleInputCount"] == diagnostics["scoreEligibleInputCount"]
        assert family["observationOnlyInputCount"] == diagnostics["observationOnlyInputCount"]


def test_liquidity_coverage_contract_keeps_proxy_only_and_observation_families_out_of_score_grade(
    isolated_db: DatabaseManager,
) -> None:
    del isolated_db
    payload = _cache_only_liquidity_service_payload(_seed_mixed_official_proxy_context)
    contract = _coverage_contract(payload)
    indicators = _indicators_by_key(payload)

    assert payload["score"]["includedIndicatorCount"] == 2
    assert payload["score"]["regime"] == "unavailable"
    assert contract["requiredInputCount"] == 39
    assert 0 < contract["scoreEligibleInputCount"] < contract["requiredInputCount"]
    assert contract["observationOnlyInputCount"] == 3

    for key in ("cn_hk_flows", "cn_money_market_rates", "futures_premarket", "crypto_funding"):
        diagnostics = indicators[key]["coverageDiagnostics"]
        assert diagnostics["observationOnly"] is True
        assert diagnostics["scoreContributionAllowed"] is False
        assert diagnostics["scoreEligibleInputCount"] == 0
        assert diagnostics["observationOnlyInputCount"] == diagnostics["fulfilledInputCount"]

    for key in ("vix_pressure", "us_rates_pressure", "us_etf_flow_proxy", "us_breadth_proxy"):
        diagnostics = indicators[key]["coverageDiagnostics"]
        if diagnostics["proxyOnly"]:
            assert diagnostics["scoreContributionAllowed"] is False
            assert diagnostics["scoreEligibleInputCount"] == 0


def test_liquidity_coverage_contract_has_safe_consumer_labels_without_advice_or_raw_terms(
    isolated_db: DatabaseManager,
) -> None:
    del isolated_db
    payload = _cache_only_liquidity_service_payload(_seed_provider_unavailable_stale_malformed_context)
    contract = _coverage_contract(payload)

    visible_text = "\n".join(
        str(item)
        for item in (
            contract["label"],
            contract["summary"],
            contract["denominatorLabel"],
            *(family["label"] for family in contract["families"]),
        )
    )
    assert visible_text
    assert not re.search(
        r"raw|debug|provider|runtime|schema|requestId|traceId|cache|buy|sell|hold|recommend|target|stop|position[- ]?sizing|买入|卖出|持有|推荐|目标价|止损|仓位",
        visible_text,
        flags=re.IGNORECASE,
    )


def test_unavailable_when_fewer_than_three_reliable_indicators(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "volatility",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "VIX", "label": "VIX", "changePercent": -2.5, "value": 15.2}],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "ETF", "label": "ETF flow proxy", "value": 0.8}],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()

    assert payload["score"]["value"] == 50
    assert payload["score"]["regime"] == "unavailable"
    assert payload["score"]["confidence"] == 0.0


def test_fallback_stale_mock_and_error_indicators_are_excluded_from_score(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "volatility",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "VIX", "label": "VIX", "changePercent": -2.5, "value": 15.2}],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "us_breadth",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 8}, {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 3}],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "ETF", "label": "ETF flow proxy", "value": 1.2}],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "crypto",
        _cache_entry(
            source="fallback",
            freshness="fallback",
            is_fallback=True,
            items=[{"symbol": "BTC", "label": "Bitcoin", "changePercent": 3.4, "value": 65000}],
            updated_at=now,
            as_of=now,
            warning="备用快照",
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "rates",
        _cache_entry(
            source="yahoo",
            freshness="stale",
            items=[{"symbol": "US10Y", "label": "10Y yield", "changePercent": -0.2, "value": 4.2}],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "fx_commodities",
        _cache_entry(
            source="mock",
            freshness="mock",
            is_fallback=True,
            items=[{"symbol": "DXY", "label": "DXY", "changePercent": -0.4, "value": 104.2}],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicators = {item["key"]: item for item in payload["indicators"]}

    assert payload["score"]["regime"] == "unavailable"
    assert payload["score"]["value"] == 50
    assert indicators["crypto_spot_momentum"]["includedInScore"] is False
    assert indicators["us_rates_pressure"]["includedInScore"] is False
    assert indicators["usd_pressure"]["includedInScore"] is False
    assert indicators["crypto_spot_momentum"]["status"] == "unavailable"
    assert indicators["us_rates_pressure"]["status"] == "unavailable"
    assert indicators["usd_pressure"]["status"] == "unavailable"


def test_fallback_source_type_items_do_not_inherit_live_panel_freshness(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "crypto",
        _cache_entry(
            source="mixed",
            freshness="live",
            items=[
                {
                    "symbol": "BTC",
                    "label": "Bitcoin",
                    "changePercent": 3.0,
                    "value": 65000,
                    "source": "curated_seed",
                    "sourceType": "fallback_static",
                    "sourceLabel": "Curated fallback seed",
                },
                {
                    "symbol": "ETH",
                    "label": "Ethereum",
                    "changePercent": 2.0,
                    "value": 3200,
                    "source": "curated_seed",
                    "sourceType": "fallback_static",
                    "sourceLabel": "Curated fallback seed",
                },
                {
                    "symbol": "BNB",
                    "label": "BNB",
                    "changePercent": 1.0,
                    "value": 600,
                    "source": "curated_seed",
                    "sourceType": "fallback_static",
                    "sourceLabel": "Curated fallback seed",
                },
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = {item["key"]: item for item in payload["indicators"]}["crypto_spot_momentum"]
    evidence = indicator["evidence"]

    assert indicator["status"] == "unavailable"
    assert indicator["freshness"] == "fallback"
    assert indicator["includedInScore"] is False
    assert evidence["isFallback"] is True
    assert evidence["isUnavailable"] is True
    assert evidence["coverage"] == 0.0
    assert evidence["freshness"] != "live"
    assert all(input_item["freshness"] != "live" for input_item in evidence["inputs"])


def test_item_stale_flag_overrides_live_freshness_for_indicator_inputs(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "rates",
        _cache_entry(
            source="yahoo",
            freshness="live",
            items=[
                {
                    "symbol": "US10Y",
                    "label": "10Y yield",
                    "changePercent": -0.2,
                    "value": 4.2,
                    "freshness": "live",
                    "isStale": True,
                    "source": "yahoo",
                    "sourceType": "unofficial_proxy",
                },
                {
                    "symbol": "US30Y",
                    "label": "30Y yield",
                    "changePercent": -0.1,
                    "value": 4.6,
                    "freshness": "live",
                    "isStale": True,
                    "source": "yahoo",
                    "sourceType": "unofficial_proxy",
                },
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = {item["key"]: item for item in payload["indicators"]}["us_rates_pressure"]
    evidence = indicator["evidence"]

    assert indicator["status"] == "unavailable"
    assert indicator["freshness"] == "stale"
    assert indicator["includedInScore"] is False
    assert evidence["isStale"] is True
    assert evidence["isUnavailable"] is True
    assert evidence["degradationReason"] == "stale_source"
    assert evidence["freshness"] != "live"
    assert all(input_item["freshness"] == "stale" for input_item in evidence["inputs"])


def test_proxy_only_indicators_do_not_inflate_total_score(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    for key, payload in {
        "volatility": _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "VIX", "label": "VIX", "changePercent": -3.0, "value": 14.6}],
            updated_at=now,
            as_of=now,
        ),
        "fx_commodities": _cache_entry(
            source="yahoo",
            freshness="live",
            items=[{"symbol": "DXY", "label": "DXY", "changePercent": -0.6, "value": 103.8}],
            updated_at=now,
            as_of=now,
        ),
        "rates": _cache_entry(
            source="yahoo",
            freshness="live",
            items=[{"symbol": "US10Y", "label": "10Y yield", "changePercent": -0.2, "value": 4.1}],
            updated_at=now,
            as_of=now,
        ),
        "crypto": _cache_entry(
            source="binance",
            freshness="live",
            items=[
                {"symbol": "BTC", "label": "Bitcoin", "changePercent": 3.0, "value": 65000},
                {"symbol": "ETH", "label": "Ethereum", "changePercent": 2.0, "value": 3200},
                {"symbol": "BNB", "label": "BNB", "changePercent": 1.0, "value": 600},
            ],
            updated_at=now,
            as_of=now,
        ),
        "us_breadth": _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 9}, {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 2}],
            updated_at=now,
            as_of=now,
        ),
        "funds_flow": _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "ETF", "label": "ETF flow proxy", "value": 1.5}],
            updated_at=now,
            as_of=now,
        ),
    }.items():
        service.cache.set(key, payload, ttl_seconds=30)

    payload = service.get_liquidity_monitor()

    indicators = {item["key"]: item for item in payload["indicators"]}

    assert payload["score"]["value"] == 50
    assert payload["score"]["regime"] == "unavailable"
    assert payload["score"]["confidence"] == 0.12
    assert payload["score"]["includedIndicatorCount"] == 1
    assert indicators["crypto_spot_momentum"]["includedInScore"] is True
    for key in ("vix_pressure", "us_rates_pressure", "us_etf_flow_proxy", "us_breadth_proxy"):
        assert indicators[key]["includedInScore"] is False
        assert indicators[key]["scoreContribution"] == 0
        assert indicators[key]["coverageDiagnostics"]["scoreExclusionReason"] == "proxy_only_missing_real_source"
    assert indicators["usd_pressure"]["includedInScore"] is False
    assert indicators["usd_pressure"]["scoreContribution"] == 0
    assert indicators["usd_pressure"]["coverageDiagnostics"]["scoreExclusionReason"] == "usd_pressure_missing_series"
    assert indicators["usd_pressure"]["coverageDiagnostics"]["missingInputs"] == ["USD_TWI"]


def test_derived_freshness_uses_weakest_input_freshness(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ)
    live = now.isoformat(timespec="seconds")
    delayed = (now - timedelta(minutes=12)).isoformat(timespec="seconds")

    service.cache.set(
        "crypto",
        _cache_entry(
            source="binance",
            freshness="live",
            items=[
                {"symbol": "BTC", "label": "Bitcoin", "changePercent": 2.0, "value": 65000, "asOf": live},
                {"symbol": "ETH", "label": "Ethereum", "changePercent": 1.0, "value": 3200, "asOf": delayed},
                {"symbol": "BNB", "label": "BNB", "changePercent": 0.5, "value": 600, "asOf": live},
            ],
            updated_at=live,
            as_of=live,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "us_breadth",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 8, "asOf": live}, {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 3, "asOf": delayed}],
            updated_at=live,
            as_of=live,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "ETF", "label": "ETF flow proxy", "value": 1.2, "asOf": live}],
            updated_at=live,
            as_of=live,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicators = {item["key"]: item for item in payload["indicators"]}

    assert indicators["crypto_spot_momentum"]["freshness"] == "delayed"
    assert indicators["us_breadth_proxy"]["freshness"] == "delayed"
    assert payload["freshness"]["weakestIndicatorFreshness"] == "delayed"


def test_missing_cn_hk_flow_source_reports_activation_diagnostic_without_score(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["cn_hk_flows"]
    diagnostic = indicator["coverageDiagnostics"]

    assert indicator["status"] == "unavailable"
    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert diagnostic["indicatorId"] == "cn_hk_flows"
    assert diagnostic["indicatorName"] == "CN/HK 资金流"
    assert "NORTHBOUND" in diagnostic["requiredInputs"]
    assert diagnostic["fulfilledInputs"] == []
    assert "NORTHBOUND" in diagnostic["missingInputs"]
    assert diagnostic["sourceTier"] == "unavailable"
    assert diagnostic["freshness"] == "unavailable"
    assert diagnostic["trustLevel"] == "unavailable"
    assert diagnostic["contributesToScore"] is False
    assert diagnostic["scoreContribution"] == 0
    assert diagnostic["capReason"] == "unavailable_source"
    assert "No audited CN/HK flow provider" in diagnostic["activationHint"]


def test_missing_us_etf_flow_proxy_reports_diagnostic_and_no_strong_score(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["us_etf_flow_proxy"]
    diagnostic = indicator["coverageDiagnostics"]

    assert indicator["status"] == "unavailable"
    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert diagnostic["requiredInputs"] == ["ETF"]
    assert diagnostic["fulfilledInputs"] == []
    assert diagnostic["missingInputs"] == ["ETF"]
    assert diagnostic["sourceTier"] == "unavailable"
    assert diagnostic["trustLevel"] == "unavailable"
    assert diagnostic["contributesToScore"] is False
    assert diagnostic["scoreContribution"] == 0
    assert "funds_flow" in diagnostic["activationHint"]


def test_fresh_binance_crypto_input_remains_live_exchange_public_when_fresh(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "crypto",
        _cache_entry(
            source="binance",
            freshness="live",
            items=[
                {"symbol": "BTC", "label": "Bitcoin", "changePercent": 3.0, "value": 65000},
                {"symbol": "ETH", "label": "Ethereum", "changePercent": 2.0, "value": 3200},
                {"symbol": "BNB", "label": "BNB", "changePercent": 1.0, "value": 600},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["crypto_spot_momentum"]
    diagnostic = indicator["coverageDiagnostics"]

    assert indicator["status"] == "live"
    assert indicator["includedInScore"] is True
    assert diagnostic["sourceTier"] == "exchange_public"
    assert diagnostic["freshness"] == "live"
    assert diagnostic["trustLevel"] == "reliable"
    assert diagnostic["fulfilledInputs"] == ["BTC", "ETH", "BNB"]
    assert diagnostic["missingInputs"] == []
    assert diagnostic["contributesToScore"] is True
    assert diagnostic["scoreContribution"] == 6
    assert diagnostic["capReason"] is None


def test_delayed_yfinance_macro_proxy_is_observation_only_without_real_source(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service(allow_external_provider_calls=True)
    quote_index = [
        datetime(2026, 5, 12, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 13, 16, 0, tzinfo=timezone.utc),
    ]

    with patch(
        "src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame",
        return_value=_FakeHistoryFrame([18.0, 15.0], index=quote_index),
        create=True,
    ):
        payload = service.get_liquidity_monitor()

    indicator = _indicators_by_key(payload)["vix_pressure"]
    diagnostic = indicator["coverageDiagnostics"]

    assert indicator["status"] == "partial"
    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert diagnostic["sourceTier"] == "unofficial_public_api"
    assert diagnostic["freshness"] == "partial"
    assert diagnostic["trustLevel"] == "usable_with_caution"
    assert diagnostic["scoreContributionAllowed"] is False
    assert diagnostic["requiredRealSourceForScore"] is True
    assert diagnostic["proxyObservationOnlyReason"] == "proxy_only_missing_real_source"
    assert diagnostic["scoreExclusionReason"] == "proxy_only_missing_real_source"
    assert diagnostic["contributesToScore"] is False
    assert diagnostic["scoreContribution"] == 0
    assert diagnostic["capReason"] == "partial_coverage"
    assert diagnostic["degradationReason"] == "partial_coverage"
    assert "scoreContributionAllowed=False" in diagnostic["activationHint"]


def test_fallback_static_liquidity_inputs_never_appear_live_in_diagnostics(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="fallback",
            freshness="fallback",
            is_fallback=True,
            items=[{"symbol": "ETF", "label": "ETF flow proxy", "value": 1.2}],
            updated_at=now,
            as_of=now,
            warning="备用快照",
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["us_etf_flow_proxy"]
    diagnostic = indicator["coverageDiagnostics"]

    assert indicator["status"] == "unavailable"
    assert indicator["freshness"] == "fallback"
    assert indicator["includedInScore"] is False
    assert diagnostic["freshness"] != "live"
    assert diagnostic["trustLevel"] == "unavailable"
    assert diagnostic["contributesToScore"] is False
    assert diagnostic["scoreContribution"] == 0
    assert diagnostic["capReason"] == "unavailable_source"


def test_liquidity_evidence_snapshot_marks_partial_inputs_without_claiming_live(
    isolated_db: DatabaseManager,
) -> None:
    del isolated_db
    payload = _cache_only_liquidity_service_payload(_seed_official_cached_macro_rates_context)
    indicator = {item["key"]: item for item in payload["indicators"]}["us_rates_pressure"]
    evidence = indicator["evidence"]

    assert evidence is not None
    assert evidence["contractVersion"] == "source_confidence_contract_v1"
    assert evidence["freshness"] == "partial"
    assert evidence["isPartial"] is True
    assert evidence["isUnavailable"] is False
    assert evidence["coverage"] == 1.0
    assert evidence["confidenceWeight"] == 0.7
    assert evidence["degradationReason"] == "partial_coverage"
    assert len(evidence["inputs"]) >= 2
    assert {item["source"] for item in evidence["inputs"]} == {"treasury", "fred"}
    assert all(item["freshness"] == "cached" for item in evidence["inputs"])
    assert all(item["confidenceWeight"] == 1.0 for item in evidence["inputs"])


def test_liquidity_api_facing_evidence_preserves_official_macro_authority_metadata(
    isolated_db: DatabaseManager,
) -> None:
    del isolated_db

    def build_seed(service: LiquidityMonitorService, quote_map: dict[str, _FakeHistoryFrame]) -> None:
        del quote_map
        official_as_of = "2026-05-07T10:00:00+08:00"
        official_observation_date = "2026-05-06"
        service.cache.set(
            "macro",
            _cache_entry(
                source="mixed",
                freshness="cached",
                items=[
                    {
                        "symbol": "VIX",
                        "label": "VIX",
                        "value": 18.22,
                        "changePercent": -4.66,
                        "source": "fred",
                        "sourceId": "fred:VIXCLS",
                        "sourceType": "official_public",
                        "sourceLabel": "FRED VIXCLS",
                        "sourceTier": "official_public",
                        "trustLevel": "reliable",
                        "freshness": "cached",
                        "asOf": official_as_of,
                        "updatedAt": official_as_of,
                        "isFallback": False,
                        "isUnavailable": False,
                        "isPartial": False,
                        "observationOnly": False,
                        "sourceAuthorityAllowed": True,
                        "scoreContributionAllowed": True,
                        "sourceAuthorityReason": None,
                        "sourceAuthorityRouteRejected": False,
                        "routeRejectedReasonCodes": [],
                        "officialSeriesId": "VIXCLS",
                        "officialObservationDate": official_observation_date,
                        "officialAsOf": official_observation_date,
                        "sourceFreshnessEvidence": {
                            "freshness": "cached",
                            "freshnessPolicy": "official_daily_us_weekday_t_plus_1",
                            "externalProviderCalls": False,
                            "isFallback": False,
                            "isStale": False,
                            "isUnavailable": False,
                        },
                    },
                    {
                        "symbol": "US2Y",
                        "label": "US 2Y",
                        "value": 4.62,
                        "changePercent": -0.22,
                        "source": "treasury",
                        "sourceId": "treasury:DGS2",
                        "sourceType": "official_public",
                        "sourceLabel": "US Treasury",
                        "sourceTier": "official_public",
                        "trustLevel": "reliable",
                        "freshness": "cached",
                        "unit": "%",
                        "asOf": official_as_of,
                        "updatedAt": official_as_of,
                        "isFallback": False,
                        "isUnavailable": False,
                        "isPartial": False,
                        "observationOnly": False,
                        "sourceAuthorityAllowed": True,
                        "scoreContributionAllowed": True,
                        "sourceAuthorityReason": None,
                        "sourceAuthorityRouteRejected": False,
                        "routeRejectedReasonCodes": [],
                        "officialSeriesId": "DGS2",
                        "officialObservationDate": official_observation_date,
                        "officialAsOf": official_observation_date,
                    },
                    {
                        "symbol": "US10Y",
                        "label": "US 10Y",
                        "value": 4.31,
                        "changePercent": -0.31,
                        "source": "treasury",
                        "sourceId": "treasury:DGS10",
                        "sourceType": "official_public",
                        "sourceLabel": "US Treasury",
                        "sourceTier": "official_public",
                        "trustLevel": "reliable",
                        "freshness": "cached",
                        "unit": "%",
                        "asOf": official_as_of,
                        "updatedAt": official_as_of,
                        "isFallback": False,
                        "isUnavailable": False,
                        "isPartial": False,
                        "observationOnly": False,
                        "sourceAuthorityAllowed": True,
                        "scoreContributionAllowed": True,
                        "sourceAuthorityReason": None,
                        "sourceAuthorityRouteRejected": False,
                        "routeRejectedReasonCodes": [],
                        "officialSeriesId": "DGS10",
                        "officialObservationDate": official_observation_date,
                        "officialAsOf": official_observation_date,
                    },
                    {
                        "symbol": "US30Y",
                        "label": "US 30Y",
                        "value": 4.58,
                        "changePercent": -0.18,
                        "source": "treasury",
                        "sourceId": "treasury:DGS30",
                        "sourceType": "official_public",
                        "sourceLabel": "US Treasury",
                        "sourceTier": "official_public",
                        "trustLevel": "reliable",
                        "freshness": "cached",
                        "unit": "%",
                        "asOf": official_as_of,
                        "updatedAt": official_as_of,
                        "isFallback": False,
                        "isUnavailable": False,
                        "isPartial": False,
                        "observationOnly": False,
                        "sourceAuthorityAllowed": True,
                        "scoreContributionAllowed": True,
                        "sourceAuthorityReason": None,
                        "sourceAuthorityRouteRejected": False,
                        "routeRejectedReasonCodes": [],
                        "officialSeriesId": "DGS30",
                        "officialObservationDate": official_observation_date,
                        "officialAsOf": official_observation_date,
                    },
                    {
                        "symbol": "SOFR",
                        "label": "SOFR",
                        "value": 5.31,
                        "source": "fred",
                        "sourceId": "fred:SOFR",
                        "sourceType": "official_public",
                        "sourceLabel": "FRED SOFR",
                        "sourceTier": "official_public",
                        "trustLevel": "reliable",
                        "freshness": "cached",
                        "unit": "%",
                        "asOf": official_as_of,
                        "updatedAt": official_as_of,
                        "isFallback": False,
                        "isUnavailable": False,
                        "isPartial": False,
                        "observationOnly": False,
                        "sourceAuthorityAllowed": True,
                        "scoreContributionAllowed": True,
                        "sourceAuthorityReason": None,
                        "sourceAuthorityRouteRejected": False,
                        "routeRejectedReasonCodes": [],
                        "officialSeriesId": "SOFR",
                        "officialObservationDate": official_observation_date,
                        "officialAsOf": official_observation_date,
                    },
                    {
                        "symbol": "CREDIT",
                        "label": "Credit spreads",
                        "value": 3.75,
                        "source": "fred",
                        "sourceId": "fred:BAMLH0A0HYM2",
                        "sourceType": "official_public",
                        "sourceLabel": "FRED BAMLH0A0HYM2",
                        "sourceTier": "official_public",
                        "trustLevel": "reliable",
                        "freshness": "cached",
                        "unit": "bps",
                        "asOf": official_as_of,
                        "updatedAt": official_as_of,
                        "isFallback": False,
                        "isUnavailable": False,
                        "isPartial": False,
                        "observationOnly": True,
                        "sourceAuthorityAllowed": True,
                        "scoreContributionAllowed": False,
                        "sourceAuthorityReason": None,
                        "sourceAuthorityRouteRejected": False,
                        "routeRejectedReasonCodes": [],
                        "officialSeriesId": "BAMLH0A0HYM2",
                        "officialObservationDate": official_observation_date,
                        "officialAsOf": official_observation_date,
                    },
                ],
                updated_at=official_as_of,
                as_of=official_as_of,
            ),
            ttl_seconds=30,
        )

    payload = _cache_only_liquidity_service_payload(build_seed)
    indicators = _indicators_by_key(payload)

    vix_inputs = {item["key"]: item for item in indicators["vix_pressure"]["evidence"]["inputs"]}
    rates_inputs = {item["key"]: item for item in indicators["us_rates_pressure"]["evidence"]["inputs"]}

    assert vix_inputs["VIX"]["sourceAuthorityAllowed"] is True
    assert vix_inputs["VIX"]["scoreContributionAllowed"] is True
    assert vix_inputs["VIX"]["sourceAuthorityRouteRejected"] is False
    assert vix_inputs["VIX"]["officialSeriesId"] == "VIXCLS"
    assert vix_inputs["VIX"]["officialObservationDate"] == "2026-05-06"
    assert vix_inputs["VIX"]["officialAsOf"] == "2026-05-06"
    assert vix_inputs["VIX"]["sourceTier"] == "official_public"
    assert vix_inputs["VIX"]["trustLevel"] == "reliable"
    assert vix_inputs["VIX"]["observationOnly"] is False
    assert vix_inputs["VIX"]["routeRejectedReasonCodes"] == []

    for key, series_id in {
        "US2Y": "DGS2",
        "US10Y": "DGS10",
        "US30Y": "DGS30",
        "SOFR": "SOFR",
    }.items():
        assert rates_inputs[key]["sourceAuthorityAllowed"] is True
        assert rates_inputs[key]["scoreContributionAllowed"] is True
        assert rates_inputs[key]["officialSeriesId"] == series_id
        assert rates_inputs[key]["officialObservationDate"] == "2026-05-06"
        assert rates_inputs[key]["officialAsOf"] == "2026-05-06"
        assert rates_inputs[key]["sourceTier"] == "official_public"
        assert rates_inputs[key]["trustLevel"] == "reliable"
        assert rates_inputs[key]["observationOnly"] is False
        assert rates_inputs[key]["routeRejectedReasonCodes"] == []

    assert rates_inputs["CREDIT"]["sourceAuthorityAllowed"] is True
    assert rates_inputs["CREDIT"]["scoreContributionAllowed"] is False
    assert rates_inputs["CREDIT"]["observationOnly"] is True
    assert rates_inputs["CREDIT"]["officialSeriesId"] == "BAMLH0A0HYM2"
    assert rates_inputs["CREDIT"]["officialObservationDate"] == "2026-05-06"
    assert rates_inputs["CREDIT"]["officialAsOf"] == "2026-05-06"
    assert rates_inputs["CREDIT"]["sourceTier"] == "official_public"
    assert rates_inputs["CREDIT"]["trustLevel"] == "reliable"
    assert rates_inputs["CREDIT"]["routeRejectedReasonCodes"] == []


def test_liquidity_evidence_snapshot_marks_unavailable_inputs_without_coverage(
    isolated_db: DatabaseManager,
) -> None:
    del isolated_db
    payload = _cache_only_liquidity_service_payload(_seed_official_cached_macro_rates_context)
    indicator = {item["key"]: item for item in payload["indicators"]}["crypto_funding"]
    evidence = indicator["evidence"]

    assert evidence is not None
    assert evidence["freshness"] == "unavailable"
    assert evidence["isUnavailable"] is True
    assert evidence["coverage"] == 0.0
    assert evidence["confidenceWeight"] == 0.0
    assert evidence["capReason"] == "unavailable_source"
    assert len(evidence["inputs"]) == 1
    assert evidence["inputs"][0]["isUnavailable"] is True
    assert evidence["inputs"][0]["coverage"] == 0.0
    assert evidence["inputs"][0]["capReason"] == "unavailable_source"


def test_liquidity_evidence_snapshot_preserves_stale_input_state_when_indicator_is_unavailable(
    isolated_db: DatabaseManager,
) -> None:
    del isolated_db
    payload = _cache_only_liquidity_service_payload(_seed_provider_unavailable_stale_malformed_context)
    indicator = {item["key"]: item for item in payload["indicators"]}["us_rates_pressure"]
    evidence = indicator["evidence"]

    assert evidence is not None
    assert evidence["isUnavailable"] is True
    assert evidence["isStale"] is True
    assert evidence["coverage"] == 0.0
    assert evidence["confidenceWeight"] == 0.0
    assert evidence["degradationReason"] == "stale_source"
    assert evidence["inputs"][0]["freshness"] == "stale"
    assert evidence["inputs"][0]["isStale"] is True
    assert evidence["inputs"][0]["capReason"] == "stale_source"


def test_liquidity_evidence_snapshot_preserves_fallback_input_state_when_indicator_is_unavailable(
    isolated_db: DatabaseManager,
) -> None:
    del isolated_db
    payload = _cache_only_liquidity_service_payload(_seed_provider_unavailable_stale_malformed_context)
    indicator = {item["key"]: item for item in payload["indicators"]}["cn_hk_flows"]
    evidence = indicator["evidence"]

    assert evidence is not None
    assert evidence["isUnavailable"] is True
    assert evidence["isFallback"] is True
    assert evidence["coverage"] == 0.0
    assert evidence["confidenceWeight"] == 0.0
    assert evidence["degradationReason"] == "fallback_source"
    assert evidence["inputs"][0]["freshness"] == "fallback"
    assert evidence["inputs"][0]["isFallback"] is True
    assert evidence["inputs"][0]["capReason"] == "fallback_source"


def test_crypto_funding_uses_explicit_bounded_binance_backfill_when_cache_snapshot_lacks_funding(isolated_db: DatabaseManager) -> None:
    service = _make_service(allow_external_provider_calls=True)
    now_dt = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ)
    now = now_dt.isoformat(timespec="seconds")
    service.cache.set(
        "crypto",
        _cache_entry(
            source="binance_ws",
            freshness="live",
            items=[
                {"symbol": "BTC", "label": "Bitcoin", "changePercent": 2.0, "value": 65000, "asOf": now},
                {"symbol": "ETH", "label": "Ethereum", "changePercent": 1.0, "value": 3200, "asOf": now},
                {"symbol": "BNB", "label": "BNB", "changePercent": 0.5, "value": 600, "asOf": now},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    funding_rows = {
        "BTCUSDT": {"lastFundingRate": "0.00012", "time": int(now_dt.timestamp() * 1000)},
        "ETHUSDT": {"lastFundingRate": "-0.00005", "time": int((now_dt - timedelta(hours=1)).timestamp() * 1000)},
    }

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=now_dt),
        patch("src.services.liquidity_monitor_service.fetch_binance_funding_row", side_effect=lambda symbol: funding_rows[symbol]),
    ):
        payload = service.get_liquidity_monitor()

    indicators = {item["key"]: item for item in payload["indicators"]}
    funding = indicators["crypto_funding"]
    evidence = funding["evidence"]

    assert payload["sourceMetadata"] == {
        "externalProviderCalls": True,
        "providerRuntimeChanged": False,
        "marketCacheMutation": False,
    }
    assert funding["status"] == "partial"
    assert funding["freshness"] == "live"
    assert funding["includedInScore"] is False
    assert evidence["isPartial"] is True
    assert evidence["freshness"] == "partial"
    assert evidence["degradationReason"] == "direct_provider_backfill"
    assert evidence["coverage"] == 1.0
    assert all(input_item["degradationReason"] == "direct_provider_backfill" for input_item in evidence["inputs"])
    assert all(input_item["freshness"] == "partial" for input_item in evidence["inputs"])
    assert "BTC" in str(funding["summary"])
    assert "ETH" in str(funding["summary"])
    assert "Binance" in str(funding["summary"])
    assert "exchange_public" in str(funding["summary"])
    assert "cache_snapshot" not in str(funding["summary"])


def test_crypto_funding_backfill_drops_stale_provider_rows_without_claiming_live(isolated_db: DatabaseManager) -> None:
    service = _make_service(allow_external_provider_calls=True)
    now_dt = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ)
    now = now_dt.isoformat(timespec="seconds")
    service.cache.set(
        "crypto",
        _cache_entry(
            source="binance_ws",
            freshness="live",
            items=[
                {"symbol": "BTC", "label": "Bitcoin", "changePercent": 2.0, "value": 65000, "asOf": now},
                {"symbol": "ETH", "label": "Ethereum", "changePercent": 1.0, "value": 3200, "asOf": now},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    old_time = int((now_dt - timedelta(days=3)).timestamp() * 1000)
    funding_rows = {
        "BTCUSDT": {"lastFundingRate": "0.00012", "time": old_time},
        "ETHUSDT": {"lastFundingRate": "-0.00005", "time": old_time},
    }

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=now_dt),
        patch("src.services.liquidity_monitor_service.fetch_binance_funding_row", side_effect=lambda symbol: funding_rows[symbol]),
    ):
        payload = service.get_liquidity_monitor()

    funding = {item["key"]: item for item in payload["indicators"]}["crypto_funding"]
    evidence = funding["evidence"]

    assert payload["sourceMetadata"]["externalProviderCalls"] is True
    assert funding["status"] == "unavailable"
    assert funding["freshness"] == "stale"
    assert funding["includedInScore"] is False
    assert evidence["isStale"] is True
    assert evidence["isUnavailable"] is True
    assert evidence["coverage"] == 0.0
    assert evidence["degradationReason"] == "stale_source"
    assert evidence["freshness"] != "live"
    assert all(input_item["freshness"] == "stale" for input_item in evidence["inputs"])


def test_crypto_funding_stays_unavailable_when_binance_public_endpoint_fails(isolated_db: DatabaseManager) -> None:
    service = _make_service(allow_external_provider_calls=True)
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "crypto",
        _cache_entry(
            source="binance_ws",
            freshness="live",
            items=[
                {"symbol": "BTC", "label": "Bitcoin", "changePercent": 2.0, "value": 65000, "asOf": now},
                {"symbol": "ETH", "label": "Ethereum", "changePercent": 1.0, "value": 3200, "asOf": now},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    with patch("src.services.liquidity_monitor_service.fetch_binance_funding_row", side_effect=RuntimeError("funding unavailable")):
        payload = service.get_liquidity_monitor()

    indicators = {item["key"]: item for item in payload["indicators"]}

    assert payload["sourceMetadata"]["externalProviderCalls"] is True
    assert indicators["crypto_funding"]["status"] == "unavailable"
    assert indicators["crypto_funding"]["freshness"] == "unavailable"
    assert "Binance" in str(indicators["crypto_funding"]["summary"])
    assert "暂不可用" in str(indicators["crypto_funding"]["summary"])


def test_response_source_metadata_reports_runtime_and_cache_boundaries(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    payload = service.get_liquidity_monitor()

    assert payload["sourceMetadata"] == {
        "externalProviderCalls": False,
        "providerRuntimeChanged": False,
        "marketCacheMutation": False,
    }


def test_crypto_breadth_uses_btc_eth_bnb_vote_not_avg_change(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "crypto",
        _cache_entry(
            source="binance",
            freshness="live",
            items=[
                {"symbol": "BTC", "label": "Bitcoin", "changePercent": 8.0, "value": 65000},
                {"symbol": "ETH", "label": "Ethereum", "changePercent": -7.0, "value": 3200},
                {"symbol": "BNB", "label": "BNB", "changePercent": 0.0, "value": 600},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "volatility",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "VIX", "label": "VIX", "changePercent": -2.5, "value": 15.2}],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[{"symbol": "ETF", "label": "ETF flow proxy", "value": 1.0}],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicators = {item["key"]: item for item in payload["indicators"]}

    assert indicators["crypto_spot_momentum"]["includedInScore"] is True
    assert indicators["crypto_spot_momentum"]["scoreContribution"] == 0
    assert "1/3" in indicators["crypto_spot_momentum"]["summary"]


def test_usd_pressure_ignores_reliable_fx_crosses_when_official_series_is_missing(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "fx_commodities",
        _cache_entry(
            source="yahoo",
            freshness="live",
            items=[
                {"symbol": "USDCNH", "label": "USD/CNH", "changePercent": 0.28, "value": 7.24},
                {"symbol": "USDJPY", "label": "USD/JPY", "changePercent": 0.39, "value": 156.4},
                {"symbol": "EURUSD", "label": "EUR/USD", "changePercent": -0.28, "value": 1.066},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicators = {item["key"]: item for item in payload["indicators"]}

    assert indicators["usd_pressure"]["includedInScore"] is False
    assert indicators["usd_pressure"]["scoreContribution"] == 0
    assert indicators["usd_pressure"]["coverageDiagnostics"]["scoreExclusionReason"] == "usd_pressure_missing_series"
    assert indicators["usd_pressure"]["coverageDiagnostics"]["missingInputs"] == ["USD_TWI"]
    assert "DTWEXBGS" in indicators["usd_pressure"]["summary"]
    assert "USD/CNH" not in indicators["usd_pressure"]["summary"]


def test_us_rates_indicator_uses_treasury_basket_when_us10y_missing(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "rates",
        _cache_entry(
            source="yahoo",
            freshness="live",
            items=[
                {"symbol": "US2Y", "label": "2Y yield", "changePercent": -0.18, "value": 4.82},
                {"symbol": "US30Y", "label": "30Y yield", "changePercent": -0.11, "value": 4.71},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicators = {item["key"]: item for item in payload["indicators"]}

    assert indicators["us_rates_pressure"]["includedInScore"] is False
    assert indicators["us_rates_pressure"]["scoreContribution"] == 0
    assert indicators["us_rates_pressure"]["coverageDiagnostics"]["scoreExclusionReason"] == "proxy_only_missing_real_source"
    assert "US2Y" in indicators["us_rates_pressure"]["summary"]


def test_us_breadth_indicator_uses_relative_proxy_votes(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "us_breadth",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[
                {"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 6},
                {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 5},
                {"symbol": "RSP_SPY", "label": "RSP vs SPY", "value": -0.4, "changePercent": -0.4},
                {"symbol": "IWM_SPY", "label": "IWM vs SPY", "value": -0.5, "changePercent": -0.5},
                {"symbol": "QQQ_SPY", "label": "QQQ vs SPY", "value": -0.2, "changePercent": -0.2},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicators = {item["key"]: item for item in payload["indicators"]}

    assert indicators["us_breadth_proxy"]["includedInScore"] is False
    assert indicators["us_breadth_proxy"]["scoreContribution"] == 0
    assert indicators["us_breadth_proxy"]["coverageDiagnostics"]["scoreExclusionReason"] == "proxy_only_missing_real_source"
    assert indicators["us_breadth_proxy"]["coverageDiagnostics"]["capReason"] == "partial_coverage"
    assert indicators["us_breadth_proxy"]["coverageDiagnostics"]["sourceAuthorityReason"] == "representative_sample_not_full_market_breadth"
    assert "RSP/SPY" in indicators["us_breadth_proxy"]["summary"]
    evidence_inputs = {
        item["key"]: item
        for item in indicators["us_breadth_proxy"]["evidence"]["inputs"]
    }
    assert evidence_inputs["SECTORS_UP"]["sourceAuthorityAllowed"] is False
    assert evidence_inputs["SECTORS_UP"]["scoreContributionAllowed"] is False
    assert evidence_inputs["SECTORS_UP"]["sourceAuthorityReason"] == "representative_sample_not_full_market_breadth"
    assert "representative_sample_not_full_market_breadth" in evidence_inputs["RSP_SPY"]["routeRejectedReasonCodes"]


def test_authorized_us_breadth_cache_scores_when_full_gates_pass(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    as_of = "2026-05-21T16:00:00+08:00"
    items = [
        _authorized_us_breadth_item("ADVANCERS", 7000, as_of=as_of, source_tier="authorized_licensed_feed"),
        _authorized_us_breadth_item("DECLINERS", 4000, as_of=as_of, source_tier="authorized_licensed_feed"),
        _authorized_us_breadth_item("UNCHANGED", 1000, as_of=as_of, source_tier="authorized_licensed_feed"),
        _authorized_us_breadth_item("ADVANCE_DECLINE_RATIO", 1.75, as_of=as_of, source_tier="authorized_licensed_feed"),
        _authorized_us_breadth_item("NEW_HIGHS", 318, as_of=as_of, source_tier="authorized_licensed_feed"),
        _authorized_us_breadth_item("NEW_LOWS", 42, as_of=as_of, source_tier="authorized_licensed_feed"),
        _authorized_us_breadth_item("HIGH_LOW_RATIO", 7.571, as_of=as_of, source_tier="authorized_licensed_feed"),
    ]
    service.cache.set(
        "us_breadth",
        _authorized_us_breadth_cache_payload(
            as_of=as_of,
            items=items,
            source_tier="authorized_licensed_feed",
        ),
        ttl_seconds=30,
    )

    with (
        patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", return_value=_FakeHistoryFrame([]), create=True) as mock_proxy,
        patch("src.services.liquidity_monitor_service.fetch_binance_funding_row", side_effect=RuntimeError("network disabled")) as mock_funding,
    ):
        payload = service.get_liquidity_monitor()

    indicator = _indicators_by_key(payload)["us_breadth_proxy"]
    diagnostics = indicator["coverageDiagnostics"]
    bundle = diagnostics["cacheBundleDiagnostics"]

    assert indicator["status"] == "live"
    assert indicator["includedInScore"] is True
    assert indicator["scoreContribution"] == 6
    assert indicator["freshness"] == "delayed"
    assert "7000/4000" in indicator["summary"]
    assert "NH/NL 318/42" in indicator["summary"]
    assert diagnostics["realSourceAvailable"] is True
    assert diagnostics["proxyOnly"] is False
    assert diagnostics["scoreContributionAllowed"] is True
    assert diagnostics["scoreExclusionReason"] is None
    assert diagnostics["missingProviderReason"] is None
    assert diagnostics["requiredInputs"] == list(AUTHORIZED_US_BREADTH_SYMBOLS)
    assert diagnostics["fulfilledInputs"] == list(AUTHORIZED_US_BREADTH_SYMBOLS)
    assert diagnostics["missingInputs"] == []
    assert bundle["providerId"] == "official_or_authorized.us_market_breadth"
    assert bundle["coverageRatio"] == 1.0
    assert bundle["observationOnly"] is False
    assert bundle["scoreContributionAllowed"] is True
    assert bundle["externalProviderCalls"] is False
    assert payload["sourceMetadata"]["externalProviderCalls"] is False
    assert payload["sourceMetadata"]["providerRuntimeChanged"] is False
    assert payload["sourceMetadata"]["marketCacheMutation"] is False
    mock_proxy.assert_not_called()
    mock_funding.assert_not_called()


def test_official_public_us_breadth_cache_scores_when_full_gates_pass(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    as_of = "2026-05-21T16:00:00+08:00"
    items = [
        _authorized_us_breadth_item("ADVANCERS", 7000, as_of=as_of, source="nyse_official_breadth", source_type="official_public", source_tier="official_public"),
        _authorized_us_breadth_item("DECLINERS", 4000, as_of=as_of, source="nyse_official_breadth", source_type="official_public", source_tier="official_public"),
        _authorized_us_breadth_item("UNCHANGED", 1000, as_of=as_of, source="nyse_official_breadth", source_type="official_public", source_tier="official_public"),
        _authorized_us_breadth_item("ADVANCE_DECLINE_RATIO", 1.75, as_of=as_of, source="nyse_official_breadth", source_type="official_public", source_tier="official_public"),
        _authorized_us_breadth_item("NEW_HIGHS", 318, as_of=as_of, source="nyse_official_breadth", source_type="official_public", source_tier="official_public"),
        _authorized_us_breadth_item("NEW_LOWS", 42, as_of=as_of, source="nyse_official_breadth", source_type="official_public", source_tier="official_public"),
        _authorized_us_breadth_item("HIGH_LOW_RATIO", 7.571, as_of=as_of, source="nyse_official_breadth", source_type="official_public", source_tier="official_public"),
    ]
    service.cache.set(
        "us_breadth",
        _authorized_us_breadth_cache_payload(
            as_of=as_of,
            items=items,
            source="nyse_official_breadth",
            source_type="official_public",
            source_tier="official_public",
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["us_breadth_proxy"]
    diagnostics = indicator["coverageDiagnostics"]
    bundle = diagnostics["cacheBundleDiagnostics"]

    assert indicator["status"] == "live"
    assert indicator["includedInScore"] is True
    assert indicator["scoreContribution"] == 6
    assert diagnostics["realSourceAvailable"] is True
    assert diagnostics["scoreContributionAllowed"] is True
    assert diagnostics["scoreExclusionReason"] is None
    assert bundle["sourceType"] == "official_public"
    assert bundle["sourceTier"] == "official_public"
    assert bundle["scoreContributionAllowed"] is True


def test_authorized_us_breadth_combined_source_tier_remains_observation_only(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    as_of = "2026-05-21T16:00:00+08:00"
    items = [
        _authorized_us_breadth_item("ADVANCERS", 7000, as_of=as_of, source_tier="official_or_authorized_licensed_feed"),
        _authorized_us_breadth_item("DECLINERS", 4000, as_of=as_of, source_tier="official_or_authorized_licensed_feed"),
        _authorized_us_breadth_item("UNCHANGED", 1000, as_of=as_of, source_tier="official_or_authorized_licensed_feed"),
        _authorized_us_breadth_item("ADVANCE_DECLINE_RATIO", 1.75, as_of=as_of, source_tier="official_or_authorized_licensed_feed"),
        _authorized_us_breadth_item("NEW_HIGHS", 318, as_of=as_of, source_tier="official_or_authorized_licensed_feed"),
        _authorized_us_breadth_item("NEW_LOWS", 42, as_of=as_of, source_tier="official_or_authorized_licensed_feed"),
        _authorized_us_breadth_item("HIGH_LOW_RATIO", 7.571, as_of=as_of, source_tier="official_or_authorized_licensed_feed"),
    ]
    service.cache.set(
        "us_breadth",
        _authorized_us_breadth_cache_payload(
            as_of=as_of,
            items=items,
            source_tier="official_or_authorized_licensed_feed",
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["us_breadth_proxy"]
    diagnostics = indicator["coverageDiagnostics"]
    bundle = diagnostics["cacheBundleDiagnostics"]

    assert indicator["status"] == "partial"
    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert diagnostics["realSourceAvailable"] is False
    assert diagnostics["scoreContributionAllowed"] is False
    assert diagnostics["scoreExclusionReason"] == "proxy_only_missing_real_source"
    assert diagnostics["sourceAuthorityReason"] == "proxy_or_placeholder_not_authorized_breadth"
    assert bundle["observationOnly"] is True
    assert bundle["scoreContributionAllowed"] is False


def test_authorized_us_breadth_missing_cache_remains_observation_only(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["us_breadth_proxy"]
    diagnostics = indicator["coverageDiagnostics"]

    assert indicator["status"] == "unavailable"
    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert diagnostics["realSourceAvailable"] is False
    assert diagnostics["scoreContributionAllowed"] is False


def test_authorized_us_breadth_stale_cache_remains_observation_only(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    as_of = "2026-05-21T16:00:00+08:00"
    items = [
        _authorized_us_breadth_item("ADVANCERS", 7000, as_of=as_of, freshness="stale", is_stale=True),
        _authorized_us_breadth_item("DECLINERS", 4000, as_of=as_of, freshness="stale", is_stale=True),
        _authorized_us_breadth_item("UNCHANGED", 1000, as_of=as_of, freshness="stale", is_stale=True),
        _authorized_us_breadth_item("ADVANCE_DECLINE_RATIO", 1.75, as_of=as_of, freshness="stale", is_stale=True),
        _authorized_us_breadth_item("NEW_HIGHS", 318, as_of=as_of, freshness="stale", is_stale=True),
        _authorized_us_breadth_item("NEW_LOWS", 42, as_of=as_of, freshness="stale", is_stale=True),
        _authorized_us_breadth_item("HIGH_LOW_RATIO", 7.571, as_of=as_of, freshness="stale", is_stale=True),
    ]
    service.cache.set(
        "us_breadth",
        _authorized_us_breadth_cache_payload(as_of=as_of, items=items, freshness="stale"),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["us_breadth_proxy"]
    diagnostics = indicator["coverageDiagnostics"]
    bundle = diagnostics["cacheBundleDiagnostics"]

    assert indicator["status"] == "partial"
    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert diagnostics["realSourceAvailable"] is True
    assert diagnostics["missingProviderReason"] is None
    assert diagnostics["scoreContributionAllowed"] is False
    assert diagnostics["scoreExclusionReason"] == "stale_source"
    assert bundle["observationOnly"] is True
    assert bundle["scoreContributionAllowed"] is False


def test_authorized_us_breadth_partial_coverage_remains_observation_only(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    as_of = "2026-05-21T16:00:00+08:00"
    items = [
        _authorized_us_breadth_item("ADVANCERS", 7000, as_of=as_of),
        _authorized_us_breadth_item("DECLINERS", 4000, as_of=as_of),
        _authorized_us_breadth_item("UNCHANGED", 1000, as_of=as_of),
        _authorized_us_breadth_item("ADVANCE_DECLINE_RATIO", 1.75, as_of=as_of),
    ]
    service.cache.set(
        "us_breadth",
        _authorized_us_breadth_cache_payload(
            as_of=as_of,
            items=items,
            is_partial=True,
            fulfilled_metrics=["ADVANCERS", "DECLINERS", "UNCHANGED", "ADVANCE_DECLINE_RATIO"],
            missing_metrics=["NEW_HIGHS", "NEW_LOWS", "HIGH_LOW_RATIO"],
            route_rejected_reason_codes=["polygon_high_low_history_unavailable"],
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["us_breadth_proxy"]
    diagnostics = indicator["coverageDiagnostics"]
    bundle = diagnostics["cacheBundleDiagnostics"]

    assert indicator["status"] == "partial"
    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert diagnostics["realSourceAvailable"] is True
    assert diagnostics["missingProviderReason"] is None
    assert diagnostics["scoreContributionAllowed"] is False
    assert diagnostics["scoreExclusionReason"] == "polygon_high_low_history_unavailable"
    assert diagnostics["missingInputs"] == ["NEW_HIGHS", "NEW_LOWS", "HIGH_LOW_RATIO"]
    assert bundle["coverageRatio"] == 0.571
    assert bundle["observationOnly"] is True
    assert bundle["scoreContributionAllowed"] is False


@pytest.mark.parametrize(
    (
        "payload_kwargs",
        "item_kwargs",
        "expected_real_source",
        "expected_score_exclusion_reason",
        "expected_authority_reason",
    ),
    [
        (
            {
                "freshness": "fallback",
                "is_fallback": True,
                "source_authority_allowed": False,
                "score_contribution_allowed": False,
                "source_authority_reason": "fallback_source",
                "route_rejected_reason_codes": ["fallback_source"],
            },
            {"freshness": "fallback", "source_authority_allowed": False, "score_contribution_allowed": False, "source_authority_reason": "fallback_source", "route_rejected_reason_codes": ["fallback_source"], "is_fallback": True},
            False,
            "proxy_only_missing_real_source",
            "fallback_source",
        ),
        (
            {
                "source": "yfinance_proxy",
                "source_type": "public_proxy",
                "source_tier": "unofficial_proxy",
                "trust_level": "usable_with_caution",
                "source_authority_allowed": False,
                "score_contribution_allowed": False,
                "source_authority_reason": "proxy_or_placeholder_not_authorized_breadth",
                "route_rejected_reason_codes": ["proxy_or_placeholder_not_authorized_breadth"],
            },
            {"source": "yfinance_proxy", "source_type": "public_proxy", "source_tier": "unofficial_proxy", "trust_level": "usable_with_caution", "source_authority_allowed": False, "score_contribution_allowed": False, "source_authority_reason": "proxy_or_placeholder_not_authorized_breadth", "route_rejected_reason_codes": ["proxy_or_placeholder_not_authorized_breadth"]},
            False,
            "proxy_only_missing_real_source",
            "proxy_or_placeholder_not_authorized_breadth",
        ),
        (
            {
                "source": "mock",
                "source_type": "synthetic_fixture",
                "source_tier": "synthetic_fixture",
                "trust_level": "weak",
                "freshness": "mock",
                "source_authority_allowed": False,
                "score_contribution_allowed": False,
                "source_authority_reason": "synthetic_fixture",
                "route_rejected_reason_codes": ["synthetic_fixture"],
            },
            {"source": "mock", "source_type": "synthetic_fixture", "source_tier": "synthetic_fixture", "trust_level": "weak", "freshness": "mock", "source_authority_allowed": False, "score_contribution_allowed": False, "source_authority_reason": "synthetic_fixture", "route_rejected_reason_codes": ["synthetic_fixture"]},
            False,
            "proxy_only_missing_real_source",
            "synthetic_fixture",
        ),
        (
            {
                "source_authority_allowed": False,
                "score_contribution_allowed": False,
                "source_authority_reason": "trust_gate_blocked",
                "route_rejected_reason_codes": ["trust_gate_blocked"],
                "trust_level": "weak",
            },
            {"source_authority_allowed": False, "score_contribution_allowed": False, "source_authority_reason": "trust_gate_blocked", "route_rejected_reason_codes": ["trust_gate_blocked"], "trust_level": "weak"},
            True,
            "trust_gate_blocked",
            "trust_gate_blocked",
        ),
    ],
)
def test_authorized_us_breadth_degraded_flags_remain_observation_only(
    isolated_db: DatabaseManager,
    payload_kwargs: Dict[str, Any],
    item_kwargs: Dict[str, Any],
    expected_real_source: bool,
    expected_score_exclusion_reason: str,
    expected_authority_reason: str,
) -> None:
    service = _make_service()
    as_of = "2026-05-21T16:00:00+08:00"
    items = [
        _authorized_us_breadth_item("ADVANCERS", 7000, as_of=as_of, **item_kwargs),
        _authorized_us_breadth_item("DECLINERS", 4000, as_of=as_of, **item_kwargs),
        _authorized_us_breadth_item("UNCHANGED", 1000, as_of=as_of, **item_kwargs),
        _authorized_us_breadth_item("ADVANCE_DECLINE_RATIO", 1.75, as_of=as_of, **item_kwargs),
        _authorized_us_breadth_item("NEW_HIGHS", 318, as_of=as_of, **item_kwargs),
        _authorized_us_breadth_item("NEW_LOWS", 42, as_of=as_of, **item_kwargs),
        _authorized_us_breadth_item("HIGH_LOW_RATIO", 7.571, as_of=as_of, **item_kwargs),
    ]
    service.cache.set(
        "us_breadth",
        _authorized_us_breadth_cache_payload(as_of=as_of, items=items, **payload_kwargs),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["us_breadth_proxy"]
    diagnostics = indicator["coverageDiagnostics"]

    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert diagnostics["realSourceAvailable"] is expected_real_source
    assert diagnostics["scoreContributionAllowed"] is False
    assert diagnostics["scoreExclusionReason"] == expected_score_exclusion_reason
    assert diagnostics["sourceAuthorityReason"] == expected_authority_reason
    assert expected_authority_reason in diagnostics["routeRejectedReasonCodes"]


def test_cache_snapshot_etf_flow_cannot_score_when_real_source_unavailable(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="cache",
            freshness="cached",
            items=[
                {
                    "symbol": "ETF",
                    "label": "ETF flow cache snapshot",
                    "value": 1.2,
                    "source": "cache",
                    "sourceType": "cache_snapshot",
                    "sourceLabel": "Cache Snapshot",
                }
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["us_etf_flow_proxy"]
    diagnostics = indicator["coverageDiagnostics"]

    assert indicator["status"] == "partial"
    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert diagnostics["realSourceAvailable"] is False
    assert diagnostics["missingProviderReason"] == "requires_authorized.us_etf_flow"
    assert diagnostics["scoreContributionAllowed"] is False
    assert diagnostics["scoreExclusionReason"] == "proxy_only_missing_real_source"
    assert diagnostics["requiredRealSourceForScore"] is True
    assert diagnostics["sourceTier"] == "snapshot"
    assert "missingProviderReason=requires_authorized.us_etf_flow" in diagnostics["activationHint"]


def test_cache_snapshot_representative_breadth_cannot_score_when_input_gates_are_false(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "us_breadth",
        _cache_entry(
            source="cache",
            freshness="cached",
            items=[
                {
                    "symbol": "SECTORS_UP",
                    "label": "Sectors Up",
                    "value": 2,
                    "source": "cache",
                    "sourceType": "cache_snapshot",
                },
                {
                    "symbol": "SECTORS_DOWN",
                    "label": "Sectors Down",
                    "value": 9,
                    "source": "cache",
                    "sourceType": "cache_snapshot",
                },
                {
                    "symbol": "RSP_SPY",
                    "label": "RSP vs SPY",
                    "value": -0.7,
                    "changePercent": -0.7,
                    "source": "cache",
                    "sourceType": "cache_snapshot",
                },
                {
                    "symbol": "IWM_SPY",
                    "label": "IWM vs SPY",
                    "value": -0.8,
                    "changePercent": -0.8,
                    "source": "cache",
                    "sourceType": "cache_snapshot",
                },
                {
                    "symbol": "QQQ_SPY",
                    "label": "QQQ vs SPY",
                    "value": -0.6,
                    "changePercent": -0.6,
                    "source": "cache",
                    "sourceType": "cache_snapshot",
                },
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["us_breadth_proxy"]
    diagnostics = indicator["coverageDiagnostics"]
    evidence_inputs = {item["key"]: item for item in indicator["evidence"]["inputs"]}

    assert indicator["status"] == "live"
    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert diagnostics["realSourceAvailable"] is False
    assert diagnostics["missingProviderReason"] == "requires_official_or_authorized.us_market_breadth"
    assert diagnostics["scoreContributionAllowed"] is False
    assert diagnostics["scoreExclusionReason"] == "proxy_only_missing_real_source"
    assert diagnostics["sourceAuthorityReason"] == "representative_sample_not_full_market_breadth"
    assert "representative_sample_not_full_market_breadth" in diagnostics["routeRejectedReasonCodes"]
    assert evidence_inputs["SECTORS_UP"]["sourceAuthorityAllowed"] is False
    assert evidence_inputs["SECTORS_UP"]["scoreContributionAllowed"] is False
    assert evidence_inputs["RSP_SPY"]["sourceAuthorityAllowed"] is False
    assert evidence_inputs["RSP_SPY"]["scoreContributionAllowed"] is False


def test_score_assembly_ignores_blocked_cache_snapshot_etf_flow(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "crypto",
        _cache_entry(
            source="binance",
            freshness="live",
            items=[
                {
                    "symbol": "BTC",
                    "label": "BTC",
                    "changePercent": 1.4,
                    "value": 64000.0,
                    "source": "binance",
                    "sourceType": "exchange_public",
                },
                {
                    "symbol": "ETH",
                    "label": "ETH",
                    "changePercent": 1.1,
                    "value": 3300.0,
                    "source": "binance",
                    "sourceType": "exchange_public",
                },
                {
                    "symbol": "BNB",
                    "label": "BNB",
                    "changePercent": 0.7,
                    "value": 610.0,
                    "source": "binance",
                    "sourceType": "exchange_public",
                },
                {
                    "symbol": "BTC_FUNDING",
                    "label": "BTC Funding",
                    "value": 0.011,
                    "changePercent": 0.011,
                    "source": "binance",
                    "sourceType": "exchange_public",
                },
                {
                    "symbol": "ETH_FUNDING",
                    "label": "ETH Funding",
                    "value": 0.009,
                    "changePercent": 0.009,
                    "source": "binance",
                    "sourceType": "exchange_public",
                },
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "volatility",
        _cache_entry(
            source="fred",
            freshness="cached",
            items=[
                _official_vix_item(value=15.2, change_percent=-2.5, as_of=now)
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "rates",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "US2Y",
                    "label": "US 2Y",
                    "value": 4.62,
                    "changePercent": -0.22,
                    "source": "treasury",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                },
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.31,
                    "changePercent": -0.31,
                    "source": "treasury",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": 4.58,
                    "changePercent": -0.18,
                    "source": "treasury",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                },
                {
                    "symbol": "SOFR",
                    "label": "SOFR",
                    "value": 5.31,
                    "source": "fred",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED SOFR",
                    "unit": "%",
                },
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="cache",
            freshness="cached",
            items=[
                {
                    "symbol": "ETF",
                    "label": "ETF flow cache snapshot",
                    "value": 1.2,
                    "source": "cache",
                    "sourceType": "cache_snapshot",
                }
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    with patch(
        "src.services.liquidity_monitor_service.fetch_binance_funding_row",
        side_effect=RuntimeError("network disabled"),
    ):
        payload = service.get_liquidity_monitor()

    indicators = _indicators_by_key(payload)

    assert indicators["crypto_spot_momentum"]["includedInScore"] is True
    assert indicators["vix_pressure"]["includedInScore"] is True
    assert indicators["us_rates_pressure"]["includedInScore"] is True
    assert indicators["us_etf_flow_proxy"]["includedInScore"] is False
    assert indicators["us_etf_flow_proxy"]["scoreContribution"] == 0
    assert payload["score"]["includedIndicatorCount"] == 3
    assert payload["score"]["includedIndicatorWeight"] == 20
    assert payload["score"]["value"] == 66


def test_liquidity_provider_activation_diagnostics_classify_proxy_indicators_and_cap_score(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "volatility",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 15.2,
                    "changePercent": -2.5,
                    "source": "yfinance_proxy",
                    "sourceType": "unofficial_proxy",
                    "sourceLabel": "Yahoo Finance",
                }
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "fx_commodities",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[
                {
                    "symbol": "DXY",
                    "label": "DXY",
                    "changePercent": -0.42,
                    "value": 103.8,
                    "source": "yfinance_proxy",
                    "sourceType": "unofficial_proxy",
                    "sourceLabel": "Yahoo Finance",
                }
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "rates",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[
                {
                    "symbol": "US10Y",
                    "label": "10Y yield",
                    "changePercent": -0.31,
                    "value": 4.31,
                    "source": "yfinance_proxy",
                    "sourceType": "unofficial_proxy",
                    "sourceLabel": "Yahoo Finance",
                },
                {
                    "symbol": "US30Y",
                    "label": "30Y yield",
                    "changePercent": -0.18,
                    "value": 4.58,
                    "source": "yfinance_proxy",
                    "sourceType": "unofficial_proxy",
                    "sourceLabel": "Yahoo Finance",
                },
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[
                {
                    "symbol": "ETF",
                    "label": "ETF flow proxy",
                    "value": 1.2,
                    "source": "yfinance_proxy",
                    "sourceType": "unofficial_proxy",
                    "sourceLabel": "Yahoo Finance",
                }
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "us_breadth",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[
                {"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 6, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
                {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 5, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
                {"symbol": "RSP_SPY", "label": "RSP vs SPY", "value": -0.4, "changePercent": -0.4, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
                {"symbol": "IWM_SPY", "label": "IWM vs SPY", "value": -0.5, "changePercent": -0.5, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
                {"symbol": "QQQ_SPY", "label": "QQQ vs SPY", "value": -0.2, "changePercent": -0.2, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicators = _indicators_by_key(payload)

    expectations = {
        "vix_pressure": ("official_public.vix_or_volatility", 8),
        "us_rates_pressure": ("official_public.us_treasury_curve", 6),
        "us_etf_flow_proxy": ("authorized.us_etf_flow", 5),
        "us_breadth_proxy": ("official_or_authorized.us_market_breadth", 6),
    }
    for key, (provider_class, max_abs_score) in expectations.items():
        diagnostics = _activation(payload, key)
        _assert_activation_fields(diagnostics)
        assert diagnostics["requiredProviderClass"] == provider_class
        assert diagnostics["configuredProviderAvailable"] is True
        assert diagnostics["realSourceAvailable"] is False
        assert diagnostics["proxyOnly"] is True
        assert diagnostics["observationOnly"] is False
        assert diagnostics["scoreContributionAllowed"] is False
        assert diagnostics["scoreExclusionReason"] == "proxy_only_missing_real_source"
        assert diagnostics["requiredRealSourceForScore"] is True
        assert diagnostics["proxyObservationOnlyReason"] == "proxy_only_missing_real_source"
        assert diagnostics["sourceTier"] == "unofficial_public_api"
        assert diagnostics["missingProviderReason"]
        assert indicators[key]["includedInScore"] is False
        assert indicators[key]["scoreContribution"] == 0
        assert diagnostics["scoreContribution"] == 0
        assert diagnostics["capReason"] == "partial_coverage"

    usd_diagnostics = _activation(payload, "usd_pressure")
    _assert_activation_fields(usd_diagnostics)
    assert usd_diagnostics["requiredProviderClass"] == "official_public.usd_pressure"
    assert usd_diagnostics["configuredProviderAvailable"] is True
    assert usd_diagnostics["realSourceAvailable"] is False
    assert usd_diagnostics["proxyOnly"] is False
    assert usd_diagnostics["observationOnly"] is False
    assert usd_diagnostics["scoreContributionAllowed"] is False
    assert usd_diagnostics["scoreExclusionReason"] == "usd_pressure_missing_series"
    assert usd_diagnostics["requiredRealSourceForScore"] is True
    assert usd_diagnostics["proxyObservationOnlyReason"] is None
    assert usd_diagnostics["sourceTier"] == "unavailable"
    assert usd_diagnostics["trustLevel"] == "unavailable"
    assert usd_diagnostics["missingInputs"] == ["USD_TWI"]
    assert usd_diagnostics["missingProviderReason"] == "requires_official_public.usd_pressure"
    usd_inputs = {str(item.get("key")): item for item in indicators["usd_pressure"]["evidence"]["inputs"]}
    assert usd_inputs["USD_TWI"]["sourceTier"] == "official_public"
    assert usd_inputs["USD_TWI"]["trustLevel"] == "unavailable"
    assert indicators["usd_pressure"]["includedInScore"] is False
    assert indicators["usd_pressure"]["scoreContribution"] == 0
    assert usd_diagnostics["scoreContribution"] == 0
    assert usd_diagnostics["capReason"] == "unavailable_source"


def test_cn_flow_indicator_uses_reliable_flow_basket_and_cn_breadth_context(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "cn_flows",
        _cache_entry(
            source="eastmoney",
            freshness="live",
            items=[
                {"symbol": "SOUTHBOUND", "label": "Southbound", "value": 28.4},
                {"symbol": "MAINLAND_MAIN", "label": "Mainland main", "value": 18.5},
                {"symbol": "MARGIN_BALANCE", "label": "Margin balance", "value": 31.2},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "cn_breadth",
        _cache_entry(
            source="eastmoney",
            freshness="live",
            items=[
                {"symbol": "EFFECT", "label": "赚钱效应", "value": 64},
                {"symbol": "ADV_RATIO", "label": "上涨比例", "value": 63.2},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicators = {item["key"]: item for item in payload["indicators"]}

    assert indicators["cn_hk_flows"]["includedInScore"] is False
    assert indicators["cn_hk_flows"]["scoreContribution"] == 0
    diagnostics = indicators["cn_hk_flows"]["coverageDiagnostics"]
    _assert_activation_fields(diagnostics)
    assert diagnostics["requiredProviderClass"] == "authorized.cn_hk_connect_flow"
    assert diagnostics["configuredProviderAvailable"] is True
    assert diagnostics["realSourceAvailable"] is False
    assert diagnostics["proxyOnly"] is False
    assert diagnostics["observationOnly"] is True
    assert diagnostics["scoreContributionAllowed"] is False
    assert diagnostics["missingProviderReason"] == "requires_authorized.cn_hk_connect_flow"
    assert diagnostics["paidDataLikelyRequired"] is True
    assert "宽度" in indicators["cn_hk_flows"]["summary"]


def test_authorized_cn_hk_flow_diagnostics_remain_observation_only_and_non_scoring(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = datetime(2026, 5, 23, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    cn_flow_payload = _cache_entry(
        source=AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID,
        freshness="delayed",
        items=[
            {
                "symbol": "NORTHBOUND",
                "label": "Northbound",
                "value": 42.6,
                "source": AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID,
                "sourceType": "authorized_licensed_feed",
                "sourceTier": "authorized_licensed_feed",
                "observationOnly": True,
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": False,
            },
            {
                "symbol": "SOUTHBOUND",
                "label": "Southbound",
                "value": -18.4,
                "source": AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID,
                "sourceType": "authorized_licensed_feed",
                "sourceTier": "authorized_licensed_feed",
                "observationOnly": True,
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": False,
            },
        ],
        updated_at=now,
        as_of=now,
    )
    cn_flow_payload.update(
        {
            "providerId": AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID,
            "sourceType": "authorized_licensed_feed",
            "sourceTier": "authorized_licensed_feed",
            "cacheOnly": True,
            "observationOnly": True,
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": False,
            "coverageRatio": 0.4,
            "fulfilledMetrics": ["NORTHBOUND", "SOUTHBOUND"],
            "missingMetrics": ["MAINLAND_MAIN", "CN_ETF", "MARGIN_BALANCE"],
        }
    )
    service.cache.set("cn_flows", cn_flow_payload, ttl_seconds=30)

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["cn_hk_flows"]
    diagnostics = indicator["coverageDiagnostics"]

    assert indicator["status"] == "partial"
    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    _assert_activation_fields(diagnostics)
    assert diagnostics["requiredProviderClass"] == AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID
    assert diagnostics["configuredProviderAvailable"] is True
    assert diagnostics["realSourceAvailable"] is True
    assert diagnostics["observationOnly"] is True
    assert diagnostics["scoreContributionAllowed"] is False
    assert diagnostics["scoreExclusionReason"] == "observation_only"
    assert diagnostics["missingProviderReason"] is None
    assert diagnostics["sourceTier"] == "authorized_licensed_feed"
    evidence_inputs = indicator["evidence"]["inputs"]
    assert {item["key"] for item in evidence_inputs} == {"NORTHBOUND", "SOUTHBOUND"}
    assert all(item["scoreContributionAllowed"] is False for item in evidence_inputs)


def test_liquidity_provider_activation_keeps_cn_money_and_futures_observation_only(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "rates",
        _cache_entry(
            source="fallback",
            freshness="fallback",
            is_fallback=True,
            items=[
                {"symbol": "DR007", "label": "DR007", "value": 1.8, "source": "fallback", "sourceType": "fallback_static"},
                {"symbol": "SHIBOR", "label": "SHIBOR", "value": 1.9, "source": "fallback", "sourceType": "fallback_static"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "futures",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[
                {"symbol": "NQ", "label": "Nasdaq futures", "changePercent": 0.6, "value": 18900, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
                {"symbol": "ES", "label": "S&P futures", "changePercent": 0.4, "value": 5280, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicators = _indicators_by_key(payload)

    cn_money = indicators["cn_money_market_rates"]
    cn_money_diagnostics = cn_money["coverageDiagnostics"]
    _assert_activation_fields(cn_money_diagnostics)
    assert cn_money["includedInScore"] is False
    assert cn_money["scoreContribution"] == 0
    assert cn_money_diagnostics["requiredProviderClass"] == "official_public.cn_money_market_rates"
    assert cn_money_diagnostics["realSourceAvailable"] is False
    assert cn_money_diagnostics["observationOnly"] is True
    assert cn_money_diagnostics["scoreContributionAllowed"] is False
    assert cn_money_diagnostics["missingProviderReason"] == "requires_official_public.cn_money_market_rates"

    futures = indicators["futures_premarket"]
    futures_diagnostics = futures["coverageDiagnostics"]
    _assert_activation_fields(futures_diagnostics)
    assert futures["includedInScore"] is False
    assert futures["scoreContribution"] == 0
    assert futures_diagnostics["requiredProviderClass"] == "exchange_or_broker_authorized.index_futures"
    assert futures_diagnostics["configuredProviderAvailable"] is True
    assert futures_diagnostics["realSourceAvailable"] is False
    assert futures_diagnostics["proxyOnly"] is True
    assert futures_diagnostics["observationOnly"] is True
    assert futures_diagnostics["scoreContributionAllowed"] is False
    assert futures_diagnostics["paidDataLikelyRequired"] is True
    assert futures_diagnostics["requiredInputs"] == ["NQ", "ES", "YM", "RTY"]
    assert futures_diagnostics["missingInputs"] == ["YM", "RTY"]
    assert futures_diagnostics["scoreExclusionReason"] == "observation_only"


def test_liquidity_cn_money_official_cache_rows_remain_observation_only_non_scoring(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "rates",
        _cache_entry(
            source=OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
            freshness="delayed",
            items=[
                {
                    "symbol": "DR007",
                    "label": "DR007",
                    "value": 1.86,
                    "changePercent": -3.13,
                    "unit": "%",
                    "source": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
                    "sourceLabel": "Official CN Money Market Rates diagnostic cache",
                    "sourceType": "official_public",
                    "sourceTier": "official_public",
                    "trustLevel": "score_grade_when_configured",
                    "officialSeriesId": "DR007",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": False,
                    "observationOnly": True,
                    "isFallback": False,
                    "freshness": "delayed",
                },
                {
                    "symbol": "SHIBOR",
                    "label": "SHIBOR overnight",
                    "value": 1.72,
                    "changePercent": -1.71,
                    "unit": "%",
                    "source": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
                    "sourceLabel": "Official CN Money Market Rates diagnostic cache",
                    "sourceType": "official_public",
                    "sourceTier": "official_public",
                    "trustLevel": "score_grade_when_configured",
                    "officialSeriesId": "SHIBOR_ON",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": False,
                    "observationOnly": True,
                    "isFallback": False,
                    "freshness": "delayed",
                },
                {
                    "symbol": "CN10Y",
                    "label": "China 10Y government bond yield context",
                    "value": 2.35,
                    "changePercent": 0.0,
                    "unit": "%",
                    "source": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
                    "sourceLabel": "Official CN Money Market Rates diagnostic cache",
                    "sourceType": "official_public",
                    "sourceTier": "official_public",
                    "trustLevel": "score_grade_when_configured",
                    "officialSeriesId": "CN10Y",
                    "sourceAuthorityAllowed": False,
                    "sourceAuthorityReason": "cn10y_context_only_not_yield_curve_authority",
                    "scoreContributionAllowed": False,
                    "observationOnly": True,
                    "isFallback": False,
                    "freshness": "delayed",
                },
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["cn_money_market_rates"]
    diagnostics = indicator["coverageDiagnostics"]

    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert diagnostics["requiredProviderClass"] == OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID
    assert diagnostics["configuredProviderAvailable"] is True
    assert diagnostics["realSourceAvailable"] is True
    assert diagnostics["observationOnly"] is True
    assert diagnostics["scoreContributionAllowed"] is False
    assert diagnostics["scoreExclusionReason"] == "observation_only"
    assert diagnostics["missingProviderReason"] is None
    bundle = diagnostics["cacheBundleDiagnostics"]
    assert bundle["providerId"] == OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID
    assert bundle["requiredSeries"] == ["DR007", "SHIBOR_ON"]
    assert bundle["fulfilledSeries"] == ["DR007", "SHIBOR_ON"]
    assert bundle["missingSeries"] == []
    assert bundle["coverageRatio"] == 1.0
    assert bundle["readinessEligible"] is True
    assert bundle["scoreGradeEvidenceAllowed"] is True
    assert bundle["cacheSafeOfficialEvidenceAllowed"] is True
    assert bundle["contextSeries"] == ["CN10Y"]
    assert bundle["contextOnlySeries"] == ["CN10Y"]
    assert bundle["externalProviderCalls"] is False
    assert bundle["observationOnly"] is False
    assert bundle["scoreContributionAllowed"] is True
    assert "cn10y_context_only_not_yield_curve_authority" in str(bundle)
    assert all(item["scoreContributionAllowed"] is False for item in indicator["evidence"]["inputs"])


def test_liquidity_cn_money_degraded_official_cache_rows_stay_observation_only(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "rates",
        _cache_entry(
            source=OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
            freshness="stale",
            items=[
                {
                    "symbol": "DR007",
                    "label": "DR007",
                    "value": 1.86,
                    "unit": "%",
                    "source": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
                    "sourceType": "official_public",
                    "sourceTier": "official_public",
                    "officialSeriesId": "DR007",
                    "freshness": "stale",
                    "isStale": True,
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                },
                {
                    "symbol": "SHIBOR",
                    "label": "SHIBOR overnight",
                    "value": 1.72,
                    "unit": "%",
                    "source": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
                    "sourceType": "official_public",
                    "sourceTier": "official_public",
                    "officialSeriesId": "SHIBOR_ON",
                    "freshness": "stale",
                    "isStale": True,
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                },
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["cn_money_market_rates"]
    diagnostics = indicator["coverageDiagnostics"]

    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert diagnostics["observationOnly"] is True
    assert diagnostics["scoreContributionAllowed"] is False
    assert diagnostics["realSourceAvailable"] is False
    assert diagnostics["missingProviderReason"] == f"requires_{OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID}"


def test_binance_crypto_activation_keeps_exchange_public_spot_scoring(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "crypto",
        _cache_entry(
            source="binance",
            freshness="live",
            items=[
                {"symbol": "BTC", "label": "BTC", "changePercent": 1.4, "value": 64000.0, "source": "binance", "sourceType": "exchange_public"},
                {"symbol": "ETH", "label": "ETH", "changePercent": 1.1, "value": 3300.0, "source": "binance", "sourceType": "exchange_public"},
                {"symbol": "BNB", "label": "BNB", "changePercent": 0.7, "value": 610.0, "source": "binance", "sourceType": "exchange_public"},
                {"symbol": "BTC_FUNDING", "label": "BTC Funding", "value": 0.011, "changePercent": 0.011, "source": "binance", "sourceType": "exchange_public"},
                {"symbol": "ETH_FUNDING", "label": "ETH Funding", "value": 0.009, "changePercent": 0.009, "source": "binance", "sourceType": "exchange_public"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicators = _indicators_by_key(payload)

    spot = indicators["crypto_spot_momentum"]
    spot_diagnostics = spot["coverageDiagnostics"]
    _assert_activation_fields(spot_diagnostics)
    assert spot["includedInScore"] is True
    assert spot["scoreContribution"] == 6
    assert spot_diagnostics["requiredProviderClass"] == "exchange_public.crypto_spot"
    assert spot_diagnostics["configuredProviderAvailable"] is True
    assert spot_diagnostics["realSourceAvailable"] is True
    assert spot_diagnostics["proxyOnly"] is False
    assert spot_diagnostics["observationOnly"] is False
    assert spot_diagnostics["scoreContributionAllowed"] is True
    assert spot_diagnostics["sourceAuthorityRouteRejected"] is False
    assert spot_diagnostics["sourceAuthorityReason"] is None
    assert spot_diagnostics["routeRejectedReasonCodes"] == []
    assert spot_diagnostics["sourceTier"] == "exchange_public"
    assert spot_diagnostics["trustLevel"] == "reliable"

    funding = indicators["crypto_funding"]
    funding_diagnostics = funding["coverageDiagnostics"]
    _assert_activation_fields(funding_diagnostics)
    assert funding["includedInScore"] is False
    assert funding["scoreContribution"] == 0
    assert funding_diagnostics["requiredProviderClass"] == "exchange_public.crypto_funding"
    assert funding_diagnostics["configuredProviderAvailable"] is True
    assert funding_diagnostics["realSourceAvailable"] is True
    assert funding_diagnostics["observationOnly"] is True
    assert funding_diagnostics["scoreContributionAllowed"] is False


def test_coinbase_crypto_inputs_cannot_claim_liquidity_score_authority(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = datetime(2026, 5, 7, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "crypto",
        _cache_entry(
            source="coinbase_public",
            freshness="live",
            items=[
                {
                    "symbol": "BTC",
                    "label": "BTC",
                    "changePercent": 1.4,
                    "value": 64000.0,
                    "source": "coinbase_public",
                    "sourceType": "exchange_public",
                },
                {
                    "symbol": "ETH",
                    "label": "ETH",
                    "changePercent": 1.1,
                    "value": 3300.0,
                    "source": "coinbase_public",
                    "sourceType": "exchange_public",
                },
                {
                    "symbol": "BNB",
                    "label": "BNB",
                    "changePercent": 0.7,
                    "value": 610.0,
                    "source": "coinbase_public",
                    "sourceType": "exchange_public",
                },
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicators = _indicators_by_key(payload)

    spot = indicators["crypto_spot_momentum"]
    spot_diagnostics = spot["coverageDiagnostics"]
    assert spot["includedInScore"] is False
    assert spot["scoreContribution"] == 0
    assert spot_diagnostics["realSourceAvailable"] is False
    assert spot_diagnostics["scoreContributionAllowed"] is False
    assert spot_diagnostics["scoreExclusionReason"] == "source_authority_router_rejected"
    assert spot_diagnostics["sourceAuthorityRouteRejected"] is True
    assert spot_diagnostics["sourceAuthorityReason"] == "source_authority_router_rejected"
    assert "provider_forbidden_for_use_case" in spot_diagnostics["routeRejectedReasonCodes"]
    assert "provider_observation_only" in spot_diagnostics["routeRejectedReasonCodes"]
    assert "scoring_not_allowed" in spot_diagnostics["routeRejectedReasonCodes"]

def test_vix_indicator_uses_yfinance_proxy_when_volatility_panel_is_unavailable(isolated_db: DatabaseManager) -> None:
    service = _make_service(allow_external_provider_calls=True)
    quote_index = [
        datetime(2026, 5, 12, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 13, 16, 0, tzinfo=timezone.utc),
    ]
    quote_map = {
        "^VIX": _FakeHistoryFrame([18.0, 15.0], index=quote_index),
    }

    requested_tickers: list[str] = []

    def _fake_quote_history(ticker: str) -> _FakeHistoryFrame:
        requested_tickers.append(ticker)
        return quote_map.get(ticker, _FakeHistoryFrame([]))

    with patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", side_effect=_fake_quote_history, create=True):
        payload = service.get_liquidity_monitor()

    indicators = {item["key"]: item for item in payload["indicators"]}

    assert payload["sourceMetadata"]["externalProviderCalls"] is True
    assert indicators["vix_pressure"]["includedInScore"] is False
    assert indicators["vix_pressure"]["status"] == "partial"
    assert indicators["vix_pressure"]["freshness"] == "delayed"
    assert indicators["vix_pressure"]["scoreContribution"] == 0
    assert indicators["vix_pressure"]["coverageDiagnostics"]["scoreContributionAllowed"] is False
    assert indicators["vix_pressure"]["coverageDiagnostics"]["scoreExclusionReason"] == "proxy_only_missing_real_source"
    assert indicators["vix_pressure"]["coverageDiagnostics"]["requiredRealSourceForScore"] is True
    assert indicators["vix_pressure"]["coverageDiagnostics"]["proxyObservationOnlyReason"] == "proxy_only_missing_real_source"
    assert indicators["vix_pressure"]["coverageDiagnostics"]["capReason"] == "partial_coverage"
    assert "Yahoo Finance" in str(indicators["vix_pressure"]["summary"])
    assert "unofficial_proxy" in str(indicators["vix_pressure"]["summary"])


def test_vix_indicator_prefers_official_macro_cache_over_yfinance_proxy(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    official_as_of = "2026-05-12T16:15:00+08:00"
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 18.22,
                    "changePercent": -4.66,
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceTier": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "officialSeriesId": "VIXCLS",
                    "officialObservationDate": "2026-05-12",
                    "officialAsOf": "2026-05-12",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                    "sourceFreshnessEvidence": {
                        "freshness": "delayed",
                        "freshnessPolicy": "official_daily_us_weekday_t_plus_1",
                        "externalProviderCalls": False,
                        "isFallback": False,
                        "isStale": False,
                        "isUnavailable": False,
                    },
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                }
            ],
            updated_at=official_as_of,
            as_of=official_as_of,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = {item["key"]: item for item in payload["indicators"]}["vix_pressure"]

    assert indicator["includedInScore"] is True
    assert indicator["status"] == "partial"
    assert indicator["freshness"] == "cached"
    assert "FRED VIXCLS" in str(indicator["summary"])
    assert "official_public" in str(indicator["summary"])
    assert "Yahoo Finance" not in str(indicator["summary"])
    assert indicator["coverageDiagnostics"]["realSourceAvailable"] is True
    assert indicator["coverageDiagnostics"]["scoreContributionAllowed"] is True
    assert indicator["evidence"]["inputs"][0]["officialSeriesId"] == "VIXCLS"
    assert indicator["evidence"]["inputs"][0]["sourceAuthorityAllowed"] is True
    assert indicator["evidence"]["inputs"][0]["scoreContributionAllowed"] is True


def test_vix_indicator_requires_explicit_official_vix_authority_before_score_grade(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    official_as_of = "2026-05-12T16:15:00+08:00"
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 18.22,
                    "changePercent": -4.66,
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceTier": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "officialSeriesId": "VIXCLS",
                    "officialObservationDate": "2026-05-12",
                    "officialAsOf": "2026-05-12",
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                }
            ],
            updated_at=official_as_of,
            as_of=official_as_of,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = {item["key"]: item for item in payload["indicators"]}["vix_pressure"]
    diagnostics = indicator["coverageDiagnostics"]
    evidence_input = indicator["evidence"]["inputs"][0]

    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert diagnostics["realSourceAvailable"] is False
    assert diagnostics["scoreContributionAllowed"] is False
    assert diagnostics["scoreExclusionReason"] == "official_vix_authority_not_explicit"
    assert diagnostics["sourceAuthorityReason"] == "official_vix_authority_not_explicit"
    assert evidence_input["sourceAuthorityAllowed"] is False
    assert evidence_input["scoreContributionAllowed"] is False
    assert evidence_input["sourceAuthorityReason"] == "official_vix_authority_not_explicit"


def test_vix_indicator_ignores_malformed_official_macro_cache_and_keeps_cached_proxy_truthful(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    as_of = "2026-05-12T16:15:00+08:00"
    service.cache.set(
        "volatility",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 15.2,
                    "changePercent": -2.5,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                    "asOf": as_of,
                    "updatedAt": as_of,
                }
            ],
            updated_at=as_of,
            as_of=as_of,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": None,
                    "changePercent": "oops",
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "asOf": as_of,
                    "updatedAt": as_of,
                }
            ],
            updated_at=as_of,
            as_of=as_of,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = {item["key"]: item for item in payload["indicators"]}["vix_pressure"]

    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert indicator["coverageDiagnostics"]["scoreExclusionReason"] == "proxy_only_missing_real_source"
    assert indicator["freshness"] == "delayed"
    assert "Yahoo Finance" in str(indicator["summary"])
    assert "类型 official_public" not in str(indicator["summary"])
    assert "类型 unofficial_proxy" in str(indicator["summary"])
    assert "FRED VIXCLS" not in str(indicator["summary"])


def test_yfinance_proxy_panels_remain_delayed_and_not_live_provider_labels(isolated_db: DatabaseManager) -> None:
    service = _make_service(allow_external_provider_calls=True)
    quote_index = [
        datetime(2026, 5, 12, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 13, 16, 0, tzinfo=timezone.utc),
    ]
    quote_map = {
        "^VIX": _FakeHistoryFrame([18.0, 15.0], index=quote_index),
    }

    def _fake_quote_history(ticker: str) -> _FakeHistoryFrame:
        return quote_map.get(ticker, _FakeHistoryFrame([]))

    with patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", side_effect=_fake_quote_history, create=True):
        payload = service.get_liquidity_monitor()

    indicator = {item["key"]: item for item in payload["indicators"]}["vix_pressure"]

    assert indicator["freshness"] == "delayed"
    assert indicator["status"] == "partial"
    assert "新鲜度 delayed" in str(indicator["summary"])
    assert "新鲜度 live" not in str(indicator["summary"])
    assert "类型 unofficial_proxy" in str(indicator["summary"])
    assert "类型 official_public" not in str(indicator["summary"])


def test_vix_indicator_normalizes_cached_yfinance_proxy_live_freshness(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    as_of = "2026-05-12T16:15:00+08:00"
    service.cache.set(
        "volatility",
        _cache_entry(
            source="yfinance_proxy",
            freshness="live",
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 15.2,
                    "changePercent": -2.5,
                    "source": "yfinance_proxy",
                    "sourceType": "unofficial_proxy",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "live",
                    "asOf": as_of,
                    "updatedAt": as_of,
                }
            ],
            updated_at=as_of,
            as_of=as_of,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = {item["key"]: item for item in payload["indicators"]}["vix_pressure"]

    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert indicator["status"] == "partial"
    assert indicator["freshness"] == "delayed"
    assert indicator["freshness"] not in {"live", "fresh"}
    assert indicator["evidence"]["inputs"][0]["freshness"] == "delayed"
    assert indicator["coverageDiagnostics"]["sourceTier"] == "unofficial_public_api"
    assert indicator["coverageDiagnostics"]["trustLevel"] == "usable_with_caution"
    assert indicator["coverageDiagnostics"]["freshness"] == "partial"
    assert indicator["coverageDiagnostics"]["scoreContributionAllowed"] is False
    assert indicator["coverageDiagnostics"]["scoreExclusionReason"] == "proxy_only_missing_real_source"
    assert "新鲜度 delayed" in str(indicator["summary"])
    assert "新鲜度 live" not in str(indicator["summary"])


def test_usd_pressure_does_not_use_yfinance_dxy_proxy_when_official_series_is_missing(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    quote_index = [
        datetime(2026, 5, 12, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 13, 16, 0, tzinfo=timezone.utc),
    ]
    quote_map = {
        "DX-Y.NYB": _FakeHistoryFrame([104.9, 104.2], index=quote_index),
    }

    requested_tickers: list[str] = []

    def _fake_quote_history(ticker: str) -> _FakeHistoryFrame:
        requested_tickers.append(ticker)
        return quote_map.get(ticker, _FakeHistoryFrame([]))

    with patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", side_effect=_fake_quote_history, create=True):
        payload = service.get_liquidity_monitor()

    indicators = {item["key"]: item for item in payload["indicators"]}
    usd_pressure = indicators["usd_pressure"]
    inputs = {str(item.get("key")): item for item in usd_pressure["evidence"]["inputs"]}

    assert "DX-Y.NYB" not in requested_tickers
    assert usd_pressure["includedInScore"] is False
    assert usd_pressure["status"] == "unavailable"
    assert usd_pressure["freshness"] == "unavailable"
    assert usd_pressure["scoreContribution"] == 0
    assert usd_pressure["coverageDiagnostics"]["scoreContributionAllowed"] is False
    assert usd_pressure["coverageDiagnostics"]["scoreExclusionReason"] == "usd_pressure_missing_series"
    assert usd_pressure["coverageDiagnostics"]["missingInputs"] == ["USD_TWI"]
    assert usd_pressure["coverageDiagnostics"]["missingProviderReason"] == "requires_official_public.usd_pressure"
    assert inputs["USD_TWI"]["officialSeriesId"] == "DTWEXBGS"
    assert inputs["USD_TWI"]["sourceAuthorityAllowed"] is False
    assert inputs["USD_TWI"]["scoreContributionAllowed"] is False
    assert inputs["USD_TWI"]["sourceAuthorityReason"] == "usd_pressure_missing_series"
    assert "DTWEXBGS" in str(usd_pressure["summary"])
    assert "DXY" not in str(usd_pressure["summary"])
    assert "Yahoo Finance" not in str(usd_pressure["summary"])


def test_us_rates_indicator_uses_yfinance_treasury_proxies_when_rates_panel_is_unavailable(isolated_db: DatabaseManager) -> None:
    service = _make_service(allow_external_provider_calls=True)
    quote_index = [
        datetime(2026, 5, 12, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 13, 16, 0, tzinfo=timezone.utc),
    ]
    quote_map = {
        "^TNX": _FakeHistoryFrame([45.8, 44.9], index=quote_index),
        "^TYX": _FakeHistoryFrame([47.5, 46.9], index=quote_index),
    }

    def _fake_quote_history(ticker: str) -> _FakeHistoryFrame:
        return quote_map.get(ticker, _FakeHistoryFrame([]))

    with patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", side_effect=_fake_quote_history, create=True):
        payload = service.get_liquidity_monitor()

    indicators = {item["key"]: item for item in payload["indicators"]}

    assert payload["sourceMetadata"]["externalProviderCalls"] is True
    assert indicators["us_rates_pressure"]["includedInScore"] is False
    assert indicators["us_rates_pressure"]["status"] == "partial"
    assert indicators["us_rates_pressure"]["freshness"] == "delayed"
    assert indicators["us_rates_pressure"]["scoreContribution"] == 0
    assert indicators["us_rates_pressure"]["coverageDiagnostics"]["scoreContributionAllowed"] is False
    assert indicators["us_rates_pressure"]["coverageDiagnostics"]["scoreExclusionReason"] == "proxy_only_missing_real_source"
    assert indicators["us_rates_pressure"]["coverageDiagnostics"]["capReason"] == "partial_coverage"
    assert "US10Y" in str(indicators["us_rates_pressure"]["summary"])
    assert "US30Y" in str(indicators["us_rates_pressure"]["summary"])
    assert "Yahoo Finance" in str(indicators["us_rates_pressure"]["summary"])


def test_us_rates_indicator_prefers_official_macro_cache_and_keeps_sofr_observation_only(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    official_as_of = "2026-05-12T16:15:00+08:00"
    service.cache.set(
        "rates",
        _cache_entry(
            source="yahoo",
            freshness="live",
            items=[
                {"symbol": "US2Y", "label": "2Y yield", "changePercent": 0.15, "value": 4.82, "source": "yahoo"},
                {"symbol": "US10Y", "label": "10Y yield", "changePercent": 0.28, "value": 4.51, "source": "yahoo"},
                {"symbol": "US30Y", "label": "30Y yield", "changePercent": 0.12, "value": 4.72, "source": "yahoo"},
            ],
            updated_at=official_as_of,
            as_of=official_as_of,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "US2Y",
                    "label": "US 2Y",
                    "value": 4.62,
                    "changePercent": -0.22,
                    "source": "treasury",
                    "sourceId": "treasury:DGS2",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                },
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.31,
                    "changePercent": -0.31,
                    "source": "treasury",
                    "sourceId": "treasury:DGS10",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": 4.58,
                    "changePercent": -0.18,
                    "source": "treasury",
                    "sourceId": "treasury:DGS30",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                },
                {
                    "symbol": "SOFR",
                    "label": "SOFR",
                    "value": 5.31,
                    "source": "fred",
                    "sourceId": "fred:SOFR",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED SOFR",
                    "unit": "%",
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                },
            ],
            updated_at=official_as_of,
            as_of=official_as_of,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = {item["key"]: item for item in payload["indicators"]}["us_rates_pressure"]
    diagnostic = indicator["coverageDiagnostics"]

    assert indicator["includedInScore"] is True
    assert indicator["status"] == "partial"
    assert indicator["freshness"] == "cached"
    assert indicator["scoreContribution"] == 4
    assert diagnostic["realSourceAvailable"] is True
    assert diagnostic["proxyOnly"] is False
    assert diagnostic["scoreContributionAllowed"] is True
    assert diagnostic["scoreExclusionReason"] is None
    assert diagnostic["requiredRealSourceForScore"] is True
    assert indicator["coverageDiagnostics"]["capReason"] == "partial_coverage"
    assert "US2Y -0.22%" in str(indicator["summary"])
    assert "US10Y -0.31%" in str(indicator["summary"])
    assert "US30Y -0.18%" in str(indicator["summary"])
    assert "SOFR +5.31" in str(indicator["summary"])
    assert "Yahoo Finance" not in str(indicator["summary"])


def test_us_rates_indicator_requires_complete_official_daily_bundle_before_score_grade(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    official_as_of = "2026-05-12T16:15:00+08:00"
    service.cache.set(
        "rates",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "US2Y",
                    "label": "US 2Y",
                    "value": 4.62,
                    "changePercent": -0.22,
                    "source": "treasury",
                    "sourceId": "treasury:DGS2",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "sourceTier": "official_public",
                    "trustLevel": "reliable",
                    "unit": "%",
                    "freshness": "cached",
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                    "officialSeriesId": "DGS2",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                    "sourceFreshnessEvidence": {
                        "freshness": "cached",
                        "freshnessPolicy": "official_daily_us_weekday_t_plus_1",
                        "externalProviderCalls": False,
                        "isFallback": False,
                        "isStale": False,
                        "isUnavailable": False,
                    },
                },
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.31,
                    "changePercent": -0.31,
                    "source": "treasury",
                    "sourceId": "treasury:DGS10",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "sourceTier": "official_public",
                    "trustLevel": "reliable",
                    "unit": "%",
                    "freshness": "cached",
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                    "officialSeriesId": "DGS10",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                    "sourceFreshnessEvidence": {
                        "freshness": "cached",
                        "freshnessPolicy": "official_daily_us_weekday_t_plus_1",
                        "externalProviderCalls": False,
                        "isFallback": False,
                        "isStale": False,
                        "isUnavailable": False,
                    },
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": 4.58,
                    "changePercent": -0.18,
                    "source": "treasury",
                    "sourceId": "treasury:DGS30",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "sourceTier": "official_public",
                    "trustLevel": "reliable",
                    "unit": "%",
                    "freshness": "cached",
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                    "officialSeriesId": "DGS30",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                    "sourceFreshnessEvidence": {
                        "freshness": "cached",
                        "freshnessPolicy": "official_daily_us_weekday_t_plus_1",
                        "externalProviderCalls": False,
                        "isFallback": False,
                        "isStale": False,
                        "isUnavailable": False,
                    },
                },
            ],
            updated_at=official_as_of,
            as_of=official_as_of,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = {item["key"]: item for item in payload["indicators"]}["us_rates_pressure"]
    diagnostics = indicator["coverageDiagnostics"]
    inputs = {str(item.get("key")): item for item in indicator["evidence"]["inputs"]}
    bundle = indicator["evidence"]["cacheBundleDiagnostics"]

    assert indicator["includedInScore"] is True
    assert indicator["scoreContribution"] == 4
    assert diagnostics["realSourceAvailable"] is True
    assert diagnostics["scoreContributionAllowed"] is True
    assert diagnostics["sourceAuthorityReason"] is None
    assert diagnostics["routeRejectedReasonCodes"] == []
    assert bundle["readinessEligible"] is True
    assert bundle["scoreGradeEvidenceAllowed"] is True
    assert bundle["coverageRatio"] == 1.0
    assert bundle["externalProviderCalls"] is False
    freshness_policies = bundle["sourceFreshnessEvidence"]["freshnessPolicies"]
    for series_id in ("DGS2", "DGS10", "DGS30"):
        assert freshness_policies[series_id] == "official_daily_us_weekday_t_plus_1"
    for key in ("US2Y", "US10Y", "US30Y"):
        assert inputs[key]["sourceAuthorityAllowed"] is True
        assert inputs[key]["scoreContributionAllowed"] is True


def test_us_rates_indicator_keeps_partial_official_macro_cache_observation_only_when_rates_panel_is_unavailable(isolated_db: DatabaseManager) -> None:
    service = _make_service()
    official_as_of = "2026-05-12T16:15:00+08:00"
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.31,
                    "changePercent": -0.31,
                    "source": "treasury",
                    "sourceId": "treasury:DGS10",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": 4.58,
                    "changePercent": -0.18,
                    "source": "treasury",
                    "sourceId": "treasury:DGS30",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                },
            ],
            updated_at=official_as_of,
            as_of=official_as_of,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = {item["key"]: item for item in payload["indicators"]}["us_rates_pressure"]

    assert indicator["includedInScore"] is False
    assert indicator["status"] == "partial"
    assert indicator["freshness"] == "cached"
    assert indicator["scoreContribution"] == 0
    assert indicator["coverageDiagnostics"]["capReason"] == "partial_coverage"
    assert indicator["coverageDiagnostics"]["realSourceAvailable"] is False
    assert indicator["coverageDiagnostics"]["scoreContributionAllowed"] is False
    assert indicator["coverageDiagnostics"]["scoreExclusionReason"] == "us_rates_required_series_missing_or_stale"
    bundle = indicator["evidence"]["cacheBundleDiagnostics"]
    assert bundle["readinessEligible"] is False
    assert bundle["scoreGradeEvidenceAllowed"] is False
    assert bundle["fulfilledSeries"] == ["DGS10", "DGS30"]
    assert bundle["missingSeries"] == ["DGS2"]
    assert "US10Y" in str(indicator["summary"])
    assert "US30Y" in str(indicator["summary"])
    assert "US Treasury" in str(indicator["summary"])
    assert "Yahoo Finance" not in str(indicator["summary"])


def test_us_rates_indicator_falls_back_to_proxy_yields_when_official_yields_are_malformed(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service(allow_external_provider_calls=True)
    official_as_of = "2026-05-12T16:15:00+08:00"
    quote_index = [
        datetime(2026, 5, 12, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 13, 16, 0, tzinfo=timezone.utc),
    ]
    quote_map = {
        "^TNX": _FakeHistoryFrame([45.8, 44.9], index=quote_index),
        "^TYX": _FakeHistoryFrame([47.5, 46.9], index=quote_index),
    }
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.31,
                    "changePercent": "oops",
                    "source": "treasury",
                    "sourceId": "treasury:DGS10",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": None,
                    "changePercent": None,
                    "source": "treasury",
                    "sourceId": "treasury:DGS30",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "unit": "%",
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                },
                {
                    "symbol": "SOFR",
                    "label": "SOFR",
                    "value": 5.31,
                    "source": "fred",
                    "sourceId": "fred:SOFR",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED SOFR",
                    "unit": "%",
                    "asOf": official_as_of,
                    "updatedAt": official_as_of,
                },
            ],
            updated_at=official_as_of,
            as_of=official_as_of,
        ),
        ttl_seconds=30,
    )

    def _fake_quote_history(ticker: str) -> _FakeHistoryFrame:
        return quote_map.get(ticker, _FakeHistoryFrame([]))

    with patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", side_effect=_fake_quote_history, create=True):
        payload = service.get_liquidity_monitor()

    indicator = {item["key"]: item for item in payload["indicators"]}["us_rates_pressure"]

    assert payload["sourceMetadata"]["externalProviderCalls"] is True
    assert indicator["includedInScore"] is False
    assert indicator["freshness"] == "delayed"
    assert indicator["scoreContribution"] == 0
    assert indicator["coverageDiagnostics"]["scoreContributionAllowed"] is False
    assert indicator["coverageDiagnostics"]["scoreExclusionReason"] == "proxy_only_missing_real_source"
    assert indicator["coverageDiagnostics"]["capReason"] == "partial_coverage"
    assert "US10Y -1.97%" in str(indicator["summary"])
    assert "US30Y -1.26%" in str(indicator["summary"])
    assert "SOFR +5.31%" in str(indicator["summary"])
    assert "Yahoo Finance" in str(indicator["summary"])
    assert "FRED SOFR" in str(indicator["summary"])
    assert "unofficial_proxy / official_public" in str(indicator["summary"])


def test_freshness_latest_as_of_uses_selected_official_snapshot_when_snapshot_wins(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    stale_cache_as_of = "2026-05-15T12:00:00+08:00"
    fresh_snapshot_as_of = "2026-05-15T14:15:00+08:00"
    service.cache.set(
        "volatility",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 21.0,
                    "changePercent": 1.5,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                    "updatedAt": stale_cache_as_of,
                    "asOf": stale_cache_as_of,
                }
            ],
            updated_at=stale_cache_as_of,
            as_of=stale_cache_as_of,
        ),
        ttl_seconds=-1,
    )
    _save_market_overview_snapshot(
        isolated_db,
        key="volatility",
        payload=_raw_snapshot_payload(
            source="mixed",
            updated_at=fresh_snapshot_as_of,
            as_of=fresh_snapshot_as_of,
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 16.8,
                    "changePercent": -3.2,
                    "source": "fred",
                    "sourceId": "fred:VIXCLS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                    "updatedAt": fresh_snapshot_as_of,
                    "asOf": fresh_snapshot_as_of,
                }
            ],
        ),
    )
    earlier_official_as_of = "2026-05-15T14:10:00+08:00"
    service.cache.set(
        "rates",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.31,
                    "changePercent": -0.31,
                    "source": "treasury",
                    "sourceId": "treasury:DGS10",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "freshness": "cached",
                    "updatedAt": earlier_official_as_of,
                    "asOf": earlier_official_as_of,
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": 4.58,
                    "changePercent": -0.18,
                    "source": "treasury",
                    "sourceId": "treasury:DGS30",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "freshness": "cached",
                    "updatedAt": earlier_official_as_of,
                    "asOf": earlier_official_as_of,
                },
            ],
            updated_at=earlier_official_as_of,
            as_of=earlier_official_as_of,
        ),
        ttl_seconds=300,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[{"symbol": "ETF", "label": "ETF flow proxy", "value": 1.2, "updatedAt": earlier_official_as_of, "asOf": earlier_official_as_of}],
            updated_at=earlier_official_as_of,
            as_of=earlier_official_as_of,
        ),
        ttl_seconds=300,
    )

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=datetime(2026, 5, 15, 14, 20, tzinfo=CN_TZ)),
        patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", return_value=_FakeHistoryFrame([]), create=True),
        patch("src.services.liquidity_monitor_service.fetch_binance_funding_row", side_effect=RuntimeError("network disabled")),
    ):
        payload = service.get_liquidity_monitor()

    assert payload["freshness"]["latestAsOf"] == fresh_snapshot_as_of
    indicator = {item["key"]: item for item in payload["indicators"]}["vix_pressure"]
    assert indicator["updatedAt"] == fresh_snapshot_as_of
    assert "FRED VIXCLS" in str(indicator["summary"])


def test_us_rates_indicator_prefers_fresh_official_snapshot_over_newer_proxy_cache(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    proxy_cache_as_of = "2026-05-15T14:18:00+08:00"
    official_snapshot_as_of = "2026-05-15T14:10:00+08:00"
    service.cache.set(
        "rates",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {
                    "symbol": "US2Y",
                    "label": "2Y yield",
                    "value": 4.95,
                    "changePercent": 0.12,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "updatedAt": proxy_cache_as_of,
                    "asOf": proxy_cache_as_of,
                },
                {
                    "symbol": "US10Y",
                    "label": "10Y yield",
                    "value": 4.55,
                    "changePercent": 0.21,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "updatedAt": proxy_cache_as_of,
                    "asOf": proxy_cache_as_of,
                },
                {
                    "symbol": "US30Y",
                    "label": "30Y yield",
                    "value": 4.79,
                    "changePercent": 0.15,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "updatedAt": proxy_cache_as_of,
                    "asOf": proxy_cache_as_of,
                },
            ],
            updated_at=proxy_cache_as_of,
            as_of=proxy_cache_as_of,
        ),
        ttl_seconds=300,
    )
    _save_market_overview_snapshot(
        isolated_db,
        key="rates",
        payload=_raw_snapshot_payload(
            source="mixed",
            freshness="cached",
            updated_at=official_snapshot_as_of,
            as_of=official_snapshot_as_of,
            items=[
                {
                    "symbol": "US2Y",
                    "label": "US 2Y",
                    "value": 4.62,
                    "changePercent": -0.22,
                    "source": "treasury",
                    "sourceId": "treasury:DGS2",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "freshness": "cached",
                    "updatedAt": official_snapshot_as_of,
                    "asOf": official_snapshot_as_of,
                },
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.31,
                    "changePercent": -0.31,
                    "source": "treasury",
                    "sourceId": "treasury:DGS10",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "freshness": "cached",
                    "updatedAt": official_snapshot_as_of,
                    "asOf": official_snapshot_as_of,
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": 4.58,
                    "changePercent": -0.18,
                    "source": "treasury",
                    "sourceId": "treasury:DGS30",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "freshness": "cached",
                    "updatedAt": official_snapshot_as_of,
                    "asOf": official_snapshot_as_of,
                },
                {
                    "symbol": "SOFR",
                    "label": "SOFR",
                    "value": 5.31,
                    "source": "fred",
                    "sourceId": "fred:SOFR",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED SOFR",
                    "freshness": "cached",
                    "updatedAt": official_snapshot_as_of,
                    "asOf": official_snapshot_as_of,
                },
            ],
        ),
    )

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=datetime(2026, 5, 15, 14, 20, tzinfo=CN_TZ)),
        patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", return_value=_FakeHistoryFrame([]), create=True),
        patch("src.services.liquidity_monitor_service.fetch_binance_funding_row", side_effect=RuntimeError("network disabled")),
    ):
        payload = service.get_liquidity_monitor()

    indicator = {item["key"]: item for item in payload["indicators"]}["us_rates_pressure"]
    diagnostics = indicator["coverageDiagnostics"]

    assert indicator["updatedAt"] == official_snapshot_as_of
    assert diagnostics["realSourceAvailable"] is True
    assert diagnostics["proxyOnly"] is False
    assert diagnostics["scoreContributionAllowed"] is True
    assert diagnostics["scoreExclusionReason"] is None
    assert "US Treasury" in str(indicator["summary"])
    assert "SOFR +5.31" in str(indicator["summary"])
    assert "Yahoo Finance" not in str(indicator["summary"])


def test_stale_official_rates_snapshot_does_not_mask_newer_proxy_cache(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    proxy_cache_as_of = "2026-05-15T14:18:00+08:00"
    stale_official_as_of = "2026-05-01T14:10:00+08:00"
    service.cache.set(
        "rates",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {
                    "symbol": "US10Y",
                    "label": "10Y yield",
                    "value": 4.55,
                    "changePercent": -0.21,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                    "updatedAt": proxy_cache_as_of,
                    "asOf": proxy_cache_as_of,
                },
                {
                    "symbol": "US30Y",
                    "label": "30Y yield",
                    "value": 4.79,
                    "changePercent": -0.15,
                    "source": "yfinance_proxy",
                    "sourceType": "proxy_public",
                    "sourceLabel": "Yahoo Finance",
                    "freshness": "delayed",
                    "updatedAt": proxy_cache_as_of,
                    "asOf": proxy_cache_as_of,
                },
            ],
            updated_at=proxy_cache_as_of,
            as_of=proxy_cache_as_of,
        ),
        ttl_seconds=300,
    )
    _save_market_overview_snapshot(
        isolated_db,
        key="rates",
        payload=_raw_snapshot_payload(
            source="mixed",
            freshness="stale",
            updated_at=stale_official_as_of,
            as_of=stale_official_as_of,
            items=[
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.31,
                    "changePercent": -0.31,
                    "source": "treasury",
                    "sourceId": "treasury:DGS10",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "freshness": "stale",
                    "officialSeriesId": "DGS10",
                    "sourceAuthorityAllowed": False,
                    "scoreContributionAllowed": False,
                    "sourceAuthorityReason": "stale_official_row",
                    "trustLevel": "weak",
                    "updatedAt": stale_official_as_of,
                    "asOf": stale_official_as_of,
                },
                {
                    "symbol": "US30Y",
                    "label": "US 30Y",
                    "value": 4.58,
                    "changePercent": -0.18,
                    "source": "treasury",
                    "sourceId": "treasury:DGS30",
                    "sourceType": "official_public",
                    "sourceLabel": "US Treasury",
                    "freshness": "stale",
                    "officialSeriesId": "DGS30",
                    "sourceAuthorityAllowed": False,
                    "scoreContributionAllowed": False,
                    "sourceAuthorityReason": "stale_official_row",
                    "trustLevel": "weak",
                    "updatedAt": stale_official_as_of,
                    "asOf": stale_official_as_of,
                },
            ],
        ),
    )

    with (
        patch.object(LiquidityMonitorService, "_now", return_value=datetime(2026, 5, 15, 14, 20, tzinfo=CN_TZ)),
        patch("src.services.liquidity_monitor_service.fetch_yfinance_quote_history_frame", return_value=_FakeHistoryFrame([]), create=True),
        patch("src.services.liquidity_monitor_service.fetch_binance_funding_row", side_effect=RuntimeError("network disabled")),
    ):
        payload = service.get_liquidity_monitor()

    indicator = {item["key"]: item for item in payload["indicators"]}["us_rates_pressure"]
    diagnostics = indicator["coverageDiagnostics"]

    assert indicator["freshness"] == "delayed"
    assert indicator["includedInScore"] is False
    assert diagnostics["scoreContributionAllowed"] is False
    assert diagnostics["scoreExclusionReason"] == "proxy_only_missing_real_source"
    assert "Yahoo Finance" in str(indicator["summary"])
    assert "US Treasury" not in str(indicator["summary"])
    assert "stale_official_row" not in str(indicator["summary"])


def test_official_credit_stress_observation_is_summary_only_and_does_not_change_score(isolated_db: DatabaseManager) -> None:
    base_as_of = "2026-05-12T16:15:00+08:00"

    def _build_payload(*, include_credit: bool) -> Dict[str, Any]:
        service = _make_service()
        service.cache.set(
            "volatility",
            _cache_entry(
                source="yfinance_proxy",
                freshness="live",
                items=[{"symbol": "VIX", "label": "VIX", "changePercent": -3.0, "value": 14.6}],
                updated_at=base_as_of,
                as_of=base_as_of,
            ),
            ttl_seconds=30,
        )
        service.cache.set(
            "funds_flow",
            _cache_entry(
                source="yfinance_proxy",
                freshness="live",
                items=[{"symbol": "ETF", "label": "ETF flow proxy", "value": 1.2}],
                updated_at=base_as_of,
                as_of=base_as_of,
            ),
            ttl_seconds=30,
        )
        macro_items = [
            {
                "symbol": "US2Y",
                "label": "US 2Y",
                "value": 4.92,
                "changePercent": -0.22,
                "source": "treasury",
                "sourceId": "treasury:DGS2",
                "sourceType": "official_public",
                "sourceLabel": "US Treasury",
                "unit": "%",
                "asOf": base_as_of,
                "updatedAt": base_as_of,
            },
            {
                "symbol": "US10Y",
                "label": "US 10Y",
                "value": 4.31,
                "changePercent": -0.31,
                "source": "treasury",
                "sourceId": "treasury:DGS10",
                "sourceType": "official_public",
                "sourceLabel": "US Treasury",
                "unit": "%",
                "asOf": base_as_of,
                "updatedAt": base_as_of,
            },
            {
                "symbol": "US30Y",
                "label": "US 30Y",
                "value": 4.58,
                "changePercent": -0.18,
                "source": "treasury",
                "sourceId": "treasury:DGS30",
                "sourceType": "official_public",
                "sourceLabel": "US Treasury",
                "unit": "%",
                "asOf": base_as_of,
                "updatedAt": base_as_of,
            },
        ]
        if include_credit:
            macro_items.append(
                {
                    "symbol": "CREDIT",
                    "label": "Credit spreads",
                    "value": 341.0,
                    "change": 12.0,
                    "changePercent": 3.65,
                    "source": "fred",
                    "sourceId": "fred:BAMLH0A0HYM2",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED ICE BofA US High Yield Index Option-Adjusted Spread",
                    "unit": "bps",
                    "asOf": base_as_of,
                    "updatedAt": base_as_of,
                    "observationOnly": True,
                    "includedInScore": False,
                }
            )
        service.cache.set(
            "macro",
            _cache_entry(
                source="mixed",
                freshness="cached",
                items=macro_items,
                updated_at=base_as_of,
                as_of=base_as_of,
            ),
            ttl_seconds=30,
        )
        return service.get_liquidity_monitor()

    baseline = _build_payload(include_credit=False)
    with_credit = _build_payload(include_credit=True)

    baseline_indicator = {item["key"]: item for item in baseline["indicators"]}["us_rates_pressure"]
    with_credit_indicator = {item["key"]: item for item in with_credit["indicators"]}["us_rates_pressure"]

    assert baseline["score"] == with_credit["score"] == {
        "value": 50,
        "regime": "unavailable",
        "confidence": 0.12,
        "includedIndicatorCount": 1,
        "possibleIndicatorWeight": 49,
        "includedIndicatorWeight": 6,
    }
    assert baseline_indicator["includedInScore"] is True
    assert baseline_indicator["scoreWeight"] == 6
    assert baseline_indicator["scoreContribution"] == 4
    assert "CREDIT" not in str(baseline_indicator["summary"])
    assert with_credit_indicator["includedInScore"] is True
    assert with_credit_indicator["scoreWeight"] == 6
    assert with_credit_indicator["scoreContribution"] == 4
    assert "CREDIT +341.00bps" in str(with_credit_indicator["summary"])


def test_fed_liquidity_indicator_scores_only_when_full_official_group_is_fresh(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    base_as_of = "2026-05-20T16:15:00+08:00"
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "FED_ASSETS",
                    "label": "Fed total assets",
                    "value": 7485000.0,
                    "changePercent": 0.13,
                    "source": "fred",
                    "sourceId": "fred:WALCL",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED Federal Reserve Total Assets",
                    "sourceTier": "official_public",
                    "trustLevel": "reliable",
                    "officialSeriesId": "WALCL",
                    "officialObservationDate": "2026-05-20",
                    "officialAsOf": "2026-05-20",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                    "routeRejectedReasonCodes": [],
                    "unit": "USD mn",
                    "freshness": "cached",
                    "asOf": base_as_of,
                    "updatedAt": base_as_of,
                },
                {
                    "symbol": "FED_RRP",
                    "label": "Overnight reverse repo",
                    "value": 432.2,
                    "changePercent": -5.01,
                    "source": "fred",
                    "sourceId": "fred:RRPONTSYD",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED Overnight Reverse Repurchase Agreements",
                    "sourceTier": "official_public",
                    "trustLevel": "reliable",
                    "officialSeriesId": "RRPONTSYD",
                    "officialObservationDate": "2026-05-20",
                    "officialAsOf": "2026-05-20",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                    "routeRejectedReasonCodes": [],
                    "unit": "USD bn",
                    "freshness": "cached",
                    "asOf": base_as_of,
                    "updatedAt": base_as_of,
                },
                {
                    "symbol": "TGA",
                    "label": "Treasury General Account",
                    "value": 812000.0,
                    "changePercent": -1.69,
                    "source": "fred",
                    "sourceId": "fred:WTREGEN",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED Treasury General Account",
                    "sourceTier": "official_public",
                    "trustLevel": "reliable",
                    "officialSeriesId": "WTREGEN",
                    "officialObservationDate": "2026-05-20",
                    "officialAsOf": "2026-05-20",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                    "routeRejectedReasonCodes": [],
                    "unit": "USD mn",
                    "freshness": "cached",
                    "asOf": base_as_of,
                    "updatedAt": base_as_of,
                },
                {
                    "symbol": "RESERVES",
                    "label": "Reserve balances",
                    "value": 3260000.0,
                    "changePercent": 0.62,
                    "source": "fred",
                    "sourceId": "fred:WRESBAL",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED Reserve Balances",
                    "sourceTier": "official_public",
                    "trustLevel": "reliable",
                    "officialSeriesId": "WRESBAL",
                    "officialObservationDate": "2026-05-20",
                    "officialAsOf": "2026-05-20",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                    "routeRejectedReasonCodes": [],
                    "unit": "USD mn",
                    "freshness": "cached",
                    "asOf": base_as_of,
                    "updatedAt": base_as_of,
                },
            ],
            updated_at=base_as_of,
            as_of=base_as_of,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["fed_liquidity"]
    diagnostics = indicator["coverageDiagnostics"]

    assert indicator["includedInScore"] is True
    assert indicator["scoreContribution"] == 6
    assert indicator["status"] == "live"
    assert diagnostics["requiredProviderClass"] == "official_public.fed_liquidity"
    assert diagnostics["requiredInputs"] == ["FED_ASSETS", "FED_RRP", "TGA", "RESERVES"]
    assert diagnostics["missingInputs"] == []
    assert diagnostics["sourceTier"] == "official_public"
    assert diagnostics["trustLevel"] == "reliable"
    assert diagnostics["realSourceAvailable"] is True
    assert diagnostics["scoreContributionAllowed"] is True
    assert diagnostics["sourceAuthorityRouteRejected"] is False
    bundle = diagnostics["cacheBundleDiagnostics"]
    assert bundle["providerId"] == "official_public.fed_liquidity"
    assert bundle["sourceType"] == "official_public"
    assert bundle["requiredSeries"] == ["WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"]
    assert bundle["fulfilledSeries"] == ["WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"]
    assert bundle["missingSeries"] == []
    assert bundle["coverageRatio"] == 1.0
    assert bundle["freshness"] in {"cached", "delayed"}
    assert bundle["externalProviderCalls"] is False
    assert bundle["observationOnly"] is False
    assert bundle["scoreContributionAllowed"] is True
    assert bundle["sourceFreshnessEvidence"]["freshnessPolicies"]["RRPONTSYD"] == "official_daily_us_weekday_t_plus_1"
    assert indicator["evidence"]["cacheBundleDiagnostics"]["scoreContributionAllowed"] is True
    assert {item["officialSeriesId"] for item in indicator["evidence"]["inputs"]} == {
        "WALCL",
        "RRPONTSYD",
        "WTREGEN",
        "WRESBAL",
    }
    assert "FRED" in str(indicator["summary"])
    assert "Yahoo Finance" not in str(indicator["summary"])


def test_fed_liquidity_indicator_remains_observation_only_when_series_is_missing(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    base_as_of = "2026-05-20T16:15:00+08:00"
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "FED_ASSETS",
                    "label": "Fed total assets",
                    "value": 7485000.0,
                    "changePercent": 0.13,
                    "source": "fred",
                    "sourceId": "fred:WALCL",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED Federal Reserve Total Assets",
                    "sourceTier": "official_public",
                    "trustLevel": "reliable",
                    "officialSeriesId": "WALCL",
                    "sourceAuthorityAllowed": False,
                    "scoreContributionAllowed": False,
                    "sourceAuthorityReason": "fed_liquidity_partial_coverage",
                    "routeRejectedReasonCodes": ["fed_liquidity_missing_series"],
                    "freshness": "cached",
                    "asOf": base_as_of,
                    "updatedAt": base_as_of,
                },
                {
                    "symbol": "FED_RRP",
                    "label": "Overnight reverse repo",
                    "value": 432.2,
                    "changePercent": -5.01,
                    "source": "fred",
                    "sourceId": "fred:RRPONTSYD",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED Overnight Reverse Repurchase Agreements",
                    "sourceTier": "official_public",
                    "trustLevel": "reliable",
                    "officialSeriesId": "RRPONTSYD",
                    "sourceAuthorityAllowed": False,
                    "scoreContributionAllowed": False,
                    "sourceAuthorityReason": "fed_liquidity_partial_coverage",
                    "routeRejectedReasonCodes": ["fed_liquidity_missing_series"],
                    "freshness": "cached",
                    "asOf": base_as_of,
                    "updatedAt": base_as_of,
                },
                {
                    "symbol": "TGA",
                    "label": "Treasury General Account",
                    "value": 812000.0,
                    "changePercent": -1.69,
                    "source": "fred",
                    "sourceId": "fred:WTREGEN",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED Treasury General Account",
                    "sourceTier": "official_public",
                    "trustLevel": "reliable",
                    "officialSeriesId": "WTREGEN",
                    "sourceAuthorityAllowed": False,
                    "scoreContributionAllowed": False,
                    "sourceAuthorityReason": "fed_liquidity_partial_coverage",
                    "routeRejectedReasonCodes": ["fed_liquidity_missing_series"],
                    "freshness": "cached",
                    "asOf": base_as_of,
                    "updatedAt": base_as_of,
                },
            ],
            updated_at=base_as_of,
            as_of=base_as_of,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["fed_liquidity"]
    diagnostics = indicator["coverageDiagnostics"]

    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert indicator["status"] == "partial"
    assert diagnostics["scoreContributionAllowed"] is False
    assert diagnostics["scoreExclusionReason"] == "fed_liquidity_required_series_missing_or_stale"
    assert diagnostics["missingInputs"] == ["RESERVES"]
    assert diagnostics["realSourceAvailable"] is False
    assert diagnostics["missingProviderReason"] == "requires_official_public.fed_liquidity"
    bundle = diagnostics["cacheBundleDiagnostics"]
    assert bundle["requiredSeries"] == ["WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"]
    assert bundle["fulfilledSeries"] == ["WALCL", "RRPONTSYD", "WTREGEN"]
    assert bundle["missingSeries"] == ["WRESBAL"]
    assert bundle["coverageRatio"] == 0.75
    assert bundle["observationOnly"] is True
    assert bundle["scoreContributionAllowed"] is False
    assert bundle["externalProviderCalls"] is False
    assert "RESERVES" in diagnostics["activationHint"]
    assert "fed_liquidity_partial_coverage" in str(indicator["evidence"]["inputs"])


def test_fed_liquidity_indicator_fails_closed_for_malformed_cache_value(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    base_as_of = "2026-05-20T16:15:00+08:00"
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                _fed_liquidity_macro_item("FED_ASSETS", value=7485000.0, change_percent=0.13),
                _fed_liquidity_macro_item("FED_RRP", value=432.2, change_percent=-5.01),
                _fed_liquidity_macro_item("TGA", value=812000.0, change_percent=-1.69),
                _fed_liquidity_macro_item("RESERVES", value="N/A", change_percent=0.62),
            ],
            updated_at=base_as_of,
            as_of=base_as_of,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["fed_liquidity"]
    diagnostics = indicator["coverageDiagnostics"]
    bundle = diagnostics["cacheBundleDiagnostics"]

    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert indicator["status"] == "partial"
    assert diagnostics["scoreContributionAllowed"] is False
    assert diagnostics["scoreExclusionReason"] == "fed_liquidity_required_series_missing_or_stale"
    assert bundle["malformedSeries"] == ["WRESBAL"]
    assert bundle["missingSeries"] == ["WRESBAL"]
    assert bundle["coverageRatio"] == 0.75
    assert bundle["scoreContributionAllowed"] is False
    assert bundle["observationOnly"] is True
    assert bundle["externalProviderCalls"] is False


def test_fed_liquidity_indicator_normalizes_partial_public_freshness_from_degraded_bundle(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    base_as_of = "2026-05-20T16:15:00+08:00"
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                _fed_liquidity_macro_item("FED_ASSETS", value=7485000.0, change_percent=0.13),
                _fed_liquidity_macro_item("FED_RRP", value=432.2, change_percent=-5.01),
                _fed_liquidity_macro_item("TGA", value=812000.0, change_percent=-1.69),
            ],
            updated_at=base_as_of,
            as_of=base_as_of,
        ),
        ttl_seconds=30,
    )

    def _partial_bundle(components: list[dict[str, Any]]) -> dict[str, Any]:
        from src.services.official_macro_liquidity_cache_contracts import (
            build_official_fed_liquidity_cache_bundle as _real_bundle_builder,
        )

        bundle = _real_bundle_builder(components)
        bundle["freshness"] = "partial"
        bundle["degradationReason"] = "partial_coverage"
        source_freshness = dict(bundle.get("sourceFreshnessEvidence") or {})
        source_freshness["freshness"] = "partial"
        bundle["sourceFreshnessEvidence"] = source_freshness
        return bundle

    with patch(
        "src.services.liquidity_monitor_service.build_official_fed_liquidity_cache_bundle",
        side_effect=_partial_bundle,
    ):
        payload = LiquidityMonitorResponse(**service.get_liquidity_monitor()).model_dump(exclude_none=True)

    indicator = _indicators_by_key(payload)["fed_liquidity"]
    diagnostics = indicator["coverageDiagnostics"]

    assert payload["sourceMetadata"]["externalProviderCalls"] is False
    assert indicator["status"] == "partial"
    assert indicator["freshness"] == "cached"
    assert indicator["evidence"]["freshness"] == "partial"
    assert indicator["evidence"]["isPartial"] is True
    assert indicator["evidence"]["degradationReason"] == "partial_coverage"
    assert diagnostics["freshness"] == "partial"
    assert diagnostics["missingInputs"] == ["RESERVES"]
    assert diagnostics["scoreContributionAllowed"] is False


def test_fed_liquidity_indicator_fails_closed_for_stale_official_bundle(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    base_as_of = "2026-05-20T16:15:00+08:00"
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="stale",
            items=[
                _fed_liquidity_macro_item(
                    "FED_ASSETS",
                    value=7485000.0,
                    change_percent=0.13,
                    freshness="stale",
                    is_stale=True,
                ),
                _fed_liquidity_macro_item(
                    "FED_RRP",
                    value=432.2,
                    change_percent=-5.01,
                    freshness="stale",
                    is_stale=True,
                ),
                _fed_liquidity_macro_item(
                    "TGA",
                    value=812000.0,
                    change_percent=-1.69,
                    freshness="stale",
                    is_stale=True,
                ),
                _fed_liquidity_macro_item(
                    "RESERVES",
                    value=3260000.0,
                    change_percent=0.62,
                    freshness="stale",
                    is_stale=True,
                ),
            ],
            updated_at=base_as_of,
            as_of=base_as_of,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["fed_liquidity"]
    diagnostics = indicator["coverageDiagnostics"]
    bundle = diagnostics["cacheBundleDiagnostics"]

    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert diagnostics["scoreContributionAllowed"] is False
    assert diagnostics["scoreExclusionReason"] == "fed_liquidity_required_series_missing_or_stale"
    assert bundle["staleSeries"] == ["WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"]
    assert bundle["observationOnly"] is True
    assert bundle["scoreContributionAllowed"] is False
    assert bundle["externalProviderCalls"] is False


def test_fed_liquidity_indicator_fails_closed_for_fallback_proxy_bundle(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    base_as_of = "2026-05-20T16:15:00+08:00"
    items = []
    for symbol in FED_LIQUIDITY_SERIES_BY_SYMBOL:
        item = _fed_liquidity_macro_item(
            symbol,
            value=1.0,
            change_percent=0.1,
            freshness="fallback",
        )
        item.update(
            {
                "source": "yfinance_proxy",
                "sourceId": f"yfinance_proxy:{item['officialSeriesId']}",
                "sourceType": "public_proxy",
                "sourceTier": "public_proxy",
                "trustLevel": "weak",
                "isFallback": True,
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "sourceFreshnessEvidence": {
                    "freshness": "fallback",
                    "isFallback": True,
                    "isStale": False,
                    "isUnavailable": False,
                },
            }
        )
        items.append(item)
    service.cache.set(
        "macro",
        _cache_entry(
            source="yfinance_proxy",
            freshness="fallback",
            is_fallback=True,
            items=items,
            updated_at=base_as_of,
            as_of=base_as_of,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["fed_liquidity"]
    diagnostics = indicator["coverageDiagnostics"]
    bundle = diagnostics["cacheBundleDiagnostics"]

    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert diagnostics["scoreContributionAllowed"] is False
    assert diagnostics["realSourceAvailable"] is False
    assert bundle["fallbackOrProxySeries"] == ["WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"]
    assert bundle["observationOnly"] is True
    assert bundle["scoreContributionAllowed"] is False
    assert bundle["externalProviderCalls"] is False


def test_fed_liquidity_indicator_requires_explicit_authority_even_with_full_coverage(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    base_as_of = "2026-05-20T16:15:00+08:00"
    items = [
        _fed_liquidity_macro_item("FED_ASSETS", value=7485000.0, change_percent=0.13),
        _fed_liquidity_macro_item(
            "FED_RRP",
            value=432.2,
            change_percent=-5.01,
            source_authority_allowed=False,
            score_contribution_allowed=False,
        ),
        _fed_liquidity_macro_item("TGA", value=812000.0, change_percent=-1.69),
        _fed_liquidity_macro_item("RESERVES", value=3260000.0, change_percent=0.62),
    ]
    items[1]["sourceAuthorityReason"] = "fed_liquidity_authority_not_explicit"
    items[1]["routeRejectedReasonCodes"] = ["fed_liquidity_authority_not_explicit"]
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=items,
            updated_at=base_as_of,
            as_of=base_as_of,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["fed_liquidity"]
    diagnostics = indicator["coverageDiagnostics"]
    inputs = {str(item.get("key")): item for item in indicator["evidence"]["inputs"]}
    bundle = diagnostics["cacheBundleDiagnostics"]

    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert diagnostics["realSourceAvailable"] is False
    assert diagnostics["scoreContributionAllowed"] is False
    assert diagnostics["scoreExclusionReason"] == "fed_liquidity_required_series_missing_or_stale"
    assert diagnostics["sourceAuthorityReason"] == "fed_liquidity_authority_not_explicit"
    assert diagnostics["routeRejectedReasonCodes"] == ["fed_liquidity_authority_not_explicit"]
    assert bundle["coverageRatio"] == 1.0
    assert bundle["fulfilledSeries"] == ["WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"]
    assert bundle["blockedSeries"] == ["RRPONTSYD"]
    assert bundle["scoreContributionAllowed"] is False
    assert bundle["observationOnly"] is True
    assert inputs["FED_RRP"]["sourceAuthorityAllowed"] is False
    assert inputs["FED_RRP"]["scoreContributionAllowed"] is False


def _official_risk_bundle(payload: Dict[str, Any]) -> Dict[str, Any]:
    bundle = payload.get("officialRiskBundleReadiness")
    assert isinstance(bundle, dict)
    return bundle


def _official_risk_family(bundle: Dict[str, Any], family_id: str) -> Dict[str, Any]:
    families = {
        str(item.get("familyId")): item
        for item in bundle.get("families", [])
        if isinstance(item, dict)
    }
    assert family_id in families
    return families[family_id]


def test_data036_official_risk_bundle_ready_requires_vix_rates_and_fed_liquidity_authority(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    _seed_data036_official_risk_context(service)

    payload = service.get_liquidity_monitor()
    bundle = _official_risk_bundle(payload)

    assert bundle["contractVersion"] == "official_risk_bundle_readiness_v1"
    assert bundle["status"] == "available"
    assert bundle["scoreAuthorityEligible"] is True
    assert bundle["scoreAuthority"] == "eligible"
    assert bundle["observationOnly"] is False
    assert bundle["sourceAuthorityState"] == "available"
    assert bundle["requiredFamilies"] == ["vix", "rates", "fedLiquidity"]
    assert bundle["missingRequiredFamilies"] == []
    assert bundle["staleFamilies"] == []
    assert bundle["blockedFamilies"] == []
    assert set(bundle["availableFamilies"]) >= {"vix", "rates", "fedLiquidity"}

    vix = _official_risk_family(bundle, "vix")
    rates = _official_risk_family(bundle, "rates")
    fed_liquidity = _official_risk_family(bundle, "fedLiquidity")
    credit = _official_risk_family(bundle, "creditStress")

    assert vix["requiredSeries"] == ["VIXCLS"]
    assert vix["sourceAuthorityAllowed"] is True
    assert vix["scoreAuthorityEligible"] is True
    assert vix["freshnessWindow"] == "official_daily_us_weekday_t_plus_1"
    assert rates["requiredSeries"] == ["DGS2", "DGS10", "DGS30"]
    assert rates["fulfilledSeries"] == ["DGS2", "DGS10", "DGS30"]
    assert rates["scoreAuthorityEligible"] is True
    assert fed_liquidity["requiredSeries"] == ["WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"]
    assert fed_liquidity["scoreAuthorityEligible"] is True
    assert credit["required"] is False
    assert credit["status"] == "available"
    assert credit["scoreAuthorityEligible"] is False
    assert credit["observationOnly"] is True
    assert all(family["sourceType"] == "official_public" for family in bundle["families"])


def test_data036_missing_vix_or_rates_keeps_official_risk_bundle_partial_or_blocked(
    isolated_db: DatabaseManager,
) -> None:
    missing_vix_service = _make_service()
    _seed_data036_official_risk_context(missing_vix_service, include_vix=False)
    missing_vix_bundle = _official_risk_bundle(missing_vix_service.get_liquidity_monitor())

    assert missing_vix_bundle["status"] in {"partial", "blocked", "missing"}
    assert missing_vix_bundle["scoreAuthorityEligible"] is False
    assert "vix" in missing_vix_bundle["missingRequiredFamilies"]
    assert _official_risk_family(missing_vix_bundle, "vix")["status"] == "missing"

    missing_rates_service = _make_service()
    _seed_data036_official_risk_context(missing_rates_service, missing_rate_series="DGS10")
    missing_rates_bundle = _official_risk_bundle(missing_rates_service.get_liquidity_monitor())
    rates = _official_risk_family(missing_rates_bundle, "rates")

    assert missing_rates_bundle["scoreAuthorityEligible"] is False
    assert missing_rates_bundle["status"] in {"partial", "blocked"}
    assert "rates" in missing_rates_bundle["missingRequiredFamilies"]
    assert rates["status"] == "partial"
    assert rates["missingSeries"] == ["DGS10"]
    assert rates["scoreAuthorityEligible"] is False


def test_data036_stale_official_series_downgrades_risk_bundle_score_authority(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    _seed_data036_official_risk_context(service, stale_rate_series="DGS10")

    bundle = _official_risk_bundle(service.get_liquidity_monitor())
    rates = _official_risk_family(bundle, "rates")

    assert bundle["status"] == "stale"
    assert bundle["scoreAuthorityEligible"] is False
    assert bundle["scoreAuthority"] == "observation_only"
    assert "rates" in bundle["staleFamilies"]
    assert rates["status"] == "stale"
    assert rates["staleSeries"] == ["DGS10"]
    assert rates["scoreAuthorityEligible"] is False
    assert rates["observationOnly"] is True


def test_data036_cache_only_without_authority_proof_keeps_risk_bundle_observation_only(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    _seed_data036_official_risk_context(
        service,
        cache_only_vix_without_authority_proof=True,
    )

    bundle = _official_risk_bundle(service.get_liquidity_monitor())
    vix = _official_risk_family(bundle, "vix")

    assert bundle["scoreAuthorityEligible"] is False
    assert bundle["scoreAuthority"] == "observation_only"
    assert bundle["observationOnly"] is True
    assert bundle["status"] == "blocked"
    assert "vix" in bundle["blockedFamilies"]
    assert vix["status"] == "blocked"
    assert vix["sourceAuthorityAllowed"] is False
    assert vix["scoreAuthorityEligible"] is False
    assert "source_authority_not_explicit" in vix["nextEvidenceRequired"]


def test_data036_official_risk_bundle_emits_no_advice_wording(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    _seed_data036_official_risk_context(service)

    dumped = json.dumps(_official_risk_bundle(service.get_liquidity_monitor()), ensure_ascii=False)

    forbidden = (
        "buy recommendation",
        "sell recommendation",
        "hold recommendation",
        "target price",
        "stop loss",
        "买入建议",
        "卖出建议",
        "持有建议",
        "目标价",
        "止损",
        "仓位建议",
        "建仓建议",
        "加仓建议",
        "减仓建议",
        "交易建议",
        "操作建议",
    )
    for phrase in forbidden:
        assert phrase not in dumped


def test_usd_pressure_scores_when_official_trade_weighted_usd_is_fresh(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = "2026-05-20T10:00:00+08:00"
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "USD_TWI",
                    "label": "Trade-weighted USD",
                    "value": 128.42,
                    "changePercent": -0.25,
                    "source": "fred",
                    "sourceId": "fred:DTWEXBGS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED Nominal Broad U.S. Dollar Index",
                    "sourceTier": "official_public",
                    "trustLevel": "reliable",
                    "freshness": "cached",
                    "asOf": now,
                    "updatedAt": now,
                    "isFallback": False,
                    "isUnavailable": False,
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                    "sourceAuthorityReason": None,
                    "sourceAuthorityRouteRejected": False,
                    "routeRejectedReasonCodes": [],
                    "officialSeriesId": "DTWEXBGS",
                    "officialObservationDate": "2026-05-20",
                    "officialAsOf": "2026-05-20",
                }
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["usd_pressure"]
    diagnostics = indicator["coverageDiagnostics"]
    inputs = {str(item.get("key")): item for item in indicator["evidence"]["inputs"]}

    assert indicator["includedInScore"] is True
    assert indicator["scoreContribution"] == 6
    assert "Trade-weighted USD" in indicator["summary"]
    assert "DXY" not in indicator["summary"]
    assert diagnostics["requiredProviderClass"] == "official_public.usd_pressure"
    assert diagnostics["realSourceAvailable"] is True
    assert diagnostics["proxyOnly"] is False
    assert diagnostics["scoreContributionAllowed"] is True
    assert diagnostics["sourceTier"] == "official_public"
    assert diagnostics["sourceAuthorityReason"] is None
    assert diagnostics["routeRejectedReasonCodes"] == []
    bundle = indicator["evidence"]["cacheBundleDiagnostics"]
    assert bundle["providerId"] == "official_public.usd_pressure"
    assert bundle["readinessEligible"] is True
    assert bundle["scoreGradeEvidenceAllowed"] is True
    assert bundle["cacheSafeOfficialEvidenceAllowed"] is True
    assert bundle["fulfilledSeries"] == ["DTWEXBGS"]
    assert bundle["missingSeries"] == []
    assert bundle["externalProviderCalls"] is False
    assert inputs["USD_TWI"]["officialSeriesId"] == "DTWEXBGS"
    assert inputs["USD_TWI"]["sourceAuthorityAllowed"] is True
    assert inputs["USD_TWI"]["scoreContributionAllowed"] is True


def test_usd_pressure_lists_official_trade_weighted_series_when_missing(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = "2026-05-20T10:00:00+08:00"
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "USD_TWI",
                    "label": "Trade-weighted USD",
                    "value": None,
                    "changePercent": None,
                    "source": "fred",
                    "sourceId": "fred:DTWEXBGS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED Nominal Broad U.S. Dollar Index",
                    "sourceTier": "official_public",
                    "trustLevel": "unavailable",
                    "freshness": "unavailable",
                    "asOf": now,
                    "updatedAt": now,
                    "isFallback": False,
                    "isUnavailable": True,
                    "sourceAuthorityAllowed": False,
                    "scoreContributionAllowed": False,
                    "sourceAuthorityReason": "usd_pressure_missing_series",
                    "routeRejectedReasonCodes": ["usd_pressure_missing_series"],
                    "officialSeriesId": "DTWEXBGS",
                    "officialObservationDate": None,
                    "officialAsOf": None,
                }
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["usd_pressure"]
    diagnostics = indicator["coverageDiagnostics"]
    inputs = {str(item.get("key")): item for item in indicator["evidence"]["inputs"]}

    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert indicator["status"] == "unavailable"
    assert diagnostics["scoreContributionAllowed"] is False
    assert diagnostics["missingInputs"] == ["USD_TWI"]
    assert diagnostics["missingProviderReason"] == "requires_official_public.usd_pressure"
    assert inputs["USD_TWI"]["officialSeriesId"] == "DTWEXBGS"
    assert inputs["USD_TWI"]["sourceAuthorityAllowed"] is False
    assert inputs["USD_TWI"]["scoreContributionAllowed"] is False
    assert inputs["USD_TWI"]["sourceAuthorityReason"] == "usd_pressure_missing_series"
    assert inputs["USD_TWI"]["routeRejectedReasonCodes"] == ["usd_pressure_missing_series"]
    bundle = indicator["evidence"]["cacheBundleDiagnostics"]
    assert bundle["readinessEligible"] is False
    assert bundle["scoreGradeEvidenceAllowed"] is False
    assert bundle["unavailableSeries"] == ["DTWEXBGS"]
    assert "unavailable_official_usd_pressure_evidence" in bundle["reasonCodes"]


def test_usd_pressure_reports_official_stale_reason_when_trade_weighted_row_is_stale(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = "2026-05-22T10:00:00+08:00"
    service.cache.set(
        "macro",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {
                    "symbol": "USD_TWI",
                    "label": "Trade-weighted USD",
                    "value": None,
                    "changePercent": None,
                    "source": "fred",
                    "sourceId": "fred:DTWEXBGS",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED Nominal Broad U.S. Dollar Index",
                    "sourceTier": "official_public",
                    "trustLevel": "unavailable",
                    "freshness": "stale",
                    "asOf": "2026-05-01",
                    "updatedAt": now,
                    "isFallback": False,
                    "isUnavailable": True,
                    "sourceAuthorityAllowed": False,
                    "scoreContributionAllowed": False,
                    "sourceAuthorityReason": "official_usd_pressure_stale",
                    "routeRejectedReasonCodes": ["official_usd_pressure_stale"],
                    "officialSeriesId": "DTWEXBGS",
                    "officialObservationDate": "2026-05-01",
                    "officialAsOf": "2026-05-01",
                }
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    indicator = _indicators_by_key(payload)["usd_pressure"]
    diagnostics = indicator["coverageDiagnostics"]
    inputs = {str(item.get("key")): item for item in indicator["evidence"]["inputs"]}

    assert indicator["includedInScore"] is False
    assert indicator["scoreContribution"] == 0
    assert diagnostics["scoreContributionAllowed"] is False
    assert diagnostics["scoreExclusionReason"] == "official_usd_pressure_stale"
    assert diagnostics["missingInputs"] == ["USD_TWI"]
    assert inputs["USD_TWI"]["sourceAuthorityReason"] == "official_usd_pressure_stale"
    assert inputs["USD_TWI"]["scoreContributionAllowed"] is False
    bundle = indicator["evidence"]["cacheBundleDiagnostics"]
    assert bundle["readinessEligible"] is False
    assert bundle["scoreGradeEvidenceAllowed"] is False
    assert bundle["staleSeries"] == ["DTWEXBGS"]
    assert "stale_official_usd_pressure_evidence" in bundle["reasonCodes"]


def test_capital_flow_signal_flags_growth_absorption_when_btc_and_gold_fail_to_confirm(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = datetime(2026, 5, 26, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "crypto",
        _cache_entry(
            source="binance",
            freshness="live",
            items=[
                {"symbol": "BTC", "label": "BTC", "changePercent": -1.6, "value": 67200.0, "source": "binance", "sourceType": "exchange_public"},
                {"symbol": "ETH", "label": "ETH", "changePercent": -0.8, "value": 3360.0, "source": "binance", "sourceType": "exchange_public"},
                {"symbol": "BNB", "label": "BNB", "changePercent": -0.4, "value": 615.0, "source": "binance", "sourceType": "exchange_public"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "volatility",
        _cache_entry(
            source="fred",
            freshness="cached",
            items=[
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 14.8,
                    "changePercent": -3.4,
                    "source": "fred",
                    "sourceType": "official_public",
                    "sourceLabel": "FRED VIXCLS",
                }
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "rates",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {"symbol": "US2Y", "label": "US 2Y", "value": 4.38, "changePercent": -0.16, "source": "treasury", "sourceType": "official_public", "sourceLabel": "US Treasury", "unit": "%"},
                {"symbol": "US10Y", "label": "US 10Y", "value": 4.09, "changePercent": -0.19, "source": "treasury", "sourceType": "official_public", "sourceLabel": "US Treasury", "unit": "%"},
                {"symbol": "US30Y", "label": "US 30Y", "value": 4.29, "changePercent": -0.14, "source": "treasury", "sourceType": "official_public", "sourceLabel": "US Treasury", "unit": "%"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "fx_commodities",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {"symbol": "DXY", "label": "DXY", "changePercent": -0.5, "value": 103.4, "source": "yfinance_proxy", "sourceType": "proxy_public", "sourceLabel": "Yahoo Finance", "freshness": "delayed"},
                {"symbol": "GLD", "label": "Gold", "changePercent": -0.7, "value": 238.2, "source": "yfinance_proxy", "sourceType": "proxy_public", "sourceLabel": "Yahoo Finance", "freshness": "delayed"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "us_breadth",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 8, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
                {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 3, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
                {"symbol": "RSP_SPY", "label": "RSP vs SPY", "value": 0.1, "changePercent": 0.1, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
                {"symbol": "IWM_SPY", "label": "IWM vs SPY", "value": 0.3, "changePercent": 0.3, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
                {"symbol": "QQQ_SPY", "label": "QQQ vs SPY", "value": 1.1, "changePercent": 1.1, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {"symbol": "ETF", "label": "ETF flow proxy", "value": 1.7, "source": "yfinance_proxy", "sourceType": "unofficial_proxy", "sourceLabel": "Yahoo Finance"}
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    signal = _capital_flow_signal(payload)
    pressure = {item["asset"]: item for item in signal["sourceAssetPressure"]}

    assert signal["observationOnly"] is True
    assert signal["sourceAuthorityAllowed"] is False
    assert signal["scoreContributionAllowed"] is False
    assert signal["capitalFlowRegime"] == "inflow"
    assert signal["likelyDestination"] == "growth_ai_software_semis"
    assert signal["confidence"] == "medium"
    assert signal["isPartial"] is True
    assert "btc_not_confirming_growth_absorption" in signal["contradictionSignals"]
    assert "gold_not_confirming_growth_absorption" in signal["contradictionSignals"]
    assert pressure["growth_ai_software_semis"]["pressure"] == "absorbing"
    assert pressure["btc"]["pressure"] == "lagging"
    assert pressure["gold"]["pressure"] == "lagging"
    assert pressure["usd"]["pressure"] == "easing"
    assert "growth" in signal["explanation"].lower()


def test_capital_flow_signal_adds_cached_funds_flow_proxy_detail_without_runtime_side_effects(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = datetime(2026, 5, 29, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "crypto",
        _cache_entry(
            source="binance",
            freshness="live",
            items=[
                {"symbol": "BTC", "label": "BTC", "changePercent": -1.4, "value": 67000.0, "source": "binance", "sourceType": "exchange_public"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "volatility",
        _cache_entry(
            source="fred",
            freshness="cached",
            items=[
                {"symbol": "VIX", "label": "VIX", "changePercent": -2.4, "value": 15.1, "source": "fred", "sourceType": "official_public", "sourceLabel": "FRED VIXCLS"}
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "rates",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {"symbol": "US2Y", "label": "US 2Y", "value": 4.38, "changePercent": -0.16, "source": "treasury", "sourceType": "official_public", "sourceLabel": "US Treasury", "unit": "%"},
                {"symbol": "US10Y", "label": "US 10Y", "value": 4.09, "changePercent": -0.19, "source": "treasury", "sourceType": "official_public", "sourceLabel": "US Treasury", "unit": "%"},
                {"symbol": "US30Y", "label": "US 30Y", "value": 4.29, "changePercent": -0.14, "source": "treasury", "sourceType": "official_public", "sourceLabel": "US Treasury", "unit": "%"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "fx_commodities",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {"symbol": "DXY", "label": "DXY", "changePercent": -0.5, "value": 103.4, "source": "yfinance_proxy", "sourceType": "proxy_public", "sourceLabel": "Yahoo Finance", "freshness": "delayed"},
                {"symbol": "GLD", "label": "Gold", "changePercent": -0.7, "value": 238.2, "source": "yfinance_proxy", "sourceType": "proxy_public", "sourceLabel": "Yahoo Finance", "freshness": "delayed"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "us_breadth",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 8, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
                {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 3, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
                {"symbol": "RSP_SPY", "label": "RSP vs SPY", "value": 0.1, "changePercent": 0.1, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
                {"symbol": "IWM_SPY", "label": "IWM vs SPY", "value": 0.3, "changePercent": 0.3, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
                {"symbol": "QQQ_SPY", "label": "QQQ vs SPY", "value": 1.1, "changePercent": 1.1, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {"symbol": "ETF", "label": "ETF flow proxy", "value": 1.7, "change_pct": 0.8, "source": "yfinance_proxy", "sourceType": "unofficial_public_api", "sourceLabel": "Yahoo Finance", "observationOnly": True, "sourceAuthorityAllowed": False, "scoreContributionAllowed": False},
                {"symbol": "INSTITUTIONAL", "label": "Institutional pressure proxy", "value": 2.4, "change_pct": 1.2, "source": "yfinance_proxy", "sourceType": "unofficial_public_api", "sourceLabel": "Yahoo Finance", "observationOnly": True, "sourceAuthorityAllowed": False, "scoreContributionAllowed": False},
                {"symbol": "INDUSTRY", "label": "Industry breadth proxy", "value": -0.6, "change_pct": -0.6, "source": "yfinance_proxy", "sourceType": "unofficial_public_api", "sourceLabel": "Yahoo Finance", "observationOnly": True, "sourceAuthorityAllowed": False, "scoreContributionAllowed": False},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    signal = _capital_flow_signal(payload)
    pressure = {item["asset"]: item for item in signal["sourceAssetPressure"]}

    assert payload["sourceMetadata"]["externalProviderCalls"] is False
    assert payload["sourceMetadata"]["providerRuntimeChanged"] is False
    assert payload["sourceMetadata"]["marketCacheMutation"] is False
    assert signal["likelyDestination"] == "growth_ai_software_semis"
    assert signal["confidence"] == "medium"
    assert signal["observationOnly"] is True
    assert signal["sourceAuthorityAllowed"] is False
    assert signal["scoreContributionAllowed"] is False
    assert pressure["qqq_institutional_proxy"]["pressure"] == "absorbing"
    assert pressure["qqq_institutional_proxy"]["changePercent"] == 1.2
    assert pressure["qqq_institutional_proxy"]["observationOnly"] is True
    assert pressure["qqq_institutional_proxy"]["isPartial"] is True
    assert pressure["iwm_industry_proxy"]["pressure"] == "lagging"
    assert pressure["iwm_industry_proxy"]["changePercent"] == -0.6
    assert pressure["iwm_industry_proxy"]["observationOnly"] is True
    assert pressure["iwm_industry_proxy"]["isPartial"] is True
    assert "proxy" in pressure["qqq_institutional_proxy"]["asset"]
    assert "proxy" in pressure["iwm_industry_proxy"]["asset"]
    assert "fund flow" not in pressure["qqq_institutional_proxy"]["asset"]
    assert "fund flow" not in pressure["iwm_industry_proxy"]["asset"]


def test_capital_flow_signal_skips_missing_funds_flow_proxy_rows_without_behavior_change(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = datetime(2026, 5, 29, 11, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "crypto",
        _cache_entry(
            source="binance",
            freshness="live",
            items=[
                {"symbol": "BTC", "label": "BTC", "changePercent": -1.4, "value": 67000.0, "source": "binance", "sourceType": "exchange_public"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "volatility",
        _cache_entry(
            source="fred",
            freshness="cached",
            items=[
                {"symbol": "VIX", "label": "VIX", "changePercent": -2.4, "value": 15.1, "source": "fred", "sourceType": "official_public", "sourceLabel": "FRED VIXCLS"}
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "rates",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {"symbol": "US2Y", "label": "US 2Y", "value": 4.38, "changePercent": -0.16, "source": "treasury", "sourceType": "official_public", "sourceLabel": "US Treasury", "unit": "%"},
                {"symbol": "US10Y", "label": "US 10Y", "value": 4.09, "changePercent": -0.19, "source": "treasury", "sourceType": "official_public", "sourceLabel": "US Treasury", "unit": "%"},
                {"symbol": "US30Y", "label": "US 30Y", "value": 4.29, "changePercent": -0.14, "source": "treasury", "sourceType": "official_public", "sourceLabel": "US Treasury", "unit": "%"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "fx_commodities",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {"symbol": "DXY", "label": "DXY", "changePercent": -0.5, "value": 103.4, "source": "yfinance_proxy", "sourceType": "proxy_public", "sourceLabel": "Yahoo Finance", "freshness": "delayed"},
                {"symbol": "GLD", "label": "Gold", "changePercent": -0.7, "value": 238.2, "source": "yfinance_proxy", "sourceType": "proxy_public", "sourceLabel": "Yahoo Finance", "freshness": "delayed"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "us_breadth",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 8, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
                {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 3, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
                {"symbol": "RSP_SPY", "label": "RSP vs SPY", "value": 0.1, "changePercent": 0.1, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
                {"symbol": "IWM_SPY", "label": "IWM vs SPY", "value": 0.3, "changePercent": 0.3, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
                {"symbol": "QQQ_SPY", "label": "QQQ vs SPY", "value": 1.1, "changePercent": 1.1, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "funds_flow",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {"symbol": "ETF", "label": "ETF flow proxy", "value": 1.7, "change_pct": 0.8, "source": "yfinance_proxy", "sourceType": "unofficial_public_api", "sourceLabel": "Yahoo Finance", "observationOnly": True, "sourceAuthorityAllowed": False, "scoreContributionAllowed": False},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    signal = _capital_flow_signal(payload)
    pressure = {item["asset"]: item for item in signal["sourceAssetPressure"]}

    assert payload["sourceMetadata"]["externalProviderCalls"] is False
    assert payload["sourceMetadata"]["providerRuntimeChanged"] is False
    assert payload["sourceMetadata"]["marketCacheMutation"] is False
    assert signal["likelyDestination"] == "growth_ai_software_semis"
    assert signal["confidence"] == "medium"
    assert signal["observationOnly"] is True
    assert signal["sourceAuthorityAllowed"] is False
    assert signal["scoreContributionAllowed"] is False
    assert "qqq_institutional_proxy" not in pressure
    assert "iwm_industry_proxy" not in pressure
    assert pressure["growth_ai_software_semis"]["pressure"] == "absorbing"
    assert pressure["btc"]["pressure"] == "lagging"
    assert pressure["gold"]["pressure"] == "lagging"
    assert pressure["usd"]["pressure"] == "easing"


def test_capital_flow_signal_flags_oil_when_backdrop_is_rate_cut_supportive(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = datetime(2026, 5, 27, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "volatility",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {"symbol": "VIX", "label": "VIX", "changePercent": -2.2, "value": 15.6, "source": "yfinance_proxy", "sourceType": "proxy_public", "sourceLabel": "Yahoo Finance", "freshness": "delayed"}
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "rates",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {"symbol": "US10Y", "label": "10Y yield", "changePercent": -0.3, "value": 4.02, "source": "yfinance_proxy", "sourceType": "proxy_public", "sourceLabel": "Yahoo Finance", "freshness": "delayed"},
                {"symbol": "US30Y", "label": "30Y yield", "changePercent": -0.2, "value": 4.21, "source": "yfinance_proxy", "sourceType": "proxy_public", "sourceLabel": "Yahoo Finance", "freshness": "delayed"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "fx_commodities",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {"symbol": "DXY", "label": "DXY", "changePercent": -0.6, "value": 103.1, "source": "yfinance_proxy", "sourceType": "proxy_public", "sourceLabel": "Yahoo Finance", "freshness": "delayed"},
                {"symbol": "WTI", "label": "WTI", "changePercent": 2.4, "value": 79.4, "source": "yfinance_proxy", "sourceType": "proxy_public", "sourceLabel": "Yahoo Finance", "freshness": "delayed"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    signal = _capital_flow_signal(payload)
    pressure = {item["asset"]: item for item in signal["sourceAssetPressure"]}

    assert signal["capitalFlowRegime"] == "inflow"
    assert signal["likelyDestination"] == "oil"
    assert signal["confidence"] == "low"
    assert signal["isPartial"] is True
    assert signal["contradictionSignals"] == []
    assert pressure["oil"]["pressure"] == "absorbing"
    assert pressure["usd"]["pressure"] == "easing"
    assert pressure["rates"]["pressure"] == "easing"
    assert "oil" in signal["explanation"].lower()
    assert "rate-cut" in signal["explanation"].lower()


def test_capital_flow_signal_returns_no_clear_edge_when_cross_asset_inputs_split(
    isolated_db: DatabaseManager,
) -> None:
    service = _make_service()
    now = datetime(2026, 5, 28, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "crypto",
        _cache_entry(
            source="binance",
            freshness="live",
            items=[
                {"symbol": "BTC", "label": "BTC", "changePercent": 2.1, "value": 68100.0, "source": "binance", "sourceType": "exchange_public"},
                {"symbol": "ETH", "label": "ETH", "changePercent": 1.3, "value": 3420.0, "source": "binance", "sourceType": "exchange_public"},
                {"symbol": "BNB", "label": "BNB", "changePercent": 0.8, "value": 624.0, "source": "binance", "sourceType": "exchange_public"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "volatility",
        _cache_entry(
            source="fred",
            freshness="cached",
            items=[
                {"symbol": "VIX", "label": "VIX", "changePercent": -3.1, "value": 14.9, "source": "fred", "sourceType": "official_public", "sourceLabel": "FRED VIXCLS"}
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "rates",
        _cache_entry(
            source="mixed",
            freshness="cached",
            items=[
                {"symbol": "US2Y", "label": "US 2Y", "value": 4.61, "changePercent": 0.12, "source": "treasury", "sourceType": "official_public", "sourceLabel": "US Treasury", "unit": "%"},
                {"symbol": "US10Y", "label": "US 10Y", "value": 4.34, "changePercent": 0.18, "source": "treasury", "sourceType": "official_public", "sourceLabel": "US Treasury", "unit": "%"},
                {"symbol": "US30Y", "label": "US 30Y", "value": 4.57, "changePercent": 0.16, "source": "treasury", "sourceType": "official_public", "sourceLabel": "US Treasury", "unit": "%"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "fx_commodities",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {"symbol": "DXY", "label": "DXY", "changePercent": 0.5, "value": 104.6, "source": "yfinance_proxy", "sourceType": "proxy_public", "sourceLabel": "Yahoo Finance", "freshness": "delayed"},
                {"symbol": "GLD", "label": "Gold", "changePercent": 1.1, "value": 242.4, "source": "yfinance_proxy", "sourceType": "proxy_public", "sourceLabel": "Yahoo Finance", "freshness": "delayed"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )
    service.cache.set(
        "us_breadth",
        _cache_entry(
            source="yfinance_proxy",
            freshness="delayed",
            items=[
                {"symbol": "SECTORS_UP", "label": "Sectors Up", "value": 5, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
                {"symbol": "SECTORS_DOWN", "label": "Sectors Down", "value": 6, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
                {"symbol": "RSP_SPY", "label": "RSP vs SPY", "value": -0.3, "changePercent": -0.3, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
                {"symbol": "IWM_SPY", "label": "IWM vs SPY", "value": -0.4, "changePercent": -0.4, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
                {"symbol": "QQQ_SPY", "label": "QQQ vs SPY", "value": -0.2, "changePercent": -0.2, "source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
            ],
            updated_at=now,
            as_of=now,
        ),
        ttl_seconds=30,
    )

    payload = service.get_liquidity_monitor()
    signal = _capital_flow_signal(payload)
    pressure = {item["asset"]: item for item in signal["sourceAssetPressure"]}

    assert signal["capitalFlowRegime"] == "mixed"
    assert signal["likelyDestination"] == "no_clear_edge"
    assert signal["confidence"] == "low"
    assert signal["isPartial"] is True
    assert "cross_asset_rotation_split" in signal["contradictionSignals"]
    assert pressure["btc"]["pressure"] == "absorbing"
    assert pressure["gold"]["pressure"] == "absorbing"
    assert pressure["growth_ai_software_semis"]["pressure"] == "lagging"
    assert pressure["usd"]["pressure"] == "tightening"
    assert "mixed" in signal["explanation"].lower()


LIQUIDITY_GOLDEN_SCENARIOS = (
    ("official_cached_macro_rates_context.json", _seed_official_cached_macro_rates_context),
    ("mixed_official_proxy_context.json", _seed_mixed_official_proxy_context),
    ("missing_macro_rates_proxy_fallback_context.json", _seed_missing_macro_rates_proxy_fallback_context),
    ("credit_stress_observation_only_context.json", _seed_credit_stress_observation_only_context),
    ("delayed_proxy_fx_commodities_context.json", _seed_delayed_proxy_fx_commodities_context),
    ("provider_unavailable_stale_malformed_context.json", _seed_provider_unavailable_stale_malformed_context),
)


@pytest.mark.parametrize(("fixture_name", "build_seed"), LIQUIDITY_GOLDEN_SCENARIOS)
def test_liquidity_monitor_golden_fixtures_match_public_dto_contract(
    isolated_db: DatabaseManager,
    fixture_name: str,
    build_seed,
) -> None:
    del isolated_db
    expected = LiquidityMonitorResponse(**_load_fixture(fixture_name)).model_dump(exclude_none=True)
    actual = _cache_only_liquidity_service_payload(build_seed)

    assert actual["capitalFlowSignal"]["observationOnly"] is True
    assert actual["capitalFlowSignal"]["sourceAuthorityAllowed"] is False
    assert actual["capitalFlowSignal"]["scoreContributionAllowed"] is False
    additive_contract_fields = {"capitalFlowSignal", "officialRiskBundleReadiness"}
    assert {
        key: value
        for key, value in actual.items()
        if key not in additive_contract_fields
    } == expected
    _assert_no_sensitive_public_payload(actual)


def test_liquidity_monitor_credit_stress_fixture_remains_observation_only_and_preserves_baseline_score(
    isolated_db: DatabaseManager,
) -> None:
    del isolated_db
    baseline = _cache_only_liquidity_service_payload(_seed_official_cached_macro_rates_context)
    with_credit = _cache_only_liquidity_service_payload(_seed_credit_stress_observation_only_context)

    baseline_indicator = {item["key"]: item for item in baseline["indicators"]}["us_rates_pressure"]
    with_credit_indicator = {item["key"]: item for item in with_credit["indicators"]}["us_rates_pressure"]

    assert baseline["score"] == with_credit["score"] == {
        "value": 50,
        "regime": "unavailable",
        "confidence": 0.29,
        "includedIndicatorCount": 2,
        "possibleIndicatorWeight": 49,
        "includedIndicatorWeight": 14,
    }
    assert "CREDIT" not in str(baseline_indicator["summary"])
    assert "CREDIT +341.00bps" in str(with_credit_indicator["summary"])
    assert baseline_indicator["scoreContribution"] == with_credit_indicator["scoreContribution"] == 4


def test_all_liquidity_golden_fixtures_are_explicitly_enumerated_and_sanitized() -> None:
    fixture_paths = sorted(FIXTURE_DIR.glob("*.json"))

    assert {path.name for path in fixture_paths} == set(LIQUIDITY_GOLDEN_FIXTURE_NAMES)
    for path in fixture_paths:
        _assert_no_sensitive_public_payload(json.loads(path.read_text(encoding="utf-8")))


def test_coverage_diagnostics_projects_authorized_licensed_source_tier_from_shared_trust_gate(
    isolated_db: DatabaseManager,
) -> None:
    del isolated_db
    service = _make_service()
    panel = PanelState(
        key="funds_flow",
        payload={
            "source": "polygon_us_grouped_daily",
            "sourceLabel": "Polygon grouped daily US equities",
            "sourceType": "authorized_licensed_feed",
        },
        source="polygon_us_grouped_daily",
        freshness="delayed",
        as_of="2026-05-23T10:00:00+08:00",
        updated_at="2026-05-23T10:00:00+08:00",
        is_fallback=False,
        is_stale=False,
    )
    evidence = service._indicator_evidence(
        status="partial",
        freshness="delayed",
        expected_input_count=1,
        inputs=[
            service._source_confidence_input(
                key="ETF",
                label="ETF",
                source="polygon_us_grouped_daily",
                source_label="Polygon grouped daily US equities",
                source_type="authorized_licensed_feed",
                as_of="2026-05-23T10:00:00+08:00",
                freshness="delayed",
                coverage=1.0,
                metadata={"sourceTier": "authorized_licensed_feed"},
            )
        ],
    )

    diagnostics = service._indicator_coverage_diagnostics(
        "licensed_probe",
        "Licensed Probe",
        status="partial",
        included=False,
        score_contribution=0,
        evidence=evidence,
        panel=panel,
    )

    assert diagnostics["sourceTier"] == "authorized_licensed_feed"


def test_degraded_authorized_breadth_snapshot_with_malformed_reason_codes_returns_payload_not_exception(
    isolated_db: DatabaseManager,
) -> None:
    service = LiquidityMonitorService(cache=MarketCache(), db=isolated_db)
    now = datetime(2026, 5, 30, 10, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    service.cache.set(
        "us_breadth",
        {
            "source": "authorized_feed",
            "freshness": "fallback",
            "updatedAt": now,
            "asOf": now,
            "items": [
                {
                    "symbol": "ADVANCERS",
                    "label": "Advancers",
                    "value": 100,
                    "source": "authorized_feed",
                    "sourceType": "authorized_licensed_feed",
                    "routeRejectedReasonCodes": 123,
                },
                {
                    "symbol": "DECLINERS",
                    "label": "Decliners",
                    "value": 200,
                    "source": "authorized_feed",
                    "sourceType": "authorized_licensed_feed",
                },
                {
                    "symbol": "UNCHANGED",
                    "label": "Unchanged",
                    "value": 10,
                    "source": "authorized_feed",
                    "sourceType": "authorized_licensed_feed",
                },
                {
                    "symbol": "ADVANCE_DECLINE_RATIO",
                    "label": "Advance / Decline Ratio",
                    "value": 0.5,
                    "source": "authorized_feed",
                    "sourceType": "authorized_licensed_feed",
                },
                {
                    "symbol": "NEW_HIGHS",
                    "label": "New Highs",
                    "value": 5,
                    "source": "authorized_feed",
                    "sourceType": "authorized_licensed_feed",
                },
                {
                    "symbol": "NEW_LOWS",
                    "label": "New Lows",
                    "value": 10,
                    "source": "authorized_feed",
                    "sourceType": "authorized_licensed_feed",
                },
                {
                    "symbol": "HIGH_LOW_RATIO",
                    "label": "High / Low Ratio",
                    "value": 0.5,
                    "source": "authorized_feed",
                    "sourceType": "authorized_licensed_feed",
                },
            ],
            "cacheBundleDiagnostics": {
                "scoreContributionAllowed": False,
                "realSourceAvailable": False,
                "reasonCodes": 456,
                "degradationReason": "provider_unavailable",
            },
        },
        ttl_seconds=30,
    )

    payload = LiquidityMonitorResponse(**service.get_liquidity_monitor()).model_dump(exclude_none=True)
    indicator = _indicators_by_key(payload)["us_breadth_proxy"]

    assert payload["score"]["regime"] == "unavailable"
    assert payload["sourceMetadata"]["externalProviderCalls"] is False
    assert indicator["status"] == "partial"
    assert indicator["includedInScore"] is False
    assert indicator["coverageDiagnostics"]["scoreContributionAllowed"] is False
    assert indicator["coverageDiagnostics"]["degradationReason"] == "fallback_source"
    assert indicator["coverageDiagnostics"]["routeRejectedReasonCodes"] == ["proxy_or_placeholder_not_authorized_breadth"]
    assert indicator["evidence"]["inputs"][0]["routeRejectedReasonCodes"] == ["proxy_or_placeholder_not_authorized_breadth"]
