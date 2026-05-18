# -*- coding: utf-8 -*-
"""Portfolio construction advisory read-model contract tests."""

from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path

from src.schemas.portfolio_construction import PortfolioConstructionReadModel
from src.services.portfolio_construction_service import PortfolioConstructionReadModelService


FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "portfolio"
    / "portfolio_snapshot_read_model_dto.json"
)


def _load_snapshot() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_portfolio_construction_read_model_projects_advisory_target_weight_drift() -> None:
    service = PortfolioConstructionReadModelService()
    snapshot = _load_snapshot()

    read_model = service.build_read_model(
        snapshot=snapshot,
        target_weights={"600519": 50.0, "AAPL": 45.0, "MSFT": 5.0},
        min_trade_threshold=0.5,
        max_position_weight=50.0,
        cash_buffer_target=15.0,
        risk_budget_notes={
            "portfolio": ["Fixture risk budget only; not a trade instruction."],
            "600519": ["Single-name cap under review."],
        },
        confidence=0.72,
        confidence_reasons=["fixture_snapshot", "stale_fx_caps_confidence"],
    )

    payload = PortfolioConstructionReadModel(**read_model.model_dump()).model_dump()
    rows = {item["symbol"]: item for item in payload["positions"]}

    assert payload["readModelType"] == "portfolio_construction_advisory_v1"
    assert payload["advisoryOnly"] is True
    assert payload["accountingMutation"] is False
    assert payload["brokerIntegration"] is False
    assert payload["tradeExecution"] is False
    assert payload["executionReadiness"] == "advisory_only_not_trade_execution"
    assert payload["targetSource"] == "caller_supplied_fixture"
    assert payload["riskBudgetNotes"] == ["Fixture risk budget only; not a trade instruction."]
    assert payload["constraints"] == {
        "minTradeThreshold": 0.5,
        "maxPositionWeight": 50.0,
        "cashBufferTarget": 15.0,
        "noTradeBand": 1.0,
    }
    assert payload["currentCashWeight"] == 13.8889
    assert payload["targetCashWeight"] == 15.0
    assert payload["cashDrift"] == -1.1111
    assert payload["cashSuggestedDeltaWeight"] == 1.1111
    assert payload["cashTradeDirection"] == "raise_cash"
    assert payload["constraintViolations"] == [
        {
            "code": "cash_buffer_below_target",
            "severity": "warning",
            "message": "Current cash weight 13.8889% is below the 15.0% advisory cash buffer target.",
        }
    ]

    assert rows["600519"]["currentWeight"] == 55.2995
    assert rows["600519"]["targetWeight"] == 50.0
    assert rows["600519"]["drift"] == 5.2995
    assert rows["600519"]["suggestedDeltaWeight"] == -5.2995
    assert rows["600519"]["estimatedTradeDirection"] == "sell"
    assert rows["600519"]["suggestedAction"] == "reduce_exposure"
    assert rows["600519"]["riskBudgetNotes"] == ["Single-name cap under review."]
    assert rows["600519"]["constraintViolations"] == [
        {
            "code": "max_position_weight_exceeded",
            "severity": "warning",
            "message": "Current weight 55.2995% is above the 50.0% advisory cap.",
        }
    ]

    assert rows["AAPL"]["currentWeight"] == 44.7005
    assert rows["AAPL"]["targetWeight"] == 45.0
    assert rows["AAPL"]["drift"] == -0.2995
    assert rows["AAPL"]["suggestedDeltaWeight"] == 0.0
    assert rows["AAPL"]["estimatedTradeDirection"] == "hold"
    assert rows["AAPL"]["suggestedAction"] == "no_action"
    assert "within_drift_threshold" in rows["AAPL"]["noActionReasons"]

    assert rows["MSFT"]["currentWeight"] == 0.0
    assert rows["MSFT"]["targetWeight"] == 5.0
    assert rows["MSFT"]["drift"] == -5.0
    assert rows["MSFT"]["suggestedDeltaWeight"] == 5.0
    assert rows["MSFT"]["estimatedTradeDirection"] == "buy"
    assert rows["MSFT"]["suggestedAction"] == "increase_exposure"
    assert rows["MSFT"]["evidence"]["source"] == "target_only_no_current_holding"
    assert "advisory_read_model_only" in rows["MSFT"]["noTradeReasons"]

    assert payload["metadata"]["confidence"] == 0.72
    assert payload["metadata"]["confidenceReasons"] == ["fixture_snapshot", "stale_fx_caps_confidence"]
    assert payload["metadata"]["evidence"]["snapshotSource"] == "backend_snapshot"
    assert payload["metadata"]["evidence"]["deterministic"] is True
    assert payload["metadata"]["evidence"]["sideEffectFree"] is True


