# -*- coding: utf-8 -*-
"""Schemas for read-only market provider operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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


class MarketProviderOperationsResponse(BaseModel):
    generatedAt: str
    window: MarketProviderOperationsWindowModel
    summary: MarketProviderOperationsSummaryModel
    items: List[MarketProviderOperationItemModel] = Field(default_factory=list)
    eventRollups: List[MarketProviderEventRollupModel] = Field(default_factory=list)
    cacheStates: List[MarketProviderCacheStateModel] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    adminLogDrillThrough: AdminLogDrillThroughModel
    metadata: Dict[str, Any] = Field(default_factory=dict)
