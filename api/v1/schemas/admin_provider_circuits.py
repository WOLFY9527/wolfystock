# -*- coding: utf-8 -*-
"""Schemas for read-only admin provider circuit diagnostics."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class _AdminProviderCircuitModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class ProviderCircuitStateItem(_AdminProviderCircuitModel):
    provider: str
    provider_category: Optional[str] = Field(default=None, alias="providerCategory")
    route_family: Optional[str] = Field(default=None, alias="routeFamily")
    state: str
    reason_bucket: Optional[str] = Field(default=None, alias="reasonBucket")
    cooldown_until: Optional[str] = Field(default=None, alias="cooldownUntil")
    operator_action_ref: Optional[str] = Field(default=None, alias="operatorActionRef")
    created_at: Optional[str] = Field(default=None, alias="createdAt")
    updated_at: Optional[str] = Field(default=None, alias="updatedAt")


class ProviderCircuitEventItem(_AdminProviderCircuitModel):
    provider: str
    provider_category: Optional[str] = Field(default=None, alias="providerCategory")
    route_family: Optional[str] = Field(default=None, alias="routeFamily")
    event_type: str = Field(alias="eventType")
    from_state: Optional[str] = Field(default=None, alias="fromState")
    to_state: Optional[str] = Field(default=None, alias="toState")
    reason_bucket: Optional[str] = Field(default=None, alias="reasonBucket")
    request_count_bucket: Optional[str] = Field(default=None, alias="requestCountBucket")
    duration_bucket_ms: Optional[int] = Field(default=None, alias="durationBucketMs")
    failure_count_bucket: Optional[str] = Field(default=None, alias="failureCountBucket")
    operator_action_ref: Optional[str] = Field(default=None, alias="operatorActionRef")
    created_at: Optional[str] = Field(default=None, alias="createdAt")


class ProviderQuotaWindowItem(_AdminProviderCircuitModel):
    provider: str
    provider_category: Optional[str] = Field(default=None, alias="providerCategory")
    route_family: Optional[str] = Field(default=None, alias="routeFamily")
    window_type: str = Field(alias="windowType")
    window_start: str = Field(alias="windowStart")
    window_end: str = Field(alias="windowEnd")
    request_count: int = Field(default=0, alias="requestCount")
    reserved_units: int = Field(default=0, alias="reservedUnits")
    consumed_units: int = Field(default=0, alias="consumedUnits")
    released_units: int = Field(default=0, alias="releasedUnits")
    rejected_count: int = Field(default=0, alias="rejectedCount")
    success_count: int = Field(default=0, alias="successCount")
    failure_count: int = Field(default=0, alias="failureCount")
    timeout_count: int = Field(default=0, alias="timeoutCount")
    provider_429_count: int = Field(default=0, alias="provider429Count")
    provider_403_count: int = Field(default=0, alias="provider403Count")
    fallback_count: int = Field(default=0, alias="fallbackCount")
    probe_count: int = Field(default=0, alias="probeCount")
    cache_only_count: int = Field(default=0, alias="cacheOnlyCount")
    stale_served_count: int = Field(default=0, alias="staleServedCount")
    created_at: Optional[str] = Field(default=None, alias="createdAt")
    updated_at: Optional[str] = Field(default=None, alias="updatedAt")


class ProviderProbeEventItem(_AdminProviderCircuitModel):
    provider: str
    provider_category: Optional[str] = Field(default=None, alias="providerCategory")
    route_family: Optional[str] = Field(default=None, alias="routeFamily")
    probe_type: str = Field(alias="probeType")
    probe_source: str = Field(alias="probeSource")
    result_bucket: str = Field(alias="resultBucket")
    duration_bucket_ms: Optional[int] = Field(default=None, alias="durationBucketMs")
    created_at: Optional[str] = Field(default=None, alias="createdAt")


class ProviderCircuitDiagnosticsMetadata(_AdminProviderCircuitModel):
    read_only: bool = Field(default=True, alias="readOnly")
    no_external_calls: bool = Field(default=True, alias="noExternalCalls")
    live_enforcement: bool = Field(default=False, alias="liveEnforcement")
    provider_behavior_changed: bool = Field(default=False, alias="providerBehaviorChanged")
    market_cache_behavior_changed: bool = Field(default=False, alias="marketCacheBehaviorChanged")
    data_sources: List[str] = Field(default_factory=list, alias="dataSources")
    limit: int = 100
    redaction: List[str] = Field(default_factory=list)
    filters: Dict[str, Any] = Field(default_factory=dict)


class ProviderCircuitStatesResponse(_AdminProviderCircuitModel):
    generated_at: str = Field(alias="generatedAt")
    items: List[ProviderCircuitStateItem] = Field(default_factory=list)
    metadata: ProviderCircuitDiagnosticsMetadata


class ProviderCircuitEventsResponse(_AdminProviderCircuitModel):
    generated_at: str = Field(alias="generatedAt")
    items: List[ProviderCircuitEventItem] = Field(default_factory=list)
    metadata: ProviderCircuitDiagnosticsMetadata


class ProviderQuotaWindowsResponse(_AdminProviderCircuitModel):
    generated_at: str = Field(alias="generatedAt")
    items: List[ProviderQuotaWindowItem] = Field(default_factory=list)
    metadata: ProviderCircuitDiagnosticsMetadata


class ProviderProbeEventsResponse(_AdminProviderCircuitModel):
    generated_at: str = Field(alias="generatedAt")
    items: List[ProviderProbeEventItem] = Field(default_factory=list)
    metadata: ProviderCircuitDiagnosticsMetadata
