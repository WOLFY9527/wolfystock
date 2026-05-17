# -*- coding: utf-8 -*-
"""Contract tests for factor observations, evidence, evaluations, and signals."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.v1.schemas.factors import FactorEvidence, FactorObservation
from src.services.factor_observations import (
    build_factor_evaluation,
    build_factor_portfolio_signal,
    coerce_factor_observation,
)


def _base_evidence_payload() -> dict[str, object]:
    return {
        "factor_id": "trend.trend_strength_20d",
        "evidence_type": "metric",
        "title": "EMA slope",
        "metric_name": "ema_slope_20d",
        "numeric_value": 0.42,
        "source_name": "unit_fixture",
        "source_type": "synthetic_fixture",
        "as_of": "2026-05-16",
        "observed_at": "2026-05-16T14:30:00Z",
        "freshness_status": "partial",
        "confidence": 0.62,
        "is_partial": True,
    }


def _base_observation_payload() -> dict[str, object]:
    return {
        "factor_id": "Trend.Trend-Strength 20D",
        "symbol": "aapl",
        "value": 0.35,
        "percentile": 0.7,
        "z_score": 1.4,
        "source_name": "unit_fixture",
        "source_type": "synthetic_fixture",
        "as_of": "2026-05-16",
        "observed_at": "2026-05-16T14:30:00Z",
        "freshness_status": "partial",
        "confidence": 0.62,
        "is_partial": True,
        "evidences": [_base_evidence_payload()],
    }


def test_observation_normalizes_factor_id_symbol_and_nested_evidence() -> None:
    observation = coerce_factor_observation(_base_observation_payload())

    assert observation.factor_id == "trend.trend_strength_20d"
    assert observation.symbol == "AAPL"
    assert len(observation.evidences) == 1
    assert observation.evidences[0].factor_id == observation.factor_id


def test_missing_source_or_as_of_is_rejected() -> None:
    payload = _base_observation_payload()
    payload["source_name"] = ""

    with pytest.raises(ValidationError):
        FactorObservation.model_validate(payload)

    payload = _base_observation_payload()
    payload["as_of"] = ""

    with pytest.raises(ValidationError):
        FactorObservation.model_validate(payload)


def test_confidence_and_numeric_bounds_are_enforced() -> None:
    with pytest.raises(ValidationError):
        FactorEvidence.model_validate({**_base_evidence_payload(), "confidence": 1.01})

    with pytest.raises(ValidationError):
        FactorObservation.model_validate({**_base_observation_payload(), "value": 1_000_001})


def test_fallback_data_cannot_claim_live_or_fresh_state() -> None:
    with pytest.raises(ValidationError):
        FactorObservation.model_validate(
            {
                **_base_observation_payload(),
                "source_type": "fallback_static",
                "freshness_status": "live",
                "is_fallback": True,
            }
        )

    with pytest.raises(ValidationError):
        FactorObservation.model_validate(
            {
                **_base_observation_payload(),
                "source_type": "fallback_static",
                "freshness_status": "fresh",
            }
        )


def test_evaluation_and_portfolio_signal_preserve_provenance_flags() -> None:
    observation = coerce_factor_observation(
        {
            **_base_observation_payload(),
            "source_type": "fallback_static",
            "freshness_status": "fallback",
            "is_fallback": True,
            "is_stale": True,
        }
    )

    evaluation = build_factor_evaluation(observation, score=0.45, disposition="observe_only")
    signal = build_factor_portfolio_signal(evaluation)

    assert evaluation.factor_id == observation.factor_id
    assert evaluation.source_type == "fallback_static"
    assert evaluation.is_fallback is True
    assert evaluation.is_stale is True
    assert signal.side == "neutral"
    assert signal.signal_weight == pytest.approx(0.45)
    assert signal.confidence == pytest.approx(observation.confidence)
