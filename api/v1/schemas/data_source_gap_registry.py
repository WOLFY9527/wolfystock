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
    "not_configured",
    "observation-only",
    "planned",
]
NewsCatalystCapabilityState = Literal[
    "available",
    "missing",
    "stale",
    "not_configured",
]
NewsCatalystCapabilityScope = Literal[
    "stock",
    "market",
    "calendar",
    "macro_policy",
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
DataSourceAcquisitionBlockerType = Literal[
    "entitlement",
    "provider-integration",
    "evidence-validation",
    "schema-contract",
    "frontend-consumption",
    "protected-review",
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


class NewsCatalystCapabilityMapItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capabilityKey: str
    consumerLabel: str
    state: NewsCatalystCapabilityState
    freshnessState: DataSourceGapFreshnessState
    scope: NewsCatalystCapabilityScope
    evidenceState: str
    missingReason: str
    operatorNextAction: str


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
    capabilityMap: List[NewsCatalystCapabilityMapItem]
    surfaceImpactMatrix: List[DataSourceSurfaceImpact]
    integrationActionPlan: List[DataSourceGapRegistryActionPlanItem]


class DataSourceAcquisitionPriorityQueueItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    familyKey: str
    familyLabel: str
    priority: DataSourceGapActionPriority
    priorityReason: str
    readinessState: DataSourceGapStatus
    primaryBlockerType: DataSourceAcquisitionBlockerType
    affectedSurfaceCount: int
    blockedOrDegradedCapabilityCount: int
    externalEntitlementRequired: bool
    protectedDomainReviewRequired: bool
    nextConcreteStep: str
    requiredEvidence: List[str]
    consumerSafeWarning: str


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
    acquisitionPriorityQueue: List[DataSourceAcquisitionPriorityQueueItem]
    families: List[DataSourceGapRegistryFamily]
    metadata: Dict[str, Any]
