# -*- coding: utf-8 -*-
"""Schemas for read-only market provider operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.schemas.trust_evidence import TrustEvidenceSnapshotV1


class MarketProviderOperationsWindowModel(BaseModel):
    key: str = "24h"
    since: Optional[str] = None


class AdminLogDrillThroughModel(BaseModel):
    label: str = "查看 Admin Logs"
    route: str = "/zh/admin/logs"
    query: Dict[str, str] = Field(default_factory=dict)
    eventId: Optional[str] = None


class MarketProviderOperationsSummaryModel(BaseModel):
    totalItems: int = 0
    liveCount: int = 0
    cacheCount: int = 0
    staleCount: int = 0
    fallbackCount: int = 0
    partialCount: int = 0
    unavailableCount: int = 0
    errorCount: int = 0
    refreshingCount: int = 0
    eventCount: int = 0
    failureCount: int = 0
    fallbackEventCount: int = 0
    staleEventCount: int = 0
    slowEventCount: int = 0


class MarketProviderOperationItemModel(BaseModel):
    provider: str = "unknown"
    sourceLabel: Optional[str] = None
    sourceType: Optional[str] = None
    domain: str
    endpoint: str
    card: str
    cacheKey: str
    status: str
    freshness: Optional[str] = None
    asOf: Optional[str] = None
    updatedAt: Optional[str] = None
    lastSuccessfulAt: Optional[str] = None
    lastKnownGoodAgeMinutes: Optional[int] = None
    latencyMs: Optional[float] = None
    isFallback: bool = False
    isStale: bool = False
    isRefreshing: bool = False
    isFromSnapshot: bool = False
    fallbackUsed: bool = False
    warning: Optional[str] = None
    errorSummary: Optional[str] = None
    trustEvidence: Optional[TrustEvidenceSnapshotV1] = None
    adminLogDrillThrough: AdminLogDrillThroughModel


class MarketProviderEventRollupModel(BaseModel):
    provider: str = "unknown"
    endpoint: Optional[str] = None
    card: Optional[str] = None
    category: Optional[str] = None
    eventCount: int = 0
    failureCount: int = 0
    fallbackCount: int = 0
    staleServedCount: int = 0
    slowCount: int = 0
    failureRate: float = 0
    topReasons: List[str] = Field(default_factory=list)
    latestLogEventId: Optional[str] = None
    latestStartedAt: Optional[str] = None
    adminLogDrillThrough: AdminLogDrillThroughModel


class MarketProviderCacheStateModel(BaseModel):
    cacheKey: str
    ttlSeconds: Optional[int] = None
    fetchedAt: Optional[str] = None
    expiresAt: Optional[str] = None
    isFresh: Optional[bool] = None
    isRefreshing: bool = False
    lastError: Optional[str] = None
    persistentSnapshotAvailable: bool = False
    persistentSnapshotAgeMinutes: Optional[int] = None
    status: str = "unavailable"


class MarketCacheEventSummaryCountsModel(BaseModel):
    hits: int = 0
    misses: int = 0
    staleServed: int = 0
    coldFallbacks: int = 0
    refreshStarted: int = 0
    refreshCompleted: int = 0
    refreshFailed: int = 0


class MarketCacheEventSummaryMetadataModel(BaseModel):
    countersSource: str = "process_local"
    readOnly: bool = True
    externalProviderCalls: bool = False
    cacheMutation: bool = False
    exactness: str = "observational_not_billing"
    durability: str = "process_local_not_durable"


class MarketCacheEventSummaryPanelModel(MarketCacheEventSummaryCountsModel):
    panelKey: str = "unknown"
    endpointFamily: str = "unknown"


class MarketCacheEventSummaryModel(BaseModel):
    metadata: MarketCacheEventSummaryMetadataModel
    totals: MarketCacheEventSummaryCountsModel
    byPanelKey: List[MarketCacheEventSummaryPanelModel] = Field(default_factory=list)


class MarketProviderOperationsResponse(BaseModel):
    generatedAt: str
    window: MarketProviderOperationsWindowModel
    summary: MarketProviderOperationsSummaryModel
    items: List[MarketProviderOperationItemModel] = Field(default_factory=list)
    eventRollups: List[MarketProviderEventRollupModel] = Field(default_factory=list)
    marketCacheEventSummary: Optional[MarketCacheEventSummaryModel] = None
    cacheStates: List[MarketProviderCacheStateModel] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    adminLogDrillThrough: AdminLogDrillThroughModel
    metadata: Dict[str, Any] = Field(default_factory=dict)


_US_OHLCV_REFRESH_UNIVERSE_ALIASES = {
    "0": "starter",
    "starter": "starter",
    "tier0": "starter",
    "tier_0": "starter",
    "tier-0": "starter",
    "1": "tier1",
    "tier1": "tier1",
    "tier_1": "tier1",
    "tier-1": "tier1",
    "configured_tier1": "tier1",
    "configured-tier1": "tier1",
}
_US_OHLCV_REFRESH_TARGET_ALIASES = {
    "symbols": "symbols",
    **_US_OHLCV_REFRESH_UNIVERSE_ALIASES,
}


def _normalize_optional_contract_label(value: Optional[str]) -> Optional[str]:
    normalized = str(value or "").strip().lower()
    return normalized or None


class UsOhlcvCacheRefreshRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "summary": "Explicit symbols dry-run",
                    "value": {
                        "symbols": ["TSLA", "NVDA"],
                        "execute": False,
                        "dryRun": True,
                        "maxSymbols": 2,
                    },
                },
                {
                    "summary": "Starter universe dry-run",
                    "value": {
                        "universe": "starter",
                        "execute": False,
                        "dryRun": True,
                        "maxSymbols": 2,
                    },
                },
                {
                    "summary": "Configured tier1 dry-run",
                    "value": {
                        "target": "tier1",
                        "execute": False,
                        "dryRun": True,
                        "maxSymbols": 5,
                    },
                },
                {
                    "summary": "Explicit bounded execution",
                    "value": {
                        "target": "symbols",
                        "symbols": ["TSLA", "NVDA"],
                        "execute": True,
                        "dryRun": False,
                        "maxSymbols": 2,
                    },
                },
            ]
        },
    )

    symbols: List[str] = Field(
        default_factory=list,
        description="Explicit US symbols to plan or refresh, for example ['TSLA', 'NVDA'].",
    )
    target: Optional[str] = Field(
        default=None,
        description="Operator-friendly target: 'symbols', 'starter', or 'tier1'.",
    )
    universe: Optional[str] = Field(
        default=None,
        description="Universe shortcut when symbols are omitted: 'starter' or 'tier1'.",
    )
    tier: str = Field(
        default="starter",
        description="Compatibility universe selector. Prefer 'universe' or 'target' for new callers.",
    )
    execute: bool = Field(
        default=False,
        description="Must be true to run provider calls and cache writes. Omitted or false plans only.",
    )
    dry_run: Optional[bool] = Field(
        default=None,
        alias="dryRun",
        description="Optional clarity flag. true means plan only; false is valid only with execute=true.",
    )
    max_symbols: int = Field(
        default=5,
        ge=1,
        le=100,
        alias="maxSymbols",
        description="Maximum missing/stale symbols to execute when execute=true.",
    )
    required_bars: int = Field(
        default=60,
        ge=1,
        le=1000,
        alias="requiredBars",
        description="Required usable daily bars for each symbol before refresh is skipped.",
    )
    require_adjusted: bool = Field(
        default=True,
        alias="requireAdjusted",
        description="Require adjusted close availability when deciding whether cached data is usable.",
    )

    @model_validator(mode="after")
    def validate_operator_contract(self) -> "UsOhlcvCacheRefreshRequest":
        self.target = _normalize_optional_contract_label(self.target)
        self.universe = _normalize_optional_contract_label(self.universe)
        self.tier = _normalize_optional_contract_label(self.tier) or "starter"

        if self.target is not None and self.target not in _US_OHLCV_REFRESH_TARGET_ALIASES:
            raise ValueError("target must be one of: symbols, starter, tier1")
        if self.universe is not None and self.universe not in _US_OHLCV_REFRESH_UNIVERSE_ALIASES:
            raise ValueError("universe must be one of: starter, tier1")
        if self.tier not in _US_OHLCV_REFRESH_UNIVERSE_ALIASES:
            raise ValueError("tier must be one of: starter, tier1")
        if self.target == "symbols" and not self.symbols:
            raise ValueError("target=symbols requires at least one symbol")
        if self.target == "symbols" and self.universe is not None:
            raise ValueError("target=symbols cannot be combined with universe")
        if self.dry_run is True and self.execute:
            raise ValueError("dryRun=true conflicts with execute=true; use dryRun=false for explicit execution")
        if self.dry_run is False and not self.execute:
            raise ValueError("dryRun=false requires execute=true; dryRun=false alone cannot execute writes")
        return self

    def resolved_tier(self) -> str:
        for value in (self.universe, self.target, self.tier):
            resolved = _US_OHLCV_REFRESH_UNIVERSE_ALIASES.get(str(value or ""))
            if resolved:
                return resolved
        return "starter"


class UsOhlcvCacheRefreshResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    contractVersion: str
    dryRun: bool
    execute: bool
    target: Dict[str, Any]
    requestedSymbols: List[str] = Field(default_factory=list)
    normalizedSymbols: List[str] = Field(default_factory=list)
    alreadyAvailableSymbols: List[str] = Field(default_factory=list)
    missingOrStaleSymbols: List[str] = Field(default_factory=list)
    skippedSymbols: List[Dict[str, Any]] = Field(default_factory=list)
    estimatedMaxProviderCalls: int = 0
    writeTarget: str
    refreshPolicy: Dict[str, Any]
    providerPolicy: Dict[str, Any]
    writePolicy: Dict[str, Any]
    plan: Dict[str, Any]
    results: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any]
    consumerSafe: bool = True
