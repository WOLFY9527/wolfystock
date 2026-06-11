# -*- coding: utf-8 -*-
"""Backtest ownership isolation regression coverage."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
import json
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import select

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.app import create_app
from src.config import Config
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID
from src.storage import (
    AnalysisHistory,
    BacktestResult,
    BacktestRun,
    DatabaseManager,
    RuleBacktestRun,
    RuleBacktestTrade,
    RuleBacktestUniverseJob,
    RuleBacktestUniverseSymbolResult,
)


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


def _dummy_analysis_result(code: str, *, name: str) -> SimpleNamespace:
    return SimpleNamespace(
        code=code,
        name=name,
        sentiment_score=61,
        operation_advice="买入",
        trend_prediction="看多",
        analysis_summary=f"{name} analysis",
        raw_result={"summary": f"{name} raw"},
        ideal_buy=None,
        secondary_buy=None,
        stop_loss=9.5,
        take_profit=11.0,
    )


class BacktestAccessIsolationTestCase(unittest.TestCase):
    @staticmethod
    def _error_code(response) -> str | None:
        payload = response.json()
        detail = payload.get("detail") if isinstance(payload, dict) else None
        if isinstance(detail, dict):
            return detail.get("error")
        if isinstance(payload, dict):
            return payload.get("error")
        return None

    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "backtest_access_isolation.db"
        self.env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=600519",
                    "GEMINI_API_KEY=test",
                    "ADMIN_AUTH_ENABLED=true",
                    f"DATABASE_PATH={self.db_path}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.db_path)
        Config.reset_instance()
        DatabaseManager.reset_instance()

        self.app = create_app(static_dir=self.data_dir / "empty-static")
        self.admin_client = TestClient(self.app)
        self.user_client = TestClient(self.app)
        self.other_user_client = TestClient(self.app)
        self.db = DatabaseManager.get_instance()

        self._login_admin()
        self.user_id = self._login_user(self.user_client, "alice", "Alice")
        self.other_user_id = self._login_user(self.other_user_client, "bob", "Bob")

    def tearDown(self) -> None:
        self.admin_client.close()
        self.user_client.close()
        self.other_user_client.close()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def _login_admin(self) -> None:
        response = self.admin_client.post(
            "/api/v1/auth/login",
            json={
                "password": "admin-pass-123",
                "passwordConfirm": "admin-pass-123",
            },
        )
        self.assertEqual(response.status_code, 200)

    def _login_user(self, client: TestClient, username: str, display_name: str) -> str:
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": username,
                "displayName": display_name,
                "createUser": True,
                "password": "secret123",
                "passwordConfirm": "secret123",
            },
        )
        self.assertEqual(response.status_code, 200)
        user_row = self.db.get_app_user_by_username(username)
        self.assertIsNotNone(user_row)
        return str(user_row.id)

    @staticmethod
    def _json_dumps(payload: dict) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _parsed_strategy(code: str) -> dict:
        return {
            "version": "v1",
            "timeframe": "daily",
            "source_text": "Buy when Close > MA3. Sell when Close < MA3.",
            "normalized_text": "Buy when Close > MA3. Sell when Close < MA3.",
            "entry": {"type": "group", "op": "and", "rules": []},
            "exit": {"type": "group", "op": "or", "rules": []},
            "confidence": 0.9,
            "needs_confirmation": False,
            "ambiguities": [],
            "summary": {
                "entry": "Close > MA3",
                "exit": "Close < MA3",
                "strategy": "moving average crossover fixture",
            },
            "max_lookback": 3,
            "strategy_kind": "moving_average_crossover",
            "strategy_spec": {
                "version": "v1",
                "strategy_type": "moving_average_crossover",
                "strategy_family": "moving_average_crossover",
                "symbol": code,
                "timeframe": "daily",
                "max_lookback": 3,
                "date_range": {"start_date": "2026-01-01", "end_date": "2026-01-31"},
                "capital": {"initial_capital": 100000.0, "currency": "CNY"},
                "costs": {"fee_bps": 0.0, "slippage_bps": 0.0},
                "signal": {
                    "indicator_family": "moving_average",
                    "fast_period": 3,
                    "slow_period": 5,
                    "fast_type": "sma",
                    "slow_type": "sma",
                    "entry_condition": "fast_crosses_above_slow",
                    "exit_condition": "fast_crosses_below_slow",
                },
                "execution": {
                    "frequency": "daily",
                    "signal_timing": "close",
                    "fill_timing": "same_bar_close",
                },
                "position_behavior": {
                    "direction": "long_only",
                    "entry_sizing": "all_in",
                    "max_positions": 1,
                    "pyramiding": False,
                },
                "end_behavior": {"policy": "force_close", "price_basis": "close"},
            },
            "executable": True,
            "normalization_state": "normalized",
        }

    def _rule_summary(self, code: str, *, total_return_pct: float) -> dict:
        return {
            "request": {
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "initial_capital": 100000.0,
                "fee_bps": 0.0,
                "slippage_bps": 0.0,
                "benchmark_mode": "none",
                "benchmark_code": None,
            },
            "status_message": "completed from owner-isolation fixture",
            "status_history": [
                {
                    "status": "completed",
                    "message": "completed from owner-isolation fixture",
                    "at": "2026-04-14T10:00:00",
                }
            ],
            "metrics": {
                "trade_count": 1,
                "win_count": 1,
                "loss_count": 0,
                "total_return_pct": total_return_pct,
                "annualized_return_pct": total_return_pct,
                "sharpe_ratio": 1.0,
                "win_rate_pct": 100.0,
                "avg_trade_return_pct": total_return_pct,
                "max_drawdown_pct": -1.0,
                "avg_holding_days": 3.0,
                "avg_holding_bars": 3.0,
                "avg_holding_calendar_days": 3.0,
                "final_equity": 100000.0 + total_return_pct * 1000.0,
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
            },
            "execution_trace": {
                "version": "v1",
                "source": "summary.execution_trace",
                "completeness": "complete",
                "missing_fields": [],
                "rows": [
                    {
                        "date": "2026-01-02",
                        "symbol_close": 100.0,
                        "benchmark_close": None,
                        "signal_summary": "fixture entry",
                        "event_type": "buy",
                        "action": "buy",
                        "action_display": "买入",
                        "fill_price": 100.0,
                        "shares": 100,
                        "cash": 90000.0,
                        "holdings_value": 10000.0,
                        "total_portfolio_value": 100000.0,
                        "daily_pnl": 0.0,
                        "daily_return": 0.0,
                        "cumulative_return": 0.0,
                        "benchmark_cumulative_return": None,
                        "buy_hold_cumulative_return": 0.0,
                        "position": 1.0,
                        "fees": 0.0,
                        "slippage": 0.0,
                        "notes": "fixture row",
                    }
                ],
                "execution_model": {},
                "execution_assumptions": {},
                "assumptions_defaults": {"items": [], "summary_text": "fixture assumptions"},
                "fallback": {"run_fallback": False, "trace_rebuilt": False, "note": "fixture"},
            },
            "robustness_analysis": {
                "state": "diagnostic_fixture",
                "profile": "owner_isolation_fixture",
                "source": "stored_fixture",
                "seed": 1450,
                "configuration": {},
            },
        }

    def _seed_backtest_fixture(self) -> tuple[int, int]:
        self.db.save_analysis_history(
            _dummy_analysis_result("600519", name="贵州茅台"),
            query_id="legacy-bootstrap-run",
            report_type="simple",
            news_content=None,
            owner_id=BOOTSTRAP_ADMIN_USER_ID,
        )
        self.db.save_analysis_history(
            _dummy_analysis_result("AAPL", name="Apple"),
            query_id="user-run",
            report_type="simple",
            news_content=None,
            owner_id=self.user_id,
        )

        legacy_history = self.db.get_analysis_history(
            query_id="legacy-bootstrap-run",
            owner_id=BOOTSTRAP_ADMIN_USER_ID,
            limit=1,
        )[0]
        user_history = self.db.get_analysis_history(
            query_id="user-run",
            owner_id=self.user_id,
            limit=1,
        )[0]

        legacy_completed_at = datetime(2026, 4, 14, 9, 0, 0)
        user_completed_at = datetime(2026, 4, 14, 10, 0, 0)

        with self.db.get_session() as session:
            legacy_run = BacktestRun(
                owner_id=BOOTSTRAP_ADMIN_USER_ID,
                code="600519",
                eval_window_days=10,
                min_age_days=14,
                force=False,
                completed_at=legacy_completed_at,
                status="completed",
                summary_json='{"scope":"legacy"}',
            )
            user_run = BacktestRun(
                owner_id=self.user_id,
                code="AAPL",
                eval_window_days=10,
                min_age_days=14,
                force=False,
                completed_at=user_completed_at,
                status="completed",
                summary_json='{"scope":"user"}',
            )
            session.add_all([legacy_run, user_run])
            session.flush()
            session.add_all(
                [
                    BacktestResult(
                        owner_id=BOOTSTRAP_ADMIN_USER_ID,
                        analysis_history_id=legacy_history.id,
                        code="600519",
                        eval_window_days=10,
                        engine_version="v1",
                        eval_status="completed",
                        evaluated_at=legacy_completed_at,
                        operation_advice="买入",
                    ),
                    BacktestResult(
                        owner_id=self.user_id,
                        analysis_history_id=user_history.id,
                        code="AAPL",
                        eval_window_days=10,
                        engine_version="v1",
                        eval_status="completed",
                        evaluated_at=user_completed_at,
                        operation_advice="买入",
                    ),
                ]
            )
            session.commit()
            return int(legacy_run.id), int(user_run.id)

    def _seed_backtest_owner_pair_fixture(self) -> tuple[int, int]:
        completed_at = datetime(2026, 4, 14, 11, 0, 0)
        self.db.save_analysis_history(
            _dummy_analysis_result("AAPL", name="Apple"),
            query_id="owner-a-clear-sample",
            report_type="simple",
            news_content=None,
            owner_id=self.user_id,
        )
        self.db.save_analysis_history(
            _dummy_analysis_result("AAPL", name="Apple B"),
            query_id="owner-b-clear-sample",
            report_type="simple",
            news_content=None,
            owner_id=self.other_user_id,
        )
        owner_a_history = self.db.get_analysis_history(
            query_id="owner-a-clear-sample",
            owner_id=self.user_id,
            limit=1,
        )[0]
        owner_b_history = self.db.get_analysis_history(
            query_id="owner-b-clear-sample",
            owner_id=self.other_user_id,
            limit=1,
        )[0]
        with self.db.get_session() as session:
            owner_a_run = BacktestRun(
                owner_id=self.user_id,
                code="AAPL",
                eval_window_days=10,
                min_age_days=14,
                force=False,
                completed_at=completed_at,
                status="completed",
                result_count=1,
                summary_json='{"scope":"owner-a"}',
            )
            owner_b_run = BacktestRun(
                owner_id=self.other_user_id,
                code="AAPL",
                eval_window_days=10,
                min_age_days=14,
                force=False,
                completed_at=completed_at,
                status="completed",
                result_count=1,
                summary_json='{"scope":"owner-b"}',
            )
            session.add_all([owner_a_run, owner_b_run])
            session.flush()
            session.add_all(
                [
                    BacktestResult(
                        owner_id=self.user_id,
                        analysis_history_id=owner_a_history.id,
                        code="AAPL",
                        eval_window_days=10,
                        engine_version="v1",
                        eval_status="completed",
                        evaluated_at=completed_at,
                        operation_advice="买入",
                    ),
                    BacktestResult(
                        owner_id=self.other_user_id,
                        analysis_history_id=owner_b_history.id,
                        code="AAPL",
                        eval_window_days=10,
                        engine_version="v1",
                        eval_status="completed",
                        evaluated_at=completed_at,
                        operation_advice="买入",
                    ),
                ]
            )
            session.commit()
            return int(owner_a_run.id), int(owner_b_run.id)

    def _seed_rule_backtest_run(
        self,
        *,
        owner_id: str,
        code: str,
        status: str = "completed",
        total_return_pct: float = 5.0,
    ) -> int:
        run_at = datetime(2026, 4, 14, 12, 0, 0)
        parsed_strategy = self._parsed_strategy(code)
        with self.db.get_session() as session:
            run = RuleBacktestRun(
                owner_id=owner_id,
                code=code,
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                parsed_strategy_json=self._json_dumps(parsed_strategy),
                strategy_hash=f"fixture-{owner_id}-{code}-{total_return_pct}",
                timeframe="daily",
                lookback_bars=252,
                initial_capital=100000.0,
                fee_bps=0.0,
                parsed_confidence=0.9,
                needs_confirmation=False,
                warnings_json="[]",
                run_at=run_at,
                completed_at=(run_at if status in {"completed", "failed", "cancelled"} else None),
                status=status,
                trade_count=1 if status == "completed" else 0,
                win_count=1 if status == "completed" else 0,
                loss_count=0,
                total_return_pct=total_return_pct if status == "completed" else None,
                win_rate_pct=100.0 if status == "completed" else None,
                avg_trade_return_pct=total_return_pct if status == "completed" else None,
                max_drawdown_pct=-1.0 if status == "completed" else None,
                avg_holding_days=3.0 if status == "completed" else None,
                final_equity=100000.0 + total_return_pct * 1000.0 if status == "completed" else None,
                summary_json=self._json_dumps(self._rule_summary(code, total_return_pct=total_return_pct)),
                ai_summary="fixture summary",
                equity_curve_json="[]",
            )
            session.add(run)
            session.flush()
            if status == "completed":
                session.add(
                    RuleBacktestTrade(
                        run_id=run.id,
                        trade_index=0,
                        code=code,
                        entry_date=date(2026, 1, 2),
                        exit_date=date(2026, 1, 5),
                        entry_price=100.0,
                        exit_price=105.0,
                        entry_signal="fixture entry",
                        exit_signal="fixture exit",
                        return_pct=total_return_pct,
                        holding_days=3,
                    )
                )
            session.commit()
            return int(run.id)

    def _seed_universe_job(self, *, owner_id: str, label: str, symbol: str) -> int:
        created_at = datetime(2026, 4, 14, 13, 0, 0)
        strategy_snapshot = {
            "strategy_text": "Buy when Close > MA3. Sell when Close < MA3.",
            "parsed_strategy": self._parsed_strategy(symbol),
            "request": {
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "lookback_bars": 252,
                "initial_capital": 100000.0,
                "fee_bps": 0.0,
                "slippage_bps": 0.0,
                "benchmark_mode": "none",
                "benchmark_code": None,
                "local_data_only": True,
                "execution_mode": "preflight_only",
            },
        }
        with self.db.get_session() as session:
            job = RuleBacktestUniverseJob(
                owner_id=owner_id,
                request_label=label,
                strategy_text=strategy_snapshot["strategy_text"],
                strategy_snapshot_json=self._json_dumps(strategy_snapshot),
                strategy_hash=f"fixture-{owner_id}-{label}",
                status="completed_with_failures",
                symbol_count=1,
                completed_count=0,
                skipped_count=1,
                failed_count=0,
                pending_count=0,
                running_count=0,
                cancel_requested=False,
                local_data_only=True,
                execution_mode="preflight_only",
                created_at=created_at,
                started_at=created_at,
                completed_at=created_at,
                updated_at=created_at,
            )
            session.add(job)
            session.flush()
            session.add(
                RuleBacktestUniverseSymbolResult(
                    job_id=job.id,
                    owner_id=owner_id,
                    sequence_index=0,
                    symbol=symbol,
                    status="skipped",
                    reason_code="blocked_missing_local_data",
                    reason_message="Fixture has no local daily bars.",
                    runtime_ms=0,
                    metrics_json=self._json_dumps(
                        {
                            "local_data_preflight": {
                                "symbol": symbol,
                                "state": "missing",
                                "reason_code": "blocked_missing_local_data",
                            }
                        }
                    ),
                    single_run_id=None,
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
            session.commit()
            return int(job.id)

    def _count_owner_rows(self, model, *, owner_id: str, code: str | None = None) -> int:
        with self.db.get_session() as session:
            query = select(model).where(model.owner_id == owner_id)
            if code is not None:
                query = query.where(model.code == code)
            return len(session.execute(query).scalars().all())

    def _rule_run_status(self, run_id: int) -> str:
        with self.db.get_session() as session:
            row = session.execute(
                select(RuleBacktestRun).where(RuleBacktestRun.id == run_id).limit(1)
            ).scalar_one()
            return str(row.status)

    def _assert_not_found(self, response, *, hidden_code: str | None = None) -> None:
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(self._error_code(response), "not_found")
        if hidden_code is not None:
            self.assertNotIn(hidden_code, response.text)

    def test_normal_user_only_sees_owned_backtest_history_and_results(self) -> None:
        legacy_run_id, user_run_id = self._seed_backtest_fixture()

        history_response = self.user_client.get("/api/v1/backtest/runs")
        self.assertEqual(history_response.status_code, 200)
        payload = history_response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual([item["code"] for item in payload["items"]], ["AAPL"])

        recent_results_response = self.user_client.get("/api/v1/backtest/results")
        self.assertEqual(recent_results_response.status_code, 200)
        result_payload = recent_results_response.json()
        self.assertEqual(result_payload["total"], 1)
        self.assertEqual([item["code"] for item in result_payload["items"]], ["AAPL"])

        own_run_response = self.user_client.get(f"/api/v1/backtest/results?run_id={user_run_id}")
        self.assertEqual(own_run_response.status_code, 200)
        own_run_payload = own_run_response.json()
        self.assertEqual(own_run_payload["total"], 1)
        self.assertEqual(own_run_payload["items"][0]["code"], "AAPL")

        leaked_run_response = self.user_client.get(f"/api/v1/backtest/results?run_id={legacy_run_id}")
        self.assertEqual(leaked_run_response.status_code, 404)
        self.assertEqual(self._error_code(leaked_run_response), "not_found")

        admin_history_response = self.admin_client.get("/api/v1/backtest/runs")
        self.assertEqual(admin_history_response.status_code, 200)
        admin_history_payload = admin_history_response.json()
        self.assertEqual(admin_history_payload["total"], 1)
        self.assertEqual(admin_history_payload["items"][0]["code"], "600519")

        admin_results_response = self.admin_client.get(f"/api/v1/backtest/results?run_id={legacy_run_id}")
        self.assertEqual(admin_results_response.status_code, 200)
        admin_results_payload = admin_results_response.json()
        self.assertEqual(admin_results_payload["total"], 1)
        self.assertEqual(admin_results_payload["items"][0]["code"], "600519")

    def test_owner_clear_results_does_not_mutate_other_owner_backtest_rows(self) -> None:
        self._seed_backtest_owner_pair_fixture()

        response = self.user_client.post("/api/v1/backtest/results/clear", json={"code": "AAPL"})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["deleted_runs"], 1)
        self.assertEqual(payload["deleted_results"], 1)

        self.assertEqual(self._count_owner_rows(BacktestRun, owner_id=self.user_id, code="AAPL"), 0)
        self.assertEqual(self._count_owner_rows(BacktestResult, owner_id=self.user_id, code="AAPL"), 0)
        self.assertEqual(self._count_owner_rows(BacktestRun, owner_id=self.other_user_id, code="AAPL"), 1)
        self.assertEqual(self._count_owner_rows(BacktestResult, owner_id=self.other_user_id, code="AAPL"), 1)

    def test_rule_backtest_run_readback_routes_deny_cross_owner_without_disclosure(self) -> None:
        own_run_id = self._seed_rule_backtest_run(
            owner_id=self.user_id,
            code="AAPL",
            total_return_pct=5.0,
        )
        other_run_id = self._seed_rule_backtest_run(
            owner_id=self.other_user_id,
            code="MSFT",
            total_return_pct=6.0,
        )

        self.assertEqual(
            self.user_client.get(f"/api/v1/backtest/rule/runs/{own_run_id}").status_code,
            200,
        )
        self.assertEqual(
            self.user_client.get(f"/api/v1/backtest/rule/runs/{own_run_id}/status").status_code,
            200,
        )

        denied_paths = [
            f"/api/v1/backtest/rule/runs/{other_run_id}",
            f"/api/v1/backtest/rule/runs/{other_run_id}/status",
            f"/api/v1/backtest/rule/runs/{other_run_id}/support-bundle-manifest",
            f"/api/v1/backtest/rule/runs/{other_run_id}/export-index",
            f"/api/v1/backtest/rule/runs/{other_run_id}/support-bundle-reproducibility-manifest",
            f"/api/v1/backtest/rule/runs/{other_run_id}/execution-trace.json",
            f"/api/v1/backtest/rule/runs/{other_run_id}/execution-trace.csv",
            f"/api/v1/backtest/rule/runs/{other_run_id}/robustness-evidence.json",
            f"/api/v1/backtest/rule/runs/{other_run_id}/regime-attribution-readiness.json",
            f"/api/v1/backtest/rule/runs/{other_run_id}/execution-model-metadata.json",
            f"/api/v1/backtest/rule/runs/{other_run_id}/oos-parameter-readiness.json",
        ]
        for path in denied_paths:
            with self.subTest(path=path):
                self._assert_not_found(self.user_client.get(path), hidden_code="MSFT")

    def test_rule_backtest_compare_treats_cross_owner_runs_as_missing(self) -> None:
        own_run_id = self._seed_rule_backtest_run(
            owner_id=self.user_id,
            code="AAPL",
            total_return_pct=5.0,
        )
        other_run_id = self._seed_rule_backtest_run(
            owner_id=self.other_user_id,
            code="MSFT",
            total_return_pct=6.0,
        )
        second_own_run_id = self._seed_rule_backtest_run(
            owner_id=self.user_id,
            code="AAPL",
            total_return_pct=7.0,
        )

        response = self.user_client.post(
            "/api/v1/backtest/rule/compare",
            json={"run_ids": [own_run_id, other_run_id, second_own_run_id]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["requested_run_ids"], [own_run_id, other_run_id, second_own_run_id])
        self.assertEqual(payload["resolved_run_ids"], [own_run_id, second_own_run_id])
        self.assertEqual(payload["comparable_run_ids"], [own_run_id, second_own_run_id])
        self.assertEqual(payload["missing_run_ids"], [other_run_id])
        self.assertEqual([item["metadata"]["code"] for item in payload["items"]], ["AAPL", "AAPL"])
        self.assertNotIn("MSFT", response.text)

    def test_rule_backtest_cancel_cross_owner_does_not_mutate_target_run(self) -> None:
        other_run_id = self._seed_rule_backtest_run(
            owner_id=self.other_user_id,
            code="MSFT",
            status="queued",
            total_return_pct=0.0,
        )
        self.assertEqual(self._rule_run_status(other_run_id), "queued")

        response = self.user_client.post(f"/api/v1/backtest/rule/runs/{other_run_id}/cancel")

        self._assert_not_found(response, hidden_code="MSFT")
        self.assertEqual(self._rule_run_status(other_run_id), "queued")

    def test_rule_backtest_universe_job_readback_routes_deny_cross_owner(self) -> None:
        own_job_id = self._seed_universe_job(owner_id=self.user_id, label="owner-a", symbol="AAPL")
        other_job_id = self._seed_universe_job(owner_id=self.other_user_id, label="owner-b", symbol="MSFT")

        own_status = self.user_client.get(f"/api/v1/backtest/rule/universe-jobs/{own_job_id}/status")
        self.assertEqual(own_status.status_code, 200, own_status.text)
        self.assertEqual(own_status.json()["id"], own_job_id)

        own_results = self.user_client.get(f"/api/v1/backtest/rule/universe-jobs/{own_job_id}/results")
        self.assertEqual(own_results.status_code, 200, own_results.text)
        self.assertEqual(own_results.json()["items"][0]["symbol"], "AAPL")

        denied_paths = [
            f"/api/v1/backtest/rule/universe-jobs/{other_job_id}/status",
            f"/api/v1/backtest/rule/universe-jobs/{other_job_id}/diagnostics",
            f"/api/v1/backtest/rule/universe-jobs/{other_job_id}/results",
        ]
        for path in denied_paths:
            with self.subTest(path=path):
                self._assert_not_found(self.user_client.get(path), hidden_code="MSFT")


if __name__ == "__main__":
    unittest.main()
