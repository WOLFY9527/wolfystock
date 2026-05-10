# -*- coding: utf-8 -*-
"""Inert data-quality required-field contracts and policy helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


CONTRACT_VERSION = "data_quality_contract_v1"


class DataQualityClass(str, Enum):
    FRESH = "fresh"
    DELAYED_USABLE = "delayed_usable"
    STALE = "stale"
    MISSING = "missing"
    FIXTURE = "fixture"
    SYNTHETIC = "synthetic"
    FALLBACK = "fallback"
    LOCAL_HISTORICAL = "local_historical"
    UNKNOWN = "unknown"


class DataQualityStatus(str, Enum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    STALE = "stale"
    MISSING = "missing"
    CONFLICTING = "conflicting"
    BLOCKED = "blocked"


class EvidenceCriticality(str, Enum):
    REQUIRED = "required"
    IMPORTANT = "important"
    OPTIONAL = "optional"


class EngineId(str, Enum):
    SCANNER = "scanner"
    ROTATION = "rotation"
    OPTIONS = "options"
    BACKTEST = "backtest"
    AI_ANALYSIS = "ai_analysis"
    PORTFOLIO_RISK = "portfolio_risk"


def _coerce_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [text for item in value if (text := str(item or "").strip())]


def _coerce_enum(enum_cls: type[Enum], value: Any, default: Enum) -> Enum:
    if isinstance(value, enum_cls):
        return value
    normalized = str(value or "").strip()
    for item in enum_cls:
        if item.value == normalized:
            return item
    return default


@dataclass(slots=True)
class DataQualityContractField:
    engine: EngineId
    field_key: str
    criticality: EvidenceCriticality
    data_quality_class: DataQualityClass
    status: DataQualityStatus
    as_of: str | None = None
    source_ref_ids: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    decision_grade: bool = False
    confidence_cap_effect: str = "cap_or_block_pending_classification"

    @classmethod
    def from_dict(cls, value: Any) -> "DataQualityContractField":
        payload = _coerce_mapping(value)
        return cls(
            engine=_coerce_enum(EngineId, payload.get("engine"), EngineId.AI_ANALYSIS),
            field_key=str(payload.get("field_key") or "").strip(),
            criticality=_coerce_enum(EvidenceCriticality, payload.get("criticality"), EvidenceCriticality.OPTIONAL),
            data_quality_class=_coerce_enum(
                DataQualityClass,
                payload.get("data_quality_class"),
                DataQualityClass.UNKNOWN,
            ),
            status=_coerce_enum(DataQualityStatus, payload.get("status"), DataQualityStatus.BLOCKED),
            as_of=str(payload.get("as_of")).strip() if payload.get("as_of") is not None else None,
            source_ref_ids=_coerce_string_list(payload.get("source_ref_ids")),
            reason_codes=_coerce_string_list(payload.get("reason_codes")),
            decision_grade=bool(payload.get("decision_grade")),
            confidence_cap_effect=str(payload.get("confidence_cap_effect") or "cap_or_block_pending_classification").strip()
            or "cap_or_block_pending_classification",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine.value,
            "field_key": self.field_key,
            "criticality": self.criticality.value,
            "data_quality_class": self.data_quality_class.value,
            "status": self.status.value,
            "as_of": self.as_of,
            "source_ref_ids": list(self.source_ref_ids),
            "reason_codes": list(self.reason_codes),
            "decision_grade": self.decision_grade,
            "confidence_cap_effect": self.confidence_cap_effect,
        }


@dataclass(slots=True)
class SourceRefPolicy:
    source_ref_id: str
    source_class: str
    provider: str
    raw_payload_stored: bool = False
    sanitized_reason_code: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: Any) -> "SourceRefPolicy":
        payload = _coerce_mapping(value)
        extra = {
            str(key): item
            for key, item in payload.items()
            if key not in {"source_ref_id", "source_class", "provider", "raw_payload_stored", "sanitized_reason_code"}
        }
        return cls(
            source_ref_id=str(payload.get("source_ref_id") or "").strip(),
            source_class=str(payload.get("source_class") or "").strip(),
            provider=str(payload.get("provider") or "").strip(),
            raw_payload_stored=bool(payload.get("raw_payload_stored")),
            sanitized_reason_code=str(payload.get("sanitized_reason_code")).strip()
            if payload.get("sanitized_reason_code") is not None
            else None,
            extra=extra,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "source_ref_id": self.source_ref_id,
            "source_class": self.source_class,
            "provider": self.provider,
            "raw_payload_stored": self.raw_payload_stored,
            "sanitized_reason_code": self.sanitized_reason_code,
        }
        payload.update(self.extra)
        return payload


@dataclass(slots=True)
class EngineRequiredFieldContract:
    engine: EngineId
    contract_version: str = CONTRACT_VERSION
    required_fields: list[DataQualityContractField] = field(default_factory=list)
    important_fields: list[DataQualityContractField] = field(default_factory=list)
    optional_fields: list[DataQualityContractField] = field(default_factory=list)
    protected_behavior_notes: list[str] = field(default_factory=list)
    source_ref_policies: list[SourceRefPolicy | Mapping[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: Any) -> "EngineRequiredFieldContract":
        payload = _coerce_mapping(value)
        return cls(
            engine=_coerce_enum(EngineId, payload.get("engine"), EngineId.AI_ANALYSIS),
            contract_version=str(payload.get("contract_version") or CONTRACT_VERSION).strip() or CONTRACT_VERSION,
            required_fields=[DataQualityContractField.from_dict(item) for item in payload.get("required_fields") or []],
            important_fields=[DataQualityContractField.from_dict(item) for item in payload.get("important_fields") or []],
            optional_fields=[DataQualityContractField.from_dict(item) for item in payload.get("optional_fields") or []],
            protected_behavior_notes=_coerce_string_list(payload.get("protected_behavior_notes")),
            source_ref_policies=[SourceRefPolicy.from_dict(item) for item in payload.get("source_ref_policies") or []],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine.value,
            "contract_version": self.contract_version,
            "required_fields": [item.to_dict() for item in self.required_fields],
            "important_fields": [item.to_dict() for item in self.important_fields],
            "optional_fields": [item.to_dict() for item in self.optional_fields],
            "protected_behavior_notes": list(self.protected_behavior_notes),
            "source_ref_policies": [
                item.to_dict() if hasattr(item, "to_dict") else dict(item)
                for item in self.source_ref_policies
            ],
        }


def coerce_engine_required_field_contract(
    value: EngineRequiredFieldContract | Mapping[str, Any],
) -> EngineRequiredFieldContract:
    if isinstance(value, EngineRequiredFieldContract):
        return value
    return EngineRequiredFieldContract.from_dict(value)


_LOCAL_HISTORICAL_DECISION_FIELDS = {
    EngineId.SCANNER: {"ohlcv.window"},
    EngineId.BACKTEST: {
        "local_bars.coverage",
        "corporate_actions.coverage",
        "rule_engine.dataset_version",
    },
}
_STALE_CAP_ALLOWED_FIELDS = {
    EngineId.ROTATION: {
        "proxy.coverage",
        "benchmark_proxy.ohlcv",
        "breadth.coverage",
        "volume.baseline",
        "flow.evidence_boundary",
    },
    EngineId.OPTIONS: {"provider.freshness"},
    EngineId.AI_ANALYSIS: {"freshness.matrix"},
    EngineId.PORTFOLIO_RISK: {"fx.freshness", "sync_import.status"},
}
_FALLBACK_CAP_ALLOWED_FIELDS = {
    EngineId.ROTATION: {
        "proxy.coverage",
        "benchmark_proxy.ohlcv",
        "breadth.coverage",
        "volume.baseline",
        "flow.evidence_boundary",
    },
    EngineId.OPTIONS: {"provider.freshness"},
    EngineId.AI_ANALYSIS: {"freshness.matrix", "source.refs", "quality.flags"},
    EngineId.PORTFOLIO_RISK: {"fx.freshness", "sync_import.status"},
}


def evaluate_confidence_cap_effect(value: DataQualityContractField | Mapping[str, Any]) -> str:
    field = value if isinstance(value, DataQualityContractField) else DataQualityContractField.from_dict(value)

    if field.criticality is EvidenceCriticality.OPTIONAL and (
        field.data_quality_class is DataQualityClass.MISSING or field.status is DataQualityStatus.MISSING
    ):
        return "visible_gap_only"
    if field.criticality is EvidenceCriticality.OPTIONAL:
        return "none"

    if field.data_quality_class in {DataQualityClass.MISSING, DataQualityClass.FIXTURE, DataQualityClass.SYNTHETIC}:
        return "block_decision_grade"
    if field.status is DataQualityStatus.MISSING:
        return "block_decision_grade"
    if field.data_quality_class is DataQualityClass.UNKNOWN:
        return "cap_or_block_pending_classification"
    if field.data_quality_class is DataQualityClass.LOCAL_HISTORICAL:
        if field.field_key in _LOCAL_HISTORICAL_DECISION_FIELDS.get(field.engine, set()):
            return "allow_local_historical"
        return "block_decision_grade"
    if field.data_quality_class is DataQualityClass.FALLBACK:
        if field.field_key in _FALLBACK_CAP_ALLOWED_FIELDS.get(field.engine, set()):
            return "cap_decision_grade"
        return "block_decision_grade"
    if field.data_quality_class is DataQualityClass.STALE or field.status is DataQualityStatus.STALE:
        if field.field_key in _STALE_CAP_ALLOWED_FIELDS.get(field.engine, set()):
            return "cap_decision_grade"
        return "block_decision_grade"
    if field.data_quality_class is DataQualityClass.DELAYED_USABLE:
        return "cap_decision_grade"
    if field.status is DataQualityStatus.CONFLICTING:
        return "cap_decision_grade"
    if field.status in {DataQualityStatus.PARTIAL, DataQualityStatus.BLOCKED}:
        return "cap_decision_grade" if field.field_key in _FALLBACK_CAP_ALLOWED_FIELDS.get(field.engine, set()) else "block_decision_grade"
    return "none"


def _unknown_field(engine: EngineId, field_key: str, criticality: EvidenceCriticality) -> DataQualityContractField:
    effect = "visible_gap_only" if criticality is EvidenceCriticality.OPTIONAL else "cap_or_block_pending_classification"
    return DataQualityContractField(
        engine=engine,
        field_key=field_key,
        criticality=criticality,
        data_quality_class=DataQualityClass.UNKNOWN,
        status=DataQualityStatus.BLOCKED,
        as_of=None,
        source_ref_ids=[],
        reason_codes=["unclassified_field"],
        decision_grade=False,
        confidence_cap_effect=effect,
    )


_CONTRACT_DEFINITIONS: dict[EngineId, dict[str, Any]] = {
    EngineId.SCANNER: {
        "required": [
            "universe.version",
            "quote.price",
            "ohlcv.window",
            "liquidity.amount",
            "score.component_inputs",
            "freshness.quote",
            "run.id",
        ],
        "important": ["coverage.summary"],
        "optional": ["news.context"],
        "notes": [
            "Inert registry only; no scanner scoring, selection, thresholds, ranking, or provider runtime order changes.",
        ],
    },
    EngineId.ROTATION: {
        "required": [
            "taxonomy.version",
            "proxy.coverage",
            "benchmark_proxy.ohlcv",
            "breadth.coverage",
            "volume.baseline",
            "flow.evidence_boundary",
        ],
        "important": ["benchmark.context"],
        "optional": ["actual_flow.provider"],
        "notes": [
            "Proxy-backed rotation evidence must not be upgraded into actual fund-flow claims.",
        ],
    },
    EngineId.OPTIONS: {
        "required": [
            "underlying.quote",
            "chain.snapshot",
            "contract.identity",
            "quote.bid_ask_mid",
            "iv.greeks",
            "liquidity.oi_volume",
            "event.calendar",
            "provider.freshness",
        ],
        "important": ["strategy.context"],
        "optional": ["iv.surface"],
        "notes": [
            "Fixture or synthetic required evidence must remain non-decision-grade; no recommendation policy changes.",
        ],
    },
    EngineId.BACKTEST: {
        "required": [
            "local_bars.coverage",
            "adjusted_data.policy",
            "corporate_actions.coverage",
            "trading_calendar.policy",
            "cost_fill.model",
            "rule_engine.dataset_version",
        ],
        "important": ["universe.snapshot"],
        "optional": ["factor.attribution"],
        "notes": [
            "Backtest contracts are offline-only and must not introduce live provider calls or math changes.",
        ],
    },
    EngineId.AI_ANALYSIS: {
        "required": [
            "evidence.packet",
            "source.refs",
            "freshness.matrix",
            "quality.flags",
            "confidence.cap",
            "explainable.facts",
        ],
        "important": ["decision.status"],
        "optional": ["news.context"],
        "notes": [
            "AI analysis contracts are additive metadata only and must not alter prompts, routing, fallback, retry, or weighting.",
        ],
    },
    EngineId.PORTFOLIO_RISK: {
        "required": [
            "holdings.lineage",
            "cash.ledger",
            "transactions.lineage",
            "fx.freshness",
            "cost_basis.method",
            "source.authority",
            "sync_import.status",
        ],
        "important": ["valuation.snapshot"],
        "optional": ["stress.scenarios"],
        "notes": [
            "Portfolio/risk contracts are metadata only and must not alter accounting, FX, sync, import, or replay semantics.",
        ],
    },
}


def get_engine_required_field_contract(engine: EngineId | str) -> EngineRequiredFieldContract:
    resolved_engine = _coerce_enum(EngineId, engine, EngineId.AI_ANALYSIS)
    definition = _CONTRACT_DEFINITIONS.get(resolved_engine)
    if definition is None:
        raise ValueError(f"unsupported engine: {engine}")
    return EngineRequiredFieldContract(
        engine=resolved_engine,
        contract_version=CONTRACT_VERSION,
        required_fields=[_unknown_field(resolved_engine, field_key, EvidenceCriticality.REQUIRED) for field_key in definition["required"]],
        important_fields=[_unknown_field(resolved_engine, field_key, EvidenceCriticality.IMPORTANT) for field_key in definition["important"]],
        optional_fields=[_unknown_field(resolved_engine, field_key, EvidenceCriticality.OPTIONAL) for field_key in definition["optional"]],
        protected_behavior_notes=list(definition["notes"]),
        source_ref_policies=[],
    )


__all__ = [
    "CONTRACT_VERSION",
    "DataQualityClass",
    "DataQualityContractField",
    "DataQualityStatus",
    "EngineId",
    "EngineRequiredFieldContract",
    "EvidenceCriticality",
    "SourceRefPolicy",
    "coerce_engine_required_field_contract",
    "evaluate_confidence_cap_effect",
    "get_engine_required_field_contract",
]
