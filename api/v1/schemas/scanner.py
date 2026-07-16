# -*- coding: utf-8 -*-
"""Market scanner API schemas."""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.core.scanner_skip_reason import normalize_scanner_skip_reason


SCANNER_CONSUMER_DATA_QUALITY_LABELS = {"ready", "delayed", "cached", "partial", "no_evidence", "unavailable"}
SCANNER_NO_ADVICE_LABEL = "Observation-only research context; not investment advice."
SCANNER_PUBLIC_FAILURE_MESSAGE = "Scanner execution failed. Review readiness and retry."
SCANNER_PUBLIC_NOTIFICATION_FAILURE_MESSAGE = "Scanner notification failed."
_SCANNER_FORBIDDEN_CONSUMER_KEYS = {
    "fallback",
    "trustlevel",
    "reasoncode",
    "reasoncodes",
    "launchverdict",
    "consumervisible",
    "advisoryonly",
    "liveenforcement",
    "isfallback",
    "isstale",
    "ispartial",
    "sourcetype",
    "scorecontributionallowed",
    "observationonly",
    "observeonly",
    "sourceauthorityallowed",
    "providerobservation",
    "cnproviderobservation",
    "providername",
    "providerid",
    "providerclass",
    "providerattempted",
    "requiredproviderclass",
    "endpointhost",
    "apikeypresent",
    "exceptionclass",
    "exceptionchain",
    "requestid",
    "traceid",
    "cachekey",
    "rawpayload",
    "rawproviderpayload",
    "credential",
    "env",
    "apikey",
    "password",
    "secret",
    "privatekey",
    "rawprovidererror",
}
_SCANNER_FORBIDDEN_CONSUMER_TEXT_RE = re.compile(
    r"fallback|trustlevel|reasoncode|launchverdict|consumervisible|advisoryonly|"
    r"liveenforcement|isfallback|isstale|ispartial|sourcetype|"
    r"scorecontributionallowed|observationonly|raw provider error|traceback|"
    r"https?://|api[_-]?key|secret|cookie|session_id|token",
    re.IGNORECASE,
)
_SCANNER_PACKET_FORBIDDEN_TEXT_RE = re.compile(
    r"fallback|trustlevel|reasoncode|launchverdict|consumervisible|advisoryonly|"
    r"liveenforcement|isfallback|isstale|ispartial|sourcetype|"
    r"scorecontributionallowed|sourceauthorityallowed|raw[_ -]?(provider|payload|diagnostic|result|error)|"
    r"provider[_ -]?(payload|timeout|error|diagnostic|trace)|request[_ -]?id|trace[_ -]?id|"
    r"_blocked|_gate|debug|stack[_ -]?trace|traceback|context_snapshot|"
    r"https?://|api[_-]?key|secret|cookie|session_id|token",
    re.IGNORECASE,
)
_SCANNER_PACKET_ADVICE_TEXT_RE = re.compile(
    r"建议(买入|卖出|加仓|减仓|持有)|买入|卖出|下单|立即交易|立即买入|"
    r"交易建议|投资建议|止损|止盈|目标价|目标位|目标区间|仓位建议|必买|稳赚|保证收益|"
    r"\b(buy now|sell now|place order|submit order|trade recommendation|trading advice|"
    r"investment advice|recommended trade|strategy recommendation|ai recommends you buy|"
    r"best contract|guaranteed return|guaranteed|take profit|stop loss|target price|"
    r"position sizing|live trading|execution ready)\b",
    re.IGNORECASE,
)


def _scanner_normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _scanner_consumer_data_quality_label(*values: Any) -> str:
    tokens: List[str] = []
    for value in values:
        if isinstance(value, dict):
            tokens.extend(str(key) for key, flag in value.items() if flag is True)
            tokens.extend(str(item) for item in value.values() if isinstance(item, str))
        elif isinstance(value, (list, tuple, set)):
            tokens.extend(str(item) for item in value)
        elif value is not None:
            tokens.append(str(value))
    normalized = " ".join(tokens).strip().lower()
    if not normalized:
        return "no_evidence"
    if any(marker in normalized for marker in ("unavailable", "provider_down", "provider_error", "data_failed", "failed", "error")):
        return "unavailable"
    if any(marker in normalized for marker in ("missing", "insufficient", "no_data", "no evidence", "no_evidence")):
        return "no_evidence"
    if any(marker in normalized for marker in ("fallback", "partial", "synthetic", "proxy", "limited", "observation")):
        return "partial"
    if any(marker in normalized for marker in ("stale", "delayed")):
        return "delayed"
    if any(marker in normalized for marker in ("cached", "cache_snapshot", "local")):
        return "cached"
    if any(marker in normalized for marker in ("ready", "available", "complete", "fresh", "live", "selected", "score_grade")):
        return "ready"
    return "no_evidence"


