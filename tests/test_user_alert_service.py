# -*- coding: utf-8 -*-
"""Focused tests for owner-scoped user alert contracts."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from src.services.user_alert_dry_run_pipeline import build_user_alert_dry_run_pipeline_result
from src.services.user_alert_service import UserAlertService
from src.storage import DatabaseManager


class UserAlertServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.db = DatabaseManager(db_url="sqlite:///:memory:")
        self.db.create_or_update_app_user(user_id="user-1", username="alice", role="user")
        self.db.create_or_update_app_user(user_id="user-2", username="bob", role="user")
        self.service = UserAlertService(db_manager=self.db)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()

    def test_owner_can_create_list_update_and_delete_watchlist_threshold_rule(self) -> None:
        created = self.service.create_rule(
            owner_id="user-1",
            symbol="nvda",
            direction="above",
            threshold_price=125.5,
            enabled=True,
            note="Only show inside the app.",
        )

        self.assertEqual(created["contract_version"], "user_alert_contract_v1")
        self.assertEqual(created["rule_type"], "watchlist_price_threshold")
        self.assertEqual(created["symbol"], "NVDA")
        self.assertEqual(created["direction"], "above")
        self.assertEqual(created["threshold_price"], 125.5)
        self.assertTrue(created["enabled"])
        self.assertTrue(created["in_app_only"])
        self.assertEqual(created["delivery_mode"], "in_app")
        self.assertTrue(created["owner_scoped"])
        self.assertEqual(created["note"], "Only show inside the app.")

        listed = self.service.list_rules(owner_id="user-1")
        self.assertEqual([item["id"] for item in listed], [created["id"]])

        updated = self.service.update_rule(
            owner_id="user-1",
            rule_id=created["id"],
            direction="below",
            threshold_price=118.25,
            enabled=False,
            note=None,
        )
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["direction"], "below")
        self.assertEqual(updated["threshold_price"], 118.25)
        self.assertFalse(updated["enabled"])
        self.assertIsNone(updated["note"])

        self.assertTrue(self.service.delete_rule(owner_id="user-1", rule_id=created["id"]))
        self.assertEqual(self.service.list_rules(owner_id="user-1"), [])

    def test_another_owner_cannot_access_or_mutate_rule(self) -> None:
        created = self.service.create_rule(
            owner_id="user-1",
            symbol="AAPL",
            direction="below",
            threshold_price=150,
        )

        self.assertEqual(self.service.list_rules(owner_id="user-2"), [])
        self.assertIsNone(self.service.get_rule(owner_id="user-2", rule_id=created["id"]))
        self.assertIsNone(
            self.service.update_rule(
                owner_id="user-2",
                rule_id=created["id"],
                enabled=False,
            )
        )
        self.assertFalse(self.service.delete_rule(owner_id="user-2", rule_id=created["id"]))
        self.assertIsNotNone(self.service.get_rule(owner_id="user-1", rule_id=created["id"]))

    def test_invalid_threshold_and_direction_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "direction"):
            self.service.create_rule(
                owner_id="user-1",
                symbol="AAPL",
                direction="near",
                threshold_price=150,
            )

        with self.assertRaisesRegex(ValueError, "threshold_price"):
            self.service.create_rule(
                owner_id="user-1",
                symbol="AAPL",
                direction="above",
                threshold_price=0,
            )

    def test_contract_does_not_call_provider_quotes_or_notification_delivery(self) -> None:
        with (
            patch("data_provider.base.DataFetcherManager.get_realtime_quote") as get_quote,
            patch("src.services.notification_service.NotificationService.emit_event") as emit_event,
            patch("src.services.notification_service.NotificationDeliveryClient.send_webhook") as send_webhook,
        ):
            self.service.create_rule(
                owner_id="user-1",
                symbol="MSFT",
                direction="above",
                threshold_price=425.0,
            )
            self.service.list_rules(owner_id="user-1")

        get_quote.assert_not_called()
        emit_event.assert_not_called()
        send_webhook.assert_not_called()

    def test_created_rule_can_feed_pure_dry_run_pipeline_without_persisting_events(self) -> None:
        observed_at = datetime(2026, 6, 8, 10, 30, tzinfo=timezone.utc)
        recorded_at = datetime(2026, 6, 8, 10, 31, tzinfo=timezone.utc)
        created = self.service.create_rule(
            owner_id="user-1",
            symbol="nvda",
            direction="above",
            threshold_price=125.5,
            enabled=True,
            note="Local review only.",
        )
        before_events = self.service.list_events(owner_id="user-1")

        result = build_user_alert_dry_run_pipeline_result(
            rule=created,
            observed_price=130.0,
            observed_at=observed_at,
            freshness={"status": "fresh", "maxAgeMinutes": 120},
            suppression={
                "muted": False,
                "snoozedUntil": None,
                "cooldownStartedAt": None,
                "cooldownSeconds": None,
                "previousFingerprint": "older-local-fingerprint",
                "previousTimeBucket": "202606080900",
            },
            now=observed_at,
            recorded_at=recorded_at,
        )

        after_events = self.service.list_events(owner_id="user-1")
        self.assertEqual(after_events, before_events)
        self.assertEqual(after_events["total"], 0)
        self.assertEqual(after_events["items"], [])

        self.assertTrue(result["dryRun"])
        self.assertTrue(result["noSend"])
        self.assertTrue(result["localOnly"])
        self.assertFalse(result["outboundAttempted"])
        self.assertFalse(result["liveOutbound"])

        evaluation = result["evaluation"]
        self.assertEqual(evaluation["ruleType"], "watchlist_price_threshold")
        self.assertEqual(evaluation["subject"], "NVDA")
        self.assertEqual(evaluation["state"], "condition_observed")
        self.assertTrue(evaluation["conditionObserved"])
        self.assertFalse(evaluation["suppressed"])
        self.assertTrue(evaluation["dryRun"])
        self.assertFalse(evaluation["outboundAttempted"])
        self.assertFalse(evaluation["liveOutbound"])
        self.assertFalse(evaluation["providerRuntimeCalled"])
        self.assertFalse(evaluation["networkCallsEnabled"])
        self.assertFalse(evaluation["marketCacheMutation"])

        packet = result["eventPacket"]
        self.assertIsNotNone(packet)
        assert packet is not None
        self.assertTrue(packet["dryRun"])
        self.assertTrue(packet["localOnly"])
        self.assertFalse(packet["outboundAttempted"])
        self.assertFalse(packet["liveOutbound"])
        self.assertEqual(packet["eventType"], "user.alert_dry_run_evaluation")

    def test_events_are_owner_scoped_sanitized_and_in_app_only(self) -> None:
        rule = self.service.create_rule(
            owner_id="user-1",
            symbol="TSLA",
            direction="above",
            threshold_price=200,
        )
        event = self.service.record_in_app_event(
            owner_id="user-1",
            rule_id=rule["id"],
            title="Price threshold condition recorded",
            message="Condition recorded for in-app review.",
        )

        self.assertEqual(event["rule_id"], rule["id"])
        self.assertEqual(event["symbol"], "TSLA")
        self.assertEqual(event["direction"], "above")
        self.assertTrue(event["in_app_only"])
        self.assertEqual(event["delivery_mode"], "in_app")
        self.assertNotIn("provider", str(event).lower())
        self.assertNotIn("webhook", str(event).lower())
        self.assertNotIn("admin", str(event).lower())
        self.assertEqual(self.service.list_events(owner_id="user-2")["items"], [])
        self.assertEqual(self.service.list_events(owner_id="user-1")["items"][0]["id"], event["id"])


if __name__ == "__main__":
    unittest.main()
