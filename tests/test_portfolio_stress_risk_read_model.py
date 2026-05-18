# -*- coding: utf-8 -*-
"""Contract tests for the advisory-only portfolio stress / VaR read model."""

from __future__ import annotations

import copy
import inspect
import json

import pytest

from src.services.portfolio_stress_risk import PortfolioStressRiskService


def _scenario(name: str, shocks: dict[str, float]) -> dict[str, object]:
    return {"name": name, "shocks": shocks}


def _sample(name: str, returns: dict[str, float]) -> dict[str, object]:
    return {"name": name, "returns": returns}


def test_portfolio_stress_risk_projects_scenario_loss_contributions_and_var_summary() -> None:
    service = PortfolioStressRiskService()

    projection = service.build_projection(
        as_of="2026-05-18T09:30:00Z",
        positions=[
            {"symbol": "AAA", "market_value": 500.0},
            {"symbol": "BBB", "market_value": 300.0},
            {"symbol": "CCC", "market_value": 200.0},
        ],
        scenario_shocks=[
            _scenario("credit_gap_down", {"AAA": -0.10, "BBB": -0.20}),
            _scenario("index_rebound", {"AAA": 0.05, "BBB": 0.02, "CCC": 0.01}),
        ],
        return_samples=[
            _sample("sample_1", {"AAA": -0.04, "BBB": -0.02, "CCC": -0.01}),
            _sample("sample_2", {"AAA": 0.01, "BBB": -0.03, "CCC": 0.00}),
            _sample("sample_3", {"AAA": -0.07, "BBB": -0.10, "CCC": -0.02}),
            _sample("sample_4", {"AAA": 0.02, "BBB": 0.01, "CCC": 0.03}),
            _sample("sample_5", {"AAA": -0.02, "BBB": -0.01, "CCC": -0.08}),
        ],
        confidence_level=0.60,
    ).model_dump()

    assert projection["readModelType"] == "portfolio_stress_var_advisory_v1"
    assert projection["advisoryOnly"] is True
    assert projection["accountingMutation"] is False
    assert projection["brokerIntegration"] is False
    assert projection["tradeExecution"] is False
    assert projection["executionReadiness"] == "advisory_only_not_trade_execution"
    assert projection["asOf"] == "2026-05-18T09:30:00Z"

    coverage = projection["coverage"]
    assert coverage["totalPositions"] == 3
    assert coverage["positionsWithUsableWeight"] == 3
    assert coverage["positionsWithMarketValue"] == 3
    assert coverage["effectiveWeightSum"] == pytest.approx(1.0)
    assert coverage["totalMarketValue"] == pytest.approx(1000.0)

    scenario = projection["scenarios"][0]
    assert scenario["name"] == "credit_gap_down"
    assert scenario["portfolioImpactPct"] == pytest.approx(-11.0)
    assert scenario["portfolioImpactAmount"] == pytest.approx(-110.0)
    assert scenario["coveredWeight"] == pytest.approx(0.8)
    assert scenario["coveredMarketValue"] == pytest.approx(800.0)
    assert scenario["missingSymbols"] == ["CCC"]
    assert scenario["warnings"] == ["missing_scenario_shock"]

    assert [item["symbol"] for item in scenario["positionContributions"]] == ["BBB", "AAA", "CCC"]
    assert scenario["positionContributions"][0]["impactPct"] == pytest.approx(-6.0)
    assert scenario["positionContributions"][0]["impactAmount"] == pytest.approx(-60.0)
    assert scenario["positionContributions"][0]["contributionToScenarioLoss"] == pytest.approx(0.5455)
    assert scenario["positionContributions"][1]["impactPct"] == pytest.approx(-5.0)
    assert scenario["positionContributions"][1]["impactAmount"] == pytest.approx(-50.0)
    assert scenario["positionContributions"][1]["contributionToScenarioLoss"] == pytest.approx(0.4545)
    assert scenario["positionContributions"][2]["warnings"] == ["missing_scenario_shock"]

    drawdown = projection["drawdownEstimate"]
    assert drawdown["lossPct"] == pytest.approx(11.0)
    assert drawdown["lossAmount"] == pytest.approx(110.0)
    assert drawdown["source"] == "scenario_credit_gap_down"
    assert drawdown["methodology"] == "max_of_worst_scenario_and_historical_cvar"

    historical_var = projection["historicalVar"]
    assert historical_var["available"] is True
    assert historical_var["confidenceLevel"] == pytest.approx(0.60)
    assert historical_var["sampleCount"] == 5
    assert historical_var["varLossPct"] == pytest.approx(2.9)
    assert historical_var["cvarLossPct"] == pytest.approx(4.9)
    assert historical_var["varLossAmount"] == pytest.approx(29.0)
    assert historical_var["cvarLossAmount"] == pytest.approx(49.0)
    assert historical_var["worstSampleReturnPct"] == pytest.approx(-6.9)
    assert historical_var["bestSampleReturnPct"] == pytest.approx(1.9)
    assert historical_var["insufficientDataReasons"] == []
    assert historical_var["missingDataWarnings"] == []

    metadata = projection["metadata"]
    assert metadata["deterministic"] is True
    assert metadata["sideEffectFree"] is True
    assert metadata["inputSource"] == "caller_supplied_positions_and_returns"
    assert metadata["noLivePrices"] is True
    assert metadata["noBrokerSync"] is True
    assert metadata["noAccountingMutation"] is True
    assert metadata["noRuntimeWiring"] is True


