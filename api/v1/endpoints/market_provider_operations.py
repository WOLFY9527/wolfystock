# -*- coding: utf-8 -*-
"""Admin-only market provider operations APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.deps import CurrentUser, require_admin_capability
from api.v1.schemas.market_provider_operations import MarketProviderOperationsResponse
from src.services.market_provider_operations_service import MarketProviderOperationsService

router = APIRouter()


@router.get(
    "/market-providers/operations",
    response_model=MarketProviderOperationsResponse,
    summary="Get read-only market provider operations status",
)
def get_market_provider_operations(
    window: str = Query(default="24h", description="Relative window: 15m, 1h, 24h, or 7d"),
    _: CurrentUser = Depends(require_admin_capability("ops:providers:read")),
):
    return MarketProviderOperationsService().get_operations(window=window)
