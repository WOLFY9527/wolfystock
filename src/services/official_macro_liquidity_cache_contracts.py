# -*- coding: utf-8 -*-
"""Cache-only official macro-liquidity bundle diagnostics.

This module is intentionally inert: it validates already-normalized cache rows
and never fetches providers, mutates cache, reads credentials, or changes
scoring formulas.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


OFFICIAL_FED_LIQUIDITY_PROVIDER_ID = "official_public.fed_liquidity"
OFFICIAL_FED_LIQUIDITY_PROVIDER_NAME = "Official Fed Liquidity"
OFFICIAL_FED_LIQUIDITY_SOURCE_TYPE = "official_public"
OFFICIAL_FED_LIQUIDITY_SOURCE_TIER = "official_public"
OFFICIAL_FED_LIQUIDITY_REQUIRED_SERIES = ("WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL")
OFFICIAL_FED_LIQUIDITY_SYMBOL_TO_SERIES_ID = {
    "FED_ASSETS": "WALCL",
    "FED_RRP": "RRPONTSYD",
    "TGA": "WTREGEN",
    "RESERVES": "WRESBAL",
}
OFFICIAL_FED_LIQUIDITY_SERIES_TO_SYMBOL = {
    series_id: symbol for symbol, series_id in OFFICIAL_FED_LIQUIDITY_SYMBOL_TO_SERIES_ID.items()
}
OFFICIAL_FED_LIQUIDITY_FRESHNESS_POLICIES = {
    "RRPONTSYD": "official_daily_us_weekday_t_plus_1",
    "WALCL": "official_weekly_fed_liquidity_t_plus_7",
    "WRESBAL": "official_weekly_fed_liquidity_t_plus_7",
    "WTREGEN": "official_weekly_fed_liquidity_t_plus_7",
}
OFFICIAL_USD_PRESSURE_PROVIDER_ID = "official_public.usd_pressure"
OFFICIAL_USD_PRESSURE_PROVIDER_NAME = "Official USD Pressure"
OFFICIAL_USD_PRESSURE_SOURCE_TYPE = "official_public"
OFFICIAL_USD_PRESSURE_SOURCE_TIER = "official_public"
OFFICIAL_USD_PRESSURE_REQUIRED_SERIES = ("DTWEXBGS",)
OFFICIAL_USD_PRESSURE_SYMBOL_TO_SERIES_ID = {
    "USD_TWI": "DTWEXBGS",
}
OFFICIAL_USD_PRESSURE_FRESHNESS_POLICIES = {
    "DTWEXBGS": "official_h10_weekly_batch_t_plus_7",
}
OFFICIAL_US_RATES_PROVIDER_ID = "official_public.us_rates"
OFFICIAL_US_RATES_PROVIDER_NAME = "Official US Rates"
OFFICIAL_US_RATES_SOURCE_TYPE = "official_public"
OFFICIAL_US_RATES_SOURCE_TIER = "official_public"
OFFICIAL_US_RATES_REQUIRED_SERIES = ("DGS2", "DGS10", "DGS30")
OFFICIAL_US_RATES_CONTEXT_SERIES = ("SOFR", "US10Y2Y", "US10Y3M")
OFFICIAL_US_RATES_SYMBOL_TO_SERIES_ID = {
    "US2Y": "DGS2",
    "US10Y": "DGS10",
    "US30Y": "DGS30",
    "SOFR": "SOFR",
    "US10Y2Y": "US10Y2Y",
    "US10Y3M": "US10Y3M",
}
OFFICIAL_US_RATES_ALIAS_TO_SERIES_ID = {
    "DGS2": "DGS2",
    "DGS10": "DGS10",
    "DGS30": "DGS30",
    "SOFR": "SOFR",
    "T10Y2Y": "US10Y2Y",
    "US10Y2Y": "US10Y2Y",
    "10Y2Y": "US10Y2Y",
    "T10Y3M": "US10Y3M",
    "US10Y3M": "US10Y3M",
    "10Y3M": "US10Y3M",
}
OFFICIAL_US_RATES_FRESHNESS_POLICIES = {
    "DGS2": "official_daily_us_weekday_t_plus_1",
    "DGS10": "official_daily_us_weekday_t_plus_1",
    "DGS30": "official_daily_us_weekday_t_plus_1",
    "SOFR": "official_daily_us_weekday_t_plus_1",
    "US10Y2Y": "official_daily_us_weekday_t_plus_1",
    "US10Y3M": "official_daily_us_weekday_t_plus_1",
}
OFFICIAL_CN_MONEY_MARKET_PROVIDER_ID = "official_public.cn_money_market_rates"
OFFICIAL_CN_MONEY_MARKET_PROVIDER_NAME = "Official CN Money Market Rates"
OFFICIAL_CN_MONEY_MARKET_SOURCE_TYPE = "official_public"
OFFICIAL_CN_MONEY_MARKET_SOURCE_TIER = "official_public"
OFFICIAL_CN_MONEY_MARKET_REQUIRED_SERIES = ("DR007", "SHIBOR_ON")
OFFICIAL_CN_MONEY_MARKET_CONTEXT_SERIES = ("SHIBOR_3M", "LPR_1Y", "LPR_5Y", "CN10Y")
OFFICIAL_CN_MONEY_MARKET_FRESHNESS_POLICIES = {
    "DR007": "session_or_daily_official_fixing_with_holiday_calendar",
    "SHIBOR_ON": "daily_official_fixing_with_holiday_calendar",
}
OFFICIAL_CN_MONEY_MARKET_ALIAS_TO_SERIES_ID = {
    "DR007": "DR007",
    "SHIBOR": "SHIBOR_ON",
    "SHIBOR_ON": "SHIBOR_ON",
    "SHIBOR_O/N": "SHIBOR_ON",
    "SHIBOR_3M": "SHIBOR_3M",
    "LPR_1Y": "LPR_1Y",
    "LPR1Y": "LPR_1Y",
    "LPR_5Y": "LPR_5Y",
    "LPR5Y": "LPR_5Y",
    "CN10Y": "CN10Y",
}

_RELIABLE_FRESHNESS = frozenset({"live", "cached", "delayed", "fresh"})
_RELIABLE_CACHE_FRESHNESS = frozenset({"cached", "delayed", "fresh"})
_UNAVAILABLE_FRESHNESS = frozenset({"unavailable", "error"})
_STALE_FRESHNESS = frozenset({"stale"})
_FALLBACK_FRESHNESS = frozenset({"fallback", "mock", "synthetic"})
_PROXY_OR_FALLBACK_SOURCE_TYPES = frozenset(
    {
        "public_proxy",
        "unofficial_proxy",
        "proxy_public",
        "unofficial_public_api",
        "fallback_static",
        "synthetic_fixture",
        "delayed_fixture",
        "malformed_fixture",
        "disabled_live_stub",
        "missing",
    }
)
_FRESHNESS_RANK = {"live": 0, "fresh": 0, "cached": 1, "delayed": 2}


def build_official_fed_liquidity_cache_bundle(
    rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return fail-closed diagnostics for the official Fed liquidity cache bundle."""
    rows_by_series: dict[str, Mapping[str, Any]] = {}
    for raw_row in rows or ():
        if not isinstance(raw_row, Mapping):
            continue
        series_id = official_fed_liquidity_series_id(raw_row)
        if series_id:
            rows_by_series[series_id] = raw_row

    fulfilled: list[str] = []
    missing: list[str] = []
    stale: list[str] = []
    malformed: list[str] = []
    fallback_or_proxy: list[str] = []
    unavailable: list[str] = []
    blocked: list[str] = []
    policy_rejected: list[str] = []
    budget_blocked: list[str] = []
    freshness_values: list[str] = []

    for series_id in OFFICIAL_FED_LIQUIDITY_REQUIRED_SERIES:
        row = rows_by_series.get(series_id)
        if row is None:
            missing.append(series_id)
            continue

        classification = _classify_fed_liquidity_row(row, series_id)
        if classification["present"]:
            fulfilled.append(series_id)
            freshness_values.append(str(classification["freshness"]))
            if classification["blocked"]:
                blocked.append(series_id)
            continue

        missing.append(series_id)
        reason = classification["reason"]
        if reason == "malformed":
            malformed.append(series_id)
        elif reason == "stale":
            stale.append(series_id)
        elif reason == "fallback_or_proxy":
            fallback_or_proxy.append(series_id)
        elif reason == "policy_rejected":
            policy_rejected.append(series_id)
        elif reason == "budget_blocked":
            budget_blocked.append(series_id)
        else:
            unavailable.append(series_id)

    required_count = len(OFFICIAL_FED_LIQUIDITY_REQUIRED_SERIES)
    coverage_count = len(fulfilled)
    coverage_ratio = round(coverage_count / required_count, 3)
    coverage_threshold = 1.0
    coverage_threshold_passed = coverage_count == required_count
    has_runtime_rows = bool(rows)
    score_allowed = bool(
        coverage_threshold_passed
        and not missing
        and not stale
        and not malformed
        and not fallback_or_proxy
        and not unavailable
        and not blocked
        and not policy_rejected
        and not budget_blocked
    )
    freshness = _bundle_freshness(
        score_allowed=score_allowed,
        freshness_values=freshness_values,
        stale=stale,
        malformed=malformed,
        fallback_or_proxy=fallback_or_proxy,
        unavailable=unavailable,
        has_runtime_rows=has_runtime_rows,
    )
    runtime_state = (
        "aggregate_supported_runtime_evidence_ready"
        if score_allowed
        else (
            "aggregate_supported_runtime_evidence_partial"
            if has_runtime_rows
            else "aggregate_supported_runtime_evidence_missing"
        )
    )
    reason_codes = _reason_codes(
        missing=missing,
        stale=stale,
        malformed=malformed,
        fallback_or_proxy=fallback_or_proxy,
        unavailable=unavailable,
        blocked=blocked,
        policy_rejected=policy_rejected,
        budget_blocked=budget_blocked,
    )
    degradation_reason = None if score_allowed else "fed_liquidity_required_series_missing_or_stale"
    if budget_blocked:
        degradation_reason = "budget_exhausted"
    elif malformed:
        degradation_reason = "malformed_official_value"

    evidence = {
        "aggregateSupported": True,
        "externalProviderCalls": False,
        "freshness": freshness,
        "freshnessPolicies": dict(OFFICIAL_FED_LIQUIDITY_FRESHNESS_POLICIES),
        "isFallback": False,
        "isPartial": bool(has_runtime_rows and not score_allowed),
        "isUnavailable": not has_runtime_rows,
        "requiredSeries": list(OFFICIAL_FED_LIQUIDITY_REQUIRED_SERIES),
        "supportedSourceIds": [f"FRED_{series_id}" for series_id in OFFICIAL_FED_LIQUIDITY_REQUIRED_SERIES],
        "runtimeEvidence": "full" if score_allowed else ("partial" if has_runtime_rows else "missing"),
        "coverageThreshold": coverage_threshold,
        "coverageThresholdPassed": coverage_threshold_passed,
        "coverageThresholdFailure": not coverage_threshold_passed,
    }
    if score_allowed or has_runtime_rows:
        evidence["coverageRatio"] = coverage_ratio
        evidence["fulfilledSeries"] = list(fulfilled)
        evidence["missingSeries"] = list(missing)
    if stale:
        evidence["staleSeries"] = list(stale)
    if malformed:
        evidence["malformedSeries"] = list(malformed)
    if budget_blocked:
        evidence["budgetBlockedSeries"] = list(budget_blocked)

    return {
        "providerId": OFFICIAL_FED_LIQUIDITY_PROVIDER_ID,
        "providerName": OFFICIAL_FED_LIQUIDITY_PROVIDER_NAME,
        "source": OFFICIAL_FED_LIQUIDITY_PROVIDER_ID,
        "sourceLabel": f"{OFFICIAL_FED_LIQUIDITY_PROVIDER_NAME} bundle",
        "sourceType": OFFICIAL_FED_LIQUIDITY_SOURCE_TYPE,
        "sourceTier": OFFICIAL_FED_LIQUIDITY_SOURCE_TIER,
        "trustLevel": "score_grade" if score_allowed else "score_grade_when_configured",
        "retrievalMode": "cache_only",
        "cacheOnly": True,
        "externalProviderCalls": False,
        "runtimeState": runtime_state,
        "freshness": freshness,
        "requiredSeries": list(OFFICIAL_FED_LIQUIDITY_REQUIRED_SERIES),
        "fulfilledSeries": list(fulfilled),
        "missingSeries": list(missing),
        "staleSeries": list(stale),
        "malformedSeries": list(malformed),
        "fallbackOrProxySeries": list(fallback_or_proxy),
        "unavailableSeries": list(unavailable),
        "blockedSeries": list(blocked),
        "policyRejectedSeries": list(policy_rejected),
        "budgetBlockedSeries": list(budget_blocked),
        "requiredMetrics": list(OFFICIAL_FED_LIQUIDITY_REQUIRED_SERIES),
        "fulfilledMetrics": list(fulfilled),
        "missingMetrics": list(missing),
        "coverageCount": coverage_count,
        "coverageRatio": coverage_ratio,
        "coverageThreshold": coverage_threshold,
        "coverageThresholdPassed": coverage_threshold_passed,
        "coverageThresholdFailure": not coverage_threshold_passed,
        "coverage": coverage_ratio,
        "isPartial": bool(has_runtime_rows and not score_allowed),
        "isStale": bool(stale),
        "isUnavailable": not has_runtime_rows,
        "isFallback": False,
        "fallbackUsed": False,
        "observationOnly": not score_allowed,
        "sourceAuthorityAllowed": score_allowed,
        "scoreContributionAllowed": score_allowed,
        "readinessEligible": score_allowed,
        "scoreGradeEvidenceAllowed": score_allowed,
        "cacheSafeOfficialEvidenceAllowed": score_allowed,
        "reasonCodes": reason_codes,
        "degradationReason": degradation_reason,
        "sourceFreshnessEvidence": evidence,
    }


