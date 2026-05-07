# -*- coding: utf-8 -*-
"""Synthetic tests for the WS2 quota policy foundation."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.quota_policy_service import QuotaPolicyService
from src.storage import DatabaseManager, QuotaReservation, QuotaUsageWindow


def _fresh_db() -> DatabaseManager:
    DatabaseManager.reset_instance()
    return DatabaseManager(db_url="sqlite:///:memory:")


class QuotaPolicyServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _fresh_db()
        self.service = QuotaPolicyService(db=self.db, enforcement_enabled=True)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()

    def test_global_kill_switch_blocks_synthetic_reservation(self) -> None:
        service = QuotaPolicyService(db=self.db, enforcement_enabled=True, global_kill_switch=True)

        result = service.reserve_quota(owner_user_id="user-1", route_family="analysis")

        self.assertFalse(result.allowed)
        self.assertEqual(result.reason_code, "global_kill_switch")
        self.assertIsNone(result.reservation_id)

    def test_disabled_service_permits_noop_pass_through(self) -> None:
        service = QuotaPolicyService(db=self.db, enforcement_enabled=False, global_kill_switch=True)

        result = service.reserve_quota(owner_user_id="user-1", route_family="analysis")

        self.assertTrue(result.allowed)
        self.assertEqual(result.status, "disabled")
        self.assertIsNone(result.reservation_id)

    def test_disabled_policy_rejects_when_enforcement_enabled(self) -> None:
        self.db.upsert_quota_policy(
            policy_key="disabled-analysis",
            scope_type="route",
            route_family="analysis",
            enabled=False,
        )

        result = self.service.reserve_quota(owner_user_id="user-1", route_family="analysis")

        self.assertFalse(result.allowed)
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.reason_code, "quota_disabled")

    def test_per_user_daily_budget_exceeded(self) -> None:
        self.db.upsert_quota_policy(
            policy_key="user-daily",
            scope_type="user",
            daily_budget_units=9,
        )

        first = self.service.reserve_quota(
            owner_user_id="user-1",
            route_family="analysis",
            token_estimate=1000,
        )
        second = self.service.reserve_quota(
            owner_user_id="user-1",
            route_family="analysis",
            token_estimate=1000,
        )

        self.assertTrue(first.allowed)
        self.assertFalse(second.allowed)
        self.assertEqual(second.reason_code, "budget_exceeded")

    def test_per_user_monthly_budget_exceeded(self) -> None:
        self.db.upsert_quota_policy(
            policy_key="user-monthly",
            scope_type="user",
            monthly_budget_units=9,
        )

        first = self.service.reserve_quota(
            owner_user_id="user-1",
            route_family="analysis",
            token_estimate=1000,
        )
        second = self.service.reserve_quota(
            owner_user_id="user-1",
            route_family="analysis",
            token_estimate=1000,
        )

        self.assertTrue(first.allowed)
        self.assertFalse(second.allowed)
        self.assertEqual(second.reason_code, "budget_exceeded")

    def test_route_weight_estimation_is_deterministic(self) -> None:
        estimates = [
            self.service.estimate_budget_units(route_family="scanner_ai", token_estimate=2100)
            for _ in range(3)
        ]

        self.assertEqual(estimates, [18, 18, 18])
        self.assertLess(
            self.service.estimate_budget_units(route_family="guest_preview", token_estimate=2100),
            estimates[0],
        )

    def _seed_budget_alert_policy(self) -> None:
        self.db.upsert_quota_policy(
            policy_key="user-budget-alerts",
            scope_type="user",
            daily_budget_units=120,
            metadata={"daily_soft_limit_units": 100},
        )

    def test_budget_alert_dry_run_under_budget(self) -> None:
        self._seed_budget_alert_policy()

        alert = self.service.classify_budget_alert(
            owner_user_id="user-1",
            route_family="analysis",
            estimated_units=40,
        )

        self.assertEqual(alert.state, "under_budget")
        self.assertEqual(alert.severity, "info")
        self.assertFalse(alert.would_block)
        self.assertEqual(alert.projected_units, 40)

    def test_budget_alert_dry_run_near_soft_limit(self) -> None:
        self._seed_budget_alert_policy()

        alert = self.service.classify_budget_alert(
            owner_user_id="user-1",
            route_family="analysis",
            estimated_units=80,
        )

        self.assertEqual(alert.state, "near_soft_limit")
        self.assertEqual(alert.reason_code, "budget_near_soft_limit")
        self.assertFalse(alert.would_block)

    def test_budget_alert_dry_run_over_soft_limit(self) -> None:
        self._seed_budget_alert_policy()

        alert = self.service.classify_budget_alert(
            owner_user_id="user-1",
            route_family="analysis",
            estimated_units=100,
        )

        self.assertEqual(alert.state, "over_soft_limit")
        self.assertEqual(alert.reason_code, "budget_soft_limit_exceeded")
        self.assertFalse(alert.would_block)

    def test_budget_alert_dry_run_over_hard_limit(self) -> None:
        self._seed_budget_alert_policy()

        alert = self.service.classify_budget_alert(
            owner_user_id="user-1",
            route_family="analysis",
            estimated_units=121,
        )

        self.assertEqual(alert.state, "over_hard_limit")
        self.assertEqual(alert.reason_code, "budget_hard_limit_exceeded")
        self.assertFalse(alert.would_block)

    def test_budget_alert_unknown_pricing_policy_fails_safe_as_warning(self) -> None:
        alert = self.service.classify_budget_alert(
            owner_user_id="user-1",
            route_family="analysis",
            estimated_units=25,
            pricing_status="pricing_unknown",
        )

        self.assertEqual(alert.state, "pricing_unknown_warning")
        self.assertEqual(alert.reason_code, "pricing_policy_unknown")
        self.assertEqual(alert.severity, "warning")
        self.assertFalse(alert.would_block)

    def test_budget_alert_owner_scoping_ignores_other_users_usage(self) -> None:
        used_by_other = self.service.reserve_quota(
            owner_user_id="user-2",
            route_family="analysis",
            estimated_units=95,
        )
        self.assertTrue(used_by_other.allowed)
        self._seed_budget_alert_policy()

        user_one = self.service.classify_budget_alert(
            owner_user_id="user-1",
            route_family="analysis",
            estimated_units=10,
        )
        user_two = self.service.classify_budget_alert(
            owner_user_id="user-2",
            route_family="analysis",
            estimated_units=10,
        )

        self.assertEqual(user_one.used_units, 0)
        self.assertEqual(user_one.state, "under_budget")
        self.assertEqual(user_two.used_units, 95)
        self.assertEqual(user_two.state, "over_soft_limit")

    def test_shadow_preflight_covers_allow_warn_soft_hard_and_pricing_unknown(self) -> None:
        self._seed_budget_alert_policy()

        cases = (
            (40, "ok", "would_allow", False),
            (80, "ok", "would_warn", False),
            (100, "ok", "would_block_soft_limit", True),
            (121, "ok", "would_block_hard_limit", True),
            (40, "pricing_unknown", "pricing_unknown_fail_safe", True),
        )
        for estimated_units, pricing_status, expected_state, expected_block in cases:
            with self.subTest(expected_state=expected_state):
                preflight = self.service.classify_shadow_preflight(
                    owner_user_id="user-1",
                    route_family="analysis",
                    estimated_units=estimated_units,
                    pricing_status=pricing_status,
                )

                self.assertEqual(preflight.state, expected_state)
                self.assertEqual(preflight.would_block, expected_block)
                payload = preflight.to_dict()
                self.assertTrue(payload["advisoryOnly"])
                self.assertFalse(payload["requestBlocked"])
                self.assertFalse(payload["liveEnforcement"])

    def test_shadow_preflight_is_read_only_and_does_not_reserve_or_consume_quota(self) -> None:
        self._seed_budget_alert_policy()
        with self.db.session_scope() as session:
            before_reservations = session.query(QuotaReservation).count()
            before_windows = session.query(QuotaUsageWindow).count()

        preflight = self.service.classify_shadow_preflight(
            owner_user_id="user-1",
            route_family="analysis",
            estimated_units=121,
        )

        self.assertEqual(preflight.state, "would_block_hard_limit")
        with self.db.session_scope() as session:
            after_reservations = session.query(QuotaReservation).count()
            after_windows = session.query(QuotaUsageWindow).count()
        self.assertEqual(after_reservations, before_reservations)
        self.assertEqual(after_windows, before_windows)

    def test_shadow_preflight_owner_isolation_excludes_other_users_usage(self) -> None:
        used_by_other = self.service.reserve_quota(
            owner_user_id="user-2",
            route_family="analysis",
            estimated_units=95,
        )
        self.assertTrue(used_by_other.allowed)
        self._seed_budget_alert_policy()

        user_one = self.service.classify_shadow_preflight(
            owner_user_id="user-1",
            route_family="analysis",
            estimated_units=10,
        )
        user_two = self.service.classify_shadow_preflight(
            owner_user_id="user-2",
            route_family="analysis",
            estimated_units=10,
        )

        self.assertEqual(user_one.budget_alert.used_units, 0)
        self.assertEqual(user_one.state, "would_allow")
        self.assertEqual(user_two.budget_alert.used_units, 95)
        self.assertEqual(user_two.state, "would_block_soft_limit")
        self.assertTrue(user_one.to_dict()["ownerIsolation"]["otherOwnersExcluded"])
        self.assertTrue(user_two.to_dict()["ownerIsolation"]["ownerScoped"])

    def test_pilot_readiness_preflight_defaults_to_advisory_disabled_enforcement(self) -> None:
        self._seed_budget_alert_policy()

        preflight = self.service.classify_pilot_readiness_preflight(
            owner_user_id="user-1",
            route_family="analysis",
            provider="openai",
            model_tier="openai/gpt-4o-mini",
            estimated_units=121,
        )

        payload = preflight.to_dict()
        self.assertEqual(preflight.state, "pilot_advisory_would_block")
        self.assertTrue(preflight.would_block)
        self.assertTrue(preflight.advisory_only)
        self.assertFalse(preflight.request_blocked)
        self.assertFalse(preflight.live_enforcement)
        self.assertFalse(payload["pilot"]["enforcementEnabled"])
        self.assertEqual(payload["scope"]["ownerUserId"], "user-1")
        self.assertEqual(payload["scope"]["provider"], "openai")
        self.assertEqual(payload["scope"]["modelTier"], "openai/gpt-4o-mini")
        self.assertEqual(payload["shadowPreflight"]["state"], "would_block_hard_limit")
        self.assertFalse(payload["invoiceReconciliation"]["enforcementWired"])
        self.assertTrue(payload["invoiceReconciliation"]["advisoryOnly"])
        self.assertTrue(payload["safety"]["noExternalCalls"])

    def test_pilot_readiness_requires_explicit_owner_scope_before_enforcement(self) -> None:
        self._seed_budget_alert_policy()

        preflight = self.service.classify_pilot_readiness_preflight(
            owner_user_id=None,
            route_family="analysis",
            provider="openai",
            model_tier="openai/gpt-4o-mini",
            estimated_units=121,
            pilot_enforcement_enabled=True,
        )

        payload = preflight.to_dict()
        self.assertEqual(preflight.state, "pilot_scope_not_ready")
        self.assertTrue(preflight.would_block)
        self.assertTrue(preflight.advisory_only)
        self.assertFalse(preflight.request_blocked)
        self.assertFalse(preflight.live_enforcement)
        self.assertFalse(payload["pilot"]["scopeExplicit"])
        self.assertFalse(payload["pilot"]["ownerScoped"])
        self.assertEqual(payload["reasonCode"], "pilot_owner_scope_required")

    def test_pilot_readiness_flag_can_report_request_block_without_global_default(self) -> None:
        self._seed_budget_alert_policy()

        preflight = self.service.classify_pilot_readiness_preflight(
            owner_user_id="user-1",
            route_family="analysis",
            estimated_units=121,
            pilot_enforcement_enabled=True,
            pilot_route_families=("analysis",),
        )

        self.assertEqual(preflight.state, "pilot_would_enforce_block")
        self.assertTrue(preflight.would_block)
        self.assertFalse(preflight.advisory_only)
        self.assertTrue(preflight.request_blocked)
        self.assertTrue(preflight.live_enforcement)

        disabled_default = QuotaPolicyService(db=self.db)
        self.assertFalse(disabled_default.enforcement_enabled)

    def test_pilot_readiness_sanitizes_scope_context(self) -> None:
        preflight = self.service.classify_pilot_readiness_preflight(
            owner_user_id="owner-token-should-redact",
            route_family="analysis",
            provider="openai?api_key=must-not-leak",
            model_tier="model-with-secret",
            estimated_units=10,
        )

        payload_text = str(preflight.to_dict()).lower()
        self.assertNotIn("must-not-leak", payload_text)
        self.assertNotIn("api_key", payload_text)
        self.assertNotIn("token-should-redact", payload_text)
        self.assertEqual(preflight.to_dict()["scope"]["provider"], "redacted")
        self.assertEqual(preflight.to_dict()["scope"]["modelTier"], "redacted")

    def test_token_cap_exceeded(self) -> None:
        self.db.upsert_quota_policy(
            policy_key="route-token-cap",
            scope_type="route",
            route_family="analysis",
            token_cap=1000,
        )

        result = self.service.reserve_quota(
            owner_user_id="user-1",
            route_family="analysis",
            token_estimate=1001,
        )

        self.assertFalse(result.allowed)
        self.assertEqual(result.reason_code, "token_cap_exceeded")

    def test_route_request_cap_exceeded(self) -> None:
        self.db.upsert_quota_policy(
            policy_key="route-cap",
            scope_type="route",
            route_family="analysis",
            request_cap=1,
        )

        first = self.service.reserve_quota(owner_user_id="user-1", route_family="analysis")
        second = self.service.reserve_quota(owner_user_id="user-1", route_family="analysis")

        self.assertTrue(first.allowed)
        self.assertFalse(second.allowed)
        self.assertEqual(second.reason_code, "route_cap_exceeded")

    def test_reservation_create_consume(self) -> None:
        result = self.service.reserve_quota(owner_user_id="user-1", route_family="analysis")

        consumed = self.service.consume_reservation(
            reservation_id=result.reservation_id,
            actual_units=max(1, result.estimated_units - 1),
        )

        self.assertTrue(result.allowed)
        self.assertTrue(consumed.allowed)
        self.assertEqual(consumed.status, "consumed")
        with self.db.session_scope() as session:
            row = session.query(QuotaReservation).filter_by(reservation_id=result.reservation_id).one()
            self.assertEqual(row.status, "consumed")

    def test_reservation_create_release(self) -> None:
        result = self.service.reserve_quota(owner_user_id="user-1", route_family="analysis")

        released = self.service.release_reservation(reservation_id=result.reservation_id)

        self.assertTrue(result.allowed)
        self.assertTrue(released.allowed)
        self.assertEqual(released.status, "released")
        with self.db.session_scope() as session:
            row = session.query(QuotaReservation).filter_by(reservation_id=result.reservation_id).one()
            self.assertEqual(row.status, "released")

    def test_expired_reservation_cannot_be_consumed(self) -> None:
        result = self.service.reserve_quota(
            owner_user_id="user-1",
            route_family="analysis",
            expires_at=datetime.now() - timedelta(seconds=1),
        )

        consumed = self.service.consume_reservation(reservation_id=result.reservation_id)

        self.assertFalse(consumed.allowed)
        self.assertEqual(consumed.reason_code, "reservation_expired")
        self.assertEqual(consumed.status, "expired")

    def test_safe_rejection_reason_codes(self) -> None:
        allowed_codes = {
            "budget_exceeded",
            "quota_disabled",
            "global_kill_switch",
            "token_cap_exceeded",
            "route_cap_exceeded",
            "reservation_expired",
        }

        for code in allowed_codes:
            self.assertIn(code, QuotaPolicyService.SAFE_REJECTION_REASON_CODES)

    def test_metadata_sanitization_drops_secret_like_keys(self) -> None:
        result = self.service.reserve_quota(
            owner_user_id="user-1",
            route_family="analysis",
            metadata={
                "safe_label": "analysis",
                "api_key": "not-a-real-key",
                "nested": {"token": "not-a-real-token", "keep": "ok"},
            },
        )

        with self.db.session_scope() as session:
            row = session.query(QuotaReservation).filter_by(reservation_id=result.reservation_id).one()
            metadata = row.to_dict()["metadata"]

        self.assertEqual(metadata, {"safe_label": "analysis", "nested": {"keep": "ok"}})
        self.assertNotIn("not-a-real", str(metadata))

    def test_no_live_llm_or_provider_path_used(self) -> None:
        def forbidden(*_args, **_kwargs):
            raise AssertionError("live path should not be called by quota policy service")

        with (
            patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
            patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
            patch("src.services.scanner_ai_service.ScannerAiInterpretationService.interpret_shortlist", side_effect=forbidden),
        ):
            result = self.service.reserve_quota(owner_user_id="user-1", route_family="analysis")
            consumed = self.service.consume_reservation(reservation_id=result.reservation_id)

        self.assertTrue(result.allowed)
        self.assertTrue(consumed.allowed)


if __name__ == "__main__":
    unittest.main()
