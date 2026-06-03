# -*- coding: utf-8 -*-
"""Pure consumer-facing research-readiness projection contract."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from src.contracts.source_confidence import (
    evaluate_market_intelligence_trust,
    evaluate_score_grade_source_authority,
)


RESEARCH_READINESS_CONTRACT_VERSION = "research_readiness_v1"


class ReadinessState(str, Enum):
    READY = "ready"
    OBSERVE_ONLY = "observe_only"
    INSUFFICIENT = "insufficient"
    BLOCKED = "blocked"
    WAITING = "waiting"


class MissingEvidence(str, Enum):
    TECHNICAL = "technical"
    FUNDAMENTALS = "fundamentals"
    NEWS = "news"
    CATALYST = "catalyst"
    MACRO = "macro"
    LIQUIDITY = "liquidity"
    SOURCE_AUTHORITY = "source_authority"
    FRESHNESS = "freshness"


class SourceAuthority(str, Enum):
    SCORE_GRADE_ALLOWED = "scoreGradeAllowed"
    OBSERVATION_ONLY = "observationOnly"
    UNAVAILABLE = "unavailable"


class FreshnessFloor(str, Enum):
    FRESH = "fresh"
    DELAYED = "delayed"
    STALE = "stale"
    FALLBACK = "fallback"
    SYNTHETIC = "synthetic"
    UNKNOWN = "unknown"


class ConsumerActionBoundary(str, Enum):
    NO_ADVICE = "no_advice"
    NO_EXECUTION = "no_execution"
    NO_TRADE = "no_trade"
    OBSERVE_ONLY = "observe_only"


READINESS_STATE_VALUES = frozenset(item.value for item in ReadinessState)
MISSING_EVIDENCE_VALUES = frozenset(item.value for item in MissingEvidence)
SOURCE_AUTHORITY_VALUES = frozenset(item.value for item in SourceAuthority)
FRESHNESS_FLOOR_VALUES = frozenset(item.value for item in FreshnessFloor)
CONSUMER_ACTION_BOUNDARY_VALUES = frozenset(item.value for item in ConsumerActionBoundary)

_READY_SOURCE_TYPES = frozenset(
    {
        "score_grade",
        "official_public",
        "official_api",
        "authorized_licensed_feed",
        "official_or_authorized_licensed_feed",
        "exchange_public",
        "broker_authorized",
    }
)
_READY_SOURCE_TIERS = frozenset(
    {
        "score_grade",
        "authorized_licensed_feed",
        "official_public",
        "exchange_public",
        "broker_authorized",
    }
)
_DEGRADED_FRESHNESS = {
    "stale",
    "fallback",
    "synthetic",
    "mock",
    "unavailable",
    "error",
    "unknown",
}
_WAITING_STATES = {"waiting", "pending", "loading", "queued", "scheduled", "in_progress"}
_DOMAIN_ALIASES = {
    "technical": MissingEvidence.TECHNICAL,
    "technical_analysis": MissingEvidence.TECHNICAL,
    "technicals": MissingEvidence.TECHNICAL,
    "fundamental": MissingEvidence.FUNDAMENTALS,
    "fundamentals": MissingEvidence.FUNDAMENTALS,
    "financials": MissingEvidence.FUNDAMENTALS,
    "news": MissingEvidence.NEWS,
    "sentiment": MissingEvidence.NEWS,
    "catalyst": MissingEvidence.CATALYST,
    "catalysts": MissingEvidence.CATALYST,
    "event": MissingEvidence.CATALYST,
    "events": MissingEvidence.CATALYST,
    "macro": MissingEvidence.MACRO,
    "market": MissingEvidence.MACRO,
    "regime": MissingEvidence.MACRO,
    "liquidity": MissingEvidence.LIQUIDITY,
    "flow": MissingEvidence.LIQUIDITY,
    "source_authority": MissingEvidence.SOURCE_AUTHORITY,
    "sourceAuthority": MissingEvidence.SOURCE_AUTHORITY,
    "authority": MissingEvidence.SOURCE_AUTHORITY,
    "freshness": MissingEvidence.FRESHNESS,
}
_NEXT_EVIDENCE_COPY = {
    MissingEvidence.TECHNICAL: ("补充技术面证据", "等待技术面证据"),
    MissingEvidence.FUNDAMENTALS: ("补充基本面证据", "等待基本面证据"),
    MissingEvidence.NEWS: ("补充新闻证据", "等待新闻证据"),
    MissingEvidence.CATALYST: ("补充催化剂证据", "等待催化剂证据"),
    MissingEvidence.MACRO: ("补充宏观证据", "等待宏观证据"),
    MissingEvidence.LIQUIDITY: ("补充流动性证据", "等待流动性证据"),
    MissingEvidence.SOURCE_AUTHORITY: ("补充来源授权证据", "等待来源授权证据"),
    MissingEvidence.FRESHNESS: ("补充新鲜度证据", "等待新鲜度证据"),
}
_VERDICT_LABELS = {
    ReadinessState.READY: "研究证据可用",
    ReadinessState.OBSERVE_ONLY: "仅观察",
    ReadinessState.INSUFFICIENT: "证据不足",
    ReadinessState.BLOCKED: "研究结论受限",
    ReadinessState.WAITING: "等待证据更新",
}
_FRESHNESS_RANK = {
    FreshnessFloor.FRESH: 0,
    FreshnessFloor.DELAYED: 1,
    FreshnessFloor.STALE: 2,
    FreshnessFloor.FALLBACK: 3,
    FreshnessFloor.SYNTHETIC: 4,
    FreshnessFloor.UNKNOWN: 5,
}


@dataclass(frozen=True, slots=True)
class EvidenceCoverage:
    score_grade_count: int
    observation_only_count: int
    missing_count: int
    total_count: int

    def to_dict(self) -> dict[str, int]:
        return {
            "scoreGradeCount": self.score_grade_count,
            "observationOnlyCount": self.observation_only_count,
            "missingCount": self.missing_count,
            "totalCount": self.total_count,
        }


@dataclass(frozen=True, slots=True)
class ResearchReadinessV1:
    research_ready: bool
    readiness_state: ReadinessState
    verdict_label: str
    blocking_reasons: tuple[str, ...]
    missing_evidence: tuple[MissingEvidence, ...]
    evidence_coverage: EvidenceCoverage
    source_authority: SourceAuthority
    freshness_floor: FreshnessFloor
    consumer_action_boundary: ConsumerActionBoundary
    next_evidence_needed: tuple[str, ...]
    debug_ref: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "contractVersion": RESEARCH_READINESS_CONTRACT_VERSION,
            "researchReady": self.research_ready,
            "readinessState": self.readiness_state.value,
            "verdictLabel": self.verdict_label,
            "blockingReasons": list(self.blocking_reasons),
            "missingEvidence": [item.value for item in self.missing_evidence],
            "evidenceCoverage": self.evidence_coverage.to_dict(),
            "sourceAuthority": self.source_authority.value,
            "freshnessFloor": self.freshness_floor.value,
            "consumerActionBoundary": self.consumer_action_boundary.value,
            "nextEvidenceNeeded": list(self.next_evidence_needed),
            "debugRef": self.debug_ref,
        }


@dataclass(frozen=True, slots=True)
class _EvidencePosture:
    domain: MissingEvidence | None
    score_grade: bool
    observation_only: bool
    freshness_floor: FreshnessFloor
    reasons: tuple[str, ...]


def build_research_readiness_v1(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a fail-closed ResearchReadinessV1 projection from caller metadata."""

    payload = dict(value or {})
    data_quality = _mapping(_get(payload, "dataQualityReport", "data_quality_report"))
    required_domains = _domain_tuple(
        _first_present(
            payload,
            "requiredEvidence",
            "requiredDomains",
            "required_evidence",
            "required_domains",
        )
        or _first_present(data_quality, "requiredEvidence", "requiredDomains")
    )
    explicit_missing = _domain_tuple(
        _first_present(
            payload,
            "missingEvidence",
            "missingDomains",
            "missingRequiredDomains",
            "pendingEvidence",
        )
        or _first_present(
            data_quality,
            "missingEvidence",
            "missingDomains",
            "missingRequiredDomains",
            "missing_required_domains",
        )
    )
    evidence_items = _evidence_items(payload, data_quality)
    evidence_postures = tuple(_evidence_posture(item) for item in evidence_items)

    blocking_reasons: list[str] = []
    missing_evidence: list[MissingEvidence] = list(explicit_missing)
    for item in explicit_missing:
        _append_unique_reason(blocking_reasons, "missing_required_evidence")

    if not payload and not evidence_items:
        _append_unique_reason(blocking_reasons, "critical_metadata_missing")
        _append_missing(missing_evidence, MissingEvidence.SOURCE_AUTHORITY)
        _append_missing(missing_evidence, MissingEvidence.FRESHNESS)

    domains_from_evidence = tuple(item.domain for item in evidence_postures if item.domain is not None)
    coverage_domains = _ordered_domain_union(required_domains, explicit_missing, domains_from_evidence)
    evidence_by_domain: dict[MissingEvidence, list[_EvidencePosture]] = {}
    for posture in evidence_postures:
        if posture.domain is None:
            continue
        evidence_by_domain.setdefault(posture.domain, []).append(posture)
        for reason in posture.reasons:
            _append_unique_reason(blocking_reasons, reason)

    score_grade_count = 0
    observation_only_count = 0
    missing_count = 0
    for domain in coverage_domains:
        if domain in missing_evidence or not evidence_by_domain.get(domain):
            missing_count += 1
            _append_missing(missing_evidence, domain)
            _append_unique_reason(blocking_reasons, "missing_required_evidence")
            continue
        if any(item.score_grade for item in evidence_by_domain[domain]):
            score_grade_count += 1
        else:
            observation_only_count += 1
            _append_unique_reason(blocking_reasons, "observation_only")

    source_authority = _source_authority(
        payload=payload,
        evidence_postures=evidence_postures,
        score_grade_count=score_grade_count,
        coverage_domains=coverage_domains,
        missing_count=missing_count,
    )
    if source_authority is SourceAuthority.UNAVAILABLE:
        _append_missing(missing_evidence, MissingEvidence.SOURCE_AUTHORITY)
        _append_unique_reason(blocking_reasons, "source_authority_missing")
    elif source_authority is SourceAuthority.OBSERVATION_ONLY:
        _append_unique_reason(blocking_reasons, "source_authority_not_score_grade")

    freshness_floor = _aggregate_freshness_floor(payload, evidence_postures)
    if freshness_floor is FreshnessFloor.UNKNOWN:
        _append_missing(missing_evidence, MissingEvidence.FRESHNESS)
        _append_unique_reason(blocking_reasons, "freshness_missing")

    if _score_cap_active(payload, data_quality):
        _append_unique_reason(blocking_reasons, "score_cap_active")

    consumer_action_boundary = _consumer_action_boundary(payload)
    safety_blocked = _consumer_action_blocked(payload, consumer_action_boundary)
    if payload and _get(payload, "noAdviceBoundary", "no_advice_boundary") is not True:
        _append_unique_reason(blocking_reasons, "no_advice_boundary_missing")
        safety_blocked = True
    if safety_blocked:
        _append_unique_reason(blocking_reasons, "consumer_action_blocked")

    waiting = _is_waiting(payload, data_quality)
    if waiting:
        _append_unique_reason(blocking_reasons, "evidence_pending")

    coverage = EvidenceCoverage(
        score_grade_count=score_grade_count,
        observation_only_count=observation_only_count,
        missing_count=missing_count,
        total_count=len(coverage_domains),
    )
    state = _readiness_state(
        waiting=waiting,
        safety_blocked=safety_blocked,
        missing_evidence=missing_evidence,
        coverage=coverage,
        source_authority=source_authority,
        freshness_floor=freshness_floor,
        blocking_reasons=blocking_reasons,
    )
    readiness = ResearchReadinessV1(
        research_ready=state is ReadinessState.READY,
        readiness_state=state,
        verdict_label=_VERDICT_LABELS[state],
        blocking_reasons=tuple(blocking_reasons),
        missing_evidence=tuple(_ordered_missing(missing_evidence)),
        evidence_coverage=coverage,
        source_authority=source_authority,
        freshness_floor=freshness_floor,
        consumer_action_boundary=consumer_action_boundary,
        next_evidence_needed=tuple(_next_evidence_needed(missing_evidence, waiting=waiting)),
        debug_ref=_debug_ref(payload),
    )
    return readiness.to_dict()


