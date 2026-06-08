# -*- coding: utf-8 -*-
"""Report-safe summary projection for Backtest + Factor Lab readiness."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


_TITLE = "回测与因子研究资料摘要"
_NO_ADVICE = "本摘要不构成投资建议，不构成买卖建议，也不构成执行指令。"
_OBSERVE_ONLY = "仅供观察，不构成投资建议，不构成买卖建议，也不构成执行指令。"

_FOUNDATION_GROUP = "基础研究资料"
_EXTENDED_GROUP = "扩展验证资料"
_UNKNOWN_ITEM = "资料状态待确认"

_READY_STATUS = "资料较完整，仍以观察为主"
_FOUNDATION_BLOCKED_STATUS = "关键资料不足，仅供观察"
_EXTENDED_BLOCKED_STATUS = "扩展验证不完整，仅供观察"
_UNKNOWN_STATUS = "资料状态待确认，仅供观察"

_SAFE_DIMENSION_LABELS = {
    "pit_as_of": "历史样本时间口径",
    "survivorship_delisted": "退市与样本留存处理",
    "corporate_actions": "复权与公司行动处理",
    "calendar_session_halt_constraints": "交易日历、交易时段与停牌约束",
    "transaction_cost_realism": "交易成本、滑点与冲击约束",
    "portfolio_rebalance_model": "组合再平衡口径",
    "dataset_snapshot_version_source_authority": "数据快照与版本口径",
    "decile_returns": "分组收益验证",
    "panel_contract": "因子样本面板口径",
    "forward_return_generation": "前瞻收益生成口径",
    "neutralization": "中性化处理",
    "factor_correlation": "因子相关性检查",
    "multi_factor_composition": "多因子组合口径",
    "oos_walk_forward": "样本外与滚动验证",
    "parameter_stability": "参数稳定性检查",
}


def build_backtest_factor_lab_report_summary(
    readiness_packet: Mapping[str, Any] | None = None,
    consumer_projection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a JSON-safe observe-only text block for future reports."""

    packet_supplied = readiness_packet is not None
    packet = dict(readiness_packet) if isinstance(readiness_packet, Mapping) else {}
    projection = dict(consumer_projection) if isinstance(consumer_projection, Mapping) else {}

    packet_result = _summary_from_packet(packet) if packet else None
    if packet_supplied and packet_result is None:
        status_kind = "unknown"
        groups = _unknown_groups()
    elif packet_result is not None:
        status_kind = packet_result["statusKind"]
        groups = packet_result["groups"]
    else:
        status_kind, groups = _summary_from_projection(projection)

    return {
        "title": _TITLE,
        "shortStatus": _short_status(status_kind),
        "observeOnlyWording": _OBSERVE_ONLY,
        "limitations": _limitations(status_kind),
        "missingPrerequisiteGroups": groups,
    }


def _summary_from_packet(packet: Mapping[str, Any]) -> dict[str, Any] | None:
    dimension_groups = _groups_from_dimensions(packet.get("dimensions"))
    if dimension_groups is not None:
        if not dimension_groups:
            return _ready_packet_result(packet)
        return {
            "statusKind": _status_kind_from_groups(dimension_groups),
            "groups": dimension_groups,
        }

    count_groups = _groups_from_counts(packet.get("dimensionCounts"))
    if count_groups is not None:
        if not count_groups:
            return _ready_packet_result(packet)
        return {
            "statusKind": _status_kind_from_groups(count_groups),
            "groups": count_groups,
        }

    return None


def _ready_packet_result(packet: Mapping[str, Any]) -> dict[str, Any] | None:
    if packet.get("professionalReady") is not True:
        return None
    return {"statusKind": "ready", "groups": []}


def _groups_from_dimensions(dimensions: Any) -> list[dict[str, Any]] | None:
    if not isinstance(dimensions, Mapping):
        return None

    groups: list[dict[str, Any]] = []
    for priority, group_name in (("p0", _FOUNDATION_GROUP), ("p1", _EXTENDED_GROUP)):
        items = dimensions.get(priority)
        if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
            return None

        missing_items = _missing_items_from_dimension_list(items)
        if missing_items:
            groups.append(
                {
                    "name": group_name,
                    "status": "待补充",
                    "items": missing_items,
                }
            )

    return groups


