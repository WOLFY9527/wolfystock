# -*- coding: utf-8 -*-
"""Synthetic tests for provider circuit/quota storage foundation."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from sqlalchemy import inspect

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.storage import DatabaseManager, ProviderCircuitEvent, ProviderProbeEvent


def _fresh_db() -> DatabaseManager:
    DatabaseManager.reset_instance()
    return DatabaseManager(db_url="sqlite:///:memory:")


class ProviderCircuitStorageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _fresh_db()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()

    def test_table_initialization_creates_provider_circuit_foundation(self) -> None:
        tables = set(inspect(self.db._engine).get_table_names())

        self.assertTrue(
            {
                "provider_quota_policies",
                "provider_quota_windows",
                "provider_circuit_states",
                "provider_circuit_events",
                "provider_probe_events",
            }.issubset(tables)
        )

    def test_circuit_state_upsert_and_read(self) -> None:
        self.db.upsert_provider_circuit_state(
            provider="FMP",
            provider_category="quote",
            route_family="analysis",
            state="closed",
            metadata={"policy_version": "v1"},
        )

        row = self.db.get_provider_circuit_state(
            provider="fmp",
            provider_category="quote",
            route_family="analysis",
        )

        self.assertIsNotNone(row)
        self.assertEqual(row["provider"], "fmp")
        self.assertEqual(row["state"], "closed")
        self.assertEqual(row["metadata"], {"policy_version": "v1"})

    def test_closed_to_open_transition_writes_event(self) -> None:
        result = self.db.transition_provider_circuit_state(
            provider="fmp",
            provider_category="quote",
            route_family="analysis",
            to_state="open",
            reason_bucket="timeout",
            cooldown_until=datetime.now() + timedelta(minutes=5),
            metadata={"safe_reason": "timeout_spike"},
        )

        self.assertEqual(result["previous_state"], "closed")
        self.assertEqual(result["state"], "open")
        self.assertEqual(result["transition_event"]["from_state"], "closed")
        self.assertEqual(result["transition_event"]["to_state"], "open")
        self.assertEqual(result["last_transition_event_id"], result["transition_event"]["id"])
        with self.db.session_scope() as session:
            self.assertEqual(session.query(ProviderCircuitEvent).count(), 1)

    def test_open_to_half_open_transition_with_cooldown_and_sample_fields(self) -> None:
        self.db.transition_provider_circuit_state(
            provider="fmp",
            provider_category="quote",
            route_family="analysis",
            to_state="open",
            reason_bucket="provider_5xx",
        )
        started = datetime.now()

        result = self.db.transition_provider_circuit_state(
            provider="fmp",
            provider_category="quote",
            route_family="analysis",
            to_state="half_open",
            reason_bucket="synthetic_test",
            cooldown_until=started,
            half_open_started_at=started,
            half_open_sample_limit=2,
            half_open_sample_count=1,
        )

        self.assertEqual(result["previous_state"], "open")
        self.assertEqual(result["state"], "half_open")
        self.assertEqual(result["half_open_sample_limit"], 2)
        self.assertEqual(result["half_open_sample_count"], 1)
        self.assertIsNotNone(result["cooldown_until"])
        self.assertIsNotNone(result["half_open_started_at"])

    def test_half_open_to_closed_transition(self) -> None:
        self.db.transition_provider_circuit_state(
            provider="fmp",
            provider_category="quote",
            route_family="analysis",
            to_state="half_open",
            reason_bucket="synthetic_test",
        )

        result = self.db.transition_provider_circuit_state(
            provider="fmp",
            provider_category="quote",
            route_family="analysis",
            to_state="closed",
            reason_bucket="recovered",
            success_sample_count=2,
            failure_sample_count=0,
        )

        self.assertEqual(result["previous_state"], "half_open")
        self.assertEqual(result["state"], "closed")
        self.assertIsNone(result["opened_at"])
        self.assertEqual(result["success_sample_count"], 2)

    def test_provider_quota_depleted_state(self) -> None:
        result = self.db.transition_provider_circuit_state(
            provider="finnhub",
            provider_category="news",
            route_family="guest_preview",
            to_state="provider_quota_depleted",
            reason_bucket="provider_429",
            cooldown_until=datetime.now() + timedelta(hours=1),
        )

        self.assertEqual(result["state"], "provider_quota_depleted")
        self.assertEqual(result["reason_bucket"], "provider_429")
        self.assertIsNotNone(result["opened_at"])

    def test_disabled_by_operator_state_uses_safe_operator_reference(self) -> None:
        result = self.db.transition_provider_circuit_state(
            provider="tavily",
            provider_category="search",
            route_family="admin_provider_probe",
            to_state="disabled_by_operator",
            reason_bucket="operator_disabled",
            operator_action_ref="audit-ticket-123",
            metadata={"operator_note": "planned maintenance", "token": "not-real"},
        )

        self.assertEqual(result["state"], "disabled_by_operator")
        self.assertEqual(result["operator_action_ref"], "audit-ticket-123")
        self.assertEqual(result["metadata"], {"operator_note": "planned maintenance"})

    def test_quota_window_counter_update(self) -> None:
        start = datetime(2026, 5, 6, 10, 0, 0)
        end = start + timedelta(hours=1)

        self.db.update_provider_quota_window_counters(
            provider="fmp",
            provider_category="quote",
            route_family="analysis",
            window_type="hour",
            window_start=start,
            window_end=end,
            request_delta=1,
            reserved_units_delta=4,
            consumed_units_delta=3,
            success_delta=1,
        )
        result = self.db.update_provider_quota_window_counters(
            provider="fmp",
            provider_category="quote",
            route_family="analysis",
            window_type="hour",
            window_start=start,
            window_end=end,
            request_delta=1,
            provider_429_delta=1,
            failure_delta=1,
            fallback_delta=1,
        )

        self.assertEqual(result["request_count"], 2)
        self.assertEqual(result["reserved_units"], 4)
        self.assertEqual(result["consumed_units"], 3)
        self.assertEqual(result["success_count"], 1)
        self.assertEqual(result["failure_count"], 1)
        self.assertEqual(result["provider_429_count"], 1)
        self.assertEqual(result["fallback_count"], 1)

    def test_metadata_sanitizer_drops_secret_like_keys(self) -> None:
        result = self.db.transition_provider_circuit_state(
            provider="fmp",
            to_state="open",
            reason_bucket="network_error",
            metadata={
                "safe_label": "fixture",
                "api_key": "not-real",
                "nested": {"token": "not-real-token", "keep": "ok"},
            },
        )

        self.assertEqual(result["metadata"], {"safe_label": "fixture", "nested": {"keep": "ok"}})
        self.assertNotIn("not-real", str(result["metadata"]))

    def test_no_raw_payload_url_key_token_cookie_session_or_stack_trace_stored(self) -> None:
        payload = {
            "safe_label": "fixture",
            "provider_payload": {"price": 1},
            "url": "https://provider.example/path?api_key=not-real",
            "raw_response": "secret body",
            "error": "Traceback (most recent call last)\nsecret stack",
            "cookie": "not-real-cookie",
            "session_id": "not-real-session",
            "safe_nested": {"request_params": {"symbol": "AAPL"}, "keep": "ok"},
        }

        result = self.db.transition_provider_circuit_state(
            provider="fmp",
            to_state="open",
            reason_bucket="malformed_payload",
            metadata=payload,
        )
        event = result["transition_event"]
        stored = f"{result['metadata']} {event['metadata']}"

        self.assertIn("safe_label", str(result["metadata"]))
        self.assertIn("keep", str(result["metadata"]))
        for forbidden in (
            "https://",
            "api_key",
            "not-real",
            "secret body",
            "Traceback",
            "cookie",
            "session",
            "request_params",
        ):
            self.assertNotIn(forbidden, stored)

    def test_record_provider_probe_event_is_synthetic_storage_only(self) -> None:
        with patch("requests.sessions.Session.request") as request_mock:
            result = self.db.record_provider_probe_event(
                provider="fmp",
                provider_category="probe",
                route_family="admin_provider_probe",
                probe_type="synthetic_fixture",
                probe_source="dry_run",
                result_bucket="success",
                metadata={"safe_label": "fixture", "url": "https://provider.example"},
            )

        self.assertEqual(result["result_bucket"], "success")
        self.assertEqual(result["metadata"], {"safe_label": "fixture"})
        request_mock.assert_not_called()
        with self.db.session_scope() as session:
            self.assertEqual(session.query(ProviderProbeEvent).count(), 1)


if __name__ == "__main__":
    unittest.main()
