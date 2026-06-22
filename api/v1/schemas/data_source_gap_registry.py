# -*- coding: utf-8 -*-
"""Schemas for the read-only data source gap registry."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict


DataSourceGapStatus = Literal[
    "ready",
    "partial",
    "missing",
    "blocked",
    "unauthorized",
    "stale",
    "observation-only",
    "planned",
]
DataSourceGapAuthorityState = Literal[
    "allowed",
    "blocked",
    "unauthorized",
    "observation-only",
    "planned",
]
DataSourceGapFreshnessState = Literal[
    "fresh",
    "live",
    "delayed",
    "cached",
    "stale",
    "partial",
    "fallback",
    "synthetic",
    "unavailable",
    "unknown",
]
DataSourceSurfaceImpactState = Literal[
    "unlocked",
    "degraded",
    "observation-only",
    "blocked",
    "planned",
    "unknown",
]


class DataSourceSurfaceImpact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    surfaceKey: str
    consumerLabel: str
    impactState: DataSourceSurfaceImpactState
    impactReason: str
    affectedCapability: str
    nextEvidenceStep: str


class DataSourceGapRegistryFamily(BaseModel):
    model_config = ConfigDict(extra="forbid")

    familyKey: str
    consumerLabel: str
    status: DataSourceGapStatus
    authorityState: DataSourceGapAuthorityState
    freshnessState: DataSourceGapFreshnessState
    entitlementOrLicensingBlocker: Optional[str] = None
    integrationBlocker: Optional[str] = None
    sourceEvidenceState: str
    nextIntegrationStep: str
    providerHydrationAllowed: bool
    scoreTradingAuthorityAllowed: bool
    consumerSafeDescription: str
    surfaceImpactMatrix: List[DataSourceSurfaceImpact]


class DataSourceGapRegistrySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    totalFamilies: int
    readyCount: int
    partialCount: int
    missingCount: int
    blockedCount: int
    unauthorizedCount: int
    staleCount: int
    observationOnlyCount: int
    plannedCount: int
    providerHydrationAllowedCount: int
    scoreTradingAuthorityAllowedCount: int


class DataSourceGapRegistryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contractVersion: str
    diagnosticOnly: bool
    providerRuntimeCalled: bool
    networkCallsEnabled: bool
    scoreAuthorityAllowed: bool
    summary: DataSourceGapRegistrySummary
    families: List[DataSourceGapRegistryFamily]
    metadata: Dict[str, Any]
