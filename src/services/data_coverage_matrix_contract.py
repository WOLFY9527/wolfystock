# -*- coding: utf-8 -*-
"""Inert Data Coverage Matrix v1 contract helpers.

This module is intentionally pure. It models reviewed coverage metadata without
importing provider runtimes, MarketCache, API layers, env/config readers, or
storage code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


DATA_COVERAGE_MATRIX_CONTRACT_VERSION = "data_coverage_matrix_v1"
_STRONG_FRESHNESS = frozenset({"fresh", "live"})


class FreshnessState(str, Enum):
    FRESH = "fresh"
    LIVE = "live"
    DELAYED = "delayed"
    CACHED = "cached"
    STALE = "stale"
    PARTIAL = "partial"
    FALLBACK = "fallback"
    SYNTHETIC = "synthetic"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class RightToDisplay(str, Enum):
    GRANTED = "granted"
    LIMITED = "limited"
    UNAVAILABLE = "unavailable"


class ConsumerProductStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UPDATING = "UPDATING"
    DELAYED = "DELAYED"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"
    PAUSED = "PAUSED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class DataCoverageValidationIssue:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class DataCoverageValidationResult:
    is_valid: bool
    issues: tuple[DataCoverageValidationIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class ConsumerDataCoverageProjection:
    status: ConsumerProductStatus
    headline: str | None = None
    as_of: str | None = None
    observation_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "headline": self.headline,
            "asOf": self.as_of,
        }


@dataclass(frozen=True, slots=True)
class DataCoverageMatrixContract:
    contract_version: str = DATA_COVERAGE_MATRIX_CONTRACT_VERSION
    surface_id: str = ""
    route_id: str = ""
    audience: str = ""
    field_key: str = ""
    evidence_family: str = ""
    provider_id: str = ""
    provider_label: str = ""
    source_id: str = ""
    source_label: str = ""
    source_type: str = ""
    source_tier: str = ""
    as_of: str | None = None
    freshness_state: FreshnessState = FreshnessState.UNKNOWN
    is_fallback: bool = False
    is_stale: bool = False
    is_partial: bool = False
    is_synthetic: bool = False
    is_unavailable: bool = False
    source_authority_allowed: bool = False
    source_authority_specified: bool = False
    score_contribution_allowed: bool = False
    score_contribution_specified: bool = False
    authority_grant: bool = False
    authority_grant_specified: bool = False
    decision_grade: bool = False
    decision_grade_specified: bool = False
    right_to_display: RightToDisplay = RightToDisplay.UNAVAILABLE
    right_to_display_specified: bool = False
    observation_only: bool = True
    diagnostic_only: bool = True
    provider_runtime_called: bool = False
    network_calls_enabled: bool = False
    market_cache_mutation: bool = False

    @classmethod
    def from_dict(cls, value: Any) -> "DataCoverageMatrixContract":
        payload = _coerce_mapping(value)
        source_authority_specified = _contains(payload, "sourceAuthorityAllowed", "source_authority_allowed")
        score_contribution_specified = _contains(
            payload,
            "scoreContributionAllowed",
            "score_contribution_allowed",
        )
        authority_grant_specified = _contains(payload, "authorityGrant", "authority_grant")
        decision_grade_specified = _contains(payload, "decisionGrade", "decision_grade")
        right_to_display_specified = _contains(payload, "rightToDisplay", "right_to_display")
        return cls(
            contract_version=_text(
                _get(payload, "contractVersion", "contract_version"),
                default=DATA_COVERAGE_MATRIX_CONTRACT_VERSION,
            ),
            surface_id=_text(_get(payload, "surfaceId", "surface_id")),
            route_id=_text(_get(payload, "routeId", "route_id")),
            audience=_text(_get(payload, "audience")),
            field_key=_text(_get(payload, "fieldKey", "field_key")),
            evidence_family=_text(_get(payload, "evidenceFamily", "evidence_family")),
            provider_id=_text(_get(payload, "providerId", "provider_id")),
            provider_label=_text(_get(payload, "providerLabel", "provider_label")),
            source_id=_text(_get(payload, "sourceId", "source_id")),
            source_label=_text(_get(payload, "sourceLabel", "source_label")),
            source_type=_text(_get(payload, "sourceType", "source_type")),
            source_tier=_text(_get(payload, "sourceTier", "source_tier")),
            as_of=_optional_text(_get(payload, "asOf", "as_of")),
            freshness_state=_coerce_freshness_state(_get(payload, "freshnessState", "freshness_state")),
            is_fallback=_bool(_get(payload, "isFallback", "is_fallback")),
            is_stale=_bool(_get(payload, "isStale", "is_stale")),
            is_partial=_bool(_get(payload, "isPartial", "is_partial")),
            is_synthetic=_bool(_get(payload, "isSynthetic", "is_synthetic")),
            is_unavailable=_bool(_get(payload, "isUnavailable", "is_unavailable")),
            source_authority_allowed=_bool(_get(payload, "sourceAuthorityAllowed", "source_authority_allowed")),
            source_authority_specified=source_authority_specified,
            score_contribution_allowed=_bool(
                _get(payload, "scoreContributionAllowed", "score_contribution_allowed")
            ),
            score_contribution_specified=score_contribution_specified,
            authority_grant=_bool(_get(payload, "authorityGrant", "authority_grant")),
            authority_grant_specified=authority_grant_specified,
            decision_grade=_bool(_get(payload, "decisionGrade", "decision_grade")),
            decision_grade_specified=decision_grade_specified,
            right_to_display=_coerce_right_to_display(_get(payload, "rightToDisplay", "right_to_display")),
            right_to_display_specified=right_to_display_specified,
            observation_only=_bool(_get(payload, "observationOnly", "observation_only"), default=True),
            diagnostic_only=_bool(_get(payload, "diagnosticOnly", "diagnostic_only"), default=True),
            provider_runtime_called=_bool(
                _get(payload, "providerRuntimeCalled", "provider_runtime_called")
            ),
            network_calls_enabled=_bool(
                _get(payload, "networkCallsEnabled", "network_calls_enabled")
            ),
            market_cache_mutation=_bool(
                _get(payload, "marketCacheMutation", "market_cache_mutation")
            ),
        )

    def normalized(self) -> "DataCoverageMatrixContract":
        right_to_display = _normalize_right_to_display(self)
        score_contribution_allowed = _normalize_score_contribution_allowed(self, right_to_display)
        authority_grant = _normalize_authority_grant(
            self,
            right_to_display=right_to_display,
            score_contribution_allowed=score_contribution_allowed,
        )
        decision_grade = _normalize_decision_grade(
            self,
            authority_grant=authority_grant,
            score_contribution_allowed=score_contribution_allowed,
        )
        observation_only = not (
            authority_grant and decision_grade and right_to_display is RightToDisplay.GRANTED
        )
        return DataCoverageMatrixContract(
            contract_version=DATA_COVERAGE_MATRIX_CONTRACT_VERSION,
            surface_id=self.surface_id,
            route_id=self.route_id,
            audience=self.audience,
            field_key=self.field_key,
            evidence_family=self.evidence_family,
            provider_id=self.provider_id,
            provider_label=self.provider_label,
            source_id=self.source_id,
            source_label=self.source_label,
            source_type=self.source_type,
            source_tier=self.source_tier,
            as_of=self.as_of,
            freshness_state=self.freshness_state,
            is_fallback=_effective_is_fallback(self),
            is_stale=_effective_is_stale(self),
            is_partial=_effective_is_partial(self),
            is_synthetic=_effective_is_synthetic(self),
            is_unavailable=_effective_is_unavailable(self),
            source_authority_allowed=self.source_authority_allowed if self.source_authority_specified else False,
            source_authority_specified=self.source_authority_specified,
            score_contribution_allowed=score_contribution_allowed,
            score_contribution_specified=self.score_contribution_specified,
            authority_grant=authority_grant,
            authority_grant_specified=self.authority_grant_specified,
            decision_grade=decision_grade,
            decision_grade_specified=self.decision_grade_specified,
            right_to_display=right_to_display,
            right_to_display_specified=self.right_to_display_specified,
            observation_only=observation_only,
            diagnostic_only=True,
            provider_runtime_called=False,
            network_calls_enabled=False,
            market_cache_mutation=False,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "contractVersion": self.contract_version,
            "surfaceId": self.surface_id,
            "routeId": self.route_id,
            "audience": self.audience,
            "fieldKey": self.field_key,
            "evidenceFamily": self.evidence_family,
            "providerId": self.provider_id,
            "providerLabel": self.provider_label,
            "sourceId": self.source_id,
            "sourceLabel": self.source_label,
            "sourceType": self.source_type,
            "sourceTier": self.source_tier,
            "freshnessState": self.freshness_state.value,
            "isFallback": self.is_fallback,
            "isStale": self.is_stale,
            "isPartial": self.is_partial,
            "isSynthetic": self.is_synthetic,
            "isUnavailable": self.is_unavailable,
            "sourceAuthorityAllowed": self.source_authority_allowed,
            "scoreContributionAllowed": self.score_contribution_allowed,
            "authorityGrant": self.authority_grant,
            "decisionGrade": self.decision_grade,
            "observationOnly": self.observation_only,
            "rightToDisplay": self.right_to_display.value,
            "diagnosticOnly": self.diagnostic_only,
            "providerRuntimeCalled": self.provider_runtime_called,
            "networkCallsEnabled": self.network_calls_enabled,
            "marketCacheMutation": self.market_cache_mutation,
        }
        if self.as_of is not None:
            payload["asOf"] = self.as_of
        return payload


def coerce_data_coverage_matrix_contract(value: Any) -> DataCoverageMatrixContract:
    if isinstance(value, DataCoverageMatrixContract):
        return value.normalized()
    return DataCoverageMatrixContract.from_dict(value).normalized()


def validate_data_coverage_matrix_contract(
    value: DataCoverageMatrixContract | Mapping[str, Any],
) -> DataCoverageValidationResult:
    contract = value if isinstance(value, DataCoverageMatrixContract) else DataCoverageMatrixContract.from_dict(value)
    issues: list[DataCoverageValidationIssue] = []

    if contract.contract_version != DATA_COVERAGE_MATRIX_CONTRACT_VERSION:
        issues.append(
            DataCoverageValidationIssue(
                "invalid_contract_version",
                "contractVersion must stay pinned to data_coverage_matrix_v1.",
            )
        )
    if not contract.surface_id:
        issues.append(DataCoverageValidationIssue("missing_surface_id", "surfaceId is required."))
    if not contract.route_id:
        issues.append(DataCoverageValidationIssue("missing_route_id", "routeId is required."))
    if not contract.audience:
        issues.append(DataCoverageValidationIssue("missing_audience", "audience is required."))
    if not contract.field_key:
        issues.append(DataCoverageValidationIssue("missing_field_key", "fieldKey is required."))
    if not contract.evidence_family:
        issues.append(
            DataCoverageValidationIssue("missing_evidence_family", "evidenceFamily is required.")
        )
    if not contract.source_authority_specified:
        issues.append(
            DataCoverageValidationIssue(
                "missing_source_authority",
                "sourceAuthorityAllowed must be reviewed explicitly.",
            )
        )
    if not contract.score_contribution_specified:
        issues.append(
            DataCoverageValidationIssue(
                "missing_score_contribution",
                "scoreContributionAllowed must be reviewed explicitly.",
            )
        )
    if not contract.right_to_display_specified:
        issues.append(
            DataCoverageValidationIssue(
                "missing_right_to_display",
                "rightToDisplay must be reviewed explicitly.",
            )
        )
    if contract.freshness_state is FreshnessState.UNKNOWN:
        issues.append(
            DataCoverageValidationIssue(
                "unknown_freshness",
                "unknown freshness must fail closed.",
            )
        )
    if _effective_is_fallback(contract):
        issues.append(
            DataCoverageValidationIssue(
                "degraded_fallback_source",
                "fallback data cannot authorize scoring or decision-grade use.",
            )
        )
    if _effective_is_stale(contract):
        issues.append(
            DataCoverageValidationIssue(
                "degraded_stale_source",
                "stale data cannot authorize scoring or decision-grade use.",
            )
        )
    if _effective_is_partial(contract):
        issues.append(
            DataCoverageValidationIssue(
                "degraded_partial_source",
                "partial coverage cannot authorize scoring or decision-grade use.",
            )
        )
    if _effective_is_synthetic(contract):
        issues.append(
            DataCoverageValidationIssue(
                "degraded_synthetic_source",
                "synthetic data cannot authorize decision-grade use.",
            )
        )
    if _effective_is_unavailable(contract):
        issues.append(
            DataCoverageValidationIssue(
                "degraded_unavailable_source",
                "unavailable data cannot authorize display or scoring.",
            )
        )
    if contract.score_contribution_allowed and not contract.source_authority_allowed:
        issues.append(
            DataCoverageValidationIssue(
                "score_contribution_without_source_authority",
                "scoreContributionAllowed cannot be true without sourceAuthorityAllowed.",
            )
        )
    if contract.authority_grant and not _can_grant_authority(
        contract,
        right_to_display=contract.right_to_display,
        score_contribution_allowed=contract.score_contribution_allowed,
    ):
        issues.append(
            DataCoverageValidationIssue(
                "authority_grant_without_prerequisites",
                "authorityGrant requires explicit authority, explicit display right, strong freshness, and non-degraded data.",
            )
        )
    if contract.decision_grade and not _can_grant_authority(
        contract,
        right_to_display=contract.right_to_display,
        score_contribution_allowed=contract.score_contribution_allowed,
    ):
        issues.append(
            DataCoverageValidationIssue(
                "decision_grade_without_prerequisites",
                "decisionGrade requires authorityGrant and scoreContributionAllowed.",
            )
        )
    if contract.provider_runtime_called:
        issues.append(
            DataCoverageValidationIssue(
                "provider_runtime_side_effect",
                "providerRuntimeCalled must stay false for inert helpers.",
            )
        )
    if contract.network_calls_enabled:
        issues.append(
            DataCoverageValidationIssue(
                "network_calls_enabled",
                "networkCallsEnabled must stay false for inert helpers.",
            )
        )
    if contract.market_cache_mutation:
        issues.append(
            DataCoverageValidationIssue(
                "market_cache_mutation",
                "marketCacheMutation must stay false for inert helpers.",
            )
        )
    if not contract.diagnostic_only:
        issues.append(
            DataCoverageValidationIssue(
                "diagnostic_only_required",
                "diagnosticOnly must stay true until a future protected-domain task wires this contract.",
            )
        )

    return DataCoverageValidationResult(is_valid=not issues, issues=tuple(issues))


def project_consumer_data_coverage(
    value: DataCoverageMatrixContract | Mapping[str, Any],
) -> ConsumerDataCoverageProjection:
    contract = coerce_data_coverage_matrix_contract(value)

    if contract.right_to_display is RightToDisplay.UNAVAILABLE:
        if contract.is_synthetic:
            return ConsumerDataCoverageProjection(
                status=ConsumerProductStatus.INSUFFICIENT,
                headline="当前信号置信度较低，仅供观察。",
                as_of=contract.as_of,
                observation_only=True,
            )
        return ConsumerDataCoverageProjection(
            status=ConsumerProductStatus.UNAVAILABLE,
            headline="本模块暂不可用，请稍后重试。",
            as_of=contract.as_of,
            observation_only=True,
        )

    if contract.freshness_state is FreshnessState.UNKNOWN:
        return ConsumerDataCoverageProjection(
            status=ConsumerProductStatus.UPDATING,
            headline="数据更新中，稍后将自动刷新。",
            as_of=contract.as_of,
            observation_only=True,
        )
    if contract.is_fallback:
        return ConsumerDataCoverageProjection(
            status=ConsumerProductStatus.PAUSED,
            headline="部分数据暂不可用，当前评分已暂停。",
            as_of=contract.as_of,
            observation_only=True,
        )
    if contract.is_partial:
        return ConsumerDataCoverageProjection(
            status=ConsumerProductStatus.PARTIAL,
            headline="部分数据暂不可用。",
            as_of=contract.as_of,
            observation_only=True,
        )
    if contract.is_stale or contract.freshness_state in {FreshnessState.DELAYED, FreshnessState.CACHED}:
        return ConsumerDataCoverageProjection(
            status=ConsumerProductStatus.DELAYED,
            headline="已使用最近一次可用数据。",
            as_of=contract.as_of,
            observation_only=True,
        )
    if contract.observation_only:
        return ConsumerDataCoverageProjection(
            status=ConsumerProductStatus.INSUFFICIENT,
            headline="当前信号置信度较低，仅供观察。",
            as_of=contract.as_of,
            observation_only=True,
        )
    return ConsumerDataCoverageProjection(
        status=ConsumerProductStatus.AVAILABLE,
        headline=None,
        as_of=contract.as_of,
        observation_only=False,
    )


def _normalize_right_to_display(contract: DataCoverageMatrixContract) -> RightToDisplay:
    if not contract.right_to_display_specified:
        return RightToDisplay.UNAVAILABLE
    if _effective_is_synthetic(contract) or _effective_is_unavailable(contract):
        return RightToDisplay.UNAVAILABLE
    if _is_display_limited(contract):
        return RightToDisplay.LIMITED
    return contract.right_to_display


def _normalize_score_contribution_allowed(
    contract: DataCoverageMatrixContract,
    right_to_display: RightToDisplay,
) -> bool:
    if not (contract.score_contribution_specified and contract.score_contribution_allowed):
        return False
    if not contract.source_authority_allowed:
        return False
    if right_to_display is not RightToDisplay.GRANTED:
        return False
    if not _has_strong_freshness(contract):
        return False
    if _has_degraded_state(contract):
        return False
    return True


def _normalize_authority_grant(
    contract: DataCoverageMatrixContract,
    *,
    right_to_display: RightToDisplay,
    score_contribution_allowed: bool,
) -> bool:
    if not (contract.authority_grant_specified and contract.authority_grant):
        return False
    return _can_grant_authority(
        contract,
        right_to_display=right_to_display,
        score_contribution_allowed=score_contribution_allowed,
    )


def _normalize_decision_grade(
    contract: DataCoverageMatrixContract,
    *,
    authority_grant: bool,
    score_contribution_allowed: bool,
) -> bool:
    if not (contract.decision_grade_specified and contract.decision_grade):
        return False
    return authority_grant and score_contribution_allowed


def _can_grant_authority(
    contract: DataCoverageMatrixContract,
    *,
    right_to_display: RightToDisplay,
    score_contribution_allowed: bool,
) -> bool:
    return bool(
        contract.source_authority_allowed
        and score_contribution_allowed
        and right_to_display is RightToDisplay.GRANTED
        and _has_strong_freshness(contract)
        and not _has_degraded_state(contract)
    )


def _has_strong_freshness(contract: DataCoverageMatrixContract) -> bool:
    return contract.freshness_state.value in _STRONG_FRESHNESS


def _has_degraded_state(contract: DataCoverageMatrixContract) -> bool:
    return any(
        (
            _effective_is_fallback(contract),
            _effective_is_stale(contract),
            _effective_is_partial(contract),
            _effective_is_synthetic(contract),
            _effective_is_unavailable(contract),
            contract.freshness_state is FreshnessState.UNKNOWN,
        )
    )


def _is_display_limited(contract: DataCoverageMatrixContract) -> bool:
    return any(
        (
            _effective_is_fallback(contract),
            _effective_is_stale(contract),
            _effective_is_partial(contract),
            contract.freshness_state in {FreshnessState.DELAYED, FreshnessState.CACHED, FreshnessState.UNKNOWN},
        )
    )


def _effective_is_fallback(contract: DataCoverageMatrixContract) -> bool:
    return contract.is_fallback or contract.freshness_state is FreshnessState.FALLBACK


def _effective_is_stale(contract: DataCoverageMatrixContract) -> bool:
    return contract.is_stale or contract.freshness_state is FreshnessState.STALE


def _effective_is_partial(contract: DataCoverageMatrixContract) -> bool:
    return contract.is_partial or contract.freshness_state is FreshnessState.PARTIAL


def _effective_is_synthetic(contract: DataCoverageMatrixContract) -> bool:
    return contract.is_synthetic or contract.freshness_state is FreshnessState.SYNTHETIC


def _effective_is_unavailable(contract: DataCoverageMatrixContract) -> bool:
    return contract.is_unavailable or contract.freshness_state is FreshnessState.UNAVAILABLE


def _coerce_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _contains(payload: Mapping[str, Any], *keys: str) -> bool:
    return any(key in payload for key in keys)


def _get(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _text(value: Any, *, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _optional_text(value: Any) -> str | None:
    text = _text(value)
    return text or None


def _bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _coerce_freshness_state(value: Any) -> FreshnessState:
    candidate = _text(value, default=FreshnessState.UNKNOWN.value).lower()
    for freshness in FreshnessState:
        if freshness.value == candidate:
            return freshness
    return FreshnessState.UNKNOWN


def _coerce_right_to_display(value: Any) -> RightToDisplay:
    candidate = _text(value, default=RightToDisplay.UNAVAILABLE.value).lower()
    for state in RightToDisplay:
        if state.value == candidate:
            return state
    return RightToDisplay.UNAVAILABLE
