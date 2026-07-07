# -*- coding: utf-8 -*-
"""Provider-neutral news/catalyst readiness and read contract foundation.

This module is intentionally inert. It normalizes caller-supplied evidence into
consumer-safe readiness semantics and never connects news providers, credentials,
caches, transports, or provider ordering.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


NEWS_CATALYST_READ_CONTRACT_VERSION = "news_catalyst_read_contract_v1"

NEWS_CATALYST_CAPABILITY_FAMILIES = (
    "stock_news",
    "market_news",
    "earnings_event_calendar",
    "macro_policy_catalyst",
    "company_developments",
)

READINESS_STATES = (
    "NO_ITEMS",
    "FETCH_FAILED",
    "NOT_CONFIGURED",
    "STALE",
    "PARTIAL",
    "READY",
)

FRESHNESS_STATES = (
    "NO_ITEMS",
    "FETCH_FAILED",
    "NOT_CONFIGURED",
    "STALE",
    "PARTIAL",
    "FRESH",
)

_SOURCE_REQUIRED_FIELDS = ("sourceId", "sourceType", "authority")
_DEFAULT_MAX_AGE_HOURS = 24.0
_FAILURE_ALIASES = frozenset(
    {
        "error",
        "failed",
        "fetch_failed",
        "failure",
        "timeout",
        "timed_out",
        "provider_timeout",
    }
)
_NO_ITEM_ALIASES = frozenset({"empty", "no_item", "no_items", "none"})
_NOT_CONFIGURED_ALIASES = frozenset({"", "missing", "not_configured", "unconfigured", "unsupported"})
_STALE_ALIASES = frozenset({"stale", "delayed"})
_PARTIAL_ALIASES = frozenset({"partial", "degraded", "incomplete"})
_READY_ALIASES = frozenset({"available", "fresh", "ok", "ready"})
_FAILURE_REASON_HINTS = (
    ("provider_timeout", "provider_timeout"),
    ("timeout", "provider_timeout"),
    ("timed_out", "provider_timeout"),
    ("unauthorized", "source_unauthorized"),
    ("forbidden", "source_unauthorized"),
    ("rate_limit", "rate_limited"),
    ("rate limit", "rate_limited"),
)
_SENSITIVE_REASON_HINTS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cachekey",
    "credential",
    "rawpayload",
    "requestid",
    "secret",
    "stack trace",
    "token",
    "traceback",
)
_SAMPLE_MARKERS = ("fixture:", "sample:", "scaffold:", "demo:")


def build_news_catalyst_read_contract_v1(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a provider-neutral, fail-closed news/catalyst read contract."""

    payload = _mapping(value)
    timezone_name = _normalize_timezone(payload.get("timezone"))
    as_of = _normalize_datetime(payload.get("asOf") or payload.get("as_of"), timezone_name)
    family_inputs = _mapping(payload.get("families"))

    families = {
        family: _build_family_contract(
            family=family,
            payload=_mapping(family_inputs.get(family)),
            as_of=as_of,
            timezone_name=timezone_name,
        )
        for family in NEWS_CATALYST_CAPABILITY_FAMILIES
    }

    return {
        "contractVersion": NEWS_CATALYST_READ_CONTRACT_VERSION,
        "providerNeutral": True,
        "networkCallsEnabled": False,
        "runtimeProviderCalls": False,
        "capabilityFamilies": list(NEWS_CATALYST_CAPABILITY_FAMILIES),
        "readinessStates": list(READINESS_STATES),
        "asOf": as_of.isoformat(),
        "timezone": timezone_name,
        "families": families,
        "redactionBoundary": {
            "consumerSafe": True,
            "rawProviderPayloadExposed": False,
            "sensitiveAuthMaterialExposed": False,
            "sampleItemsExposedAsCurrent": False,
        },
    }


