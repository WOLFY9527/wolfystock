# -*- coding: utf-8 -*-
"""Focused tests for pure user alert suppression policy decisions."""

from __future__ import annotations

import ast
import importlib
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.services.user_alert_suppression_policy import evaluate_user_alert_suppression_policy


class UserAlertSuppressionPolicyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 6, 8, 10, 30, tzinfo=timezone.utc)

    def test_allowed_when_no_suppression_matches(self) -> None:
        result = evaluate_user_alert_suppression_policy(now=self.now)

        self.assertEqual(result["state"], "allowed")
        self.assertTrue(result["allowed"])
        self.assertFalse(result["suppressed"])

    def test_muted_has_highest_precedence(self) -> None:
        result = evaluate_user_alert_suppression_policy(
            now=self.now,
            muted=True,
            snoozed_until=self.now + timedelta(hours=2),
            cooldown_started_at=self.now - timedelta(minutes=5),
            cooldown_seconds=900,
            current_fingerprint="alert:nvda",
            current_time_bucket="202606081000",
            previous_fingerprint="alert:nvda",
            previous_time_bucket="202606081000",
        )

        self.assertEqual(result["state"], "suppressed_muted")
        self.assertFalse(result["allowed"])
        self.assertTrue(result["suppressed"])

    def test_snooze_is_timezone_safe(self) -> None:
        suppressed = evaluate_user_alert_suppression_policy(
            now="2026-06-08T10:30:00Z",
            snoozed_until="2026-06-08T19:00:00+08:00",
        )
        expired = evaluate_user_alert_suppression_policy(
            now="2026-06-08T10:30:00Z",
            snoozed_until="2026-06-08T18:30:00+08:00",
        )

        self.assertEqual(suppressed["state"], "suppressed_snoozed")
        self.assertEqual(expired["state"], "allowed")

    def test_cooldown_suppresses_only_within_window(self) -> None:
        active = evaluate_user_alert_suppression_policy(
            now=self.now,
            cooldown_started_at=self.now - timedelta(minutes=10),
            cooldown_seconds=900,
        )
        expired = evaluate_user_alert_suppression_policy(
            now=self.now,
            cooldown_started_at=self.now - timedelta(minutes=16),
            cooldown_seconds=900,
        )

        self.assertEqual(active["state"], "suppressed_cooldown")
        self.assertEqual(expired["state"], "allowed")

    def test_duplicate_requires_matching_fingerprint_and_bucket(self) -> None:
        duplicate = evaluate_user_alert_suppression_policy(
            now=self.now,
            current_fingerprint="alert:nvda",
            current_time_bucket="202606081000",
            previous_fingerprint="alert:nvda",
            previous_time_bucket="202606081000",
        )
        different_bucket = evaluate_user_alert_suppression_policy(
            now=self.now,
            current_fingerprint="alert:nvda",
            current_time_bucket="202606081100",
            previous_fingerprint="alert:nvda",
            previous_time_bucket="202606081000",
        )

        self.assertEqual(duplicate["state"], "suppressed_duplicate")
        self.assertEqual(different_bucket["state"], "allowed")

    def test_incomplete_or_invalid_policy_inputs_fail_closed(self) -> None:
        cases = (
            {
                "name": "missing_now",
                "kwargs": {},
            },
            {
                "name": "negative_cooldown",
                "kwargs": {
                    "now": self.now,
                    "cooldown_started_at": self.now,
                    "cooldown_seconds": -1,
                },
            },
            {
                "name": "cooldown_without_window",
                "kwargs": {
                    "now": self.now,
                    "cooldown_started_at": self.now,
                },
            },
            {
                "name": "partial_duplicate_identity",
                "kwargs": {
                    "now": self.now,
                    "current_fingerprint": "alert:nvda",
                    "current_time_bucket": "202606081000",
                },
            },
            {
                "name": "blank_fingerprint",
                "kwargs": {
                    "now": self.now,
                    "current_fingerprint": "   ",
                    "current_time_bucket": "202606081000",
                    "previous_fingerprint": "alert:nvda",
                    "previous_time_bucket": "202606081000",
                },
            },
        )

        for case in cases:
            with self.subTest(case=case["name"]):
                result = evaluate_user_alert_suppression_policy(**case["kwargs"])
                self.assertEqual(result["state"], "invalid_policy")
                self.assertFalse(result["allowed"])
                self.assertFalse(result["suppressed"])

    def test_states_remain_bounded(self) -> None:
        states = {
            evaluate_user_alert_suppression_policy(now=self.now)["state"],
            evaluate_user_alert_suppression_policy(now=self.now, muted=True)["state"],
            evaluate_user_alert_suppression_policy(
                now=self.now,
                snoozed_until=self.now + timedelta(minutes=5),
            )["state"],
            evaluate_user_alert_suppression_policy(
                now=self.now,
                cooldown_started_at=self.now - timedelta(minutes=1),
                cooldown_seconds=120,
            )["state"],
            evaluate_user_alert_suppression_policy(
                now=self.now,
                current_fingerprint="alert:nvda",
                current_time_bucket="202606081000",
                previous_fingerprint="alert:nvda",
                previous_time_bucket="202606081000",
            )["state"],
            evaluate_user_alert_suppression_policy(now=self.now, cooldown_seconds=0)["state"],
        }

        self.assertEqual(
            states,
            {
                "allowed",
                "suppressed_muted",
                "suppressed_snoozed",
                "suppressed_cooldown",
                "suppressed_duplicate",
                "invalid_policy",
            },
        )

    def test_module_stays_free_of_protected_runtime_and_real_send_imports(self) -> None:
        module = importlib.import_module("src.services.user_alert_suppression_policy")
        source_path = Path(module.__file__)
        source_text = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source_text)
        forbidden_imports = {
            "src.storage",
            "src.notification",
            "src.services.notification_service",
            "src.services.market_cache",
            "src.core",
            "api",
            "data_provider",
            "os",
            "requests",
            "httpx",
            "urllib",
            "socket",
            "smtplib",
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

        lowered = source_text.lower()
        self.assertNotIn("datetime.now(", lowered)
        self.assertNotIn("send(", lowered)
        self.assertNotIn("webhook", lowered)


if __name__ == "__main__":
    unittest.main()
