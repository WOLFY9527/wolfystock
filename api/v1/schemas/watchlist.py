# -*- coding: utf-8 -*-
"""User watchlist schemas."""

from __future__ import annotations

import re
from typing import List, Literal, Optional

from data_provider.base import canonical_stock_code
from pydantic import BaseModel, Field, field_validator


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
    theme_id: Optional[str] = None
    universe_type: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WatchlistItemListResponse(BaseModel):
    items: List[WatchlistItemResponse] = Field(default_factory=list)


class WatchlistDeleteResponse(BaseModel):
    deleted: int
