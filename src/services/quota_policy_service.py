# -*- coding: utf-8 -*-
"""Synthetic quota policy foundation for future LLM/API enforcement."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, Optional, Tuple

from sqlalchemy import func, or_, select

from src.storage import DatabaseManager, QuotaReservation, QuotaUsageWindow


@dataclass(frozen=True)
class QuotaDecision:
    """Result of a synthetic quota policy operation."""

    allowed: bool
    status: str
    reason_code: Optional[str] = None
    reservation_id: Optional[str] = None
    estimated_units: int = 0


class QuotaPolicyService:
    """Budget/quota policy checks that are not wired into live providers yet."""

    SAFE_REJECTION_REASON_CODES = {
        "budget_exceeded",
        "quota_disabled",
        "global_kill_switch",
        "token_cap_exceeded",
        "route_cap_exceeded",
        "reservation_expired",
    }

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
        now: Optional[datetime] = None,
    ) -> QuotaDecision:
        if not self.enforcement_enabled:
            return QuotaDecision(allowed=True, status="disabled")
        current_time = now or datetime.now()
        route_key = self.classify_route_family(route_family)
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

        with self.db.session_scope() as session:
            daily_start, daily_end = self._window_bounds("daily", current_time)
            monthly_start, monthly_end = self._window_bounds("monthly", current_time)

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
                    route_family=route_key,
                    window_type="daily",
                    window_start=daily_start,
                )
                if route_requests + 1 > route_cap:
                    return self._reject("route_cap_exceeded")

            reservation_id = f"qres_{uuid.uuid4().hex}"
            expires = expires_at or current_time + timedelta(minutes=15)
            row = QuotaReservation(
                reservation_id=reservation_id,
                owner_user_id=self._normalize_optional(owner_user_id),
                route_family=route_key,
                provider=provider_key,
                model_tier=model_key,
                estimated_units=units,
                status="reserved",
                metadata_json=self.db._safe_json_dumps(self.db._sanitize_quota_metadata(metadata or {})),
                created_at=current_time,
                updated_at=current_time,
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
                    route_family=route_key,
                    provider=provider_key,
                    model_tier=model_key,
                    window_type=window_type,
                    window_start=start,
                    window_end=end,
                    now=current_time,
                )
                owner_window.reserved_units = int(owner_window.reserved_units or 0) + units
                owner_window.request_count = int(owner_window.request_count or 0) + 1
                owner_window.updated_at = current_time

                route_window = self._get_or_create_window(
                    session=session,
                    owner_user_id=None,
                    route_family=route_key,
                    provider=provider_key,
                    model_tier=model_key,
                    window_type=window_type,
                    window_start=start,
                    window_end=end,
                    now=current_time,
                )
                route_window.reserved_units = int(route_window.reserved_units or 0) + units
                route_window.request_count = int(route_window.request_count or 0) + 1
                route_window.updated_at = current_time

            return QuotaDecision(
                allowed=True,
                status="reserved",
                reservation_id=reservation_id,
                estimated_units=units,
            )

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
            return self._reject("reservation_expired", status="expired")
        with self.db.session_scope() as session:
            row = session.execute(
                select(QuotaReservation)
                .where(QuotaReservation.reservation_id == normalized_id)
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                return self._reject("reservation_expired", status="expired")
            if row.status != "reserved" or row.expires_at <= current_time:
                row.status = "expired"
                row.reason_code = "reservation_expired"
                row.updated_at = current_time
                return self._reject("reservation_expired", status="expired", reservation_id=normalized_id)

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
            return self._reject("reservation_expired", status="expired")
        with self.db.session_scope() as session:
            row = session.execute(
                select(QuotaReservation)
                .where(QuotaReservation.reservation_id == normalized_id)
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                return self._reject("reservation_expired", status="expired")
            if row.status != "reserved" or row.expires_at <= current_time:
                row.status = "expired"
                row.reason_code = "reservation_expired"
                row.updated_at = current_time
                return self._reject("reservation_expired", status="expired", reservation_id=normalized_id)

            self._move_reserved_units(session=session, row=row, consumed_units=0, now=current_time)
            row.status = "released"
            row.updated_at = current_time
            return QuotaDecision(
                allowed=True,
                status="released",
                reservation_id=normalized_id,
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
        query = select(QuotaUsageWindow).where(
            QuotaUsageWindow.route_family == route_family,
            QuotaUsageWindow.window_type == window_type,
            QuotaUsageWindow.window_start == window_start,
        )
        query = query.where(
            QuotaUsageWindow.owner_user_id.is_(None)
            if owner_key is None
            else QuotaUsageWindow.owner_user_id == owner_key
        )
        query = query.where(
            QuotaUsageWindow.provider.is_(None)
            if provider is None
            else QuotaUsageWindow.provider == provider
        )
        query = query.where(
            QuotaUsageWindow.model_tier.is_(None)
            if model_tier is None
            else QuotaUsageWindow.model_tier == model_tier
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
        for window_type, window_start in (
            ("daily", self._window_bounds("daily", row.created_at)[0]),
            ("monthly", self._window_bounds("monthly", row.created_at)[0]),
        ):
            windows_query = select(QuotaUsageWindow).where(
                QuotaUsageWindow.route_family == row.route_family,
                QuotaUsageWindow.window_type == window_type,
                QuotaUsageWindow.window_start == window_start,
            )
            if row.owner_user_id is None:
                windows_query = windows_query.where(QuotaUsageWindow.owner_user_id.is_(None))
            else:
                windows_query = windows_query.where(
                    or_(QuotaUsageWindow.owner_user_id == row.owner_user_id, QuotaUsageWindow.owner_user_id.is_(None))
                )
            if row.provider is None:
                windows_query = windows_query.where(QuotaUsageWindow.provider.is_(None))
            else:
                windows_query = windows_query.where(QuotaUsageWindow.provider == row.provider)
            if row.model_tier is None:
                windows_query = windows_query.where(QuotaUsageWindow.model_tier.is_(None))
            else:
                windows_query = windows_query.where(QuotaUsageWindow.model_tier == row.model_tier)
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
