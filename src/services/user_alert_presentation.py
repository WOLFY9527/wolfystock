# -*- coding: utf-8 -*-
"""Pure presentation and time normalization helpers for user alerts."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


_STATIC_COPY = {
    "suppressed_cooldown": ("提醒已暂缓", "本次条件已观察到，但仍在提醒间隔内。结果仅用于站内 dry-run 检查。"),
    "suppressed_duplicate": ("重复提醒已折叠", "本次条件已观察到，但与最近一次结果重复。结果仅用于站内 dry-run 检查。"),
    "suppressed_muted": ("提醒已静默", "本次条件已观察到，但该提醒当前处于静默状态。结果仅用于站内 dry-run 检查。"),
    "suppressed_snoozed": ("提醒稍后再看", "本次条件已观察到，但该提醒仍在稍后再看期间。结果仅用于站内 dry-run 检查。"),
    "blocked_insufficient_data": ("数据不足", "最近一次可用价格信息不足，此次不做提醒判断，也不会假定为最新数据。"),
}
_ERROR_COPY = ("无法完成提醒检查", "当前无法完成提醒检查，请稍后再试。")


def build_user_alert_presentation_copy(
    *,
    state: str,
    subject: str,
    threshold_price: Decimal | float | None,
    observed_price: Decimal | float | None,
) -> tuple[str, str]:
    """Build bounded consumer-facing copy from sanitized alert fields."""
    threshold_text = format_user_alert_price(threshold_price)
    observed_text = format_user_alert_price(observed_price)
    if state == "condition_observed":
        return (
            f"{subject} 价格提醒已记录",
            f"价格已达到你设定的关注条件（阈值 {threshold_text}，观察值 {observed_text}）。仅供观察，不会发送外部通知。",
        )
    if state == "condition_not_observed":
        return (
            f"{subject} 尚未触发提醒",
            f"价格暂未达到你设定的关注条件（阈值 {threshold_text}，观察值 {observed_text}）。",
        )
    title_suffix, message = _STATIC_COPY.get(state, _ERROR_COPY)
    return f"{subject} {title_suffix}", message


def coerce_user_alert_datetime(value: Any) -> datetime | None:
    """Coerce user-alert timestamps while preserving existing timezone behavior."""
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


def format_user_alert_price(value: Decimal | float | None) -> str:
    """Preserve the evaluation Decimal and event-packet float formatting."""
    if value is None:
        return "--"
    if isinstance(value, Decimal):
        text = format(value.normalize(), "f")
        return text.rstrip("0").rstrip(".") if "." in text else text
    return format(value, "g")


__all__ = ["build_user_alert_presentation_copy", "coerce_user_alert_datetime", "format_user_alert_price"]
