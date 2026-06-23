# -*- coding: utf-8 -*-
"""DATA-096 data sufficiency gate tests for rule backtest outputs."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

from src.config import Config
from src.services.backtest_data_sufficiency import assess_backtest_data_sufficiency
from src.services.rule_backtest_service import RuleBacktestService
from src.storage import DatabaseManager, StockDaily


FORBIDDEN_LEAK_KEYS = (
    "providerClass",
    "providerName",
    "apiKey",
    "env",
    "token",
    "credential",
    "requestId",
    "traceId",
    "cacheKey",
    "rawPayload",
    "exceptionClass",
    "exceptionChain",
)


class BacktestDataSufficiencyGateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_PATH"] = os.path.join(self._temp_dir.name, "data096.db")
        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()
        with self.db.get_session() as session:
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
                10.8,
                11.3,
                11.8,
                12.2,
            ]
            for index, close in enumerate(closes):
                session.add(
                    StockDaily(
                        code="600519",
                        date=date(2024, 1, 1) + timedelta(days=index),
                        open=close - 0.1,
                        high=close + 0.2,
                        low=max(0.01, close - 0.3),
                        close=close,
                        data_source="local_us_parquet",
                    )
                )
            session.commit()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self._temp_dir.cleanup()

    @staticmethod
    def _assert_no_forbidden_leakage(payload: dict) -> None:
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        for key in FORBIDDEN_LEAK_KEYS:
            assert key not in serialized, key
        assert "secret-token-value" not in serialized

    @staticmethod
    def _sufficient_quality() -> dict:
        return {
            "source": "local_us_parquet",
            "authority_status": "allowed",
            "authority_source_type": "cache_snapshot",
            "authority_reason_codes": [],
            "bar_count": 24,
            "expected_bar_count": 24,
            "missing_bar_count": 0,
            "anomaly_count": 0,
            "adjustment_mode": "split_dividend_adjusted",
            "adjusted_ohlc_available": True,
            "return_basis": "adjusted_total_return",
            "dividends_handled": "handled",
            "splits_handled": "handled",
            "freshness_status": "fresh",
            "warnings": [],
        }

    def test_sufficient_fixture_remains_executable(self) -> None:
        service = RuleBacktestService(self.db)
        original_builder = service._build_data_quality_payload

        def sufficient_builder(**kwargs):
            payload = original_builder(**kwargs)
            payload.update(self._sufficient_quality())
            return payload

        with patch.object(service, "_ensure_market_history", return_value=0), patch.object(
            service,
            "_get_llm_adapter",
            return_value=None,
        ), patch.object(service, "_build_data_quality_payload", side_effect=sufficient_builder):
            response = service.run_backtest(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                start_date="2024-01-05",
                end_date="2024-01-20",
                lookback_bars=20,
                benchmark_mode="same_symbol_buy_and_hold",
                confirmed=True,
            )

        self.assertEqual(response["status"], "completed")
        self.assertIsNone(response["no_result_reason"])
        self.assertEqual(response["data_sufficiency"]["status"], "sufficient")
        self.assertEqual(response["data_sufficiency"]["calculation_state"], "executable")
        self.assertIsNotNone(response["sharpe_ratio"])
        self.assertIsNotNone(response["max_drawdown_pct"])
        self.assertEqual(response["summary"]["data_sufficiency"], response["data_sufficiency"])

    def test_insufficient_history_is_not_available_and_does_not_fabricate_metrics(self) -> None:
        service = RuleBacktestService(self.db)
        with patch.object(service, "_ensure_market_history", return_value=0), patch.object(
            service,
            "_get_llm_adapter",
            return_value=None,
        ):
            response = service.run_backtest(
                code="NODATA",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                start_date="2024-01-01",
                end_date="2024-01-31",
                lookback_bars=20,
                confirmed=True,
            )

        gate = response["data_sufficiency"]
        self.assertEqual(gate["status"], "insufficient_history")
        self.assertEqual(gate["calculation_state"], "not_available")
        self.assertIn("insufficient_history", gate["blocked_reasons"])
        for metric in (
            "sharpe_ratio",
            "annualized_return_pct",
            "benchmark_return_pct",
            "excess_return_vs_benchmark_pct",
            "buy_and_hold_return_pct",
            "excess_return_vs_buy_and_hold_pct",
            "win_rate_pct",
            "avg_trade_return_pct",
            "max_drawdown_pct",
            "final_equity",
        ):
            self.assertIsNone(response[metric], metric)
        self.assertIn("数据不足，暂不形成结论", response["ai_summary"])

    def test_missing_benchmark_prevents_benchmark_relative_claims(self) -> None:
        service = RuleBacktestService(self.db)
        with patch.object(service, "_ensure_market_history", return_value=0), patch.object(
            service,
            "_get_llm_adapter",
            return_value=None,
        ), patch.object(
            service,
            "_load_external_benchmark_context",
            return_value=(
                [],
                {"label": "SPY", "resolved_mode": "custom_code", "code": "SPY", "return_pct": None},
                "SPY 在当前窗口没有可用行情。",
            ),
        ):
            response = service.run_backtest(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                benchmark_mode="custom_code",
                benchmark_code="SPY",
                confirmed=True,
            )

        gate = response["data_sufficiency"]
        self.assertEqual(gate["status"], "missing_benchmark")
        self.assertEqual(gate["calculation_state"], "degraded")
        self.assertIn("missing_benchmark", gate["degraded_reasons"])
        self.assertIsNone(response["benchmark_return_pct"])
        self.assertIsNone(response["excess_return_vs_benchmark_pct"])
        self.assertNotIn("相对基准超额", response["ai_summary"])

    def test_missing_corporate_action_adjustment_degrades_without_blocking(self) -> None:
        service = RuleBacktestService(self.db)
        with patch.object(service, "_ensure_market_history", return_value=0), patch.object(
            service,
            "_get_llm_adapter",
            return_value=None,
        ):
            response = service.run_backtest(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                start_date="2024-01-05",
                end_date="2024-01-20",
                lookback_bars=20,
                benchmark_mode="same_symbol_buy_and_hold",
                confirmed=True,
            )

        gate = response["data_sufficiency"]
        self.assertEqual(response["status"], "completed")
        self.assertEqual(gate["status"], "missing_adjustments")
        self.assertEqual(gate["calculation_state"], "degraded")
        self.assertIn("missing_adjustments", gate["degraded_reasons"])
        self.assertIsNotNone(response["total_return_pct"])

    def test_gate_can_classify_provider_entitlement_stale_and_factor_input_states(self) -> None:
        cases = [
            (
                "provider_missing",
                {"authority_status": "degraded_fill_only", "authority_source_type": "missing", "authority_reason_codes": ["source_authority_unknown"], "bar_count": 20},
                {},
                {"status": "provider_missing", "calculation_state": "degraded"},
            ),
            (
                "entitlement_required",
                {"authority_status": "rejected", "authority_reason_codes": ["entitlement_required"], "bar_count": 20},
                {},
                {"status": "entitlement_required", "calculation_state": "not_available"},
            ),
            (
                "stale_data",
                {"authority_status": "allowed", "bar_count": 20, "freshness_status": "stale", "adjustment_mode": "split_dividend_adjusted", "dividends_handled": "handled", "splits_handled": "handled"},
                {},
                {"status": "stale_data", "calculation_state": "degraded"},
            ),
            (
                "missing_factor_inputs",
                self._sufficient_quality(),
                {"state": "missing", "missing_reasons": ["factor_observations_missing"]},
                {"status": "missing_factor_inputs", "calculation_state": "degraded"},
            ),
        ]
        for label, data_quality, factor_inputs, expected in cases:
            with self.subTest(label=label):
                payload = assess_backtest_data_sufficiency(
                    {
                        "status": "completed",
                        "data_quality": data_quality,
                        "benchmark_summary": {"resolved_mode": "none"},
                        "factor_inputs": factor_inputs,
                    }
                )
                self.assertEqual(payload["status"], expected["status"])
                self.assertEqual(payload["calculation_state"], expected["calculation_state"])

    def test_sufficiency_payload_redacts_internal_provider_and_trace_fields(self) -> None:
        gate = assess_backtest_data_sufficiency(
            {
                "status": "completed",
                "providerClass": "LeakyProvider",
                "requestId": "rq-1",
                "traceId": "tr-1",
                "rawPayload": {"token": "secret-token-value"},
                "data_quality": {
                    "source": "local_us_parquet",
                    "authority_status": "allowed",
                    "authority_source_type": "cache_snapshot",
                    "authority_reason_codes": [],
                    "bar_count": 20,
                    "adjustment_mode": "unknown",
                    "warnings": [{"code": "adjustment_status_unknown", "providerName": "HiddenVendor"}],
                },
                "benchmark_summary": {"resolved_mode": "none", "cacheKey": "ck-1"},
                "factor_inputs": {"state": "ready", "apiKey": "secret-token-value"},
            }
        )

        self._assert_no_forbidden_leakage(gate)

    def test_focused_sufficiency_tests_do_not_call_external_history_fetch(self) -> None:
        service = RuleBacktestService(self.db)
        with patch.object(service, "_ensure_market_history", return_value=0), patch.object(
            service,
            "_get_llm_adapter",
            return_value=None,
        ), patch(
            "src.services.rule_backtest_service.fetch_daily_history_with_local_us_fallback",
            side_effect=AssertionError("external history fetch must not run in DATA-096 tests"),
        ):
            response = service.run_backtest(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                start_date="2024-01-05",
                end_date="2024-01-20",
                lookback_bars=20,
                benchmark_mode="same_symbol_buy_and_hold",
                confirmed=True,
            )

        self.assertIn(response["data_sufficiency"]["status"], {"sufficient", "missing_adjustments"})


if __name__ == "__main__":
    unittest.main()
