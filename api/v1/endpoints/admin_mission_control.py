# -*- coding: utf-8 -*-
"""Admin-only read API for Mission Control posture."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.deps import CurrentUser, require_admin_capability
from api.v1.schemas.admin_mission_control import AdminMissionControlResponse
from src.services.admin_mission_control_service import AdminMissionControlService

router = APIRouter()


@router.get(
    "/mission-control",
    response_model=AdminMissionControlResponse,
    summary="Get read-only admin mission control posture",
)
def get_admin_mission_control(
    request: Request,
    _: CurrentUser = Depends(require_admin_capability("ops:logs:read")),
) -> AdminMissionControlResponse:
    service = getattr(request.app.state, "admin_mission_control_service", None)
    if service is None:
        service = AdminMissionControlService()
    return AdminMissionControlResponse.model_validate(
        service.build_snapshot(app_state=request.app.state)
    )