def _build_family_contract(
    *,
    family: str,
    payload: Mapping[str, Any],
    as_of: datetime,
    timezone_name: str,
) -> dict[str, Any]:
    source = _source_contract(_mapping(payload.get("source")))
    raw_items = _sequence(payload.get("items"))
    items = [
        item
        for item in (
            _normalize_item(raw_item, fallback_source=source, fallback_timezone=timezone_name)
            for raw_item in raw_items
        )
        if item is not None
    ]
    filtered_sample_count = len(raw_items) - len(items)
    evidence_ref = _safe_text(payload.get("evidenceRef") or payload.get("evidence_ref"))
    configured = _source_configured(source)
    requested_state = _normalize_requested_state(payload.get("state") or payload.get("readinessState"))
    failure_reason = _failure_reason(payload.get("failureReason") or payload.get("error") or payload.get("reason"))
    max_age_hours = _number(payload.get("maxAgeHours"), default=_DEFAULT_MAX_AGE_HOURS)

    readiness_state, freshness_state, stale_reason, no_item_reason = _derive_states(
        requested_state=requested_state,
        configured=configured,
        items=items,
        failure_reason=failure_reason,
        filtered_sample_count=filtered_sample_count,
        as_of=as_of,
        max_age_hours=max_age_hours,
    )

    return {
        "capabilityFamily": family,
        "readinessState": readiness_state,
        "freshnessState": freshness_state,
        "asOf": as_of.isoformat(),
        "timezone": timezone_name,
        "source": source,
        "sourceId": source["sourceId"],
        "sourceType": source["sourceType"],
        "sourceAuthority": source["authority"],
        "evidenceRef": evidence_ref or _first_item_evidence_ref(items),
        "itemCount": len(items),
        "items": items,
        "noItemState": {
            "isNoItems": readiness_state == "NO_ITEMS",
            "reason": no_item_reason,
        },
        "failureState": {
            "isFailed": readiness_state == "FETCH_FAILED",
            "reason": failure_reason if readiness_state == "FETCH_FAILED" else None,
        },
        "staleReason": stale_reason,
        "publicDisplay": {
            "consumerSafe": True,
            "rawProviderPayloadExposed": False,
            "sensitiveAuthMaterialExposed": False,
            "redactedProviderDiagnostics": True,
            "sampleItemsExposedAsCurrent": False,
            "displayBoundary": "readiness_and_evidence_only",
        },
    }


def _derive_states(
    *,
    requested_state: str | None,
    configured: bool,
    items: Sequence[Mapping[str, Any]],
    failure_reason: str | None,
    filtered_sample_count: int,
    as_of: datetime,
    max_age_hours: float,
) -> tuple[str, str, str | None, str | None]:
    if requested_state == "FETCH_FAILED" or failure_reason:
        return "FETCH_FAILED", "FETCH_FAILED", None, None
    if not configured:
        return "NOT_CONFIGURED", "NOT_CONFIGURED", None, None
    if not items:
        reason = "sample_items_filtered" if filtered_sample_count else "source_returned_no_items"
        return "NO_ITEMS", "NO_ITEMS", None, reason

    stale_reason = _stale_reason(items=items, as_of=as_of, max_age_hours=max_age_hours)
    if requested_state == "STALE" or stale_reason:
        return "STALE", "STALE", stale_reason or "source_marked_stale", None

    if requested_state == "PARTIAL" or any(item["limitations"] for item in items):
        return "PARTIAL", "PARTIAL", None, None

    if requested_state in {"NO_ITEMS", "NOT_CONFIGURED"}:
        return requested_state, requested_state, None, "source_returned_no_items" if requested_state == "NO_ITEMS" else None

    return "READY", "FRESH", None, None


def _normalize_item(
    raw_item: Any,
    *,
    fallback_source: Mapping[str, Any],
    fallback_timezone: str,
) -> dict[str, Any] | None:
    item = _mapping(raw_item)
    if not item or _is_sample_item(item):
        return None

    published_at = _normalize_datetime_or_none(item.get("publishedAt") or item.get("published_at"), fallback_timezone)
    event_timestamp = _normalize_datetime_or_none(
        item.get("eventTimestamp") or item.get("event_timestamp") or item.get("eventAt") or item.get("event_at"),
        fallback_timezone,
    )
    source_id = _safe_text(item.get("sourceId") or item.get("source_id") or fallback_source.get("sourceId")) or "unknown"
    source_type = _safe_text(item.get("sourceType") or item.get("source_type") or fallback_source.get("sourceType")) or "unknown"
    source_authority = (
        _safe_text(item.get("sourceAuthority") or item.get("source_authority") or fallback_source.get("authority"))
        or "unknown"
    )
    evidence_ref = _safe_text(item.get("evidenceRef") or item.get("evidence_ref"))
    limitations: list[str] = []
    if published_at is None:
        limitations.append("published_timestamp_missing")
    if event_timestamp is None:
        limitations.append("event_timestamp_missing")
    if not evidence_ref:
        limitations.append("evidence_reference_missing")

    return {
        "id": _safe_text(item.get("id")) or _safe_id(item.get("title") or item.get("summary")),
        "title": _safe_text(item.get("title") or item.get("headline")),
        "summary": _safe_text(item.get("summary") or item.get("description")),
        "publishedAt": published_at.isoformat() if published_at else None,
        "eventTimestamp": event_timestamp.isoformat() if event_timestamp else None,
        "timezone": _normalize_timezone(item.get("timezone") or fallback_timezone),
        "sourceId": source_id,
        "sourceType": source_type,
        "sourceAuthority": source_authority,
        "evidenceRef": evidence_ref,
        "limitations": limitations,
    }


