# -*- coding: utf-8 -*-
"""Pure suppression policy helper for user alert delivery decisions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional


_ALLOWED_STATES = {
    "allowed",
    "suppressed_muted",
    "suppressed_snoozed",
    "suppressed_cooldown",
    "suppressed_duplicate",
    "invalid_policy",
}


def evaluate_user_alert_suppression_policy(
    *,
    now: Any = None,
    muted: Any = False,
    snoozed_until: Any = None,
    cooldown_started_at: Any = None,
    cooldown_seconds: Any = None,
    current_fingerprint: Any = None,
    current_time_bucket: Any = None,
    previous_fingerprint: Any = None,
    previous_time_bucket: Any = None,
) -> dict[str, Any]:
    """Evaluate a caller-provided suppression policy without side effects."""
    try:
        current_time = _coerce_datetime(now)
        if current_time is None:
            raise ValueError("now is required")

        duplicate_policy_present = any(
            value is not None
            for value in (
                current_fingerprint,
                current_time_bucket,
                previous_fingerprint,
                previous_time_bucket,
            )
        )
        current_fp = _normalize_token(current_fingerprint, allow_none=True)
        current_bucket = _normalize_token(current_time_bucket, allow_none=True)
        previous_fp = _normalize_token(previous_fingerprint, allow_none=True)
        previous_bucket = _normalize_token(previous_time_bucket, allow_none=True)
        if duplicate_policy_present and not all((current_fp, current_bucket, previous_fp, previous_bucket)):
            raise ValueError("duplicate policy must be complete")

        cooldown_policy_present = cooldown_started_at is not None or cooldown_seconds is not None
        cooldown_started = _coerce_datetime(cooldown_started_at)
        cooldown_window = _normalize_positive_int(cooldown_seconds, allow_none=True)
        if cooldown_policy_present and (cooldown_started is None or cooldown_window is None):
            raise ValueError("cooldown policy must be complete")

        if _coerce_bool(muted):
            return _result_payload("suppressed_muted")

        snooze_until = _coerce_datetime(snoozed_until)
        if snooze_until is not None and snooze_until > current_time:
            return _result_payload("suppressed_snoozed")

        if cooldown_started is not None and cooldown_window is not None:
            cooldown_expires_at = cooldown_started + timedelta(seconds=cooldown_window)
            if cooldown_expires_at > current_time:
                return _result_payload("suppressed_cooldown")

        if (
            current_fp is not None
            and current_bucket is not None
            and previous_fp is not None
            and previous_bucket is not None
            and current_fp == previous_fp
            and current_bucket == previous_bucket
        ):
            return _result_payload("suppressed_duplicate")

        return _result_payload("allowed")
    except Exception:
        return _result_payload("invalid_policy")


def _result_payload(state: str) -> dict[str, Any]:
    if state not in _ALLOWED_STATES:
        raise ValueError("state must remain bounded")
    return {
        "state": state,
        "allowed": state == "allowed",
        "suppressed": state.startswith("suppressed_"),
    }


def _coerce_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_positive_int(value: Any, *, allow_none: bool = False) -> Optional[int]:
    if value is None:
        if allow_none:
            return None
        raise ValueError("integer value is required")
    normalized = int(value)
    if normalized <= 0:
        raise ValueError("integer value must be greater than 0")
    return normalized


def _normalize_token(value: Any, *, allow_none: bool = False) -> Optional[str]:
    if value is None:
        if allow_none:
            return None
        raise ValueError("token is required")
    text = str(value).strip()
    if not text:
        raise ValueError("token must not be blank")
    return text


__all__ = ["evaluate_user_alert_suppression_policy"]