def test_portfolio_stress_risk_supports_weight_only_inputs_and_reports_insufficient_data() -> None:
    service = PortfolioStressRiskService()
    positions = [
        {"symbol": "BBB", "weight": 0.4},
        {"symbol": "AAA", "weight": 0.6},
    ]
    scenario_shocks = [_scenario("single_name_selloff", {"AAA": -0.10})]
    return_samples = [
        _sample("sample_1", {"AAA": -0.02}),
        _sample("sample_2", {"AAA": 0.01, "BBB": -0.03}),
    ]

    original_positions = copy.deepcopy(positions)
    original_scenarios = copy.deepcopy(scenario_shocks)
    original_samples = copy.deepcopy(return_samples)

    first = service.build_projection(
        positions=positions,
        scenario_shocks=scenario_shocks,
        return_samples=return_samples,
        confidence_level=0.95,
    ).model_dump()
    second = service.build_projection(
        positions=list(reversed(positions)),
        scenario_shocks=copy.deepcopy(scenario_shocks),
        return_samples=list(reversed(return_samples)),
        confidence_level=0.95,
    ).model_dump()

    assert positions == original_positions
    assert scenario_shocks == original_scenarios
    assert return_samples == original_samples
    assert first == second

    scenario = first["scenarios"][0]
    assert scenario["portfolioImpactPct"] == pytest.approx(-6.0)
    assert scenario["portfolioImpactAmount"] is None
    assert scenario["coveredWeight"] == pytest.approx(0.6)
    assert scenario["coveredMarketValue"] is None
    assert scenario["missingSymbols"] == ["BBB"]
    assert scenario["warnings"] == ["missing_scenario_shock"]

    historical_var = first["historicalVar"]
    assert historical_var["available"] is False
    assert historical_var["sampleCount"] == 2
    assert historical_var["varLossPct"] is None
    assert historical_var["cvarLossPct"] is None
    assert historical_var["insufficientDataReasons"] == ["insufficient_return_samples"]
    assert historical_var["missingDataWarnings"] == ["partial_return_sample_coverage"]

    serialized = json.dumps(first, sort_keys=True).lower()
    for forbidden in (
        "broker_sync",
        "scanner_runtime",
        "backtest_runtime",
        "cash_ledger_mutation",
        "holdings_mutation",
        "cost_basis_mutation",
        "account_snapshot_write",
    ):
        assert forbidden not in serialized


def test_portfolio_stress_risk_service_has_no_accounting_broker_or_runtime_wiring_imports() -> None:
    import src.services.portfolio_stress_risk as module

    source = inspect.getsource(module)
    forbidden_fragments = (
        "src.repositories",
        "src.storage",
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
        "data_provider",
    )

    for fragment in forbidden_fragments:
        assert fragment not in source
