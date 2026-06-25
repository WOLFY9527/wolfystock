# -*- coding: utf-8 -*-
"""Read-only aggregation for market provider operations."""

from __future__ import annotations

import copy
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
import threading
import time
from typing import Any, ClassVar, Dict, Iterable, List, Optional, Tuple

from src.config import get_config
from src.services.execution_log_service import ExecutionLogService
from src.services.llm_instrumentation import snapshot_llm_event_counters
from src.services.market_cache import MARKET_CACHE_TTLS, SAFE_MARKET_CACHE_PANEL_KEYS, MarketCache, market_cache
from src.services.market_data_source_registry import resolve_source_label
from src.services.macro_provider_readiness_service import build_macro_provider_readiness_contract
from src.services.system_config_provider_projection import project_tickflow_entitlement_health
from src.services.trust_evidence_projection import build_trust_evidence_snapshot_v1
from src.storage import DatabaseManager
from src.utils.security import sanitize_message

CN_TZ = timezone(timedelta(hours=8))
SAFE_WINDOW_VALUES = {"15m", "1h", "24h", "7d"}
MARKET_LOG_CATEGORIES = ("data_source", "market", "cache", "api")
MARKET_EVENT_NAMES = {
    "MarketDataFallbackUsed",
    "MarketDataStaleServed",
    "MarketProviderRefreshFailed",
    "MarketProviderFallbackUsed",
    "MarketSnapshotServedStale",
    "MarketCacheColdStartSlow",
    "ExternalSourceTimeout",
    "ExternalDataSourceTimeout",
}
SENSITIVE_FIELD_PATTERN = r"api[-_]?key|token|secret|password|authorization|webhook|raw[-_]?payload|raw[-_]?response|request[-_]?body|response[-_]?body|headers?"
SECRET_ASSIGNMENT_RE = re.compile(rf"\b({SENSITIVE_FIELD_PATTERN})\b\s*[:=]\s*[^\s,;]+", re.IGNORECASE)
SECRET_WORD_RE = re.compile(rf"({SENSITIVE_FIELD_PATTERN})", re.IGNORECASE)
SUMMARY_CACHE_TTL_SECONDS = 10.0
SUMMARY_CACHE_VERSION = "GET:/api/v1/admin/market-providers/operations:v1"
PROVIDER_OPS_REGISTRY_LABEL_SOURCES = frozenset(
    {
        "eastmoney",
        "sina",
        "tickflow",
        "yahoo",
        "yfinance",
        "yfinance_proxy",
        "binance",
        "binance_ws",
        "alternative",
        "alternative_me",
        "cnn",
        "cached",
        "fallback",
        "mock",
        "polygon_us_grouped_daily",
        "unavailable",
    }
)
PROVIDER_OPS_LEGACY_LABEL_OVERRIDES = {
    "fred": "FRED",
    "treasury": "US Treasury",
    "computed": "系统计算",
    "mixed": "多来源",
    "public": "公开数据",
}
MARKET_CACHE_EVENT_COUNTER_FIELDS = {
    "market_cache_hit": "hits",
    "market_cache_miss": "misses",
    "market_cache_stale_served": "staleServed",
    "market_cache_cold_start_fallback_served": "coldFallbacks",
    "market_cache_refresh_started": "refreshStarted",
    "market_cache_refresh_completed": "refreshCompleted",
    "market_cache_refresh_failed": "refreshFailed",
}
MARKET_CACHE_EVENT_SUMMARY_FIELDS = (
    "hits",
    "misses",
    "staleServed",
    "coldFallbacks",
    "refreshStarted",
    "refreshCompleted",
    "refreshFailed",
)


@dataclass(frozen=True)
class MarketProviderPanel:
    cache_key: str
    domain: str
    endpoint: str
    card: str
    ttl_key: str


