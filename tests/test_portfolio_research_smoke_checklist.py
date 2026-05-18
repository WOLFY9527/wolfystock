# -*- coding: utf-8 -*-
"""Portfolio Research smoke coverage and manual checklist contract."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from src.services.portfolio_construction_service import PortfolioConstructionReadModelService
from src.services.portfolio_factor_exposure import PortfolioFactorExposureService
from src.services.portfolio_risk_attribution import PortfolioRiskAttributionService
from src.services.portfolio_stress_risk import PortfolioStressRiskService


FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "portfolio"
    / "portfolio_snapshot_read_model_dto.json"
)
CHECKLIST_PATH = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "portfolio"
    / "portfolio-research-smoke-checklist.md"
)


def _load_snapshot() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _position_weight(row: dict[str, object]) -> dict[str, object]:
    return {
        "symbol": row["symbol"],
        "weight": round(float(row["currentWeight"]) / 100.0, 6),
    }


def _position_market_value(row: dict[str, object]) -> dict[str, object]:
    return {
        "symbol": row["symbol"],
        "market_value": row["currentMarketValue"],
    }


def _factor_observation(symbol: str, factor_id: str, value: float) -> dict[str, object]:
    return {
        "observation": {
            "factor_id": factor_id,
            "symbol": symbol,
            "value": value,
            "source_name": "portfolio_research_fixture",
            "source_type": "synthetic_fixture",
            "as_of": "2026-05-18",
            "observed_at": "2026-05-18T09:30:00Z",
            "freshness_status": "partial",
            "confidence": 0.5,
            "is_partial": True,
        }
    }


def test_portfolio_research_smoke_helpers_compose_without_mutation_or_runtime_side_effects() -> None:
    checklist = CHECKLIST_PATH.read_text(encoding="utf-8")
    assert "python3 -m pytest" in checklist
    assert "advisory-only" in checklist
    assert "not trade execution" in checklist
    assert "must not be manually tested" in checklist

    snapshot = _load_snapshot()
    original_snapshot = copy.deepcopy(snapshot)

    construction_service = PortfolioConstructionReadModelService()
    factor_service = PortfolioFactorExposureService()
    attribution_service = PortfolioRiskAttributionService()
    stress_service = PortfolioStressRiskService()

    construction_projection = construction_service.build_read_model(
        snapshot=snapshot,
        target_weights={"600519": 50.0, "AAPL": 45.0, "MSFT": 5.0},
        min_trade_threshold=0.5,
        max_position_weight=50.0,
        cash_buffer_target=15.0,
    ).model_dump()

    # Current repo state uses the construction advisory projection as the
    # read-only rebalance surface for target-weight drift and delta suggestions.
    rebalance_projection = construction_projection
    weighted_rows = [
        row for row in construction_projection["positions"] if row["symbol"] in {"600519", "AAPL"}
    ]
    position_weights = [_position_weight(row) for row in weighted_rows]
    position_market_values = [_position_market_value(row) for row in weighted_rows]
    factor_observations = [
        _factor_observation("600519", "quality.earnings_quality", 0.8),
        _factor_observation("AAPL", "quality.earnings_quality", 0.6),
        _factor_observation("600519", "momentum.momentum_21d", 0.4),
        _factor_observation("AAPL", "momentum.momentum_21d", 0.9),
    ]

    factor_projection = factor_service.build_projection(
        snapshot={"as_of": snapshot["as_of"]},
        position_weights=position_weights,
        observations=factor_observations,
    ).model_dump()

    factor_exposures = []
    for factor_id, factor_row in factor_projection["exposuresByFactorId"].items():
        for row in weighted_rows:
            matching = next(
                item
                for item in factor_observations
                if item["observation"]["symbol"] == row["symbol"]
                and item["observation"]["factor_id"] == factor_id
            )
            factor_exposures.append(
                {
                    "symbol": row["symbol"],
                    "factor_id": factor_id,
                    "exposure": matching["observation"]["value"],
                    "factor_risk": abs(float(factor_row["exposure"] or 0.0)) or 1.0,
                }
            )

    attribution_projection = attribution_service.build_projection(
        snapshot={"as_of": snapshot["as_of"], "currency": snapshot["currency"]},
        position_weights=position_weights,
        position_market_values=position_market_values,
        classifications=[
            {"symbol": "600519", "sector": "Consumer Staples", "industry": "Beverages"},
            {"symbol": "AAPL", "sector": "Technology", "industry": "Consumer Electronics"},
        ],
        risk_metrics=[
            {"symbol": "600519", "risk_metric": 0.18},
            {"symbol": "AAPL", "risk_metric": 0.12},
        ],
        factor_exposures=factor_exposures,
    ).model_dump()

    stress_projection = stress_service.build_projection(
        as_of=snapshot["as_of"],
        positions=position_market_values,
        scenario_shocks=[
            {"name": "consumer_tech_gap_down", "shocks": {"600519": -0.08, "AAPL": -0.06}},
            {"name": "quality_rebound", "shocks": {"600519": 0.03, "AAPL": 0.04}},
        ],
        return_samples=[
            {"name": "sample_1", "returns": {"600519": -0.02, "AAPL": -0.01}},
            {"name": "sample_2", "returns": {"600519": -0.01, "AAPL": 0.02}},
            {"name": "sample_3", "returns": {"600519": -0.05, "AAPL": -0.03}},
            {"name": "sample_4", "returns": {"600519": 0.01, "AAPL": 0.03}},
            {"name": "sample_5", "returns": {"600519": -0.04, "AAPL": -0.02}},
        ],
        confidence_level=0.8,
    ).model_dump()

    assert snapshot == original_snapshot

    assert construction_projection["advisoryOnly"] is True
    assert rebalance_projection["tradeExecution"] is False
    assert factor_projection["readModelType"] == "portfolio_factor_exposure_advisory_v1"
    assert attribution_projection["readModelType"] == "portfolio_risk_attribution_advisory_v1"
    assert stress_projection["readModelType"] == "portfolio_stress_var_advisory_v1"

    assert construction_projection["accountingMutation"] is False
    assert rebalance_projection["brokerIntegration"] is False
    assert factor_projection["tradeExecution"] is False
    assert attribution_projection["accountingMutation"] is False
    assert stress_projection["brokerIntegration"] is False

    assert list(factor_projection["exposuresByFactorId"]) == [
        "momentum.momentum_21d",
        "quality.earnings_quality",
    ]
    assert attribution_projection["coverage"]["eligiblePositions"] == 2
    assert stress_projection["coverage"]["positionsWithMarketValue"] == 2
    assert stress_projection["historicalVar"]["available"] is True

    serialized = json.dumps(
        {
            "construction": construction_projection,
            "rebalance": rebalance_projection,
            "factor": factor_projection,
            "attribution": attribution_projection,
            "stress": stress_projection,
        },
        sort_keys=True,
    ).lower()
    for forbidden in (
        "create_trade_event",
        "broker_sync",
        "portfolio_ibkr_sync_service",
        "account_snapshot_write",
        "alembic",
        "frontend",
        "api.v1.endpoints",
        "data_provider",
    ):
        assert forbidden not in serialized
