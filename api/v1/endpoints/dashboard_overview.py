# -*- coding: utf-8 -*-
"""Homepage dashboard market intelligence overview endpoint."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends

from api.deps import CurrentUser, get_optional_current_user
from api.v1.schemas.dashboard_overview import DashboardMarketIntelligenceOverviewResponse
from src.services.dashboard_overview_service import DashboardOverviewService

router = APIRouter()


def _actor(current_user: Optional[CurrentUser]) -> Optional[Dict[str, Any]]:
    if current_user is None or not hasattr(current_user, "user_id"):
        return {"actor_type": "anonymous", "role": "anonymous", "display_name": "Anonymous"}
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "display_name": current_user.display_name,
        "role": current_user.role,
        "actor_type": "admin" if current_user.is_admin else "user",
        "session_id": current_user.session_id,
    }


@router.get(
    "/market-intelligence-overview",
    response_model=DashboardMarketIntelligenceOverviewResponse,
    response_model_exclude_none=True,
    summary="Get consumer-safe homepage market intelligence overview",
)
def get_market_intelligence_overview(
    current_user: Optional[CurrentUser] = Depends(get_optional_current_user),
):
    _actor(current_user)
    return DashboardOverviewService().get_market_intelligence_overview()
