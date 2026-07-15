# -*- coding: utf-8 -*-
"""Characterization tests for user-alert presentation and time helpers."""

from __future__ import annotations

import ast
import importlib
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path


class UserAlertPresentationTestCase(unittest.TestCase):
    @staticmethod
    def _load_helpers():
        try:
            module = importlib.import_module("src.services.user_alert_presentation")
        except ModuleNotFoundError as exc:
            raise AssertionError("user-alert presentation helper module is missing") from exc
        return module.build_user_alert_presentation_copy, module.coerce_user_alert_datetime

    def test_copy_characterizes_every_state_branch(self) -> None:
        build_copy, _ = self._load_helpers()
        cases = (
            (
                "condition_observed",
                "NVDA 价格提醒已记录",
                "价格已达到你设定的关注条件（阈值 125.5，观察值 130）。仅供观察，不会发送外部通知。",
            ),
            (
                "condition_not_observed",
                "NVDA 尚未触发提醒",
                "价格暂未达到你设定的关注条件（阈值 125.5，观察值 130）。",
            ),
            (
                "suppressed_cooldown",
                "NVDA 提醒已暂缓",
                "本次条件已观察到，但仍在提醒间隔内。结果仅用于站内 dry-run 检查。",
            ),
            (
                "suppressed_duplicate",
                "NVDA 重复提醒已折叠",
                "本次条件已观察到，但与最近一次结果重复。结果仅用于站内 dry-run 检查。",
            ),
            (
                "suppressed_muted",
                "NVDA 提醒已静默",
                "本次条件已观察到，但该提醒当前处于静默状态。结果仅用于站内 dry-run 检查。",
            ),
            (
                "suppressed_snoozed",
                "NVDA 提醒稍后再看",
                "本次条件已观察到，但该提醒仍在稍后再看期间。结果仅用于站内 dry-run 检查。",
            ),
            (
                "blocked_insufficient_data",
                "NVDA 数据不足",
                "最近一次可用价格信息不足，此次不做提醒判断，也不会假定为最新数据。",
            ),
            (
                "error",
                "NVDA 无法完成提醒检查",
                "当前无法完成提醒检查，请稍后再试。",
            ),
        )

        for state, expected_title, expected_message in cases:
            with self.subTest(state=state):
                self.assertEqual(
                    build_copy(
                        state=state,
                        subject="NVDA",
                        threshold_price=Decimal("125.500"),
                        observed_price=Decimal("130.000"),
                    ),
                    (expected_title, expected_message),
                )

    def test_copy_preserves_float_and_missing_price_formatting(self) -> None:
        build_copy, _ = self._load_helpers()

        self.assertEqual(
            build_copy(
                state="condition_observed",
                subject="AAPL",
                threshold_price=1234567.0,
                observed_price=None,
            ),
            (
                "AAPL 价格提醒已记录",
                "价格已达到你设定的关注条件（阈值 1.23457e+06，观察值 --）。仅供观察，不会发送外部通知。",
            ),
        )
        self.assertEqual(
            build_copy(
                state="unexpected",
                subject="该标的",
                threshold_price=None,
                observed_price=None,
            ),
            ("该标的 无法完成提醒检查", "当前无法完成提醒检查，请稍后再试。"),
        )

    def test_datetime_characterizes_every_input_branch(self) -> None:
        _, coerce_datetime = self._load_helpers()
        aware = datetime(2026, 6, 8, 18, 30, tzinfo=timezone(timedelta(hours=8)))
        naive = datetime(2026, 6, 8, 10, 30)

        self.assertIsNone(coerce_datetime(None))
        self.assertIsNone(coerce_datetime("   "))
        self.assertIs(coerce_datetime(aware), aware)
        self.assertEqual(coerce_datetime(naive), naive.replace(tzinfo=timezone.utc))
        self.assertEqual(coerce_datetime("2026-06-08T10:30:00Z"), datetime(2026, 6, 8, 10, 30, tzinfo=timezone.utc))
        self.assertEqual(coerce_datetime("2026-06-08T10:30:00"), datetime(2026, 6, 8, 10, 30, tzinfo=timezone.utc))
        self.assertEqual(coerce_datetime("2026-06-08T18:30:00+08:00"), aware)
        self.assertIsNone(coerce_datetime("not-a-datetime"))

    def test_consumers_use_domain_local_helpers_without_local_duplicates(self) -> None:
        self._load_helpers()
        repo_root = Path(__file__).resolve().parents[1]
        owners = {
            "src/services/user_alert_evaluation.py": {"build_user_alert_presentation_copy", "coerce_user_alert_datetime"},
            "src/services/user_alert_event_packet.py": {"build_user_alert_presentation_copy", "coerce_user_alert_datetime"},
            "src/services/user_alert_dry_run_pipeline.py": {"coerce_user_alert_datetime"},
        }

        for relative_path, expected_imports in owners.items():
            with self.subTest(owner=relative_path):
                tree = ast.parse((repo_root / relative_path).read_text(encoding="utf-8"))
                local_functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
                self.assertNotIn("_consumer_copy", local_functions)
                self.assertNotIn("_coerce_datetime", local_functions)
                helper_imports = {
                    alias.name
                    for node in tree.body
                    if isinstance(node, ast.ImportFrom) and node.module == "src.services.user_alert_presentation"
                    for alias in node.names
                }
                self.assertTrue(expected_imports.issubset(helper_imports))


if __name__ == "__main__":
    unittest.main()
