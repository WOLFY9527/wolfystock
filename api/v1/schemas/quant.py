# -*- coding: utf-8 -*-
"""Quant analytics API schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


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


class QuantDuckDBBenchmarkResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    engine: str = "duckdb"
    elapsed_ms: float = Field(0.0, alias="elapsedMs")
    ohlcv_rows: int = Field(0, alias="ohlcvRows")
    factor_rows: int = Field(0, alias="factorRows")
    symbol_count: int = Field(0, alias="symbolCount")
    date_count: int = Field(0, alias="dateCount")
    factor_count: int = Field(0, alias="factorCount")
    error: Optional[str] = None
