# -*- coding: utf-8 -*-
"""Unit tests for market data cache stale-while-revalidate behavior."""

from __future__ import annotations

import inspect
import json
import threading
import time
import unittest
from concurrent.futures import Future
from datetime import timedelta
from unittest.mock import Mock

from src.services.market_cache import MarketCache, MarketCacheRemoteBackend, NullMarketCacheRemoteBackend
from src.services.llm_instrumentation import (
    reset_llm_event_counters,
    set_llm_event_sink,
    snapshot_llm_event_counters,
)


class _RemoteBackendUnavailable(RuntimeError):
    pass


class _FakeRemoteMarketCacheBackend(MarketCacheRemoteBackend):
    def __init__(self, *, fail_on_write: bool = False, delay_on_write_seconds: float = 0.0) -> None:
        self.fail_on_write = fail_on_write
        self.delay_on_write_seconds = delay_on_write_seconds
        self.documents: dict[str, dict] = {}
        self.read_calls = 0
        self.write_calls = 0

    def seed(self, key: str, document: dict) -> None:
        self.documents[key] = json.loads(json.dumps(document, ensure_ascii=False, sort_keys=True))

    def get(self, key: str) -> dict | None:
        self.read_calls += 1
        document = self.documents.get(key)
        if document is None:
            return None
        return json.loads(json.dumps(document, ensure_ascii=False, sort_keys=True))

    def persist(self, key: str, document: dict) -> None:
        self.write_calls += 1
        if self.delay_on_write_seconds > 0:
            time.sleep(self.delay_on_write_seconds)
        if self.fail_on_write:
            raise _RemoteBackendUnavailable("redis backend unavailable")
        self.documents[key] = json.loads(json.dumps(document, ensure_ascii=False, sort_keys=True))


