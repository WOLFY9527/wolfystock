# -*- coding: utf-8 -*-
"""Contract tests for the advisory-only portfolio scenario risk read model."""

from __future__ import annotations

import copy
import inspect
import json

import pytest

from src.services.portfolio_scenario_risk import PortfolioScenarioRiskService


def _position(symbol: str, market_value: float, bucket: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {"symbol": symbol, "market_value": market_value}
    if bucket is not None:
        payload["bucket"] = bucket
    return payload


def _exposure(
    symbol: str,
    label: str,
    *,
    exposure: float = 1.0,
    label_type: str = "explicit_label",
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "label": label,
        "label_type": label_type,
        "exposure": exposure,
    }


def _scenario(name: str, shocks: dict[str, float]) -> dict[str, object]:
    return {"name": name, "shocks": shocks}


def test_portfolio_scenario_risk_calculates_symbol_and_proxy_shock_impacts() -> None:
    service = PortfolioScenarioRiskService()

    projection = service.build_projection(
        as_of="2026-05-18T09:30:00Z",
        positions=[
            _position("NVDA", 1000.0, "AI Semis"),
            _position("MSFT", 500.0, "Mega Cap Software"),
            _position("BND", 500.0, "Defensive Bonds"),
        ],
        exposures=[
            _exposure("NVDA", "QQQ", label_type="index_proxy"),
            _exposure("MSFT", "QQQ", exposure=0.8, label_type="index_proxy"),
        ],
        scenario_shocks=[
            _scenario("nvda_gap_down", {"NVDA": -0.10}),
            _scenario("qqq_proxy_down", {"QQQ": -0.05}),
        ],
    ).model_dump()

    assert projection["readModelType"] == "portfolio_scenario_risk_advisory_v1"
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
    assert coverage["totalMarketValue"] == pytest.approx(2000.0)
    assert coverage["effectiveWeightSum"] == pytest.approx(1.0)
    assert coverage["explicitExposureRows"] == 2
    assert coverage["labelsWithExplicitCoverage"] == ["QQQ"]

    symbol_scenario = projection["scenarios"][0]
    assert symbol_scenario["name"] == "nvda_gap_down"
    assert symbol_scenario["portfolioImpactPct"] == pytest.approx(-5.0)
    assert symbol_scenario["portfolioImpactAmount"] == pytest.approx(-100.0)
    assert symbol_scenario["coveredWeight"] == pytest.approx(0.5)
    assert symbol_scenario["coveredMarketValue"] == pytest.approx(1000.0)
    assert symbol_scenario["missingCoverage"] == []
    assert [item["symbol"] for item in symbol_scenario["positionContributions"]] == [
        "NVDA",
        "BND",
        "MSFT",
    ]
    assert symbol_scenario["positionContributions"][0]["impactAmount"] == pytest.approx(-100.0)
    assert symbol_scenario["positionContributions"][0]["contributionToScenarioLoss"] == pytest.approx(1.0)

    proxy_scenario = projection["scenarios"][1]
    assert proxy_scenario["name"] == "qqq_proxy_down"
    assert proxy_scenario["portfolioImpactPct"] == pytest.approx(-3.5)
    assert proxy_scenario["portfolioImpactAmount"] == pytest.approx(-70.0)
    assert proxy_scenario["coveredWeight"] == pytest.approx(0.75)
    assert proxy_scenario["coveredMarketValue"] == pytest.approx(1500.0)
    assert proxy_scenario["warnings"] == ["missing_scenario_coverage"]
    assert proxy_scenario["missingCoverage"] == [
        {"label": "QQQ", "labelType": "index_proxy", "missingSymbols": ["BND"]}
    ]

    assert [item["symbol"] for item in proxy_scenario["positionContributions"]] == [
        "NVDA",
        "MSFT",
        "BND",
    ]
    nvda, msft, bnd = proxy_scenario["positionContributions"]
    assert nvda["impactPct"] == pytest.approx(-2.5)
    assert nvda["impactAmount"] == pytest.approx(-50.0)
    assert nvda["contributionToScenarioLoss"] == pytest.approx(0.7143)
    assert nvda["appliedShocks"] == [
        {
            "label": "QQQ",
            "labelType": "index_proxy",
            "shockPct": -5.0,
            "exposure": 1.0,
            "impactPct": -2.5,
            "impactAmount": -50.0,
        }
    ]
    assert msft["impactPct"] == pytest.approx(-1.0)
    assert msft["impactAmount"] == pytest.approx(-20.0)
    assert msft["contributionToScenarioLoss"] == pytest.approx(0.2857)
    assert bnd["impactPct"] is None
    assert bnd["impactAmount"] is None
    assert bnd["warnings"] == ["missing_scenario_coverage"]

    assert [item["bucket"] for item in proxy_scenario["bucketContributions"]] == [
        "AI Semis",
        "Mega Cap Software",
    ]
    assert proxy_scenario["bucketContributions"][0]["impactAmount"] == pytest.approx(-50.0)
    assert proxy_scenario["bucketContributions"][1]["impactAmount"] == pytest.approx(-20.0)


def test_portfolio_scenario_risk_reports_missing_coverage_without_inferring_labels() -> None:
    service = PortfolioScenarioRiskService()
    positions = [
        {"symbol": "AAA", "weight": 0.60},
        {"symbol": "BBB", "weight": 0.40},
    ]
    exposures = [_exposure("AAA", "growth_theme", label_type="theme")]
    scenario_shocks = [_scenario("theme_and_currency", {"growth_theme": -0.10, "USD": 0.02})]

    original_positions = copy.deepcopy(positions)
    original_exposures = copy.deepcopy(exposures)
    original_scenarios = copy.deepcopy(scenario_shocks)

    projection = service.build_projection(
        positions=positions,
        exposures=exposures,
        scenario_shocks=scenario_shocks,
    ).model_dump()

    assert positions == original_positions
    assert exposures == original_exposures
    assert scenario_shocks == original_scenarios

    scenario = projection["scenarios"][0]
    assert scenario["portfolioImpactPct"] == pytest.approx(-6.0)
    assert scenario["portfolioImpactAmount"] is None
    assert scenario["coveredWeight"] == pytest.approx(0.6)
    assert scenario["coveredMarketValue"] is None
    assert scenario["warnings"] == ["missing_scenario_coverage"]
    assert scenario["missingCoverage"] == [
        {"label": "GROWTH_THEME", "labelType": "theme", "missingSymbols": ["BBB"]},
        {"label": "USD", "labelType": "explicit_label", "missingSymbols": ["AAA", "BBB"]},
    ]
    assert [item["symbol"] for item in scenario["positionContributions"]] == ["AAA", "BBB"]
    assert scenario["positionContributions"][0]["appliedShocks"][0]["label"] == "GROWTH_THEME"
    assert scenario["positionContributions"][1]["warnings"] == ["missing_scenario_coverage"]


def test_portfolio_scenario_risk_exposes_advisory_no_mutation_flags() -> None:
    service = PortfolioScenarioRiskService()

    projection = service.build_projection(
        positions=[_position("NVDA", 1000.0)],
        scenario_shocks=[_scenario("nvda_gap_down", {"NVDA": -0.10})],
    ).model_dump()

    metadata = projection["metadata"]
    assert metadata["deterministic"] is True
    assert metadata["sideEffectFree"] is True
    assert metadata["inputSource"] == "caller_supplied_positions_exposures_and_scenarios"
    assert metadata["noBrokerSync"] is True
    assert metadata["noAccountingMutation"] is True
    assert metadata["noOrderPlacement"] is True
    assert metadata["notInvestmentAdvice"] is True
    assert metadata["noProviderRuntime"] is True

    serialized = json.dumps(projection, sort_keys=True).lower()
    for forbidden in (
        "broker_sync",
        "cash_ledger_mutation",
        "holdings_mutation",
        "cost_basis_mutation",
        "account_snapshot_write",
        "order_placement",
    ):
        assert forbidden not in serialized


def test_portfolio_scenario_risk_has_no_broker_accounting_provider_or_runtime_imports() -> None:
    import src.services.portfolio_scenario_risk as module

    source = inspect.getsource(module)
    forbidden_fragments = (
        "src.repositories",
        "src.storage",
        "portfolio_service",
        "portfolio_import_service",
        "portfolio_ibkr_sync_service",
        "portfolio_risk_service",
        "PortfolioCashLedger",
        "PortfolioPositionLot",
        "create_trade_event",
        "create_cash_ledger_event",
        "sync_read_only_account_state",
        "scanner",
        "backtest",
        "api.v1.endpoints",
        "data_provider",
        "market_cache",
        "runtime",
    )

    for fragment in forbidden_fragments:
        assert fragment not in source
