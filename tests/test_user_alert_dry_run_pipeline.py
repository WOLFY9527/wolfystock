# -*- coding: utf-8 -*-
"""Focused tests for the pure local user alert dry-run pipeline helper."""

from __future__ import annotations

import ast
import importlib
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.services.user_alert_dry_run_pipeline import build_user_alert_dry_run_pipeline_result


class UserAlertDryRunPipelineTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 6, 8, 10, 30, tzinfo=timezone.utc)
        self.recorded_at = datetime(2026, 6, 8, 10, 31, tzinfo=timezone.utc)
        self.rule = {
            "id": 7,
            "rule_type": "watchlist_price_threshold",
            "symbol": "NVDA",
            "direction": "above",
            "threshold_price": 125.5,
            "note": "secret owner note that must not leak",
            "owner_id": "owner-secret",
        }
        self.suppression = {
            "muted": False,
            "snoozedUntil": None,
            "cooldownStartedAt": None,
            "cooldownSeconds": None,
            "previousFingerprint": "older-fingerprint",
            "previousTimeBucket": "202606080900",
            "providerTrace": {"provider": "secret-provider"},
            "reasonCode": "must-not-leak",
        }

    def test_unsuppressed_pipeline_builds_local_only_packet(self) -> None:
        result = build_user_alert_dry_run_pipeline_result(
            rule=self.rule,
            observed_price=130.0,
            observed_at=self.now,
            freshness={"status": "fresh"},
            suppression=self.suppression,
            now=self.now,
            recorded_at=self.recorded_at,
        )

        self.assertTrue(result["dryRun"])
        self.assertFalse(result["outboundAttempted"])
        self.assertFalse(result["liveOutbound"])
        self.assertTrue(result["localOnly"])
        self.assertFalse(result["suppressedLocalRecord"])

        evaluation = result["evaluation"]
        suppression = result["suppression"]
        packet = result["eventPacket"]

        self.assertEqual(evaluation["state"], "condition_observed")
        self.assertTrue(evaluation["conditionObserved"])
        self.assertFalse(evaluation["suppressed"])
        self.assertEqual(suppression["state"], "allowed")
        self.assertTrue(suppression["allowed"])
        self.assertFalse(suppression["suppressed"])

        self.assertIsNotNone(packet)
        self.assertEqual(packet["state"], "condition_observed")
        self.assertEqual(packet["observedAsOf"], "2026-06-08T10:30:00Z")
        self.assertEqual(packet["createdAt"], "2026-06-08T10:31:00Z")
        self.assertTrue(packet["localOnly"])

        combined_text = json.dumps(
            {
                "title": evaluation["title"],
                "message": evaluation["message"],
                "packetTitle": packet["title"],
                "packetMessage": packet["message"],
            },
            ensure_ascii=False,
        ).lower()
        for forbidden in (
            "reasoncode",
            "providertrace",
            "condition_observed",
            "suppressed_muted",
            "owner-secret",
            "secret owner note",
            "buy",
            "sell",
            "stop",
            "target",
            "position sizing",
        ):
            self.assertNotIn(forbidden, combined_text)

    def test_suppression_blocks_packet_by_default(self) -> None:
        result = build_user_alert_dry_run_pipeline_result(
            rule=self.rule,
            observed_price=130.0,
            observed_at=self.now,
            freshness={"status": "fresh"},
            suppression={**self.suppression, "muted": True},
            now=self.now,
            recorded_at=self.recorded_at,
        )

        self.assertEqual(result["evaluation"]["state"], "suppressed_muted")
        self.assertTrue(result["evaluation"]["suppressed"])
        self.assertEqual(result["suppression"]["state"], "suppressed_muted")
        self.assertIsNone(result["eventPacket"])
        self.assertFalse(result["suppressedLocalRecord"])

    def test_history_like_suppressed_preview_does_not_emit_record_by_default(self) -> None:
        result = build_user_alert_dry_run_pipeline_result(
            rule={
                **self.rule,
                "owner_id": "owner-private-marker",
                "note": "private owner memo",
                "rawPayload": {"marker": "raw-payload-marker"},
                "persistedEventId": "persisted-marker",
            },
            observed_price=130.0,
            observed_at=self.now,
            freshness={"status": "fresh", "rawPayload": {"marker": "freshness-private-marker"}},
            suppression={**self.suppression, "muted": True},
            now=self.now,
            recorded_at=self.recorded_at,
        )

        self.assertTrue(result["dryRun"])
        self.assertTrue(result["noSend"])
        self.assertFalse(result["outboundAttempted"])
        self.assertFalse(result["liveOutbound"])
        self.assertTrue(result["localOnly"])
        self.assertFalse(result["suppressedLocalRecord"])
        self.assertIsNone(result["eventPacket"])

        evaluation = result["evaluation"]
        self.assertEqual(evaluation["state"], "suppressed_muted")
        self.assertTrue(evaluation["dryRun"])
        self.assertFalse(evaluation["outboundAttempted"])
        self.assertFalse(evaluation["liveOutbound"])
        self.assertFalse(evaluation["providerRuntimeCalled"])
        self.assertFalse(evaluation["networkCallsEnabled"])
        self.assertFalse(evaluation["marketCacheMutation"])
        self.assertTrue(evaluation["suppressed"])

        serialized = json.dumps(result, ensure_ascii=False).lower()
        for forbidden in (
            "owner-private-marker",
            "private owner memo",
            "raw-payload-marker",
            "persisted-marker",
            "freshness-private-marker",
            "rawpayload",
            "persistedeventid",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_suppressed_local_record_is_opt_in(self) -> None:
        result = build_user_alert_dry_run_pipeline_result(
            rule=self.rule,
            observed_price=130.0,
            observed_at=self.now,
            freshness={"status": "fresh"},
            suppression={**self.suppression, "muted": True},
            now=self.now,
            recorded_at=self.recorded_at,
            include_suppressed_local_record=True,
        )

        self.assertEqual(result["evaluation"]["state"], "suppressed_muted")
        self.assertEqual(result["suppression"]["state"], "suppressed_muted")
        self.assertTrue(result["suppressedLocalRecord"])
        self.assertIsNotNone(result["eventPacket"])
        self.assertEqual(result["eventPacket"]["state"], "suppressed_muted")
        self.assertTrue(result["eventPacket"]["safeMetadata"]["suppressed"])

    def test_history_like_local_record_is_opt_in_and_local_only(self) -> None:
        result = build_user_alert_dry_run_pipeline_result(
            rule=self.rule,
            observed_price=130.0,
            observed_at=self.now,
            freshness={"status": "fresh"},
            suppression={**self.suppression, "muted": True},
            now=self.now,
            recorded_at=self.recorded_at,
            include_suppressed_local_record=True,
        )

        packet = result["eventPacket"]

        self.assertTrue(result["dryRun"])
        self.assertTrue(result["noSend"])
        self.assertFalse(result["outboundAttempted"])
        self.assertFalse(result["liveOutbound"])
        self.assertTrue(result["localOnly"])
        self.assertTrue(result["suppressedLocalRecord"])
        self.assertIsNotNone(packet)
        self.assertEqual(packet["observedAsOf"], "2026-06-08T10:30:00Z")
        self.assertEqual(packet["createdAt"], "2026-06-08T10:31:00Z")
        self.assertTrue(packet["dryRun"])
        self.assertFalse(packet["outboundAttempted"])
        self.assertFalse(packet["liveOutbound"])
        self.assertTrue(packet["localOnly"])
        self.assertTrue(packet["safeMetadata"]["suppressed"])

    def test_output_is_deterministic_from_safe_inputs(self) -> None:
        first = build_user_alert_dry_run_pipeline_result(
            rule=self.rule,
            observed_price=130.0,
            observed_at=self.now,
            freshness={"status": "fresh", "providerTrace": {"raw": "must-not-leak"}},
            suppression=self.suppression,
            now=self.now,
            recorded_at=self.recorded_at,
        )
        second = build_user_alert_dry_run_pipeline_result(
            rule={**self.rule, "id": 99, "note": "changed secret", "owner_id": "another-owner"},
            observed_price=130.0,
            observed_at=self.now,
            freshness={"status": "fresh", "reasonCode": "changed-secret"},
            suppression={
                **self.suppression,
                "ownerNote": "another secret note",
                "providerTrace": {"provider": "another-provider"},
                "cooldownStartedAt": self.now - timedelta(hours=2),
                "cooldownSeconds": 60,
            },
            now=self.now,
            recorded_at=self.recorded_at,
        )

        self.assertEqual(first, second)

    def test_module_stays_free_of_protected_runtime_imports(self) -> None:
        module = importlib.import_module("src.services.user_alert_dry_run_pipeline")
        self.assertTrue(hasattr(module, "build_user_alert_dry_run_pipeline_result"))

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
        self.assertNotIn("reasoncode", lowered)
        self.assertNotIn("providertrace", lowered)
        self.assertNotIn("raw_payload", lowered)


if __name__ == "__main__":
    unittest.main()
