# -*- coding: utf-8 -*-
"""Tests for AI-assisted rule backtesting."""

import csv
import copy
import hashlib
import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from sqlalchemy import select

from src.config import Config
from src.core.rule_backtest_engine import RuleBacktestEngine, RuleBacktestParser
from src.services.backtest_professional_readiness import build_backtest_professional_readiness
from src.services.rule_backtest_support_exports import (
    build_execution_assumptions_fingerprint,
    build_execution_trace_export_csv_text,
    build_execution_trace_export_json_payload,
    build_reproducibility_authority_summary,
    build_support_bundle_reproducibility_manifest,
    build_support_bundle_manifest,
    build_support_export_index,
    resolve_stored_robustness_evidence_payload,
)
from src.services.rule_backtest_text_completion import create_rule_backtest_text_completion
from src.services.rule_backtest_service import RuleBacktestService, run_backtest_automated
from src.storage import DatabaseManager, RuleBacktestRun, RuleBacktestTrade, StockDaily

EXPECTED_TRACE_EXPORT_JSON_KEYS = [
    "version",
    "source",
    "completeness",
    "missing_fields",
    "trace_rows",
    "assumptions",
    "execution_model",
    "execution_assumptions",
    "benchmark_summary",
    "fallback",
]

EXPECTED_TRACE_EXPORT_FIELD_LABELS = [
    "日期",
    "标的收盘价",
    "基准收盘价",
    "信号摘要",
    "动作",
    "成交价",
    "持股数",
    "现金",
    "持仓市值",
    "总资产",
    "当日盈亏",
    "当日收益率",
    "策略累计收益率",
    "基准累计收益率",
    "买入持有累计收益率",
    "仓位",
    "手续费",
    "滑点",
    "备注",
    "assumptions",
    "fallback",
]

FORBIDDEN_PUBLIC_ADVICE_TERMS = [
    "place order",
    "submit order",
    "buy now",
    "sell now",
    "guaranteed",
    "must buy",
    "must sell",
    "ai recommends you buy",
    "best contract",
    "稳赚",
    "必买",
    "保证收益",
    "下单",
    "立即买入",
    "立即卖出",
    "立即交易",
    "买入按钮",
]

FORBIDDEN_BACKTEST_MUTATION_SURFACES = [
    "/api/v1/portfolio",
    "/api/v1/orders",
    "/api/v1/broker",
    "/api/v1/broker/orders",
    "/api/v1/trade",
    "/api/v1/execute",
    "/api/v1/submit-order",
    "broker_credentials",
    "broker_order_payload",
    "broker_execution",
    "order_placement",
    "order_payload",
    "place_order",
    "submit_order",
    "execute_order",
    "portfolio_mutation",
]

FORBIDDEN_ROBUSTNESS_OPTIMIZER_TERMS = [
    "optimizer",
    "optimization",
    "parameter_tuning",
    "parameter tuning",
    "auto_tune",
    "auto-tune",
    "grid_search",
    "grid search",
]

WALK_FORWARD_DIAGNOSTIC_WINDOW_KEYS = {
    "window_index",
    "state",
    "train_start",
    "train_end",
    "test_start",
    "test_end",
    "trade_count",
    "metrics",
}


class RuleBacktestTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_rule_backtest.db")
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

    def _allow_market_history_fetch(self) -> None:
        if getattr(self, "_ensure_market_history_patcher_active", False):
            self._ensure_market_history_patcher.stop()
            self._ensure_market_history_patcher_active = False

    @staticmethod
    def _make_bars(
        closes: list[float],
        *,
        start: date = date(2024, 1, 1),
        volumes: list[float] | None = None,
    ) -> list[SimpleNamespace]:
        resolved_volumes = volumes or [1000.0] * len(closes)
        return [
            SimpleNamespace(
                code="TEST",
                date=start + timedelta(days=index),
                open=float(close) - 0.1,
                high=float(close) + 0.2,
                low=max(0.01, float(close) - 0.3),
                close=float(close),
                volume=float(resolved_volumes[index]),
            )
            for index, close in enumerate(closes)
        ]

    def _seed_history(self, code: str, closes: list[float], *, start: date = date(2024, 1, 1)) -> None:
        with self.db.get_session() as session:
            for index, close in enumerate(closes):
                session.add(
                    StockDaily(
                        code=code,
                        date=start + timedelta(days=index),
                        open=float(close) - 0.1,
                        high=float(close) + 0.2,
                        low=max(0.01, float(close) - 0.3),
                        close=float(close),
                    )
                )
            session.commit()

    @staticmethod
    def _payload_without_allowed_oos_authority_flags(payload: dict) -> dict:
        normalized = copy.deepcopy(payload)
        evidence = normalized.get("walk_forward_oos_evidence")
        if isinstance(evidence, dict):
            authority = evidence.get("authority")
            if isinstance(authority, dict) and authority.get("optimizer_executed") is False:
                authority.pop("optimizer_executed")
        return normalized

    @staticmethod
    def _assert_public_backtest_text_is_analytical(text: str) -> None:
        normalized = text.lower()
        for needle in FORBIDDEN_PUBLIC_ADVICE_TERMS:
            assert needle.lower() not in normalized, needle
        for needle in FORBIDDEN_BACKTEST_MUTATION_SURFACES:
            assert needle.lower() not in normalized, needle

    @staticmethod
    def _assert_robustness_payload_avoids_optimizer_semantics(payload: dict) -> None:
        normalized_payload = RuleBacktestTestCase._payload_without_allowed_oos_authority_flags(payload)
        serialized = json.dumps(normalized_payload, ensure_ascii=False, sort_keys=True).lower()
        for needle in FORBIDDEN_ROBUSTNESS_OPTIMIZER_TERMS:
            assert needle not in serialized, needle

    @staticmethod
    def _assert_robustness_payload_stays_diagnostic_only(payload: dict) -> None:
        RuleBacktestTestCase._assert_robustness_payload_avoids_optimizer_semantics(payload)
        assert payload.get("source") == "summary.robustness_analysis"
        assert "professional_quant_ready" not in payload

        contract_metadata = dict(payload.get("contract_metadata") or {})
        assert contract_metadata.get("diagnostic_only") is True
        assert contract_metadata.get("parameter_selection_executed") is False
        assert contract_metadata.get("parameter_sweep_executed") is False
        assert contract_metadata.get("provider_calls_executed") is False
        assert contract_metadata.get("portfolio_allocation_backtest_executed") is False
        assert contract_metadata.get("professional_quant_readiness_claimed") is False
        assert contract_metadata.get("walk_forward_validation_claimed") is False
        assert contract_metadata.get("input_strategy_policy") == "reuse_input_strategy_without_parameter_search"

        walk_forward = dict(payload.get("walk_forward") or {})
        walk_forward_serialized = json.dumps(walk_forward, ensure_ascii=False, sort_keys=True).lower()
        for forbidden in (
            "validation_score",
            "validated_strategy",
            "selected_strategy",
            "optimized_parameters",
        ):
            assert forbidden not in walk_forward_serialized, forbidden

        windows = list(walk_forward.get("windows") or [])
        if windows:
            assert set(windows[0].keys()) == WALK_FORWARD_DIAGNOSTIC_WINDOW_KEYS

        oos_evidence = dict(payload.get("walk_forward_oos_evidence") or {})
        if oos_evidence:
            assert oos_evidence.get("contract_kind") == "backtest_walk_forward_oos_diagnostic_evidence"
            assert oos_evidence.get("diagnostic_only") is True
            assert oos_evidence.get("decision_grade") is False
            authority = dict(oos_evidence.get("authority") or {})
            assert authority.get("provider_calls_executed") is False
            assert authority.get("engine_math_changed") is False
            assert authority.get("strategy_parameters_mutated") is False
            assert authority.get("optimizer_executed") is False
            assert authority.get("parameter_sweep_executed") is False

    @staticmethod
    def _compare_run_payload(
        *,
        run_id: int,
        code: str,
        status: str = "completed",
        parsed_strategy: dict | None = None,
    ) -> dict:
        return {
            "id": run_id,
            "code": code,
            "status": status,
            "run_at": "2024-01-01T00:00:00",
            "completed_at": "2024-01-01T00:05:00" if status == "completed" else None,
            "timeframe": "daily",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "period_start": "2024-01-01",
            "period_end": "2024-01-31",
            "lookback_bars": 20,
            "initial_capital": 100000.0,
            "fee_bps": 0.0,
            "slippage_bps": 0.0,
            "parsed_strategy": parsed_strategy or {},
            "trade_count": 0,
            "win_count": 0,
            "loss_count": 0,
            "total_return_pct": 0.0,
            "annualized_return_pct": 0.0,
            "benchmark_return_pct": 0.0,
            "excess_return_vs_benchmark_pct": 0.0,
            "buy_and_hold_return_pct": 0.0,
            "excess_return_vs_buy_and_hold_pct": 0.0,
            "win_rate_pct": 0.0,
            "avg_trade_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "avg_holding_days": 0.0,
            "avg_holding_bars": 0.0,
            "avg_holding_calendar_days": 0.0,
            "final_equity": 100000.0,
            "benchmark_mode": "auto",
            "benchmark_code": None,
            "benchmark_summary": {},
            "buy_and_hold_summary": {},
            "execution_model": {},
            "result_authority": {},
        }

    def test_parse_simple_ma_rsi_strategy(self) -> None:
        parser = RuleBacktestParser()
        parsed = parser.parse("Buy when MA5 > MA20 and RSI6 < 40. Sell when MA5 < MA20 or RSI6 > 70.")

        self.assertEqual(parsed.timeframe, "daily")
        self.assertFalse(parsed.needs_confirmation)
        self.assertGreater(parsed.confidence, 0.9)
        self.assertEqual(parsed.summary["entry"], "买入条件：MA5 > MA20 且 RSI6 < 40")
        self.assertEqual(parsed.summary["exit"], "卖出条件：MA5 < MA20 或 RSI6 > 70")

    def test_parse_typo_ris6_suggests_rsi6(self) -> None:
        parser = RuleBacktestParser()
        parsed = parser.parse("Buy when MA5 > MA20 and RIS6 < 40. Sell when MA5 < MA20 or RSI6 > 70.")

        self.assertTrue(parsed.needs_confirmation)
        self.assertTrue(any("RSI6" in str(item.get("suggestion", "")) for item in parsed.ambiguities))

    def test_parse_chinese_periodic_buy_instruction_into_structured_draft(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy("资金100000，从2025-01-01到2025-12-31，每天买100股ORCL，买到资金耗尽为止")

        self.assertEqual(parsed["strategy_kind"], "periodic_accumulation")
        self.assertEqual(parsed["strategy_spec"]["strategy_type"], "periodic_accumulation")
        self.assertEqual(parsed["strategy_spec"]["strategy_family"], "periodic_accumulation")
        self.assertEqual(parsed["strategy_spec"]["symbol"], "ORCL")
        self.assertEqual(parsed["strategy_spec"]["date_range"]["start_date"], "2025-01-01")
        self.assertEqual(parsed["strategy_spec"]["date_range"]["end_date"], "2025-12-31")
        self.assertEqual(parsed["strategy_spec"]["capital"]["initial_capital"], 100000.0)
        self.assertEqual(parsed["strategy_spec"]["schedule"]["frequency"], "daily")
        self.assertEqual(parsed["strategy_spec"]["entry"]["order"]["mode"], "fixed_shares")
        self.assertEqual(parsed["strategy_spec"]["entry"]["order"]["quantity"], 100.0)
        self.assertEqual(parsed["strategy_spec"]["position_behavior"]["cash_policy"], "stop_when_insufficient_cash")
        self.assertEqual(parsed["strategy_spec"]["entry"]["price_basis"], "open")
        self.assertTrue(parsed["strategy_spec"]["support"]["executable"])
        self.assertTrue(parsed["needs_confirmation"])

    def test_parse_chinese_periodic_amount_instruction_into_structured_draft(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy("资金100000，从2025-01-01到2025-12-31，每天买1000元ORCL，买到区间结束")

        self.assertEqual(parsed["strategy_kind"], "periodic_accumulation")
        self.assertEqual(parsed["strategy_spec"]["strategy_type"], "periodic_accumulation")
        self.assertEqual(parsed["strategy_spec"]["symbol"], "ORCL")
        self.assertEqual(parsed["strategy_spec"]["entry"]["order"]["mode"], "fixed_amount")
        self.assertIsNone(parsed["strategy_spec"]["entry"]["order"]["quantity"])
        self.assertEqual(parsed["strategy_spec"]["entry"]["order"]["amount"], 1000.0)
        self.assertEqual(parsed["strategy_spec"]["position_behavior"]["cash_policy"], "skip_when_insufficient_cash")
        self.assertTrue(parsed["strategy_spec"]["support"]["executable"])

    def test_normalize_moving_average_crossover_strategy_spec(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy(
            "5日均线上穿20日均线买入，下穿卖出",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )

        self.assertEqual(parsed["strategy_kind"], "moving_average_crossover")
        self.assertEqual(parsed["strategy_spec"]["strategy_type"], "moving_average_crossover")
        self.assertEqual(parsed["strategy_spec"]["signal"]["indicator_family"], "moving_average")
        self.assertEqual(parsed["strategy_spec"]["signal"]["fast_period"], 5)
        self.assertEqual(parsed["strategy_spec"]["signal"]["slow_period"], 20)
        self.assertEqual(parsed["strategy_spec"]["signal"]["fast_type"], "simple")
        self.assertEqual(parsed["strategy_spec"]["signal"]["entry_condition"], "fast_crosses_above_slow")
        self.assertEqual(parsed["strategy_spec"]["execution"]["signal_timing"], "bar_close")
        self.assertEqual(parsed["strategy_spec"]["execution"]["fill_timing"], "next_bar_open")
        self.assertTrue(parsed["executable"])
        self.assertEqual(parsed["normalization_state"], "assumed")
        self.assertTrue(any(item.get("key") == "fast_type" for item in parsed["assumptions"]))

    def test_normalize_macd_crossover_strategy_spec(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy(
            "MACD金叉买入，死叉卖出",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )

        self.assertEqual(parsed["strategy_kind"], "macd_crossover")
        self.assertEqual(parsed["strategy_spec"]["strategy_type"], "macd_crossover")
        self.assertEqual(parsed["strategy_spec"]["signal"]["indicator_family"], "macd")
        self.assertEqual(parsed["strategy_spec"]["signal"]["fast_period"], 12)
        self.assertEqual(parsed["strategy_spec"]["signal"]["slow_period"], 26)
        self.assertEqual(parsed["strategy_spec"]["signal"]["signal_period"], 9)
        self.assertTrue(parsed["executable"])
        self.assertEqual(parsed["normalization_state"], "assumed")
        self.assertTrue(any(item.get("key") == "macd_periods" for item in parsed["assumptions"]))
        self.assertTrue(any(group.get("key") == "indicator_defaults" for group in parsed["assumption_groups"]))

    def test_normalize_rsi_threshold_strategy_spec(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy(
            "RSI 小于 30 买入，大于 70 卖出",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )

        self.assertEqual(parsed["strategy_kind"], "rsi_threshold")
        self.assertEqual(parsed["strategy_spec"]["strategy_type"], "rsi_threshold")
        self.assertEqual(parsed["strategy_spec"]["signal"]["indicator_family"], "rsi")
        self.assertEqual(parsed["strategy_spec"]["signal"]["period"], 14)
        self.assertEqual(parsed["strategy_spec"]["signal"]["lower_threshold"], 30.0)
        self.assertEqual(parsed["strategy_spec"]["signal"]["upper_threshold"], 70.0)
        self.assertEqual(parsed["strategy_spec"]["strategy_family"], "rsi_threshold")
        self.assertTrue(parsed["strategy_spec"]["support"]["executable"])
        self.assertTrue(parsed["executable"])
        self.assertEqual(parsed["normalization_state"], "assumed")
        self.assertTrue(any(item.get("key") == "rsi_period" for item in parsed["assumptions"]))

    def test_parse_strategy_returns_compact_unsupported_rewrite_guidance(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy(
            "AAPL和NVDA各半仓，MACD金叉买入，止损 5%",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )

        self.assertFalse(parsed["executable"])
        self.assertEqual(parsed["normalization_state"], "unsupported")
        self.assertIn("单一标的", parsed["unsupported_reason"])
        self.assertEqual(parsed["strategy_spec"]["support"]["normalization_state"], "unsupported")
        self.assertIn("单一标的", parsed["strategy_spec"]["support"]["unsupported_reason"])
        self.assertEqual(parsed["detected_strategy_family"], "macd_crossover")
        self.assertIn("MACD", parsed["core_intent_summary"])
        self.assertTrue(parsed["supported_portion_summary"])
        self.assertTrue(parsed["unsupported_details"])
        self.assertEqual(parsed["unsupported_details"][0]["code"], "unsupported_multi_symbol")
        self.assertGreaterEqual(len(parsed["unsupported_extensions"]), 2)
        self.assertGreaterEqual(len(parsed["rewrite_suggestions"]), 1)
        self.assertTrue(any("AAPL" in item["strategy_text"] or "NVDA" in item["strategy_text"] for item in parsed["rewrite_suggestions"]))

    def test_re_normalization_prefers_explicit_indicator_strategy_spec_over_setup_defaults(self) -> None:
        service = RuleBacktestService(self.db)
        parsed_dict = service.parse_strategy(
            "5日均线上穿20日均线买入，下穿卖出",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )
        parsed_dict["setup"]["fast_period"] = 5
        parsed_dict["setup"]["slow_period"] = 20
        parsed_dict["setup"]["fast_type"] = "simple"
        parsed_dict["strategy_spec"]["signal"]["fast_period"] = 8
        parsed_dict["strategy_spec"]["signal"]["slow_period"] = 21
        parsed_dict["strategy_spec"]["signal"]["fast_type"] = "ema"
        parsed_dict["strategy_spec"]["signal"]["slow_type"] = "ema"
        parsed_dict["strategy_spec"]["capital"]["initial_capital"] = 75000.0
        parsed_dict["strategy_spec"]["signal"]["unexpected_field"] = "drop_me"
        parsed_dict["strategy_spec"]["execution"]["unexpected_field"] = "drop_me"
        parsed_dict["strategy_spec"]["unexpected_field"] = "drop_me"

        parsed = service._dict_to_parsed_strategy(parsed_dict, parsed_dict["source_text"])
        normalized = service._normalize_parsed_strategy(parsed)

        self.assertEqual(normalized.strategy_spec["signal"]["fast_period"], 8)
        self.assertEqual(normalized.strategy_spec["signal"]["slow_period"], 21)
        self.assertEqual(normalized.strategy_spec["signal"]["fast_type"], "ema")
        self.assertEqual(normalized.strategy_spec["signal"]["slow_type"], "ema")
        self.assertEqual(normalized.strategy_spec["capital"]["initial_capital"], 75000.0)
        self.assertEqual(normalized.strategy_spec["strategy_family"], "moving_average_crossover")
        self.assertTrue(normalized.strategy_spec["support"]["executable"])
        self.assertNotIn("unexpected_field", normalized.strategy_spec)
        self.assertNotIn("unexpected_field", normalized.strategy_spec["signal"])
        self.assertNotIn("unexpected_field", normalized.strategy_spec["execution"])

    def test_re_normalization_prefers_explicit_periodic_strategy_spec_over_setup_defaults(self) -> None:
        service = RuleBacktestService(self.db)
        parsed_dict = service.parse_strategy("资金100000，从2025-01-01到2025-12-31，每天买100股ORCL，买到资金耗尽为止")
        parsed_dict["setup"]["order_mode"] = "fixed_shares"
        parsed_dict["setup"]["quantity_per_trade"] = 100
        parsed_dict["strategy_spec"]["entry"]["order"]["mode"] = "fixed_amount"
        parsed_dict["strategy_spec"]["entry"]["order"]["quantity"] = None
        parsed_dict["strategy_spec"]["entry"]["order"]["amount"] = 5000.0
        parsed_dict["strategy_spec"]["capital"]["initial_capital"] = 120000.0
        parsed_dict["strategy_spec"]["entry"]["order"]["unexpected_field"] = "drop_me"
        parsed_dict["strategy_spec"]["schedule"]["unexpected_field"] = "drop_me"
        parsed_dict["strategy_spec"]["unexpected_field"] = "drop_me"

        parsed = service._dict_to_parsed_strategy(parsed_dict, parsed_dict["source_text"])
        normalized = service._normalize_parsed_strategy(parsed)

        self.assertEqual(normalized.strategy_spec["entry"]["order"]["mode"], "fixed_amount")
        self.assertIsNone(normalized.strategy_spec["entry"]["order"]["quantity"])
        self.assertEqual(normalized.strategy_spec["entry"]["order"]["amount"], 5000.0)
        self.assertEqual(normalized.strategy_spec["capital"]["initial_capital"], 120000.0)
        self.assertEqual(normalized.strategy_spec["strategy_family"], "periodic_accumulation")
        self.assertTrue(normalized.strategy_spec["support"]["executable"])
        self.assertNotIn("unexpected_field", normalized.strategy_spec)
        self.assertNotIn("unexpected_field", normalized.strategy_spec["entry"]["order"])
        self.assertNotIn("unexpected_field", normalized.strategy_spec["schedule"])

    def test_normalize_legacy_setup_backed_indicator_strategy_into_canonical_family_shape(self) -> None:
        service = RuleBacktestService(self.db)
        parsed_dict = service.parse_strategy(
            "MACD金叉买入，死叉卖出",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )
        parsed_dict["strategy_spec"] = {}
        parsed_dict["setup"]["symbol"] = "AAPL"
        parsed_dict["setup"]["indicator_family"] = "macd"
        parsed_dict["setup"]["fast_period"] = 12
        parsed_dict["setup"]["slow_period"] = 26
        parsed_dict["setup"]["signal_period"] = 9
        parsed_dict["setup"]["initial_capital"] = 50000

        parsed = service._dict_to_parsed_strategy(parsed_dict, parsed_dict["source_text"])
        normalized = service._normalize_parsed_strategy(
            parsed,
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )

        self.assertEqual(normalized.strategy_spec["strategy_type"], "macd_crossover")
        self.assertEqual(normalized.strategy_spec["strategy_family"], "macd_crossover")
        self.assertEqual(normalized.strategy_spec["signal"]["indicator_family"], "macd")
        self.assertEqual(normalized.strategy_spec["signal"]["fast_period"], 12)
        self.assertEqual(normalized.strategy_spec["signal"]["slow_period"], 26)
        self.assertEqual(normalized.strategy_spec["signal"]["signal_period"], 9)
        self.assertEqual(normalized.strategy_spec["execution"]["signal_timing"], "bar_close")
        self.assertEqual(normalized.strategy_spec["execution"]["fill_timing"], "next_bar_open")
        self.assertEqual(normalized.strategy_spec["position_behavior"]["direction"], "long_only")
        self.assertEqual(normalized.strategy_spec["end_behavior"]["policy"], "liquidate_at_end")

    def test_request_normalization_prefers_camel_case_strategy_spec_over_legacy_setup_defaults(self) -> None:
        service = RuleBacktestService(self.db)
        base = service.parse_strategy(
            "MACD金叉买入，死叉卖出",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )
        request_payload = {
            "version": "v1",
            "timeframe": "daily",
            "sourceText": base["source_text"],
            "normalizedText": base["normalized_text"],
            "entry": base["entry"],
            "exit": base["exit"],
            "confidence": base["confidence"],
            "needsConfirmation": base["needs_confirmation"],
            "ambiguities": base["ambiguities"],
            "summary": base["summary"],
            "maxLookback": base["max_lookback"],
            "setup": {
                "symbol": "AAPL",
                "indicatorFamily": "macd",
                "fastPeriod": 5,
                "slowPeriod": 20,
                "signalPeriod": 7,
                "initialCapital": 50000,
            },
            "strategySpec": {
                "strategyType": "macd_crossover",
                "symbol": "AAPL",
                "dateRange": {"startDate": "2024-01-01", "endDate": "2024-12-31"},
                "capital": {"initialCapital": 75000.0, "currency": "USD"},
                "costs": {"feeBps": 1.5, "slippageBps": 2.5},
                "signal": {
                    "indicatorFamily": "macd",
                    "fastPeriod": 12,
                    "slowPeriod": 26,
                    "signalPeriod": 9,
                },
                "execution": {
                    "frequency": "daily",
                    "signalTiming": "bar_close",
                    "fillTiming": "next_bar_open",
                },
                "positionBehavior": {
                    "direction": "long_only",
                    "entrySizing": "all_in",
                    "maxPositions": 1,
                    "pyramiding": False,
                },
                "endBehavior": {"policy": "liquidate_at_end", "priceBasis": "close"},
            },
        }

        parsed = service._dict_to_parsed_strategy(request_payload, base["source_text"])
        normalized = service._normalize_parsed_strategy(parsed)

        self.assertEqual(parsed.strategy_kind, "macd_crossover")
        self.assertEqual(parsed.setup["fast_period"], 5)
        self.assertEqual(parsed.strategy_spec["signal"]["signal_period"], 9)
        self.assertEqual(normalized.strategy_spec["signal"]["fast_period"], 12)
        self.assertEqual(normalized.strategy_spec["signal"]["slow_period"], 26)
        self.assertEqual(normalized.strategy_spec["signal"]["signal_period"], 9)
        self.assertEqual(normalized.strategy_spec["capital"]["initial_capital"], 75000.0)
        self.assertEqual(normalized.strategy_spec["costs"]["fee_bps"], 1.5)
        self.assertEqual(normalized.strategy_spec["costs"]["slippage_bps"], 2.5)

    def test_request_normalization_accepts_camel_case_periodic_setup_legacy_input(self) -> None:
        service = RuleBacktestService(self.db)
        request_payload = {
            "version": "v1",
            "timeframe": "daily",
            "sourceText": "从2025-01-01到2025-12-31，每天买100股ORCL",
            "normalizedText": "从2025-01-01到2025-12-31，每天买100股ORCL",
            "entry": {"type": "group", "op": "and", "rules": []},
            "exit": {"type": "group", "op": "or", "rules": []},
            "confidence": 0.9,
            "needsConfirmation": True,
            "ambiguities": [],
            "summary": {"entry": "买入条件：--", "exit": "卖出条件：--", "strategy": "区间定投策略"},
            "maxLookback": 1,
            "strategyKind": "periodic_accumulation",
            "setup": {
                "symbol": "ORCL",
                "startDate": "2025-01-01",
                "endDate": "2025-12-31",
                "initialCapital": 100000,
                "orderMode": "fixed_shares",
                "quantityPerTrade": 100,
                "executionFrequency": "daily",
                "executionTiming": "session_open",
                "executionPriceBasis": "open",
                "cashPolicy": "stop_when_insufficient_cash",
            },
            "strategySpec": {},
        }

        parsed = service._dict_to_parsed_strategy(request_payload, request_payload["sourceText"])
        normalized = service._normalize_parsed_strategy(parsed)

        self.assertEqual(parsed.setup["start_date"], "2025-01-01")
        self.assertEqual(parsed.setup["quantity_per_trade"], 100)
        self.assertEqual(normalized.strategy_spec["strategy_type"], "periodic_accumulation")
        self.assertEqual(normalized.strategy_spec["symbol"], "ORCL")
        self.assertEqual(normalized.strategy_spec["date_range"]["start_date"], "2025-01-01")
        self.assertEqual(normalized.strategy_spec["entry"]["order"]["mode"], "fixed_shares")
        self.assertEqual(normalized.strategy_spec["entry"]["order"]["quantity"], 100.0)

    def test_request_normalization_preserves_generic_fallback_for_unsupported_structured_input(self) -> None:
        service = RuleBacktestService(self.db)
        request_payload = {
            "version": "v1",
            "timeframe": "daily",
            "sourceText": "如果指数跌破均线则空仓，否则执行自定义逻辑",
            "normalizedText": "如果指数跌破均线则空仓，否则执行自定义逻辑",
            "entry": {"type": "group", "op": "and", "rules": []},
            "exit": {"type": "group", "op": "or", "rules": []},
            "confidence": 0.8,
            "needsConfirmation": True,
            "ambiguities": [],
            "summary": {"entry": "买入条件：--", "exit": "卖出条件：--", "strategy": "自定义策略"},
            "maxLookback": 5,
            "setup": {
                "indicatorFamily": "macd",
                "fastPeriod": 12,
                "slowPeriod": 26,
            },
            "strategySpec": {
                "strategyType": "custom_branching_strategy",
                "strategyFamily": "custom_branching_strategy",
                "customBranching": {"if": "index_below_ma", "then": "flat"},
                "customThreshold": 5,
            },
        }

        parsed = service._dict_to_parsed_strategy(request_payload, request_payload["sourceText"])
        normalized = service._normalize_parsed_strategy(parsed)

        self.assertEqual(parsed.strategy_kind, "custom_branching_strategy")
        self.assertEqual(normalized.strategy_spec["strategy_type"], "custom_branching_strategy")
        self.assertEqual(normalized.strategy_spec["strategy_family"], "custom_branching_strategy")
        self.assertEqual(normalized.strategy_spec["customBranching"]["if"], "index_below_ma")
        self.assertEqual(normalized.strategy_spec["customThreshold"], 5)
        self.assertNotIn("signal", normalized.strategy_spec)

    def test_parse_strategy_supports_fixed_stop_loss_extension_for_indicator_strategy(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy(
            "MACD金叉买入，止损5%，死叉卖出",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )

        self.assertTrue(parsed["executable"])
        self.assertNotEqual(parsed["normalization_state"], "unsupported")
        self.assertEqual(parsed["detected_strategy_family"], "macd_crossover")
        self.assertIn("MACD", parsed["core_intent_summary"])
        self.assertEqual(parsed["strategy_spec"]["risk_controls"]["stop_loss_pct"], 5.0)
        self.assertEqual(parsed["unsupported_details"], [])
        self.assertEqual(parsed["unsupported_extensions"], [])

    def test_parse_strategy_supports_take_profit_extension_for_indicator_strategy(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy(
            "MACD金叉买入，止损5%，止盈10%，死叉卖出",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )

        self.assertTrue(parsed["executable"])
        self.assertNotEqual(parsed["normalization_state"], "unsupported")
        self.assertEqual(parsed["detected_strategy_family"], "macd_crossover")
        self.assertEqual(parsed["strategy_spec"]["risk_controls"]["stop_loss_pct"], 5.0)
        self.assertEqual(parsed["strategy_spec"]["risk_controls"]["take_profit_pct"], 10.0)
        self.assertEqual(parsed["unsupported_details"], [])
        self.assertEqual(parsed["unsupported_extensions"], [])

    def test_parse_strategy_supports_trailing_stop_extension_for_indicator_strategy(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy(
            "5日均线上穿20日均线买入，移动止损8%，下穿卖出",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )

        self.assertTrue(parsed["executable"])
        self.assertNotEqual(parsed["normalization_state"], "unsupported")
        self.assertEqual(parsed["detected_strategy_family"], "moving_average_crossover")
        self.assertEqual(parsed["strategy_spec"]["risk_controls"]["trailing_stop_pct"], 8.0)
        self.assertEqual(parsed["unsupported_details"], [])
        self.assertEqual(parsed["unsupported_extensions"], [])

    def test_parse_strategy_marks_scaling_request_unsupported_with_rsi_rewrite(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy(
            "RSI低于30分三批买入，高于70卖出",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )

        self.assertFalse(parsed["executable"])
        self.assertEqual(parsed["normalization_state"], "unsupported")
        self.assertEqual(parsed["detected_strategy_family"], "rsi_threshold")
        self.assertIn("RSI", parsed["core_intent_summary"])
        self.assertEqual(parsed["unsupported_details"][0]["code"], "unsupported_position_scaling")
        self.assertIn("RSI", parsed["supported_portion_summary"])
        self.assertTrue(any("RSI14 低于30买入，高于70卖出" in item["strategy_text"] for item in parsed["rewrite_suggestions"]))

    def test_parse_strategy_marks_parameter_optimization_unsupported_with_fixed_parameter_rewrite(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy(
            "优化 2020 到 2025 最佳 MACD 参数",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )

        self.assertFalse(parsed["executable"])
        self.assertEqual(parsed["normalization_state"], "unsupported")
        self.assertEqual(parsed["detected_strategy_family"], "macd_crossover")
        self.assertIn("MACD", parsed["core_intent_summary"])
        self.assertEqual(parsed["unsupported_details"][0]["code"], "unsupported_parameter_optimization")
        self.assertIn("MACD", parsed["supported_portion_summary"])
        self.assertTrue(any("MACD金叉买入，死叉卖出" in item["strategy_text"] for item in parsed["rewrite_suggestions"]))

    def test_parse_strategy_surfaces_partial_family_guidance_for_generic_indicator_requests(self) -> None:
        service = RuleBacktestService(self.db)
        cases = [
            ("均线策略", "均线", "5日均线上穿20日均线买入，下穿卖出"),
            ("MACD策略", "MACD", "MACD金叉买入，死叉卖出"),
            ("RSI策略", "RSI", "RSI14 低于30买入，高于70卖出"),
        ]

        for text, expected_summary_token, expected_rewrite in cases:
            with self.subTest(text=text):
                parsed = service.parse_strategy(
                    text,
                    code="AAPL",
                    start_date="2024-01-01",
                    end_date="2024-12-31",
                    initial_capital=50000,
                )

                self.assertFalse(parsed["executable"])
                self.assertEqual(parsed["normalization_state"], "unsupported")
                self.assertEqual(parsed["unsupported_details"][0]["code"], "unsupported_missing_exit_rule")
                self.assertIsNotNone(parsed["detected_strategy_family"])
                self.assertIsNotNone(parsed["core_intent_summary"])
                self.assertIn(expected_summary_token, parsed["supported_portion_summary"])
                self.assertTrue(any(expected_rewrite in item["strategy_text"] for item in parsed["rewrite_suggestions"]))

    def test_parse_strategy_preserves_ma_core_intent_when_stop_extension_is_unsupported(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy(
            "5日线上穿20日线买入，跌破10日线止损",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )

        self.assertFalse(parsed["executable"])
        self.assertEqual(parsed["normalization_state"], "unsupported")
        self.assertEqual(parsed["detected_strategy_family"], "moving_average_crossover")
        self.assertIn("均线交叉", parsed["core_intent_summary"])
        self.assertTrue(any(item["code"] == "unsupported_strategy_combination" for item in parsed["unsupported_extensions"]))
        self.assertTrue(any("5日均线上穿20日均线买入，下穿卖出" in item["strategy_text"] for item in parsed["rewrite_suggestions"]))

    def test_engine_evaluates_sample_history_deterministically(self) -> None:
        parser = RuleBacktestParser()
        parsed = parser.parse("Buy when Close > MA3. Sell when Close < MA3.")
        engine = RuleBacktestEngine()

        with self.db.get_session() as session:
            bars = session.query(StockDaily).filter(StockDaily.code == "600519").order_by(StockDaily.date).all()

        result = engine.run(
            code="600519",
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=100000.0,
            fee_bps=0.0,
            lookback_bars=20,
        )

        self.assertGreater(result.metrics["trade_count"], 0)
        self.assertIsNone(result.no_result_reason)
        self.assertGreater(len(result.equity_curve), 0)
        self.assertIn("buy_and_hold_return_pct", result.metrics)
        self.assertIn("excess_return_vs_buy_and_hold_pct", result.metrics)
        self.assertGreater(len(result.benchmark_curve), 0)
        self.assertEqual(result.benchmark_summary["method"], "same_symbol_buy_and_hold")
        self.assertEqual(result.execution_model.signal_evaluation_timing, "bar_close")
        self.assertEqual(result.execution_model.entry_timing, "next_bar_open")
        self.assertEqual(result.execution_model.entry_fill_price_basis, "open")
        self.assertEqual(result.execution_model.market_rules["terminal_bar_fill_fallback"], "same_bar_close")
        result_payload = result.to_dict()
        self.assertGreater(len(result_payload["benchmark_curve"]), 0)
        self.assertEqual(result_payload["execution_model"]["entry_timing"], "next_bar_open")
        self.assertIn("cash", result_payload["equity_curve"][0])
        self.assertIn("shares_held", result_payload["equity_curve"][0])
        self.assertIn("total_portfolio_value", result_payload["equity_curve"][0])
        first_trade = result_payload["trades"][0]
        self.assertEqual(first_trade["side"], "long")
        self.assertEqual(first_trade["entry_reason"], "signal_entry")
        self.assertIn(first_trade["exit_reason"], {"signal_exit", "final_close"})
        self.assertGreater(first_trade["quantity"], 0)
        self.assertIn("gross_pnl", first_trade)
        self.assertIn("net_pnl", first_trade)
        self.assertIn("fees", first_trade)
        self.assertIn("slippage", first_trade)
        self.assertEqual(first_trade["signal_reason"], "rule_conditions")
        self.assertEqual(result.execution_assumptions.indicator_price_basis, "close")
        self.assertEqual(result.execution_assumptions.entry_fill_timing, "next_bar_open")

    def test_engine_fixture_is_deterministic_explicit_and_uses_next_bar_entries(self) -> None:
        parser = RuleBacktestParser()
        parsed = parser.parse("Buy when Close > MA3. Sell when Close < MA3.")
        engine = RuleBacktestEngine()

        bars = self._make_bars(
            [10.0, 10.0, 10.0, 11.0, 12.0, 9.0, 8.0, 10.0],
            start=date(2024, 1, 1),
        )
        first = engine.run(
            code="SAFE",
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=100000.0,
            fee_bps=2.5,
            slippage_bps=1.25,
            lookback_bars=20,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 8),
        ).to_dict()
        second = engine.run(
            code="SAFE",
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=100000.0,
            fee_bps=2.5,
            slippage_bps=1.25,
            lookback_bars=20,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 8),
        ).to_dict()

        self.assertEqual(first["metrics"], second["metrics"])
        self.assertEqual(first["trades"], second["trades"])
        self.assertEqual(first["equity_curve"], second["equity_curve"])
        self.assertEqual(first["execution_model"]["fee_bps_per_side"], 2.5)
        self.assertEqual(first["execution_model"]["slippage_bps_per_side"], 1.25)
        self.assertEqual(first["execution_model"]["entry_timing"], "next_bar_open")
        self.assertEqual(first["execution_assumptions"]["entry_fill_timing"], "next_bar_open")
        self.assertGreater(len(first["trades"]), 0)
        for trade in first["trades"]:
            self.assertLess(trade["entry_signal_date"], trade["entry_date"])

    def test_engine_entry_fill_is_stable_when_future_candles_change(self) -> None:
        parser = RuleBacktestParser()
        parsed = parser.parse("Buy when Close > MA3. Sell when Close < MA3.")
        engine = RuleBacktestEngine()

        prefix = [10.0, 10.0, 10.0, 11.0, 12.0]
        base = engine.run(
            code="SAFE",
            parsed_strategy=parsed,
            bars=self._make_bars(prefix, start=date(2024, 1, 1)),
            initial_capital=100000.0,
            lookback_bars=20,
        ).to_dict()
        with_future_shock = engine.run(
            code="SAFE",
            parsed_strategy=parsed,
            bars=self._make_bars(prefix + [200.0, 1.0], start=date(2024, 1, 1)),
            initial_capital=100000.0,
            lookback_bars=20,
        ).to_dict()

        self.assertGreater(len(base["trades"]), 0)
        self.assertGreater(len(with_future_shock["trades"]), 0)
        self.assertEqual(base["trades"][0]["entry_signal_date"], with_future_shock["trades"][0]["entry_signal_date"])
        self.assertEqual(base["trades"][0]["entry_date"], with_future_shock["trades"][0]["entry_date"])
        self.assertEqual(base["trades"][0]["entry_price"], with_future_shock["trades"][0]["entry_price"])

    def test_service_missing_market_data_returns_safe_sanitized_no_result(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_ensure_market_history", return_value=0), patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.run_backtest(
                code="NODATA",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                start_date="2024-01-01",
                end_date="2024-01-31",
                lookback_bars=20,
                confirmed=True,
            )

        self.assertEqual(response["status"], "completed")
        self.assertEqual(response["no_result_reason"], "insufficient_history")
        self.assertEqual(response["trade_count"], 0)
        self.assertEqual(response["data_quality"]["bar_count"], 0)
        self.assertTrue(response["data_quality"]["source"])
        self.assertTrue(response["data_quality"]["warnings"])
        self.assertIn("no_result_reason", response)
        self.assertIn("data_quality", response["summary"])
        self.assertEqual(response["summary"]["data_quality"]["bar_count"], 0)
        self.assertIsNotNone(response["no_result_message"])
        serialized = json.dumps(response, ensure_ascii=False, sort_keys=True)
        for forbidden in ("SECRET", "TOKEN", "api_key", "payload_json", "raw_provider_payload"):
            self.assertNotIn(forbidden, serialized)
        self._assert_public_backtest_text_is_analytical(serialized)

    def test_service_normalizes_timezone_datetime_boundaries_to_dates(self) -> None:
        service = RuleBacktestService(self.db)

        start_date, end_date = service._normalize_date_range(
            start_date="2024-01-05T23:30:00+08:00",
            end_date="2024-01-20T00:30:00+08:00",
        )

        self.assertEqual(start_date, date(2024, 1, 5))
        self.assertEqual(end_date, date(2024, 1, 20))

    def test_service_runs_periodic_accumulation_with_existing_result_shape(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy("资金100000，从2024-01-05到2024-01-20，每天买100股ORCL，买到资金耗尽为止", code="600519")
        parsed["setup"] = {}

        with patch.object(service, "_ensure_market_history", return_value=0):
            response = service.run_backtest(
                code="600519",
                strategy_text=parsed["source_text"],
                parsed_strategy=parsed,
                start_date="2024-01-05",
                end_date="2024-01-20",
                initial_capital=100000.0,
                confirmed=True,
            )

        self.assertEqual(response["parsed_strategy"]["strategy_kind"], "periodic_accumulation")
        self.assertEqual(response["parsed_strategy"]["strategy_spec"]["strategy_type"], "periodic_accumulation")
        self.assertEqual(response["start_date"], "2024-01-05")
        self.assertEqual(response["end_date"], "2024-01-20")
        self.assertEqual(response["period_start"], "2024-01-05")
        self.assertEqual(response["period_end"], "2024-01-20")
        self.assertGreater(len(response["equity_curve"]), 0)
        self.assertGreater(len(response["trades"]), 0)
        self.assertGreater(len(response["benchmark_curve"]), 0)
        self.assertEqual(response["benchmark_summary"]["method"], "same_symbol_buy_and_hold")
        self.assertGreater(len(response["buy_and_hold_curve"]), 0)
        self.assertEqual(response["buy_and_hold_summary"]["resolved_mode"], "same_symbol_buy_and_hold")
        self.assertGreater(len(response["audit_rows"]), 0)
        self.assertEqual(response["summary"]["visualization"]["audit_rows"], response["audit_rows"])
        self.assertEqual(response["execution_model"]["entry_timing"], "same_bar_open")
        self.assertEqual(response["execution_model"]["exit_timing"], "forced_close_at_window_end_close")
        self.assertEqual(response["summary"]["execution_model"]["entry_fill_price_basis"], "open")
        self.assertIn("total_portfolio_value", response["audit_rows"][0])
        self.assertIn("cumulative_return", response["audit_rows"][0])
        self.assertIn("position", response["audit_rows"][0])
        self.assertEqual(response["trades"][0]["entry_reason"], "scheduled_entry")
        self.assertEqual(response["trades"][0]["exit_reason"], "final_close")
        self.assertGreater(response["trades"][0]["quantity"], 0)
        self.assertIn("net_pnl", response["trades"][0])
        self.assertGreater(len(response["daily_return_series"]), 0)
        self.assertGreater(len(response["exposure_curve"]), 0)
        self.assertIn("execution_assumptions", response)
        self.assertIn("total_return_pct", response)

    def test_rule_backtest_result_includes_data_quality_and_execution_metadata(self) -> None:
        service = RuleBacktestService(self.db)
        with self.db.get_session() as session:
            rows = session.query(StockDaily).filter(StockDaily.code == "600519").all()
            for row in rows:
                row.data_source = "local_us_parquet"
            session.commit()

        with patch.object(service, "_ensure_market_history", return_value=0), patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.run_backtest(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                start_date="2024-01-05",
                end_date="2024-01-20",
                lookback_bars=20,
                fee_bps=2.5,
                slippage_bps=1.25,
                benchmark_mode="same_symbol_buy_and_hold",
                confirmed=True,
            )

        data_quality = response["data_quality"]
        self.assertEqual(data_quality["symbol"], "600519")
        self.assertEqual(data_quality["source"], "local_us_parquet")
        self.assertEqual(data_quality["frequency"], "1d")
        self.assertEqual(data_quality["requested_start"], "2024-01-05")
        self.assertEqual(data_quality["requested_end"], "2024-01-20")
        self.assertGreater(data_quality["bar_count"], 0)
        self.assertIn("actual_start", data_quality)
        self.assertIn("actual_end", data_quality)
        self.assertEqual(data_quality["authority_status"], "allowed")
        self.assertEqual(data_quality["authority_source_type"], "cache_snapshot")
        self.assertEqual(data_quality["authority_reason_codes"], [])
        self.assertEqual(data_quality["adjustment_mode"], "unknown")
        self.assertEqual(data_quality["dividends_handled"], "unknown")
        self.assertEqual(data_quality["splits_handled"], "unknown")
        self.assertTrue(any(warning["code"] == "adjustment_status_unknown" for warning in data_quality["warnings"]))

        assumptions = response["execution_assumptions"]
        self.assertEqual(assumptions["engine"], "deterministic")
        self.assertEqual(assumptions["fee_model"]["commission_bps"], 2.5)
        self.assertEqual(assumptions["slippage_model"]["slippage_bps"], 1.25)
        self.assertEqual(assumptions["fill_price"], "open")
        self.assertTrue(assumptions["allow_fractional_shares"])
        self.assertEqual(response["summary"]["data_quality"], data_quality)

    def test_rule_backtest_data_quality_marks_proxy_history_as_degraded_fill_only(self) -> None:
        service = RuleBacktestService(self.db)
        with self.db.get_session() as session:
            rows = session.query(StockDaily).filter(StockDaily.code == "600519").all()
            for row in rows:
                row.data_source = "yfinance"
            session.commit()

        with patch.object(service, "_ensure_market_history", return_value=0), patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.run_backtest(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                start_date="2024-01-05",
                end_date="2024-01-20",
                lookback_bars=20,
                benchmark_mode="same_symbol_buy_and_hold",
                confirmed=True,
            )

        data_quality = response["data_quality"]
        self.assertEqual(data_quality["source"], "yfinance")
        self.assertEqual(data_quality["authority_status"], "degraded_fill_only")
        self.assertEqual(data_quality["authority_source_type"], "unofficial_proxy")
        self.assertIn("proxy_source_not_reproducible", data_quality["authority_reason_codes"])
        self.assertTrue(any(warning["code"] == "backtest_authority_degraded" for warning in data_quality["warnings"]))
        self.assertEqual(response["professionalReadiness"]["reproducibility_state"], "degraded_source_authority")
        self.assertIn(
            "proxy_source_not_reproducible",
            response["professionalReadiness"]["categories"]["reproducibility"]["blockers"],
        )

    def test_rule_backtest_data_quality_marks_unknown_history_source_as_degraded_fill_only(self) -> None:
        service = RuleBacktestService(self.db)
        run_kwargs = {
            "code": "600519",
            "strategy_text": "Buy when Close > MA3. Sell when Close < MA3.",
            "start_date": "2024-01-05",
            "end_date": "2024-01-20",
            "lookback_bars": 20,
            "benchmark_mode": "same_symbol_buy_and_hold",
            "confirmed": True,
        }

        with self.db.get_session() as session:
            rows = session.query(StockDaily).filter(StockDaily.code == "600519").all()
            for row in rows:
                row.data_source = "local_us_parquet"
            session.commit()

        with patch.object(service, "_get_llm_adapter", return_value=None):
            local_response = service.run_backtest(**run_kwargs)

        with self.db.get_session() as session:
            rows = session.query(StockDaily).filter(StockDaily.code == "600519").all()
            for row in rows:
                row.data_source = "Unknown"
            session.commit()

        with patch.object(service, "_get_llm_adapter", return_value=None):
            unknown_response = service.run_backtest(**run_kwargs)

        data_quality = unknown_response["data_quality"]
        self.assertEqual(data_quality["source"], "Unknown")
        self.assertEqual(data_quality["authority_status"], "degraded_fill_only")
        self.assertEqual(data_quality["authority_source_type"], "missing")
        self.assertEqual(data_quality["authority_reason_codes"], ["source_authority_unknown"])
        self.assertTrue(any(warning["code"] == "backtest_authority_degraded" for warning in data_quality["warnings"]))
        self.assertEqual(unknown_response["professionalReadiness"]["reproducibility_state"], "degraded_source_authority")
        self.assertIn(
            "source_authority_unknown",
            unknown_response["professionalReadiness"]["categories"]["reproducibility"]["blockers"],
        )
        for key in ("trade_count", "total_return_pct", "max_drawdown_pct", "final_equity"):
            self.assertEqual(unknown_response[key], local_response[key])
        self.assertEqual(unknown_response["trades"], local_response["trades"])

    def test_rule_backtest_data_quality_reports_missing_bars_and_anomalies(self) -> None:
        service = RuleBacktestService(self.db)
        self._seed_history(
            "MISS",
            [100, 101, 102, 103, 104, 105, 106, 170, 108, 109, 110],
            start=date(2024, 1, 1),
        )
        with self.db.get_session() as session:
            skipped = session.query(StockDaily).filter(StockDaily.code == "MISS", StockDaily.date == date(2024, 1, 8)).one()
            session.delete(skipped)
            anomalous = session.query(StockDaily).filter(StockDaily.code == "MISS", StockDaily.date == date(2024, 1, 9)).one()
            anomalous.high = 120.0
            anomalous.low = 121.0
            session.commit()

        with patch.object(service, "_ensure_market_history", return_value=0), patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.run_backtest(
                code="MISS",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                start_date="2024-01-01",
                end_date="2024-01-16",
                lookback_bars=20,
                benchmark_mode="same_symbol_buy_and_hold",
                confirmed=True,
            )

        data_quality = response["data_quality"]
        warning_codes = {warning["code"] for warning in data_quality["warnings"]}
        self.assertGreater(data_quality["missing_bar_count"], 0)
        self.assertIn("missing_bars_detected", warning_codes)
        self.assertGreater(data_quality["anomaly_count"], 0)
        self.assertIn("ohlcv_anomalies_detected", warning_codes)
        self.assertTrue(any(anomaly["type"] == "high_below_low" for anomaly in data_quality["anomalies"]))

    def test_rule_backtest_data_quality_reports_missing_benchmark_without_changing_returns(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_ensure_market_history", return_value=0), patch.object(service, "_get_llm_adapter", return_value=None):
            baseline = service.run_backtest(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                benchmark_mode="none",
                confirmed=True,
            )

        with (
            patch.object(service, "_ensure_market_history", return_value=0),
            patch.object(service, "_get_llm_adapter", return_value=None),
            patch.object(
                service,
                "_load_external_benchmark_context",
                return_value=([], {"label": "SPY", "resolved_mode": "custom_code", "return_pct": None}, "SPY 在当前窗口没有可用行情。"),
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

        self.assertEqual(response["total_return_pct"], baseline["total_return_pct"])
        self.assertTrue(any(warning["code"] == "benchmark_data_missing" for warning in response["data_quality"]["warnings"]))

    def test_service_run_backtest_fetches_missing_us_history_via_shared_local_first_helper(self) -> None:
        self._allow_market_history_fetch()
        service = RuleBacktestService(self.db)
        frame = pd.DataFrame(
            [
                {
                    "date": current_date.isoformat(),
                    "open": close - 0.1,
                    "high": close + 0.2,
                    "low": max(0.01, close - 0.3),
                    "close": close,
                    "volume": 1000,
                }
                for current_date, close in [
                    (date(2024, 1, 1) + timedelta(days=index), 100.0 + index)
                    for index in range(24)
                ]
            ]
        )

        with patch(
            "src.services.rule_backtest_service.fetch_daily_history_with_local_us_fallback",
            return_value=(frame, "local_us_parquet"),
        ) as fetch_mock, patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.run_backtest(
                code="AAPL",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                start_date="2024-01-05",
                end_date="2024-01-24",
                lookback_bars=10,
                initial_capital=100000.0,
                benchmark_mode="none",
                confirmed=True,
            )

        fetch_mock.assert_called_once()
        self.assertEqual(fetch_mock.call_args.args[0], "AAPL")
        self.assertEqual(fetch_mock.call_args.kwargs["log_context"], "[rule-backtest date-range history]")
        self.assertEqual(response["code"], "AAPL")
        self.assertIsNone(response["no_result_reason"])
        self.assertGreater(len(response["equity_curve"]), 0)
        self.assertGreater(len(response["trades"]), 0)

        with self.db.get_session() as session:
            daily_rows = session.query(StockDaily).filter(StockDaily.code == "AAPL").order_by(StockDaily.date).all()

        self.assertEqual(len(daily_rows), 24)
        self.assertEqual(daily_rows[0].date.isoformat(), "2024-01-01")
        self.assertEqual(daily_rows[-1].date.isoformat(), "2024-01-24")

    def test_service_uses_market_appropriate_auto_benchmark_defaults(self) -> None:
        service = RuleBacktestService(self.db)

        self.assertEqual(service._default_benchmark_mode_for_code("600519"), "index_hs300")
        self.assertEqual(service._default_benchmark_mode_for_code("AAPL"), "etf_qqq")
        self.assertEqual(service._default_benchmark_mode_for_code("BTC-USD"), "same_symbol_buy_and_hold")

    def test_service_exposes_sharpe_ratio_through_run_detail_and_history(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )

        detail = service.get_run(response["id"])
        history = service.list_runs(code="600519", page=1, limit=10)

        self.assertIsNotNone(response["sharpe_ratio"])
        self.assertEqual(response["sharpe_ratio"], response["summary"]["metrics"]["sharpe_ratio"])
        self.assertEqual(detail["sharpe_ratio"], response["sharpe_ratio"])
        self.assertEqual(history["items"][0]["sharpe_ratio"], response["sharpe_ratio"])
        self.assertIn("summary.metrics", detail["result_authority"]["metrics_source"])
        self.assertIn("summary.metrics", history["items"][0]["result_authority"]["metrics_source"])

    def test_service_applies_custom_benchmark_context_for_custom_code_mode(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None), patch.object(
            service,
            "_load_external_benchmark_context",
            return_value=(
                [
                    {"date": "2024-01-08", "close": 100.0, "cumulative_return_pct": 0.0},
                    {"date": "2024-01-09", "close": 103.0, "cumulative_return_pct": 3.0},
                ],
                {
                    "requested_mode": "custom_code",
                    "resolved_mode": "custom_code",
                    "label": "自定义 SPY",
                    "code": "SPY",
                    "method": "benchmark_security",
                    "auto_resolved": False,
                    "fallback_used": False,
                    "return_pct": 3.0,
                },
                None,
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

        self.assertEqual(response["benchmark_summary"]["resolved_mode"], "custom_code")
        self.assertEqual(response["benchmark_summary"]["code"], "SPY")
        self.assertEqual(response["benchmark_return_pct"], 3.0)
        self.assertEqual(
            response["summary"]["visualization"]["comparison"]["metrics"]["benchmark_return_pct"],
            3.0,
        )
        self.assertIn("sharpe_ratio", response["summary"]["metrics"])

    def test_engine_honors_explicit_start_end_date_window(self) -> None:
        parser = RuleBacktestParser()
        parsed = parser.parse("Buy when Close > MA3. Sell when Close < MA3.")
        engine = RuleBacktestEngine()

        with self.db.get_session() as session:
            bars = session.query(StockDaily).filter(StockDaily.code == "600519").order_by(StockDaily.date).all()

        result = engine.run(
            code="600519",
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=100000.0,
            fee_bps=0.0,
            lookback_bars=20,
            start_date=date(2024, 1, 8),
            end_date=date(2024, 1, 18),
        )

        self.assertEqual(result.metrics["period_start"], "2024-01-08")
        self.assertEqual(result.metrics["period_end"], "2024-01-18")
        self.assertTrue(all(point.date >= date(2024, 1, 8) for point in result.equity_curve))
        self.assertTrue(all(point.date <= date(2024, 1, 18) for point in result.equity_curve))
        self.assertTrue(all((point.get("date") or "") >= "2024-01-08" for point in result.benchmark_curve))
        self.assertTrue(all((point.get("date") or "") <= "2024-01-18" for point in result.benchmark_curve))
        self.assertTrue(all(trade.entry_date >= date(2024, 1, 8) for trade in result.trades))
        self.assertTrue(all(trade.exit_date <= date(2024, 1, 18) for trade in result.trades))

    def test_build_walk_forward_analysis_splits_rolling_windows_and_aggregates_metrics(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service._dict_to_parsed_strategy(
            service.parse_strategy(
                "Buy when Close > MA3. Sell when Close < MA3.",
                code="TEST",
                start_date="2024-01-01",
                end_date="2024-05-31",
                initial_capital=100000.0,
            ),
            "Buy when Close > MA3. Sell when Close < MA3.",
        )
        bars = self._make_bars(
            [100.0 + (index * 0.35) + ((-1) ** index) * 1.25 for index in range(72)],
            start=date(2024, 1, 1),
        )

        payload = service._build_walk_forward_analysis(
            code="TEST",
            parsed=parsed,
            bars=bars,
            initial_capital=100000.0,
            fee_bps=0.0,
            slippage_bps=0.0,
            lookback_bars=20,
            benchmark_mode="auto",
            benchmark_code=None,
            train_bars=24,
            test_bars=12,
            step_bars=12,
            max_windows=4,
        )

        self.assertEqual(payload["state"], "available")
        self.assertEqual(payload["window_count"], 4)
        self.assertEqual(len(payload["windows"]), 4)
        self.assertEqual(payload["windows"][0]["train_start"], "2024-01-01")
        self.assertEqual(payload["windows"][0]["test_start"], "2024-01-25")
        self.assertEqual(payload["windows"][0]["test_end"], "2024-02-05")
        self.assertIn("mean_total_return_pct", payload["aggregate_metrics"])
        self.assertIn("worst_max_drawdown_pct", payload["aggregate_metrics"])
        self.assertTrue(all(item["state"] == "completed" for item in payload["windows"]))

    def test_build_monte_carlo_analysis_runs_multiple_simulations_and_reports_distribution(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service._dict_to_parsed_strategy(
            service.parse_strategy(
                "Buy when Close > MA3. Sell when Close < MA3.",
                code="TEST",
                start_date="2024-01-01",
                end_date="2024-05-31",
                initial_capital=100000.0,
            ),
            "Buy when Close > MA3. Sell when Close < MA3.",
        )
        bars = self._make_bars(
            [100.0 + (index * 0.4) + ((-1) ** index) * 0.9 for index in range(80)],
            start=date(2024, 1, 1),
        )

        payload = service._build_monte_carlo_analysis(
            code="TEST",
            parsed=parsed,
            bars=bars,
            initial_capital=100000.0,
            fee_bps=0.0,
            slippage_bps=0.0,
            lookback_bars=20,
            benchmark_mode="auto",
            benchmark_code=None,
            start_date=None,
            end_date=None,
            simulation_count=8,
            noise_scale=0.75,
            seed=20260423,
        )

        self.assertEqual(payload["state"], "available")
        self.assertEqual(payload["simulation_count"], 8)
        self.assertEqual(len(payload["paths"]), 8)
        self.assertEqual(payload["paths"][0]["simulation_index"], 1)
        self.assertIn("total_return_pct", payload["paths"][0]["metrics"])
        self.assertIn("p05_total_return_pct", payload["aggregate_metrics"])
        self.assertIn("p95_total_return_pct", payload["aggregate_metrics"])
        self.assertLessEqual(
            payload["aggregate_metrics"]["p05_total_return_pct"],
            payload["aggregate_metrics"]["p95_total_return_pct"],
        )

    def test_build_robustness_analysis_preserves_default_monte_carlo_configuration_when_omitted(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service._dict_to_parsed_strategy(
            service.parse_strategy(
                "Buy when Close > MA3. Sell when Close < MA3.",
                code="TEST",
                start_date="2024-01-01",
                end_date="2024-05-31",
                initial_capital=100000.0,
            ),
            "Buy when Close > MA3. Sell when Close < MA3.",
        )
        bars = self._make_bars(
            [100.0 + (index * 0.45) + ((-1) ** index) * 0.8 for index in range(80)],
            start=date(2024, 1, 1),
        )

        payload = service._build_robustness_analysis(
            code="TEST",
            parsed=parsed,
            bars=bars,
            initial_capital=100000.0,
            fee_bps=0.0,
            slippage_bps=0.0,
            lookback_bars=20,
            benchmark_mode="auto",
            benchmark_code=None,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 5, 31),
        )

        self.assertEqual(
            payload["configuration"]["walk_forward"],
            {
                "train_window": 24,
                "test_window": 12,
                "step": 12,
                "max_windows": 4,
            },
        )
        self.assertEqual(payload["configuration"]["monte_carlo"]["simulation_count"], 12)
        self.assertEqual(payload["configuration"]["monte_carlo"]["noise_scale"], 0.75)
        self.assertIsNone(payload["configuration"]["monte_carlo"]["seed"])
        self.assertEqual(
            payload["configuration"]["stress_tests"]["scenario_keys"],
            ["single_day_shock_down_15", "volatility_whipsaw"],
        )
        self.assertGreater(payload["walk_forward"]["window_count"], 0)
        self.assertEqual(payload["monte_carlo"]["simulation_count"], 12)
        self.assertEqual(
            payload["seed"],
            service._build_robustness_seed(
                code="TEST",
                parsed=parsed,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 5, 31),
                lookback_bars=20,
                initial_capital=100000.0,
            ),
        )
        self._assert_robustness_payload_avoids_optimizer_semantics(payload)

    def test_build_robustness_analysis_exposes_diagnostic_only_contract_metadata(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service._dict_to_parsed_strategy(
            service.parse_strategy(
                "Buy when Close > MA3. Sell when Close < MA3.",
                code="TEST",
                start_date="2024-01-01",
                end_date="2024-05-31",
                initial_capital=100000.0,
            ),
            "Buy when Close > MA3. Sell when Close < MA3.",
        )
        bars = self._make_bars(
            [100.0 + (index * 0.45) + ((-1) ** index) * 0.8 for index in range(80)],
            start=date(2024, 1, 1),
        )

        payload = service._build_robustness_analysis(
            code="TEST",
            parsed=parsed,
            bars=bars,
            initial_capital=100000.0,
            fee_bps=0.0,
            slippage_bps=0.0,
            lookback_bars=20,
            benchmark_mode="auto",
            benchmark_code=None,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 5, 31),
        )

        self._assert_robustness_payload_stays_diagnostic_only(payload)

    def test_run_backtest_persists_custom_monte_carlo_robustness_config(self) -> None:
        service = RuleBacktestService(self.db)
        self._seed_history(
            "AAPL",
            [100.0 + (index * 0.35) + ((-1) ** index) * 1.0 for index in range(96)],
            start=date(2024, 1, 1),
        )

        with patch.object(service, "_ensure_market_history", return_value=0), patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.run_backtest(
                code="AAPL",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
                robustness_config={
                    "walk_forward": {
                        "train_window": 36,
                        "test_window": 18,
                        "step": 9,
                        "max_windows": 3,
                    },
                    "monte_carlo": {
                        "simulation_count": 8,
                        "seed": 4242,
                        "noise_scale": 0.5,
                    }
                },
            )

        detail = service.get_run(response["id"])
        history = service.list_runs(code="AAPL", page=1, limit=10)

        self.assertEqual(response["robustness_analysis"]["seed"], 4242)
        self.assertEqual(response["robustness_analysis"]["monte_carlo"]["simulation_count"], 8)
        self.assertEqual(
            response["robustness_analysis"]["configuration"]["walk_forward"],
            {
                "train_window": 36,
                "test_window": 18,
                "step": 9,
                "max_windows": 3,
            },
        )
        self.assertEqual(
            response["robustness_analysis"]["configuration"]["monte_carlo"],
            {"simulation_count": 8, "seed": 4242, "noise_scale": 0.5},
        )
        self.assertEqual(
            detail["summary"]["request"]["robustness_config"]["walk_forward"],
            {
                "train_window": 36,
                "test_window": 18,
                "step": 9,
                "max_windows": 3,
            },
        )
        self.assertEqual(
            detail["summary"]["request"]["robustness_config"]["monte_carlo"],
            {"simulation_count": 8, "seed": 4242, "noise_scale": 0.5},
        )
        self.assertEqual(
            detail["robustness_analysis"]["configuration"]["walk_forward"],
            {
                "train_window": 36,
                "test_window": 18,
                "step": 9,
                "max_windows": 3,
            },
        )
        self.assertEqual(
            detail["robustness_analysis"]["configuration"]["monte_carlo"],
            {"simulation_count": 8, "seed": 4242, "noise_scale": 0.5},
        )
        self.assertEqual(
            history["items"][0]["summary"]["request"]["robustness_config"]["walk_forward"],
            {
                "train_window": 36,
                "test_window": 18,
                "step": 9,
                "max_windows": 3,
            },
        )
        self.assertEqual(
            history["items"][0]["summary"]["request"]["robustness_config"]["monte_carlo"],
            {"simulation_count": 8, "seed": 4242, "noise_scale": 0.5},
        )

    def test_run_backtest_rejects_out_of_bounds_monte_carlo_simulation_count(self) -> None:
        service = RuleBacktestService(self.db)

        with self.assertRaisesRegex(
            ValueError,
            "robustness_config\\.monte_carlo\\.simulation_count",
        ):
            service.run_backtest(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                confirmed=True,
                robustness_config={
                    "monte_carlo": {
                        "simulation_count": 0,
                    }
                },
            )

    def test_run_backtest_rejects_out_of_bounds_walk_forward_train_window(self) -> None:
        service = RuleBacktestService(self.db)

        with self.assertRaisesRegex(
            ValueError,
            "robustness_config\\.walk_forward\\.train_window",
        ):
            service.run_backtest(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                confirmed=True,
                robustness_config={
                    "walk_forward": {
                        "train_window": 3,
                    }
                },
            )

    def test_build_stress_test_analysis_reports_worst_scenario_metrics(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service._dict_to_parsed_strategy(
            service.parse_strategy(
                "Buy when Close > MA3. Sell when Close < MA3.",
                code="TEST",
                start_date="2024-01-01",
                end_date="2024-05-31",
                initial_capital=100000.0,
            ),
            "Buy when Close > MA3. Sell when Close < MA3.",
        )
        bars = self._make_bars(
            [100.0 + (index * 0.5) + ((-1) ** index) * 0.75 for index in range(80)],
            start=date(2024, 1, 1),
        )

        payload = service._build_stress_test_analysis(
            code="TEST",
            parsed=parsed,
            bars=bars,
            initial_capital=100000.0,
            fee_bps=0.0,
            slippage_bps=0.0,
            lookback_bars=20,
            benchmark_mode="auto",
            benchmark_code=None,
            start_date=None,
            end_date=None,
        )

        self.assertEqual(payload["state"], "available")
        self.assertEqual(len(payload["scenarios"]), 2)
        self.assertEqual(payload["scenarios"][0]["scenario_key"], "single_day_shock_down_15")
        self.assertIn("max_drawdown_pct", payload["scenarios"][0]["metrics"])
        self.assertEqual(payload["worst_scenario"]["scenario_key"], "single_day_shock_down_15")

    def test_service_persists_robustness_analysis_through_run_detail_and_history(self) -> None:
        service = RuleBacktestService(self.db)
        self._seed_history(
            "000001",
            [100.0 + (index * 0.3) + ((-1) ** index) * 1.1 for index in range(96)],
            start=date(2024, 1, 1),
        )

        with patch.object(service, "_ensure_market_history", return_value=0), patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.run_backtest(
                code="000001",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )

        detail = service.get_run(response["id"])
        history = service.list_runs(code="000001", page=1, limit=10)

        self.assertIn("robustness_analysis", response)
        self.assertEqual(response["robustness_analysis"]["state"], "available")
        self.assertGreater(response["robustness_analysis"]["walk_forward"]["window_count"], 0)
        self.assertEqual(detail["robustness_analysis"]["state"], "available")
        self.assertEqual(history["items"][0]["robustness_analysis"]["state"], "available")
        self.assertEqual(detail["summary"]["robustness_analysis"], detail["robustness_analysis"])
        self._assert_robustness_payload_stays_diagnostic_only(response["robustness_analysis"])
        self._assert_robustness_payload_stays_diagnostic_only(detail["robustness_analysis"])
        self._assert_robustness_payload_stays_diagnostic_only(history["items"][0]["robustness_analysis"])

    def test_professional_readiness_requires_lineage_cost_fill_and_corporate_action_evidence(self) -> None:
        readiness = build_backtest_professional_readiness(
            data_quality={
                "authority_status": "allowed",
                "authority_source_type": "cache_snapshot",
                "authority_reason_codes": [],
                "adjustment_mode": "adjusted_ohlc",
                "return_basis": "adjusted_total_return",
                "dividends_handled": "handled",
                "splits_handled": "unknown",
            },
            execution_assumptions={
                "trading_calendar": "XNYS",
                "holiday_calendar": "modeled",
                "half_day_policy": "modeled",
                "volume_participation_limit": None,
                "partial_fill_supported": False,
                "no_fill_supported": True,
                "limit_up_down_handling": "modeled",
                "halt_handling": "modeled",
                "fee_model": {"commission_bps": 2.5},
                "slippage_model": {"slippage_bps": 1.25},
            },
            cost_capacity_diagnostics={"assumptions": {"spread_bps": 0.0, "minimum_fee": 0.0}},
            result_authority={
                "domains": {
                    "execution_assumptions_snapshot": {
                        "completeness": "complete",
                    }
                }
            },
            dataset_version="unknown",
        ).to_dict()

        self.assertFalse(readiness["professional_quant_ready"])
        self.assertEqual(readiness["overall_state"], "research_prototype")
        self.assertIn("split_policy_unverified", readiness["categories"]["corporate_actions"]["blockers"])
        self.assertIn("partial_fill_model_missing", readiness["categories"]["fill_model"]["blockers"])
        self.assertIn("liquidity_constraints_not_modelled", readiness["categories"]["fill_model"]["blockers"])
        self.assertIn("tax_model_missing", readiness["categories"]["cost_model"]["blockers"])
        self.assertIn("market_impact_model_missing", readiness["categories"]["cost_model"]["blockers"])
        self.assertIn("dataset_version_unknown", readiness["categories"]["reproducibility"]["blockers"])

    def test_professional_readiness_treats_unknown_authority_as_reproducibility_blocker(self) -> None:
        readiness = build_backtest_professional_readiness(
            data_quality={
                "authority_status": "unknown",
                "authority_reason_codes": ["source_authority_unknown"],
                "adjustment_mode": "adjusted_ohlc",
                "return_basis": "adjusted_total_return",
                "dividends_handled": "handled",
                "splits_handled": "handled",
            },
            execution_assumptions={
                "trading_calendar": "XNYS",
                "holiday_calendar": "modeled",
                "half_day_policy": "modeled",
                "volume_participation_limit": 0.1,
                "partial_fill_supported": True,
                "no_fill_supported": True,
                "limit_up_down_handling": "modeled",
                "halt_handling": "modeled",
                "fee_model": {"commission_bps": 2.5},
                "slippage_model": {"slippage_bps": 1.25},
            },
            cost_capacity_diagnostics={
                "assumptions": {
                    "spread_bps": 0.5,
                    "minimum_fee": 1.0,
                    "tax_model": "modeled",
                    "market_impact_model": "modeled",
                }
            },
            result_authority={
                "domains": {
                    "execution_assumptions_snapshot": {
                        "completeness": "complete",
                    }
                },
                "reproducibility_ready": True,
            },
            dataset_version="fixture-v1",
        ).to_dict()

        self.assertFalse(readiness["professional_reproducibility_ready"])
        self.assertEqual(readiness["reproducibility_state"], "blocked_source_authority")
        self.assertIn(
            "source_authority_unknown",
            readiness["categories"]["reproducibility"]["blockers"],
        )

    def test_universe_jobs_remain_local_only_and_execute_symbols_in_sequence(self) -> None:
        service = RuleBacktestService(self.db)
        self._seed_history(
            "AAPL",
            [100.0 + (index * 0.2) for index in range(80)],
            start=date(2024, 1, 1),
        )
        self._seed_history(
            "MSFT",
            [200.0 + (index * 0.15) for index in range(80)],
            start=date(2024, 1, 1),
        )

        created = service.create_universe_job(
            symbols=["MSFT", "AAPL", "MSFT"],
            strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
            start_date="2024-01-01",
            end_date="2024-02-29",
            lookback_bars=20,
        )

        self.assertTrue(created["local_data_only"])
        self.assertEqual(created["execution_mode"], "preflight_only")
        self.assertEqual(created["symbol_count"], 2)
        self.assertEqual(created["completed_count"], 2)
        self.assertEqual(created["skipped_count"], 0)
        self.assertEqual(created["professionalReadiness"]["overall_state"], "research_prototype")

        stored_rows = service.repo.get_universe_symbol_results(int(created["id"]))
        self.assertEqual([row.symbol for row in stored_rows], ["AAPL", "MSFT"])
        self.assertEqual([int(row.sequence_index) for row in stored_rows], [0, 1])
        self.assertTrue(all(str(row.status) == "ready_local_data" for row in stored_rows))

        executed_codes: list[str] = []

        def _fake_engine_run(**kwargs: object) -> SimpleNamespace:
            code = str(kwargs["code"])
            executed_codes.append(code)
            return SimpleNamespace(
                metrics={
                    "trade_count": 1,
                    "total_return_pct": 1.5 if code == "AAPL" else 2.5,
                    "max_drawdown_pct": -0.8 if code == "AAPL" else -1.1,
                    "win_rate_pct": 100.0,
                    "final_equity": 101500.0 if code == "AAPL" else 102500.0,
                },
                no_result_reason=None,
            )

        with patch.object(service.engine, "run", side_effect=_fake_engine_run) as engine_run:
            finished = service.run_universe_job_sequential(int(created["id"]))

        self.assertEqual(executed_codes, ["AAPL", "MSFT"])
        self.assertEqual(engine_run.call_count, 2)
        service._ensure_market_history.assert_not_called()
        self.assertEqual(finished["execution_mode"], "sequential_local")
        self.assertEqual(finished["status"], "completed")
        self.assertEqual(finished["completed_count"], 2)
        self.assertEqual(finished["failed_count"], 0)
        self.assertEqual(finished["skipped_count"], 0)

        result_payload = service.list_universe_job_results(int(created["id"]), page=1, limit=10)
        self.assertEqual([item["symbol"] for item in result_payload["items"]], ["AAPL", "MSFT"])
        self.assertEqual([item["sequence_index"] for item in result_payload["items"]], [0, 1])
        self.assertEqual([item["status"] for item in result_payload["items"]], ["completed", "completed"])
        self.assertEqual(result_payload["items"][0]["total_return_pct"], 1.5)
        self.assertEqual(result_payload["items"][1]["total_return_pct"], 2.5)

    def test_build_drawdown_regime_attribution_payload_available_from_stored_audit_rows(self) -> None:
        service = RuleBacktestService(self.db)

        payload = service._build_drawdown_regime_attribution_payload(
            [
                {"date": "2024-01-01", "drawdown_pct": 0},
                {"date": "2024-01-02", "drawdown_pct": -4.2},
                {"date": "2024-01-03", "drawdown_pct": "-8.5"},
                {"date": "2024-01-04", "drawdown_pct": -12.0},
                {"date": "2024-01-05", "drawdown_pct": -24.0},
            ],
            source="summary.visualization.audit_rows",
        )

        self.assertEqual(payload["version"], "v1")
        self.assertEqual(payload["source"], "summary.visualization.audit_rows")
        self.assertEqual(payload["state"], "available")
        self.assertEqual(payload["bucket_counts"]["peak"]["count"], 1)
        self.assertEqual(payload["bucket_counts"]["shallow"]["worst_depth_pct"], 4.2)
        self.assertEqual(payload["bucket_counts"]["moderate"]["avg_depth_pct"], 8.5)
        self.assertEqual(payload["bucket_counts"]["deep"]["count"], 1)
        self.assertEqual(payload["bucket_counts"]["severe"]["count"], 1)
        self.assertEqual(payload["bucket_counts"]["unknown"]["count"], 0)
        self.assertEqual(payload["contribution_summaries"]["classified_rows"]["share_pct"], 100.0)
        self.assertEqual(payload["contribution_summaries"]["missing_rows"]["share_pct"], 0.0)
        self.assertIsNone(payload["unavailable_reason"])

    def test_build_drawdown_regime_attribution_payload_partial_when_audit_rows_are_missing_drawdown(self) -> None:
        service = RuleBacktestService(self.db)

        payload = service._build_drawdown_regime_attribution_payload(
            [
                {"date": "2024-01-01", "drawdown_pct": 0},
                {"date": "2024-01-02", "drawdown_pct": -6.25},
                {"date": "2024-01-03", "drawdown_pct": None},
                {"date": "2024-01-04", "drawdown_pct": "bad-data"},
            ],
            source="summary.visualization.audit_rows",
        )

        self.assertEqual(payload["source"], "summary.visualization.audit_rows")
        self.assertEqual(payload["state"], "partial")
        self.assertEqual(payload["bucket_counts"]["peak"]["count"], 1)
        self.assertEqual(payload["bucket_counts"]["moderate"]["count"], 1)
        self.assertEqual(payload["bucket_counts"]["unknown"]["count"], 2)
        self.assertEqual(payload["bucket_counts"]["unknown"]["share_pct"], 50.0)
        self.assertEqual(payload["contribution_summaries"]["classified_rows"]["count"], 2)
        self.assertEqual(payload["contribution_summaries"]["missing_rows"]["count"], 2)
        self.assertIsNone(payload["unavailable_reason"])

    def test_build_drawdown_regime_attribution_payload_unavailable_without_stored_audit_rows(self) -> None:
        service = RuleBacktestService(self.db)

        payload = service._build_drawdown_regime_attribution_payload(
            [],
            source="summary.visualization.audit_rows",
        )

        self.assertEqual(payload["source"], "unavailable")
        self.assertEqual(payload["state"], "unavailable")
        self.assertEqual(payload["unavailable_reason"], "stored_audit_rows_missing")
        self.assertEqual(payload["bucket_counts"]["peak"]["count"], 0)
        self.assertEqual(payload["bucket_counts"]["unknown"]["count"], 0)
        self.assertEqual(payload["contribution_summaries"]["classified_rows"]["count"], 0)
        self.assertEqual(payload["contribution_summaries"]["missing_rows"]["count"], 0)

    def test_service_readback_keeps_stored_drawdown_regime_attribution_payload(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )

        stored_payload = service._build_drawdown_regime_attribution_payload(
            [{"date": "2024-01-01", "drawdown_pct": -3.5}],
            source="summary.drawdown_regime_attribution",
        )
        stored_payload["contribution_summaries"]["causality_note"] = "stored payload sentinel"

        with self.db.get_session() as session:
            row = session.execute(select(RuleBacktestRun).where(RuleBacktestRun.id == response["id"])).scalar_one()
            summary = json.loads(row.summary_json or "{}")
            summary["drawdown_regime_attribution"] = stored_payload
            row.summary_json = json.dumps(summary, ensure_ascii=False)
            session.commit()

        detail = service.get_run(response["id"])

        self.assertIn("drawdown_regime_attribution", response["summary"])
        self.assertEqual(detail["summary"]["drawdown_regime_attribution"], stored_payload)

    def test_auto_benchmark_falls_back_to_same_symbol_when_external_series_unavailable(self) -> None:
        service = RuleBacktestService(self.db)
        parser = RuleBacktestParser()
        parsed = parser.parse("Buy when Close > MA3. Sell when Close < MA3.")
        engine = RuleBacktestEngine()

        with self.db.get_session() as session:
            bars = session.query(StockDaily).filter(StockDaily.code == "600519").order_by(StockDaily.date).all()

        result = engine.run(
            code="600519",
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=100000.0,
            fee_bps=0.0,
            lookback_bars=20,
        )

        with patch.object(
            service,
            "_load_external_benchmark_context",
            return_value=([], {"label": "沪深300", "resolved_mode": "index_hs300", "return_pct": None}, "沪深300 在当前窗口没有可用行情。"),
        ):
            service._apply_benchmark_context(
                result,
                instrument_code="600519",
                benchmark_mode="auto",
                benchmark_code=None,
                start_date=None,
                end_date=None,
            )

        self.assertEqual(result.benchmark_summary["requested_mode"], "auto")
        self.assertEqual(result.benchmark_summary["resolved_mode"], "same_symbol_buy_and_hold")
        self.assertTrue(result.benchmark_summary["auto_resolved"])
        self.assertTrue(result.benchmark_summary["fallback_used"])
        self.assertIn("沪深300", result.benchmark_summary["unavailable_reason"])
        self.assertGreater(len(result.benchmark_curve), 0)
        self.assertEqual(result.metrics["benchmark_return_pct"], result.metrics["buy_and_hold_return_pct"])

    def test_service_persists_canonical_benchmark_comparison_payload(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )

        comparison = response["summary"]["visualization"].get("comparison") or {}
        self.assertEqual(comparison.get("version"), "v1")
        self.assertEqual(comparison.get("source"), response["result_authority"]["comparison_source"])
        self.assertEqual(comparison.get("benchmark_summary"), response["benchmark_summary"])
        self.assertEqual(comparison.get("buy_and_hold_summary"), response["buy_and_hold_summary"])
        self.assertEqual(comparison.get("benchmark_curve"), response["benchmark_curve"])
        self.assertEqual(comparison.get("buy_and_hold_curve"), response["buy_and_hold_curve"])
        self.assertEqual(comparison.get("metrics", {}).get("benchmark_return_pct"), response["benchmark_return_pct"])
        self.assertEqual(comparison.get("metrics", {}).get("buy_and_hold_return_pct"), response["buy_and_hold_return_pct"])

    def test_service_exports_execution_trace_csv_and_json_from_stored_result(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )

        self.assertIn("execution_trace", response)
        self.assertGreater(len(response["execution_trace"]["rows"]), 0)
        self.assertTrue(response["execution_trace"]["assumptions_defaults"]["summary_text"])

        csv_path = os.path.join(self._temp_dir.name, "trace.csv")
        json_path = os.path.join(self._temp_dir.name, "trace.json")
        service.export_execution_trace_csv(run_id=response["id"], output_path=csv_path)
        service.export_execution_trace_json(run_id=response["id"], output_path=json_path)

        with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertGreater(len(rows), 0)
        self.assertEqual(
            list(rows[0].keys()),
            [
                "日期",
                "标的收盘价",
                "基准收盘价",
                "信号摘要",
                "动作",
                "成交价",
                "持股数",
                "现金",
                "持仓市值",
                "总资产",
                "当日盈亏",
                "当日收益率",
                "策略累计收益率",
                "基准累计收益率",
                "买入持有累计收益率",
                "仓位",
                "手续费",
                "滑点",
                "备注",
                "assumptions",
                "fallback",
            ],
        )
        self.assertIn("fallback", rows[0])
        self.assertIn("assumptions", rows[0])
        self.assertIn("仓位", rows[0])
        self.assertIn("现金", rows[0])
        self.assertIn("总资产", rows[0])
        self.assertTrue(any((row.get("动作") or "") in {"买", "卖"} for row in rows))
        self.assertTrue(all((row.get("fallback") or "") for row in rows))

        csv_text = service.get_execution_trace_export_csv_text(run_id=response["id"])
        self.assertIn("日期,标的收盘价,基准收盘价", csv_text)
        self.assertIn("fallback", csv_text)
        self._assert_public_backtest_text_is_analytical(csv_text)

        payload = service.get_execution_trace_export_json(run_id=response["id"])
        self.assertEqual(payload["source"], response["execution_trace"]["source"])
        self.assertGreater(len(payload["trace_rows"]), 0)
        self.assertEqual(payload["assumptions"]["summary_text"], response["execution_trace"]["assumptions_defaults"]["summary_text"])
        self.assertEqual(payload["benchmark_summary"], response["benchmark_summary"])
        self._assert_public_backtest_text_is_analytical(json.dumps(payload, ensure_ascii=False, sort_keys=True))

    def test_service_exports_support_bundle_manifest_json_from_stored_result(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )

        manifest_path = os.path.join(self._temp_dir.name, "support_bundle_manifest.json")
        service.export_support_bundle_manifest_json(run_id=response["id"], output_path=manifest_path)

        with open(manifest_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)

        self.assertEqual(payload["manifest_version"], "v1")
        self.assertEqual(payload["manifest_kind"], "rule_backtest_support_bundle")
        self.assertEqual(payload["run"]["id"], response["id"])
        self.assertEqual(payload["run"]["code"], response["code"])
        self.assertEqual(payload["run"]["status"], response["status"])
        self.assertEqual(payload["run"]["strategy_hash"], response["strategy_hash"])
        self.assertEqual(payload["run_timing"], response["run_timing"])
        self.assertEqual(payload["run_diagnostics"], response["run_diagnostics"])
        self.assertEqual(payload["artifact_availability"], response["artifact_availability"])
        self.assertEqual(payload["readback_integrity"], response["readback_integrity"])
        self.assertEqual(
            payload["result_authority"],
            {
                "contract_version": response["result_authority"]["contract_version"],
                "read_mode": response["result_authority"]["read_mode"],
                "domains": response["result_authority"]["domains"],
            },
        )
        self.assertEqual(payload["artifact_counts"]["trade_rows_count"], len(response["trades"]))
        self.assertEqual(payload["artifact_counts"]["equity_curve_points"], len(response["equity_curve"]))
        self.assertEqual(payload["artifact_counts"]["audit_rows_count"], len(response["audit_rows"]))
        self.assertEqual(
            payload["artifact_counts"]["execution_trace_rows_count"],
            len(response["execution_trace"]["rows"]),
        )
        self.assertNotIn("trades", payload)
        self.assertNotIn("equity_curve", payload)
        self.assertNotIn("audit_rows", payload)
        self.assertNotIn("execution_trace", payload)
        self._assert_public_backtest_text_is_analytical(json.dumps(payload, ensure_ascii=False, sort_keys=True))

    def test_service_builds_support_bundle_reproducibility_manifest_from_stored_result(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )

        payload = service.get_support_bundle_reproducibility_manifest(response["id"])

        self.assertEqual(payload["manifest_version"], "v1")
        self.assertEqual(payload["manifest_kind"], "rule_backtest_reproducibility_manifest")
        self.assertEqual(payload["run"]["id"], response["id"])
        self.assertEqual(payload["run"]["strategy_hash"], response["strategy_hash"])
        self.assertEqual(payload["run_diagnostics"], response["run_diagnostics"])
        self.assertEqual(payload["run_timing"], response["run_timing"])
        self.assertEqual(payload["artifact_availability"], response["artifact_availability"])
        self.assertEqual(payload["readback_integrity"], response["readback_integrity"])
        self.assertEqual(
            payload["execution_assumptions_fingerprint"]["source"],
            response["execution_assumptions_snapshot"]["source"],
        )
        self.assertEqual(
            payload["execution_assumptions_fingerprint"]["completeness"],
            response["execution_assumptions_snapshot"]["completeness"],
        )
        self.assertTrue(payload["execution_assumptions_fingerprint"]["hash_sha256"])
        self.assertEqual(
            payload["result_authority"]["domains"]["execution_trace"],
            {
                "source": response["result_authority"]["domains"]["execution_trace"]["source"],
                "completeness": response["result_authority"]["domains"]["execution_trace"]["completeness"],
                "state": response["result_authority"]["domains"]["execution_trace"]["state"],
            },
        )
        self.assertNotIn("trades", payload)
        self.assertNotIn("equity_curve", payload)
        self.assertNotIn("audit_rows", payload)
        self.assertNotIn("execution_trace", payload)
        self._assert_public_backtest_text_is_analytical(json.dumps(payload, ensure_ascii=False, sort_keys=True))

    def test_service_support_export_index_reports_manifest_and_execution_trace_exports(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )

        export_index = service.get_support_export_index(response["id"])
        self.assertEqual(export_index["run_id"], response["id"])
        self.assertEqual(export_index["status"], response["status"])
        self.assertEqual(
            [item["key"] for item in export_index["exports"]],
            [
                "support_bundle_manifest_json",
                "support_bundle_reproducibility_manifest_json",
                "execution_trace_json",
                "execution_trace_csv",
                "robustness_evidence_json",
            ],
        )
        manifest_item = export_index["exports"][0]
        self.assertTrue(manifest_item["available"])
        self.assertEqual(manifest_item["delivery_mode"], "api")
        self.assertEqual(
            manifest_item["endpoint_path"],
            f"/api/v1/backtest/rule/runs/{response['id']}/support-bundle-manifest",
        )
        self.assertEqual(manifest_item["payload_class"], "compact")
        reproducibility_item = export_index["exports"][1]
        self.assertTrue(reproducibility_item["available"])
        self.assertEqual(reproducibility_item["delivery_mode"], "api")
        self.assertEqual(
            reproducibility_item["endpoint_path"],
            f"/api/v1/backtest/rule/runs/{response['id']}/support-bundle-reproducibility-manifest",
        )
        self.assertEqual(reproducibility_item["payload_class"], "compact")
        for item in export_index["exports"][2:4]:
            self.assertTrue(item["available"])
            self.assertEqual(item["availability_reason"], "execution_trace_rows_present")
            self.assertEqual(item["payload_class"], "heavy")
        self.assertEqual(export_index["exports"][2]["delivery_mode"], "api")
        self.assertEqual(
            export_index["exports"][2]["endpoint_path"],
            f"/api/v1/backtest/rule/runs/{response['id']}/execution-trace.json",
        )
        self.assertEqual(export_index["exports"][3]["delivery_mode"], "api")
        self.assertEqual(
            export_index["exports"][3]["endpoint_path"],
            f"/api/v1/backtest/rule/runs/{response['id']}/execution-trace.csv",
        )
        robustness_item = export_index["exports"][4]
        self.assertTrue(robustness_item["available"])
        self.assertEqual(robustness_item["availability_reason"], "stored_robustness_analysis_present")
        self.assertEqual(robustness_item["delivery_mode"], "api")
        self.assertEqual(
            robustness_item["endpoint_path"],
            f"/api/v1/backtest/rule/runs/{response['id']}/robustness-evidence.json",
        )
        self.assertEqual(robustness_item["payload_class"], "heavy")
        self._assert_public_backtest_text_is_analytical(json.dumps(export_index, ensure_ascii=False, sort_keys=True))

    def test_support_export_helpers_project_materialized_run_payloads_purely(self) -> None:
        trace_export_columns = [
            ("date", "日期"),
            ("symbol_close", "标的收盘价"),
            ("benchmark_close", "基准收盘价"),
            ("signal_summary", "信号摘要"),
            ("action_display", "动作"),
            ("fill_price", "成交价"),
            ("shares", "持股数"),
            ("cash", "现金"),
            ("holdings_value", "持仓市值"),
            ("total_portfolio_value", "总资产"),
            ("daily_pnl", "当日盈亏"),
            ("daily_return", "当日收益率"),
            ("cumulative_return", "策略累计收益率"),
            ("benchmark_cumulative_return", "基准累计收益率"),
            ("buy_hold_cumulative_return", "买入持有累计收益率"),
            ("position", "仓位"),
            ("fees", "手续费"),
            ("slippage", "滑点"),
            ("notes", "备注"),
            ("assumptions_defaults", "assumptions"),
            ("fallback", "fallback"),
        ]
        run = {
            "id": 321,
            "code": "600519",
            "status": "completed",
            "status_message": "done",
            "run_at": "2024-01-01T00:00:00",
            "completed_at": "2024-01-01T00:05:00",
            "strategy_hash": "hash321",
            "timeframe": "daily",
            "lookback_bars": 20,
            "period_start": "2024-01-01",
            "period_end": "2024-01-31",
            "benchmark_mode": "auto",
            "benchmark_code": None,
            "trade_count": 1,
            "total_return_pct": 1.2,
            "sharpe_ratio": 0.8,
            "max_drawdown_pct": 0.3,
            "final_equity": 101200.0,
            "no_result_reason": None,
            "no_result_message": None,
            "run_timing": {"finished_at": "2024-01-01T00:05:00"},
            "run_diagnostics": {"current_status": "completed"},
            "artifact_availability": {"has_execution_trace": True},
            "readback_integrity": {"integrity_level": "stored_complete"},
            "result_authority": {
                "contract_version": "v1",
                "read_mode": "stored_first",
                "domains": {
                    "execution_trace": {
                        "source": "summary.execution_trace",
                        "completeness": "complete",
                        "state": "available",
                        "missing": [],
                        "missing_kind": "fields",
                    },
                    "execution_assumptions_snapshot": {
                        "source": "summary.execution_assumptions_snapshot",
                        "completeness": "complete",
                        "state": "available",
                    },
                },
            },
            "status_history": [{"status": "completed"}],
            "warnings": [],
            "trades": [{"id": 1}],
            "equity_curve": [{"date": "2024-01-01"}],
            "audit_rows": [{"date": "2024-01-01"}],
            "daily_return_series": [{"date": "2024-01-01"}],
            "exposure_curve": [{"date": "2024-01-01"}],
            "execution_trace": {
                "version": "v1",
                "source": "summary.execution_trace",
                "completeness": "complete",
                "missing_fields": [],
                "assumptions_defaults": {"summary_text": "baseline"},
                "execution_model": {"fill_model": "next_open"},
                "execution_assumptions": {"summary_text": "baseline"},
                "fallback": {"trace_rebuilt": False},
                "rows": [
                    {
                        "date": "2024-01-02",
                        "symbol_close": 10.5,
                        "benchmark_close": 9.8,
                        "signal_summary": "ma cross",
                        "event_type": "action",
                        "action": "buy",
                        "action_display": "买",
                        "fill_price": 10.6,
                        "shares": 100,
                        "cash": 8940,
                        "holdings_value": 1060,
                        "total_portfolio_value": 10000,
                        "daily_pnl": 0,
                        "daily_return": 0,
                        "cumulative_return": 0,
                        "benchmark_cumulative_return": 0,
                        "buy_hold_cumulative_return": 0,
                        "position": 1,
                        "fees": 0,
                        "slippage": 0,
                        "notes": "",
                        "assumptions_defaults": "baseline",
                        "fallback": "none",
                    }
                ],
            },
            "execution_assumptions_snapshot": {
                "source": "summary.execution_assumptions_snapshot",
                "completeness": "complete",
                "payload": {"summary_text": "baseline", "fill_model": "next_open"},
            },
            "execution_assumptions": {"summary_text": "baseline", "fill_model": "next_open"},
            "benchmark_summary": {"requested_mode": "auto"},
            "summary": {"robustness_analysis": {"state": "research_prototype", "seed": 7}},
            "robustness_analysis": {"state": "research_prototype", "seed": 99},
        }

        authority = build_reproducibility_authority_summary(run["result_authority"])
        fingerprint = build_execution_assumptions_fingerprint(
            run["execution_assumptions_snapshot"],
            run["execution_assumptions"],
        )
        manifest = build_support_bundle_manifest(run)
        export_index = build_support_export_index(run)
        trace_json = build_execution_trace_export_json_payload(
            run,
            trace_export_columns,
            action_formatter=lambda action: {"buy": "买"}.get(action, action),
        )
        trace_csv = build_execution_trace_export_csv_text(
            run,
            trace_export_columns,
            action_formatter=lambda action: {"buy": "买"}.get(action, action),
        )

        self.assertEqual(authority["domains"]["execution_trace"]["state"], "available")
        self.assertEqual(fingerprint["source"], "summary.execution_assumptions_snapshot")
        self.assertTrue(fingerprint["hash_sha256"])
        self.assertEqual(manifest["artifact_counts"]["execution_trace_rows_count"], 1)
        self.assertEqual(export_index["run_id"], 321)
        self.assertTrue(export_index["exports"][2]["available"])
        self.assertEqual(export_index["exports"][4]["availability_reason"], "stored_robustness_analysis_present")
        self.assertEqual(trace_json["trace_rows"][0]["动作"], "买")
        self.assertEqual(trace_json["benchmark_summary"]["requested_mode"], "auto")
        self.assertEqual(trace_csv.splitlines()[0].split(","), EXPECTED_TRACE_EXPORT_FIELD_LABELS)

    def test_support_manifests_project_dataset_lineage_from_stored_quality(self) -> None:
        run = {
            "id": 654,
            "code": "AAPL",
            "status": "completed",
            "strategy_hash": "fixture",
            "timeframe": "daily",
            "lookback_bars": 20,
            "period_start": "2024-01-03",
            "period_end": "2024-01-19",
            "benchmark_mode": "same_symbol_buy_and_hold",
            "benchmark_code": "AAPL",
            "trade_count": 0,
            "run_timing": {},
            "run_diagnostics": {},
            "artifact_availability": {},
            "readback_integrity": {},
            "result_authority": {"contract_version": "v1", "read_mode": "stored_first", "domains": {}},
            "execution_assumptions_snapshot": {},
            "execution_assumptions": {},
            "status_history": [],
            "warnings": [],
            "trades": [],
            "equity_curve": [],
            "audit_rows": [],
            "daily_return_series": [],
            "exposure_curve": [],
            "execution_trace": {"rows": []},
            "data_quality": {
                "source": "local_us_parquet_dir",
                "provider": "Local US Parquet Directory",
                "authority_status": "allowed",
                "authority_source_type": "cache_snapshot",
                "authority_reason_codes": [],
                "requested_start": "2024-01-02",
                "requested_end": "2024-01-31",
                "actual_start": "2024-01-03",
                "actual_end": "2024-01-19",
                "bar_count": 12,
            },
            "professionalReadiness": {
                "reproducibility_state": "partial_without_dataset_lineage",
            },
        }

        manifest = build_support_bundle_manifest(run)
        reproducibility = build_support_bundle_reproducibility_manifest(run)

        expected_lineage = {
            "source": "local_us_parquet_dir",
            "provider": "Local US Parquet Directory",
            "authority_status": "allowed",
            "authority_source_type": "cache_snapshot",
            "authority_reason_codes": [],
            "authority_reason_families": [],
            "authority_allowed": True,
            "degraded_fill_only": False,
            "requested_range": {"start": "2024-01-02", "end": "2024-01-31"},
            "actual_range": {"start": "2024-01-03", "end": "2024-01-19"},
            "bar_count": 12,
            "dataset_version": "unknown",
        }
        self.assertEqual(manifest["dataset_lineage"], expected_lineage)
        self.assertEqual(reproducibility["dataset_lineage"], expected_lineage)
        self.assertNotIn("manifest_id", manifest["dataset_lineage"])
        self.assertNotIn("hash_sha256", manifest["dataset_lineage"])
        self.assertEqual(manifest["run"]["id"], 654)
        self.assertEqual(reproducibility["result_authority"]["read_mode"], "stored_first")

    def test_support_manifests_project_authority_reason_families_sidecar_from_raw_codes(self) -> None:
        run = {
            "id": 656,
            "code": "AAPL",
            "status": "completed",
            "data_quality": {
                "source": "local_us_parquet",
                "provider": "Local US Parquet",
                "authority_status": "rejected",
                "authority_source_type": "cache_snapshot",
                "authority_reason_codes": [
                    "provider_forbidden_for_use_case",
                    "totally_new_reason_code",
                ],
                "requested_start": "2024-01-02",
                "requested_end": "2024-01-31",
                "actual_start": "2024-01-03",
                "actual_end": "2024-01-19",
                "bar_count": 12,
            },
        }

        manifest = build_support_bundle_manifest(run)
        reproducibility = build_support_bundle_reproducibility_manifest(run)
        lineage = manifest["dataset_lineage"]

        self.assertEqual(
            lineage["authority_reason_codes"],
            ["provider_forbidden_for_use_case", "totally_new_reason_code"],
        )
        self.assertEqual(
            lineage["authority_reason_families"],
            [
                {
                    "raw_code": "provider_forbidden_for_use_case",
                    "family": "authority_rejected",
                    "scope": "backtest_authority",
                },
                {
                    "raw_code": "totally_new_reason_code",
                    "family": "unclassified",
                    "scope": None,
                },
            ],
        )
        self.assertEqual(reproducibility["dataset_lineage"], lineage)
        self.assertFalse(lineage["authority_allowed"])
        self.assertFalse(lineage["degraded_fill_only"])
        self.assertEqual(lineage["dataset_version"], "unknown")

    def test_support_manifests_project_unknown_authority_reason_family_without_rewriting_status(self) -> None:
        run = {
            "id": 657,
            "code": "AAPL",
            "status": "completed",
            "data_quality": {
                "source": "Unknown",
                "provider": "Unknown",
                "authority_status": "unknown",
                "authority_reason_codes": ["source_authority_unknown"],
                "requested_start": "2024-01-02",
                "requested_end": "2024-01-31",
                "actual_start": "2024-01-03",
                "actual_end": "2024-01-19",
                "bar_count": 12,
            },
        }

        manifest = build_support_bundle_manifest(run)
        reproducibility = build_support_bundle_reproducibility_manifest(run)
        lineage = manifest["dataset_lineage"]

        self.assertEqual(lineage["source"], "Unknown")
        self.assertEqual(lineage["authority_status"], "unknown")
        self.assertEqual(lineage["authority_reason_codes"], ["source_authority_unknown"])
        self.assertEqual(
            lineage["authority_reason_families"],
            [
                {
                    "raw_code": "source_authority_unknown",
                    "family": "reproducibility_degraded",
                    "scope": "backtest_authority",
                }
            ],
        )
        self.assertFalse(lineage["authority_allowed"])
        self.assertFalse(lineage["degraded_fill_only"])
        self.assertEqual(reproducibility["dataset_lineage"], lineage)

    def test_support_manifests_keep_authority_reason_fields_empty_when_missing(self) -> None:
        run = {
            "id": 655,
            "code": "AAPL",
            "status": "completed",
            "data_quality": {
                "source": "database_cache",
                "provider": "database_cache",
                "authority_status": "unknown",
                "requested_start": "2024-01-02",
                "requested_end": "2024-01-31",
                "actual_start": "2024-01-03",
                "actual_end": "2024-01-19",
                "bar_count": 12,
            },
        }

        manifest = build_support_bundle_manifest(run)
        lineage = manifest["dataset_lineage"]

        self.assertEqual(lineage["authority_status"], "unknown")
        self.assertEqual(lineage["authority_reason_codes"], [])
        self.assertEqual(lineage["authority_reason_families"], [])
        self.assertFalse(lineage["authority_allowed"])
        self.assertFalse(lineage["degraded_fill_only"])
        self.assertEqual(lineage["authority_source_type"], "unknown")
        self.assertEqual(lineage["dataset_version"], "unknown")

    def test_service_exports_stored_robustness_evidence_json(self) -> None:
        service = RuleBacktestService(self.db)
        self._seed_history(
            "000001",
            [100.0 + (index * 0.3) + ((-1) ** index) * 1.1 for index in range(96)],
            start=date(2024, 1, 1),
        )

        with patch.object(service, "_ensure_market_history", return_value=0), patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.run_backtest(
                code="000001",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                robustness_config={
                    "walk_forward": {
                        "train_window": 36,
                        "test_window": 18,
                        "step": 9,
                        "max_windows": 3,
                    },
                    "monte_carlo": {
                        "simulation_count": 16,
                        "seed": 4242,
                        "noise_scale": 0.5,
                    },
                },
                confirmed=True,
            )

        export_index = service.get_support_export_index(response["id"])
        robustness_item = export_index["exports"][4]
        payload = service.get_robustness_evidence_export_json(response["id"])

        self.assertTrue(robustness_item["available"])
        self.assertEqual(robustness_item["availability_reason"], "stored_robustness_analysis_present")
        self.assertEqual(payload["state"], response["robustness_analysis"]["state"])
        self.assertEqual(payload["configuration"], response["robustness_analysis"]["configuration"])
        self.assertEqual(payload["walk_forward"], response["robustness_analysis"]["walk_forward"])
        self.assertEqual(payload["seed"], 4242)
        self.assertEqual(payload["configuration"]["walk_forward"]["train_window"], 36)
        self.assertEqual(payload["configuration"]["monte_carlo"]["simulation_count"], 16)
        self.assertEqual(
            payload["walk_forward_oos_evidence"]["contract_kind"],
            "backtest_walk_forward_oos_diagnostic_evidence",
        )
        self.assertEqual(payload["walk_forward_oos_evidence"]["source_run_id"], response["id"])
        self.assertEqual(payload["walk_forward_oos_evidence"]["source"], "stored_robustness_analysis.walk_forward")
        self.assertEqual(payload["walk_forward_oos_evidence"]["read_mode"], "stored_first")
        self.assertEqual(
            payload["walk_forward_oos_evidence"]["authority"],
            {
                "input_mode": "stored_robustness_analysis_walk_forward",
                "adapter_execution_count": 0,
                "new_strategy_execution_count": 0,
                "provider_calls_executed": False,
                "engine_math_changed": False,
                "strategy_parameters_mutated": False,
                "optimizer_executed": False,
                "parameter_sweep_executed": False,
            },
        )
        self._assert_robustness_payload_avoids_optimizer_semantics(payload)
        self._assert_public_backtest_text_is_analytical(json.dumps(payload, ensure_ascii=False, sort_keys=True))

    def test_service_marks_robustness_evidence_export_unavailable_when_stored_payload_missing(self) -> None:
        service = RuleBacktestService(self.db)
        self._seed_history(
            "000001",
            [100.0 + (index * 0.3) + ((-1) ** index) * 1.1 for index in range(96)],
            start=date(2024, 1, 1),
        )

        with patch.object(service, "_ensure_market_history", return_value=0), patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.run_backtest(
                code="000001",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )

        with self.db.get_session() as session:
            row = session.execute(select(RuleBacktestRun).where(RuleBacktestRun.id == response["id"])).scalar_one()
            summary = json.loads(row.summary_json or "{}")
            summary.pop("robustness_analysis", None)
            row.summary_json = json.dumps(summary, ensure_ascii=False)
            session.commit()

        export_index = service.get_support_export_index(response["id"])
        robustness_item = export_index["exports"][4]

        self.assertFalse(robustness_item["available"])
        self.assertEqual(robustness_item["availability_reason"], "stored_robustness_analysis_missing")
        with self.assertRaisesRegex(ValueError, "has no stored robustness evidence to export"):
            service.get_robustness_evidence_export_json(response["id"])

    def test_resolve_stored_robustness_evidence_payload_prefers_summary_authority(self) -> None:
        summary_payload = {
            "state": "research_prototype",
            "seed": 7,
            "configuration": {
                "walk_forward": {
                    "train_window": 24,
                    "test_window": 12,
                    "step": 12,
                    "max_windows": 4,
                },
                "monte_carlo": {
                    "simulation_count": 12,
                    "seed": 7,
                    "noise_scale": 0.75,
                },
            },
        }
        run_payload = {
            "state": "research_prototype",
            "seed": 99,
            "configuration": {
                "walk_forward": {
                    "train_window": 36,
                    "test_window": 18,
                    "step": 9,
                    "max_windows": 3,
                },
                "monte_carlo": {
                    "simulation_count": 16,
                    "seed": 99,
                    "noise_scale": 0.5,
                },
            },
        }

        payload = resolve_stored_robustness_evidence_payload(
            {
                "summary": {"robustness_analysis": summary_payload},
                "robustness_analysis": run_payload,
            }
        )

        self.assertEqual(payload["state"], summary_payload["state"])
        self.assertEqual(payload["seed"], summary_payload["seed"])
        self.assertEqual(payload["configuration"], summary_payload["configuration"])
        self.assertNotEqual(payload["seed"], run_payload["seed"])
        self.assertEqual(
            payload["walk_forward_oos_evidence"]["contract_kind"],
            "backtest_walk_forward_oos_diagnostic_evidence",
        )
        self._assert_robustness_payload_avoids_optimizer_semantics(payload)

    def _assert_support_bundle_export_contract(
        self,
        *,
        service: RuleBacktestService,
        run_id: int,
    ) -> None:
        run = service.get_run(run_id)
        assert run is not None

        manifest = service.get_support_bundle_manifest(run_id)
        reproducibility = service.get_support_bundle_reproducibility_manifest(run_id)
        export_index = service.get_support_export_index(run_id)

        self.assertEqual(export_index["run_id"], run_id)
        self.assertEqual(export_index["status"], run["status"])
        self.assertEqual(
            [item["key"] for item in export_index["exports"]],
            [
                "support_bundle_manifest_json",
                "support_bundle_reproducibility_manifest_json",
                "execution_trace_json",
                "execution_trace_csv",
                "robustness_evidence_json",
            ],
        )

        self.assertEqual(manifest["run"]["id"], run_id)
        self.assertEqual(reproducibility["run"]["id"], run_id)
        self.assertEqual(manifest["run"]["status"], run["status"])
        self.assertEqual(reproducibility["run"]["status"], run["status"])
        self.assertEqual(manifest["run_timing"], run["run_timing"])
        self.assertEqual(reproducibility["run_timing"], run["run_timing"])
        self.assertEqual(manifest["run_diagnostics"], run["run_diagnostics"])
        self.assertEqual(reproducibility["run_diagnostics"], run["run_diagnostics"])
        self.assertEqual(manifest["artifact_availability"], run["artifact_availability"])
        self.assertEqual(reproducibility["artifact_availability"], run["artifact_availability"])
        self.assertEqual(manifest["readback_integrity"], run["readback_integrity"])
        self.assertEqual(reproducibility["readback_integrity"], run["readback_integrity"])
        self.assertEqual(
            manifest["result_authority"],
            {
                "contract_version": run["result_authority"]["contract_version"],
                "read_mode": run["result_authority"]["read_mode"],
                "domains": run["result_authority"]["domains"],
            },
        )
        self.assertEqual(
            reproducibility["result_authority"],
            {
                "contract_version": run["result_authority"]["contract_version"],
                "read_mode": run["result_authority"]["read_mode"],
                "domains": {
                    domain_name: {
                        "source": domain_payload["source"],
                        "completeness": domain_payload["completeness"],
                        "state": domain_payload["state"],
                    }
                    for domain_name, domain_payload in run["result_authority"]["domains"].items()
                },
            },
        )
        self.assertEqual(
            manifest["result_authority"]["domains"]["execution_trace"],
            {
                "source": run["result_authority"]["domains"]["execution_trace"]["source"],
                "completeness": run["result_authority"]["domains"]["execution_trace"]["completeness"],
                "state": run["result_authority"]["domains"]["execution_trace"]["state"],
                "missing": run["result_authority"]["domains"]["execution_trace"]["missing"],
                "missing_kind": run["result_authority"]["domains"]["execution_trace"]["missing_kind"],
            },
        )
        execution_assumptions_payload = dict(
            (run.get("execution_assumptions_snapshot") or {}).get("payload")
            or run.get("execution_assumptions")
            or {}
        )
        expected_execution_assumptions_hash = (
            hashlib.sha256(
                json.dumps(
                    execution_assumptions_payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            if execution_assumptions_payload
            else None
        )
        self.assertEqual(
            reproducibility["execution_assumptions_fingerprint"]["source"],
            run["result_authority"]["domains"]["execution_assumptions_snapshot"]["source"],
        )
        self.assertEqual(
            reproducibility["execution_assumptions_fingerprint"]["completeness"],
            run["result_authority"]["domains"]["execution_assumptions_snapshot"]["completeness"],
        )
        self.assertEqual(
            reproducibility["execution_assumptions_fingerprint"]["summary_text"],
            execution_assumptions_payload.get("summary_text"),
        )
        self.assertEqual(
            reproducibility["execution_assumptions_fingerprint"]["hash_sha256"],
            expected_execution_assumptions_hash,
        )
        self.assertEqual(manifest["artifact_counts"]["trade_rows_count"], len(run.get("trades") or []))
        self.assertEqual(
            manifest["artifact_counts"]["execution_trace_rows_count"],
            len((run.get("execution_trace") or {}).get("rows") or []),
        )
        for payload in (manifest, reproducibility, export_index):
            self._assert_public_backtest_text_is_analytical(
                json.dumps(payload, ensure_ascii=False, sort_keys=True)
            )

        expected_trace_available = bool((run.get("execution_trace") or {}).get("rows") or [])
        expected_trace_reason = (
            "execution_trace_rows_present" if expected_trace_available else "execution_trace_rows_missing"
        )
        expected_robustness_available = bool(dict(run.get("robustness_analysis") or {}))
        expected_robustness_reason = (
            "stored_robustness_analysis_present"
            if expected_robustness_available
            else "stored_robustness_analysis_missing"
        )
        expected_exports = [
            (
                "support_bundle_manifest_json",
                True,
                "run_exists",
                "json",
                "application/json",
                "api",
                f"/api/v1/backtest/rule/runs/{run_id}/support-bundle-manifest",
                "compact",
            ),
            (
                "support_bundle_reproducibility_manifest_json",
                True,
                "run_exists",
                "json",
                "application/json",
                "api",
                f"/api/v1/backtest/rule/runs/{run_id}/support-bundle-reproducibility-manifest",
                "compact",
            ),
            (
                "execution_trace_json",
                expected_trace_available,
                expected_trace_reason,
                "json",
                "application/json",
                "api",
                f"/api/v1/backtest/rule/runs/{run_id}/execution-trace.json",
                "heavy",
            ),
            (
                "execution_trace_csv",
                expected_trace_available,
                expected_trace_reason,
                "csv",
                "text/csv",
                "api",
                f"/api/v1/backtest/rule/runs/{run_id}/execution-trace.csv",
                "heavy",
            ),
            (
                "robustness_evidence_json",
                expected_robustness_available,
                expected_robustness_reason,
                "json",
                "application/json",
                "api",
                f"/api/v1/backtest/rule/runs/{run_id}/robustness-evidence.json",
                "heavy",
            ),
        ]
        for item, expected in zip(export_index["exports"], expected_exports):
            (
                expected_key,
                expected_available,
                expected_reason,
                expected_format,
                expected_media_type,
                expected_delivery_mode,
                expected_endpoint_path,
                expected_payload_class,
            ) = expected
            self.assertEqual(item["key"], expected_key)
            self.assertEqual(item["available"], expected_available)
            self.assertEqual(item["availability_reason"], expected_reason)
            self.assertEqual(item["format"], expected_format)
            self.assertEqual(item["media_type"], expected_media_type)
            self.assertEqual(item["delivery_mode"], expected_delivery_mode)
            self.assertEqual(item["endpoint_path"], expected_endpoint_path)
            self.assertEqual(item["payload_class"], expected_payload_class)

        if expected_trace_available:
            trace_json = service.get_execution_trace_export_json(run_id)
            trace_csv_text = service.get_execution_trace_export_csv_text(run_id)
            trace_csv_lines = trace_csv_text.splitlines()
            trace_csv_rows = list(csv.DictReader(trace_csv_lines))
            self.assertEqual(trace_json["source"], run["execution_trace"]["source"])
            self.assertEqual(trace_json["completeness"], run["execution_trace"]["completeness"])
            self.assertEqual(
                reproducibility["result_authority"]["domains"]["execution_trace"]["source"],
                trace_json["source"],
            )
            self.assertEqual(
                reproducibility["result_authority"]["domains"]["execution_trace"]["completeness"],
                trace_json["completeness"],
            )
            self.assertEqual(list(trace_json.keys()), EXPECTED_TRACE_EXPORT_JSON_KEYS)
            self.assertEqual(
                list(trace_json["trace_rows"][0].keys()),
                EXPECTED_TRACE_EXPORT_FIELD_LABELS,
            )
            self.assertEqual(trace_csv_lines[0].split(","), EXPECTED_TRACE_EXPORT_FIELD_LABELS)
            self.assertEqual(len(trace_json["trace_rows"]), len(trace_csv_rows))
            self.assertEqual(
                len(trace_json["trace_rows"]),
                manifest["artifact_counts"]["execution_trace_rows_count"],
            )
            self.assertEqual(trace_json["benchmark_summary"], run["benchmark_summary"])
            self.assertEqual(
                trace_json["benchmark_summary"].get("requested_mode"),
                manifest["run"]["benchmark_mode"],
            )
            self._assert_public_backtest_text_is_analytical(
                json.dumps(trace_json, ensure_ascii=False, sort_keys=True)
            )
            self._assert_public_backtest_text_is_analytical(trace_csv_text)
        else:
            with self.assertRaisesRegex(ValueError, "has no audit rows to export"):
                service.get_execution_trace_export_json(run_id)
            with self.assertRaisesRegex(ValueError, "has no audit rows to export"):
                service.get_execution_trace_export_csv_text(run_id)
            self.assertEqual(
                manifest["result_authority"]["domains"]["execution_trace"]["source"],
                "unavailable",
            )
            self.assertEqual(
                manifest["result_authority"]["domains"]["execution_trace"]["completeness"],
                "unavailable",
            )
            self.assertEqual(
                manifest["result_authority"]["domains"]["execution_trace"]["state"],
                "unavailable",
            )
            self.assertEqual(
                reproducibility["result_authority"]["domains"]["execution_trace"]["source"],
                "unavailable",
            )
            self.assertEqual(
                reproducibility["result_authority"]["domains"]["execution_trace"]["completeness"],
                "unavailable",
            )
            self.assertEqual(
                reproducibility["result_authority"]["domains"]["execution_trace"]["state"],
                "unavailable",
            )

        if expected_robustness_available:
            robustness_payload = service.get_robustness_evidence_export_json(run_id)
            self.assertEqual(robustness_payload["state"], run["robustness_analysis"]["state"])
            self.assertEqual(robustness_payload["configuration"], run["robustness_analysis"]["configuration"])
            self.assertEqual(robustness_payload["walk_forward"], run["robustness_analysis"]["walk_forward"])
            self.assertEqual(
                robustness_payload["walk_forward_oos_evidence"]["contract_kind"],
                "backtest_walk_forward_oos_diagnostic_evidence",
            )
            self.assertEqual(robustness_payload["walk_forward_oos_evidence"]["source_run_id"], run_id)
            self._assert_robustness_payload_avoids_optimizer_semantics(robustness_payload)
            self._assert_public_backtest_text_is_analytical(
                json.dumps(robustness_payload, ensure_ascii=False, sort_keys=True)
            )
        else:
            with self.assertRaisesRegex(ValueError, "has no stored robustness evidence to export"):
                service.get_robustness_evidence_export_json(run_id)

    def test_support_bundle_artifact_exports_form_coherent_handoff_surface(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )

        self._assert_support_bundle_export_contract(service=service, run_id=response["id"])

    def test_support_bundle_artifact_exports_preserve_coherent_handoff_surface_during_live_storage_repair(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )

        deleted = service.repo.delete_trades_by_run_ids([response["id"]])
        self.assertGreater(deleted, 0)

        self._assert_support_bundle_export_contract(service=service, run_id=response["id"])

    def test_support_bundle_readback_surfaces_keep_missing_trace_explicit_without_engine_rerun(self) -> None:
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
        summary = json.loads(run_row.summary_json)
        summary["execution_trace"] = {}
        summary["visualization"] = dict(summary.get("visualization") or {})
        summary["visualization"]["audit_rows"] = []
        summary["visualization"]["daily_return_series"] = []
        summary["visualization"]["exposure_curve"] = []
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        with patch.object(
            service.engine,
            "run",
            side_effect=AssertionError("support-bundle readback must not rerun stored strategy calculations"),
        ) as engine_run_mock:
            manifest = service.get_support_bundle_manifest(response["id"])
            reproducibility = service.get_support_bundle_reproducibility_manifest(response["id"])
            export_index = service.get_support_export_index(response["id"])
            robustness_payload = service.get_robustness_evidence_export_json(response["id"])
            with self.assertRaisesRegex(ValueError, "has no audit rows to export"):
                service.get_execution_trace_export_json(response["id"])
            with self.assertRaisesRegex(ValueError, "has no audit rows to export"):
                service.get_execution_trace_export_csv_text(response["id"])

        engine_run_mock.assert_not_called()
        self._assert_robustness_payload_avoids_optimizer_semantics(robustness_payload)
        self.assertFalse(manifest["artifact_availability"]["has_execution_trace"])
        self.assertEqual(manifest["artifact_counts"]["execution_trace_rows_count"], 0)
        self.assertEqual(
            manifest["result_authority"]["domains"]["execution_trace"],
            {
                "source": "unavailable",
                "completeness": "unavailable",
                "state": "unavailable",
                "missing": ["rows"],
                "missing_kind": "fields",
            },
        )
        self.assertEqual(
            reproducibility["result_authority"]["domains"]["execution_trace"],
            {
                "source": "unavailable",
                "completeness": "unavailable",
                "state": "unavailable",
            },
        )
        self.assertEqual(
            [
                export_index["exports"][2]["availability_reason"],
                export_index["exports"][3]["availability_reason"],
            ],
            ["execution_trace_rows_missing", "execution_trace_rows_missing"],
        )
        self.assertFalse(export_index["exports"][2]["available"])
        self.assertFalse(export_index["exports"][3]["available"])
        repaired_run = service.get_run(response["id"])
        assert repaired_run is not None
        self.assertTrue(repaired_run["artifact_availability"]["has_trade_rows"])
        self.assertFalse(repaired_run["artifact_availability"]["has_execution_trace"])
        self.assertEqual(
            repaired_run["artifact_availability"]["source"],
            "summary.artifact_availability+live_storage_repair",
        )
        self.assertTrue(repaired_run["readback_integrity"]["used_live_storage_repair"])
        self.assertEqual(repaired_run["readback_integrity"]["integrity_level"], "drift_repaired")
        self.assertEqual(repaired_run["readback_integrity"]["drift_domains"], ["execution_trace"])

    def test_run_response_exposes_stored_first_result_authority(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )

        authority = response["result_authority"]
        self.assertEqual(authority["contract_version"], "v1")
        self.assertEqual(authority["read_mode"], "stored_first")
        self.assertEqual(authority["summary_source"], "row.summary_json")
        self.assertEqual(authority["summary_completeness"], "complete")
        self.assertEqual(authority["summary_missing_fields"], [])
        self.assertEqual(authority["parsed_strategy_source"], "row.parsed_strategy_json")
        self.assertEqual(authority["parsed_strategy_completeness"], "complete")
        self.assertEqual(authority["parsed_strategy_missing_fields"], [])
        self.assertEqual(authority["metrics_source"], "summary.metrics+row_columns_fallback")
        self.assertEqual(authority["metrics_completeness"], "stored_partial_repaired")
        self.assertIn("annualized_return_pct", authority["metrics_missing_fields"])
        self.assertEqual(authority["execution_model_source"], "summary.execution_model")
        self.assertEqual(authority["execution_model_completeness"], "complete")
        self.assertEqual(authority["execution_model_missing_fields"], [])
        self.assertEqual(authority["execution_assumptions_source"], "summary.execution_assumptions_snapshot")
        self.assertEqual(authority["execution_assumptions_snapshot_completeness"], "complete")
        self.assertEqual(authority["execution_assumptions_snapshot_missing_keys"], [])
        self.assertEqual(authority["comparison_source"], "summary.visualization.comparison")
        self.assertEqual(authority["comparison_completeness"], "complete")
        self.assertEqual(authority["comparison_missing_sections"], [])
        self.assertEqual(authority["replay_payload_source"], "summary.visualization.audit_rows")
        self.assertEqual(authority["replay_payload_completeness"], "complete")
        self.assertEqual(authority["replay_payload_missing_sections"], [])
        self.assertEqual(authority["audit_rows_source"], "summary.visualization.audit_rows")
        self.assertEqual(authority["daily_return_series_source"], "summary.visualization.daily_return_series")
        self.assertEqual(authority["exposure_curve_source"], "summary.visualization.exposure_curve")
        self.assertEqual(authority["trade_rows_source"], "stored_rule_backtest_trades")
        self.assertEqual(authority["trade_rows_completeness"], "complete")
        self.assertEqual(authority["trade_rows_missing_fields"], [])
        self.assertEqual(authority["equity_curve_source"], "row.equity_curve_json")
        self.assertEqual(authority["equity_curve_completeness"], "complete")
        self.assertEqual(authority["equity_curve_missing_fields"], [])
        self.assertEqual(authority["execution_trace_source"], "summary.execution_trace")
        self.assertEqual(response["artifact_availability"]["source"], "summary.artifact_availability")
        self.assertEqual(response["artifact_availability"]["completeness"], "complete")
        self.assertTrue(response["artifact_availability"]["has_trade_rows"])
        self.assertTrue(response["artifact_availability"]["has_equity_curve"])
        self.assertTrue(response["artifact_availability"]["has_execution_trace"])
        self.assertEqual(response["summary"]["artifact_availability"], response["artifact_availability"])
        self.assertEqual(
            response["readback_integrity"]["source"],
            "derived_from_result_authority+stored_repair",
        )
        self.assertEqual(response["readback_integrity"]["completeness"], "stored_partial_repaired")
        self.assertFalse(response["readback_integrity"]["used_legacy_fallback"])
        self.assertFalse(response["readback_integrity"]["used_live_storage_repair"])
        self.assertEqual(response["readback_integrity"]["drift_domains"], [])
        self.assertEqual(response["readback_integrity"]["missing_summary_fields"], [])
        self.assertEqual(response["readback_integrity"]["integrity_level"], "stored_repaired")
        self.assertEqual(response["summary"]["readback_integrity"], response["readback_integrity"])
        self.assertEqual(
            authority["domains"]["summary"],
            {
                "source": "row.summary_json",
                "completeness": "complete",
                "state": "available",
                "missing": authority["summary_missing_fields"],
                "missing_kind": "fields",
            },
        )
        self.assertEqual(
            authority["domains"]["parsed_strategy"],
            {
                "source": "row.parsed_strategy_json",
                "completeness": "complete",
                "state": "available",
                "missing": [],
                "missing_kind": "fields",
            },
        )
        self.assertEqual(
            authority["domains"]["metrics"],
            {
                "source": "summary.metrics+row_columns_fallback",
                "completeness": "stored_partial_repaired",
                "state": "available",
                "missing": authority["metrics_missing_fields"],
                "missing_kind": "fields",
            },
        )
        self.assertEqual(
            authority["domains"]["execution_model"],
            {
                "source": "summary.execution_model",
                "completeness": "complete",
                "state": "available",
                "missing": [],
                "missing_kind": "fields",
            },
        )
        self.assertEqual(
            authority["domains"]["comparison"],
            {
                "source": "summary.visualization.comparison",
                "completeness": "complete",
                "state": "available",
                "missing": [],
                "missing_kind": "sections",
            },
        )
        self.assertEqual(
            authority["domains"]["replay_payload"],
            {
                "source": "summary.visualization.audit_rows",
                "completeness": "complete",
                "state": "available",
                "missing": [],
                "missing_kind": "sections",
            },
        )
        self.assertEqual(
            authority["domains"]["execution_assumptions_snapshot"],
            {
                "source": "summary.execution_assumptions_snapshot",
                "completeness": "complete",
                "state": "available",
                "missing": [],
                "missing_kind": "keys",
            },
        )
        self.assertEqual(
            authority["domains"]["trade_rows"],
            {
                "source": "stored_rule_backtest_trades",
                "completeness": "complete",
                "state": "available",
                "missing": [],
                "missing_kind": "fields",
            },
        )
        self.assertEqual(
            authority["domains"]["equity_curve"],
            {
                "source": "row.equity_curve_json",
                "completeness": "complete",
                "state": "available",
                "missing": [],
                "missing_kind": "fields",
            },
        )
        self.assertEqual(
            authority["domains"]["execution_trace"],
            {
                "source": "summary.execution_trace",
                "completeness": "complete",
                "state": "available",
                "missing": [],
                "missing_kind": "fields",
            },
        )
        self.assertEqual(response["execution_assumptions_snapshot"]["version"], "v1")
        self.assertEqual(
            response["execution_assumptions_snapshot"]["source"],
            "summary.execution_assumptions_snapshot",
        )
        self.assertEqual(
            response["execution_assumptions_snapshot"]["payload"],
            response["execution_assumptions"],
        )

    def test_compare_runs_returns_stored_first_completed_run_snapshots(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            first = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )
            second = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA5. Sell when Close < MA5.",
                lookback_bars=20,
                confirmed=True,
            )

        payload = service.compare_runs([int(first["id"]), int(second["id"])])

        self.assertEqual(payload["comparison_source"], "stored_rule_backtest_runs")
        self.assertEqual(payload["read_mode"], "stored_first")
        self.assertEqual(payload["requested_run_ids"], [int(first["id"]), int(second["id"])])
        self.assertEqual(payload["resolved_run_ids"], [int(first["id"]), int(second["id"])])
        self.assertEqual(payload["comparable_run_ids"], [int(first["id"]), int(second["id"])])
        self.assertEqual(payload["missing_run_ids"], [])
        self.assertEqual(payload["unavailable_runs"], [])
        self.assertEqual(payload["field_groups"], ["metadata", "parsed_strategy", "metrics", "benchmark", "execution_model"])
        self.assertEqual(len(payload["items"]), 2)
        first_item = payload["items"][0]
        self.assertEqual(first_item["metadata"]["id"], int(first["id"]))
        self.assertEqual(first_item["metadata"]["code"], "600519")
        self.assertEqual(first_item["metadata"]["status"], "completed")
        self.assertEqual(first_item["parsed_strategy"]["strategy_kind"], first["parsed_strategy"]["strategy_kind"])
        self.assertIn("strategy_type", first_item["parsed_strategy"]["strategy_spec"])
        self.assertEqual(first_item["metrics"]["trade_count"], first["trade_count"])
        self.assertEqual(first_item["benchmark"]["benchmark_mode"], first["benchmark_mode"])
        self.assertIn("method", first_item["benchmark"]["benchmark_summary"])
        self.assertEqual(first_item["execution_model"]["timeframe"], first["execution_model"]["timeframe"])
        self.assertEqual(
            first_item["result_authority"]["domains"]["metrics"]["source"],
            first["result_authority"]["domains"]["metrics"]["source"],
        )
        comparison_summary = payload["comparison_summary"]
        self.assertEqual(comparison_summary["baseline"]["run_id"], int(first["id"]))
        self.assertEqual(
            comparison_summary["baseline"]["selection_rule"],
            "first_comparable_run_by_request_order",
        )
        self.assertEqual(comparison_summary["context"]["code_values"], ["600519"])
        self.assertTrue(comparison_summary["context"]["all_same_code"])
        self.assertTrue(comparison_summary["context"]["all_same_timeframe"])
        self.assertEqual(
            comparison_summary["context"]["strategy_family_values"],
            sorted(
                {
                    str(first["parsed_strategy"]["strategy_spec"].get("strategy_family") or ""),
                    str(second["parsed_strategy"]["strategy_spec"].get("strategy_family") or ""),
                }
            ),
        )
        total_return_delta = comparison_summary["metric_deltas"]["total_return_pct"]
        self.assertEqual(total_return_delta["state"], "comparable")
        self.assertEqual(total_return_delta["baseline_run_id"], int(first["id"]))
        self.assertEqual(total_return_delta["baseline_value"], first["total_return_pct"])
        self.assertEqual(total_return_delta["deltas"][0]["run_id"], int(first["id"]))
        self.assertEqual(total_return_delta["deltas"][0]["delta_vs_baseline"], 0.0)

    def test_compare_runs_reports_missing_requested_runs_without_recomputing(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            first = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )
            second = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA5. Sell when Close < MA5.",
                lookback_bars=20,
                confirmed=True,
            )

        payload = service.compare_runs([int(first["id"]), 999999, int(second["id"])])

        self.assertEqual(payload["requested_run_ids"], [int(first["id"]), 999999, int(second["id"])])
        self.assertEqual(payload["resolved_run_ids"], [int(first["id"]), int(second["id"])])
        self.assertEqual(payload["comparable_run_ids"], [int(first["id"]), int(second["id"])])
        self.assertEqual(payload["missing_run_ids"], [999999])
        self.assertEqual(payload["unavailable_runs"], [])
        self.assertEqual(len(payload["items"]), 2)
        self.assertEqual(payload["comparison_summary"]["baseline"]["run_id"], int(first["id"]))

    def test_compare_runs_rejects_requests_without_two_completed_runs(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            completed = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )
            queued = service.submit_backtest(
                code="600519",
                strategy_text="Buy when Close > MA5. Sell when Close < MA5.",
                lookback_bars=20,
                confirmed=True,
            )

        with self.assertRaises(ValueError) as ctx:
            service.compare_runs([int(completed["id"]), int(queued["id"])])

        self.assertIn("At least two completed accessible rule backtest runs are required for comparison", str(ctx.exception))
        self.assertIn(str(int(queued["id"])), str(ctx.exception))

    def test_compare_runs_summary_marks_partial_metric_comparability(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            first = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )
            second = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA5. Sell when Close < MA5.",
                lookback_bars=20,
                confirmed=True,
            )

        first_row = service.repo.get_run(int(first["id"]), **service._owner_kwargs())
        self.assertIsNotNone(first_row)
        first_summary = json.loads(first_row.summary_json)
        first_summary.setdefault("metrics", {})
        first_summary["metrics"]["annualized_return_pct"] = 12.34
        service.repo.update_run(
            int(first["id"]),
            **service._owner_kwargs(),
            summary_json=service._serialize_json(first_summary),
        )

        payload = service.compare_runs([int(first["id"]), int(second["id"])])

        annualized_delta = payload["comparison_summary"]["metric_deltas"]["annualized_return_pct"]
        self.assertEqual(annualized_delta["state"], "partial")
        self.assertEqual(annualized_delta["baseline_run_id"], int(first["id"]))
        self.assertEqual(annualized_delta["baseline_value"], 12.34)
        self.assertEqual(annualized_delta["available_run_ids"], [int(first["id"])])
        self.assertEqual(annualized_delta["unavailable_run_ids"], [int(second["id"])])
        self.assertEqual(len(annualized_delta["deltas"]), 1)
        self.assertEqual(annualized_delta["deltas"][0]["run_id"], int(first["id"]))
        self.assertEqual(annualized_delta["deltas"][0]["delta_vs_baseline"], 0.0)

    def test_compare_runs_adds_identical_period_comparison_summary(self) -> None:
        service = RuleBacktestService(self.db)
        first_window = ("2024-01-01", "2024-01-24")
        second_window = ("2024-01-01", "2024-01-24")

        with patch.object(service, "_get_llm_adapter", return_value=None):
            first_parsed = service.parse_strategy(
                "Buy when Close > MA3. Sell when Close < MA3.",
                code="600519",
                start_date=first_window[0],
                end_date=first_window[1],
                initial_capital=100000.0,
            )
            second_parsed = service.parse_strategy(
                code="600519",
                strategy_text="Buy when Close > MA5. Sell when Close < MA5.",
                start_date=second_window[0],
                end_date=second_window[1],
                initial_capital=100000.0,
            )
            first = service.run_backtest(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                parsed_strategy=first_parsed,
                start_date=first_window[0],
                end_date=first_window[1],
                lookback_bars=20,
                benchmark_mode="same_symbol_buy_and_hold",
                confirmed=True,
            )
            second = service.run_backtest(
                code="600519",
                strategy_text="Buy when Close > MA5. Sell when Close < MA5.",
                parsed_strategy=second_parsed,
                start_date=second_window[0],
                end_date=second_window[1],
                lookback_bars=20,
                benchmark_mode="same_symbol_buy_and_hold",
                confirmed=True,
            )

        payload = service.compare_runs([int(first["id"]), int(second["id"])])

        period_comparison = payload["period_comparison"]
        self.assertEqual(period_comparison["baseline_run_id"], int(first["id"]))
        self.assertEqual(
            period_comparison["selection_rule"],
            "first_comparable_run_by_request_order",
        )
        self.assertEqual(period_comparison["relationship"], "identical")
        self.assertEqual(period_comparison["state"], "comparable")
        self.assertTrue(period_comparison["meaningfully_comparable"])
        self.assertEqual(
            period_comparison["period_bounds"],
            [
                {
                    "run_id": int(first["id"]),
                    "period_start": first["period_start"],
                    "period_end": first["period_end"],
                    "availability": "complete",
                },
                {
                    "run_id": int(second["id"]),
                    "period_start": second["period_start"],
                    "period_end": second["period_end"],
                    "availability": "complete",
                },
            ],
        )
        self.assertEqual(len(period_comparison["pairs"]), 1)
        self.assertEqual(period_comparison["pairs"][0]["run_id"], int(second["id"]))
        self.assertEqual(period_comparison["pairs"][0]["relationship"], "identical")
        self.assertEqual(period_comparison["pairs"][0]["state"], "comparable")
        self.assertTrue(period_comparison["pairs"][0]["meaningfully_comparable"])
        self.assertEqual(period_comparison["pairs"][0]["overlap_start"], first["period_start"])
        self.assertEqual(period_comparison["pairs"][0]["overlap_end"], first["period_end"])
        self.assertEqual(period_comparison["pairs"][0]["diagnostics"], ["identical_periods"])

    def test_compare_runs_adds_overlapping_period_comparison_summary(self) -> None:
        service = RuleBacktestService(self.db)
        strategy_text = "Buy when Close > MA3. Sell when Close < MA3."

        with patch.object(service, "_get_llm_adapter", return_value=None):
            first_parsed = service.parse_strategy(
                strategy_text,
                code="600519",
                start_date="2024-01-05",
                end_date="2024-01-20",
                initial_capital=100000.0,
            )
            first = service.run_backtest(
                code="600519",
                strategy_text=strategy_text,
                parsed_strategy=first_parsed,
                start_date="2024-01-05",
                end_date="2024-01-20",
                lookback_bars=20,
                benchmark_mode="same_symbol_buy_and_hold",
                confirmed=True,
            )
            second_parsed = service.parse_strategy(
                strategy_text,
                code="600519",
                start_date="2024-01-10",
                end_date="2024-01-24",
                initial_capital=100000.0,
            )
            second = service.run_backtest(
                code="600519",
                strategy_text=strategy_text,
                parsed_strategy=second_parsed,
                start_date="2024-01-10",
                end_date="2024-01-24",
                lookback_bars=20,
                benchmark_mode="same_symbol_buy_and_hold",
                confirmed=True,
            )

        payload = service.compare_runs([int(first["id"]), int(second["id"])])

        period_comparison = payload["period_comparison"]
        self.assertEqual(period_comparison["relationship"], "overlapping")
        self.assertEqual(period_comparison["state"], "comparable")
        self.assertTrue(period_comparison["meaningfully_comparable"])
        self.assertEqual(period_comparison["pairs"][0]["relationship"], "overlapping")
        self.assertEqual(period_comparison["pairs"][0]["overlap_start"], "2024-01-10")
        self.assertEqual(period_comparison["pairs"][0]["overlap_end"], "2024-01-20")
        self.assertEqual(period_comparison["pairs"][0]["overlap_days"], 11)
        self.assertIsNone(period_comparison["pairs"][0]["gap_days"])
        self.assertEqual(period_comparison["pairs"][0]["diagnostics"], ["overlapping_periods"])

    def test_compare_runs_adds_disjoint_period_comparison_summary(self) -> None:
        service = RuleBacktestService(self.db)
        strategy_text = "Buy when Close > MA3. Sell when Close < MA3."

        with patch.object(service, "_get_llm_adapter", return_value=None):
            first_parsed = service.parse_strategy(
                strategy_text,
                code="600519",
                start_date="2024-01-01",
                end_date="2024-01-08",
                initial_capital=100000.0,
            )
            first = service.run_backtest(
                code="600519",
                strategy_text=strategy_text,
                parsed_strategy=first_parsed,
                start_date="2024-01-01",
                end_date="2024-01-08",
                lookback_bars=20,
                benchmark_mode="same_symbol_buy_and_hold",
                confirmed=True,
            )
            second_parsed = service.parse_strategy(
                strategy_text,
                code="600519",
                start_date="2024-01-15",
                end_date="2024-01-20",
                initial_capital=100000.0,
            )
            second = service.run_backtest(
                code="600519",
                strategy_text=strategy_text,
                parsed_strategy=second_parsed,
                start_date="2024-01-15",
                end_date="2024-01-20",
                lookback_bars=20,
                benchmark_mode="same_symbol_buy_and_hold",
                confirmed=True,
            )

        payload = service.compare_runs([int(first["id"]), int(second["id"])])

        period_comparison = payload["period_comparison"]
        self.assertEqual(period_comparison["relationship"], "disjoint")
        self.assertEqual(period_comparison["state"], "not_comparable")
        self.assertFalse(period_comparison["meaningfully_comparable"])
        self.assertEqual(period_comparison["pairs"][0]["relationship"], "disjoint")
        self.assertIsNone(period_comparison["pairs"][0]["overlap_start"])
        self.assertIsNone(period_comparison["pairs"][0]["overlap_end"])
        self.assertIsNone(period_comparison["pairs"][0]["overlap_days"])
        self.assertEqual(period_comparison["pairs"][0]["gap_days"], 6)
        self.assertEqual(period_comparison["pairs"][0]["diagnostics"], ["disjoint_periods"])

    def test_compare_runs_marks_partial_period_metadata_availability(self) -> None:
        service = RuleBacktestService(self.db)
        first_window = ("2024-01-01", "2024-01-24")
        second_window = ("2024-01-01", "2024-01-24")

        with patch.object(service, "_get_llm_adapter", return_value=None):
            first_parsed = service.parse_strategy(
                "Buy when Close > MA3. Sell when Close < MA3.",
                code="600519",
                start_date=first_window[0],
                end_date=first_window[1],
                initial_capital=100000.0,
            )
            second_parsed = service.parse_strategy(
                code="600519",
                strategy_text="Buy when Close > MA5. Sell when Close < MA5.",
                start_date=second_window[0],
                end_date=second_window[1],
                initial_capital=100000.0,
            )
            first = service.run_backtest(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                parsed_strategy=first_parsed,
                start_date=first_window[0],
                end_date=first_window[1],
                lookback_bars=20,
                benchmark_mode="same_symbol_buy_and_hold",
                confirmed=True,
            )
            second = service.run_backtest(
                code="600519",
                strategy_text="Buy when Close > MA5. Sell when Close < MA5.",
                parsed_strategy=second_parsed,
                start_date=second_window[0],
                end_date=second_window[1],
                lookback_bars=20,
                benchmark_mode="same_symbol_buy_and_hold",
                confirmed=True,
            )

        second_row = service.repo.get_run(int(second["id"]), **service._owner_kwargs())
        self.assertIsNotNone(second_row)
        second_summary = json.loads(second_row.summary_json)
        second_summary.setdefault("metrics", {})
        second_summary["metrics"]["period_start"] = second["period_start"]
        second_summary["metrics"]["period_end"] = None
        service.repo.update_run(
            int(second["id"]),
            **service._owner_kwargs(),
            summary_json=service._serialize_json(second_summary),
        )

        payload = service.compare_runs([int(first["id"]), int(second["id"])])

        period_comparison = payload["period_comparison"]
        self.assertEqual(period_comparison["relationship"], "partial")
        self.assertEqual(period_comparison["state"], "limited")
        self.assertFalse(period_comparison["meaningfully_comparable"])
        self.assertEqual(
            period_comparison["period_bounds"][1],
            {
                "run_id": int(second["id"]),
                "period_start": second["period_start"],
                "period_end": None,
                "availability": "partial",
            },
        )
        self.assertEqual(period_comparison["pairs"][0]["relationship"], "partial")
        self.assertEqual(period_comparison["pairs"][0]["state"], "limited")
        self.assertFalse(period_comparison["pairs"][0]["meaningfully_comparable"])
        self.assertEqual(period_comparison["pairs"][0]["diagnostics"], ["missing_period_end"])

    def test_compare_runs_builds_same_family_parameter_comparison(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None), patch.object(
            service,
            "_ensure_market_history",
            return_value=0,
        ):
            first_parsed = service.parse_strategy(
                "5日均线上穿20日均线买入，下穿卖出",
                code="600519",
                start_date="2024-01-01",
                end_date="2024-01-24",
                initial_capital=100000.0,
            )
            second_parsed = service.parse_strategy(
                "10日均线上穿30日均线买入，下穿卖出",
                code="600519",
                start_date="2024-01-01",
                end_date="2024-01-24",
                initial_capital=100000.0,
            )
            first = service.run_backtest(
                code="600519",
                strategy_text="5日均线上穿20日均线买入，下穿卖出",
                parsed_strategy=first_parsed,
                start_date="2024-01-01",
                end_date="2024-01-24",
                lookback_bars=20,
                confirmed=True,
            )
            second = service.run_backtest(
                code="600519",
                strategy_text="10日均线上穿30日均线买入，下穿卖出",
                parsed_strategy=second_parsed,
                start_date="2024-01-01",
                end_date="2024-01-24",
                lookback_bars=20,
                confirmed=True,
            )

        payload = service.compare_runs([int(first["id"]), int(second["id"])])

        parameter_comparison = payload["parameter_comparison"]
        self.assertEqual(parameter_comparison["state"], "same_family_comparable")
        self.assertEqual(parameter_comparison["strategy_family_values"], ["moving_average_crossover"])
        self.assertEqual(parameter_comparison["strategy_type_values"], ["moving_average_crossover"])
        self.assertIn("strategy_spec.signal.fast_period", parameter_comparison["differing_parameter_keys"])
        self.assertIn("strategy_spec.signal.slow_period", parameter_comparison["differing_parameter_keys"])
        self.assertIn("strategy_spec.execution.signal_timing", parameter_comparison["shared_parameter_keys"])
        self.assertEqual(
            parameter_comparison["shared_parameters"]["strategy_spec.execution.signal_timing"],
            "bar_close",
        )
        self.assertEqual(
            parameter_comparison["differing_parameters"]["strategy_spec.signal.fast_period"]["values"],
            [
                {"run_id": int(first["id"]), "value": 5},
                {"run_id": int(second["id"]), "value": 10},
            ],
        )

    def test_compare_runs_adds_stored_compare_derived_heatmap_projection(self) -> None:
        service = RuleBacktestService(self.db)
        first_payload = self._compare_run_payload(
            run_id=101,
            code="600519",
            parsed_strategy={
                "strategy_kind": "moving_average_crossover",
                "strategy_spec": {
                    "strategy_type": "moving_average_crossover",
                    "strategy_family": "moving_average_crossover",
                    "signal": {
                        "indicator_family": "moving_average",
                        "fast_period": 5,
                        "slow_period": 20,
                        "fast_type": "simple",
                        "slow_type": "simple",
                        "entry_condition": "fast_crosses_above_slow",
                        "exit_condition": "fast_crosses_below_slow",
                    },
                    "execution": {
                        "frequency": "daily",
                        "signal_timing": "bar_close",
                        "fill_timing": "next_bar_open",
                    },
                    "position_behavior": {
                        "direction": "long_only",
                        "entry_sizing": "all_in",
                        "max_positions": 1,
                        "pyramiding": False,
                    },
                    "end_behavior": {"policy": "liquidate_at_end", "price_basis": "close"},
                },
            },
        )
        first_payload["total_return_pct"] = 12.4
        first_payload["max_drawdown_pct"] = 5.2

        second_payload = self._compare_run_payload(
            run_id=202,
            code="600519",
            parsed_strategy={
                "strategy_kind": "moving_average_crossover",
                "strategy_spec": {
                    "strategy_type": "moving_average_crossover",
                    "strategy_family": "moving_average_crossover",
                    "signal": {
                        "indicator_family": "moving_average",
                        "fast_period": 10,
                        "slow_period": 50,
                        "fast_type": "simple",
                        "slow_type": "simple",
                        "entry_condition": "fast_crosses_above_slow",
                        "exit_condition": "fast_crosses_below_slow",
                    },
                    "execution": {
                        "frequency": "daily",
                        "signal_timing": "bar_close",
                        "fill_timing": "next_bar_open",
                    },
                    "position_behavior": {
                        "direction": "long_only",
                        "entry_sizing": "all_in",
                        "max_positions": 1,
                        "pyramiding": False,
                    },
                    "end_behavior": {"policy": "liquidate_at_end", "price_basis": "close"},
                },
            },
        )
        second_payload["total_return_pct"] = 14.6
        second_payload["max_drawdown_pct"] = 6.0

        third_payload = self._compare_run_payload(
            run_id=303,
            code="600519",
            parsed_strategy={
                "strategy_kind": "moving_average_crossover",
                "strategy_spec": {
                    "strategy_type": "moving_average_crossover",
                    "strategy_family": "moving_average_crossover",
                    "signal": {
                        "indicator_family": "moving_average",
                        "fast_period": 10,
                        "fast_type": "simple",
                        "entry_condition": "fast_crosses_above_slow",
                        "exit_condition": "fast_crosses_below_slow",
                    },
                    "execution": {
                        "frequency": "daily",
                        "signal_timing": "bar_close",
                        "fill_timing": "next_bar_open",
                    },
                    "position_behavior": {
                        "direction": "long_only",
                        "entry_sizing": "all_in",
                        "max_positions": 1,
                        "pyramiding": False,
                    },
                    "end_behavior": {"policy": "liquidate_at_end", "price_basis": "close"},
                },
            },
        )
        third_payload["total_return_pct"] = 9.1
        third_payload["max_drawdown_pct"] = 7.4

        rows = [SimpleNamespace(id=101), SimpleNamespace(id=202), SimpleNamespace(id=303)]
        with patch.object(service.repo, "get_runs_by_ids", return_value=rows), patch.object(
            service,
            "_run_row_to_dict",
            side_effect=[first_payload, second_payload, third_payload],
        ):
            payload = service.compare_runs([101, 202, 303, 999999])

        projection = payload["heatmap_projection"]
        evidence = payload["parameter_stability_evidence"]
        self.assertIsNotNone(projection)
        self.assertEqual(projection["contract_kind"], "rule_backtest_compare_heatmap_projection")
        self.assertEqual(projection["contract_version"], "v1")
        self.assertEqual(projection["source"], "stored_compare_projection")
        self.assertEqual(projection["read_mode"], "stored_projection_only")
        self.assertEqual(projection["requested_compare_run_ids"], [101, 202, 303, 999999])
        self.assertEqual(projection["resolved_compare_run_ids"], [101, 202, 303])
        self.assertEqual(projection["source_run_ids"], [101, 202, 303])
        self.assertEqual(projection["missing_run_ids"], [999999])
        self.assertEqual(projection["metric_keys"], ["total_return_pct", "max_drawdown_pct"])
        self.assertEqual(projection["authority"]["comparison_source"], "stored_rule_backtest_runs")
        self.assertEqual(projection["authority"]["execution_count"], 0)
        self.assertFalse(projection["authority"]["provider_calls_executed"])
        self.assertEqual(projection["axes"]["x"]["axis_key"], "strategy_spec.signal.fast_period")
        self.assertEqual(projection["axes"]["x"]["values"], [5, 10])
        self.assertEqual(projection["axes"]["y"]["axis_key"], "strategy_spec.signal.slow_period")
        self.assertEqual(projection["axes"]["y"]["values"], [20, 50, None])
        self.assertEqual(
            projection["cell_availability_states"],
            ["available", "missing", "ambiguous"],
        )

        cells = {
            (cell["x_value"], cell["y_value"]): cell
            for cell in projection["cells"]
        }
        self.assertEqual(cells[(5, 20)]["availability_state"], "available")
        self.assertEqual(cells[(5, 20)]["source_run_ids"], [101])
        self.assertEqual(cells[(5, 20)]["metrics"]["total_return_pct"]["value"], 12.4)
        self.assertEqual(cells[(5, 20)]["metrics"]["max_drawdown_pct"]["value"], 5.2)
        self.assertEqual(cells[(10, 50)]["availability_state"], "available")
        self.assertEqual(cells[(10, 50)]["source_run_ids"], [202])
        self.assertEqual(cells[(5, 50)]["availability_state"], "missing")
        self.assertEqual(cells[(5, 50)]["metrics"]["total_return_pct"]["value"], None)
        self.assertEqual(cells[(10, None)]["availability_state"], "ambiguous")
        self.assertEqual(cells[(10, None)]["source_run_ids"], [303])
        self.assertEqual(cells[(10, None)]["metrics"]["total_return_pct"]["state"], "ambiguous")
        self.assertEqual(evidence["contract_kind"], "backtest_parameter_stability_diagnostic_evidence")
        self.assertEqual(evidence["source"], "stored_compare_summary")
        self.assertTrue(evidence["diagnostic_only"])
        self.assertFalse(evidence["decision_grade"])
        self.assertEqual(evidence["parameter_set_count"], 3)
        self.assertEqual(evidence["compatible_run_coverage"]["requested_run_count"], 4)
        self.assertEqual(evidence["compatible_run_coverage"]["resolved_run_count"], 3)
        self.assertEqual(evidence["compatible_run_coverage"]["compatible_run_ids"], [101, 202, 303])
        self.assertEqual(evidence["compatible_run_coverage"]["missing_run_ids"], [999999])
        self.assertEqual(evidence["missing_run_diagnostics"], [{"run_id": 999999, "reason": "missing_run"}])
        self.assertEqual(evidence["metric_dispersion"]["total_return_pct"]["range"], 5.5)
        self.assertFalse(evidence["authority"]["provider_calls_executed"])
        self.assertEqual(evidence["authority"]["execution_count"], 0)
        self._assert_robustness_payload_avoids_optimizer_semantics(evidence)

    def test_compare_runs_omits_heatmap_projection_without_two_usable_axes(self) -> None:
        service = RuleBacktestService(self.db)
        first_payload = self._compare_run_payload(
            run_id=101,
            code="600519",
            parsed_strategy={
                "strategy_kind": "moving_average_crossover",
                "strategy_spec": {
                    "strategy_type": "moving_average_crossover",
                    "strategy_family": "moving_average_crossover",
                    "signal": {
                        "indicator_family": "moving_average",
                        "fast_period": 5,
                        "slow_period": 20,
                        "fast_type": "simple",
                        "slow_type": "simple",
                        "entry_condition": "fast_crosses_above_slow",
                        "exit_condition": "fast_crosses_below_slow",
                    },
                    "execution": {
                        "frequency": "daily",
                        "signal_timing": "bar_close",
                        "fill_timing": "next_bar_open",
                    },
                },
            },
        )
        second_payload = self._compare_run_payload(
            run_id=202,
            code="600519",
            parsed_strategy={
                "strategy_kind": "moving_average_crossover",
                "strategy_spec": {
                    "strategy_type": "moving_average_crossover",
                    "strategy_family": "moving_average_crossover",
                    "signal": {
                        "indicator_family": "moving_average",
                        "fast_period": 10,
                        "slow_period": 20,
                        "fast_type": "simple",
                        "slow_type": "simple",
                        "entry_condition": "fast_crosses_above_slow",
                        "exit_condition": "fast_crosses_below_slow",
                    },
                    "execution": {
                        "frequency": "daily",
                        "signal_timing": "bar_close",
                        "fill_timing": "next_bar_open",
                    },
                },
            },
        )

        rows = [SimpleNamespace(id=101), SimpleNamespace(id=202)]
        with patch.object(service.repo, "get_runs_by_ids", return_value=rows), patch.object(
            service,
            "_run_row_to_dict",
            side_effect=[first_payload, second_payload],
        ):
            payload = service.compare_runs([101, 202])

        self.assertIsNone(payload["heatmap_projection"])

    def test_compare_runs_parameter_comparison_marks_different_families(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None), patch.object(
            service,
            "_ensure_market_history",
            return_value=0,
        ):
            moving_average = service.run_backtest(
                code="600519",
                strategy_text="5日均线上穿20日均线买入，下穿卖出",
                parsed_strategy=service.parse_strategy(
                    "5日均线上穿20日均线买入，下穿卖出",
                    code="600519",
                    start_date="2024-01-01",
                    end_date="2024-01-24",
                    initial_capital=100000.0,
                ),
                start_date="2024-01-01",
                end_date="2024-01-24",
                lookback_bars=20,
                confirmed=True,
            )
            macd = service.run_backtest(
                code="600519",
                strategy_text="MACD金叉买入，死叉卖出",
                parsed_strategy=service.parse_strategy(
                    "MACD金叉买入，死叉卖出",
                    code="600519",
                    start_date="2024-01-01",
                    end_date="2024-01-24",
                    initial_capital=100000.0,
                ),
                start_date="2024-01-01",
                end_date="2024-01-24",
                lookback_bars=20,
                confirmed=True,
            )

        payload = service.compare_runs([int(moving_average["id"]), int(macd["id"])])

        parameter_comparison = payload["parameter_comparison"]
        self.assertEqual(parameter_comparison["state"], "different_family")
        self.assertEqual(
            parameter_comparison["strategy_family_values"],
            ["macd_crossover", "moving_average_crossover"],
        )
        self.assertEqual(parameter_comparison["shared_parameter_keys"], [])
        self.assertEqual(parameter_comparison["differing_parameter_keys"], [])
        self.assertEqual(parameter_comparison["missing_parameter_keys"], [])

    def test_compare_runs_parameter_comparison_marks_partial_missing_keys(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None), patch.object(
            service,
            "_ensure_market_history",
            return_value=0,
        ):
            first = service.run_backtest(
                code="600519",
                strategy_text="5日均线上穿20日均线买入，下穿卖出",
                parsed_strategy=service.parse_strategy(
                    "5日均线上穿20日均线买入，下穿卖出",
                    code="600519",
                    start_date="2024-01-01",
                    end_date="2024-01-24",
                    initial_capital=100000.0,
                ),
                start_date="2024-01-01",
                end_date="2024-01-24",
                lookback_bars=20,
                confirmed=True,
            )
            second = service.run_backtest(
                code="600519",
                strategy_text="10日均线上穿30日均线买入，下穿卖出",
                parsed_strategy=service.parse_strategy(
                    "10日均线上穿30日均线买入，下穿卖出",
                    code="600519",
                    start_date="2024-01-01",
                    end_date="2024-01-24",
                    initial_capital=100000.0,
                ),
                start_date="2024-01-01",
                end_date="2024-01-24",
                lookback_bars=20,
                confirmed=True,
            )

        first_row = service.repo.get_run(int(first["id"]), **service._owner_kwargs())
        self.assertIsNotNone(first_row)
        first_parsed_strategy = json.loads(first_row.parsed_strategy_json)
        first_parsed_strategy["strategy_spec"]["signal"].pop("slow_period", None)
        service.repo.update_run(
            int(first["id"]),
            **service._owner_kwargs(),
            parsed_strategy_json=service._serialize_json(first_parsed_strategy),
        )

        payload = service.compare_runs([int(first["id"]), int(second["id"])])

        parameter_comparison = payload["parameter_comparison"]
        self.assertEqual(parameter_comparison["state"], "partial")
        self.assertIn("strategy_spec.signal.slow_period", parameter_comparison["missing_parameter_keys"])
        self.assertEqual(
            parameter_comparison["missing_parameters"]["strategy_spec.signal.slow_period"]["available_run_ids"],
            [int(second["id"])],
        )
        self.assertEqual(
            parameter_comparison["missing_parameters"]["strategy_spec.signal.slow_period"]["unavailable_run_ids"],
            [int(first["id"])],
        )
        self.assertEqual(
            parameter_comparison["missing_parameters"]["strategy_spec.signal.slow_period"]["state"],
            "partial",
        )

    def test_compare_runs_adds_same_code_market_code_comparison(self) -> None:
        service = RuleBacktestService(self.db)
        first_payload = self._compare_run_payload(run_id=101, code="600519")
        second_payload = self._compare_run_payload(run_id=202, code="SH600519")
        rows = [SimpleNamespace(id=101), SimpleNamespace(id=202)]

        with patch.object(service.repo, "get_runs_by_ids", return_value=rows), patch.object(
            service,
            "_run_row_to_dict",
            side_effect=[first_payload, second_payload],
        ):
            payload = service.compare_runs([101, 202])

        market_code_comparison = payload["market_code_comparison"]
        self.assertEqual(market_code_comparison["baseline_run_id"], 101)
        self.assertEqual(market_code_comparison["selection_rule"], "first_comparable_run_by_request_order")
        self.assertEqual(market_code_comparison["relationship"], "same_code")
        self.assertEqual(market_code_comparison["state"], "direct")
        self.assertTrue(market_code_comparison["directly_comparable"])
        self.assertEqual(
            market_code_comparison["runs"],
            [
                {
                    "run_id": 101,
                    "code": "600519",
                    "normalized_code": "600519",
                    "market": "cn",
                    "availability": "complete",
                    "diagnostics": [],
                },
                {
                    "run_id": 202,
                    "code": "SH600519",
                    "normalized_code": "600519",
                    "market": "cn",
                    "availability": "complete",
                    "diagnostics": [],
                },
            ],
        )
        self.assertEqual(
            market_code_comparison["pairs"],
            [
                {
                    "run_id": 202,
                    "relationship": "same_code",
                    "state": "direct",
                    "directly_comparable": True,
                    "baseline_code": "600519",
                    "candidate_code": "600519",
                    "baseline_market": "cn",
                    "candidate_market": "cn",
                    "diagnostics": ["same_normalized_code"],
                }
            ],
        )
        self.assertEqual(market_code_comparison["diagnostics"], ["same_normalized_code"])

    def test_compare_runs_adds_same_market_different_code_market_code_comparison(self) -> None:
        service = RuleBacktestService(self.db)
        first_payload = self._compare_run_payload(run_id=101, code="600519")
        second_payload = self._compare_run_payload(run_id=202, code="000001")
        rows = [SimpleNamespace(id=101), SimpleNamespace(id=202)]

        with patch.object(service.repo, "get_runs_by_ids", return_value=rows), patch.object(
            service,
            "_run_row_to_dict",
            side_effect=[first_payload, second_payload],
        ):
            payload = service.compare_runs([101, 202])

        market_code_comparison = payload["market_code_comparison"]
        self.assertEqual(market_code_comparison["relationship"], "same_market_different_code")
        self.assertEqual(market_code_comparison["state"], "limited")
        self.assertFalse(market_code_comparison["directly_comparable"])
        self.assertEqual(market_code_comparison["pairs"][0]["relationship"], "same_market_different_code")
        self.assertEqual(market_code_comparison["pairs"][0]["baseline_market"], "cn")
        self.assertEqual(market_code_comparison["pairs"][0]["candidate_market"], "cn")
        self.assertEqual(
            market_code_comparison["pairs"][0]["diagnostics"],
            ["same_market_different_code"],
        )

    def test_compare_runs_adds_different_market_market_code_comparison(self) -> None:
        service = RuleBacktestService(self.db)
        first_payload = self._compare_run_payload(run_id=101, code="600519")
        second_payload = self._compare_run_payload(run_id=202, code="AAPL")
        rows = [SimpleNamespace(id=101), SimpleNamespace(id=202)]

        with patch.object(service.repo, "get_runs_by_ids", return_value=rows), patch.object(
            service,
            "_run_row_to_dict",
            side_effect=[first_payload, second_payload],
        ):
            payload = service.compare_runs([101, 202])

        market_code_comparison = payload["market_code_comparison"]
        self.assertEqual(market_code_comparison["relationship"], "different_market")
        self.assertEqual(market_code_comparison["state"], "limited")
        self.assertFalse(market_code_comparison["directly_comparable"])
        self.assertEqual(market_code_comparison["pairs"][0]["relationship"], "different_market")
        self.assertEqual(market_code_comparison["pairs"][0]["baseline_market"], "cn")
        self.assertEqual(market_code_comparison["pairs"][0]["candidate_market"], "us")
        self.assertEqual(
            market_code_comparison["pairs"][0]["diagnostics"],
            ["different_market"],
        )

    def test_compare_runs_marks_partial_and_unavailable_market_code_metadata(self) -> None:
        service = RuleBacktestService(self.db)
        first_payload = self._compare_run_payload(run_id=101, code="600519")
        partial_payload = self._compare_run_payload(run_id=202, code="UNKNOWN-CODE")
        unavailable_payload = self._compare_run_payload(run_id=303, code="")
        rows = [SimpleNamespace(id=101), SimpleNamespace(id=202), SimpleNamespace(id=303)]

        with patch.object(service.repo, "get_runs_by_ids", return_value=rows), patch.object(
            service,
            "_run_row_to_dict",
            side_effect=[first_payload, partial_payload, unavailable_payload],
        ):
            payload = service.compare_runs([101, 202, 303])

        market_code_comparison = payload["market_code_comparison"]
        self.assertEqual(market_code_comparison["relationship"], "unavailable_metadata")
        self.assertEqual(market_code_comparison["state"], "limited")
        self.assertFalse(market_code_comparison["directly_comparable"])
        self.assertEqual(
            market_code_comparison["runs"],
            [
                {
                    "run_id": 101,
                    "code": "600519",
                    "normalized_code": "600519",
                    "market": "cn",
                    "availability": "complete",
                    "diagnostics": [],
                },
                {
                    "run_id": 202,
                    "code": "UNKNOWN-CODE",
                    "normalized_code": "UNKNOWN-CODE",
                    "market": None,
                    "availability": "partial",
                    "diagnostics": ["unrecognized_market_from_code"],
                },
                {
                    "run_id": 303,
                    "code": None,
                    "normalized_code": None,
                    "market": None,
                    "availability": "unavailable",
                    "diagnostics": ["missing_code"],
                },
            ],
        )
        self.assertEqual(market_code_comparison["pairs"][0]["relationship"], "partial_metadata")
        self.assertEqual(
            market_code_comparison["pairs"][0]["diagnostics"],
            ["candidate_market_unavailable", "partial_market_code_metadata"],
        )
        self.assertEqual(market_code_comparison["pairs"][1]["relationship"], "unavailable_metadata")
        self.assertEqual(
            market_code_comparison["pairs"][1]["diagnostics"],
            ["candidate_code_unavailable", "market_code_metadata_unavailable"],
        )
        self.assertEqual(
            market_code_comparison["diagnostics"],
            [
                "candidate_market_unavailable",
                "partial_market_code_metadata",
                "candidate_code_unavailable",
                "market_code_metadata_unavailable",
            ],
        )

    def test_build_compare_robustness_summary_marks_highly_comparable_when_dimensions_align(self) -> None:
        payload = RuleBacktestService._build_compare_robustness_summary(
            market_code_comparison={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "relationship": "same_code",
                "state": "direct",
                "directly_comparable": True,
                "diagnostics": ["same_normalized_code"],
            },
            period_comparison={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "relationship": "identical",
                "state": "comparable",
                "meaningfully_comparable": True,
                "diagnostics": ["identical_periods"],
            },
            comparison_summary={
                "baseline": {"run_id": 101, "selection_rule": "first_comparable_run_by_request_order"},
                "metric_deltas": {
                    "total_return_pct": {"state": "comparable"},
                    "annualized_return_pct": {"state": "comparable"},
                },
            },
            parameter_comparison={
                "state": "same_family_comparable",
                "shared_parameter_keys": ["strategy_spec.execution.signal_timing"],
                "differing_parameter_keys": ["strategy_spec.signal.fast_period"],
                "missing_parameter_keys": [],
            },
        )

        self.assertEqual(payload["overall_state"], "highly_comparable")
        self.assertTrue(payload["directly_comparable"])
        self.assertEqual(payload["aligned_dimensions"], ["market_code", "metrics_baseline", "parameter_set", "periods"])
        self.assertEqual(payload["partial_dimensions"], [])
        self.assertEqual(payload["divergent_dimensions"], [])
        self.assertEqual(payload["unavailable_dimensions"], [])
        self.assertEqual(payload["dimensions"]["market_code"]["state"], "aligned")
        self.assertEqual(payload["dimensions"]["metrics_baseline"]["state"], "aligned")
        self.assertEqual(payload["dimensions"]["parameter_set"]["state"], "aligned")
        self.assertEqual(payload["dimensions"]["periods"]["state"], "aligned")

    def test_build_compare_robustness_summary_marks_partially_comparable_when_dimensions_are_partial(self) -> None:
        payload = RuleBacktestService._build_compare_robustness_summary(
            market_code_comparison={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "relationship": "same_code",
                "state": "direct",
                "directly_comparable": True,
                "diagnostics": ["same_normalized_code"],
            },
            period_comparison={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "relationship": "partial",
                "state": "limited",
                "meaningfully_comparable": False,
                "diagnostics": ["missing_period_end"],
            },
            comparison_summary={
                "baseline": {"run_id": 101, "selection_rule": "first_comparable_run_by_request_order"},
                "metric_deltas": {
                    "total_return_pct": {"state": "comparable"},
                    "annualized_return_pct": {"state": "partial"},
                },
            },
            parameter_comparison={
                "state": "partial",
                "shared_parameter_keys": ["strategy_spec.execution.signal_timing"],
                "differing_parameter_keys": [],
                "missing_parameter_keys": ["strategy_spec.signal.slow_period"],
            },
        )

        self.assertEqual(payload["overall_state"], "partially_comparable")
        self.assertFalse(payload["directly_comparable"])
        self.assertEqual(payload["aligned_dimensions"], ["market_code"])
        self.assertEqual(payload["partial_dimensions"], ["metrics_baseline", "parameter_set", "periods"])
        self.assertEqual(payload["divergent_dimensions"], [])
        self.assertEqual(payload["unavailable_dimensions"], [])
        self.assertEqual(payload["dimensions"]["metrics_baseline"]["partial_metric_keys"], ["annualized_return_pct"])
        self.assertEqual(payload["dimensions"]["parameter_set"]["state"], "partial")
        self.assertEqual(payload["dimensions"]["periods"]["state"], "partial")

    def test_build_compare_robustness_summary_marks_context_limited_when_dimension_diverges(self) -> None:
        payload = RuleBacktestService._build_compare_robustness_summary(
            market_code_comparison={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "relationship": "different_market",
                "state": "limited",
                "directly_comparable": False,
                "diagnostics": ["different_market"],
            },
            period_comparison={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "relationship": "overlapping",
                "state": "comparable",
                "meaningfully_comparable": True,
                "diagnostics": ["overlapping_periods"],
            },
            comparison_summary={
                "baseline": {"run_id": 101, "selection_rule": "first_comparable_run_by_request_order"},
                "metric_deltas": {
                    "total_return_pct": {"state": "comparable"},
                },
            },
            parameter_comparison={
                "state": "different_family",
                "shared_parameter_keys": [],
                "differing_parameter_keys": [],
                "missing_parameter_keys": [],
            },
        )

        self.assertEqual(payload["overall_state"], "context_limited")
        self.assertFalse(payload["directly_comparable"])
        self.assertEqual(payload["divergent_dimensions"], ["market_code", "parameter_set"])
        self.assertEqual(payload["dimensions"]["market_code"]["state"], "divergent")
        self.assertEqual(payload["dimensions"]["parameter_set"]["state"], "divergent")

    def test_build_compare_robustness_summary_marks_insufficient_context_when_dimension_is_unavailable(self) -> None:
        payload = RuleBacktestService._build_compare_robustness_summary(
            market_code_comparison={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "relationship": "unavailable_metadata",
                "state": "limited",
                "directly_comparable": False,
                "diagnostics": ["market_code_metadata_unavailable"],
            },
            period_comparison={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "relationship": "unavailable",
                "state": "limited",
                "meaningfully_comparable": False,
                "diagnostics": ["period_metadata_unavailable"],
            },
            comparison_summary={
                "baseline": {"run_id": 101, "selection_rule": "first_comparable_run_by_request_order"},
                "metric_deltas": {
                    "total_return_pct": {"state": "unavailable"},
                    "annualized_return_pct": {"state": "baseline_unavailable"},
                },
            },
            parameter_comparison={
                "state": "unavailable",
                "shared_parameter_keys": [],
                "differing_parameter_keys": [],
                "missing_parameter_keys": [],
            },
        )

        self.assertEqual(payload["overall_state"], "insufficient_context")
        self.assertFalse(payload["directly_comparable"])
        self.assertEqual(payload["aligned_dimensions"], [])
        self.assertEqual(payload["partial_dimensions"], [])
        self.assertEqual(payload["divergent_dimensions"], [])
        self.assertEqual(
            payload["unavailable_dimensions"],
            ["market_code", "metrics_baseline", "parameter_set", "periods"],
        )
        self.assertEqual(payload["dimensions"]["metrics_baseline"]["unavailable_metric_keys"], ["annualized_return_pct", "total_return_pct"])
        self.assertEqual(payload["dimensions"]["market_code"]["state"], "unavailable")

    def test_build_compare_profile_summary_classifies_parameter_variants(self) -> None:
        payload = RuleBacktestService._build_compare_profile_summary(
            market_code_comparison={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "relationship": "same_code",
                "state": "direct",
                "directly_comparable": True,
                "diagnostics": ["same_normalized_code"],
            },
            period_comparison={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "relationship": "identical",
                "state": "comparable",
                "meaningfully_comparable": True,
                "diagnostics": ["identical_periods"],
            },
            parameter_comparison={
                "state": "same_family_comparable",
                "shared_parameter_keys": ["strategy_spec.execution.signal_timing"],
                "differing_parameter_keys": ["strategy_spec.signal.fast_period"],
                "missing_parameter_keys": [],
            },
            robustness_summary={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "overall_state": "highly_comparable",
                "aligned_dimensions": ["market_code", "metrics_baseline", "parameter_set", "periods"],
                "partial_dimensions": [],
                "divergent_dimensions": [],
                "unavailable_dimensions": [],
                "dimensions": {},
                "diagnostics": [],
            },
        )

        self.assertEqual(payload["primary_profile"], "same_strategy_parameter_variants")
        self.assertEqual(payload["aligned_dimensions"], ["market_code", "metrics_baseline", "parameter_set", "periods"])
        self.assertEqual(payload["driving_dimensions"], ["parameter_set"])
        self.assertTrue(payload["dimension_flags"]["same_code"])
        self.assertTrue(payload["dimension_flags"]["same_market"])
        self.assertTrue(payload["dimension_flags"]["same_strategy_family"])
        self.assertTrue(payload["dimension_flags"]["parameter_differences_present"])
        self.assertFalse(payload["dimension_flags"]["period_differences_present"])

    def test_build_compare_profile_summary_classifies_same_code_different_periods(self) -> None:
        payload = RuleBacktestService._build_compare_profile_summary(
            market_code_comparison={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "relationship": "same_code",
                "state": "direct",
                "directly_comparable": True,
                "diagnostics": ["same_normalized_code"],
            },
            period_comparison={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "relationship": "overlapping",
                "state": "comparable",
                "meaningfully_comparable": True,
                "diagnostics": ["overlapping_periods"],
            },
            parameter_comparison={
                "state": "same_family_comparable",
                "shared_parameter_keys": ["strategy_spec.execution.signal_timing"],
                "differing_parameter_keys": [],
                "missing_parameter_keys": [],
            },
            robustness_summary={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "overall_state": "highly_comparable",
                "aligned_dimensions": ["market_code", "metrics_baseline", "parameter_set", "periods"],
                "partial_dimensions": [],
                "divergent_dimensions": [],
                "unavailable_dimensions": [],
                "dimensions": {},
                "diagnostics": [],
            },
        )

        self.assertEqual(payload["primary_profile"], "same_code_different_periods")
        self.assertEqual(payload["driving_dimensions"], ["periods"])
        self.assertTrue(payload["dimension_flags"]["same_code"])
        self.assertTrue(payload["dimension_flags"]["period_differences_present"])

    def test_build_compare_profile_summary_classifies_same_market_cross_code(self) -> None:
        payload = RuleBacktestService._build_compare_profile_summary(
            market_code_comparison={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "relationship": "same_market_different_code",
                "state": "limited",
                "directly_comparable": False,
                "diagnostics": ["same_market_different_code"],
            },
            period_comparison={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "relationship": "identical",
                "state": "comparable",
                "meaningfully_comparable": True,
                "diagnostics": ["identical_periods"],
            },
            parameter_comparison={
                "state": "unavailable",
                "shared_parameter_keys": [],
                "differing_parameter_keys": [],
                "missing_parameter_keys": [],
            },
            robustness_summary={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "overall_state": "context_limited",
                "aligned_dimensions": ["metrics_baseline", "periods"],
                "partial_dimensions": [],
                "divergent_dimensions": ["market_code"],
                "unavailable_dimensions": ["parameter_set"],
                "dimensions": {},
                "diagnostics": ["same_market_different_code", "parameter_context_unavailable"],
            },
        )

        self.assertEqual(payload["primary_profile"], "same_market_cross_code")
        self.assertEqual(payload["driving_dimensions"], ["market_code"])
        self.assertFalse(payload["dimension_flags"]["same_code"])
        self.assertTrue(payload["dimension_flags"]["same_market"])
        self.assertFalse(payload["dimension_flags"]["cross_market"])

    def test_build_compare_profile_summary_classifies_mixed_context_when_no_single_mode_dominates(self) -> None:
        payload = RuleBacktestService._build_compare_profile_summary(
            market_code_comparison={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "relationship": "same_code",
                "state": "direct",
                "directly_comparable": True,
                "diagnostics": ["same_normalized_code"],
            },
            period_comparison={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "relationship": "identical",
                "state": "comparable",
                "meaningfully_comparable": True,
                "diagnostics": ["identical_periods"],
            },
            parameter_comparison={
                "state": "different_family",
                "shared_parameter_keys": [],
                "differing_parameter_keys": [],
                "missing_parameter_keys": [],
            },
            robustness_summary={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "overall_state": "context_limited",
                "aligned_dimensions": ["market_code", "metrics_baseline", "periods"],
                "partial_dimensions": [],
                "divergent_dimensions": ["parameter_set"],
                "unavailable_dimensions": [],
                "dimensions": {},
                "diagnostics": ["different_parameter_context"],
            },
        )

        self.assertEqual(payload["primary_profile"], "mixed_context")
        self.assertEqual(payload["driving_dimensions"], ["parameter_set"])
        self.assertEqual(payload["diagnostics"], ["different_parameter_context"])

    def test_build_compare_profile_summary_classifies_insufficient_context(self) -> None:
        payload = RuleBacktestService._build_compare_profile_summary(
            market_code_comparison={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "relationship": "unavailable_metadata",
                "state": "limited",
                "directly_comparable": False,
                "diagnostics": ["market_code_metadata_unavailable"],
            },
            period_comparison={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "relationship": "unavailable",
                "state": "limited",
                "meaningfully_comparable": False,
                "diagnostics": ["period_metadata_unavailable"],
            },
            parameter_comparison={
                "state": "unavailable",
                "shared_parameter_keys": [],
                "differing_parameter_keys": [],
                "missing_parameter_keys": [],
            },
            robustness_summary={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "overall_state": "insufficient_context",
                "aligned_dimensions": [],
                "partial_dimensions": [],
                "divergent_dimensions": [],
                "unavailable_dimensions": ["market_code", "metrics_baseline", "parameter_set", "periods"],
                "dimensions": {},
                "diagnostics": [
                    "market_code_metadata_unavailable",
                    "unavailable_metric_deltas",
                    "parameter_context_unavailable",
                    "period_metadata_unavailable",
                ],
            },
        )

        self.assertEqual(payload["primary_profile"], "insufficient_context")
        self.assertEqual(
            payload["driving_dimensions"],
            ["market_code", "metrics_baseline", "parameter_set", "periods"],
        )
        self.assertEqual(
            payload["diagnostics"],
            [
                "market_code_metadata_unavailable",
                "unavailable_metric_deltas",
                "parameter_context_unavailable",
                "period_metadata_unavailable",
            ],
        )

    def test_build_compare_highlights_summary_marks_clear_single_winners(self) -> None:
        payload = RuleBacktestService._build_compare_highlights_summary(
            comparison_summary={
                "baseline": {"run_id": 101, "selection_rule": "first_comparable_run_by_request_order"},
                "metric_deltas": {
                    "total_return_pct": {
                        "state": "comparable",
                        "available_run_ids": [101, 202],
                        "deltas": [
                            {"run_id": 101, "value": 10.0, "delta_vs_baseline": 0.0},
                            {"run_id": 202, "value": 15.0, "delta_vs_baseline": 5.0},
                        ],
                    },
                    "max_drawdown_pct": {
                        "state": "comparable",
                        "available_run_ids": [101, 202],
                        "deltas": [
                            {"run_id": 101, "value": 12.0, "delta_vs_baseline": 0.0},
                            {"run_id": 202, "value": 8.0, "delta_vs_baseline": -4.0},
                        ],
                    },
                },
            },
            robustness_summary={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "overall_state": "highly_comparable",
                "diagnostics": [],
            },
            comparison_profile={
                "primary_profile": "same_strategy_parameter_variants",
            },
        )

        self.assertEqual(payload["primary_profile"], "same_strategy_parameter_variants")
        self.assertEqual(payload["overall_context_state"], "highly_comparable")
        self.assertEqual(payload["highlights"]["total_return_pct"]["state"], "winner")
        self.assertEqual(payload["highlights"]["total_return_pct"]["winner_run_ids"], [202])
        self.assertEqual(payload["highlights"]["total_return_pct"]["winner_value"], 15.0)
        self.assertEqual(payload["highlights"]["max_drawdown_pct"]["state"], "winner")
        self.assertEqual(payload["highlights"]["max_drawdown_pct"]["winner_run_ids"], [202])
        self.assertEqual(payload["highlights"]["max_drawdown_pct"]["preference"], "lower_is_better")

    def test_build_compare_highlights_summary_marks_ties(self) -> None:
        payload = RuleBacktestService._build_compare_highlights_summary(
            comparison_summary={
                "baseline": {"run_id": 101, "selection_rule": "first_comparable_run_by_request_order"},
                "metric_deltas": {
                    "total_return_pct": {
                        "state": "comparable",
                        "available_run_ids": [101, 202],
                        "deltas": [
                            {"run_id": 101, "value": 15.0, "delta_vs_baseline": 0.0},
                            {"run_id": 202, "value": 15.0, "delta_vs_baseline": 0.0},
                        ],
                    },
                },
            },
            robustness_summary={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "overall_state": "highly_comparable",
                "diagnostics": [],
            },
            comparison_profile={
                "primary_profile": "same_strategy_parameter_variants",
            },
        )

        self.assertEqual(payload["highlights"]["total_return_pct"]["state"], "tie")
        self.assertEqual(payload["highlights"]["total_return_pct"]["winner_run_ids"], [101, 202])
        self.assertEqual(payload["highlights"]["total_return_pct"]["winner_value"], 15.0)

    def test_build_compare_highlights_summary_marks_limited_context_winners(self) -> None:
        payload = RuleBacktestService._build_compare_highlights_summary(
            comparison_summary={
                "baseline": {"run_id": 101, "selection_rule": "first_comparable_run_by_request_order"},
                "metric_deltas": {
                    "total_return_pct": {
                        "state": "comparable",
                        "available_run_ids": [101, 202],
                        "deltas": [
                            {"run_id": 101, "value": 10.0, "delta_vs_baseline": 0.0},
                            {"run_id": 202, "value": 12.0, "delta_vs_baseline": 2.0},
                        ],
                    },
                    "annualized_return_pct": {
                        "state": "partial",
                        "available_run_ids": [101],
                        "deltas": [
                            {"run_id": 101, "value": 8.0, "delta_vs_baseline": 0.0},
                        ],
                    },
                },
            },
            robustness_summary={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "overall_state": "context_limited",
                "diagnostics": ["different_parameter_context"],
            },
            comparison_profile={
                "primary_profile": "mixed_context",
            },
        )

        self.assertEqual(payload["highlights"]["total_return_pct"]["state"], "limited_context_winner")
        self.assertEqual(payload["highlights"]["total_return_pct"]["winner_run_ids"], [202])
        self.assertEqual(
            payload["highlights"]["total_return_pct"]["diagnostics"],
            ["context_limited_context", "profile_mixed_context"],
        )
        self.assertEqual(payload["highlights"]["annualized_return_pct"]["state"], "limited_context_winner")
        self.assertEqual(
            payload["highlights"]["annualized_return_pct"]["diagnostics"],
            ["partial_metric_availability", "context_limited_context", "profile_mixed_context"],
        )

    def test_build_compare_highlights_summary_marks_unavailable_metrics(self) -> None:
        payload = RuleBacktestService._build_compare_highlights_summary(
            comparison_summary={
                "baseline": {"run_id": 101, "selection_rule": "first_comparable_run_by_request_order"},
                "metric_deltas": {
                    "annualized_return_pct": {
                        "state": "unavailable",
                        "available_run_ids": [],
                        "deltas": [],
                    },
                    "benchmark_return_pct": {
                        "state": "baseline_unavailable",
                        "available_run_ids": [202],
                        "deltas": [
                            {"run_id": 202, "value": 3.0, "delta_vs_baseline": None},
                        ],
                    },
                },
            },
            robustness_summary={
                "baseline_run_id": 101,
                "selection_rule": "first_comparable_run_by_request_order",
                "overall_state": "insufficient_context",
                "diagnostics": ["unavailable_metric_deltas"],
            },
            comparison_profile={
                "primary_profile": "insufficient_context",
            },
        )

        self.assertEqual(payload["highlights"]["annualized_return_pct"]["state"], "unavailable")
        self.assertEqual(payload["highlights"]["annualized_return_pct"]["winner_run_ids"], [])
        self.assertEqual(
            payload["highlights"]["annualized_return_pct"]["diagnostics"],
            ["insufficient_compare_context"],
        )
        self.assertEqual(payload["highlights"]["benchmark_return_pct"]["state"], "unavailable")
        self.assertEqual(payload["highlights"]["benchmark_return_pct"]["winner_run_ids"], [])

    def test_periodic_trace_marks_skip_and_python_automation_can_auto_confirm(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None), patch.object(
            service,
            "_ensure_market_history",
            return_value=0,
        ):
            with self.assertRaises(ValueError):
                service.parse_and_run(
                    code="600519",
                    strategy_text="资金1500，从2024-01-05到2024-01-20，每天买100股ORCL，买到资金耗尽为止",
                    confirmed=False,
                )

            response = service.parse_and_run_automated(
                code="600519",
                strategy_text="资金1500，从2024-01-05到2024-01-20，每天买100股ORCL，买到资金耗尽为止",
                start_date="2024-01-05",
                end_date="2024-01-20",
                initial_capital=1500.0,
            )

        trace_rows = list(response["execution_trace"]["rows"])
        self.assertTrue(any(row.get("event_type") == "buy" for row in trace_rows))
        self.assertTrue(any(row.get("event_type") == "skip" for row in trace_rows))
        self.assertTrue(any("默认/推断" in str(row.get("assumptions_defaults") or "") for row in trace_rows))

    def test_execution_trace_marks_benchmark_fallback_without_recomputing_rows(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None), patch.object(
            service,
            "_load_external_benchmark_context",
            return_value=(
                [],
                {
                    "label": "沪深300",
                    "code": "000300.SH",
                    "method": "benchmark_security",
                    "requested_mode": "index_hs300",
                    "resolved_mode": "index_hs300",
                    "price_basis": "close",
                    "return_pct": None,
                    "unavailable_reason": "沪深300 在当前窗口没有可用行情。",
                },
                "沪深300 在当前窗口没有可用行情。",
            ),
        ):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                benchmark_mode="auto",
                confirmed=True,
            )

        self.assertTrue(response["execution_trace"]["fallback"]["run_fallback"])
        self.assertTrue(all(str(row.get("fallback") or "").strip() not in {"", "无"} for row in response["execution_trace"]["rows"]))

    def test_get_run_rebuilds_execution_trace_for_legacy_run_with_provenance(self) -> None:
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
        summary = json.loads(run_row.summary_json)
        summary.pop("execution_trace", None)
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(detail["execution_trace"]["source"], "rebuilt_from_stored_audit_rows")
        self.assertTrue(detail["execution_trace"]["fallback"]["trace_rebuilt"])
        self.assertTrue(all("历史运行回补trace" in str(row.get("fallback") or "") for row in detail["execution_trace"]["rows"]))
        self.assertEqual(detail["result_authority"]["execution_trace_source"], "rebuilt_from_stored_audit_rows")
        self.assertEqual(detail["result_authority"]["execution_trace_completeness"], "legacy_rebuilt")
        self.assertEqual(detail["result_authority"]["execution_trace_missing_fields"], ["stored_trace"])
        self.assertEqual(detail["result_authority"]["audit_rows_source"], "summary.visualization.audit_rows")

    def test_get_run_preserves_stored_empty_execution_trace_and_repairs_metadata(self) -> None:
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
        summary = json.loads(run_row.summary_json)
        summary["execution_trace"] = {
            "source": "summary.execution_trace",
            "rows": [],
        }
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(detail["execution_trace"]["rows"], [])
        self.assertEqual(detail["execution_trace"]["source"], "summary.execution_trace+repaired_fields")
        self.assertEqual(detail["execution_trace"]["completeness"], "stored_partial_repaired")
        self.assertIn("execution_model", detail["execution_trace"]["missing_fields"])
        self.assertIn("execution_assumptions", detail["execution_trace"]["missing_fields"])
        self.assertEqual(
            detail["result_authority"]["execution_trace_source"],
            "summary.execution_trace+repaired_fields",
        )
        self.assertEqual(detail["result_authority"]["execution_trace_completeness"], "stored_partial_repaired")
        self.assertIn("execution_model", detail["result_authority"]["execution_trace_missing_fields"])

    def test_get_run_marks_execution_trace_unavailable_when_trace_and_audit_rows_missing(self) -> None:
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
        summary = json.loads(run_row.summary_json)
        summary.pop("execution_trace", None)
        summary["visualization"]["audit_rows"] = []
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(detail["execution_trace"]["source"], "unavailable")
        self.assertEqual(detail["execution_trace"]["completeness"], "unavailable")
        self.assertEqual(detail["execution_trace"]["missing_fields"], ["stored_trace", "rows"])
        self.assertEqual(detail["execution_trace"]["rows"], [])
        self.assertEqual(detail["result_authority"]["execution_trace_source"], "unavailable")
        self.assertEqual(detail["result_authority"]["execution_trace_completeness"], "unavailable")
        self.assertEqual(
            detail["result_authority"]["execution_trace_missing_fields"],
            ["stored_trace", "rows"],
        )

    def test_get_run_marks_execution_model_as_derived_when_snapshot_missing(self) -> None:
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
        summary = json.loads(run_row.summary_json)
        summary.pop("execution_model", None)
        summary["request"].pop("execution_model", None)
        summary.pop("execution_assumptions_snapshot", None)
        summary["execution_assumptions"] = {
            "timeframe": "daily",
            "signal_evaluation_timing": "evaluate rules on each bar close",
            "entry_fill_timing": "next_bar_open",
            "exit_fill_timing": "next_bar_open; last openless bar falls back to same-bar close",
            "default_fill_price_basis": "open",
            "position_sizing": "single_position_full_notional",
            "fee_model": "bps_per_side",
            "fee_bps_per_side": 1.5,
            "slippage_model": "bps_per_side",
            "slippage_bps_per_side": 2.5,
        }
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(
            detail["result_authority"]["execution_model_source"],
            "derived_from_execution_assumptions_and_request",
        )
        self.assertEqual(
            detail["result_authority"]["execution_assumptions_source"],
            "summary.execution_assumptions+derived_defaults",
        )
        self.assertEqual(
            detail["result_authority"]["execution_assumptions_snapshot_completeness"],
            "legacy_partial_repaired",
        )
        self.assertIn(
            "benchmark_method",
            detail["result_authority"]["execution_assumptions_snapshot_missing_keys"],
        )
        self.assertEqual(
            detail["execution_assumptions_snapshot"]["source"],
            "summary.execution_assumptions+derived_defaults",
        )
        self.assertEqual(detail["execution_model"]["entry_timing"], "next_bar_open")

    def test_get_run_prefers_persisted_request_execution_model_when_summary_snapshot_missing(self) -> None:
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
        summary = json.loads(run_row.summary_json)
        summary.pop("execution_model", None)
        summary.pop("execution_assumptions_snapshot", None)
        summary.pop("execution_assumptions", None)
        summary["request"]["execution_model"] = {
            "version": "v1",
            "timeframe": "daily",
            "signal_evaluation_timing": "bar_close",
            "entry_timing": "next_bar_open",
            "exit_timing": "forced_close_at_window_end_close",
            "entry_fill_price_basis": "open",
            "exit_fill_price_basis": "close",
            "position_sizing": "single_position_full_notional",
            "fee_model": "bps_per_side",
            "fee_bps_per_side": 1.5,
            "slippage_model": "bps_per_side",
            "slippage_bps_per_side": 2.5,
            "market_rules": {
                "trading_day_execution": "available_bars_only",
                "terminal_bar_fill_fallback": "same_bar_close",
                "window_end_position_handling": "force_flatten",
            },
        }
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(
            detail["result_authority"]["execution_model_source"],
            "summary.request.execution_model",
        )
        self.assertEqual(
            detail["result_authority"]["execution_model_completeness"],
            "complete",
        )
        self.assertEqual(detail["result_authority"]["execution_model_missing_fields"], [])
        self.assertEqual(
            detail["result_authority"]["domains"]["execution_model"],
            {
                "source": "summary.request.execution_model",
                "completeness": "complete",
                "state": "available",
                "missing": [],
                "missing_kind": "fields",
            },
        )
        self.assertEqual(detail["execution_model"]["exit_timing"], "forced_close_at_window_end_close")
        self.assertEqual(detail["execution_model"]["exit_fill_price_basis"], "close")
        self.assertEqual(detail["execution_model"]["fee_bps_per_side"], 1.5)

    def test_get_run_repairs_partial_stored_execution_model_with_provenance(self) -> None:
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
        summary = json.loads(run_row.summary_json)
        summary["execution_model"] = {
            "version": "v1",
            "timeframe": "daily",
            "entry_timing": "same_bar_open",
            "fee_bps_per_side": 4.2,
            "market_rules": {
                "trading_day_execution": "available_bars_only",
            },
        }
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(
            detail["result_authority"]["execution_model_source"],
            "summary.execution_model+repaired_fields",
        )
        self.assertEqual(
            detail["result_authority"]["execution_model_completeness"],
            "stored_partial_repaired",
        )
        self.assertEqual(
            detail["result_authority"]["execution_model_missing_fields"],
            [
                "signal_evaluation_timing",
                "exit_timing",
                "entry_fill_price_basis",
                "exit_fill_price_basis",
                "position_sizing",
                "fee_model",
                "slippage_model",
                "slippage_bps_per_side",
                "market_rules.terminal_bar_fill_fallback",
                "market_rules.window_end_position_handling",
            ],
        )
        self.assertEqual(detail["execution_model"]["entry_timing"], "same_bar_open")
        self.assertEqual(detail["execution_model"]["signal_evaluation_timing"], "bar_close")
        self.assertEqual(
            detail["execution_model"]["market_rules"]["terminal_bar_fill_fallback"],
            "same_bar_close",
        )
        self.assertEqual(
            detail["result_authority"]["domains"]["execution_model"],
            {
                "source": "summary.execution_model+repaired_fields",
                "completeness": "stored_partial_repaired",
                "state": "available",
                "missing": [
                    "signal_evaluation_timing",
                    "exit_timing",
                    "entry_fill_price_basis",
                    "exit_fill_price_basis",
                    "position_sizing",
                    "fee_model",
                    "slippage_model",
                    "slippage_bps_per_side",
                    "market_rules.terminal_bar_fill_fallback",
                    "market_rules.window_end_position_handling",
                ],
                "missing_kind": "fields",
            },
        )

    def test_get_run_prefers_stored_execution_assumptions_snapshot_for_reopen(self) -> None:
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
        summary = json.loads(run_row.summary_json)
        summary["execution_assumptions_snapshot"] = {
            "version": "v1",
            "source": "summary.execution_assumptions_snapshot",
            "completeness": "complete",
            "missing_keys": [],
            "payload": {
                "timeframe": "daily",
                "indicator_price_basis": "hlc3",
                "signal_evaluation_timing": "bar_close",
                "entry_fill_timing": "next_bar_open",
                "exit_fill_timing": "next_bar_open; same_bar_close",
                "default_fill_price_basis": "open",
                "position_sizing": "single_position_full_notional",
                "fee_model": "bps_per_side",
                "fee_bps_per_side": 1.25,
                "slippage_model": "bps_per_side",
                "slippage_bps_per_side": 3.5,
                "benchmark_method": "custom_snapshot_authority",
                "benchmark_price_basis": "close",
            },
        }
        summary.pop("execution_assumptions", None)
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(
            detail["result_authority"]["execution_assumptions_source"],
            "summary.execution_assumptions_snapshot",
        )
        self.assertEqual(detail["execution_assumptions"]["indicator_price_basis"], "hlc3")
        self.assertEqual(detail["execution_assumptions"]["benchmark_method"], "custom_snapshot_authority")
        self.assertEqual(
            detail["execution_assumptions_snapshot"]["payload"]["indicator_price_basis"],
            "hlc3",
        )

    def test_module_level_run_backtest_automated_exports_trace_files(self) -> None:
        with patch.object(RuleBacktestService, "_ensure_market_history", return_value=0), patch.object(
            RuleBacktestService,
            "_get_llm_adapter",
            return_value=None,
        ):
            result = run_backtest_automated(
                symbol="600519",
                scenario="cash_insufficiency_skip",
                initial_capital=1500.0,
                output_dir=self._temp_dir.name,
            )

        self.assertTrue(os.path.exists(result["csv_path"]))
        self.assertTrue(os.path.exists(result["json_path"]))
        self.assertEqual(result["scenario"], "cash_insufficiency_skip")

    def test_service_persists_explicit_benchmark_unavailable_reason_without_fabricated_returns(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None), patch.object(
            service,
            "_load_external_benchmark_context",
            return_value=(
                [],
                {
                    "label": "沪深300",
                    "code": "000300.SH",
                    "method": "benchmark_security",
                    "requested_mode": "index_hs300",
                    "resolved_mode": "index_hs300",
                    "price_basis": "close",
                    "return_pct": None,
                    "unavailable_reason": "沪深300 在当前窗口没有可用行情。",
                },
                "沪深300 在当前窗口没有可用行情。",
            ),
        ):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                benchmark_mode="index_hs300",
                confirmed=True,
            )

        comparison = response["summary"]["visualization"].get("comparison") or {}
        self.assertEqual(response["benchmark_summary"]["resolved_mode"], "index_hs300")
        self.assertIn("沪深300", response["benchmark_summary"]["unavailable_reason"])
        self.assertEqual(response["benchmark_curve"], [])
        self.assertIsNone(response["benchmark_return_pct"])
        self.assertIsNotNone(response["buy_and_hold_return_pct"])
        self.assertEqual(comparison.get("benchmark_summary"), response["benchmark_summary"])
        self.assertIsNone(comparison.get("metrics", {}).get("benchmark_return_pct"))
        self.assertEqual(
            comparison.get("metrics", {}).get("buy_and_hold_return_pct"),
            response["buy_and_hold_return_pct"],
        )

    def test_engine_executes_moving_average_crossover_from_normalized_spec(self) -> None:
        service = RuleBacktestService(self.db)
        bars = self._make_bars([10, 9.8, 9.6, 9.4, 9.2, 9.4, 9.8, 10.2, 10.8, 11.2, 11.6, 11.1, 10.7, 10.2, 9.8, 9.4, 9.0, 9.3, 9.7, 10.1, 10.5, 10.9, 11.3, 11.7, 12.1, 11.6, 11.0, 10.4, 9.8, 9.2])
        parsed_dict = service.parse_strategy(
            "5日均线上穿20日均线买入，下穿卖出",
            code="TEST",
            start_date="2024-01-01",
            end_date="2024-01-30",
            initial_capital=100000,
        )
        parsed = service._dict_to_parsed_strategy(parsed_dict, parsed_dict["source_text"])
        engine = RuleBacktestEngine()

        result = engine.run(
            code="TEST",
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=100000.0,
            lookback_bars=30,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 30),
        )

        self.assertGreater(result.metrics["trade_count"], 0)
        self.assertGreater(len(result.equity_curve), 0)
        self.assertEqual(result.parsed_strategy.strategy_spec["strategy_type"], "moving_average_crossover")

    def test_engine_executes_macd_crossover_from_normalized_spec(self) -> None:
        service = RuleBacktestService(self.db)
        bars = self._make_bars([10, 10.1, 10.2, 10.4, 10.7, 11.1, 11.5, 11.8, 12.0, 11.7, 11.2, 10.8, 10.4, 10.0, 9.7, 9.5, 9.8, 10.2, 10.7, 11.2, 11.8, 12.3, 12.6, 12.2, 11.7, 11.1, 10.6, 10.2, 9.9, 9.6, 9.9, 10.4, 10.9, 11.4, 11.9, 12.4, 12.8, 12.3, 11.7, 11.0])
        parsed_dict = service.parse_strategy(
            "MACD金叉买入，死叉卖出",
            code="TEST",
            start_date="2024-01-01",
            end_date="2024-02-09",
            initial_capital=100000,
        )
        parsed = service._dict_to_parsed_strategy(parsed_dict, parsed_dict["source_text"])
        engine = RuleBacktestEngine()

        result = engine.run(
            code="TEST",
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=100000.0,
            lookback_bars=40,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 9),
        )

        self.assertGreater(result.metrics["trade_count"], 0)
        self.assertGreater(len(result.equity_curve), 0)
        self.assertEqual(result.parsed_strategy.strategy_spec["strategy_type"], "macd_crossover")

    def test_engine_exits_indicator_position_when_fixed_stop_loss_triggers(self) -> None:
        service = RuleBacktestService(self.db)
        bars = self._make_bars([10.0, 9.0, 8.0, 7.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 10.0, 9.0, 8.0, 7.0], start=date(2024, 1, 1))
        parsed_dict = service.parse_strategy(
            "3日均线上穿5日均线买入，止损5%，下穿卖出",
            code="TEST",
            start_date="2024-01-01",
            end_date="2024-01-14",
            initial_capital=100000,
        )
        parsed = service._dict_to_parsed_strategy(parsed_dict, parsed_dict["source_text"])
        engine = RuleBacktestEngine()

        result = engine.run(
            code="TEST",
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=100000.0,
            lookback_bars=14,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 14),
        )

        self.assertGreater(result.metrics["trade_count"], 0)
        self.assertEqual(result.parsed_strategy.strategy_spec["risk_controls"]["stop_loss_pct"], 5.0)
        self.assertEqual(result.trades[0].exit_trigger, "FIXED_STOP_LOSS_5%")
        self.assertLess(result.trades[0].exit_date, date(2024, 1, 14))

    def test_engine_exits_indicator_position_when_take_profit_triggers(self) -> None:
        service = RuleBacktestService(self.db)
        bars = self._make_bars([10.0, 9.0, 8.0, 7.0, 6.0, 7.0, 8.0, 9.0, 10.0, 12.0, 13.0, 12.0, 11.0], start=date(2024, 1, 1))
        parsed_dict = service.parse_strategy(
            "3日均线上穿5日均线买入，止盈10%，下穿卖出",
            code="TEST",
            start_date="2024-01-01",
            end_date="2024-01-13",
            initial_capital=100000,
        )
        parsed = service._dict_to_parsed_strategy(parsed_dict, parsed_dict["source_text"])
        engine = RuleBacktestEngine()

        result = engine.run(
            code="TEST",
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=100000.0,
            lookback_bars=13,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 13),
        )

        self.assertGreater(result.metrics["trade_count"], 0)
        self.assertEqual(result.parsed_strategy.strategy_spec["risk_controls"]["take_profit_pct"], 10.0)
        self.assertEqual(result.trades[0].exit_trigger, "TAKE_PROFIT_10%")
        self.assertLess(result.trades[0].exit_date, date(2024, 1, 13))

    def test_engine_exits_indicator_position_when_trailing_stop_triggers(self) -> None:
        service = RuleBacktestService(self.db)
        bars = self._make_bars([10.0, 9.0, 8.0, 7.0, 6.0, 7.0, 8.0, 9.0, 10.0, 12.0, 14.0, 13.0, 12.0, 11.0], start=date(2024, 1, 1))
        parsed_dict = service.parse_strategy(
            "3日均线上穿5日均线买入，移动止损8%，下穿卖出",
            code="TEST",
            start_date="2024-01-01",
            end_date="2024-01-14",
            initial_capital=100000,
        )
        parsed = service._dict_to_parsed_strategy(parsed_dict, parsed_dict["source_text"])
        engine = RuleBacktestEngine()

        result = engine.run(
            code="TEST",
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=100000.0,
            lookback_bars=14,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 14),
        )

        self.assertGreater(result.metrics["trade_count"], 0)
        self.assertEqual(result.parsed_strategy.strategy_spec["risk_controls"]["trailing_stop_pct"], 8.0)
        self.assertEqual(result.trades[0].exit_trigger, "TRAILING_STOP_8%")

    def test_engine_executes_rsi_threshold_from_normalized_spec(self) -> None:
        service = RuleBacktestService(self.db)
        bars = self._make_bars([10, 11, 12, 13, 14, 15, 14, 13, 12, 11, 10, 9, 8, 9, 10, 11, 12, 13, 14, 15, 14, 13, 12, 11, 10, 9, 8, 9, 10, 11, 12, 13])
        parsed_dict = service.parse_strategy(
            "RSI6 小于 30 买入，RSI6 大于 70 卖出",
            code="TEST",
            start_date="2024-01-01",
            end_date="2024-02-01",
            initial_capital=100000,
        )
        parsed = service._dict_to_parsed_strategy(parsed_dict, parsed_dict["source_text"])
        engine = RuleBacktestEngine()

        result = engine.run(
            code="TEST",
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=100000.0,
            lookback_bars=32,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 1),
        )

        self.assertGreater(result.metrics["trade_count"], 0)
        self.assertGreater(len(result.equity_curve), 0)
        self.assertEqual(result.parsed_strategy.strategy_spec["strategy_type"], "rsi_threshold")

    def test_engine_executes_new_classic_template_strategies_from_catalog_text(self) -> None:
        service = RuleBacktestService(self.db)
        engine = RuleBacktestEngine()
        cases = [
            {
                "strategy_type": "bollinger_breakout",
                "text": "收盘价突破布林带上轨买入，跌回中轨卖出",
                "closes": [10.0, 10.1, 10.0, 10.2, 10.1, 10.0, 10.2, 10.1, 10.0, 10.2, 10.1, 10.0, 10.2, 10.1, 10.0, 10.3, 10.7, 11.1, 11.4, 11.0, 10.7, 10.4, 10.1, 9.9, 10.2, 10.5, 10.8, 10.6, 10.3, 10.0],
            },
            {
                "strategy_type": "atr_breakout",
                "text": "ATR14 扩张且价格突破前高时买入，跌回突破位下方卖出",
                "closes": [10.0, 10.02, 10.01, 10.03, 10.02, 10.01, 10.03, 10.02, 10.01, 10.04, 10.03, 10.02, 10.08, 10.7, 11.4, 12.0, 11.6, 11.1, 10.7, 10.2, 10.0, 10.4, 10.9, 11.2, 10.8, 10.4, 10.1],
            },
            {
                "strategy_type": "obv_trend_confirmation",
                "text": "价格站上均线且 OBV 同步创新高时买入，OBV 转弱时卖出",
                "closes": [10.0, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9, 11.0, 11.2, 11.5, 11.8, 12.1, 12.3, 12.0, 11.7, 11.3, 11.0, 10.7, 10.5, 10.8, 11.0],
                "volumes": [100, 105, 110, 115, 120, 125, 130, 140, 150, 160, 170, 220, 260, 300, 340, 360, 180, 160, 140, 120, 110, 100, 130, 150],
            },
            {
                "strategy_type": "support_resistance_bounce",
                "text": "回踩支撑企稳买入，接近阻力位卖出",
                "closes": [12.0, 11.6, 11.2, 10.8, 10.3, 10.0, 10.2, 10.6, 11.0, 11.4, 11.8, 12.0, 11.7, 11.3, 10.9, 10.4, 10.1, 10.0, 10.3, 10.7, 11.1, 11.5, 11.9, 11.6],
            },
            {
                "strategy_type": "macd_rsi_combo",
                "text": "MACD金叉且RSI14上穿50买入，任一信号走弱卖出",
                "closes": [10.0, 9.8, 9.6, 9.5, 9.4, 9.5, 9.7, 10.0, 10.4, 10.9, 11.3, 11.7, 12.0, 11.8, 11.4, 11.0, 10.6, 10.3, 10.0, 9.8, 10.0, 10.3, 10.7, 11.0],
            },
            {
                "strategy_type": "sma_bollinger_combo",
                "text": "SMA20 在 SMA60 上方且价格重回布林带中轨上方时买入",
                "closes": [10.0, 10.1, 10.2, 10.4, 10.5, 10.7, 10.8, 11.0, 11.1, 11.2, 11.4, 11.5, 11.7, 11.8, 11.9, 12.0, 12.1, 12.2, 12.3, 12.4, 12.2, 12.0, 11.8, 11.9, 12.1, 12.4, 12.7, 12.5, 12.2, 11.9],
            },
            {
                "strategy_type": "trend_momentum_volume_mix",
                "text": "均线多头、RSI 强势且放量突破同时出现时买入",
                "closes": [10.0, 10.1, 10.3, 10.4, 10.6, 10.7, 10.9, 11.0, 11.2, 11.3, 11.5, 11.6, 11.8, 11.9, 12.1, 12.2, 12.4, 12.5, 12.7, 12.8, 13.3, 13.7, 14.0, 13.8, 13.4, 13.0, 12.7, 12.9],
                "volumes": [100, 100, 105, 110, 110, 115, 120, 120, 125, 130, 130, 135, 140, 145, 145, 150, 155, 160, 160, 165, 320, 360, 340, 200, 180, 160, 150, 155],
            },
            {
                "strategy_type": "multi_indicator_trend_filter",
                "text": "价格位于长期均线上方、MACD 为正且波动率扩张时才允许入场",
                "closes": [10.0, 10.1, 10.2, 10.4, 10.5, 10.7, 10.8, 11.0, 11.1, 11.3, 11.4, 11.6, 11.7, 11.9, 12.0, 12.2, 12.3, 12.5, 12.7, 12.8, 13.1, 13.5, 13.9, 14.2, 13.8, 13.3, 12.9, 12.6],
            },
            {
                "strategy_type": "bollinger_rsi_reversion_combo",
                "text": "价格跌破布林带下轨且 RSI2 低于10时买入，回到中轨或 RSI 回到60卖出",
                "closes": [12.0, 12.1, 12.2, 12.1, 12.0, 11.9, 11.8, 11.6, 11.3, 10.9, 10.4, 10.0, 9.7, 9.5, 9.8, 10.2, 10.7, 11.1, 11.4, 11.7, 11.5, 11.2, 11.0],
            },
            {
                "strategy_type": "triple_moving_average_trend_stack",
                "text": "SMA20 大于 SMA60 且 SMA60 大于 SMA120，价格回踩 SMA20 转强时买入",
                "closes": [10.0, 10.1, 10.2, 10.4, 10.5, 10.7, 10.8, 11.0, 11.1, 11.3, 11.4, 11.6, 11.7, 11.9, 12.0, 12.2, 12.3, 12.5, 12.6, 12.8, 12.6, 12.4, 12.2, 12.3, 12.6, 12.9, 13.2, 13.0, 12.7, 12.4],
            },
            {
                "strategy_type": "support_resistance_macd_combo",
                "text": "价格在支撑位企稳且 MACD 金叉时买入，接近阻力位或 MACD 死叉时卖出",
                "closes": [12.0, 11.6, 11.1, 10.7, 10.2, 10.0, 10.1, 10.4, 10.8, 11.2, 11.7, 12.0, 11.8, 11.4, 10.9, 10.5, 10.1, 10.0, 10.2, 10.6, 11.0, 11.5, 11.9, 11.6],
            },
            {
                "strategy_type": "vwap_volume_breakout_combo",
                "text": "价格重回 VWAP 上方且突破平台高点并放量时买入，跌回 VWAP 下方卖出",
                "closes": [10.0, 9.9, 10.0, 10.1, 10.2, 10.1, 10.0, 10.1, 10.2, 10.1, 10.2, 10.3, 10.4, 10.3, 10.4, 10.5, 10.6, 10.8, 11.2, 11.6, 11.9, 11.7, 11.4, 11.0, 10.7],
                "volumes": [120, 118, 122, 125, 128, 126, 124, 126, 128, 130, 132, 134, 136, 138, 140, 142, 145, 150, 320, 360, 340, 220, 180, 160, 150],
            },
        ]

        for case in cases:
            with self.subTest(strategy_type=case["strategy_type"]):
                closes = case["closes"]
                bars = self._make_bars(
                    closes,
                    volumes=case.get("volumes"),
                )
                parsed_dict = service.parse_strategy(
                    case["text"],
                    code="TEST",
                    start_date="2024-01-01",
                    end_date=(date(2024, 1, 1) + timedelta(days=len(closes) - 1)).isoformat(),
                    initial_capital=100000,
                )
                parsed = service._dict_to_parsed_strategy(parsed_dict, parsed_dict["source_text"])

                result = engine.run(
                    code="TEST",
                    parsed_strategy=parsed,
                    bars=bars,
                    initial_capital=100000.0,
                    lookback_bars=len(closes),
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 1, 1) + timedelta(days=len(closes) - 1),
                )

                self.assertEqual(result.parsed_strategy.strategy_spec["strategy_type"], case["strategy_type"])
                self.assertTrue(result.parsed_strategy.executable)
                self.assertGreater(len(result.equity_curve), 0)
                self.assertIn(result.no_result_reason, {None, "no_trades", "no_entry_signals"})
                self.assertIn("final_equity", result.metrics)
                self.assertIn("total_return_pct", result.metrics)

    def test_engine_handles_single_day_window_for_periodic_accumulation(self) -> None:
        service = RuleBacktestService(self.db)
        bars = self._make_bars([10, 10.2, 10.4, 10.6, 10.8, 11.0, 11.2, 11.4])
        parsed_dict = service.parse_strategy(
            "资金10000，从2024-01-01到2024-01-08，每天买1000元TEST，买到区间结束",
            code="TEST",
            start_date="2024-01-01",
            end_date="2024-01-08",
            initial_capital=10000,
        )
        parsed = service._dict_to_parsed_strategy(parsed_dict, parsed_dict["source_text"])
        engine = RuleBacktestEngine()

        result = engine.run(
            code="TEST",
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=10000.0,
            lookback_bars=8,
            start_date=date(2024, 1, 8),
            end_date=date(2024, 1, 8),
        )

        self.assertEqual(result.metrics["period_start"], "2024-01-08")
        self.assertEqual(result.metrics["period_end"], "2024-01-08")
        self.assertEqual(result.metrics["bars_used"], 1)
        self.assertEqual(len(result.equity_curve), 1)
        self.assertEqual(result.metrics["trade_count"], 1)

    def test_engine_skips_fixed_amount_accumulation_when_remaining_cash_is_below_target(self) -> None:
        service = RuleBacktestService(self.db)
        bars = self._make_bars([10, 10.1, 10.2], start=date(2024, 1, 1))
        parsed_dict = service.parse_strategy(
            "资金1000，从2024-01-01到2024-01-03，每天买600元TEST，买到区间结束",
            code="TEST",
            start_date="2024-01-01",
            end_date="2024-01-03",
            initial_capital=1000,
        )
        parsed = service._dict_to_parsed_strategy(parsed_dict, parsed_dict["source_text"])
        engine = RuleBacktestEngine()

        result = engine.run(
            code="TEST",
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=1000.0,
            lookback_bars=3,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 3),
        )

        self.assertEqual(result.parsed_strategy.strategy_spec["entry"]["order"]["mode"], "fixed_amount")
        self.assertEqual([point.executed_action for point in result.equity_curve], ["accumulate", None, "forced_close"])
        self.assertEqual(result.equity_curve[1].notes, "skip_buy_when_insufficient_cash")
        self.assertEqual(result.equity_curve[1].signal_summary, "现金不足，跳过本次计划买入")
        self.assertEqual(result.metrics["trade_count"], 1)
        self.assertEqual(result.metrics["entry_signal_count"], 3)
        self.assertEqual(result.trades[0].entry_indicators["shares"], 60.606061)

    def test_engine_stops_fixed_amount_accumulation_when_cash_policy_requires_stop(self) -> None:
        service = RuleBacktestService(self.db)
        bars = self._make_bars([10, 10.1, 10.2], start=date(2024, 1, 1))
        parsed_dict = service.parse_strategy(
            "资金1000，从2024-01-01到2024-01-03，每天买600元TEST，买到资金耗尽为止",
            code="TEST",
            start_date="2024-01-01",
            end_date="2024-01-03",
            initial_capital=1000,
        )
        parsed = service._dict_to_parsed_strategy(parsed_dict, parsed_dict["source_text"])
        engine = RuleBacktestEngine()

        result = engine.run(
            code="TEST",
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=1000.0,
            lookback_bars=3,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 3),
        )

        self.assertEqual(result.parsed_strategy.strategy_spec["position_behavior"]["cash_policy"], "stop_when_insufficient_cash")
        self.assertEqual([point.executed_action for point in result.equity_curve], ["accumulate", None, "forced_close"])
        self.assertEqual(result.equity_curve[1].notes, "stop_buying_when_insufficient_cash")
        self.assertEqual(result.equity_curve[1].signal_summary, "现金不足，后续停止继续买入")
        self.assertEqual(result.metrics["trade_count"], 1)
        self.assertEqual(result.metrics["entry_signal_count"], 2)
        self.assertEqual(result.trades[0].entry_indicators["shares"], 60.606061)

    def test_engine_handles_single_day_window_for_moving_average_crossover(self) -> None:
        service = RuleBacktestService(self.db)
        bars = self._make_bars([10, 9.8, 9.6, 9.4, 9.2, 9.4, 9.8, 10.2, 10.8, 11.2, 11.6, 11.1, 10.7, 10.2, 9.8, 9.4, 9.0, 9.3, 9.7, 10.1, 10.5, 10.9, 11.3, 11.7, 12.1, 11.6, 11.0, 10.4, 9.8, 9.2])
        parsed_dict = service.parse_strategy(
            "5日均线上穿20日均线买入，下穿卖出",
            code="TEST",
            start_date="2024-01-01",
            end_date="2024-01-30",
            initial_capital=100000,
        )
        parsed = service._dict_to_parsed_strategy(parsed_dict, parsed_dict["source_text"])
        engine = RuleBacktestEngine()

        result = engine.run(
            code="TEST",
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=100000.0,
            lookback_bars=30,
            start_date=date(2024, 1, 30),
            end_date=date(2024, 1, 30),
        )

        self.assertEqual(result.metrics["period_start"], "2024-01-30")
        self.assertEqual(result.metrics["period_end"], "2024-01-30")
        self.assertEqual(result.metrics["bars_used"], 1)
        self.assertEqual(len(result.equity_curve), 1)
        self.assertEqual(result.metrics["trade_count"], 0)
        self.assertIn(result.no_result_reason, {"no_entry_signals", "no_trades"})

    def test_engine_handles_single_day_window_for_macd_crossover(self) -> None:
        service = RuleBacktestService(self.db)
        bars = self._make_bars([10, 10.1, 10.2, 10.4, 10.7, 11.1, 11.5, 11.8, 12.0, 11.7, 11.2, 10.8, 10.4, 10.0, 9.7, 9.5, 9.8, 10.2, 10.7, 11.2, 11.8, 12.3, 12.6, 12.2, 11.7, 11.1, 10.6, 10.2, 9.9, 9.6, 9.9, 10.4, 10.9, 11.4, 11.9, 12.4, 12.8, 12.3, 11.7, 11.0])
        parsed_dict = service.parse_strategy(
            "MACD金叉买入，死叉卖出",
            code="TEST",
            start_date="2024-01-01",
            end_date="2024-02-09",
            initial_capital=100000,
        )
        parsed = service._dict_to_parsed_strategy(parsed_dict, parsed_dict["source_text"])
        engine = RuleBacktestEngine()

        result = engine.run(
            code="TEST",
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=100000.0,
            lookback_bars=40,
            start_date=date(2024, 2, 9),
            end_date=date(2024, 2, 9),
        )

        self.assertEqual(result.metrics["period_start"], "2024-02-09")
        self.assertEqual(result.metrics["period_end"], "2024-02-09")
        self.assertEqual(result.metrics["bars_used"], 1)
        self.assertEqual(len(result.equity_curve), 1)
        self.assertEqual(result.metrics["trade_count"], 0)
        self.assertIn(result.no_result_reason, {"no_entry_signals", "no_trades"})

    def test_engine_handles_single_day_window_for_rsi_threshold(self) -> None:
        service = RuleBacktestService(self.db)
        bars = self._make_bars([10, 11, 12, 13, 14, 15, 14, 13, 12, 11, 10, 9, 8, 9, 10, 11, 12, 13, 14, 15, 14, 13, 12, 11, 10, 9, 8, 9, 10, 11, 12, 13])
        parsed_dict = service.parse_strategy(
            "RSI6 小于 30 买入，RSI6 大于 70 卖出",
            code="TEST",
            start_date="2024-01-01",
            end_date="2024-02-01",
            initial_capital=100000,
        )
        parsed = service._dict_to_parsed_strategy(parsed_dict, parsed_dict["source_text"])
        engine = RuleBacktestEngine()

        result = engine.run(
            code="TEST",
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=100000.0,
            lookback_bars=32,
            start_date=date(2024, 2, 1),
            end_date=date(2024, 2, 1),
        )

        self.assertEqual(result.metrics["period_start"], "2024-02-01")
        self.assertEqual(result.metrics["period_end"], "2024-02-01")
        self.assertEqual(result.metrics["bars_used"], 1)
        self.assertEqual(len(result.equity_curve), 1)
        self.assertEqual(result.metrics["trade_count"], 0)
        self.assertIn(result.no_result_reason, {"no_entry_signals", "no_trades"})

    def test_text_completion_facade_forwards_call_text_arguments(self) -> None:
        captured = {}

        class FakeAdapter:
            def call_text(self, messages, *, temperature, max_tokens):
                captured["messages"] = messages
                captured["temperature"] = temperature
                captured["max_tokens"] = max_tokens
                return SimpleNamespace(content="ok")

        completion = create_rule_backtest_text_completion(adapter=FakeAdapter())
        assert completion is not None

        response = completion.call_text(
            [{"role": "user", "content": "hello"}],
            temperature=0.2,
            max_tokens=700,
        )

        self.assertEqual(response.content, "ok")
        self.assertEqual(captured["messages"], [{"role": "user", "content": "hello"}])
        self.assertEqual(captured["temperature"], 0.2)
        self.assertEqual(captured["max_tokens"], 700)

    def test_text_completion_service_preserves_parser_and_summary_call_args(self) -> None:
        parser_calls = []
        summary_calls = []

        class FakeTextCompletion:
            def call_text(self, messages, *, temperature, max_tokens):
                if temperature == 0 and max_tokens == 900:
                    parser_calls.append(
                        {
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                        }
                    )
                    return SimpleNamespace(
                        content=json.dumps(
                            {
                                "version": "v1",
                                "timeframe": "daily",
                                "entry": {
                                    "type": "comparison",
                                    "left": {"kind": "indicator", "indicator": "close"},
                                    "compare": ">",
                                    "right": {"kind": "indicator", "indicator": "ma", "period": 3},
                                    "text": "Close > MA3",
                                },
                                "exit": {
                                    "type": "comparison",
                                    "left": {"kind": "indicator", "indicator": "close"},
                                    "compare": "<",
                                    "right": {"kind": "indicator", "indicator": "ma", "period": 3},
                                    "text": "Close < MA3",
                                },
                                "confidence": 0.88,
                                "needs_confirmation": False,
                                "ambiguities": [],
                                "summary": {
                                    "entry": "买入条件：Close > MA3",
                                    "exit": "卖出条件：Close < MA3",
                                    "strategy": "价格突破均线",
                                },
                            },
                            ensure_ascii=False,
                        )
                    )
                if temperature == 0.2 and max_tokens == 700:
                    summary_calls.append(
                        {
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                        }
                    )
                    return SimpleNamespace(content="LLM summary")
                raise AssertionError(f"Unexpected text completion call: temperature={temperature}, max_tokens={max_tokens}")

        service = RuleBacktestService(self.db, llm_adapter=FakeTextCompletion())
        with patch.object(service.parser, "_parse_expression", return_value=(None, {"issues": [], "issue_count": 0})):
            service.parse_strategy("Momentum breakout idea.", code="600519")
        self.assertEqual(len(parser_calls), 1)
        self.assertEqual(parser_calls[0]["temperature"], 0)
        self.assertEqual(parser_calls[0]["max_tokens"], 900)

        response = service.parse_and_run(
            code="600519",
            strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
            lookback_bars=20,
            confirmed=True,
        )

        self.assertEqual(response["ai_summary"], "LLM summary")
        self.assertEqual(len(summary_calls), 1)
        self.assertEqual(summary_calls[0]["temperature"], 0.2)
        self.assertEqual(summary_calls[0]["max_tokens"], 700)

    def test_service_generates_fallback_ai_summary_and_persists_runs(self) -> None:
        service = RuleBacktestService(self.db)
        strategy_text = "Buy when Close > MA3. Sell when Close < MA3."

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text=strategy_text,
                lookback_bars=20,
                confirmed=True,
            )

        self.assertGreater(response["trade_count"], 0)
        self.assertIn("总收益", response["ai_summary"])

        history = service.list_runs(code="600519", page=1, limit=10)
        self.assertEqual(history["total"], 1)
        self.assertEqual(history["items"][0]["trade_count"], response["trade_count"])
        self.assertIn("buy_and_hold_return_pct", history["items"][0])
        self.assertIn("benchmark_curve", history["items"][0])
        self.assertIn("benchmark_summary", history["items"][0])
        self.assertIn("execution_model", history["items"][0])
        self.assertIn("execution_assumptions", history["items"][0])
        self.assertEqual(history["items"][0]["result_authority"]["contract_version"], "v1")
        self.assertEqual(history["items"][0]["result_authority"]["summary_source"], "row.summary_json")
        self.assertEqual(history["items"][0]["result_authority"]["summary_completeness"], "complete")
        self.assertEqual(history["items"][0]["result_authority"]["summary_missing_fields"], [])
        self.assertEqual(history["items"][0]["result_authority"]["parsed_strategy_source"], "row.parsed_strategy_json")
        self.assertEqual(history["items"][0]["result_authority"]["parsed_strategy_completeness"], "complete")
        self.assertEqual(history["items"][0]["result_authority"]["parsed_strategy_missing_fields"], [])
        self.assertEqual(history["items"][0]["result_authority"]["replay_payload_source"], "omitted_without_detail_read")
        self.assertEqual(history["items"][0]["result_authority"]["replay_payload_completeness"], "omitted")
        self.assertEqual(history["items"][0]["result_authority"]["replay_payload_missing_sections"], [])
        self.assertEqual(history["items"][0]["result_authority"]["trade_rows_source"], "omitted_without_detail_read")
        self.assertEqual(history["items"][0]["result_authority"]["trade_rows_completeness"], "omitted")
        self.assertEqual(history["items"][0]["result_authority"]["trade_rows_missing_fields"], [])
        self.assertEqual(history["items"][0]["result_authority"]["equity_curve_source"], "omitted_without_detail_read")
        self.assertEqual(history["items"][0]["result_authority"]["equity_curve_completeness"], "omitted")
        self.assertEqual(history["items"][0]["result_authority"]["equity_curve_missing_fields"], [])
        self.assertEqual(history["items"][0]["result_authority"]["execution_trace_source"], "omitted_without_detail_read")
        self.assertEqual(history["items"][0]["result_authority"]["execution_trace_completeness"], "omitted")
        self.assertEqual(history["items"][0]["result_authority"]["execution_trace_missing_fields"], [])
        self.assertEqual(history["items"][0]["artifact_availability"]["source"], "summary.artifact_availability")
        self.assertTrue(history["items"][0]["artifact_availability"]["has_trade_rows"])
        self.assertTrue(history["items"][0]["artifact_availability"]["has_execution_trace"])
        self.assertEqual(
            history["items"][0]["summary"]["artifact_availability"],
            history["items"][0]["artifact_availability"],
        )
        self.assertEqual(
            history["items"][0]["result_authority"]["domains"]["parsed_strategy"],
            {
                "source": "row.parsed_strategy_json",
                "completeness": "complete",
                "state": "available",
                "missing": [],
                "missing_kind": "fields",
            },
        )
        self.assertEqual(
            history["items"][0]["result_authority"]["domains"]["summary"],
            {
                "source": "row.summary_json",
                "completeness": "complete",
                "state": "available",
                "missing": [],
                "missing_kind": "fields",
            },
        )
        self.assertEqual(
            history["items"][0]["result_authority"]["domains"]["replay_payload"],
            {
                "source": "omitted_without_detail_read",
                "completeness": "omitted",
                "state": "omitted",
                "missing": [],
                "missing_kind": "sections",
            },
        )
        self.assertEqual(
            history["items"][0]["result_authority"]["domains"]["trade_rows"],
            {
                "source": "omitted_without_detail_read",
                "completeness": "omitted",
                "state": "omitted",
                "missing": [],
                "missing_kind": "fields",
            },
        )
        self.assertEqual(
            history["items"][0]["result_authority"]["domains"]["equity_curve"],
            {
                "source": "omitted_without_detail_read",
                "completeness": "omitted",
                "state": "omitted",
                "missing": [],
                "missing_kind": "fields",
            },
        )
        self.assertEqual(
            history["items"][0]["result_authority"]["domains"]["execution_trace"],
            {
                "source": "omitted_without_detail_read",
                "completeness": "omitted",
                "state": "omitted",
                "missing": [],
                "missing_kind": "fields",
            },
        )

    def test_get_run_marks_partial_stored_trade_rows_with_explicit_repair_provenance(self) -> None:
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
        stored_trade_rows = service.repo.get_trades_by_run(run_row.id)
        self.assertGreater(len(stored_trade_rows), 0)

        with self.db.get_session() as session:
            trade_row = session.execute(
                select(RuleBacktestTrade)
                .where(RuleBacktestTrade.id == stored_trade_rows[0].id)
                .limit(1)
            ).scalar_one()
            trade_row.entry_rule_json = None
            trade_row.exit_rule_json = None
            trade_row.notes = None
            session.commit()

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertGreater(len(detail["trades"]), 0)
        self.assertEqual(
            detail["result_authority"]["trade_rows_source"],
            "stored_rule_backtest_trades+compat_repair",
        )
        self.assertEqual(
            detail["result_authority"]["trade_rows_completeness"],
            "stored_partial_repaired",
        )
        self.assertIn("entry_rule", detail["result_authority"]["trade_rows_missing_fields"])
        self.assertIn("exit_rule", detail["result_authority"]["trade_rows_missing_fields"])
        self.assertIn("entry_fill_basis", detail["result_authority"]["trade_rows_missing_fields"])
        self.assertEqual(
            detail["result_authority"]["domains"]["trade_rows"],
            {
                "source": "stored_rule_backtest_trades+compat_repair",
                "completeness": "stored_partial_repaired",
                "state": "available",
                "missing": detail["result_authority"]["trade_rows_missing_fields"],
                "missing_kind": "fields",
            },
        )
        self.assertEqual(detail["trades"][0]["entry_rule"], {})
        self.assertEqual(detail["trades"][0]["exit_rule"], {})
        self.assertEqual(detail["trades"][0]["entry_trigger"], detail["trades"][0]["entry_signal"])
        self.assertEqual(detail["trades"][0]["exit_trigger"], detail["trades"][0]["exit_signal"])

    def test_get_run_marks_trade_rows_unavailable_when_persisted_rows_are_missing(self) -> None:
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
        deleted = service.repo.delete_trades_by_run_ids([run_row.id])
        self.assertGreater(deleted, 0)

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(detail["trades"], [])
        self.assertEqual(detail["trade_count"], response["trade_count"])
        self.assertEqual(detail["result_authority"]["trade_rows_source"], "unavailable")
        self.assertEqual(detail["result_authority"]["trade_rows_completeness"], "unavailable")
        self.assertEqual(
            detail["result_authority"]["trade_rows_missing_fields"],
            ["stored_trade_rows"],
        )
        self.assertEqual(
            detail["result_authority"]["domains"]["trade_rows"],
            {
                "source": "unavailable",
                "completeness": "unavailable",
                "state": "unavailable",
                "missing": ["stored_trade_rows"],
                "missing_kind": "fields",
            },
        )
        self.assertEqual(
            detail["artifact_availability"]["source"],
            "summary.artifact_availability+live_storage_repair",
        )
        self.assertEqual(detail["artifact_availability"]["completeness"], "stored_partial_repaired")
        self.assertFalse(detail["artifact_availability"]["has_trade_rows"])
        self.assertEqual(detail["summary"]["artifact_availability"], detail["artifact_availability"])
        self.assertEqual(
            detail["readback_integrity"]["source"],
            "derived_from_result_authority+live_storage_repair",
        )
        self.assertEqual(detail["readback_integrity"]["completeness"], "stored_partial_repaired")
        self.assertFalse(detail["readback_integrity"]["used_legacy_fallback"])
        self.assertTrue(detail["readback_integrity"]["used_live_storage_repair"])
        self.assertTrue(detail["readback_integrity"]["has_summary_storage_drift"])
        self.assertEqual(detail["readback_integrity"]["drift_domains"], ["trade_rows"])
        self.assertEqual(detail["readback_integrity"]["integrity_level"], "drift_repaired")
        self.assertEqual(detail["summary"]["readback_integrity"], detail["readback_integrity"])

        status = service.get_run_status(run_row.id)
        assert status is not None
        self.assertFalse(status["artifact_availability"]["has_trade_rows"])
        self.assertEqual(
            status["artifact_availability"]["source"],
            "summary.artifact_availability+live_storage_repair",
        )
        self.assertEqual(
            status["readback_integrity"]["source"],
            "derived_from_status_summary+live_storage_repair",
        )
        self.assertTrue(status["readback_integrity"]["used_live_storage_repair"])
        self.assertEqual(status["readback_integrity"]["drift_domains"], ["trade_rows"])

        history = service.list_runs(code="600519", page=1, limit=10)
        self.assertFalse(history["items"][0]["artifact_availability"]["has_trade_rows"])
        self.assertEqual(
            history["items"][0]["artifact_availability"]["source"],
            "summary.artifact_availability+live_storage_repair",
        )
        self.assertEqual(
            history["items"][0]["readback_integrity"]["source"],
            "derived_from_result_authority+live_storage_repair",
        )
        self.assertTrue(history["items"][0]["readback_integrity"]["used_live_storage_repair"])
        self.assertEqual(history["items"][0]["readback_integrity"]["drift_domains"], ["trade_rows"])

    def test_support_bundle_manifest_export_preserves_live_storage_repair_summary(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )

        deleted = service.repo.delete_trades_by_run_ids([response["id"]])
        self.assertGreater(deleted, 0)

        manifest_path = os.path.join(self._temp_dir.name, "support_bundle_manifest_drift.json")
        service.export_support_bundle_manifest_json(run_id=response["id"], output_path=manifest_path)

        with open(manifest_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)

        self.assertFalse(payload["artifact_availability"]["has_trade_rows"])
        self.assertEqual(
            payload["artifact_availability"]["source"],
            "summary.artifact_availability+live_storage_repair",
        )
        self.assertTrue(payload["readback_integrity"]["used_live_storage_repair"])
        self.assertTrue(payload["readback_integrity"]["has_summary_storage_drift"])
        self.assertEqual(payload["readback_integrity"]["drift_domains"], ["trade_rows"])
        self.assertEqual(payload["readback_integrity"]["integrity_level"], "drift_repaired")
        self.assertEqual(payload["artifact_counts"]["trade_rows_count"], 0)
        self.assertEqual(
            payload["result_authority"]["domains"]["trade_rows"]["source"],
            "unavailable",
        )

    def test_reproducibility_manifest_preserves_live_storage_repair_summary(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )

        deleted = service.repo.delete_trades_by_run_ids([response["id"]])
        self.assertGreater(deleted, 0)

        payload = service.get_support_bundle_reproducibility_manifest(response["id"])

        self.assertFalse(payload["artifact_availability"]["has_trade_rows"])
        self.assertEqual(
            payload["artifact_availability"]["source"],
            "summary.artifact_availability+live_storage_repair",
        )
        self.assertTrue(payload["readback_integrity"]["used_live_storage_repair"])
        self.assertTrue(payload["readback_integrity"]["has_summary_storage_drift"])
        self.assertEqual(payload["readback_integrity"]["drift_domains"], ["trade_rows"])
        self.assertEqual(payload["readback_integrity"]["integrity_level"], "drift_repaired")
        self.assertEqual(payload["result_authority"]["domains"]["trade_rows"]["source"], "unavailable")
        self.assertTrue(payload["execution_assumptions_fingerprint"]["hash_sha256"])

    def test_support_export_index_truthfully_marks_missing_trace_exports_unavailable(self) -> None:
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
        summary = json.loads(run_row.summary_json)
        summary["execution_trace"] = {}
        summary["visualization"] = dict(summary.get("visualization") or {})
        summary["visualization"]["audit_rows"] = []
        summary["visualization"]["daily_return_series"] = []
        summary["visualization"]["exposure_curve"] = []
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        self._assert_support_bundle_export_contract(service=service, run_id=response["id"])

    def test_get_run_repairs_partial_stored_parsed_strategy_with_provenance(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy(
            "MACD金叉买入，死叉卖出",
            code="600519",
            start_date="2024-01-08",
            end_date="2024-01-18",
            initial_capital=100000.0,
        )

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.run_backtest(
                code="600519",
                strategy_text=parsed["source_text"],
                parsed_strategy=parsed,
                start_date="2024-01-08",
                end_date="2024-01-18",
                lookback_bars=20,
                confirmed=True,
            )

        run_row = service.repo.get_run(response["id"])
        assert run_row is not None
        service.repo.update_run(
            run_row.id,
            parsed_strategy_json=service._serialize_json(
                {
                    "version": "v1",
                    "timeframe": "daily",
                    "source_text": parsed["source_text"],
                    "normalized_text": parsed["normalized_text"],
                    "summary": parsed["summary"],
                    "strategy_kind": "macd_crossover",
                    "setup": {
                        "symbol": "600519",
                        "indicator_family": "macd",
                        "fast_period": 12,
                        "slow_period": 26,
                        "signal_period": 9,
                    },
                    "strategy_spec": {},
                }
            ),
        )

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(detail["parsed_strategy"]["strategy_kind"], "macd_crossover")
        self.assertEqual(detail["parsed_strategy"]["strategy_spec"]["strategy_type"], "macd_crossover")
        self.assertEqual(detail["parsed_strategy"]["strategy_spec"]["signal"]["fast_period"], 12)
        self.assertEqual(
            detail["result_authority"]["parsed_strategy_source"],
            "row.parsed_strategy_json+repaired_fields",
        )
        self.assertEqual(
            detail["result_authority"]["parsed_strategy_completeness"],
            "stored_partial_repaired",
        )
        self.assertIn("entry", detail["result_authority"]["parsed_strategy_missing_fields"])
        self.assertIn("executable", detail["result_authority"]["parsed_strategy_missing_fields"])
        self.assertIn("strategy_spec.strategy_type", detail["result_authority"]["parsed_strategy_missing_fields"])
        self.assertIn(
            "strategy_spec.signal.fast_period",
            detail["result_authority"]["parsed_strategy_missing_fields"],
        )
        self.assertEqual(
            detail["result_authority"]["domains"]["parsed_strategy"]["source"],
            "row.parsed_strategy_json+repaired_fields",
        )

    def test_get_run_uses_summary_parsed_strategy_fallback_when_snapshot_missing(self) -> None:
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
        service.repo.update_run(run_row.id, parsed_strategy_json="")

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(detail["parsed_strategy"]["source_text"], response["strategy_text"])
        self.assertEqual(
            detail["parsed_strategy"]["summary"]["entry"],
            response["parsed_strategy"]["summary"]["entry"],
        )
        self.assertEqual(
            detail["result_authority"]["parsed_strategy_source"],
            "summary.parsed_strategy_summary+row_defaults",
        )
        self.assertEqual(
            detail["result_authority"]["parsed_strategy_completeness"],
            "legacy_summary_only",
        )
        self.assertIn(
            "strategy_spec.strategy_type",
            detail["result_authority"]["parsed_strategy_missing_fields"],
        )

    def test_get_run_marks_parsed_strategy_unavailable_when_snapshot_and_summary_missing(self) -> None:
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
        summary = json.loads(run_row.summary_json)
        summary.pop("parsed_strategy_summary", None)
        service.repo.update_run(
            run_row.id,
            summary_json=service._serialize_json(summary),
            parsed_strategy_json="",
        )

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(detail["parsed_strategy"]["normalization_state"], "unavailable")
        self.assertEqual(detail["result_authority"]["parsed_strategy_source"], "unavailable")
        self.assertEqual(detail["result_authority"]["parsed_strategy_completeness"], "unavailable")
        self.assertEqual(
            detail["result_authority"]["parsed_strategy_missing_fields"],
            ["stored_parsed_strategy"],
        )

    def test_get_run_repairs_partial_stored_summary_with_provenance(self) -> None:
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
        service.repo.update_run(
            run_row.id,
            summary_json=service._serialize_json(
                {
                    "request": {
                        "lookback_bars": 20,
                    },
                    "status_history": [
                        {
                            "status": "completed",
                            "at": run_row.completed_at.isoformat() if run_row.completed_at else None,
                        }
                    ],
                    "metrics": {
                        "trade_count": 7,
                    },
                }
            ),
        )

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(detail["summary"]["request"]["lookback_bars"], 20)
        self.assertEqual(detail["summary"]["request"]["initial_capital"], response["initial_capital"])
        self.assertEqual(
            detail["summary"]["parsed_strategy_summary"]["entry"],
            response["parsed_strategy"]["summary"]["entry"],
        )
        self.assertEqual(
            detail["summary"]["execution_model"]["entry_timing"],
            detail["execution_model"]["entry_timing"],
        )
        self.assertIn("comparison", detail["summary"]["visualization"])
        self.assertEqual(
            detail["result_authority"]["summary_source"],
            "row.summary_json+repaired_fields",
        )
        self.assertEqual(
            detail["result_authority"]["summary_completeness"],
            "stored_partial_repaired",
        )
        self.assertIn("request.initial_capital", detail["result_authority"]["summary_missing_fields"])
        self.assertIn("parsed_strategy_summary", detail["result_authority"]["summary_missing_fields"])
        self.assertIn("execution_model", detail["result_authority"]["summary_missing_fields"])
        self.assertIn("visualization", detail["result_authority"]["summary_missing_fields"])
        self.assertEqual(
            detail["result_authority"]["domains"]["summary"]["source"],
            "row.summary_json+repaired_fields",
        )

    def test_get_run_derives_summary_from_stored_domains_when_snapshot_missing(self) -> None:
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
        service.repo.update_run(run_row.id, summary_json="")

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(detail["summary"]["request"]["lookback_bars"], response["lookback_bars"])
        self.assertEqual(detail["summary"]["request"]["initial_capital"], response["initial_capital"])
        self.assertEqual(
            detail["summary"]["parsed_strategy_summary"]["entry"],
            response["parsed_strategy"]["summary"]["entry"],
        )
        self.assertEqual(detail["summary"]["metrics"]["trade_count"], response["trade_count"])
        self.assertEqual(detail["summary"]["execution_model"]["entry_timing"], detail["execution_model"]["entry_timing"])
        self.assertEqual(detail["summary"]["ai_summary"], response["ai_summary"])
        self.assertEqual(
            detail["result_authority"]["summary_source"],
            "derived_from_stored_domains+row_columns",
        )
        self.assertEqual(
            detail["result_authority"]["summary_completeness"],
            "legacy_derived",
        )
        self.assertIn("stored_summary", detail["result_authority"]["summary_missing_fields"])
        self.assertIn("request.start_date", detail["result_authority"]["summary_missing_fields"])
        self.assertIn("status_message", detail["result_authority"]["summary_missing_fields"])
        self.assertEqual(
            detail["readback_integrity"]["source"],
            "derived_from_result_authority+legacy_fallback",
        )
        self.assertEqual(detail["readback_integrity"]["completeness"], "legacy_derived")
        self.assertTrue(detail["readback_integrity"]["used_legacy_fallback"])
        self.assertFalse(detail["readback_integrity"]["used_live_storage_repair"])
        self.assertFalse(detail["readback_integrity"]["has_summary_storage_drift"])
        self.assertEqual(detail["readback_integrity"]["integrity_level"], "legacy_fallback")
        self.assertEqual(
            detail["readback_integrity"]["missing_summary_fields"],
            detail["result_authority"]["summary_missing_fields"],
        )

    def test_get_run_repairs_partial_stored_equity_curve_with_provenance(self) -> None:
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
        stored_curve = json.loads(run_row.equity_curve_json)
        self.assertGreater(len(stored_curve), 0)
        stored_curve[0] = {
            "date": stored_curve[0]["date"],
            "total_portfolio_value": stored_curve[0]["total_portfolio_value"],
            "cumulative_return_pct": stored_curve[0]["cumulative_return_pct"],
            "drawdown_pct": stored_curve[0]["drawdown_pct"],
            "close": stored_curve[0]["close"],
            "action": stored_curve[0]["executed_action"],
            "shares": stored_curve[0]["shares_held"],
            "cash": stored_curve[0]["cash"],
            "holdings_value": stored_curve[0]["holdings_value"],
            "position": stored_curve[0]["exposure_pct"],
            "fees": stored_curve[0]["fee_amount"],
            "slippage": stored_curve[0]["slippage_amount"],
            "notes": stored_curve[0]["notes"],
        }
        service.repo.update_run(
            run_row.id,
            equity_curve_json=service._serialize_json(stored_curve),
        )

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertGreater(len(detail["equity_curve"]), 0)
        repaired_point = detail["equity_curve"][0]
        self.assertIn("equity", repaired_point)
        self.assertIn("total_portfolio_value", repaired_point)
        self.assertIn("executed_action", repaired_point)
        self.assertIn("shares_held", repaired_point)
        self.assertIn("exposure_pct", repaired_point)
        self.assertEqual(
            detail["result_authority"]["equity_curve_source"],
            "row.equity_curve_json+repaired_fields",
        )
        self.assertEqual(
            detail["result_authority"]["equity_curve_completeness"],
            "stored_partial_repaired",
        )
        self.assertIn("equity", detail["result_authority"]["equity_curve_missing_fields"])
        self.assertIn("executed_action", detail["result_authority"]["equity_curve_missing_fields"])
        self.assertIn("shares_held", detail["result_authority"]["equity_curve_missing_fields"])
        self.assertEqual(
            detail["result_authority"]["domains"]["equity_curve"]["source"],
            "row.equity_curve_json+repaired_fields",
        )

    def test_get_run_derives_equity_curve_from_stored_audit_rows_when_snapshot_missing(self) -> None:
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
        service.repo.update_run(run_row.id, equity_curve_json=None)

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertGreater(len(detail["equity_curve"]), 0)
        self.assertEqual(
            detail["result_authority"]["equity_curve_source"],
            "derived_from_summary.visualization.audit_rows",
        )
        self.assertEqual(
            detail["result_authority"]["equity_curve_completeness"],
            "legacy_rebuilt",
        )
        self.assertEqual(detail["result_authority"]["equity_curve_missing_fields"], [])
        self.assertEqual(
            detail["result_authority"]["domains"]["equity_curve"],
            {
                "source": "derived_from_summary.visualization.audit_rows",
                "completeness": "legacy_rebuilt",
                "state": "available",
                "missing": [],
                "missing_kind": "fields",
            },
        )
        self.assertIn("equity", detail["equity_curve"][0])
        self.assertIn("total_portfolio_value", detail["equity_curve"][0])

    def test_get_run_marks_equity_curve_unavailable_when_snapshot_and_audit_rows_missing(self) -> None:
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
        summary = json.loads(run_row.summary_json)
        summary["visualization"]["audit_rows"] = []
        service.repo.update_run(
            run_row.id,
            summary_json=service._serialize_json(summary),
            equity_curve_json=None,
        )

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(detail["equity_curve"], [])
        self.assertEqual(detail["result_authority"]["equity_curve_source"], "unavailable")
        self.assertEqual(detail["result_authority"]["equity_curve_completeness"], "unavailable")
        self.assertEqual(
            detail["result_authority"]["equity_curve_missing_fields"],
            ["stored_equity_curve"],
        )

    def test_service_persists_requested_date_range_and_period(self) -> None:
        service = RuleBacktestService(self.db)
        strategy_text = "Buy when Close > MA3. Sell when Close < MA3."

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text=strategy_text,
                lookback_bars=20,
                confirmed=True,
            )
            ranged = service.run_backtest(
                code="600519",
                strategy_text=strategy_text,
                parsed_strategy=response["parsed_strategy"],
                start_date="2024-01-08",
                end_date="2024-01-18",
                lookback_bars=20,
                confirmed=True,
            )

        self.assertEqual(ranged["start_date"], "2024-01-08")
        self.assertEqual(ranged["end_date"], "2024-01-18")
        self.assertEqual(ranged["period_start"], "2024-01-08")
        self.assertEqual(ranged["period_end"], "2024-01-18")
        self.assertEqual(ranged["summary"]["request"]["start_date"], "2024-01-08")
        self.assertEqual(ranged["summary"]["request"]["end_date"], "2024-01-18")
        self.assertTrue(all((point.get("date") or "") >= "2024-01-08" for point in ranged["equity_curve"]))
        self.assertTrue(all((point.get("date") or "") <= "2024-01-18" for point in ranged["equity_curve"]))
        self.assertTrue(all((point.get("date") or "") >= "2024-01-08" for point in ranged["benchmark_curve"]))
        self.assertTrue(all((point.get("date") or "") <= "2024-01-18" for point in ranged["benchmark_curve"]))
        self.assertTrue(all((point.get("date") or "") >= "2024-01-08" for point in ranged["daily_return_series"]))
        self.assertTrue(all((point.get("date") or "") <= "2024-01-18" for point in ranged["daily_return_series"]))

    def test_submit_and_process_backtest_records_async_status_history(self) -> None:
        service = RuleBacktestService(self.db)
        strategy_text = "Buy when Close > MA3. Sell when Close < MA3."

        with patch.object(service, "_get_llm_adapter", return_value=None):
            submitted = service.submit_backtest(
                code="600519",
                strategy_text=strategy_text,
                start_date="2024-01-08",
                end_date="2024-01-18",
                lookback_bars=20,
                confirmed=True,
            )

            self.assertIn(submitted["status"], {"parsing", "queued"})
            self.assertGreaterEqual(len(submitted["status_history"]), 1)

            service.process_submitted_run(submitted["id"])

        detail = service.get_run(submitted["id"])
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail["status"], "completed")
        self.assertGreaterEqual(len(detail["status_history"]), 3)
        self.assertEqual(detail["summary"]["request"]["lookback_bars"], 20)
        self.assertEqual(detail["summary"]["request"]["start_date"], "2024-01-08")
        self.assertEqual(detail["summary"]["request"]["end_date"], "2024-01-18")
        self.assertEqual(detail["summary"]["request"]["confirmed"], True)
        self.assertEqual(detail["start_date"], "2024-01-08")
        self.assertEqual(detail["end_date"], "2024-01-18")
        self.assertIn("execution_assumptions", detail["summary"])
        statuses = [item.get("status") for item in detail["status_history"]]
        self.assertIn("running", statuses)
        self.assertIn("summarizing", statuses)
        self.assertIn("completed", statuses)
        self.assertIn("buy_and_hold_return_pct", detail)
        self.assertIn("excess_return_vs_buy_and_hold_pct", detail)
        self.assertIn("benchmark_curve", detail)
        self.assertIn("benchmark_summary", detail)
        self.assertIn("audit_rows", detail)

    def test_failed_and_cancelled_runs_expose_structured_run_diagnostics(self) -> None:
        service = RuleBacktestService(self.db)
        strategy_text = "Buy when Close > MA3. Sell when Close < MA3."

        cancelled = service.submit_backtest(
            code="600519",
            strategy_text=strategy_text,
            start_date="2024-01-08",
            end_date="2024-01-18",
            lookback_bars=20,
            confirmed=True,
        )
        cancelled_status = service.cancel_run(cancelled["id"])
        self.assertIsNotNone(cancelled_status)
        assert cancelled_status is not None
        self.assertEqual(cancelled_status["status"], "cancelled")
        self.assertEqual(cancelled_status["run_diagnostics"]["terminal_status"], "cancelled")
        self.assertEqual(cancelled_status["run_diagnostics"]["reason_code"], "cancelled")
        self.assertEqual(cancelled_status["run_diagnostics"]["last_non_terminal_status"], "parsing")
        self.assertEqual(cancelled_status["readback_integrity"]["source"], "stored_status_summary")
        self.assertEqual(cancelled_status["readback_integrity"]["integrity_level"], "stored_complete")
        self.assertFalse(cancelled_status["readback_integrity"]["used_legacy_fallback"])
        self.assertFalse(cancelled_status["readback_integrity"]["used_live_storage_repair"])

        with patch.object(service, "parse_strategy", side_effect=RuntimeError("parse boom")):
            failed = service.submit_backtest(
                code="600519",
                strategy_text=strategy_text,
                start_date="2024-01-08",
                end_date="2024-01-18",
                lookback_bars=20,
                confirmed=True,
            )
            service.process_submitted_run(failed["id"])

        failed_status = service.get_run_status(failed["id"])
        self.assertIsNotNone(failed_status)
        assert failed_status is not None
        self.assertEqual(failed_status["status"], "failed")
        self.assertEqual(failed_status["run_diagnostics"]["terminal_status"], "failed")
        self.assertEqual(failed_status["run_diagnostics"]["reason_code"], "execution_failed")
        self.assertEqual(failed_status["run_diagnostics"]["last_non_terminal_status"], "parsing")
        self.assertIn("parse boom", failed_status["run_diagnostics"]["message"])
        self.assertEqual(failed_status["readback_integrity"]["source"], "stored_status_summary")
        self.assertEqual(failed_status["readback_integrity"]["integrity_level"], "stored_complete")

        failed_detail = service.get_run(failed["id"])
        self.assertIsNotNone(failed_detail)
        assert failed_detail is not None
        self.assertEqual(failed_detail["run_diagnostics"]["terminal_status"], "failed")
        self.assertEqual(failed_detail["summary"]["run_diagnostics"]["terminal_status"], "failed")

        history = service.list_runs(code="600519", page=1, limit=10)
        by_status = {item["status"]: item for item in history["items"]}
        self.assertEqual(by_status["cancelled"]["run_diagnostics"]["terminal_status"], "cancelled")
        self.assertEqual(by_status["failed"]["run_diagnostics"]["terminal_status"], "failed")

    def test_failed_and_cancelled_runs_expose_structured_run_timing(self) -> None:
        service = RuleBacktestService(self.db)
        strategy_text = "Buy when Close > MA3. Sell when Close < MA3."

        cancelled = service.submit_backtest(
            code="600519",
            strategy_text=strategy_text,
            start_date="2024-01-08",
            end_date="2024-01-18",
            lookback_bars=20,
            confirmed=True,
        )
        cancelled_status = service.cancel_run(cancelled["id"])
        self.assertIsNotNone(cancelled_status)
        assert cancelled_status is not None
        self.assertEqual(cancelled_status["run_timing"]["created_at"], cancelled_status["run_at"])
        self.assertEqual(cancelled_status["run_timing"]["cancelled_at"], cancelled_status["completed_at"])
        self.assertEqual(cancelled_status["run_timing"]["finished_at"], cancelled_status["completed_at"])
        self.assertIsNone(cancelled_status["run_timing"]["started_at"])
        self.assertIsNone(cancelled_status["run_timing"]["queue_duration_seconds"])

        with patch.object(service, "parse_strategy", side_effect=RuntimeError("parse boom")):
            failed = service.submit_backtest(
                code="600519",
                strategy_text=strategy_text,
                start_date="2024-01-08",
                end_date="2024-01-18",
                lookback_bars=20,
                confirmed=True,
            )
            service.process_submitted_run(failed["id"])

        failed_detail = service.get_run(failed["id"])
        self.assertIsNotNone(failed_detail)
        assert failed_detail is not None
        self.assertEqual(failed_detail["run_timing"]["created_at"], failed_detail["run_at"])
        self.assertEqual(failed_detail["run_timing"]["failed_at"], failed_detail["completed_at"])
        self.assertEqual(failed_detail["run_timing"]["finished_at"], failed_detail["completed_at"])
        self.assertIsNone(failed_detail["run_timing"]["started_at"])
        self.assertIsNone(failed_detail["run_timing"]["run_duration_seconds"])
        self.assertEqual(failed_detail["summary"]["run_timing"]["failed_at"], failed_detail["completed_at"])

        history = service.list_runs(code="600519", page=1, limit=10)
        by_status = {item["status"]: item for item in history["items"]}
        self.assertEqual(by_status["cancelled"]["run_timing"]["cancelled_at"], by_status["cancelled"]["completed_at"])
        self.assertEqual(by_status["failed"]["run_timing"]["failed_at"], by_status["failed"]["completed_at"])

    def test_get_run_prefers_persisted_audit_ledger_over_reconstruction(self) -> None:
        service = RuleBacktestService(self.db)
        strategy_text = "Buy when Close > MA3. Sell when Close < MA3."

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text=strategy_text,
                lookback_bars=20,
                confirmed=True,
            )

        run_row = service.repo.get_run(response["id"])
        assert run_row is not None
        summary = json.loads(run_row.summary_json)
        summary["visualization"]["audit_rows"] = [
            {
                "date": "2024-01-20",
                "symbol_close": 999.0,
                "benchmark_close": None,
                "position": 0.0,
                "shares": None,
                "cash": 123456.0,
                "holdings_value": 0.0,
                "total_portfolio_value": 123456.0,
                "daily_pnl": 3456.0,
                "daily_return": 2.88,
                "cumulative_return": 23.456,
                "benchmark_cumulative_return": None,
                "buy_hold_cumulative_return": None,
                "action": "buy",
                "fill_price": 12.34,
                "signal_summary": "stored-ledger-row",
                "drawdown_pct": -0.5,
                "position_state": "flat",
                "fees": None,
                "slippage": None,
                "notes": "persisted-ledger",
                "unavailable_reason": "stored-only",
            }
        ]
        summary["visualization"]["daily_return_series"] = []
        summary["visualization"]["exposure_curve"] = []
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(detail["audit_rows"], summary["visualization"]["audit_rows"])
        self.assertEqual(detail["audit_rows"][0]["symbol_close"], 999.0)
        self.assertEqual(detail["audit_rows"][0]["signal_summary"], "stored-ledger-row")
        self.assertEqual(detail["daily_return_series"][0]["equity"], 123456.0)
        self.assertEqual(detail["daily_return_series"][0]["daily_return_pct"], 2.88)
        self.assertEqual(detail["exposure_curve"][0]["executed_action"], "buy")
        self.assertEqual(detail["exposure_curve"][0]["position_state"], "flat")
        self.assertEqual(
            detail["result_authority"]["replay_payload_source"],
            "summary.visualization.audit_rows+repaired_sections",
        )
        self.assertEqual(detail["result_authority"]["replay_payload_completeness"], "stored_partial_repaired")
        self.assertEqual(
            detail["result_authority"]["replay_payload_missing_sections"],
            ["daily_return_series", "exposure_curve"],
        )
        self.assertEqual(
            detail["result_authority"]["domains"]["replay_payload"],
            {
                "source": "summary.visualization.audit_rows+repaired_sections",
                "completeness": "stored_partial_repaired",
                "state": "available",
                "missing": ["daily_return_series", "exposure_curve"],
                "missing_kind": "sections",
            },
        )
        self.assertEqual(detail["result_authority"]["audit_rows_source"], "summary.visualization.audit_rows")
        self.assertEqual(
            detail["result_authority"]["daily_return_series_source"],
            "rebuilt_from_summary.visualization.audit_rows",
        )
        self.assertEqual(
            detail["result_authority"]["exposure_curve_source"],
            "rebuilt_from_summary.visualization.audit_rows",
        )

    def test_get_run_prefers_persisted_benchmark_comparison_payload_over_legacy_fields(self) -> None:
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
        summary = json.loads(run_row.summary_json)
        summary["visualization"]["benchmark_curve"] = []
        summary["visualization"]["benchmark_summary"] = {
            "label": "legacy benchmark",
            "requested_mode": "auto",
            "resolved_mode": "etf_qqq",
            "method": "benchmark_security",
            "price_basis": "close",
            "return_pct": 1.1,
            "unavailable_reason": None,
        }
        summary["visualization"]["buy_and_hold_curve"] = []
        summary["visualization"]["buy_and_hold_summary"] = {
            "label": "legacy buy hold",
            "requested_mode": "same_symbol_buy_and_hold",
            "resolved_mode": "same_symbol_buy_and_hold",
            "method": "same_symbol_buy_and_hold",
            "price_basis": "close",
            "return_pct": 2.2,
            "unavailable_reason": None,
        }
        summary["metrics"]["benchmark_return_pct"] = 1.1
        summary["metrics"]["buy_and_hold_return_pct"] = 2.2
        summary["metrics"]["excess_return_vs_benchmark_pct"] = 0.1
        summary["metrics"]["excess_return_vs_buy_and_hold_pct"] = -1.0
        summary["visualization"]["comparison"] = {
            "version": "v1",
            "source": "stored",
            "benchmark_curve": [
                {
                    "date": "2024-01-20",
                    "close": 321.0,
                    "normalized_value": 1.099,
                    "cumulative_return_pct": 9.9,
                }
            ],
            "benchmark_summary": {
                "label": "stored benchmark",
                "requested_mode": "auto",
                "resolved_mode": "etf_qqq",
                "method": "benchmark_security",
                "price_basis": "close",
                "return_pct": 9.9,
                "unavailable_reason": "stored benchmark reason",
            },
            "buy_and_hold_curve": [
                {
                    "date": "2024-01-20",
                    "close": 205.5,
                    "normalized_value": 1.055,
                    "cumulative_return_pct": 5.5,
                }
            ],
            "buy_and_hold_summary": {
                "label": "stored buy hold",
                "requested_mode": "same_symbol_buy_and_hold",
                "resolved_mode": "same_symbol_buy_and_hold",
                "method": "same_symbol_buy_and_hold",
                "price_basis": "close",
                "return_pct": 5.5,
                "unavailable_reason": None,
            },
            "metrics": {
                "benchmark_return_pct": 9.9,
                "excess_return_vs_benchmark_pct": -4.4,
                "buy_and_hold_return_pct": 5.5,
                "excess_return_vs_buy_and_hold_pct": 0.0,
            },
        }
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(detail["benchmark_summary"]["label"], "stored benchmark")
        self.assertEqual(detail["benchmark_summary"]["unavailable_reason"], "stored benchmark reason")
        self.assertEqual(detail["benchmark_curve"][0]["close"], 321.0)
        self.assertEqual(detail["buy_and_hold_summary"]["label"], "stored buy hold")
        self.assertEqual(detail["buy_and_hold_curve"][0]["cumulative_return_pct"], 5.5)
        self.assertEqual(detail["benchmark_return_pct"], 9.9)
        self.assertEqual(detail["buy_and_hold_return_pct"], 5.5)
        self.assertEqual(detail["excess_return_vs_benchmark_pct"], -4.4)

        history = service.list_runs(code="600519", page=1, limit=10)
        self.assertEqual(history["items"][0]["benchmark_summary"]["label"], "stored benchmark")
        self.assertEqual(history["items"][0]["benchmark_return_pct"], 9.9)
        self.assertEqual(history["items"][0]["result_authority"]["comparison_source"], "summary.visualization.comparison")
        self.assertEqual(history["items"][0]["result_authority"]["comparison_completeness"], "complete")
        self.assertEqual(history["items"][0]["result_authority"]["comparison_missing_sections"], [])

    def test_get_run_repairs_partial_stored_benchmark_comparison_payload_with_explicit_provenance(self) -> None:
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
        summary = json.loads(run_row.summary_json)
        summary["visualization"]["comparison"] = {
            "version": "v1",
            "source": "summary.visualization.comparison",
            "benchmark_summary": {
                "label": "stored benchmark partial",
                "requested_mode": "auto",
                "resolved_mode": "etf_qqq",
                "method": "benchmark_security",
                "price_basis": "close",
                "return_pct": 8.8,
                "unavailable_reason": None,
            },
        }
        summary["visualization"]["buy_and_hold_summary"] = {
            "label": "legacy buy hold fallback",
            "requested_mode": "same_symbol_buy_and_hold",
            "resolved_mode": "same_symbol_buy_and_hold",
            "method": "same_symbol_buy_and_hold",
            "price_basis": "close",
            "return_pct": 4.4,
            "unavailable_reason": None,
        }
        summary["visualization"]["buy_and_hold_curve"] = [
            {"date": "2024-01-20", "close": 204.4, "normalized_value": 1.044, "cumulative_return_pct": 4.4}
        ]
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(detail["benchmark_summary"]["label"], "stored benchmark partial")
        self.assertEqual(detail["buy_and_hold_summary"]["label"], "legacy buy hold fallback")
        self.assertEqual(detail["buy_and_hold_curve"][0]["cumulative_return_pct"], 4.4)
        self.assertEqual(
            detail["result_authority"]["comparison_source"],
            "summary.visualization.comparison+repaired_sections",
        )
        self.assertEqual(detail["result_authority"]["comparison_completeness"], "stored_partial_repaired")
        self.assertIn("buy_and_hold_summary", detail["result_authority"]["comparison_missing_sections"])
        self.assertIn("buy_and_hold_curve", detail["result_authority"]["comparison_missing_sections"])

    def test_get_run_preserves_stored_empty_comparison_payload_without_legacy_curve_fallback(self) -> None:
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
        summary = json.loads(run_row.summary_json)
        summary["visualization"]["benchmark_curve"] = [
            {"date": "2024-01-20", "close": 999.0, "normalized_value": 1.99, "cumulative_return_pct": 99.0}
        ]
        summary["visualization"]["buy_and_hold_curve"] = [
            {"date": "2024-01-20", "close": 888.0, "normalized_value": 1.88, "cumulative_return_pct": 88.0}
        ]
        summary["visualization"]["comparison"] = {
            "version": "v1",
            "source": "summary.visualization.comparison",
            "benchmark_curve": [],
            "benchmark_summary": dict(summary["visualization"]["benchmark_summary"] or {}),
            "buy_and_hold_curve": [],
            "buy_and_hold_summary": dict(summary["visualization"]["buy_and_hold_summary"] or {}),
            "metrics": {
                "benchmark_return_pct": summary["metrics"].get("benchmark_return_pct"),
                "buy_and_hold_return_pct": summary["metrics"].get("buy_and_hold_return_pct"),
                "excess_return_vs_benchmark_pct": summary["metrics"].get("excess_return_vs_benchmark_pct"),
                "excess_return_vs_buy_and_hold_pct": summary["metrics"].get("excess_return_vs_buy_and_hold_pct"),
            },
        }
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(detail["benchmark_curve"], [])
        self.assertEqual(detail["buy_and_hold_curve"], [])
        self.assertEqual(detail["result_authority"]["comparison_source"], "summary.visualization.comparison")
        self.assertEqual(detail["result_authority"]["comparison_completeness"], "complete")
        self.assertEqual(detail["result_authority"]["comparison_missing_sections"], [])

    def test_get_run_marks_comparison_unavailable_when_no_stored_or_legacy_payload_exists(self) -> None:
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
        summary = json.loads(run_row.summary_json)
        summary["visualization"].pop("comparison", None)
        summary["visualization"]["benchmark_curve"] = []
        summary["visualization"]["benchmark_summary"] = {}
        summary["visualization"]["buy_and_hold_curve"] = []
        summary["visualization"]["buy_and_hold_summary"] = {}
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(detail["benchmark_curve"], [])
        self.assertEqual(detail["benchmark_summary"], {})
        self.assertEqual(detail["buy_and_hold_curve"], [])
        self.assertEqual(detail["buy_and_hold_summary"], {})
        self.assertEqual(detail["result_authority"]["comparison_source"], "unavailable")
        self.assertEqual(detail["result_authority"]["comparison_completeness"], "unavailable")
        self.assertEqual(
            detail["result_authority"]["comparison_missing_sections"],
            ["comparison", "benchmark_summary", "buy_and_hold_summary"],
        )
        self.assertEqual(
            detail["result_authority"]["domains"]["comparison"],
            {
                "source": "unavailable",
                "completeness": "unavailable",
                "state": "unavailable",
                "missing": ["comparison", "benchmark_summary", "buy_and_hold_summary"],
                "missing_kind": "sections",
            },
        )

    def test_history_reads_prefer_stored_summary_metrics_over_row_columns(self) -> None:
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
        summary = json.loads(run_row.summary_json)
        summary["metrics"].update(
            {
                "trade_count": 7,
                "win_count": 6,
                "loss_count": 1,
                "total_return_pct": 88.8,
                "annualized_return_pct": 44.4,
                "win_rate_pct": 85.7143,
                "avg_trade_return_pct": 12.34,
                "max_drawdown_pct": 9.87,
                "avg_holding_days": 8.0,
                "avg_holding_bars": 8.0,
                "avg_holding_calendar_days": 10.0,
                "final_equity": 188800.0,
            }
        )
        summary["visualization"]["daily_return_series"] = [
            {
                "date": "2024-01-20",
                "equity": 188800.0,
                "daily_return_pct": 3.21,
                "daily_pnl": 5875.0,
            }
        ]
        summary["visualization"]["exposure_curve"] = [
            {
                "date": "2024-01-20",
                "exposure": 0.25,
                "position_state": "custom-stored",
                "executed_action": "hold",
                "fill_price": 321.0,
            }
        ]
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(detail["trade_count"], 7)
        self.assertEqual(detail["win_count"], 6)
        self.assertEqual(detail["loss_count"], 1)
        self.assertEqual(detail["total_return_pct"], 88.8)
        self.assertEqual(detail["annualized_return_pct"], 44.4)
        self.assertEqual(detail["win_rate_pct"], 85.7143)
        self.assertEqual(detail["avg_trade_return_pct"], 12.34)
        self.assertEqual(detail["max_drawdown_pct"], 9.87)
        self.assertEqual(detail["avg_holding_days"], 8.0)
        self.assertEqual(detail["avg_holding_bars"], 8.0)
        self.assertEqual(detail["avg_holding_calendar_days"], 10.0)
        self.assertEqual(detail["final_equity"], 188800.0)
        self.assertEqual(detail["result_authority"]["metrics_source"], "summary.metrics")
        self.assertEqual(detail["result_authority"]["metrics_completeness"], "complete")
        self.assertEqual(detail["result_authority"]["metrics_missing_fields"], [])
        self.assertEqual(detail["daily_return_series"], summary["visualization"]["daily_return_series"])
        self.assertEqual(detail["exposure_curve"], summary["visualization"]["exposure_curve"])

        history = service.list_runs(code="600519", page=1, limit=10)
        self.assertEqual(history["items"][0]["trade_count"], 7)
        self.assertEqual(history["items"][0]["total_return_pct"], 88.8)
        self.assertEqual(history["items"][0]["annualized_return_pct"], 44.4)
        self.assertEqual(history["items"][0]["final_equity"], 188800.0)
        self.assertEqual(history["items"][0]["result_authority"]["metrics_source"], "summary.metrics")
        self.assertEqual(history["items"][0]["result_authority"]["metrics_completeness"], "complete")
        self.assertEqual(history["items"][0]["result_authority"]["metrics_missing_fields"], [])

    def test_get_run_uses_explicit_legacy_fallback_when_stored_replay_payload_is_missing(self) -> None:
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
        summary = json.loads(run_row.summary_json)
        summary["metrics"] = {}
        summary["visualization"].pop("comparison", None)
        summary["visualization"]["audit_rows"] = []
        summary["visualization"]["daily_return_series"] = []
        summary["visualization"]["exposure_curve"] = []
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertGreater(len(detail["audit_rows"]), 0)
        self.assertGreater(len(detail["daily_return_series"]), 0)
        self.assertGreater(len(detail["exposure_curve"]), 0)
        self.assertEqual(detail["trade_count"], run_row.trade_count)
        self.assertEqual(detail["total_return_pct"], run_row.total_return_pct)
        self.assertEqual(detail["result_authority"]["metrics_source"], "row_columns_fallback")
        self.assertEqual(detail["result_authority"]["metrics_completeness"], "legacy_row_columns")
        self.assertIn("annualized_return_pct", detail["result_authority"]["metrics_missing_fields"])
        self.assertIn("avg_holding_calendar_days", detail["result_authority"]["metrics_missing_fields"])
        self.assertEqual(detail["result_authority"]["replay_payload_source"], "derived_from_stored_run_artifacts")
        self.assertEqual(detail["result_authority"]["replay_payload_completeness"], "legacy_complete")
        self.assertEqual(detail["result_authority"]["replay_payload_missing_sections"], [])
        self.assertEqual(detail["result_authority"]["audit_rows_source"], "derived_from_stored_run_artifacts")
        self.assertEqual(
            detail["result_authority"]["daily_return_series_source"],
            "derived_from_stored_run_artifacts",
        )
        self.assertEqual(
            detail["result_authority"]["exposure_curve_source"],
            "derived_from_stored_run_artifacts",
        )
        self.assertEqual(detail["benchmark_return_pct"], detail["benchmark_summary"]["return_pct"])

    def test_get_run_repairs_partial_stored_metrics_with_explicit_provenance(self) -> None:
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
        summary = json.loads(run_row.summary_json)
        summary["metrics"] = {
            "trade_count": 7,
            "total_return_pct": 88.8,
            "annualized_return_pct": 44.4,
        }
        service.repo.update_run(
            run_row.id,
            summary_json=service._serialize_json(summary),
            win_count=6,
            loss_count=1,
            win_rate_pct=85.0,
            avg_trade_return_pct=12.3,
            max_drawdown_pct=9.8,
            avg_holding_days=8.0,
            final_equity=188800.0,
        )

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(detail["trade_count"], 7)
        self.assertEqual(detail["total_return_pct"], 88.8)
        self.assertEqual(detail["annualized_return_pct"], 44.4)
        self.assertEqual(detail["win_count"], 6)
        self.assertEqual(detail["loss_count"], 1)
        self.assertEqual(detail["final_equity"], 188800.0)
        self.assertEqual(detail["result_authority"]["metrics_source"], "summary.metrics+row_columns_fallback")
        self.assertEqual(detail["result_authority"]["metrics_completeness"], "stored_partial_repaired")
        self.assertIn("win_count", detail["result_authority"]["metrics_missing_fields"])
        self.assertIn("final_equity", detail["result_authority"]["metrics_missing_fields"])
        self.assertIn("avg_holding_calendar_days", detail["result_authority"]["metrics_missing_fields"])

    def test_get_run_derives_execution_model_for_legacy_runs_without_structured_config(self) -> None:
        service = RuleBacktestService(self.db)
        strategy_text = "Buy when Close > MA3. Sell when Close < MA3."

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text=strategy_text,
                lookback_bars=20,
                confirmed=True,
            )

        run_row = service.repo.get_run(response["id"])
        assert run_row is not None
        summary = json.loads(run_row.summary_json)
        summary.pop("execution_model", None)
        summary["request"].pop("execution_model", None)
        summary.pop("execution_assumptions_snapshot", None)
        summary["execution_assumptions"] = {
            "timeframe": "daily",
            "signal_evaluation_timing": "evaluate rules on each bar close",
            "entry_fill_timing": "next_bar_open",
            "exit_fill_timing": "next_bar_open; last openless bar falls back to same-bar close",
            "default_fill_price_basis": "open",
            "position_sizing": "single_position_full_notional",
            "fee_model": "bps_per_side",
            "fee_bps_per_side": 1.5,
            "slippage_model": "bps_per_side",
            "slippage_bps_per_side": 2.5,
        }
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(detail["execution_model"]["signal_evaluation_timing"], "bar_close")
        self.assertEqual(detail["execution_model"]["entry_timing"], "next_bar_open")
        self.assertEqual(detail["execution_model"]["entry_fill_price_basis"], "open")
        self.assertEqual(detail["execution_model"]["fee_bps_per_side"], 1.5)
        self.assertEqual(detail["execution_model"]["slippage_bps_per_side"], 2.5)
        self.assertEqual(detail["execution_model"]["market_rules"]["terminal_bar_fill_fallback"], "same_bar_close")


if __name__ == "__main__":
    unittest.main()
