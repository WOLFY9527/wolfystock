# -*- coding: utf-8 -*-
"""Market scanner API schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


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
    cn_provider_observation: Dict[str, Any] = Field(default_factory=dict)


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
