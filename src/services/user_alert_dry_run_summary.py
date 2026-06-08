# -*- coding: utf-8 -*-
"""Pure local review summary helper for user alert dry-run results."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Optional


_TRUE_TEXT = frozenset({"1", "true", "yes", "y", "on"})
_FALSE_TEXT = frozenset({"0", "false", "no", "n", "off"})

_TEXT_FIELDS = (
    "status",
    "state",
    "deliveryStatus",
    "safeStatus",
    "result",
    "classification",
    "outcome",
)
_ERROR_MARKERS = frozenset({"error", "failed", "failure", "exception"})
_INSUFFICIENT_MARKERS = frozenset(
    {"insufficient", "no data", "missing data", "data missing", "unavailable"}
)
_SUPPRESSED_MARKERS = frozenset(
    {"suppressed", "advisory only", "quiet", "no alert", "paused"}
)
_OBSERVED_MARKERS = frozenset(
    {"observed", "triggered", "dry run intent", "would notify", "would alert", "would emit"}
)


def _coerce_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_TEXT:
            return True
        if normalized in _FALSE_TEXT:
            return False
        if not normalized:
            return None
    return bool(value)


def _first_bool(result: Mapping[str, Any], *keys: str) -> Optional[bool]:
    for key in keys:
        if key in result:
            return _coerce_bool(result.get(key))
    return None


def _normalized_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower().replace("_", " ").replace("-", " ")


def _status_text(result: Mapping[str, Any]) -> str:
    return " ".join(
        text
        for text in (_normalized_text(result.get(field)) for field in _TEXT_FIELDS)
        if text
    )


def _has_marker(text: str, markers: frozenset[str]) -> bool:
    return any(marker in text for marker in markers)


def _has_send_boundary_issue(result: Mapping[str, Any]) -> bool:
    return any(
        flag is True
        for flag in (
            _first_bool(result, "outboundAttempted", "outbound_attempted"),
            _first_bool(result, "liveOutbound", "live_outbound"),
        )
    ) or any(
        flag is False
        for flag in (
            _first_bool(result, "dryRun", "dry_run"),
            _first_bool(result, "noSend", "no_send"),
        )
    )


def _classify_result(result: Mapping[str, Any]) -> str:
    if _has_send_boundary_issue(result):
        return "error"

    text = _status_text(result)
    if _first_bool(result, "error") is True or _has_marker(text, _ERROR_MARKERS):
        return "error"
    if _first_bool(result, "insufficientData", "insufficient_data") is True or _has_marker(
        text,
        _INSUFFICIENT_MARKERS,
    ):
        return "insufficient"
    if (
        _first_bool(result, "suppressed") is True
        or _first_bool(result, "alertDeliveryIntent", "alert_delivery_intent") is False
        or _has_marker(text, _SUPPRESSED_MARKERS)
    ):
        return "suppressed"
    if (
        _first_bool(
            result,
            "observed",
            "alertDeliveryIntent",
            "wouldNotify",
            "wouldSend",
            "wouldEmit",
            "wouldAlert",
        )
        is True
        or _has_marker(text, _OBSERVED_MARKERS)
    ):
        return "observed"
    return "suppressed"


def _safe_status(
    *,
    total_count: int,
    error_count: int,
    insufficient_data_count: int,
    send_boundary_issue: bool,
) -> str:
    if send_boundary_issue:
        return "PAUSED"
    if total_count == 0:
        return "INSUFFICIENT"
    if error_count == total_count:
        return "UNAVAILABLE"
    if insufficient_data_count == total_count:
        return "INSUFFICIENT"
    if error_count or insufficient_data_count:
        return "PARTIAL"
    return "AVAILABLE"


def _item_label(count: int) -> str:
    return "item" if count == 1 else "items"


def _consumer_summary(
    *,
    total_count: int,
    observed_count: int,
    suppressed_count: int,
    insufficient_data_count: int,
    error_count: int,
    send_boundary_issue: bool,
) -> str:
    if send_boundary_issue:
        return (
            "Alert review paused because a send boundary flag was raised. "
            "Treat this as local review only."
        )
    return (
        f"Alert review checked {total_count} {_item_label(total_count)}: "
        f"{observed_count} observed, {suppressed_count} quiet, "
        f"{insufficient_data_count} limited by data, {error_count} needs review. "
        "No messages were sent."
    )


def _admin_summary(
    *,
    total_count: int,
    observed_count: int,
    suppressed_count: int,
    insufficient_data_count: int,
    error_count: int,
    send_boundary_issue: bool,
) -> str:
    prefix = "Local alert review failed closed" if send_boundary_issue else "Local alert review"
    suffix = "Send boundary flag detected." if send_boundary_issue else "Send boundary clear."
    return (
        f"{prefix}: total {total_count}, observed {observed_count}, "
        f"suppressed {suppressed_count}, "
        f"insufficient data {insufficient_data_count}, errors {error_count}. {suffix}"
    )


def summarize_user_alert_dry_run_results(results: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize caller-provided alert dry-run results without side effects."""
    items = list(results)
    total_count = len(items)

    counts = {
        "observed": 0,
        "suppressed": 0,
        "insufficient": 0,
        "error": 0,
    }
    for item in items:
        counts[_classify_result(item)] += 1

    outbound_attempted = any(
        _first_bool(item, "outboundAttempted", "outbound_attempted") is True for item in items
    )
    live_outbound = any(
        _first_bool(item, "liveOutbound", "live_outbound") is True for item in items
    )
    dry_run = all(_first_bool(item, "dryRun", "dry_run") is not False for item in items)
    no_send = (
        not outbound_attempted
        and not live_outbound
        and all(_first_bool(item, "noSend", "no_send") is not False for item in items)
        and dry_run
    )
    send_boundary_issue = not no_send

    observed_count = counts["observed"]
    suppressed_count = counts["suppressed"]
    insufficient_data_count = counts["insufficient"]
    error_count = counts["error"]

    return {
        "totalCount": total_count,
        "observedCount": observed_count,
        "suppressedCount": suppressed_count,
        "insufficientDataCount": insufficient_data_count,
        "errorCount": error_count,
        "safeStatus": _safe_status(
            total_count=total_count,
            error_count=error_count,
            insufficient_data_count=insufficient_data_count,
            send_boundary_issue=send_boundary_issue,
        ),
        "noSendReview": {
            "dryRun": dry_run,
            "noSend": no_send,
            "outboundAttempted": outbound_attempted,
            "liveOutbound": live_outbound,
        },
        "consumerSummary": _consumer_summary(
            total_count=total_count,
            observed_count=observed_count,
            suppressed_count=suppressed_count,
            insufficient_data_count=insufficient_data_count,
            error_count=error_count,
            send_boundary_issue=send_boundary_issue,
        ),
        "adminSummary": _admin_summary(
            total_count=total_count,
            observed_count=observed_count,
            suppressed_count=suppressed_count,
            insufficient_data_count=insufficient_data_count,
            error_count=error_count,
            send_boundary_issue=send_boundary_issue,
        ),
    }


__all__ = ["summarize_user_alert_dry_run_results"]
