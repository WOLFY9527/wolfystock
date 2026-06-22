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
DataSourceGapActionType = Literal[
    "provider-entitlement",
    "provider-integration",
    "evidence-validation",
    "schema-contract",
    "frontend-consumption",
    "manual-review",
    "blocked",
]
DataSourceGapActionPriority = Literal["critical", "high", "medium", "low"]
DataSourceGapActionStatus = Literal[
    "ready-to-start",
    "blocked",
    "waiting-entitlement",
    "waiting-evidence",
    "planned",
    "not-required",
]


class DataSourceSurfaceImpact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    surfaceKey: str
    consumerLabel: str
    impactState: DataSourceSurfaceImpactState
    impactReason: str
    affectedCapability: str
    nextEvidenceStep: str


class DataSourceGapRegistryActionPlanItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actionKey: str
    actionLabel: str
    actionType: DataSourceGapActionType
    priority: DataSourceGapActionPriority
    status: DataSourceGapActionStatus
    reason: str
    requiredEvidence: List[str]
    blockedBy: List[str]
    affectedSurfacesOrCapabilities: List[str]
    nextConcreteStep: str
    requiresExternalProviderLicenseWork: bool
    requiresProtectedDomainReview: bool


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
    integrationActionPlan: List[DataSourceGapRegistryActionPlanItem]


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
