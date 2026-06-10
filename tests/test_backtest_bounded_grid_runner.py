# -*- coding: utf-8 -*-
"""Contracts for the bounded diagnostic parameter-grid runner."""

from __future__ import annotations

import copy
import json
import inspect
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from src.core.rule_backtest_engine import ParsedStrategy
from src.services import backtest_bounded_grid_runner as runner_module
from src.services.backtest_bounded_grid_runner import run_bounded_parameter_grid_diagnostic
from src.services.backtest_parameter_stability import build_parameter_stability_plan

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "backtest"


class _BombEngine:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, **_: Any) -> dict[str, Any]:
        self.calls += 1
        raise AssertionError("engine must not run")


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _fixture_input() -> dict[str, Any]:
    return dict(_load_fixture("rule_backtest_compute_shadow_cli_v4_ma_crossover.json")["input"])


def _make_bars() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            code="SAFE",
            date=date.fromisoformat(bar["date"]),
            open=float(bar["open"]),
            high=float(bar["high"]),
            low=float(bar["low"]),
            close=float(bar["close"]),
            volume=float(bar["volume"]),
        )
        for bar in _fixture_input()["bars"]
    ]


def _parsed_strategy() -> ParsedStrategy:
    payload = _fixture_input()["parsed_strategy"]
    return ParsedStrategy(
        version=str(payload["version"]),
        timeframe=str(payload["timeframe"]),
        source_text=str(payload.get("source_text") or ""),
        normalized_text=str(payload.get("normalized_text") or ""),
        entry=dict(payload["entry"]),
        exit=dict(payload["exit"]),
        confidence=float(payload.get("confidence", 1.0)),
        needs_confirmation=bool(payload.get("needs_confirmation", False)),
        ambiguities=list(payload.get("ambiguities", [])),
        summary=dict(payload.get("summary", {})),
        max_lookback=int(payload["max_lookback"]),
        strategy_kind=str(payload["strategy_kind"]),
        setup=dict(payload.get("setup", {})),
        strategy_spec=dict(payload.get("strategy_spec", {})),
        executable=bool(payload.get("executable", False)),
        normalization_state=str(payload.get("normalization_state", "normalized_contract")),
        assumptions=list(payload.get("assumptions", [])),
        assumption_groups=list(payload.get("assumption_groups", [])),
        unsupported_reason=payload.get("unsupported_reason"),
        unsupported_details=list(payload.get("unsupported_details", [])),
        unsupported_extensions=list(payload.get("unsupported_extensions", [])),
        detected_strategy_family=payload.get("detected_strategy_family"),
        core_intent_summary=payload.get("core_intent_summary"),
        interpretation_confidence=float(payload.get("interpretation_confidence", payload.get("confidence", 1.0))),
        supported_portion_summary=payload.get("supported_portion_summary"),
        rewrite_suggestions=list(payload.get("rewrite_suggestions", [])),
        parse_warnings=list(payload.get("parse_warnings", [])),
    )


def _plan(
    parameter_grid: dict[str, list[Any]],
    *,
    max_combinations: int | None = None,
    overflow_policy: str = "reject",
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if max_combinations is not None:
        kwargs["max_combinations"] = max_combinations
    return build_parameter_stability_plan(
        strategy_id="ma-cross-fixture",
        dataset_id="supplied-bars-v1",
        base_parameters={
            "strategy_spec.signal.fast_type": "simple",
            "strategy_spec.signal.slow_type": "simple",
        },
        parameter_grid=parameter_grid,
        metric_keys=["total_return_pct", "max_drawdown_pct", "trade_count"],
        primary_metric="total_return_pct",
        risk_metric="max_drawdown_pct",
        min_completed_runs=2,
        overflow_policy=overflow_policy,
        **kwargs,
    )


def test_executes_small_accepted_grid_with_supplied_bars_and_aggregates_metrics() -> None:
    plan = _plan(
        {
            "strategy_spec.signal.fast_period": [2, 3],
            "strategy_spec.signal.slow_period": [5],
        }
    )
    descriptor_snapshot = copy.deepcopy(plan["parameter_grid_descriptor"])
    bundle_snapshot = copy.deepcopy(plan["parameter_grid_request_bundle"])
    parsed = _parsed_strategy()
    parsed_snapshot = copy.deepcopy(parsed.to_dict())

    result = run_bounded_parameter_grid_diagnostic(
        parameter_stability_plan=plan,
        parsed_strategy=parsed,
        bars=_make_bars(),
        code="SAFE",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 10),
        lookback_bars=20,
        initial_capital=100000.0,
        fee_bps=2.5,
        slippage_bps=1.25,
    )

    assert result["state"] == "completed"
    assert result["diagnosticOnly"] is True
    assert result["gridExecutionCount"] == 2
    assert result["acceptedRequestCount"] == 2
    assert result["executionSemantics"]["providerCallsExecuted"] is False
    assert result["executionSemantics"]["marketCacheAccessed"] is False
    assert result["executionSemantics"]["storageMutation"] is False
    assert result["executionSemantics"]["optimizerExecuted"] is False
    assert result["executionSemantics"]["winnerPromotion"] is False
    assert result["executionSemantics"]["decisionGrade"] is False
    assert [item["parameterValues"] for item in result["requestResults"]] == [
        {"strategy_spec.signal.fast_period": 2, "strategy_spec.signal.slow_period": 5},
        {"strategy_spec.signal.fast_period": 3, "strategy_spec.signal.slow_period": 5},
    ]
    for item in result["requestResults"]:
        assert item["state"] == "completed"
        assert {"total_return_pct", "max_drawdown_pct", "trade_count"} <= set(item["metrics"])

    surface = result["parameterStabilitySurface"]
    assert surface["state"] == "available"
    assert surface["metric_surface"]["completed_run_count"] == 2
    assert surface["execution_semantics"]["strategy_execution_count"] == 0
    assert surface["best_summary"]["automatic_winner_promotion"] is False
    assert surface["diagnostic_only"] is True

    assert plan["parameter_grid_descriptor"] == descriptor_snapshot
    assert plan["parameter_grid_request_bundle"] == bundle_snapshot
    assert parsed.to_dict() == parsed_snapshot
    assert descriptor_snapshot["execution_count"] == 0
    assert descriptor_snapshot["optimizer_executed"] is False
    assert descriptor_snapshot["winner_promotion"] is False
    assert descriptor_snapshot["decision_grade"] is False
    assert bundle_snapshot["execution_count"] == 0
    assert bundle_snapshot["optimizer_executed"] is False
    assert bundle_snapshot["winner_promotion"] is False
    assert bundle_snapshot["decision_grade"] is False