def test_portfolio_construction_read_model_is_deterministic_and_does_not_mutate_snapshot() -> None:
    service = PortfolioConstructionReadModelService()
    snapshot = _load_snapshot()
    original_snapshot = copy.deepcopy(snapshot)

    first = service.build_read_model(
        snapshot=snapshot,
        target_weights={"AAPL": 45.0, "600519": 50.0, "MSFT": 5.0},
        min_trade_threshold=0.5,
        max_position_weight=50.0,
        cash_buffer_target=15.0,
    ).model_dump()
    second = service.build_read_model(
        snapshot=snapshot,
        target_weights={"MSFT": 5.0, "600519": 50.0, "AAPL": 45.0},
        min_trade_threshold=0.5,
        max_position_weight=50.0,
        cash_buffer_target=15.0,
    ).model_dump()

    assert first == second
    assert snapshot == original_snapshot

    serialized = json.dumps(first, sort_keys=True).lower()
    for forbidden in (
        "order_id",
        "orderid",
        "broker_connection",
        "brokerconnection",
        "cash_ledger_mutation",
        "holding_mutation",
        "cost_basis_mutation",
        "pnl_mutation",
    ):
        assert forbidden not in serialized


def test_portfolio_construction_service_has_no_accounting_or_broker_mutation_imports() -> None:
    import src.services.portfolio_construction_service as module

    source = inspect.getsource(module)
    forbidden_fragments = (
        "src.storage",
        "src.repositories",
        "portfolio_service",
        "portfolio_import_service",
        "portfolio_ibkr_sync_service",
        "PortfolioTrade",
        "PortfolioCashLedger",
        "PortfolioCorporateAction",
        "PortfolioDailySnapshot",
        "PortfolioPosition",
        "PortfolioPositionLot",
        "commit_import_records",
        "sync_read_only_account_state",
        "refresh_fx_rates",
        "create_trade_event",
        "update_trade_event",
        "delete_trade_event",
        "create_cash_ledger_event",
        "delete_cash_ledger_event",
        "create_corporate_action",
        "delete_corporate_action",
    )

    for fragment in forbidden_fragments:
        assert fragment not in source


def test_portfolio_construction_read_model_blocks_trade_when_delta_is_below_min_threshold() -> None:
    service = PortfolioConstructionReadModelService()
    snapshot = _load_snapshot()

    read_model = service.build_read_model(
        snapshot=snapshot,
        target_weights={"AAPL": 45.2},
        drift_threshold=0.1,
        min_trade_threshold=1.0,
    ).model_dump()

    row = next(item for item in read_model["positions"] if item["symbol"] == "AAPL")

    assert row["drift"] == -0.4995
    assert row["suggestedDeltaWeight"] == 0.0
    assert row["estimatedTradeDirection"] == "hold"
    assert row["suggestedAction"] == "no_action"
    assert "below_min_trade_threshold" in row["noActionReasons"]


def test_portfolio_construction_read_model_handles_missing_market_value_and_tiny_portfolio_without_trade_advice() -> None:
    service = PortfolioConstructionReadModelService()
    snapshot = {
        "as_of": "2026-05-18T09:30:00Z",
        "currency": "USD",
        "total_market_value": 0.005,
        "total_cash": 0.0,
        "total_equity": 0.005,
        "portfolioRiskEvidence": {"source": "tiny_fixture"},
        "accounts": [
            {
                "account_id": 1,
                "positions": [
                    {
                        "symbol": "TSLA",
                        "market": "us",
                        "currency": "USD",
                        "market_value_base": None,
                    }
                ],
            }
        ],
    }
    original_snapshot = copy.deepcopy(snapshot)

    read_model = service.build_read_model(
        snapshot=snapshot,
        target_weights={"TSLA": 50.0},
        drift_threshold=0.25,
        min_trade_threshold=0.5,
    ).model_dump()

    row = read_model["positions"][0]

    assert read_model["totalMarketValue"] == 0.005
    assert "portfolio_value_too_small" in read_model["noTradeReasons"]
    assert row["currentWeight"] == 0.0
    assert row["targetWeight"] == 50.0
    assert row["suggestedDeltaWeight"] == 0.0
    assert row["estimatedTradeDirection"] == "hold"
    assert row["suggestedAction"] == "no_action"
    assert "missing_market_value" in row["noActionReasons"]
    assert "portfolio_value_too_small" in row["noActionReasons"]
    assert row["constraintViolations"] == [
        {
            "code": "missing_market_value",
            "severity": "warning",
            "message": "Current holding has no usable market value in the read-only snapshot.",
        }
    ]
    assert snapshot == original_snapshot
