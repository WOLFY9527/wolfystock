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
    priority_rank: int = Field(default=0, alias="priorityRank")
    priority_tier: str = Field(default="watch", alias="priorityTier")
    impact_level: str = Field(default="low", alias="impactLevel")
    recommended_next_action: str = Field(default="", alias="recommendedNextAction")
    blocking_reason_summary: str = Field(default="", alias="blockingReasonSummary")
    owner_surface: str = Field(default="admin_maintenance", alias="ownerSurface")
    remediation_surface: str = Field(default="/admin", alias="remediationSurface")
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


class AdminOpsCockpitMaintenanceQueueItem(_AdminOpsStatusModel):
    domain_key: str = Field(alias="domainKey")
    label: str
    status: str
    priority_rank: int = Field(alias="priorityRank")
    priority_tier: str = Field(alias="priorityTier")
    impact_level: str = Field(alias="impactLevel")
    recommended_next_action: str = Field(alias="recommendedNextAction")
    blocking_reason_summary: str = Field(alias="blockingReasonSummary")
    owner_surface: str = Field(alias="ownerSurface")
    remediation_surface: str = Field(alias="remediationSurface")


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
    recommended_maintenance_queue: List[AdminOpsCockpitMaintenanceQueueItem] = Field(
        default_factory=list,
        alias="recommendedMaintenanceQueue",
    )
    blockers: List[AdminOpsCockpitBlocker] = Field(default_factory=list)
    safe_next_actions: List[str] = Field(default_factory=list, alias="safeNextActions")
    limitations: List[str] = Field(default_factory=list)
    priority_summary: Dict[str, int] = Field(default_factory=dict, alias="prioritySummary")


class AdminScannerUniverseReadinessResponse(_AdminOpsStatusModel):
    contract_version: str = Field(default="scanner_universe_operator_readiness_v1", alias="contractVersion")
    status: str
    scanner_universe_status: Optional[str] = Field(default=None, alias="scannerUniverseStatus")
    market: str = "cn"
    profile: str = "cn_preopen_v1"
    freshness_state: str = Field(default="unknown", alias="freshnessState")
    last_updated_at: Optional[str] = Field(default=None, alias="lastUpdatedAt")
    universe_size: int = Field(default=0, alias="universeSize")
    affected_product_surfaces: List[str] = Field(default_factory=list, alias="affectedProductSurfaces")
    next_operator_action: str = Field(default="", alias="nextOperatorAction")
    scanner_universe_readiness: Dict[str, Any] = Field(default_factory=dict, alias="scannerUniverseReadiness")
    candidate_generation_state: Optional[str] = Field(default=None, alias="candidateGenerationState")
    candidate_generation_blockers: List[str] = Field(default_factory=list, alias="candidateGenerationBlockers")
    read_only: bool = Field(default=True, alias="readOnly")
    no_external_calls: bool = Field(default=True, alias="noExternalCalls")
    mutation_enabled: bool = Field(default=False, alias="mutationEnabled")
    provider_calls_enabled: bool = Field(default=False, alias="providerCallsEnabled")
    consumer_visible: bool = Field(default=False, alias="consumerVisible")


class AdminScannerUniverseRefreshResponse(_AdminOpsStatusModel):
    contract_version: str = Field(default="scanner_universe_operator_action_v1", alias="contractVersion")
    status: str
    action_status: str = Field(alias="actionStatus")
    market: str = "cn"
    profile: str = "cn_preopen_v1"
    refresh_executed: bool = Field(default=False, alias="refreshExecuted")
    mutation_enabled: bool = Field(default=False, alias="mutationEnabled")
    no_external_calls: bool = Field(default=True, alias="noExternalCalls")
    provider_calls_enabled: bool = Field(default=False, alias="providerCallsEnabled")
    runtime_behavior_changed: bool = Field(default=False, alias="runtimeBehaviorChanged")
    next_operator_action: str = Field(default="", alias="nextOperatorAction")
    before: Dict[str, Any] = Field(default_factory=dict)
    after: Dict[str, Any] = Field(default_factory=dict)


class AdminBuildProvenance(_AdminOpsStatusModel):
    contract: str = "admin_build_provenance_v1"
    read_only: bool = Field(default=True, alias="readOnly")
    no_external_calls: bool = Field(default=True, alias="noExternalCalls")
    runtime_behavior_changed: bool = Field(default=False, alias="runtimeBehaviorChanged")
    consumer_visible: bool = Field(default=False, alias="consumerVisible")
    backend_git_sha: Optional[str] = Field(default=None, alias="backendGitSha")
    backend_branch: Optional[str] = Field(default=None, alias="backendBranch")
    backend_commit_timestamp: Optional[str] = Field(default=None, alias="backendCommitTimestamp")
    backend_runtime_started_at: Optional[str] = Field(default=None, alias="backendRuntimeStartedAt")
    frontend_main_asset_filename: Optional[str] = Field(default=None, alias="frontendMainAssetFilename")
    frontend_main_asset_hash: Optional[str] = Field(default=None, alias="frontendMainAssetHash")
    frontend_asset_manifest_hash: Optional[str] = Field(default=None, alias="frontendAssetManifestHash")
    frontend_asset_manifest_source: Optional[str] = Field(default=None, alias="frontendAssetManifestSource")
    frontend_static_build_timestamp: Optional[str] = Field(default=None, alias="frontendStaticBuildTimestamp")
    static_asset_mode: str = Field(default="unknown", alias="staticAssetMode")
    static_asset_root_provenance: str = Field(default="unknown", alias="staticAssetRootProvenance")
    static_asset_root_label: Optional[str] = Field(default=None, alias="staticAssetRootLabel")
    static_asset_root_exists: bool = Field(default=False, alias="staticAssetRootExists")
    static_index_present: bool = Field(default=False, alias="staticIndexPresent")
    freshness_status: str = Field(default="unknown", alias="freshnessStatus")
    comparison_basis: Optional[str] = Field(default=None, alias="comparisonBasis")
    stale: Optional[bool] = None
    reason_codes: List[str] = Field(default_factory=list, alias="reasonCodes")


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
    runtime_log_sink_summary: AdminOpsStatusSection = Field(alias="runtimeLogSinkSummary")
    retention_policy_status: AdminOpsStatusSection = Field(alias="retentionPolicyStatus")
    execution_log_retention_risk: AdminOpsStatusSection = Field(alias="executionLogRetentionRisk")
    db_size_risk: AdminOpsStatusSection = Field(alias="dbSizeRisk")
    admin_role_assignment_status: AdminOpsStatusSection = Field(alias="adminRoleAssignmentStatus")
    durable_task_backlog_status: AdminOpsStatusSection = Field(alias="durableTaskBacklogStatus")
    recommended_maintenance_actions: List[str] = Field(default_factory=list, alias="recommendedMaintenanceActions")
    build_provenance: AdminBuildProvenance = Field(alias="buildProvenance")
    launch_cockpit: AdminOpsLaunchCockpit = Field(alias="launchCockpit")
    metadata: Dict[str, Any] = Field(default_factory=dict)
