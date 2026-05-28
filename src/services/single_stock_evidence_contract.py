# -*- coding: utf-8 -*-
"""Pure metadata contract for single-stock evidence boundaries."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence


SINGLE_STOCK_EVIDENCE_CONTRACT_VERSION = "single_stock_evidence_contract_v1"
REDACTED = "redacted"
ALLOWED_DOMAINS = frozenset(
    {
        "quote",
        "fundamentals",
        "technicals",
        "catalyst",
        "intraday",
        "history",
    }
)
ALLOWED_FRESHNESS = frozenset(
    {
        "live",
        "fresh",
        "delayed",
        "cached",
        "stale",
        "partial",
        "fallback",
        "synthetic",
        "unknown",
        "unavailable",
    }
)
_SAFE_TEXT_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789_:-+./ ")
_SECRET_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "password",
    "secret",
    "token",
    "account_id",
    "accountid",
)
_URL_LIKE_HOST_RE = re.compile(r"^[a-z0-9-]+(?:\.[a-z0-9-]+)+(?::\d+)?(?:[/?#].*)?$")
_CONFIDENCE_CAP_RULES = (
    ("unavailable_source", 0.0),
    ("fallback_source", 0.4),
    ("stale_source", 0.6),
    ("partial_coverage", 0.7),
    ("synthetic_source", 0.2),
    ("freshness_not_proven", 0.5),
)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _float(value: Any, *, default: float = 1.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number < 0.0:
        return 0.0
    if number > 1.0:
        return 1.0
    return number


def _looks_like_url_text(text: str) -> bool:
    lowered = text.lower()
    if lowered.startswith(("http://", "https://", "www.")):
        return True
    return bool(_URL_LIKE_HOST_RE.fullmatch(lowered))


def _sanitize_text(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    lowered = text.lower()
    if any(marker in lowered for marker in _SECRET_MARKERS):
        return REDACTED
    if _looks_like_url_text(text):
        return REDACTED
    if any(marker in text for marker in ("{", "}", "[", "]")):
        return REDACTED
    if len(text) > 160:
        return REDACTED
    if any(character.lower() not in _SAFE_TEXT_CHARS for character in text):
        return REDACTED
    return text


def _sanitize_string_list(value: Any) -> list[str]:
    sanitized: list[str] = []
    for item in _sequence(value):
        safe_item = _sanitize_text(item)
        if safe_item is None:
            continue
        sanitized.append(safe_item)
    return sanitized


def _sanitize_domain(value: Any) -> str:
    text = (_sanitize_text(value) or "unknown").lower()
    return text if text in ALLOWED_DOMAINS else "unknown"


def _sanitize_freshness(value: Any) -> str:
    text = (_sanitize_text(value) or "unknown").lower()
    return text if text in ALLOWED_FRESHNESS else "unknown"


def _sanitize_coverage(value: Any) -> float | dict[str, Any] | None:
    if isinstance(value, (int, float)):
        return _float(value, default=0.0)
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, raw in value.items():
            safe_key = _sanitize_text(key)
            safe_value = _sanitize_text(raw)
            if safe_key and safe_value is not None:
                sanitized[safe_key] = safe_value
        return sanitized or None
    return None


def _sanitize_field_refs(value: Any) -> dict[str, dict[str, str]]:
    refs: dict[str, dict[str, str]] = {}
    for field_name, raw_ref in _mapping(value).items():
        safe_field_name = _sanitize_text(field_name)
        if not safe_field_name or safe_field_name == REDACTED:
            continue
        raw_mapping = _mapping(raw_ref)
        safe_ref: dict[str, str] = {}
        for key in ("providerId", "sourceType", "asOf", "freshness", "sourceNote"):
            safe_value = _sanitize_text(raw_mapping.get(key))
            if safe_value is None:
                continue
            safe_ref[key] = _sanitize_freshness(safe_value) if key == "freshness" else safe_value
        if safe_ref:
            refs[safe_field_name] = safe_ref
    return refs


def _active_cap_reasons(
    *,
    is_unavailable: bool,
    is_fallback: bool,
    is_stale: bool,
    is_partial: bool,
    is_synthetic: bool,
    raw_freshness: str,
    freshness: str,
    as_of: str | None,
) -> list[str]:
    reasons: list[str] = []
    if is_unavailable or freshness == "unavailable":
        reasons.append("unavailable_source")
    if is_fallback or freshness == "fallback":
        reasons.append("fallback_source")
    if is_stale or freshness == "stale":
        reasons.append("stale_source")
    if is_partial or freshness == "partial":
        reasons.append("partial_coverage")
    if is_synthetic or freshness == "synthetic":
        reasons.append("synthetic_source")
    if (raw_freshness in {"live", "fresh"} or freshness in {"live", "fresh"}) and not as_of:
        reasons.append("freshness_not_proven")
    return reasons


def _cap_reason_and_value(confidence_weight: float, reasons: Sequence[str]) -> tuple[float, str | None]:
    if not reasons:
        return confidence_weight, None
    cap_lookup = dict(_CONFIDENCE_CAP_RULES)
    capped_weight = confidence_weight
    winning_reason: str | None = None
    winning_cap = 1.0
    for reason in reasons:
        cap = cap_lookup.get(reason)
        if cap is None:
            continue
        if winning_reason is None or cap < winning_cap:
            winning_reason = reason
            winning_cap = cap
        capped_weight = min(capped_weight, cap)
    return capped_weight, winning_reason


def _normalized_freshness(
    raw_freshness: str,
    *,
    is_unavailable: bool,
    is_fallback: bool,
    is_stale: bool,
    is_partial: bool,
    is_synthetic: bool,
    as_of: str | None,
) -> str:
    if is_unavailable:
        return "unavailable"
    if is_fallback:
        return "fallback"
    if is_stale:
        return "stale"
    if is_partial:
        return "partial"
    if is_synthetic:
        return "synthetic"
    if raw_freshness in {"live", "fresh"} and not as_of:
        return "unknown"
    return raw_freshness


def _claim_boundary(claim: str, allowed: bool, reason_code: str, detail: str) -> dict[str, Any]:
    return {
        "claim": claim,
        "allowed": allowed,
        "reasonCode": reason_code,
        "detail": detail,
    }


def build_single_stock_evidence_contract(value: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _mapping(value)
    domain = _sanitize_domain(payload.get("domain"))
    as_of = _sanitize_text(payload.get("asOf"))
    observed_at = _sanitize_text(payload.get("observedAt"))
    generated_at = _sanitize_text(payload.get("generatedAt"))
    raw_freshness = _sanitize_freshness(payload.get("freshness"))
    raw_provider_id = _text(payload.get("providerId")).lower()
    raw_source_type = _text(payload.get("sourceType")).lower()
    is_unavailable = raw_freshness == "unavailable" or raw_provider_id in {"missing", "unavailable"} or raw_source_type in {
        "missing",
        "unavailable",
    }
    is_fallback = _bool(payload.get("isFallback"))
    is_stale = _bool(payload.get("isStale"))
    is_partial = _bool(payload.get("isPartial"))
    is_synthetic = _bool(payload.get("isSynthetic"))
    confidence_weight = _float(payload.get("confidenceWeight"), default=1.0)
    freshness = _normalized_freshness(
        raw_freshness,
        is_unavailable=is_unavailable,
        is_fallback=is_fallback,
        is_stale=is_stale,
        is_partial=is_partial,
        is_synthetic=is_synthetic,
        as_of=as_of,
    )
    active_reasons = _active_cap_reasons(
        is_unavailable=is_unavailable,
        is_fallback=is_fallback,
        is_stale=is_stale,
        is_partial=is_partial,
        is_synthetic=is_synthetic,
        raw_freshness=raw_freshness,
        freshness=freshness,
        as_of=as_of,
    )
    confidence_weight, cap_reason = _cap_reason_and_value(confidence_weight, active_reasons)
    live_or_fresh_reliable = freshness in {"live", "fresh"} and as_of is not None and cap_reason is None
    field_refs = _sanitize_field_refs(payload.get("fieldRefs"))

    claim_boundaries = [
        _claim_boundary(
            "live_or_fresh_reliable",
            live_or_fresh_reliable,
            "freshness_proven" if live_or_fresh_reliable else (cap_reason or "freshness_not_proven"),
            "freshness_and_as_of_present" if live_or_fresh_reliable else "live_or_fresh_claim_blocked",
        ),
        _claim_boundary(
            "field_level_provenance",
            bool(field_refs) if domain == "quote" else True,
            "field_refs_present"
            if domain == "quote" and field_refs
            else "field_refs_not_required"
            if domain != "quote"
            else "field_refs_missing",
            "quote_field_refs_available"
            if domain == "quote" and field_refs
            else "domain_not_quote"
            if domain != "quote"
            else "quote_field_refs_missing",
        ),
    ]

    return {
        "contractVersion": SINGLE_STOCK_EVIDENCE_CONTRACT_VERSION,
        "diagnosticOnly": True,
        "observationOnly": not live_or_fresh_reliable or cap_reason is not None,
        "authorityGrant": False,
        "domain": domain,
        "symbol": _sanitize_text(payload.get("symbol")),
        "providerId": _sanitize_text(payload.get("providerId")),
        "sourceType": _sanitize_text(payload.get("sourceType")),
        "asOf": as_of,
        "observedAt": observed_at,
        "generatedAt": generated_at,
        "freshness": freshness,
        "isFallback": is_fallback,
        "isStale": is_stale,
        "isPartial": is_partial,
        "isSynthetic": is_synthetic,
        "confidenceWeight": confidence_weight,
        "capReason": cap_reason,
        "degradationReason": cap_reason,
        "fallbackChain": _sanitize_string_list(payload.get("fallbackChain")),
        "fieldRefs": field_refs,
        "coverage": _sanitize_coverage(payload.get("coverage")),
        "missingFields": _sanitize_string_list(payload.get("missingFields")),
        "budgetSkipReason": _sanitize_text(payload.get("budgetSkipReason")),
        "claimBoundaries": claim_boundaries,
    }