def _source_contract(source: Mapping[str, Any]) -> dict[str, str]:
    return {
        "sourceId": _safe_text(source.get("sourceId") or source.get("source_id")) or "not_configured",
        "sourceType": _safe_text(source.get("sourceType") or source.get("source_type")) or "not_configured",
        "authority": _safe_text(source.get("authority") or source.get("sourceAuthority")) or "not_configured",
    }


def _source_configured(source: Mapping[str, Any]) -> bool:
    return all(str(source.get(key) or "") != "not_configured" for key in _SOURCE_REQUIRED_FIELDS)


def _normalize_requested_state(value: Any) -> str | None:
    text = _safe_text(value).lower().replace("-", "_").replace(" ", "_")
    if text in _FAILURE_ALIASES:
        return "FETCH_FAILED"
    if text in _NO_ITEM_ALIASES:
        return "NO_ITEMS"
    if text in _NOT_CONFIGURED_ALIASES:
        return "NOT_CONFIGURED" if text else None
    if text in _STALE_ALIASES:
        return "STALE"
    if text in _PARTIAL_ALIASES:
        return "PARTIAL"
    if text in _READY_ALIASES:
        return "READY"
    return None


def _failure_reason(value: Any) -> str | None:
    raw_text = str(value or "").strip()
    if not raw_text:
        return None
    lowered = raw_text.lower()
    for hint, reason in _FAILURE_REASON_HINTS:
        if hint in lowered:
            return reason
    if any(marker in lowered for marker in _SENSITIVE_REASON_HINTS):
        return "fetch_failed"
    text = _safe_text(raw_text)
    if not text:
        return "fetch_failed"
    return _safe_code(text) or "fetch_failed"


def _stale_reason(
    *,
    items: Sequence[Mapping[str, Any]],
    as_of: datetime,
    max_age_hours: float,
) -> str | None:
    for item in items:
        published_at = _parse_datetime(item.get("publishedAt"))
        if published_at is None:
            return "published_at_missing"
        if (as_of - published_at).total_seconds() > max_age_hours * 3600:
            return "published_at_exceeds_max_age"
    return None


def _normalize_datetime(value: Any, timezone_name: str) -> datetime:
    parsed = _parse_datetime(value)
    if parsed is not None:
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=ZoneInfo(timezone_name))
        return parsed
    return datetime.now(ZoneInfo(timezone_name)).replace(microsecond=0)


def _normalize_datetime_or_none(value: Any, timezone_name: str) -> datetime | None:
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=ZoneInfo(timezone_name))
    return parsed


def _parse_datetime(value: Any) -> datetime | None:
    text = _safe_text(value)
    if not text:
        return None
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(timezone.utc) if parsed.utcoffset() == timezone.utc.utcoffset(parsed) else parsed


def _normalize_timezone(value: Any) -> str:
    text = _safe_text(value) or "UTC"
    try:
        ZoneInfo(text)
    except ZoneInfoNotFoundError:
        return "UTC"
    return text


def _is_sample_item(item: Mapping[str, Any]) -> bool:
    if item.get("sample") is True or item.get("isSample") is True:
        return True
    evidence_ref = str(item.get("evidenceRef") or item.get("evidence_ref") or "").strip().lower()
    if evidence_ref.startswith(_SAMPLE_MARKERS):
        return True
    source_authority = str(item.get("sourceAuthority") or item.get("source_authority") or "").strip().lower()
    return source_authority in {"synthetic_fixture", "fallback_static", "sample", "scaffold"}


def _first_item_evidence_ref(items: Sequence[Mapping[str, Any]]) -> str | None:
    for item in items:
        value = _safe_text(item.get("evidenceRef"))
        if value:
            return value
    return None


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _safe_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if any(marker in lowered for marker in _SENSITIVE_REASON_HINTS):
        return ""
    return text[:240]


def _safe_code(value: Any) -> str:
    text = _safe_text(value).lower().replace("-", "_").replace(" ", "_")
    return "".join(char for char in text if char.isalnum() or char == "_")[:80]


def _safe_id(value: Any) -> str:
    text = _safe_code(value)
    return text or "item"


def _number(value: Any, *, default: float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


__all__ = [
    "FRESHNESS_STATES",
    "NEWS_CATALYST_CAPABILITY_FAMILIES",
    "NEWS_CATALYST_READ_CONTRACT_VERSION",
    "READINESS_STATES",
    "build_news_catalyst_read_contract_v1",
]
