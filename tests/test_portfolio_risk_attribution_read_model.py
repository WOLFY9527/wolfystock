# -*- coding: utf-8 -*-
"""Contract tests for the advisory-only portfolio risk attribution read model."""

from __future__ import annotations

import copy
import inspect

import pytest

from src.services.portfolio_risk_attribution import PortfolioRiskAttributionService


def _weight(symbol: str, weight: object) -> dict[str, object]:
    return {"symbol": symbol, "weight": weight}


def _market_value(symbol: str, market_value: object) -> dict[str, object]:
    return {"symbol": symbol, "market_value": market_value}


def _classification(symbol: str, *, sector: object = None, industry: object = None) -> dict[str, object]:
    return {"symbol": symbol, "sector": sector, "industry": industry}


def _risk_metric(symbol: str, risk_metric: object) -> dict[str, object]:
    return {"symbol": symbol, "risk_metric": risk_metric}


def _factor_exposure(
    symbol: str,
    *,
    factor_id: str,
    exposure: object,
    factor_risk: object | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "symbol": symbol,
        "factor_id": factor_id,
        "exposure": exposure,
    }
    if factor_risk is not None:
        payload["factor_risk"] = factor_risk
    return payload


def test_portfolio_risk_attribution_projects_deterministic_advisory_breakdowns() -> None:
    service = PortfolioRiskAttributionService()

    projection = service.build_projection(
        snapshot={"as_of": "2026-05-18T09:30:00Z", "currency": "USD"},
        position_weights=[_weight("AAA", 0.50), _weight("BBB", 0.30), _weight("CCC", 0.20)],
        position_market_values=[_market_value("AAA", 500.0), _market_value("BBB", 300.0), _market_value("CCC", 200.0)],
        classifications=[
            _classification("AAA", sector="Technology", industry="Software"),
            _classification("BBB", sector="Technology", industry="Hardware"),
            _classification("CCC", sector="Healthcare", industry="Pharma"),
        ],
        risk_metrics=[_risk_metric("AAA", 0.20), _risk_metric("BBB", 0.10), _risk_metric("CCC", 0.05)],
        factor_exposures=[
            _factor_exposure("AAA", factor_id="momentum.momentum_21d", exposure=1.2, factor_risk=0.4),
            _factor_exposure("BBB", factor_id="momentum.momentum_21d", exposure=0.5, factor_risk=0.4),
            _factor_exposure("CCC", factor_id="momentum.momentum_21d", exposure=-0.3, factor_risk=0.4),
            _factor_exposure("AAA", factor_id="value.valuation_gap", exposure=0.5, factor_risk=0.2),
            _factor_exposure("BBB", factor_id="value.valuation_gap", exposure=-0.2, factor_risk=0.2),
        ],
    )

    assert projection.readModelType == "portfolio_risk_attribution_advisory_v1"
    assert projection.advisoryOnly is True
    assert projection.accountingMutation is False
    assert projection.brokerIntegration is False
    assert projection.tradeExecution is False
    assert projection.executionReadiness == "advisory_only_not_trade_execution"
    assert projection.asOf == "2026-05-18T09:30:00Z"
    assert projection.currency == "USD"
    assert projection.warnings == ()

    assert projection.coverage.totalPositions == 3
    assert projection.coverage.eligiblePositions == 3
    assert projection.coverage.marketValueCount == 3
    assert projection.coverage.missingMarketValueCount == 0
    assert projection.coverage.sectorCount == 3
    assert projection.coverage.industryCount == 3
    assert projection.coverage.positionRiskMetricCount == 3
    assert projection.coverage.missingPositionRiskMetricCount == 0
    assert projection.coverage.grossWeight == pytest.approx(1.0)
    assert projection.coverage.totalMarketValue == pytest.approx(1000.0)
    assert projection.coverage.factorCoverageById == {
        "momentum.momentum_21d": 3,
        "value.valuation_gap": 2,
    }

    assert [item.symbol for item in projection.byPosition] == ["AAA", "BBB", "CCC"]

    aaa = projection.byPosition[0]
    bbb = projection.byPosition[1]
    ccc = projection.byPosition[2]

    assert aaa.sector == "Technology"
    assert aaa.industry == "Software"
    assert aaa.weight == pytest.approx(0.5)
    assert aaa.weightPct == pytest.approx(50.0)
    assert aaa.marketValue == pytest.approx(500.0)
    assert aaa.marketValueWeightPct == pytest.approx(50.0)
    assert aaa.concentrationContribution == pytest.approx(0.25)
    assert aaa.specificRiskContribution == pytest.approx(0.10)
    assert aaa.factorContribution == pytest.approx(0.29)
    assert aaa.totalContribution == pytest.approx(0.64)
    assert aaa.contributionPct == pytest.approx(70.6402, rel=1e-4)
    assert aaa.warnings == ()

    assert bbb.totalContribution == pytest.approx(0.192)
    assert bbb.contributionPct == pytest.approx(21.1921, rel=1e-4)
    assert ccc.totalContribution == pytest.approx(0.074)
    assert ccc.contributionPct == pytest.approx(8.1678, rel=1e-4)

    assert [item.label for item in projection.bySector] == ["Technology", "Healthcare"]
    assert projection.bySector[0].totalContribution == pytest.approx(0.832)
    assert projection.bySector[0].contributionPct == pytest.approx(91.8322, rel=1e-4)

    assert [item.label for item in projection.byIndustry] == [
        "Software",
        "Hardware",
        "Pharma",
    ]
    assert projection.byIndustry[0].totalContribution == pytest.approx(0.64)

    assert list(projection.byFactorId) == [
        "momentum.momentum_21d",
        "value.valuation_gap",
    ]
    momentum = projection.byFactorId["momentum.momentum_21d"]
    value = projection.byFactorId["value.valuation_gap"]

    assert momentum.weightedExposure == pytest.approx(0.69)
    assert momentum.factorRisk == pytest.approx(0.4)
    assert momentum.contribution == pytest.approx(0.324)
    assert momentum.contributionPct == pytest.approx(35.7616, rel=1e-4)
    assert momentum.coveredPositionCount == 3
    assert momentum.missingPositionCount == 0

    assert value.weightedExposure == pytest.approx(0.19)
    assert value.factorRisk == pytest.approx(0.2)
    assert value.contribution == pytest.approx(0.062)
    assert value.coveredPositionCount == 2
    assert value.missingPositionCount == 1
    assert value.warnings == ("missing_factor_exposure",)

    assert projection.concentrationContribution.hhi == pytest.approx(0.38)
    assert projection.concentrationContribution.effectivePositionCount == pytest.approx(2.6316, rel=1e-4)
    assert projection.concentrationContribution.contribution == pytest.approx(0.38)
    assert projection.concentrationContribution.contributionPct == pytest.approx(41.9437, rel=1e-4)
    assert [item.symbol for item in projection.topRiskContributors[:3]] == ["AAA", "BBB", "CCC"]

    assert projection.metadata.evidence.snapshotSource == "read_only_snapshot"
    assert projection.metadata.evidence.deterministic is True
    assert projection.metadata.evidence.sideEffectFree is True


