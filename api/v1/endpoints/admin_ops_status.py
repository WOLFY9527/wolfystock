# -*- coding: utf-8 -*-
"""Admin-only read API for ops status snapshots."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.deps import CurrentUser, require_admin_capability
from api.v1.schemas.admin_ops_status import AdminOpsStatusResponse
from src.services.admin_ops_status_service import AdminOpsStatusService

router = APIRouter()


@router.get(
    "/ops/status",
    response_model=AdminOpsStatusResponse,
    summary="Get read-only admin ops status snapshot",
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
