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

    def _assert_advisory_only_projection(self, payload: dict) -> None:
        self.assertTrue(payload["advisory_only"])
        self.assertEqual(payload["default_off_label"], "provider_circuit_live_enforcement_default_off")
        self.assertEqual(payload["rollback_label"], "no_runtime_change_to_rollback")
        self.assertFalse(payload["live_enforcement"])
        self.assertFalse(payload["would_block_call"])
        self.assertFalse(payload["would_change_provider_order"])
        self.assertFalse(payload["would_change_fallback_behavior"])
        self.assertTrue(payload["no_external_calls"])
        self.assertFalse(payload["provider_behavior_changed"])
        self.assertFalse(payload["market_cache_behavior_changed"])

    def _assert_runtime_pilot_never_changes_provider_behavior(self, payload: dict) -> None:
        self.assertEqual(payload["contract_version"], "provider_reliability_runtime_v1")
        self.assertFalse(payload["production_enforcement_enabled"])
        self.assertFalse(payload["live_enforcement"])
        self.assertFalse(payload["would_block_call"])
        self.assertFalse(payload["would_change_provider_order"])
        self.assertFalse(payload["would_change_fallback_behavior"])
        self.assertTrue(payload["no_external_calls"])
        self.assertFalse(payload["provider_behavior_changed"])
        self.assertFalse(payload["market_cache_behavior_changed"])
        self.assertEqual(payload["default_off_label"], "provider_reliability_runtime_pilot_default_off")
        self.assertEqual(payload["rollback_label"], "provider_reliability_runtime_pilot_disable_flag")

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
        self._assert_advisory_only_projection(result)
        self.assertFalse(result["would_block_if_enforced"])
        self.assertIsNone(result["enforcement_block_reason_code"])

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

    def test_preflight_state_projects_failure_buckets_without_live_blocking(self) -> None:
        for bucket in sorted(self.observer.FAILURE_BUCKETS):
            with self.subTest(bucket=bucket):
                result = self.observer.classify_preflight_state(result_bucket=bucket)

                self._assert_advisory_only_projection(result)
                self.assertTrue(result["would_block_if_enforced"])
                self.assertEqual(result["enforcement_block_reason_code"], bucket)
                self.assertIn(result["enforcement_block_reason_code"], self.observer.RESULT_BUCKETS)

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
        self._assert_advisory_only_projection(decision)
        self.assertTrue(decision["would_block_if_enforced"])
        self.assertEqual(decision["enforcement_block_reason_code"], "timeout")

    def test_controlled_enforcement_decision_stays_advisory_when_enabled_scope_matches(self) -> None:
        self.db.transition_provider_circuit_state(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            to_state="open",
            reason_bucket="timeout",
            cooldown_until=datetime(2026, 5, 6, 16, 0, 0),
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

        self.assertTrue(decision["controlled_enforcement_enabled"])
        self.assertTrue(decision["controlled_scope_matched"])
        self.assertEqual(decision["controlled_enforcement_status"], "advisory_only_would_block_not_enforced")
        self._assert_advisory_only_projection(decision)
        self.assertTrue(decision["would_block_if_enforced"])
        self.assertEqual(decision["enforcement_block_reason_code"], "timeout")
        request_mock.assert_not_called()

    def test_admin_enforcement_projection_requires_explicit_matching_scope(self) -> None:
        self.db.transition_provider_circuit_state(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            to_state="provider_quota_depleted",
            reason_bucket="provider_429",
            now=datetime(2026, 5, 6, 15, 0, 0),
        )

        decision = self.observer.build_admin_enforcement_projection(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            controlled_provider_categories=("options",),
            controlled_route_families=("analysis",),
            now=datetime(2026, 5, 6, 15, 30, 0),
        )

        self.assertFalse(decision["scope_matched"])
        self._assert_advisory_only_projection(decision)
        self.assertTrue(decision["would_block_if_enforced"])
        self.assertEqual(decision["enforcement_block_reason_code"], "provider_429")

    def test_admin_enforcement_projection_for_scoped_block_returns_advisory_only(self) -> None:
        self.db.transition_provider_circuit_state(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            to_state="disabled_by_operator",
            reason_bucket="auth_or_key_invalid",
            now=datetime(2026, 5, 6, 15, 0, 0),
        )

        with patch("requests.sessions.Session.request") as request_mock:
            decision = self.observer.build_admin_enforcement_projection(
                provider="tradier",
                provider_category="options",
                route_family="options_lab",
                controlled_provider_categories=("options",),
                controlled_route_families=("options_lab",),
                now=datetime(2026, 5, 6, 15, 30, 0),
            )

        self.assertTrue(decision["scope_matched"])
        self._assert_advisory_only_projection(decision)
        self.assertTrue(decision["would_block_if_enforced"])
        self.assertEqual(decision["enforcement_block_reason_code"], "auth_or_key_invalid")
        request_mock.assert_not_called()

    def test_admin_enforcement_projection_respects_expired_cooldown_as_non_blocking_advisory(self) -> None:
        self.db.transition_provider_circuit_state(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            to_state="open",
            reason_bucket="timeout",
            cooldown_until=datetime(2026, 5, 6, 15, 0, 0),
            now=datetime(2026, 5, 6, 14, 30, 0),
        )

        decision = self.observer.build_admin_enforcement_projection(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            controlled_provider_categories=("options",),
            controlled_route_families=("options_lab",),
            now=datetime(2026, 5, 6, 15, 30, 0),
        )

        self.assertTrue(decision["scope_matched"])
        self._assert_advisory_only_projection(decision)
        self.assertFalse(decision["would_block_if_enforced"])
        self.assertIsNone(decision["enforcement_block_reason_code"])

    def test_admin_enforcement_projection_marks_half_open_sample_limit_as_advisory_only(self) -> None:
        self.db.transition_provider_circuit_state(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            to_state="half_open",
            reason_bucket="timeout",
            half_open_started_at=datetime(2026, 5, 6, 15, 0, 0),
            half_open_sample_limit=2,
            half_open_sample_count=2,
            now=datetime(2026, 5, 6, 15, 0, 0),
        )

        decision = self.observer.build_admin_enforcement_projection(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            controlled_provider_categories=("options",),
            controlled_route_families=("options_lab",),
            now=datetime(2026, 5, 6, 15, 30, 0),
        )

        self.assertEqual(decision["circuit_state"], "half_open")
        self.assertTrue(decision["scope_matched"])
        self._assert_advisory_only_projection(decision)
        self.assertTrue(decision["would_block_if_enforced"])
        self.assertEqual(decision["enforcement_block_reason_code"], "timeout")
        self.assertTrue(decision["half_open_sample_limit_reached"])
        self.assertEqual(decision["half_open_sample_limit"], 2)
        self.assertEqual(decision["half_open_sample_count"], 2)

    def test_sla_readiness_projection_marks_matching_scope_without_live_block(self) -> None:
        with patch("requests.sessions.Session.request") as request_mock:
            self.observer.record_observation(
                provider="tradier",
                provider_category="options",
                route_family="options_lab",
                result_bucket="auth_or_key_invalid",
                observed_at=datetime(2026, 5, 6, 15, 0, 0),
                metadata={
                    "safe_label": "projection",
                    "request_body": "must-not-leak",
                    "stack_trace": "Traceback must-not-leak",
                },
            )
            diagnostics = self.observer.build_sla_readiness_diagnostics(
                provider="tradier",
                provider_category="options",
                route_family="options_lab",
                now=datetime(2026, 5, 6, 15, 30, 0),
                controlled_provider_categories=("options",),
                controlled_route_families=("options_lab",),
            )

        projection = diagnostics["circuitPreflight"]
        self.assertTrue(projection["scope_matched"])
        self._assert_advisory_only_projection(projection)
        self.assertTrue(projection["would_block_if_enforced"])
        self.assertEqual(projection["enforcement_block_reason_code"], "auth_or_key_invalid")
        self.assertTrue(diagnostics["noExternalCalls"])
        self.assertFalse(diagnostics["liveEnforcement"])
        request_mock.assert_not_called()
        text = str(diagnostics).lower()
        for blocked in ("must-not-leak", "request_body", "stack_trace", "traceback"):
            self.assertNotIn(blocked, text)

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

    def test_runtime_pilot_policy_projects_timeout_429_403_and_5xx_buckets_without_enforcement(self) -> None:
        cases = (
            ("timeout", "open", "cooldown_active", "fallback_advised", "insufficient"),
            ("provider_429", "provider_quota_depleted", "quota_depleted", "quota_depleted", "insufficient"),
            ("provider_403", "disabled_by_operator", "operator_disabled", "operator_disabled", "insufficient"),
            ("provider_5xx", "open", "cooldown_active", "fallback_advised", "insufficient"),
        )
        for index, (bucket, state, health, degraded, sufficiency) in enumerate(cases):
            provider = f"tradier-{index}"
            with self.subTest(bucket=bucket):
                self.db.transition_provider_circuit_state(
                    provider=provider,
                    provider_category="options",
                    route_family="options_lab",
                    to_state=state,
                    reason_bucket=bucket,
                    cooldown_until=datetime(2026, 5, 6, 16, 0, 0),
                    now=datetime(2026, 5, 6, 15, 0, 0),
                )

                decision = self.observer.build_runtime_pilot_decision(
                    provider=provider,
                    provider_category="options",
                    route_family="options_lab",
                    pilot_enabled=True,
                    fallback_evaluation_enabled=True,
                    pilot_provider_categories=("options",),
                    pilot_route_families=("options_lab",),
                    now=datetime(2026, 5, 6, 15, 30, 0),
                )

                self._assert_runtime_pilot_never_changes_provider_behavior(decision)
                self.assertTrue(decision["pilot_enabled"])
                self.assertTrue(decision["scope_matched"])
                self.assertEqual(decision["health_status"], health)
                self.assertEqual(decision["degraded_status"], degraded)
                self.assertEqual(decision["sufficiency_status"], sufficiency)
                self.assertTrue(decision["would_block_if_enforced"])
                self.assertTrue(decision["pilot_would_block"])
                self.assertTrue(decision["would_fallback_if_enforced"])
                self.assertTrue(decision["pilot_would_fallback"])
                self.assertEqual(decision["enforcement_block_reason_code"], bucket)

    def test_runtime_pilot_cooldown_and_half_open_sampling_are_evaluation_only(self) -> None:
        self.db.transition_provider_circuit_state(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            to_state="open",
            reason_bucket="timeout",
            cooldown_until=datetime(2026, 5, 6, 15, 0, 0),
            now=datetime(2026, 5, 6, 14, 0, 0),
        )
        expired_cooldown = self.observer.build_runtime_pilot_decision(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            pilot_enabled=True,
            fallback_evaluation_enabled=True,
            pilot_provider_categories=("options",),
            pilot_route_families=("options_lab",),
            now=datetime(2026, 5, 6, 15, 30, 0),
        )

        self._assert_runtime_pilot_never_changes_provider_behavior(expired_cooldown)
        self.assertEqual(expired_cooldown["health_status"], "half_open_ready")
        self.assertTrue(expired_cooldown["half_open_sample_allowed"])
        self.assertFalse(expired_cooldown["would_block_if_enforced"])
        self.assertFalse(expired_cooldown["pilot_would_block"])
        self.assertEqual(expired_cooldown["degraded_status"], "recovery_sampling")

        self.db.transition_provider_circuit_state(
            provider="polygon",
            provider_category="options",
            route_family="options_lab",
            to_state="half_open",
            reason_bucket="provider_5xx",
            half_open_started_at=datetime(2026, 5, 6, 15, 10, 0),
            half_open_sample_limit=2,
            half_open_sample_count=2,
            now=datetime(2026, 5, 6, 15, 10, 0),
        )
        sample_limited = self.observer.build_runtime_pilot_decision(
            provider="polygon",
            provider_category="options",
            route_family="options_lab",
            pilot_enabled=True,
            fallback_evaluation_enabled=True,
            pilot_provider_categories=("options",),
            pilot_route_families=("options_lab",),
            now=datetime(2026, 5, 6, 15, 30, 0),
        )

        self._assert_runtime_pilot_never_changes_provider_behavior(sample_limited)
        self.assertEqual(sample_limited["health_status"], "half_open_sample_limited")
        self.assertEqual(sample_limited["half_open_sample_limit"], 2)
        self.assertEqual(sample_limited["half_open_sample_count"], 2)
        self.assertTrue(sample_limited["half_open_sample_limit_reached"])
        self.assertFalse(sample_limited["half_open_sample_allowed"])
        self.assertTrue(sample_limited["pilot_would_block"])
        self.assertTrue(sample_limited["pilot_would_fallback"])

    def test_runtime_pilot_scope_and_rollback_flags_suppress_pilot_actions(self) -> None:
        self.db.transition_provider_circuit_state(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            to_state="open",
            reason_bucket="timeout",
            cooldown_until=datetime(2026, 5, 6, 16, 0, 0),
            now=datetime(2026, 5, 6, 15, 0, 0),
        )

        out_of_scope = self.observer.build_runtime_pilot_decision(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            pilot_enabled=True,
            fallback_evaluation_enabled=True,
            pilot_provider_categories=("quote",),
            pilot_route_families=("analysis",),
            now=datetime(2026, 5, 6, 15, 30, 0),
        )
        rolled_back = self.observer.build_runtime_pilot_decision(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            pilot_enabled=False,
            fallback_evaluation_enabled=True,
            pilot_provider_categories=("options",),
            pilot_route_families=("options_lab",),
            now=datetime(2026, 5, 6, 15, 30, 0),
        )

        self.assertEqual(out_of_scope["decision_status"], "scope_not_enabled")
        self.assertFalse(out_of_scope["scope_matched"])
        self.assertTrue(out_of_scope["would_block_if_enforced"])
        self.assertFalse(out_of_scope["pilot_would_block"])
        self.assertFalse(out_of_scope["pilot_would_fallback"])
        self.assertEqual(rolled_back["decision_status"], "disabled_by_default")
        self.assertTrue(rolled_back["scope_matched"])
        self.assertFalse(rolled_back["pilot_enabled"])
        self.assertTrue(rolled_back["would_block_if_enforced"])
        self.assertFalse(rolled_back["pilot_would_block"])
        self.assertFalse(rolled_back["pilot_would_fallback"])
        self._assert_runtime_pilot_never_changes_provider_behavior(out_of_scope)
        self._assert_runtime_pilot_never_changes_provider_behavior(rolled_back)

    def test_runtime_pilot_diagnostics_are_sanitized_and_do_not_mutate_or_call_live_paths(self) -> None:
        self.db.transition_provider_circuit_state(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            to_state="disabled_by_operator",
            reason_bucket="auth_or_key_invalid",
            operator_action_ref=(
                "provider outage https://provider.example.test/raw?token=must-not-leak "
                "raw_exception_message=ProviderError(must-not-leak)"
            ),
            metadata={
                "api_key": "must-not-leak",
                "headers": {"Authorization": "Bearer must-not-leak"},
                "raw_payload": {"token": "must-not-leak"},
                "safe_label": "runtime_pilot_fixture",
            },
            now=datetime(2026, 5, 6, 15, 0, 0),
        )
        with self.db.session_scope() as session:
            event_count = session.query(ProviderCircuitEvent).count()

        with patch("requests.sessions.Session.request") as request_mock:
            decision = self.observer.build_runtime_pilot_decision(
                provider="tradier",
                provider_category="options",
                route_family="options_lab",
                pilot_enabled=True,
                fallback_evaluation_enabled=True,
                pilot_provider_categories=("options",),
                pilot_route_families=("options_lab",),
                now=datetime(2026, 5, 6, 15, 30, 0),
            )

        self._assert_runtime_pilot_never_changes_provider_behavior(decision)
        self.assertEqual(decision["diagnostic_ref"], "diagnostic_ref_redacted")
        self.assertEqual(decision["sanitized_diagnostics"]["reasonBucket"], "auth_or_key_invalid")
        text = str(decision).lower()
        for blocked in (
            "must-not-leak",
            "provider.example.test",
            "https://",
            "token",
            "api_key",
            "authorization",
            "raw_payload",
            "raw_exception",
            "providererror",
        ):
            self.assertNotIn(blocked, text)
        request_mock.assert_not_called()
        with self.db.session_scope() as session:
            self.assertEqual(session.query(ProviderCircuitEvent).count(), event_count)


if __name__ == "__main__":
    unittest.main()
