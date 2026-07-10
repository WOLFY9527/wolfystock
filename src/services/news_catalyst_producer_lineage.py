# -*- coding: utf-8 -*-
"""Passive producer-owned lineage bundle for News/Catalyst search results."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any


NEWS_CATALYST_PRODUCER_LINEAGE_VERSION = (
    "news_catalyst_producer_lineage_bundle_v1"
)

_MISSING_PRODUCER_IDS = frozenset(
    {"", "filtered", "none", "not_configured", "unknown"}
)
_SAMPLE_MARKERS = ("demo", "fixture", "mock", "sample", "scaffold", "synthetic")


def build_news_catalyst_producer_lineage_bundle_v1(
    response: Any,
    *,
    capability_family: str,
) -> dict[str, Any]:
    """Build a bounded lineage bundle without provider calls or invented metadata."""

    source_id = _producer_source_id(_value(response, "provider"))
    source_type = _producer_source_type(source_id)
    authority = "non_authoritative" if source_id else None
    as_of = _optional_text(_value(response, "asOf", "as_of"))
    timezone_name = _optional_text(_value(response, "timezone"))
    limitations: list[str] = []

    if source_id is None:
        limitations.append("producer_source_missing")
    elif source_type == "sample":
        limitations.append("sample_producer_non_authoritative")
    else:
        limitations.append("search_proxy_non_authoritative")
    if as_of is None:
        limitations.append("as_of_missing")
    if timezone_name is None:
        limitations.append("timezone_missing")

    items = [
        _build_item(
            raw_item,
            capability_family=capability_family,
            producer_source_id=source_id,
            producer_source_type=source_type,
            bundle_as_of=as_of,
            bundle_timezone=timezone_name,
        )
        for raw_item in _sequence(_value(response, "results"))
    ]

    return {
        "contractVersion": NEWS_CATALYST_PRODUCER_LINEAGE_VERSION,
        "producerBoundary": "search_service_response",
        "capabilityFamily": _optional_text(capability_family),
        "sourceId": source_id,
        "sourceType": source_type,
        "authority": authority,
        "evidenceRef": None,
        "publishedAt": None,
        "eventTimestamp": None,
        "asOf": as_of,
        "timezone": timezone_name,
        "limitations": limitations,
        "itemCount": len(items),
        "items": items,
        "networkCallsEnabled": False,
        "runtimeProviderCalls": False,
    }


def _build_item(
    raw_item: Any,
    *,
    capability_family: str,
    producer_source_id: str | None,
    producer_source_type: str | None,
    bundle_as_of: str | None,
    bundle_timezone: str | None,
) -> dict[str, Any]:
    source_id = _optional_text(_value(raw_item, "source"))
    source_type = "publisher_reference" if source_id else None
    evidence_ref = _optional_text(_value(raw_item, "evidenceRef", "evidence_ref", "url"))
    published_at = _optional_text(
        _value(raw_item, "publishedAt", "published_at", "published_date")
    )
    event_timestamp = _optional_text(
        _value(raw_item, "eventTimestamp", "event_timestamp", "event_at")
    )
    as_of = _optional_text(_value(raw_item, "asOf", "as_of")) or bundle_as_of
    timezone_name = (
        _optional_text(_value(raw_item, "timezone"))
        or _timezone_from_timestamp(published_at)
        or bundle_timezone
    )
    limitations: list[str] = []

    if source_id is None:
        limitations.append("publisher_source_missing")
    limitations.append("publisher_authority_not_established")
    if evidence_ref is None:
        limitations.append("evidence_reference_missing")
    if published_at is None:
        limitations.append("published_at_missing")
    if event_timestamp is None:
        limitations.append("event_timestamp_missing")
    if as_of is None:
        limitations.append("as_of_missing")
    if timezone_name is None:
        limitations.append("timezone_missing")
    if producer_source_type == "sample":
        limitations.append("sample_producer_non_authoritative")
    elif producer_source_id:
        limitations.append("search_proxy_non_authoritative")

    return {
        "itemId": _item_id(
            producer_source_id=producer_source_id,
            source_id=source_id,
            evidence_ref=evidence_ref,
            title=_optional_text(_value(raw_item, "title", "headline")),
            published_at=published_at,
        ),
        "capabilityFamily": _optional_text(capability_family),
        "sourceId": source_id,
        "sourceType": source_type,
        "authority": None,
        "evidenceRef": evidence_ref,
        "publishedAt": published_at,
        "eventTimestamp": event_timestamp,
        "asOf": as_of,
        "timezone": timezone_name,
        "limitations": limitations,
    }


def _item_id(
    *,
    producer_source_id: str | None,
    source_id: str | None,
    evidence_ref: str | None,
    title: str | None,
    published_at: str | None,
) -> str:
    identity = "|".join(
        value or ""
        for value in (
            producer_source_id,
            source_id,
            evidence_ref,
            title,
            published_at,
        )
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
    return f"news_lineage_{digest}"


def _producer_source_id(value: Any) -> str | None:
    text = _optional_text(value)
    if text is None or text.lower() in _MISSING_PRODUCER_IDS:
        return None
    return text


def _producer_source_type(source_id: str | None) -> str | None:
    if source_id is None:
        return None
    lowered = source_id.lower()
    if any(marker in lowered for marker in _SAMPLE_MARKERS):
        return "sample"
    return "search_proxy"


def _timezone_from_timestamp(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        return None
    offset = parsed.utcoffset()
    if offset is None:
        return None
    total_minutes = int(offset.total_seconds() // 60)
    if total_minutes == 0:
        return "UTC"
    sign = "+" if total_minutes >= 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def _value(value: Any, *names: str) -> Any:
    if isinstance(value, Mapping):
        for name in names:
            if name in value:
                return value[name]
        return None
    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    return None


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return list(value)
    return []


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:1000] if text else None


__all__ = [
    "NEWS_CATALYST_PRODUCER_LINEAGE_VERSION",
    "build_news_catalyst_producer_lineage_bundle_v1",
]
