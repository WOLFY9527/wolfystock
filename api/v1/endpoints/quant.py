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
    QuantDuckDBBuildFactorsRequest,
    QuantDuckDBBuildFactorsResponse,
    QuantDuckDBCompareRuntimeContextRequest,
    QuantDuckDBCompareRuntimeContextResponse,
    QuantDuckDBCoverageResponse,
    QuantDuckDBFactorSnapshotRequest,
    QuantDuckDBFactorSnapshotResponse,
    QuantDuckDBHealthResponse,
    QuantDuckDBIngestRequest,
    QuantDuckDBIngestResponse,
    QuantDuckDBInitRequest,
    QuantDuckDBInitResponse,
    QuantDuckDBValidateFactorPathRequest,
    QuantDuckDBValidateFactorPathResponse,
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
    "/duckdb/ingest-ohlcv",
    response_model=QuantDuckDBIngestResponse,
    responses={401: {"description": "Unauthorized", "model": ErrorResponse}, 403: {"description": "Admin access required", "model": ErrorResponse}},
    summary="Ingest bounded OHLCV rows into DuckDB",
    description="Explicitly ingest normalized payload rows or bounded local StockDaily rows into the optional DuckDB quant store.",
)
def ingest_duckdb_ohlcv(
    request: QuantDuckDBIngestRequest = QuantDuckDBIngestRequest(),
    service: QuantDuckDBService = Depends(get_quant_duckdb_service),
    _admin: CurrentUser = Depends(require_admin_user),
) -> QuantDuckDBIngestResponse:
    if request.source == "payload":
        rows = [row.model_dump(by_alias=True) for row in request.rows or []]
        payload = service.ingest_ohlcv(rows)
        payload.setdefault("source", "payload")
    else:
        payload = service.ingest_ohlcv_from_existing_store(
            symbols=request.symbols,
            start_date=request.start_date,
            end_date=request.end_date,
            max_symbols=request.max_symbols,
            dry_run=request.dry_run,
        )
    return QuantDuckDBIngestResponse.model_validate(payload)


@router.post(
    "/duckdb/build-factors",
    response_model=QuantDuckDBBuildFactorsResponse,
    responses={401: {"description": "Unauthorized", "model": ErrorResponse}, 403: {"description": "Admin access required", "model": ErrorResponse}},
    summary="Build basic DuckDB daily factors",
    description="Build conservative factor_daily rows from already-ingested ohlcv_daily rows.",
)
def build_duckdb_factors(
    request: QuantDuckDBBuildFactorsRequest = QuantDuckDBBuildFactorsRequest(),
    service: QuantDuckDBService = Depends(get_quant_duckdb_service),
    _admin: CurrentUser = Depends(require_admin_user),
) -> QuantDuckDBBuildFactorsResponse:
    payload = service.build_basic_factors(
        symbols=request.symbols,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    return QuantDuckDBBuildFactorsResponse.model_validate(payload)


@router.post(
    "/duckdb/factor-snapshot",
    response_model=QuantDuckDBFactorSnapshotResponse,
    responses={401: {"description": "Unauthorized", "model": ErrorResponse}, 403: {"description": "Admin access required", "model": ErrorResponse}},
    summary="Read DuckDB factor snapshots for validation",
    description="Return read-only factor_daily snapshots for explicit scanner/backtest validation context.",
)
def get_duckdb_factor_snapshot(
    request: QuantDuckDBFactorSnapshotRequest = QuantDuckDBFactorSnapshotRequest(),
    service: QuantDuckDBService = Depends(get_quant_duckdb_service),
    _admin: CurrentUser = Depends(require_admin_user),
) -> QuantDuckDBFactorSnapshotResponse:
    payload = service.get_factor_snapshot(
        symbols=request.symbols,
        as_of_date=request.as_of_date,
        lookback_days=request.lookback_days,
        factors=request.factors,
    )
    return QuantDuckDBFactorSnapshotResponse.model_validate(payload)


@router.post(
    "/duckdb/validate-factor-path",
    response_model=QuantDuckDBValidateFactorPathResponse,
    responses={401: {"description": "Unauthorized", "model": ErrorResponse}, 403: {"description": "Admin access required", "model": ErrorResponse}},
    summary="Validate optional DuckDB factor path coverage",
    description="Report read-only factor_daily coverage diagnostics without changing scanner or backtest runtime behavior.",
)
def validate_duckdb_factor_path(
    request: QuantDuckDBValidateFactorPathRequest = QuantDuckDBValidateFactorPathRequest(),
    service: QuantDuckDBService = Depends(get_quant_duckdb_service),
    _admin: CurrentUser = Depends(require_admin_user),
) -> QuantDuckDBValidateFactorPathResponse:
    payload = service.validate_factor_coverage(
        symbols=request.symbols,
        start_date=request.start_date,
        end_date=request.end_date,
        min_factor_rows=request.min_factor_rows,
    )
    return QuantDuckDBValidateFactorPathResponse.model_validate(payload)


@router.post(
    "/duckdb/compare-runtime-context",
    response_model=QuantDuckDBCompareRuntimeContextResponse,
    responses={401: {"description": "Unauthorized", "model": ErrorResponse}, 403: {"description": "Admin access required", "model": ErrorResponse}},
    summary="Compare runtime context with DuckDB factors",
    description="Return diagnostics comparing caller-provided scanner/backtest context to optional factor_daily coverage.",
)
def compare_duckdb_runtime_context(
    request: QuantDuckDBCompareRuntimeContextRequest = QuantDuckDBCompareRuntimeContextRequest(),
    service: QuantDuckDBService = Depends(get_quant_duckdb_service),
    _admin: CurrentUser = Depends(require_admin_user),
) -> QuantDuckDBCompareRuntimeContextResponse:
    payload = service.compare_factor_context(
        symbols=request.symbols,
        scanner_snapshot=request.scanner_snapshot,
        backtest_snapshot=request.backtest_snapshot,
        date_range=request.date_range,
    )
    return QuantDuckDBCompareRuntimeContextResponse.model_validate(payload)


@router.get(
    "/duckdb/coverage",
    response_model=QuantDuckDBCoverageResponse,
    responses={401: {"description": "Unauthorized", "model": ErrorResponse}, 403: {"description": "Admin access required", "model": ErrorResponse}},
    summary="Get DuckDB quant data coverage",
    description="Report OHLCV/factor rows, symbol counts, date ranges, and a bounded per-symbol coverage sample.",
)
def get_duckdb_coverage(
    service: QuantDuckDBService = Depends(get_quant_duckdb_service),
    _admin: CurrentUser = Depends(require_admin_user),
) -> QuantDuckDBCoverageResponse:
    payload = service.get_coverage()
    return QuantDuckDBCoverageResponse.model_validate(payload)


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
