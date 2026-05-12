# -*- coding: utf-8 -*-
"""Admin-only read APIs for safe portfolio visibility projections."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import CurrentUser, require_admin_capability
from api.v1.schemas.admin_portfolio import (
    AdminHoldingListResponse,
    AdminPortfolioAccountDetailResponse,
    AdminPortfolioActivityResponse,
    AdminPortfolioSummaryResponse,
)
from src.auth_context import AdminActorContext
from src.services.admin_governance_audit_service import AdminGovernanceAuditService
from src.services.admin_portfolio_service import AdminPortfolioService

router = APIRouter()


def _normalize_user_id(user_id: str) -> str:
    normalized = str(user_id or "").strip()
    if not normalized or len(normalized) > 64:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": "Invalid user_id"})
    return normalized


def _normalize_symbol(symbol: Optional[str]) -> Optional[str]:
    if symbol is None:
        return None
    normalized = str(symbol or "").strip().upper()
    if not normalized:
        return None
    if len(normalized) > 32:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": "Invalid symbol"})
    return normalized


def _normalize_market(market: Optional[str]) -> Optional[str]:
    if market is None:
        return None
    normalized = str(market or "").strip().lower()
    if not normalized:
        return None
    if len(normalized) > 16:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": "Invalid market"})
    return normalized


def _service_or_404(user_id: str) -> AdminPortfolioService:
    service = AdminPortfolioService()
    if not service.target_user_exists(user_id):
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "User not found"})
    return service


def _to_admin_actor(current_user: CurrentUser) -> AdminActorContext:
    return AdminActorContext(
        user_id=current_user.user_id,
        username=current_user.username,
        display_name=current_user.display_name,
        role=current_user.role,
        is_admin=current_user.is_admin,
    )


def _record_audit(
    *,
    action: str,
    actor: AdminActorContext,
    target_user_id: str,
    metadata: dict,
) -> None:
    AdminGovernanceAuditService().record_view(
        action=action,
        actor=actor,
        target_user_id=target_user_id,
        metadata=metadata,
    )


@router.get(
    "/users/{user_id}/portfolio-summary",
    response_model=AdminPortfolioSummaryResponse,
    summary="Read one user's safe admin portfolio summary",
)
def get_admin_portfolio_summary(
    user_id: str,
    include_inactive: bool = Query(default=False),
    current_user: CurrentUser = Depends(require_admin_capability("users:portfolio:read")),
) -> AdminPortfolioSummaryResponse:
    actor = _to_admin_actor(current_user)
    normalized_user_id = _normalize_user_id(user_id)
    service = _service_or_404(normalized_user_id)
    response = AdminPortfolioSummaryResponse.model_validate(
        service.get_summary(user_id=normalized_user_id, include_inactive=include_inactive)
    )
    _record_audit(
        action="admin_portfolio.summary_viewed",
        actor=actor,
        target_user_id=normalized_user_id,
        metadata={
            "include_inactive": bool(include_inactive),
            "account_count": response.account_count,
            "active_account_count": response.active_account_count,
        },
    )
    return response


@router.get(
    "/users/{user_id}/holdings",
    response_model=AdminHoldingListResponse,
    summary="List one user's safe admin holdings projection",
)
def list_admin_user_holdings(
    user_id: str,
    account_id: Optional[int] = Query(default=None, ge=1),
    symbol: Optional[str] = Query(default=None, max_length=32),
    market: Optional[str] = Query(default=None, max_length=16),
    include_zero: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=10000),
    current_user: CurrentUser = Depends(require_admin_capability("users:portfolio:read")),
) -> AdminHoldingListResponse:
    actor = _to_admin_actor(current_user)
    normalized_user_id = _normalize_user_id(user_id)
    service = _service_or_404(normalized_user_id)
    items, total = service.list_holdings(
        user_id=normalized_user_id,
        account_id=account_id,
        symbol=_normalize_symbol(symbol),
        market=_normalize_market(market),
        include_zero=include_zero,
        limit=limit,
        offset=offset,
    )
    if total < 0:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Portfolio account not found"})
    response = AdminHoldingListResponse.model_validate(
        {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
            "limitations": ["raw_broker_payloads_excluded", "raw_broker_refs_masked"],
        }
    )
    _record_audit(
        action="admin_portfolio.holdings_viewed",
        actor=actor,
        target_user_id=normalized_user_id,
        metadata={
            "account_id": account_id,
            "symbol": _normalize_symbol(symbol),
            "market": _normalize_market(market),
            "include_zero": bool(include_zero),
            "limit": limit,
            "offset": offset,
            "result_count": len(items),
            "total": total,
        },
    )
    return response


@router.get(
    "/users/{user_id}/portfolio-activity",
    response_model=AdminPortfolioActivityResponse,
    summary="List one user's safe admin portfolio activity projection",
)
def list_admin_user_portfolio_activity(
    user_id: str,
    account_id: Optional[int] = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=10000),
    current_user: CurrentUser = Depends(require_admin_capability("users:portfolio:read")),
) -> AdminPortfolioActivityResponse:
    actor = _to_admin_actor(current_user)
    normalized_user_id = _normalize_user_id(user_id)
    service = _service_or_404(normalized_user_id)
    items, total, summary = service.list_activity(
        user_id=normalized_user_id,
        account_id=account_id,
        limit=limit,
        offset=offset,
    )
    if total < 0:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Portfolio account not found"})
    response = AdminPortfolioActivityResponse.model_validate(
        {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
            "summary": summary,
            "limitations": ["notes_and_raw_import_rows_excluded"],
        }
    )
    _record_audit(
        action="admin_portfolio.activity_viewed",
        actor=actor,
        target_user_id=normalized_user_id,
        metadata={
            "account_id": account_id,
            "limit": limit,
            "offset": offset,
            "result_count": len(items),
            "total": total,
            "summary": response.summary.model_dump(by_alias=True),
        },
    )
    return response


@router.get(
    "/users/{user_id}/portfolio/accounts/{account_id}",
    response_model=AdminPortfolioAccountDetailResponse,
    summary="Read one user's safe admin portfolio account detail",
)
def get_admin_portfolio_account_detail(
    user_id: str,
    account_id: int,
    current_user: CurrentUser = Depends(require_admin_capability("users:portfolio:read")),
) -> AdminPortfolioAccountDetailResponse:
    actor = _to_admin_actor(current_user)
    normalized_user_id = _normalize_user_id(user_id)
    if account_id <= 0:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": "Invalid account_id"})
    service = _service_or_404(normalized_user_id)
    payload = service.get_account_detail(user_id=normalized_user_id, account_id=account_id)
    if payload is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Portfolio account not found"})
    response = AdminPortfolioAccountDetailResponse.model_validate(payload)
    _record_audit(
        action="admin_portfolio.account_detail_viewed",
        actor=actor,
        target_user_id=normalized_user_id,
        metadata={
            "account_id": account_id,
            "holding_total": response.holdings.total,
            "activity_total": response.activity.total,
            "broker_connection_count": len(response.broker_connections),
        },
    )
    return response
