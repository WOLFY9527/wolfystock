# -*- coding: utf-8 -*-
"""Admin-only read APIs for duplicate-cost summaries."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select

from api.deps import CurrentUser, require_admin_capability
from api.v1.schemas.admin_cost import (
    DuplicateCostSummaryResponse,
    DuplicateCostSummaryWindow,
    LlmLedgerSummaryResponse,
    LlmLedgerSummaryRollup,
    LlmLedgerSummaryTotal,
    ModelPricingPoliciesResponse,
    ModelPricingPolicyItem,
    QuotaDryRunRequest,
    QuotaDryRunResponse,
)
from src.services.duplicate_cost_summary_service import DuplicateCostSummaryService
from src.services.llm_cost_ledger_service import LlmCostLedgerService
from src.services.quota_policy_service import QuotaDecision, QuotaPolicyService
from src.storage import DatabaseManager, ModelPricingPolicy
from src.utils.security import sanitize_message, sanitize_url

router = APIRouter()

_LEDGER_WINDOWS = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


def _safe_source_url(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    lowered = text.lower()
    if not (lowered.startswith("https://") or lowered.startswith("http://")):
        return None
    return sanitize_url(sanitize_message(text))[:500]


def _pricing_policy_item(row: ModelPricingPolicy) -> ModelPricingPolicyItem:
    return ModelPricingPolicyItem(
        provider=str(row.provider or "unknown"),
        model=str(row.model or "unknown"),
        inputPricePer1m=str(row.input_price_per_1m or 0),
        cachedInputPricePer1m=str(row.cached_input_price_per_1m) if row.cached_input_price_per_1m is not None else None,
        outputPricePer1m=str(row.output_price_per_1m or 0),
        currency=str(row.currency or "USD"),
        effectiveFrom=row.effective_from.isoformat() if row.effective_from else None,
        effectiveUntil=row.effective_until.isoformat() if row.effective_until else None,
        active=bool(row.active),
        sourceLabel=sanitize_message(str(row.source_label or "").strip())[:128] or None,
        sourceUrl=_safe_source_url(row.source_url),
        updatedAt=row.updated_at.isoformat() if row.updated_at else None,
    )


@router.get(
    "/cost/duplicate-summary",
    response_model=DuplicateCostSummaryResponse,
    summary="Get read-only duplicate-cost summary",
)
def get_duplicate_cost_summary(
    window: str = Query(default="24h", description="Relative window: 15m, 1h, 24h, or 7d"),
    bucket: str = Query(default="hour", description="Aggregation bucket contract: hour or day"),
    area: str = Query(default="all", description="all, llm, provider, market-cache, or scanner-ai"),
    limit: int = Query(default=50, ge=1, le=200),
    _: CurrentUser = Depends(require_admin_capability("cost:observability:read")),
) -> DuplicateCostSummaryResponse:
    try:
        return DuplicateCostSummaryService().build_summary(
            window=window,
            bucket=bucket,
            area=area,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": str(exc)},
        ) from exc


@router.post(
    "/cost/quota-dry-run",
    response_model=QuotaDryRunResponse,
    summary="Evaluate quota policy through a dry-run diagnostic path",
)
def run_quota_dry_run(
    request: QuotaDryRunRequest,
    _: CurrentUser = Depends(require_admin_capability("cost:observability:read")),
) -> QuotaDryRunResponse:
    route_family = QuotaPolicyService().classify_route_family(request.route_family)
    enforcement_enabled = request.enforcement_mode != "disabled"
    service = QuotaPolicyService(
        enforcement_enabled=enforcement_enabled,
        global_kill_switch=bool(request.global_kill_switch),
    )

    budget_alert = service.classify_budget_alert(
        owner_user_id=request.owner_user_id,
        route_family=route_family,
        provider=request.provider,
        model_tier=request.model_tier,
        token_estimate=request.token_estimate,
        estimated_units=request.estimated_units,
        pricing_status=request.pricing_status,
    )
    shadow_preflight = service.classify_shadow_preflight(
        owner_user_id=request.owner_user_id,
        route_family=route_family,
        provider=request.provider,
        model_tier=request.model_tier,
        token_estimate=request.token_estimate,
        estimated_units=request.estimated_units,
        pricing_status=request.pricing_status,
    )
    pilot_readiness = service.classify_pilot_readiness_preflight(
        owner_user_id=request.owner_user_id,
        route_family=route_family,
        provider=request.provider,
        model_tier=request.model_tier,
        token_estimate=request.token_estimate,
        estimated_units=request.estimated_units,
        pricing_status=request.pricing_status,
        pilot_enforcement_enabled=request.enforcement_mode == "enabled",
        pilot_owner_user_ids=tuple(request.pilot_owner_user_ids or ()),
        pilot_route_families=(route_family,),
    )
    budget_alert_payload = budget_alert.to_dict()
    shadow_preflight_payload = shadow_preflight.to_dict()
    pilot_readiness_payload = pilot_readiness.to_dict()
    budget_alert_notification_payload = service.build_budget_alert_notification_intent(pilot_readiness)
    safe_owner_user_id = service._safe_context_label(request.owner_user_id)
    budget_alert_payload["ownerUserId"] = safe_owner_user_id
    shadow_preflight_payload["ownerUserId"] = safe_owner_user_id
    quota_decision_mode = (
        "pilot_enforced"
        if request.enforcement_mode == "enabled" and pilot_readiness_payload["pilot"]["scopeExplicit"]
        else "advisory"
    )
    if request.enforcement_mode == "enabled" and quota_decision_mode == "advisory":
        decision = QuotaDecision(
            allowed=True,
            status="pilot_advisory",
            reason_code=pilot_readiness.reason_code,
            estimated_units=int(budget_alert.estimated_units or 0),
        )
    elif request.operation == "estimate":
        decision = service.evaluate_quota(
            owner_user_id=request.owner_user_id,
            route_family=route_family,
            provider=request.provider,
            model_tier=request.model_tier,
            token_estimate=request.token_estimate,
            estimated_units=request.estimated_units,
        )
    elif request.operation == "reserve":
        decision = service.reserve_quota(
            owner_user_id=request.owner_user_id,
            route_family=route_family,
            provider=request.provider,
            model_tier=request.model_tier,
            token_estimate=request.token_estimate,
            estimated_units=request.estimated_units,
            metadata={
                **request.metadata,
                "source": "admin_quota_dry_run",
                "diagnostic_only": True,
            },
        )
    elif request.operation == "consume":
        decision = service.consume_reservation(
            reservation_id=request.reservation_id,
            actual_units=request.actual_units,
        )
    else:
        decision = service.release_reservation(reservation_id=request.reservation_id)

    response_allowed = bool(decision.allowed)
    response_status = decision.status
    response_reason_code = decision.reason_code
    if request.enforcement_mode == "enabled":
        if quota_decision_mode == "pilot_enforced":
            response_allowed = not bool(pilot_readiness.request_blocked)
            response_status = "pilot_enforced_block" if pilot_readiness.request_blocked else "pilot_enforced_allow"
            response_reason_code = pilot_readiness.reason_code if pilot_readiness.request_blocked else None
        else:
            response_allowed = True
            response_status = "pilot_advisory"
            response_reason_code = pilot_readiness.reason_code
    return QuotaDryRunResponse(
        allowed=response_allowed,
        wouldBlock=not response_allowed,
        status=response_status,
        reasonCode=response_reason_code,
        routeFamily=route_family,
        estimatedUnits=int(decision.estimated_units or 0),
        enforcementMode=request.enforcement_mode,
        operation=request.operation,
        reservationId=decision.reservation_id,
        metadata={
            "diagnosticOnly": True,
            "liveEnforcement": False,
            "noExternalCalls": True,
            "quotaDecisionMode": quota_decision_mode,
            "budgetAlert": budget_alert_payload,
            "budgetAlertNotification": budget_alert_notification_payload,
            "shadowPreflight": shadow_preflight_payload,
            "pilotReadiness": pilot_readiness_payload,
            "invoiceReconciliation": pilot_readiness_payload["invoiceReconciliation"],
            "operatorReview": {
                "quotaDecisionMode": quota_decision_mode,
                "quotaStatusLabel": response_status,
                "pilotStatusLabel": pilot_readiness_payload["operatorReview"]["statusLabel"],
                "budgetAlertDeliveryStatusLabel": budget_alert_notification_payload["operatorReview"]["deliveryStatusLabel"],
                "rollbackLabel": pilot_readiness_payload["operatorReview"]["rollbackLabel"],
                "globalEnforcementChanged": False,
                "realOutboundNotification": False,
            },
            "dataSources": ["quota_policy_definitions", "quota_usage_windows", "quota_reservations"],
            "redaction": [
                "prompt_content",
                "provider_payload",
                "credentials",
                "session_references",
                "stack_details",
            ],
        },
    )


@router.get(
    "/cost/llm-ledger-summary",
    response_model=LlmLedgerSummaryResponse,
    summary="Get read-only LLM cost ledger summary",
)
def get_llm_ledger_summary(
    window: str = Query(default="24h", description="Relative window: 24h, 7d, or 30d"),
    bucket: str = Query(default="day", description="Aggregation bucket contract: hour or day"),
    limit: int = Query(default=50, ge=1, le=200),
    _: CurrentUser = Depends(require_admin_capability("cost:observability:read")),
) -> LlmLedgerSummaryResponse:
    window_key = str(window or "24h").strip().lower()
    bucket_key = str(bucket or "day").strip().lower()
    if window_key not in _LEDGER_WINDOWS:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": f"Invalid window: {window}"})
    if bucket_key not in {"hour", "day"}:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": f"Invalid bucket: {bucket}"})

    now = datetime.now()
    from_dt = now - _LEDGER_WINDOWS[window_key]
    summary = LlmCostLedgerService().get_summary(
        from_dt=from_dt,
        to_dt=now,
        limit=limit,
    )

    return LlmLedgerSummaryResponse(
        generatedAt=now.isoformat(),
        window=DuplicateCostSummaryWindow(
            key=window_key,
            **{"from": from_dt.isoformat()},
            to=now.isoformat(),
            bucket=bucket_key,
            historical=True,
        ),
        total=LlmLedgerSummaryTotal(**summary["total"]),
        byUser=[
            LlmLedgerSummaryRollup(
                group=str(row.get("owner_user_id") or "guest_or_unknown"),
                calls=int(row.get("calls") or 0),
                totalTokens=int(row.get("total_tokens") or 0),
                totalCostUsd=str(row.get("total_cost_usd") or "0"),
                dimensions={"owner_user_id": str(row.get("owner_user_id") or "guest_or_unknown")},
            )
            for row in summary.get("by_user", [])
        ],
        byProviderModel=[
            LlmLedgerSummaryRollup(
                group=str(row.get("provider_model") or "unknown"),
                calls=int(row.get("calls") or 0),
                totalTokens=int(row.get("total_tokens") or 0),
                totalCostUsd=str(row.get("total_cost_usd") or "0"),
                dimensions={
                    "provider": str(row.get("provider") or "unknown"),
                    "model": str(row.get("model") or "unknown"),
                },
            )
            for row in summary.get("by_provider_model", [])
        ],
        byRouteFamily=[
            LlmLedgerSummaryRollup(
                group=str(row.get("route_family") or "unknown"),
                calls=int(row.get("calls") or 0),
                totalTokens=int(row.get("total_tokens") or 0),
                totalCostUsd=str(row.get("total_cost_usd") or "0"),
                dimensions={"route_family": str(row.get("route_family") or "unknown")},
            )
            for row in summary.get("by_route_family", [])
        ],
        metadata={
            "readOnly": True,
            "noExternalCalls": True,
            "liveEnforcement": False,
            "dataSources": ["llm_cost_ledger", "model_pricing_policies"],
            "redaction": ["prompts_omitted", "provider_payloads_omitted", "credentials_omitted", "safe_hash_labels_only"],
        },
    )


@router.get(
    "/cost/model-pricing-policies",
    response_model=ModelPricingPoliciesResponse,
    summary="Get read-only model pricing policies",
)
def get_model_pricing_policies(
    limit: int = Query(default=200, ge=1, le=500),
    _: CurrentUser = Depends(require_admin_capability("cost:observability:read")),
) -> ModelPricingPoliciesResponse:
    now = datetime.now()
    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        rows = (
            session.execute(
                select(ModelPricingPolicy)
                .order_by(
                    desc(ModelPricingPolicy.active),
                    ModelPricingPolicy.provider,
                    ModelPricingPolicy.model,
                    desc(ModelPricingPolicy.effective_from),
                    desc(ModelPricingPolicy.updated_at),
                )
                .limit(limit)
            )
            .scalars()
            .all()
        )

    return ModelPricingPoliciesResponse(
        generatedAt=now.isoformat(),
        activeCount=sum(1 for row in rows if bool(row.active)),
        policies=[_pricing_policy_item(row) for row in rows],
        metadata={
            "readOnly": True,
            "noExternalCalls": True,
            "liveEnforcement": False,
            "manualMaintenance": True,
            "dataSources": ["model_pricing_policies"],
            "redaction": ["metadata_omitted", "internal_row_fields_omitted", "secret_like_source_url_params_masked"],
        },
    )
