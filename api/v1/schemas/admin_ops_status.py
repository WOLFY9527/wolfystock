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
    metadata: Dict[str, Any] = Field(default_factory=dict)
