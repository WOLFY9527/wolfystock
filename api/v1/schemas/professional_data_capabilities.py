# -*- coding: utf-8 -*-
"""Schemas for professional data capability readiness."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict


ProfessionalDataCapabilityStatus = Literal[
    "live",
    "degraded",
    "entitlement_required",
    "configured_missing",
    "not_implemented",
]

ProfessionalDataCapabilityCategory = Literal[
    "options_structure",
    "market_breadth_flows",
    "sector_rotation",
    "macro_cross_asset_regime",
    "stock_research_data",
    "backtest_data_availability",
]


class ProfessionalDataCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capabilityId: str
    label: str
    category: ProfessionalDataCapabilityCategory
    status: ProfessionalDataCapabilityStatus
    freshness: str
    sourceLabel: str
    reason: str
    earningsCalendarReadiness: Dict[str, Any] | None = None
    readiness: Optional[Dict[str, Any]] = None


class ProfessionalDataCapabilitySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    totalCapabilities: int
    liveCount: int
    degradedCount: int
    entitlementRequiredCount: int
    configuredMissingCount: int
    notImplementedCount: int


class ProfessionalDataCapabilityRegistryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contractVersion: str
    consumerSafe: bool
    summary: ProfessionalDataCapabilitySummary
    categories: List[ProfessionalDataCapabilityCategory]
    capabilities: List[ProfessionalDataCapability]


class ProfessionalDataCapabilityAdminItem(ProfessionalDataCapability):
    model_config = ConfigDict(extra="forbid")

    adminDiagnostics: Dict[str, Any]


class ProfessionalDataCapabilityRegistryAdminResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contractVersion: str
    consumerSafe: bool
    summary: ProfessionalDataCapabilitySummary
    categories: List[ProfessionalDataCapabilityCategory]
    capabilities: List[ProfessionalDataCapabilityAdminItem]
    macroReadiness: Dict[str, Any]