class MarketCacheTestCase(unittest.TestCase):
    def setUp(self) -> None:
        reset_llm_event_counters()
        set_llm_event_sink(None)

    def tearDown(self) -> None:
        reset_llm_event_counters()
        set_llm_event_sink(None)

    def _event_counts(self) -> dict[str, int]:
        return {item["event"]: item["count"] for item in snapshot_llm_event_counters()}

    def _wait_until(self, predicate, timeout: float = 1.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.01)
        return bool(predicate())

    def test_fresh_cache_hit_does_not_call_fetcher(self) -> None:
        cache = MarketCache(max_workers=1)
        cache.set("crypto", {"source": "binance", "value": 1}, ttl_seconds=30)
        fetcher = Mock(return_value={"source": "binance", "value": 2})

        payload = cache.get_or_refresh("crypto", 30, fetcher)

        self.assertEqual(payload["value"], 1)
        fetcher.assert_not_called()
        self.assertEqual(self._event_counts().get("market_cache_hit"), 1)

    def test_cold_cache_fetches_and_stores_payload(self) -> None:
        cache = MarketCache(max_workers=1)
        fetcher = Mock(return_value={"source": "binance", "value": 2})

        payload = cache.get_or_refresh("crypto", 30, fetcher)

        self.assertEqual(payload["value"], 2)
        self.assertEqual(cache.get("crypto").data["value"], 2)
        fetcher.assert_called_once()
        counts = self._event_counts()
        self.assertEqual(counts.get("market_cache_miss"), 1)
        self.assertEqual(counts.get("market_cache_refresh_started"), 1)
        self.assertEqual(counts.get("market_cache_refresh_completed"), 1)

    def test_cold_cache_slow_fetcher_returns_fallback_and_refreshes_later(self) -> None:
        cache = MarketCache(max_workers=1)
        release_fetch = threading.Event()

        def fetcher() -> dict:
            release_fetch.wait(2)
            return {"source": "binance", "value": 2}

        start = time.monotonic()
        payload = cache.get_or_refresh(
            "crypto",
            30,
            fetcher,
            fallback_factory=lambda: {"source": "fallback", "value": 1, "freshness": "fallback", "isFallback": True},
            cold_start_timeout_seconds=0.05,
        )
        elapsed = time.monotonic() - start

        self.assertLess(elapsed, 0.5)
        self.assertEqual(payload["value"], 1)
        self.assertTrue(payload["isRefreshing"])
        release_fetch.set()
        self.assertTrue(cache.wait_for_refreshes(timeout=2))
        refreshed = cache.get_or_refresh(
            "crypto",
            30,
            Mock(side_effect=AssertionError("fresh cache should not fetch")),
        )
        self.assertEqual(refreshed["value"], 2)
        self.assertFalse(refreshed["isRefreshing"])
        counts = self._event_counts()
        self.assertEqual(counts.get("market_cache_miss"), 1)
        self.assertEqual(counts.get("market_cache_refresh_started"), 1)
        self.assertEqual(counts.get("market_cache_refresh_completed"), 1)
        self.assertEqual(counts.get("market_cache_cold_start_fallback_served"), 1)

    def test_cold_fallback_with_stuck_refresh_allows_retry_after_lease_expires(self) -> None:
        cache = MarketCache(max_workers=2, refresh_stale_after_seconds=0.02)
        first_started = threading.Event()
        release_first = threading.Event()
        retry_started = threading.Event()

        def stuck_fetcher() -> dict:
            first_started.set()
            release_first.wait(2)
            return {"source": "binance", "value": 99}

        def retry_fetcher() -> dict:
            retry_started.set()
            return {"source": "binance", "value": 2}

        try:
            fallback = cache.get_or_refresh(
                "crypto",
                30,
                stuck_fetcher,
                fallback_factory=lambda: {"source": "fallback", "value": 1, "freshness": "fallback", "isFallback": True},
                cold_start_timeout_seconds=0.01,
            )
            self.assertEqual(fallback["value"], 1)
            self.assertEqual(fallback["freshness"], "fallback")
            self.assertTrue(fallback["isRefreshing"])
            self.assertTrue(first_started.wait(1))
            time.sleep(0.03)

            retry_payload = cache.get_or_refresh(
                "crypto",
                30,
                retry_fetcher,
                fallback_factory=lambda: {"source": "fallback", "value": 1, "freshness": "fallback", "isFallback": True},
                cold_start_timeout_seconds=0.01,
            )

            self.assertEqual(retry_payload["value"], 1)
            self.assertEqual(retry_payload["freshness"], "fallback")
            self.assertTrue(retry_payload["isRefreshing"])
            self.assertTrue(retry_started.wait(1))
            self.assertTrue(self._wait_until(lambda: cache.get("crypto").data.get("value") == 2))
        finally:
            release_first.set()

        self.assertTrue(cache.wait_for_refreshes(timeout=2))
        self.assertEqual(cache.get("crypto").data["value"], 2)

    def test_concurrent_cold_request_returns_fallback_while_first_refreshes(self) -> None:
        cache = MarketCache(max_workers=1)
        release_fetch = threading.Event()

        def fetcher() -> dict:
            release_fetch.wait(2)
            return {"source": "binance", "value": 2}

        first_result = []
        first_thread = threading.Thread(target=lambda: first_result.append(cache.get_or_refresh(
            "crypto",
            30,
            fetcher,
            fallback_factory=lambda: {"source": "fallback", "value": 1, "freshness": "fallback", "isFallback": True},
            cold_start_timeout_seconds=0.05,
        )))
        first_thread.start()
        time.sleep(0.01)

        start = time.monotonic()
        second = cache.get_or_refresh(
            "crypto",
            30,
            fetcher,
            fallback_factory=lambda: {"source": "fallback", "value": 1, "freshness": "fallback", "isFallback": True},
            cold_start_timeout_seconds=0.05,
        )
        elapsed = time.monotonic() - start

        self.assertLess(elapsed, 0.5)
        self.assertEqual(second["value"], 1)
        self.assertTrue(second["isRefreshing"])
        release_fetch.set()
        first_thread.join(2)
        self.assertTrue(cache.wait_for_refreshes(timeout=2))
        refreshed = cache.get_or_refresh("crypto", 30, Mock(side_effect=AssertionError("fresh cache should not fetch")))
        self.assertEqual(refreshed["value"], 2)

    def test_expired_cache_returns_stale_payload_and_marks_refreshing(self) -> None:
        cache = MarketCache(max_workers=1)
        cache.set("crypto", {"source": "binance", "value": 1}, ttl_seconds=1)
        cache.get("crypto").expires_at = cache.get("crypto").fetched_at - timedelta(seconds=1)
        refresh_started = threading.Event()
        release_refresh = threading.Event()

        def fetcher() -> dict:
            refresh_started.set()
            release_refresh.wait(2)
            return {"source": "binance", "value": 2}

        payload = cache.get_or_refresh("crypto", 1, fetcher, allow_stale=True, background_refresh=True)

        self.assertEqual(payload["value"], 1)
        self.assertTrue(payload["isRefreshing"])
        self.assertEqual(self._event_counts().get("market_cache_stale_served"), 1)
        self.assertTrue(refresh_started.wait(1))
        release_refresh.set()
        self.assertTrue(cache.wait_for_refreshes(timeout=2))
        counts = self._event_counts()
        self.assertEqual(counts.get("market_cache_refresh_started"), 1)
        self.assertEqual(counts.get("market_cache_refresh_completed"), 1)

    def test_expired_cache_starts_only_one_background_refresh(self) -> None:
        cache = MarketCache(max_workers=2)
        cache.set("crypto", {"source": "binance", "value": 1}, ttl_seconds=1)
        cache.get("crypto").expires_at = cache.get("crypto").fetched_at - timedelta(seconds=1)
        release_refresh = threading.Event()
        calls = 0
        calls_lock = threading.Lock()

        def fetcher() -> dict:
            nonlocal calls
            with calls_lock:
                calls += 1
            release_refresh.wait(2)
            return {"source": "binance", "value": 2}

        payloads = [cache.get_or_refresh("crypto", 1, fetcher) for _ in range(5)]

        self.assertTrue(all(payload["isRefreshing"] for payload in payloads))
        release_refresh.set()
        self.assertTrue(cache.wait_for_refreshes(timeout=2))
        self.assertEqual(calls, 1)

    def test_stale_snapshot_returns_while_global_refresh_executor_is_saturated(self) -> None:
        cache = MarketCache(max_workers=1)
        cache.set("crypto", {"source": "binance", "value": 1}, ttl_seconds=1)
        cache.get("crypto").expires_at = cache.get("crypto").fetched_at - timedelta(seconds=1)
        cache.set("sentiment", {"source": "cnn", "value": 52}, ttl_seconds=1)
        cache.get("sentiment").expires_at = cache.get("sentiment").fetched_at - timedelta(seconds=1)
        release_hung_refresh = threading.Event()
        hung_started = threading.Event()
        unrelated_started = threading.Event()

        def hung_fetcher() -> dict:
            hung_started.set()
            release_hung_refresh.wait(2)
            return {"source": "binance", "value": 2}

        def unrelated_fetcher() -> dict:
            unrelated_started.set()
            return {"source": "cnn", "value": 60}

        try:
            crypto_payload = cache.get_or_refresh("crypto", 1, hung_fetcher, allow_stale=True, background_refresh=True)
            self.assertEqual(crypto_payload["value"], 1)
            self.assertTrue(crypto_payload["isRefreshing"])
            self.assertTrue(hung_started.wait(1))

            started = time.monotonic()
            sentiment_payload = cache.get_or_refresh(
                "sentiment",
                1,
                unrelated_fetcher,
                allow_stale=True,
                background_refresh=True,
            )
            elapsed = time.monotonic() - started

            self.assertLess(elapsed, 0.5)
            self.assertEqual(sentiment_payload["value"], 52)
            self.assertTrue(sentiment_payload["isStale"])
            self.assertTrue(sentiment_payload["isRefreshing"])
            self.assertFalse(unrelated_started.is_set())
        finally:
            release_hung_refresh.set()

        self.assertTrue(cache.wait_for_refreshes(timeout=2))
        self.assertTrue(unrelated_started.is_set())

    def test_background_refresh_failure_can_retry_on_next_stale_request(self) -> None:
        cache = MarketCache(max_workers=1)
        cache.set("rates", {"source": "fred", "value": 4.1}, ttl_seconds=1)
        cache.get("rates").expires_at = cache.get("rates").fetched_at - timedelta(seconds=1)

        failed_payload = cache.get_or_refresh(
            "rates",
            1,
            Mock(side_effect=RuntimeError("fred timeout")),
            allow_stale=True,
            background_refresh=True,
        )
        self.assertEqual(failed_payload["value"], 4.1)
        self.assertTrue(failed_payload["isRefreshing"])
        self.assertTrue(cache.wait_for_refreshes(timeout=2))
        self.assertFalse(cache.get("rates").is_refreshing)

        retry_started = threading.Event()

        def retry_fetcher() -> dict:
            retry_started.set()
            return {"source": "fred", "value": 4.2}

        retry_payload = cache.get_or_refresh(
            "rates",
            1,
            retry_fetcher,
            allow_stale=True,
            background_refresh=True,
        )

        self.assertEqual(retry_payload["value"], 4.1)
        self.assertEqual(retry_payload["warning"], "数据源刷新失败，当前显示最近快照")
        self.assertTrue(retry_started.wait(1))
        self.assertTrue(cache.wait_for_refreshes(timeout=2))
        self.assertEqual(cache.get("rates").data["value"], 4.2)

    def test_cold_fallback_under_worker_saturation_remains_fallback_not_live(self) -> None:
        cache = MarketCache(max_workers=1)
        cache.set("crypto", {"source": "binance", "value": 1}, ttl_seconds=1)
        cache.get("crypto").expires_at = cache.get("crypto").fetched_at - timedelta(seconds=1)
        release_hung_refresh = threading.Event()
        hung_started = threading.Event()
        queued_started = threading.Event()

        def hung_fetcher() -> dict:
            hung_started.set()
            release_hung_refresh.wait(2)
            return {"source": "binance", "value": 2}

        def queued_fetcher() -> dict:
            queued_started.set()
            return {"source": "sina", "value": 999, "freshness": "live"}

        try:
            cache.get_or_refresh("crypto", 1, hung_fetcher, allow_stale=True, background_refresh=True)
            self.assertTrue(hung_started.wait(1))

            payload = cache.get_or_refresh(
                "cn_indices",
                30,
                queued_fetcher,
                fallback_factory=lambda: {"source": "fallback", "value": 7, "freshness": "fallback", "isFallback": True},
                cold_start_timeout_seconds=0.01,
            )

            self.assertEqual(payload["value"], 7)
            self.assertEqual(payload["freshness"], "fallback")
            self.assertTrue(payload["isFallback"])
            self.assertNotEqual(payload["freshness"], "live")
            self.assertTrue(payload["isRefreshing"])
            self.assertFalse(queued_started.is_set())
        finally:
            release_hung_refresh.set()

        self.assertTrue(cache.wait_for_refreshes(timeout=2))

    def test_fetcher_failure_uses_fallback_without_changing_freshness(self) -> None:
        cache = MarketCache(max_workers=1)

        payload = cache.get_or_refresh(
            "cn_indices",
            30,
            Mock(side_effect=RuntimeError("provider down")),
            fallback_factory=lambda: {"source": "fallback", "freshness": "fallback", "isFallback": True},
        )

        self.assertEqual(payload["source"], "fallback")
        self.assertEqual(payload["freshness"], "fallback")
        self.assertTrue(payload["isFallback"])

    def test_background_refresh_failure_preserves_stale_payload_with_warning(self) -> None:
        cache = MarketCache(max_workers=1)
        cache.set("sentiment", {"source": "cnn", "value": 10}, ttl_seconds=1)
        entry = cache.get("sentiment")
        entry.expires_at = entry.fetched_at - timedelta(seconds=1)

        first_payload = cache.get_or_refresh(
            "sentiment",
            1,
            Mock(side_effect=RuntimeError("cnn unavailable")),
            allow_stale=True,
            background_refresh=True,
        )
        self.assertTrue(first_payload["isRefreshing"])
        self.assertTrue(cache.wait_for_refreshes(timeout=2))

        second_payload = cache.get_or_refresh(
            "sentiment",
            1,
            Mock(side_effect=RuntimeError("still down")),
            allow_stale=True,
            background_refresh=False,
        )

        self.assertEqual(second_payload["value"], 10)
        self.assertEqual(cache.get("sentiment").data["value"], 10)
        self.assertEqual(second_payload["warning"], "数据源刷新失败，当前显示最近快照")
        self.assertIn("cnn unavailable", second_payload["lastError"])
        counts = self._event_counts()
        self.assertEqual(counts.get("market_cache_stale_served"), 2)
        self.assertEqual(counts.get("market_cache_refresh_started"), 1)
        self.assertEqual(counts.get("market_cache_refresh_failed"), 1)

    def test_concurrent_cold_requests_only_call_fetcher_once(self) -> None:
        cache = MarketCache(max_workers=2)
        calls = 0
        calls_lock = threading.Lock()
        release_fetch = threading.Event()

        def fetcher() -> dict:
            nonlocal calls
            with calls_lock:
                calls += 1
            time.sleep(0.05)
            release_fetch.wait(2)
            return {"source": "binance", "value": 7}

        results = []
        threads = [
            threading.Thread(target=lambda: results.append(cache.get_or_refresh("crypto", 30, fetcher)))
            for _ in range(10)
        ]
        for thread in threads:
            thread.start()
        time.sleep(0.1)
        release_fetch.set()
        for thread in threads:
            thread.join(2)

        self.assertEqual(calls, 1)
        self.assertEqual(len(results), 10)
        self.assertTrue(all(payload["value"] == 7 for payload in results))

    def test_metric_sink_failure_is_swallowed(self) -> None:
        cache = MarketCache(max_workers=1)
        cache.set("crypto", {"source": "binance", "value": 1}, ttl_seconds=30)
        set_llm_event_sink(Mock(side_effect=RuntimeError("metric sink down")))

        payload = cache.get_or_refresh("crypto", 30, Mock(side_effect=AssertionError("fresh cache should not fetch")))

        self.assertEqual(payload["value"], 1)
        self.assertEqual(self._event_counts().get("market_cache_hit"), 1)

    def test_null_remote_backend_is_default_noop_adapter(self) -> None:
        cache = MarketCache(max_workers=1)

        self.assertIsInstance(cache._remote_backend, NullMarketCacheRemoteBackend)

    def test_market_cache_remote_seam_requires_no_redis_dependency_or_env_flag(self) -> None:
        import src.services.market_cache as market_cache_module

        source = inspect.getsource(market_cache_module)
        parameters = inspect.signature(MarketCache.__init__).parameters

        self.assertNotIn("import redis", source)
        self.assertNotIn("from redis", source)
        self.assertNotIn("import valkey", source)
        self.assertNotIn("from valkey", source)
        self.assertNotIn("os.getenv", source)
        self.assertEqual(
            tuple(parameters.keys()),
            ("self", "max_workers", "refresh_stale_after_seconds", "remote_backend"),
        )
        self.assertNotIn("redis_url", source.lower())
        self.assertNotIn("valkey_url", source.lower())

    def test_remote_projection_only_persists_json_safe_cache_contract(self) -> None:
        cache = MarketCache(max_workers=1)
        cache.set(
            "market_overview:indices",
            {
                "source": "mixed",
                "sourceLabel": "多来源",
                "freshness": "partial",
                "isFallback": False,
                "isStale": True,
                "isPartial": True,
                "isSynthetic": False,
                "asOf": "2026-05-28T09:30:00+08:00",
                "updatedAt": "2026-05-28T09:31:00+08:00",
                "providerHealth": {
                    "provider": "mixed",
                    "status": "refreshing",
                    "sourceLabel": "多来源",
                    "asOf": "2026-05-28T09:30:00+08:00",
                    "updatedAt": "2026-05-28T09:31:00+08:00",
                    "isFallback": False,
                    "isStale": True,
                    "isRefreshing": True,
                },
                "evidenceSnapshot": {
                    "contractVersion": "market_overview_evidence.v1",
                    "diagnosticOnly": True,
                    "scoreReliabilityAllowed": False,
                    "source": "mixed",
                    "sourceLabel": "多来源",
                    "freshness": "partial",
                    "isFallback": False,
                    "isStale": True,
                    "isPartial": True,
                    "isSynthetic": False,
                    "isRefreshing": True,
                    "asOf": "2026-05-28T09:30:00+08:00",
                    "updatedAt": "2026-05-28T09:31:00+08:00",
                    "providerHealth": {"status": "refreshing"},
                },
                "sourceConfidence": {
                    "freshness": "partial",
                    "source": "mixed",
                    "sourceLabel": "多来源",
                    "scoreReliabilityAllowed": False,
                    "isFallback": False,
                    "isStale": True,
                    "isPartial": True,
                    "asOf": "2026-05-28T09:30:00+08:00",
                    "updatedAt": "2026-05-28T09:31:00+08:00",
                },
            },
            ttl_seconds=30,
        )
        entry = cache.get("market_overview:indices")
        self.assertIsNotNone(entry)
        assert entry is not None
        entry.is_refreshing = True
        entry.last_error = "provider timeout"

        runtime_only = {
            "lock": cache._lock_for("market_overview:indices"),
            "future": Future(),
            "executor": cache._executor,
            "fetcher": Mock(return_value={"source": "live"}),
        }
        projected = cache.project_remote_entry(entry, is_stale=True)

        self.assertEqual(projected["key"], "market_overview:indices")
        self.assertEqual(projected["data"]["freshness"], "partial")
        self.assertTrue(projected["data"]["isStale"])
        self.assertTrue(projected["data"]["isPartial"])
        self.assertFalse(projected["data"]["isFallback"])
        self.assertFalse(projected["data"]["isSynthetic"])
        self.assertNotIn("isRefreshing", projected["data"])
        self.assertNotIn("lastError", projected["data"])
        self.assertNotIn("refreshError", projected["data"])
        self.assertEqual(projected["data"]["source"], "mixed")
        self.assertEqual(projected["data"]["sourceLabel"], "多来源")
        self.assertEqual(projected["data"]["asOf"], "2026-05-28T09:30:00+08:00")
        self.assertEqual(projected["data"]["updatedAt"], "2026-05-28T09:31:00+08:00")
        self.assertEqual(projected["data"]["providerHealth"]["status"], "refreshing")
        self.assertFalse(projected["data"]["evidenceSnapshot"]["scoreReliabilityAllowed"])
        self.assertEqual(projected["data"]["sourceConfidence"]["freshness"], "partial")
        self.assertTrue(all(name not in projected for name in runtime_only))

    def test_remote_projection_rejects_non_json_process_local_state(self) -> None:
        cache = MarketCache(max_workers=1)
        invalid_cases = {
            "callable": lambda: {"source": "binance"},
            "lock": cache._lock_for("crypto"),
            "future": Future(),
            "executor": cache._executor,
            "processLocal": object(),
        }

        for field_name, invalid_value in invalid_cases.items():
            with self.subTest(field_name=field_name):
                cache.set("crypto", {"source": "binance"}, ttl_seconds=30)
                entry = cache.get("crypto")
                self.assertIsNotNone(entry)
                assert entry is not None
                entry.data[field_name] = invalid_value
                with self.assertRaisesRegex(TypeError, "JSON-safe"):
                    cache.project_remote_entry(entry)

    def test_local_memory_cache_remains_authoritative_over_remote_backend(self) -> None:
        backend = _FakeRemoteMarketCacheBackend()
        cache = MarketCache(max_workers=1, remote_backend=backend)
        cache.set("crypto", {"source": "binance", "value": 1, "freshness": "live"}, ttl_seconds=30)
        backend.seed(
            "crypto",
            {
                "key": "crypto",
                "ttlSeconds": 30,
                "fetchedAt": "2026-05-29T09:30:00+08:00",
                "expiresAt": "2026-05-29T09:31:00+08:00",
                "data": {"source": "fallback", "value": 999, "freshness": "fallback", "isFallback": True},
            },
        )

        payload = cache.get_or_refresh(
            "crypto",
            30,
            Mock(side_effect=AssertionError("fresh local cache should stay authoritative")),
        )

        self.assertEqual(payload["source"], "binance")
        self.assertEqual(payload["value"], 1)
        self.assertEqual(payload["freshness"], "live")
        self.assertEqual(backend.read_calls, 0)
        self.assertEqual(backend.documents["crypto"]["data"]["source"], "binance")
        self.assertEqual(backend.documents["crypto"]["data"]["value"], 1)

    def test_remote_backend_failure_degrades_to_current_local_fallback_behavior(self) -> None:
        backend = _FakeRemoteMarketCacheBackend(fail_on_write=True)
        cache = MarketCache(max_workers=1, remote_backend=backend)

        payload = cache.get_or_refresh(
            "cn_indices",
            30,
            Mock(side_effect=RuntimeError("provider down")),
            fallback_factory=lambda: {"source": "fallback", "freshness": "fallback", "isFallback": True},
        )

        self.assertEqual(payload["source"], "fallback")
        self.assertEqual(payload["freshness"], "fallback")
        self.assertTrue(payload["isFallback"])
        self.assertEqual(cache.get("cn_indices").data["source"], "fallback")
        self.assertEqual(cache.get("cn_indices").data["freshness"], "fallback")
        self.assertEqual(backend.write_calls, 1)

    def test_slow_remote_backend_preserves_local_payload_semantics(self) -> None:
        control_cache = MarketCache(max_workers=1)
        backend = _FakeRemoteMarketCacheBackend(delay_on_write_seconds=0.01)
        remote_cache = MarketCache(max_workers=1, remote_backend=backend)
        seed_payload = {"source": "binance", "value": 7, "freshness": "live"}

        control_cache.set("crypto", seed_payload, ttl_seconds=30)
        remote_cache.set("crypto", seed_payload, ttl_seconds=30)

        expected = control_cache.get_or_refresh(
            "crypto",
            30,
            Mock(side_effect=AssertionError("fresh control cache should not fetch")),
        )
        actual = remote_cache.get_or_refresh(
            "crypto",
            30,
            Mock(side_effect=AssertionError("fresh remote-backed cache should not fetch")),
        )

        self.assertEqual(actual, expected)
        self.assertEqual(actual["source"], "binance")
        self.assertEqual(actual["value"], 7)
        self.assertEqual(actual["freshness"], "live")
        self.assertEqual(backend.read_calls, 0)
        self.assertGreaterEqual(backend.write_calls, 2)


if __name__ == "__main__":
    unittest.main()
