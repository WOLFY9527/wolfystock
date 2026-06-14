# -*- coding: utf-8 -*-
"""Consumer-safe market data quality labels."""

from __future__ import annotations

from typing import Any, Mapping


DATA_QUALITY_LABELS = {
    "ready": "正常",
    "delayed": "数据延迟",
    "cached": "使用缓存数据",
    "partial": "部分数据缺失",
    "no_evidence": "暂无证据",
    "unavailable": "暂不可用",
}


def build_consumer_data_quality_state(value: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(value or {})
    freshness = str(payload.get("freshness") or payload.get("status") or "").strip().lower()
    state = _consumer_data_quality_state(payload, freshness=freshness)
    return {
        "state": state,
        "label": DATA_QUALITY_LABELS[state],
        "available": state == "ready",
    }


def _consumer_data_quality_state(payload: Mapping[str, Any], *, freshness: str) -> str:
    if _truthy(payload.get("isUnavailable")) or freshness in {"unavailable", "error", "mock", "synthetic"}:
        return "unavailable"
    if _truthy(payload.get("isPartial")) or freshness == "partial":
        return "partial"
    if _truthy(payload.get("isStale")) or freshness in {"stale", "delayed"}:
        return "delayed"
    if _truthy(payload.get("isFallback")) or freshness in {"fallback", "cached"}:
        return "cached"
    if freshness in {"live", "fresh", "ready"}:
        return "ready"
    return "no_evidence"


def _truthy(value: Any) -> bool:
    return value is True
