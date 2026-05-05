# -*- coding: utf-8 -*-
"""Best-effort, privacy-safe LLM instrumentation counters."""

from __future__ import annotations

import logging
import re
import hashlib
from collections import Counter
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_ALLOWED_EVENTS = frozenset(
    {
        "llm_call_started",
        "llm_call_completed",
        "llm_call_failed",
        "llm_fallback_attempt",
        "llm_integrity_retry",
        "llm_usage_persisted",
        "market_cache_hit",
        "market_cache_stale_served",
        "market_cache_miss",
        "market_cache_refresh_started",
        "market_cache_refresh_completed",
        "market_cache_refresh_failed",
        "market_cache_cold_start_fallback_served",
        "provider_call_started",
        "provider_call_completed",
        "provider_call_failed",
        "provider_fallback_attempt",
        "provider_insufficient_payload",
        "provider_timeout",
        "provider_quota_risk_observed",
        "provider_cache_hit",
        "provider_cache_miss",
        "provider_inflight_join",
        "provider_duplicate_candidate_observed",
        "scanner_ai_duplicate_candidate_observed",
        "scanner_ai_interpretation_started",
        "scanner_ai_interpretation_completed",
        "scanner_ai_interpretation_skipped",
    }
)

_ALLOWED_LABELS = frozenset(
    {
        "call_type",
        "model_family",
        "provider",
        "route",
        "caller_family",
        "attempt_index",
        "fallback_depth",
        "retry_reason",
        "outcome",
        "duration_bucket",
        "token_bucket",
        "report_type",
        "language",
        "market",
        "panel_key",
        "endpoint_family",
        "provider_category",
        "refresh_mode",
        "freshness_bucket",
        "error_bucket",
        "retry_reason_bucket",
        "cache_key_hash",
        "profile",
        "rank_bucket",
        "top_n",
        "prompt_version",
        "candidate_hash",
        "skip_reason",
    }
)

_COUNTERS: Counter[Tuple[str, Tuple[Tuple[str, str], ...]]] = Counter()
_LOCK = Lock()
_Sink = Callable[[str, Dict[str, str]], None]
_SINK: Optional[_Sink] = None


def _default_sink(event_name: str, labels: Dict[str, str]) -> None:
    logger.debug("[llm-instrumentation] %s %s", event_name, labels)


def set_llm_event_sink(sink: Optional[_Sink]) -> None:
    """Set an optional process-local sink for tests or future adapters."""
    global _SINK
    with _LOCK:
        _SINK = sink


def reset_llm_event_counters() -> None:
    """Clear process-local counters. Intended for unit tests."""
    with _LOCK:
        _COUNTERS.clear()


def snapshot_llm_event_counters() -> List[Dict[str, Any]]:
    """Return a copy of process-local counter entries for tests/internal diagnostics."""
    with _LOCK:
        items = list(_COUNTERS.items())
    snapshot: List[Dict[str, Any]] = []
    for (event_name, labels_tuple), count in sorted(items):
        snapshot.append(
            {
                "event": event_name,
                "labels": dict(labels_tuple),
                "count": count,
            }
        )
    return snapshot


def bucket_duration_ms(duration_ms: Any) -> str:
    try:
        value = float(duration_ms)
    except (TypeError, ValueError):
        return "unknown"
    if value < 0:
        return "unknown"
    if value < 100:
        return "lt_100ms"
    if value < 500:
        return "100ms-500ms"
    if value < 1_000:
        return "500ms-1s"
    if value < 5_000:
        return "1s-5s"
    if value < 15_000:
        return "5s-15s"
    if value < 60_000:
        return "15s-60s"
    return "gte_60s"


def bucket_token_count(tokens: Any) -> str:
    try:
        value = int(tokens)
    except (TypeError, ValueError):
        return "unknown"
    if value <= 0:
        return "0"
    if value < 1_000:
        return "1-999"
    if value < 10_000:
        return "1k-10k"
    if value < 50_000:
        return "10k-50k"
    return "gte_50k"


def bucket_retry_reason(reason: Any) -> str:
    text = ""
    if isinstance(reason, BaseException):
        text = f"{type(reason).__name__} {reason}"
    else:
        text = str(reason or "")
    lowered = text.lower()
    if "timeout" in lowered or "timed out" in lowered:
        return "timeout"
    if "rate" in lowered and "limit" in lowered:
        return "rate_limited"
    if "quota" in lowered:
        return "quota"
    if "auth" in lowered or "api key" in lowered or "permission" in lowered:
        return "auth"
    if "empty" in lowered:
        return "empty_response"
    if "insufficient" in lowered:
        return "insufficient_payload"
    if "json" in lowered or "parse" in lowered:
        return "parse_error"
    if "invalid" in lowered:
        return "invalid_response"
    if "network" in lowered or "connection" in lowered:
        return "network"
    if lowered.strip():
        return "failed"
    return "unknown"