def build_official_usd_pressure_cache_bundle(
    rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return fail-closed readiness diagnostics for official USD pressure cache rows."""
    return _build_official_macro_readiness_bundle(
        rows,
        provider_id=OFFICIAL_USD_PRESSURE_PROVIDER_ID,
        provider_name=OFFICIAL_USD_PRESSURE_PROVIDER_NAME,
        source_label="Official USD Pressure readiness cache",
        source_type=OFFICIAL_USD_PRESSURE_SOURCE_TYPE,
        source_tier=OFFICIAL_USD_PRESSURE_SOURCE_TIER,
        required_series=OFFICIAL_USD_PRESSURE_REQUIRED_SERIES,
        context_series=(),
        freshness_policies=OFFICIAL_USD_PRESSURE_FRESHNESS_POLICIES,
        series_resolver=official_usd_pressure_series_id,
        row_classifier=_classify_usd_pressure_row,
        ready_runtime_state="official_usd_pressure_cache_ready",
        partial_runtime_state="official_usd_pressure_cache_partial",
        missing_runtime_state="official_usd_pressure_cache_missing",
        reason_prefix="official_usd_pressure",
        degradation_default="usd_pressure_required_series_missing_or_stale",
    )


def build_official_us_rates_cache_bundle(
    rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return fail-closed readiness diagnostics for official US rate cache rows."""
    return _build_official_macro_readiness_bundle(
        rows,
        provider_id=OFFICIAL_US_RATES_PROVIDER_ID,
        provider_name=OFFICIAL_US_RATES_PROVIDER_NAME,
        source_label="Official US Rates readiness cache",
        source_type=OFFICIAL_US_RATES_SOURCE_TYPE,
        source_tier=OFFICIAL_US_RATES_SOURCE_TIER,
        required_series=OFFICIAL_US_RATES_REQUIRED_SERIES,
        context_series=OFFICIAL_US_RATES_CONTEXT_SERIES,
        freshness_policies=OFFICIAL_US_RATES_FRESHNESS_POLICIES,
        series_resolver=official_us_rates_series_id,
        row_classifier=_classify_us_rates_row,
        ready_runtime_state="official_us_rates_cache_ready",
        partial_runtime_state="official_us_rates_cache_partial",
        missing_runtime_state="official_us_rates_cache_missing",
        reason_prefix="official_us_rates",
        degradation_default="us_rates_required_series_missing_or_stale",
    )


def build_official_cn_money_market_cache_bundle(
    rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return fail-closed readiness diagnostics for official CN money-market cache rows."""
    required_set = set(OFFICIAL_CN_MONEY_MARKET_REQUIRED_SERIES)
    context_set = set(OFFICIAL_CN_MONEY_MARKET_CONTEXT_SERIES)
    rows_by_series: dict[str, Mapping[str, Any]] = {}
    context_series: list[str] = []
    has_runtime_rows = False

    for raw_row in rows or ():
        if not isinstance(raw_row, Mapping):
            continue
        series_id = official_cn_money_market_series_id(raw_row)
        if not series_id:
            continue
        has_runtime_rows = True
        if series_id in required_set:
            rows_by_series[series_id] = raw_row
        elif series_id in context_set and series_id not in context_series:
            context_series.append(series_id)

    fulfilled: list[str] = []
    missing: list[str] = []
    stale: list[str] = []
    malformed: list[str] = []
    fallback_or_proxy: list[str] = []
    unavailable: list[str] = []
    blocked: list[str] = []
    policy_rejected: list[str] = []
    freshness_values: list[str] = []

    for series_id in OFFICIAL_CN_MONEY_MARKET_REQUIRED_SERIES:
        row = rows_by_series.get(series_id)
        if row is None:
            missing.append(series_id)
            continue

        classification = _classify_cn_money_market_row(row, series_id)
        if classification["present"]:
            fulfilled.append(series_id)
            freshness_values.append(str(classification["freshness"]))
            if classification["blocked"]:
                blocked.append(series_id)
            continue

        reason = classification["reason"]
        if reason == "malformed":
            malformed.append(series_id)
        elif reason == "stale":
            stale.append(series_id)
        elif reason == "fallback_or_proxy":
            fallback_or_proxy.append(series_id)
        elif reason == "policy_rejected":
            policy_rejected.append(series_id)
        else:
            unavailable.append(series_id)

    required_count = len(OFFICIAL_CN_MONEY_MARKET_REQUIRED_SERIES)
    coverage_count = len(fulfilled)
    coverage_ratio = round(coverage_count / required_count, 3)
    readiness_eligible = bool(
        coverage_count == required_count
        and not missing
        and not stale
        and not malformed
        and not fallback_or_proxy
        and not unavailable
        and not blocked
        and not policy_rejected
    )
    freshness = _cn_money_market_bundle_freshness(
        readiness_eligible=readiness_eligible,
        freshness_values=freshness_values,
        stale=stale,
        malformed=malformed,
        fallback_or_proxy=fallback_or_proxy,
        unavailable=unavailable,
        has_runtime_rows=has_runtime_rows,
    )
    runtime_state = (
        "official_cn_money_market_cache_ready"
        if readiness_eligible
        else (
            "official_cn_money_market_cache_partial"
            if has_runtime_rows
            else "official_cn_money_market_cache_missing"
        )
    )
    reason_codes = _cn_money_market_reason_codes(
        readiness_eligible=readiness_eligible,
        missing=missing,
        stale=stale,
        malformed=malformed,
        fallback_or_proxy=fallback_or_proxy,
        unavailable=unavailable,
        blocked=blocked,
        policy_rejected=policy_rejected,
    )
    if "CN10Y" in context_series:
        reason_codes.append("cn10y_context_only_not_yield_curve_authority")
    degradation_reason = None if readiness_eligible else "cn_money_market_required_series_missing_or_stale"
    if malformed:
        degradation_reason = "malformed_official_value"
    elif fallback_or_proxy:
        degradation_reason = "fallback_or_proxy_source"
    elif unavailable:
        degradation_reason = "unavailable_official_cn_money_market_evidence"

    evidence = {
        "aggregateSupported": True,
        "cacheOnly": True,
        "externalProviderCalls": False,
        "freshness": freshness,
        "freshnessPolicies": dict(OFFICIAL_CN_MONEY_MARKET_FRESHNESS_POLICIES),
        "isFallback": False,
        "isPartial": bool(has_runtime_rows and not readiness_eligible),
        "isUnavailable": not has_runtime_rows,
        "readinessEligible": readiness_eligible,
        "scoreGradeEvidenceAllowed": readiness_eligible,
        "cacheSafeOfficialEvidenceAllowed": readiness_eligible,
        "requiredSeries": list(OFFICIAL_CN_MONEY_MARKET_REQUIRED_SERIES),
        "supportedSourceIds": [
            f"OFFICIAL_CN_MONEY_MARKET:{series_id}"
            for series_id in OFFICIAL_CN_MONEY_MARKET_REQUIRED_SERIES
        ],
        "runtimeEvidence": "full" if readiness_eligible else ("partial" if has_runtime_rows else "missing"),
        "coverageRatio": coverage_ratio,
        "fulfilledSeries": list(fulfilled),
        "missingSeries": list(missing),
        "contextSeries": list(context_series),
    }
    if stale:
        evidence["staleSeries"] = list(stale)
    if malformed:
        evidence["malformedSeries"] = list(malformed)
    if fallback_or_proxy:
        evidence["fallbackOrProxySeries"] = list(fallback_or_proxy)
    if unavailable:
        evidence["unavailableSeries"] = list(unavailable)

    return {
        "providerId": OFFICIAL_CN_MONEY_MARKET_PROVIDER_ID,
        "providerName": OFFICIAL_CN_MONEY_MARKET_PROVIDER_NAME,
        "source": OFFICIAL_CN_MONEY_MARKET_PROVIDER_ID,
        "sourceLabel": f"{OFFICIAL_CN_MONEY_MARKET_PROVIDER_NAME} readiness cache",
        "sourceType": OFFICIAL_CN_MONEY_MARKET_SOURCE_TYPE,
        "sourceTier": OFFICIAL_CN_MONEY_MARKET_SOURCE_TIER,
        "trustLevel": "score_grade_when_configured",
        "retrievalMode": "cache_only",
        "cacheOnly": True,
        "externalProviderCalls": False,
        "runtimeState": runtime_state,
        "freshness": freshness,
        "requiredSeries": list(OFFICIAL_CN_MONEY_MARKET_REQUIRED_SERIES),
        "fulfilledSeries": list(fulfilled),
        "missingSeries": list(missing),
        "staleSeries": list(stale),
        "malformedSeries": list(malformed),
        "fallbackOrProxySeries": list(fallback_or_proxy),
        "unavailableSeries": list(unavailable),
        "blockedSeries": list(blocked),
        "policyRejectedSeries": list(policy_rejected),
        "requiredMetrics": list(OFFICIAL_CN_MONEY_MARKET_REQUIRED_SERIES),
        "fulfilledMetrics": list(fulfilled),
        "missingMetrics": list(missing),
        "contextSeries": list(context_series),
        "contextOnlySeries": list(context_series),
        "coverageCount": coverage_count,
        "coverageRatio": coverage_ratio,
        "coverage": coverage_ratio,
        "isPartial": bool(has_runtime_rows and not readiness_eligible),
        "isStale": bool(stale),
        "isUnavailable": not has_runtime_rows or bool(unavailable and not fulfilled),
        "isFallback": False,
        "fallbackUsed": False,
        "observationOnly": not readiness_eligible,
        "sourceAuthorityAllowed": readiness_eligible,
        "scoreContributionAllowed": readiness_eligible,
        "readinessEligible": readiness_eligible,
        "scoreGradeEvidenceAllowed": readiness_eligible,
        "cacheSafeOfficialEvidenceAllowed": readiness_eligible,
        "reasonCodes": reason_codes,
        "degradationReason": degradation_reason,
        "sourceFreshnessEvidence": evidence,
    }


def official_fed_liquidity_series_id(row: Mapping[str, Any]) -> str | None:
    """Resolve a Fed liquidity row to its official FRED series id."""
    explicit = _text(
        row.get("officialSeriesId")
        or row.get("official_series_id")
        or row.get("seriesId")
        or row.get("series_id")
        or row.get("sourceId")
        or row.get("source_id")
    ).upper()
    for series_id in OFFICIAL_FED_LIQUIDITY_REQUIRED_SERIES:
        if explicit == series_id or explicit.endswith(f":{series_id}") or series_id in explicit.split(":"):
            return series_id
    symbol = _text(row.get("symbol") or row.get("key")).upper()
    return OFFICIAL_FED_LIQUIDITY_SYMBOL_TO_SERIES_ID.get(symbol)


def official_usd_pressure_series_id(row: Mapping[str, Any]) -> str | None:
    """Resolve a USD pressure row to its official FRED series id."""
    explicit = _text(
        row.get("officialSeriesId")
        or row.get("official_series_id")
        or row.get("seriesId")
        or row.get("series_id")
        or row.get("sourceId")
        or row.get("source_id")
    ).upper()
    for series_id in OFFICIAL_USD_PRESSURE_REQUIRED_SERIES:
        if explicit == series_id or explicit.endswith(f":{series_id}") or series_id in explicit.split(":"):
            return series_id
    symbol = _text(row.get("symbol") or row.get("key")).upper()
    return OFFICIAL_USD_PRESSURE_SYMBOL_TO_SERIES_ID.get(symbol)


def official_us_rates_series_id(row: Mapping[str, Any]) -> str | None:
    """Resolve a US rates row to its normalized official series id."""
    explicit = _text(
        row.get("officialSeriesId")
        or row.get("official_series_id")
        or row.get("seriesId")
        or row.get("series_id")
        or row.get("sourceId")
        or row.get("source_id")
        or row.get("symbol")
        or row.get("key")
    ).upper()
    normalized_explicit = explicit.replace("-", "_").replace(" ", "_")
    if ":" in normalized_explicit:
        normalized_explicit = normalized_explicit.rsplit(":", 1)[-1]
    series_id = OFFICIAL_US_RATES_ALIAS_TO_SERIES_ID.get(normalized_explicit)
    if series_id:
        return series_id
    symbol = _text(row.get("symbol") or row.get("key")).upper()
    return OFFICIAL_US_RATES_SYMBOL_TO_SERIES_ID.get(symbol)


def official_cn_money_market_series_id(row: Mapping[str, Any]) -> str | None:
    """Resolve a CN money-market row to its normalized official series id."""
    explicit = _text(
        row.get("officialSeriesId")
        or row.get("official_series_id")
        or row.get("seriesId")
        or row.get("series_id")
        or row.get("sourceId")
        or row.get("source_id")
        or row.get("symbol")
        or row.get("key")
    ).upper()
    normalized = OFFICIAL_CN_MONEY_MARKET_ALIAS_TO_SERIES_ID.get(
        explicit.replace("-", "_").replace(" ", "_"),
        explicit.replace("-", "_").replace(" ", "_"),
    )
    valid_series = set(OFFICIAL_CN_MONEY_MARKET_REQUIRED_SERIES) | set(OFFICIAL_CN_MONEY_MARKET_CONTEXT_SERIES)
    return normalized if normalized in valid_series else None


def _build_official_macro_readiness_bundle(
    rows: Sequence[Mapping[str, Any]] | None,
    *,
    provider_id: str,
    provider_name: str,
    source_label: str,
    source_type: str,
    source_tier: str,
    required_series: Sequence[str],
    context_series: Sequence[str],
    freshness_policies: Mapping[str, str],
    series_resolver: Any,
    row_classifier: Any,
    ready_runtime_state: str,
    partial_runtime_state: str,
    missing_runtime_state: str,
    reason_prefix: str,
    degradation_default: str,
) -> dict[str, Any]:
    required_set = set(required_series)
    context_set = set(context_series)
    valid_set = required_set | context_set
    rows_by_series: dict[str, Mapping[str, Any]] = {}
    has_runtime_rows = False

    for raw_row in rows or ():
        if not isinstance(raw_row, Mapping):
            continue
        series_id = series_resolver(raw_row)
        if not series_id or series_id not in valid_set:
            continue
        has_runtime_rows = True
        rows_by_series[series_id] = raw_row

    fulfilled_required: list[str] = []
    fulfilled_context: list[str] = []
    missing: list[str] = []
    stale: list[str] = []
    malformed: list[str] = []
    fallback_or_proxy: list[str] = []
    unavailable: list[str] = []
    blocked: list[str] = []
    policy_rejected: list[str] = []
    budget_blocked: list[str] = []
    freshness_values: list[str] = []

    for series_id in required_series:
        row = rows_by_series.get(series_id)
        if row is None:
            missing.append(series_id)
            continue
        classification = row_classifier(row, series_id)
        if classification["present"]:
            fulfilled_required.append(series_id)
            freshness_values.append(str(classification["freshness"]))
            if classification["blocked"]:
                blocked.append(series_id)
            continue
        _append_classification_reason(
            str(classification["reason"]),
            series_id=series_id,
            stale=stale,
            malformed=malformed,
            fallback_or_proxy=fallback_or_proxy,
            unavailable=unavailable,
            policy_rejected=policy_rejected,
            budget_blocked=budget_blocked,
        )

    for series_id in context_series:
        row = rows_by_series.get(series_id)
        if row is None:
            continue
        classification = row_classifier(row, series_id)
        if classification["present"]:
            fulfilled_context.append(series_id)
            freshness_values.append(str(classification["freshness"]))
            if classification["blocked"]:
                blocked.append(series_id)
            continue
        _append_classification_reason(
            str(classification["reason"]),
            series_id=series_id,
            stale=stale,
            malformed=malformed,
            fallback_or_proxy=fallback_or_proxy,
            unavailable=unavailable,
            policy_rejected=policy_rejected,
            budget_blocked=budget_blocked,
        )

    required_count = len(required_series)
    coverage_count = len(fulfilled_required)
    coverage_ratio = round(coverage_count / required_count, 3) if required_count else 0.0
    coverage_threshold = 1.0
    coverage_threshold_passed = coverage_count == required_count
    readiness_eligible = bool(
        coverage_threshold_passed
        and not missing
        and not stale
        and not malformed
        and not fallback_or_proxy
        and not unavailable
        and not blocked
        and not policy_rejected
        and not budget_blocked
    )
    freshness = _bundle_freshness(
        score_allowed=readiness_eligible,
        freshness_values=freshness_values,
        stale=stale,
        malformed=malformed,
        fallback_or_proxy=fallback_or_proxy,
        unavailable=unavailable,
        has_runtime_rows=has_runtime_rows,
    )
    runtime_state = (
        ready_runtime_state
        if readiness_eligible
        else (partial_runtime_state if has_runtime_rows else missing_runtime_state)
    )
    reason_codes = _macro_readiness_reason_codes(
        reason_prefix=reason_prefix,
        readiness_eligible=readiness_eligible,
        missing=missing,
        stale=stale,
        malformed=malformed,
        fallback_or_proxy=fallback_or_proxy,
        unavailable=unavailable,
        blocked=blocked,
        policy_rejected=policy_rejected,
        budget_blocked=budget_blocked,
    )
    degradation_reason = None if readiness_eligible else degradation_default
    if budget_blocked:
        degradation_reason = "budget_exhausted"
    elif malformed:
        degradation_reason = "malformed_official_value"
    elif fallback_or_proxy:
        degradation_reason = "fallback_or_proxy_source"
    elif unavailable:
        degradation_reason = f"unavailable_{reason_prefix}_evidence"

    eligible_series = [*fulfilled_required, *fulfilled_context]
    evidence = {
        "aggregateSupported": True,
        "cacheOnly": True,
        "externalProviderCalls": False,
        "freshness": freshness,
        "freshnessPolicies": dict(freshness_policies),
        "isFallback": False,
        "isPartial": bool(has_runtime_rows and not readiness_eligible),
        "isUnavailable": not has_runtime_rows,
        "readinessEligible": readiness_eligible,
        "scoreGradeEvidenceAllowed": readiness_eligible,
        "cacheSafeOfficialEvidenceAllowed": readiness_eligible,
        "requiredSeries": list(required_series),
        "contextSeries": list(context_series),
        "eligibleSeries": list(eligible_series),
        "supportedSourceIds": [f"OFFICIAL_MACRO:{series_id}" for series_id in required_series],
        "runtimeEvidence": "full" if readiness_eligible else ("partial" if has_runtime_rows else "missing"),
        "coverageRatio": coverage_ratio,
        "coverageThreshold": coverage_threshold,
        "coverageThresholdPassed": coverage_threshold_passed,
        "coverageThresholdFailure": not coverage_threshold_passed,
        "fulfilledSeries": list(fulfilled_required),
        "missingSeries": list(missing),
    }
    if stale:
        evidence["staleSeries"] = list(stale)
    if malformed:
        evidence["malformedSeries"] = list(malformed)
    if fallback_or_proxy:
        evidence["fallbackOrProxySeries"] = list(fallback_or_proxy)
    if unavailable:
        evidence["unavailableSeries"] = list(unavailable)
    if budget_blocked:
        evidence["budgetBlockedSeries"] = list(budget_blocked)

    return {
        "providerId": provider_id,
        "providerName": provider_name,
        "source": provider_id,
        "sourceLabel": source_label,
        "sourceType": source_type,
        "sourceTier": source_tier,
        "trustLevel": "score_grade" if readiness_eligible else "score_grade_when_configured",
        "retrievalMode": "cache_only",
        "cacheOnly": True,
        "externalProviderCalls": False,
        "runtimeState": runtime_state,
        "freshness": freshness,
        "requiredSeries": list(required_series),
        "contextSeries": list(context_series),
        "eligibleSeries": list(eligible_series),
        "fulfilledSeries": list(fulfilled_required),
        "fulfilledContextSeries": list(fulfilled_context),
        "missingSeries": list(missing),
        "staleSeries": list(stale),
        "malformedSeries": list(malformed),
        "fallbackOrProxySeries": list(fallback_or_proxy),
        "unavailableSeries": list(unavailable),
        "blockedSeries": list(blocked),
        "policyRejectedSeries": list(policy_rejected),
        "budgetBlockedSeries": list(budget_blocked),
        "requiredMetrics": list(required_series),
        "fulfilledMetrics": list(fulfilled_required),
        "missingMetrics": list(missing),
        "coverageCount": coverage_count,
        "coverageRatio": coverage_ratio,
        "coverageThreshold": coverage_threshold,
        "coverageThresholdPassed": coverage_threshold_passed,
        "coverageThresholdFailure": not coverage_threshold_passed,
        "coverage": coverage_ratio,
        "isPartial": bool(has_runtime_rows and not readiness_eligible),
        "isStale": bool(stale),
        "isUnavailable": not has_runtime_rows or bool(unavailable and not fulfilled_required),
        "isFallback": False,
        "fallbackUsed": False,
        "observationOnly": not readiness_eligible,
        "sourceAuthorityAllowed": readiness_eligible,
        "scoreContributionAllowed": readiness_eligible,
        "readinessEligible": readiness_eligible,
        "scoreGradeEvidenceAllowed": readiness_eligible,
        "cacheSafeOfficialEvidenceAllowed": readiness_eligible,
        "reasonCodes": reason_codes,
        "degradationReason": degradation_reason,
        "sourceFreshnessEvidence": evidence,
    }


def _append_classification_reason(
    reason: str,
    *,
    series_id: str,
    stale: list[str],
    malformed: list[str],
    fallback_or_proxy: list[str],
    unavailable: list[str],
    policy_rejected: list[str],
    budget_blocked: list[str],
) -> None:
    if reason == "malformed":
        malformed.append(series_id)
    elif reason == "stale":
        stale.append(series_id)
    elif reason == "fallback_or_proxy":
        fallback_or_proxy.append(series_id)
    elif reason == "policy_rejected":
        policy_rejected.append(series_id)
    elif reason == "budget_blocked":
        budget_blocked.append(series_id)
    else:
        unavailable.append(series_id)


def _classify_fed_liquidity_row(row: Mapping[str, Any], series_id: str) -> dict[str, Any]:
    freshness = _row_freshness(row)
    if _row_budget_blocked(row):
        return {"present": False, "reason": "budget_blocked", "blocked": False, "freshness": freshness}
    if _row_is_fallback_or_proxy(row, freshness=freshness):
        return {"present": False, "reason": "fallback_or_proxy", "blocked": False, "freshness": freshness}
    if _row_is_stale(row, freshness=freshness):
        return {"present": False, "reason": "stale", "blocked": False, "freshness": freshness}
    if _row_is_unavailable(row, freshness=freshness):
        return {"present": False, "reason": "unavailable", "blocked": False, "freshness": freshness}
    numeric_value = _numeric(row.get("value") if row.get("value") is not None else row.get("price"))
    if numeric_value is None:
        return {"present": False, "reason": "malformed", "blocked": False, "freshness": freshness}
    if not _row_has_official_fred_provenance(row, series_id):
        return {"present": False, "reason": "fallback_or_proxy", "blocked": False, "freshness": freshness}
    if freshness not in _RELIABLE_FRESHNESS:
        return {"present": False, "reason": "unavailable", "blocked": False, "freshness": freshness}
    if not _row_is_cache_safe(row):
        return {"present": False, "reason": "policy_rejected", "blocked": False, "freshness": freshness}
    if _row_policy_rejected(row, series_id):
        return {"present": False, "reason": "policy_rejected", "blocked": False, "freshness": freshness}
    blocked = bool(row.get("sourceAuthorityAllowed") is False or row.get("scoreContributionAllowed") is False)
    return {"present": True, "reason": None, "blocked": blocked, "freshness": freshness}


def _classify_usd_pressure_row(row: Mapping[str, Any], series_id: str) -> dict[str, Any]:
    freshness = _row_freshness(row)
    if _row_budget_blocked(row):
        return {"present": False, "reason": "budget_blocked", "blocked": False, "freshness": freshness}
    if _row_is_fallback_or_proxy(row, freshness=freshness):
        return {"present": False, "reason": "fallback_or_proxy", "blocked": False, "freshness": freshness}
    if _row_is_stale(row, freshness=freshness):
        return {"present": False, "reason": "stale", "blocked": False, "freshness": freshness}
    if _row_is_unavailable(row, freshness=freshness):
        return {"present": False, "reason": "unavailable", "blocked": False, "freshness": freshness}
    numeric_value = _numeric(row.get("value") if row.get("value") is not None else row.get("price"))
    if numeric_value is None:
        return {"present": False, "reason": "malformed", "blocked": False, "freshness": freshness}
    if not _row_has_official_usd_pressure_provenance(row, series_id):
        return {"present": False, "reason": "fallback_or_proxy", "blocked": False, "freshness": freshness}
    if freshness not in _RELIABLE_FRESHNESS:
        return {"present": False, "reason": "unavailable", "blocked": False, "freshness": freshness}
    if not _row_is_cache_safe(row):
        return {"present": False, "reason": "policy_rejected", "blocked": False, "freshness": freshness}
    if _official_macro_policy_rejected(row, series_id, OFFICIAL_USD_PRESSURE_FRESHNESS_POLICIES):
        return {"present": False, "reason": "policy_rejected", "blocked": False, "freshness": freshness}
    blocked = bool(row.get("sourceAuthorityAllowed") is False or row.get("scoreContributionAllowed") is False)
    return {"present": True, "reason": None, "blocked": blocked, "freshness": freshness}


def _classify_us_rates_row(row: Mapping[str, Any], series_id: str) -> dict[str, Any]:
    freshness = _row_freshness(row)
    if _row_budget_blocked(row):
        return {"present": False, "reason": "budget_blocked", "blocked": False, "freshness": freshness}
    if _row_is_fallback_or_proxy(row, freshness=freshness):
        return {"present": False, "reason": "fallback_or_proxy", "blocked": False, "freshness": freshness}
    if _row_is_stale(row, freshness=freshness):
        return {"present": False, "reason": "stale", "blocked": False, "freshness": freshness}
    if _row_is_unavailable(row, freshness=freshness):
        return {"present": False, "reason": "unavailable", "blocked": False, "freshness": freshness}
    numeric_value = _numeric(row.get("value") if row.get("value") is not None else row.get("price"))
    if numeric_value is None:
        return {"present": False, "reason": "malformed", "blocked": False, "freshness": freshness}
    if not _row_has_official_us_rates_provenance(row, series_id):
        return {"present": False, "reason": "fallback_or_proxy", "blocked": False, "freshness": freshness}
    if freshness not in _RELIABLE_FRESHNESS:
        return {"present": False, "reason": "unavailable", "blocked": False, "freshness": freshness}
    if not _row_is_cache_safe(row):
        return {"present": False, "reason": "policy_rejected", "blocked": False, "freshness": freshness}
    if _official_macro_policy_rejected(row, series_id, OFFICIAL_US_RATES_FRESHNESS_POLICIES):
        return {"present": False, "reason": "policy_rejected", "blocked": False, "freshness": freshness}
    blocked = bool(row.get("sourceAuthorityAllowed") is False or row.get("scoreContributionAllowed") is False)
    return {"present": True, "reason": None, "blocked": blocked, "freshness": freshness}


def _classify_cn_money_market_row(row: Mapping[str, Any], series_id: str) -> dict[str, Any]:
    freshness = _row_freshness(row)
    if _row_is_unavailable(row, freshness=freshness):
        return {"present": False, "reason": "unavailable", "blocked": False, "freshness": freshness}
    if _row_is_fallback_or_proxy(row, freshness=freshness):
        return {"present": False, "reason": "fallback_or_proxy", "blocked": False, "freshness": freshness}
    if _row_is_stale(row, freshness=freshness):
        return {"present": False, "reason": "stale", "blocked": False, "freshness": freshness}
    numeric_value = _numeric(row.get("value") if row.get("value") is not None else row.get("price"))
    if numeric_value is None:
        return {"present": False, "reason": "malformed", "blocked": False, "freshness": freshness}
    if not _row_has_official_cn_money_market_provenance(row, series_id):
        return {"present": False, "reason": "fallback_or_proxy", "blocked": False, "freshness": freshness}
    if freshness not in _RELIABLE_CACHE_FRESHNESS:
        return {"present": False, "reason": "policy_rejected", "blocked": False, "freshness": freshness}
    if not _row_is_cache_safe(row):
        return {"present": False, "reason": "policy_rejected", "blocked": False, "freshness": freshness}
    blocked = bool(row.get("sourceAuthorityAllowed") is False or row.get("readinessEligible") is False)
    return {"present": True, "reason": None, "blocked": blocked, "freshness": freshness}


def _row_has_official_fred_provenance(row: Mapping[str, Any], series_id: str) -> bool:
    source_type = _text(row.get("sourceType") or row.get("source_type")).lower()
    source_tier = _text(row.get("sourceTier") or row.get("source_tier")).lower()
    source = _text(row.get("source")).lower()
    source_id = _text(row.get("sourceId") or row.get("source_id")).lower()
    explicit_series_id = _text(row.get("officialSeriesId") or row.get("official_series_id") or row.get("seriesId") or row.get("series_id")).upper()
    official_type = source_type == "official_public" or source_tier == "official_public"
    official_source = (
        explicit_series_id == series_id
        or source in {"fred", OFFICIAL_FED_LIQUIDITY_PROVIDER_ID}
        or source_id == f"fred:{series_id}".lower()
        or source_id.endswith(f":{series_id}".lower())
    )
    return bool(official_type and official_source)


def _row_has_official_usd_pressure_provenance(row: Mapping[str, Any], series_id: str) -> bool:
    source_type = _text(row.get("sourceType") or row.get("source_type")).lower()
    source_tier = _text(row.get("sourceTier") or row.get("source_tier")).lower()
    source = _text(row.get("source")).lower()
    provider_id = _text(row.get("providerId") or row.get("provider_id")).lower()
    source_id = _text(row.get("sourceId") or row.get("source_id")).lower()
    explicit_series_id = _text(
        row.get("officialSeriesId")
        or row.get("official_series_id")
        or row.get("seriesId")
        or row.get("series_id")
    ).upper()
    official_type = source_type == "official_public" or source_tier == "official_public"
    official_source = (
        provider_id == OFFICIAL_USD_PRESSURE_PROVIDER_ID
        or source in {"fred", OFFICIAL_USD_PRESSURE_PROVIDER_ID}
        or explicit_series_id == series_id
        or source_id == f"fred:{series_id}".lower()
        or source_id.endswith(f":{series_id}".lower())
    )
    return bool(official_type and official_source)


def _row_has_official_us_rates_provenance(row: Mapping[str, Any], series_id: str) -> bool:
    source_type = _text(row.get("sourceType") or row.get("source_type")).lower()
    source_tier = _text(row.get("sourceTier") or row.get("source_tier")).lower()
    source = _text(row.get("source")).lower()
    provider_id = _text(row.get("providerId") or row.get("provider_id")).lower()
    source_id = _text(row.get("sourceId") or row.get("source_id")).lower()
    normalized_series = official_us_rates_series_id(row)
    official_type = source_type == "official_public" or source_tier == "official_public"
    official_source = (
        provider_id == OFFICIAL_US_RATES_PROVIDER_ID
        or source in {"fred", "treasury", "nyfed", OFFICIAL_US_RATES_PROVIDER_ID}
        or source_id.startswith(("fred:", "treasury:", "nyfed:"))
        or normalized_series == series_id
    )
    return bool(official_type and official_source and normalized_series == series_id)


def _row_has_official_cn_money_market_provenance(row: Mapping[str, Any], series_id: str) -> bool:
    source_type = _text(row.get("sourceType") or row.get("source_type")).lower()
    source_tier = _text(row.get("sourceTier") or row.get("source_tier")).lower()
    source = _text(row.get("source")).lower()
    provider_id = _text(row.get("providerId") or row.get("provider_id")).lower()
    source_id = _text(row.get("sourceId") or row.get("source_id")).upper()
    explicit_series_id = _text(
        row.get("officialSeriesId")
        or row.get("official_series_id")
        or row.get("seriesId")
        or row.get("series_id")
    ).upper()
    official_type = source_type == "official_public" or source_tier == "official_public"
    official_source = (
        provider_id == OFFICIAL_CN_MONEY_MARKET_PROVIDER_ID
        or source == OFFICIAL_CN_MONEY_MARKET_PROVIDER_ID
        or explicit_series_id == series_id
        or source_id == series_id
        or source_id.endswith(f":{series_id}")
    )
    return bool(official_type and official_source)


def _row_is_cache_safe(row: Mapping[str, Any]) -> bool:
    evidence = row.get("sourceFreshnessEvidence")
    external_provider_calls = row.get("externalProviderCalls")
    cache_only = row.get("cacheOnly")
    if isinstance(evidence, Mapping):
        if evidence.get("externalProviderCalls") is True:
            return False
        if evidence.get("cacheOnly") is False:
            return False
    if external_provider_calls is True or cache_only is False:
        return False
    return True


def _row_freshness(row: Mapping[str, Any]) -> str:
    evidence = row.get("sourceFreshnessEvidence")
    evidence_freshness = ""
    if isinstance(evidence, Mapping):
        evidence_freshness = _text(evidence.get("freshness")).lower()
    return _text(row.get("freshness") or evidence_freshness or "unavailable").lower()


def _row_is_stale(row: Mapping[str, Any], *, freshness: str) -> bool:
    evidence = row.get("sourceFreshnessEvidence")
    evidence_is_stale = isinstance(evidence, Mapping) and bool(evidence.get("isStale"))
    return bool(row.get("isStale") or evidence_is_stale or freshness in _STALE_FRESHNESS)


def _row_is_unavailable(row: Mapping[str, Any], *, freshness: str) -> bool:
    evidence = row.get("sourceFreshnessEvidence")
    evidence_is_unavailable = isinstance(evidence, Mapping) and bool(evidence.get("isUnavailable"))
    return bool(row.get("isUnavailable") or evidence_is_unavailable or freshness in _UNAVAILABLE_FRESHNESS)


def _row_is_fallback_or_proxy(row: Mapping[str, Any], *, freshness: str) -> bool:
    evidence = row.get("sourceFreshnessEvidence")
    evidence_is_fallback = isinstance(evidence, Mapping) and bool(evidence.get("isFallback"))
    source_type = _text(row.get("sourceType") or row.get("source_type")).lower()
    source = _text(row.get("source")).lower()
    return bool(
        row.get("isFallback")
        or row.get("fallbackUsed")
        or evidence_is_fallback
        or freshness in _FALLBACK_FRESHNESS
        or source in {"fallback", "mock", "synthetic", "yahoo", "yfinance", "yfinance_proxy"}
        or source_type in _PROXY_OR_FALLBACK_SOURCE_TYPES
    )


def _row_policy_rejected(row: Mapping[str, Any], series_id: str) -> bool:
    evidence = row.get("sourceFreshnessEvidence")
    if not isinstance(evidence, Mapping):
        return False
    policy = _text(evidence.get("freshnessPolicy") or row.get("freshnessPolicy"))
    expected = OFFICIAL_FED_LIQUIDITY_FRESHNESS_POLICIES[series_id]
    return bool(policy and policy != expected)


def _official_macro_policy_rejected(
    row: Mapping[str, Any],
    series_id: str,
    freshness_policies: Mapping[str, str],
) -> bool:
    evidence = row.get("sourceFreshnessEvidence")
    policy = _text(row.get("freshnessPolicy"))
    if isinstance(evidence, Mapping):
        policy = _text(evidence.get("freshnessPolicy") or policy)
    expected = freshness_policies.get(series_id)
    return bool(policy and expected and policy != expected)


def _row_budget_blocked(row: Mapping[str, Any]) -> bool:
    evidence = row.get("sourceFreshnessEvidence")
    values: list[Any] = [
        row.get("sourceAuthorityReason"),
        row.get("degradationReason"),
        row.get("officialOverlayFailureReason"),
    ]
    route_codes = row.get("routeRejectedReasonCodes")
    if isinstance(route_codes, Sequence) and not isinstance(route_codes, (str, bytes)):
        values.extend(route_codes)
    if isinstance(evidence, Mapping):
        values.extend(
            [
                evidence.get("sourceAuthorityReason"),
                evidence.get("degradationReason"),
                evidence.get("officialOverlayFailureReason"),
            ]
        )
        reason_codes = evidence.get("reasonCodes")
        if isinstance(reason_codes, Sequence) and not isinstance(reason_codes, (str, bytes)):
            values.extend(reason_codes)
    normalized = {_text(value).lower() for value in values if _text(value)}
    return bool(
        "budget_exhausted" in normalized
        or "external_call_budget_exhausted" in normalized
        or "skipped_by_budget" in normalized
    )


def _numeric(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _bundle_freshness(
    *,
    score_allowed: bool,
    freshness_values: Sequence[str],
    stale: Sequence[str],
    malformed: Sequence[str],
    fallback_or_proxy: Sequence[str],
    unavailable: Sequence[str],
    has_runtime_rows: bool,
) -> str:
    if score_allowed:
        normalized = [_normalize_freshness(item) for item in freshness_values]
        return max(normalized, key=lambda item: _FRESHNESS_RANK.get(item, 99)) if normalized else "delayed"
    if stale:
        return "stale"
    if fallback_or_proxy:
        return "fallback"
    if malformed or unavailable:
        return "unavailable"
    if has_runtime_rows:
        return "partial"
    return "unavailable"


def _cn_money_market_bundle_freshness(
    *,
    readiness_eligible: bool,
    freshness_values: Sequence[str],
    stale: Sequence[str],
    malformed: Sequence[str],
    fallback_or_proxy: Sequence[str],
    unavailable: Sequence[str],
    has_runtime_rows: bool,
) -> str:
    if readiness_eligible:
        normalized = [_normalize_freshness(item) for item in freshness_values]
        return max(normalized, key=lambda item: _FRESHNESS_RANK.get(item, 99)) if normalized else "delayed"
    if stale:
        return "stale"
    if fallback_or_proxy:
        return "fallback"
    if malformed or unavailable:
        return "unavailable"
    if has_runtime_rows:
        return "partial"
    return "unavailable"


def _normalize_freshness(value: str) -> str:
    return "delayed" if value == "fresh" else value


def _reason_codes(
    *,
    missing: Sequence[str],
    stale: Sequence[str],
    malformed: Sequence[str],
    fallback_or_proxy: Sequence[str],
    unavailable: Sequence[str],
    blocked: Sequence[str],
    policy_rejected: Sequence[str],
    budget_blocked: Sequence[str] = (),
) -> list[str]:
    codes = ["official_macro_transport_supported"]
    if budget_blocked:
        codes.append("budget_blocked_official_macro_route")
    if stale:
        codes.append("stale_official_macro_evidence")
    if malformed:
        codes.append("malformed_official_value")
    if fallback_or_proxy:
        codes.append("fallback_or_proxy_source")
    if unavailable:
        codes.append("unavailable_official_macro_evidence")
    if blocked:
        codes.append("source_authority_or_score_gate_blocked")
    if policy_rejected:
        codes.append("freshness_policy_mismatch")
    if missing:
        codes.append("missing_official_macro_row")
    return list(dict.fromkeys(codes))


def _macro_readiness_reason_codes(
    *,
    reason_prefix: str,
    readiness_eligible: bool,
    missing: Sequence[str],
    stale: Sequence[str],
    malformed: Sequence[str],
    fallback_or_proxy: Sequence[str],
    unavailable: Sequence[str],
    blocked: Sequence[str],
    policy_rejected: Sequence[str],
    budget_blocked: Sequence[str],
) -> list[str]:
    codes = [f"{reason_prefix}_readiness_contract"]
    if readiness_eligible:
        codes.append(f"{reason_prefix}_readiness_eligible")
    if budget_blocked:
        codes.append("budget_blocked_official_macro_route")
    if stale:
        codes.append(f"stale_{reason_prefix}_evidence")
    if malformed:
        codes.append("malformed_official_value")
    if fallback_or_proxy:
        codes.append("fallback_or_proxy_source")
    if unavailable:
        codes.append(f"unavailable_{reason_prefix}_evidence")
    if blocked:
        codes.append("source_authority_or_score_gate_blocked")
    if policy_rejected:
        codes.append("cache_safety_policy_mismatch")
    if missing:
        codes.append(f"missing_{reason_prefix}_row")
    return list(dict.fromkeys(codes))


def _cn_money_market_reason_codes(
    *,
    readiness_eligible: bool,
    missing: Sequence[str],
    stale: Sequence[str],
    malformed: Sequence[str],
    fallback_or_proxy: Sequence[str],
    unavailable: Sequence[str],
    blocked: Sequence[str],
    policy_rejected: Sequence[str],
) -> list[str]:
    codes = ["official_cn_money_market_readiness_contract"]
    if readiness_eligible:
        codes.append("official_cn_money_market_readiness_eligible")
    if stale:
        codes.append("stale_official_cn_money_market_evidence")
    if malformed:
        codes.append("malformed_official_value")
    if fallback_or_proxy:
        codes.append("fallback_or_proxy_source")
    if unavailable:
        codes.append("unavailable_official_cn_money_market_evidence")
    if blocked:
        codes.append("source_authority_or_readiness_gate_blocked")
    if policy_rejected:
        codes.append("cache_safety_policy_mismatch")
    if missing:
        codes.append("missing_official_cn_money_market_row")
    return list(dict.fromkeys(codes))


def _text(value: Any) -> str:
    return str(value or "").strip()


__all__ = [
    "OFFICIAL_CN_MONEY_MARKET_ALIAS_TO_SERIES_ID",
    "OFFICIAL_CN_MONEY_MARKET_CONTEXT_SERIES",
    "OFFICIAL_CN_MONEY_MARKET_FRESHNESS_POLICIES",
    "OFFICIAL_CN_MONEY_MARKET_PROVIDER_ID",
    "OFFICIAL_CN_MONEY_MARKET_PROVIDER_NAME",
    "OFFICIAL_CN_MONEY_MARKET_REQUIRED_SERIES",
    "OFFICIAL_CN_MONEY_MARKET_SOURCE_TIER",
    "OFFICIAL_CN_MONEY_MARKET_SOURCE_TYPE",
    "OFFICIAL_FED_LIQUIDITY_FRESHNESS_POLICIES",
    "OFFICIAL_FED_LIQUIDITY_PROVIDER_ID",
    "OFFICIAL_FED_LIQUIDITY_PROVIDER_NAME",
    "OFFICIAL_FED_LIQUIDITY_REQUIRED_SERIES",
    "OFFICIAL_FED_LIQUIDITY_SERIES_TO_SYMBOL",
    "OFFICIAL_FED_LIQUIDITY_SOURCE_TIER",
    "OFFICIAL_FED_LIQUIDITY_SOURCE_TYPE",
    "OFFICIAL_FED_LIQUIDITY_SYMBOL_TO_SERIES_ID",
    "OFFICIAL_USD_PRESSURE_FRESHNESS_POLICIES",
    "OFFICIAL_USD_PRESSURE_PROVIDER_ID",
    "OFFICIAL_USD_PRESSURE_PROVIDER_NAME",
    "OFFICIAL_USD_PRESSURE_REQUIRED_SERIES",
    "OFFICIAL_USD_PRESSURE_SOURCE_TIER",
    "OFFICIAL_USD_PRESSURE_SOURCE_TYPE",
    "OFFICIAL_USD_PRESSURE_SYMBOL_TO_SERIES_ID",
    "OFFICIAL_US_RATES_CONTEXT_SERIES",
    "OFFICIAL_US_RATES_FRESHNESS_POLICIES",
    "OFFICIAL_US_RATES_PROVIDER_ID",
    "OFFICIAL_US_RATES_PROVIDER_NAME",
    "OFFICIAL_US_RATES_REQUIRED_SERIES",
    "OFFICIAL_US_RATES_SOURCE_TIER",
    "OFFICIAL_US_RATES_SOURCE_TYPE",
    "OFFICIAL_US_RATES_SYMBOL_TO_SERIES_ID",
    "build_official_cn_money_market_cache_bundle",
    "build_official_fed_liquidity_cache_bundle",
    "build_official_us_rates_cache_bundle",
    "build_official_usd_pressure_cache_bundle",
    "official_cn_money_market_series_id",
    "official_fed_liquidity_series_id",
    "official_us_rates_series_id",
    "official_usd_pressure_series_id",
]
