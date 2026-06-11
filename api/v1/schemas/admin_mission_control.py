# -*- coding: utf-8 -*-
"""Schemas for the read-only admin mission control cockpit."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class _AdminMissionControlModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class AdminMissionControlPosture(_AdminMissionControlModel):
    landed_foundation: bool = Field(alias="landedFoundation")
    evidence_tooling_exists: bool = Field(alias="evidenceToolingExists")
    real_operator_evidence_missing: bool = Field(alias="realOperatorEvidenceMissing")
    approval_required: bool = Field(alias="approvalRequired")
    public_launch_no_go: bool = Field(alias="publicLaunchNoGo")


class AdminMissionControlSourceRef(_AdminMissionControlModel):
    kind: Literal["admin_route", "api", "doc", "test", "script", "fixture"]
    label: str
    ref: str


class AdminMissionControlDomainSlice(_AdminMissionControlModel):
    id: str
    title: str
    status: str
    status_label: str = Field(alias="statusLabel")
    summary: str
    posture: AdminMissionControlPosture
    read_only: bool = Field(default=True, alias="readOnly")
    no_external_calls: bool = Field(default=True, alias="noExternalCalls")
    live_enforcement: bool = Field(default=False, alias="liveEnforcement")
    runtime_behavior_changed: bool = Field(default=False, alias="runtimeBehaviorChanged")
    data_sources: List[str] = Field(default_factory=list, alias="dataSources")
    evidence_refs: List[AdminMissionControlSourceRef] = Field(default_factory=list, alias="evidenceRefs")
    blocker_refs: List[AdminMissionControlSourceRef] = Field(default_factory=list, alias="blockerRefs")
    approval_refs: List[AdminMissionControlSourceRef] = Field(default_factory=list, alias="approvalRefs")
    linked_admin_routes: List[str] = Field(default_factory=list, alias="linkedAdminRoutes")
    ops_status: Optional[Dict[str, Any]] = Field(default=None, alias="opsStatus")
    limitations: List[str] = Field(default_factory=list)


class AdminMissionControlSummary(_AdminMissionControlModel):
    domain_count: int = Field(alias="domainCount")
    landed_foundation_count: int = Field(alias="landedFoundationCount")
    evidence_tooling_count: int = Field(alias="evidenceToolingCount")
    real_operator_evidence_missing_count: int = Field(alias="realOperatorEvidenceMissingCount")
    approval_required_count: int = Field(alias="approvalRequiredCount")
    public_launch_no_go_count: int = Field(alias="publicLaunchNoGoCount")


class AdminMissionControlResponse(_AdminMissionControlModel):
    generated_at: str = Field(alias="generatedAt")
    read_only: bool = Field(default=True, alias="readOnly")
    no_external_calls: bool = Field(default=True, alias="noExternalCalls")
    live_enforcement: bool = Field(default=False, alias="liveEnforcement")
    runtime_behavior_changed: bool = Field(default=False, alias="runtimeBehaviorChanged")
    public_launch_approved: bool = Field(default=False, alias="publicLaunchApproved")
    release_approved: bool = Field(default=False, alias="releaseApproved")
    launch_verdict: Literal["NO_GO"] = Field(default="NO_GO", alias="launchVerdict")
    ops_snapshot_available: bool = Field(alias="opsSnapshotAvailable")
    summary: AdminMissionControlSummary
    domains: List[AdminMissionControlDomainSlice]
    posture_legend: Dict[str, str] = Field(alias="postureLegend")
    metadata: Dict[str, Any] = Field(default_factory=dict)
