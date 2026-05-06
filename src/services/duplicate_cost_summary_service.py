# -*- coding: utf-8 -*-
"""Read-only duplicate-cost summary aggregation for admin APIs."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

from api.v1.schemas.admin_cost import (
    DuplicateCostCacheEfficiency,
    DuplicateCostLimitation,
    DuplicateCostLlmSection,
    DuplicateCostMarketCacheSection,
    DuplicateCostMetadata,
    DuplicateCostOverview,
    DuplicateCostProviderSection,
    DuplicateCostRollup,
    DuplicateCostScannerAiSection,
    DuplicateCostSummaryResponse,
    DuplicateCostSummaryWindow,
)
from src.services.llm_instrumentation import snapshot_llm_event_counters
from src.storage import DatabaseManager


_WINDOWS = {
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}
_BUCKETS = {"hour", "day"}
_AREAS = {"all", "llm", "provider", "market-cache", "scanner-ai"}
_AREA_EVENTS = {
    "llm": ("llm_",),
    "provider": ("provider_",),
    "market-cache": ("market_cache_",),
    "scanner-ai": ("scanner_ai_",),
}
_SAFE_DIMENSION_KEYS = {
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


class DuplicateCostSummaryService:
    """Build a privacy-safe process-local duplicate-cost summary."""

    def build_summary(
        self,
        *,
        window: str = "24h",
        bucket: str = "hour",
        area: str = "all",
        limit: int = 50,
    ) -> DuplicateCostSummaryResponse:
        now = datetime.now(timezone.utc)
        window_key = self._validate_window(window)
        bucket_key = self._validate_bucket(bucket)
        area_key = self._validate_area(area)
        bounded_limit = max(1, min(int(limit), 200))
        from_dt = now - _WINDOWS[window_key]

        rows = self._counter_rows(area_key)
        counts = Counter({row["event"]: int(row["count"]) for row in rows})
        usage_summary, usage_unavailable = self._llm_usage_summary(from_dt, now)

        summary = DuplicateCostOverview(
            llm_calls=self._llm_attempt_count(counts),
            llm_usage_calls=int(usage_summary.get("total_calls", 0) or 0),
            llm_usage_tokens=int(usage_summary.get("total_tokens", 0) or 0),
            estimated_duplicate_candidates=sum(
                count
                for event, count in counts.items()
                if event.endswith("_duplicate_candidate_observed")
            ),
            provider_calls=int(counts.get("provider_call_started", 0)),
            provider_cache_hits=int(counts.get("provider_cache_hit", 0)),
            provider_cache_misses=int(counts.get("provider_cache_miss", 0)),
            provider_inflight_joins=int(counts.get("provider_inflight_join", 0)),
            provider_cache_hit_rate=self._rate(counts.get("provider_cache_hit", 0), counts.get("provider_cache_miss", 0)),
            market_cache_hits=int(counts.get("market_cache_hit", 0)),
            market_cache_misses=int(counts.get("market_cache_miss", 0)),
            market_cache_stale_served=int(counts.get("market_cache_stale_served", 0)),
            market_cache_cold_fallbacks=int(counts.get("market_cache_cold_start_fallback_served", 0)),
            market_cache_hit_rate=self._rate(counts.get("market_cache_hit", 0), counts.get("market_cache_miss", 0)),
            fallback_attempts=int(counts.get("llm_fallback_attempt", 0) + counts.get("provider_fallback_attempt", 0)),
            integrity_retries=int(counts.get("llm_integrity_retry", 0)),
            scanner_ai_attempts=int(counts.get("scanner_ai_interpretation_started", 0)),
            scanner_ai_completed=int(counts.get("scanner_ai_interpretation_completed", 0)),
            scanner_ai_skipped=int(counts.get("scanner_ai_interpretation_skipped", 0)),
        )

        limitations = self._limitations(usage_unavailable=usage_unavailable)
        metadata = DuplicateCostMetadata(
            data_sources=["process_local_counters", "llm_usage"],
            unsupported_sources=(["llm_usage"] if usage_unavailable else []),
            redaction=[
                "prompts_omitted",
                "messages_omitted",
                "provider_payloads_omitted",
                "urls_omitted",
                "credentials_omitted",
                "safe_hash_labels_only",
            ],
            requested_area=area_key,
            limit=bounded_limit,
            notes={
                "windowSupport": "counter snapshot is process-local and not timestamped",
                "aggregation": "bounded labels only",
            },
        )

        return DuplicateCostSummaryResponse(
            generated_at=now.isoformat(),
            window=DuplicateCostSummaryWindow(
                key=window_key,
                date_from=from_dt.isoformat(),
                date_to=now.isoformat(),
                bucket=bucket_key,
                historical=False,
            ),
            summary=summary,
            llm=self._llm_section(rows, usage_summary, bounded_limit),
            providers=self._provider_section(rows, bounded_limit),
            market_cache=self._market_cache_section(rows, bounded_limit),
            scanner_ai=self._scanner_ai_section(rows, bounded_limit),
            limitations=limitations,
            metadata=metadata,
        )

    def _counter_rows(self, area: str) -> List[Dict[str, Any]]:
        rows = []
        prefixes = _AREA_EVENTS.get(area)
        for row in snapshot_llm_event_counters():
            event = str(row.get("event") or "")
            if prefixes and not event.startswith(prefixes):
                continue
            rows.append(
                {
                    "event": event,
                    "count": int(row.get("count") or 0),
                    "labels": self._safe_dimensions(row.get("labels") or {}),
                }
            )
        return rows

    def _llm_usage_summary(self, from_dt: datetime, to_dt: datetime) -> tuple[Dict[str, Any], bool]:
        try:
            db = getattr(DatabaseManager, "_instance", None)
            if db is None:
                return {"total_calls": 0, "total_tokens": 0, "by_call_type": [], "by_model": []}, True
            return db.get_llm_usage_summary(from_dt.replace(tzinfo=None), to_dt.replace(tzinfo=None)), False
        except Exception:
            return {"total_calls": 0, "total_tokens": 0, "by_call_type": [], "by_model": []}, True

    def _llm_section(self, rows: Sequence[Dict[str, Any]], usage: Dict[str, Any], limit: int) -> DuplicateCostLlmSection:
        usage_by_call_type = [
            DuplicateCostRollup(
                group=str(row.get("call_type") or "unknown"),
                count=int(row.get("calls") or 0),
                event_counts={"llm_usage": int(row.get("calls") or 0)},
                dimensions={
                    "call_type": str(row.get("call_type") or "unknown"),
                    "token_bucket": self._usage_token_bucket(row.get("total_tokens")),
                },
            )
            for row in (usage.get("by_call_type") or [])[:limit]
        ]
        usage_by_model = [
            DuplicateCostRollup(
                group=self._safe_text(row.get("model")),
                count=int(row.get("calls") or 0),
                event_counts={"llm_usage": int(row.get("calls") or 0)},
                dimensions={"model_family": self._safe_text(row.get("model")), "token_bucket": self._usage_token_bucket(row.get("total_tokens"))},
            )
            for row in (usage.get("by_model") or [])[:limit]
        ]
        return DuplicateCostLlmSection(
            by_call_type=self._rollup(rows, ("llm_call_started", "llm_call_completed", "llm_call_failed"), ("call_type",), limit),
            duplicate_candidates=self._rollup(rows, ("llm_duplicate_candidate_observed",), ("call_type", "cache_key_hash"), limit),
            fallbacks=self._rollup(rows, ("llm_fallback_attempt",), ("call_type", "fallback_depth", "retry_reason"), limit),
            integrity_retries=self._rollup(rows, ("llm_integrity_retry",), ("call_type", "report_type", "language", "retry_reason"), limit),
            usage_by_call_type=usage_by_call_type,
            usage_by_model=usage_by_model,
        )

    def _provider_section(self, rows: Sequence[Dict[str, Any]], limit: int) -> DuplicateCostProviderSection:
        return DuplicateCostProviderSection(
            by_category=self._rollup(
                rows,
                (
                    "provider_call_started",
                    "provider_call_completed",
                    "provider_call_failed",
                    "provider_cache_hit",
                    "provider_cache_miss",
                    "provider_inflight_join",
                ),
                ("provider_category", "market"),
                limit,
            ),
            fallback_depth=self._rollup(rows, ("provider_fallback_attempt",), ("provider_category", "market", "fallback_depth", "retry_reason_bucket"), limit),
            cache_efficiency=self._provider_cache_efficiency(rows, limit),
            duplicate_candidates=self._rollup(rows, ("provider_duplicate_candidate_observed",), ("provider_category", "market", "cache_key_hash"), limit),
        )

    def _market_cache_section(self, rows: Sequence[Dict[str, Any]], limit: int) -> DuplicateCostMarketCacheSection:
        return DuplicateCostMarketCacheSection(
            by_panel_key=self._rollup(
                rows,
                (
                    "market_cache_hit",
                    "market_cache_miss",
                    "market_cache_stale_served",
                    "market_cache_cold_start_fallback_served",
                    "market_cache_refresh_started",
                    "market_cache_refresh_completed",
                    "market_cache_refresh_failed",
                ),
                ("panel_key", "endpoint_family"),
                limit,
            ),
            stale_served=self._rollup(rows, ("market_cache_stale_served",), ("panel_key", "freshness_bucket"), limit),
            cold_fallbacks=self._rollup(rows, ("market_cache_cold_start_fallback_served",), ("panel_key", "freshness_bucket"), limit),
            refreshes=self._rollup(
                rows,
                ("market_cache_refresh_started", "market_cache_refresh_completed", "market_cache_refresh_failed"),
                ("panel_key", "refresh_mode", "error_bucket"),
                limit,
            ),
        )

    def _scanner_ai_section(self, rows: Sequence[Dict[str, Any]], limit: int) -> DuplicateCostScannerAiSection:
        return DuplicateCostScannerAiSection(
            interpretations=self._rollup(
                rows,
                (
                    "scanner_ai_interpretation_started",
                    "scanner_ai_interpretation_completed",
                ),
                ("market", "profile", "rank_bucket", "top_n"),
                limit,
            ),
            duplicate_candidates=self._rollup(rows, ("scanner_ai_duplicate_candidate_observed",), ("market", "profile", "candidate_hash"), limit),
            skips=self._rollup(rows, ("scanner_ai_interpretation_skipped",), ("market", "profile", "skip_reason"), limit),
        )

    def _rollup(
        self,
        rows: Sequence[Dict[str, Any]],
        events: Iterable[str],
        dimension_keys: Sequence[str],
        limit: int,
    ) -> List[DuplicateCostRollup]:
        wanted = set(events)
        buckets: Dict[tuple[str, ...], Dict[str, Any]] = {}
        for row in rows:
            event = row["event"]
            if event not in wanted:
                continue
            labels = row["labels"]
            dimensions = {key: labels[key] for key in dimension_keys if labels.get(key)}
            group = "|".join(dimensions.values()) or "unknown"
            key = tuple([group, *[f"{k}={v}" for k, v in sorted(dimensions.items())]])
            bucket = buckets.setdefault(key, {"group": group, "count": 0, "event_counts": Counter(), "dimensions": dimensions})
            bucket["count"] += row["count"]
            bucket["event_counts"][event] += row["count"]
        return [
            DuplicateCostRollup(
                group=value["group"],
                count=int(value["count"]),
                event_counts=dict(sorted(value["event_counts"].items())),
                dimensions=value["dimensions"],
            )
            for value in sorted(buckets.values(), key=lambda item: (-int(item["count"]), item["group"]))[:limit]
        ]

    def _provider_cache_efficiency(self, rows: Sequence[Dict[str, Any]], limit: int) -> List[DuplicateCostCacheEfficiency]:
        grouped: Dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
        dims_by_key: Dict[tuple[str, str, str], Dict[str, str]] = {}
        for row in rows:
            event = row["event"]
            if event not in {"provider_cache_hit", "provider_cache_miss", "provider_inflight_join"}:
                continue
            labels = row["labels"]
            dims = {
                key: labels[key]
                for key in ("provider", "provider_category", "market")
                if labels.get(key)
            }
            group = (
                dims.get("provider", "unknown"),
                dims.get("provider_category", "unknown"),
                dims.get("market", "unknown"),
            )
            dims_by_key[group] = dims
            grouped[group][event] += row["count"]
        items = []
        for group, counts in grouped.items():
            hits = int(counts.get("provider_cache_hit", 0))
            misses = int(counts.get("provider_cache_miss", 0))
            joins = int(counts.get("provider_inflight_join", 0))
            items.append(
                DuplicateCostCacheEfficiency(
                    group="|".join(group),
                    hits=hits,
                    misses=misses,
                    inflight_joins=joins,
                    hit_rate=self._rate(hits, misses),
                    dimensions=dims_by_key[group],
                )
            )
        return sorted(items, key=lambda item: (-(item.hits + item.misses + item.inflight_joins), item.group))[:limit]

    def _limitations(self, *, usage_unavailable: bool) -> List[DuplicateCostLimitation]:
        items = [
            DuplicateCostLimitation(
                code="process_local_counters_reset_on_restart",
                message="Counters are in-process snapshots and reset on process restart.",
                severity="warning",
            ),
            DuplicateCostLimitation(
                code="counter_snapshot_not_timestamped",
                message="Window parameters are accepted for contract compatibility; process-local counters do not support historical bucketing.",
                severity="warning",
            ),
            DuplicateCostLimitation(
                code="observational_not_billing",
                message="Counts indicate observed attempts and duplicate candidates, not invoice-grade billing.",
                severity="info",
            ),
        ]
        if usage_unavailable:
            items.append(
                DuplicateCostLimitation(
                    code="llm_usage_unavailable",
                    message="Persisted LLM usage summary was unavailable; process-local counters are still returned.",
                    severity="warning",
                )
            )
        return items

    @staticmethod
    def _validate_window(value: str) -> str:
        key = str(value or "24h").strip().lower()
        if key not in _WINDOWS:
            raise ValueError(f"Invalid window: {value}")
        return key

    @staticmethod
    def _validate_bucket(value: str) -> str:
        key = str(value or "hour").strip().lower()
        if key not in _BUCKETS:
            raise ValueError(f"Invalid bucket: {value}")
        return key

    @staticmethod
    def _validate_area(value: str) -> str:
        key = str(value or "all").strip().lower()
        if key not in _AREAS:
            raise ValueError(f"Invalid area: {value}")
        return key

    @staticmethod
    def _safe_dimensions(labels: Dict[str, Any]) -> Dict[str, str]:
        safe: Dict[str, str] = {}
        for key, value in labels.items():
            if key in _SAFE_DIMENSION_KEYS and value is not None:
                safe[key] = str(value)[:64]
        return safe

    @staticmethod
    def _llm_attempt_count(counts: Counter[str]) -> int:
        started = int(counts.get("llm_call_started", 0))
        if started:
            return started
        return int(counts.get("llm_call_completed", 0) + counts.get("llm_call_failed", 0))

    @staticmethod
    def _rate(hits: Any, misses: Any) -> Optional[float]:
        hit_count = int(hits or 0)
        miss_count = int(misses or 0)
        total = hit_count + miss_count
        if total <= 0:
            return None
        return round(hit_count / total, 4)

    @staticmethod
    def _safe_text(value: Any) -> str:
        text = str(value or "unknown").strip().lower()
        return text[:64] or "unknown"

    @staticmethod
    def _usage_token_bucket(value: Any) -> str:
        try:
            tokens = int(value or 0)
        except Exception:
            return "unknown"
        if tokens <= 0:
            return "0"
        if tokens < 1_000:
            return "1-999"
        if tokens < 10_000:
            return "1k-10k"
        if tokens < 50_000:
            return "10k-50k"
        return "gte_50k"
