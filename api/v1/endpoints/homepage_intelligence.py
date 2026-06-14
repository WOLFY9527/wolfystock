# -*- coding: utf-8 -*-
"""Bounded homepage intelligence metadata endpoint for UI discovery and UAT."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends

from api.deps import CurrentUser, get_optional_current_user
from api.v1.schemas.homepage_intelligence import HomepageIntelligenceResponse
from src.services.homepage_intelligence_service import HomepageIntelligenceService

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
    "/intelligence",
    response_model=HomepageIntelligenceResponse,
    response_model_exclude_none=True,
    summary="Get bounded homepage metadata and fixed fixtures for UI discovery/UAT",
)
def get_homepage_intelligence(
    current_user: Optional[CurrentUser] = Depends(get_optional_current_user),
):
    _actor(current_user)
    return HomepageIntelligenceService().build_bundle()
