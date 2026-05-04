# -*- coding: utf-8 -*-
"""Optional quant analytics endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from api.deps import CurrentUser, get_config_dep, require_admin_user
from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.quant import (
    QuantDuckDBBenchmarkRequest,
    QuantDuckDBBenchmarkResponse,
    QuantDuckDBHealthResponse,
    QuantDuckDBInitRequest,
    QuantDuckDBInitResponse,
)
from src.config import Config
from src.services.quant_analytics.duckdb_service import QuantDuckDBService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_quant_duckdb_service(config: Config = Depends(get_config_dep)) -> QuantDuckDBService:
    return QuantDuckDBService.from_config(config)


@router.get(
    "/duckdb/health",
    response_model=QuantDuckDBHealthResponse,
    responses={401: {"description": "Unauthorized", "model": ErrorResponse}, 403: {"description": "Admin access required", "model": ErrorResponse}},
    summary="Get DuckDB quant engine health",
    description="Return safe availability/status metadata for the optional DuckDB quant analytics engine.",
)
def get_duckdb_health(
    service: QuantDuckDBService = Depends(get_quant_duckdb_service),
    _admin: CurrentUser = Depends(require_admin_user),
) -> QuantDuckDBHealthResponse:
    return QuantDuckDBHealthResponse.model_validate(service.health())


@router.post(
    "/duckdb/init",
    response_model=QuantDuckDBInitResponse,
    responses={401: {"description": "Unauthorized", "model": ErrorResponse}, 403: {"description": "Admin access required", "model": ErrorResponse}},
    summary="Initialize DuckDB quant schema",
    description="Create DuckDB quant analytics tables only when explicitly invoked.",
)
def initialize_duckdb_schema(
    request: QuantDuckDBInitRequest = QuantDuckDBInitRequest(),
    service: QuantDuckDBService = Depends(get_quant_duckdb_service),
    _admin: CurrentUser = Depends(require_admin_user),
) -> QuantDuckDBInitResponse:
    payload = service.initialize_schema(force=request.allow_when_disabled)
    return QuantDuckDBInitResponse.model_validate(payload)


@router.post(
    "/duckdb/benchmark",
    response_model=QuantDuckDBBenchmarkResponse,
    responses={401: {"description": "Unauthorized", "model": ErrorResponse}, 403: {"description": "Admin access required", "model": ErrorResponse}},
    summary="Run DuckDB quant factor benchmark",
    description="Run a bounded read-only benchmark over precomputed factor rows.",
)
def run_duckdb_benchmark(
    request: QuantDuckDBBenchmarkRequest = QuantDuckDBBenchmarkRequest(),
    service: QuantDuckDBService = Depends(get_quant_duckdb_service),
    _admin: CurrentUser = Depends(require_admin_user),
) -> QuantDuckDBBenchmarkResponse:
    payload = service.benchmark_factor_query(
        symbol_limit=request.symbol_limit,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    return QuantDuckDBBenchmarkResponse.model_validate(payload)
