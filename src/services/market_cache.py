# -*- coding: utf-8 -*-
"""Small in-memory cache for market snapshots with stale-while-revalidate."""

from __future__ import annotations

import copy
import hashlib
import logging
import queue
import re
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional, Protocol

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
REMOTE_RUNTIME_ONLY_FIELDS = frozenset({"isRefreshing", "lastError", "refreshError"})


@dataclass
class MarketCacheEntry:
    key: str
    data: dict
    fetched_at: datetime
    expires_at: datetime
    ttl_seconds: int
    is_refreshing: bool = False
    last_error: Optional[str] = None
    refresh_started_at: Optional[float] = None
    refresh_generation: int = 0


class MarketCacheRemoteBackend(Protocol):
    """Best-effort remote mirror for future persisted MarketCache projections."""

    def persist(self, key: str, document: dict) -> None:
        """Persist a JSON-safe mirror document for the given cache key."""


class NullMarketCacheRemoteBackend:
    """Default remote backend that preserves current local-only behavior."""

    def persist(self, key: str, document: dict) -> None:
        return None


class MarketCacheRemoteMirrorDispatcher:
    """Asynchronous mirror-only wrapper for best-effort remote persistence."""

    _STOP = object()

    def __init__(self, backend: MarketCacheRemoteBackend, queue_size: int = 256) -> None:
        if queue_size < 1:
            raise ValueError("queue_size must be positive")
        self._backend = backend
        self._queue: queue.Queue[object] = queue.Queue(maxsize=queue_size)
        self._state_lock = threading.Lock()
        self._pending_done = threading.Condition()
        self._pending = 0
        self._closed = False
        self._worker = threading.Thread(
            target=self._run,
            name="market-cache-remote-mirror",
            daemon=True,
        )
        self._worker.start()

    def persist(self, key: str, document: dict) -> None:
        try:
            document_copy = copy.deepcopy(document)
        except Exception:
            logger.debug(
                "[MarketCacheRemoteMirrorDispatcher] mirror skipped key_hash=%s reason=document_copy_failed",
                self._safe_key_hash(key),
            )
            return
        with self._state_lock:
            if self._closed:
                logger.debug(
                    "[MarketCacheRemoteMirrorDispatcher] mirror skipped key_hash=%s reason=closed",
                    self._safe_key_hash(key),
                )
                return
            try:
                self._increment_pending()
                self._queue.put_nowait((key, document_copy))
            except queue.Full:
                self._decrement_pending()
                logger.debug(
                    "[MarketCacheRemoteMirrorDispatcher] mirror skipped key_hash=%s reason=queue_full queue_size=%s",
                    self._safe_key_hash(key),
                    self._queue.maxsize,
                )

    def drain(self, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        with self._pending_done:
            while self._pending:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._pending_done.wait(remaining)
        return True

    def shutdown(self, timeout: float = 5.0) -> bool:
        with self._state_lock:
            already_closed = self._closed
            self._closed = True
        drained = self.drain(timeout=timeout)
        with self._state_lock:
            if not already_closed:
                try:
                    self._queue.put_nowait(self._STOP)
                except queue.Full:
                    return False
        self._worker.join(timeout=timeout)
        return drained and not self._worker.is_alive()

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is self._STOP:
                    return
                key, document = item
                try:
                    self._backend.persist(key, document)
                except Exception:
                    logger.debug(
                        "[MarketCacheRemoteMirrorDispatcher] mirror skipped key_hash=%s reason=backend_error backend=%s",
                        self._safe_key_hash(key),
                        self._safe_backend_name(),
                    )
                finally:
                    self._decrement_pending()
            finally:
                self._queue.task_done()

    def _increment_pending(self) -> None:
        with self._pending_done:
            self._pending += 1

    def _decrement_pending(self) -> None:
        with self._pending_done:
            if self._pending > 0:
                self._pending -= 1
            if self._pending == 0:
                self._pending_done.notify_all()

    def _safe_backend_name(self) -> str:
        name = type(self._backend).__name__
        return re.sub(r"[^A-Za-z0-9_.-]", "_", name)[:80] or "unknown"

    @staticmethod
    def _safe_key_hash(key: str) -> str:
        return hashlib.sha256(str(key).encode("utf-8")).hexdigest()[:12]


class MarketCache:
    """Thread-safe market cache shaped so it can be swapped for Redis later."""

    def __init__(
        self,
        max_workers: int = 4,
        refresh_stale_after_seconds: float = 30.0,
        remote_backend: Optional[MarketCacheRemoteBackend] = None,
    ) -> None:
        self._entries: Dict[str, MarketCacheEntry] = {}
        self._locks: Dict[str, threading.RLock] = {}
        self._global_lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="market-cache")
        self._futures: set[Future] = set()
        self._refresh_stale_after_seconds = refresh_stale_after_seconds
        self._refresh_generation_counter = 0
        self._remote_backend: MarketCacheRemoteBackend = remote_backend or NullMarketCacheRemoteBackend()

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
        self._persist_remote_entry_best_effort(entry)
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
        refresh_generation: Optional[int] = None
        while True:
            with lock:
                entry = self._entries.get(key)
                refresh_was_stale = False
                if entry and entry.is_refreshing and self._refresh_is_stale(entry):
                    self._clear_refresh_state(entry)
                    refresh_was_stale = True
                if entry and entry.expires_at > self._now():
                    if refresh_was_stale and background_refresh:
                        self._start_background_refresh(key, ttl_seconds, fetcher)
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
                    )
                    placeholder.ttl_seconds = ttl_seconds
                    refresh_generation = self._mark_refresh_started(placeholder)
                    self._entries[key] = placeholder
                    break
            time.sleep(0.01)

        if background_refresh and fallback_factory is not None and cold_start_timeout_seconds is not None:
            logger.debug("[MarketCache] cold fetch start key=%s timeout=%s", key, cold_start_timeout_seconds)
            self._emit_cache_event(key, "market_cache_refresh_started", refresh_mode="cold")
            future = self._executor.submit(self._refresh, key, ttl_seconds, fetcher, "cold", refresh_generation)
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
                    )
                    now = self._now()
                    placeholder.data = copy.deepcopy(data)
                    placeholder.fetched_at = now
                    placeholder.expires_at = now + timedelta(seconds=ttl_seconds)
                    placeholder.ttl_seconds = ttl_seconds
                    placeholder.is_refreshing = True
                    if placeholder.refresh_started_at is None:
                        placeholder.refresh_started_at = time.monotonic()
                    if placeholder.refresh_generation == 0 and refresh_generation is not None:
                        placeholder.refresh_generation = refresh_generation
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
                        self._clear_refresh_state(current)
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

    def project_remote_entry(self, entry: MarketCacheEntry, *, is_stale: bool = False) -> dict:
        sanitized = self._project_remote_value(entry.data)
        if is_stale or entry.expires_at <= self._now():
            sanitized.setdefault("isStale", True)
        return {
            "key": entry.key,
            "ttlSeconds": entry.ttl_seconds,
            "fetchedAt": entry.fetched_at.isoformat(timespec="seconds"),
            "expiresAt": entry.expires_at.isoformat(timespec="seconds"),
            "data": sanitized,
        }

    def _start_background_refresh(self, key: str, ttl_seconds: int, fetcher: Callable[[], dict]) -> None:
        entry = self._entries.get(key)
        if entry is None or entry.is_refreshing:
            return
        refresh_generation = self._mark_refresh_started(entry)
        self._emit_cache_event(key, "market_cache_refresh_started", refresh_mode="background")
        future = self._executor.submit(self._refresh, key, ttl_seconds, fetcher, "background", refresh_generation)
        with self._global_lock:
            self._futures.add(future)
        future.add_done_callback(self._discard_future)

    def _refresh(
        self,
        key: str,
        ttl_seconds: int,
        fetcher: Callable[[], dict],
        refresh_mode: str = "background",
        refresh_generation: Optional[int] = None,
    ) -> None:
        lock = self._lock_for(key)
        started_at = time.monotonic()
        try:
            data = fetcher()
        except Exception as exc:
            with lock:
                entry = self._entries.get(key)
                if entry and self._is_current_refresh(entry, refresh_generation):
                    self._clear_refresh_state(entry)
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
            current = self._entries.get(key)
            if not current or not self._is_current_refresh(current, refresh_generation):
                logger.debug("[MarketCache] ignored superseded refresh key=%s", key)
                return
            new_entry = self._entry_from_data(key, data, ttl_seconds)
            new_entry.refresh_generation = current.refresh_generation
            self._entries[key] = new_entry
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
        should_mark_stale = is_stale or entry.expires_at <= self._now()
        if should_mark_stale:
            payload.setdefault("isStale", True)
        if entry.last_error:
            payload["lastError"] = entry.last_error
            payload["refreshError"] = entry.last_error
            payload["warning"] = payload.get("warning") or REFRESH_WARNING
        self._persist_remote_entry_best_effort(entry, is_stale=should_mark_stale)
        return payload

    def _persist_remote_entry_best_effort(self, entry: MarketCacheEntry, *, is_stale: bool = False) -> None:
        try:
            document = self.project_remote_entry(entry, is_stale=is_stale)
            self._remote_backend.persist(entry.key, document)
        except Exception as exc:
            logger.debug("[MarketCache] remote mirror skipped key=%s error=%s", entry.key, exc)

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

    def _mark_refresh_started(self, entry: MarketCacheEntry) -> int:
        entry.is_refreshing = True
        entry.refresh_started_at = time.monotonic()
        with self._global_lock:
            self._refresh_generation_counter += 1
            entry.refresh_generation = self._refresh_generation_counter
        return entry.refresh_generation

    @staticmethod
    def _clear_refresh_state(entry: MarketCacheEntry) -> None:
        entry.is_refreshing = False
        entry.refresh_started_at = None

    def _refresh_is_stale(self, entry: MarketCacheEntry) -> bool:
        if not entry.is_refreshing:
            return False
        if entry.refresh_started_at is None:
            return True
        return time.monotonic() - entry.refresh_started_at >= self._refresh_stale_after_seconds

    @staticmethod
    def _is_current_refresh(entry: MarketCacheEntry, refresh_generation: Optional[int]) -> bool:
        return refresh_generation is None or entry.refresh_generation == refresh_generation

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

    def _project_remote_value(self, value: Any, path: str = "root") -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [self._project_remote_value(item, f"{path}[{index}]") for index, item in enumerate(value)]
        if isinstance(value, dict):
            sanitized: dict[str, Any] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise TypeError(f"remote backend projection requires string keys at {path}")
                if key in REMOTE_RUNTIME_ONLY_FIELDS:
                    continue
                sanitized[key] = self._project_remote_value(item, f"{path}.{key}")
            return sanitized
        raise TypeError(f"remote backend projection requires JSON-safe values, got {type(value).__name__} at {path}")

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


