# -*- coding: utf-8 -*-
"""Pure composition helper for local-only user alert dry-run results."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.services.user_alert_evaluation import evaluate_user_alert_dry_run
from src.services.user_alert_event_packet import build_user_alert_event_packet
from src.services.user_alert_suppression_policy import evaluate_user_alert_suppression_policy


def build_user_alert_dry_run_pipeline_result(
    *,
    rule: Any,
    observed_price: Any,
    observed_at: Any,
    freshness: Any = None,
    suppression: Any = None,
    now: Any = None,
    recorded_at: Any = None,
    dedupe_bucket_minutes: int = 60,
    include_suppressed_local_record: bool = False,
) -> dict[str, Any]:
    """Compose evaluation, suppression, and optional local packet without side effects."""
    current_time = _coerce_datetime(now) or datetime.now(timezone.utc)
    packet_time = _coerce_datetime(recorded_at) or current_time
    base_evaluation = evaluate_user_alert_dry_run(
        rule=rule,
        observed_price=observed_price,
        observed_at=observed_at,
        freshness=freshness,
        now=current_time,
        dedupe_bucket_minutes=dedupe_bucket_minutes,
    )

    suppression_result = _build_suppression_result(
        evaluation=base_evaluation,
        suppression=suppression,
        now=current_time,
        dedupe_bucket_minutes=dedupe_bucket_minutes,
    )
    final_evaluation = _finalize_evaluation(
        base_evaluation=base_evaluation,
        rule=rule,
        observed_price=observed_price,
        observed_at=observed_at,
        freshness=freshness,
        now=current_time,
        dedupe_bucket_minutes=dedupe_bucket_minutes,
        suppression_state=suppression_result["state"],
    )

    should_emit_packet = _should_emit_packet(
        evaluation=final_evaluation,
        suppression=suppression_result,
        include_suppressed_local_record=include_suppressed_local_record,
    )
    event_packet = (
        build_user_alert_event_packet(result=final_evaluation, now=packet_time)
        if should_emit_packet
        else None
    )

    return {
        "dryRun": True,
        "noSend": True,
        "outboundAttempted": False,
        "liveOutbound": False,
        "localOnly": True,
        "suppressedLocalRecord": bool(final_evaluation["suppressed"] and event_packet is not None),
        "evaluation": final_evaluation,
        "suppression": suppression_result,
        "eventPacket": event_packet,
    }


def _build_suppression_result(
    *,
    evaluation: dict[str, Any],
    suppression: Any,
    now: datetime,
    dedupe_bucket_minutes: int,
) -> dict[str, Any]:
    if not evaluation.get("conditionObserved"):
        return {
            "state": "not_applicable",
            "evaluated": False,
            "allowed": False,
            "suppressed": False,
        }

    payload = _as_dict(suppression)
    result = evaluate_user_alert_suppression_policy(
        now=now,
        muted=_read_value(payload, "muted", "isMuted", "is_muted"),
        snoozed_until=_read_value(payload, "snoozedUntil", "snoozed_until"),
        cooldown_started_at=_read_value(payload, "cooldownStartedAt", "cooldown_started_at"),
        cooldown_seconds=_read_value(payload, "cooldownSeconds", "cooldown_seconds"),
        current_fingerprint=evaluation.get("dedupeFingerprint"),
        current_time_bucket=_time_bucket_label(
            _coerce_datetime(evaluation.get("observedAt")) or now,
            bucket_minutes=dedupe_bucket_minutes,
        ),
        previous_fingerprint=_read_value(payload, "previousFingerprint", "previous_fingerprint"),
        previous_time_bucket=_read_value(payload, "previousTimeBucket", "previous_time_bucket"),
    )
    return {
        "state": result["state"],
        "evaluated": True,
        "allowed": bool(result["allowed"]),
        "suppressed": bool(result["suppressed"]),
    }


def _finalize_evaluation(
    *,
    base_evaluation: dict[str, Any],
    rule: Any,
    observed_price: Any,
    observed_at: Any,
    freshness: Any,
    now: datetime,
    dedupe_bucket_minutes: int,
    suppression_state: str,
) -> dict[str, Any]:
    if not suppression_state.startswith("suppressed_"):
        return dict(base_evaluation)

    suppression_projection = _suppression_projection(suppression_state)
    return evaluate_user_alert_dry_run(
        rule=rule,
        observed_price=observed_price,
        observed_at=observed_at,
        freshness=freshness,
        suppression=suppression_projection,
        now=now,
        dedupe_bucket_minutes=dedupe_bucket_minutes,
    )


def _should_emit_packet(
    *,
    evaluation: dict[str, Any],
    suppression: dict[str, Any],
    include_suppressed_local_record: bool,
) -> bool:
    if suppression["state"] == "invalid_policy":
        return False
    if evaluation["suppressed"] and not include_suppressed_local_record:
        return False
    return True


def _suppression_projection(state: str) -> dict[str, Any]:
    if state == "suppressed_muted":
        return {"muted": True}
    if state == "suppressed_snoozed":
        return {"snoozedUntil": "9999-12-31T23:59:59Z"}
    if state == "suppressed_cooldown":
        return {"cooldownActive": True}
    if state == "suppressed_duplicate":
        return {"duplicateActive": True}
    return {}


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {}


def _read_value(source: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in source:
            return source[key]
    return None


def _coerce_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _time_bucket_label(value: datetime, *, bucket_minutes: int) -> str:
    bucket_seconds = max(1, int(bucket_minutes or 60)) * 60
    timestamp = int(value.timestamp())
    bucket_start = timestamp - (timestamp % bucket_seconds)
    return datetime.fromtimestamp(bucket_start, tz=timezone.utc).strftime("%Y%m%d%H%M")


__all__ = ["build_user_alert_dry_run_pipeline_result"]
