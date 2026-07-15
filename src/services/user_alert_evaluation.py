# -*- coding: utf-8 -*-
"""Pure dry-run evaluation helper for user watchlist price alerts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
from typing import Any, Dict, Optional

from src.services.user_alert_presentation import (
    build_user_alert_presentation_copy,
    coerce_user_alert_datetime,
    format_user_alert_price,
)


_ALERT_CLASS = "watchlist_price_threshold"
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
_BLOCKED_FRESHNESS = {"stale", "delayed", "partial", "fallback", "synthetic", "unavailable", "unknown"}


def evaluate_user_alert_dry_run(
    *,
    rule: Any,
    observed_price: Any,
    observed_at: Any,
    freshness: Any = None,
    suppression: Any = None,
    now: Any = None,
    dedupe_bucket_minutes: int = 60,
) -> Dict[str, Any]:
    """Evaluate caller-provided alert data without outbound side effects."""
    try:
        current_time = coerce_user_alert_datetime(now) or datetime.now(timezone.utc)
        normalized_rule = _normalize_rule(rule)
        normalized_freshness = _as_dict(freshness)
        normalized_suppression = _as_dict(suppression)
        normalized_price = _normalize_price(observed_price, allow_none=True)
        normalized_observed_at = coerce_user_alert_datetime(observed_at)

        state = _classify_data_state(
            observed_price=normalized_price,
            observed_at=normalized_observed_at,
            freshness=normalized_freshness,
            now=current_time,
        )
        condition_observed = False
        suppressed = False

        if state == "condition_not_observed":
            condition_observed = _condition_met(
                direction=normalized_rule["direction"],
                threshold_price=normalized_rule["threshold_price"],
                observed_price=normalized_price,
            )
            state = "condition_observed" if condition_observed else "condition_not_observed"
            if condition_observed:
                suppression_state = _suppression_state(normalized_suppression, current_time)
                if suppression_state is not None:
                    state = suppression_state
                    suppressed = True

        title, message = build_user_alert_presentation_copy(
            state=state,
            subject=normalized_rule["subject"],
            threshold_price=normalized_rule["threshold_price"],
            observed_price=normalized_price,
        )
        bucket_label = _time_bucket_label(
            normalized_observed_at or current_time,
            bucket_minutes=max(1, int(dedupe_bucket_minutes or 60)),
        )

        return _result_payload(
            state=state,
            rule_type=normalized_rule["rule_type"],
            subject=normalized_rule["subject"],
            direction=normalized_rule["direction"],
            threshold_price=normalized_rule["threshold_price"],
            observed_price=normalized_price,
            observed_at=normalized_observed_at,
            freshness_status=_normalize_text(
                _read_value(normalized_freshness, "status", "freshnessStatus", "freshness_status")
            ),
            title=title,
            message=message,
            condition_observed=condition_observed,
            suppressed=suppressed,
            dedupe_fingerprint=_build_dedupe_fingerprint(
                rule_type=normalized_rule["rule_type"],
                subject=normalized_rule["subject"],
                condition=(
                    f'{normalized_rule["direction"]}@'
                    f'{format_user_alert_price(normalized_rule["threshold_price"])}'
                ),
                safe_state=state,
                time_bucket=bucket_label,
            ),
        )
    except Exception:
        subject = _safe_subject(rule)
        title, message = build_user_alert_presentation_copy(
            state="error",
            subject=subject,
            threshold_price=None,
            observed_price=None,
        )
        return _result_payload(
            state="error",
            rule_type=_ALERT_CLASS,
            subject=subject,
            direction=None,
            threshold_price=None,
            observed_price=None,
            observed_at=coerce_user_alert_datetime(observed_at),
            freshness_status=None,
            title=title,
            message=message,
            condition_observed=False,
            suppressed=False,
            dedupe_fingerprint=_build_dedupe_fingerprint(
                rule_type=_ALERT_CLASS,
                subject=subject,
                condition="invalid-rule",
                safe_state="error",
                time_bucket=_time_bucket_label(
                    coerce_user_alert_datetime(now) or datetime.now(timezone.utc),
                    bucket_minutes=60,
                ),
            ),
        )


def _normalize_rule(rule: Any) -> Dict[str, Any]:
    payload = _as_dict(rule)
    symbol = _normalize_subject(_read_value(payload, "symbol", "subject"))
    direction = _normalize_direction(_read_value(payload, "direction"))
    threshold_price = _normalize_price(_read_value(payload, "threshold_price", "thresholdPrice"))
    rule_type = _normalize_text(_read_value(payload, "rule_type", "ruleType")) or _ALERT_CLASS
    if rule_type != _ALERT_CLASS:
        raise ValueError("unsupported rule_type")
    return {
        "rule_type": rule_type,
        "subject": symbol,
        "direction": direction,
        "threshold_price": threshold_price,
    }


def _classify_data_state(
    *,
    observed_price: Optional[Decimal],
    observed_at: Optional[datetime],
    freshness: Dict[str, Any],
    now: datetime,
) -> str:
    if observed_price is None or observed_at is None:
        return "blocked_insufficient_data"
    freshness_status = _normalize_text(
        _read_value(freshness, "status", "freshnessStatus", "freshness_status", "freshness")
    )
    if freshness_status in _BLOCKED_FRESHNESS:
        return "blocked_insufficient_data"
    max_age_minutes = _normalize_int(
        _read_value(freshness, "maxAgeMinutes", "max_age_minutes", "maxAge", "max_age"),
        allow_none=True,
    )
    if max_age_minutes is not None and observed_at < now - timedelta(minutes=max_age_minutes):
        return "blocked_insufficient_data"
    return "condition_not_observed"


def _condition_met(*, direction: str, threshold_price: Decimal, observed_price: Decimal) -> bool:
    if direction == "above":
        return observed_price >= threshold_price
    return observed_price <= threshold_price


def _suppression_state(suppression: Dict[str, Any], now: datetime) -> Optional[str]:
    if _coerce_bool(_read_value(suppression, "muted", "isMuted", "is_muted")):
        return "suppressed_muted"
    snoozed_until = coerce_user_alert_datetime(_read_value(suppression, "snoozedUntil", "snoozed_until"))
    if snoozed_until is not None and snoozed_until > now:
        return "suppressed_snoozed"
    if _coerce_bool(_read_value(suppression, "cooldownActive", "cooldown_active")):
        return "suppressed_cooldown"
    if _coerce_bool(_read_value(suppression, "duplicateActive", "duplicate_active")):
        return "suppressed_duplicate"
    return None


def _result_payload(
    *,
    state: str,
    rule_type: str,
    subject: str,
    direction: Optional[str],
    threshold_price: Optional[Decimal],
    observed_price: Optional[Decimal],
    observed_at: Optional[datetime],
    freshness_status: Optional[str],
    title: str,
    message: str,
    condition_observed: bool,
    suppressed: bool,
    dedupe_fingerprint: str,
) -> Dict[str, Any]:
    if state not in _ALLOWED_STATES:
        raise ValueError("state must remain bounded")
    return {
        "state": state,
        "dryRun": True,
        "outboundAttempted": False,
        "liveOutbound": False,
        "providerRuntimeCalled": False,
        "networkCallsEnabled": False,
        "marketCacheMutation": False,
        "observationOnly": True,
        "conditionObserved": bool(condition_observed),
        "suppressed": bool(suppressed),
        "ruleType": rule_type,
        "subject": subject,
        "direction": direction,
        "thresholdPrice": _float_or_none(threshold_price),
        "observedPrice": _float_or_none(observed_price),
        "observedAt": observed_at.isoformat().replace("+00:00", "Z") if observed_at else None,
        "freshnessStatus": freshness_status,
        "title": title,
        "message": message,
        "dedupeFingerprint": dedupe_fingerprint,
    }


def _build_dedupe_fingerprint(
    *,
    rule_type: str,
    subject: str,
    condition: str,
    safe_state: str,
    time_bucket: str,
) -> str:
    material = "|".join((rule_type, subject, condition, safe_state, time_bucket))
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
    return f"user-alert-dry-run:{digest}"


def _time_bucket_label(value: datetime, *, bucket_minutes: int) -> str:
    bucket_seconds = max(1, bucket_minutes) * 60
    timestamp = int(value.timestamp())
    bucket_start = timestamp - (timestamp % bucket_seconds)
    return datetime.fromtimestamp(bucket_start, tz=timezone.utc).strftime("%Y%m%d%H%M")


def _as_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {}


def _read_value(source: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in source:
            return source[key]
    return None


def _normalize_subject(value: Any) -> str:
    text = _normalize_text(value)
    if not text:
        raise ValueError("symbol is required")
    return text.upper()


def _normalize_direction(value: Any) -> str:
    text = _normalize_text(value)
    if text not in {"above", "below"}:
        raise ValueError("direction must be above or below")
    return text


def _normalize_price(value: Any, *, allow_none: bool = False) -> Optional[Decimal]:
    if value is None:
        if allow_none:
            return None
        raise ValueError("price is required")
    try:
        normalized = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("price must be numeric") from exc
    if not normalized.is_finite() or normalized <= 0:
        raise ValueError("price must be greater than 0")
    return normalized


def _normalize_int(value: Any, *, allow_none: bool = False) -> Optional[int]:
    if value is None:
        if allow_none:
            return None
        raise ValueError("integer value is required")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("integer value is invalid") from exc


def _normalize_text(value: Any) -> Optional[str]:
    text = str(value).strip().lower() if value is not None else ""
    return text or None


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "on"}


def _float_or_none(value: Optional[Decimal]) -> Optional[float]:
    return float(value) if value is not None else None


def _safe_subject(rule: Any) -> str:
    payload = _as_dict(rule)
    subject = _read_value(payload, "symbol", "subject")
    if subject is None:
        return "该标的"
    text = str(subject).strip().upper()
    return text or "该标的"


__all__ = ["evaluate_user_alert_dry_run"]
