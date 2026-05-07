# -*- coding: utf-8 -*-
"""Schemas for admin execution logs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ExecutionLogEventModel(BaseModel):
    id: int
    event_at: Optional[str] = None
    level: Optional[str] = None
    phase: str
    category: Optional[str] = None
    event_name: Optional[str] = None
    step: Optional[str] = None
    action: Optional[str] = None
    outcome: Optional[str] = None
    reason: Optional[str] = None
    target: Optional[str] = None
    status: str
    truth_level: str
    message: Optional[str] = None
    error_code: Optional[str] = None
    detail: Dict[str, Any] = Field(default_factory=dict)


class ExecutionLogSessionSummaryModel(BaseModel):
    session_id: str
    task_id: Optional[str] = None
    query_id: Optional[str] = None
    analysis_history_id: Optional[int] = None
    code: Optional[str] = None
    name: Optional[str] = None
    overall_status: str
    truth_level: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    summary: Dict[str, Any] = Field(default_factory=dict)
    readable_summary: Dict[str, Any] = Field(default_factory=dict)


class ExecutionLogSessionDetailModel(ExecutionLogSessionSummaryModel):
    events: List[ExecutionLogEventModel] = Field(default_factory=list)
    operation_detail: Dict[str, Any] = Field(default_factory=dict)


class ExecutionLogSummaryModel(BaseModel):
    error_count: int = 0
    warning_count: int = 0
    data_source_failure_count: int = 0
    slow_request_count: int = 0
    latest_critical_at: Optional[str] = None
    health_summary: Optional["AdminLogHealthSummaryModel"] = None


class ExecutionLogSessionListResponse(BaseModel):
    total: int
    items: List[ExecutionLogSessionSummaryModel] = Field(default_factory=list)
    summary: ExecutionLogSummaryModel = Field(default_factory=ExecutionLogSummaryModel)


class AdminLogHealthBucketModel(BaseModel):
    key: str
    label: str
    count: int


class AdminLogTopErrorModel(BaseModel):
    id: str
    event: Optional[str] = None
    category: Optional[str] = None
    provider: Optional[str] = None
    source: Optional[str] = None
    reason: Optional[str] = None
    errorSummary: Optional[str] = None
    startedAt: Optional[str] = None
    status: Optional[str] = None


class AdminLogHealthSummaryModel(BaseModel):
    total_events: int = 0
    failed_events: int = 0
    warning_events: int = 0
    slow_events: int = 0
    failure_rate: float = 0
    status: str = "healthy"
    failures_by_category: List[AdminLogHealthBucketModel] = Field(default_factory=list)
    failures_by_provider: List[AdminLogHealthBucketModel] = Field(default_factory=list)
    failures_by_reason: List[AdminLogHealthBucketModel] = Field(default_factory=list)
    top_recent_errors: List[AdminLogTopErrorModel] = Field(default_factory=list)
    actor_breakdown: List[AdminLogHealthBucketModel] = Field(default_factory=list)
    latest_critical_error: Optional[AdminLogTopErrorModel] = None


class ExecutionStepModel(BaseModel):
    id: Optional[str] = None
    executionId: Optional[str] = None
    name: str
    label: str
    category: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    endpoint: Optional[str] = None
    apiPath: Optional[str] = None
    status: str
    reason: Optional[str] = None
    message: Optional[str] = None
    startedAt: Optional[str] = None
    finishedAt: Optional[str] = None
    durationMs: Optional[float] = None
    errorType: Optional[str] = None
    errorMessage: Optional[str] = None
    recordId: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BusinessEventModel(BaseModel):
    id: str
    event: str
    category: str
    type: Optional[str] = None
    eventType: Optional[str] = None
    status: str
    summary: str
    subject: Optional[str] = None
    symbol: Optional[str] = None
    market: Optional[str] = None
    actorType: Optional[str] = None
    actorLabel: Optional[str] = None
    contextLabel: Optional[str] = None
    route: Optional[str] = None
    endpoint: Optional[str] = None
    provider: Optional[str] = None
    source: Optional[str] = None
    component: Optional[str] = None
    feature: Optional[str] = None
    reason: Optional[str] = None
    errorSummary: Optional[str] = None
    traceId: Optional[str] = None
    rootCauseSummary: Optional[str] = None
    stepTraceAvailable: Optional[bool] = None
    analysisType: Optional[str] = None
    strategyId: Optional[str] = None
    scannerId: Optional[str] = None
    backtestId: Optional[str] = None
    userId: Optional[str] = None
    requestId: Optional[str] = None
    recordId: Optional[str] = None
    startedAt: Optional[str] = None
    finishedAt: Optional[str] = None
    durationMs: Optional[float] = None
    stepCount: int = 0
    successStepCount: int = 0
    failedStepCount: int = 0
    skippedStepCount: int = 0
    unknownStepCount: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BusinessEventDetailModel(BusinessEventModel):
    steps: List[ExecutionStepModel] = Field(default_factory=list)


class BusinessEventListResponse(BaseModel):
    items: List[BusinessEventModel] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
    hasMore: bool = False
    health_summary: Optional[AdminLogHealthSummaryModel] = None


class AdminLogStorageSummaryModel(BaseModel):
    total_log_count: int = 0
    event_count: int = 0
    session_count: int = 0
    total_event_count: int = 0
    oldest_log_timestamp: Optional[str] = None
    oldest_event_at: Optional[str] = None
    newest_log_timestamp: Optional[str] = None
    newest_event_at: Optional[str] = None
    retention_days: int = 90
    minimum_retention_days: int = 7
    retention_tiers: Dict[str, Any] = Field(default_factory=dict)
    retention_cutoff: Optional[str] = None
    logs_older_than_retention_count: int = 0
    estimated_storage_bytes: Optional[int] = None
    size_bytes: Optional[int] = None
    storage_size_bytes: Optional[int] = None
    size_label: Optional[str] = None
    storage_size_label: Optional[str] = None
    storage_size_available: bool = False
    measurement_scope: str = "unavailable"
    measurement_status: str = "unavailable"
    measurement_reason: Optional[str] = None
    soft_limit_bytes: Optional[int] = None
    storage_soft_limit_bytes: int = 512 * 1024 * 1024
    hard_limit_bytes: Optional[int] = None
    storage_hard_limit_bytes: int = 1024 * 1024 * 1024
    used_percentage_of_soft_limit: Optional[float] = None
    used_percentage_of_hard_limit: Optional[float] = None
    capacity_cleanup_recommended: bool = False
    auto_cleanup_enabled: bool = True
    auto_cleanup_performed: bool = False
    auto_cleanup_message: Optional[str] = None
    capacity_cleanup_plan: Dict[str, Any] = Field(default_factory=dict)
    postgres_vacuum_note: Optional[str] = None
    warning_threshold_count: int = 50000
    critical_threshold_count: int = 100000
    warning_threshold_storage_bytes: Optional[int] = None
    status: str = "ok"
    status_reasons: List[str] = Field(default_factory=list)
    recommended_cleanup_action: str = "No cleanup needed."
    last_cleanup_timestamp: Optional[str] = None


class AdminLogCleanupRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mode: Optional[str] = None
    use_retention: bool = Field(
        default=False,
        validation_alias=AliasChoices("use_retention", "useRetention"),
        serialization_alias="useRetention",
    )
    older_than: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("older_than", "olderThan"),
        serialization_alias="olderThan",
    )
    dry_run: bool = Field(
        default=True,
        validation_alias=AliasChoices("dry_run", "dryRun"),
        serialization_alias="dryRun",
    )
    status: Optional[str] = None
    category: Optional[str] = None
    batch_size: int = Field(
        default=1000,
        validation_alias=AliasChoices("batch_size", "batchSize"),
        serialization_alias="batchSize",
    )


class AdminLogCleanupResponse(BaseModel):
    mode: str = "retention"
    dry_run: bool = True
    cutoff: Optional[str] = None
    matched_log_count: int = 0
    matched_event_count: int = 0
    deleted_log_count: int = 0
    deleted_event_count: int = 0
    status_filter: Optional[str] = None
    category_filter: Optional[str] = None
    additional_cleanup_needed: bool = False
    message: Optional[str] = None
    postgres_vacuum_note: Optional[str] = None