PANELS: Tuple[MarketProviderPanel, ...] = (
    MarketProviderPanel("indices", "equity_index", "/api/v1/market-overview/indices", "IndexTrendsCard", "equity_index"),
    MarketProviderPanel("volatility", "futures", "/api/v1/market-overview/volatility", "VolatilityCard", "futures"),
    MarketProviderPanel("sentiment", "sentiment", "/api/v1/market/sentiment", "MarketSentimentCard", "sentiment"),
    MarketProviderPanel("funds_flow", "flows", "/api/v1/market-overview/funds-flow", "FundsFlowCard", "flows"),
    MarketProviderPanel("macro", "macro_rate", "/api/v1/market-overview/macro", "MacroIndicatorsCard", "rates"),
    MarketProviderPanel("crypto", "crypto", "/api/v1/market/crypto", "CryptoCard", "crypto"),
    MarketProviderPanel("cn_indices", "equity_index", "/api/v1/market/cn-indices", "ChinaIndicesCard", "cn_indices"),
    MarketProviderPanel("cn_breadth", "breadth", "/api/v1/market/cn-breadth", "ChinaBreadthCard", "breadth"),
    MarketProviderPanel("cn_flows", "flows", "/api/v1/market/cn-flows", "ChinaFlowsCard", "flows"),
    MarketProviderPanel("sector_rotation", "sentiment", "/api/v1/market/sector-rotation", "SectorRotationCard", "sector_rotation"),
    MarketProviderPanel("us_breadth", "breadth", "/api/v1/market/us-breadth", "UsBreadthCard", "breadth"),
    MarketProviderPanel("rates", "macro_rate", "/api/v1/market/rates", "RatesCard", "rates"),
    MarketProviderPanel("fx_commodities", "fx_commodity", "/api/v1/market/fx-commodities", "FxCommoditiesCard", "fx_commodity"),
    MarketProviderPanel("temperature", "sentiment", "/api/v1/market/temperature", "MarketTemperatureCard", "temperature"),
    MarketProviderPanel("market_briefing", "sentiment", "/api/v1/market/market-briefing", "MarketBriefingCard", "market_briefing"),
    MarketProviderPanel("futures", "futures", "/api/v1/market/futures", "FuturesCard", "futures"),
    MarketProviderPanel("cn_short_sentiment", "sentiment", "/api/v1/market/cn-short-sentiment", "ChinaShortSentimentCard", "sentiment"),
)


