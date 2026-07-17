# -*- coding: utf-8 -*-
"""Pure leveraged ETF mapper endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_current_user
from api.v1.schemas.leveraged_etf_mapper import (
    LeveragedEtfMapperCalculateRequest,
    LeveragedEtfMapperCalculateResponse,
    LeveragedEtfMappingsResponse,
)
from src.services.leveraged_etf_mapper_service import (
    LeveragedEtfMapperInputError,
    LeveragedEtfMapperService,
)


router = APIRouter(dependencies=[Depends(get_current_user)])


def _service() -> LeveragedEtfMapperService:
    return LeveragedEtfMapperService()


@router.get(
    "/mappings",
    response_model=LeveragedEtfMappingsResponse,
    summary="List curated leveraged ETF mapper metadata",
)
def list_leveraged_etf_mappings() -> LeveragedEtfMappingsResponse:
    return _service().list_mappings_payload()


@router.post(
    "/calculate",
    response_model=LeveragedEtfMapperCalculateResponse,
    summary="Calculate caller-provided leveraged ETF scenarios",
)
def calculate_leveraged_etf_scenario(
    request: LeveragedEtfMapperCalculateRequest,
) -> LeveragedEtfMapperCalculateResponse:
    try:
        return _service().calculate(
            etf_symbol=request.etfSymbol,
            underlying_symbol=request.underlyingSymbol,
            etf_ref_price=request.etfRefPrice,
            underlying_ref_price=request.underlyingRefPrice,
            underlying_target_price=request.underlyingTargetPrice,
            etf_target_price=request.etfTargetPrice,
        )
    except LeveragedEtfMapperInputError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": exc.code, "message": str(exc)},
        ) from exc
