# -*- coding: utf-8 -*-
"""Contract tests for the advisory-only portfolio factor exposure read model."""

from __future__ import annotations

import copy
import inspect
from types import SimpleNamespace

import pytest

from src.services.portfolio_factor_exposure import PortfolioFactorExposureService


def _observation(
    *,
    factor_id: str,
    symbol: str,
    as_of: str,
    value: float | None,
    neutralized_value: float | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "observation": {
            "factor_id": factor_id,
            "symbol": symbol,
            "value": value,
            "source_name": "unit_fixture",
            "source_type": "synthetic_fixture",
            "as_of": as_of,
            "observed_at": f"{as_of}T15:00:00Z",
            "freshness_status": "partial",
            "confidence": 0.55,
            "is_partial": True,
        }
    }
    if neutralized_value is not None:
        payload["neutralized_value"] = neutralized_value
    return payload


def _weight(symbol: str, weight: object) -> dict[str, object]:
    return {"symbol": symbol, "weight": weight}


def test_portfolio_factor_exposure_projects_weighted_exposure_by_factor_id() -> None:
    service = PortfolioFactorExposureService()

    projection = service.build_projection(
        snapshot={"as_of": "2026-05-18T09:30:00Z"},
        position_weights=[_weight("AAA", 0.50), _weight("BBB", 0.30), _weight("CCC", 0.20)],
        observations=[
            _observation(factor_id="momentum.momentum_21d", symbol="AAA", as_of="2026-05-16", value=1.0),
            _observation(factor_id="momentum.momentum_21d", symbol="BBB", as_of="2026-05-16", value=2.0),
            _observation(factor_id="momentum.momentum_21d", symbol="CCC", as_of="2026-05-16", value=4.0),
            _observation(factor_id="trend.trend_strength_20d", symbol="AAA", as_of="2026-05-16", value=5.0),
            _observation(factor_id="trend.trend_strength_20d", symbol="BBB", as_of="2026-05-16", value=-1.0),
            _observation(factor_id="trend.trend_strength_20d", symbol="CCC", as_of="2026-05-16", value=0.5),
        ],
    )

    assert projection.advisoryOnly is True
    assert projection.accountingMutation is False
    assert projection.brokerIntegration is False
    assert projection.tradeExecution is False
    assert projection.asOf == "2026-05-18T09:30:00Z"
    assert list(projection.exposuresByFactorId) == [
        "momentum.momentum_21d",
        "trend.trend_strength_20d",
    ]

    momentum = projection.exposuresByFactorId["momentum.momentum_21d"]
    trend = projection.exposuresByFactorId["trend.trend_strength_20d"]

    assert momentum.exposure == pytest.approx(1.9)
    assert momentum.weightedExposure == pytest.approx(1.9)
    assert momentum.grossExposure == pytest.approx(1.9)
    assert momentum.netExposure == pytest.approx(1.9)
    assert momentum.coverage == pytest.approx(1.0)
    assert momentum.missingFactorCount == 0
    assert momentum.warnings == ()
    assert momentum.asOf == "2026-05-16"
    assert momentum.window.as_of_start == "2026-05-16"
    assert momentum.window.as_of_end == "2026-05-16"
    assert momentum.window.as_of_count == 1

    assert trend.exposure == pytest.approx(2.3)
    assert trend.weightedExposure == pytest.approx(2.3)
    assert trend.grossExposure == pytest.approx(2.9)
    assert trend.netExposure == pytest.approx(2.3)


def test_portfolio_factor_exposure_counts_missing_observations_and_preserves_order() -> None:
    service = PortfolioFactorExposureService()

    projection = service.build_projection(
        snapshot={"as_of": "2026-05-18T09:30:00Z"},
        position_weights=[_weight("AAA", 0.6), _weight("BBB", 0.4)],
        observations=[
            _observation(factor_id="trend.trend_strength_20d", symbol="AAA", as_of="2026-05-16", value=2.0),
            _observation(factor_id="momentum.momentum_21d", symbol="AAA", as_of="2026-05-16", value=4.0),
        ],
    )

    assert list(projection.exposuresByFactorId) == [
        "momentum.momentum_21d",
        "trend.trend_strength_20d",
    ]
    assert projection.exposuresByFactorId["momentum.momentum_21d"].missingFactorCount == 1
    assert projection.exposuresByFactorId["momentum.momentum_21d"].warnings == (
        "missing_factor_observation",
    )
    assert projection.exposuresByFactorId["trend.trend_strength_20d"].missingFactorCount == 1