def build_market_cache_from_config() -> MarketCache:
    """Build the module singleton from config while keeping direct MarketCache() local-only."""

    from src.config import get_config
    from src.services.market_cache_redis_backend import build_market_cache_remote_backend_from_config

    config = get_config()
    remote_backend = build_market_cache_remote_backend_from_config(config)
    return MarketCache(remote_backend=remote_backend)


_market_cache_singleton: Optional[MarketCache] = None
_market_cache_singleton_lock = threading.RLock()


def get_market_cache() -> MarketCache:
    """Return the lazily built module singleton."""

    global _market_cache_singleton
    with _market_cache_singleton_lock:
        if _market_cache_singleton is None:
            _market_cache_singleton = build_market_cache_from_config()
        return _market_cache_singleton


def reset_market_cache_for_tests() -> None:
    """Reset the lazy singleton for deterministic tests."""

    global _market_cache_singleton
    with _market_cache_singleton_lock:
        cache = _market_cache_singleton
        _market_cache_singleton = None
    if cache is None:
        return
    remote_backend = getattr(cache, "_remote_backend", None)
    shutdown = getattr(remote_backend, "shutdown", None)
    if callable(shutdown):
        shutdown(timeout=2)


class _MarketCacheProxy:
    """Compatibility proxy for consumers that import market_cache directly."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_market_cache(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(get_market_cache(), name, value)

    def __repr__(self) -> str:
        if _market_cache_singleton is None:
            return "<MarketCacheProxy lazy>"
        return repr(_market_cache_singleton)


market_cache = _MarketCacheProxy()
