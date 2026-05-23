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

_RELIABLE_FRESHNESS = frozenset({"live", "cached", "delayed", "fresh"})
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
        else:
            unavailable.append(series_id)

    required_count = len(OFFICIAL_FED_LIQUIDITY_REQUIRED_SERIES)
    coverage_count = len(fulfilled)
    coverage_ratio = round(coverage_count / required_count, 3)
    has_runtime_rows = bool(rows)
    score_allowed = bool(
        coverage_count == required_count
        and not missing
        and not stale
        and not malformed
        and not fallback_or_proxy
        and not unavailable
        and not blocked
        and not policy_rejected
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
    )
    degradation_reason = None if score_allowed else "fed_liquidity_required_series_missing_or_stale"
    if malformed:
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
    }
    if score_allowed or has_runtime_rows:
        evidence["coverageRatio"] = coverage_ratio
        evidence["fulfilledSeries"] = list(fulfilled)
        evidence["missingSeries"] = list(missing)
    if stale:
        evidence["staleSeries"] = list(stale)
    if malformed:
        evidence["malformedSeries"] = list(malformed)

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
        "requiredMetrics": list(OFFICIAL_FED_LIQUIDITY_REQUIRED_SERIES),
        "fulfilledMetrics": list(fulfilled),
        "missingMetrics": list(missing),
        "coverageCount": coverage_count,
        "coverageRatio": coverage_ratio,
        "coverage": coverage_ratio,
        "isPartial": bool(has_runtime_rows and not score_allowed),
        "isStale": bool(stale),
        "isUnavailable": not has_runtime_rows,
        "isFallback": False,
        "fallbackUsed": False,
        "observationOnly": not score_allowed,
        "sourceAuthorityAllowed": score_allowed,
        "scoreContributionAllowed": score_allowed,
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


def _classify_fed_liquidity_row(row: Mapping[str, Any], series_id: str) -> dict[str, Any]:
    freshness = _row_freshness(row)
    numeric_value = _numeric(row.get("value") if row.get("value") is not None else row.get("price"))
    if numeric_value is None:
        return {"present": False, "reason": "malformed", "blocked": False, "freshness": freshness}
    if _row_is_fallback_or_proxy(row, freshness=freshness):
        return {"present": False, "reason": "fallback_or_proxy", "blocked": False, "freshness": freshness}
    if _row_is_stale(row, freshness=freshness):
        return {"present": False, "reason": "stale", "blocked": False, "freshness": freshness}
    if _row_is_unavailable(row, freshness=freshness):
        return {"present": False, "reason": "unavailable", "blocked": False, "freshness": freshness}
    if not _row_has_official_fred_provenance(row, series_id):
        return {"present": False, "reason": "fallback_or_proxy", "blocked": False, "freshness": freshness}
    if freshness not in _RELIABLE_FRESHNESS:
        return {"present": False, "reason": "unavailable", "blocked": False, "freshness": freshness}
    if _row_policy_rejected(row, series_id):
        return {"present": False, "reason": "policy_rejected", "blocked": False, "freshness": freshness}
    blocked = bool(row.get("sourceAuthorityAllowed") is False or row.get("scoreContributionAllowed") is False)
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
) -> list[str]:
    codes = ["official_macro_transport_supported"]
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


def _text(value: Any) -> str:
    return str(value or "").strip()


__all__ = [
    "OFFICIAL_FED_LIQUIDITY_FRESHNESS_POLICIES",
    "OFFICIAL_FED_LIQUIDITY_PROVIDER_ID",
    "OFFICIAL_FED_LIQUIDITY_PROVIDER_NAME",
    "OFFICIAL_FED_LIQUIDITY_REQUIRED_SERIES",
    "OFFICIAL_FED_LIQUIDITY_SERIES_TO_SYMBOL",
    "OFFICIAL_FED_LIQUIDITY_SOURCE_TIER",
    "OFFICIAL_FED_LIQUIDITY_SOURCE_TYPE",
    "OFFICIAL_FED_LIQUIDITY_SYMBOL_TO_SERIES_ID",
    "build_official_fed_liquidity_cache_bundle",
    "official_fed_liquidity_series_id",
]
