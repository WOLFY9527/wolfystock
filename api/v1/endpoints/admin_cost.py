# -*- coding: utf-8 -*-
"""Admin-only read APIs for duplicate-cost summaries."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import CurrentUser, require_admin_capability, require_admin_user
from api.v1.schemas.admin_cost import (
    DuplicateCostSummaryResponse,
    DuplicateCostSummaryWindow,
    LlmLedgerSummaryResponse,
    LlmLedgerSummaryRollup,
    LlmLedgerSummaryTotal,
    QuotaDryRunRequest,
    QuotaDryRunResponse,
)
from src.services.duplicate_cost_summary_service import DuplicateCostSummaryService
from src.services.llm_cost_ledger_service import LlmCostLedgerService
from src.services.quota_policy_service import QuotaPolicyService

router = APIRouter()

_LEDGER_WINDOWS = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


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
    _: CurrentUser = Depends(require_admin_user),
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

    if request.operation == "estimate":
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

    return QuotaDryRunResponse(
        allowed=bool(decision.allowed),
        wouldBlock=not bool(decision.allowed),
        status=decision.status,
        reasonCode=decision.reason_code,
        routeFamily=route_family,
        estimatedUnits=int(decision.estimated_units or 0),
        enforcementMode=request.enforcement_mode,
        operation=request.operation,
        reservationId=decision.reservation_id,
        metadata={
            "diagnosticOnly": True,
            "liveEnforcement": False,
            "noExternalCalls": True,
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
