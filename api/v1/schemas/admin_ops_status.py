# -*- coding: utf-8 -*-
"""Schemas for read-only admin ops status snapshots."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class _AdminOpsStatusModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class AdminOpsStatusSection(_AdminOpsStatusModel):
    available: bool = False
    status: str = "unavailable"
    service: str = ""
    configured: bool = False
    last_checked_at: Optional[str] = Field(default=None, alias="lastCheckedAt")
    message: str = ""
    label: str = "advisory"
    reason_code: Optional[str] = Field(default=None, alias="reasonCode")
    read_only: bool = Field(default=True, alias="readOnly")
    no_external_calls: bool = Field(default=True, alias="noExternalCalls")
    advisory_only: bool = Field(default=True, alias="advisoryOnly")
    live_enforcement: bool = Field(default=False, alias="liveEnforcement")
    enforcement_enabled: bool = Field(default=False, alias="enforcementEnabled")
    runtime_behavior_changed: bool = Field(default=False, alias="runtimeBehaviorChanged")
    consumer_visible: bool = Field(default=False, alias="consumerVisible")
    provider_behavior_changed: bool = Field(default=False, alias="providerBehaviorChanged")
    market_cache_behavior_changed: bool = Field(default=False, alias="marketCacheBehaviorChanged")
    delete_allowed: bool = Field(default=False, alias="deleteAllowed")
    data_sources: List[str] = Field(default_factory=list, alias="dataSources")
    summary: Dict[str, Any] = Field(default_factory=dict)
    limitations: List[str] = Field(default_factory=list)


class AdminOpsAdvisoryVsEnforcement(_AdminOpsStatusModel):
    label: str = "advisory_snapshot"
    enforcement_label: str = Field(default="not_launch_control", alias="enforcementLabel")
    source_unavailable_behavior: str = Field(default="degrade_to_unavailable", alias="sourceUnavailableBehavior")
    read_only: bool = Field(default=True, alias="readOnly")
    no_external_calls: bool = Field(default=True, alias="noExternalCalls")
    live_enforcement: bool = Field(default=False, alias="liveEnforcement")
    runtime_behavior_changed: bool = Field(default=False, alias="runtimeBehaviorChanged")
    consumer_visible: bool = Field(default=False, alias="consumerVisible")


class AdminOpsCockpitFollowUpProposal(_AdminOpsStatusModel):
    proposal_key: str = Field(alias="proposalKey")
    title: str
    approval_needed: bool = Field(default=True, alias="approvalNeeded")
    likely_files: List[str] = Field(default_factory=list, alias="likelyFiles")
    risk: str
    validation: List[str] = Field(default_factory=list)


class AdminOpsCockpitDomain(_AdminOpsStatusModel):
    domain_key: str = Field(alias="domainKey")
    label: str
    status: str
    status_label: str = Field(alias="statusLabel")
    detail_route: str = Field(alias="detailRoute")
    foundation_landed: bool = Field(alias="foundationLanded")
    evidence_tooling_present: bool = Field(alias="evidenceToolingPresent")
    real_operator_evidence_missing: bool = Field(alias="realOperatorEvidenceMissing")
    approval_required: bool = Field(default=True, alias="approvalRequired")
    public_launch_no_go: bool = Field(default=True, alias="publicLaunchNoGo")
    read_only: bool = Field(default=True, alias="readOnly")
    advisory_only: bool = Field(default=True, alias="advisoryOnly")
    no_external_calls: bool = Field(default=True, alias="noExternalCalls")
    live_enforcement: bool = Field(default=False, alias="liveEnforcement")
    runtime_behavior_changed: bool = Field(default=False, alias="runtimeBehaviorChanged")
    provider_runtime_changed: bool = Field(default=False, alias="providerRuntimeChanged")
    external_actions_enabled: bool = Field(default=False, alias="externalActionsEnabled")
    evidence_refs: List[str] = Field(default_factory=list, alias="evidenceRefs")
    blocker_refs: List[str] = Field(default_factory=list, alias="blockerRefs")
    safe_next_actions: List[str] = Field(default_factory=list, alias="safeNextActions")
    limitations: List[str] = Field(default_factory=list)
    follow_up_proposals: List[AdminOpsCockpitFollowUpProposal] = Field(
        default_factory=list,
        alias="followUpProposals",
    )


class AdminOpsCockpitBlocker(_AdminOpsStatusModel):
    blocker_key: str = Field(alias="blockerKey")
    title: str
    severity: str
    public_launch_no_go: bool = Field(default=True, alias="publicLaunchNoGo")
    approval_required: bool = Field(default=True, alias="approvalRequired")
    affected_domains: List[str] = Field(default_factory=list, alias="affectedDomains")
    evidence_refs: List[str] = Field(default_factory=list, alias="evidenceRefs")
    next_action: str = Field(alias="nextAction")


class AdminOpsLaunchCockpit(_AdminOpsStatusModel):
    contract: str = "admin_ops_launch_cockpit_v1"
    status: str = "unavailable"
    last_checked_at: Optional[str] = Field(default=None, alias="lastCheckedAt")
    message: str = ""
    read_only: bool = Field(default=True, alias="readOnly")
    advisory_only: bool = Field(default=True, alias="advisoryOnly")
    no_external_calls: bool = Field(default=True, alias="noExternalCalls")
    public_launch_approved: bool = Field(default=False, alias="publicLaunchApproved")
    public_launch_no_go: bool = Field(default=True, alias="publicLaunchNoGo")
    live_enforcement: bool = Field(default=False, alias="liveEnforcement")
    runtime_behavior_changed: bool = Field(default=False, alias="runtimeBehaviorChanged")
    approval_required: bool = Field(default=True, alias="approvalRequired")
    summary_counts: Dict[str, int] = Field(default_factory=dict, alias="summaryCounts")
    unsafe_action_states: Dict[str, bool] = Field(default_factory=dict, alias="unsafeActionStates")
    domains: List[AdminOpsCockpitDomain] = Field(default_factory=list)
    blockers: List[AdminOpsCockpitBlocker] = Field(default_factory=list)
    safe_next_actions: List[str] = Field(default_factory=list, alias="safeNextActions")
    limitations: List[str] = Field(default_factory=list)


class AdminOpsStatusResponse(_AdminOpsStatusModel):
    generated_at: str = Field(alias="generatedAt")
    read_only: bool = Field(default=True, alias="readOnly")
    no_external_calls: bool = Field(default=True, alias="noExternalCalls")
    live_enforcement: bool = Field(default=False, alias="liveEnforcement")
    runtime_behavior_changed: bool = Field(default=False, alias="runtimeBehaviorChanged")
    consumer_visible: bool = Field(default=False, alias="consumerVisible")
    advisory_vs_enforcement: AdminOpsAdvisoryVsEnforcement = Field(alias="advisoryVsEnforcement")
    provider_status_summary: AdminOpsStatusSection = Field(alias="providerStatusSummary")
    quota_cost_advisory_status_summary: AdminOpsStatusSection = Field(alias="quotaCostAdvisoryStatusSummary")
    storage_readiness_summary: AdminOpsStatusSection = Field(alias="storageReadinessSummary")
    task_queue_status_summary: AdminOpsStatusSection = Field(alias="taskQueueStatusSummary")
    admin_log_evidence_summary: AdminOpsStatusSection = Field(alias="adminLogEvidenceSummary")
    launch_cockpit: AdminOpsLaunchCockpit = Field(alias="launchCockpit")
    metadata: Dict[str, Any] = Field(default_factory=dict)
