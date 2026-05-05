# -*- coding: utf-8 -*-
"""Small in-memory cache for market snapshots with stale-while-revalidate."""

from __future__ import annotations

import copy
import hashlib
import logging
import re
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Optional

from src.services.llm_instrumentation import emit_market_cache_event


CN_TZ = timezone(timedelta(hours=8))
REFRESH_WARNING = "数据源刷新失败，当前显示最近快照"
logger = logging.getLogger(__name__)


MARKET_CACHE_TTLS = {
    "crypto": 15,
    "futures": 30,
    "equity_index": 30,
    "cn_indices": 30,
    "fx_commodity": 60,
    "breadth": 60,
    "flows": 180,
    "sector_rotation": 180,
    "sentiment": 1800,
    "rates": 600,
    "temperature": 30,
    "market_briefing": 30,
}
SAFE_MARKET_CACHE_PANEL_KEYS = frozenset(
    {
        *MARKET_CACHE_TTLS.keys(),
        "indices",
        "volatility",
        "funds_flow",
        "macro",
        "cn_breadth",
        "us_breadth",
        "cn_flows",
        "fx_commodities",
        "cn_short_sentiment",
    }
)


@dataclass
class MarketCacheEntry:
    key: str
    data: dict
    fetched_at: datetime
    expires_at: datetime
    ttl_seconds: int
    is_refreshing: bool = False
    last_error: Optional[str] = None


