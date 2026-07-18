# -*- coding: utf-8 -*-
"""DATA-037 bounded rule backtest parameter sweep pilot contracts."""

from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

from src.config import Config  # noqa: E402
from src.services.backtest_bounded_grid_runner import run_bounded_parameter_grid_diagnostic  # noqa: E402
from src.services.backtest_parameter_stability import build_parameter_stability_plan  # noqa: E402
from src.services.rule_backtest_service import RuleBacktestService  # noqa: E402
from src.storage import DatabaseManager, StockDaily  # noqa: E402


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "backtest"
FORBIDDEN_PUBLIC_TERMS = (
    "reco" + "mmended",
    "opti" + "mal",
    "should" + " use",
    "best" + " strategy",
    "guaran" + "teed",
    "professional" + "-ready",
    "production" + "-ready",
    "买入" + "建议",
    "卖出" + "建议",
    "持有" + "建议",
    "目标" + "价",
    "止" + "损",
    "仓位" + "建议",
    "建仓" + "建议",
    "加仓" + "建议",
    "减仓" + "建议",
    "交易" + "建议",
    "操作" + "建议",
)


def _load_fixture() -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / "rule_backtest_compute_shadow_cli_v4_ma_crossover.json").read_text(encoding="utf-8"))


def _fixture_input() -> dict[str, Any]:
    return dict(_load_fixture()["input"])


def _parsed_strategy_payload() -> dict[str, Any]:
    return copy.deepcopy(_fixture_input()["parsed_strategy"])


def _seed_history(db: DatabaseManager, code: str = "600519", *, days: int = 60) -> None:
    closes = [
        10.0,
        10.2,
        10.1,
        10.5,
        11.0,
        11.6,
        11.8,
        11.2,
        10.8,
        10.2,
        9.9,
        10.3,
        10.9,
        11.4,
        11.9,
        12.1,
        11.7,
        11.1,
        10.7,
        10.4,
    ]
    start = date(2024, 1, 1)
    with db.get_session() as session:
        for index in range(days):
            close = closes[index % len(closes)] + float(index // len(closes)) * 0.15
            session.add(
                StockDaily(
                    code=code,
                    date=start + timedelta(days=index),
                    open=close - 0.1,
                    high=close + 0.2,
                    low=max(0.01, close - 0.3),
                    close=close,
                    volume=1000.0 + index,
                )
            )
        session.commit()


def _sweep_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "code": "600519",
        "strategy_text": "MA diagnostic comparison",
        "parsed_strategy": _parsed_strategy_payload(),
        "start_date": "2024-01-01",
        "end_date": "2024-02-20",
        "lookback_bars": 20,
        "initial_capital": 100000.0,
        "fee_bps": 2.5,
        "slippage_bps": 1.25,
        "execution_model": {"version": "v1"},
        "confirmed": True,
        "parameter_grid": {
            "strategy_spec.signal.fast_period": [2, 3],
            "strategy_spec.signal.slow_period": [5],
        },
        "max_combinations": 10,
        "total_timeout_seconds": 30.0,
    }
    kwargs.update(overrides)
    return kwargs


class RuleBacktestParameterSweepPilotServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_PATH"] = os.path.join(self._temp_dir.name, "data037_backtest.db")
        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()
        _seed_history(self.db)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self._temp_dir.cleanup()

    def test_parameter_sweep_executes_multiple_local_parameter_sets(self) -> None:
        service = RuleBacktestService(self.db)

        result = service.run_parameter_sweep_pilot(**_sweep_kwargs())

        self.assertEqual(result["state"], "completed")
        self.assertTrue(result["diagnosticOnly"])
        self.assertTrue(result["researchOnly"])
        self.assertTrue(result["notOptimizer"])
        self.assertFalse(result["winnerPromotion"])
        self.assertFalse(result["decisionGrade"])
        self.assertEqual(result["summary"]["completedCount"], 2)
        self.assertEqual(result["summary"]["totalParameterSets"], 2)
        self.assertEqual(result["summary"]["runCount"], 2)
        self.assertEqual(result["summary"]["skippedCount"], 0)
        self.assertEqual(result["summary"]["blockedCount"], 0)
        self.assertEqual(result["datasetMetadata"]["localDataOnly"], True)
        self.assertEqual(result["engine"]["version"], "v1")
        self.assertEqual(result["storage"]["mode"], "response_only")
        lineage = result["datasetLineageReadiness"]
        self.assertEqual(lineage["readinessState"], "diagnostic-only")
        self.assertFalse(lineage["professionalReadinessApproved"])
        self.assertFalse(lineage["decisionGrade"])
        self.assertEqual(lineage["barBoundary"]["barSource"], "local_stock_daily_rows")
        self.assertTrue(lineage["barBoundary"]["localBars"])
        self.assertTrue(lineage["barBoundary"]["suppliedBarsToRunner"])
        self.assertFalse(lineage["barBoundary"]["acceptedAsProviderAuthority"])
        self.assertFalse(lineage["barBoundary"]["providerCallsExecuted"])
        self.assertEqual(lineage["lineageFields"]["adjustedBasis"]["state"], "unknown")
        self.assertEqual(lineage["lineageFields"]["corporateActionPolicy"]["state"], "unknown")
        self.assertEqual(lineage["lineageFields"]["calendarSessionPolicy"]["state"], "unknown")
        self.assertEqual(lineage["lineageFields"]["pointInTimeMembershipStatus"]["state"], "unknown")
        self.assertEqual(lineage["lineageFields"]["survivorshipBiasMarker"]["state"], "unknown")
        self.assertEqual(lineage["sourceAuthority"]["authorityStatus"], "unknown")
        self.assertIn("adjustedBasis", lineage["missingLineageFields"])
        self.assertIn("corporateActionPolicy", lineage["missingLineageFields"])
        self.assertIn("calendarSessionPolicy", lineage["missingLineageFields"])
        self.assertIn("pointInTimeMembershipStatus", lineage["missingLineageFields"])
        self.assertIn("sourceAuthority", lineage["missingLineageFields"])
        self.assertEqual(
            lineage["reproducibility"]["gridDescriptorHashSha256"],
            result["reproducibilityMetadata"]["gridDescriptorHashSha256"],
        )
        self.assertEqual(
            lineage["parameterSetBoundary"]["parameterSetIds"],
            [row["parameterSetId"] for row in result["parameterRows"]],
        )
        self.assertEqual(len(result["parameterRows"]), 2)
        self.assertEqual(len({row["parameterSetId"] for row in result["parameterRows"]}), 2)
        for row in result["parameterRows"]:
            self.assertEqual(row["state"], "completed")
            self.assertIn("total_return_pct", row["metrics"])
            self.assertIn("max_drawdown_pct", row["metrics"])
            self.assertIn("trade_count", row["metrics"])

    def test_parameter_sweep_reproducibility_metadata_is_deterministic(self) -> None:
        service = RuleBacktestService(self.db)

        first = service.run_parameter_sweep_pilot(**_sweep_kwargs())
        second = service.run_parameter_sweep_pilot(**_sweep_kwargs())

        self.assertEqual(first["reproducibilityMetadata"], second["reproducibilityMetadata"])
        self.assertEqual(
            first["reproducibilityMetadata"]["requestBundleId"],
            second["reproducibilityMetadata"]["requestBundleId"],
        )
        self.assertEqual(
            [row["parameterSetId"] for row in first["parameterRows"]],
            [row["parameterSetId"] for row in second["parameterRows"]],
        )

    def test_parameter_sweep_rejects_oversized_grid(self) -> None:
        service = RuleBacktestService(self.db)

        result = service.run_parameter_sweep_pilot(
            **_sweep_kwargs(
                parameter_grid={
                    "strategy_spec.signal.fast_period": list(range(1, 12)),
                    "strategy_spec.signal.slow_period": [20],
                }
            )
        )

        self.assertEqual(result["state"], "rejected")
        self.assertEqual(result["failClosedReasonCode"], "max_combinations_rejected")
        self.assertEqual(result["summary"]["completedCount"], 0)
        self.assertEqual(result["summary"]["failedCount"], 0)
        self.assertEqual(result["datasetLineageReadiness"]["readinessState"], "blocked")
        self.assertEqual(result["datasetLineageReadiness"]["barBoundary"]["barSource"], "not_loaded_fail_closed")
        self.assertFalse(result["datasetLineageReadiness"]["barBoundary"]["providerCallsExecuted"])

    def test_parameter_sweep_rejects_empty_grid(self) -> None:
        service = RuleBacktestService(self.db)

        result = service.run_parameter_sweep_pilot(**_sweep_kwargs(parameter_grid={}))

        self.assertEqual(result["state"], "rejected")
        self.assertEqual(result["failClosedReasonCode"], "parameter_grid_empty")
        self.assertEqual(result["summary"]["completedCount"], 0)
        self.assertEqual(result["summary"]["skippedCount"], 0)
        self.assertEqual(result["datasetLineageReadiness"]["readinessState"], "blocked")
        self.assertEqual(result["datasetLineageReadiness"]["barBoundary"]["barSource"], "not_loaded_fail_closed")

    def test_parameter_sweep_rejects_parameter_paths_not_owned_by_strategy(self) -> None:
        service = RuleBacktestService(self.db)

        result = service.run_parameter_sweep_pilot(
            **_sweep_kwargs(parameter_grid={"strategy_spec.risk.nonexistent_control": [1]})
        )

        self.assertEqual(result["state"], "rejected")
        self.assertEqual(result["failClosedReasonCode"], "parameter_path_application_failed")
        self.assertEqual(result["summary"]["completedCount"], 0)
        self.assertEqual(result["datasetLineageReadiness"]["readinessState"], "blocked")
        self.assertEqual(result["datasetLineageReadiness"]["barBoundary"]["barSource"], "local_stock_daily_rows")
        self.assertFalse(result["datasetLineageReadiness"]["barBoundary"]["acceptedAsProviderAuthority"])

    def test_parameter_sweep_rejects_unsafe_parameter_path(self) -> None:
        service = RuleBacktestService(self.db)

        result = service.run_parameter_sweep_pilot(**_sweep_kwargs(parameter_grid={"code": ["AAPL"]}))

        self.assertEqual(result["state"], "rejected")
        self.assertEqual(result["failClosedReasonCode"], "unsafe_parameter_path")
        self.assertEqual(result["summary"]["completedCount"], 0)
        self.assertEqual(result["datasetLineageReadiness"]["readinessState"], "blocked")
        self.assertEqual(result["datasetLineageReadiness"]["barBoundary"]["barSource"], "local_stock_daily_rows")
        self.assertFalse(result["datasetLineageReadiness"]["barBoundary"]["acceptedAsProviderAuthority"])

    def test_parameter_sweep_missing_local_bars_skips_requested_sets(self) -> None:
        service = RuleBacktestService(self.db)

        result = service.run_parameter_sweep_pilot(**_sweep_kwargs(code="000000"))

        self.assertEqual(result["state"], "rejected")
        self.assertEqual(result["failClosedReasonCode"], "blocked_missing_local_data")
        self.assertEqual(result["summary"]["skippedCount"], 2)
        self.assertEqual(len(result["skippedRows"]), 2)
        self.assertTrue(all(row["reasonCode"] == "blocked_missing_local_data" for row in result["skippedRows"]))
        lineage = result["datasetLineageReadiness"]
        self.assertEqual(lineage["readinessState"], "blocked")
        self.assertEqual(lineage["barBoundary"]["barSource"], "unavailable_local_bars")
        self.assertFalse(lineage["barBoundary"]["localBars"])
        self.assertFalse(lineage["barBoundary"]["acceptedAsProviderAuthority"])
        self.assertFalse(lineage["barBoundary"]["providerCallsExecuted"])

    def test_parameter_sweep_response_has_no_public_decision_copy(self) -> None:
        service = RuleBacktestService(self.db)
        result = service.run_parameter_sweep_pilot(**_sweep_kwargs())

        serialized = json.dumps(result, ensure_ascii=False).lower()
        for term in FORBIDDEN_PUBLIC_TERMS:
            self.assertNotIn(term.lower(), serialized)

    def test_parameter_sweep_does_not_use_market_hydration_or_storage(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_ensure_market_history", side_effect=AssertionError("external history loader must stay unused")):
            with patch.object(service.repo, "save_run", side_effect=AssertionError("sweep pilot must not create stored runs")):
                result = service.run_parameter_sweep_pilot(**_sweep_kwargs())

        self.assertEqual(result["state"], "completed")
        self.assertFalse(result["storage"]["storedReadbackAvailable"])


class RuleBacktestParameterSweepPilotRunnerTest(unittest.TestCase):
    def test_runner_passes_supplied_parameters_into_existing_engine_path(self) -> None:
        fixture = _fixture_input()
        plan = build_parameter_stability_plan(
            strategy_id="ma-fixture",
            dataset_id="fixture-bars",
            base_parameters={},
            parameter_grid={
                "strategy_spec.signal.fast_period": [2, 3],
                "strategy_spec.signal.slow_period": [5],
            },
            metric_keys=["total_return_pct", "max_drawdown_pct", "trade_count"],
            max_combinations=10,
            overflow_policy="reject",
            min_completed_runs=1,
        )
        bars = [
            SimpleNamespace(
                code="600519",
                date=date.fromisoformat(bar["date"]),
                open=float(bar["open"]),
                high=float(bar["high"]),
                low=float(bar["low"]),
                close=float(bar["close"]),
                volume=float(bar["volume"]),
            )
            for bar in fixture["bars"]
        ]

        class CapturingEngine:
            def __init__(self) -> None:
                self.fast_periods: list[int] = []

            def run(self, **kwargs: Any) -> dict[str, Any]:
                parsed_strategy = kwargs["parsed_strategy"]
                self.fast_periods.append(int(parsed_strategy.strategy_spec["signal"]["fast_period"]))
                return {
                    "metrics": {
                        "total_return_pct": 1.2,
                        "max_drawdown_pct": 0.5,
                        "trade_count": 1,
                    },
                    "warnings": [],
                }

        engine = CapturingEngine()
        result = run_bounded_parameter_grid_diagnostic(
            parameter_stability_plan=plan,
            parsed_strategy=RuleBacktestService()._dict_to_parsed_strategy(fixture["parsed_strategy"], "fixture"),
            bars=bars,
            code="600519",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 10),
            lookback_bars=10,
            initial_capital=100000.0,
            fee_bps=0.0,
            slippage_bps=0.0,
            engine=engine,
        )

        self.assertEqual(result["state"], "completed")
        self.assertEqual(engine.fast_periods, [2, 3])
        self.assertEqual(result["summary"]["completedCount"], 2)

    def test_runner_records_blocked_parameter_set_and_continues(self) -> None:
        fixture = _fixture_input()
        plan = build_parameter_stability_plan(
            strategy_id="ma-fixture",
            dataset_id="fixture-bars",
            base_parameters={},
            parameter_grid={
                "strategy_spec.signal.fast_period": [2, 3],
                "strategy_spec.signal.slow_period": [5],
            },
            metric_keys=["total_return_pct", "max_drawdown_pct", "trade_count"],
            max_combinations=10,
            overflow_policy="reject",
            min_completed_runs=1,
        )
        bars = [
            SimpleNamespace(
                code="600519",
                date=date.fromisoformat(bar["date"]),
                open=float(bar["open"]),
                high=float(bar["high"]),
                low=float(bar["low"]),
                close=float(bar["close"]),
                volume=float(bar["volume"]),
            )
            for bar in fixture["bars"]
        ]

        class BlockingEngine:
            calls = 0

            def run(self, **_: Any) -> dict[str, Any]:
                self.calls += 1
                if self.calls == 1:
                    return {
                        "metrics": {},
                        "no_result_reason": "insufficient_history",
                        "no_result_message": "Insufficient supplied bars for this parameter set.",
                        "warnings": [],
                    }
                return {
                    "metrics": {
                        "total_return_pct": 1.2,
                        "max_drawdown_pct": 0.5,
                        "trade_count": 1,
                    },
                    "warnings": [],
                }

        result = run_bounded_parameter_grid_diagnostic(
            parameter_stability_plan=plan,
            parsed_strategy=RuleBacktestService()._dict_to_parsed_strategy(fixture["parsed_strategy"], "fixture"),
            bars=bars,
            code="600519",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 10),
            lookback_bars=10,
            initial_capital=100000.0,
            fee_bps=0.0,
            slippage_bps=0.0,
            engine=BlockingEngine(),
        )

        states = [row["state"] for row in result["requestResults"]]
        self.assertEqual(states, ["blocked", "completed"])
        self.assertEqual(result["summary"]["blockedCount"], 1)
        self.assertEqual(result["summary"]["completedCount"], 1)
        self.assertEqual(result["blockedRows"][0]["reasonCode"], "insufficient_history")
