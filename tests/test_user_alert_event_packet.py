# -*- coding: utf-8 -*-
"""Focused tests for pure local-only user alert event packet projection."""

from __future__ import annotations

import ast
import importlib
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.services.user_alert_evaluation import evaluate_user_alert_dry_run
from src.services.user_alert_event_packet import build_user_alert_event_packet


class UserAlertEventPacketTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 6, 8, 10, 30, tzinfo=timezone.utc)
        self.rule = {
            "id": 7,
            "rule_type": "watchlist_price_threshold",
            "symbol": "NVDA",
            "direction": "above",
            "threshold_price": 125.5,
            "note": "secret owner note that must not leak",
            "owner_id": "owner-secret",
        }

    def test_builds_local_only_append_only_packet_from_dry_run_evaluation(self) -> None:
        evaluation = evaluate_user_alert_dry_run(
            rule=self.rule,
            observed_price=130.0,
            observed_at=self.now,
            freshness={"status": "fresh"},
            now=self.now,
        )

        packet = build_user_alert_event_packet(result=evaluation, now=self.now)

        self.assertEqual(packet["packetKind"], "user_alert_event_packet")
        self.assertEqual(packet["packetVersion"], "user_alert_event_packet_v1")
        self.assertEqual(packet["eventType"], "user.alert_dry_run_evaluation")
        self.assertEqual(packet["state"], "condition_observed")
        self.assertTrue(packet["dryRun"])
        self.assertFalse(packet["outboundAttempted"])
        self.assertFalse(packet["liveOutbound"])
        self.assertTrue(packet["localOnly"])
        self.assertEqual(packet["observedAsOf"], "2026-06-08T10:30:00Z")
        self.assertEqual(packet["createdAt"], "2026-06-08T10:30:00Z")
        self.assertTrue(packet["fingerprint"].startswith("user-alert-event:"))
        self.assertIn("NVDA", packet["title"])
        self.assertIn("125.5", packet["message"])
        self.assertIn("130", packet["message"])

        safe_metadata = packet["safeMetadata"]
        self.assertEqual(safe_metadata["subject"], "NVDA")
        self.assertEqual(safe_metadata["ruleType"], "watchlist_price_threshold")
        self.assertEqual(safe_metadata["direction"], "above")
        self.assertEqual(safe_metadata["thresholdPrice"], 125.5)
        self.assertEqual(safe_metadata["observedPrice"], 130.0)
        self.assertEqual(safe_metadata["freshnessStatus"], "fresh")
        self.assertTrue(safe_metadata["conditionObserved"])
        self.assertFalse(safe_metadata["suppressed"])
        self.assertEqual(safe_metadata["dedupeFingerprint"], evaluation["dedupeFingerprint"])

        serialized = json.dumps(packet, ensure_ascii=False).lower()
        for forbidden in (
            "reasoncode",
            "providertrace",
            "owner-secret",
            "secret owner note",
            "rawpayload",
            "owner_note",
            "raw_payload",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_rebuilds_consumer_text_and_fingerprint_without_secret_or_payload_leakage(self) -> None:
        base = evaluate_user_alert_dry_run(
            rule=self.rule,
            observed_price=130.0,
            observed_at=self.now,
            freshness={"status": "fresh"},
            now=self.now,
        )
        polluted = {
            **base,
            "title": "NVDA condition_observed owner_note provider_trace",
            "message": "reasonCode=budget_hard_limit_exceeded raw_payload token=must-not-leak",
            "reasonCode": "budget_hard_limit_exceeded",
            "providerTrace": {"provider": "secret-provider", "rawPayload": {"token": "must-not-leak"}},
            "ownerNote": "secret owner note",
            "rawPayload": {"email": "private@example.com"},
        }
        changed_secrets = {
            **polluted,
            "ownerNote": "another secret owner note",
            "rawPayload": {"email": "another@example.com"},
            "providerTrace": {"provider": "other-provider", "rawPayload": {"token": "another-secret"}},
        }

        polluted_packet = build_user_alert_event_packet(result=polluted, now=self.now)
        changed_packet = build_user_alert_event_packet(result=changed_secrets, now=self.now)

        self.assertEqual(polluted_packet["fingerprint"], changed_packet["fingerprint"])

        combined_text = f'{polluted_packet["title"]} {polluted_packet["message"]} {json.dumps(polluted_packet["safeMetadata"], ensure_ascii=False)}'.lower()
        for forbidden in (
            "condition_observed",
            "owner_note",
            "provider_trace",
            "reasoncode",
            "raw_payload",
            "must-not-leak",
            "private@example.com",
            "secret owner note",
        ):
            self.assertNotIn(forbidden, combined_text)

        self.assertIn("已记录", polluted_packet["title"])
        self.assertIn("仅供观察", polluted_packet["message"])

    def test_history_like_preview_packet_keeps_safe_times_and_fingerprints(self) -> None:
        observed_at = self.now - timedelta(minutes=5)
        created_at = self.now + timedelta(minutes=2)
        preview_rule = {
            **self.rule,
            "owner_id": "owner-private-marker",
            "note": "private owner memo",
            "rawPayload": {"marker": "raw-payload-marker"},
            "persistedEventId": "persisted-marker",
        }
        changed_private_fields_rule = {
            **preview_rule,
            "id": 999,
            "owner_id": "changed-owner-private-marker",
            "note": "changed private memo",
            "rawPayload": {"marker": "changed-raw-payload-marker"},
            "persistedEventId": "changed-persisted-marker",
        }

        preview = evaluate_user_alert_dry_run(
            rule=preview_rule,
            observed_price=130.0,
            observed_at=observed_at,
            freshness={"status": "fresh", "rawPayload": {"marker": "freshness-private-marker"}},
            now=self.now,
        )
        changed_private_fields = evaluate_user_alert_dry_run(
            rule=changed_private_fields_rule,
            observed_price=130.0,
            observed_at=observed_at,
            freshness={"status": "fresh", "rawPayload": {"marker": "changed-freshness-private-marker"}},
            now=self.now,
        )

        packet = build_user_alert_event_packet(result=preview, now=created_at)
        changed_packet = build_user_alert_event_packet(result=changed_private_fields, now=created_at)

        self.assertEqual(packet["observedAsOf"], "2026-06-08T10:25:00Z")
        self.assertEqual(packet["createdAt"], "2026-06-08T10:32:00Z")
        self.assertTrue(packet["dryRun"])
        self.assertFalse(packet["outboundAttempted"])
        self.assertFalse(packet["liveOutbound"])
        self.assertTrue(packet["localOnly"])
        self.assertEqual(preview["dedupeFingerprint"], changed_private_fields["dedupeFingerprint"])
        self.assertEqual(packet["safeMetadata"]["dedupeFingerprint"], preview["dedupeFingerprint"])
        self.assertEqual(packet["fingerprint"], changed_packet["fingerprint"])

        serialized = json.dumps(
            {
                "evaluation": preview,
                "packet": packet,
            },
            ensure_ascii=False,
        ).lower()
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

    def test_blocked_results_remain_bounded_and_local_only(self) -> None:
        evaluation = evaluate_user_alert_dry_run(
            rule=self.rule,
            observed_price=None,
            observed_at=self.now,
            freshness={"status": "fresh"},
            now=self.now,
        )

        packet = build_user_alert_event_packet(result=evaluation, now=self.now)

        self.assertEqual(packet["state"], "blocked_insufficient_data")
        self.assertEqual(packet["observedAsOf"], "2026-06-08T10:30:00Z")
        self.assertIn("数据不足", packet["title"])
        self.assertIn("最近一次可用", packet["message"])
        self.assertTrue(packet["localOnly"])

    def test_module_stays_free_of_protected_runtime_imports(self) -> None:
        module = importlib.import_module("src.services.user_alert_event_packet")
        self.assertTrue(hasattr(module, "build_user_alert_event_packet"))

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