def _missing_items_from_dimension_list(items: Sequence[Any]) -> list[str]:
    missing_items: list[str] = []
    for item in items:
        if not isinstance(item, Mapping):
            _append_unique(missing_items, _UNKNOWN_ITEM)
            continue

        state = str(item.get("state") or "").strip().lower()
        if state == "available":
            continue

        label = _SAFE_DIMENSION_LABELS.get(str(item.get("id") or ""))
        _append_unique(missing_items, label or _UNKNOWN_ITEM)

    return missing_items


def _groups_from_counts(counts: Any) -> list[dict[str, Any]] | None:
    if not isinstance(counts, Mapping):
        return None

    groups: list[dict[str, Any]] = []
    for priority, group_name in (("p0", _FOUNDATION_GROUP), ("p1", _EXTENDED_GROUP)):
        blocked = _blocked_count_from_counts(counts, priority)
        if blocked is None:
            return None
        if blocked > 0:
            groups.append(
                {
                    "name": group_name,
                    "status": "待补充",
                    "items": [f"{blocked} 项资料待补充"],
                }
            )

    return groups


def _blocked_count_from_counts(counts: Mapping[str, Any], priority: str) -> int | None:
    priority_counts = counts.get(priority)
    if not isinstance(priority_counts, Mapping):
        return None

    missing = _safe_int(priority_counts.get("missing"))
    ambiguous = _safe_int(priority_counts.get("ambiguous"))
    if missing is None or ambiguous is None:
        return None
    return missing + ambiguous


def _summary_from_projection(projection: Mapping[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    state = str(projection.get("consumerState") or "").strip().upper()
    if state == "AVAILABLE":
        return "ready", []
    if state == "PARTIAL":
        return "extended_blocked", [
            {
                "name": _EXTENDED_GROUP,
                "status": "待确认",
                "items": ["扩展验证资料待确认"],
            }
        ]
    if state in {"INSUFFICIENT", "PAUSED", "UNAVAILABLE", "UPDATING", "DELAYED"}:
        return "foundation_blocked", [
            {
                "name": _FOUNDATION_GROUP,
                "status": "待确认",
                "items": ["基础研究资料待确认"],
            }
        ]
    return "unknown", _unknown_groups()


def _status_kind_from_groups(groups: Sequence[Mapping[str, Any]]) -> str:
    names = {str(group.get("name") or "") for group in groups}
    if _FOUNDATION_GROUP in names:
        return "foundation_blocked"
    if _EXTENDED_GROUP in names:
        return "extended_blocked"
    return "unknown"


def _short_status(status_kind: str) -> str:
    if status_kind == "ready":
        return _READY_STATUS
    if status_kind == "foundation_blocked":
        return _FOUNDATION_BLOCKED_STATUS
    if status_kind == "extended_blocked":
        return _EXTENDED_BLOCKED_STATUS
    return _UNKNOWN_STATUS


def _limitations(status_kind: str) -> list[str]:
    if status_kind == "ready":
        return [
            "资料较完整仍不代表未来表现承诺。",
            _NO_ADVICE,
        ]
    if status_kind == "foundation_blocked":
        return [
            "关键研究资料仍不完整，当前结果更适合作为观察参考。",
            _NO_ADVICE,
        ]
    if status_kind == "extended_blocked":
        return [
            "基础研究资料已具备，但扩展验证仍不完整，置信度受限。",
            _NO_ADVICE,
        ]
    return [
        "输入资料缺失或格式无法确认，默认按资料不足处理。",
        _NO_ADVICE,
    ]


def _unknown_groups() -> list[dict[str, Any]]:
    return [
        {
            "name": _FOUNDATION_GROUP,
            "status": "待确认",
            "items": [_UNKNOWN_ITEM],
        },
        {
            "name": _EXTENDED_GROUP,
            "status": "待确认",
            "items": [_UNKNOWN_ITEM],
        },
    ]


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)