class MarketCache:
    """Thread-safe market cache shaped so it can be swapped for Redis later."""

    def __init__(self, max_workers: int = 4) -> None:
        self._entries: Dict[str, MarketCacheEntry] = {}
        self._locks: Dict[str, threading.RLock] = {}
        self._global_lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="market-cache")
        self._futures: set[Future] = set()

    def get(self, key: str) -> Optional[MarketCacheEntry]:
        with self._lock_for(key):
            return self._entries.get(key)

    def set(self, key: str, data: dict, ttl_seconds: int) -> MarketCacheEntry:
        now = self._now()
        entry = MarketCacheEntry(
            key=key,
            data=copy.deepcopy(data),
            fetched_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
            ttl_seconds=ttl_seconds,
        )
        with self._lock_for(key):
            self._entries[key] = entry
        return entry

    def is_fresh(self, key: str) -> bool:
        entry = self.get(key)
        return bool(entry and entry.expires_at > self._now())

    def get_or_refresh(
        self,
        key: str,
        ttl_seconds: int,
        fetcher: Callable[[], dict],
        fallback_factory: Optional[Callable[[], dict]] = None,
        allow_stale: bool = True,
        background_refresh: bool = True,
        cold_start_timeout_seconds: Optional[float] = None,
    ) -> dict:
        lock = self._lock_for(key)
        wait_started_at: Optional[float] = None
        while True:
            with lock:
                entry = self._entries.get(key)
                if entry and entry.expires_at > self._now():
                    logger.debug("[MarketCache] cache hit key=%s", key)
                    self._emit_cache_event(key, "market_cache_hit", freshness_bucket="fresh")
                    return self._payload(entry)
                if entry and entry.data and allow_stale:
                    if background_refresh:
                        self._start_background_refresh(key, ttl_seconds, fetcher)
                    logger.debug("[MarketCache] stale return key=%s refreshing=%s", key, bool(entry.is_refreshing))
                    self._emit_cache_event(key, "market_cache_stale_served", freshness_bucket="stale")
                    return self._payload(entry, is_stale=True)
                if entry and entry.is_refreshing:
                    if wait_started_at is None:
                        wait_started_at = time.monotonic()
                    if (
                        fallback_factory is not None
                        and cold_start_timeout_seconds is not None
                        and time.monotonic() - wait_started_at >= cold_start_timeout_seconds
                    ):
                        data = fallback_factory()
                        now = self._now()
                        entry.data = copy.deepcopy(data)
                        entry.fetched_at = now
                        entry.expires_at = now + timedelta(seconds=ttl_seconds)
                        entry.ttl_seconds = ttl_seconds
                        entry.is_refreshing = True
                        logger.debug("[MarketCache] cold wait fallback return key=%s", key)
                        self._emit_cache_event(
                            key,
                            "market_cache_cold_start_fallback_served",
                            freshness_bucket="fallback",
                            outcome="timeout",
                        )
                        return self._payload(entry)
                else:
                    self._emit_cache_event(key, "market_cache_miss", freshness_bucket="cold")
                    placeholder = entry or MarketCacheEntry(
                        key=key,
                        data={},
                        fetched_at=self._now(),
                        expires_at=self._now() - timedelta(seconds=1),
                        ttl_seconds=ttl_seconds,
                        is_refreshing=True,
                    )
                    placeholder.is_refreshing = True
                    placeholder.ttl_seconds = ttl_seconds
                    self._entries[key] = placeholder
                    break
            time.sleep(0.01)

        if background_refresh and fallback_factory is not None and cold_start_timeout_seconds is not None:
            logger.debug("[MarketCache] cold fetch start key=%s timeout=%s", key, cold_start_timeout_seconds)
            self._emit_cache_event(key, "market_cache_refresh_started", refresh_mode="cold")
            future = self._executor.submit(self._refresh, key, ttl_seconds, fetcher, "cold")
            with self._global_lock:
                self._futures.add(future)
            future.add_done_callback(self._discard_future)
            try:
                future.result(timeout=cold_start_timeout_seconds)
            except TimeoutError:
                data = fallback_factory()
                with lock:
                    current = self._entries.get(key)
                    if current and current.data and not current.is_refreshing:
                        return self._payload(current)
                    placeholder = current or MarketCacheEntry(
                        key=key,
                        data={},
                        fetched_at=self._now(),
                        expires_at=self._now() - timedelta(seconds=1),
                        ttl_seconds=ttl_seconds,
                        is_refreshing=True,
                    )
                    now = self._now()
                    placeholder.data = copy.deepcopy(data)
                    placeholder.fetched_at = now
                    placeholder.expires_at = now + timedelta(seconds=ttl_seconds)
                    placeholder.ttl_seconds = ttl_seconds
                    placeholder.is_refreshing = True
                    self._entries[key] = placeholder
                    logger.debug("[MarketCache] cold fallback return key=%s", key)
                    self._emit_cache_event(
                        key,
                        "market_cache_cold_start_fallback_served",
                        freshness_bucket="fallback",
                        outcome="timeout",
                    )
                    return self._payload(placeholder)

            with lock:
                current = self._entries.get(key)
                if current and current.data:
                    return self._payload(current)
                last_error = current.last_error if current else None

            data = fallback_factory()
            with lock:
                new_entry = self._entry_from_data(key, data, ttl_seconds)
                new_entry.last_error = last_error
                self._entries[key] = new_entry
                logger.debug("[MarketCache] cold fallback return key=%s error=%s", key, bool(last_error))
                self._emit_cache_event(
                    key,
                    "market_cache_cold_start_fallback_served",
                    freshness_bucket="fallback",
                    outcome="error" if last_error else "empty_refresh",
                    error_bucket=last_error,
                )
                return self._payload(new_entry)

        try:
            logger.debug("[MarketCache] cold fetch start key=%s", key)
            started_at = time.monotonic()
            self._emit_cache_event(key, "market_cache_refresh_started", refresh_mode="cold")
            data = fetcher()
        except Exception as exc:
            self._emit_cache_event(
                key,
                "market_cache_refresh_failed",
                refresh_mode="cold",
                outcome="failed",
                error_bucket=exc,
            )
            if fallback_factory is None:
                with lock:
                    current = self._entries.get(key)
                    if current:
                        current.is_refreshing = False
                        current.last_error = str(exc)
                raise
            data = fallback_factory()
            with lock:
                new_entry = self._entry_from_data(key, data, ttl_seconds)
                new_entry.last_error = str(exc)
                self._entries[key] = new_entry
                logger.debug("[MarketCache] fallback return key=%s error=%s", key, exc)
                self._emit_cache_event(
                    key,
                    "market_cache_cold_start_fallback_served",
                    freshness_bucket="fallback",
                    outcome="error",
                    error_bucket=exc,
                )
                return self._payload(new_entry)

        with lock:
            new_entry = self._entry_from_data(key, data, ttl_seconds)
            self._entries[key] = new_entry
            self._emit_cache_event(
                key,
                "market_cache_refresh_completed",
                refresh_mode="cold",
                outcome="success",
                duration_bucket=(time.monotonic() - started_at) * 1000,
                freshness_bucket="fresh",
            )
            return self._payload(new_entry)

    def wait_for_refreshes(self, timeout: float = 5.0) -> bool:
        futures = self._snapshot_futures()
        for future in futures:
            try:
                future.result(timeout=timeout)
            except Exception:
                return False
        return True

    def clear(self) -> None:
        with self._global_lock:
            self._entries.clear()
            self._locks.clear()
            self._futures.clear()

    def _start_background_refresh(self, key: str, ttl_seconds: int, fetcher: Callable[[], dict]) -> None:
        entry = self._entries.get(key)
        if entry is None or entry.is_refreshing:
            return
        entry.is_refreshing = True
        self._emit_cache_event(key, "market_cache_refresh_started", refresh_mode="background")
        future = self._executor.submit(self._refresh, key, ttl_seconds, fetcher, "background")
        with self._global_lock:
            self._futures.add(future)
        future.add_done_callback(self._discard_future)

    def _refresh(self, key: str, ttl_seconds: int, fetcher: Callable[[], dict], refresh_mode: str = "background") -> None:
        lock = self._lock_for(key)
        started_at = time.monotonic()
        try:
            data = fetcher()
        except Exception as exc:
            with lock:
                entry = self._entries.get(key)
                if entry:
                    entry.is_refreshing = False
                    entry.last_error = str(exc)
            logger.debug("[MarketCache] refresh failed key=%s error=%s", key, exc)
            self._emit_cache_event(
                key,
                "market_cache_refresh_failed",
                refresh_mode=refresh_mode,
                outcome="failed",
                duration_bucket=(time.monotonic() - started_at) * 1000,
                error_bucket=exc,
            )
            return
        with lock:
            self._entries[key] = self._entry_from_data(key, data, ttl_seconds)
        logger.debug("[MarketCache] refresh success key=%s", key)
        self._emit_cache_event(
            key,
            "market_cache_refresh_completed",
            refresh_mode=refresh_mode,
            outcome="success",
            duration_bucket=(time.monotonic() - started_at) * 1000,
            freshness_bucket="fresh",
        )

    def _payload(self, entry: MarketCacheEntry, is_stale: bool = False) -> dict:
        payload = copy.deepcopy(entry.data)
        if entry.is_refreshing:
            payload["isRefreshing"] = True
        else:
            payload.setdefault("isRefreshing", False)
        if is_stale or entry.expires_at <= self._now():
            payload.setdefault("isStale", True)
        if entry.last_error:
            payload["lastError"] = entry.last_error
            payload["refreshError"] = entry.last_error
            payload["warning"] = payload.get("warning") or REFRESH_WARNING
        return payload

    def _entry_from_data(self, key: str, data: dict, ttl_seconds: int) -> MarketCacheEntry:
        now = self._now()
        return MarketCacheEntry(
            key=key,
            data=copy.deepcopy(data),
            fetched_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
            ttl_seconds=ttl_seconds,
            is_refreshing=False,
        )

    def _lock_for(self, key: str) -> threading.RLock:
        with self._global_lock:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.RLock()
                self._locks[key] = lock
            return lock

    def _snapshot_futures(self) -> list[Future]:
        with self._global_lock:
            return list(self._futures)

    def _discard_future(self, future: Future) -> None:
        with self._global_lock:
            self._futures.discard(future)

    def _emit_cache_event(self, key: str, event_name: str, **labels: object) -> None:
        emit_market_cache_event(event_name, **self._metric_labels(key, **labels))

    def _metric_labels(self, key: str, **labels: object) -> dict:
        safe_panel = self._safe_panel_key(key)
        base: dict = {
            "endpoint_family": "market_cache",
            "cache_key_hash": hashlib.sha256(key.encode("utf-8")).hexdigest()[:12],
            "provider_category": safe_panel if safe_panel in MARKET_CACHE_TTLS else "unknown",
        }
        if safe_panel != "unknown":
            base["panel_key"] = safe_panel
        base.update(labels)
        return base

    @staticmethod
    def _safe_panel_key(key: str) -> str:
        text = str(key or "").strip().lower()
        if text in SAFE_MARKET_CACHE_PANEL_KEYS and re.fullmatch(r"[a-z0-9_-]{1,48}", text):
            return text
        return "unknown"

    @staticmethod
    def _now() -> datetime:
        return datetime.now(CN_TZ)


market_cache = MarketCache()
