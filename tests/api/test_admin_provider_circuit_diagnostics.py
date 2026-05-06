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

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from api.deps import CurrentUser, get_current_user
from api.v1.endpoints import admin_provider_circuits
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID
from src.storage import DatabaseManager


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


class AdminProviderCircuitDiagnosticsApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "provider_circuit_api.db"
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")
        self.app = FastAPI()
        self.app.include_router(admin_provider_circuits.router, prefix="/api/v1/admin")
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
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
        fmp = next(item for item in payload["items"] if item["provider"] == "fmp")
        self.assertEqual(fmp["providerCategory"], "quote")
        self.assertEqual(fmp["routeFamily"], "analysis")
        self.assertEqual(fmp["state"], "open")
        self.assertEqual(fmp["reasonBucket"], "timeout")
        self.assertEqual(fmp["operatorActionRef"], "SAFE-AUDIT-1")

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
            response = self.client.get("/api/v1/admin/providers/circuits")

        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
