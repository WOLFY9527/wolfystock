# -*- coding: utf-8 -*-
"""Schemas for read-only admin duplicate-cost summaries."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class _AdminCostModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class DuplicateCostSummaryWindow(_AdminCostModel):
    key: str = "24h"
    date_from: str = Field(alias="from")
    date_to: str = Field(alias="to")
    bucket: Literal["hour", "day"] = "hour"
    historical: bool = False


class DuplicateCostOverview(_AdminCostModel):
    llm_calls: int = Field(default=0, alias="llmCalls")
    llm_usage_calls: int = Field(default=0, alias="llmUsageCalls")
    llm_usage_tokens: int = Field(default=0, alias="llmUsageTokens")
    estimated_duplicate_candidates: int = Field(default=0, alias="estimatedDuplicateCandidates")
    provider_calls: int = Field(default=0, alias="providerCalls")
    provider_cache_hits: int = Field(default=0, alias="providerCacheHits")
    provider_cache_misses: int = Field(default=0, alias="providerCacheMisses")
    provider_inflight_joins: int = Field(default=0, alias="providerInflightJoins")
    provider_cache_hit_rate: Optional[float] = Field(default=None, alias="providerCacheHitRate")
    market_cache_hits: int = Field(default=0, alias="marketCacheHits")
    market_cache_misses: int = Field(default=0, alias="marketCacheMisses")
    market_cache_stale_served: int = Field(default=0, alias="marketCacheStaleServed")
    market_cache_cold_fallbacks: int = Field(default=0, alias="marketCacheColdFallbacks")
    market_cache_hit_rate: Optional[float] = Field(default=None, alias="marketCacheHitRate")
    fallback_attempts: int = Field(default=0, alias="fallbackAttempts")
    integrity_retries: int = Field(default=0, alias="integrityRetries")
    scanner_ai_attempts: int = Field(default=0, alias="scannerAiAttempts")
    scanner_ai_completed: int = Field(default=0, alias="scannerAiCompleted")
    scanner_ai_skipped: int = Field(default=0, alias="scannerAiSkipped")


class DuplicateCostRollup(_AdminCostModel):
    group: str
    count: int = 0
    event_counts: Dict[str, int] = Field(default_factory=dict, alias="eventCounts")
    dimensions: Dict[str, str] = Field(default_factory=dict)


class DuplicateCostCacheEfficiency(_AdminCostModel):
    group: str
    hits: int = 0
    misses: int = 0
    inflight_joins: int = Field(default=0, alias="inflightJoins")
    hit_rate: Optional[float] = Field(default=None, alias="hitRate")
    dimensions: Dict[str, str] = Field(default_factory=dict)


class DuplicateCostLlmSection(_AdminCostModel):
    by_call_type: List[DuplicateCostRollup] = Field(default_factory=list, alias="byCallType")
    duplicate_candidates: List[DuplicateCostRollup] = Field(default_factory=list, alias="duplicateCandidates")
    fallbacks: List[DuplicateCostRollup] = Field(default_factory=list)
    integrity_retries: List[DuplicateCostRollup] = Field(default_factory=list, alias="integrityRetries")
    usage_by_call_type: List[DuplicateCostRollup] = Field(default_factory=list, alias="usageByCallType")
    usage_by_model: List[DuplicateCostRollup] = Field(default_factory=list, alias="usageByModel")


class DuplicateCostProviderSection(_AdminCostModel):
    by_category: List[DuplicateCostRollup] = Field(default_factory=list, alias="byCategory")
    fallback_depth: List[DuplicateCostRollup] = Field(default_factory=list, alias="fallbackDepth")
    cache_efficiency: List[DuplicateCostCacheEfficiency] = Field(default_factory=list, alias="cacheEfficiency")
    duplicate_candidates: List[DuplicateCostRollup] = Field(default_factory=list, alias="duplicateCandidates")


class DuplicateCostMarketCacheSection(_AdminCostModel):
    by_panel_key: List[DuplicateCostRollup] = Field(default_factory=list, alias="byPanelKey")
    stale_served: List[DuplicateCostRollup] = Field(default_factory=list, alias="staleServed")
    cold_fallbacks: List[DuplicateCostRollup] = Field(default_factory=list, alias="coldFallbacks")
    refreshes: List[DuplicateCostRollup] = Field(default_factory=list)


class DuplicateCostScannerAiSection(_AdminCostModel):
    interpretations: List[DuplicateCostRollup] = Field(default_factory=list)
    duplicate_candidates: List[DuplicateCostRollup] = Field(default_factory=list, alias="duplicateCandidates")
    skips: List[DuplicateCostRollup] = Field(default_factory=list)


class DuplicateCostLimitation(_AdminCostModel):
    code: str
    message: str
    severity: Literal["info", "warning"] = "info"


class DuplicateCostMetadata(_AdminCostModel):
    read_only: bool = Field(default=True, alias="readOnly")
    no_external_calls: bool = Field(default=True, alias="noExternalCalls")
    counters_source: str = Field(default="process_local", alias="countersSource")
    exactness: str = "observational_not_billing"
    data_sources: List[str] = Field(default_factory=list, alias="dataSources")
    unsupported_sources: List[str] = Field(default_factory=list, alias="unsupportedSources")
    redaction: List[str] = Field(default_factory=list)
    requested_area: str = Field(default="all", alias="requestedArea")
    limit: int = 50
    notes: Dict[str, Any] = Field(default_factory=dict)


class DuplicateCostSummaryResponse(_AdminCostModel):
    generated_at: str = Field(alias="generatedAt")
    window: DuplicateCostSummaryWindow
    summary: DuplicateCostOverview
    llm: DuplicateCostLlmSection
    providers: DuplicateCostProviderSection
    market_cache: DuplicateCostMarketCacheSection = Field(alias="marketCache")
    scanner_ai: DuplicateCostScannerAiSection = Field(alias="scannerAi")
    limitations: List[DuplicateCostLimitation] = Field(default_factory=list)
    metadata: DuplicateCostMetadata


class QuotaDryRunRequest(_AdminCostModel):
    owner_user_id: Optional[str] = Field(default=None, alias="ownerUserId")
    route_family: str = Field(default="analysis", alias="routeFamily")
    provider: Optional[str] = None
    model_tier: Optional[str] = Field(default=None, alias="modelTier")
    token_estimate: Optional[int] = Field(default=None, alias="tokenEstimate", ge=0)
    estimated_units: Optional[int] = Field(default=None, alias="estimatedUnits", ge=0)
    enforcement_mode: Literal["disabled", "dry_run", "enabled"] = Field(default="dry_run", alias="enforcementMode")
    operation: Literal["estimate", "reserve", "consume", "release"] = "estimate"
    reservation_id: Optional[str] = Field(default=None, alias="reservationId")
    actual_units: Optional[int] = Field(default=None, alias="actualUnits", ge=0)
    global_kill_switch: bool = Field(default=False, alias="globalKillSwitch")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QuotaDryRunResponse(_AdminCostModel):
    allowed: bool
    would_block: bool = Field(default=False, alias="wouldBlock")
    status: str
    reason_code: Optional[str] = Field(default=None, alias="reasonCode")
    route_family: str = Field(default="analysis", alias="routeFamily")
    estimated_units: int = Field(default=0, alias="estimatedUnits")
    enforcement_mode: Literal["disabled", "dry_run", "enabled"] = Field(default="dry_run", alias="enforcementMode")
    operation: Literal["estimate", "reserve", "consume", "release"] = "estimate"
    reservation_id: Optional[str] = Field(default=None, alias="reservationId")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LlmLedgerSummaryTotal(_AdminCostModel):
    calls: int = 0
    prompt_tokens: int = Field(default=0, alias="promptTokens")
    cached_input_tokens: int = Field(default=0, alias="cachedInputTokens")
    completion_tokens: int = Field(default=0, alias="completionTokens")
    total_tokens: int = Field(default=0, alias="totalTokens")
    total_cost_usd: str = Field(default="0", alias="totalCostUsd")


class LlmLedgerSummaryRollup(_AdminCostModel):
    group: str
    calls: int = 0
    total_tokens: int = Field(default=0, alias="totalTokens")
    total_cost_usd: str = Field(default="0", alias="totalCostUsd")
    dimensions: Dict[str, str] = Field(default_factory=dict)


class LlmLedgerSummaryResponse(_AdminCostModel):
    generated_at: str = Field(alias="generatedAt")
    window: DuplicateCostSummaryWindow
    total: LlmLedgerSummaryTotal
    by_user: List[LlmLedgerSummaryRollup] = Field(default_factory=list, alias="byUser")
    by_provider_model: List[LlmLedgerSummaryRollup] = Field(default_factory=list, alias="byProviderModel")
    by_route_family: List[LlmLedgerSummaryRollup] = Field(default_factory=list, alias="byRouteFamily")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ModelPricingPolicyItem(_AdminCostModel):
    provider: str
    model: str
    input_price_per_1m: str = Field(alias="inputPricePer1m")
    cached_input_price_per_1m: Optional[str] = Field(default=None, alias="cachedInputPricePer1m")
    output_price_per_1m: str = Field(alias="outputPricePer1m")
    currency: str
    effective_from: Optional[str] = Field(default=None, alias="effectiveFrom")
    effective_until: Optional[str] = Field(default=None, alias="effectiveUntil")
    active: bool
    source_label: Optional[str] = Field(default=None, alias="sourceLabel")
    source_url: Optional[str] = Field(default=None, alias="sourceUrl")
    updated_at: Optional[str] = Field(default=None, alias="updatedAt")


class ModelPricingPoliciesResponse(_AdminCostModel):
    generated_at: str = Field(alias="generatedAt")
    active_count: int = Field(default=0, alias="activeCount")
    policies: List[ModelPricingPolicyItem] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
