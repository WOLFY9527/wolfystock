# -*- coding: utf-8 -*-
"""User watchlist schemas."""

from __future__ import annotations

import re
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator
from src.utils.symbol_normalization import canonical_stock_code


class WatchlistItemCreateRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16)
    market: Literal["cn", "hk", "us"] = "cn"
    name: Optional[str] = Field(None, max_length=128)
    source: Literal["scanner"] = "scanner"
    scanner_run_id: Optional[int] = None
    scanner_rank: Optional[int] = Field(None, ge=1)
    scanner_score: Optional[float] = Field(None, ge=0, le=100)
    theme_id: Optional[str] = Field(None, max_length=64)
    universe_type: Optional[str] = Field(None, max_length=32)
    notes: Optional[str] = Field(None, max_length=500)

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        normalized = canonical_stock_code(value).strip().upper()
        if not normalized:
            raise ValueError("symbol is required")
        if len(normalized) > 16:
            raise ValueError("symbol must be at most 16 characters")
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]*", normalized):
            raise ValueError("symbol contains invalid characters")
        return normalized

    @field_validator("name", "theme_id", "universe_type", "notes")
    @classmethod
    def _normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        normalized = str(value or "").strip()
        return normalized or None

    @field_validator("market")
    @classmethod
    def _normalize_market(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"cn", "hk", "us"}:
            raise ValueError("market must be one of: cn, hk, us")
        return normalized


class WatchlistItemResponse(BaseModel):
    id: int
    symbol: str
    market: str
    name: Optional[str] = None
    source: str
    scanner_run_id: Optional[int] = None
    scanner_rank: Optional[int] = None
    scanner_score: Optional[float] = None
    last_scored_at: Optional[str] = None
    score_source: Optional[str] = None
    score_profile: Optional[str] = None
    score_reason: Optional[str] = None
    score_status: Optional[str] = None
    score_error: Optional[str] = None
    theme_id: Optional[str] = None
    universe_type: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    intelligence: Optional["WatchlistIntelligenceResponse"] = None


class WatchlistScannerIntelligenceResponse(BaseModel):
    last_score: Optional[float] = None
    last_rank: Optional[int] = None
    status: str = "unknown"
    theme: Optional[str] = None
    theme_label: Optional[str] = None
    profile: Optional[str] = None
    reason: Optional[str] = None
    last_scanned_at: Optional[str] = None


class WatchlistStrategySimulationIntelligenceResponse(BaseModel):
    lookback_days: Optional[int] = None
    forward_days: Optional[int] = None
    avg_forward_return_pct: Optional[float] = None
    hit_rate: Optional[float] = None
    avg_excess_return_pct: Optional[float] = None
    selection_count: Optional[int] = None
    data_coverage: Optional[float] = None
    status: str = "unknown"


class WatchlistBacktestIntelligenceResponse(BaseModel):
    last_result_id: Optional[int] = None
    total_return_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    sharpe: Optional[float] = None
    trade_count: Optional[int] = None
    tested_at: Optional[str] = None


class WatchlistIntelligenceResponse(BaseModel):
    scanner: WatchlistScannerIntelligenceResponse = Field(default_factory=WatchlistScannerIntelligenceResponse)
    strategy_simulation: WatchlistStrategySimulationIntelligenceResponse = Field(default_factory=WatchlistStrategySimulationIntelligenceResponse)
    backtest: WatchlistBacktestIntelligenceResponse = Field(default_factory=WatchlistBacktestIntelligenceResponse)


class WatchlistItemListResponse(BaseModel):
    items: List[WatchlistItemResponse] = Field(default_factory=list)


class WatchlistDeleteResponse(BaseModel):
    deleted: int


class WatchlistScoreRefreshRequest(BaseModel):
    market: Optional[Literal["cn", "hk", "us"]] = None
    source: Optional[Literal["scanner"]] = None
    theme: Optional[str] = Field(None, max_length=64)
    symbols: Optional[List[str]] = None
    force: bool = False

    @field_validator("symbols")
    @classmethod
    def _normalize_symbols(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None
        normalized: List[str] = []
        seen = set()
        for item in value:
            symbol = canonical_stock_code(item).strip().upper()
            if not symbol:
                continue
            if len(symbol) > 16:
                raise ValueError("symbol must be at most 16 characters")
            if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]*", symbol):
                raise ValueError("symbol contains invalid characters")
            if symbol not in seen:
                seen.add(symbol)
                normalized.append(symbol)
        return normalized

    @field_validator("theme")
    @classmethod
    def _normalize_theme(cls, value: Optional[str]) -> Optional[str]:
        normalized = str(value or "").strip()
        return normalized or None


class WatchlistScoreRefreshResult(BaseModel):
    symbol: str
    market: str
    status: str
    message: Optional[str] = None
    score: Optional[float] = None
    rank: Optional[int] = None
    scanner_run_id: Optional[int] = None


class WatchlistScoreRefreshResponse(BaseModel):
    ok: bool
    updated_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    started_at: str
    completed_at: str
    markets: List[str] = Field(default_factory=list)
    results: List[WatchlistScoreRefreshResult] = Field(default_factory=list)


class WatchlistScoreRefreshStatusResponse(BaseModel):
    enabled: bool
    us_time: str
    cn_time: str
    hk_time: str
    max_symbols: int
    running: bool = False
