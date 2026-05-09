# -*- coding: utf-8 -*-
"""Sanitized in-process provider usage diagnostics ledger.

This module is observability-only. It does not import provider clients, call
networks, read credentials, mutate provider order, or store raw payloads.
"""

from __future__ import annotations

import re
import threading
import uuid
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional


DEFAULT_PROVIDER_USAGE_LEDGER_MAX_EVENTS = 1000
MAX_METADATA_KEYS = 24
MAX_METADATA_LIST_ITEMS = 10
MAX_METADATA_STRING_LENGTH = 160
MAX_LABEL_LENGTH = 80
MAX_SYMBOL_LENGTH = 32
SENSITIVE_KEY_RE = re.compile(
    r"(token|secret|password|authorization|cookie|api_key|key|header|request_body|response_body|raw|payload)",
    re.IGNORECASE,
)
SAFE_LABEL_RE = re.compile(r"[^a-z0-9_.:-]+")
SAFE_SYMBOL_RE = re.compile(r"[^A-Z0-9_.:-]+")

PROVIDER_USAGE_ACTIONS = {
    "attempted",
    "cache_hit",
    "skipped_by_cache",
    "skipped_by_budget",
    "skipped_by_mode",
    "deadline_exceeded",
    "timeout",
    "success",
    "failure",
}
PROVIDER_USAGE_OUTCOMES = {"ok", "skipped", "failed", "partial"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_label(value: Any, *, default: Optional[str] = None, max_length: int = MAX_LABEL_LENGTH) -> Optional[str]:
    if value is None:
        return default
    text = str(value).strip().lower()
    if not text:
        return default
    text = SAFE_LABEL_RE.sub("_", text).strip("_.:-")
    if not text:
        return default
    return text[:max_length]


def _safe_symbol(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text:
        return None
    text = SAFE_SYMBOL_RE.sub("", text)
    return text[:MAX_SYMBOL_LENGTH] or None


def _sanitize_text(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"(?i)(token|secret|password|authorization|cookie|api[_-]?key|key)\s*[:=]\s*[^\s,;]+", r"\1=REDACTED", text)
    text = re.sub(r"(?i)\b(raw[_-]?payload|raw[_-]?response|request[_-]?body|response[_-]?body|headers?)\b[^\s,;]*", "REDACTED", text)
    if len(text) > MAX_METADATA_STRING_LENGTH:
        return text[: MAX_METADATA_STRING_LENGTH - 3] + "..."
    return text


def _safe_reason_code(value: Any) -> Optional[str]:
    label = _safe_label(value)
    if not label:
        return None
    parts = [part for part in label.split("_") if part not in {"token", "secret", "password", "authorization", "cookie", "api", "key", "redacted"}]
    return "_".join(parts)[:MAX_LABEL_LENGTH] or None


def _sanitize_metadata_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 2:
        return None
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, Mapping):
        return _sanitize_metadata(value, depth=depth + 1)
    if isinstance(value, (list, tuple, set)):
        items = []
        for item in list(value)[:MAX_METADATA_LIST_ITEMS]:
            sanitized = _sanitize_metadata_value(item, depth=depth + 1)
            if sanitized is not None:
                items.append(sanitized)
        return items
    return _sanitize_text(value)


def _sanitize_metadata(metadata: Optional[Mapping[str, Any]], *, depth: int = 0) -> dict[str, Any]:
    if not isinstance(metadata, Mapping):
        return {}
    sanitized: dict[str, Any] = {}
    for raw_key, value in list(metadata.items())[:MAX_METADATA_KEYS]:
        key = _safe_label(raw_key, max_length=64)
        if not key or SENSITIVE_KEY_RE.search(str(raw_key)):
            continue
        sanitized_value = _sanitize_metadata_value(value, depth=depth)
        if sanitized_value is not None:
            sanitized[key] = sanitized_value
    return sanitized


def _coerce_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return _utc_now()


@dataclass(frozen=True)
class ProviderUsageEvent:
    action: str
    outcome: str
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: datetime = field(default_factory=_utc_now)
    research_mode: Optional[str] = None
    symbol: Optional[str] = None
    market: Optional[str] = None
    analysis_context: Optional[str] = None
    category: Optional[str] = None
    provider: Optional[str] = None
    reason_code: Optional[str] = None
    elapsed_ms: Optional[float] = None
    budget_profile: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, Any]:
        timestamp = _coerce_timestamp(self.timestamp)
        action = _safe_label(self.action, default="failure")
        outcome = _safe_label(self.outcome, default="failed")
        if action not in PROVIDER_USAGE_ACTIONS:
            action = "failure"
        if outcome not in PROVIDER_USAGE_OUTCOMES:
            outcome = "failed"
        payload: dict[str, Any] = {
            "eventId": _safe_label(self.event_id, default=uuid.uuid4().hex, max_length=64),
            "timestamp": timestamp.astimezone(timezone.utc).isoformat(timespec="milliseconds"),
            "action": action,
            "outcome": outcome,
            "metadata": _sanitize_metadata(self.metadata),
        }
        optional_fields = {
            "researchMode": _safe_label(self.research_mode),
            "symbol": _safe_symbol(self.symbol),
            "market": _safe_label(self.market),
            "analysisContext": _safe_label(self.analysis_context),
            "category": _safe_label(self.category),
            "provider": _safe_label(self.provider),
            "reasonCode": _safe_reason_code(self.reason_code),
            "budgetProfile": _safe_label(self.budget_profile),
        }
        for key, value in optional_fields.items():
            if value is not None:
                payload[key] = value
        if self.elapsed_ms is not None:
            try:
                payload["elapsedMs"] = max(0.0, round(float(self.elapsed_ms), 3))
            except Exception:
                pass
        return payload


