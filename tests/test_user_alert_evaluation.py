# -*- coding: utf-8 -*-
"""Focused tests for pure dry-run user alert evaluation."""

from __future__ import annotations

import ast
import importlib
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from src.services.user_alert_evaluation import evaluate_user_alert_dry_run


class UserAlertEvaluationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 6, 8, 10, 30, tzinfo=timezone.utc)
        self.rule = {
            "id": 7,
            "rule_type": "watchlist_price_threshold",
            "symbol": "NVDA",
            "direction": "above",
            "threshold_price": 125.5,
            "note": "secret owner note that must not affect dedupe",
            "owner_id": "owner-secret",
        }

    def test_condition_observed_returns_pure_dry_run_intent(self) -> None:
        result = evaluate_user_alert_dry_run(
            rule=self.rule,
            observed_price=130.0,
            observed_at=self.now,
            freshness={"status": "fresh"},
            now=self.now,
        )

        self.assertEqual(result["state"], "condition_observed")
        self.assertTrue(result["conditionObserved"])
        self.assertTrue(result["dryRun"])
        self.assertFalse(result["outboundAttempted"])
        self.assertFalse(result["liveOutbound"])
        self.assertFalse(result["providerRuntimeCalled"])
        self.assertFalse(result["networkCallsEnabled"])
        self.assertFalse(result["marketCacheMutation"])
        self.assertTrue(result["observationOnly"])
        self.assertEqual(result["ruleType"], "watchlist_price_threshold")
        self.assertEqual(result["subject"], "NVDA")
        self.assertIn("NVDA", result["title"])
        self.assertIn("125.5", result["message"])
        self.assertIn("130", result["message"])
        combined = f'{result["title"]} {result["message"]} {result["dedupeFingerprint"]}'.lower()
        for forbidden in (
            "reasoncode",
            "condition_observed",
            "provider",
            "trace",
            "buy",
            "sell",
            "target",
            "position",
            "owner-secret",
            "secret owner note",
        ):
            self.assertNotIn(forbidden, combined)

    def test_condition_not_observed_when_threshold_not_met(self) -> None:
        result = evaluate_user_alert_dry_run(
            rule=self.rule,
            observed_price=120.0,
            observed_at=self.now,
            freshness={"status": "fresh"},
            now=self.now,
        )

        self.assertEqual(result["state"], "condition_not_observed")
        self.assertFalse(result["conditionObserved"])
        self.assertIn("尚未触发", result["title"])
        self.assertIn("125.5", result["message"])
        self.assertNotIn("实时", result["message"])

    def test_missing_or_stale_price_fails_closed(self) -> None:
        cases = (
            {
                "name": "missing_price",
                "kwargs": {
                    "rule": self.rule,
                    "observed_price": None,
                    "observed_at": self.now,
                    "freshness": {"status": "fresh"},
                    "now": self.now,
                },
            },
            {
                "name": "missing_as_of",
                "kwargs": {
                    "rule": self.rule,
                    "observed_price": 130.0,
                    "observed_at": None,
                    "freshness": {"status": "fresh"},
                    "now": self.now,
                },
            },
            {
                "name": "stale_flag",
                "kwargs": {
                    "rule": self.rule,
                    "observed_price": 130.0,
                    "observed_at": self.now,
                    "freshness": {"status": "stale"},
                    "now": self.now,
                },
            },
            {
                "name": "stale_age",
                "kwargs": {
                    "rule": self.rule,
                    "observed_price": 130.0,
                    "observed_at": self.now - timedelta(hours=4),
                    "freshness": {"maxAgeMinutes": 30},
                    "now": self.now,
                },
            },
        )

        for case in cases:
            with self.subTest(case=case["name"]):
                result = evaluate_user_alert_dry_run(**case["kwargs"])
                self.assertEqual(result["state"], "blocked_insufficient_data")
                self.assertFalse(result["conditionObserved"])
                self.assertIn("数据不足", result["title"])
                self.assertIn("最近一次可用", result["message"])
                self.assertNotIn("实时", result["message"])
                self.assertNotIn("当前", result["message"])

    def test_suppression_states_are_bounded_and_safe(self) -> None:
        cases = (
            ("suppressed_cooldown", {"cooldownActive": True}),
            ("suppressed_duplicate", {"duplicateActive": True}),
            ("suppressed_muted", {"muted": True}),
            ("suppressed_snoozed", {"snoozedUntil": "2026-06-08T12:00:00Z"}),
        )

        for expected_state, suppression in cases:
            with self.subTest(state=expected_state):
                result = evaluate_user_alert_dry_run(
                    rule=self.rule,
                    observed_price=130.0,
                    observed_at=self.now,
                    freshness={"status": "fresh"},
                    suppression=suppression,
                    now=self.now,
                )
                self.assertEqual(result["state"], expected_state)
                self.assertTrue(result["conditionObserved"])
                self.assertTrue(result["suppressed"])
                self.assertFalse(result["outboundAttempted"])
                consumer_text = f'{result["title"]} {result["message"]}'.lower()
                self.assertNotIn("reasoncode", consumer_text)
                self.assertNotIn("provider", consumer_text)

    def test_invalid_rule_fails_safe_as_error(self) -> None:
        result = evaluate_user_alert_dry_run(
            rule={"symbol": "NVDA", "direction": "sideways", "threshold_price": 125.5},
            observed_price=130.0,
            observed_at=self.now,
            freshness={"status": "fresh"},
            now=self.now,
        )

        self.assertEqual(result["state"], "error")
        self.assertFalse(result["conditionObserved"])
        self.assertIn("无法完成提醒检查", result["title"])
        self.assertNotIn("sideways", result["message"])
        self.assertNotIn("traceback", result["message"].lower())

    def test_dedupe_fingerprint_is_deterministic_from_safe_fields_and_time_bucket(self) -> None:
        same_bucket = evaluate_user_alert_dry_run(
            rule=self.rule,
            observed_price=130.0,
            observed_at=self.now,
            freshness={"status": "fresh"},
            now=self.now,
        )
        same_bucket_with_secret_changes = evaluate_user_alert_dry_run(
            rule={**self.rule, "note": "new secret", "owner_id": "another-secret", "id": 99},
            observed_price=131.0,
            observed_at=self.now + timedelta(minutes=10),
            freshness={"status": "fresh"},
            now=self.now + timedelta(minutes=10),
        )
        next_bucket = evaluate_user_alert_dry_run(
            rule=self.rule,
            observed_price=132.0,
            observed_at=self.now + timedelta(hours=1),
            freshness={"status": "fresh"},
            now=self.now + timedelta(hours=1),
        )

        self.assertEqual(same_bucket["dedupeFingerprint"], same_bucket_with_secret_changes["dedupeFingerprint"])
        self.assertNotEqual(same_bucket["dedupeFingerprint"], next_bucket["dedupeFingerprint"])

    def test_object_inputs_are_supported(self) -> None:
        rule = SimpleNamespace(
            rule_type="watchlist_price_threshold",
            symbol="TSLA",
            direction="below",
            threshold_price=200.0,
        )
        freshness = SimpleNamespace(status="fresh", max_age_minutes=120)
        suppression = SimpleNamespace(muted=False)

        result = evaluate_user_alert_dry_run(
            rule=rule,
            observed_price=190.0,
            observed_at=self.now,
            freshness=freshness,
            suppression=suppression,
            now=self.now,
        )

        self.assertEqual(result["state"], "condition_observed")
        self.assertEqual(result["subject"], "TSLA")

    def test_module_stays_free_of_protected_runtime_imports(self) -> None:
        module = importlib.import_module("src.services.user_alert_evaluation")
        self.assertTrue(hasattr(module, "evaluate_user_alert_dry_run"))

        source_path = Path(module.__file__)
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        forbidden_imports = {
            "src.storage",
            "src.notification",
            "src.services.notification_service",
            "src.core",
            "src.services.market_cache",
            "data_provider",
            "api",
        }
        seen = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    seen.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    seen.add(node.module)

        for import_name in seen:
            for forbidden in forbidden_imports:
                self.assertFalse(
                    import_name == forbidden or import_name.startswith(f"{forbidden}."),
                    msg=f"forbidden import detected: {import_name}",
                )


if __name__ == "__main__":
    unittest.main()
