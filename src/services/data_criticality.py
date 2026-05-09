# -*- coding: utf-8 -*-
"""Decision-critical data quality helpers for analysis hot paths."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional


class DataCriticality(str, Enum):
    REQUIRED = "required"
    IMPORTANT = "important"
    OPTIONAL = "optional"
    DECORATIVE = "decorative"


REQUIRED_FIELDS = {
    "quote.price",
    "quote.previous_close",
    "candles.ohlc",
    "metadata.source",
    "metadata.as_of",
}

IMPORTANT_FIELDS = {
    "technicals.ma",
    "technicals.rsi",
    "technicals.macd",
    "technicals.volatility",
    "fundamentals.revenue",
    "fundamentals.eps",
    "fundamentals.pe",
    "fundamentals.roe",
    "fundamentals.margin",
    "profile.market_cap",
    "profile.sector",
}

OPTIONAL_FIELDS = {
    "news",
    "sentiment",
    "analyst_ratings",
    "detailed_fundamentals",
    "social_data",
}

DECORATIVE_FIELDS = {
    "provider_prose",
    "raw_provider_diagnostics",
    "social_snippets",
    "non_decision_metadata",
}

SAFE_REASON_RE = re.compile(r"[^a-zA-Z0-9_.:-]+")
SECRET_MARKERS = (
    "api_key",
    "apikey",
    "secret",
    "token",
    "bearer",
    "password",
    "cookie",
    "session",
    "sk-",
    "webhook",
    "http://",
    "https://",
    "traceback",
    "stack trace",
)

ENRICHMENT_SOURCES = ("news", "sentiment", "detailed_fundamentals")
NON_LIVE_SOURCE_MARKERS = ("synthetic", "mock", "fixture", "fallback")


@dataclass(frozen=True)
class DataQualityReport:
    data_quality_tier: str
    data_quality_score: int
    required_available: bool
    important_missing: List[str] = field(default_factory=list)
    optional_missing: List[str] = field(default_factory=list)
    stale_sources: List[str] = field(default_factory=list)
    provider_timeouts: List[str] = field(default_factory=list)
    provider_cooldowns: List[str] = field(default_factory=list)
    confidence_cap: int = 100
    reason_codes: List[str] = field(default_factory=list)
    freshness: Dict[str, Any] = field(default_factory=dict)
    enrichment_status: str = "skipped"
    enrichment_sources: List[str] = field(default_factory=list)
    completed_sources: List[str] = field(default_factory=list)
    pending_sources: List[str] = field(default_factory=list)
    failed_sources: List[str] = field(default_factory=list)
    skipped_sources: List[str] = field(default_factory=list)
    enrichment_reasons: Dict[str, List[str]] = field(default_factory=dict)
    enrichment_updated_at: Optional[str] = None
    enrichment_as_of: Optional[str] = None

    def to_api_dict(self) -> Dict[str, Any]:
        return {
            "dataQualityTier": self.data_quality_tier,
            "dataQualityScore": self.data_quality_score,
            "requiredAvailable": self.required_available,
            "importantMissing": list(self.important_missing),
            "optionalMissing": list(self.optional_missing),
            "staleSources": list(self.stale_sources),
            "providerTimeouts": list(self.provider_timeouts),
            "providerCooldowns": list(self.provider_cooldowns),
            "confidenceCap": self.confidence_cap,
            "reasonCodes": list(self.reason_codes),
            "freshness": dict(self.freshness),
            "enrichmentStatus": self.enrichment_status,
            "enrichmentSources": list(self.enrichment_sources),
            "completedSources": list(self.completed_sources),
            "pendingSources": list(self.pending_sources),
            "failedSources": list(self.failed_sources),
            "skippedSources": list(self.skipped_sources),
            "enrichmentReasons": {key: list(value) for key, value in self.enrichment_reasons.items()},
            "enrichmentUpdatedAt": self.enrichment_updated_at,
            "enrichmentAsOf": self.enrichment_as_of,
        }


def classify_field(field_name: str) -> DataCriticality:
    normalized = str(field_name or "").strip()
    if normalized in REQUIRED_FIELDS:
        return DataCriticality.REQUIRED
    if normalized in IMPORTANT_FIELDS:
        return DataCriticality.IMPORTANT
    if normalized in OPTIONAL_FIELDS:
        return DataCriticality.OPTIONAL
    return DataCriticality.DECORATIVE if normalized in DECORATIVE_FIELDS else DataCriticality.OPTIONAL


def sanitize_reason_code(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "unknown"
    if any(marker in text for marker in SECRET_MARKERS):
        return "redacted_sensitive_reason"
    text = SAFE_REASON_RE.sub("_", text).strip("_")
    return (text or "unknown")[:80]


def sanitize_reason_codes(values: Iterable[Any]) -> List[str]:
    result: List[str] = []
    for value in values:
        code = sanitize_reason_code(value)
        if code not in result:
            result.append(code)
    return result[:24]


def _status_bucket(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status in {"ok", "used", "partial", "completed", "success"}:
        return "completed"
    if status in {"pending", "attempting", "running"}:
        return "pending"
    if status in {"failed", "missing", "timeout", "unavailable", "error"}:
        return "failed"
    if status in {"not_configured", "skipped", "configured_not_used", "not_supported"}:
        return "skipped"
    return "unknown"


def _source_reasons(
    *,
    source: str,
    diagnostics: Mapping[str, Any],
    data_quality: Mapping[str, Any],
    missing_fields: List[str],
) -> List[str]:
    reasons: List[Any] = []
    failure_reasons = diagnostics.get("failure_reasons", [])
    if isinstance(failure_reasons, (list, tuple, set)):
        for reason in failure_reasons:
            reason_text = str(reason or "").lower()
            if (
                source == "news" and "news" in reason_text
                or source == "sentiment" and "sentiment" in reason_text
                or source == "detailed_fundamentals" and ("fundamental" in reason_text or "earning" in reason_text)
            ):
                reasons.append(reason)
    if source == "news":
        reasons.append(diagnostics.get("news_reason"))
        status = diagnostics.get("news_status")
    elif source == "sentiment":
        reasons.append(diagnostics.get("sentiment_reason"))
        status = diagnostics.get("sentiment_status") or data_quality.get("sentiment_status")
    else:
        reasons.extend([
            diagnostics.get("fundamentals_reason"),
            diagnostics.get("earnings_reason"),
        ])
        status = diagnostics.get("fundamentals_status") or diagnostics.get("earnings_status")
        if "detailed_fundamentals" in missing_fields:
            reasons.append("detailed_fundamentals_missing")
    if (
        status
        and _status_bucket(status) not in {"completed", "unknown"}
        and not (source == "news" and any(str(reason).lower() == "optional_news_timeout" for reason in reasons))
        and not (source == "sentiment" and any(str(reason).lower() == "optional_sentiment_timeout" for reason in reasons))
    ):
        reasons.append(f"{source}_{status}")
    return sanitize_reason_codes(reason for reason in reasons if reason)


def _build_enrichment_metadata(
    *,
    data_quality: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    missing_fields: List[str],
    optional_enrichment_pending: bool,
    freshness: Mapping[str, Any],
) -> Dict[str, Any]:
    failure_reasons = [str(item or "").lower() for item in diagnostics.get("failure_reasons", []) or []]

    source_states: Dict[str, str] = {}
    for source in ENRICHMENT_SOURCES:
        if source == "news":
            status = _status_bucket(diagnostics.get("news_status"))
            if optional_enrichment_pending and any("news" in reason and "timeout" in reason for reason in failure_reasons):
                status = "pending"
        elif source == "sentiment":
            status = _status_bucket(diagnostics.get("sentiment_status") or data_quality.get("sentiment_status"))
            if optional_enrichment_pending and any("sentiment" in reason and "timeout" in reason for reason in failure_reasons):
                status = "pending"
        else:
            fundamentals_status = _status_bucket(diagnostics.get("fundamentals_status"))
            earnings_status = _status_bucket(diagnostics.get("earnings_status"))
            if "detailed_fundamentals" in missing_fields:
                status = "failed"
            elif "completed" in {fundamentals_status, earnings_status}:
                status = "completed"
            elif "failed" in {fundamentals_status, earnings_status}:
                status = "failed"
            elif "pending" in {fundamentals_status, earnings_status}:
                status = "pending"
            elif {fundamentals_status, earnings_status} <= {"skipped", "unknown"}:
                status = "skipped"
            else:
                status = "unknown"
        source_states[source] = "skipped" if status == "unknown" else status

    completed = [source for source, status in source_states.items() if status == "completed"]
    pending = [source for source, status in source_states.items() if status == "pending"]
    failed = [source for source, status in source_states.items() if status == "failed"]
    skipped = [source for source, status in source_states.items() if status == "skipped"]

    if pending:
        enrichment_status = "pending"
    elif len(completed) == len(ENRICHMENT_SOURCES):
        enrichment_status = "complete"
    elif failed and not completed and not pending:
        enrichment_status = "failed"
    elif completed or failed:
        enrichment_status = "partial"
    else:
        enrichment_status = "skipped"

    reasons = {
        source: _source_reasons(
            source=source,
            diagnostics=diagnostics,
            data_quality=data_quality,
            missing_fields=missing_fields,
        )
        for source in ENRICHMENT_SOURCES
    }
    reasons = {source: value for source, value in reasons.items() if value}
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    as_of = (
        freshness.get("newsPublishedAt")
        or freshness.get("reportGeneratedAt")
        or freshness.get("marketTimestamp")
    )
    return {
        "enrichment_status": enrichment_status,
        "enrichment_sources": list(ENRICHMENT_SOURCES),
        "completed_sources": completed,
        "pending_sources": pending,
        "failed_sources": failed,
        "skipped_sources": skipped,
        "enrichment_reasons": reasons,
        "enrichment_updated_at": now,
        "enrichment_as_of": str(as_of) if as_of else None,
    }


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().lower() not in {"n/a", "na", "none", "null", "数据缺失"}
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _quote_required_available(context: Mapping[str, Any]) -> bool:
    realtime = context.get("realtime") if isinstance(context.get("realtime"), dict) else {}
    today = context.get("today") if isinstance(context.get("today"), dict) else {}
    yesterday = context.get("yesterday") if isinstance(context.get("yesterday"), dict) else {}
    price = realtime.get("price") or today.get("close")
    previous_close = realtime.get("pre_close") or yesterday.get("close")
    has_ohlc = all(_has_value(today.get(name) or realtime.get(name)) for name in ("open", "high", "low"))
    has_source = _has_value(realtime.get("source") or today.get("data_source"))
    has_as_of = _has_value(context.get("market_timestamp") or realtime.get("market_timestamp"))
    return all((_has_value(price), _has_value(previous_close), has_ohlc, has_source, has_as_of))


def _is_stale(context: Mapping[str, Any]) -> bool:
    session_type = str(context.get("session_type") or "").strip()
    if session_type == "last_completed_session":
        return True
    timestamp = context.get("market_timestamp")
    if not isinstance(timestamp, str) or not timestamp:
        return False
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - parsed.astimezone(timezone.utc) > timedelta(days=3)


def _has_non_live_required_source(context: Mapping[str, Any]) -> bool:
    realtime = context.get("realtime") if isinstance(context.get("realtime"), dict) else {}
    today = context.get("today") if isinstance(context.get("today"), dict) else {}
    source_text = " ".join(
        str(value or "").strip().lower()
        for value in (realtime.get("source"), today.get("data_source"))
        if value
    )
    return any(marker in source_text for marker in NON_LIVE_SOURCE_MARKERS)


def build_data_quality_report(
    *,
    context: Mapping[str, Any],
    data_quality: Optional[Mapping[str, Any]] = None,
    diagnostics: Optional[Mapping[str, Any]] = None,
    provider_health: Optional[Mapping[str, Any]] = None,
    optional_enrichment_pending: bool = False,
) -> DataQualityReport:
    data_quality = data_quality or {}
    diagnostics = diagnostics or {}
    provider_health = provider_health or {}

    missing_fields = [str(item) for item in data_quality.get("missing_fields", []) if str(item)]
    required_available = _quote_required_available(context)
    important_missing = [
        item
        for item in missing_fields
        if item.startswith("technicals.") or item.startswith("fundamentals.") or item.startswith("earnings.")
    ]

    optional_missing: List[str] = []
    if data_quality.get("sentiment_status") in {"weak", "missing", "failed"}:
        optional_missing.append("sentiment")
    news_status = str(diagnostics.get("news_status") or "").strip().lower()
    if news_status in {"not_configured", "failed", "skipped", "timeout", "configured_not_used"}:
        optional_missing.append("news")
    if "detailed_fundamentals" in missing_fields:
        optional_missing.append("detailed_fundamentals")
    if optional_enrichment_pending:
        optional_missing.append("optional_enrichment_pending")

    provider_timeouts = sanitize_reason_codes(provider_health.get("provider_timeouts", []))
    provider_cooldowns = sanitize_reason_codes(provider_health.get("provider_cooldowns", []))
    failure_reasons = sanitize_reason_codes(diagnostics.get("failure_reasons", []))

    stale_sources: List[str] = []
    if _is_stale(context):
        stale_sources.append("quote")
    non_live_required_source = _has_non_live_required_source(context)

    confidence_cap = 100
    score = 100
    reason_codes: List[str] = []
    if not required_available:
        confidence_cap = min(confidence_cap, 40)
        score = min(score, 40)
        reason_codes.append("required_data_missing")
    if important_missing:
        confidence_cap = min(confidence_cap, 70)
        score = min(score, 70)
        reason_codes.append("important_data_missing")
    if stale_sources:
        confidence_cap = min(confidence_cap, 75)
        score = min(score, 75)
        reason_codes.append("stale_required_source")
    if non_live_required_source:
        confidence_cap = min(confidence_cap, 75)
        score = min(score, 75)
        reason_codes.append("non_live_required_source")
    if optional_missing:
        score = max(0, score - min(8, 2 * len(set(optional_missing))))
        reason_codes.append("optional_enrichment_missing")
    if provider_timeouts:
        score = max(0, score - min(8, 2 * len(provider_timeouts)))
        reason_codes.append("provider_timeout")
    if provider_cooldowns:
        score = max(0, score - min(10, 3 * len(provider_cooldowns)))
        reason_codes.append("provider_hot_path_cooldown")

    if not required_available:
        tier = "insufficient"
    elif not important_missing and not stale_sources and not non_live_required_source:
        tier = "decision_grade"
    elif len(important_missing) <= 3:
        tier = "analysis_grade"
    else:
        tier = "partial"

    freshness = {
        "marketTimestamp": context.get("market_timestamp"),
        "marketSessionDate": context.get("market_session_date"),
        "newsPublishedAt": context.get("news_published_at"),
        "reportGeneratedAt": context.get("report_generated_at"),
        "sessionType": context.get("session_type"),
        "marketTimezone": context.get("market_timezone"),
    }
    clean_freshness = {key: value for key, value in freshness.items() if value is not None}
    enrichment_metadata = _build_enrichment_metadata(
        data_quality=data_quality,
        diagnostics=diagnostics,
        missing_fields=missing_fields,
        optional_enrichment_pending=optional_enrichment_pending,
        freshness=clean_freshness,
    )
    return DataQualityReport(
        data_quality_tier=tier,
        data_quality_score=max(0, min(100, int(score))),
        required_available=required_available,
        important_missing=important_missing[:24],
        optional_missing=list(dict.fromkeys(optional_missing))[:12],
        stale_sources=stale_sources,
        provider_timeouts=provider_timeouts,
        provider_cooldowns=provider_cooldowns,
        confidence_cap=confidence_cap,
        reason_codes=sanitize_reason_codes([*reason_codes, *failure_reasons]),
        freshness=clean_freshness,
        **enrichment_metadata,
    )