def _scanner_sanitize_consumer_value(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = _scanner_normalize_key(str(key))
            if any(marker in normalized_key for marker in _SCANNER_FORBIDDEN_CONSUMER_KEYS):
                continue
            clean = _scanner_sanitize_consumer_value(item)
            if clean is not None:
                sanitized[str(key)] = clean
        return sanitized
    if isinstance(value, list):
        return [item for item in (_scanner_sanitize_consumer_value(item) for item in value) if item is not None]
    if isinstance(value, str):
        if _SCANNER_FORBIDDEN_CONSUMER_TEXT_RE.search(value):
            return None
        return value
    return value


def _scanner_packet_safe_text(value: Any) -> Optional[str]:
    if value is None or isinstance(value, (dict, list, tuple, set)):
        return None
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        return None
    if _SCANNER_PACKET_FORBIDDEN_TEXT_RE.search(text):
        return None
    if _SCANNER_PACKET_ADVICE_TEXT_RE.search(text):
        return None
    return text


def _scanner_packet_safe_list(values: Any, *, limit: int = 4) -> List[str]:
    raw_items = values if isinstance(values, (list, tuple, set)) else [values]
    result: List[str] = []
    seen = set()
    for item in raw_items:
        text = _scanner_packet_safe_text(item)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _scanner_packet_first_safe(*values: Any) -> Optional[str]:
    for value in values:
        if isinstance(value, (list, tuple, set)):
            text = _scanner_packet_first_safe(*value)
        else:
            text = _scanner_packet_safe_text(value)
        if text:
            return text
    return None


def _scanner_packet_labeled_values(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    result: List[str] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        label = _scanner_packet_safe_text(item.get("label"))
        item_value = _scanner_packet_safe_text(item.get("value"))
        if label and item_value:
            result.append(f"{label}: {item_value}")
        elif label:
            result.append(label)
    return _scanner_packet_safe_list(result)


def _build_scanner_candidate_research_packet(value: Any) -> Dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    summary_frame = payload.get("candidateResearchSummaryFrame")
    if not isinstance(summary_frame, dict):
        summary_frame = {}
    readiness = payload.get("candidateResearchReadiness")
    if not isinstance(readiness, dict):
        readiness = {}
    consumer_diagnostics = payload.get("consumerDiagnostics")
    if not isinstance(consumer_diagnostics, dict):
        consumer_diagnostics = {}

    why_surfaced = _scanner_packet_first_safe(
        summary_frame.get("primaryResearchReason"),
        payload.get("reason_summary"),
        payload.get("reasons"),
    ) or "本轮扫描出现可复核的趋势、动量或流动性线索。"

    primary_evidence = _scanner_packet_safe_list(summary_frame.get("evidenceHighlights"))
    if not primary_evidence:
        primary_evidence = _scanner_packet_safe_list(payload.get("reasons"), limit=3)
    if not primary_evidence:
        primary_evidence = _scanner_packet_labeled_values(payload.get("feature_signals"))
    if not primary_evidence:
        primary_evidence = _scanner_packet_labeled_values(payload.get("key_metrics"))

    limiting_evidence = _scanner_packet_safe_list(summary_frame.get("missingEvidence"))
    if not limiting_evidence:
        limiting_evidence = _scanner_packet_safe_list(readiness.get("missingEvidence"))
    if not limiting_evidence:
        limiting_evidence = _scanner_packet_safe_list(consumer_diagnostics.get("missingEvidence"))
    if not limiting_evidence:
        limiting_evidence = _scanner_packet_safe_list(summary_frame.get("blockingReasons"))
    if not limiting_evidence:
        limiting_evidence = _scanner_packet_safe_list(payload.get("risk_notes"))

    data_quality_notes: List[str] = []
    for label, source in (
        ("data quality", consumer_diagnostics.get("dataQualityState")),
        ("freshness", consumer_diagnostics.get("freshnessState")),
        ("readiness", readiness.get("readinessState")),
    ):
        safe_value = _scanner_packet_safe_text(source)
        if safe_value:
            data_quality_notes.append(f"{label}: {safe_value}")
    data_quality_notes.extend(_scanner_packet_safe_list(consumer_diagnostics.get("warningFlags"), limit=2))
    data_quality_notes.extend(_scanner_packet_safe_list(consumer_diagnostics.get("userFacingLabels"), limit=2))
    data_quality_notes = _scanner_packet_safe_list(data_quality_notes, limit=4)

    reason_label = _scanner_packet_first_safe(
        consumer_diagnostics.get("reasonLabel"),
        payload.get("quality_hint"),
    ) or "证据有限，需补充研究"
    research_next_step = _scanner_packet_first_safe(
        summary_frame.get("nextResearchStep"),
        consumer_diagnostics.get("nextEvidence"),
        readiness.get("nextEvidenceNeeded"),
    ) or "补充缺口证据后再复核。"

    return {
        "whySurfaced": why_surfaced,
        "primaryEvidence": primary_evidence,
        "limitingEvidence": limiting_evidence,
        "dataQualityNotes": data_quality_notes,
        "rejectedOrLimitedReasonSafeLabel": reason_label,
        "researchNextStep": research_next_step,
        "evidenceBoundaries": _build_scanner_candidate_evidence_boundaries(payload),
        "noAdviceLabel": SCANNER_NO_ADVICE_LABEL,
        "observationOnly": True,
    }


def _scanner_safe_string_list(values: Any, *, limit: int = 6) -> List[str]:
    raw_items = values if isinstance(values, (list, tuple, set)) else [values]
    result: List[str] = []
    seen = set()
    for item in raw_items:
        text = _scanner_packet_safe_text(item)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _build_scanner_candidate_evidence_boundaries(value: Any) -> Dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    readiness = payload.get("candidateResearchReadiness") if isinstance(payload.get("candidateResearchReadiness"), dict) else {}
    summary_frame = payload.get("candidateResearchSummaryFrame") if isinstance(payload.get("candidateResearchSummaryFrame"), dict) else {}
    consumer_diagnostics = payload.get("consumerDiagnostics") if isinstance(payload.get("consumerDiagnostics"), dict) else {}
    ohlcv = payload.get("historicalOhlcvReadiness") if isinstance(payload.get("historicalOhlcvReadiness"), dict) else {}
    source_frame = payload.get("candidateSourceProvenanceFrame") if isinstance(payload.get("candidateSourceProvenanceFrame"), dict) else {}

    missing_evidence = _scanner_safe_string_list(
        readiness.get("missingEvidence")
        or summary_frame.get("missingEvidence")
        or consumer_diagnostics.get("missingEvidence")
        or ohlcv.get("missingRequirements")
    )
    next_evidence = _scanner_safe_string_list(
        readiness.get("nextEvidenceNeeded")
        or summary_frame.get("nextResearchStep")
        or consumer_diagnostics.get("nextEvidence")
    )
    return {
        "boundaryType": "observation_only",
        "noAdvice": True,
        "noAdviceLabel": SCANNER_NO_ADVICE_LABEL,
        "decisionGrade": False,
        "observationMode": True,
        "readinessState": _scanner_packet_safe_text(
            readiness.get("readinessState")
            or summary_frame.get("frameState")
            or "unknown"
        ) or "unknown",
        "sourceAuthority": _scanner_packet_safe_text(readiness.get("sourceAuthority")) or "unknown",
        "freshness": _scanner_packet_safe_text(
            readiness.get("freshnessFloor")
            or summary_frame.get("freshness")
            or consumer_diagnostics.get("freshnessCategory")
            or "unknown"
        ) or "unknown",
        "missingEvidence": missing_evidence,
        "nextEvidenceNeeded": next_evidence,
        "ohlcvState": ohlcv.get("overallState"),
        "sourceProvenance": {
            "entryCount": int(source_frame.get("entryCount") or 0),
            "scoringEvidenceCount": int(source_frame.get("scoreContributionAllowedCount") or 0),
            "observationEvidenceCount": int(source_frame.get("observationOnlyCount") or 0),
        },
    }


def _build_scanner_candidate_ranking_confidence(value: Any) -> Dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    consumer_diagnostics = payload.get("consumerDiagnostics") if isinstance(payload.get("consumerDiagnostics"), dict) else {}
    diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), dict) else {}
    explainability = diagnostics.get("score_explainability") if isinstance(diagnostics.get("score_explainability"), dict) else {}
    score_confidence = consumer_diagnostics.get("scoreConfidence", explainability.get("score_confidence"))
    return {
        "rank": int(payload.get("rank") or 0),
        "score": payload.get("score"),
        "rawScore": payload.get("raw_score"),
        "finalScore": payload.get("final_score"),
        "scoreConfidence": score_confidence,
        "confidenceCategory": str(consumer_diagnostics.get("confidenceCategory") or "unknown"),
        "dataQualityState": str(consumer_diagnostics.get("dataQualityState") or "unknown"),
        "sourceConfidenceBucket": str(consumer_diagnostics.get("sourceConfidenceBucket") or "unknown"),
        "freshnessCategory": str(consumer_diagnostics.get("freshnessCategory") or "unknown"),
        "rankingUse": "relative_observation_only",
    }


