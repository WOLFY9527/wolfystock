# -*- coding: utf-8 -*-
"""Pure helpers for factor observations, evidence, and evaluation DTOs."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from api.v1.schemas.factors import (
    FactorDisposition,
    FactorEvaluation,
    FactorEvidence,
    FactorNeutralizationSpec,
    FactorObservation,
    FactorPortfolioSignal,
)


def coerce_factor_evidence(value: FactorEvidence | Mapping[str, Any]) -> FactorEvidence:
    """Normalize arbitrary evidence payloads into the stable DTO."""
    if isinstance(value, FactorEvidence):
        return value
    return FactorEvidence.model_validate(value)


def coerce_factor_observation(value: FactorObservation | Mapping[str, Any]) -> FactorObservation:
    """Normalize arbitrary observation payloads into the stable DTO."""
    if isinstance(value, FactorObservation):
        return value
    return FactorObservation.model_validate(value)


def build_factor_evaluation(
    observation: FactorObservation | Mapping[str, Any],
    *,
    score: float,
    disposition: FactorDisposition | None = None,
    confidence: float | None = None,
    evidences: Sequence[FactorEvidence | Mapping[str, Any]] | None = None,
    neutralization: FactorNeutralizationSpec | Mapping[str, Any] | None = None,
    notes: Sequence[str] | None = None,
) -> FactorEvaluation:
    """Project a validated observation into an inert evaluation DTO."""
    normalized_observation = coerce_factor_observation(observation)
    normalized_evidences = (
        [coerce_factor_evidence(item) for item in evidences]
        if evidences is not None
        else list(normalized_observation.evidences)
    )
    normalized_neutralization = _coerce_neutralization(neutralization)
    return FactorEvaluation(
        factor_id=normalized_observation.factor_id,
        symbol=normalized_observation.symbol,
        score=score,
        disposition=disposition or _default_disposition(score),
        observation=normalized_observation,
        evidences=normalized_evidences,
        neutralization=normalized_neutralization,
        notes=list(notes or []),
        source_name=normalized_observation.source_name,
        source_type=normalized_observation.source_type,
        as_of=normalized_observation.as_of,
        observed_at=normalized_observation.observed_at,
        freshness_status=normalized_observation.freshness_status,
        confidence=normalized_observation.confidence if confidence is None else confidence,
        is_fallback=normalized_observation.is_fallback,
        is_stale=normalized_observation.is_stale,
        is_partial=normalized_observation.is_partial,
    )


def build_factor_portfolio_signal(
    evaluation: FactorEvaluation | Mapping[str, Any],
    *,
    signal_weight: float | None = None,
    conviction: float | None = None,
    side: str | None = None,
    neutralization: FactorNeutralizationSpec | Mapping[str, Any] | None = None,
    notes: Sequence[str] | None = None,
) -> FactorPortfolioSignal:
    """Project an inert factor evaluation into a stable portfolio-signal DTO."""
    normalized_evaluation = evaluation if isinstance(evaluation, FactorEvaluation) else FactorEvaluation.model_validate(evaluation)
    normalized_neutralization = _coerce_neutralization(neutralization) or normalized_evaluation.neutralization
    resolved_weight = normalized_evaluation.score if signal_weight is None else signal_weight
    return FactorPortfolioSignal(
        factor_id=normalized_evaluation.factor_id,
        symbol=normalized_evaluation.symbol,
        side=_resolve_signal_side(normalized_evaluation.disposition, side, resolved_weight),
        signal_weight=resolved_weight,
        conviction=normalized_evaluation.confidence if conviction is None else conviction,
        evaluation_score=normalized_evaluation.score,
        neutralization=normalized_neutralization,
        notes=list(notes or []),
        source_name=normalized_evaluation.source_name,
        source_type=normalized_evaluation.source_type,
        as_of=normalized_evaluation.as_of,
        observed_at=normalized_evaluation.observed_at,
        freshness_status=normalized_evaluation.freshness_status,
        confidence=normalized_evaluation.confidence,
        is_fallback=normalized_evaluation.is_fallback,
        is_stale=normalized_evaluation.is_stale,
        is_partial=normalized_evaluation.is_partial,
    )


def _coerce_neutralization(
    value: FactorNeutralizationSpec | Mapping[str, Any] | None,
) -> FactorNeutralizationSpec | None:
    if value is None or isinstance(value, FactorNeutralizationSpec):
        return value
    return FactorNeutralizationSpec.model_validate(value)


def _default_disposition(score: float) -> FactorDisposition:
    if score > 0:
        return "positive"
    if score < 0:
        return "negative"
    return "neutral"


def _resolve_signal_side(disposition: str, side: str | None, signal_weight: float) -> str:
    if side:
        return side
    if disposition in {"observe_only", "blocked"}:
        return "neutral"
    if signal_weight > 0:
        return "long"
    if signal_weight < 0:
        return "short"
    return "neutral"


__all__ = [
    "build_factor_evaluation",
    "build_factor_portfolio_signal",
    "coerce_factor_evidence",
    "coerce_factor_observation",
]