class MarketProviderOperationsService:
    """Build a provider operations payload without provider fetches or writes."""

    _summary_cache: ClassVar[Dict[str, Dict[str, Any]]] = {}
    _summary_cache_lock: ClassVar[threading.RLock] = threading.RLock()

    def __init__(
        self,
        *,
        cache: MarketCache = market_cache,
        db: Optional[DatabaseManager] = None,
        log_service: Optional[ExecutionLogService] = None,
    ) -> None:
        self.cache = cache
        self.db = db or DatabaseManager.get_instance()
        self.log_service = log_service or ExecutionLogService()

    def get_operations(self, *, window: str = "24h") -> Dict[str, Any]:
        normalized_window = self._normalize_window(window)
        summary_cache_key = self._summary_cache_key(normalized_window)
        cached_payload = self._read_summary_cache(summary_cache_key)
        if cached_payload is not None:
            return cached_payload

        generated_at = self._now()
        cache_states, items, cache_limitations, provider_diagnostics = self._read_cache_and_snapshots(generated_at)
        events = self._read_market_events(normalized_window)
        event_rollups = self._rollup_events(events, normalized_window)
        summary = self._summary(items, event_rollups)
        limitations = list(cache_limitations)
        if not events:
            limitations.append("admin_logs_no_degraded_market_events_in_window")
        payload = {
            "generatedAt": generated_at.isoformat(timespec="seconds"),
            "window": {
                "key": normalized_window,
                "since": normalized_window,
            },
            "summary": summary,
            "items": items,
            "eventRollups": event_rollups,
            "marketCacheEventSummary": self._market_cache_event_summary(),
            "cacheStates": cache_states,
            "limitations": sorted(set(limitations)),
            "adminLogDrillThrough": self._drillthrough(since=normalized_window, query="market provider"),
            "metadata": {
                "source": "market_cache_and_admin_logs",
                "readOnly": True,
                "externalProviderCalls": False,
                "cacheMutation": False,
                "providerDiagnostics": provider_diagnostics,
                "summaryCache": self._summary_cache_metadata(
                    key=summary_cache_key,
                    stored_at_monotonic=time.monotonic(),
                    generated_at=generated_at,
                    hit=False,
                ),
            },
        }
        return self._write_summary_cache(summary_cache_key, payload)

    @classmethod
    def clear_summary_cache(cls) -> None:
        with cls._summary_cache_lock:
            cls._summary_cache.clear()

    @staticmethod
    def _summary_cache_key(window: str) -> str:
        return f"{SUMMARY_CACHE_VERSION}:{window}"

    @classmethod
    def _read_summary_cache(cls, key: str) -> Optional[Dict[str, Any]]:
        now_monotonic = time.monotonic()
        with cls._summary_cache_lock:
            entry = cls._summary_cache.get(key)
            if not entry:
                return None
            stored_at_monotonic = float(entry.get("stored_at_monotonic") or 0)
            if now_monotonic - stored_at_monotonic >= SUMMARY_CACHE_TTL_SECONDS:
                cls._summary_cache.pop(key, None)
                return None
            payload = copy.deepcopy(entry.get("payload") or {})
        generated_at = MarketProviderOperationsService._parse_time(payload.get("generatedAt")) or MarketProviderOperationsService._now()
        payload.setdefault("metadata", {})["summaryCache"] = cls._summary_cache_metadata(
            key=key,
            stored_at_monotonic=stored_at_monotonic,
            generated_at=generated_at,
            hit=True,
            now_monotonic=now_monotonic,
        )
        return payload

    @classmethod
    def _write_summary_cache(cls, key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        stored_at_monotonic = time.monotonic()
        generated_at = cls._parse_time(payload.get("generatedAt")) or cls._now()
        payload.setdefault("metadata", {})["summaryCache"] = cls._summary_cache_metadata(
            key=key,
            stored_at_monotonic=stored_at_monotonic,
            generated_at=generated_at,
            hit=False,
            now_monotonic=stored_at_monotonic,
        )
        with cls._summary_cache_lock:
            cls._summary_cache[key] = {
                "stored_at_monotonic": stored_at_monotonic,
                "payload": copy.deepcopy(payload),
            }
        return copy.deepcopy(payload)

    @staticmethod
    def _summary_cache_metadata(
        *,
        key: str,
        stored_at_monotonic: float,
        generated_at: datetime,
        hit: bool,
        now_monotonic: Optional[float] = None,
    ) -> Dict[str, Any]:
        now_monotonic = time.monotonic() if now_monotonic is None else now_monotonic
        return {
            "enabled": True,
            "ttlSeconds": int(SUMMARY_CACHE_TTL_SECONDS),
            "key": key,
            "hit": hit,
            "asOf": generated_at.isoformat(timespec="seconds"),
            "cacheAgeMs": max(0, int((now_monotonic - stored_at_monotonic) * 1000)),
        }

    def _read_cache_and_snapshots(self, now: datetime) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str], Dict[str, Any]]:
        cache_states: List[Dict[str, Any]] = []
        items: List[Dict[str, Any]] = []
        limitations: List[str] = []
        tickflow_api_key = getattr(get_config(), "tickflow_api_key", None)
        provider_diagnostics: Dict[str, Any] = {
            "macroFredReadiness": build_macro_provider_readiness_contract(
                include_admin_diagnostics=True
            )
        }
        for panel in PANELS:
            entry = self.cache.get(panel.cache_key)
            snapshot = self.db.get_market_overview_snapshot(f"market_overview:{panel.cache_key}")
            snapshot_payload = snapshot.get("payload") if isinstance(snapshot, dict) and isinstance(snapshot.get("payload"), dict) else {}
            payload = copy.deepcopy(entry.data) if entry is not None and isinstance(entry.data, dict) else copy.deepcopy(snapshot_payload)
            provider_health = payload.get("providerHealth") if isinstance(payload.get("providerHealth"), dict) else {}
            if entry is None and not snapshot_payload:
                limitations.append(f"cache_metadata_unavailable:{panel.cache_key}")
            cache_states.append(self._cache_state(panel, entry, snapshot, now))
            items.append(self._item(panel, entry, snapshot, payload, now))
            if panel.cache_key == "cn_breadth":
                provider_diagnostics["tickflowCnBreadth"] = project_tickflow_entitlement_health(
                    api_key=tickflow_api_key,
                    source=self._safe_public_text(
                        payload.get("source")
                        or payload.get("provider")
                        or provider_health.get("provider")
                        or (snapshot.get("source") if isinstance(snapshot, dict) else None)
                    ),
                    source_type=self._safe_public_text(
                        payload.get("sourceType")
                        or provider_health.get("sourceType")
                        or (snapshot.get("source_type") if isinstance(snapshot, dict) else None)
                    ),
                    fallback_reason=self._safe_public_text(
                        payload.get("fallbackReason")
                        or payload.get("fallback_reason")
                        or payload.get("reasonCode")
                        or provider_health.get("reasonCode")
                    ),
                    warning=self._safe_error(payload.get("warning")),
                    error_summary=self._safe_error(
                        provider_health.get("errorSummary")
                        or payload.get("lastError")
                        or payload.get("refreshError")
                        or (snapshot.get("last_error") if isinstance(snapshot, dict) else None)
                    ),
                )
        return cache_states, items, limitations, provider_diagnostics

    def _cache_state(
        self,
        panel: MarketProviderPanel,
        entry: Any,
        snapshot: Optional[Dict[str, Any]],
        now: datetime,
    ) -> Dict[str, Any]:
        snapshot_updated = self._parse_time(snapshot.get("updated_at")) if isinstance(snapshot, dict) else None
        is_fresh = entry.expires_at > now if entry is not None else None
        return {
            "cacheKey": panel.cache_key,
            "ttlSeconds": int(entry.ttl_seconds) if entry is not None else MARKET_CACHE_TTLS.get(panel.ttl_key),
            "fetchedAt": self._iso(getattr(entry, "fetched_at", None)),
            "expiresAt": self._iso(getattr(entry, "expires_at", None)),
            "isFresh": is_fresh,
            "isRefreshing": bool(getattr(entry, "is_refreshing", False)),
            "lastError": self._safe_error(getattr(entry, "last_error", None)),
            "persistentSnapshotAvailable": bool(snapshot),
            "persistentSnapshotAgeMinutes": self._age_minutes(snapshot_updated, now),
            "status": "fresh" if is_fresh is True else ("stale" if entry is not None else "unavailable"),
        }

    def _item(
        self,
        panel: MarketProviderPanel,
        entry: Any,
        snapshot: Optional[Dict[str, Any]],
        payload: Dict[str, Any],
        now: datetime,
    ) -> Dict[str, Any]:
        provider_health = payload.get("providerHealth") if isinstance(payload.get("providerHealth"), dict) else {}
        source = self._safe_public_text(
            provider_health.get("provider")
            or payload.get("provider")
            or payload.get("source")
            or (snapshot.get("source") if isinstance(snapshot, dict) else None)
            or "unknown"
        ) or "unknown"
        freshness = self._safe_public_text(payload.get("freshness") or (snapshot.get("freshness") if isinstance(snapshot, dict) else None))
        is_fallback = bool(payload.get("isFallback") or payload.get("fallbackUsed") or payload.get("fallback_used") or (snapshot.get("is_fallback") if isinstance(snapshot, dict) else False))
        is_stale = bool(payload.get("isStale") or freshness == "stale")
        is_refreshing = bool(payload.get("isRefreshing") or getattr(entry, "is_refreshing", False))
        is_from_snapshot = bool(payload.get("isFromSnapshot") or (entry is None and snapshot))
        status = self._status(provider_health, payload, entry, freshness, is_fallback, is_stale, is_refreshing, is_from_snapshot)
        last_successful = self._safe_public_text(payload.get("lastSuccessfulAt") or payload.get("asOf") or (snapshot.get("as_of") if isinstance(snapshot, dict) else None))
        as_of = self._safe_public_text(payload.get("asOf") or payload.get("last_update") or (snapshot.get("as_of") if isinstance(snapshot, dict) else None))
        updated_at = self._safe_public_text(payload.get("updatedAt") or payload.get("last_update") or payload.get("last_refresh_at") or (snapshot.get("updated_at") if isinstance(snapshot, dict) else None))
        last_successful_time = self._parse_time(last_successful or as_of or updated_at)
        trust_evidence = self._trust_evidence_snapshot(
            panel=panel,
            payload=payload,
            generated_at=now,
            as_of=last_successful_time,
            status=status,
            freshness=freshness,
            source=source,
            is_fallback=is_fallback,
            is_stale=is_stale,
            is_refreshing=is_refreshing,
            is_from_snapshot=is_from_snapshot,
        )
        return {
            "provider": source,
            "sourceLabel": self._provider_source_label(source, payload.get("sourceLabel")),
            "sourceType": self._safe_public_text(payload.get("sourceType")),
            "domain": panel.domain,
            "endpoint": panel.endpoint,
            "card": self._safe_public_text(payload.get("panelName") or payload.get("panel_name") or panel.card) or panel.card,
            "cacheKey": panel.cache_key,
            "status": status,
            "freshness": freshness,
            "asOf": as_of,
            "updatedAt": updated_at,
            "lastSuccessfulAt": last_successful,
            "lastKnownGoodAgeMinutes": self._age_minutes(last_successful_time, now),
            "latencyMs": self._number_or_none(provider_health.get("latencyMs") or payload.get("latencyMs")),
            "isFallback": is_fallback,
            "isStale": is_stale,
            "isRefreshing": is_refreshing,
            "isFromSnapshot": is_from_snapshot,
            "fallbackUsed": bool(is_fallback or payload.get("fallbackUsed") or payload.get("fallback_used")),
            "warning": self._safe_error(payload.get("warning")),
            "errorSummary": self._safe_error(provider_health.get("errorSummary") or payload.get("lastError") or payload.get("refreshError") or (snapshot.get("last_error") if isinstance(snapshot, dict) else None)),
            "trustEvidence": trust_evidence,
            "adminLogDrillThrough": self._drillthrough(category=None, provider=source, query=panel.endpoint),
        }

    @classmethod
    def _trust_evidence_snapshot(
        cls,
        *,
        panel: MarketProviderPanel,
        payload: Dict[str, Any],
        generated_at: datetime,
        as_of: Optional[datetime],
        status: str,
        freshness: Optional[str],
        source: str,
        is_fallback: bool,
        is_stale: bool,
        is_refreshing: bool,
        is_from_snapshot: bool,
    ) -> Dict[str, Any]:
        is_partial = status == "partial" or bool(payload.get("isPartial") or payload.get("partial"))
        is_synthetic = cls._trust_evidence_is_synthetic(source=source, freshness=freshness)
        has_fallback = bool(is_fallback or status == "fallback")
        availability_state, consumer_state, message_key = cls._trust_evidence_availability(
            status=status,
            is_refreshing=is_refreshing,
            is_fallback=has_fallback,
            is_stale=is_stale,
            is_partial=is_partial,
            is_synthetic=is_synthetic,
        )
        freshness_state = cls._trust_evidence_freshness(
            status=status,
            freshness=freshness,
            is_fallback=has_fallback,
            is_stale=is_stale,
            is_from_snapshot=is_from_snapshot,
            is_synthetic=is_synthetic,
        )
        source_class = cls._trust_evidence_source_class(
            payload.get("sourceType"),
            source=source,
            is_fallback=has_fallback,
            is_from_snapshot=is_from_snapshot,
            is_synthetic=is_synthetic,
        )
        snapshot = build_trust_evidence_snapshot_v1(
            surface_key="market_provider_operations",
            entity_key=f"market_provider_operations:{panel.cache_key}",
            generated_at=generated_at,
            as_of=as_of,
            availability_state=availability_state,
            freshness_state=freshness_state,
            source_class=source_class,
            has_fallback=has_fallback,
            is_stale=is_stale,
            is_partial=is_partial,
            is_synthetic=is_synthetic,
            is_admin_only_detail=False,
            consumer_state=consumer_state,
            consumer_message_key=message_key,
            consumer_badge_keys=cls._trust_evidence_badges(
                consumer_state=consumer_state,
                freshness_state=freshness_state,
                has_fallback=has_fallback,
                is_stale=is_stale,
                is_partial=is_partial,
                is_synthetic=is_synthetic,
            ),
            admin_diagnostic_refs=(f"trust-evidence:market-provider-operations:{panel.cache_key}",),
        )
        return snapshot.model_dump(mode="json")

    @staticmethod
    def _trust_evidence_availability(
        *,
        status: str,
        is_refreshing: bool,
        is_fallback: bool,
        is_stale: bool,
        is_partial: bool,
        is_synthetic: bool,
    ) -> Tuple[str, str, str]:
        if status in {"unavailable", "error"}:
            return "unavailable", "UNAVAILABLE", "trust_evidence.unavailable"
        if is_refreshing or status == "refreshing":
            return "updating", "UPDATING", "trust_evidence.updating"
        if is_synthetic:
            return "observation_only", "OBSERVATION_ONLY", "trust_evidence.observation_only"
        if is_fallback or status == "fallback":
            return "partial", "PARTIAL", "trust_evidence.fallback"
        if is_partial or status == "partial":
            return "partial", "PARTIAL", "trust_evidence.partial"
        if is_stale or status == "stale":
            return "delayed", "DELAYED", "trust_evidence.stale"
        return "available", "AVAILABLE", "trust_evidence.available"

    @staticmethod
    def _trust_evidence_freshness(
        *,
        status: str,
        freshness: Optional[str],
        is_fallback: bool,
        is_stale: bool,
        is_from_snapshot: bool,
        is_synthetic: bool,
    ) -> str:
        normalized = str(freshness or "").strip().lower()
        if is_synthetic or normalized == "mock":
            return "synthetic"
        if is_fallback or status == "fallback" or normalized == "fallback":
            return "fallback"
        if is_stale or status == "stale" or normalized == "stale":
            return "stale"
        if status in {"unavailable", "error"}:
            return "unavailable"
        if normalized == "live":
            return "live"
        if normalized in {"fresh", "delayed", "cached", "partial"}:
            return normalized
        if normalized == "cache" or status == "cache" or is_from_snapshot:
            return "cached"
        if status == "partial":
            return "partial"
        return "unknown"

    @staticmethod
    def _trust_evidence_source_class(
        source_type: Any,
        *,
        source: str,
        is_fallback: bool,
        is_from_snapshot: bool,
        is_synthetic: bool,
    ) -> str:
        if is_synthetic:
            return "synthetic"
        normalized_type = str(source_type or "").strip().lower()
        if normalized_type:
            if "official" in normalized_type:
                return "official_public"
            if "licensed" in normalized_type or "authorized" in normalized_type:
                return "licensed_authorized"
            if "proxy" in normalized_type or normalized_type in {"public", "public_api", "api"}:
                return "public_proxy"
            if "cache" in normalized_type:
                return "local_cache"
        normalized_source = str(source or "").strip().lower()
        if normalized_source in {"mock"}:
            return "synthetic"
        if is_fallback or is_from_snapshot or normalized_source in {"fallback", "cached"}:
            return "local_cache"
        return "unknown"

    @staticmethod
    def _trust_evidence_is_synthetic(*, source: str, freshness: Optional[str]) -> bool:
        normalized_source = str(source or "").strip().lower()
        normalized_freshness = str(freshness or "").strip().lower()
        return normalized_source == "mock" or normalized_freshness == "mock"

    @staticmethod
    def _trust_evidence_badges(
        *,
        consumer_state: str,
        freshness_state: str,
        has_fallback: bool,
        is_stale: bool,
        is_partial: bool,
        is_synthetic: bool,
    ) -> Tuple[str, ...]:
        if consumer_state == "UNAVAILABLE":
            return ("source_unavailable",)
        if is_synthetic:
            return ("observation_only",)

        badges: List[str] = []
        if freshness_state == "delayed":
            badges.append("source_delayed")
        if is_stale:
            badges.append("source_stale")
        if is_partial:
            badges.append("source_partial")
        if has_fallback:
            badges.append("source_fallback")
        if not badges:
            badges.append("source_current")
        return tuple(badges)

    def _read_market_events(self, window: str) -> List[Dict[str, Any]]:
        events_by_id: Dict[str, Dict[str, Any]] = {}
        for category in MARKET_LOG_CATEGORIES:
            items, _ = self.log_service.list_business_events(
                category=category,
                since=window,
                limit=200,
                offset=0,
            )
            for item in items:
                if not self._is_market_event(item):
                    continue
                event_id = str(item.get("id") or "")
                if event_id:
                    events_by_id[event_id] = item
        return list(events_by_id.values())

    def _rollup_events(self, events: Iterable[Dict[str, Any]], window: str) -> List[Dict[str, Any]]:
        buckets: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        reasons: Dict[Tuple[str, str, str], Counter] = defaultdict(Counter)
        for event in events:
            provider = self._safe_public_text(event.get("provider") or event.get("source") or "unknown") or "unknown"
            endpoint = self._safe_public_text(event.get("endpoint"))
            card = self._safe_public_text(event.get("component") or event.get("contextLabel"))
            key = (provider, endpoint or "", card or "")
            bucket = buckets.setdefault(
                key,
                {
                    "provider": provider,
                    "endpoint": endpoint,
                    "card": card,
                    "category": self._safe_public_text(event.get("category")),
                    "eventCount": 0,
                    "failureCount": 0,
                    "fallbackCount": 0,
                    "staleServedCount": 0,
                    "slowCount": 0,
                    "latestLogEventId": None,
                    "latestStartedAt": None,
                },
            )
            bucket["eventCount"] += 1
            if self._is_failure_event(event):
                bucket["failureCount"] += 1
            if self._is_fallback_event(event):
                bucket["fallbackCount"] += 1
            if self._is_stale_event(event):
                bucket["staleServedCount"] += 1
            if self._is_slow_event(event):
                bucket["slowCount"] += 1
            reason = self._safe_error(event.get("reason") or event.get("errorSummary") or event.get("eventType"))
            if reason:
                reasons[key][reason] += 1
            started_at = self._safe_public_text(event.get("startedAt"))
            if started_at and (not bucket["latestStartedAt"] or started_at > bucket["latestStartedAt"]):
                bucket["latestStartedAt"] = started_at
                bucket["latestLogEventId"] = self._safe_public_text(event.get("id"))
        rollups: List[Dict[str, Any]] = []
        for key, bucket in buckets.items():
            event_count = int(bucket["eventCount"] or 0)
            bucket["failureRate"] = round(float(bucket["failureCount"]) / float(event_count), 4) if event_count else 0
            bucket["topReasons"] = [reason for reason, _ in reasons[key].most_common(5)]
            bucket["adminLogDrillThrough"] = self._drillthrough(
                category=bucket.get("category"),
                provider=bucket.get("provider"),
                query=bucket.get("endpoint") or bucket.get("card"),
                since=window,
                event_id=bucket.get("latestLogEventId"),
            )
            rollups.append(bucket)
        return sorted(rollups, key=lambda item: (str(item.get("latestStartedAt") or ""), int(item.get("eventCount") or 0)), reverse=True)

    def _summary(self, items: List[Dict[str, Any]], event_rollups: List[Dict[str, Any]]) -> Dict[str, Any]:
        counts = Counter(str(item.get("status") or "unavailable") for item in items)
        return {
            "totalItems": len(items),
            "liveCount": counts["live"],
            "cacheCount": counts["cache"],
            "staleCount": counts["stale"],
            "fallbackCount": counts["fallback"],
            "partialCount": counts["partial"],
            "unavailableCount": counts["unavailable"],
            "errorCount": counts["error"],
            "refreshingCount": counts["refreshing"],
            "eventCount": sum(int(item.get("eventCount") or 0) for item in event_rollups),
            "failureCount": sum(int(item.get("failureCount") or 0) for item in event_rollups),
            "fallbackEventCount": sum(int(item.get("fallbackCount") or 0) for item in event_rollups),
            "staleEventCount": sum(int(item.get("staleServedCount") or 0) for item in event_rollups),
            "slowEventCount": sum(int(item.get("slowCount") or 0) for item in event_rollups),
        }

    @staticmethod
    def _market_cache_event_summary() -> Dict[str, Any]:
        totals = MarketProviderOperationsService._empty_market_cache_event_counts()
        by_panel: Dict[Tuple[str, str], Dict[str, Any]] = {}

        for row in snapshot_llm_event_counters():
            event_name = str(row.get("event") or "")
            field = MARKET_CACHE_EVENT_COUNTER_FIELDS.get(event_name)
            if field is None:
                continue
            count = int(row.get("count") or 0)
            labels = row.get("labels") if isinstance(row.get("labels"), dict) else {}
            panel_key = MarketProviderOperationsService._safe_market_cache_panel_key(labels.get("panel_key"))
            endpoint_family = MarketProviderOperationsService._safe_counter_label(labels.get("endpoint_family")) or "unknown"
            bucket = by_panel.setdefault(
                (panel_key, endpoint_family),
                {
                    "panelKey": panel_key,
                    "endpointFamily": endpoint_family,
                    **MarketProviderOperationsService._empty_market_cache_event_counts(),
                },
            )
            totals[field] += count
            bucket[field] += count

        return {
            "metadata": {
                "countersSource": "process_local",
                "readOnly": True,
                "externalProviderCalls": False,
                "cacheMutation": False,
                "exactness": "observational_not_billing",
                "durability": "process_local_not_durable",
            },
            "totals": totals,
            "byPanelKey": sorted(
                by_panel.values(),
                key=lambda item: (
                    -sum(int(item.get(field) or 0) for field in MARKET_CACHE_EVENT_SUMMARY_FIELDS),
                    str(item.get("panelKey") or ""),
                    str(item.get("endpointFamily") or ""),
                ),
            ),
        }

    @staticmethod
    def _empty_market_cache_event_counts() -> Dict[str, int]:
        return {field: 0 for field in MARKET_CACHE_EVENT_SUMMARY_FIELDS}

    @staticmethod
    def _safe_market_cache_panel_key(value: Any) -> str:
        text = MarketProviderOperationsService._safe_counter_label(value) or "unknown"
        return text if text in SAFE_MARKET_CACHE_PANEL_KEYS else "unknown"

    @staticmethod
    def _safe_counter_label(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value or "").strip().lower()
        if not re.fullmatch(r"[a-z0-9._:/-]{1,64}", text):
            return None
        return text

    @staticmethod
    def _status(
        provider_health: Dict[str, Any],
        payload: Dict[str, Any],
        entry: Any,
        freshness: Optional[str],
        is_fallback: bool,
        is_stale: bool,
        is_refreshing: bool,
        is_from_snapshot: bool,
    ) -> str:
        explicit = str(provider_health.get("status") or "").strip().lower()
        if explicit in {"live", "cache", "stale", "fallback", "partial", "unavailable", "error", "refreshing"}:
            return explicit
        source = str(payload.get("source") or "").lower()
        if is_refreshing:
            return "refreshing"
        if source == "unavailable" or freshness == "error":
            return "unavailable"
        if payload.get("lastError") or payload.get("refreshError"):
            return "stale" if (is_stale or is_from_snapshot) else "error"
        if is_fallback or freshness in {"fallback", "mock"} or source in {"fallback", "mock"}:
            return "fallback"
        if is_stale or freshness == "stale" or is_from_snapshot:
            return "stale"
        if freshness == "live":
            return "live"
        if entry is not None or payload:
            return "cache"
        return "unavailable"

    @staticmethod
    def _is_market_event(event: Dict[str, Any]) -> bool:
        event_text = " ".join(
            str(event.get(key) or "")
            for key in ("event", "eventType", "summary", "contextLabel", "component", "endpoint", "feature")
        )
        return (
            str(event.get("eventType") or "") in MARKET_EVENT_NAMES
            or "Market" in event_text
            or "/api/v1/market" in event_text
        )

    @staticmethod
    def _is_failure_event(event: Dict[str, Any]) -> bool:
        return str(event.get("status") or "").lower() in {"failed", "error", "critical"} or "fail" in str(event.get("eventType") or "").lower()

    @staticmethod
    def _is_fallback_event(event: Dict[str, Any]) -> bool:
        text = f"{event.get('eventType') or ''} {event.get('summary') or ''} {event.get('reason') or ''}".lower()
        return "fallback" in text or "备用" in text

    @staticmethod
    def _is_stale_event(event: Dict[str, Any]) -> bool:
        text = f"{event.get('eventType') or ''} {event.get('summary') or ''} {event.get('reason') or ''}".lower()
        return "stale" in text or "过期" in text

    @staticmethod
    def _is_slow_event(event: Dict[str, Any]) -> bool:
        if "slow" in str(event.get("eventType") or "").lower():
            return True
        duration = MarketProviderOperationsService._number_or_none(event.get("durationMs"))
        return bool(duration is not None and duration >= 2000)

    @staticmethod
    def _normalize_window(window: str) -> str:
        text = str(window or "24h").strip().lower()
        return text if text in SAFE_WINDOW_VALUES else "24h"

    @staticmethod
    def _drillthrough(
        *,
        category: Optional[str] = None,
        provider: Optional[str] = None,
        query: Optional[str] = None,
        since: str = "24h",
        event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        safe_query: Dict[str, str] = {"since": MarketProviderOperationsService._normalize_window(since)}
        if category:
            safe_query["category"] = str(category)
        if provider and provider != "unknown":
            safe_query["provider"] = MarketProviderOperationsService._safe_public_text(provider) or provider
        if query:
            safe_query["query"] = MarketProviderOperationsService._safe_public_text(query) or ""
        return {
            "label": "查看 Admin Logs",
            "route": "/zh/admin/logs",
            "query": safe_query,
            "eventId": MarketProviderOperationsService._safe_public_text(event_id),
        }

    @staticmethod
    def _safe_public_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = sanitize_message(str(value).strip())
        if not text:
            return None
        text = SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=***", text)
        if SECRET_WORD_RE.search(text):
            text = SECRET_WORD_RE.sub("***", text)
        return text[:500]

    @staticmethod
    def _provider_source_label(source: Any, source_label: Any = None) -> Optional[str]:
        explicit_label = MarketProviderOperationsService._safe_public_text(source_label)
        if explicit_label:
            return explicit_label

        normalized_source = str(source or "").strip().lower()
        if not normalized_source:
            return None
        if (
            normalized_source not in PROVIDER_OPS_REGISTRY_LABEL_SOURCES
            and normalized_source not in PROVIDER_OPS_LEGACY_LABEL_OVERRIDES
        ):
            return None
        return MarketProviderOperationsService._safe_public_text(
            resolve_source_label(
                normalized_source,
                source_label=PROVIDER_OPS_LEGACY_LABEL_OVERRIDES.get(normalized_source),
            )
        )

    @staticmethod
    def _safe_error(value: Any) -> Optional[str]:
        text = MarketProviderOperationsService._safe_public_text(value)
        return text[:180] if text else None

    @staticmethod
    def _number_or_none(value: Any) -> Optional[float]:
        try:
            number = float(value)
        except Exception:
            return None
        return number if number >= 0 else None

    @staticmethod
    def _parse_time(value: Any) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            parsed = value
        else:
            try:
                parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except Exception:
                return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=CN_TZ)
        return parsed.astimezone(CN_TZ)

    @staticmethod
    def _iso(value: Any) -> Optional[str]:
        parsed = MarketProviderOperationsService._parse_time(value)
        return parsed.isoformat(timespec="seconds") if parsed else None

    @staticmethod
    def _age_minutes(value: Optional[datetime], now: datetime) -> Optional[int]:
        if value is None:
            return None
        return max(0, int((now - value.astimezone(CN_TZ)).total_seconds() // 60))

    @staticmethod
    def _now() -> datetime:
        return datetime.now(CN_TZ)
