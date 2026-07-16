# -*- coding: utf-8 -*-
"""Pure authority helpers for Market observation and effective time."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Iterable, Mapping, NamedTuple, Sequence


PROVIDER_TIMESTAMP = "provider_timestamp"
PROVIDER_EFFECTIVE_DATE = "provider_effective_date"
MISSING = "missing"


class MarketObservationTime(NamedTuple):
    observed_at: str | None
    source: str


def extract_authoritative_market_time(
    payload: Mapping[str, Any] | None,
    *,
    provider_timestamp_fields: Sequence[str] = (
        "observedAt",
        "observed_at",
        "providerTimestamp",
        "provider_timestamp",
        "asOf",
        "as_of",
    ),
    provider_effective_date_fields: Sequence[str] = (
        "observationDate",
        "observation_date",
        "officialObservationDate",
        "officialAsOf",
        "effectiveDate",
        "effective_date",
    ),
) -> MarketObservationTime:
    """Return only explicitly permitted provider-owned market time."""
    if not isinstance(payload, Mapping):
        return MarketObservationTime(None, MISSING)
    source = str(payload.get("source") or "").strip().lower()
    if (
        payload.get("providerTimestampAvailable") is False
        or payload.get("isFallback")
        or payload.get("fallbackUsed")
        or payload.get("isUnavailable")
        or source in {"fallback", "mock", "synthetic", "unavailable", "missing"}
    ):
        return MarketObservationTime(None, MISSING)
    for field in provider_timestamp_fields:
        normalized = normalize_authoritative_market_time(payload.get(field))
        if normalized is not None:
            return MarketObservationTime(normalized, PROVIDER_TIMESTAMP)
    for field in provider_effective_date_fields:
        normalized = normalize_authoritative_market_time(payload.get(field))
        if normalized is not None:
            return MarketObservationTime(normalized, PROVIDER_EFFECTIVE_DATE)
    return MarketObservationTime(None, MISSING)


def normalize_authoritative_market_time(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()
    if not text:
        return None
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            date.fromisoformat(text)
        except ValueError:
            return None
    return text


def provider_epoch_to_iso(value: Any, *, milliseconds: bool) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return None
    if milliseconds:
        timestamp /= 1000.0
    try:
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def authoritative_market_watermark(
    payloads: Iterable[Mapping[str, Any]],
) -> MarketObservationTime:
    """Return the oldest authoritative time among eligible inputs."""
    candidates: list[tuple[datetime, MarketObservationTime]] = []
    for payload in payloads:
        if _excluded_input(payload):
            continue
        observation = extract_authoritative_market_time(payload)
        if observation.observed_at is None:
            continue
        parsed = _comparable_datetime(observation.observed_at)
        if parsed is not None:
            candidates.append((parsed, observation))
    if not candidates:
        return MarketObservationTime(None, MISSING)
    return min(candidates, key=lambda item: item[0])[1]


def _excluded_input(payload: Mapping[str, Any]) -> bool:
    source = str(payload.get("source") or "").strip().lower()
    freshness = str(payload.get("freshness") or "").strip().lower()
    return bool(
        payload.get("isFallback")
        or payload.get("fallbackUsed")
        or payload.get("isUnavailable")
        or source in {"fallback", "mock", "synthetic", "unavailable", "missing"}
        or freshness in {"fallback", "mock", "synthetic", "unavailable", "error"}
    )


def _comparable_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed_date = date.fromisoformat(value)
        except ValueError:
            return None
        parsed = datetime.combine(parsed_date, datetime.min.time(), tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