def test_rejects_over_cap_grid_by_default_without_truncating_or_running_engine() -> None:
    plan = _plan(
        {
            "strategy_spec.signal.fast_period": list(range(1, 12)),
            "strategy_spec.signal.slow_period": [20],
        }
    )
    engine = _BombEngine()

    result = run_bounded_parameter_grid_diagnostic(
        parameter_stability_plan=plan,
        parsed_strategy=_parsed_strategy(),
        bars=_make_bars(),
        code="SAFE",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 12),
        lookback_bars=4,
        initial_capital=10000.0,
        fee_bps=0.0,
        slippage_bps=0.0,
        engine=engine,
    )

    assert result["state"] == "rejected"
    assert result["failClosedReasonCode"] == "max_combinations_rejected"
    assert result["overflowPolicy"] == "reject"
    assert result["gridExecutionCount"] == 0
    assert result["requestResults"] == []
    assert engine.calls == 0


def test_rejects_unsafe_parameter_paths_before_engine_execution() -> None:
    plan = _plan({"code": ["AAPL"], "strategy_spec.signal.fast_period": [2]})
    engine = _BombEngine()

    result = run_bounded_parameter_grid_diagnostic(
        parameter_stability_plan=plan,
        parsed_strategy=_parsed_strategy(),
        bars=_make_bars(),
        code="SAFE",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 12),
        lookback_bars=4,
        initial_capital=10000.0,
        fee_bps=0.0,
        slippage_bps=0.0,
        engine=engine,
    )

    assert result["state"] == "rejected"
    assert result["failClosedReasonCode"] == "unsafe_parameter_path"
    assert result["failClosedDiagnostics"]["parameterPath"] == "code"
    assert result["gridExecutionCount"] == 0
    assert engine.calls == 0


def test_rejects_request_identity_fields_before_engine_execution() -> None:
    plan = _plan({"strategy_spec.signal.fast_period": [2], "strategy_spec.signal.slow_period": [5]})
    request_bundle = copy.deepcopy(plan["parameter_grid_request_bundle"])
    request_bundle["requests"][0]["external_run_id"] = "stored-run-42"
    request_bundle["requests"][0]["request_id"] = "client-request-42"
    engine = _BombEngine()

    result = run_bounded_parameter_grid_diagnostic(
        parameter_grid_request_bundle=request_bundle,
        parameter_grid_descriptor=plan["parameter_grid_descriptor"],
        parameter_stability_plan=plan,
        parsed_strategy=_parsed_strategy(),
        bars=_make_bars(),
        code="SAFE",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 12),
        lookback_bars=4,
        initial_capital=10000.0,
        fee_bps=0.0,
        slippage_bps=0.0,
        engine=engine,
    )

    assert result["state"] == "rejected"
    assert result["failClosedReasonCode"] == "request_identity_fields_not_allowed"
    assert result["failClosedDiagnostics"]["fieldName"] == "external_run_id"
    assert result["failClosedDiagnostics"]["requestIndex"] == 1
    assert result["gridExecutionCount"] == 0
    assert engine.calls == 0


