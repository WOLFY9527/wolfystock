# -*- coding: utf-8 -*-
"""Synthetic LLM cost ledger and pricing policy helpers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from typing import Any, Dict, Optional

from src.storage import DatabaseManager, ModelPricingPolicy, QuotaReservation


_MILLION = Decimal("1000000")
_COST_QUANT = Decimal("0.00000001")


@dataclass(frozen=True)
class PricingLookupResult:
    status: str
    policy: Optional[ModelPricingPolicy] = None


@dataclass(frozen=True)
class CostCalculationResult:
    status: str
    provider: str
    model: str
    prompt_tokens: int
    cache_hit_tokens: int
    cache_miss_tokens: int
    completion_tokens: int
    total_tokens: int
    input_cost_usd: Decimal
    cached_input_cost_usd: Decimal
    output_cost_usd: Decimal
    total_cost_usd: Decimal
    pricing_policy_key: Optional[str] = None
    pricing_snapshot: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class LedgerWriteResult:
    status: str
    ledger_id: Optional[str] = None
    cost: Optional[CostCalculationResult] = None
    quota_reconciliation: Optional["QuotaReservationReconciliationResult"] = None


@dataclass(frozen=True)
class QuotaReservationReconciliationResult:
    result_code: str
    reservation_id: Optional[str] = None
    action: Optional[str] = None
    quota_status: Optional[str] = None
    reason_code: Optional[str] = None


class QuotaReservationReconciliationHelper:
    """Best-effort bridge from synthetic cost ledger rows to quota reservations."""

    TERMINAL_STATUSES = {"consumed", "released", "expired"}

    def __init__(self, *, db: DatabaseManager, quota_policy_service: Optional[Any] = None) -> None:
        self.db = db
        self._quota_policy_service = quota_policy_service

    def reconcile(
        self,
        *,
        cost_result: Optional[CostCalculationResult] = None,
        ledger_row: Optional[Dict[str, Any]] = None,
        quota_reservation_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> QuotaReservationReconciliationResult:
        reservation_id = self._normalize_reservation_id(
            quota_reservation_id
            or getattr(cost_result, "quota_reservation_id", None)
            or (ledger_row or {}).get("quota_reservation_id")
        )
        if not reservation_id:
            return QuotaReservationReconciliationResult(result_code="no_reservation")

        status = str(
            getattr(cost_result, "status", None)
            or (ledger_row or {}).get("status")
            or "pricing_unknown"
        ).strip().lower()
        current_time = now or datetime.now()

        try:
            reservation = self._read_reservation(reservation_id)
            if reservation is None:
                return QuotaReservationReconciliationResult(
                    result_code="reservation_missing",
                    reservation_id=reservation_id,
                    reason_code="reservation_missing",
                )
            if reservation.status in self.TERMINAL_STATUSES:
                return self._terminal_result(reservation_id=reservation_id, status=reservation.status)
            if reservation.status != "reserved":
                return self._terminal_result(reservation_id=reservation_id, status=reservation.status)
            if reservation.expires_at <= current_time:
                return self._expire_reserved_reservation(reservation_id=reservation_id, now=current_time)

            if status == "ok":
                return self._consume(reservation_id=reservation_id, now=current_time)
            if status in {"pricing_unknown", "pricing_inactive"}:
                return self._release(
                    reservation_id=reservation_id,
                    now=current_time,
                    result_code="pricing_unknown_no_consume",
                )
            if status == "invalid_usage":
                return self._release(
                    reservation_id=reservation_id,
                    now=current_time,
                    result_code="invalid_usage_no_consume",
                )
            return self._release(
                reservation_id=reservation_id,
                now=current_time,
                result_code="reconciled_released",
            )
        except Exception:
            return QuotaReservationReconciliationResult(
                result_code="reconciliation_error",
                reservation_id=reservation_id,
                reason_code="reconciliation_error",
            )

    def _quota_service(self) -> Any:
        if self._quota_policy_service is None:
            from src.services.quota_policy_service import QuotaPolicyService

            self._quota_policy_service = QuotaPolicyService(db=self.db, enforcement_enabled=True)
        return self._quota_policy_service

    def _read_reservation(self, reservation_id: str) -> Optional[QuotaReservation]:
        with self.db.session_scope() as session:
            row = session.query(QuotaReservation).filter_by(reservation_id=reservation_id).one_or_none()
            if row is not None:
                session.expunge(row)
            return row

    def _consume(self, *, reservation_id: str, now: datetime) -> QuotaReservationReconciliationResult:
        decision = self._quota_service().consume_reservation(reservation_id=reservation_id, now=now)
        if decision.allowed and decision.status == "consumed":
            return QuotaReservationReconciliationResult(
                result_code="reconciled_consumed",
                reservation_id=reservation_id,
                action="consume",
                quota_status=decision.status,
            )
        return self._decision_failure_result(decision=decision, reservation_id=reservation_id, action="consume")

    def _release(
        self,
        *,
        reservation_id: str,
        now: datetime,
        result_code: str,
    ) -> QuotaReservationReconciliationResult:
        decision = self._quota_service().release_reservation(reservation_id=reservation_id, now=now)
        if decision.allowed and decision.status == "released":
            return QuotaReservationReconciliationResult(
                result_code=result_code,
                reservation_id=reservation_id,
                action="release",
                quota_status=decision.status,
            )
        return self._decision_failure_result(decision=decision, reservation_id=reservation_id, action="release")

    def _expire_reserved_reservation(self, *, reservation_id: str, now: datetime) -> QuotaReservationReconciliationResult:
        decision = self._quota_service().release_reservation(reservation_id=reservation_id, now=now)
        return QuotaReservationReconciliationResult(
            result_code="reservation_expired",
            reservation_id=reservation_id,
            action="expire",
            quota_status=decision.status,
            reason_code="reservation_expired",
        )

    @staticmethod
    def _decision_failure_result(
        *,
        decision: Any,
        reservation_id: str,
        action: str,
    ) -> QuotaReservationReconciliationResult:
        if getattr(decision, "reason_code", None) == "reservation_expired" or getattr(decision, "status", None) == "expired":
            return QuotaReservationReconciliationResult(
                result_code="reservation_expired",
                reservation_id=reservation_id,
                action=action,
                quota_status=getattr(decision, "status", None),
                reason_code="reservation_expired",
            )
        return QuotaReservationReconciliationResult(
            result_code="reservation_already_terminal",
            reservation_id=reservation_id,
            action=action,
            quota_status=getattr(decision, "status", None),
            reason_code=getattr(decision, "reason_code", None),
        )

    @staticmethod
    def _terminal_result(*, reservation_id: str, status: Optional[str]) -> QuotaReservationReconciliationResult:
        if status == "expired":
            return QuotaReservationReconciliationResult(
                result_code="reservation_expired",
                reservation_id=reservation_id,
                quota_status=status,
                reason_code="reservation_expired",
            )
        return QuotaReservationReconciliationResult(
            result_code="reservation_already_terminal",
            reservation_id=reservation_id,
            quota_status=status,
            reason_code="reservation_already_terminal",
        )

    @staticmethod
    def _normalize_reservation_id(value: Optional[str]) -> Optional[str]:
        text = str(value or "").strip()
        return text[:64] if text else None


class LlmCostLedgerService:
    """Compute estimated LLM cost and write synthetic ledger rows."""

    SAFE_RESULT_CODES = {"ok", "pricing_unknown", "invalid_usage", "pricing_inactive"}

    def __init__(self, *, db: Optional[DatabaseManager] = None, quota_policy_service: Optional[Any] = None) -> None:
        self.db = db or DatabaseManager.get_instance()
        self._quota_policy_service = quota_policy_service

    def sanitize_metadata(self, metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return self.db._sanitize_llm_cost_metadata(metadata or {})

    def lookup_pricing_policy(
        self,
        *,
        provider: str,
        model: str,
        at: Optional[datetime] = None,
    ) -> PricingLookupResult:
        policy = self.db.get_model_pricing_policy(provider=provider, model=model, at=at)
        if policy is not None:
            return PricingLookupResult(status="ok", policy=policy)
        inactive = self.db.get_model_pricing_policy(provider=provider, model=model, at=at, include_inactive=True)
        if inactive is not None and not bool(inactive.active):
            return PricingLookupResult(status="pricing_inactive", policy=inactive)
        return PricingLookupResult(status="pricing_unknown")

    def calculate_cost(
        self,
        *,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        route_family: str,
        call_type: str,
        cached_input_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        at: Optional[datetime] = None,
    ) -> CostCalculationResult:
        del route_family, call_type
        prompt_count = int(prompt_tokens or 0)
        cached_count = int(cached_input_tokens or 0)
        completion_count = int(completion_tokens or 0)
        total_count = int(total_tokens if total_tokens is not None else prompt_count + completion_count)
        provider_key = str(provider or "unknown").strip().lower() or "unknown"
        model_key = str(model or "unknown").strip().lower() or "unknown"
        if prompt_count < 0 or cached_count < 0 or completion_count < 0 or total_count < 0 or cached_count > prompt_count:
            return self._zero_result("invalid_usage", provider_key, model_key, prompt_count, cached_count, completion_count, total_count)

        lookup = self.lookup_pricing_policy(provider=provider_key, model=model_key, at=at)
        if lookup.status != "ok" or lookup.policy is None:
            return self._zero_result(lookup.status, provider_key, model_key, prompt_count, cached_count, completion_count, total_count)

        policy = lookup.policy
        input_price = Decimal(str(policy.input_price_per_1m or 0))
        output_price = Decimal(str(policy.output_price_per_1m or 0))
        cached_price = Decimal(str(policy.cached_input_price_per_1m)) if policy.cached_input_price_per_1m is not None else None
        cache_miss = max(0, prompt_count - cached_count)
        if cached_price is None:
            regular_input_tokens = prompt_count
            cached_cost = Decimal("0")
        else:
            regular_input_tokens = cache_miss
            cached_cost = self._price_tokens(cached_count, cached_price)
        input_cost = self._price_tokens(regular_input_tokens, input_price)
        output_cost = self._price_tokens(completion_count, output_price)
        total_cost = self._quantize(input_cost + cached_cost + output_cost)
        snapshot = {
            "policy_key": policy.policy_key,
            "provider": policy.provider,
            "model": policy.model,
            "pricing_unit": policy.pricing_unit,
            "input_price_per_1m": str(policy.input_price_per_1m or 0),
            "cached_input_price_per_1m": str(policy.cached_input_price_per_1m) if policy.cached_input_price_per_1m is not None else None,
            "output_price_per_1m": str(policy.output_price_per_1m or 0),
            "currency": policy.currency,
            "effective_from": policy.effective_from.isoformat() if policy.effective_from else None,
            "source_label": policy.source_label,
        }
        return CostCalculationResult(
            status="ok",
            provider=provider_key,
            model=model_key,
            prompt_tokens=prompt_count,
            cache_hit_tokens=cached_count,
            cache_miss_tokens=cache_miss,
            completion_tokens=completion_count,
            total_tokens=total_count,
            input_cost_usd=input_cost,
            cached_input_cost_usd=cached_cost,
            output_cost_usd=output_cost,
            total_cost_usd=total_cost,
            pricing_policy_key=policy.policy_key,
            pricing_snapshot=snapshot,
        )

    def reconcile_usage(
        self,
        *,
        owner_user_id: Optional[str] = None,
        guest_bucket_hash: Optional[str] = None,
        route_family: str,
        call_type: str,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        cached_input_tokens: Optional[int] = None,
        quota_reservation_id: Optional[str] = None,
        request_hash: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        at: Optional[datetime] = None,
    ) -> LedgerWriteResult:
        cost = self.calculate_cost(
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            cached_input_tokens=cached_input_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            route_family=route_family,
            call_type=call_type,
            at=at,
        )
        ledger_id = f"llmcost_{uuid.uuid4().hex}"
        self.db.record_llm_cost_ledger(
            ledger_id=ledger_id,
            owner_user_id=owner_user_id,
            guest_bucket_hash=guest_bucket_hash,
            route_family=route_family,
            call_type=call_type,
            provider=provider,
            model=model,
            prompt_tokens=max(0, int(prompt_tokens or 0)),
            cached_input_tokens=max(0, int(cached_input_tokens or 0)),
            cache_miss_input_tokens=max(0, int(cost.cache_miss_tokens or 0)),
            completion_tokens=max(0, int(completion_tokens or 0)),
            total_tokens=max(0, int(total_tokens or 0)),
            input_cost_usd=cost.input_cost_usd,
            cached_input_cost_usd=cost.cached_input_cost_usd,
            output_cost_usd=cost.output_cost_usd,
            total_cost_usd=cost.total_cost_usd,
            pricing_policy_key=cost.pricing_policy_key,
            pricing_snapshot=cost.pricing_snapshot or {},
            quota_reservation_id=quota_reservation_id,
            request_hash=request_hash,
            status=cost.status,
            metadata=metadata or {},
            created_at=at or datetime.now(),
        )
        quota_reconciliation = None
        if quota_reservation_id:
            quota_reconciliation = QuotaReservationReconciliationHelper(
                db=self.db,
                quota_policy_service=self._quota_policy_service,
            ).reconcile(
                cost_result=cost,
                quota_reservation_id=quota_reservation_id,
                now=at,
            )
        return LedgerWriteResult(
            status=cost.status,
            ledger_id=ledger_id,
            cost=cost,
            quota_reconciliation=quota_reconciliation,
        )

    def get_summary(self, *, from_dt: datetime, to_dt: datetime, limit: int = 50) -> Dict[str, Any]:
        return self.db.get_llm_cost_ledger_summary(from_dt=from_dt, to_dt=to_dt, limit=limit)

    @staticmethod
    def _price_tokens(tokens: int, price_per_1m: Decimal) -> Decimal:
        return LlmCostLedgerService._quantize((Decimal(max(0, int(tokens or 0))) * price_per_1m) / _MILLION)

    @staticmethod
    def _quantize(value: Decimal) -> Decimal:
        return Decimal(value).quantize(_COST_QUANT, rounding=ROUND_HALF_UP)

    @staticmethod
    def _zero_result(
        status: str,
        provider: str,
        model: str,
        prompt_tokens: int,
        cached_input_tokens: int,
        completion_tokens: int,
        total_tokens: int,
    ) -> CostCalculationResult:
        safe_status = status if status in LlmCostLedgerService.SAFE_RESULT_CODES else "pricing_unknown"
        return CostCalculationResult(
            status=safe_status,
            provider=provider,
            model=model,
            prompt_tokens=max(0, prompt_tokens),
            cache_hit_tokens=max(0, cached_input_tokens),
            cache_miss_tokens=max(0, prompt_tokens - cached_input_tokens),
            completion_tokens=max(0, completion_tokens),
            total_tokens=max(0, total_tokens),
            input_cost_usd=Decimal("0"),
            cached_input_cost_usd=Decimal("0"),
            output_cost_usd=Decimal("0"),
            total_cost_usd=Decimal("0"),
        )
