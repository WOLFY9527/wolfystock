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

    def test_preflight_state_classifies_success_as_healthy_without_enforcement(self) -> None:
        result = self.observer.classify_preflight_state(result_bucket="success")

        self.assertEqual(result["preflight_state"], "healthy")
        self.assertEqual(result["state_candidate"], "closed")
        self.assertFalse(result["live_enforcement"])
        self.assertFalse(result["would_block_call"])
        self.assertFalse(result["would_change_provider_order"])
        self.assertFalse(result["would_change_fallback_behavior"])

    def test_preflight_state_classifies_quota_and_auth_buckets_as_degraded_candidates(self) -> None:
        quota_result = self.observer.classify_preflight_state(result_bucket="provider_429")
        auth_result = self.observer.classify_preflight_state(result_bucket="auth_or_key_invalid")

        self.assertEqual(quota_result["preflight_state"], "degraded")
        self.assertEqual(quota_result["state_candidate"], "provider_quota_depleted")
        self.assertEqual(auth_result["preflight_state"], "degraded")
        self.assertEqual(auth_result["state_candidate"], "disabled_by_operator")
        self.assertFalse(quota_result["live_enforcement"])
        self.assertFalse(auth_result["live_enforcement"])

    def test_preflight_state_classifies_timeout_and_5xx_buckets_as_open_candidates(self) -> None:
        timeout_result = self.observer.classify_preflight_state(result_bucket="timeout")
        error_result = self.observer.classify_preflight_state(result_bucket="provider_5xx")

        self.assertEqual(timeout_result["preflight_state"], "open_candidate")
        self.assertEqual(timeout_result["state_candidate"], "open")
        self.assertEqual(error_result["preflight_state"], "open_candidate")
        self.assertEqual(error_result["state_candidate"], "open")
        self.assertFalse(timeout_result["would_block_call"])
        self.assertFalse(error_result["would_change_provider_order"])

    def test_record_observation_returns_matching_preflight_state_without_durable_transition(self) -> None:
        result = self.observer.record_observation(
            provider="fmp",
            provider_category="quote",
            route_family="analysis",
            result_bucket="provider_429",
            observed_at=datetime(2026, 5, 6, 15, 0, 0),
        )

        self.assertEqual(result["preflight"]["preflight_state"], "degraded")
        self.assertEqual(result["preflight"]["state_candidate"], "provider_quota_depleted")
        self.assertFalse(result["preflight"]["live_enforcement"])
        self.assertIsNone(result["state"])

    def test_sla_readiness_diagnostics_summarize_recent_errors_without_secrets_or_enforcement(self) -> None:
        with patch("requests.sessions.Session.request") as request_mock:
            self.observer.record_observation(
                provider="FMP",
                provider_category="quote",
                route_family="analysis",
                result_bucket="timeout",
                duration_ms=1200,
                observed_at=datetime(2026, 5, 6, 15, 0, 0),
                metadata={
                    "safe_label": "fixture",
                    "api_key": "must-not-leak",
                    "url": "https://provider.example.test/raw?token=must-not-leak",
                    "raw_payload": "must-not-leak",
                },
            )
            self.observer.record_observation(
                provider="fmp",
                provider_category="quote",
                route_family="analysis",
                result_bucket="provider_429",
                duration_ms=80,
                observed_at=datetime(2026, 5, 6, 15, 5, 0),
                metadata={"authorization": "Bearer must-not-leak"},
            )
            diagnostics = self.observer.build_sla_readiness_diagnostics(
                provider="FMP",
                provider_category="quote",
                route_family="analysis",
                now=datetime(2026, 5, 6, 15, 10, 0),
            )

        self.assertEqual(diagnostics["provider"], "fmp")
        self.assertTrue(diagnostics["readOnly"])
        self.assertTrue(diagnostics["noExternalCalls"])
        self.assertFalse(diagnostics["liveEnforcement"])
        self.assertFalse(diagnostics["providerBehaviorChanged"])
        self.assertFalse(diagnostics["marketCacheBehaviorChanged"])
        self.assertEqual(diagnostics["sla"]["latencyBucketMs"], 100)
        self.assertEqual(diagnostics["sla"]["latencyState"], "normal")
        self.assertEqual(diagnostics["sla"]["errorRate"], 1.0)
        self.assertEqual(diagnostics["sla"]["errorState"], "critical")
        self.assertEqual(diagnostics["sla"]["freshnessSeconds"], 300)
        self.assertEqual(diagnostics["sla"]["freshnessState"], "fresh")
        self.assertEqual(diagnostics["counters"]["requestCount"], 2)
        self.assertEqual(diagnostics["counters"]["failureCount"], 2)
        self.assertEqual(diagnostics["trendSummary"]["windowCountBucket"], "1")
        self.assertEqual(diagnostics["trendSummary"]["requestCountBucket"], "2_5")
        self.assertEqual(diagnostics["trendSummary"]["failureCountBucket"], "2_5")
        self.assertEqual(diagnostics["trendSummary"]["provider429CountBucket"], "1")
        self.assertEqual(diagnostics["trendSummary"]["latestObservationAt"], "2026-05-06T15:05:00")
        self.assertEqual(diagnostics["recentErrors"][0]["reasonBucket"], "provider_429")
        self.assertEqual(diagnostics["recentErrors"][0]["countBucket"], "1")
        self.assertEqual(diagnostics["circuitPreflight"]["preflight_state"], "degraded")
        self.assertFalse(diagnostics["circuitPreflight"]["would_block_call"])
        self.assertTrue(diagnostics["circuitPreflight"]["would_block_if_enforced"])
        self.assertEqual(diagnostics["circuitPreflight"]["enforcement_block_reason_code"], "provider_429")
        self.assertFalse(diagnostics["circuitPreflight"]["would_change_provider_order"])
        self.assertFalse(diagnostics["circuitPreflight"]["would_change_fallback_behavior"])
        request_mock.assert_not_called()
        text = str(diagnostics).lower()
        for blocked in (
            "must-not-leak",
            "api_key",
            "token",
            "authorization",
            "raw_payload",
            "https://provider.example",
        ):
            self.assertNotIn(blocked, text)

    def test_sla_readiness_diagnostics_normalize_empty_observations(self) -> None:
        diagnostics = self.observer.build_sla_readiness_diagnostics(
            provider="tradier",
            now=datetime(2026, 5, 6, 15, 10, 0),
        )

        self.assertEqual(diagnostics["provider"], "tradier")
        self.assertEqual(diagnostics["sla"]["latencyState"], "unknown")
        self.assertEqual(diagnostics["sla"]["errorState"], "unknown")
        self.assertEqual(diagnostics["sla"]["freshnessState"], "unknown")
        self.assertEqual(diagnostics["trendSummary"]["requestCountBucket"], "0")
        self.assertIsNone(diagnostics["trendSummary"]["latestObservationAt"])
        self.assertEqual(diagnostics["recentErrors"], [])
        self.assertEqual(diagnostics["circuitPreflight"]["preflight_state"], "healthy")
        self.assertFalse(diagnostics["circuitPreflight"]["would_block_call"])
        self.assertFalse(diagnostics["circuitPreflight"]["would_block_if_enforced"])
        self.assertIsNone(diagnostics["circuitPreflight"]["enforcement_block_reason_code"])

    def test_cooldown_observation_returns_open_candidate_preflight_without_state_change(self) -> None:
        result = self.observer.record_cooldown_observation(
            provider="alpaca",
            provider_category="quote",
            route_family="analysis",
            reason_bucket="timeout",
            cooldown_until=datetime(2026, 5, 6, 16, 0, 0),
            observed_at=datetime(2026, 5, 6, 15, 30, 0),
        )

        self.assertEqual(result["preflight"]["preflight_state"], "open_candidate")
        self.assertEqual(result["preflight"]["state_candidate"], "open")
        self.assertFalse(result["preflight"]["live_enforcement"])
        self.assertTrue(result["preflight"]["would_block_if_enforced"])
        self.assertEqual(result["preflight"]["enforcement_block_reason_code"], "timeout")
        self.assertIsNone(result["state"])

    def test_controlled_enforcement_decision_is_disabled_by_default_for_blocked_state(self) -> None:
        self.db.transition_provider_circuit_state(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            to_state="open",
            reason_bucket="timeout",
            cooldown_until=datetime(2026, 5, 6, 16, 0, 0),
            now=datetime(2026, 5, 6, 15, 0, 0),
        )

        decision = self.observer.build_controlled_enforcement_decision(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            now=datetime(2026, 5, 6, 15, 30, 0),
        )

        self.assertEqual(decision["controlled_enforcement_status"], "disabled_by_default")
        self.assertFalse(decision["controlled_enforcement_enabled"])
        self.assertFalse(decision["controlled_scope_matched"])
        self.assertFalse(decision["live_enforcement"])
        self.assertFalse(decision["would_block_call"])
        self.assertTrue(decision["would_block_if_enforced"])
        self.assertEqual(decision["enforcement_block_reason_code"], "timeout")
        self.assertFalse(decision["would_change_provider_order"])
        self.assertFalse(decision["would_change_fallback_behavior"])
        self.assertTrue(decision["no_external_calls"])

    def test_controlled_enforcement_requires_explicit_matching_scope(self) -> None:
        self.db.transition_provider_circuit_state(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            to_state="provider_quota_depleted",
            reason_bucket="provider_429",
            now=datetime(2026, 5, 6, 15, 0, 0),
        )

        decision = self.observer.build_controlled_enforcement_decision(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            controlled_enforcement_enabled=True,
            controlled_provider_categories=("options",),
            controlled_route_families=("analysis",),
            now=datetime(2026, 5, 6, 15, 30, 0),
        )

        self.assertEqual(decision["controlled_enforcement_status"], "scope_not_enabled")
        self.assertTrue(decision["controlled_enforcement_enabled"])
        self.assertFalse(decision["controlled_scope_matched"])
        self.assertFalse(decision["live_enforcement"])
        self.assertFalse(decision["would_block_call"])
        self.assertTrue(decision["would_block_if_enforced"])
        self.assertEqual(decision["enforcement_block_reason_code"], "provider_429")

    def test_controlled_enforcement_enabled_for_scoped_block_returns_enforceable_decision_only(self) -> None:
        self.db.transition_provider_circuit_state(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            to_state="disabled_by_operator",
            reason_bucket="auth_or_key_invalid",
            now=datetime(2026, 5, 6, 15, 0, 0),
        )

        with patch("requests.sessions.Session.request") as request_mock:
            decision = self.observer.build_controlled_enforcement_decision(
                provider="tradier",
                provider_category="options",
                route_family="options_lab",
                controlled_enforcement_enabled=True,
                controlled_provider_categories=("options",),
                controlled_route_families=("options_lab",),
                now=datetime(2026, 5, 6, 15, 30, 0),
            )

        self.assertEqual(decision["controlled_enforcement_status"], "blocked")
        self.assertTrue(decision["controlled_enforcement_enabled"])
        self.assertTrue(decision["controlled_scope_matched"])
        self.assertTrue(decision["live_enforcement"])
        self.assertTrue(decision["would_block_call"])
        self.assertTrue(decision["would_block_if_enforced"])
        self.assertEqual(decision["enforcement_block_reason_code"], "auth_or_key_invalid")
        self.assertFalse(decision["would_change_provider_order"])
        self.assertFalse(decision["would_change_fallback_behavior"])
        self.assertFalse(decision["provider_behavior_changed"])
        self.assertFalse(decision["market_cache_behavior_changed"])
        request_mock.assert_not_called()

    def test_controlled_enforcement_decision_does_not_mutate_circuit_rows_when_disabled(self) -> None:
        self.db.transition_provider_circuit_state(
            provider="polygon",
            provider_category="options",
            route_family="options_lab",
            to_state="open",
            reason_bucket="provider_5xx",
            now=datetime(2026, 5, 6, 15, 0, 0),
        )
        with self.db.session_scope() as session:
            state_count = session.query(ProviderCircuitEvent).count()

        decision = self.observer.build_controlled_enforcement_decision(
            provider="polygon",
            provider_category="options",
            route_family="options_lab",
        )

        self.assertEqual(decision["controlled_enforcement_status"], "disabled_by_default")
        self.assertFalse(decision["would_block_call"])
        self.assertTrue(decision["would_block_if_enforced"])
        with self.db.session_scope() as session:
            self.assertEqual(session.query(ProviderCircuitEvent).count(), state_count)


if __name__ == "__main__":
    unittest.main()
