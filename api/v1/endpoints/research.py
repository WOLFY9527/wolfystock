# -*- coding: utf-8 -*-
"""Research Radar read-only endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import CurrentUser, get_current_user, get_current_user_id, get_database_manager
from api.v1.schemas.research_radar import ResearchRadarResponse
from src.repositories.scanner_repo import ScannerRepository
from src.services.research_radar_service import ResearchRadarService
from src.storage import DatabaseManager


router = APIRouter()


@router.get(
    "/radar",
    response_model=ResearchRadarResponse,
    summary="Get research radar queue",
    description=(
        "Build a research-only radar queue from the latest available scanner candidate evidence. "
        "The endpoint is read-only and does not run scanners or mutate watchlists."
    ),
)
def get_research_radar(
    market: Optional[str] = Query(None, description="Optional scanner market filter"),
    profile: Optional[str] = Query(None, description="Optional scanner profile filter"),
    limit: int = Query(20, ge=1, le=100, description="Recent scanner runs to inspect"),
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> ResearchRadarResponse:
    bounded_limit = max(1, min(int(limit or 20), 20))
    service = ResearchRadarService(
        scanner_repository=ScannerRepository(db_manager),
    )
    payload = service.build_from_latest_scanner_run(
        market=market,
        profile=profile,
        owner_id=get_current_user_id(current_user),
        limit=bounded_limit,
    )
    return ResearchRadarResponse.model_validate(payload)