class ProviderUsageLedger:
    def __init__(self, *, max_events: int = DEFAULT_PROVIDER_USAGE_LEDGER_MAX_EVENTS) -> None:
        self.max_events = max(1, int(max_events or DEFAULT_PROVIDER_USAGE_LEDGER_MAX_EVENTS))
        self._events: deque[dict[str, Any]] = deque(maxlen=self.max_events)
        self._lock = threading.RLock()

    def record(self, event: ProviderUsageEvent | Mapping[str, Any]) -> dict[str, Any]:
        if isinstance(event, ProviderUsageEvent):
            payload = event.to_public_dict()
        elif isinstance(event, Mapping):
            payload = ProviderUsageEvent(**dict(event)).to_public_dict()
        else:
            payload = ProviderUsageEvent(action="failure", outcome="failed", reason_code="invalid_event").to_public_dict()
        with self._lock:
            self._events.append(payload)
        return dict(payload)

    def snapshot(
        self,
        *,
        limit: int = 100,
        since: Optional[datetime] = None,
        research_mode: Optional[str] = None,
        provider: Optional[str] = None,
        category: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        effective_limit = min(max(1, int(limit or 100)), self.max_events)
        since_dt = _coerce_timestamp(since) if since is not None else None
        mode_filter = _safe_label(research_mode)
        provider_filter = _safe_label(provider)
        category_filter = _safe_label(category)
        with self._lock:
            events = list(self._events)
        filtered: list[dict[str, Any]] = []
        for event in events:
            event_time = _parse_timestamp(event.get("timestamp"))
            if since_dt is not None and event_time is not None and event_time < since_dt:
                continue
            if mode_filter and event.get("researchMode") != mode_filter:
                continue
            if provider_filter and event.get("provider") != provider_filter:
                continue
            if category_filter and event.get("category") != category_filter:
                continue
            filtered.append(dict(event))
        return filtered[-effective_limit:]

    def clear_for_tests(self) -> None:
        with self._lock:
            self._events.clear()

    def summarize(self, *, window_seconds: int = 3600) -> dict[str, Any]:
        seconds = max(1, int(window_seconds or 3600))
        since = _utc_now() - timedelta(seconds=seconds)
        events = self.snapshot(limit=self.max_events, since=since)
        by_action = Counter(event.get("action") or "unknown" for event in events)
        by_provider = Counter(event.get("provider") or "unknown" for event in events)
        by_category = Counter(event.get("category") or "unknown" for event in events)
        by_mode = Counter(event.get("researchMode") or "unspecified" for event in events)
        return {
            "windowSeconds": seconds,
            "totalEvents": len(events),
            "byAction": dict(sorted(by_action.items())),
            "byProvider": dict(sorted(by_provider.items())),
            "byCategory": dict(sorted(by_category.items())),
            "byResearchMode": dict(sorted(by_mode.items())),
            "skippedByBudget": by_action.get("skipped_by_budget", 0),
            "deadlineExceeded": by_action.get("deadline_exceeded", 0),
            "timeout": by_action.get("timeout", 0),
            "cacheHit": by_action.get("cache_hit", 0),
        }


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


_DEFAULT_LEDGER: Optional[ProviderUsageLedger] = None
_DEFAULT_LEDGER_LOCK = threading.Lock()


def get_provider_usage_ledger() -> ProviderUsageLedger:
    global _DEFAULT_LEDGER
    with _DEFAULT_LEDGER_LOCK:
        if _DEFAULT_LEDGER is None:
            _DEFAULT_LEDGER = ProviderUsageLedger()
        return _DEFAULT_LEDGER


def record_provider_usage_event(**kwargs: Any) -> dict[str, Any]:
    return get_provider_usage_ledger().record(ProviderUsageEvent(**kwargs))


__all__ = [
    "DEFAULT_PROVIDER_USAGE_LEDGER_MAX_EVENTS",
    "PROVIDER_USAGE_ACTIONS",
    "PROVIDER_USAGE_OUTCOMES",
    "ProviderUsageEvent",
    "ProviderUsageLedger",
    "get_provider_usage_ledger",
    "record_provider_usage_event",
]
