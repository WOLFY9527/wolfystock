# -*- coding: utf-8 -*-
"""Inert source-confidence and provider-capability DTO contracts.

The helpers in this module are pure metadata utilities. They do not import
provider clients, read credentials, call networks, mutate MarketCache, or alter
runtime provider ordering.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Protocol


SOURCE_CONFIDENCE_CONTRACT_VERSION = "source_confidence_contract_v1"
STRONG_FRESHNESS_VALUES = {"fresh", "live"}


class SourceFreshness(str, Enum):
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


class SupportsSourceConfidence(Protocol):
    """Protocol for DTOs that can expose source-confidence metadata."""

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable source-confidence payload."""


@dataclass(frozen=True, slots=True)
class SourceConfidenceContract:
    source: str
    source_label: str
    as_of: str | None = None
    freshness: SourceFreshness = SourceFreshness.UNKNOWN
    is_fallback: bool = False
    is_stale: bool = False
    is_partial: bool = False
    is_synthetic: bool = False
    is_unavailable: bool = False
    confidence_weight: float = 0.0
    coverage: float | None = None
    degradation_reason: str | None = None
    cap_reason: str | None = None

    @classmethod
    def from_dict(cls, value: Any) -> "SourceConfidenceContract":
        payload = _coerce_mapping(value)
        return cls(
            source=_text(_get(payload, "source")),
            source_label=_text(_get(payload, "source_label", "sourceLabel")),
            as_of=_optional_text(_get(payload, "as_of", "asOf")),
            freshness=_coerce_freshness(_get(payload, "freshness")),
            is_fallback=_bool(_get(payload, "is_fallback", "isFallback")),
            is_stale=_bool(_get(payload, "is_stale", "isStale")),
            is_partial=_bool(_get(payload, "is_partial", "isPartial")),
            is_synthetic=_bool(_get(payload, "is_synthetic", "isSynthetic")),
            is_unavailable=_bool(_get(payload, "is_unavailable", "isUnavailable")),
            confidence_weight=_float(
                _get(payload, "confidence_weight", "confidenceWeight"),
                default=0.0,
            ),
            coverage=_optional_float(_get(payload, "coverage")),
            degradation_reason=_optional_text(_get(payload, "degradation_reason", "degradationReason")),
            cap_reason=_optional_text(_get(payload, "cap_reason", "capReason")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "sourceLabel": self.source_label,
            "asOf": self.as_of,
            "freshness": self.freshness.value,
            "isFallback": self.is_fallback,
            "isStale": self.is_stale,
            "isPartial": self.is_partial,
            "isSynthetic": self.is_synthetic,
            "isUnavailable": self.is_unavailable,
            "confidenceWeight": self.confidence_weight,
            "coverage": self.coverage,
            "degradationReason": self.degradation_reason,
            "capReason": self.cap_reason,
        }


@dataclass(frozen=True, slots=True)
class ProviderCapabilityContract:
    provider_id: str
    source: str
    source_label: str
    domains: tuple[str, ...] = ()
    markets: tuple[str, ...] = ()
    freshness_cap: SourceFreshness = SourceFreshness.UNKNOWN
    live_eligible: bool = False
    delayed_eligible: bool = False
    fallback_eligible: bool = False
    synthetic_eligible: bool = False
    confidence_weight_cap: float = 1.0
    coverage: float | None = None
    cap_reason: str | None = None

    @classmethod
    def from_dict(cls, value: Any) -> "ProviderCapabilityContract":
        payload = _coerce_mapping(value)
        return cls(
            provider_id=_text(_get(payload, "provider_id", "providerId")),
            source=_text(_get(payload, "source")),
            source_label=_text(_get(payload, "source_label", "sourceLabel")),
            domains=_string_tuple(_get(payload, "domains")),
            markets=_string_tuple(_get(payload, "markets")),
            freshness_cap=_coerce_freshness(_get(payload, "freshness_cap", "freshnessCap")),
            live_eligible=_bool(_get(payload, "live_eligible", "liveEligible")),
            delayed_eligible=_bool(_get(payload, "delayed_eligible", "delayedEligible")),
            fallback_eligible=_bool(_get(payload, "fallback_eligible", "fallbackEligible")),
            synthetic_eligible=_bool(_get(payload, "synthetic_eligible", "syntheticEligible")),
            confidence_weight_cap=_bounded_float(
                _get(payload, "confidence_weight_cap", "confidenceWeightCap"),
                default=1.0,
            ),
            coverage=_optional_bounded_float(_get(payload, "coverage")),
            cap_reason=_optional_text(_get(payload, "cap_reason", "capReason")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "providerId": self.provider_id,
            "source": self.source,
            "sourceLabel": self.source_label,
            "domains": list(self.domains),
            "markets": list(self.markets),
            "freshnessCap": self.freshness_cap.value,
            "liveEligible": self.live_eligible,
            "delayedEligible": self.delayed_eligible,
            "fallbackEligible": self.fallback_eligible,
            "syntheticEligible": self.synthetic_eligible,
            "confidenceWeightCap": self.confidence_weight_cap,
            "coverage": self.coverage,
            "capReason": self.cap_reason,
        }


@dataclass(frozen=True, slots=True)
class ProviderCapabilitySupportContract:
    provider_name: str
    provider_id: str
    capability: str
    source_type: str
    source_tier: str
    trust_level: str
    freshness_expectation: str
    observation_only: bool = False
    score_contribution_allowed: bool = False
    paid_data_likely_required: bool = False
    key_required: bool = False
    cache_required: bool = False
    background_refresh_recommended: bool = False
    degradation_reason: str | None = None
    missing_provider_reason: str | None = None

    @classmethod
    def from_dict(cls, value: Any) -> "ProviderCapabilitySupportContract":
        payload = _coerce_mapping(value)
        return cls(
            provider_name=_text(_get(payload, "provider_name", "providerName")),
            provider_id=_text(_get(payload, "provider_id", "providerId")),
            capability=_text(_get(payload, "capability")),
            source_type=_text(_get(payload, "source_type", "sourceType")),
            source_tier=_text(_get(payload, "source_tier", "sourceTier")),
            trust_level=_text(_get(payload, "trust_level", "trustLevel")),
            freshness_expectation=_text(_get(payload, "freshness_expectation", "freshnessExpectation")),
            observation_only=_bool(_get(payload, "observation_only", "observationOnly")),
            score_contribution_allowed=_bool(
                _get(payload, "score_contribution_allowed", "scoreContributionAllowed")
            ),
            paid_data_likely_required=_bool(
                _get(payload, "paid_data_likely_required", "paidDataLikelyRequired")
            ),
            key_required=_bool(_get(payload, "key_required", "keyRequired")),
            cache_required=_bool(_get(payload, "cache_required", "cacheRequired")),
            background_refresh_recommended=_bool(
                _get(payload, "background_refresh_recommended", "backgroundRefreshRecommended")
            ),
            degradation_reason=_optional_text(_get(payload, "degradation_reason", "degradationReason")),
            missing_provider_reason=_optional_text(
                _get(payload, "missing_provider_reason", "missingProviderReason")
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "providerName": self.provider_name,
            "providerId": self.provider_id,
            "capability": self.capability,
            "sourceType": self.source_type,
            "sourceTier": self.source_tier,
            "trustLevel": self.trust_level,
            "freshnessExpectation": self.freshness_expectation,
            "observationOnly": self.observation_only,
            "scoreContributionAllowed": self.score_contribution_allowed,
            "paidDataLikelyRequired": self.paid_data_likely_required,
            "keyRequired": self.key_required,
            "cacheRequired": self.cache_required,
            "backgroundRefreshRecommended": self.background_refresh_recommended,
            "degradationReason": self.degradation_reason,
            "missingProviderReason": self.missing_provider_reason,
        }


@dataclass(frozen=True, slots=True)
class ProviderFitMetadataContract:
    provider_name: str
    provider_id: str
    provider_category: str
    source_tier: str
    trust_level: str
    freshness_expectation: str
    observation_only: bool = False
    score_contribution_allowed: bool = False
    paid_data_likely_required: bool = False
    key_required: bool = False
    live_tests_avoided: bool = True
    cache_required: bool = False
    background_refresh_recommended: bool = False
    enabled_by_default: bool = False
    missing_provider_reason: str | None = None
    degradation_reason: str | None = None
    plan_dependent: bool = False
    best_use_cases: tuple[str, ...] = ()
    rejected_for: tuple[str, ...] = ()
    not_recommended_for: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: Any) -> "ProviderFitMetadataContract":
        payload = _coerce_mapping(value)
        return cls(
            provider_name=_text(_get(payload, "provider_name", "providerName")),
            provider_id=_text(_get(payload, "provider_id", "providerId")),
            provider_category=_text(_get(payload, "provider_category", "providerCategory")),
            source_tier=_text(_get(payload, "source_tier", "sourceTier")),
            trust_level=_text(_get(payload, "trust_level", "trustLevel")),
            freshness_expectation=_text(_get(payload, "freshness_expectation", "freshnessExpectation")),
            observation_only=_bool(_get(payload, "observation_only", "observationOnly")),
            score_contribution_allowed=_bool(
                _get(payload, "score_contribution_allowed", "scoreContributionAllowed")
            ),
            paid_data_likely_required=_bool(
                _get(payload, "paid_data_likely_required", "paidDataLikelyRequired")
            ),
            key_required=_bool(_get(payload, "key_required", "keyRequired")),
            live_tests_avoided=_bool(_get(payload, "live_tests_avoided", "liveTestsAvoided")),
            cache_required=_bool(_get(payload, "cache_required", "cacheRequired")),
            background_refresh_recommended=_bool(
                _get(payload, "background_refresh_recommended", "backgroundRefreshRecommended")
            ),
            enabled_by_default=_bool(_get(payload, "enabled_by_default", "enabledByDefault")),
            missing_provider_reason=_optional_text(
                _get(payload, "missing_provider_reason", "missingProviderReason")
            ),
            degradation_reason=_optional_text(_get(payload, "degradation_reason", "degradationReason")),
            plan_dependent=_bool(_get(payload, "plan_dependent", "planDependent")),
            best_use_cases=_string_tuple(_get(payload, "best_use_cases", "bestUseCases")),
            rejected_for=_string_tuple(_get(payload, "rejected_for", "rejectedFor")),
            not_recommended_for=_string_tuple(
                _get(payload, "not_recommended_for", "notRecommendedFor")
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "providerName": self.provider_name,
            "providerId": self.provider_id,
            "providerCategory": self.provider_category,
            "sourceTier": self.source_tier,
            "trustLevel": self.trust_level,
            "freshnessExpectation": self.freshness_expectation,
            "observationOnly": self.observation_only,
            "scoreContributionAllowed": self.score_contribution_allowed,
            "paidDataLikelyRequired": self.paid_data_likely_required,
            "keyRequired": self.key_required,
            "liveTestsAvoided": self.live_tests_avoided,
            "cacheRequired": self.cache_required,
            "backgroundRefreshRecommended": self.background_refresh_recommended,
            "enabledByDefault": self.enabled_by_default,
            "missingProviderReason": self.missing_provider_reason,
            "degradationReason": self.degradation_reason,
            "planDependent": self.plan_dependent,
            "bestUseCases": list(self.best_use_cases),
            "rejectedFor": list(self.rejected_for),
            "notRecommendedFor": list(self.not_recommended_for),
        }


@dataclass(frozen=True, slots=True)
class ProviderDryRunProbeContract:
    provider_name: str
    provider_id: str
    enabled_by_default: bool = False
    reason_code: str = "provider_fit_metadata_only"
    network_call_executed: bool = False
    no_default_live_http_calls: bool = True
    http_method: str = "NONE"
    key_required: bool = False
    required_credential_count: int = 0
    configured_credential_count: int = 0
    requires_credential_presence_only: bool = False
    live_tests_avoided: bool = True
    cache_required: bool = False
    background_refresh_recommended: bool = False
    observation_only: bool = True
    score_contribution_allowed: bool = False
    raw_credential_values_included: bool = False
    provider_payload_values_included: bool = False
    response_bodies_included: bool = False
    missing_provider_reason: str | None = None
    degradation_reason: str | None = None

    @classmethod
    def from_dict(cls, value: Any) -> "ProviderDryRunProbeContract":
        payload = _coerce_mapping(value)
        return cls(
            provider_name=_text(_get(payload, "provider_name", "providerName")),
            provider_id=_text(_get(payload, "provider_id", "providerId")),
            enabled_by_default=_bool(_get(payload, "enabled_by_default", "enabledByDefault")),
            reason_code=_text(_get(payload, "reason_code", "reasonCode")) or "provider_fit_metadata_only",
            network_call_executed=_bool(_get(payload, "network_call_executed", "networkCallExecuted")),
            no_default_live_http_calls=_bool(
                _get(payload, "no_default_live_http_calls", "noDefaultLiveHttpCalls")
            ),
            http_method=_text(_get(payload, "http_method", "httpMethod")) or "NONE",
            key_required=_bool(_get(payload, "key_required", "keyRequired")),
            required_credential_count=int(_float(_get(payload, "required_credential_count", "requiredCredentialCount"), default=0.0)),
            configured_credential_count=int(
                _float(_get(payload, "configured_credential_count", "configuredCredentialCount"), default=0.0)
            ),
            requires_credential_presence_only=_bool(
                _get(payload, "requires_credential_presence_only", "requiresCredentialPresenceOnly")
            ),
            live_tests_avoided=_bool(_get(payload, "live_tests_avoided", "liveTestsAvoided")),
            cache_required=_bool(_get(payload, "cache_required", "cacheRequired")),
            background_refresh_recommended=_bool(
                _get(payload, "background_refresh_recommended", "backgroundRefreshRecommended")
            ),
            observation_only=_bool(_get(payload, "observation_only", "observationOnly")),
            score_contribution_allowed=_bool(
                _get(payload, "score_contribution_allowed", "scoreContributionAllowed")
            ),
            raw_credential_values_included=_bool(
                _get(payload, "raw_credential_values_included", "rawCredentialValuesIncluded")
            ),
            provider_payload_values_included=_bool(
                _get(payload, "provider_payload_values_included", "providerPayloadValuesIncluded")
            ),
            response_bodies_included=_bool(_get(payload, "response_bodies_included", "responseBodiesIncluded")),
            missing_provider_reason=_optional_text(
                _get(payload, "missing_provider_reason", "missingProviderReason")
            ),
            degradation_reason=_optional_text(_get(payload, "degradation_reason", "degradationReason")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "providerName": self.provider_name,
            "providerId": self.provider_id,
            "enabledByDefault": self.enabled_by_default,
            "reasonCode": self.reason_code,
            "networkCallExecuted": self.network_call_executed,
            "noDefaultLiveHttpCalls": self.no_default_live_http_calls,
            "httpMethod": self.http_method,
            "keyRequired": self.key_required,
            "requiredCredentialCount": self.required_credential_count,
            "configuredCredentialCount": self.configured_credential_count,
            "requiresCredentialPresenceOnly": self.requires_credential_presence_only,
            "liveTestsAvoided": self.live_tests_avoided,
            "cacheRequired": self.cache_required,
            "backgroundRefreshRecommended": self.background_refresh_recommended,
            "observationOnly": self.observation_only,
            "scoreContributionAllowed": self.score_contribution_allowed,
            "rawCredentialValuesIncluded": self.raw_credential_values_included,
            "providerPayloadValuesIncluded": self.provider_payload_values_included,
            "responseBodiesIncluded": self.response_bodies_included,
            "missingProviderReason": self.missing_provider_reason,
            "degradationReason": self.degradation_reason,
        }


@dataclass(frozen=True, slots=True)
class SourceConfidenceValidationIssue:
    code: str
    message: str
    field: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "field": self.field,
        }


@dataclass(frozen=True, slots=True)
class SourceConfidenceValidationResult:
    issues: tuple[SourceConfidenceValidationIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict[str, Any]:
        return {
            "isValid": self.is_valid,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def coerce_source_confidence_contract(value: SourceConfidenceContract | Mapping[str, Any]) -> SourceConfidenceContract:
    """Return a normalized contract where degraded flags cap strong freshness."""

    contract = value if isinstance(value, SourceConfidenceContract) else SourceConfidenceContract.from_dict(value)
    return apply_source_confidence_caps(contract)


def coerce_provider_capability_contract(
    value: ProviderCapabilityContract | Mapping[str, Any],
) -> ProviderCapabilityContract:
    """Return a provider capability DTO from a mapping without side effects."""

    return value if isinstance(value, ProviderCapabilityContract) else ProviderCapabilityContract.from_dict(value)


def coerce_provider_capability_support_contract(
    value: ProviderCapabilitySupportContract | Mapping[str, Any],
) -> ProviderCapabilitySupportContract:
    """Return provider/capability metadata DTOs from mappings without side effects."""

    return (
        value
        if isinstance(value, ProviderCapabilitySupportContract)
        else ProviderCapabilitySupportContract.from_dict(value)
    )


def coerce_provider_fit_metadata_contract(
    value: ProviderFitMetadataContract | Mapping[str, Any],
) -> ProviderFitMetadataContract:
    """Return provider-fit metadata DTOs from mappings without side effects."""

    return (
        value
        if isinstance(value, ProviderFitMetadataContract)
        else ProviderFitMetadataContract.from_dict(value)
    )


def coerce_provider_dry_run_probe_contract(
    value: ProviderDryRunProbeContract | Mapping[str, Any],
) -> ProviderDryRunProbeContract:
    """Return provider dry-run probe DTOs from mappings without side effects."""

    return (
        value
        if isinstance(value, ProviderDryRunProbeContract)
        else ProviderDryRunProbeContract.from_dict(value)
    )


def apply_source_confidence_caps(contract: SourceConfidenceContract) -> SourceConfidenceContract:
    """Cap freshness/weight so degraded sources cannot be projected as fresh."""

    flags = _derived_flags(contract)
    degraded = _degradation_cap(flags)
    if degraded is None:
        return SourceConfidenceContract(
            source=contract.source,
            source_label=contract.source_label,
            as_of=contract.as_of,
            freshness=contract.freshness,
            is_fallback=flags["is_fallback"],
            is_stale=flags["is_stale"],
            is_partial=flags["is_partial"],
            is_synthetic=flags["is_synthetic"],
            is_unavailable=flags["is_unavailable"],
            confidence_weight=_bounded_float(contract.confidence_weight, default=0.0),
            coverage=_optional_bounded_float(contract.coverage),
            degradation_reason=contract.degradation_reason,
            cap_reason=contract.cap_reason,
        )

    freshness, cap, reason = degraded
    coverage = _optional_bounded_float(contract.coverage)
    if flags["is_unavailable"]:
        coverage = 0.0
    return SourceConfidenceContract(
        source=contract.source,
        source_label=contract.source_label,
        as_of=contract.as_of,
        freshness=freshness,
        is_fallback=flags["is_fallback"],
        is_stale=flags["is_stale"],
        is_partial=flags["is_partial"],
        is_synthetic=flags["is_synthetic"],
        is_unavailable=flags["is_unavailable"],
        confidence_weight=min(_bounded_float(contract.confidence_weight, default=0.0), cap),
        coverage=coverage,
        degradation_reason=contract.degradation_reason or reason,
        cap_reason=contract.cap_reason or reason,
    )


def validate_source_confidence_contract(
    value: SourceConfidenceContract | Mapping[str, Any],
) -> SourceConfidenceValidationResult:
    """Validate source-confidence metadata without normalizing it first."""

    contract = value if isinstance(value, SourceConfidenceContract) else SourceConfidenceContract.from_dict(value)
    flags = _derived_flags(contract)
    issues: list[SourceConfidenceValidationIssue] = []
    if any(flags.values()) and contract.freshness.value in STRONG_FRESHNESS_VALUES:
        issues.append(
            SourceConfidenceValidationIssue(
                code="degraded_claims_live_freshness",
                message="Fallback, stale, partial, synthetic, or unavailable data must not claim live/fresh freshness.",
                field="freshness",
            )
        )

    if contract.confidence_weight < 0 or contract.confidence_weight > 1:
        issues.append(
            SourceConfidenceValidationIssue(
                code="confidence_weight_out_of_range",
                message="confidenceWeight must be between 0.0 and 1.0.",
                field="confidenceWeight",
            )
        )
    degraded = _degradation_cap(flags)
    if degraded is not None and contract.confidence_weight > degraded[1]:
        issues.append(
            SourceConfidenceValidationIssue(
                code="confidence_weight_exceeds_degraded_cap",
                message="Degraded source confidenceWeight exceeds the contract cap.",
                field="confidenceWeight",
            )
        )
    if contract.coverage is not None and (contract.coverage < 0 or contract.coverage > 1):
        issues.append(
            SourceConfidenceValidationIssue(
                code="coverage_out_of_range",
                message="coverage must be between 0.0 and 1.0 when present.",
                field="coverage",
            )
        )
    if flags["is_unavailable"] and (contract.coverage or 0.0) > 0.0:
        issues.append(
            SourceConfidenceValidationIssue(
                code="unavailable_claims_coverage",
                message="Unavailable sources must not claim positive coverage.",
                field="coverage",
            )
        )
    return SourceConfidenceValidationResult(issues=tuple(issues))


def _coerce_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _get(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _optional_text(value: Any) -> str | None:
    text = _text(value)
    return text or None


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _bounded_float(value: Any, *, default: float) -> float:
    number = _float(value, default=default)
    return max(0.0, min(1.0, number))


def _float(value: Any, *, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return number


def _optional_bounded_float(value: Any) -> float | None:
    if value is None:
        return None
    return _bounded_float(value, default=0.0)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return _float(value, default=0.0)


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple, set)):
        return ()
    return tuple(text for item in value if (text := _text(item)))


def _coerce_freshness(value: Any) -> SourceFreshness:
    if isinstance(value, SourceFreshness):
        return value
    normalized = _text(value).lower()
    for item in SourceFreshness:
        if item.value == normalized:
            return item
    return SourceFreshness.UNKNOWN


def _derived_flags(contract: SourceConfidenceContract) -> dict[str, bool]:
    source = contract.source.lower()
    freshness = contract.freshness
    return {
        "is_unavailable": contract.is_unavailable
        or freshness is SourceFreshness.UNAVAILABLE
        or source in {"missing", "unavailable"},
        "is_synthetic": contract.is_synthetic
        or freshness is SourceFreshness.SYNTHETIC
        or "synthetic" in source
        or source in {"mock", "fixture", "unit_fixture"},
        "is_fallback": contract.is_fallback
        or freshness is SourceFreshness.FALLBACK
        or source.endswith("_fallback")
        or source == "fallback",
        "is_stale": contract.is_stale or freshness is SourceFreshness.STALE,
        "is_partial": contract.is_partial or freshness is SourceFreshness.PARTIAL,
    }


def _degradation_cap(flags: Mapping[str, bool]) -> tuple[SourceFreshness, float, str] | None:
    if flags.get("is_unavailable"):
        return (SourceFreshness.UNAVAILABLE, 0.0, "unavailable_source")
    if flags.get("is_synthetic"):
        return (SourceFreshness.SYNTHETIC, 0.2, "synthetic_source")
    if flags.get("is_fallback"):
        return (SourceFreshness.FALLBACK, 0.4, "fallback_source")
    if flags.get("is_stale"):
        return (SourceFreshness.STALE, 0.6, "stale_source")
    if flags.get("is_partial"):
        return (SourceFreshness.PARTIAL, 0.7, "partial_coverage")
    return None


__all__ = [
    "SOURCE_CONFIDENCE_CONTRACT_VERSION",
    "STRONG_FRESHNESS_VALUES",
    "ProviderCapabilityContract",
    "ProviderDryRunProbeContract",
    "ProviderFitMetadataContract",
    "ProviderCapabilitySupportContract",
    "SourceConfidenceContract",
    "SourceConfidenceValidationIssue",
    "SourceConfidenceValidationResult",
    "SourceFreshness",
    "SupportsSourceConfidence",
    "apply_source_confidence_caps",
    "coerce_provider_capability_contract",
    "coerce_provider_dry_run_probe_contract",
    "coerce_provider_fit_metadata_contract",
    "coerce_provider_capability_support_contract",
    "coerce_source_confidence_contract",
    "validate_source_confidence_contract",
]