def _evidence_items(payload: Mapping[str, Any], data_quality: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    for key in ("evidence", "evidenceItems", "sourceEvidence", "sources"):
        value = payload.get(key)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return tuple(item for item in value if isinstance(item, Mapping))
    value = data_quality.get("evidence")
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _evidence_posture(item: Mapping[str, Any]) -> _EvidencePosture:
    trust = evaluate_market_intelligence_trust(item)
    freshness = _freshness_floor(trust.get("freshness") or item.get("freshness"))
    degraded = _evidence_degraded(item, freshness)
    observation_only = (
        _bool(_get(item, "observationOnly", "observation_only"))
        or degraded
        or _get(item, "sourceAuthorityAllowed", "source_authority_allowed") is not True
        or _get(item, "scoreContributionAllowed", "score_contribution_allowed") is not True
    )
    authority = evaluate_score_grade_source_authority(
        source_type=_get(item, "sourceType", "source_type"),
        source_tier=_get(item, "sourceTier", "source_tier"),
        trust_level=_get(item, "trustLevel", "trust_level"),
        observation_only=observation_only,
        score_contribution_allowed=_get(item, "scoreContributionAllowed", "score_contribution_allowed") is True,
        source_authority_allowed=_get(item, "sourceAuthorityAllowed", "source_authority_allowed") is True,
        freshness=trust.get("freshness") or item.get("freshness"),
        is_fallback=_bool(_get(item, "isFallback", "is_fallback", "fallbackUsed", "fallback_used")),
        is_stale=_bool(_get(item, "isStale", "is_stale")),
        is_synthetic=_bool(_get(item, "isSynthetic", "is_synthetic")) or _is_fixture(item),
        is_unavailable=_bool(_get(item, "isUnavailable", "is_unavailable")),
        allowed_source_types=_READY_SOURCE_TYPES,
        allowed_source_tiers=_READY_SOURCE_TIERS,
    )
    reasons = list(_evidence_reasons(item, freshness=freshness, degraded=degraded))
    score_grade = bool(
        authority.allowed
        and not observation_only
        and freshness in {FreshnessFloor.FRESH, FreshnessFloor.DELAYED}
        and float(trust.get("scoreCap") or 0.0) >= 0.8
    )
    return _EvidencePosture(
        domain=_domain(_get(item, "domain", "evidenceDomain", "key", "pillar")),
        score_grade=score_grade,
        observation_only=not score_grade,
        freshness_floor=freshness,
        reasons=tuple(reasons),
    )


def _evidence_reasons(
    item: Mapping[str, Any],
    *,
    freshness: FreshnessFloor,
    degraded: bool,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if _is_public_proxy(item):
        reasons.append("public_proxy_evidence")
    if freshness is FreshnessFloor.STALE:
        reasons.append("stale_evidence")
    if freshness is FreshnessFloor.FALLBACK or _bool(_get(item, "isFallback", "is_fallback", "fallbackUsed")):
        reasons.append("fallback_evidence")
    if freshness is FreshnessFloor.SYNTHETIC or _bool(_get(item, "isSynthetic", "is_synthetic")):
        reasons.append("synthetic_evidence")
    if _is_fixture(item):
        reasons.append("fixture_evidence")
    if _bool(_get(item, "observationOnly", "observation_only")):
        reasons.append("observation_only")
    if degraded and not reasons:
        reasons.append("observation_only")
    return tuple(dict.fromkeys(reasons))


def _evidence_degraded(item: Mapping[str, Any], freshness: FreshnessFloor) -> bool:
    raw_freshness = _text(_get(item, "freshness")).lower()
    return bool(
        freshness in {FreshnessFloor.STALE, FreshnessFloor.FALLBACK, FreshnessFloor.SYNTHETIC}
        or raw_freshness in _DEGRADED_FRESHNESS
        or _is_public_proxy(item)
        or _is_fixture(item)
        or _bool(_get(item, "isFallback", "is_fallback", "fallbackUsed", "fallback_used"))
        or _bool(_get(item, "isStale", "is_stale"))
        or _bool(_get(item, "isSynthetic", "is_synthetic"))
        or _bool(_get(item, "isUnavailable", "is_unavailable"))
    )


def _source_authority(
    *,
    payload: Mapping[str, Any],
    evidence_postures: Sequence[_EvidencePosture],
    score_grade_count: int,
    coverage_domains: Sequence[MissingEvidence],
    missing_count: int,
) -> SourceAuthority:
    if (
        coverage_domains
        and score_grade_count == len(coverage_domains)
        and missing_count == 0
        and _get(payload, "sourceAuthorityAllowed", "source_authority_allowed") is True
        and _get(payload, "scoreContributionAllowed", "score_contribution_allowed") is True
    ):
        return SourceAuthority.SCORE_GRADE_ALLOWED
    if evidence_postures:
        return SourceAuthority.OBSERVATION_ONLY
    return SourceAuthority.UNAVAILABLE


def _aggregate_freshness_floor(
    payload: Mapping[str, Any],
    evidence_postures: Sequence[_EvidencePosture],
) -> FreshnessFloor:
    floors = [item.freshness_floor for item in evidence_postures]
    payload_floor = _freshness_floor(_get(payload, "freshness", "freshnessFloor"))
    if payload_floor is not FreshnessFloor.UNKNOWN:
        floors.append(payload_floor)
    if not floors:
        return FreshnessFloor.UNKNOWN
    return max(floors, key=lambda item: _FRESHNESS_RANK[item])


def _freshness_floor(value: Any) -> FreshnessFloor:
    normalized = _text(value).lower()
    if normalized in {"live", "fresh"}:
        return FreshnessFloor.FRESH
    if normalized in {"delayed", "cached", "cache", "partial"}:
        return FreshnessFloor.DELAYED
    if normalized == "stale":
        return FreshnessFloor.STALE
    if normalized == "fallback":
        return FreshnessFloor.FALLBACK
    if normalized in {"synthetic", "mock", "synthetic_delayed"}:
        return FreshnessFloor.SYNTHETIC
    return FreshnessFloor.UNKNOWN


def _readiness_state(
    *,
    waiting: bool,
    safety_blocked: bool,
    missing_evidence: Sequence[MissingEvidence],
    coverage: EvidenceCoverage,
    source_authority: SourceAuthority,
    freshness_floor: FreshnessFloor,
    blocking_reasons: Sequence[str],
) -> ReadinessState:
    if waiting:
        return ReadinessState.WAITING
    if safety_blocked:
        return ReadinessState.BLOCKED
    if missing_evidence or coverage.missing_count > 0:
        return ReadinessState.INSUFFICIENT
    if (
        coverage.total_count > 0
        and coverage.score_grade_count == coverage.total_count
        and source_authority is SourceAuthority.SCORE_GRADE_ALLOWED
        and freshness_floor in {FreshnessFloor.FRESH, FreshnessFloor.DELAYED}
        and not blocking_reasons
    ):
        return ReadinessState.READY
    if coverage.total_count > 0 or source_authority is SourceAuthority.OBSERVATION_ONLY:
        return ReadinessState.OBSERVE_ONLY
    return ReadinessState.INSUFFICIENT


def _consumer_action_boundary(payload: Mapping[str, Any]) -> ConsumerActionBoundary:
    explicit = _text(_get(payload, "consumerActionBoundary", "consumer_action_boundary")).lower()
    for item in ConsumerActionBoundary:
        if explicit == item.value:
            return item
    if _bool(_get(payload, "noTradingBoundary", "no_trading_boundary", "noTrading", "no_trading")):
        return ConsumerActionBoundary.NO_TRADE
    if _bool(_get(payload, "noOrderBoundary", "no_order_boundary", "noOrder", "no_order")):
        return ConsumerActionBoundary.NO_EXECUTION
    if _bool(_get(payload, "observationOnly", "observation_only")):
        return ConsumerActionBoundary.OBSERVE_ONLY
    return ConsumerActionBoundary.NO_ADVICE


def _consumer_action_blocked(
    payload: Mapping[str, Any],
    boundary: ConsumerActionBoundary,
) -> bool:
    return bool(
        boundary in {ConsumerActionBoundary.NO_EXECUTION, ConsumerActionBoundary.NO_TRADE}
        or _bool(_get(payload, "noTradingBoundary", "no_trading_boundary", "noTrading", "no_trading"))
        or _bool(_get(payload, "noOrderBoundary", "no_order_boundary", "noOrder", "no_order"))
    )


def _score_cap_active(payload: Mapping[str, Any], data_quality: Mapping[str, Any]) -> bool:
    for key in ("scoreCap", "confidenceCap", "confidence_cap", "scoreConfidenceCap"):
        value = _get(payload, key)
        if value is None:
            value = _get(data_quality, key)
        if value is not None and _bounded_float(value, default=1.0) < 1.0:
            return True
    score_state = _text(_get(payload, "scoreState", "score_state") or _get(data_quality, "scoreState", "score_state"))
    return score_state.lower() in {"capped", "data_insufficient", "insufficient", "blocked"}


def _is_waiting(payload: Mapping[str, Any], data_quality: Mapping[str, Any]) -> bool:
    if _domain_tuple(_get(payload, "pendingEvidence")):
        return True
    states = (
        _text(_get(payload, "processingState", "status", "state")).lower(),
        _text(_get(data_quality, "processingState", "status", "state")).lower(),
    )
    return any(state in _WAITING_STATES for state in states)


def _next_evidence_needed(
    missing_evidence: Sequence[MissingEvidence],
    *,
    waiting: bool,
) -> list[str]:
    index = 1 if waiting else 0
    return [_NEXT_EVIDENCE_COPY[item][index] for item in _ordered_missing(missing_evidence)]


def _domain_tuple(value: Any) -> tuple[MissingEvidence, ...]:
    values = value if isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray)) else (value,)
    result: list[MissingEvidence] = []
    for item in values:
        domain = _domain(item)
        if domain is not None and domain not in result:
            result.append(domain)
    return tuple(result)


