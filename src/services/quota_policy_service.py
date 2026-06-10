# -*- coding: utf-8 -*-
"""Synthetic quota policy foundation for future LLM/API enforcement."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from src.storage import DatabaseManager, QuotaReservation, QuotaUsageWindow


@dataclass(frozen=True)
class QuotaDecision:
    """Result of a synthetic quota policy operation."""

    allowed: bool
    status: str
    reason_code: Optional[str] = None
    reservation_id: Optional[str] = None
    estimated_units: int = 0


@dataclass(frozen=True)
class BudgetAlertDryRun:
    """Diagnostic budget alert classification for future UI/API warnings."""

    state: str
    severity: str
    reason_code: Optional[str]
    would_block: bool
    owner_user_id: Optional[str]
    route_family: str
    window_type: str
    used_units: int
    estimated_units: int
    projected_units: int
    soft_limit_units: Optional[int]
    hard_limit_units: Optional[int]
    pricing_status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "severity": self.severity,
            "reasonCode": self.reason_code,
            "wouldBlock": self.would_block,
            "ownerUserId": self.owner_user_id,
            "routeFamily": self.route_family,
            "windowType": self.window_type,
            "usedUnits": self.used_units,
            "estimatedUnits": self.estimated_units,
            "projectedUnits": self.projected_units,
            "softLimitUnits": self.soft_limit_units,
            "hardLimitUnits": self.hard_limit_units,
            "pricingStatus": self.pricing_status,
            "liveEnforcement": False,
        }


@dataclass(frozen=True)
class QuotaShadowPreflight:
    """Advisory-only quota enforcement classification for launch preflight."""

    state: str
    reason_code: Optional[str]
    would_block: bool
    owner_user_id: Optional[str]
    route_family: str
    pricing_status: str
    budget_alert: BudgetAlertDryRun

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "reasonCode": self.reason_code,
            "wouldBlock": self.would_block,
            "advisoryOnly": True,
            "requestBlocked": False,
            "liveEnforcement": False,
            "ownerUserId": self.owner_user_id,
            "routeFamily": self.route_family,
            "pricingStatus": self.pricing_status,
            "ownerIsolation": {
                "ownerScoped": self.owner_user_id is not None,
                "otherOwnersExcluded": True,
            },
            "usedUnits": self.budget_alert.used_units,
            "estimatedUnits": self.budget_alert.estimated_units,
            "projectedUnits": self.budget_alert.projected_units,
            "softLimitUnits": self.budget_alert.soft_limit_units,
            "hardLimitUnits": self.budget_alert.hard_limit_units,
        }


@dataclass(frozen=True)
class QuotaPilotReadinessPreflight:
    """Pilot-readiness report for quota enforcement without changing runtime wiring."""

    state: str
    reason_code: Optional[str]
    would_block: bool
    advisory_only: bool
    request_blocked: bool
    live_enforcement: bool
    pilot_enforcement_enabled: bool
    pilot_scope_explicit: bool
    owner_scoped: bool
    owner_user_id: Optional[str]
    route_family: str
    provider: Optional[str]
    model_tier: Optional[str]
    route_in_scope: bool
    reservation_id: Optional[str]
    provider_model_context: Dict[str, Optional[str]]
    allow_reason_code: Optional[str]
    owner_eligible: bool
    owner_eligibility_reason_code: Optional[str]
    owner_auth_enabled: bool
    owner_authenticated: bool
    owner_transitional: bool
    shadow_preflight: QuotaShadowPreflight

    def to_dict(self) -> Dict[str, Any]:
        shadow_payload = self.shadow_preflight.to_dict()
        shadow_payload["ownerUserId"] = self.owner_user_id
        return {
            "state": self.state,
            "pilotState": self.state,
            "reasonCode": self.reason_code,
            "wouldBlock": self.would_block,
            "advisoryOnly": self.advisory_only,
            "requestBlocked": self.request_blocked,
            "liveEnforcement": self.live_enforcement,
            "routeInScope": self.route_in_scope,
            "reservationId": self.reservation_id,
            "providerModelContext": self.provider_model_context,
            "allowReasonCode": self.allow_reason_code,
            "pilot": {
                "enforcementEnabled": self.pilot_enforcement_enabled,
                "scopeExplicit": self.pilot_scope_explicit,
                "ownerScoped": self.owner_scoped,
                "ownerEligible": self.owner_eligible,
                "routeInScope": self.route_in_scope,
            },
            "scope": {
                "ownerUserId": self.owner_user_id,
                "routeFamily": self.route_family,
                "provider": self.provider,
                "modelTier": self.model_tier,
            },
            "ownerEligibility": {
                "eligible": self.owner_eligible,
                "reasonCode": self.owner_eligibility_reason_code,
                "authEnabled": self.owner_auth_enabled,
                "authenticated": self.owner_authenticated,
                "transitional": self.owner_transitional,
                "bootstrapAllowed": False,
            },
            "shadowPreflight": shadow_payload,
            "invoiceReconciliation": {
                "advisoryOnly": True,
                "enforcementInput": False,
                "enforcementWired": False,
                "liveInvoiceIngestion": False,
            },
            "safety": {
                "diagnosticOnly": True,
                "noExternalCalls": True,
                "liveProviderCalls": False,
                "liveLlmCalls": False,
                "runtimeWiringChanged": False,
            },
            "operatorReview": {
                "statusLabel": self.state,
                "decisionLabel": "pilot_enforced_would_block" if self.request_blocked else "advisory_only",
                "rollbackLabel": (
                    "remove_owner_from_pilot_allowlist_or_disable_pilot_mode"
                    if self.request_blocked
                    else "no_runtime_change_to_rollback"
                ),
                "requiresExplicitOwnerAllowlist": True,
                "globalEnforcementChanged": False,
            },
        }


@dataclass(frozen=True)
class QuotaPilotDecisionContract:
    """Narrow decision contract for a future owner-allowlisted quota pilot."""

    route_key: str
    owner_id: Optional[str]
    estimate_units: int
    pilot_enabled: bool
    owner_in_scope: bool
    route_in_scope: bool
    pilot_state: str
    reservation_id: Optional[str]
    provider_model_context: Dict[str, Optional[str]]
    allow_reason_code: Optional[str]
    owner_eligible: bool
    owner_eligibility_reason_code: Optional[str]
    owner_auth_enabled: bool
    owner_authenticated: bool
    owner_transitional: bool
    request_blocked: bool
    block_reason_code: Optional[str]
    live_enforcement: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "routeKey": self.route_key,
            "ownerId": self.owner_id,
            "estimateUnits": self.estimate_units,
            "pilotEnabled": self.pilot_enabled,
            "ownerInScope": self.owner_in_scope,
            "routeInScope": self.route_in_scope,
            "pilotState": self.pilot_state,
            "reservationId": self.reservation_id,
            "providerModelContext": self.provider_model_context,
            "allowReasonCode": self.allow_reason_code,
            "ownerEligibility": {
                "eligible": self.owner_eligible,
                "reasonCode": self.owner_eligibility_reason_code,
                "authEnabled": self.owner_auth_enabled,
                "authenticated": self.owner_authenticated,
                "transitional": self.owner_transitional,
                "bootstrapAllowed": False,
            },
            "requestBlocked": self.request_blocked,
            "blockReasonCode": self.block_reason_code,
            "liveEnforcement": self.live_enforcement,
        }


class QuotaPolicyService:
    """Budget/quota policy checks that are not wired into live providers yet."""

    SENSITIVE_CONTEXT_TOKENS = (
        "api_key",
        "apikey",
        "token",
        "secret",
        "cookie",
        "password",
        "credential",
        "session",
    )

    SAFE_REJECTION_REASON_CODES = {
        "budget_exceeded",
        "quota_disabled",
        "global_kill_switch",
        "token_cap_exceeded",
        "route_cap_exceeded",
        "reservation_expired",
        "reservation_already_terminal",
        "reservation_missing",
    }

    TERMINAL_RESERVATION_STATUSES = {"consumed", "released", "expired"}

    ROUTE_WEIGHTS = {
        "guest_preview": 1,
        "analysis": 5,
        "async_analysis": 6,
        "scanner_ai": 6,
        "agent_chat": 4,
        "options_scenario": 2,
        "provider_market": 2,
    }

    def __init__(
        self,
        *,
        db: Optional[DatabaseManager] = None,
        enforcement_enabled: bool = False,
        global_kill_switch: bool = False,
    ) -> None:
        self.db = db or DatabaseManager.get_instance()
        self.enforcement_enabled = bool(enforcement_enabled)
        self.global_kill_switch = bool(global_kill_switch)

    def classify_route_family(self, route_family: Optional[str]) -> str:
        normalized = str(route_family or "").strip().lower().replace("-", "_")
        return normalized if normalized in self.ROUTE_WEIGHTS else "analysis"

    def route_weight(self, route_family: Optional[str]) -> int:
        return int(self.ROUTE_WEIGHTS[self.classify_route_family(route_family)])

    def estimate_budget_units(self, *, route_family: Optional[str], token_estimate: Optional[int] = None) -> int:
        token_units = max(1, math.ceil(max(0, int(token_estimate or 0)) / 1000))
        return self.route_weight(route_family) * token_units

    def evaluate_quota(
        self,
        *,
        owner_user_id: Optional[str],
        route_family: str,
        provider: Optional[str] = None,
        model_tier: Optional[str] = None,
        token_estimate: Optional[int] = None,
        estimated_units: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> QuotaDecision:
        """Evaluate quota policy without creating a reservation."""
        route_key = self.classify_route_family(route_family)
        units = max(
            1,
            int(estimated_units)
            if estimated_units is not None
            else self.estimate_budget_units(route_family=route_key, token_estimate=token_estimate),
        )
        if not self.enforcement_enabled:
            return QuotaDecision(allowed=True, status="disabled", estimated_units=units)

        current_time = now or datetime.now()
        provider_key = self._normalize_optional(provider, lowercase=True)
        model_key = self._normalize_optional(model_tier, lowercase=True)
        policies = list(self._matching_policies(route_key, provider_key, model_key))

        if self.global_kill_switch or self._policy_kill_switch_enabled(policies):
            return self._reject("global_kill_switch", estimated_units=units)
        if any(not bool(policy.get("enabled", True)) for policy in policies):
            return self._reject("quota_disabled", estimated_units=units)

        token_cap = self._minimum_cap(policies, "token_cap")
        if token_cap is not None and int(token_estimate or 0) > token_cap:
            return self._reject("token_cap_exceeded", estimated_units=units)

        with self.db.session_scope() as session:
            daily_start, _daily_end = self._window_bounds("daily", current_time)
            monthly_start, _monthly_end = self._window_bounds("monthly", current_time)

            if self._budget_exceeded(
                session=session,
                owner_user_id=owner_user_id,
                window_type="daily",
                window_start=daily_start,
                budget_units=self._minimum_cap(policies, "daily_budget_units"),
                estimate_units=units,
            ):
                return self._reject("budget_exceeded", estimated_units=units)
            if self._budget_exceeded(
                session=session,
                owner_user_id=owner_user_id,
                window_type="monthly",
                window_start=monthly_start,
                budget_units=self._minimum_cap(policies, "monthly_budget_units"),
                estimate_units=units,
            ):
                return self._reject("budget_exceeded", estimated_units=units)

            route_cap = self._minimum_cap(
                [policy for policy in policies if policy.get("scope_type") == "route"],
                "request_cap",
            )
            if route_cap is not None:
                route_requests = self._request_count(
                    session=session,
                    owner_user_id=None,
                    route_family=route_key,
                    window_type="daily",
                    window_start=daily_start,
                )
                if route_requests + 1 > route_cap:
                    return self._reject("route_cap_exceeded", estimated_units=units)

        return QuotaDecision(allowed=True, status="allowed", estimated_units=units)

    def classify_budget_alert(
        self,
        *,
        owner_user_id: Optional[str],
        route_family: str,
        provider: Optional[str] = None,
        model_tier: Optional[str] = None,
        token_estimate: Optional[int] = None,
        estimated_units: Optional[int] = None,
        pricing_status: str = "ok",
        now: Optional[datetime] = None,
    ) -> BudgetAlertDryRun:
        """Classify budget state for dry-run diagnostics without enforcing it."""
        route_key = self.classify_route_family(route_family)
        units = max(
            1,
            int(estimated_units)
            if estimated_units is not None
            else self.estimate_budget_units(route_family=route_key, token_estimate=token_estimate),
        )
        pricing_key = str(pricing_status or "pricing_unknown").strip().lower() or "pricing_unknown"
        if pricing_key != "ok":
            return BudgetAlertDryRun(
                state="pricing_unknown_warning",
                severity="warning",
                reason_code="pricing_policy_unknown",
                would_block=False,
                owner_user_id=self._normalize_optional(owner_user_id),
                route_family=route_key,
                window_type="daily",
                used_units=0,
                estimated_units=units,
                projected_units=units,
                soft_limit_units=None,
                hard_limit_units=None,
                pricing_status=pricing_key,
            )

        current_time = now or datetime.now()
        provider_key = self._normalize_optional(provider, lowercase=True)
        model_key = self._normalize_optional(model_tier, lowercase=True)
        policies = list(self._matching_policies(route_key, provider_key, model_key))
        hard_limit = self._minimum_cap(policies, "daily_budget_units")
        soft_limit = self._minimum_soft_limit(policies)
        if soft_limit is None and hard_limit is not None:
            soft_limit = max(1, int(hard_limit * 0.8))

        daily_start, _daily_end = self._window_bounds("daily", current_time)
        with self.db.session_scope() as session:
            used_units = self._used_budget_units(
                session=session,
                owner_user_id=owner_user_id,
                window_type="daily",
                window_start=daily_start,
            )

        projected = used_units + units
        state = "under_budget"
        severity = "info"
        reason_code = None
        if hard_limit is not None and projected > hard_limit:
            state = "over_hard_limit"
            severity = "warning"
            reason_code = "budget_hard_limit_exceeded"
        elif soft_limit is not None and projected >= soft_limit:
            state = "over_soft_limit"
            severity = "warning"
            reason_code = "budget_soft_limit_exceeded"
        elif soft_limit is not None and projected >= max(1, int(soft_limit * 0.8)):
            state = "near_soft_limit"
            severity = "warning"
            reason_code = "budget_near_soft_limit"

        return BudgetAlertDryRun(
            state=state,
            severity=severity,
            reason_code=reason_code,
            would_block=False,
            owner_user_id=self._normalize_optional(owner_user_id),
            route_family=route_key,
            window_type="daily",
            used_units=used_units,
            estimated_units=units,
            projected_units=projected,
            soft_limit_units=soft_limit,
            hard_limit_units=hard_limit,
            pricing_status=pricing_key,
        )

    def classify_shadow_preflight(
        self,
        *,
        owner_user_id: Optional[str],
        route_family: str,
        provider: Optional[str] = None,
        model_tier: Optional[str] = None,
        token_estimate: Optional[int] = None,
        estimated_units: Optional[int] = None,
        pricing_status: str = "ok",
        now: Optional[datetime] = None,
    ) -> QuotaShadowPreflight:
        """Classify a future enforcement result without enforcing or reserving quota."""
        budget_alert = self.classify_budget_alert(
            owner_user_id=owner_user_id,
            route_family=route_family,
            provider=provider,
            model_tier=model_tier,
            token_estimate=token_estimate,
            estimated_units=estimated_units,
            pricing_status=pricing_status,
            now=now,
        )
        pricing_key = budget_alert.pricing_status
        decision = self.evaluate_quota(
            owner_user_id=owner_user_id,
            route_family=route_family,
            provider=provider,
            model_tier=model_tier,
            token_estimate=token_estimate,
            estimated_units=estimated_units,
            now=now,
        )

        state = "would_allow"
        reason_code = decision.reason_code
        would_block = False
        if pricing_key != "ok":
            state = "pricing_unknown_fail_safe"
            reason_code = "pricing_policy_unknown"
            would_block = True
        elif budget_alert.state == "over_hard_limit" or not decision.allowed:
            state = "would_block_hard_limit"
            reason_code = reason_code or budget_alert.reason_code
            would_block = True
        elif budget_alert.state == "over_soft_limit":
            state = "would_block_soft_limit"
            reason_code = budget_alert.reason_code
            would_block = True
        elif budget_alert.state == "near_soft_limit":
            state = "would_warn"
            reason_code = budget_alert.reason_code

        return QuotaShadowPreflight(
            state=state,
            reason_code=reason_code,
            would_block=would_block,
            owner_user_id=self._normalize_optional(owner_user_id),
            route_family=self.classify_route_family(route_family),
            pricing_status=pricing_key,
            budget_alert=budget_alert,
        )

    def build_quota_pilot_decision_contract(
        self,
        *,
        owner_user_id: Optional[str],
        route_family: str,
        provider: Optional[str] = None,
        model_tier: Optional[str] = None,
        token_estimate: Optional[int] = None,
        estimated_units: Optional[int] = None,
        pricing_status: str = "ok",
        pilot_enabled: bool = False,
        pilot_owner_user_ids: Optional[Iterable[str]] = None,
        pilot_route_families: Optional[Iterable[str]] = None,
        live_enforcement: bool = False,
        owner_authenticated: bool = True,
        owner_transitional: bool = False,
        auth_enabled: bool = True,
        now: Optional[datetime] = None,
    ) -> QuotaPilotDecisionContract:
        """Build an advisory-only pilot decision contract without runtime side effects."""
        route_key = self.classify_route_family(route_family)
        owner_id = self._normalize_optional(owner_user_id)
        estimate_units = (
            max(0, int(estimated_units))
            if estimated_units is not None
            else self.estimate_budget_units(route_family=route_key, token_estimate=token_estimate)
        )
        pricing_key = str(pricing_status or "pricing_unknown").strip().lower() or "pricing_unknown"
        allowed_owners = {
            normalized
            for normalized in (self._normalize_optional(value) for value in (pilot_owner_user_ids or ()))
            if normalized is not None
        }
        owner_eligible, owner_eligibility_reason = self._pilot_owner_eligibility(
            owner_id=owner_id,
            owner_authenticated=owner_authenticated,
            owner_transitional=owner_transitional,
            auth_enabled=auth_enabled,
        )
        owner_in_scope = bool(owner_eligible and owner_id and owner_id in allowed_owners)
        allowed_routes = {
            self.classify_route_family(value)
            for value in (pilot_route_families if pilot_route_families is not None else ("analysis",))
        }
        route_in_scope = route_key in allowed_routes
        provider_context = {
            "provider": self._safe_context_label(provider, lowercase=True),
            "modelTier": self._safe_context_label(model_tier, lowercase=True),
            "pricingStatus": pricing_key,
        }

        block_reason_code: Optional[str] = None
        if owner_id is None:
            block_reason_code = "pilot_owner_missing"
        elif not owner_eligible:
            block_reason_code = owner_eligibility_reason
        elif not owner_in_scope:
            block_reason_code = "pilot_owner_out_of_scope"
        elif not route_in_scope:
            block_reason_code = "pilot_route_out_of_scope"
        elif pricing_key != "ok":
            block_reason_code = "pricing_unknown_advisory"
        elif estimate_units == 0:
            block_reason_code = "zero_cost_advisory"

        shadow_would_block = False
        if block_reason_code is None:
            shadow = self.classify_shadow_preflight(
                owner_user_id=owner_id,
                route_family=route_key,
                provider=provider,
                model_tier=model_tier,
                token_estimate=token_estimate,
                estimated_units=estimate_units,
                pricing_status=pricing_key,
                now=now,
            )
            shadow_would_block = bool(shadow.would_block)
            block_reason_code = shadow.budget_alert.reason_code or shadow.reason_code

        can_live_enforce = bool(pilot_enabled and owner_in_scope and route_in_scope and live_enforcement)
        request_blocked = bool(can_live_enforce and shadow_would_block)
        pilot_state = self._pilot_contract_state(
            pilot_enabled=bool(pilot_enabled),
            owner_id=owner_id,
            owner_eligible=owner_eligible,
            owner_in_scope=owner_in_scope,
            route_in_scope=route_in_scope,
            request_blocked=request_blocked,
            shadow_would_block=shadow_would_block,
        )
        allow_reason_code = self._pilot_allow_reason_code(
            pilot_enabled=bool(pilot_enabled),
            owner_id=owner_id,
            owner_eligible=owner_eligible,
            owner_in_scope=owner_in_scope,
            route_in_scope=route_in_scope,
            request_blocked=request_blocked,
            shadow_would_block=shadow_would_block,
            pricing_status=pricing_key,
            estimate_units=estimate_units,
        )
        return QuotaPilotDecisionContract(
            route_key=route_key,
            owner_id=owner_id,
            estimate_units=estimate_units,
            pilot_enabled=bool(pilot_enabled),
            owner_in_scope=owner_in_scope,
            route_in_scope=route_in_scope,
            pilot_state=pilot_state,
            reservation_id=None,
            provider_model_context=provider_context,
            allow_reason_code=allow_reason_code,
            owner_eligible=owner_eligible,
            owner_eligibility_reason_code=owner_eligibility_reason,
            owner_auth_enabled=bool(auth_enabled),
            owner_authenticated=bool(owner_authenticated),
            owner_transitional=bool(owner_transitional),
            request_blocked=request_blocked,
            block_reason_code=block_reason_code,
            live_enforcement=bool(request_blocked),
        )

    def classify_pilot_readiness_preflight(
        self,
        *,
        owner_user_id: Optional[str],
        route_family: str,
        provider: Optional[str] = None,
        model_tier: Optional[str] = None,
        token_estimate: Optional[int] = None,
        estimated_units: Optional[int] = None,
        pricing_status: str = "ok",
        pilot_enforcement_enabled: bool = False,
        pilot_owner_user_ids: Optional[Iterable[str]] = None,
        pilot_route_families: Optional[Iterable[str]] = None,
        owner_authenticated: bool = True,
        owner_transitional: bool = False,
        auth_enabled: bool = True,
        now: Optional[datetime] = None,
    ) -> QuotaPilotReadinessPreflight:
        """Report pilot readiness while keeping the default mode advisory-only."""
        route_key = self.classify_route_family(route_family)
        shadow = self.classify_shadow_preflight(
            owner_user_id=owner_user_id,
            route_family=route_key,
            provider=provider,
            model_tier=model_tier,
            token_estimate=token_estimate,
            estimated_units=estimated_units,
            pricing_status=pricing_status,
            now=now,
        )
        owner_key = self._normalize_optional(owner_user_id)
        owner_scoped = owner_key is not None
        owner_eligible, owner_eligibility_reason = self._pilot_owner_eligibility(
            owner_id=owner_key,
            owner_authenticated=owner_authenticated,
            owner_transitional=owner_transitional,
            auth_enabled=auth_enabled,
        )
        allowed_owners = {
            normalized
            for normalized in (self._normalize_optional(value) for value in (pilot_owner_user_ids or ()))
            if normalized is not None
        }
        owner_scope_explicit = bool(owner_eligible and owner_key and owner_key in allowed_owners)
        allowed_routes = {self.classify_route_family(value) for value in (pilot_route_families or (route_key,))}
        route_scoped = route_key in allowed_routes
        pilot_scope_explicit = owner_scope_explicit and route_scoped
        pilot_flag_enabled = bool(pilot_enforcement_enabled)
        can_enforce = pilot_flag_enabled and pilot_scope_explicit
        request_blocked = bool(can_enforce and shadow.would_block)
        advisory_only = not request_blocked
        safe_provider = self._safe_context_label(provider, lowercase=True)
        safe_model_tier = self._safe_context_label(model_tier, lowercase=True)
        provider_context = {
            "provider": safe_provider,
            "modelTier": safe_model_tier,
            "pricingStatus": shadow.pricing_status,
        }

        state = "pilot_advisory_allow"
        reason_code = shadow.reason_code
        if pilot_flag_enabled and not owner_scoped:
            state = "pilot_scope_not_ready"
            reason_code = "pilot_owner_scope_required"
        elif pilot_flag_enabled and not owner_eligible:
            state = "pilot_owner_not_eligible"
            reason_code = owner_eligibility_reason
        elif pilot_flag_enabled and not allowed_owners:
            state = "pilot_scope_not_ready"
            reason_code = "pilot_owner_scope_required"
        elif pilot_flag_enabled and not owner_scope_explicit:
            state = "pilot_owner_out_of_scope"
            reason_code = "pilot_owner_out_of_scope"
        elif pilot_flag_enabled and not route_scoped:
            state = "pilot_scope_not_ready"
            reason_code = "pilot_route_scope_required"
        elif request_blocked:
            state = "pilot_would_enforce_block"
        elif shadow.would_block:
            state = "pilot_advisory_would_block"
        allow_reason_code = self._pilot_allow_reason_code(
            pilot_enabled=pilot_flag_enabled,
            owner_id=owner_key,
            owner_eligible=owner_eligible,
            owner_in_scope=owner_scope_explicit,
            route_in_scope=route_scoped,
            request_blocked=request_blocked,
            shadow_would_block=shadow.would_block,
            pricing_status=shadow.pricing_status,
            estimate_units=int(shadow.budget_alert.estimated_units or 0),
        )

        return QuotaPilotReadinessPreflight(
            state=state,
            reason_code=reason_code,
            would_block=bool(shadow.would_block),
            advisory_only=advisory_only,
            request_blocked=request_blocked,
            live_enforcement=request_blocked,
            pilot_enforcement_enabled=pilot_flag_enabled,
            pilot_scope_explicit=pilot_scope_explicit,
            owner_scoped=owner_scoped,
            owner_user_id=self._safe_context_label(owner_user_id),
            route_family=route_key,
            provider=safe_provider,
            model_tier=safe_model_tier,
            route_in_scope=route_scoped,
            reservation_id=None,
            provider_model_context=provider_context,
            allow_reason_code=allow_reason_code,
            owner_eligible=owner_eligible,
            owner_eligibility_reason_code=owner_eligibility_reason,
            owner_auth_enabled=bool(auth_enabled),
            owner_authenticated=bool(owner_authenticated),
            owner_transitional=bool(owner_transitional),
            shadow_preflight=shadow,
        )

    @staticmethod
    def _pilot_owner_eligibility(
        *,
        owner_id: Optional[str],
        owner_authenticated: bool,
        owner_transitional: bool,
        auth_enabled: bool,
    ) -> Tuple[bool, Optional[str]]:
        if owner_id is None:
            return False, "pilot_owner_missing"
        if not bool(auth_enabled) and bool(owner_transitional):
            return False, "pilot_auth_disabled_bootstrap_not_eligible"
        if bool(owner_transitional):
            return False, "pilot_transitional_owner_not_eligible"
        if not bool(owner_authenticated):
            return False, "pilot_owner_not_authenticated"
        return True, None

    @staticmethod
    def _pilot_contract_state(
        *,
        pilot_enabled: bool,
        owner_id: Optional[str],
        owner_eligible: bool,
        owner_in_scope: bool,
        route_in_scope: bool,
        request_blocked: bool,
        shadow_would_block: bool,
    ) -> str:
        if request_blocked:
            return "pilot_would_enforce_block"
        if not pilot_enabled:
            return "pilot_disabled"
        if owner_id is None:
            return "pilot_scope_not_ready"
        if not owner_eligible:
            return "pilot_owner_not_eligible"
        if not owner_in_scope:
            return "pilot_owner_out_of_scope"
        if not route_in_scope:
            return "pilot_scope_not_ready"
        if shadow_would_block:
            return "pilot_advisory_would_block"
        return "pilot_advisory_allow"

    @staticmethod
    def _pilot_allow_reason_code(
        *,
        pilot_enabled: bool,
        owner_id: Optional[str],
        owner_eligible: bool,
        owner_in_scope: bool,
        route_in_scope: bool,
        request_blocked: bool,
        shadow_would_block: bool,
        pricing_status: str,
        estimate_units: int,
    ) -> Optional[str]:
        if request_blocked:
            return None
        if owner_id is None:
            return "pilot_owner_missing_advisory_allow"
        if not owner_eligible:
            return "pilot_owner_not_eligible_advisory_allow"
        if not pilot_enabled:
            if shadow_would_block:
                return "advisory_only_would_block_not_enforced"
            return "pilot_disabled_advisory_allow"
        if not owner_in_scope:
            return "pilot_owner_out_of_scope_advisory_allow"
        if not route_in_scope:
            return "pilot_route_out_of_scope_advisory_allow"
        if str(pricing_status or "").lower() != "ok":
            return "pricing_unknown_advisory_allow"
        if int(estimate_units or 0) == 0:
            return "zero_cost_advisory_allow"
        if shadow_would_block:
            return "advisory_only_would_block_not_enforced"
        return "pilot_scope_ready_advisory_allow"

    def build_budget_alert_notification_intent(
        self,
        pilot_readiness: QuotaPilotReadinessPreflight,
    ) -> Dict[str, Any]:
        """Build sanitized dry-run notification evidence without delivery side effects."""
        pilot_payload = pilot_readiness.to_dict()
        budget_alert = pilot_readiness.shadow_preflight.budget_alert
        should_emit_alert = bool(pilot_readiness.request_blocked)
        state = "dry_run_intent" if should_emit_alert else "suppressed_advisory_only"
        delivery_status = "dry_run_disabled" if should_emit_alert else "suppressed_advisory_only"

        return {
            "state": state,
            "eventType": "cost.quota_budget_alert",
            "severity": "warning" if should_emit_alert else "info",
            "reasonCode": pilot_readiness.reason_code,
            "alertDeliveryIntent": should_emit_alert,
            "deliveryStatus": delivery_status,
            "dryRun": True,
            "outboundAttempted": False,
            "liveOutbound": False,
            "runtimeWiringChanged": False,
            "scope": {
                "ownerUserId": pilot_payload["scope"]["ownerUserId"],
                "routeFamily": pilot_payload["scope"]["routeFamily"],
                "provider": pilot_payload["scope"]["provider"],
                "modelTier": pilot_payload["scope"]["modelTier"],
            },
            "budgetContext": {
                "budgetState": budget_alert.state,
                "pricingStatus": budget_alert.pricing_status,
                "usedUnits": budget_alert.used_units,
                "estimatedUnits": budget_alert.estimated_units,
                "projectedUnits": budget_alert.projected_units,
                "softLimitUnits": budget_alert.soft_limit_units,
                "hardLimitUnits": budget_alert.hard_limit_units,
                "wouldBlock": pilot_readiness.would_block,
                "requestBlocked": pilot_readiness.request_blocked,
            },
            "invoiceReconciliation": pilot_payload["invoiceReconciliation"],
            "safety": {
                "diagnosticOnly": True,
                "noExternalCalls": True,
                "liveLlmCalls": False,
                "liveProviderCalls": False,
                "liveInvoiceIngestion": False,
                "realOutboundNotification": False,
                "runtimeWiringChanged": False,
            },
            "operatorReview": {
                "statusLabel": state,
                "deliveryStatusLabel": delivery_status,
                "rollbackLabel": (
                    "disable_pilot_mode_before_delivery_wiring"
                    if should_emit_alert
                    else "no_runtime_change_to_rollback"
                ),
                "realOutboundNotification": False,
                "globalEnforcementChanged": False,
            },
        }

    def reserve_quota(
        self,
        *,
        owner_user_id: Optional[str],
        route_family: str,
        provider: Optional[str] = None,
        model_tier: Optional[str] = None,
        token_estimate: Optional[int] = None,
        estimated_units: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None,
        idempotency_key: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> QuotaDecision:
        if not self.enforcement_enabled:
            return QuotaDecision(allowed=True, status="disabled")
        current_time = now or datetime.now()
        route_key = self.classify_route_family(route_family)
        owner_key = self._normalize_optional(owner_user_id)
        provider_key = self._normalize_optional(provider, lowercase=True)
        model_key = self._normalize_optional(model_tier, lowercase=True)
        units = max(
            1,
            int(estimated_units)
            if estimated_units is not None
            else self.estimate_budget_units(route_family=route_key, token_estimate=token_estimate),
        )
        policies = list(self._matching_policies(route_key, provider_key, model_key))

        if self.global_kill_switch or self._policy_kill_switch_enabled(policies):
            return self._reject("global_kill_switch")
        if any(not bool(policy.get("enabled", True)) for policy in policies):
            return self._reject("quota_disabled")

        token_cap = self._minimum_cap(policies, "token_cap")
        if token_cap is not None and int(token_estimate or 0) > token_cap:
            return self._reject("token_cap_exceeded")

        request_hash = self.db.quota_reservation_idempotency_hash(
            idempotency_key=idempotency_key,
            owner_user_id=owner_key,
            route_family=route_key,
            provider=provider_key,
            model_tier=model_key,
        )

        for attempt in range(2):
            try:
                return self._reserve_quota_once(
                    owner_user_id=owner_key,
                    route_family=route_key,
                    provider=provider_key,
                    model_tier=model_key,
                    token_estimate=token_estimate,
                    units=units,
                    policies=policies,
                    metadata=metadata,
                    expires_at=expires_at,
                    now=current_time,
                    request_idempotency_key_hash=request_hash,
                )
            except IntegrityError:
                replay = self._replay_reservation_by_idempotency_hash(
                    request_idempotency_key_hash=request_hash,
                    now=current_time,
                )
                if replay is not None:
                    return replay
                if attempt == 0:
                    continue
                raise

        return self._reject("budget_exceeded")

    def _reserve_quota_once(
        self,
        *,
        owner_user_id: Optional[str],
        route_family: str,
        provider: Optional[str],
        model_tier: Optional[str],
        token_estimate: Optional[int],
        units: int,
        policies: Iterable[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]],
        expires_at: Optional[datetime],
        now: datetime,
        request_idempotency_key_hash: Optional[str],
    ) -> QuotaDecision:
        with self.db.session_scope() as session:
            replay = self._replay_reservation_by_idempotency_hash(
                session=session,
                request_idempotency_key_hash=request_idempotency_key_hash,
                now=now,
            )
            if replay is not None:
                return replay

            daily_start, daily_end = self._window_bounds("daily", now)
            monthly_start, monthly_end = self._window_bounds("monthly", now)

            if self._budget_exceeded(
                session=session,
                owner_user_id=owner_user_id,
                window_type="daily",
                window_start=daily_start,
                budget_units=self._minimum_cap(policies, "daily_budget_units"),
                estimate_units=units,
            ):
                return self._reject("budget_exceeded")
            if self._budget_exceeded(
                session=session,
                owner_user_id=owner_user_id,
                window_type="monthly",
                window_start=monthly_start,
                budget_units=self._minimum_cap(policies, "monthly_budget_units"),
                estimate_units=units,
            ):
                return self._reject("budget_exceeded")

            route_cap = self._minimum_cap(
                [policy for policy in policies if policy.get("scope_type") == "route"],
                "request_cap",
            )
            if route_cap is not None:
                route_requests = self._request_count(
                    session=session,
                    owner_user_id=None,
                    route_family=route_family,
                    window_type="daily",
                    window_start=daily_start,
                )
                if route_requests + 1 > route_cap:
                    return self._reject("route_cap_exceeded")

            reservation_id = f"qres_{uuid.uuid4().hex}"
            expires = expires_at or now + timedelta(minutes=15)
            row = QuotaReservation(
                reservation_id=reservation_id,
                owner_user_id=owner_user_id,
                route_family=route_family,
                provider=provider,
                model_tier=model_tier,
                request_idempotency_key_hash=request_idempotency_key_hash,
                estimated_units=units,
                status="reserved",
                metadata_json=self.db._safe_json_dumps(self.db._sanitize_quota_metadata(metadata or {})),
                created_at=now,
                updated_at=now,
                expires_at=expires,
            )
            session.add(row)
            for window_type, start, end in (
                ("daily", daily_start, daily_end),
                ("monthly", monthly_start, monthly_end),
            ):
                owner_window = self._get_or_create_window(
                    session=session,
                    owner_user_id=owner_user_id,
                    route_family=route_family,
                    provider=provider,
                    model_tier=model_tier,
                    window_type=window_type,
                    window_start=start,
                    window_end=end,
                    now=now,
                )
                owner_window.reserved_units = int(owner_window.reserved_units or 0) + units
                owner_window.request_count = int(owner_window.request_count or 0) + 1
                owner_window.updated_at = now

                route_window = self._get_or_create_window(
                    session=session,
                    owner_user_id=None,
                    route_family=route_family,
                    provider=provider,
                    model_tier=model_tier,
                    window_type=window_type,
                    window_start=start,
                    window_end=end,
                    now=now,
                )
                route_window.reserved_units = int(route_window.reserved_units or 0) + units
                route_window.request_count = int(route_window.request_count or 0) + 1
                route_window.updated_at = now

            return QuotaDecision(
                allowed=True,
                status="reserved",
                reservation_id=reservation_id,
                estimated_units=units,
            )

    def _replay_reservation_by_idempotency_hash(
        self,
        *,
        request_idempotency_key_hash: Optional[str],
        now: datetime,
        session: Optional[Any] = None,
    ) -> Optional[QuotaDecision]:
        if not request_idempotency_key_hash:
            return None
        if session is None:
            with self.db.session_scope() as replay_session:
                return self._replay_reservation_by_idempotency_hash(
                    session=replay_session,
                    request_idempotency_key_hash=request_idempotency_key_hash,
                    now=now,
                )

        row = session.execute(
            select(QuotaReservation)
            .where(QuotaReservation.request_idempotency_key_hash == request_idempotency_key_hash)
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            return None

        reservation_id = str(row.reservation_id or "").strip()
        status = str(row.status or "").strip().lower()
        if status == "reserved" and row.expires_at <= now:
            return self._expire_reserved_reservation(
                session=session,
                row=row,
                reservation_id=reservation_id,
                now=now,
            )
        if status == "reserved":
            return QuotaDecision(
                allowed=True,
                status="reserved",
                reservation_id=reservation_id,
                estimated_units=int(row.estimated_units or 0),
            )
        return self._terminal_reservation_decision(row=row, reservation_id=reservation_id)

    def consume_reservation(
        self,
        *,
        reservation_id: Optional[str],
        actual_units: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> QuotaDecision:
        current_time = now or datetime.now()
        normalized_id = str(reservation_id or "").strip()
        if not normalized_id:
            return self._missing_reservation_decision(reservation_id=None)
        with self.db.session_scope() as session:
            row = session.execute(
                select(QuotaReservation)
                .where(QuotaReservation.reservation_id == normalized_id)
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                return self._missing_reservation_decision(reservation_id=normalized_id)
            status = str(row.status or "").strip().lower()
            if status != "reserved":
                return self._terminal_reservation_decision(row=row, reservation_id=normalized_id)
            if row.expires_at <= current_time:
                return self._expire_reserved_reservation(
                    session=session,
                    row=row,
                    reservation_id=normalized_id,
                    now=current_time,
                )

            consumed_units = max(0, int(actual_units if actual_units is not None else row.estimated_units or 0))
            self._move_reserved_units(session=session, row=row, consumed_units=consumed_units, now=current_time)
            row.status = "consumed"
            row.updated_at = current_time
            return QuotaDecision(
                allowed=True,
                status="consumed",
                reservation_id=normalized_id,
                estimated_units=int(row.estimated_units or 0),
            )

    def release_reservation(
        self,
        *,
        reservation_id: Optional[str],
        now: Optional[datetime] = None,
    ) -> QuotaDecision:
        current_time = now or datetime.now()
        normalized_id = str(reservation_id or "").strip()
        if not normalized_id:
            return self._missing_reservation_decision(reservation_id=None)
        with self.db.session_scope() as session:
            row = session.execute(
                select(QuotaReservation)
                .where(QuotaReservation.reservation_id == normalized_id)
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                return self._missing_reservation_decision(reservation_id=normalized_id)
            status = str(row.status or "").strip().lower()
            if status != "reserved":
                return self._terminal_reservation_decision(row=row, reservation_id=normalized_id)
            if row.expires_at <= current_time:
                return self._expire_reserved_reservation(
                    session=session,
                    row=row,
                    reservation_id=normalized_id,
                    now=current_time,
                )

            self._move_reserved_units(session=session, row=row, consumed_units=0, now=current_time)
            row.status = "released"
            row.updated_at = current_time
            return QuotaDecision(
                allowed=True,
                status="released",
                reservation_id=normalized_id,
                estimated_units=int(row.estimated_units or 0),
            )

    def _missing_reservation_decision(self, *, reservation_id: Optional[str]) -> QuotaDecision:
        return QuotaDecision(
            allowed=False,
            status="missing",
            reason_code="reservation_missing",
            reservation_id=reservation_id,
        )

    def _terminal_reservation_decision(
        self,
        *,
        row: QuotaReservation,
        reservation_id: str,
    ) -> QuotaDecision:
        status = str(row.status or "expired").strip().lower() or "expired"
        reason_code = "reservation_expired" if status == "expired" else "reservation_already_terminal"
        return QuotaDecision(
            allowed=False,
            status=status,
            reason_code=reason_code,
            reservation_id=reservation_id,
            estimated_units=int(row.estimated_units or 0),
        )

    def _expire_reserved_reservation(
        self,
        *,
        session: Any,
        row: QuotaReservation,
        reservation_id: str,
        now: datetime,
    ) -> QuotaDecision:
        self._move_reserved_units(session=session, row=row, consumed_units=0, now=now)
        row.status = "expired"
        row.reason_code = "reservation_expired"
        row.updated_at = now
        return self._reject(
            "reservation_expired",
            status="expired",
            reservation_id=reservation_id,
            estimated_units=int(row.estimated_units or 0),
        )

    def _matching_policies(
        self,
        route_family: str,
        provider: Optional[str],
        model_tier: Optional[str],
    ) -> Iterable[Dict[str, Any]]:
        policies = self.db.list_quota_policies(route_family=route_family, provider=provider, model_tier=model_tier)
        for policy in policies:
            scope = policy.get("scope_type")
            if scope == "route" and policy.get("route_family") not in (None, route_family):
                continue
            if scope in {"provider", "model_tier"}:
                if policy.get("provider") not in (None, provider):
                    continue
                if policy.get("model_tier") not in (None, model_tier):
                    continue
            yield policy

    @staticmethod
    def _policy_kill_switch_enabled(policies: Iterable[Dict[str, Any]]) -> bool:
        for policy in policies:
            if policy.get("scope_type") == "global" and bool((policy.get("metadata") or {}).get("kill_switch")):
                return True
        return False

    @staticmethod
    def _minimum_cap(policies: Iterable[Dict[str, Any]], key: str) -> Optional[int]:
        values = [int(policy[key]) for policy in policies if policy.get(key) is not None]
        return min(values) if values else None

    @staticmethod
    def _minimum_soft_limit(policies: Iterable[Dict[str, Any]]) -> Optional[int]:
        values = []
        for policy in policies:
            metadata = policy.get("metadata") or {}
            if not isinstance(metadata, dict):
                continue
            for key in ("daily_soft_limit_units", "soft_limit_units", "budget_soft_limit_units"):
                if metadata.get(key) is not None:
                    values.append(max(0, int(metadata[key])))
                    break
        return min(values) if values else None

    @staticmethod
    def _window_bounds(window_type: str, now: datetime) -> Tuple[datetime, datetime]:
        if window_type == "monthly":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)
            return start, end
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=1)

    @staticmethod
    def _normalize_optional(value: Optional[str], *, lowercase: bool = False) -> Optional[str]:
        text = str(value or "").strip()
        if lowercase:
            text = text.lower()
        return text[:64] if text else None

    @classmethod
    def _safe_context_label(cls, value: Optional[str], *, lowercase: bool = False) -> Optional[str]:
        text = str(value or "").strip()
        if not text:
            return None
        lowered = text.lower().replace("-", "_")
        if any(token in lowered for token in cls.SENSITIVE_CONTEXT_TOKENS):
            return "redacted"
        if lowercase:
            text = text.lower()
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_./:")
        safe = "".join(char if char in allowed else "_" for char in text)
        return safe[:96] if safe else None

    def _budget_exceeded(
        self,
        *,
        session: Any,
        owner_user_id: Optional[str],
        window_type: str,
        window_start: datetime,
        budget_units: Optional[int],
        estimate_units: int,
    ) -> bool:
        if budget_units is None:
            return False
        used = session.execute(
            select(
                func.coalesce(func.sum(QuotaUsageWindow.reserved_units), 0),
                func.coalesce(func.sum(QuotaUsageWindow.consumed_units), 0),
            ).where(
                QuotaUsageWindow.owner_user_id == self._normalize_optional(owner_user_id),
                QuotaUsageWindow.window_type == window_type,
                QuotaUsageWindow.window_start == window_start,
            )
        ).one()
        return int(used[0] or 0) + int(used[1] or 0) + estimate_units > int(budget_units)

    def _used_budget_units(
        self,
        *,
        session: Any,
        owner_user_id: Optional[str],
        window_type: str,
        window_start: datetime,
    ) -> int:
        used = session.execute(
            select(
                func.coalesce(func.sum(QuotaUsageWindow.reserved_units), 0),
                func.coalesce(func.sum(QuotaUsageWindow.consumed_units), 0),
            ).where(
                QuotaUsageWindow.owner_user_id == self._normalize_optional(owner_user_id),
                QuotaUsageWindow.window_type == window_type,
                QuotaUsageWindow.window_start == window_start,
            )
        ).one()
        return int(used[0] or 0) + int(used[1] or 0)

    def _request_count(
        self,
        *,
        session: Any,
        owner_user_id: Optional[str],
        route_family: str,
        window_type: str,
        window_start: datetime,
    ) -> int:
        query = select(func.coalesce(func.sum(QuotaUsageWindow.request_count), 0)).where(
            QuotaUsageWindow.route_family == route_family,
            QuotaUsageWindow.window_type == window_type,
            QuotaUsageWindow.window_start == window_start,
        )
        if owner_user_id is None:
            query = query.where(QuotaUsageWindow.owner_user_id.is_(None))
        else:
            query = query.where(QuotaUsageWindow.owner_user_id == self._normalize_optional(owner_user_id))
        return int(session.execute(query).scalar_one() or 0)

    def _get_or_create_window(
        self,
        *,
        session: Any,
        owner_user_id: Optional[str],
        route_family: str,
        provider: Optional[str],
        model_tier: Optional[str],
        window_type: str,
        window_start: datetime,
        window_end: datetime,
        now: datetime,
    ) -> QuotaUsageWindow:
        owner_key = self._normalize_optional(owner_user_id)
        identity = self.db.quota_window_identity_values(
            owner_user_id=owner_key,
            route_family=route_family,
            provider=provider,
            model_tier=model_tier,
        )
        query = select(QuotaUsageWindow).where(
            QuotaUsageWindow.window_identity_key == identity["window_identity_key"],
            QuotaUsageWindow.window_type == window_type,
            QuotaUsageWindow.window_start == window_start,
        )
        row = session.execute(query.limit(1)).scalar_one_or_none()
        if row is not None:
            return row
        row = QuotaUsageWindow(
            owner_user_id=owner_key,
            route_family=route_family,
            provider=provider,
            model_tier=model_tier,
            window_type=window_type,
            window_start=window_start,
            window_end=window_end,
            updated_at=now,
            **identity,
        )
        session.add(row)
        return row

    def _move_reserved_units(
        self,
        *,
        session: Any,
        row: QuotaReservation,
        consumed_units: int,
        now: datetime,
    ) -> None:
        estimated_units = int(row.estimated_units or 0)
        owner_identity = self.db.quota_window_identity_values(
            owner_user_id=row.owner_user_id,
            route_family=row.route_family,
            provider=row.provider,
            model_tier=row.model_tier,
        )
        route_identity = self.db.quota_window_identity_values(
            owner_user_id=None,
            route_family=row.route_family,
            provider=row.provider,
            model_tier=row.model_tier,
        )
        identity_keys = {
            owner_identity["window_identity_key"],
            route_identity["window_identity_key"],
        }
        for window_type, window_start in (
            ("daily", self._window_bounds("daily", row.created_at)[0]),
            ("monthly", self._window_bounds("monthly", row.created_at)[0]),
        ):
            windows_query = select(QuotaUsageWindow).where(
                QuotaUsageWindow.window_identity_key.in_(identity_keys),
                QuotaUsageWindow.window_type == window_type,
                QuotaUsageWindow.window_start == window_start,
            )
            for window in session.execute(windows_query).scalars().all():
                window.reserved_units = max(0, int(window.reserved_units or 0) - estimated_units)
                window.consumed_units = int(window.consumed_units or 0) + consumed_units
                window.updated_at = now

    def _reject(
        self,
        reason_code: str,
        *,
        status: str = "rejected",
        reservation_id: Optional[str] = None,
        estimated_units: int = 0,
    ) -> QuotaDecision:
        safe_reason = reason_code if reason_code in self.SAFE_REJECTION_REASON_CODES else "budget_exceeded"
        return QuotaDecision(
            allowed=False,
            status=status,
            reason_code=safe_reason,
            reservation_id=reservation_id,
            estimated_units=estimated_units,
        )