def bucket_model_family(model: Any) -> str:
    raw = str(model or "").strip().lower()
    if not raw:
        return "unknown"
    provider = ""
    model_name = raw
    if "/" in raw:
        provider, model_name = raw.split("/", 1)
        provider = _bounded_label(provider)
    family = _model_family_name(model_name)
    return f"{provider}/{family}" if provider else family


def provider_from_model(model: Any) -> str:
    raw = str(model or "").strip().lower()
    if "/" in raw:
        return _bounded_label(raw.split("/", 1)[0])
    if raw:
        return _bounded_label(raw.split("-", 1)[0])
    return "unknown"


def hash_label_value(value: Any) -> str:
    """Return a bounded non-reversible label hash for cache keys or request identity."""
    text = str(value or "")
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def emit_llm_event(event_name: str, **labels: Any) -> None:
    """Emit a bounded LLM event; failures are always swallowed."""
    _emit_event(event_name, labels)


def emit_market_cache_event(event_name: str, **labels: Any) -> None:
    """Emit a bounded MarketCache event; failures are always swallowed."""
    _emit_event(event_name, labels)


def emit_provider_event(event_name: str, **labels: Any) -> None:
    """Emit a bounded provider event; failures are always swallowed."""
    _emit_event(event_name, labels)


def emit_scanner_ai_event(event_name: str, **labels: Any) -> None:
    """Emit a bounded Scanner AI event; failures are always swallowed."""
    _emit_event(event_name, labels)


def _emit_event(event_name: str, labels: Dict[str, Any]) -> None:
    try:
        normalized_event = _bounded_label(event_name)
        if normalized_event not in _ALLOWED_EVENTS:
            return
        safe_labels = _sanitize_labels(labels)
        key = (normalized_event, tuple(sorted(safe_labels.items())))
        with _LOCK:
            _COUNTERS[key] += 1
            sink = _SINK
        try:
            (sink or _default_sink)(normalized_event, dict(safe_labels))
        except Exception as exc:
            logger.debug("[llm-instrumentation] sink failed: %s", type(exc).__name__)
    except Exception as exc:
        logger.debug("[llm-instrumentation] emit failed: %s", type(exc).__name__)


def _sanitize_labels(labels: Dict[str, Any]) -> Dict[str, str]:
    safe: Dict[str, str] = {}
    for key, value in labels.items():
        if key not in _ALLOWED_LABELS or value is None:
            continue
        if key == "model_family":
            safe[key] = bucket_model_family(value)
        elif key == "provider":
            safe[key] = _bounded_label(value)
        elif key in {"attempt_index", "fallback_depth", "top_n"}:
            safe[key] = _bounded_int_label(value)
        elif key in {"retry_reason", "retry_reason_bucket"}:
            safe[key] = bucket_retry_reason(value)
        elif key == "error_bucket":
            safe[key] = bucket_retry_reason(value)
        elif key == "duration_bucket":
            safe[key] = bucket_duration_ms(value)
        elif key == "token_bucket":
            safe[key] = bucket_token_count(value)
        else:
            safe[key] = _bounded_label(value)
    return safe


def _bounded_int_label(value: Any) -> str:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return "unknown"
    return str(max(0, min(parsed, 99)))


def _bounded_label(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9._:/-]+", "_", text)
    text = text.strip("._:/-")
    return (text[:64] or "unknown")


def _model_family_name(model_name: str) -> str:
    parts = [part for part in re.split(r"[-_]+", model_name) if part]
    if not parts:
        return "unknown"
    if parts[0] == "gemini" and len(parts) >= 2:
        return _bounded_label("-".join(parts[:2]))
    if parts[0] == "gpt" and len(parts) >= 2:
        return _bounded_label("-".join(parts[:2]))
    if parts[0] == "claude" and len(parts) >= 3:
        return _bounded_label(".".join(parts[:3]))
    if parts[0] == "deepseek" and len(parts) >= 2:
        return _bounded_label("-".join(parts[:2]))
    return _bounded_label("-".join(parts[:2]))