def _scanner_consumer_diagnostics_payload(value: Any) -> Dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    quality = _scanner_consumer_data_quality_label(
        payload.get("dataQualityState"),
        payload.get("freshnessState"),
        payload.get("freshnessCategory"),
        payload.get("sourceClass"),
        payload.get("status"),
        payload.get("sourceConfidenceBucket"),
    )
    allowed = {
        "status",
        "reasonBucket",
        "reasonLabel",
        "nextEvidence",
        "sourceConfidenceBucket",
        "confidenceCategory",
        "freshnessCategory",
        "scoreConfidence",
        "missingEvidence",
        "userFacingLabels",
        "warningFlags",
        "investorSignal",
    }
    sanitized = {
        key: _scanner_sanitize_consumer_value(payload.get(key))
        for key in allowed
        if key in payload
    }
    sanitized = {key: item for key, item in sanitized.items() if item is not None}
    sanitized["dataQualityState"] = quality
    return sanitized


def sanitize_scanner_consumer_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Project scanner run payloads into the normal-user API contract."""
    result = copy.deepcopy(payload or {})
    if isinstance(result.get("diagnostics"), dict):
        result["diagnostics"] = _scanner_sanitize_consumer_value(result["diagnostics"])
    for frame_key in ("scannerContextFrame",):
        if isinstance(result.get(frame_key), dict):
            result[frame_key] = _scanner_sanitize_consumer_value(result[frame_key])
    for collection_key in ("shortlist", "selected"):
        items = result.get(collection_key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            diagnostics = item.get("diagnostics") if isinstance(item.get("diagnostics"), dict) else {}
            consumer_diagnostics = item.get("consumerDiagnostics") if isinstance(item.get("consumerDiagnostics"), dict) else {}
            source_confidence = {}
            score_explainability = diagnostics.get("score_explainability") if isinstance(diagnostics, dict) else {}
            if isinstance(score_explainability, dict) and isinstance(score_explainability.get("source_confidence"), dict):
                source_confidence = score_explainability["source_confidence"]
            item["consumerDiagnostics"] = _scanner_consumer_diagnostics_payload(
                {
                    **consumer_diagnostics,
                    "dataQualityState": consumer_diagnostics.get("dataQualityState")
                    or diagnostics.get("dataQualityState")
                    or source_confidence.get("freshness"),
                    "freshnessState": consumer_diagnostics.get("freshnessState") or source_confidence.get("freshness"),
                    "sourceClass": consumer_diagnostics.get("sourceClass") or source_confidence.get("sourceType"),
                    "status": consumer_diagnostics.get("status"),
                }
            )
            item["diagnostics"] = {}
            item["candidateSourceProvenanceFrame"] = {}
            if isinstance(item.get("historicalOhlcvReadiness"), dict):
                item["historicalOhlcvReadiness"] = _scanner_sanitize_consumer_value(item["historicalOhlcvReadiness"])
            item["suppressCandidateResearchPacket"] = True
            for frame_key in (
                "candidateEvidenceFrame",
                "candidateResearchReadiness",
                "candidateResearchSummaryFrame",
            ):
                if isinstance(item.get(frame_key), dict):
                    item[frame_key] = _scanner_sanitize_consumer_value(item[frame_key])
    candidates = result.get("candidates")
    if isinstance(candidates, list):
        for item in candidates:
            if not isinstance(item, dict):
                continue
            item.pop("provider", None)
            item.pop("reason", None)
            item["failed_rules"] = []
            item["missing_fields"] = []
            item["metrics"] = {}
            item["cn_provider_observation"] = {}
            if isinstance(item.get("historicalOhlcvReadiness"), dict):
                item["historicalOhlcvReadiness"] = _scanner_sanitize_consumer_value(item["historicalOhlcvReadiness"])
            item["consumerDiagnostics"] = _scanner_consumer_diagnostics_payload(item.get("consumerDiagnostics"))
    return result


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

    @model_validator(mode="after")
    def _sanitize_public_notification_failure(self) -> "ScannerNotificationResult":
        self.report_path = None
        if self.status == "failed" and self.message:
            self.message = SCANNER_PUBLIC_NOTIFICATION_FAILURE_MESSAGE
        return self


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
    reason_bucket = normalize_scanner_skip_reason(
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
    market: Optional[str] = None
    name: str
    rank: int
    score: float
    priority: Optional[str] = None
    reason: Optional[str] = None
    limitation: Optional[str] = None
    nextCheck: Optional[str] = None
    evidenceQuality: Optional[str] = None
    dataFreshness: Dict[str, Any] = Field(default_factory=dict)
    noAdviceDisclosure: Optional[str] = None
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
    historicalOhlcvReadiness: Dict[str, Any] = Field(default_factory=dict)
    candidateEvidenceFrame: Dict[str, Any] = Field(default_factory=dict)
    candidateResearchReadiness: Dict[str, Any] = Field(default_factory=dict)
    candidateResearchSummaryFrame: Dict[str, Any] = Field(default_factory=dict)
    candidateSourceProvenanceFrame: Dict[str, Any] = Field(default_factory=dict)
    candidateResearchPacket: Dict[str, Any] = Field(default_factory=dict)
    evidenceBoundaries: Dict[str, Any] = Field(default_factory=dict)
    rankingConfidence: Dict[str, Any] = Field(default_factory=dict)
    noAdviceLabel: str = SCANNER_NO_ADVICE_LABEL
    suppressCandidateResearchPacket: bool = Field(False, exclude=True)

    @field_validator("diagnostics")
    @classmethod
    def _validate_explainability_diagnostics(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return _lock_candidate_diagnostics_metadata(value)

    @field_validator("consumerDiagnostics")
    @classmethod
    def _validate_consumer_diagnostics(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return _dump_metadata_model(ScannerConsumerDiagnosticsMetadata, value)

    @model_validator(mode="after")
    def _populate_candidate_research_packet(self) -> "ScannerCandidateResponse":
        payload = self.model_dump(
            exclude={
                "candidateResearchPacket",
                "evidenceBoundaries",
                "rankingConfidence",
            }
        )
        if not self.evidenceBoundaries:
            self.evidenceBoundaries = _build_scanner_candidate_evidence_boundaries(payload)
        if not self.rankingConfidence:
            self.rankingConfidence = _build_scanner_candidate_ranking_confidence(payload)
        if not self.noAdviceLabel:
            self.noAdviceLabel = SCANNER_NO_ADVICE_LABEL
        if self.suppressCandidateResearchPacket:
            self.candidateResearchPacket = {}
            return self
        self.candidateResearchPacket = _build_scanner_candidate_research_packet(payload)
        return self


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
    historicalOhlcvReadiness: Dict[str, Any] = Field(default_factory=dict)
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
    dataReadiness: Dict[str, Any] = Field(default_factory=dict)
    scannerLineage: Dict[str, Any] = Field(default_factory=dict)
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

    @field_validator("failure_reason", mode="before")
    @classmethod
    def _sanitize_failure_reason(cls, value: Any) -> Optional[str]:
        return SCANNER_PUBLIC_FAILURE_MESSAGE if str(value or "").strip() else None

    @field_validator("diagnostics", mode="before")
    @classmethod
    def _sanitize_failure_diagnostics(cls, value: Any) -> Dict[str, Any]:
        diagnostics = copy.deepcopy(value) if isinstance(value, dict) else {}
        failure = diagnostics.get("failure")
        if isinstance(failure, dict) and failure.get("message"):
            failure["message"] = SCANNER_PUBLIC_FAILURE_MESSAGE
        return diagnostics


class ScannerResearchOverlayOriginalState(BaseModel):
    ticker: str
    rank: int = 0
    score: Optional[float] = None
    rawScore: Optional[float] = None
    finalScore: Optional[float] = None
    status: str = "selected"


class ScannerResearchOverlayFitFrame(BaseModel):
    state: str
    signals: List[Dict[str, Any]] = Field(default_factory=list)


class ScannerResearchOverlayThemeAlignment(BaseModel):
    state: str
    themes: List[str] = Field(default_factory=list)
    signals: List[Dict[str, Any]] = Field(default_factory=list)


class ScannerResearchOverlayEvidenceQuality(BaseModel):
    status: str
    score: int = 0
    missingEvidence: List[str] = Field(default_factory=list)


class ScannerResearchOverlayDrilldownTarget(BaseModel):
    label: str
    route: str
    section: str
    reason: str


class ScannerResearchOverlayItem(BaseModel):
    ticker: str
    overlayState: str
    researchSummary: str
    originalScannerCandidateState: ScannerResearchOverlayOriginalState
    researchPriority: str
    regimeFit: ScannerResearchOverlayFitFrame
    themeAlignment: ScannerResearchOverlayThemeAlignment
    evidenceQuality: ScannerResearchOverlayEvidenceQuality
    whyThisMattersToday: List[str] = Field(default_factory=list)
    whatToVerify: List[str] = Field(default_factory=list)
    riskFlags: List[str] = Field(default_factory=list)
    riskObservations: List[str] = Field(default_factory=list)
    evidenceGaps: List[str] = Field(default_factory=list)
    drilldownTargets: List[ScannerResearchOverlayDrilldownTarget] = Field(default_factory=list)
    consumerIssues: List[Dict[str, str]] = Field(default_factory=list)
    noAdviceDisclosure: str


class ScannerResearchOverlayThemeLeadershipPacket(BaseModel):
    theme: str = ""
    leadershipState: Literal["broadening", "concentrated", "fading", "insufficient_evidence"] = "insufficient_evidence"
    leadingSymbols: List[str] = Field(default_factory=list)
    laggingSymbols: List[str] = Field(default_factory=list)
    breadthEvidence: Dict[str, Any] = Field(default_factory=dict)
    concentrationEvidence: Dict[str, Any] = Field(default_factory=dict)
    evidenceGaps: List[str] = Field(default_factory=list)
    freshness: str = "unknown"
    suggestedResearchPath: List[str] = Field(default_factory=list)
    observationOnly: Literal[True] = True


class ScannerResearchOverlayDataQuality(BaseModel):
    status: str
    availableCandidateCount: int = 0
    reliableCandidateCount: int = 0
    missingEvidence: List[str] = Field(default_factory=list)
    consumerIssues: List[Dict[str, str]] = Field(default_factory=list)


class ScannerResearchOverlayResponse(BaseModel):
    schemaVersion: str
    generatedAt: str
    runId: Optional[int] = None
    market: str = ""
    profile: str = ""
    overlayState: str
    researchSummary: str
    items: List[ScannerResearchOverlayItem] = Field(default_factory=list)
    themeLeadershipPacket: ScannerResearchOverlayThemeLeadershipPacket = Field(
        default_factory=ScannerResearchOverlayThemeLeadershipPacket
    )
    aggregateSummary: Dict[str, Any] = Field(default_factory=dict)
    queueDiversity: Dict[str, Any] = Field(default_factory=dict)
    dataQuality: ScannerResearchOverlayDataQuality
    missingEvidence: List[str] = Field(default_factory=list)
    evidenceGaps: List[str] = Field(default_factory=list)
    riskObservations: List[str] = Field(default_factory=list)
    drilldownTargets: List[ScannerResearchOverlayDrilldownTarget] = Field(default_factory=list)
    consumerIssues: List[Dict[str, str]] = Field(default_factory=list)
    noAdviceDisclosure: str
    observationOnly: Literal[True] = True
    decisionGrade: Literal[False] = False


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

    @field_validator("failure_reason", mode="before")
    @classmethod
    def _sanitize_failure_reason(cls, value: Any) -> Optional[str]:
        return SCANNER_PUBLIC_FAILURE_MESSAGE if str(value or "").strip() else None


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

    @field_validator("failure_reason", mode="before")
    @classmethod
    def _sanitize_failure_reason(cls, value: Any) -> Optional[str]:
        return SCANNER_PUBLIC_FAILURE_MESSAGE if str(value or "").strip() else None


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
