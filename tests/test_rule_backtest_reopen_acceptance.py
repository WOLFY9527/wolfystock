# -*- coding: utf-8 -*-
"""Integrated acceptance tests for stored-first rule-backtest reopen trustworthiness."""

import json
import os
import tempfile
import unittest
from datetime import date
from unittest.mock import patch

from src.config import Config
from src.services.rule_backtest_service import RuleBacktestService
from src.storage import DatabaseManager, StockDaily


class RuleBacktestReopenAcceptanceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_rule_backtest_acceptance.db")
        os.environ["DATABASE_PATH"] = self._db_path

        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()
        self._ensure_market_history_patcher = patch.object(
            RuleBacktestService,
            "_ensure_market_history",
            return_value=0,
        )
        self._ensure_market_history_patcher.start()
        self._ensure_market_history_patcher_active = True

        with self.db.get_session() as session:
            closes = [10, 10.2, 10.1, 10.5, 11.0, 11.6, 11.8, 11.2, 10.8, 10.2, 9.9, 10.3, 10.9, 11.4, 11.9, 12.1, 11.7, 11.1, 10.7, 10.4, 10.8, 11.3, 11.8, 12.2]
            for index, close in enumerate(closes):
                session.add(
                    StockDaily(
                        code="600519",
                        date=date(2024, 1, 1).fromordinal(date(2024, 1, 1).toordinal() + index),
                        open=close - 0.1,
                        high=close + 0.2,
                        low=close - 0.3,
                        close=float(close),
                    )
                )
            session.commit()

    def tearDown(self) -> None:
        if getattr(self, "_ensure_market_history_patcher_active", False):
            self._ensure_market_history_patcher.stop()
            self._ensure_market_history_patcher_active = False
        DatabaseManager.reset_instance()
        self._temp_dir.cleanup()

    def _run_completed_backtest(self) -> tuple[RuleBacktestService, dict, object]:
        service = RuleBacktestService(self.db)
        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )

        run_row = service.repo.get_run(response["id"])
        assert run_row is not None
        return service, response, run_row

    def test_reopen_acceptance_detail_history_contract_stays_aligned_across_domains(self) -> None:
        service, _, run_row = self._run_completed_backtest()

        detail = service.get_run(run_row.id)
        status = service.get_run_status(run_row.id)
        history = service.list_runs(code="600519", page=1, limit=10)
        assert detail is not None
        assert status is not None
        item = history["items"][0]

        for domain in [
            "summary",
            "parsed_strategy",
            "metrics",
            "execution_model",
            "execution_assumptions_snapshot",
            "comparison",
        ]:
            self.assertEqual(
                detail["result_authority"]["domains"][domain],
                item["result_authority"]["domains"][domain],
            )

        self.assertEqual(detail["summary"]["parsed_strategy_summary"], detail["parsed_strategy"]["summary"])
        self.assertEqual(detail["summary"]["metrics"]["trade_count"], detail["trade_count"])
        self.assertEqual(detail["summary"]["metrics"]["final_equity"], detail["final_equity"])
        self.assertEqual(detail["summary"]["execution_model"], detail["execution_model"])
        self.assertEqual(detail["summary"]["execution_assumptions_snapshot"], detail["execution_assumptions_snapshot"])
        self.assertEqual(detail["summary"]["execution_trace"], detail["execution_trace"])
        self.assertEqual(detail["summary"]["visualization"]["audit_rows"], detail["audit_rows"])
        self.assertEqual(
            detail["summary"]["visualization"]["daily_return_series"],
            detail["daily_return_series"],
        )
        self.assertEqual(detail["summary"]["visualization"]["exposure_curve"], detail["exposure_curve"])

        self.assertEqual(item["summary"]["parsed_strategy_summary"], item["parsed_strategy"]["summary"])
        self.assertEqual(item["summary"]["metrics"]["trade_count"], item["trade_count"])
        self.assertEqual(item["summary"]["metrics"]["final_equity"], item["final_equity"])
        self.assertEqual(item["summary"]["execution_model"], item["execution_model"])
        self.assertEqual(item["summary"]["execution_assumptions_snapshot"], item["execution_assumptions_snapshot"])
        self.assertEqual(item["summary"]["execution_trace"], {})
        self.assertEqual(item["summary"]["visualization"]["audit_rows"], [])
        self.assertEqual(item["summary"]["visualization"]["daily_return_series"], [])
        self.assertEqual(item["summary"]["visualization"]["exposure_curve"], [])
        self.assertEqual(detail["run_timing"], status["run_timing"])
        self.assertEqual(item["run_timing"], status["run_timing"])
        self.assertEqual(detail["run_diagnostics"], status["run_diagnostics"])
        self.assertEqual(item["run_diagnostics"], status["run_diagnostics"])

        self.assertEqual(detail["artifact_availability"], item["artifact_availability"])
        self.assertEqual(status["artifact_availability"], item["artifact_availability"])
        self.assertEqual(detail["summary"]["artifact_availability"], detail["artifact_availability"])
        self.assertEqual(item["summary"]["artifact_availability"], item["artifact_availability"])
        self.assertTrue(detail["artifact_availability"]["has_trade_rows"])
        self.assertTrue(item["artifact_availability"]["has_trade_rows"])
        self.assertTrue(status["artifact_availability"]["has_trade_rows"])
        self.assertEqual(detail["readback_integrity"], item["readback_integrity"])
        self.assertEqual(detail["summary"]["readback_integrity"], detail["readback_integrity"])
        self.assertEqual(item["summary"]["readback_integrity"], item["readback_integrity"])
        self.assertEqual(detail["readback_integrity"]["integrity_level"], "stored_repaired")
        self.assertFalse(detail["readback_integrity"]["used_live_storage_repair"])
        self.assertEqual(status["readback_integrity"]["source"], "stored_status_summary")
        self.assertEqual(status["readback_integrity"]["integrity_level"], "stored_complete")
        self.assertFalse(status["readback_integrity"]["used_legacy_fallback"])
        self.assertFalse(status["readback_integrity"]["used_live_storage_repair"])
        self.assertFalse(status["readback_integrity"]["used_legacy_fallback"])
        self.assertFalse(status["readback_integrity"]["used_live_storage_repair"])

    def test_reopen_acceptance_repaired_detail_and_history_share_repaired_domains_without_summary_drift(self) -> None:
        service, response, run_row = self._run_completed_backtest()

        summary = json.loads(run_row.summary_json)
        comparison = dict((summary.get("visualization") or {}).get("comparison") or {})
        comparison.pop("buy_and_hold_summary", None)
        comparison.pop("buy_and_hold_curve", None)
        summary["request"] = {"lookback_bars": 20}
        summary["metrics"] = {"trade_count": response["trade_count"]}
        summary["execution_model"] = {"timeframe": "daily"}
        summary["execution_trace"] = {"source": "summary.execution_trace", "rows": []}
        summary["visualization"] = dict(summary.get("visualization") or {})
        summary["visualization"]["comparison"] = comparison
        service.repo.update_run(
            run_row.id,
            summary_json=service._serialize_json(summary),
            parsed_strategy_json=service._serialize_json(
                {
                    "version": "v1",
                    "timeframe": "daily",
                    "source_text": response["strategy_text"],
                    "normalized_text": response["strategy_text"],
                    "summary": response["parsed_strategy"]["summary"],
                    "strategy_kind": "moving_average_crossover",
                    "setup": {
                        "symbol": "600519",
                        "indicator_family": "moving_average",
                        "fast_period": 3,
                        "slow_period": 5,
                    },
                    "strategy_spec": {},
                }
            ),
        )

        detail = service.get_run(run_row.id)
        history = service.list_runs(code="600519", page=1, limit=10)
        assert detail is not None
        item = history["items"][0]

        for domain in [
            "summary",
            "parsed_strategy",
            "metrics",
            "execution_model",
            "comparison",
        ]:
            self.assertEqual(
                detail["result_authority"]["domains"][domain],
                item["result_authority"]["domains"][domain],
            )
            self.assertEqual(
                detail["result_authority"]["domains"][domain]["completeness"],
                "stored_partial_repaired",
            )

        self.assertEqual(detail["summary"]["execution_trace"], detail["execution_trace"])
        self.assertEqual(
            detail["summary"]["visualization"]["comparison"]["buy_and_hold_summary"],
            detail["buy_and_hold_summary"],
        )
        self.assertEqual(
            detail["summary"]["visualization"]["comparison"]["buy_and_hold_curve"],
            detail["buy_and_hold_curve"],
        )
        self.assertEqual(item["summary"]["execution_trace"], {})
        self.assertEqual(item["summary"]["visualization"]["audit_rows"], [])
        self.assertEqual(item["summary"]["visualization"]["daily_return_series"], [])
        self.assertEqual(item["summary"]["visualization"]["exposure_curve"], [])

    def test_reopen_acceptance_rebuilt_trace_stays_readback_only_without_engine_rerun(self) -> None:
        service, _, run_row = self._run_completed_backtest()

        summary = json.loads(run_row.summary_json)
        summary.pop("execution_trace", None)
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        with patch.object(
            service.engine,
            "run",
            side_effect=AssertionError("readback projections must not rerun stored strategy calculations"),
        ) as engine_run_mock:
            detail = service.get_run(run_row.id)
            status = service.get_run_status(run_row.id)
            history = service.list_runs(code="600519", page=1, limit=10)

        assert detail is not None
        assert status is not None
        item = history["items"][0]
        engine_run_mock.assert_not_called()

        self.assertEqual(detail["execution_trace"]["source"], "rebuilt_from_stored_audit_rows")
        self.assertTrue(detail["execution_trace"]["fallback"]["trace_rebuilt"])
        self.assertEqual(
            detail["result_authority"]["domains"]["execution_trace"],
            {
                "source": "rebuilt_from_stored_audit_rows",
                "completeness": "legacy_rebuilt",
                "state": "available",
                "missing": ["stored_trace"],
                "missing_kind": "fields",
            },
        )
        self.assertEqual(item["summary"]["execution_trace"], {})
        self.assertEqual(
            item["result_authority"]["domains"]["execution_trace"],
            {
                "source": "omitted_without_detail_read",
                "completeness": "omitted",
                "state": "omitted",
                "missing": [],
                "missing_kind": "fields",
            },
        )
        self.assertEqual(item["result_authority"]["execution_trace_source"], "omitted_without_detail_read")
        self.assertEqual(item["result_authority"]["execution_trace_completeness"], "omitted")
        self.assertEqual(item["result_authority"]["execution_trace_missing_fields"], [])
        self.assertEqual(
            status["readback_integrity"]["source"],
            "derived_from_status_summary+live_storage_repair",
        )
        self.assertEqual(status["readback_integrity"]["integrity_level"], "drift_repaired")
        self.assertTrue(status["readback_integrity"]["used_live_storage_repair"])
        self.assertTrue(status["readback_integrity"]["has_summary_storage_drift"])
        self.assertEqual(status["readback_integrity"]["drift_domains"], ["execution_trace"])

    def test_reopen_acceptance_legacy_fallback_surfaces_are_explicit_across_status_detail_history(self) -> None:
        service, _, run_row = self._run_completed_backtest()
        service.repo.update_run(run_row.id, summary_json="")

        detail = service.get_run(run_row.id)
        status = service.get_run_status(run_row.id)
        history = service.list_runs(code="600519", page=1, limit=10)
        assert detail is not None
        assert status is not None
        item = history["items"][0]

        for payload in [detail, item]:
            self.assertEqual(payload["artifact_availability"]["source"], "derived_from_live_storage")
            self.assertEqual(payload["artifact_availability"]["completeness"], "legacy_derived")
            self.assertFalse(payload["artifact_availability"]["has_summary"])
            self.assertEqual(payload["readback_integrity"]["source"], "derived_from_result_authority+legacy_fallback")
            self.assertEqual(payload["readback_integrity"]["completeness"], "legacy_derived")
            self.assertTrue(payload["readback_integrity"]["used_legacy_fallback"])
            self.assertFalse(payload["readback_integrity"]["used_live_storage_repair"])
            self.assertFalse(payload["readback_integrity"]["has_summary_storage_drift"])
            self.assertEqual(payload["readback_integrity"]["integrity_level"], "legacy_fallback")
            self.assertEqual(payload["summary"]["artifact_availability"], payload["artifact_availability"])
            self.assertEqual(payload["summary"]["readback_integrity"], payload["readback_integrity"])
            self.assertEqual(payload["summary"]["run_diagnostics"]["current_status"], "completed")
            self.assertEqual(payload["summary"]["run_timing"]["finished_at"], payload["completed_at"])

        self.assertEqual(detail["readback_integrity"], item["readback_integrity"])
        self.assertEqual(detail["artifact_availability"], item["artifact_availability"])
        self.assertEqual(status["artifact_availability"]["source"], "derived_from_live_storage")
        self.assertEqual(status["artifact_availability"]["completeness"], "legacy_derived")
        self.assertFalse(status["artifact_availability"]["has_summary"])
        self.assertEqual(status["readback_integrity"]["source"], "derived_from_status_row_columns")
        self.assertEqual(status["readback_integrity"]["completeness"], "legacy_derived")
        self.assertTrue(status["readback_integrity"]["used_legacy_fallback"])
        self.assertFalse(status["readback_integrity"]["used_live_storage_repair"])
        self.assertFalse(status["readback_integrity"]["has_summary_storage_drift"])
        self.assertEqual(status["readback_integrity"]["integrity_level"], "legacy_fallback")
        self.assertIn("stored_summary", status["readback_integrity"]["missing_summary_fields"])
        self.assertIn("run_timing", status["readback_integrity"]["missing_summary_fields"])
        self.assertIn("run_diagnostics", status["readback_integrity"]["missing_summary_fields"])
        self.assertEqual(status["run_timing"], {})
        self.assertEqual(status["run_diagnostics"], {})

    def test_reopen_acceptance_live_storage_repair_surfaces_trade_row_drift_across_status_detail_history(self) -> None:
        service, response, run_row = self._run_completed_backtest()
        deleted = service.repo.delete_trades_by_run_ids([run_row.id])
        self.assertGreater(deleted, 0)

        detail = service.get_run(run_row.id)
        status = service.get_run_status(run_row.id)
        history = service.list_runs(code="600519", page=1, limit=10)
        assert detail is not None
        assert status is not None
        item = history["items"][0]

        for payload in [detail, item]:
            self.assertEqual(payload["trade_count"], response["trade_count"])
            self.assertEqual(
                payload["artifact_availability"]["source"],
                "summary.artifact_availability+live_storage_repair",
            )
            self.assertEqual(payload["artifact_availability"]["completeness"], "stored_partial_repaired")
            self.assertFalse(payload["artifact_availability"]["has_trade_rows"])
            self.assertEqual(
                payload["readback_integrity"]["source"],
                "derived_from_result_authority+live_storage_repair",
            )
            self.assertEqual(payload["readback_integrity"]["completeness"], "stored_partial_repaired")
            self.assertFalse(payload["readback_integrity"]["used_legacy_fallback"])
            self.assertTrue(payload["readback_integrity"]["used_live_storage_repair"])
            self.assertTrue(payload["readback_integrity"]["has_summary_storage_drift"])
            self.assertEqual(payload["readback_integrity"]["drift_domains"], ["trade_rows"])
            self.assertEqual(payload["readback_integrity"]["integrity_level"], "drift_repaired")

        self.assertEqual(detail["artifact_availability"], item["artifact_availability"])
        self.assertEqual(detail["readback_integrity"], item["readback_integrity"])
        self.assertEqual(detail["run_timing"], status["run_timing"])
        self.assertEqual(item["run_timing"], status["run_timing"])
        self.assertEqual(detail["run_diagnostics"], status["run_diagnostics"])
        self.assertEqual(item["run_diagnostics"], status["run_diagnostics"])
        self.assertEqual(
            status["artifact_availability"]["source"],
            "summary.artifact_availability+live_storage_repair",
        )
        self.assertFalse(status["artifact_availability"]["has_trade_rows"])
        self.assertEqual(
            status["readback_integrity"]["source"],
            "derived_from_status_summary+live_storage_repair",
        )
        self.assertEqual(status["readback_integrity"]["completeness"], "stored_partial_repaired")
        self.assertFalse(status["readback_integrity"]["used_legacy_fallback"])
        self.assertTrue(status["readback_integrity"]["used_live_storage_repair"])
        self.assertTrue(status["readback_integrity"]["has_summary_storage_drift"])
        self.assertEqual(status["readback_integrity"]["drift_domains"], ["trade_rows"])
        self.assertEqual(status["readback_integrity"]["integrity_level"], "drift_repaired")
