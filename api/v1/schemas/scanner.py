# -*- coding: utf-8 -*-
"""Market scanner API schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ScannerRunRequest(BaseModel):
    market: Literal["cn", "us", "hk"] = Field("cn", description="目标市场，当前阶段实现 cn / us / hk profile")
    profile: Optional[str] = Field(None, description="扫描配置 key，默认按市场选择")
    shortlist_size: int = Field(5, ge=1, le=20, description="输出观察名单数量")
    universe_limit: Optional[int] = Field(None, ge=50, le=1000, description="进入详细评估前的候选池上限")
    detail_limit: Optional[int] = Field(None, ge=10, le=200, description="进入详细特征计算的候选数")
    universe_type: Literal["default", "theme", "symbols"] = Field("default", description="扫描标的池类型")
    theme_id: Optional[str] = Field(None, description="theme 标的池 id")
    symbols: List[str] = Field(default_factory=list, max_length=200, description="自定义扫描代码列表")

    @field_validator("theme_id")
    @classmethod
    def _normalize_theme_id(cls, value: Optional[str]) -> Optional[str]:
        normalized = (value or "").strip().lower()
        return normalized or None

    @field_validator("symbols", mode="before")
    @classmethod
    def _normalize_symbols(cls, value: Any) -> List[str]:
        if value is None:
            return []
        raw_items = value if isinstance(value, list) else [value]
        result: List[str] = []
        seen = set()
        for item in raw_items:
            symbol = str(item or "").strip().upper()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            result.append(symbol)
        return result


class ScannerThemeResponse(BaseModel):
    id: str
    label_zh: str
    label_en: str
    market: str
    description: str
    symbols: List[str] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    source: str
    version: str
    is_seed_list: bool = True
    requires_manual_maintenance: bool = False
    criteria_prompt: Optional[str] = None
    generated_at: Optional[str] = None
    updated_at: Optional[str] = None
    refresh_policy: Optional[str] = None
    ai_metadata: Dict[str, Any] = Field(default_factory=dict)


class ScannerThemesResponse(BaseModel):
    items: List[ScannerThemeResponse] = Field(default_factory=list)


class ScannerThemeGenerateRequest(BaseModel):
    id: str = Field(..., min_length=3, max_length=64, description="Custom theme id, lowercase snake_case")
    label: str = Field(..., min_length=2, max_length=80, description="User-facing custom theme label")
    market: Literal["cn", "us", "hk"] = Field("us", description="Target market for generated symbols")
    prompt: str = Field(..., min_length=12, max_length=600, description="Theme criteria prompt")
    manual_symbols: List[str] = Field(default_factory=list, max_length=200, description="Optional manually added symbols")

    @field_validator("id")
    @classmethod
    def _normalize_id(cls, value: str) -> str:
        return str(value or "").strip().lower()

    @field_validator("manual_symbols", mode="before")
    @classmethod
    def _normalize_manual_symbols(cls, value: Any) -> List[str]:
        return ScannerRunRequest._normalize_symbols(value)


class ScannerThemeSuggestionResponse(BaseModel):
    symbol: str
    reason: str
    confidence: float
    evidence: List[str] = Field(default_factory=list)


class ScannerThemeGenerationResponse(BaseModel):
    theme: ScannerThemeResponse
    suggestions: List[ScannerThemeSuggestionResponse] = Field(default_factory=list)
    message: str


class ScannerLabeledValue(BaseModel):
    label: str
    value: str


class ScannerNotificationResult(BaseModel):
    attempted: bool = False
    status: str = "not_attempted"
    success: Optional[bool] = None
    channels: List[str] = Field(default_factory=list)
    message: Optional[str] = None
    report_path: Optional[str] = None
    sent_at: Optional[str] = None


class ScannerAiInterpretationResponse(BaseModel):
    available: bool = False
    status: str = "skipped"
    summary: Optional[str] = None
    opportunity_type: Optional[str] = None
    risk_interpretation: Optional[str] = None
    watch_plan: Optional[str] = None
    review_commentary: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    generated_at: Optional[str] = None
    message: Optional[str] = None


class ScannerCandidateOutcomeResponse(BaseModel):
    review_status: str = "pending"
    outcome_label: str = "pending"
    thesis_match: str = "pending"
    review_window_days: int = 3
    anchor_date: Optional[str] = None
    window_end_date: Optional[str] = None
    same_day_close_return_pct: Optional[float] = None
    next_day_return_pct: Optional[float] = None
    review_window_return_pct: Optional[float] = None
    max_favorable_move_pct: Optional[float] = None
    max_adverse_move_pct: Optional[float] = None
    benchmark_code: Optional[str] = None
    benchmark_return_pct: Optional[float] = None
    outperformed_benchmark: Optional[bool] = None


class ScannerReviewSummaryResponse(BaseModel):
    available: bool = False
    review_window_days: int = 3
    review_status: str = "pending"
    candidate_count: int = 0
    reviewed_count: int = 0
    pending_count: int = 0
    hit_rate_pct: Optional[float] = None
    outperform_rate_pct: Optional[float] = None
    avg_same_day_close_return_pct: Optional[float] = None
    avg_review_window_return_pct: Optional[float] = None
    avg_max_favorable_move_pct: Optional[float] = None
    avg_max_adverse_move_pct: Optional[float] = None
    strong_count: int = 0
    mixed_count: int = 0
    weak_count: int = 0
    best_symbol: Optional[str] = None
    best_return_pct: Optional[float] = None
    weakest_symbol: Optional[str] = None
    weakest_return_pct: Optional[float] = None


class ScannerWatchlistDeltaItem(BaseModel):
    symbol: str
    name: Optional[str] = None
    current_rank: Optional[int] = None
    previous_rank: Optional[int] = None
    rank_delta: Optional[int] = None


class ScannerWatchlistComparisonResponse(BaseModel):
    available: bool = False
    previous_run_id: Optional[int] = None
    previous_watchlist_date: Optional[str] = None
    new_count: int = 0
    retained_count: int = 0
    dropped_count: int = 0
    new_symbols: List[ScannerWatchlistDeltaItem] = Field(default_factory=list)
    retained_symbols: List[ScannerWatchlistDeltaItem] = Field(default_factory=list)
    dropped_symbols: List[ScannerWatchlistDeltaItem] = Field(default_factory=list)


class ScannerQualitySummaryResponse(BaseModel):
    available: bool = False
    review_window_days: int = 3
    benchmark_code: Optional[str] = None
    run_count: int = 0
    reviewed_run_count: int = 0
    reviewed_candidate_count: int = 0
    review_coverage_pct: Optional[float] = None
    avg_candidates_per_run: Optional[float] = None
    avg_shortlist_return_pct: Optional[float] = None
    positive_run_rate_pct: Optional[float] = None
    hit_rate_pct: Optional[float] = None
    outperform_rate_pct: Optional[float] = None
    positive_candidate_avg_score: Optional[float] = None
    negative_candidate_avg_score: Optional[float] = None


class ScannerSourceConfidenceMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: Optional[str] = None
    sourceLabel: Optional[str] = None
    sourceType: Optional[str] = None
    asOf: Optional[str] = None
    freshness: Optional[str] = None
    isFallback: Optional[bool] = None
    isStale: Optional[bool] = None
    isPartial: Optional[bool] = None
    isSynthetic: Optional[bool] = None
    isUnavailable: Optional[bool] = None
    confidenceWeight: Optional[float] = None
    coverage: Optional[float] = None
    degradationReason: Optional[str] = None
    capReason: Optional[str] = None
    sourceAuthorityAllowed: Optional[bool] = None
    scoreContributionAllowed: Optional[bool] = None
    observationOnly: Optional[bool] = None
    proxyOnly: Optional[bool] = None


class ScannerScoreExplainabilityMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    raw_score: Optional[float] = None
    final_score: Optional[float] = None
    score_delta: Optional[float] = None
    score_cap: Optional[float] = None
    score_confidence: Optional[float] = None
    evidence_coverage: Optional[float] = None
    cap_reason: Optional[str] = None
    degradation_reason: Optional[str] = None
    cap_applied: Optional[bool] = None
    missing_evidence: List[str] = Field(default_factory=list)
    reason_codes: List[str] = Field(default_factory=list)
    score_grade_allowed: Optional[bool] = None
    source_confidence: Optional[ScannerSourceConfidenceMetadata] = None


class ScannerFreshnessDetailMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    quoteState: Optional[str] = None
    historyState: Optional[str] = None
    latestTradeDate: Optional[str] = None


class ScannerProviderObservationMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    observationOnly: Optional[bool] = None
    scoreContributionAllowed: Optional[bool] = None
    entries: List[Dict[str, Any]] = Field(default_factory=list)


class ScannerEvidencePacketMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    symbol: Optional[str] = None
    market: Optional[str] = None
    rank: Optional[int] = None
    score: Optional[float] = None
    rawScore: Optional[float] = None
    finalScore: Optional[float] = None
    scoreConfidence: Optional[float] = None
    evidenceCoverage: Optional[float] = None
    capReason: Optional[str] = None
    degradationReason: Optional[str] = None
    evidenceVersion: Optional[str] = None
    runId: Optional[int] = None
    dataQualityState: Optional[str] = None
    freshnessState: Optional[str] = None
    freshnessDetail: Optional[ScannerFreshnessDetailMetadata] = None
    providerObservation: Optional[ScannerProviderObservationMetadata] = None
    missingEvidence: List[str] = Field(default_factory=list)
    userFacingLabels: List[str] = Field(default_factory=list)
    warningFlags: List[str] = Field(default_factory=list)
    sourceConfidence: Optional[ScannerSourceConfidenceMetadata] = None


class ScannerConsumerDiagnosticsMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: Optional[str] = None
    reasonBucket: Optional[str] = None
    reasonLabel: Optional[str] = None
    nextEvidence: Optional[str] = None
    sourceConfidenceBucket: Optional[str] = None
    confidenceCategory: Optional[str] = None
    freshnessCategory: Optional[str] = None
    scoreGradeAllowed: Optional[bool] = None
    scoreConfidence: Optional[float] = None
    capReason: Optional[str] = None
    degradationReason: Optional[str] = None
    dataQualityState: Optional[str] = None
    freshnessState: Optional[str] = None
    sourceClass: Optional[str] = None
    missingEvidence: List[str] = Field(default_factory=list)
    userFacingLabels: List[str] = Field(default_factory=list)
    warningFlags: List[str] = Field(default_factory=list)
    investorSignal: Optional[Dict[str, Any]] = None


def _dump_metadata_model(model_type: Any, value: Any) -> Any:
    if isinstance(value, model_type):
        return value.model_dump(exclude_unset=True)
    if isinstance(value, dict):
        return model_type.model_validate(value).model_dump(exclude_unset=True)
    return value


def _lock_candidate_diagnostics_metadata(value: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(value or {})
    if isinstance(payload.get("score_explainability"), dict):
        payload["score_explainability"] = _dump_metadata_model(
            ScannerScoreExplainabilityMetadata,
            payload["score_explainability"],
        )
    if isinstance(payload.get("evidence_packet"), dict):
        payload["evidence_packet"] = _dump_metadata_model(
            ScannerEvidencePacketMetadata,
            payload["evidence_packet"],
        )
    return payload


_SCANNER_CONSUMER_REASON_COPY: Dict[str, Dict[str, str]] = {
    "selected": {
        "label": "已进入本轮观察名单",
        "next": "继续跟踪后续数据确认。",
    },
    "score_fit": {
        "label": "综合条件未进入本轮观察名单",
        "next": "等待趋势、动量或流动性条件改善后再复核。",
    },
    "liquidity": {
        "label": "流动性未达到本轮观察要求",
        "next": "观察成交额和成交量改善后再复核。",
    },
    "history_coverage": {
        "label": "历史行情覆盖不足",
        "next": "等待更多历史行情覆盖后再复核。",
    },
    "price_range": {
        "label": "价格区间不符合本轮观察要求",
        "next": "等待价格回到本轮观察范围后再复核。",
    },
    "trend_fit": {
        "label": "趋势结构尚未满足观察条件",
        "next": "等待均线和趋势结构改善后再复核。",
    },
    "momentum_fit": {
        "label": "动量延续不足",
        "next": "等待动量信号重新确认后再复核。",
    },
    "universe_scope": {
        "label": "不在本轮扫描范围",
        "next": "确认代码、市场和主题范围后再重新扫描。",
    },
    "input_validation": {
        "label": "输入信息不完整",
        "next": "补充或修正输入后再重新扫描。",
    },
    "other": {
        "label": "未达到本轮观察条件",
        "next": "保留为观察线索，等待后续扫描复核。",
    },
}


def _candidate_diagnostic_reason_bucket(
    *,
    status: str,
    reason: Optional[str],
    failed_rules: List[str],
    missing_fields: List[str],
) -> str:
    tokens = " ".join(
        str(item or "").strip().lower()
        for item in [status, reason, *failed_rules, *missing_fields]
        if str(item or "").strip()
    )
    if status == "selected":
        return "selected"
    if status == "data_failed" or "not_enough_history" in tokens or "missing price history" in tokens:
        return "history_coverage"
    if "history" in tokens and ("missing" in tokens or "insufficient" in tokens):
        return "history_coverage"
    if "below_score_threshold" in tokens:
        return "score_fit"
    if any(marker in tokens for marker in ("liquidity", "volume", "amount", "turnover")):
        return "liquidity"
    if "price" in tokens:
        return "price_range"
    if any(marker in tokens for marker in ("trend", "ma20", "ma60")):
        return "trend_fit"
    if "momentum" in tokens:
        return "momentum_fit"
    if any(marker in tokens for marker in ("unsupported_market", "benchmark_symbol_skipped", "duplicate_symbol")):
        return "universe_scope"
    if any(marker in tokens for marker in ("invalid_payload", "invalid", "payload")):
        return "input_validation"
    return "other"


def _candidate_source_confidence_bucket(status: str, score: Optional[float], reason_bucket: str) -> str:
    if status == "data_failed" or reason_bucket == "history_coverage" or score is None:
        return "insufficient"
    if status in {"selected", "rejected", "evaluated"}:
        return "score_grade"
    return "unknown"


def _build_candidate_diagnostic_consumer_projection(
    *,
    status: str,
    score: Optional[float],
    reason: Optional[str],
    failed_rules: List[str],
    missing_fields: List[str],
) -> Dict[str, Any]:
    reason_bucket = _candidate_diagnostic_reason_bucket(
        status=status,
        reason=reason,
        failed_rules=failed_rules,
        missing_fields=missing_fields,
    )
    copy = _SCANNER_CONSUMER_REASON_COPY[reason_bucket]
    source_bucket = _candidate_source_confidence_bucket(status, score, reason_bucket)
    if source_bucket == "score_grade":
        data_quality_state = "ready"
        confidence_category = "high"
    elif source_bucket == "limited":
        data_quality_state = "limited"
        confidence_category = "limited"
    elif source_bucket == "insufficient":
        data_quality_state = "insufficient"
        confidence_category = "insufficient"
    else:
        data_quality_state = "unknown"
        confidence_category = "unknown"
    freshness_category = "insufficient" if source_bucket == "insufficient" else "unknown"
    return {
        "reasonBucket": reason_bucket,
        "reasonLabel": copy["label"],
        "nextEvidence": copy["next"],
        "sourceConfidenceBucket": source_bucket,
        "confidenceCategory": confidence_category,
        "freshnessCategory": freshness_category,
        "dataQualityState": data_quality_state,
    }


class ScannerCandidateResponse(BaseModel):
    symbol: str
    name: str
    rank: int
    score: float
    raw_score: Optional[float] = None
    final_score: Optional[float] = None
    quality_hint: Optional[str] = None
    reason_summary: Optional[str] = None
    reasons: List[str] = Field(default_factory=list)
    key_metrics: List[ScannerLabeledValue] = Field(default_factory=list)
    feature_signals: List[ScannerLabeledValue] = Field(default_factory=list)
    risk_notes: List[str] = Field(default_factory=list)
    watch_context: List[ScannerLabeledValue] = Field(default_factory=list)
    boards: List[str] = Field(default_factory=list)
    appeared_in_recent_runs: int = 0
    last_trade_date: Optional[str] = None
    scan_timestamp: Optional[str] = None
    ai_interpretation: ScannerAiInterpretationResponse = Field(default_factory=ScannerAiInterpretationResponse)
    realized_outcome: ScannerCandidateOutcomeResponse = Field(default_factory=ScannerCandidateOutcomeResponse)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    consumerDiagnostics: Dict[str, Any] = Field(default_factory=dict)
    candidateEvidenceFrame: Dict[str, Any] = Field(default_factory=dict)
    candidateResearchReadiness: Dict[str, Any] = Field(default_factory=dict)
    candidateResearchSummaryFrame: Dict[str, Any] = Field(default_factory=dict)
    candidateSourceProvenanceFrame: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("diagnostics")
    @classmethod
    def _validate_explainability_diagnostics(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return _lock_candidate_diagnostics_metadata(value)

    @field_validator("consumerDiagnostics")
    @classmethod
    def _validate_consumer_diagnostics(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return _dump_metadata_model(ScannerConsumerDiagnosticsMetadata, value)


class ScannerThemeDiagnosticsResponse(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    universe_count: int = 0
    symbols: List[str] = Field(default_factory=list)


class ScannerSummaryDiagnosticsResponse(BaseModel):
    universe_count: int = 0
    submitted_count: int = 0
    evaluated_count: int = 0
    selected_count: int = 0
    rejected_count: int = 0
    data_failed_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    limited_by_result_cap: bool = False


class ScannerCandidateDiagnosticsResponse(BaseModel):
    symbol: str
    name: Optional[str] = None
    rank: int = 0
    status: Literal["selected", "rejected", "data_failed", "skipped", "error", "evaluated"] = "skipped"
    score: Optional[float] = None
    provider: Optional[str] = None
    reason: Optional[str] = None
    failed_rules: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    consumerReasonBucket: Optional[str] = None
    consumerReasonLabel: Optional[str] = None
    consumerNextEvidence: Optional[str] = None
    consumerDiagnostics: Dict[str, Any] = Field(default_factory=dict)
    cn_provider_observation: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("consumerDiagnostics")
    @classmethod
    def _validate_consumer_diagnostics(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return _dump_metadata_model(ScannerConsumerDiagnosticsMetadata, value)

    @model_validator(mode="after")
    def _populate_consumer_projection(self) -> "ScannerCandidateDiagnosticsResponse":
        projection = _build_candidate_diagnostic_consumer_projection(
            status=str(self.status or "skipped"),
            score=self.score,
            reason=self.reason,
            failed_rules=list(self.failed_rules or []),
            missing_fields=list(self.missing_fields or []),
        )
        if not self.consumerReasonBucket:
            self.consumerReasonBucket = str(projection["reasonBucket"])
        if not self.consumerReasonLabel:
            self.consumerReasonLabel = str(projection["reasonLabel"])
        if not self.consumerNextEvidence:
            self.consumerNextEvidence = str(projection["nextEvidence"])
        consumer_diagnostics = dict(self.consumerDiagnostics or {})
        for key, value in projection.items():
            consumer_diagnostics.setdefault(key, value)
        self.consumerDiagnostics = _dump_metadata_model(
            ScannerConsumerDiagnosticsMetadata,
            consumer_diagnostics,
        )
        return self


class ScannerRunDetailResponse(BaseModel):
    id: int
    market: str
    profile: str
    profile_label: Optional[str] = None
    status: str
    run_at: Optional[str] = None
    completed_at: Optional[str] = None
    watchlist_date: Optional[str] = None
    trigger_mode: Optional[str] = None
    universe_name: str
    shortlist_size: int
    universe_size: int
    preselected_size: int
    evaluated_size: int
    source_summary: Optional[str] = None
    headline: Optional[str] = None
    universe_notes: List[str] = Field(default_factory=list)
    scoring_notes: List[str] = Field(default_factory=list)
    universe_type: str = "default"
    theme_id: Optional[str] = None
    theme_label: Optional[str] = None
    requested_symbols_count: int = 0
    accepted_symbols_count: int = 0
    rejected_symbols: List[str] = Field(default_factory=list)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    scannerContextFrame: Dict[str, Any] = Field(default_factory=dict)
    notification: ScannerNotificationResult = Field(default_factory=ScannerNotificationResult)
    failure_reason: Optional[str] = None
    comparison_to_previous: ScannerWatchlistComparisonResponse = Field(default_factory=ScannerWatchlistComparisonResponse)
    review_summary: ScannerReviewSummaryResponse = Field(default_factory=ScannerReviewSummaryResponse)
    theme: ScannerThemeDiagnosticsResponse = Field(default_factory=ScannerThemeDiagnosticsResponse)
    summary: ScannerSummaryDiagnosticsResponse = Field(default_factory=ScannerSummaryDiagnosticsResponse)
    selected: List[ScannerCandidateResponse] = Field(default_factory=list)
    candidates: List[ScannerCandidateDiagnosticsResponse] = Field(default_factory=list)
    shortlist: List[ScannerCandidateResponse] = Field(default_factory=list)


class ScannerRunHistoryItem(BaseModel):
    id: int
    market: str
    profile: str
    profile_label: Optional[str] = None
    status: str
    run_at: Optional[str] = None
    completed_at: Optional[str] = None
    watchlist_date: Optional[str] = None
    trigger_mode: Optional[str] = None
    universe_name: str
    shortlist_size: int
    universe_size: int
    preselected_size: int
    evaluated_size: int
    source_summary: Optional[str] = None
    headline: Optional[str] = None
    universe_type: str = "default"
    theme_id: Optional[str] = None
    theme_label: Optional[str] = None
    requested_symbols_count: int = 0
    accepted_symbols_count: int = 0
    rejected_symbols: List[str] = Field(default_factory=list)
    top_symbols: List[str] = Field(default_factory=list)
    notification_status: Optional[str] = None
    failure_reason: Optional[str] = None
    change_summary: ScannerWatchlistComparisonResponse = Field(default_factory=ScannerWatchlistComparisonResponse)
    review_summary: ScannerReviewSummaryResponse = Field(default_factory=ScannerReviewSummaryResponse)


class ScannerRunHistoryResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[ScannerRunHistoryItem] = Field(default_factory=list)


class ScannerStrategySimulationWindow(BaseModel):
    lookback_days: int = Field(..., alias="lookbackDays")
    forward_days: int = Field(..., alias="forwardDays")
    run_count: int = Field(..., alias="runCount")

    model_config = {"populate_by_name": True}


class ScannerStrategySimulationSummary(BaseModel):
    historical_runs: int = Field(0, alias="historicalRuns")
    selection_events: int = Field(0, alias="selectionEvents")
    avg_selected_per_run: Optional[float] = Field(None, alias="avgSelectedPerRun")
    hit_rate: Optional[float] = Field(None, alias="hitRate")
    avg_forward_return_pct: Optional[float] = Field(None, alias="avgForwardReturnPct")
    median_forward_return_pct: Optional[float] = Field(None, alias="medianForwardReturnPct")
    avg_benchmark_return_pct: Optional[float] = Field(None, alias="avgBenchmarkReturnPct")
    avg_excess_return_pct: Optional[float] = Field(None, alias="avgExcessReturnPct")
    positive_selection_rate: Optional[float] = Field(None, alias="positiveSelectionRate")
    best_symbol: Optional[str] = Field(None, alias="bestSymbol")
    worst_symbol: Optional[str] = Field(None, alias="worstSymbol")
    data_coverage: Optional[float] = Field(None, alias="dataCoverage")

    model_config = {"populate_by_name": True}


class ScannerStrategySimulationRun(BaseModel):
    run_id: int = Field(..., alias="runId")
    run_at: Optional[str] = Field(None, alias="runAt")
    selected_count: int = Field(0, alias="selectedCount")
    rejected_count: int = Field(0, alias="rejectedCount")
    selected_symbols: List[str] = Field(default_factory=list, alias="selectedSymbols")
    avg_forward_return_pct: Optional[float] = Field(None, alias="avgForwardReturnPct")
    benchmark_return_pct: Optional[float] = Field(None, alias="benchmarkReturnPct")
    excess_return_pct: Optional[float] = Field(None, alias="excessReturnPct")

    model_config = {"populate_by_name": True}


class ScannerStrategySimulationSymbol(BaseModel):
    symbol: str
    selection_count: int = Field(0, alias="selectionCount")
    avg_score: Optional[float] = Field(None, alias="avgScore")
    avg_forward_return_pct: Optional[float] = Field(None, alias="avgForwardReturnPct")
    hit_rate: Optional[float] = Field(None, alias="hitRate")
    best_forward_return_pct: Optional[float] = Field(None, alias="bestForwardReturnPct")
    worst_forward_return_pct: Optional[float] = Field(None, alias="worstForwardReturnPct")

    model_config = {"populate_by_name": True}


class ScannerStrategySimulationResponse(BaseModel):
    theme: Optional[str] = None
    profile: str
    market: str
    window: ScannerStrategySimulationWindow
    status: Literal["ready", "insufficient_history", "partial", "failed"]
    summary: ScannerStrategySimulationSummary = Field(default_factory=ScannerStrategySimulationSummary)
    runs: List[ScannerStrategySimulationRun] = Field(default_factory=list)
    symbols: List[ScannerStrategySimulationSymbol] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class ScannerOperationRunSummary(BaseModel):
    id: int
    watchlist_date: Optional[str] = None
    trigger_mode: Optional[str] = None
    status: str
    run_at: Optional[str] = None
    headline: Optional[str] = None
    shortlist_size: int = 0
    notification_status: Optional[str] = None
    failure_reason: Optional[str] = None


class ScannerOperationalStatusResponse(BaseModel):
    market: str
    profile: str
    profile_label: Optional[str] = None
    watchlist_date: str
    today_trading_day: bool
    schedule_enabled: bool
    schedule_time: Optional[str] = None
    schedule_run_immediately: bool = False
    notification_enabled: bool = False
    today_watchlist: Optional[ScannerOperationRunSummary] = None
    last_run: Optional[ScannerOperationRunSummary] = None
    last_scheduled_run: Optional[ScannerOperationRunSummary] = None
    last_manual_run: Optional[ScannerOperationRunSummary] = None
    latest_failure: Optional[ScannerOperationRunSummary] = None
    quality_summary: ScannerQualitySummaryResponse = Field(default_factory=ScannerQualitySummaryResponse)
