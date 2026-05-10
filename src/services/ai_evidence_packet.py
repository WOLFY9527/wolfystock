# -*- coding: utf-8 -*-
"""Additive AI evidence packet schema and confidence-cap policy helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


AI_EVIDENCE_PACKET_VERSION = "ai_evidence_packet_v1"
AI_EVIDENCE_CONFIDENCE_POLICY_VERSION = "confidence_cap_policy_v1"


class AiEvidenceEngine(str, Enum):
    SCANNER = "scanner"
    ROTATION = "rotation"
    OPTIONS = "options"
    BACKTEST = "backtest"
    PORTFOLIO_RISK = "portfolio_risk"
    DATA_QUALITY = "data_quality"
    ANALYSIS = "analysis"


class AiEvidenceDecisionStatus(str, Enum):
    ALLOWED = "allowed"
    CAUTION = "caution"
    FORBIDDEN = "禁止判断"


class AiEvidenceCriticality(str, Enum):
    REQUIRED = "required"
    IMPORTANT = "important"
    OPTIONAL = "optional"


class AiEvidenceStatus(str, Enum):
    AVAILABLE = "available"
    MISSING = "missing"
    STALE = "stale"
    PARTIAL = "partial"
    CONFLICTING = "conflicting"
    SYNTHETIC = "synthetic"
    FIXTURE = "fixture"


class AiEvidenceFreshnessClass(str, Enum):
    FRESH = "fresh"
    DELAYED_USABLE = "delayed_usable"
    STALE = "stale"
    MISSING = "missing"
    FIXTURE = "fixture"
    SYNTHETIC = "synthetic"
    LOCAL_HISTORICAL = "local_historical"
    FALLBACK = "fallback"
    UNKNOWN = "unknown"


class AiEvidenceSourceClass(str, Enum):
    LIVE = "live"
    DELAYED = "delayed"
    CACHE = "cache"
    LOCAL = "local"
    FIXTURE = "fixture"
    SYNTHETIC = "synthetic"
    FALLBACK = "fallback"
    INFERRED = "inferred"
    LOCAL_HISTORICAL = "local_historical"


def _coerce_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    result: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            result.append(text)
    return result


def _coerce_enum(enum_cls: type[Enum], value: Any, default: Enum) -> Enum:
    if isinstance(value, enum_cls):
        return value
    normalized = str(value or "").strip()
    for item in enum_cls:
        if item.value == normalized:
            return item
    return default


def _deep_plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [_deep_plain(item) for item in value]
    if isinstance(value, tuple):
        return [_deep_plain(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _deep_plain(item) for key, item in value.items()}
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _deep_plain(value.to_dict())
    return value


@dataclass(slots=True)
class AiEvidenceEntity:
    type: str
    id: str
    symbol: str | None = None
    market: str = "unknown"
    display_name: str | None = None

    @classmethod
    def from_dict(cls, value: Any) -> "AiEvidenceEntity":
        payload = _coerce_mapping(value)
        return cls(
            type=str(payload.get("type") or "").strip(),
            id=str(payload.get("id") or "").strip(),
            symbol=str(payload.get("symbol")).strip() if payload.get("symbol") is not None else None,
            market=str(payload.get("market") or "unknown").strip() or "unknown",
            display_name=str(payload.get("display_name")).strip() if payload.get("display_name") is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "id": self.id,
            "symbol": self.symbol,
            "market": self.market,
            "display_name": self.display_name,
        }


@dataclass(slots=True)
class AiEvidenceItem:
    key: str
    criticality: AiEvidenceCriticality
    status: AiEvidenceStatus
    value_class: str
    source_ref_ids: list[str] = field(default_factory=list)
    as_of: str | None = None
    freshness_class: AiEvidenceFreshnessClass = AiEvidenceFreshnessClass.UNKNOWN
    reason_codes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: Any) -> "AiEvidenceItem":
        payload = _coerce_mapping(value)
        return cls(
            key=str(payload.get("key") or "").strip(),
            criticality=_coerce_enum(AiEvidenceCriticality, payload.get("criticality"), AiEvidenceCriticality.OPTIONAL),
            status=_coerce_enum(AiEvidenceStatus, payload.get("status"), AiEvidenceStatus.MISSING),
            value_class=str(payload.get("value_class") or "").strip(),
            source_ref_ids=_coerce_string_list(payload.get("source_ref_ids")),
            as_of=str(payload.get("as_of")).strip() if payload.get("as_of") is not None else None,
            freshness_class=_coerce_enum(
                AiEvidenceFreshnessClass,
                payload.get("freshness_class"),
                AiEvidenceFreshnessClass.UNKNOWN,
            ),
            reason_codes=_coerce_string_list(payload.get("reason_codes")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "criticality": self.criticality.value,
            "status": self.status.value,
            "value_class": self.value_class,
            "source_ref_ids": list(self.source_ref_ids),
            "as_of": self.as_of,
            "freshness_class": self.freshness_class.value,
            "reason_codes": list(self.reason_codes),
        }


@dataclass(slots=True)
class AiEvidenceSourceRef:
    source_ref_id: str
    provider: str
    category: str
    source_class: AiEvidenceSourceClass
    cache_hit: bool | None = None
    provider_usage_event_ids: list[str] = field(default_factory=list)
    sanitized_reason_code: str | None = None
    raw_payload_stored: bool = False

    @classmethod
    def from_dict(cls, value: Any) -> "AiEvidenceSourceRef":
        payload = _coerce_mapping(value)
        return cls(
            source_ref_id=str(payload.get("source_ref_id") or "").strip(),
            provider=str(payload.get("provider") or "").strip(),
            category=str(payload.get("category") or "").strip(),
            source_class=_coerce_enum(AiEvidenceSourceClass, payload.get("source_class"), AiEvidenceSourceClass.LOCAL),
            cache_hit=bool(payload["cache_hit"]) if payload.get("cache_hit") is not None else None,
            provider_usage_event_ids=_coerce_string_list(payload.get("provider_usage_event_ids")),
            sanitized_reason_code=str(payload.get("sanitized_reason_code")).strip()
            if payload.get("sanitized_reason_code") is not None
            else None,
            raw_payload_stored=bool(payload.get("raw_payload_stored")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_ref_id": self.source_ref_id,
            "provider": self.provider,
            "category": self.category,
            "source_class": self.source_class.value,
            "cache_hit": self.cache_hit,
            "provider_usage_event_ids": list(self.provider_usage_event_ids),
            "sanitized_reason_code": self.sanitized_reason_code,
            "raw_payload_stored": self.raw_payload_stored,
        }


@dataclass(slots=True)
class AiExplainableFact:
    fact_id: str
    statement: str
    source_ref_ids: list[str] = field(default_factory=list)
    criticality: AiEvidenceCriticality = AiEvidenceCriticality.IMPORTANT
    confidence_class: str = "medium"
    user_visible: bool = True

    @classmethod
    def from_dict(cls, value: Any) -> "AiExplainableFact":
        payload = _coerce_mapping(value)
        return cls(
            fact_id=str(payload.get("fact_id") or "").strip(),
            statement=str(payload.get("statement") or "").strip(),
            source_ref_ids=_coerce_string_list(payload.get("source_ref_ids")),
            criticality=_coerce_enum(AiEvidenceCriticality, payload.get("criticality"), AiEvidenceCriticality.IMPORTANT),
            confidence_class=str(payload.get("confidence_class") or "medium").strip() or "medium",
            user_visible=bool(payload.get("user_visible", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "statement": self.statement,
            "source_ref_ids": list(self.source_ref_ids),
            "criticality": self.criticality.value,
            "confidence_class": self.confidence_class,
            "user_visible": self.user_visible,
        }


@dataclass(slots=True)
class AiEvidenceConfidenceCap:
    value: int
    policy_version: str = AI_EVIDENCE_CONFIDENCE_POLICY_VERSION
    reason_codes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: Any) -> "AiEvidenceConfidenceCap":
        payload = _coerce_mapping(value)
        raw_value = payload.get("value", 100)
        try:
            confidence_value = int(raw_value)
        except (TypeError, ValueError):
            confidence_value = 100
        return cls(
            value=max(0, min(100, confidence_value)),
            policy_version=str(payload.get("policy_version") or AI_EVIDENCE_CONFIDENCE_POLICY_VERSION).strip(),
            reason_codes=_coerce_string_list(payload.get("reason_codes")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "policy_version": self.policy_version,
            "reason_codes": list(self.reason_codes),
        }


@dataclass(slots=True)
class AiEvidencePacket:
    engine: AiEvidenceEngine
    entity: AiEvidenceEntity
    run_id: str
    evidence_version: str
    required_evidence: list[AiEvidenceItem] = field(default_factory=list)
    optional_evidence: list[AiEvidenceItem] = field(default_factory=list)
    freshness: dict[str, Any] = field(default_factory=dict)
    quality_flags: list[str] = field(default_factory=list)
    decision_status: AiEvidenceDecisionStatus = AiEvidenceDecisionStatus.ALLOWED
    confidence_cap: AiEvidenceConfidenceCap = field(default_factory=lambda: AiEvidenceConfidenceCap(value=100))
    source_refs: list[AiEvidenceSourceRef] = field(default_factory=list)
    explainable_facts: list[AiExplainableFact] = field(default_factory=list)
    admin_diagnostics: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: Any) -> "AiEvidencePacket":
        payload = _coerce_mapping(value)
        return cls(
            engine=_coerce_enum(AiEvidenceEngine, payload.get("engine"), AiEvidenceEngine.ANALYSIS),
            entity=AiEvidenceEntity.from_dict(payload.get("entity")),
            run_id=str(payload.get("run_id") or "").strip(),
            evidence_version=str(payload.get("evidence_version") or AI_EVIDENCE_PACKET_VERSION).strip()
            or AI_EVIDENCE_PACKET_VERSION,
            required_evidence=[AiEvidenceItem.from_dict(item) for item in payload.get("required_evidence") or []],
            optional_evidence=[AiEvidenceItem.from_dict(item) for item in payload.get("optional_evidence") or []],
            freshness=_deep_plain(_coerce_mapping(payload.get("freshness"))),
            quality_flags=_coerce_string_list(payload.get("quality_flags")),
            decision_status=_coerce_enum(
                AiEvidenceDecisionStatus,
                payload.get("decision_status"),
                AiEvidenceDecisionStatus.ALLOWED,
            ),
            confidence_cap=AiEvidenceConfidenceCap.from_dict(payload.get("confidence_cap")),
            source_refs=[AiEvidenceSourceRef.from_dict(item) for item in payload.get("source_refs") or []],
            explainable_facts=[AiExplainableFact.from_dict(item) for item in payload.get("explainable_facts") or []],
            admin_diagnostics=_deep_plain(_coerce_mapping(payload.get("admin_diagnostics"))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine.value,
            "entity": self.entity.to_dict(),
            "run_id": self.run_id,
            "evidence_version": self.evidence_version,
            "required_evidence": [item.to_dict() for item in self.required_evidence],
            "optional_evidence": [item.to_dict() for item in self.optional_evidence],
            "freshness": _deep_plain(self.freshness),
            "quality_flags": list(self.quality_flags),
            "decision_status": self.decision_status.value,
            "confidence_cap": self.confidence_cap.to_dict(),
            "source_refs": [item.to_dict() for item in self.source_refs],
            "explainable_facts": [item.to_dict() for item in self.explainable_facts],
            "admin_diagnostics": _deep_plain(self.admin_diagnostics),
        }


@dataclass(slots=True)
class AiEvidencePolicyResult:
    decision_status: AiEvidenceDecisionStatus
    confidence_cap: AiEvidenceConfidenceCap
    quality_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_status": self.decision_status.value,
            "confidence_cap": self.confidence_cap.to_dict(),
            "quality_flags": list(self.quality_flags),
        }


def coerce_ai_evidence_packet(value: AiEvidencePacket | Mapping[str, Any]) -> AiEvidencePacket:
    if isinstance(value, AiEvidencePacket):
        return value
    return AiEvidencePacket.from_dict(value)


def _append_unique(target: list[str], value: str) -> None:
    text = str(value or "").strip()
    if text and text not in target:
        target.append(text)


def _required_source_classes(packet: AiEvidencePacket, item: AiEvidenceItem) -> list[AiEvidenceSourceClass]:
    source_map = {source.source_ref_id: source for source in packet.source_refs}
    classes: list[AiEvidenceSourceClass] = []
    for source_ref_id in item.source_ref_ids:
        source = source_map.get(source_ref_id)
        if source is not None and source.source_class not in classes:
            classes.append(source.source_class)
    return classes


def _decision_rank(value: AiEvidenceDecisionStatus) -> int:
    return {
        AiEvidenceDecisionStatus.FORBIDDEN: 0,
        AiEvidenceDecisionStatus.CAUTION: 1,
        AiEvidenceDecisionStatus.ALLOWED: 2,
    }[value]


def evaluate_evidence_policy(value: AiEvidencePacket | Mapping[str, Any]) -> AiEvidencePolicyResult:
    packet = coerce_ai_evidence_packet(value)
    current_cap = max(0, min(100, int(packet.confidence_cap.value)))
    decision_status = AiEvidenceDecisionStatus.ALLOWED
    cap_reason_codes: list[str] = []
    quality_flags = list(packet.quality_flags)

    has_missing_required = False
    has_stale_required = False
    severe_stale_required = False
    has_fixture_or_synthetic_required = False
    has_conflicting_required = False
    severe_conflicting_required = False

    for item in packet.required_evidence:
        source_classes = _required_source_classes(packet, item)
        reason_text = " ".join(item.reason_codes).lower()

        if item.status is AiEvidenceStatus.MISSING or item.freshness_class is AiEvidenceFreshnessClass.MISSING:
            has_missing_required = True
        if item.status is AiEvidenceStatus.STALE or item.freshness_class is AiEvidenceFreshnessClass.STALE:
            has_stale_required = True
            if not item.as_of or "severe" in reason_text or "no_usable_as_of" in reason_text:
                severe_stale_required = True
        if item.status is AiEvidenceStatus.CONFLICTING:
            has_conflicting_required = True
            if "action" in reason_text and "risk" in reason_text or "severe" in reason_text:
                severe_conflicting_required = True
        if (
            item.status in {AiEvidenceStatus.FIXTURE, AiEvidenceStatus.SYNTHETIC}
            or item.freshness_class in {AiEvidenceFreshnessClass.FIXTURE, AiEvidenceFreshnessClass.SYNTHETIC}
            or any(source_class in {AiEvidenceSourceClass.FIXTURE, AiEvidenceSourceClass.SYNTHETIC} for source_class in source_classes)
        ):
            has_fixture_or_synthetic_required = True

    flag_text = " ".join(quality_flags).lower()
    if "required_data_missing" in quality_flags or "missing required" in flag_text:
        has_missing_required = True
    if "stale_required_data" in quality_flags:
        has_stale_required = True
    if "conflicting_evidence" in quality_flags:
        has_conflicting_required = True
    if "severe_conflicting_evidence" in quality_flags:
        has_conflicting_required = True
        severe_conflicting_required = True
    if "fixture_data" in quality_flags or "synthetic_data" in quality_flags:
        has_fixture_or_synthetic_required = True

    if has_missing_required:
        decision_status = AiEvidenceDecisionStatus.FORBIDDEN
        current_cap = min(current_cap, 40)
        _append_unique(cap_reason_codes, "required_data_missing")
        _append_unique(quality_flags, "required_data_missing")
    if has_stale_required:
        if _decision_rank(decision_status) > _decision_rank(AiEvidenceDecisionStatus.CAUTION):
            decision_status = AiEvidenceDecisionStatus.CAUTION
        current_cap = min(current_cap, 60 if severe_stale_required else 75)
        _append_unique(cap_reason_codes, "stale_required_data")
        _append_unique(quality_flags, "stale_required_data")
    if has_fixture_or_synthetic_required:
        decision_status = AiEvidenceDecisionStatus.FORBIDDEN
        current_cap = min(current_cap, 35)
        _append_unique(cap_reason_codes, "fixture_or_synthetic_required_evidence")
        _append_unique(quality_flags, "fixture_data")
    if has_conflicting_required:
        if _decision_rank(decision_status) > _decision_rank(AiEvidenceDecisionStatus.CAUTION):
            decision_status = AiEvidenceDecisionStatus.CAUTION
        current_cap = min(current_cap, 45 if severe_conflicting_required else 60)
        _append_unique(cap_reason_codes, "conflicting_evidence")
        _append_unique(quality_flags, "conflicting_evidence")

    return AiEvidencePolicyResult(
        decision_status=decision_status,
        confidence_cap=AiEvidenceConfidenceCap(
            value=max(0, min(100, current_cap)),
            policy_version=AI_EVIDENCE_CONFIDENCE_POLICY_VERSION,
            reason_codes=cap_reason_codes,
        ),
        quality_flags=quality_flags,
    )


__all__ = [
    "AI_EVIDENCE_CONFIDENCE_POLICY_VERSION",
    "AI_EVIDENCE_PACKET_VERSION",
    "AiEvidenceConfidenceCap",
    "AiEvidenceCriticality",
    "AiEvidenceDecisionStatus",
    "AiEvidenceEngine",
    "AiEvidenceEntity",
    "AiEvidenceFreshnessClass",
    "AiEvidenceItem",
    "AiEvidencePacket",
    "AiEvidencePolicyResult",
    "AiEvidenceSourceClass",
    "AiEvidenceSourceRef",
    "AiEvidenceStatus",
    "AiExplainableFact",
    "coerce_ai_evidence_packet",
    "evaluate_evidence_policy",
]
