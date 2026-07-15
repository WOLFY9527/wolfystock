# -*- coding: utf-8 -*-
"""Pure helper that projects user alert dry-run results into local event packets."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping

from src.services.user_alert_presentation import (
    build_user_alert_presentation_copy,
    coerce_user_alert_datetime,
)


PACKET_KIND = "user_alert_event_packet"
PACKET_VERSION = "user_alert_event_packet_v1"
EVENT_TYPE = "user.alert_dry_run_evaluation"
_DEFAULT_SUBJECT = "该标的"
_ALLOWED_STATES = {
    "condition_observed",
    "condition_not_observed",
    "blocked_insufficient_data",
    "suppressed_cooldown",
    "suppressed_duplicate",
    "suppressed_muted",
    "suppressed_snoozed",
    "error",
}


def build_user_alert_event_packet(
    *,
    result: Mapping[str, Any] | Any,
    now: Any = None,
) -> dict[str, Any]:
    """Project a caller-supplied dry-run evaluation into a local-only event packet."""
    payload = _mapping(result)
    created_at = coerce_user_alert_datetime(now) or datetime.now(timezone.utc)
    state = _state(payload.get("state"))
    subject = _subject(payload.get("subject"))
    rule_type = _text(payload.get("ruleType")) or "watchlist_price_threshold"
    direction = _text(payload.get("direction"))
    threshold_price = _number(payload.get("thresholdPrice"))
    observed_price = _number(payload.get("observedPrice"))
    observed_as_of = coerce_user_alert_datetime(payload.get("observedAt")) or created_at
    freshness_status = _text(payload.get("freshnessStatus"))
    condition_observed = _bool(payload.get("conditionObserved"))
    suppressed = _bool(payload.get("suppressed"))
    dedupe_fingerprint = _text(payload.get("dedupeFingerprint")) or "user-alert-dry-run:missing"

    title, message = build_user_alert_presentation_copy(
        state=state,
        subject=subject,
        threshold_price=threshold_price,
        observed_price=observed_price,
    )
    safe_metadata = {
        "ruleType": rule_type,
        "subject": subject,
        "direction": direction,
        "thresholdPrice": threshold_price,
        "observedPrice": observed_price,
        "freshnessStatus": freshness_status,
        "conditionObserved": condition_observed,
        "suppressed": suppressed,
        "dedupeFingerprint": dedupe_fingerprint,
    }

    return {
        "packetKind": PACKET_KIND,
        "packetVersion": PACKET_VERSION,
        "eventType": EVENT_TYPE,
        "state": state,
        "title": title,
        "message": message,
        "fingerprint": _build_fingerprint(
            state=state,
            rule_type=rule_type,
            subject=subject,
            direction=direction,
            observed_as_of=observed_as_of,
            condition_observed=condition_observed,
            suppressed=suppressed,
            dedupe_fingerprint=dedupe_fingerprint,
        ),
        "observedAsOf": _isoformat(observed_as_of),
        "createdAt": _isoformat(created_at),
        "dryRun": True,
        "outboundAttempted": False,
        "liveOutbound": False,
        "localOnly": True,
        "safeMetadata": safe_metadata,
    }


def _build_fingerprint(
    *,
    state: str,
    rule_type: str,
    subject: str,
    direction: str | None,
    observed_as_of: datetime,
    condition_observed: bool,
    suppressed: bool,
    dedupe_fingerprint: str,
) -> str:
    safe_material = {
        "eventType": EVENT_TYPE,
        "state": state,
        "ruleType": rule_type,
        "subject": subject,
        "direction": direction,
        "observedAsOf": _isoformat(observed_as_of),
        "conditionObserved": condition_observed,
        "suppressed": suppressed,
        "dedupeFingerprint": dedupe_fingerprint,
    }
    digest = hashlib.sha256(_canonical_json(safe_material).encode("utf-8")).hexdigest()[:24]
    return f"user-alert-event:{digest}"


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _mapping(value: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, Mapping):
        return dict(value.items())
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {}


def _state(value: Any) -> str:
    text = _text(value)
    return text if text in _ALLOWED_STATES else "error"


def _subject(value: Any) -> str:
    text = str(value or "").strip().upper()
    return text or _DEFAULT_SUBJECT


def _text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = ["build_user_alert_event_packet"]
