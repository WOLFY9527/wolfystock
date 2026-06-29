# -*- coding: utf-8 -*-
"""Admin-only read API for ops status snapshots."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from api.deps import CurrentUser, get_database_manager, require_admin_capability
from api.v1.schemas.admin_ops_status import (
    AdminOpsStatusResponse,
    AdminScannerUniverseReadinessResponse,
    AdminScannerUniverseRefreshResponse,
)
from api.v1.schemas.admin_surface_readiness import BackendSurfaceReadinessResponse
from src.services.admin_ops_status_service import AdminOpsStatusService
from src.services.admin_surface_contract_readiness_service import (
    AdminSurfaceContractReadinessService,
)
from src.services.market_scanner_ops_service import MarketScannerOperationsService
from src.storage import DatabaseManager

router = APIRouter()


def _scanner_universe_operator_service(
    *,
    request: Request,
    db_manager: DatabaseManager,
) -> MarketScannerOperationsService:
    service = getattr(request.app.state, "scanner_universe_operator_service", None)
    if service is not None:
        return service
    return MarketScannerOperationsService(db_manager=db_manager)


@router.get(
    "/ops/status",
    response_model=AdminOpsStatusResponse,
    summary="Get read-only admin ops status snapshot",
)
@router.get(
    "/ops-status",
    response_model=AdminOpsStatusResponse,
    summary="Compatibility alias for admin ops status snapshot",
    include_in_schema=False,
)
@router.get(
    "/launch-cockpit",
    response_model=AdminOpsStatusResponse,
    summary="Compatibility alias for admin launch cockpit ops snapshot",
    include_in_schema=False,
)
def get_admin_ops_status(
    request: Request,
    _: CurrentUser = Depends(require_admin_capability("ops:logs:read")),
) -> AdminOpsStatusResponse:
    service = getattr(request.app.state, "admin_ops_status_service", None)
    if service is None:
        service = AdminOpsStatusService()
    return AdminOpsStatusResponse.model_validate(
        service.build_status(app_state=request.app.state)
    )


@router.get(
    "/ops/surface-readiness",
    response_model=BackendSurfaceReadinessResponse,
    summary="Get read-only backend surface contract parity snapshot",
)
def get_admin_surface_readiness(
    request: Request,
    _: CurrentUser = Depends(require_admin_capability("ops:logs:read")),
) -> BackendSurfaceReadinessResponse:
    service = getattr(request.app.state, "admin_surface_contract_readiness_service", None)
    if service is None:
        service = AdminSurfaceContractReadinessService()
    return BackendSurfaceReadinessResponse.model_validate(
        service.build_snapshot(routes=request.app.routes)
    )


@router.get(
    "/ops/scanner-universe-readiness",
    response_model=AdminScannerUniverseReadinessResponse,
    summary="Get admin scanner universe readiness and next operator action",
)
@router.get(
    "/scanner/universe-readiness",
    response_model=AdminScannerUniverseReadinessResponse,
    summary="Compatibility alias for admin scanner universe readiness",
    include_in_schema=False,
)
def get_admin_scanner_universe_readiness(
    request: Request,
    market: str = Query("cn"),
    profile: str | None = Query(None),
    db_manager: DatabaseManager = Depends(get_database_manager),
    _: CurrentUser = Depends(require_admin_capability("ops:logs:read")),
) -> AdminScannerUniverseReadinessResponse:
    service = _scanner_universe_operator_service(request=request, db_manager=db_manager)
    return AdminScannerUniverseReadinessResponse.model_validate(
        service.get_universe_operator_readiness(market=market, profile=profile)
    )


@router.post(
    "/ops/scanner-universe-refresh",
    response_model=AdminScannerUniverseRefreshResponse,
    summary="Request bounded admin scanner universe refresh action",
)
def request_admin_scanner_universe_refresh(
    request: Request,
    market: str = Query("cn"),
    profile: str | None = Query(None),
    db_manager: DatabaseManager = Depends(get_database_manager),
    _: CurrentUser = Depends(require_admin_capability("ops:logs:read")),
) -> AdminScannerUniverseRefreshResponse:
    service = _scanner_universe_operator_service(request=request, db_manager=db_manager)
    return AdminScannerUniverseRefreshResponse.model_validate(
        service.request_universe_refresh_action(market=market, profile=profile)
    )
