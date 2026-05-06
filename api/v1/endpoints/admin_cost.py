# -*- coding: utf-8 -*-
"""Admin-only read APIs for duplicate-cost summaries."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import CurrentUser, require_admin_user
from api.v1.schemas.admin_cost import DuplicateCostSummaryResponse
from src.services.duplicate_cost_summary_service import DuplicateCostSummaryService

router = APIRouter()


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
