# -*- coding: utf-8 -*-
"""Synthetic tests for provider circuit dry-run observations."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.provider_circuit_observer import ProviderCircuitObserver
from src.storage import DatabaseManager, ProviderCircuitEvent, ProviderProbeEvent, ProviderQuotaWindow


def _fresh_db() -> DatabaseManager:
    DatabaseManager.reset_instance()
    return DatabaseManager(db_url="sqlite:///:memory:")


class ProviderCircuitObserverTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _fresh_db()
        self.observer = ProviderCircuitObserver(db=self.db)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()

    def test_timeout_observation_records_dry_run_failure_counter_and_event_only(self) -> None:
        observed_at = datetime(2026, 5, 6, 10, 15, 30)

        result = self.observer.record_observation(
            provider="FMP",
            provider_category="quote",
            route_family="analysis",
            result_bucket="timeout",
            duration_ms=1234,
            observed_at=observed_at,
            metadata={
                "safe_label": "fixture",
                "url": "https://provider.example.test/raw?api_key=must-not-leak",
                "exception_text": "Traceback must-not-leak",
            },
        )

        self.assertEqual(result["quota_window"]["request_count"], 1)
        self.assertEqual(result["quota_window"]["failure_count"], 1)
        self.assertEqual(result["quota_window"]["timeout_count"], 1)
        self.assertEqual(result["event"]["event_type"], "policy_dry_run")
        self.assertEqual(result["event"]["reason_bucket"], "timeout")
        self.assertEqual(result["event"]["duration_bucket_ms"], 1500)
        self.assertEqual(
            result["event"]["metadata"],
            {
                "safe_label": "fixture",
                "dry_run": True,
                "observation_kind": "result",
                "result_bucket": "timeout",
            },
        )
        self.assertIsNone(result["state"])

        with self.db.session_scope() as session:
            self.assertEqual(session.query(ProviderQuotaWindow).count(), 1)
            self.assertEqual(session.query(ProviderCircuitEvent).count(), 1)
            self.assertEqual(session.query(ProviderProbeEvent).count(), 0)
            self.assertEqual(session.query(ProviderCircuitEvent).one().to_state, None)

    def test_success_observation_records_counter_without_circuit_event_or_state(self) -> None:
        result = self.observer.record_observation(
            provider="finnhub",
            provider_category="news",
            route_family="guest_preview",
            result_bucket="success",
            observed_at=datetime(2026, 5, 6, 11, 5, 0),
        )

        self.assertEqual(result["quota_window"]["request_count"], 1)
        self.assertEqual(result["quota_window"]["success_count"], 1)
        self.assertIsNone(result["event"])
        self.assertIsNone(result["state"])
        with self.db.session_scope() as session:
            self.assertEqual(session.query(ProviderCircuitEvent).count(), 0)

    def test_probe_like_observation_records_probe_event_and_probe_counter(self) -> None:
        with patch("requests.sessions.Session.request") as request_mock:
            result = self.observer.record_observation(
                provider="tavily",
                provider_category="probe",
                route_family="admin_provider_probe",
                result_bucket="provider_403",
                probe_type="synthetic_fixture",
                duration_ms=220,
                observed_at=datetime(2026, 5, 6, 12, 0, 0),
                metadata={"safe_label": "probe", "token": "must-not-leak"},
            )

        self.assertEqual(result["quota_window"]["probe_count"], 1)
        self.assertEqual(result["quota_window"]["provider_403_count"], 1)
        self.assertEqual(result["probe_event"]["result_bucket"], "provider_403")
        self.assertEqual(result["probe_event"]["duration_bucket_ms"], 250)
        self.assertEqual(
            result["probe_event"]["metadata"],
            {
                "safe_label": "probe",
                "dry_run": True,
                "observation_kind": "result",
                "result_bucket": "provider_403",
            },
        )
        request_mock.assert_not_called()

    def test_quota_policy_block_observation_counts_rejected_not_live_request(self) -> None:
        result = self.observer.record_observation(
            provider="alpha_vantage",
            provider_category="fundamentals",
            route_family="analysis",
            result_bucket="quota_policy_block",
            observed_at=datetime(2026, 5, 6, 13, 0, 0),
        )

        self.assertEqual(result["quota_window"]["request_count"], 0)
        self.assertEqual(result["quota_window"]["rejected_count"], 1)
        self.assertEqual(result["quota_window"]["failure_count"], 1)
        self.assertEqual(result["event"]["reason_bucket"], "quota_policy_block")

    def test_cooldown_observation_is_event_only_and_does_not_open_state(self) -> None:
        result = self.observer.record_cooldown_observation(
            provider="alpaca",
            provider_category="quote",
            route_family="analysis",
            reason_bucket="timeout",
            cooldown_until=datetime(2026, 5, 6, 10, 30, 0),
            observed_at=datetime(2026, 5, 6, 10, 20, 0),
        )

        self.assertIsNone(result["quota_window"])
        self.assertIsNone(result["state"])
        self.assertEqual(result["event"]["event_type"], "policy_dry_run")
        self.assertEqual(result["event"]["reason_bucket"], "timeout")
        self.assertEqual(result["event"]["metadata"]["observation_kind"], "cooldown")
        with self.db.session_scope() as session:
            self.assertEqual(session.query(ProviderQuotaWindow).count(), 0)

    def test_unsupported_observation_bucket_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.observer.record_observation(
                provider="fmp",
                result_bucket="raw_exception_message",
                observed_at=datetime(2026, 5, 6, 14, 0, 0),
            )

    def test_window_bounds_are_derived_from_observed_at(self) -> None:
        result = self.observer.record_observation(
            provider="fmp",
            result_bucket="provider_429",
            window_type="minute",
            observed_at=datetime(2026, 5, 6, 14, 17, 42),
        )

        self.assertEqual(result["quota_window"]["window_start"], "2026-05-06T14:17:00")
        self.assertEqual(result["quota_window"]["window_end"], "2026-05-06T14:18:00")


if __name__ == "__main__":
    unittest.main()