def _domain(value: Any) -> MissingEvidence | None:
    normalized = _text(value)
    if not normalized:
        return None
    normalized_key = normalized.replace("-", "_").replace(".", "_")
    return _DOMAIN_ALIASES.get(normalized_key) or _DOMAIN_ALIASES.get(normalized_key.lower())


def _ordered_domain_union(*groups: Iterable[MissingEvidence]) -> tuple[MissingEvidence, ...]:
    result: list[MissingEvidence] = []
    for group in groups:
        for item in group:
            if item not in result:
                result.append(item)
    return tuple(result)


def _ordered_missing(values: Sequence[MissingEvidence]) -> list[MissingEvidence]:
    ordered = []
    for item in MissingEvidence:
        if item in values and item not in ordered:
            ordered.append(item)
    return ordered


def _append_missing(values: list[MissingEvidence], item: MissingEvidence) -> None:
    if item not in values:
        values.append(item)


def _append_unique_reason(values: list[str], reason: str) -> None:
    if reason not in values:
        values.append(reason)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _first_present(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _get(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _bounded_float(value: Any, *, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(0.0, min(1.0, number))


def _is_public_proxy(payload: Mapping[str, Any]) -> bool:
    tokens = {
        _text(_get(payload, "source", "providerId", "providerName")).lower(),
        _text(_get(payload, "sourceType", "source_type")).lower(),
        _text(_get(payload, "sourceTier", "source_tier")).lower(),
    }
    return bool(
        _bool(_get(payload, "proxyOnly", "proxy_only"))
        or any("proxy" in token for token in tokens if token)
        or "public_proxy" in tokens
        or "unofficial_proxy" in tokens
    )


def _is_fixture(payload: Mapping[str, Any]) -> bool:
    tokens = {
        _text(_get(payload, "source", "providerId", "providerName")).lower(),
        _text(_get(payload, "sourceType", "source_type")).lower(),
        _text(_get(payload, "sourceTier", "source_tier")).lower(),
        _text(_get(payload, "fixtureKind", "fixture_kind")).lower(),
    }
    return any("fixture" in token for token in tokens if token)


def _debug_ref(payload: Mapping[str, Any]) -> str:
    raw = _text(
        _get(
            payload,
            "debugRef",
            "debug_ref",
            "executionId",
            "execution_id",
            "runId",
            "run_id",
            "reportId",
            "report_id",
        )
    )
    if not raw:
        return "unavailable"
    safe_chars = []
    for char in raw[:160]:
        safe_chars.append(char if char.isalnum() or char in {":", "-", "_", ".", "/", "#"} else "_")
    return "".join(safe_chars) or "unavailable"


__all__ = [
    "CONSUMER_ACTION_BOUNDARY_VALUES",
    "FRESHNESS_FLOOR_VALUES",
    "MISSING_EVIDENCE_VALUES",
    "READINESS_STATE_VALUES",
    "RESEARCH_READINESS_CONTRACT_VERSION",
    "SOURCE_AUTHORITY_VALUES",
    "ConsumerActionBoundary",
    "EvidenceCoverage",
    "FreshnessFloor",
    "MissingEvidence",
    "ReadinessState",
    "ResearchReadinessV1",
    "SourceAuthority",
    "build_research_readiness_v1",
]
