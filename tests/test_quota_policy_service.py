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
from src.storage import DatabaseManager, QuotaReservation


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
