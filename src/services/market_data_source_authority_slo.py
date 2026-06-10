# -*- coding: utf-8 -*-
"""Inert source-authority SLO facade for market-data product surfaces.

This module is a thin wrapper around ``data_coverage_matrix_v1``. It enumerates
feature/endpoint expectations for T-1422 without importing provider runtimes,
API routers, MarketCache, storage, scanner scoring, LLM/report code, or
frontend modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Final, Mapping

from src.services.data_coverage_matrix_builder import build_data_coverage_matrix_row
from src.services.data_coverage_matrix_contract import (
    DATA_COVERAGE_MATRIX_CONTRACT_VERSION,
    ConsumerProductStatus,
    FreshnessState,
    RightToDisplay,
    project_consumer_data_coverage,
)


MARKET_DATA_SOURCE_AUTHORITY_SLO_VERSION: Final[str] = DATA_COVERAGE_MATRIX_CONTRACT_VERSION

EXPECTED_SOURCE_AUTHORITY_FIELDS: Final[tuple[str, ...]] = (
    "freshnessState",
    "isFallback",
    "isStale",
    "sourceAuthorityAllowed",
    "scoreContributionAllowed",
    "authorityGrant",
    "observationOnly",
    "rightToDisplay",
    "consumerSafeProjection",
)

PROTECTED_RUNTIME_BOUNDARIES: Final[tuple[str, ...]] = (
    "provider_runtime_order",
    "provider_live_call_paths",
    "provider_fallback_behavior",
    "market_cache_ttl_swr_cold_start_keys",
    "scanner_scoring_ranking_selection_thresholds",
    "api_response_contracts",
    "storage_schema_migrations",
    "auth_rbac_security",
    "llm_prompt_report_decision_logic",
    "frontend_ui_layout_apps_dsa_web",
)


class MarketDataSourceAuthorityFeature(str, Enum):
    MARKET_OVERVIEW = "market_overview"
    LIQUIDITY = "liquidity"
    ROTATION = "rotation"
    SCANNER = "scanner"
    WATCHLIST = "watchlist"


class SourceAuthoritySloRiskLevel(str, Enum):
    STANDARD = "standard"
    HIGHER_RISK_PARTIAL = "higher_risk_partial"


class SourceAuthoritySloReadiness(str, Enum):
    READY = "ready"
    OBSERVATION_ONLY = "observation_only"
    PARTIAL = "partial"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class MarketDataSourceAuthoritySloExpectation:
    feature_id: MarketDataSourceAuthorityFeature
    feature_label: str
    surface_id: str
    field_key: str
    endpoint_ids: tuple[str, ...]
    expected_fields: tuple[str, ...]
    score_contribution_applicable: bool
    observation_only_applicable: bool
    consumer_safe_projection_required: bool
    min_confidence_weight: float
    current_contract_uniform: bool
    risk_level: SourceAuthoritySloRiskLevel
    partial_reason_codes: tuple[str, ...]
    consumer_safe_projection_expectations: tuple[str, ...]
    protected_runtime_boundaries: tuple[str, ...] = PROTECTED_RUNTIME_BOUNDARIES
    contract_version: str = MARKET_DATA_SOURCE_AUTHORITY_SLO_VERSION
    diagnostic_only: bool = True
    provider_runtime_called: bool = False
    api_called: bool = False
    network_calls_enabled: bool = False
    market_cache_mutation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "contractVersion": self.contract_version,
            "featureId": self.feature_id.value,
            "featureLabel": self.feature_label,
            "surfaceId": self.surface_id,
            "fieldKey": self.field_key,
            "endpointIds": list(self.endpoint_ids),
            "expectedFields": list(self.expected_fields),
            "scoreContributionApplicable": self.score_contribution_applicable,
            "observationOnlyApplicable": self.observation_only_applicable,
            "consumerSafeProjectionRequired": self.consumer_safe_projection_required,
            "minConfidenceWeight": self.min_confidence_weight,
            "currentContractUniform": self.current_contract_uniform,
            "riskLevel": self.risk_level.value,
            "partialReasonCodes": list(self.partial_reason_codes),
            "consumerSafeProjectionExpectations": list(self.consumer_safe_projection_expectations),
            "protectedRuntimeBoundaries": list(self.protected_runtime_boundaries),
            "diagnosticOnly": self.diagnostic_only,
            "providerRuntimeCalled": self.provider_runtime_called,
            "apiCalled": self.api_called,
            "networkCallsEnabled": self.network_calls_enabled,
            "marketCacheMutation": self.market_cache_mutation,
        }


@dataclass(frozen=True, slots=True)
class SourceAuthoritySloEvaluation:
    feature_id: MarketDataSourceAuthorityFeature
    readiness: SourceAuthoritySloReadiness
    consumer_status: ConsumerProductStatus
    reason_codes: tuple[str, ...]
    data_coverage_row: dict[str, Any]
    validation_issue_codes: tuple[str, ...]
    source_authority_allowed: bool
    score_contribution_allowed: bool
    observation_only: bool
    right_to_display: RightToDisplay
    expectation_risk_level: SourceAuthoritySloRiskLevel
    current_contract_uniform: bool
    diagnostic_only: bool = True
    provider_runtime_called: bool = False
    api_called: bool = False
    network_calls_enabled: bool = False
    market_cache_mutation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "contractVersion": MARKET_DATA_SOURCE_AUTHORITY_SLO_VERSION,
            "featureId": self.feature_id.value,
            "readiness": self.readiness.value,
            "consumerStatus": self.consumer_status.value,
            "reasonCodes": list(self.reason_codes),
            "dataCoverageRow": dict(self.data_coverage_row),
            "validationIssueCodes": list(self.validation_issue_codes),
            "sourceAuthorityAllowed": self.source_authority_allowed,
            "scoreContributionAllowed": self.score_contribution_allowed,
            "observationOnly": self.observation_only,
            "rightToDisplay": self.right_to_display.value,
            "expectationRiskLevel": self.expectation_risk_level.value,
            "currentContractUniform": self.current_contract_uniform,
            "diagnosticOnly": self.diagnostic_only,
            "providerRuntimeCalled": self.provider_runtime_called,
            "apiCalled": self.api_called,
            "networkCallsEnabled": self.network_calls_enabled,
            "marketCacheMutation": self.market_cache_mutation,
        }


MARKET_DATA_SOURCE_AUTHORITY_SLO_MATRIX: Final[tuple[MarketDataSourceAuthoritySloExpectation, ...]] = (
    MarketDataSourceAuthoritySloExpectation(
        feature_id=MarketDataSourceAuthorityFeature.MARKET_OVERVIEW,
        feature_label="Market Overview",
        surface_id="market_overview",
        field_key="market_regime",
        endpoint_ids=(
            "/api/v1/market-overview/indices",
            "/api/v1/market-overview/volatility",
            "/api/v1/market-overview/sentiment",
            "/api/v1/market-overview/funds-flow",
            "/api/v1/market-overview/macro",
            "/api/v1/market/temperature",
        ),
        expected_fields=EXPECTED_SOURCE_AUTHORITY_FIELDS,
        score_contribution_applicable=True,
        observation_only_applicable=True,
        consumer_safe_projection_required=True,
        min_confidence_weight=0.70,
        current_contract_uniform=False,
        risk_level=SourceAuthoritySloRiskLevel.HIGHER_RISK_PARTIAL,
        partial_reason_codes=("market_overview_contract_not_uniform",),
        consumer_safe_projection_expectations=(
            "product_status_only",
            "hide_raw_provider_diagnostics",
            "do_not_project_source_labels_as_authority",
        ),
    ),
    MarketDataSourceAuthoritySloExpectation(
        feature_id=MarketDataSourceAuthorityFeature.LIQUIDITY,
        feature_label="Liquidity",
        surface_id="liquidity",
        field_key="liquidity_score_status",
        endpoint_ids=("/api/v1/market/liquidity-monitor",),
        expected_fields=EXPECTED_SOURCE_AUTHORITY_FIELDS,
        score_contribution_applicable=True,
        observation_only_applicable=True,
        consumer_safe_projection_required=True,
        min_confidence_weight=0.70,
        current_contract_uniform=True,
        risk_level=SourceAuthoritySloRiskLevel.STANDARD,
        partial_reason_codes=(),
        consumer_safe_projection_expectations=(
            "product_status_only",
            "pause_score_when_fallback_or_stale",
            "hide_raw_provider_diagnostics",
        ),
    ),
    MarketDataSourceAuthoritySloExpectation(
        feature_id=MarketDataSourceAuthorityFeature.ROTATION,
        feature_label="Rotation",
        surface_id="rotation",
        field_key="rotation_score_status",
        endpoint_ids=("/api/v1/market/rotation-radar", "/api/v1/market/sector-rotation"),
        expected_fields=EXPECTED_SOURCE_AUTHORITY_FIELDS,
        score_contribution_applicable=True,
        observation_only_applicable=True,
        consumer_safe_projection_required=True,
        min_confidence_weight=0.70,
        current_contract_uniform=True,
        risk_level=SourceAuthoritySloRiskLevel.STANDARD,
        partial_reason_codes=(),
        consumer_safe_projection_expectations=(
            "product_status_only",
            "do_not_grant_stage_or_rank_authority_from_source_labels",
            "hide_raw_provider_diagnostics",
        ),
    ),
    MarketDataSourceAuthoritySloExpectation(
        feature_id=MarketDataSourceAuthorityFeature.SCANNER,
        feature_label="Scanner",
        surface_id="scanner",
        field_key="candidate_score_status",
        endpoint_ids=(
            "/api/v1/scanner/run",
            "/api/v1/scanner/runs",
            "/api/v1/scanner/status",
        ),
        expected_fields=EXPECTED_SOURCE_AUTHORITY_FIELDS,
        score_contribution_applicable=True,
        observation_only_applicable=True,
        consumer_safe_projection_required=True,
        min_confidence_weight=0.70,
        current_contract_uniform=True,
        risk_level=SourceAuthoritySloRiskLevel.STANDARD,
        partial_reason_codes=(),
        consumer_safe_projection_expectations=(
            "observation_only_summary_when_authority_missing",
            "do_not_change_scanner_scoring_ranking_or_thresholds",
            "hide_raw_provider_diagnostics",
        ),
    ),
    MarketDataSourceAuthoritySloExpectation(
        feature_id=MarketDataSourceAuthorityFeature.WATCHLIST,
        feature_label="Watchlist",
        surface_id="watchlist",
        field_key="watchlist_readiness_status",
        endpoint_ids=(
            "/api/v1/watchlist/items",
            "/api/v1/watchlist/refresh-scores",
            "/api/v1/watchlist/refresh-status",
        ),
        expected_fields=EXPECTED_SOURCE_AUTHORITY_FIELDS,
        score_contribution_applicable=True,
        observation_only_applicable=True,
        consumer_safe_projection_required=True,
        min_confidence_weight=0.70,
        current_contract_uniform=True,
        risk_level=SourceAuthoritySloRiskLevel.STANDARD,
        partial_reason_codes=(),
        consumer_safe_projection_expectations=(
            "product_status_only",
            "do_not_imply_trade_or_execution_authority",
            "hide_scanner_lineage_diagnostics_by_default",
        ),
    ),
)

MARKET_DATA_SOURCE_AUTHORITY_SLO_BY_FEATURE: Final[
    dict[MarketDataSourceAuthorityFeature, MarketDataSourceAuthoritySloExpectation]
] = {entry.feature_id: entry for entry in MARKET_DATA_SOURCE_AUTHORITY_SLO_MATRIX}


def get_market_data_source_authority_slo_matrix() -> tuple[MarketDataSourceAuthoritySloExpectation, ...]:
    return MARKET_DATA_SOURCE_AUTHORITY_SLO_MATRIX


def get_market_data_source_authority_slo_expectation(
    feature_id: Any,
) -> MarketDataSourceAuthoritySloExpectation:
    feature = _coerce_feature(feature_id)
    try:
        return MARKET_DATA_SOURCE_AUTHORITY_SLO_BY_FEATURE[feature]
    except KeyError as exc:
        raise LookupError(f"Unknown market-data source-authority SLO feature: {feature.value}") from exc


def evaluate_market_data_source_authority_slo(
    observation: Mapping[str, Any],
) -> SourceAuthoritySloEvaluation:
    feature = _coerce_feature(_get(observation, "featureId", "feature_id"))
    expectation = get_market_data_source_authority_slo_expectation(feature)
    source_states = _coerce_source_states(_get(observation, "sourceStates", "source_states"))
    confidence_weight = _optional_float(
        _get(observation, "confidenceWeight", "confidence_weight", "confidence")
    )
    slo_reason_codes = _slo_reason_codes(
        expectation=expectation,
        observation=observation,
        source_states=source_states,
        confidence_weight=confidence_weight,
    )
    matrix_metadata = _matrix_metadata(
        expectation=expectation,
        observation=observation,
        source_states=source_states,
        confidence_weight=confidence_weight,
        slo_reason_codes=slo_reason_codes,
    )
    build_result = build_data_coverage_matrix_row(
        matrix_metadata,
        surface_id=expectation.surface_id,
        field_key=expectation.field_key,
    )
    row = build_result.to_dict()
    validation_issue_codes = tuple(issue.code for issue in build_result.validation.issues)
    reason_codes = tuple(dict.fromkeys((*slo_reason_codes, *validation_issue_codes)))
    projection = project_consumer_data_coverage(row)

    return SourceAuthoritySloEvaluation(
        feature_id=feature,
        readiness=_readiness_for(reason_codes),
        consumer_status=_consumer_status_for(reason_codes, projection.status),
        reason_codes=reason_codes,
        data_coverage_row=row,
        validation_issue_codes=validation_issue_codes,
        source_authority_allowed=bool(row["sourceAuthorityAllowed"]) and not reason_codes,
        score_contribution_allowed=bool(row["scoreContributionAllowed"]) and not reason_codes,
        observation_only=bool(row["observationOnly"] or reason_codes),
        right_to_display=RightToDisplay(row["rightToDisplay"]),
        expectation_risk_level=expectation.risk_level,
        current_contract_uniform=expectation.current_contract_uniform,
    )


def _matrix_metadata(
    *,
    expectation: MarketDataSourceAuthoritySloExpectation,
    observation: Mapping[str, Any],
    source_states: tuple[str, ...],
    confidence_weight: float | None,
    slo_reason_codes: tuple[str, ...],
) -> dict[str, Any]:
    freshness_state = _coerce_freshness(_get(observation, "freshness", "freshnessState", "freshness_state"))
    if "mixed_source_state" in slo_reason_codes and freshness_state in {FreshnessState.FRESH, FreshnessState.LIVE}:
        freshness_state = FreshnessState.PARTIAL

    raw_allows_grants = not slo_reason_codes
    return {
        "providerId": _text(_get(observation, "providerId", "provider_id")) or "source_authority_slo_descriptor",
        "providerLabel": "Source authority SLO descriptor",
        "sourceId": "source_authority_slo_observation",
        "sourceLabel": "Source authority SLO observation",
        "sourceType": "source_authority_slo_fixture",
        "sourceTier": "source_authority_slo_fixture",
        "freshnessState": freshness_state.value,
        "isFallback": _bool(_get(observation, "isFallback", "is_fallback", "fallback"))
        or "fallback" in source_states,
        "isStale": _bool(_get(observation, "isStale", "is_stale", "stale")) or "stale" in source_states,
        "isPartial": _bool(_get(observation, "isPartial", "is_partial", "partial"))
        or "partial" in source_states
        or "mixed_source_state" in slo_reason_codes,
        "isSynthetic": _bool(_get(observation, "isSynthetic", "is_synthetic", "synthetic"))
        or "synthetic" in source_states,
        "isUnavailable": _bool(_get(observation, "isUnavailable", "is_unavailable", "unavailable"))
        or "unavailable" in source_states,
        "sourceAuthorityAllowed": bool(
            raw_allows_grants and _bool(_get(observation, "sourceAuthorityAllowed", "source_authority_allowed"))
        ),
        "scoreContributionAllowed": bool(
            raw_allows_grants
            and expectation.score_contribution_applicable
            and _bool(_get(observation, "scoreContributionAllowed", "score_contribution_allowed"))
        ),
        "authorityGrant": bool(raw_allows_grants and _bool(_get(observation, "authorityGrant", "authority_grant"))),
        "decisionGrade": bool(raw_allows_grants and _bool(_get(observation, "decisionGrade", "decision_grade"))),
        "rightToDisplay": "granted" if raw_allows_grants else _limited_display_for(freshness_state, confidence_weight),
        "observationOnly": not raw_allows_grants,
        "diagnosticOnly": True,
        "providerRuntimeCalled": False,
        "networkCallsEnabled": False,
        "marketCacheMutation": False,
    }


def _slo_reason_codes(
    *,
    expectation: MarketDataSourceAuthoritySloExpectation,
    observation: Mapping[str, Any],
    source_states: tuple[str, ...],
    confidence_weight: float | None,
) -> tuple[str, ...]:
    reason_codes: list[str] = list(expectation.partial_reason_codes)
    freshness = _coerce_freshness(_get(observation, "freshness", "freshnessState", "freshness_state"))

    if "mixed" in source_states or len(source_states) > 1:
        reason_codes.append("mixed_source_state")
    if "unknown" in source_states:
        reason_codes.append("unknown_source_state")
    if freshness is FreshnessState.UNKNOWN:
        reason_codes.append("unknown_freshness")
    if freshness is FreshnessState.FALLBACK or _bool(_get(observation, "isFallback", "is_fallback", "fallback")):
        reason_codes.append("fallback_source_state")
    if freshness is FreshnessState.STALE or _bool(_get(observation, "isStale", "is_stale", "stale")):
        reason_codes.append("stale_source_state")
    if freshness is FreshnessState.PARTIAL or _bool(_get(observation, "isPartial", "is_partial", "partial")):
        reason_codes.append("partial_source_state")
    if freshness is FreshnessState.SYNTHETIC or _bool(_get(observation, "isSynthetic", "is_synthetic", "synthetic")):
        reason_codes.append("synthetic_source_state")
    if freshness is FreshnessState.UNAVAILABLE or _bool(
        _get(observation, "isUnavailable", "is_unavailable", "unavailable")
    ):
        reason_codes.append("unavailable_source_state")
    if confidence_weight is None:
        reason_codes.append("missing_confidence_weight")
    elif confidence_weight < expectation.min_confidence_weight:
        reason_codes.append("low_confidence")
    if not _bool(_get(observation, "sourceAuthorityAllowed", "source_authority_allowed")):
        reason_codes.append("missing_source_authority")
    if expectation.score_contribution_applicable and not _bool(
        _get(observation, "scoreContributionAllowed", "score_contribution_allowed")
    ):
        reason_codes.append("missing_score_contribution")
    if expectation.consumer_safe_projection_required and not _bool(
        _get(observation, "consumerSafeProjection", "consumer_safe_projection")
    ):
        reason_codes.append("missing_consumer_safe_projection")

    return tuple(dict.fromkeys(reason_codes))


def _readiness_for(reason_codes: tuple[str, ...]) -> SourceAuthoritySloReadiness:
    if not reason_codes:
        return SourceAuthoritySloReadiness.READY
    if set(reason_codes) <= {"missing_score_contribution"}:
        return SourceAuthoritySloReadiness.OBSERVATION_ONLY
    if "market_overview_contract_not_uniform" in reason_codes or "partial_source_state" in reason_codes:
        return SourceAuthoritySloReadiness.PARTIAL
    return SourceAuthoritySloReadiness.BLOCKED


def _consumer_status_for(
    reason_codes: tuple[str, ...],
    projection_status: ConsumerProductStatus,
) -> ConsumerProductStatus:
    reason_set = set(reason_codes)
    if not reason_set:
        return ConsumerProductStatus.AVAILABLE
    if "unavailable_source_state" in reason_set or "synthetic_source_state" in reason_set:
        return ConsumerProductStatus.UNAVAILABLE
    if "mixed_source_state" in reason_set or "partial_source_state" in reason_set:
        return ConsumerProductStatus.PARTIAL
    if "fallback_source_state" in reason_set:
        return ConsumerProductStatus.PAUSED
    if "stale_source_state" in reason_set:
        return ConsumerProductStatus.DELAYED
    if "low_confidence" in reason_set:
        return ConsumerProductStatus.INSUFFICIENT
    if "market_overview_contract_not_uniform" in reason_set:
        return ConsumerProductStatus.PARTIAL
    if "unknown_freshness" in reason_set:
        return ConsumerProductStatus.UPDATING
    return projection_status


def _limited_display_for(freshness_state: FreshnessState, confidence_weight: float | None) -> str:
    if freshness_state in {FreshnessState.SYNTHETIC, FreshnessState.UNAVAILABLE}:
        return RightToDisplay.UNAVAILABLE.value
    if confidence_weight is not None and confidence_weight <= 0:
        return RightToDisplay.UNAVAILABLE.value
    return RightToDisplay.LIMITED.value


def _coerce_feature(value: Any) -> MarketDataSourceAuthorityFeature:
    if isinstance(value, MarketDataSourceAuthorityFeature):
        return value
    text = _normalize_key(value)
    for feature in MarketDataSourceAuthorityFeature:
        if text == feature.value:
            return feature
    raise LookupError(f"Unknown market-data source-authority SLO feature: {value!r}")


def _coerce_freshness(value: Any) -> FreshnessState:
    if isinstance(value, FreshnessState):
        return value
    text = _normalize_key(value)
    aliases = {"fixture": "synthetic", "missing": "unavailable", "mock": "synthetic"}
    text = aliases.get(text, text)
    for freshness in FreshnessState:
        if text == freshness.value:
            return freshness
    return FreshnessState.UNKNOWN


def _coerce_source_states(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        raw_values = [value]
    elif isinstance(value, tuple | list | set):
        raw_values = list(value)
    else:
        return ()

    normalized: list[str] = []
    for raw_value in raw_values:
        text = _normalize_key(raw_value)
        if text in {"mixed", "fallback", "stale", "partial", "synthetic", "unavailable", "fresh", "live"}:
            normalized.append(text)
        elif text:
            normalized.append("unknown")
    return tuple(normalized)


def _get(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _bool(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = _normalize_key(value)
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    return "_".join(part for part in text.replace("-", "_").replace("/", "_").split("_") if part)