def test_portfolio_factor_exposure_excludes_zero_and_tiny_weights() -> None:
    service = PortfolioFactorExposureService()

    projection = service.build_projection(
        snapshot={"as_of": "2026-05-18T09:30:00Z"},
        position_weights=[
            _weight("AAA", 0.5),
            _weight("BBB", 0.0),
            _weight("CCC", 1e-15),
            _weight("DDD", "bad"),
        ],
        observations=[
            _observation(factor_id="trend.trend_strength_20d", symbol="AAA", as_of="2026-05-16", value=2.0),
            _observation(factor_id="trend.trend_strength_20d", symbol="BBB", as_of="2026-05-16", value=8.0),
            _observation(factor_id="trend.trend_strength_20d", symbol="CCC", as_of="2026-05-16", value=9.0),
        ],
    )

    summary = projection.exposuresByFactorId["trend.trend_strength_20d"]

    assert projection.coverage.totalPositions == 4
    assert projection.coverage.eligiblePositions == 1
    assert projection.coverage.zeroWeightCount == 2
    assert projection.coverage.invalidWeightCount == 1
    assert projection.coverage.grossWeight == pytest.approx(0.5)
    assert projection.coverage.netWeight == pytest.approx(0.5)
    assert projection.warnings == ("invalid_weight", "zero_weight")
    assert summary.exposure == pytest.approx(2.0)
    assert summary.weightedExposure == pytest.approx(1.0)
    assert summary.coverage == pytest.approx(1.0)


def test_portfolio_factor_exposure_prefers_neutralized_values_when_available() -> None:
    service = PortfolioFactorExposureService()

    projection = service.build_projection(
        snapshot={"as_of": "2026-05-18T09:30:00Z"},
        position_weights=[_weight("AAA", 0.75), _weight("BBB", 0.25)],
        observations=[
            _observation(
                factor_id="relative_strength.relative_strength_63d",
                symbol="AAA",
                as_of="2026-05-16",
                value=10.0,
                neutralized_value=-1.0,
            ),
            SimpleNamespace(
                factor_id="relative_strength.relative_strength_63d",
                symbol="BBB",
                as_of="2026-05-16",
                value=3.0,
                neutralized_value=1.0,
            ),
        ],
    )

    summary = projection.exposuresByFactorId["relative_strength.relative_strength_63d"]

    assert summary.exposure == pytest.approx(-0.5)
    assert summary.weightedExposure == pytest.approx(-0.5)
    assert summary.grossExposure == pytest.approx(1.0)
    assert summary.netExposure == pytest.approx(-0.5)


def test_portfolio_factor_exposure_does_not_mutate_inputs() -> None:
    service = PortfolioFactorExposureService()
    snapshot = {"as_of": "2026-05-18T09:30:00Z", "metadata": {"source": "fixture"}}
    position_weights = [_weight("BBB", 0.4), _weight("AAA", 0.6)]
    observations = [
        _observation(factor_id="momentum.momentum_21d", symbol="AAA", as_of="2026-05-16", value=4.0),
        _observation(factor_id="momentum.momentum_21d", symbol="BBB", as_of="2026-05-16", value=2.0),
    ]
    original_snapshot = copy.deepcopy(snapshot)
    original_weights = copy.deepcopy(position_weights)
    original_observations = copy.deepcopy(observations)

    first = service.build_projection(
        snapshot=snapshot,
        position_weights=position_weights,
        observations=observations,
    )
    second = service.build_projection(
        snapshot=snapshot,
        position_weights=list(reversed(position_weights)),
        observations=list(reversed(observations)),
    )

    assert snapshot == original_snapshot
    assert position_weights == original_weights
    assert observations == original_observations
    assert first.model_dump() == second.model_dump()


def test_portfolio_factor_exposure_service_has_no_accounting_broker_or_runtime_wiring_imports() -> None:
    import src.services.portfolio_factor_exposure as module

    source = inspect.getsource(module)
    forbidden_fragments = (
        "src.repositories",
        "portfolio_service",
        "portfolio_import_service",
        "portfolio_ibkr_sync_service",
        "PortfolioCashLedger",
        "PortfolioPositionLot",
        "create_trade_event",
        "create_cash_ledger_event",
        "sync_read_only_account_state",
        "scanner",
        "backtest",
        "api.v1.endpoints",
    )

    for fragment in forbidden_fragments:
        assert fragment not in source
