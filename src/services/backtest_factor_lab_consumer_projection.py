# -*- coding: utf-8 -*-
"""Pure consumer-safe projection for Backtest + Factor Lab readiness packets."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


_DEFAULT_P0_DIMENSION_COUNT = 7
_DEFAULT_P1_DIMENSION_COUNT = 8


def project_backtest_factor_lab_consumer_readiness(
    readiness_packet: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Translate a readiness packet into bounded consumer-facing product copy."""

    packet = dict(readiness_packet) if isinstance(readiness_packet, Mapping) else {}
    p0_blocked, p1_blocked = _blocked_dimension_counts(packet)
    has_blockers = (p0_blocked + p1_blocked) > 0
    ready = bool(packet.get("professionalReady")) and not has_blockers

    if ready:
        return {
            "consumerState": "AVAILABLE",
            "confidencePosture": "资料较完整，仍以研究观察为主",
            "shortExplanation": "当前回测与因子研究资料较完整，可继续查看结果与对比。",
            "blockedDimensionSummary": "当前未发现明显资料缺口。",
        }

    if p0_blocked > 0:
        return {
            "consumerState": "INSUFFICIENT",
            "confidencePosture": "当前仅供观察",
            "shortExplanation": "关键研究资料仍不完整，当前结果更适合用作观察参考。",
            "blockedDimensionSummary": _blocked_dimension_summary(
                p0_blocked=p0_blocked,
                p1_blocked=p1_blocked,
            ),
        }

    if p1_blocked > 0:
        return {
            "consumerState": "PARTIAL",
            "confidencePosture": "置信度受限，仅供观察",
            "shortExplanation": "基础研究资料已具备，但扩展验证仍不完整。",
            "blockedDimensionSummary": _blocked_dimension_summary(
                p0_blocked=p0_blocked,
                p1_blocked=p1_blocked,
            ),
        }

    return {
        "consumerState": "INSUFFICIENT",
        "confidencePosture": "当前仅供观察",
        "shortExplanation": "研究资料状态仍待确认，当前结果更适合用作观察参考。",
        "blockedDimensionSummary": _blocked_dimension_summary(
            p0_blocked=_DEFAULT_P0_DIMENSION_COUNT,
            p1_blocked=_DEFAULT_P1_DIMENSION_COUNT,
        ),
    }


def _blocked_dimension_counts(packet: Mapping[str, Any]) -> tuple[int, int]:
    counts = packet.get("dimensionCounts")
    p0_blocked = _blocked_count_from_counts(counts, "p0")
    p1_blocked = _blocked_count_from_counts(counts, "p1")
    if p0_blocked is not None and p1_blocked is not None:
        return p0_blocked, p1_blocked

    dimensions = packet.get("dimensions")
    p0_from_dimensions = _blocked_count_from_dimensions(dimensions, "p0")
    p1_from_dimensions = _blocked_count_from_dimensions(dimensions, "p1")
    if p0_from_dimensions is not None and p1_from_dimensions is not None:
        return p0_from_dimensions, p1_from_dimensions

    if bool(packet.get("professionalReady")):
        return 0, 0
    return _DEFAULT_P0_DIMENSION_COUNT, _DEFAULT_P1_DIMENSION_COUNT


def _blocked_count_from_counts(counts: Any, priority: str) -> int | None:
    if not isinstance(counts, Mapping):
        return None
    priority_counts = counts.get(priority)
    if not isinstance(priority_counts, Mapping):
        return None
    missing = _safe_int(priority_counts.get("missing"))
    ambiguous = _safe_int(priority_counts.get("ambiguous"))
    if missing is None or ambiguous is None:
        return None
    return missing + ambiguous


def _blocked_count_from_dimensions(dimensions: Any, priority: str) -> int | None:
    if not isinstance(dimensions, Mapping):
        return None
    items = dimensions.get(priority)
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
        return None

    blocked = 0
    for item in items:
        if not isinstance(item, Mapping):
            blocked += 1
            continue
        if str(item.get("state") or "").lower() != "available":
            blocked += 1
    return blocked


def _blocked_dimension_summary(*, p0_blocked: int, p1_blocked: int) -> str:
    if p0_blocked <= 0 and p1_blocked <= 0:
        return "当前未发现明显资料缺口。"
    if p0_blocked > 0 and p1_blocked > 0:
        return (
            f"基础研究条件仍有 {p0_blocked} 项待补充，"
            f"扩展研究条件仍有 {p1_blocked} 项待补充。"
        )
    if p0_blocked > 0:
        return f"基础研究条件仍有 {p0_blocked} 项待补充。"
    return f"扩展研究条件仍有 {p1_blocked} 项待补充。"


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None
