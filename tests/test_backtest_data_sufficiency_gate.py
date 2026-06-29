# -*- coding: utf-8 -*-
"""DATA-096 data sufficiency gate tests for rule backtest outputs."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch

import pandas as pd

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

from src.config import Config
from src.services.backtest_data_sufficiency import assess_backtest_data_sufficiency
from src.services.rule_backtest_service import RuleBacktestService
from src.services.us_history_helper import persist_local_us_daily_history
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
        self._env_keys = [
            "WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED",
            "WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED",
            "WOLFYSTOCK_HISTORICAL_OHLCV_CACHE_SEED_ENABLED",
            "LOCAL_US_PARQUET_DIR",
            "US_STOCK_PARQUET_DIR",
        ]
        self._env_snapshot = {key: os.environ.get(key) for key in self._env_keys}
        for key in self._env_keys:
            os.environ.pop(key, None)
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
        for key in self._env_keys:
            if self._env_snapshot[key] is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = self._env_snapshot[key] or ""

    @staticmethod
    def _assert_no_forbidden_leakage(payload: dict) -> None:
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        for key in FORBIDDEN_LEAK_KEYS:
            assert key not in serialized, key
        assert "secret-token-value" not in serialized

    def _seed_daily_rows(self, code: str, closes: list[float], *, start: date = date(2024, 1, 2)) -> None:
        with self.db.get_session() as session:
            for index, close in enumerate(closes):
                session.add(
                    StockDaily(
                        code=code,
                        date=start + timedelta(days=index),
                        open=close - 0.1,
                        high=close + 0.2,
                        low=max(0.01, close - 0.3),
                        close=close,
                        volume=1000.0 + index,
                        data_source="local_us_parquet",
                    )
                )
            session.commit()

    @staticmethod
    def _cache_frame(closes: list[float], *, start: date = date(2024, 1, 2), adjusted: bool = True) -> pd.DataFrame:
        rows: list[dict] = []
        for index, close in enumerate(closes):
            row = {
                "date": start + timedelta(days=index),
                "open": close - 0.1,
                "high": close + 0.2,
                "low": max(0.01, close - 0.3),
                "close": close,
                "volume": 1000.0 + index,
            }
            if adjusted:
                row["adjusted_close"] = close - 0.25
            rows.append(row)
        return pd.DataFrame(rows)

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

    @staticmethod
    def _historical_readiness(
        *,
        provider_state: str = "available",
        overall_state: str = "ready",
        required_bars: int = 20,
        usable_bars: int = 20,
        missing_bars: int = 0,
        missing_requirements: list[str] | None = None,
        freshness_state: str = "current",
        adjustment_state: str = "available",
        benchmark_state: str = "not_requested",
    ) -> dict:
        return {
            "contractVersion": "historical_ohlcv_readiness_v1",
            "symbol": "600519",
            "timeframe": "1d",
            "requiredBars": required_bars,
            "usableBars": usable_bars,
            "missingBars": missing_bars,
            "providerState": provider_state,
            "overallState": overall_state,
            "freshnessState": freshness_state,
            "adjustmentState": adjustment_state,
            "benchmarkState": benchmark_state,
            "missingRequirements": missing_requirements or [],
            "consumerSafe": True,
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

    def test_missing_ohlcv_provider_is_not_available_and_does_not_fabricate_metrics(self) -> None:
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
        self.assertEqual(gate["status"], "provider_missing")
        self.assertEqual(gate["calculation_state"], "not_available")
        self.assertIn("provider_missing", gate["blocked_reasons"])
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

    def test_gate_consumes_historical_ohlcv_readiness_when_provider_is_missing(self) -> None:
        gate = assess_backtest_data_sufficiency(
            {
                "status": "completed",
                "data_quality": self._sufficient_quality(),
                "historicalOhlcvReadiness": self._historical_readiness(
                    provider_state="provider_missing",
                    overall_state="blocked",
                    required_bars=30,
                    usable_bars=0,
                    missing_bars=30,
                    missing_requirements=["provider_missing", "insufficient_history"],
                    freshness_state="unknown",
                    adjustment_state="not_required",
                ),
            }
        )

        self.assertEqual(gate["status"], "provider_missing")
        self.assertEqual(gate["calculation_state"], "not_available")
        self.assertIn("provider_missing", gate["blocked_reasons"])
        self.assertIn("insufficient_history", gate["blocked_reasons"])
        self.assertEqual(gate["input_states"]["history"], "missing")
        self.assertEqual(gate["input_states"]["provider"], "missing")
        self.assertEqual(gate["ohlcv_readiness"]["requiredBars"], 30)
        self.assertEqual(gate["ohlcv_readiness"]["usableBars"], 0)
        self.assertEqual(gate["ohlcv_readiness"]["missingBars"], 30)

    def test_gate_does_not_degrade_when_adjusted_ohlcv_is_not_required(self) -> None:
        gate = assess_backtest_data_sufficiency(
            {
                "status": "completed",
                "data_quality": {"bar_count": 20},
                "historicalOhlcvReadiness": self._historical_readiness(
                    adjustment_state="not_required",
                ),
            }
        )

        self.assertEqual(gate["status"], "sufficient")
        self.assertEqual(gate["calculation_state"], "executable")
        self.assertEqual(gate["degraded_reasons"], [])
        self.assertEqual(gate["input_states"]["adjustments"], "available")
        self.assertEqual(
            gate["ohlcv_readiness"]["adjustedDataRequirement"],
            {"required": False, "state": "not_required"},
        )

    def test_gate_consumes_historical_ohlcv_readiness_bar_counts_and_degraded_states(self) -> None:
        cases = [
            (
                "insufficient_history",
                self._historical_readiness(
                    overall_state="blocked",
                    required_bars=30,
                    usable_bars=12,
                    missing_bars=18,
                    missing_requirements=["insufficient_history"],
                ),
                "not_available",
            ),
            (
                "stale_data",
                self._historical_readiness(
                    overall_state="degraded",
                    missing_requirements=["stale_data"],
                    freshness_state="stale",
                ),
                "degraded",
            ),
            (
                "missing_adjustments",
                self._historical_readiness(
                    overall_state="degraded",
                    missing_requirements=["missing_adjustments"],
                    adjustment_state="missing",
                ),
                "not_available",
            ),
            (
                "missing_benchmark",
                self._historical_readiness(
                    overall_state="degraded",
                    missing_requirements=["missing_benchmark"],
                    benchmark_state="missing",
                ),
                "not_available",
            ),
            (
                "entitlement_required",
                self._historical_readiness(
                    provider_state="entitlement_required",
                    overall_state="blocked",
                    required_bars=30,
                    usable_bars=0,
                    missing_bars=30,
                    missing_requirements=["entitlement_required", "insufficient_history"],
                    freshness_state="unknown",
                ),
                "not_available",
            ),
        ]

        for expected_status, readiness, calculation_state in cases:
            with self.subTest(expected_status=expected_status):
                gate = assess_backtest_data_sufficiency(
                    {
                        "status": "completed",
                        "data_quality": self._sufficient_quality(),
                        "historicalOhlcvReadiness": readiness,
                    }
                )

                self.assertEqual(gate["status"], expected_status)
                self.assertEqual(gate["calculation_state"], calculation_state)
                self.assertEqual(gate["ohlcv_readiness"]["requiredBars"], readiness["requiredBars"])
                self.assertEqual(gate["ohlcv_readiness"]["usableBars"], readiness["usableBars"])
                self.assertEqual(gate["ohlcv_readiness"]["missingBars"], readiness["missingBars"])

    def test_gate_redacts_historical_ohlcv_readiness_internal_fields(self) -> None:
        gate = assess_backtest_data_sufficiency(
            {
                "status": "completed",
                "data_quality": self._sufficient_quality(),
                "historicalOhlcvReadiness": {
                    **self._historical_readiness(),
                    "providerName": "LeakyProvider",
                    "providerClass": "LeakyProviderClass",
                    "requestId": "rq-secret",
                    "traceId": "trace-secret",
                    "cacheKey": "cache-secret",
                    "rawPayload": {"token": "secret-token-value"},
                    "exceptionClass": "RuntimeError",
                    "endpointHost": "provider.example.test",
                },
            }
        )

        self._assert_no_forbidden_leakage(gate)

    def test_missing_benchmark_blocks_execution_without_fabricating_metrics(self) -> None:
        service = RuleBacktestService(self.db)
        with patch.object(service, "_ensure_market_history", return_value=0), patch.object(
            service,
            "_get_llm_adapter",
            return_value=None,
        ), patch.object(service.engine, "run", wraps=service.engine.run) as engine_run:
            response = service.run_backtest(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                benchmark_mode="custom_code",
                benchmark_code="SPY",
                confirmed=True,
            )

        engine_run.assert_not_called()
        gate = response["data_sufficiency"]
        self.assertEqual(gate["status"], "missing_benchmark")
        self.assertEqual(gate["calculation_state"], "not_available")
        self.assertIn("missing_benchmark", gate["blocked_reasons"])
        self.assertEqual(response["no_result_reason"], "missing_benchmark")
        self.assertIsNone(response["total_return_pct"])
        self.assertIsNone(response["max_drawdown_pct"])
        self.assertIsNone(response["benchmark_return_pct"])
        self.assertIsNone(response["excess_return_vs_benchmark_pct"])
        readiness = response["historicalOhlcvReadiness"]
        self.assertEqual(readiness["benchmarkReadiness"]["status"], "missing")
        self.assertGreater(readiness["symbolBarsAvailable"], 0)
        self.assertEqual(readiness["benchmarkBarsAvailable"], 0)
        self.assertIn("benchmark_ohlcv", readiness["missingDataFamilies"])
        self.assertNotIn("相对基准超额", response["ai_summary"])

    def test_insufficient_benchmark_coverage_blocks_execution_distinctly(self) -> None:
        self._seed_daily_rows("AAPL", [100.0 + index for index in range(24)])
        self._seed_daily_rows("SPY", [400.0, 401.0, 402.0])
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None), patch.object(
            service.engine,
            "run",
            wraps=service.engine.run,
        ) as engine_run:
            response = service.run_backtest(
                code="AAPL",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                start_date="2024-01-02",
                end_date="2024-01-19",
                lookback_bars=20,
                benchmark_mode="custom_code",
                benchmark_code="SPY",
                confirmed=True,
            )

        engine_run.assert_not_called()
        readiness = response["historicalOhlcvReadiness"]
        self.assertEqual(response["data_sufficiency"]["status"], "missing_benchmark")
        self.assertEqual(response["data_sufficiency"]["calculation_state"], "not_available")
        self.assertEqual(readiness["status"], "insufficient_coverage")
        self.assertEqual(readiness["benchmarkReadiness"]["status"], "insufficient_coverage")
        self.assertEqual(readiness["benchmarkBarsAvailable"], 3)
        self.assertIn("benchmark_ohlcv", readiness["missingDataFamilies"])
        self.assertNotIn("symbol_ohlcv", readiness["missingDataFamilies"])
        self.assertIsNone(response["total_return_pct"])

    def test_seeded_symbol_and_benchmark_adjusted_cache_unlocks_data110_execution(self) -> None:
        cache_dir = tempfile.TemporaryDirectory()
        self.addCleanup(cache_dir.cleanup)
        os.environ["LOCAL_US_PARQUET_DIR"] = cache_dir.name
        persist_local_us_daily_history("AAPL", self._cache_frame([100.0 + (index * 0.5) for index in range(28)]))
        persist_local_us_daily_history("SPY", self._cache_frame([400.0 + (index * 0.4) for index in range(28)]))
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None), patch.object(
            service.engine,
            "run",
            wraps=service.engine.run,
        ) as engine_run:
            response = service.run_backtest(
                code="AAPL",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                start_date="2024-01-02",
                end_date="2024-01-19",
                lookback_bars=20,
                benchmark_mode="custom_code",
                benchmark_code="SPY",
                confirmed=True,
            )

        self.assertGreater(engine_run.call_count, 0)
        gate = response["data_sufficiency"]
        readiness = response["historicalOhlcvReadiness"]
        self.assertEqual(response["status"], "completed")
        self.assertIsNone(response["no_result_reason"])
        self.assertEqual(gate["status"], "sufficient")
        self.assertEqual(gate["calculation_state"], "executable")
        self.assertEqual(readiness["status"], "available")
        self.assertTrue(readiness["executable"])
        self.assertEqual(readiness["adjustedDataRequirement"], {"required": True, "state": "available"})
        self.assertGreaterEqual(readiness["symbolBarsAvailable"], readiness["requiredBarCount"])
        self.assertGreaterEqual(readiness["benchmarkBarsAvailable"], readiness["requiredBarCount"])
        self.assertEqual(readiness["benchmarkReadiness"]["status"], "available")
        self.assertEqual(readiness["benchmarkReadiness"]["adjustmentState"], "available")
        self.assertIsNotNone(response["total_return_pct"])
        self.assertIsNotNone(response["benchmark_return_pct"])

    def test_seeded_symbol_and_benchmark_without_adjusted_blocks_data110_metrics(self) -> None:
        self._seed_daily_rows("AAPL", [100.0 + (index * 0.5) for index in range(28)])
        self._seed_daily_rows("SPY", [400.0 + (index * 0.4) for index in range(28)])
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None), patch.object(
            service.engine,
            "run",
            wraps=service.engine.run,
        ) as engine_run:
            response = service.run_backtest(
                code="AAPL",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                start_date="2024-01-02",
                end_date="2024-01-19",
                lookback_bars=20,
                benchmark_mode="custom_code",
                benchmark_code="SPY",
                confirmed=True,
            )

        engine_run.assert_not_called()
        readiness = response["historicalOhlcvReadiness"]
        self.assertEqual(response["data_sufficiency"]["status"], "missing_adjustments")
        self.assertEqual(response["data_sufficiency"]["calculation_state"], "not_available")
        self.assertEqual(response["no_result_reason"], "missing_adjustments")
        self.assertEqual(readiness["adjustedDataRequirement"], {"required": True, "state": "missing"})
        self.assertIn("adjusted_prices", readiness["missingDataFamilies"])
        self.assertIsNone(response["total_return_pct"])
        self.assertIsNone(response["benchmark_return_pct"])

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
                {"status": "provider_missing", "calculation_state": "not_available"},
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
