# -*- coding: utf-8 -*-
"""Read-only admin provider circuit diagnostics API tests."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from api.deps import CurrentUser, get_current_user
from api.v1.endpoints import admin_provider_circuits
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID
from src.services.options_market_data_provider import OptionsLiveProviderConfig
from src.services.provider_circuit_observer import ProviderCircuitObserver
from src.storage import DatabaseManager


PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ENABLED_ENV = "WOLFYSTOCK_PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ENABLED"
PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ROLLBACK_ENV = "WOLFYSTOCK_PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ROLLBACK_ENABLED"


def _admin_with_provider_read() -> CurrentUser:
    return CurrentUser(
        user_id=BOOTSTRAP_ADMIN_USER_ID,
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=("ops:providers:read",),
    )


def _admin_without_provider_read() -> CurrentUser:
    return CurrentUser(
        user_id=BOOTSTRAP_ADMIN_USER_ID,
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=("cost:observability:read",),
    )


def _regular_user() -> CurrentUser:
    return CurrentUser(
        user_id="user-1",
        username="alice",
        display_name="Alice",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
    )


def _unauthenticated_user() -> CurrentUser:
    raise HTTPException(
        status_code=401,
        detail={"error": "unauthorized", "message": "Login required"},
    )


class AdminProviderCircuitDiagnosticsApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.pop(PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ENABLED_ENV, None)
        os.environ.pop(PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ROLLBACK_ENV, None)
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "provider_circuit_api.db"
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")
        self.app = FastAPI()
        self.app.include_router(admin_provider_circuits.router, prefix="/api/v1/admin")
        self.app.dependency_overrides[get_current_user] = _unauthenticated_user
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        os.environ.pop(PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ENABLED_ENV, None)
        os.environ.pop(PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ROLLBACK_ENV, None)
        self.client.close()
        self.app.dependency_overrides.clear()
        DatabaseManager.reset_instance()
        self.temp_dir.cleanup()

    def _as_provider_read_admin(self) -> None:
        self.app.dependency_overrides[get_current_user] = _admin_with_provider_read

    def _as_admin_without_provider_read(self) -> None:
        self.app.dependency_overrides[get_current_user] = _admin_without_provider_read

    def _as_user(self) -> None:
        self.app.dependency_overrides[get_current_user] = _regular_user

    @staticmethod
    def _json_text(payload: object) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _sla_item(
        payload: dict,
        *,
        provider: str,
        provider_category: str | None,
        route_family: str | None,
    ) -> dict:
        return next(
            item
            for item in payload["items"]
            if item["provider"] == provider
            and item.get("providerCategory") == provider_category
            and item.get("routeFamily") == route_family
        )

    def _seed_circuit_fixture(self) -> datetime:
        base = datetime(2026, 5, 6, 10, 0, 0)
        self.db.transition_provider_circuit_state(
            provider="fmp",
            provider_category="quote",
            route_family="analysis",
            to_state="open",
            reason_bucket="timeout",
            cooldown_until=base + timedelta(minutes=10),
            operator_action_ref="SAFE-AUDIT-1",
            metadata={
                "safe_label": "fixture",
                "api_key": "must-not-leak",
                "url": "https://provider.example.test/raw?token=must-not-leak",
                "raw_response": "must-not-leak",
                "stack_trace": "Traceback must-not-leak",
            },
            now=base,
        )
        self.db.transition_provider_circuit_state(
            provider="finnhub",
            provider_category="news",
            route_family="guest_preview",
            to_state="provider_quota_depleted",
            reason_bucket="provider_429",
            now=base + timedelta(minutes=1),
        )
        self.db.update_provider_quota_window_counters(
            provider="fmp",
            provider_category="quote",
            route_family="analysis",
            window_type="hour",
            window_start=base,
            window_end=base + timedelta(hours=1),
            request_delta=5,
            consumed_units_delta=12,
            success_delta=3,
            failure_delta=2,
            timeout_delta=1,
            provider_429_delta=1,
            probe_delta=1,
            metadata={"safe_label": "quota", "cookie": "must-not-leak"},
        )
        self.db.record_provider_probe_event(
            provider="fmp",
            provider_category="probe",
            route_family="admin_provider_probe",
            probe_type="synthetic_fixture",
            probe_source="dry_run",
            result_bucket="provider_403",
            duration_bucket_ms=250,
            metadata={"safe_label": "probe", "token": "must-not-leak"},
            created_at=base + timedelta(minutes=2),
        )
        return base

    def test_admin_with_provider_read_capability_can_read_seeded_circuit_states(self) -> None:
        self._as_provider_read_admin()
        self._seed_circuit_fixture()

        response = self.client.get("/api/v1/admin/providers/circuits")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["metadata"]["dataSources"], ["provider_circuit_states"])
        self.assertTrue(payload["metadata"]["readOnly"])
        self.assertTrue(payload["metadata"]["noExternalCalls"])
        self.assertFalse(payload["metadata"]["liveEnforcement"])
        self.assertFalse(payload["metadata"]["providerBehaviorChanged"])
        self.assertFalse(payload["metadata"]["marketCacheBehaviorChanged"])
        fmp = next(item for item in payload["items"] if item["provider"] == "fmp")
        self.assertEqual(fmp["providerCategory"], "quote")
        self.assertEqual(fmp["routeFamily"], "analysis")
        self.assertEqual(fmp["state"], "open")
        self.assertEqual(fmp["reasonBucket"], "timeout")
        self.assertEqual(fmp["operatorActionRef"], "SAFE-AUDIT-1")

    def test_all_provider_diagnostics_surfaces_remain_read_only_and_non_enforcing(self) -> None:
        self._as_provider_read_admin()
        self._seed_circuit_fixture()

        responses = (
            self.client.get("/api/v1/admin/providers/circuits"),
            self.client.get("/api/v1/admin/providers/circuits/events"),
            self.client.get("/api/v1/admin/providers/quota-windows"),
            self.client.get("/api/v1/admin/providers/probe-events"),
            self.client.get("/api/v1/admin/providers/sla-readiness"),
        )

        for response in responses:
            self.assertEqual(response.status_code, 200)
            metadata = response.json()["metadata"]
            self.assertTrue(metadata["readOnly"])
            self.assertTrue(metadata["noExternalCalls"])
            self.assertFalse(metadata["liveEnforcement"])
            self.assertFalse(metadata["providerBehaviorChanged"])
            self.assertFalse(metadata["marketCacheBehaviorChanged"])

    def test_empty_circuit_states_with_provider_failure_signals_warns_about_possible_unwired_circuit(self) -> None:
        self._as_provider_read_admin()
        base = datetime.now() - timedelta(minutes=10)
        self.db.update_provider_quota_window_counters(
            provider="fmp",
            provider_category="quote",
            route_family="analysis",
            window_type="hour",
            window_start=base,
            window_end=base + timedelta(hours=1),
            request_delta=3,
            failure_delta=1,
            timeout_delta=1,
            metadata={
                "safe_label": "provider_failure_signal",
                "raw_payload": "must-not-leak",
                "url": "https://provider.example.test/raw?api_key=must-not-leak",
            },
        )

        response = self.client.get("/api/v1/admin/providers/circuits")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["items"], [])
        metadata = payload["metadata"]
        self.assertEqual(metadata["circuitStateCoverageStatus"], "possible_unwired")
        self.assertTrue(metadata["providerFailureSignalsPresent"])
        self.assertFalse(metadata["circuitStatesPresent"])
        self.assertFalse(metadata["circuitEventsPresent"])
        self.assertFalse(metadata["probeEventsPresent"])
        self.assertTrue(metadata["possibleUnwiredCircuitObservation"])
        self.assertEqual(
            metadata["recommendedNextAction"],
            "provider_failures_observed_without_circuit_state_rows_review_circuit_wiring",
        )
        self.assertEqual(metadata["diagnosticSignalSources"], ["provider_quota_windows"])
        self.assertTrue(metadata["readOnly"])
        self.assertTrue(metadata["noExternalCalls"])
        self.assertFalse(metadata["liveEnforcement"])
        self.assertFalse(metadata["providerBehaviorChanged"])
        self.assertFalse(metadata["marketCacheBehaviorChanged"])
        text = self._json_text(payload).lower()
        for forbidden in (
            "must-not-leak",
            "https://provider.example",
            "api_key",
            "raw_payload",
            "owner_user_id",
            "guest_bucket_hash",
        ):
            self.assertNotIn(forbidden, text)

    def test_empty_circuit_states_with_admin_log_provider_failure_signals_warns_without_raw_log_payload(self) -> None:
        self._as_provider_read_admin()
        base = datetime.now() - timedelta(minutes=10)
        self.db.create_execution_log_session(
            session_id="scanner-provider-failure-1",
            task_id="scanner_run",
            code="us",
            name="Scanner provider failure",
            overall_status="partial",
            truth_level="actual",
            summary={
                "scanner_run": {
                    "provider_failure_count": 2,
                    "provider_diagnostics": {
                        "provider_failure_count": 2,
                        "providers_used": ["fmp"],
                        "raw_payload": "must-not-leak",
                        "url": "https://provider.example.test/raw?token=must-not-leak",
                    },
                },
            },
            started_at=base,
        )

        response = self.client.get("/api/v1/admin/providers/circuits")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        metadata = payload["metadata"]
        self.assertEqual(metadata["circuitStateCoverageStatus"], "possible_unwired")
        self.assertTrue(metadata["providerFailureSignalsPresent"])
        self.assertFalse(metadata["circuitStatesPresent"])
        self.assertFalse(metadata["circuitEventsPresent"])
        self.assertFalse(metadata["probeEventsPresent"])
        self.assertTrue(metadata["possibleUnwiredCircuitObservation"])
        self.assertIn("execution_log_sessions", metadata["diagnosticSignalSources"])
        text = self._json_text(payload).lower()
        for forbidden in (
            "must-not-leak",
            "provider.example.test",
            "https://",
            "token",
            "raw_payload",
        ):
            self.assertNotIn(forbidden, text)

    def test_empty_circuit_states_without_failure_signals_reports_idle_neutral_status(self) -> None:
        self._as_provider_read_admin()

        response = self.client.get("/api/v1/admin/providers/circuits")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["items"], [])
        metadata = payload["metadata"]
        self.assertEqual(metadata["circuitStateCoverageStatus"], "idle_no_signals")
        self.assertFalse(metadata["providerFailureSignalsPresent"])
        self.assertFalse(metadata["circuitStatesPresent"])
        self.assertFalse(metadata["circuitEventsPresent"])
        self.assertFalse(metadata["probeEventsPresent"])
        self.assertFalse(metadata["possibleUnwiredCircuitObservation"])
        self.assertEqual(metadata["recommendedNextAction"], "no_action_provider_circuit_infrastructure_idle")

    def test_circuit_states_present_suppresses_possible_unwired_warning(self) -> None:
        self._as_provider_read_admin()
        base = datetime.now() - timedelta(minutes=10)
        self.db.transition_provider_circuit_state(
            provider="fmp",
            provider_category="quote",
            route_family="analysis",
            to_state="closed",
            reason_bucket="timeout",
            now=base,
        )
        self.db.update_provider_quota_window_counters(
            provider="fmp",
            provider_category="quote",
            route_family="analysis",
            window_type="hour",
            window_start=base,
            window_end=base + timedelta(hours=1),
            request_delta=3,
            failure_delta=1,
        )

        response = self.client.get("/api/v1/admin/providers/circuits")

        self.assertEqual(response.status_code, 200)
        metadata = response.json()["metadata"]
        self.assertEqual(metadata["circuitStateCoverageStatus"], "states_present")
        self.assertTrue(metadata["providerFailureSignalsPresent"])
        self.assertTrue(metadata["circuitStatesPresent"])
        self.assertTrue(metadata["circuitEventsPresent"])
        self.assertFalse(metadata["probeEventsPresent"])
        self.assertFalse(metadata["possibleUnwiredCircuitObservation"])
        self.assertEqual(metadata["recommendedNextAction"], "review_existing_circuit_state_rows")

    def test_provider_circuit_diagnostics_auth_boundaries_remain_401_403_and_admin_200(self) -> None:
        no_auth = self.client.get("/api/v1/admin/providers/circuits")
        self.assertEqual(no_auth.status_code, 401)
        self.assertEqual(no_auth.json()["detail"]["error"], "unauthorized")

        self._as_user()
        consumer = self.client.get("/api/v1/admin/providers/circuits")
        self.assertEqual(consumer.status_code, 403)
        self.assertEqual(consumer.json()["detail"]["error"], "admin_required")

        self._as_provider_read_admin()
        admin = self.client.get("/api/v1/admin/providers/circuits")
        self.assertEqual(admin.status_code, 200)
        self.assertIn("circuitStateCoverageStatus", admin.json()["metadata"])

    def test_non_admin_denied(self) -> None:
        self._as_user()

        response = self.client.get("/api/v1/admin/providers/circuits")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["error"], "admin_required")

    def test_admin_lacking_provider_read_capability_denied(self) -> None:
        self._as_admin_without_provider_read()

        response = self.client.get("/api/v1/admin/providers/circuits")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["error"], "admin_capability_required")
        self.assertNotIn("ops:providers:read", response.text)

    def test_sla_readiness_requires_provider_read_capability(self) -> None:
        self._as_admin_without_provider_read()

        response = self.client.get("/api/v1/admin/providers/sla-readiness")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["error"], "admin_capability_required")
        self.assertNotIn("ops:providers:read", response.text)

    def test_limit_is_bounded(self) -> None:
        self._as_provider_read_admin()
        for index in range(230):
            self.db.upsert_provider_circuit_state(
                provider=f"provider-{index}",
                provider_category="quote",
                route_family="analysis",
                state="closed",
            )

        response = self.client.get("/api/v1/admin/providers/circuits?limit=999")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 200)
        self.assertEqual(response.json()["metadata"]["limit"], 200)

    def test_filters_work(self) -> None:
        self._as_provider_read_admin()
        base = self._seed_circuit_fixture()

        response = self.client.get(
            "/api/v1/admin/providers/circuits",
            params={
                "provider": "FMP",
                "state": "open",
                "routeFamily": "analysis",
                "since": (base - timedelta(minutes=1)).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["provider"], "fmp")

    def test_response_is_sanitized_and_omits_raw_secret_like_metadata(self) -> None:
        self._as_provider_read_admin()
        self._seed_circuit_fixture()

        response = self.client.get("/api/v1/admin/providers/circuits")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        text = self._json_text(payload).lower()
        for forbidden in (
            "must-not-leak",
            "api_key",
            "raw_response",
            "https://provider.example",
            "token",
            "cookie",
            "traceback",
            "owner_user_id",
            "guest_bucket_hash",
        ):
            self.assertNotIn(forbidden, text)
        for item in payload["items"]:
            self.assertNotIn("metadata", item)

    def test_diagnostics_responses_drop_unsafe_refs_filters_and_exception_text(self) -> None:
        self._as_provider_read_admin()
        base = datetime(2026, 5, 6, 10, 0, 0)
        unsafe_ref = (
            "provider outage https://provider.example.test/raw?token=must-not-leak "
            "session_id=raw-session-123 cookie=raw-cookie "
            "raw_exception_message=ProviderError(must-not-leak)"
        )
        self.db.transition_provider_circuit_state(
            provider="fmp",
            provider_category="quote",
            route_family="analysis",
            to_state="open",
            reason_bucket="network_error",
            operator_action_ref=unsafe_ref,
            metadata={
                "headers": {"Authorization": "Bearer must-not-leak"},
                "raw_response": {"session_id": "raw-session-123"},
                "safe_summary": "provider_error_bucket",
                "stack_trace": "Traceback raw_exception_message must-not-leak",
            },
            now=base,
        )
        self.db.update_provider_quota_window_counters(
            provider="fmp",
            provider_category="quote",
            route_family="analysis",
            window_type="hour",
            window_start=base,
            window_end=base + timedelta(hours=1),
            request_delta=1,
            rejected_delta=1,
            metadata={
                "request_url": "https://provider.example.test/quota?api_key=must-not-leak",
                "cookie": "raw-cookie",
                "safe_summary": "quota_rejected_bucket",
            },
        )
        self.db.record_provider_probe_event(
            provider="fmp",
            provider_category="probe",
            route_family="admin_provider_probe",
            probe_type="synthetic_fixture",
            probe_source="dry_run",
            result_bucket="provider_403",
            duration_bucket_ms=250,
            metadata={
                "response_body": "must-not-leak",
                "raw_exception": "ProviderError(raw-session-123)",
                "safe_summary": "probe_result_bucket",
            },
            created_at=base + timedelta(minutes=1),
        )

        unsafe_filter = "https://provider.example.test/raw?token=must-not-leak&session_id=raw-session-123"
        responses = {
            "states": self.client.get("/api/v1/admin/providers/circuits", params={"provider": unsafe_filter}),
            "events": self.client.get("/api/v1/admin/providers/circuits/events", params={"provider": unsafe_filter}),
            "quota": self.client.get("/api/v1/admin/providers/quota-windows", params={"provider": unsafe_filter}),
            "probes": self.client.get("/api/v1/admin/providers/probe-events", params={"provider": unsafe_filter}),
            "sla": self.client.get(
                "/api/v1/admin/providers/sla-readiness",
                params={"provider": unsafe_filter, "since": "2026-05-06T00:00:00"},
            ),
        }

        for name, response in responses.items():
            self.assertEqual(response.status_code, 200, name)

        unfiltered = {
            "states": self.client.get("/api/v1/admin/providers/circuits", params={"provider": "fmp"}),
            "events": self.client.get("/api/v1/admin/providers/circuits/events", params={"provider": "fmp"}),
            "quota": self.client.get("/api/v1/admin/providers/quota-windows", params={"provider": "fmp"}),
            "probes": self.client.get("/api/v1/admin/providers/probe-events", params={"provider": "fmp"}),
            "sla": self.client.get(
                "/api/v1/admin/providers/sla-readiness",
                params={"provider": "fmp", "since": "2026-05-06T00:00:00"},
            ),
        }
        for name, response in unfiltered.items():
            self.assertEqual(response.status_code, 200, name)

        state = unfiltered["states"].json()["items"][0]
        self.assertEqual(state["provider"], "fmp")
        self.assertEqual(state["reasonBucket"], "network_error")
        self.assertEqual(state["operatorActionRef"], "diagnostic_ref_redacted")
        event = unfiltered["events"].json()["items"][0]
        self.assertEqual(event["eventType"], "state_transition")
        self.assertEqual(event["reasonBucket"], "network_error")
        self.assertEqual(event["operatorActionRef"], "diagnostic_ref_redacted")
        quota = unfiltered["quota"].json()["items"][0]
        self.assertEqual(quota["requestCount"], 1)
        self.assertEqual(quota["rejectedCount"], 1)
        probe = unfiltered["probes"].json()["items"][0]
        self.assertEqual(probe["probeType"], "synthetic_fixture")
        self.assertEqual(probe["resultBucket"], "provider_403")
        sla = next(
            item
            for item in unfiltered["sla"].json()["items"]
            if item["provider"] == "fmp" and item["providerCategory"] == "quote" and item["routeFamily"] == "analysis"
        )
        self.assertEqual(sla["provider"], "fmp")
        self.assertFalse(sla["liveEnforcement"])
        self.assertFalse(sla["wouldBlockCall"])
        self.assertEqual(sla["recentErrors"][0]["reasonBucket"], "network_error")

        text = self._json_text(
            {
                "filtered": {key: item.json() for key, item in responses.items()},
                "unfiltered": {key: item.json() for key, item in unfiltered.items()},
            }
        ).lower()
        for forbidden in (
            "must-not-leak",
            "provider.example.test",
            "https://",
            "?token=",
            "session_id",
            "raw-session-123",
            "raw-cookie",
            "cookie=",
            "raw_exception_message",
            "providererror(",
            "traceback",
            "authorization",
            "raw_response",
            "response_body",
        ):
            self.assertNotIn(forbidden, text)

    def test_circuit_events_read_returns_safe_reason_buckets(self) -> None:
        self._as_provider_read_admin()
        self._seed_circuit_fixture()

        response = self.client.get(
            "/api/v1/admin/providers/circuits/events",
            params={"provider": "fmp", "eventType": "state_transition"},
        )

        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["eventType"], "state_transition")
        self.assertEqual(items[0]["reasonBucket"], "timeout")
        self.assertNotIn("metadata", self._json_text(items[0]).lower())

    def test_quota_windows_read_returns_safe_aggregates(self) -> None:
        self._as_provider_read_admin()
        self._seed_circuit_fixture()

        response = self.client.get("/api/v1/admin/providers/quota-windows", params={"provider": "fmp"})

        self.assertEqual(response.status_code, 200)
        item = response.json()["items"][0]
        self.assertEqual(item["provider"], "fmp")
        self.assertEqual(item["requestCount"], 5)
        self.assertEqual(item["consumedUnits"], 12)
        self.assertEqual(item["successCount"], 3)
        self.assertEqual(item["failureCount"], 2)
        self.assertEqual(item["timeoutCount"], 1)
        self.assertEqual(item["provider429Count"], 1)
        self.assertEqual(item["probeCount"], 1)

    def test_probe_events_read_returns_safe_result_buckets(self) -> None:
        self._as_provider_read_admin()
        self._seed_circuit_fixture()

        response = self.client.get("/api/v1/admin/providers/probe-events", params={"provider": "fmp"})

        self.assertEqual(response.status_code, 200)
        item = response.json()["items"][0]
        self.assertEqual(item["probeType"], "synthetic_fixture")
        self.assertEqual(item["probeSource"], "dry_run")
        self.assertEqual(item["resultBucket"], "provider_403")
        self.assertEqual(item["durationBucketMs"], 250)
        self.assertNotIn("actor", self._json_text(item).lower())

    def test_endpoint_does_not_call_live_provider_llm_or_cache_paths(self) -> None:
        self._as_provider_read_admin()
        self._seed_circuit_fixture()

        def forbidden(*_args, **_kwargs):
            raise AssertionError("live path should not be called by provider diagnostics")

        with (
            patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
            patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
            patch("src.services.scanner_ai_service.ScannerAiInterpretationService.interpret_shortlist", side_effect=forbidden),
            patch("requests.sessions.Session.request", side_effect=forbidden),
        ):
            response = self.client.get("/api/v1/admin/providers/sla-readiness")

        self.assertEqual(response.status_code, 200)

    def test_storage_backed_provider_diagnostics_do_not_mutate_state_or_send_notifications(self) -> None:
        self._as_provider_read_admin()
        self._seed_circuit_fixture()

        def forbidden(*_args, **_kwargs):
            raise AssertionError("read-only diagnostics should not mutate state or send notifications")

        with (
            patch("src.storage.DatabaseManager.transition_provider_circuit_state", side_effect=forbidden),
            patch("src.storage.DatabaseManager.update_provider_quota_window_counters", side_effect=forbidden),
            patch("src.storage.DatabaseManager.record_provider_probe_event", side_effect=forbidden),
            patch(
                "src.services.provider_circuit_observer.ProviderCircuitObserver.record_observation",
                side_effect=forbidden,
            ),
            patch("src.notification.NotificationService.send", side_effect=forbidden),
            patch("requests.sessions.Session.request", side_effect=forbidden),
        ):
            responses = (
                self.client.get("/api/v1/admin/providers/circuits"),
                self.client.get("/api/v1/admin/providers/circuits/events"),
                self.client.get("/api/v1/admin/providers/quota-windows"),
                self.client.get("/api/v1/admin/providers/probe-events"),
            )

        for response in responses:
            self.assertEqual(response.status_code, 200)
            metadata = response.json()["metadata"]
            self.assertTrue(metadata["readOnly"])
            self.assertTrue(metadata["noExternalCalls"])

    def test_diagnostics_api_reads_provider_circuit_observer_dry_run_rows(self) -> None:
        self._as_provider_read_admin()
        observer = ProviderCircuitObserver(db=self.db)
        observer.record_observation(
            provider="FMP",
            provider_category="quote",
            route_family="analysis",
            result_bucket="timeout",
            duration_ms=1200,
            observed_at=datetime(2026, 5, 6, 10, 15, 0),
            metadata={
                "safe_label": "observer_fixture",
                "url": "https://provider.example.test/raw?api_key=must-not-leak",
                "raw_response": "must-not-leak",
            },
        )
        observer.record_observation(
            provider="tavily",
            provider_category="probe",
            route_family="admin_provider_probe",
            result_bucket="provider_403",
            probe_type="synthetic_fixture",
            duration_ms=220,
            observed_at=datetime(2026, 5, 6, 10, 20, 0),
            metadata={"safe_label": "observer_probe", "token": "must-not-leak"},
        )

        events_response = self.client.get(
            "/api/v1/admin/providers/circuits/events",
            params={"provider": "fmp", "eventType": "policy_dry_run"},
        )
        windows_response = self.client.get("/api/v1/admin/providers/quota-windows", params={"provider": "fmp"})
        probes_response = self.client.get("/api/v1/admin/providers/probe-events", params={"provider": "tavily"})

        self.assertEqual(events_response.status_code, 200)
        self.assertEqual(windows_response.status_code, 200)
        self.assertEqual(probes_response.status_code, 200)
        event = events_response.json()["items"][0]
        window = windows_response.json()["items"][0]
        probe = probes_response.json()["items"][0]
        self.assertEqual(event["eventType"], "policy_dry_run")
        self.assertEqual(event["reasonBucket"], "timeout")
        self.assertEqual(event["durationBucketMs"], 1500)
        self.assertEqual(window["requestCount"], 1)
        self.assertEqual(window["failureCount"], 1)
        self.assertEqual(window["timeoutCount"], 1)
        self.assertEqual(probe["probeType"], "synthetic_fixture")
        self.assertEqual(probe["probeSource"], "dry_run")
        self.assertEqual(probe["resultBucket"], "provider_403")
        text = self._json_text(
            {"events": events_response.json(), "windows": windows_response.json(), "probes": probes_response.json()}
        ).lower()
        self.assertNotIn("must-not-leak", text)
        self.assertNotIn("https://provider.example", text)

    def test_sla_readiness_endpoint_exposes_sanitized_readiness_without_live_calls(self) -> None:
        self._as_provider_read_admin()
        observer = ProviderCircuitObserver(db=self.db)
        observer.record_observation(
            provider="FMP",
            provider_category="quote",
            route_family="analysis",
            result_bucket="timeout",
            duration_ms=1200,
            observed_at=datetime(2026, 5, 6, 10, 15, 0),
            metadata={
                "safe_label": "observer_fixture",
                "url": "https://provider.example.test/raw?api_key=must-not-leak",
                "raw_response": "must-not-leak",
            },
        )

        with patch("requests.sessions.Session.request") as request_mock:
            response = self.client.get(
                "/api/v1/admin/providers/sla-readiness",
                params={"provider": "fmp", "since": "2026-05-06T00:00:00"},
            )

        self.assertEqual(response.status_code, 200)
        request_mock.assert_not_called()
        payload = response.json()
        self.assertTrue(payload["metadata"]["readOnly"])
        self.assertTrue(payload["metadata"]["noExternalCalls"])
        self.assertFalse(payload["metadata"]["liveEnforcement"])
        fmp = self._sla_item(payload, provider="fmp", provider_category="quote", route_family="analysis")
        self.assertEqual(fmp["provider"], "fmp")
        self.assertEqual(fmp["providerCategory"], "quote")
        self.assertEqual(fmp["routeFamily"], "analysis")
        self.assertEqual(fmp["latencyBucketMs"], 1500)
        self.assertEqual(fmp["latencyState"], "slow")
        self.assertIn(fmp["freshnessState"], {"fresh", "stale", "expired"})
        self.assertIn("freshnessSeconds", fmp)
        self.assertIn("credentialsPresent", fmp)
        self.assertIn("liveHttpCallsEnabled", fmp)
        self.assertIn("wouldBlockCall", fmp)
        self.assertIn("wouldBlockIfEnforced", fmp)
        self.assertEqual(fmp["recentErrors"][0]["reasonBucket"], "timeout")
        self.assertEqual(fmp["recentErrors"][0]["countBucket"], "1")
        self.assertEqual(fmp["trendSummary"]["windowCountBucket"], "1")
        self.assertEqual(fmp["trendSummary"]["requestCountBucket"], "1")
        self.assertEqual(fmp["trendSummary"]["failureCountBucket"], "1")
        self.assertEqual(fmp["trendSummary"]["latestObservationAt"], "2026-05-06T10:15:00")
        self.assertEqual(fmp["credentialState"], "unknown")
        self.assertEqual(fmp["circuitAdvisoryState"], "open_candidate")
        self.assertFalse(fmp["scopeMatched"])
        self.assertFalse(fmp["liveEnforcement"])
        self.assertFalse(fmp["wouldBlockCall"])
        self.assertTrue(fmp["wouldBlockIfEnforced"])
        self.assertEqual(fmp["enforcementBlockReasonCode"], "timeout")
        self.assertFalse(fmp["wouldChangeProviderOrder"])
        self.assertFalse(fmp["wouldChangeFallbackBehavior"])
        text = self._json_text(payload).lower()
        for blocked in ("must-not-leak", "api_key", "raw_response", "https://provider.example", "token"):
            self.assertNotIn(blocked, text)

    def test_sla_readiness_endpoint_exposes_missing_options_credentials_sanitized(self) -> None:
        self._as_provider_read_admin()
        env = {
            "OPTIONS_LIVE_PROVIDERS_ENABLED": "1",
            "OPTIONS_LIVE_PROVIDER_KEYS": "tradier",
        }

        with patch.dict(os.environ, env, clear=True), patch("requests.sessions.Session.request") as request_mock:
            response = self.client.get("/api/v1/admin/providers/sla-readiness", params={"provider": "tradier"})

        self.assertEqual(response.status_code, 200)
        request_mock.assert_not_called()
        item = self._sla_item(
            response.json(),
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
        )
        self.assertEqual(item["provider"], "tradier")
        self.assertEqual(item["readinessState"], "missing_credentials")
        self.assertEqual(item["credentialState"], "missing_credentials")
        self.assertEqual(item["reasonCode"], "options_provider_credentials_missing")
        self.assertFalse(item["credentialsPresent"])
        self.assertEqual(item["credentialContract"]["state"], "missing")
        self.assertEqual(item["credentialContract"]["requiredCredentialCount"], 1)
        self.assertEqual(item["credentialContract"]["configuredCredentialCount"], 0)
        self.assertFalse(item["liveHttpCallsEnabled"])
        self.assertFalse(item["wouldBlockCall"])
        self.assertFalse(item["wouldBlockIfEnforced"])
        self.assertEqual(item["recentErrors"], [])
        self.assertEqual(item["trendSummary"]["requestCountBucket"], "0")
        text = self._json_text(response.json()).lower()
        for blocked in ("tradier_api_token", "api_token", "token", "secret", "password"):
            self.assertNotIn(blocked, text)

    def test_sla_readiness_endpoint_exposes_options_credential_states_as_booleans_only(self) -> None:
        self._as_provider_read_admin()
        env = {
            "OPTIONS_LIVE_PROVIDERS_ENABLED": "1",
            "OPTIONS_LIVE_PROVIDER_KEYS": "tradier",
            "TRADIER_API_TOKEN": "valid_synthetic_readiness_value_1234567890",
        }

        with patch.dict(os.environ, env, clear=True), patch("requests.sessions.Session.request") as request_mock:
            response = self.client.get("/api/v1/admin/providers/sla-readiness", params={"provider": "tradier"})

        self.assertEqual(response.status_code, 200)
        request_mock.assert_not_called()
        item = self._sla_item(
            response.json(),
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
        )
        self.assertEqual(item["provider"], "tradier")
        self.assertEqual(item["readinessState"], "live_credentials_present_live_calls_disabled")
        self.assertEqual(item["credentialState"], "live_credentials_present_live_calls_disabled")
        self.assertEqual(item["reasonCode"], "options_provider_live_calls_disabled")
        self.assertTrue(item["liveProvidersEnabled"])
        self.assertTrue(item["providerEnabled"])
        self.assertTrue(item["credentialsPresent"])
        self.assertEqual(item["credentialContract"]["state"], "present")
        self.assertEqual(item["credentialContract"]["configuredCredentialCount"], 1)
        self.assertFalse(item["dryRunEnabled"])
        self.assertFalse(item["liveHttpCallsEnabled"])
        self.assertFalse(item["brokerOrderPathEnabled"])
        self.assertFalse(item["portfolioMutationPathEnabled"])
        self.assertFalse(item["tradeableData"])
        text = self._json_text(response.json()).lower()
        for blocked in ("valid_synthetic_readiness_value", "tradier_api_token", "api_token", "token"):
            self.assertNotIn(blocked, text)

    def test_sla_readiness_endpoint_exposes_malformed_options_credentials_sanitized(self) -> None:
        self._as_provider_read_admin()
        env = {
            "OPTIONS_LIVE_PROVIDERS_ENABLED": "1",
            "OPTIONS_LIVE_PROVIDER_KEYS": "tradier",
            "TRADIER_API_TOKEN": "placeholder",
        }

        with patch.dict(os.environ, env, clear=True), patch("requests.sessions.Session.request") as request_mock:
            response = self.client.get("/api/v1/admin/providers/sla-readiness", params={"provider": "tradier"})

        self.assertEqual(response.status_code, 200)
        request_mock.assert_not_called()
        item = self._sla_item(
            response.json(),
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
        )
        self.assertEqual(item["provider"], "tradier")
        self.assertEqual(item["readinessState"], "malformed_credentials")
        self.assertEqual(item["credentialState"], "malformed_credentials")
        self.assertEqual(item["reasonCode"], "options_provider_credentials_malformed")
        self.assertFalse(item["credentialsPresent"])
        self.assertEqual(item["credentialContract"]["state"], "malformed")
        self.assertEqual(item["credentialContract"]["invalidCredentialCount"], 1)
        self.assertFalse(item["liveHttpCallsEnabled"])
        self.assertFalse(item["wouldBlockCall"])
        text = self._json_text(response.json()).lower()
        for blocked in ("placeholder", "tradier_api_token", "api_token", "token", "secret"):
            self.assertNotIn(blocked, text)

    def test_sla_readiness_endpoint_reports_partial_credentials_sanitized_and_would_block_without_live_calls(self) -> None:
        self._as_provider_read_admin()
        observer = ProviderCircuitObserver(db=self.db)
        observer.record_observation(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            result_bucket="auth_or_key_invalid",
            observed_at=datetime(2026, 5, 6, 10, 30, 0),
        )
        staged_config = OptionsLiveProviderConfig(
            live_providers_enabled=True,
            enabled_provider_keys=frozenset({"tradier"}),
            partial_credential_provider_keys=frozenset({"tradier"}),
        )

        with patch.object(admin_provider_circuits.OptionsLiveProviderConfig, "from_env", return_value=staged_config), patch(
            "requests.sessions.Session.request"
        ) as request_mock:
            response = self.client.get(
                "/api/v1/admin/providers/sla-readiness",
                params={"provider": "tradier", "since": "2026-05-06T00:00:00"},
            )

        self.assertEqual(response.status_code, 200)
        request_mock.assert_not_called()
        item = self._sla_item(
            response.json(),
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
        )
        self.assertEqual(item["provider"], "tradier")
        self.assertEqual(item["readinessState"], "partial_credentials")
        self.assertEqual(item["credentialState"], "partial_credentials")
        self.assertFalse(item["credentialsPresent"])
        self.assertEqual(item["credentialContract"]["state"], "partial")
        self.assertEqual(item["credentialContract"]["reasonCode"], "options_provider_credentials_partial")
        self.assertEqual(item["credentialContract"]["requiredCredentialCount"], 1)
        self.assertEqual(item["credentialContract"]["configuredCredentialCount"], 0)
        self.assertEqual(item["credentialContract"]["partialCredentialCount"], 1)
        self.assertFalse(item["liveHttpCallsEnabled"])
        self.assertFalse(item["wouldBlockCall"])
        self.assertTrue(item["wouldBlockIfEnforced"])
        self.assertEqual(item["enforcementBlockReasonCode"], "auth_or_key_invalid")
        self.assertEqual(item["circuitAdvisoryState"], "degraded")
        self.assertTrue(item["scopeMatched"])
        self.assertFalse(item["wouldChangeProviderOrder"])
        self.assertFalse(item["wouldChangeFallbackBehavior"])
        text = self._json_text(response.json()).lower()
        for blocked in ("api_key", "api token", "token", "secret", "password", "placeholder"):
            self.assertNotIn(blocked, text)

    def test_sla_readiness_endpoint_projects_scoped_block_without_live_enforcement_or_side_effects(self) -> None:
        self._as_provider_read_admin()
        self.db.transition_provider_circuit_state(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            to_state="open",
            reason_bucket="timeout",
            cooldown_until=datetime(2026, 5, 6, 11, 0, 0),
            metadata={
                "safe_label": "projection",
                "url": "https://provider.example.test/raw?api_key=must-not-leak",
                "headers": "must-not-leak",
                "stack_trace": "Traceback must-not-leak",
            },
            now=datetime(2026, 5, 6, 10, 30, 0),
        )

        def forbidden(*_args, **_kwargs):
            raise AssertionError("admin projection must not call provider/cache/llm paths")

        with (
            patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
            patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
            patch(
                "src.services.scanner_ai_service.ScannerAiInterpretationService.interpret_shortlist",
                side_effect=forbidden,
            ),
            patch("requests.sessions.Session.request", side_effect=forbidden),
        ):
            response = self.client.get(
                "/api/v1/admin/providers/sla-readiness",
                params={"provider": "tradier", "since": "2026-05-06T00:00:00"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        item = self._sla_item(payload, provider="tradier", provider_category="options", route_family="options_lab")
        self.assertEqual(item["provider"], "tradier")
        self.assertEqual(item["providerCategory"], "options")
        self.assertEqual(item["routeFamily"], "options_lab")
        self.assertTrue(item["scopeMatched"])
        self.assertFalse(item["liveEnforcement"])
        self.assertFalse(item["wouldBlockCall"])
        self.assertTrue(item["wouldBlockIfEnforced"])
        self.assertEqual(item["enforcementBlockReasonCode"], "timeout")
        self.assertFalse(item["providerBehaviorChanged"])
        self.assertFalse(item["marketCacheBehaviorChanged"])
        self.assertTrue(item["noExternalCalls"])
        text = self._json_text(payload).lower()
        for blocked in ("must-not-leak", "https://provider.example", "traceback must-not-leak"):
            self.assertNotIn(blocked, text)

    def test_sla_readiness_default_omits_runtime_pilot_projection(self) -> None:
        self._as_provider_read_admin()
        self.db.transition_provider_circuit_state(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            to_state="open",
            reason_bucket="timeout",
            cooldown_until=datetime(2026, 5, 6, 11, 0, 0),
            now=datetime(2026, 5, 6, 10, 30, 0),
        )

        response = self.client.get(
            "/api/v1/admin/providers/sla-readiness",
            params={"provider": "tradier", "since": "2026-05-06T00:00:00"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        for item in payload["items"]:
            self.assertNotIn("runtimePilot", item)
            self.assertNotIn("adminProbePilotEvidence", item)

    def test_sla_readiness_runtime_pilot_opt_in_is_advisory_sanitized_and_offline(self) -> None:
        self._as_provider_read_admin()
        self.db.transition_provider_circuit_state(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            to_state="open",
            reason_bucket="timeout",
            cooldown_until=datetime(2026, 5, 6, 11, 0, 0),
            metadata={
                "safe_label": "runtime_pilot_projection",
                "url": "https://provider.example.test/raw?api_key=must-not-leak",
                "headers": {"Authorization": "Bearer must-not-leak"},
                "raw_response": "must-not-leak",
                "stack_trace": "Traceback must-not-leak",
            },
            now=datetime(2026, 5, 6, 10, 30, 0),
        )

        def forbidden(*_args, **_kwargs):
            raise AssertionError("runtime pilot projection must stay read-only and offline")

        with (
            patch("src.storage.DatabaseManager.transition_provider_circuit_state", side_effect=forbidden),
            patch("src.storage.DatabaseManager.update_provider_quota_window_counters", side_effect=forbidden),
            patch("src.storage.DatabaseManager.record_provider_probe_event", side_effect=forbidden),
            patch(
                "src.services.provider_circuit_observer.ProviderCircuitObserver.record_observation",
                side_effect=forbidden,
            ),
            patch("src.services.quota_policy_service.QuotaPolicyService.evaluate_quota", side_effect=forbidden),
            patch("src.services.quota_policy_service.QuotaPolicyService.reserve_quota", side_effect=forbidden),
            patch("src.services.quota_policy_service.QuotaPolicyService.consume_reservation", side_effect=forbidden),
            patch("src.services.quota_policy_service.QuotaPolicyService.release_reservation", side_effect=forbidden),
            patch("src.notification.NotificationService.send", side_effect=forbidden),
            patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
            patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
            patch(
                "src.services.scanner_ai_service.ScannerAiInterpretationService.interpret_shortlist",
                side_effect=forbidden,
            ),
            patch("requests.sessions.Session.request", side_effect=forbidden),
        ):
            response = self.client.get(
                "/api/v1/admin/providers/sla-readiness",
                params={
                    "provider": "tradier",
                    "since": "2026-05-06T00:00:00",
                    "runtimePilotEnabled": "true",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        item = self._sla_item(payload, provider="tradier", provider_category="options", route_family="options_lab")
        self.assertFalse(item["liveEnforcement"])
        self.assertFalse(item["wouldBlockCall"])
        self.assertTrue(item["wouldBlockIfEnforced"])
        self.assertFalse(item["wouldChangeProviderOrder"])
        self.assertFalse(item["wouldChangeFallbackBehavior"])
        self.assertTrue(item["noExternalCalls"])
        self.assertFalse(item["providerBehaviorChanged"])
        self.assertFalse(item["marketCacheBehaviorChanged"])
        self.assertFalse(item["brokerOrderPathEnabled"])
        self.assertFalse(item["portfolioMutationPathEnabled"])
        self.assertFalse(item["tradeableData"])
        runtime_pilot = item["runtimePilot"]
        self.assertEqual(runtime_pilot["contractVersion"], "provider_reliability_runtime_v1")
        self.assertTrue(runtime_pilot["pilotEnabled"])
        self.assertFalse(runtime_pilot["fallbackEvaluationEnabled"])
        self.assertTrue(runtime_pilot["scopeMatched"])
        self.assertTrue(runtime_pilot["advisoryOnly"])
        self.assertFalse(runtime_pilot["productionEnforcementEnabled"])
        self.assertFalse(runtime_pilot["liveEnforcement"])
        self.assertFalse(runtime_pilot["wouldBlockCall"])
        self.assertTrue(runtime_pilot["wouldBlockIfEnforced"])
        self.assertTrue(runtime_pilot["pilotWouldBlock"])
        self.assertFalse(runtime_pilot["pilotWouldFallback"])
        self.assertEqual(runtime_pilot["enforcementBlockReasonCode"], "timeout")
        self.assertFalse(runtime_pilot["wouldChangeProviderOrder"])
        self.assertFalse(runtime_pilot["wouldChangeFallbackBehavior"])
        self.assertTrue(runtime_pilot["noExternalCalls"])
        self.assertFalse(runtime_pilot["providerBehaviorChanged"])
        self.assertFalse(runtime_pilot["marketCacheBehaviorChanged"])
        self.assertFalse(runtime_pilot["brokerOrderPathEnabled"])
        self.assertFalse(runtime_pilot["portfolioMutationPathEnabled"])
        self.assertFalse(runtime_pilot["tradeableData"])
        self.assertEqual(runtime_pilot["defaultOffLabel"], "provider_reliability_runtime_pilot_default_off")
        self.assertEqual(runtime_pilot["rollbackLabel"], "provider_reliability_runtime_pilot_disable_flag")
        text = self._json_text(payload).lower()
        for blocked in (
            "must-not-leak",
            "https://provider.example",
            "api_key",
            "authorization",
            "raw_response",
            "traceback",
        ):
            self.assertNotIn(blocked, text)

    def test_sla_readiness_runtime_pilot_fallback_evaluation_flag_opt_in(self) -> None:
        self._as_provider_read_admin()
        self.db.transition_provider_circuit_state(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            to_state="open",
            reason_bucket="timeout",
            cooldown_until=datetime(2026, 5, 6, 11, 0, 0),
            now=datetime(2026, 5, 6, 10, 30, 0),
        )

        response = self.client.get(
            "/api/v1/admin/providers/sla-readiness",
            params={
                "provider": "tradier",
                "since": "2026-05-06T00:00:00",
                "runtimePilotFallbackEvaluationEnabled": "true",
            },
        )

        self.assertEqual(response.status_code, 200)
        item = self._sla_item(
            response.json(),
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
        )
        runtime_pilot = item["runtimePilot"]
        self.assertFalse(runtime_pilot["pilotEnabled"])
        self.assertTrue(runtime_pilot["fallbackEvaluationEnabled"])
        self.assertTrue(runtime_pilot["scopeMatched"])
        self.assertTrue(runtime_pilot["advisoryOnly"])
        self.assertFalse(runtime_pilot["liveEnforcement"])
        self.assertFalse(runtime_pilot["wouldBlockCall"])
        self.assertFalse(runtime_pilot["pilotWouldBlock"])
        self.assertTrue(runtime_pilot["pilotWouldFallback"])
        self.assertFalse(runtime_pilot["wouldChangeProviderOrder"])
        self.assertFalse(runtime_pilot["wouldChangeFallbackBehavior"])
        self.assertTrue(runtime_pilot["noExternalCalls"])
        self.assertFalse(runtime_pilot["providerBehaviorChanged"])
        self.assertFalse(runtime_pilot["marketCacheBehaviorChanged"])

    def test_sla_readiness_admin_probe_pilot_evidence_is_bounded_sanitized_and_opt_in(self) -> None:
        self._as_provider_read_admin()
        os.environ[PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ENABLED_ENV] = "true"
        os.environ.pop(PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ROLLBACK_ENV, None)
        self.db.transition_provider_circuit_state(
            provider="fmp",
            provider_category="data_source_validation",
            route_family="admin_provider_probe",
            to_state="provider_quota_depleted",
            reason_bucket="provider_429",
            metadata={
                "safe_label": "admin_probe_pilot",
                "url": "https://provider.example.test/raw?api_key=must-not-leak",
                "request_id": "request-id-must-not-leak",
                "requestId": "request-id-camel-must-not-leak",
                "headers": {"Authorization": "Bearer must-not-leak"},
                "token": "token-must-not-leak",
                "raw_payload": "must-not-leak",
                "trace": "Traceback trace-must-not-leak",
                "traceId": "trace-id-must-not-leak",
                "credential": "credential-must-not-leak",
                "cache_key": "cache-key-must-not-leak",
                "cacheKey": "cache-key-camel-must-not-leak",
                "stack_trace": "Traceback must-not-leak",
            },
            now=datetime(2026, 5, 6, 10, 30, 0),
        )

        def forbidden(*_args, **_kwargs):
            raise AssertionError("admin probe pilot evidence must stay read-only and offline")

        with (
            patch("src.storage.DatabaseManager.transition_provider_circuit_state", side_effect=forbidden),
            patch("src.storage.DatabaseManager.update_provider_quota_window_counters", side_effect=forbidden),
            patch("src.storage.DatabaseManager.record_provider_probe_event", side_effect=forbidden),
            patch(
                "src.services.provider_circuit_observer.ProviderCircuitObserver.record_observation",
                side_effect=forbidden,
            ),
            patch("src.services.quota_policy_service.QuotaPolicyService.evaluate_quota", side_effect=forbidden),
            patch("src.services.quota_policy_service.QuotaPolicyService.reserve_quota", side_effect=forbidden),
            patch("src.services.quota_policy_service.QuotaPolicyService.consume_reservation", side_effect=forbidden),
            patch("src.services.quota_policy_service.QuotaPolicyService.release_reservation", side_effect=forbidden),
            patch("src.notification.NotificationService.send", side_effect=forbidden),
            patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
            patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
            patch(
                "src.services.scanner_ai_service.ScannerAiInterpretationService.interpret_shortlist",
                side_effect=forbidden,
            ),
            patch("requests.sessions.Session.request", side_effect=forbidden),
        ):
            response = self.client.get(
                "/api/v1/admin/providers/sla-readiness",
                params={
                    "provider": "fmp",
                    "routeFamily": "admin_provider_probe",
                    "since": "2026-05-06T00:00:00",
                    "adminProbePilotEvidence": "true",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        item = self._sla_item(
            payload,
            provider="fmp",
            provider_category="data_source_validation",
            route_family="admin_provider_probe",
        )
        evidence = item["adminProbePilotEvidence"]
        self.assertEqual(evidence["contractVersion"], "provider_admin_probe_pilot_evidence_v1")
        self.assertTrue(evidence["pilotEnabled"])
        self.assertFalse(evidence["rollbackEnabled"])
        self.assertEqual(evidence["selectedBoundary"], "/config/data-source/test-builtin")
        self.assertEqual(evidence["apiRoute"], "/api/v1/system/config/data-source/test-builtin")
        self.assertTrue(evidence["selectedBoundaryOnly"])
        self.assertEqual(evidence["providerCategory"], "data_source_validation")
        self.assertEqual(evidence["routeFamily"], "admin_provider_probe")
        self.assertEqual(evidence["lastDecisionCategory"], "blocked")
        self.assertTrue(evidence["scopeMatched"])
        self.assertTrue(evidence["liveEnforcement"])
        self.assertTrue(evidence["wouldBlockCall"])
        self.assertTrue(evidence["wouldBlockIfEnforced"])
        self.assertTrue(evidence["adminProbeOnly"])
        self.assertTrue(evidence["defaultOffPosture"])
        self.assertTrue(evidence["rollbackAvailable"])
        self.assertFalse(evidence["publicRuntimeProviderBlocking"])
        self.assertFalse(evidence["memberRuntimeProviderBlocking"])
        self.assertFalse(evidence["providerRuntimeEnforcement"])
        self.assertFalse(evidence["providerOrderFallbackCacheBehaviorChanged"])
        self.assertTrue(evidence["sanitizedFieldsOnly"])
        self.assertFalse(evidence["acceptedOperatorEvidencePresent"])
        self.assertIn(
            "public_provider_circuit_enforcement_not_accepted",
            evidence["remainingPublicLaunchNoGoItems"],
        )
        self.assertEqual(evidence["enforcementBlockReasonCode"], "provider_429")
        self.assertFalse(evidence["wouldChangeProviderOrder"])
        self.assertFalse(evidence["wouldChangeFallbackBehavior"])
        self.assertTrue(evidence["noExternalCalls"])
        self.assertTrue(evidence["adminProbeBehaviorChanged"])
        self.assertFalse(evidence["globalProviderBehaviorChanged"])
        self.assertFalse(evidence["marketCacheBehaviorChanged"])
        self.assertFalse(evidence["quotaEnforcementChanged"])
        self.assertFalse(evidence["authRbacSessionChanged"])
        self.assertFalse(evidence["notificationSendEnabled"])
        self.assertFalse(evidence["publicLaunchReady"])
        self.assertEqual(evidence["defaultOffLabel"], "provider_circuit_admin_probe_pilot_default_off")
        self.assertEqual(
            evidence["rollbackLabel"],
            "WOLFYSTOCK_PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ROLLBACK_ENABLED",
        )
        self.assertIn("provider_admin_probe_pilot_evidence", ",".join(payload["metadata"]["dataSources"]))
        text = self._json_text(payload).lower()
        for blocked in (
            "must-not-leak",
            "https://provider.example",
            "api_key",
            "authorization",
            "request-id-must-not-leak",
            "request-id-camel-must-not-leak",
            "token-must-not-leak",
            "raw_payload",
            "trace-must-not-leak",
            "trace-id-must-not-leak",
            "credential-must-not-leak",
            "cache-key-must-not-leak",
            "cache-key-camel-must-not-leak",
            "traceback",
        ):
            self.assertNotIn(blocked, text)

    def test_sla_readiness_admin_probe_pilot_evidence_shows_default_off_and_rollback(self) -> None:
        self._as_provider_read_admin()
        self.db.transition_provider_circuit_state(
            provider="fmp",
            provider_category="data_source_validation",
            route_family="admin_provider_probe",
            to_state="open",
            reason_bucket="timeout",
            now=datetime(2026, 5, 6, 10, 30, 0),
        )

        response = self.client.get(
            "/api/v1/admin/providers/sla-readiness",
            params={
                "provider": "fmp",
                "routeFamily": "admin_provider_probe",
                "since": "2026-05-06T00:00:00",
                "adminProbePilotEvidence": "true",
            },
        )

        self.assertEqual(response.status_code, 200)
        default_off_item = self._sla_item(
            response.json(),
            provider="fmp",
            provider_category="data_source_validation",
            route_family="admin_provider_probe",
        )
        default_off_evidence = default_off_item["adminProbePilotEvidence"]
        self.assertFalse(default_off_evidence["pilotEnabled"])
        self.assertFalse(default_off_evidence["rollbackEnabled"])
        self.assertEqual(default_off_evidence["lastDecisionCategory"], "disabled_by_default")
        self.assertFalse(default_off_evidence["liveEnforcement"])
        self.assertFalse(default_off_evidence["wouldBlockCall"])
        self.assertTrue(default_off_evidence["wouldBlockIfEnforced"])
        self.assertFalse(default_off_evidence["adminProbeBehaviorChanged"])
        self.assertFalse(default_off_evidence["globalProviderBehaviorChanged"])
        self.assertFalse(default_off_evidence["marketCacheBehaviorChanged"])

        os.environ[PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ENABLED_ENV] = "true"
        os.environ[PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ROLLBACK_ENV] = "true"
        rollback_response = self.client.get(
            "/api/v1/admin/providers/sla-readiness",
            params={
                "provider": "fmp",
                "routeFamily": "admin_provider_probe",
                "since": "2026-05-06T00:00:00",
                "adminProbePilotEvidence": "true",
            },
        )

        self.assertEqual(rollback_response.status_code, 200)
        rollback_item = self._sla_item(
            rollback_response.json(),
            provider="fmp",
            provider_category="data_source_validation",
            route_family="admin_provider_probe",
        )
        rollback_evidence = rollback_item["adminProbePilotEvidence"]
        self.assertTrue(rollback_evidence["pilotEnabled"])
        self.assertTrue(rollback_evidence["rollbackEnabled"])
        self.assertEqual(rollback_evidence["lastDecisionCategory"], "disabled_by_rollback")
        self.assertFalse(rollback_evidence["liveEnforcement"])
        self.assertFalse(rollback_evidence["wouldBlockCall"])
        self.assertTrue(rollback_evidence["wouldBlockIfEnforced"])
        self.assertEqual(rollback_evidence["enforcementBlockReasonCode"], "timeout")
        self.assertFalse(rollback_evidence["adminProbeBehaviorChanged"])
        self.assertFalse(rollback_evidence["globalProviderBehaviorChanged"])
        self.assertFalse(rollback_evidence["marketCacheBehaviorChanged"])

    def test_sla_readiness_admin_probe_pilot_evidence_omits_out_of_scope_dimensions(self) -> None:
        self._as_provider_read_admin()
        observer = ProviderCircuitObserver(db=self.db)
        observer.record_observation(
            provider="fmp",
            provider_category="quote",
            route_family="analysis",
            result_bucket="operator_disabled",
            observed_at=datetime(2026, 5, 6, 10, 45, 0),
            metadata={
                "safe_label": "out_of_scope",
                "url": "https://provider.example.test/raw?token=must-not-leak",
                "raw_payload": "must-not-leak",
            },
        )

        response = self.client.get(
            "/api/v1/admin/providers/sla-readiness",
            params={
                "provider": "fmp",
                "routeFamily": "analysis",
                "since": "2026-05-06T00:00:00",
                "adminProbePilotEvidence": "true",
            },
        )

        self.assertEqual(response.status_code, 200)
        item = self._sla_item(response.json(), provider="fmp", provider_category="quote", route_family="analysis")
        self.assertNotIn("adminProbePilotEvidence", item)
        text = self._json_text(response.json()).lower()
        for blocked in ("must-not-leak", "provider.example", "?token=", "raw_payload"):
            self.assertNotIn(blocked, text)

    def test_sla_readiness_endpoint_separates_scoped_and_unscoped_items_by_dimensions(self) -> None:
        self._as_provider_read_admin()
        observer = ProviderCircuitObserver(db=self.db)
        self.db.transition_provider_circuit_state(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            to_state="open",
            reason_bucket="timeout",
            cooldown_until=datetime(2026, 5, 6, 11, 0, 0),
            now=datetime(2026, 5, 6, 10, 30, 0),
        )
        observer.record_observation(
            provider="tradier",
            provider_category="quote",
            route_family="analysis",
            result_bucket="operator_disabled",
            observed_at=datetime(2026, 5, 6, 10, 40, 0),
            metadata={
                "safe_label": "route_mismatch",
                "request_body": "must-not-leak",
                "url": "https://provider.example.test/raw?token=must-not-leak",
            },
        )

        with patch("requests.sessions.Session.request") as request_mock:
            response = self.client.get(
                "/api/v1/admin/providers/sla-readiness",
                params={"provider": "tradier", "since": "2026-05-06T00:00:00"},
            )

        self.assertEqual(response.status_code, 200)
        request_mock.assert_not_called()
        payload = response.json()
        scoped = self._sla_item(payload, provider="tradier", provider_category="options", route_family="options_lab")
        unscoped = self._sla_item(payload, provider="tradier", provider_category="quote", route_family="analysis")
        self.assertTrue(scoped["scopeMatched"])
        self.assertFalse(scoped["liveEnforcement"])
        self.assertFalse(scoped["wouldBlockCall"])
        self.assertTrue(scoped["wouldBlockIfEnforced"])
        self.assertEqual(scoped["enforcementBlockReasonCode"], "timeout")
        self.assertTrue(scoped["noExternalCalls"])
        self.assertFalse(scoped["providerBehaviorChanged"])
        self.assertFalse(scoped["marketCacheBehaviorChanged"])
        self.assertFalse(unscoped["scopeMatched"])
        self.assertFalse(unscoped["liveEnforcement"])
        self.assertFalse(unscoped["wouldBlockCall"])
        self.assertTrue(unscoped["wouldBlockIfEnforced"])
        self.assertEqual(unscoped["enforcementBlockReasonCode"], "operator_disabled")
        self.assertEqual(unscoped["circuitStateCandidate"], "disabled_by_operator")
        self.assertTrue(unscoped["noExternalCalls"])
        self.assertFalse(unscoped["wouldChangeProviderOrder"])
        self.assertFalse(unscoped["wouldChangeFallbackBehavior"])
        text = self._json_text(payload).lower()
        for blocked in ("must-not-leak", "request_body", "provider.example", "?token="):
            self.assertNotIn(blocked, text)

    def test_sla_readiness_endpoint_keeps_every_item_advisory_only(self) -> None:
        self._as_provider_read_admin()
        observer = ProviderCircuitObserver(db=self.db)
        self.db.transition_provider_circuit_state(
            provider="tradier",
            provider_category="options",
            route_family="options_lab",
            to_state="provider_quota_depleted",
            reason_bucket="provider_429",
            now=datetime(2026, 5, 6, 10, 30, 0),
        )
        observer.record_observation(
            provider="fmp",
            provider_category="quote",
            route_family="analysis",
            result_bucket="operator_disabled",
            observed_at=datetime(2026, 5, 6, 10, 45, 0),
        )

        response = self.client.get("/api/v1/admin/providers/sla-readiness", params={"since": "2026-05-06T00:00:00"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        allowed_reason_codes = set(ProviderCircuitObserver.RESULT_BUCKETS)
        for item in payload["items"]:
            with self.subTest(provider=item["provider"], category=item.get("providerCategory"), route=item.get("routeFamily")):
                self.assertFalse(item["liveEnforcement"])
                self.assertFalse(item["wouldBlockCall"])
                self.assertTrue(item["noExternalCalls"])
                self.assertFalse(item["providerBehaviorChanged"])
                self.assertFalse(item["marketCacheBehaviorChanged"])
                self.assertFalse(item["wouldChangeProviderOrder"])
                self.assertFalse(item["wouldChangeFallbackBehavior"])
                reason_code = item.get("enforcementBlockReasonCode")
                if reason_code is not None:
                    self.assertIn(reason_code, allowed_reason_codes)
                for recent_error in item["recentErrors"]:
                    self.assertIn(recent_error["reasonBucket"], allowed_reason_codes)
        text = self._json_text(payload).lower()
        for blocked in ("api_key", "access_token", "authorization", "raw_payload", "https://"):
            self.assertNotIn(blocked, text)

    def test_sla_readiness_diagnostics_do_not_mutate_state_or_send_notifications(self) -> None:
        self._as_provider_read_admin()
        self._seed_circuit_fixture()

        def forbidden(*_args, **_kwargs):
            raise AssertionError("sla readiness diagnostics should stay read-only and offline")

        with (
            patch("src.storage.DatabaseManager.transition_provider_circuit_state", side_effect=forbidden),
            patch("src.storage.DatabaseManager.update_provider_quota_window_counters", side_effect=forbidden),
            patch("src.storage.DatabaseManager.record_provider_probe_event", side_effect=forbidden),
            patch("src.services.provider_circuit_observer.ProviderCircuitObserver.record_observation", side_effect=forbidden),
            patch("src.notification.NotificationService.send", side_effect=forbidden),
            patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
            patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
            patch("src.services.scanner_ai_service.ScannerAiInterpretationService.interpret_shortlist", side_effect=forbidden),
            patch("requests.sessions.Session.request", side_effect=forbidden),
        ):
            response = self.client.get(
                "/api/v1/admin/providers/sla-readiness",
                params={"provider": "fmp", "since": "2026-05-06T00:00:00"},
            )

        self.assertEqual(response.status_code, 200)
        metadata = response.json()["metadata"]
        self.assertTrue(metadata["readOnly"])
        self.assertTrue(metadata["noExternalCalls"])
        self.assertFalse(metadata["liveEnforcement"])


if __name__ == "__main__":
    unittest.main()
