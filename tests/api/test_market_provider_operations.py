# -*- coding: utf-8 -*-
"""Read-only market provider operations aggregation tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from api.v1.endpoints import market_provider_operations
import src.services.market_provider_operations_service as operations_service
from src.services.market_cache import market_cache
from src.services.market_overview_service import MarketOverviewService
from src.services.market_provider_operations_service import MarketProviderOperationsService
from src.storage import DatabaseManager


def _admin_user() -> CurrentUser:
    return CurrentUser(
        user_id="bootstrap-admin",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
    )


def _regular_user() -> CurrentUser:
    return CurrentUser(
        user_id="user-1",
        username="alice",
        display_name="Alice",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
    )


class _FakeLogService:
    def __init__(self, events: Optional[List[Dict[str, Any]]] = None) -> None:
        self.events = events or []

    def list_business_events(self, *, category: Optional[str] = None, **_: Any) -> Tuple[List[Dict[str, Any]], int]:
        items = [item for item in self.events if not category or item.get("category") == category]
        return items, len(items)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path):
    DatabaseManager.reset_instance()
    DatabaseManager(db_url=f"sqlite:///{tmp_path / 'market-provider-operations.sqlite'}")
    MarketProviderOperationsService.clear_summary_cache()
    market_cache.clear()
    MarketOverviewService._market_data_cache.clear()
    yield
    MarketProviderOperationsService.clear_summary_cache()
    market_cache.clear()
    MarketOverviewService._market_data_cache.clear()
    DatabaseManager.reset_instance()


def _service(events: Optional[List[Dict[str, Any]]] = None) -> MarketProviderOperationsService:
    return MarketProviderOperationsService(
        cache=market_cache,
        db=DatabaseManager.get_instance(),
        log_service=_FakeLogService(events),
    )


def test_endpoint_requires_admin_auth_consistent_with_admin_apis() -> None:
    app = FastAPI()
    app.include_router(market_provider_operations.router, prefix="/api/v1/admin")

    app.dependency_overrides[get_current_user] = _regular_user
    user_client = TestClient(app)
    user_response = user_client.get("/api/v1/admin/market-providers/operations")
    assert user_response.status_code == 403
    assert user_response.json()["detail"]["error"] == "admin_required"

    app.dependency_overrides[get_current_user] = _admin_user
    admin_client = TestClient(app)
    with patch("api.v1.endpoints.market_provider_operations.MarketProviderOperationsService", return_value=_service([])):
        admin_response = admin_client.get("/api/v1/admin/market-providers/operations")
    assert admin_response.status_code == 200
    assert admin_response.json()["metadata"]["readOnly"] is True


def test_aggregator_does_not_call_external_providers_or_cache_refresh() -> None:
    market_cache.set(
        "crypto",
        {
            "source": "binance",
            "sourceLabel": "Binance",
            "freshness": "live",
            "updatedAt": "2026-05-06T10:00:00+08:00",
            "items": [{"symbol": "BTCUSDT", "price": 65000}],
        },
        ttl_seconds=15,
    )

    with (
        patch.object(MarketOverviewService, "_fetch_crypto_market_snapshot", side_effect=AssertionError("provider called")),
        patch.object(market_cache, "get_or_refresh", side_effect=AssertionError("cache refresh called")),
    ):
        payload = _service([]).get_operations(window="24h")

    crypto = next(item for item in payload["items"] if item["cacheKey"] == "crypto")
    assert crypto["provider"] == "binance"
    assert payload["metadata"]["externalProviderCalls"] is False


def test_operations_summary_cache_reuses_projection_within_ttl() -> None:
    service = _service([])

    with (
        patch.object(service, "_read_cache_and_snapshots", wraps=service._read_cache_and_snapshots) as cache_reader,
        patch.object(service, "_read_market_events", wraps=service._read_market_events) as event_reader,
    ):
        first = service.get_operations(window="24h")
        second = service.get_operations(window="24h")

    assert cache_reader.call_count == 1
    assert event_reader.call_count == 1
    assert first["metadata"]["summaryCache"]["hit"] is False
    assert second["metadata"]["summaryCache"]["hit"] is True
    assert second["metadata"]["summaryCache"]["ttlSeconds"] == 10
    assert second["metadata"]["summaryCache"]["key"] == "GET:/api/v1/admin/market-providers/operations:v1:24h"
    assert second["metadata"]["summaryCache"]["cacheAgeMs"] >= 0


def test_operations_summary_cache_expiry_rebuilds_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = {"now": 1000.0}
    monkeypatch.setattr(operations_service.time, "monotonic", lambda: clock["now"])
    service = _service([])

    with patch.object(service, "_read_market_events", wraps=service._read_market_events) as event_reader:
        first = service.get_operations(window="24h")
        clock["now"] = 1005.0
        second = service.get_operations(window="24h")
        clock["now"] = 1011.0
        third = service.get_operations(window="24h")

    assert event_reader.call_count == 2
    assert first["metadata"]["summaryCache"]["hit"] is False
    assert second["metadata"]["summaryCache"]["hit"] is True
    assert second["metadata"]["summaryCache"]["cacheAgeMs"] == 5000
    assert third["metadata"]["summaryCache"]["hit"] is False


def test_cached_operations_summary_remains_sanitized_without_raw_payloads_or_secrets() -> None:
    market_cache.set(
        "rates",
        {
            "source": "yahoo",
            "freshness": "stale",
            "lastError": "provider failed token=SECRET api_key=ABC raw_payload={secret}",
            "warning": "Authorization: Bearer SECRET",
            "items": [{"raw_payload": "SECRET"}],
        },
        ttl_seconds=60,
    )
    service = _service([])

    service.get_operations(window="24h")
    cached = service.get_operations(window="24h")
    dumped = str(cached)

    assert cached["metadata"]["summaryCache"]["hit"] is True
    assert "SECRET" not in dumped
    assert "ABC" not in dumped
    assert "raw_payload" not in dumped


def test_cached_operations_summary_keeps_provider_failure_state_visible() -> None:
    events = [
        {
            "id": "failed-1",
            "event": "MarketProviderRefreshFailed",
            "eventType": "MarketProviderRefreshFailed",
            "category": "data_source",
            "status": "failed",
            "summary": "MarketProviderRefreshFailed",
            "endpoint": "/api/v1/market/sentiment",
            "provider": "cnn",
            "component": "MarketSentimentCard",
            "reason": "provider_error",
            "startedAt": "2026-05-06T10:10:00+08:00",
        },
    ]
    service = _service(events)

    first = service.get_operations(window="24h")
    service.log_service.events = []
    cached = service.get_operations(window="24h")

    assert first["summary"]["failureCount"] == 1
    assert cached["metadata"]["summaryCache"]["hit"] is True
    assert cached["summary"]["failureCount"] == 1
    assert cached["eventRollups"][0]["provider"] == "cnn"


def test_aggregator_does_not_mutate_market_cache() -> None:
    entry = market_cache.set(
        "indices",
        {
            "source": "yahoo",
            "freshness": "cached",
            "updatedAt": "2026-05-06T09:00:00+08:00",
            "items": [{"symbol": "SPX", "value": 5200}],
        },
        ttl_seconds=30,
    )
    before = {
        "keys": sorted(market_cache._entries.keys()),
        "data": dict(entry.data),
        "fetched_at": entry.fetched_at,
        "expires_at": entry.expires_at,
        "is_refreshing": entry.is_refreshing,
        "last_error": entry.last_error,
    }

    _service([]).get_operations(window="24h")
    after_entry = market_cache.get("indices")

    assert sorted(market_cache._entries.keys()) == before["keys"]
    assert after_entry is not None
    assert after_entry.data == before["data"]
    assert after_entry.fetched_at == before["fetched_at"]
    assert after_entry.expires_at == before["expires_at"]
    assert after_entry.is_refreshing == before["is_refreshing"]
    assert after_entry.last_error == before["last_error"]


def test_admin_logs_degraded_market_events_are_summarized() -> None:
    events = [
        {
            "id": "fallback-1",
            "event": "MarketDataFallbackUsed",
            "eventType": "MarketDataFallbackUsed",
            "category": "data_source",
            "status": "partial",
            "summary": "MarketDataFallbackUsed",
            "endpoint": "/api/v1/market/crypto",
            "provider": "binance",
            "component": "CryptoCard",
            "reason": "timeout",
            "startedAt": "2026-05-06T10:00:00+08:00",
        },
        {
            "id": "stale-1",
            "event": "MarketDataStaleServed",
            "eventType": "MarketDataStaleServed",
            "category": "market",
            "status": "success",
            "summary": "MarketDataStaleServed",
            "endpoint": "/api/v1/market/crypto",
            "provider": "binance",
            "component": "CryptoCard",
            "reason": "stale",
            "startedAt": "2026-05-06T10:05:00+08:00",
        },
        {
            "id": "failed-1",
            "event": "MarketProviderRefreshFailed",
            "eventType": "MarketProviderRefreshFailed",
            "category": "data_source",
            "status": "failed",
            "summary": "MarketProviderRefreshFailed",
            "endpoint": "/api/v1/market/sentiment",
            "provider": "cnn",
            "component": "MarketSentimentCard",
            "reason": "provider_error",
            "startedAt": "2026-05-06T10:10:00+08:00",
        },
    ]

    payload = _service(events).get_operations(window="24h")

    crypto = next(item for item in payload["eventRollups"] if item["provider"] == "binance")
    assert crypto["eventCount"] == 2
    assert crypto["fallbackCount"] == 1
    assert crypto["staleServedCount"] == 1
    cnn = next(item for item in payload["eventRollups"] if item["provider"] == "cnn")
    assert cnn["failureCount"] == 1
    assert payload["summary"]["eventCount"] == 3
    assert payload["summary"]["fallbackEventCount"] == 1
    assert payload["summary"]["staleEventCount"] == 1


def test_empty_no_log_state_returns_safe_empty_rollups() -> None:
    payload = _service([]).get_operations(window="24h")

    assert payload["eventRollups"] == []
    assert payload["summary"]["eventCount"] == 0
    assert "admin_logs_no_degraded_market_events_in_window" in payload["limitations"]


def test_response_sanitizes_raw_secrets_tokens_and_webhooks() -> None:
    entry = market_cache.set(
        "rates",
        {
            "source": "yahoo",
            "freshness": "stale",
            "lastError": "provider failed token=SECRET api_key=ABC webhook=https://hooks.example.test/raw",
            "warning": "Authorization: Bearer SECRET",
            "items": [],
        },
        ttl_seconds=60,
    )
    entry.last_error = "refresh failed password=SECRET token=SECRET"

    payload = _service([]).get_operations(window="24h")
    dumped = str(payload)

    assert "SECRET" not in dumped
    assert "ABC" not in dumped
    assert "hooks.example.test/raw" not in dumped
    rates = next(item for item in payload["items"] if item["cacheKey"] == "rates")
    assert "***" in (rates["errorSummary"] or "")


def test_admin_logs_drill_through_query_model_is_structured_and_safe() -> None:
    market_cache.set(
        "cn_indices",
        {
            "source": "sina",
            "freshness": "cached",
            "updatedAt": "2026-05-06T10:00:00+08:00",
            "items": [{"symbol": "000001.SH", "value": 3100}],
        },
        ttl_seconds=30,
    )

    payload = _service([]).get_operations(window="7d")
    item = next(item for item in payload["items"] if item["cacheKey"] == "cn_indices")
    drill = item["adminLogDrillThrough"]

    assert drill["route"] == "/zh/admin/logs"
    assert set(drill["query"]).issubset({"since", "category", "provider", "query"})
    assert drill["query"]["provider"] == "sina"
    assert drill["query"]["query"] == "/api/v1/market/cn-indices"
    assert "select" not in str(drill).lower()
    assert "token" not in str(drill).lower()


def test_all_admin_log_drill_through_links_remain_read_only_queries() -> None:
    events = [
        {
            "id": "failed-1",
            "event": "MarketProviderRefreshFailed",
            "eventType": "MarketProviderRefreshFailed",
            "category": "data_source",
            "status": "failed",
            "summary": "MarketProviderRefreshFailed",
            "endpoint": "/api/v1/market/sentiment",
            "provider": "cnn",
            "component": "MarketSentimentCard",
            "reason": "provider_error",
            "startedAt": "2026-05-06T10:10:00+08:00",
        },
    ]

    payload = _service(events).get_operations(window="24h")
    drills = [
        payload["adminLogDrillThrough"],
        payload["items"][0]["adminLogDrillThrough"],
        payload["eventRollups"][0]["adminLogDrillThrough"],
    ]

    for drill in drills:
        assert drill["route"] == "/zh/admin/logs"
        assert set(drill["query"]).issubset({"since", "category", "provider", "query"})
        assert "mode" not in drill["query"]
        assert "dryRun" not in drill["query"]
        assert "useRetention" not in drill["query"]
        assert "delete" not in str(drill).lower()
        assert "cleanup" not in str(drill).lower()

    assert payload["adminLogDrillThrough"]["query"] == {"since": "24h", "query": "market provider"}
    assert payload["eventRollups"][0]["adminLogDrillThrough"]["eventId"] == "failed-1"


def test_timeout_fallback_and_stale_cache_health_signals_stay_distinct_and_read_only() -> None:
    market_cache.set(
        "sentiment",
        {
            "source": "finnhub",
            "sourceLabel": "Finnhub",
            "freshness": "fallback",
            "fallbackUsed": True,
            "updatedAt": "2026-05-06T10:00:00+08:00",
            "warning": "Fallback served after timeout token=SECRET",
            "items": [{"symbol": "SPY", "score": 60}],
        },
        ttl_seconds=30,
    )
    DatabaseManager.get_instance().save_market_overview_snapshot(
        key="market_overview:rates",
        payload={
            "source": "yahoo",
            "sourceLabel": "Yahoo Finance",
            "freshness": "stale",
            "as_of": "2026-05-06T09:30:00+08:00",
            "updated_at": "2026-05-06T09:31:00+08:00",
            "items": [{"symbol": "US10Y", "value": 4.2}],
        },
    )
    events = [
        {
            "id": "fallback-timeout-1",
            "event": "MarketDataFallbackUsed",
            "eventType": "MarketDataFallbackUsed",
            "category": "data_source",
            "status": "partial",
            "summary": "MarketDataFallbackUsed",
            "endpoint": "/api/v1/market/sentiment",
            "provider": "finnhub",
            "component": "MarketSentimentCard",
            "reason": "timeout",
            "startedAt": "2026-05-06T10:01:00+08:00",
        },
    ]

    payload = _service(events).get_operations(window="24h")

    fallback_item = next(item for item in payload["items"] if item["cacheKey"] == "sentiment")
    stale_item = next(item for item in payload["items"] if item["cacheKey"] == "rates")
    rollup = next(item for item in payload["eventRollups"] if item["provider"] == "finnhub")

    assert payload["metadata"]["readOnly"] is True
    assert payload["metadata"]["externalProviderCalls"] is False
    assert payload["metadata"]["cacheMutation"] is False
    assert fallback_item["status"] == "fallback"
    assert fallback_item["fallbackUsed"] is True
    assert stale_item["status"] == "stale"
    assert stale_item["isFromSnapshot"] is True
    assert rollup["fallbackCount"] == 1
    assert rollup["topReasons"] == ["timeout"]
    assert "SECRET" not in str(payload)


def test_unavailable_cache_metadata_is_represented_honestly() -> None:
    payload = _service([]).get_operations(window="24h")

    crypto = next(item for item in payload["items"] if item["cacheKey"] == "crypto")
    crypto_cache = next(item for item in payload["cacheStates"] if item["cacheKey"] == "crypto")
    assert crypto["status"] == "unavailable"
    assert crypto_cache["status"] == "unavailable"
    assert "cache_metadata_unavailable:crypto" in payload["limitations"]


def test_persisted_snapshot_metadata_is_used_without_provider_fetch() -> None:
    DatabaseManager.get_instance().save_market_overview_snapshot(
        key="market_overview:indices",
        payload={
            "source": "yahoo",
            "sourceLabel": "Yahoo Finance",
            "freshness": "live",
            "asOf": "2026-05-06T09:30:00+08:00",
            "updatedAt": "2026-05-06T09:31:00+08:00",
            "items": [{"symbol": "SPX", "value": 5200}],
        },
    )

    with patch.object(MarketOverviewService, "_fetch_indices", side_effect=AssertionError("provider called")):
        payload = _service([]).get_operations(window="24h")

    indices = next(item for item in payload["items"] if item["cacheKey"] == "indices")
    cache_state = next(item for item in payload["cacheStates"] if item["cacheKey"] == "indices")
    assert indices["provider"] == "yahoo"
    assert indices["isFromSnapshot"] is True
    assert cache_state["persistentSnapshotAvailable"] is True


def test_tickflow_projection_reports_configured_key_before_runtime_entitlement_observation() -> None:
    with patch(
        "src.services.market_provider_operations_service.get_config",
        return_value=SimpleNamespace(tickflow_api_key="tf-secret"),
    ):
        payload = _service([]).get_operations(window="24h")

    projection = payload["metadata"]["providerDiagnostics"]["tickflowCnBreadth"]

    assert projection["status"] == "key_configured"
    assert projection["credentialState"] == "configured"
    assert projection["credentialConfigured"] is True
    assert projection["reachabilityState"] == "unknown"
    assert projection["tickflowReachable"] is None
    assert projection["breadthEntitlementState"] == "unknown"
    assert projection["breadthEntitlementUsable"] is None
    assert projection["reasonCode"] is None


def test_tickflow_projection_reports_reachable_and_breadth_entitlement_usable_from_cached_snapshot() -> None:
    market_cache.set(
        "cn_breadth",
        {
            "source": "tickflow",
            "sourceLabel": "TickFlow",
            "sourceType": "public_api",
            "freshness": "cached",
            "updatedAt": "2026-05-14T09:30:00+08:00",
            "asOf": "2026-05-14T09:30:00+08:00",
            "items": [{"symbol": "ADV_RATIO", "value": 66.6}],
        },
        ttl_seconds=60,
    )

    with patch(
        "src.services.market_provider_operations_service.get_config",
        return_value=SimpleNamespace(tickflow_api_key="tf-secret"),
    ):
        payload = _service([]).get_operations(window="24h")

    cn_breadth = next(item for item in payload["items"] if item["cacheKey"] == "cn_breadth")
    projection = payload["metadata"]["providerDiagnostics"]["tickflowCnBreadth"]

    assert cn_breadth["status"] == "cache"
    assert projection["status"] == "breadth_entitlement_usable"
    assert projection["credentialState"] == "configured"
    assert projection["reachabilityState"] == "reachable"
    assert projection["tickflowReachable"] is True
    assert projection["breadthEntitlementState"] == "usable"
    assert projection["breadthEntitlementUsable"] is True
    assert projection["reasonCode"] is None
    assert projection["observedSource"] == "tickflow"


@pytest.mark.parametrize(
    ("reason_code", "status", "reachability_state", "tickflow_reachable", "entitlement_state", "entitlement_usable"),
    [
        ("tickflow_not_configured", "key_missing", "unknown", None, "unknown", None),
        ("tickflow_permission_unavailable", "permission_denied", "reachable", True, "permission_denied", False),
        ("tickflow_timeout", "timeout", "timeout", False, "unknown", None),
        ("tickflow_market_stats_empty", "empty", "reachable", True, "empty", False),
        ("tickflow_market_stats_malformed", "malformed", "reachable", True, "malformed", False),
    ],
)
def test_tickflow_projection_distinguishes_entitlement_and_health_reason_codes(
    reason_code: str,
    status: str,
    reachability_state: str,
    tickflow_reachable: Optional[bool],
    entitlement_state: str,
    entitlement_usable: Optional[bool],
) -> None:
    market_cache.set(
        "cn_breadth",
        {
            "source": "fallback",
            "sourceLabel": "Fallback",
            "freshness": "fallback",
            "fallbackUsed": True,
            "fallbackReason": reason_code,
            "lastError": f"{reason_code} token=SECRET url=https://api.tickflow.test/raw",
            "items": [{"symbol": "ADV_RATIO", "value": 51.0}],
        },
        ttl_seconds=60,
    )

    configured_key = None if reason_code == "tickflow_not_configured" else "tf-secret"
    with patch(
        "src.services.market_provider_operations_service.get_config",
        return_value=SimpleNamespace(tickflow_api_key=configured_key),
    ):
        payload = _service([]).get_operations(window="24h")

    cn_breadth = next(item for item in payload["items"] if item["cacheKey"] == "cn_breadth")
    projection = payload["metadata"]["providerDiagnostics"]["tickflowCnBreadth"]

    assert cn_breadth["status"] == "error"
    assert cn_breadth["fallbackUsed"] is True
    assert projection["status"] == status
    assert projection["credentialState"] == ("missing" if reason_code == "tickflow_not_configured" else "configured")
    assert projection["reachabilityState"] == reachability_state
    assert projection["tickflowReachable"] is tickflow_reachable
    assert projection["breadthEntitlementState"] == entitlement_state
    assert projection["breadthEntitlementUsable"] is entitlement_usable
    assert projection["reasonCode"] == reason_code
    assert "SECRET" not in str(projection)
    assert "https://api.tickflow.test/raw" not in str(projection)
