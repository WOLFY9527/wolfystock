# -*- coding: utf-8 -*-
"""Quant analytics API schemas."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class QuantDuckDBHealthResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    enabled: bool = False
    available: bool = False
    database_path: str = Field("", alias="databasePath")
    parquet_root: str = Field("", alias="parquetRoot")
    version: Optional[str] = None
    error: Optional[str] = None
    schema_initialized: bool = Field(False, alias="schemaInitialized")
    status: str
    engine: str = "duckdb"


class QuantDuckDBInitRequest(BaseModel):
    allow_when_disabled: bool = Field(False, alias="allowWhenDisabled")


class QuantDuckDBInitResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    engine: str = "duckdb"
    version: Optional[str] = None
    error: Optional[str] = None
    schema_initialized: bool = Field(False, alias="schemaInitialized")


class QuantDuckDBBenchmarkRequest(BaseModel):
    symbol_limit: Optional[int] = Field(None, ge=1, alias="symbolLimit")
    start_date: Optional[str] = Field(None, alias="startDate")
    end_date: Optional[str] = Field(None, alias="endDate")


class QuantDuckDBFactorSnapshotRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    symbols: list[str] = Field(default_factory=list)
    as_of_date: Optional[str] = Field(None, alias="asOfDate")
    lookback_days: Optional[int] = Field(None, ge=1, alias="lookbackDays")
    factors: Optional[list[str]] = None


class QuantDuckDBValidateFactorPathRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    symbols: list[str] = Field(default_factory=list)
    start_date: Optional[str] = Field(None, alias="startDate")
    end_date: Optional[str] = Field(None, alias="endDate")
    min_factor_rows: Optional[int] = Field(None, ge=1, alias="minFactorRows")


class QuantDuckDBCompareRuntimeContextRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    symbols: list[str] = Field(default_factory=list)
    scanner_snapshot: Optional[dict[str, Any]] = Field(None, alias="scannerSnapshot")
    backtest_snapshot: Optional[dict[str, Any]] = Field(None, alias="backtestSnapshot")
    date_range: Optional[dict[str, Any]] = Field(None, alias="dateRange")


class QuantOHLCVRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    symbol: str = Field(..., min_length=1)
    trade_date: str = Field(..., alias="tradeDate")
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: Optional[float] = None
    adj_close: Optional[float] = Field(None, alias="adjClose")
    source: Optional[str] = None
    market: Optional[str] = None


class QuantDuckDBIngestRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    symbols: Optional[list[str]] = None
    start_date: Optional[str] = Field(None, alias="startDate")
    end_date: Optional[str] = Field(None, alias="endDate")
    max_symbols: Optional[int] = Field(None, ge=1, alias="maxSymbols")
    dry_run: bool = Field(False, alias="dryRun")
    source: str = "existing_store"
    rows: Optional[list[QuantOHLCVRow]] = None

    @model_validator(mode="after")
    def validate_source_has_rows(self) -> "QuantDuckDBIngestRequest":
        if self.source == "payload" and not self.rows:
            raise ValueError("rows are required when source is payload")
        return self


class QuantDuckDBIngestResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    engine: str = "duckdb"
    source: Optional[str] = None
    ingested_rows: int = Field(0, alias="ingestedRows")
    available_rows: int = Field(0, alias="availableRows")
    symbol_count: int = Field(0, alias="symbolCount")
    symbols_requested: int = Field(0, alias="symbolsRequested")
    start_date: Optional[str] = Field(None, alias="startDate")
    end_date: Optional[str] = Field(None, alias="endDate")
    duration_ms: float = Field(0.0, alias="durationMs")
    error: Optional[str] = None


class QuantDuckDBBuildFactorsRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    symbols: Optional[list[str]] = None
    start_date: Optional[str] = Field(None, alias="startDate")
    end_date: Optional[str] = Field(None, alias="endDate")


class QuantDuckDBBuildFactorsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    engine: str = "duckdb"
    ohlcv_rows: int = Field(0, alias="ohlcvRows")
    factor_rows: int = Field(0, alias="factorRows")
    factor_count: int = Field(0, alias="factorCount")
    duration_ms: float = Field(0.0, alias="durationMs")
    error: Optional[str] = None


class QuantDuckDBFactorCoverageSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    requested_symbols: int = Field(0, alias="requestedSymbols")
    covered_symbols: int = Field(0, alias="coveredSymbols")
    missing_symbols: int = Field(0, alias="missingSymbols")
    sufficient_symbols: int = Field(0, alias="sufficientSymbols")
    row_count: int = Field(0, alias="rowCount")
    min_factor_date: Optional[str] = Field(None, alias="minFactorDate")
    max_factor_date: Optional[str] = Field(None, alias="maxFactorDate")


class QuantDuckDBFactorSnapshotRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    symbol: str
    trade_date: Optional[str] = Field(None, alias="tradeDate")
    factors: dict[str, Optional[float]] = Field(default_factory=dict)
    factor_trend: Optional[str] = Field(None, alias="factorTrend")
    factor_momentum: Optional[str] = Field(None, alias="factorMomentum")
    factor_data_mode: str = Field("empty", alias="factorDataMode")
    factor_warnings: list[str] = Field(default_factory=list, alias="factorWarnings")


class QuantDuckDBFactorSnapshotResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    engine: str = "duckdb"
    data_mode: str = Field("empty", alias="dataMode")
    duration_ms: float = Field(0.0, alias="durationMs")
    row_count: int = Field(0, alias="rowCount")
    coverage: QuantDuckDBFactorCoverageSummary = Field(default_factory=QuantDuckDBFactorCoverageSummary)
    factor_dates: list[str] = Field(default_factory=list, alias="factorDates")
    missing_symbols: list[str] = Field(default_factory=list, alias="missingSymbols")
    factors: list[str] = Field(default_factory=list)
    snapshots: list[QuantDuckDBFactorSnapshotRow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: Optional[str] = None


class QuantDuckDBValidateFactorPathResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    engine: str = "duckdb"
    data_mode: str = Field("empty", alias="dataMode")
    duration_ms: float = Field(0.0, alias="durationMs")
    row_count: int = Field(0, alias="rowCount")
    coverage: QuantDuckDBFactorCoverageSummary = Field(default_factory=QuantDuckDBFactorCoverageSummary)
    factor_dates: list[str] = Field(default_factory=list, alias="factorDates")
    missing_symbols: list[str] = Field(default_factory=list, alias="missingSymbols")
    insufficient_symbols: list[str] = Field(default_factory=list, alias="insufficientSymbols")
    warnings: list[str] = Field(default_factory=list)
    error: Optional[str] = None


class QuantDuckDBCompareRuntimeContextResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    engine: str = "duckdb"
    data_mode: str = Field("empty", alias="dataMode")
    duration_ms: float = Field(0.0, alias="durationMs")
    runtime_contexts: list[str] = Field(default_factory=list, alias="runtimeContexts")
    coverage: QuantDuckDBFactorCoverageSummary = Field(default_factory=QuantDuckDBFactorCoverageSummary)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    snapshots: list[QuantDuckDBFactorSnapshotRow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: Optional[str] = None


class QuantDuckDBCoverageSymbol(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    symbol: str
    ohlcv_rows: int = Field(0, alias="ohlcvRows")
    min_trade_date: Optional[str] = Field(None, alias="minTradeDate")
    max_trade_date: Optional[str] = Field(None, alias="maxTradeDate")
    factor_rows: int = Field(0, alias="factorRows")
    latest_factor_date: Optional[str] = Field(None, alias="latestFactorDate")


class QuantDuckDBCoverageResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    engine: str = "duckdb"
    enabled: bool = False
    database_path: str = Field("", alias="databasePath")
    total_ohlcv_rows: int = Field(0, alias="totalOhlcvRows")
    total_factor_rows: int = Field(0, alias="totalFactorRows")
    symbol_count: int = Field(0, alias="symbolCount")
    min_trade_date: Optional[str] = Field(None, alias="minTradeDate")
    max_trade_date: Optional[str] = Field(None, alias="maxTradeDate")
    latest_factor_date: Optional[str] = Field(None, alias="latestFactorDate")
    symbols: list[QuantDuckDBCoverageSymbol] = Field(default_factory=list)
    empty_reason: Optional[str] = Field(None, alias="emptyReason")
    error: Optional[str] = None


class QuantDuckDBBenchmarkTopResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    symbol: str
    trade_date: Optional[str] = Field(None, alias="tradeDate")
    close: Optional[float] = None
    return_1d: Optional[float] = Field(None, alias="return1d")
    ma20: Optional[float] = None
    momentum_20d: Optional[float] = Field(None, alias="momentum20d")
    volatility_20d: Optional[float] = Field(None, alias="volatility20d")
    close_vs_ma20: Optional[float] = Field(None, alias="closeVsMa20")
    factor_score: Optional[float] = Field(None, alias="factorScore")


class QuantDuckDBBenchmarkResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    engine: str = "duckdb"
    elapsed_ms: float = Field(0.0, alias="elapsedMs")
    duration_ms: float = Field(0.0, alias="durationMs")
    ohlcv_rows: int = Field(0, alias="ohlcvRows")
    factor_rows: int = Field(0, alias="factorRows")
    rows_scanned: int = Field(0, alias="rowsScanned")
    symbols_scanned: int = Field(0, alias="symbolsScanned")
    symbol_count: int = Field(0, alias="symbolCount")
    date_count: int = Field(0, alias="dateCount")
    factor_count: int = Field(0, alias="factorCount")
    query_type: str = Field("factor_daily_top_scores", alias="queryType")
    data_mode: str = Field("empty", alias="dataMode")
    start_date: Optional[str] = Field(None, alias="startDate")
    end_date: Optional[str] = Field(None, alias="endDate")
    top_results: list[QuantDuckDBBenchmarkTopResult] = Field(default_factory=list, alias="topResults")
    error: Optional[str] = None
