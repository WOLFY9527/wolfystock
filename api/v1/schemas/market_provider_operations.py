# -*- coding: utf-8 -*-
"""Schemas for read-only market provider operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

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


class UsOhlcvCacheRefreshRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    symbols: List[str] = Field(default_factory=list)
    tier: str = "starter"
    execute: bool = False
    max_symbols: int = Field(default=5, ge=1, le=100, alias="maxSymbols")
    required_bars: int = Field(default=60, ge=1, le=1000, alias="requiredBars")
    require_adjusted: bool = Field(default=True, alias="requireAdjusted")


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