def test_zero_timeout_budget_fails_closed_before_engine_execution() -> None:
    plan = _plan({"strategy_spec.signal.fast_period": [2], "strategy_spec.signal.slow_period": [4]})
    engine = _BombEngine()

    result = run_bounded_parameter_grid_diagnostic(
        parameter_stability_plan=plan,
        parsed_strategy=_parsed_strategy(),
        bars=_make_bars(),
        code="SAFE",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 12),
        lookback_bars=4,
        initial_capital=10000.0,
        fee_bps=0.0,
        slippage_bps=0.0,
        total_timeout_seconds=0,
        engine=engine,
    )

    assert result["state"] == "timeout_budget_exhausted"
    assert result["failClosedReasonCode"] == "total_timeout_budget_exhausted_before_execution"
    assert result["timeout"]["mode"] == "synchronous_between_request_budget"
    assert result["timeout"]["exhausted"] is True
    assert result["gridExecutionCount"] == 0
    assert engine.calls == 0


def test_runner_surface_does_not_synthesize_external_or_stored_run_identity() -> None:
    plan = _plan({"strategy_spec.signal.fast_period": [3], "strategy_spec.signal.slow_period": [5]})

    result = run_bounded_parameter_grid_diagnostic(
        parameter_stability_plan=plan,
        parsed_strategy=_parsed_strategy(),
        bars=_make_bars(),
        code="SAFE",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 10),
        lookback_bars=20,
        initial_capital=100000.0,
        fee_bps=2.5,
        slippage_bps=1.25,
    )

    assert result["state"] == "completed"
    assert result["executionSemantics"]["storageMutation"] is False
    assert result["executionSemantics"]["storedRunIdentityCreated"] is False
    assert all("externalRunId" not in item for item in result["requestResults"])
    assert all("runId" not in item for item in result["requestResults"])

    surface_rows = list(result["parameterStabilitySurface"]["metric_surface"]["rows"] or [])
    assert surface_rows
    assert all(row["external_run_id"] is None for row in surface_rows)


def test_runner_does_not_call_service_storage_provider_or_market_cache_paths() -> None:
    plan = _plan({"strategy_spec.signal.fast_period": [3], "strategy_spec.signal.slow_period": [5]})

    with (
        patch(
            "src.services.us_history_helper.fetch_daily_history_with_local_us_fallback",
            side_effect=AssertionError,
        ) as fetch_history,
        patch(
            "src.repositories.stock_repo.StockRepository.save_dataframe",
            side_effect=AssertionError,
        ) as save_dataframe,
        patch(
            "src.repositories.rule_backtest_repo.RuleBacktestRepository.save_run",
            side_effect=AssertionError,
        ) as save_run,
        patch(
            "src.repositories.rule_backtest_repo.RuleBacktestRepository.update_run",
            side_effect=AssertionError,
        ) as update_run,
        patch(
            "src.repositories.rule_backtest_repo.RuleBacktestRepository.save_trades",
            side_effect=AssertionError,
        ) as save_trades,
        patch(
            "src.storage.DatabaseManager.sync_phase_e_rule_backtest_shadow",
            side_effect=AssertionError,
        ) as sync_shadow,
        patch(
            "src.services.market_cache.MarketCache.get_or_refresh",
            side_effect=AssertionError,
        ) as market_cache,
        patch(
            "src.services.rule_backtest_text_completion.RuleBacktestTextCompletion.call_text",
            side_effect=AssertionError,
        ) as llm_call,
    ):
        result = run_bounded_parameter_grid_diagnostic(
            parameter_stability_plan=plan,
            parsed_strategy=_parsed_strategy(),
            bars=_make_bars(),
            code="SAFE",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 10),
            lookback_bars=20,
            initial_capital=100000.0,
            fee_bps=2.5,
            slippage_bps=1.25,
        )

    assert result["state"] == "completed"
    for mocked in (
        fetch_history,
        save_dataframe,
        save_run,
        update_run,
        save_trades,
        sync_shadow,
        market_cache,
        llm_call,
    ):
        mocked.assert_not_called()


def test_runner_source_does_not_import_service_storage_provider_or_market_cache_paths() -> None:
    source = inspect.getsource(runner_module)

    for forbidden in (
        "RuleBacktestService",
        "RuleBacktestRepository",
        "MarketCache",
        "_ensure_market_history",
        "get_or_refresh",
        "save_run",
        "save_trades",
    ):
        assert forbidden not in source


def test_runner_source_does_not_expose_public_api_or_schema_surface() -> None:
    source = inspect.getsource(runner_module)

    for forbidden in (
        "api.v1",
        "/api/v1/backtest",
        "schemas.backtest",
        "BacktestRunRequest",
        "BacktestRunResponse",
        "router",
    ):
        assert forbidden not in source
