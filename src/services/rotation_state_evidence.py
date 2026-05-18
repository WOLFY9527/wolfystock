# -*- coding: utf-8 -*-
"""Advisory-only rotation state evidence derived from existing radar fields."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from src.contracts.source_confidence import (
    SOURCE_CONFIDENCE_CONTRACT_VERSION,
    coerce_source_confidence_contract,
)


ROTATION_STATE_EVIDENCE_SCHEMA_VERSION = "rotation_state_evidence_v1"
NO_ADVICE_DISCLOSURE = "仅用于观察资金轮动迹象，非买卖建议。"
STATE_LABELS = {
    "accumulation": "低位吸筹观察",
    "breakout": "突破确认观察",
    "acceleration": "加速扩张观察",
    "overheated": "过热拥挤观察",
    "divergence": "强弱分歧观察",
    "fading": "降温走弱观察",
    "insufficient_evidence": "证据不足",
}
FLOW_FORBIDDEN_WORDING = (
    "资金流入确认",
    "真实资金流",
    "主力资金确认",
    "北向资金确认",
    "南向资金确认",
    "ETF 申赎确认",
)


class RotationFlowEvidenceType(str, Enum):
    NONE = "none"
    PROXY_ONLY = "proxy_only"
    REAL_FLOW = "real_flow"
    MIXED_REAL_AND_PROXY = "mixed_real_and_proxy"


@dataclass(slots=True)
class RotationStateSignal:
    status: str
    label: str
    value: float | str | None = None
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "label": self.label,
            "value": self.value,
            "note": self.note,
        }


@dataclass(slots=True)
class RotationRequiredDataStatus:
    status: str
    hasSufficientEvidence: bool
    missingLabels: list[str] = field(default_factory=list)
    missingReasonCodes: list[str] = field(default_factory=list)
    coverageLabels: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "hasSufficientEvidence": self.hasSufficientEvidence,
            "missingLabels": list(self.missingLabels),
            "missingReasonCodes": list(self.missingReasonCodes),
            "coverageLabels": list(self.coverageLabels),
        }


@dataclass(slots=True)
class RotationStateEvidence:
    market: str
    themeId: str
    taxonomyVersion: str
    state: str
    stateConfidence: float
    stateExplanation: str
    flowLanguageAllowed: bool
    flowEvidenceType: RotationFlowEvidenceType
    requiredDataStatus: RotationRequiredDataStatus
    signals: dict[str, RotationStateSignal]
    riskLabels: list[str]
    uiSummary: str
    adminDiagnostics: dict[str, Any]
    computedAt: str | None = None
    asOf: str | None = None
    noAdviceDisclosure: str = NO_ADVICE_DISCLOSURE

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": ROTATION_STATE_EVIDENCE_SCHEMA_VERSION,
            "market": self.market,
            "themeId": self.themeId,
            "taxonomyVersion": self.taxonomyVersion,
            "computedAt": self.computedAt,
            "asOf": self.asOf,
            "state": self.state,
            "stateConfidence": round(max(0.0, min(1.0, self.stateConfidence)), 2),
            "stateLabel": STATE_LABELS[self.state],
            "stateExplanation": self.stateExplanation,
            "flowLanguageAllowed": self.flowLanguageAllowed,
            "flowEvidenceType": self.flowEvidenceType.value,
            "requiredDataStatus": self.requiredDataStatus.to_dict(),
            "signals": {key: value.to_dict() for key, value in self.signals.items()},
            "riskLabels": list(self.riskLabels),
            "uiSummary": self.uiSummary,
            "adminDiagnostics": dict(self.adminDiagnostics),
            "noAdviceDisclosure": self.noAdviceDisclosure,
        }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    result: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            result.append(text)
    return result


def _coerce_real_flow(payload: Mapping[str, Any]) -> bool:
    return all(
        str(payload.get(key) or "").strip()
        for key in ("source", "methodology", "asOf", "marketScope", "freshness")
    )


def _flow_boundary(theme: Mapping[str, Any], context: Mapping[str, Any]) -> tuple[RotationFlowEvidenceType, bool]:
    real_flow_payload = _mapping(context.get("flowEvidence")) or _mapping(theme.get("flowEvidence"))
    has_real_flow = _coerce_real_flow(real_flow_payload)
    has_proxy_inputs = not bool(theme.get("staticThemeOnly")) and (
        _number(_mapping(theme.get("relativeStrength")).get("averageRelativeStrengthPercent")) is not None
        or _number(_mapping(theme.get("volume")).get("averageRelativeVolume")) is not None
        or _number(_mapping(theme.get("breadth")).get("percentUp")) is not None
    )
    if has_real_flow and has_proxy_inputs:
        return RotationFlowEvidenceType.MIXED_REAL_AND_PROXY, True
    if has_real_flow:
        return RotationFlowEvidenceType.REAL_FLOW, True
    if has_proxy_inputs:
        return RotationFlowEvidenceType.PROXY_ONLY, False
    return RotationFlowEvidenceType.NONE, False


def _required_data_status(
    theme: Mapping[str, Any],
    flow_type: RotationFlowEvidenceType,
) -> RotationRequiredDataStatus:
    breadth = _mapping(theme.get("breadth"))
    volume = _mapping(theme.get("volume"))
    relative_strength = _mapping(theme.get("relativeStrength"))
    proxy_quality = _mapping(theme.get("proxyQuality"))
    persistence = _mapping(theme.get("persistenceEvidence"))
    missing_labels: list[str] = []
    missing_reason_codes: list[str] = []
    coverage_labels: list[str] = []

    if bool(theme.get("staticThemeOnly")) or str(theme.get("source")) == "local_taxonomy":
        missing_labels.extend(["待接入本地行情", "分类观察", "真实资金流暂缺"])
        missing_reason_codes.extend(["taxonomy_only", "local_market_data_missing", "real_flow_missing"])
    if _number(relative_strength.get("averageRelativeStrengthPercent")) is None:
        missing_labels.append("代理强度")
        missing_reason_codes.append("relative_strength_missing")
    else:
        coverage_labels.append("代理强度")
    if _number(breadth.get("percentUp")) is None or _number(breadth.get("percentOutperformingBenchmark")) is None:
        missing_labels.append("广度确认")
        missing_reason_codes.append("breadth_missing")
    else:
        coverage_labels.append("广度确认")
    if _number(volume.get("averageRelativeVolume")) is None:
        missing_labels.append("量能确认")
        missing_reason_codes.append("volume_missing")
    else:
        coverage_labels.append("量能确认")
    if not _string_list(persistence.get("availableWindows")):
        missing_labels.append("跨时窗延续")
        missing_reason_codes.append("persistence_windows_missing")
    else:
        coverage_labels.append("跨时窗延续")
    if proxy_quality.get("hasMissingRequiredProxy"):
        missing_labels.append("轮动代理证据")
        missing_reason_codes.append("proxy_coverage_incomplete")
    else:
        coverage_labels.append("轮动代理证据")
    if flow_type is RotationFlowEvidenceType.NONE:
        missing_labels.append("真实资金流暂缺")
        missing_reason_codes.append("real_flow_missing")

    has_sufficient = not bool(theme.get("staticThemeOnly")) and len(
        {
            "relative_strength_missing",
            "breadth_missing",
            "volume_missing",
            "persistence_windows_missing",
        }.intersection(missing_reason_codes)
    ) == 0
    status = "ready" if has_sufficient else "insufficient"
    return RotationRequiredDataStatus(
        status=status,
        hasSufficientEvidence=has_sufficient,
        missingLabels=list(dict.fromkeys(missing_labels)),
        missingReasonCodes=list(dict.fromkeys(missing_reason_codes)),
        coverageLabels=list(dict.fromkeys(coverage_labels)),
    )


def _signal_status(value: float | None, *, strong: float, usable: float = 0.0) -> str:
    if value is None:
        return "missing"
    if value >= strong:
        return "strong"
    if value >= usable:
        return "usable"
    return "weak"


def _ratio(value: Any) -> float | None:
    number = _number(value)
    if number is None:
        return None
    if number > 1.0:
        number = number / 100.0
    return max(0.0, min(1.0, number))


def _signals(
    theme: Mapping[str, Any],
    flow_type: RotationFlowEvidenceType,
) -> dict[str, RotationStateSignal]:
    relative_strength = _mapping(theme.get("relativeStrength"))
    breadth = _mapping(theme.get("breadth"))
    volume = _mapping(theme.get("volume"))
    persistence = _mapping(theme.get("persistenceEvidence"))
    synchronization = _mapping(theme.get("synchronization"))
    leadership = _mapping(theme.get("leadership"))
    risk_labels = set(_string_list(theme.get("riskLabels")))

    rs_value = _number(relative_strength.get("averageRelativeStrengthPercent"))
    breadth_value = _number(breadth.get("percentOutperformingBenchmark"))
    volume_value = _number(volume.get("averageRelativeVolume"))
    persistence_value = _number(persistence.get("score"))
    volatility_flag = 1.0 if "gap_fade_risk" in risk_labels else 0.0
    correlation_flag = _number(leadership.get("leadershipConcentrationPercent"))

    fund_flow_label = {
        RotationFlowEvidenceType.NONE: "证据不足",
        RotationFlowEvidenceType.PROXY_ONLY: "轮动代理证据",
        RotationFlowEvidenceType.REAL_FLOW: "真实资金流",
        RotationFlowEvidenceType.MIXED_REAL_AND_PROXY: "轮动代理证据 + 真实资金流",
    }[flow_type]
    fund_flow_note = {
        RotationFlowEvidenceType.NONE: "分类观察",
        RotationFlowEvidenceType.PROXY_ONLY: "代理强度 / 广度确认 / 量能确认",
        RotationFlowEvidenceType.REAL_FLOW: "真实流向字段已齐备",
        RotationFlowEvidenceType.MIXED_REAL_AND_PROXY: "真实流向字段与代理证据同时可用",
    }[flow_type]

    return {
        "relativeStrength": RotationStateSignal(
            status=_signal_status(rs_value, strong=1.5, usable=0.2),
            label="代理强度",
            value=round(rs_value, 2) if rs_value is not None else None,
            note=f"相对基准 {relative_strength.get('benchmark') or 'unknown'}",
        ),
        "breadth": RotationStateSignal(
            status=_signal_status(breadth_value, strong=70.0, usable=50.0),
            label="广度确认",
            value=round(breadth_value, 1) if breadth_value is not None else None,
            note=f"上涨 {breadth.get('percentUp')}%，跑赢 {breadth.get('percentOutperformingBenchmark')}%",
        ),
        "volumeExpansion": RotationStateSignal(
            status=_signal_status(volume_value, strong=1.4, usable=1.0),
            label="量能确认",
            value=round(volume_value, 2) if volume_value is not None else None,
            note=str(volume.get("label") or "证据不足"),
        ),
        "momentumPersistence": RotationStateSignal(
            status=_signal_status(persistence_value, strong=0.75, usable=0.45),
            label="跨时窗延续",
            value=round(persistence_value, 2) if persistence_value is not None else None,
            note=str(persistence.get("label") or "证据不足"),
        ),
        "volatilityRegime": RotationStateSignal(
            status="risk" if volatility_flag else "neutral",
            label="波动约束",
            value=volatility_flag,
            note="冲高回落风险抬升" if volatility_flag else "未见明显波动阻断",
        ),
        "correlationShift": RotationStateSignal(
            status="crowded" if correlation_flag is not None and correlation_flag >= 60 else "neutral",
            label="相关性 / 集中度",
            value=round(correlation_flag, 1) if correlation_flag is not None else None,
            note=synchronization.get("label") or "分类观察",
        ),
        "fundFlow": RotationStateSignal(
            status="allowed" if flow_type in {RotationFlowEvidenceType.REAL_FLOW, RotationFlowEvidenceType.MIXED_REAL_AND_PROXY} else "proxy_only" if flow_type is RotationFlowEvidenceType.PROXY_ONLY else "missing",
            label=fund_flow_label,
            value=flow_type.value,
            note=fund_flow_note,
        ),
    }


def _infer_state(theme: Mapping[str, Any], required: RotationRequiredDataStatus) -> tuple[str, float, str]:
    stage = str(theme.get("stage") or "")
    confidence = _number(theme.get("confidence")) or 0.0
    risk_labels = set(_string_list(theme.get("riskLabels")))
    relative_strength = _mapping(theme.get("relativeStrength"))
    breadth = _mapping(theme.get("breadth"))
    volume = _mapping(theme.get("volume"))
    persistence = _mapping(theme.get("persistenceEvidence"))
    leadership = _mapping(theme.get("leadership"))

    rs_value = _number(relative_strength.get("averageRelativeStrengthPercent"))
    percent_up = _number(breadth.get("percentUp"))
    outperform = _number(breadth.get("percentOutperformingBenchmark"))
    volume_value = _number(volume.get("averageRelativeVolume"))
    persistence_value = _number(persistence.get("score")) or 0.0
    concentration = _number(leadership.get("leadershipConcentrationPercent")) or 0.0
    static_theme = bool(theme.get("staticThemeOnly")) or str(theme.get("source")) == "local_taxonomy"

    if static_theme or not required.hasSufficientEvidence:
        return (
            "insufficient_evidence",
            min(confidence, 0.35),
            "当前仅有分类或代理残缺证据，先维持证据不足，不替代原有阶段结论。",
        )
    if stage == "cooling_watch" or persistence.get("label") == "跨时窗降温" or (
        (percent_up is not None and percent_up < 40)
        and (outperform is not None and outperform < 40)
        and persistence_value <= 0.35
    ):
        return (
            "fading",
            min(confidence, 0.72),
            "相对强弱与广度已降温，跨时窗延续转弱，保持降温走弱观察。",
        )
    if (
        ((rs_value or 0.0) > 0.5 and (outperform is not None and outperform < 55))
        or "thin_breadth" in risk_labels
        or "stale_or_incomplete_windows" in risk_labels
        or _mapping(theme.get("proxyQuality")).get("hasMissingRequiredProxy")
    ):
        return (
            "divergence",
            min(confidence, 0.68),
            "代理强度与广度或时窗确认不一致，当前更适合作为强弱分歧观察。",
        )
    if (
        "gap_fade_risk" in risk_labels
        or (
            "single_name_driven" in risk_labels
            and concentration >= 60
            and (percent_up or 0.0) >= 65
            and (outperform or 0.0) >= 65
        )
        or ((volume_value or 0.0) >= 2.3 and (rs_value or 0.0) >= 1.8 and concentration >= 55)
    ):
        return (
            "overheated",
            min(0.88, max(confidence, 0.55)),
            "强度与量能偏高，同时拥挤或回落风险抬升，因此标记为过热拥挤观察。",
        )
    if (
        (rs_value or 0.0) >= 1.5
        and (percent_up or 0.0) >= 80
        and (outperform or 0.0) >= 80
        and (volume_value or 0.0) >= 1.4
        and persistence_value >= 0.75
    ):
        return (
            "acceleration",
            min(0.92, max(confidence, 0.6)),
            "代理强度、广度、量能与跨时窗延续同时增强，符合加速扩张观察。",
        )
    if (
        (rs_value or 0.0) >= 0.9
        and (percent_up or 0.0) >= 65
        and (outperform or 0.0) >= 65
        and (volume_value or 0.0) >= 1.1
    ):
        return (
            "breakout",
            min(0.85, max(confidence, 0.5)),
            "代理强度、广度与量能已形成确认，但仍保持为突破确认观察而非建议结论。",
        )
    if (
        (rs_value or 0.0) >= 0.2
        and (percent_up or 0.0) >= 55
        and (outperform or 0.0) >= 55
        and (volume_value or 0.0) >= 1.0
    ):
        return (
            "accumulation",
            min(0.78, max(confidence, 0.45)),
            "代理强度与广度处于改善初期，量能可用且未见明显阻断，维持低位吸筹观察。",
        )
    return (
        "insufficient_evidence",
        min(confidence, 0.4),
        "现有代理与时窗证据不足以形成更明确的轮动状态判断。",
    )


def _ui_summary(state: str, signals: Mapping[str, RotationStateSignal], required: RotationRequiredDataStatus) -> str:
    if state == "insufficient_evidence":
        summary = "分类观察，待接入本地行情与更完整代理证据。"
    else:
        parts = [
            STATE_LABELS[state],
            signals["relativeStrength"].label,
            signals["breadth"].label,
            signals["volumeExpansion"].label,
        ]
        summary = " / ".join(parts[:2]) + "；" + "、".join(parts[2:])
    for forbidden in FLOW_FORBIDDEN_WORDING:
        if forbidden in summary:
            summary = summary.replace(forbidden, "轮动代理证据")
    if required.missingLabels and "待接入本地行情" in required.missingLabels and "分类观察" not in summary:
        summary = f"{summary} 分类观察。"
    return summary


def _signal_source_confidence(
    *,
    source: str,
    source_label: str,
    as_of: str | None,
    freshness: str,
    coverage_ratio: float | None,
    is_fallback: bool,
    is_stale: bool,
    is_partial: bool,
    is_unavailable: bool,
    degradation_reason: str | None,
) -> dict[str, Any]:
    confidence_weight = 0.0 if is_unavailable else coverage_ratio if coverage_ratio is not None else 0.0
    return coerce_source_confidence_contract(
        {
            "source": source,
            "sourceLabel": source_label,
            "asOf": as_of,
            "freshness": freshness,
            "isFallback": is_fallback,
            "isStale": is_stale,
            "isPartial": is_partial,
            "isUnavailable": is_unavailable,
            "confidenceWeight": confidence_weight,
            "coverage": coverage_ratio,
            "degradationReason": degradation_reason,
        }
    ).to_dict()


def _evidence_snapshot(
    theme: Mapping[str, Any],
    *,
    computed_at: str | None,
    as_of: str | None,
    signals: Mapping[str, RotationStateSignal],
) -> dict[str, Any]:
    theme_source = str(theme.get("source") or "rotation_state").strip() or "rotation_state"
    theme_source_label = str(theme.get("sourceLabel") or "轮动证据").strip() or "轮动证据"
    theme_freshness = str(theme.get("freshness") or "unknown").strip() or "unknown"
    theme_is_fallback = bool(theme.get("isFallback"))
    theme_is_stale = bool(theme.get("isStale"))
    theme_is_partial = bool(theme.get("isPartial"))
    theme_is_unavailable = bool(theme.get("isUnavailable")) or theme_freshness in {"unavailable", "error"}

    breadth = _mapping(theme.get("breadth"))
    volume = _mapping(theme.get("volume"))
    synchronization = _mapping(theme.get("synchronization"))
    persistence = _mapping(theme.get("persistenceEvidence"))
    required_windows = _string_list(persistence.get("requiredWindows")) or ["5m", "15m", "60m", "1d"]
    available_windows = _string_list(persistence.get("availableWindows"))
    stale_or_fallback_windows = _string_list(persistence.get("staleOrFallbackWindows"))

    breadth_coverage_ratio = _ratio(breadth.get("coveragePercent"))
    configured_members = max(int(_number(breadth.get("configuredMembers")) or 0), 0)
    volume_available_members = max(int(_number(volume.get("availableMemberCount")) or 0), 0)
    volume_coverage_ratio = (
        max(0.0, min(1.0, volume_available_members / configured_members))
        if configured_members > 0
        else breadth_coverage_ratio
    )
    persistence_coverage_ratio = (
        max(0.0, min(1.0, len(available_windows) / len(required_windows)))
        if required_windows
        else 0.0
    )
    signal_definitions = {
        "relativeStrength": {
            "label": "代理强度",
            "status": signals["relativeStrength"].status,
            "value": signals["relativeStrength"].value,
            "coverageRatio": breadth_coverage_ratio,
            "isFallback": theme_is_fallback,
            "isStale": theme_is_stale,
            "isPartial": (breadth_coverage_ratio or 0.0) < 1.0 or signals["relativeStrength"].status == "weak",
            "isUnavailable": signals["relativeStrength"].value is None,
            "degradationReason": "weak_signal" if signals["relativeStrength"].status == "weak" else "signal_unavailable" if signals["relativeStrength"].value is None else "partial_coverage" if (breadth_coverage_ratio or 0.0) < 1.0 else None,
        },
        "breadth": {
            "label": "广度确认",
            "status": signals["breadth"].status,
            "value": signals["breadth"].value,
            "coverageRatio": breadth_coverage_ratio,
            "isFallback": theme_is_fallback,
            "isStale": theme_is_stale,
            "isPartial": (breadth_coverage_ratio or 0.0) < 1.0 or signals["breadth"].status == "weak",
            "isUnavailable": signals["breadth"].value is None,
            "degradationReason": "weak_signal" if signals["breadth"].status == "weak" else "signal_unavailable" if signals["breadth"].value is None else "partial_coverage" if (breadth_coverage_ratio or 0.0) < 1.0 else None,
        },
        "volume": {
            "label": "量能确认",
            "status": signals["volumeExpansion"].status,
            "value": signals["volumeExpansion"].value,
            "coverageRatio": volume_coverage_ratio,
            "isFallback": theme_is_fallback,
            "isStale": theme_is_stale,
            "isPartial": (volume_coverage_ratio or 0.0) < 1.0 or signals["volumeExpansion"].status == "weak",
            "isUnavailable": signals["volumeExpansion"].value is None,
            "degradationReason": "weak_signal" if signals["volumeExpansion"].status == "weak" else "signal_unavailable" if signals["volumeExpansion"].value is None else "partial_coverage" if (volume_coverage_ratio or 0.0) < 1.0 else None,
        },
        "persistence": {
            "label": "跨时窗延续",
            "status": signals["momentumPersistence"].status,
            "value": signals["momentumPersistence"].value,
            "coverageRatio": persistence_coverage_ratio,
            "isFallback": theme_is_fallback,
            "isStale": theme_is_stale,
            "isPartial": len(available_windows) < len(required_windows) or signals["momentumPersistence"].status in {"weak", "usable"} or bool(stale_or_fallback_windows),
            "isUnavailable": signals["momentumPersistence"].value is None or not available_windows,
            "degradationReason": "signal_unavailable" if signals["momentumPersistence"].value is None or not available_windows else "partial_coverage" if len(available_windows) < len(required_windows) or bool(stale_or_fallback_windows) else "weak_signal" if signals["momentumPersistence"].status == "weak" else None,
        },
        "vwapParticipation": {
            "label": "VWAP 参与度",
            "status": _signal_status(_number(synchronization.get("aboveVwapPercent")), strong=70.0, usable=50.0),
            "value": _number(synchronization.get("aboveVwapPercent")),
            "coverageRatio": breadth_coverage_ratio,
            "isFallback": theme_is_fallback,
            "isStale": theme_is_stale,
            "isPartial": (breadth_coverage_ratio or 0.0) < 1.0 or (_number(synchronization.get("aboveVwapPercent")) or 0.0) < 50.0,
            "isUnavailable": _number(synchronization.get("aboveVwapPercent")) is None,
            "degradationReason": "weak_signal" if (_number(synchronization.get("aboveVwapPercent")) or 0.0) < 50.0 and _number(synchronization.get("aboveVwapPercent")) is not None else "signal_unavailable" if _number(synchronization.get("aboveVwapPercent")) is None else "partial_coverage" if (breadth_coverage_ratio or 0.0) < 1.0 else None,
        },
    }

    signal_snapshots: dict[str, Any] = {}
    degraded_signal_count = 0
    unavailable_signal_count = 0
    coverage_ratios: list[float] = []
    for key, item in signal_definitions.items():
        coverage_ratio = item["coverageRatio"]
        coverage_percent = round(coverage_ratio * 100, 1) if coverage_ratio is not None else None
        source_confidence = _signal_source_confidence(
            source=f"{theme_source}.{key}",
            source_label=f"{theme_source_label} {item['label']}",
            as_of=as_of,
            freshness=theme_freshness,
            coverage_ratio=coverage_ratio,
            is_fallback=bool(item["isFallback"]),
            is_stale=bool(item["isStale"]),
            is_partial=bool(item["isPartial"]),
            is_unavailable=bool(item["isUnavailable"]),
            degradation_reason=item["degradationReason"],
        )
        degraded = bool(
            source_confidence["isFallback"]
            or source_confidence["isStale"]
            or source_confidence["isPartial"]
            or source_confidence["isUnavailable"]
            or item["status"] in {"weak", "missing"}
        )
        if degraded:
            degraded_signal_count += 1
        if source_confidence["isUnavailable"]:
            unavailable_signal_count += 1
        if coverage_ratio is not None:
            coverage_ratios.append(coverage_ratio)
        signal_snapshots[key] = {
            "key": key,
            "label": item["label"],
            "status": item["status"],
            "value": item["value"],
            "available": not source_confidence["isUnavailable"],
            "degraded": degraded,
            "coveragePercent": coverage_percent,
            "coverageRatio": coverage_ratio,
            "source": source_confidence["source"],
            "sourceLabel": source_confidence["sourceLabel"],
            "asOf": source_confidence["asOf"],
            "freshness": source_confidence["freshness"],
            "isFallback": source_confidence["isFallback"],
            "isStale": source_confidence["isStale"],
            "isPartial": source_confidence["isPartial"],
            "isUnavailable": source_confidence["isUnavailable"],
            "degradationReason": source_confidence["degradationReason"],
            "capReason": source_confidence["capReason"],
            "sourceConfidence": source_confidence,
        }

    overall_coverage_ratio = min(coverage_ratios) if coverage_ratios else 0.0
    overall_signal_count = len(signal_snapshots)
    overall_partial = bool(theme_is_partial) or (
        degraded_signal_count > 0 and not theme_is_fallback and not theme_is_stale and not theme_is_unavailable
    )
    source_confidence = _signal_source_confidence(
        source=f"{theme_source}.snapshot",
        source_label=f"{theme_source_label} 快照",
        as_of=as_of,
        freshness=theme_freshness,
        coverage_ratio=overall_coverage_ratio,
        is_fallback=theme_is_fallback,
        is_stale=theme_is_stale,
        is_partial=overall_partial,
        is_unavailable=theme_is_unavailable,
        degradation_reason=(
            "source_unavailable"
            if theme_is_unavailable
            else "partial_coverage"
            if overall_partial
            else "fallback_source"
            if theme_is_fallback
            else "stale_source"
            if theme_is_stale
            else None
        ),
    )
    return {
        "contractVersion": SOURCE_CONFIDENCE_CONTRACT_VERSION,
        "computedAt": computed_at,
        "asOf": as_of,
        "source": theme_source,
        "sourceLabel": theme_source_label,
        "freshness": source_confidence["freshness"],
        "isFallback": source_confidence["isFallback"],
        "isStale": source_confidence["isStale"],
        "isPartial": source_confidence["isPartial"],
        "isUnavailable": source_confidence["isUnavailable"],
        "signalCount": overall_signal_count,
        "degradedSignalCount": degraded_signal_count,
        "unavailableSignalCount": unavailable_signal_count,
        "coveragePercent": round(overall_coverage_ratio * 100, 1),
        "coverageRatio": round(overall_coverage_ratio, 4),
        "signalOrder": list(signal_snapshots),
        "sourceConfidence": source_confidence,
        "signals": signal_snapshots,
    }


def build_rotation_state_evidence(
    theme: Mapping[str, Any],
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    ctx = _mapping(context)
    market = str(ctx.get("market") or theme.get("market") or "US").strip() or "US"
    taxonomy_version = str(ctx.get("taxonomyVersion") or "sector_rotation_taxonomy_v1").strip() or "sector_rotation_taxonomy_v1"
    flow_type, flow_language_allowed = _flow_boundary(theme, ctx)
    required = _required_data_status(theme, flow_type)
    signals = _signals(theme, flow_type)
    state, state_confidence, explanation = _infer_state(theme, required)
    ui_summary = _ui_summary(state, signals, required)
    diagnostics = {
        "market": market,
        "themeId": str(theme.get("id") or "").strip(),
        "source": {
            "themeSource": theme.get("source"),
            "themeSourceLabel": theme.get("sourceLabel"),
            "dataQuality": theme.get("dataQuality"),
            "dataCoverage": theme.get("dataCoverage"),
            "sourceClass": theme.get("sourceClass"),
        },
        "inputs": {
            "stage": theme.get("stage"),
            "rotationScore": theme.get("rotationScore"),
            "confidence": theme.get("confidence"),
            "riskLabels": _string_list(theme.get("riskLabels")),
            "relativeStrength": _mapping(theme.get("relativeStrength")),
            "breadth": _mapping(theme.get("breadth")),
            "volume": _mapping(theme.get("volume")),
            "persistenceEvidence": _mapping(theme.get("persistenceEvidence")),
            "synchronization": _mapping(theme.get("synchronization")),
            "leadership": _mapping(theme.get("leadership")),
            "proxyQuality": _mapping(theme.get("proxyQuality")),
        },
        "requiredDataStatus": required.to_dict(),
        "flowBoundary": {
            "flowEvidenceType": flow_type.value,
            "flowLanguageAllowed": flow_language_allowed,
            "realFlowDetected": flow_type in {RotationFlowEvidenceType.REAL_FLOW, RotationFlowEvidenceType.MIXED_REAL_AND_PROXY},
        },
        "stateDecision": {
            "state": state,
            "stateLabel": STATE_LABELS[state],
            "confidence": round(state_confidence, 2),
            "explanation": explanation,
        },
    }
    evidence = RotationStateEvidence(
        market=market,
        themeId=str(theme.get("id") or "").strip(),
        taxonomyVersion=taxonomy_version,
        computedAt=str(ctx.get("computedAt") or theme.get("updatedAt") or "").strip() or None,
        asOf=str(ctx.get("asOf") or theme.get("asOf") or "").strip() or None,
        state=state,
        stateConfidence=state_confidence,
        stateExplanation=explanation,
        flowLanguageAllowed=flow_language_allowed,
        flowEvidenceType=flow_type,
        requiredDataStatus=required,
        signals=signals,
        riskLabels=[STATE_LABELS[state], *_string_list(theme.get("riskLabels"))],
        uiSummary=ui_summary,
        adminDiagnostics=diagnostics,
        noAdviceDisclosure=str(theme.get("noAdviceDisclosure") or NO_ADVICE_DISCLOSURE),
    ).to_dict()
    evidence["evidenceSnapshot"] = _evidence_snapshot(
        theme,
        computed_at=evidence.get("computedAt"),
        as_of=evidence.get("asOf"),
        signals=signals,
    )
    evidence["source"] = evidence["evidenceSnapshot"]["source"]
    evidence["sourceLabel"] = evidence["evidenceSnapshot"]["sourceLabel"]
    evidence["freshness"] = evidence["evidenceSnapshot"]["freshness"]
    evidence["isFallback"] = evidence["evidenceSnapshot"]["isFallback"]
    evidence["isStale"] = evidence["evidenceSnapshot"]["isStale"]
    evidence["isPartial"] = evidence["evidenceSnapshot"]["isPartial"]
    evidence["isUnavailable"] = evidence["evidenceSnapshot"]["isUnavailable"]
    evidence["sourceConfidence"] = evidence["evidenceSnapshot"]["sourceConfidence"]
    evidence["signalOrder"] = list(evidence["evidenceSnapshot"]["signalOrder"])
    return evidence
