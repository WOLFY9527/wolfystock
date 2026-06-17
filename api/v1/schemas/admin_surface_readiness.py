# -*- coding: utf-8 -*-
"""Schemas for the read-only backend surface contract parity gate."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class _AdminSurfaceReadinessModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class BackendSurfaceRouteSummary(_AdminSurfaceReadinessModel):
    method: str
    path: str
    exists: bool = True
    response_model: Optional[str] = Field(default=None, alias="responseModel")
    typed_contract: bool = Field(default=False, alias="typedContract")


class BackendSurfaceReadinessItem(_AdminSurfaceReadinessModel):
    surface_key: str = Field(alias="surfaceKey")
    label: str
    status: str
    route_status: str = Field(alias="routeStatus")
    primary_route: BackendSurfaceRouteSummary = Field(alias="primaryRoute")
    related_routes: List[BackendSurfaceRouteSummary] = Field(default_factory=list, alias="relatedRoutes")
    auth_requirement: Dict[str, str] = Field(alias="authRequirement")
    contract: Optional[str] = None
    schema_version_status: str = Field(alias="schemaVersionStatus")
    observation_boundary_status: str = Field(alias="observationBoundaryStatus")
    degraded_state_shape_status: str = Field(alias="degradedStateShapeStatus")
    consumer_safe_issue_labels_status: str = Field(alias="consumerSafeIssueLabelsStatus")
    contract_status: str = Field(default="not_applicable", alias="contractStatus")
    synthesis_contract_status: str = Field(default="not_applicable", alias="synthesisContractStatus")
    implementation_status: str = Field(alias="implementationStatus")
    gaps: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class BackendSurfaceReadinessResponse(_AdminSurfaceReadinessModel):
    generated_at: str = Field(alias="generatedAt")
    read_only: bool = Field(default=True, alias="readOnly")
    no_external_calls: bool = Field(default=True, alias="noExternalCalls")
    live_enforcement: bool = Field(default=False, alias="liveEnforcement")
    runtime_behavior_changed: bool = Field(default=False, alias="runtimeBehaviorChanged")
    consumer_visible: bool = Field(default=False, alias="consumerVisible")
    surfaces: List[BackendSurfaceReadinessItem]
    summary: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
