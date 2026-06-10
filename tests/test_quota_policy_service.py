# -*- coding: utf-8 -*-
"""Synthetic tests for the WS2 quota policy foundation."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.multi_user import BOOTSTRAP_ADMIN_USER_ID
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

    def _reservation_window_counts(self, reservation_id: str):
        with self.db.session_scope() as session:
            reservation = session.query(QuotaReservation).filter_by(reservation_id=reservation_id).one()
            query = session.query(QuotaUsageWindow).filter(
                QuotaUsageWindow.route_family == reservation.route_family,
            )
            if reservation.owner_user_id is None:
                query = query.filter(QuotaUsageWindow.owner_user_id.is_(None))
            else:
                query = query.filter(
                    (QuotaUsageWindow.owner_user_id == reservation.owner_user_id)
                    | (QuotaUsageWindow.owner_user_id.is_(None))
                )
            if reservation.provider is None:
                query = query.filter(QuotaUsageWindow.provider.is_(None))
            else:
                query = query.filter(QuotaUsageWindow.provider == reservation.provider)
            if reservation.model_tier is None:
                query = query.filter(QuotaUsageWindow.model_tier.is_(None))
            else:
                query = query.filter(QuotaUsageWindow.model_tier == reservation.model_tier)
            rows = query.all()
            return sorted(
                [
                    (
                        row.owner_user_id,
                        row.window_type,
                        int(row.reserved_units or 0),
                        int(row.consumed_units or 0),
                    )
                    for row in rows
                ],
                key=lambda item: (item[0] or "", item[1]),
            )

    def _assert_reservation_window_counts(
        self,
        reservation_id: str,
        *,
        reserved_units: int,
        consumed_units: int,
    ) -> None:
        counts = self._reservation_window_counts(reservation_id)
        self.assertEqual(len(counts), 4)
        self.assertEqual(
            {(reserved, consumed) for _owner, _window, reserved, consumed in counts},
            {(reserved_units, consumed_units)},
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

    def test_quota_pilot_decision_contract_default_shape_is_advisory_only(self) -> None:
        self._seed_budget_alert_policy()

        decision = self.service.build_quota_pilot_decision_contract(
            owner_user_id="user-1",
            route_family="analysis",
            estimated_units=121,
            pilot_owner_user_ids=("user-1",),
        )

        payload = decision.to_dict()
        self.assertEqual(
            set(payload),
            {
                "routeKey",
                "ownerId",
                "estimateUnits",
                "pilotEnabled",
                "ownerInScope",
                "routeInScope",
                "pilotState",
                "reservationId",
                "providerModelContext",
                "allowReasonCode",
                "ownerEligibility",
                "requestBlocked",
                "blockReasonCode",
                "liveEnforcement",
            },
        )
        self.assertEqual(payload["routeKey"], "analysis")
        self.assertEqual(payload["ownerId"], "user-1")
        self.assertEqual(payload["estimateUnits"], 121)
        self.assertFalse(payload["pilotEnabled"])
        self.assertTrue(payload["ownerInScope"])
        self.assertTrue(payload["routeInScope"])
        self.assertEqual(payload["pilotState"], "pilot_disabled")
        self.assertIsNone(payload["reservationId"])
        self.assertEqual(
            payload["providerModelContext"],
            {"provider": None, "modelTier": None, "pricingStatus": "ok"},
        )
        self.assertEqual(payload["allowReasonCode"], "advisory_only_would_block_not_enforced")
        self.assertEqual(
            payload["ownerEligibility"],
            {
                "eligible": True,
                "reasonCode": None,
                "authEnabled": True,
                "authenticated": True,
                "transitional": False,
                "bootstrapAllowed": False,
            },
        )
        self.assertFalse(payload["requestBlocked"])
        self.assertEqual(payload["blockReasonCode"], "budget_hard_limit_exceeded")
        self.assertFalse(payload["liveEnforcement"])

    def test_quota_pilot_decision_contract_requires_authenticated_non_transitional_owner(self) -> None:
        self._seed_budget_alert_policy()

        decision = self.service.build_quota_pilot_decision_contract(
            owner_user_id=BOOTSTRAP_ADMIN_USER_ID,
            route_family="analysis",
            estimated_units=121,
            pilot_enabled=True,
            pilot_owner_user_ids=(BOOTSTRAP_ADMIN_USER_ID,),
            live_enforcement=True,
            owner_authenticated=False,
            owner_transitional=True,
            auth_enabled=False,
        )

        payload = decision.to_dict()
        self.assertFalse(payload["ownerInScope"])
        self.assertTrue(payload["routeInScope"])
        self.assertEqual(payload["pilotState"], "pilot_owner_not_eligible")
        self.assertEqual(payload["ownerEligibility"]["reasonCode"], "pilot_auth_disabled_bootstrap_not_eligible")
        self.assertFalse(payload["ownerEligibility"]["eligible"])
        self.assertFalse(payload["requestBlocked"])
        self.assertFalse(payload["liveEnforcement"])
        self.assertEqual(payload["allowReasonCode"], "pilot_owner_not_eligible_advisory_allow")
        self.assertEqual(payload["blockReasonCode"], "pilot_auth_disabled_bootstrap_not_eligible")

    def test_quota_pilot_decision_contract_missing_owner_is_not_ready_not_global_enforcement(self) -> None:
        self._seed_budget_alert_policy()

        decision = self.service.build_quota_pilot_decision_contract(
            owner_user_id=None,
            route_family="analysis",
            estimated_units=121,
            pilot_enabled=True,
            pilot_owner_user_ids=("user-1",),
            live_enforcement=True,
        )

        self.assertIsNone(decision.owner_id)
        self.assertFalse(decision.owner_in_scope)
        self.assertFalse(decision.request_blocked)
        self.assertEqual(decision.block_reason_code, "pilot_owner_missing")
        self.assertFalse(decision.to_dict()["ownerEligibility"]["eligible"])
        self.assertEqual(decision.to_dict()["ownerEligibility"]["reasonCode"], "pilot_owner_missing")
        self.assertFalse(decision.live_enforcement)

    def test_quota_pilot_decision_contract_unknown_pricing_and_zero_cost_stay_advisory(self) -> None:
        self._seed_budget_alert_policy()

        unknown_pricing = self.service.build_quota_pilot_decision_contract(
            owner_user_id="pilot-user",
            route_family="analysis",
            estimated_units=121,
            pricing_status="pricing_unknown",
            pilot_enabled=True,
            pilot_owner_user_ids=("pilot-user",),
            live_enforcement=True,
        )
        zero_cost = self.service.build_quota_pilot_decision_contract(
            owner_user_id="pilot-user",
            route_family="analysis",
            estimated_units=0,
            pricing_status="ok",
            pilot_enabled=True,
            pilot_owner_user_ids=("pilot-user",),
            live_enforcement=True,
        )

        self.assertTrue(unknown_pricing.owner_in_scope)
        self.assertFalse(unknown_pricing.request_blocked)
        self.assertEqual(unknown_pricing.block_reason_code, "pricing_unknown_advisory")
        self.assertEqual(unknown_pricing.to_dict()["allowReasonCode"], "pricing_unknown_advisory_allow")
        self.assertEqual(unknown_pricing.to_dict()["providerModelContext"]["pricingStatus"], "pricing_unknown")
        self.assertIsNone(unknown_pricing.to_dict()["reservationId"])
        self.assertFalse(unknown_pricing.live_enforcement)
        self.assertEqual(zero_cost.estimate_units, 0)
        self.assertTrue(zero_cost.owner_in_scope)
        self.assertFalse(zero_cost.request_blocked)
        self.assertEqual(zero_cost.block_reason_code, "zero_cost_advisory")
        self.assertEqual(zero_cost.to_dict()["allowReasonCode"], "zero_cost_advisory_allow")
        self.assertIsNone(zero_cost.to_dict()["reservationId"])
        self.assertFalse(zero_cost.live_enforcement)

    def test_quota_pilot_decision_contract_can_report_explicit_test_only_live_block(self) -> None:
        self._seed_budget_alert_policy()

        decision = self.service.build_quota_pilot_decision_contract(
            owner_user_id="pilot-user",
            route_family="analysis",
            estimated_units=121,
            pilot_enabled=True,
            pilot_owner_user_ids=("pilot-user",),
            live_enforcement=True,
        )

        self.assertTrue(decision.pilot_enabled)
        self.assertTrue(decision.owner_in_scope)
        self.assertTrue(decision.request_blocked)
        self.assertEqual(decision.block_reason_code, "budget_hard_limit_exceeded")
        self.assertTrue(decision.live_enforcement)

    def test_quota_pilot_decision_contract_is_read_only_and_not_analysis_route_wired(self) -> None:
        self._seed_budget_alert_policy()
        with self.db.session_scope() as session:
            before_reservations = session.query(QuotaReservation).count()
            before_windows = session.query(QuotaUsageWindow).count()

        decision = self.service.build_quota_pilot_decision_contract(
            owner_user_id="pilot-user",
            route_family="analysis",
            estimated_units=121,
            pilot_enabled=True,
            pilot_owner_user_ids=("pilot-user",),
            live_enforcement=True,
        )

        with self.db.session_scope() as session:
            after_reservations = session.query(QuotaReservation).count()
            after_windows = session.query(QuotaUsageWindow).count()
        route_source = (Path(__file__).resolve().parents[1] / "api/v1/endpoints/analysis.py").read_text()
        self.assertTrue(decision.request_blocked)
        self.assertEqual(after_reservations, before_reservations)
        self.assertEqual(after_windows, before_windows)
        self.assertNotIn("build_quota_pilot_decision_contract", route_source)
        self.assertNotIn("QuotaPilotDecisionContract", route_source)
        self.assertNotIn("reserve_quota(", route_source)

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
        self.assertFalse(payload["pilot"]["scopeExplicit"])
        self.assertEqual(payload["pilotState"], "pilot_advisory_would_block")
        self.assertTrue(payload["routeInScope"])
        self.assertIsNone(payload["reservationId"])
        self.assertEqual(
            payload["providerModelContext"],
            {
                "provider": "openai",
                "modelTier": "openai/gpt-4o-mini",
                "pricingStatus": "ok",
            },
        )
        self.assertEqual(payload["allowReasonCode"], "advisory_only_would_block_not_enforced")
        self.assertTrue(payload["ownerEligibility"]["eligible"])
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
        self.assertFalse(payload["ownerEligibility"]["eligible"])
        self.assertEqual(payload["ownerEligibility"]["reasonCode"], "pilot_owner_missing")
        self.assertEqual(payload["reasonCode"], "pilot_owner_scope_required")

    def test_pilot_readiness_rejects_auth_disabled_transitional_bootstrap_owner_scope(self) -> None:
        self._seed_budget_alert_policy()

        preflight = self.service.classify_pilot_readiness_preflight(
            owner_user_id=BOOTSTRAP_ADMIN_USER_ID,
            route_family="analysis",
            estimated_units=121,
            pilot_enforcement_enabled=True,
            pilot_owner_user_ids=(BOOTSTRAP_ADMIN_USER_ID,),
            pilot_route_families=("analysis",),
            owner_authenticated=False,
            owner_transitional=True,
            auth_enabled=False,
        )

        payload = preflight.to_dict()
        self.assertEqual(preflight.state, "pilot_owner_not_eligible")
        self.assertEqual(preflight.reason_code, "pilot_auth_disabled_bootstrap_not_eligible")
        self.assertTrue(preflight.would_block)
        self.assertTrue(preflight.advisory_only)
        self.assertFalse(preflight.request_blocked)
        self.assertFalse(preflight.live_enforcement)
        self.assertTrue(payload["routeInScope"])
        self.assertFalse(payload["pilot"]["scopeExplicit"])
        self.assertFalse(payload["pilot"]["ownerEligible"])
        self.assertEqual(payload["ownerEligibility"]["reasonCode"], "pilot_auth_disabled_bootstrap_not_eligible")
        self.assertEqual(payload["allowReasonCode"], "pilot_owner_not_eligible_advisory_allow")

    def test_pilot_readiness_requires_explicit_owner_allowlist_for_enabled_pilot(self) -> None:
        self._seed_budget_alert_policy()

        preflight = self.service.classify_pilot_readiness_preflight(
            owner_user_id="user-1",
            route_family="analysis",
            provider="openai",
            model_tier="openai/gpt-4o-mini",
            estimated_units=121,
            pilot_enforcement_enabled=True,
        )

        self.assertEqual(preflight.state, "pilot_scope_not_ready")
        self.assertTrue(preflight.would_block)
        self.assertTrue(preflight.advisory_only)
        self.assertFalse(preflight.request_blocked)
        self.assertFalse(preflight.live_enforcement)
        payload = preflight.to_dict()
        self.assertFalse(payload["pilot"]["scopeExplicit"])
        self.assertTrue(payload["pilot"]["ownerScoped"])
        self.assertEqual(payload["reasonCode"], "pilot_owner_scope_required")

    def test_pilot_readiness_out_of_scope_owner_remains_advisory_only(self) -> None:
        self._seed_budget_alert_policy()

        preflight = self.service.classify_pilot_readiness_preflight(
            owner_user_id="user-2",
            route_family="analysis",
            estimated_units=121,
            pilot_enforcement_enabled=True,
            pilot_owner_user_ids=("user-1",),
            pilot_route_families=("analysis",),
        )

        self.assertEqual(preflight.state, "pilot_owner_out_of_scope")
        self.assertTrue(preflight.would_block)
        self.assertTrue(preflight.advisory_only)
        self.assertFalse(preflight.request_blocked)
        self.assertFalse(preflight.live_enforcement)
        self.assertEqual(preflight.reason_code, "pilot_owner_out_of_scope")

    def test_pilot_readiness_flag_can_report_request_block_without_global_default(self) -> None:
        self._seed_budget_alert_policy()

        preflight = self.service.classify_pilot_readiness_preflight(
            owner_user_id="user-1",
            route_family="analysis",
            estimated_units=121,
            pilot_enforcement_enabled=True,
            pilot_owner_user_ids=("user-1",),
            pilot_route_families=("analysis",),
        )

        self.assertEqual(preflight.state, "pilot_would_enforce_block")
        self.assertTrue(preflight.would_block)
        self.assertFalse(preflight.advisory_only)
        self.assertTrue(preflight.request_blocked)
        self.assertTrue(preflight.live_enforcement)

        disabled_default = QuotaPolicyService(db=self.db)
        self.assertFalse(disabled_default.enforcement_enabled)

    def test_pilot_acceptance_requires_enabled_mode_and_owner_allowlist(self) -> None:
        self._seed_budget_alert_policy()

        cases = (
            (
                "allowlist_without_enabled_mode",
                False,
                ("pilot-user",),
                "pilot-user",
                "pilot_advisory_would_block",
                True,
                False,
                False,
            ),
            (
                "enabled_without_allowlist",
                True,
                (),
                "pilot-user",
                "pilot_scope_not_ready",
                True,
                False,
                False,
            ),
            (
                "enabled_out_of_scope",
                True,
                ("pilot-user",),
                "other-user",
                "pilot_owner_out_of_scope",
                True,
                False,
                False,
            ),
            (
                "enabled_in_scope",
                True,
                ("pilot-user",),
                "pilot-user",
                "pilot_would_enforce_block",
                False,
                True,
                True,
            ),
        )
        for name, enabled, owners, owner, state, advisory_only, request_blocked, live_enforcement in cases:
            with self.subTest(name=name):
                preflight = self.service.classify_pilot_readiness_preflight(
                    owner_user_id=owner,
                    route_family="analysis",
                    estimated_units=121,
                    pilot_enforcement_enabled=enabled,
                    pilot_owner_user_ids=owners,
                    pilot_route_families=("analysis",),
                )

                self.assertEqual(preflight.state, state)
                self.assertTrue(preflight.would_block)
                self.assertEqual(preflight.advisory_only, advisory_only)
                self.assertEqual(preflight.request_blocked, request_blocked)
                self.assertEqual(preflight.live_enforcement, live_enforcement)
                operator_review = preflight.to_dict()["operatorReview"]
                self.assertEqual(operator_review["statusLabel"], state)
                self.assertEqual(operator_review["requiresExplicitOwnerAllowlist"], True)
                self.assertFalse(operator_review["globalEnforcementChanged"])
                if request_blocked:
                    self.assertEqual(operator_review["decisionLabel"], "pilot_enforced_would_block")
                    self.assertEqual(
                        operator_review["rollbackLabel"],
                        "remove_owner_from_pilot_allowlist_or_disable_pilot_mode",
                    )
                else:
                    self.assertEqual(operator_review["decisionLabel"], "advisory_only")
                    self.assertEqual(operator_review["rollbackLabel"], "no_runtime_change_to_rollback")

    def test_pilot_readiness_marks_invoice_reconciliation_as_non_enforcement_input(self) -> None:
        self._seed_budget_alert_policy()

        preflight = self.service.classify_pilot_readiness_preflight(
            owner_user_id="pilot-user",
            route_family="analysis",
            estimated_units=121,
            pilot_enforcement_enabled=True,
            pilot_owner_user_ids=("pilot-user",),
            pilot_route_families=("analysis",),
        )

        invoice = preflight.to_dict()["invoiceReconciliation"]
        self.assertTrue(invoice["advisoryOnly"])
        self.assertFalse(invoice["enforcementInput"])
        self.assertFalse(invoice["enforcementWired"])
        self.assertFalse(invoice["liveInvoiceIngestion"])

    def test_pilot_enforced_budget_alert_notification_intent_is_sanitized_dry_run_only(self) -> None:
        self._seed_budget_alert_policy()

        preflight = self.service.classify_pilot_readiness_preflight(
            owner_user_id="pilot-session-should-redact",
            route_family="analysis",
            provider="openai?api_key=must-not-leak&token=raw-token&password=raw-password",
            model_tier="model-with-secret-cookie-session-provider-credential",
            estimated_units=121,
            pilot_enforcement_enabled=True,
            pilot_owner_user_ids=("pilot-session-should-redact",),
            pilot_route_families=("analysis",),
        )
        intent = self.service.build_budget_alert_notification_intent(preflight)

        self.assertEqual(intent["state"], "dry_run_intent")
        self.assertTrue(intent["alertDeliveryIntent"])
        self.assertEqual(intent["eventType"], "cost.quota_budget_alert")
        self.assertEqual(intent["deliveryStatus"], "dry_run_disabled")
        self.assertTrue(intent["dryRun"])
        self.assertFalse(intent["outboundAttempted"])
        self.assertFalse(intent["liveOutbound"])
        self.assertEqual(intent["scope"]["ownerUserId"], "redacted")
        self.assertEqual(intent["scope"]["provider"], "redacted")
        self.assertEqual(intent["scope"]["modelTier"], "redacted")
        self.assertEqual(intent["budgetContext"]["hardLimitUnits"], 120)
        self.assertEqual(intent["budgetContext"]["projectedUnits"], 121)
        self.assertEqual(intent["budgetContext"]["budgetState"], "over_hard_limit")
        self.assertTrue(intent["invoiceReconciliation"]["advisoryOnly"])
        self.assertFalse(intent["invoiceReconciliation"]["enforcementInput"])
        self.assertFalse(intent["invoiceReconciliation"]["liveInvoiceIngestion"])
        self.assertTrue(intent["safety"]["noExternalCalls"])
        self.assertEqual(intent["operatorReview"]["statusLabel"], "dry_run_intent")
        self.assertEqual(intent["operatorReview"]["deliveryStatusLabel"], "dry_run_disabled")
        self.assertEqual(intent["operatorReview"]["rollbackLabel"], "disable_pilot_mode_before_delivery_wiring")
        self.assertFalse(intent["operatorReview"]["realOutboundNotification"])
        self.assertFalse(intent["operatorReview"]["globalEnforcementChanged"])
        text = str(intent).lower()
        self.assertNotIn("must-not-leak", text)
        self.assertNotIn("raw-token", text)
        self.assertNotIn("raw-password", text)
        self.assertNotIn("api_key", text)
        self.assertNotIn("password", text)
        self.assertNotIn("session-should-redact", text)
        self.assertNotIn("cookie", text)
        self.assertNotIn("provider-credential", text)
        self.assertNotIn("model-with-secret", text)

    def test_advisory_only_budget_alert_notification_intent_is_suppressed(self) -> None:
        self._seed_budget_alert_policy()

        preflight = self.service.classify_pilot_readiness_preflight(
            owner_user_id="other-user",
            route_family="analysis",
            estimated_units=121,
            pilot_enforcement_enabled=True,
            pilot_owner_user_ids=("pilot-user",),
            pilot_route_families=("analysis",),
        )
        intent = self.service.build_budget_alert_notification_intent(preflight)

        self.assertEqual(preflight.state, "pilot_owner_out_of_scope")
        self.assertEqual(intent["state"], "suppressed_advisory_only")
        self.assertFalse(intent["alertDeliveryIntent"])
        self.assertEqual(intent["deliveryStatus"], "suppressed_advisory_only")
        self.assertTrue(intent["dryRun"])
        self.assertFalse(intent["outboundAttempted"])
        self.assertFalse(intent["liveOutbound"])
        self.assertTrue(intent["invoiceReconciliation"]["advisoryOnly"])
        self.assertFalse(intent["invoiceReconciliation"]["enforcementInput"])
        self.assertEqual(intent["operatorReview"]["statusLabel"], "suppressed_advisory_only")
        self.assertEqual(intent["operatorReview"]["deliveryStatusLabel"], "suppressed_advisory_only")
        self.assertEqual(intent["operatorReview"]["rollbackLabel"], "no_runtime_change_to_rollback")
        self.assertFalse(intent["operatorReview"]["realOutboundNotification"])

    def test_budget_alert_notification_intent_does_not_enable_default_quota_enforcement(self) -> None:
        self._seed_budget_alert_policy()
        disabled_default = QuotaPolicyService(db=self.db)

        preflight = disabled_default.classify_pilot_readiness_preflight(
            owner_user_id="pilot-user",
            route_family="analysis",
            estimated_units=121,
            pilot_enforcement_enabled=True,
            pilot_owner_user_ids=("pilot-user",),
            pilot_route_families=("analysis",),
        )
        intent = disabled_default.build_budget_alert_notification_intent(preflight)

        self.assertFalse(disabled_default.enforcement_enabled)
        self.assertEqual(intent["deliveryStatus"], "dry_run_disabled")
        self.assertFalse(intent["runtimeWiringChanged"])
        self.assertFalse(intent["liveOutbound"])

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

    def test_double_consume_terminal_idempotent_does_not_double_move_units(self) -> None:
        result = self.service.reserve_quota(
            owner_user_id="user-1",
            route_family="analysis",
            estimated_units=10,
        )

        first = self.service.consume_reservation(reservation_id=result.reservation_id, actual_units=7)
        second = self.service.consume_reservation(reservation_id=result.reservation_id, actual_units=9)

        self.assertTrue(first.allowed)
        self.assertEqual(first.status, "consumed")
        self.assertFalse(second.allowed)
        self.assertEqual(second.status, "consumed")
        self.assertEqual(second.reason_code, "reservation_already_terminal")
        self._assert_reservation_window_counts(
            result.reservation_id,
            reserved_units=0,
            consumed_units=7,
        )
        with self.db.session_scope() as session:
            row = session.query(QuotaReservation).filter_by(reservation_id=result.reservation_id).one()
            self.assertEqual(row.status, "consumed")
            self.assertIsNone(row.reason_code)

    def test_reservation_create_release(self) -> None:
        result = self.service.reserve_quota(owner_user_id="user-1", route_family="analysis")

        released = self.service.release_reservation(reservation_id=result.reservation_id)

        self.assertTrue(result.allowed)
        self.assertTrue(released.allowed)
        self.assertEqual(released.status, "released")
        with self.db.session_scope() as session:
            row = session.query(QuotaReservation).filter_by(reservation_id=result.reservation_id).one()
            self.assertEqual(row.status, "released")

    def test_double_release_terminal_idempotent_does_not_double_move_units(self) -> None:
        result = self.service.reserve_quota(
            owner_user_id="user-1",
            route_family="analysis",
            estimated_units=10,
        )

        first = self.service.release_reservation(reservation_id=result.reservation_id)
        second = self.service.release_reservation(reservation_id=result.reservation_id)

        self.assertTrue(first.allowed)
        self.assertEqual(first.status, "released")
        self.assertFalse(second.allowed)
        self.assertEqual(second.status, "released")
        self.assertEqual(second.reason_code, "reservation_already_terminal")
        self._assert_reservation_window_counts(
            result.reservation_id,
            reserved_units=0,
            consumed_units=0,
        )
        with self.db.session_scope() as session:
            row = session.query(QuotaReservation).filter_by(reservation_id=result.reservation_id).one()
            self.assertEqual(row.status, "released")
            self.assertIsNone(row.reason_code)

    def test_consume_after_release_keeps_released_terminal_state(self) -> None:
        result = self.service.reserve_quota(
            owner_user_id="user-1",
            route_family="analysis",
            estimated_units=10,
        )

        released = self.service.release_reservation(reservation_id=result.reservation_id)
        consumed = self.service.consume_reservation(reservation_id=result.reservation_id, actual_units=8)

        self.assertTrue(released.allowed)
        self.assertFalse(consumed.allowed)
        self.assertEqual(consumed.status, "released")
        self.assertEqual(consumed.reason_code, "reservation_already_terminal")
        self._assert_reservation_window_counts(
            result.reservation_id,
            reserved_units=0,
            consumed_units=0,
        )
        with self.db.session_scope() as session:
            row = session.query(QuotaReservation).filter_by(reservation_id=result.reservation_id).one()
            self.assertEqual(row.status, "released")

    def test_release_after_consume_keeps_consumed_terminal_state(self) -> None:
        result = self.service.reserve_quota(
            owner_user_id="user-1",
            route_family="analysis",
            estimated_units=10,
        )

        consumed = self.service.consume_reservation(reservation_id=result.reservation_id, actual_units=8)
        released = self.service.release_reservation(reservation_id=result.reservation_id)

        self.assertTrue(consumed.allowed)
        self.assertFalse(released.allowed)
        self.assertEqual(released.status, "consumed")
        self.assertEqual(released.reason_code, "reservation_already_terminal")
        self._assert_reservation_window_counts(
            result.reservation_id,
            reserved_units=0,
            consumed_units=8,
        )
        with self.db.session_scope() as session:
            row = session.query(QuotaReservation).filter_by(reservation_id=result.reservation_id).one()
            self.assertEqual(row.status, "consumed")

    def test_expired_reservation_cannot_be_consumed(self) -> None:
        result = self.service.reserve_quota(
            owner_user_id="user-1",
            route_family="analysis",
            estimated_units=10,
            expires_at=datetime.now() - timedelta(seconds=1),
        )

        consumed = self.service.consume_reservation(reservation_id=result.reservation_id)

        self.assertFalse(consumed.allowed)
        self.assertEqual(consumed.reason_code, "reservation_expired")
        self.assertEqual(consumed.status, "expired")
        self._assert_reservation_window_counts(
            result.reservation_id,
            reserved_units=0,
            consumed_units=0,
        )

    def test_releasing_expired_reserved_reservation_reclaims_capacity_once(self) -> None:
        result = self.service.reserve_quota(
            owner_user_id="user-1",
            route_family="analysis",
            estimated_units=10,
            expires_at=datetime.now() - timedelta(seconds=1),
        )

        first = self.service.release_reservation(reservation_id=result.reservation_id)
        second = self.service.release_reservation(reservation_id=result.reservation_id)

        self.assertFalse(first.allowed)
        self.assertEqual(first.status, "expired")
        self.assertEqual(first.reason_code, "reservation_expired")
        self.assertFalse(second.allowed)
        self.assertEqual(second.status, "expired")
        self.assertEqual(second.reason_code, "reservation_expired")
        self._assert_reservation_window_counts(
            result.reservation_id,
            reserved_units=0,
            consumed_units=0,
        )
        with self.db.session_scope() as session:
            row = session.query(QuotaReservation).filter_by(reservation_id=result.reservation_id).one()
            self.assertEqual(row.status, "expired")
            self.assertEqual(row.reason_code, "reservation_expired")

    def test_missing_reservation_returns_explicit_safe_code(self) -> None:
        consumed = self.service.consume_reservation(reservation_id="qres_missing")
        released = self.service.release_reservation(reservation_id="")

        self.assertFalse(consumed.allowed)
        self.assertEqual(consumed.status, "missing")
        self.assertEqual(consumed.reason_code, "reservation_missing")
        self.assertEqual(consumed.reservation_id, "qres_missing")
        self.assertFalse(released.allowed)
        self.assertEqual(released.status, "missing")
        self.assertEqual(released.reason_code, "reservation_missing")
        self.assertIsNone(released.reservation_id)

    def test_safe_rejection_reason_codes(self) -> None:
        allowed_codes = {
            "budget_exceeded",
            "quota_disabled",
            "global_kill_switch",
            "token_cap_exceeded",
            "route_cap_exceeded",
            "reservation_expired",
            "reservation_already_terminal",
            "reservation_missing",
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
