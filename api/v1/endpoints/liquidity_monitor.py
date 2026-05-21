# -*- coding: utf-8 -*-
"""Advisory-only liquidity monitor endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from api.v1.schemas.liquidity_monitor import LiquidityMonitorResponse
from src.services.liquidity_monitor_service import LiquidityMonitorService


router = APIRouter()


@router.get(
    "/liquidity-monitor",
    response_model=LiquidityMonitorResponse,
    response_model_exclude_none=True,
    summary="Get advisory liquidity monitor",
)
def get_liquidity_monitor() -> LiquidityMonitorResponse:
    return LiquidityMonitorService().get_liquidity_monitor()