def test_portfolio_risk_attribution_reports_missing_data_and_is_input_order_stable() -> None:
    service = PortfolioRiskAttributionService()
    snapshot = {"as_of": "2026-05-18T09:30:00Z", "currency": "USD"}
    position_weights = [
        _weight("BBB", 0.0),
        _weight("AAA", 0.6),
        _weight("DDD", 0.4),
        _weight("CCC", "bad"),
    ]
    position_market_values = [_market_value("AAA", 600.0), _market_value("DDD", None)]
    classifications = [
        _classification("DDD", sector=None, industry="Biotech"),
        _classification("AAA", sector="Technology", industry="Software"),
    ]
    risk_metrics = [_risk_metric("AAA", 0.2), _risk_metric("DDD", "bad")]
    factor_exposures = [
        _factor_exposure("AAA", factor_id="momentum.momentum_21d", exposure=1.0, factor_risk=0.5),
    ]

    original_snapshot = copy.deepcopy(snapshot)
    original_weights = copy.deepcopy(position_weights)
    original_market_values = copy.deepcopy(position_market_values)
    original_classifications = copy.deepcopy(classifications)
    original_risk_metrics = copy.deepcopy(risk_metrics)
    original_factor_exposures = copy.deepcopy(factor_exposures)

    first = service.build_projection(
        snapshot=snapshot,
        position_weights=position_weights,
        position_market_values=position_market_values,
        classifications=classifications,
        risk_metrics=risk_metrics,
        factor_exposures=factor_exposures,
    )
    second = service.build_projection(
        snapshot=snapshot,
        position_weights=list(reversed(position_weights)),
        position_market_values=list(reversed(position_market_values)),
        classifications=list(reversed(classifications)),
        risk_metrics=list(reversed(risk_metrics)),
        factor_exposures=list(reversed(factor_exposures)),
    )

    assert first.model_dump() == second.model_dump()
    assert snapshot == original_snapshot
    assert position_weights == original_weights
    assert position_market_values == original_market_values
    assert classifications == original_classifications
    assert risk_metrics == original_risk_metrics
    assert factor_exposures == original_factor_exposures

    assert first.coverage.totalPositions == 4
    assert first.coverage.eligiblePositions == 2
    assert first.coverage.invalidWeightCount == 1
    assert first.coverage.zeroWeightCount == 1
    assert first.coverage.marketValueCount == 1
    assert first.coverage.missingMarketValueCount == 1
    assert first.coverage.sectorCount == 1
    assert first.coverage.missingSectorCount == 1
    assert first.coverage.industryCount == 2
    assert first.coverage.positionRiskMetricCount == 1
    assert first.coverage.missingPositionRiskMetricCount == 1
    assert first.coverage.factorCoverageById == {"momentum.momentum_21d": 1}
    assert first.warnings == (
        "invalid_weight",
        "zero_weight",
        "missing_market_value",
        "missing_sector",
        "missing_position_risk_metric",
        "missing_factor_exposure",
        "invalid_position_risk_metric",
    )

    assert [item.symbol for item in first.byPosition] == ["AAA", "DDD"]

    ddd = first.byPosition[1]
    assert ddd.sector == "UNCLASSIFIED"
    assert ddd.industry == "Biotech"
    assert ddd.marketValue == pytest.approx(0.0)
    assert ddd.marketValueWeightPct == pytest.approx(0.0)
    assert ddd.concentrationContribution == pytest.approx(0.16)
    assert ddd.specificRiskContribution == pytest.approx(0.0)
    assert ddd.factorContribution == pytest.approx(0.0)
    assert ddd.totalContribution == pytest.approx(0.16)
    assert ddd.warnings == (
        "missing_market_value",
        "missing_sector",
        "missing_position_risk_metric",
        "missing_factor_exposure",
    )

    assert list(first.byFactorId) == ["momentum.momentum_21d"]
    assert first.byFactorId["momentum.momentum_21d"].missingPositionCount == 1
    assert first.bySector[0].label == "Technology"
    assert first.bySector[1].label == "UNCLASSIFIED"


def test_portfolio_risk_attribution_service_has_no_accounting_broker_or_runtime_wiring_imports() -> None:
    import src.services.portfolio_risk_attribution as module

    source = inspect.getsource(module)
    forbidden_fragments = (
        "src.storage",
        "src.repositories",
        "portfolio_service",
        "portfolio_import_service",
        "portfolio_ibkr_sync_service",
        "PortfolioCashLedger",
        "PortfolioPositionLot",
        "create_trade_event",
        "create_cash_ledger_event",
        "sync_read_only_account_state",
        "api.v1.endpoints",
        "scanner",
        "backtest",
    )

    for fragment in forbidden_fragments:
        assert fragment not in source
