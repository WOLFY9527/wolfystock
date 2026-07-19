# -*- coding: utf-8 -*-
"""Shared VIX metadata normalization helpers."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional


VOLATILITY_AUTHORITY_SNAPSHOT_CONTRACT_VERSION = "volatility_authority_snapshot_v1"
_VIX_SYMBOLS = {"VIX", "VIXCLS"}
_PROXY_SOURCE_VALUES = {"yahoo", "yfinance", "yfinance_proxy"}
_PROXY_SOURCE_TYPES = {"unofficial_proxy", "public_proxy", "proxy_public"}
_OFFICIAL_SOURCE_VALUES = {"fred"}
_OFFICIAL_SOURCE_TYPES = {"official_public"}
_OFFICIAL_VIX_SERIES_ID = "VIXCLS"
_FRESH_STATES = {"fresh", "live"}
_DELAYED_STATES = {"delayed", "cached"}
_STALE_STATES = {"stale", "fallback", "mock", "unavailable", "error", "partial", "synthetic"}


def is_vix_symbol(value: Any) -> bool:
    text = str(value or "").strip().upper()
    if not text:
        return False
    return text in _VIX_SYMBOLS or text.lstrip("^") in _VIX_SYMBOLS or text.endswith(":VIXCLS")


def normalize_vix_quote_metadata(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Return VIX quote metadata with delayed/unofficial semantics preserved."""

    normalized = dict(payload)
    if not is_vix_symbol(
        normalized.get("symbol")
        or normalized.get("key")
        or normalized.get("label")
        or normalized.get("sourceId")
    ):
        return normalized

    source = str(normalized.get("source") or "").strip().lower()
    source_type = str(normalized.get("sourceType") or "").strip().lower()
    source_id = str(normalized.get("sourceId") or "").strip().lower()
    freshness = str(normalized.get("freshness") or "").strip().lower()

    original_freshness = freshness
    if source in _PROXY_SOURCE_VALUES or source_type in _PROXY_SOURCE_TYPES:
        normalized["sourceType"] = "unofficial_proxy"
        normalized["sourceLabel"] = normalized.get("sourceLabel") or "Yahoo Finance"
        normalized["freshness"] = _normalize_proxy_freshness(freshness)
    elif source in _OFFICIAL_SOURCE_VALUES or source_type in _OFFICIAL_SOURCE_TYPES or source_id == "fred:vixcls":
        normalized["sourceType"] = "official_public"
        normalized["freshness"] = _normalize_official_freshness(freshness)

    freshness = str(normalized.get("freshness") or "").strip().lower()
    if freshness in {"delayed", "stale", "cached"} and (
        (freshness != original_freshness and not normalized.get("degradationReason"))
        or normalized.get("degradationReason") == "proxy_source"
    ):
        normalized["degradationReason"] = "delayed_source"
    if freshness == "delayed":
        normalized["isStale"] = False
    normalized = _apply_volatility_authority_snapshot(normalized)
    return normalized


