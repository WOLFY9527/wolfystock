# -*- coding: utf-8 -*-
"""Admin quota dry-run integration tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID
from src.storage import DatabaseManager


def _admin_user() -> CurrentUser:
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


def _admin_without_cost_capability() -> CurrentUser:
    return CurrentUser(
        user_id=BOOTSTRAP_ADMIN_USER_ID,
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=("users:read",),
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


class AdminQuotaDryRunApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "admin_quota.db"
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")

        from api.v1.endpoints import admin_cost

        self.app = FastAPI()
        self.app.include_router(admin_cost.router, prefix="/api/v1/admin")
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        DatabaseManager.reset_instance()
        self.temp_dir.cleanup()

    def _as_admin(self) -> None:
        self.app.dependency_overrides[get_current_user] = _admin_user

    def _as_admin_without_cost_capability(self) -> None:
        self.app.dependency_overrides[get_current_user] = _admin_without_cost_capability

    def _as_user(self) -> None:
        self.app.dependency_overrides[get_current_user] = _regular_user

    @staticmethod
    def _json_text(payload) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def _post_dry_run(self, payload: dict) -> object:
        with patch("src.services.quota_policy_service.DatabaseManager.get_instance", return_value=self.db):
            return self.client.post("/api/v1/admin/cost/quota-dry-run", json=payload)

    def test_admin_cost_capability_required(self) -> None:
        response = self.client.post("/api/v1/admin/cost/quota-dry-run", json={})
        self.assertEqual(response.status_code, 401)

        self._as_user()
        forbidden = self.client.post("/api/v1/admin/cost/quota-dry-run", json={})
        self.assertEqual(forbidden.status_code, 403)

        self._as_admin_without_cost_capability()
        missing_capability = self.client.post("/api/v1/admin/cost/quota-dry-run", json={})
        self.assertEqual(missing_capability.status_code, 403)

    def test_dry_run_allowed_decision(self) -> None:
        self._as_admin()

        response = self._post_dry_run(
            {
                "ownerUserId": "user-1",
                "routeFamily": "analysis",
                "tokenEstimate": 2100,
            }
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["allowed"])
        self.assertFalse(payload["wouldBlock"])
        self.assertEqual(payload["status"], "allowed")
        self.assertEqual(payload["routeFamily"], "analysis")
        self.assertEqual(payload["estimatedUnits"], 15)
        self.assertEqual(payload["enforcementMode"], "dry_run")
        self.assertFalse(payload["metadata"]["liveEnforcement"])
        self.assertTrue(payload["metadata"]["noExternalCalls"])
        self.assertEqual(payload["metadata"]["budgetAlert"]["state"], "under_budget")
        self.assertFalse(payload["metadata"]["budgetAlert"]["liveEnforcement"])
        self.assertEqual(payload["metadata"]["shadowPreflight"]["state"], "would_allow")
        self.assertFalse(payload["metadata"]["shadowPreflight"]["wouldBlock"])
        self.assertTrue(payload["metadata"]["shadowPreflight"]["advisoryOnly"])
        self.assertFalse(payload["metadata"]["shadowPreflight"]["requestBlocked"])
        self.assertFalse(payload["metadata"]["shadowPreflight"]["liveEnforcement"])
        pilot = payload["metadata"]["pilotReadiness"]
        self.assertEqual(pilot["state"], "pilot_advisory_allow")
        self.assertFalse(pilot["pilot"]["enforcementEnabled"])
        self.assertTrue(pilot["pilot"]["scopeExplicit"])
        self.assertFalse(pilot["requestBlocked"])
        self.assertFalse(pilot["liveEnforcement"])
        self.assertFalse(pilot["invoiceReconciliation"]["enforcementWired"])
        self.assertTrue(pilot["safety"]["noExternalCalls"])

    def test_dry_run_budget_alert_states_are_diagnostic_only(self) -> None:
        self._as_admin()
        self.db.upsert_quota_policy(
            policy_key="user-budget-alerts",
            scope_type="user",
            daily_budget_units=120,
            metadata={"daily_soft_limit_units": 100},
        )

        cases = (
            (40, "under_budget", "would_allow", True),
            (80, "near_soft_limit", "would_warn", True),
            (100, "over_soft_limit", "would_block_soft_limit", True),
            (121, "over_hard_limit", "would_block_hard_limit", False),
        )
        for estimated_units, expected_alert_state, expected_shadow_state, expected_allowed in cases:
            with self.subTest(expected_shadow_state=expected_shadow_state):
                response = self._post_dry_run(
                    {
                        "ownerUserId": "user-1",
                        "routeFamily": "analysis",
                        "estimatedUnits": estimated_units,
                    }
                )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["allowed"], expected_allowed)
                self.assertEqual(payload["wouldBlock"], not expected_allowed)
                self.assertEqual(payload["metadata"]["budgetAlert"]["state"], expected_alert_state)
                self.assertFalse(payload["metadata"]["budgetAlert"]["wouldBlock"])
                self.assertFalse(payload["metadata"]["budgetAlert"]["liveEnforcement"])
                self.assertEqual(payload["metadata"]["shadowPreflight"]["state"], expected_shadow_state)
                self.assertEqual(
                    payload["metadata"]["shadowPreflight"]["wouldBlock"],
                    expected_shadow_state.startswith("would_block"),
                )
                self.assertTrue(payload["metadata"]["shadowPreflight"]["advisoryOnly"])
                self.assertFalse(payload["metadata"]["shadowPreflight"]["requestBlocked"])
                self.assertFalse(payload["metadata"]["shadowPreflight"]["liveEnforcement"])
                pilot = payload["metadata"]["pilotReadiness"]
                self.assertEqual(pilot["shadowPreflight"]["state"], expected_shadow_state)
                self.assertFalse(pilot["pilot"]["enforcementEnabled"])
                self.assertFalse(pilot["requestBlocked"])
                self.assertFalse(pilot["liveEnforcement"])
                self.assertTrue(pilot["advisoryOnly"])

    def test_dry_run_shadow_preflight_pricing_unknown_fails_safe_advisory_only(self) -> None:
        self._as_admin()

        response = self._post_dry_run(
            {
                "ownerUserId": "user-1",
                "routeFamily": "analysis",
                "estimatedUnits": 25,
                "pricingStatus": "pricing_unknown",
            }
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["allowed"])
        self.assertFalse(payload["wouldBlock"])
        self.assertEqual(payload["metadata"]["budgetAlert"]["state"], "pricing_unknown_warning")
        shadow = payload["metadata"]["shadowPreflight"]
        self.assertEqual(shadow["state"], "pricing_unknown_fail_safe")
        self.assertEqual(shadow["reasonCode"], "pricing_policy_unknown")
        self.assertTrue(shadow["wouldBlock"])
        self.assertTrue(shadow["advisoryOnly"])
        self.assertFalse(shadow["requestBlocked"])
        self.assertFalse(shadow["liveEnforcement"])
        pilot = payload["metadata"]["pilotReadiness"]
        self.assertEqual(pilot["state"], "pilot_advisory_would_block")
        self.assertEqual(pilot["reasonCode"], "pricing_policy_unknown")
        self.assertTrue(pilot["wouldBlock"])
        self.assertFalse(pilot["requestBlocked"])
        self.assertFalse(pilot["liveEnforcement"])

    def test_dry_run_shadow_preflight_owner_isolation_metadata_is_advisory_only(self) -> None:
        self._as_admin()
        self.db.upsert_quota_policy(
            policy_key="user-budget-alerts",
            scope_type="user",
            daily_budget_units=120,
            metadata={"daily_soft_limit_units": 100},
        )
        self._post_dry_run(
            {
                "ownerUserId": "user-2",
                "routeFamily": "analysis",
                "operation": "reserve",
                "estimatedUnits": 95,
            }
        )

        response = self._post_dry_run(
            {
                "ownerUserId": "user-1",
                "routeFamily": "analysis",
                "estimatedUnits": 10,
            }
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        shadow = payload["metadata"]["shadowPreflight"]
        self.assertEqual(shadow["state"], "would_allow")
        self.assertEqual(shadow["usedUnits"], 0)
        self.assertTrue(shadow["ownerIsolation"]["ownerScoped"])
        self.assertTrue(shadow["ownerIsolation"]["otherOwnersExcluded"])
        self.assertFalse(shadow["requestBlocked"])
        pilot = payload["metadata"]["pilotReadiness"]
        self.assertEqual(pilot["scope"]["ownerUserId"], "user-1")
        self.assertTrue(pilot["pilot"]["scopeExplicit"])
        self.assertFalse(pilot["requestBlocked"])

    def test_dry_run_pilot_readiness_requires_owner_scope_for_enabled_pilot(self) -> None:
        self._as_admin()
        self.db.upsert_quota_policy(
            policy_key="user-budget-alerts",
            scope_type="user",
            daily_budget_units=120,
            metadata={"daily_soft_limit_units": 100},
        )

        response = self._post_dry_run(
            {
                "routeFamily": "analysis",
                "estimatedUnits": 121,
                "enforcementMode": "enabled",
            }
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        pilot = payload["metadata"]["pilotReadiness"]
        self.assertEqual(pilot["state"], "pilot_scope_not_ready")
        self.assertEqual(pilot["reasonCode"], "pilot_owner_scope_required")
        self.assertTrue(pilot["wouldBlock"])
        self.assertTrue(pilot["advisoryOnly"])
        self.assertFalse(pilot["requestBlocked"])
        self.assertFalse(pilot["liveEnforcement"])
        self.assertFalse(pilot["pilot"]["ownerScoped"])

    def test_dry_run_pilot_readiness_sanitizes_scope_context(self) -> None:
        self._as_admin()

        response = self._post_dry_run(
            {
                "ownerUserId": "owner-token-must-not-leak",
                "routeFamily": "analysis",
                "provider": "openai?api_key=must-not-leak",
                "modelTier": "model-with-secret",
                "estimatedUnits": 10,
            }
        )

        self.assertEqual(response.status_code, 200)
        text = self._json_text(response.json()).lower()
        self.assertNotIn("must-not-leak", text)
        pilot = response.json()["metadata"]["pilotReadiness"]
        self.assertEqual(pilot["scope"]["ownerUserId"], "redacted")
        self.assertEqual(pilot["scope"]["provider"], "redacted")
        self.assertEqual(pilot["scope"]["modelTier"], "redacted")

    def test_dry_run_would_block_global_kill_switch(self) -> None:
        self._as_admin()

        response = self._post_dry_run(
            {
                "ownerUserId": "user-1",
                "routeFamily": "scanner-ai",
                "tokenEstimate": 1000,
                "globalKillSwitch": True,
            }
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["allowed"])
        self.assertTrue(payload["wouldBlock"])
        self.assertEqual(payload["reasonCode"], "global_kill_switch")
        self.assertEqual(payload["routeFamily"], "scanner_ai")

    def test_dry_run_would_block_token_cap(self) -> None:
        self._as_admin()
        self.db.upsert_quota_policy(
            policy_key="analysis-token-cap",
            scope_type="route",
            route_family="analysis",
            token_cap=1000,
        )

        response = self._post_dry_run(
            {
                "ownerUserId": "user-1",
                "routeFamily": "analysis",
                "tokenEstimate": 1001,
            }
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["allowed"])
        self.assertTrue(payload["wouldBlock"])
        self.assertEqual(payload["reasonCode"], "token_cap_exceeded")

    def test_reservation_lifecycle_through_diagnostic_path(self) -> None:
        self._as_admin()

        reserved = self._post_dry_run(
            {
                "ownerUserId": "user-1",
                "routeFamily": "analysis",
                "operation": "reserve",
                "tokenEstimate": 1000,
                "metadata": {"safe_label": "quota-test", "api_key": "must-not-leak"},
            }
        )
        self.assertEqual(reserved.status_code, 200)
        reservation_id = reserved.json()["reservationId"]
        self.assertTrue(reservation_id)

        consumed = self._post_dry_run(
            {
                "operation": "consume",
                "reservationId": reservation_id,
                "actualUnits": 4,
            }
        )
        self.assertEqual(consumed.status_code, 200)
        self.assertTrue(consumed.json()["allowed"])
        self.assertEqual(consumed.json()["status"], "consumed")

        reserved_for_release = self._post_dry_run(
            {
                "ownerUserId": "user-1",
                "routeFamily": "analysis",
                "operation": "reserve",
                "tokenEstimate": 1000,
            }
        )
        released = self._post_dry_run(
            {
                "operation": "release",
                "reservationId": reserved_for_release.json()["reservationId"],
            }
        )
        self.assertEqual(released.status_code, 200)
        self.assertTrue(released.json()["allowed"])
        self.assertEqual(released.json()["status"], "released")

    def test_disabled_mode_is_non_blocking(self) -> None:
        self._as_admin()

        response = self._post_dry_run(
            {
                "ownerUserId": "user-1",
                "routeFamily": "analysis",
                "tokenEstimate": 1001,
                "enforcementMode": "disabled",
                "globalKillSwitch": True,
            }
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["allowed"])
        self.assertFalse(payload["wouldBlock"])
        self.assertEqual(payload["status"], "disabled")

    def test_existing_cost_summary_remains_unblocked_by_quota_policy(self) -> None:
        self._as_admin()
        self.db.upsert_quota_policy(
            policy_key="global-kill-switch",
            scope_type="global",
            metadata={"kill_switch": True},
        )

        with (
            patch("src.services.quota_policy_service.DatabaseManager.get_instance", return_value=self.db),
            patch("src.services.duplicate_cost_summary_service.DatabaseManager.get_instance", return_value=self.db),
        ):
            dry_run = self.client.post("/api/v1/admin/cost/quota-dry-run", json={"routeFamily": "analysis"})
            summary = self.client.get("/api/v1/admin/cost/duplicate-summary")

        self.assertEqual(dry_run.status_code, 200)
        self.assertFalse(dry_run.json()["allowed"])
        self.assertEqual(summary.status_code, 200)

    def test_response_does_not_expose_secret_like_metadata(self) -> None:
        self._as_admin()

        response = self._post_dry_run(
            {
                "ownerUserId": "user-1",
                "routeFamily": "analysis",
                "operation": "reserve",
                "metadata": {
                    "api_key": "must-not-leak",
                    "cookie": "must-not-leak",
                    "raw_prompt": "must-not-leak",
                    "safe_label": "quota-test",
                },
            }
        )

        self.assertEqual(response.status_code, 200)
        text = self._json_text(response.json()).lower()
        for blocked in ("must-not-leak", "api_key", "cookie", "raw_prompt", "session_id", "stack_trace"):
            self.assertNotIn(blocked, text)

    def test_endpoint_does_not_call_live_llm_or_provider_paths(self) -> None:
        self._as_admin()

        def forbidden(*_args, **_kwargs):
            raise AssertionError("live path should not be called by quota dry-run")

        with (
            patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
            patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
            patch("src.services.scanner_ai_service.ScannerAiInterpretationService.interpret_shortlist", side_effect=forbidden),
            patch("src.services.quota_policy_service.DatabaseManager.get_instance", return_value=self.db),
        ):
            response = self.client.post(
                "/api/v1/admin/cost/quota-dry-run",
                json={"ownerUserId": "user-1", "routeFamily": "analysis"},
            )

        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
