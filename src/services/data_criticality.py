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
)


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
    if optional_enrichment_pending:
        optional_missing.append("optional_enrichment_pending")

    provider_timeouts = sanitize_reason_codes(provider_health.get("provider_timeouts", []))
    provider_cooldowns = sanitize_reason_codes(provider_health.get("provider_cooldowns", []))
    failure_reasons = sanitize_reason_codes(diagnostics.get("failure_reasons", []))

    stale_sources: List[str] = []
    if _is_stale(context):
        stale_sources.append("quote")

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
    elif not important_missing and not stale_sources:
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
        freshness={key: value for key, value in freshness.items() if value is not None},
    )