def normalize_vix_panel_metadata(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a VIX-sensitive panel payload with explicit freshness metadata."""

    normalized = dict(payload)
    raw_items = normalized.get("items")
    if not isinstance(raw_items, list):
        return normalized

    raw_vix_item = _first_vix_item(raw_items)
    if not isinstance(raw_vix_item, dict):
        return normalized
    vix_item = normalize_vix_quote_metadata(raw_vix_item)
    normalized["items"] = [
        {
            **item,
            "sourceType": vix_item.get("sourceType"),
            "sourceLabel": vix_item.get("sourceLabel"),
            "freshness": vix_item.get("freshness"),
            "isStale": bool(vix_item.get("isStale")),
            "degradationReason": vix_item.get("degradationReason"),
            "sourceFreshnessEvidence": {
                "freshness": vix_item.get("freshness"),
                "isFallback": bool(vix_item.get("isFallback")),
                "isStale": bool(vix_item.get("isStale")),
                "isPartial": bool(vix_item.get("isPartial")),
                "isUnavailable": bool(vix_item.get("isUnavailable")),
                "warning": vix_item.get("warning"),
            },
        }
        if item is raw_vix_item
        else item
        for item in raw_items
    ]

    panel_source = str(normalized.get("source") or "").strip().lower()
    if vix_item.get("sourceType") and not normalized.get("sourceType") and panel_source != "mixed":
        normalized["sourceType"] = vix_item["sourceType"]
    if vix_item.get("asOf"):
        normalized["asOf"] = vix_item["asOf"]
    if vix_item.get("updatedAt"):
        normalized["updatedAt"] = vix_item["updatedAt"]

    freshness = str(vix_item.get("freshness") or "").strip().lower()
    if freshness:
        normalized["sourceFreshnessEvidence"] = {
            "freshness": freshness,
            "isFallback": bool(vix_item.get("isFallback")),
            "isStale": bool(vix_item.get("isStale") or freshness == "stale"),
            "isPartial": bool(vix_item.get("isPartial")),
            "isUnavailable": bool(vix_item.get("isUnavailable")),
            "warning": vix_item.get("warning"),
        }
    return normalized


def _first_vix_item(items: list[Any]) -> Optional[Dict[str, Any]]:
    for item in items:
        if isinstance(item, dict) and is_vix_symbol(item.get("symbol")):
            return item
    return None


def _apply_volatility_authority_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    snapshot = _build_volatility_authority_snapshot(payload)
    result = dict(payload)
    result["volatilityAuthoritySnapshot"] = snapshot
    result["volatilitySnapshotId"] = snapshot["snapshotId"]
    result["sourceAuthorityState"] = snapshot["authorityState"]
    result["scoreAuthorityEligible"] = bool(snapshot["scoreEligibility"]["allowed"])
    result["scoreContributionAllowed"] = bool(snapshot["scoreEligibility"]["allowed"])

    if snapshot["authorityState"] in {"blocked", "proxy", "missing"}:
        result["sourceAuthorityAllowed"] = False
        result["observationOnly"] = True
    elif snapshot["authorityState"] == "official":
        result["sourceAuthorityAllowed"] = result.get("sourceAuthorityAllowed") is True
        if result["sourceAuthorityAllowed"] is not True:
            result["observationOnly"] = True

    if snapshot["proxyFallback"]:
        result["isProxy"] = True
        result["observationOnly"] = True
        if snapshot["freshnessState"] in _DELAYED_STATES:
            result["degradationReason"] = "delayed_source"
    if snapshot["coverageState"] == "rejected":
        result["isUnavailable"] = True
    result["consumerEligibility"] = dict(snapshot["consumerEligibility"])
    return result


def _build_volatility_authority_snapshot(payload: Mapping[str, Any]) -> Dict[str, Any]:
    source = _safe_text(payload.get("source")).lower()
    source_type = _safe_text(payload.get("sourceType")).lower()
    source_id = _safe_text(payload.get("sourceId"))
    source_id_lower = source_id.lower()
    symbol = _canonical_vix_symbol(payload)
    official_series_id = _official_series_id(payload)
    observation_time = _safe_text(payload.get("asOf") or payload.get("date") or payload.get("timestamp")) or None
    retrieval_time = _safe_text(payload.get("updatedAt") or payload.get("receivedAt") or payload.get("retrievedAt")) or None
    freshness = _freshness_state(payload)
    is_proxy = source in _PROXY_SOURCE_VALUES or source_type in _PROXY_SOURCE_TYPES
    is_official = source in _OFFICIAL_SOURCE_VALUES or source_type in _OFFICIAL_SOURCE_TYPES or source_id_lower == "fred:vixcls"
    identity_state = _vix_identity_state(symbol=symbol, official_series_id=official_series_id, source_id=source_id)

    authority_state = "missing"
    coverage_state = "missing"
    delayed_stale_reason = None
    if identity_state == "identity_mismatch":
        authority_state = "blocked"
        coverage_state = "rejected"
        delayed_stale_reason = "identity_mismatch"
    elif is_proxy:
        authority_state = "proxy"
        coverage_state = "available" if _has_value(payload) else "missing"
        delayed_stale_reason = _freshness_reason(freshness, proxy=True)
    elif is_official:
        authority_state = "official"
        coverage_state = "available" if _has_value(payload) else "missing"
        delayed_stale_reason = _freshness_reason(freshness, proxy=False)
    elif _has_value(payload):
        authority_state = "blocked"
        coverage_state = "rejected"
        delayed_stale_reason = "unrecognized_volatility_source"

    explicit_authority = payload.get("sourceAuthorityAllowed") is True
    consumer_eligible = (
        authority_state == "official"
        and coverage_state == "available"
        and freshness not in _STALE_STATES
        and explicit_authority
    )
    market_overview_eligible = consumer_eligible or (authority_state == "proxy" and coverage_state == "available")
    score_reason = _score_eligibility_reason(
        authority_state=authority_state,
        coverage_state=coverage_state,
        identity_state=identity_state,
        freshness=freshness,
    )
    snapshot_id = _volatility_snapshot_id(
        symbol=symbol,
        source_id=source_id,
        observation_time=observation_time,
    )

    return {
        "contractVersion": VOLATILITY_AUTHORITY_SNAPSHOT_CONTRACT_VERSION,
        "snapshotId": snapshot_id,
        "instrumentIdentity": {
            "symbol": symbol,
            "canonicalSymbol": "VIX",
            "officialSeriesId": official_series_id,
            "identityState": identity_state,
        },
        "sourceId": source_id or None,
        "sourceType": source_type or None,
        "authorityState": authority_state,
        "observationTime": observation_time,
        "retrievalTime": retrieval_time,
        "freshnessState": freshness,
        "delayedStaleReason": delayed_stale_reason,
        "coverageState": coverage_state,
        "proxyFallback": authority_state == "proxy",
        "consumerEligibility": {
            "marketOverview": bool(market_overview_eligible),
            "liquidity": bool(consumer_eligible),
            "scenarioBaseline": bool(consumer_eligible),
        },
        "scoreEligibility": {
            "allowed": False,
            "reason": score_reason,
        },
    }


def _canonical_vix_symbol(payload: Mapping[str, Any]) -> str:
    raw = _safe_text(payload.get("symbol") or payload.get("key") or payload.get("label") or "VIX").upper()
    return "VIX" if raw in {"^VIX", "VIXCLS"} else raw[:32] or "VIX"


def _official_series_id(payload: Mapping[str, Any]) -> str:
    series_id = _safe_text(payload.get("officialSeriesId")).upper()
    if series_id:
        return series_id[:32]
    source_id = _safe_text(payload.get("sourceId")).upper()
    if source_id.endswith(":VIXCLS"):
        return _OFFICIAL_VIX_SERIES_ID
    symbol = _safe_text(payload.get("symbol") or payload.get("key")).upper().lstrip("^")
    return _OFFICIAL_VIX_SERIES_ID if symbol in {"VIX", "VIXCLS"} else ""


def _vix_identity_state(*, symbol: str, official_series_id: str, source_id: str) -> str:
    normalized_symbol = symbol.upper().lstrip("^")
    normalized_series = official_series_id.upper()
    normalized_source_id = source_id.upper()
    if normalized_series and normalized_series != _OFFICIAL_VIX_SERIES_ID:
        return "identity_mismatch"
    if normalized_source_id.endswith(":VIXCLS") or normalized_series == _OFFICIAL_VIX_SERIES_ID:
        return "canonical_official_vix"
    if normalized_symbol in {"VIX", "VIXCLS"}:
        return "canonical_vix_proxy"
    return "identity_mismatch"


def _freshness_state(payload: Mapping[str, Any]) -> str:
    freshness = _safe_text(payload.get("freshness") or payload.get("freshnessState")).lower()
    if freshness in _FRESH_STATES | _DELAYED_STATES | _STALE_STATES:
        if freshness == "live":
            return "fresh"
        return freshness
    return "unknown"


def _freshness_reason(freshness: str, *, proxy: bool) -> str | None:
    if proxy:
        return "unofficial_proxy_delayed" if freshness in _FRESH_STATES | _DELAYED_STATES else "unofficial_proxy_stale"
    if freshness in _DELAYED_STATES:
        return "official_delayed_publication"
    if freshness in _STALE_STATES:
        return f"official_{freshness}_source"
    return None


def _score_eligibility_reason(
    *,
    authority_state: str,
    coverage_state: str,
    identity_state: str,
    freshness: str,
) -> str:
    if identity_state == "identity_mismatch":
        return "identity_mismatch"
    if coverage_state != "available":
        return "volatility_snapshot_missing"
    if authority_state == "proxy":
        return "unofficial_proxy_not_score_grade"
    if authority_state != "official":
        return "source_authority_not_official"
    if freshness in _STALE_STATES or freshness == "unknown":
        return "volatility_snapshot_freshness_not_ready"
    return "volatility_snapshot_score_default_closed"


def _volatility_snapshot_id(*, symbol: str, source_id: str, observation_time: str | None) -> str:
    source = source_id or "unknown_source"
    observed = observation_time or "unknown_observation_time"
    return f"volatility:{symbol}:{source}:{observed}"[:240]


def _has_value(payload: Mapping[str, Any]) -> bool:
    value = payload.get("value", payload.get("price"))
    if value is None:
        return False
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_proxy_freshness(freshness: str) -> str:
    if freshness in {"stale", "fallback", "mock", "unavailable", "error", "partial", "synthetic", "cached", "delayed"}:
        return freshness
    return "delayed"


def _normalize_official_freshness(freshness: str) -> str:
    if freshness in {"stale", "fallback", "mock", "unavailable", "error", "partial", "synthetic", "cached", "delayed"}:
        return freshness
    return "delayed"


__all__ = [
    "VOLATILITY_AUTHORITY_SNAPSHOT_CONTRACT_VERSION",
    "is_vix_symbol",
    "normalize_vix_panel_metadata",
    "normalize_vix_quote_metadata",
]
