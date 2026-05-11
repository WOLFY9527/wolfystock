# -*- coding: utf-8 -*-
"""Contract guards for provider runtime and MarketCache public boundaries."""

from __future__ import annotations

import json
import threading
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

import src.services.market_provider_operations_service as market_provider_operations_service_module
from src.services.analysis_provider_planner import (
    DataCategory,
    apply_research_budget_profile,
    build_analysis_provider_plan,
)
from src.services.market_cache import MarketCache
from src.services.market_provider_operations_service import (
    CN_TZ,
    MarketProviderOperationsService,
)
from src.services.provider_capability_matrix import get_provider_capability
from src.services.provider_plan_advisor import describe_provider_plan
from src.services.provider_usage_ledger import (
    ProviderUsageEvent,
    get_provider_usage_ledger,
)
from src.storage import DatabaseManager


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "provider_runtime"
PROVIDER_CAPABILITY_FIELDS = tuple(
    get_provider_capability("local_cache").__class__.__annotations__.keys()
)
FIXED_USAGE_TIMESTAMP = datetime(2026, 5, 11, 16, 0, tzinfo=timezone.utc)
FIXED_OPERATIONS_NOW = datetime(2026, 5, 12, 1, 0, tzinfo=CN_TZ)
FIXED_OPERATIONS_FETCHED_AT = datetime(2026, 5, 12, 0, 55, tzinfo=CN_TZ)
FORBIDDEN_FIXTURE_KEYS = {
    "authorization",
    "cookie",
    "api_key",
    "password",
    "request_body",
    "response_body",
    "raw_payload",
    "raw_response",
    "headers",
}
FORBIDDEN_FIXTURE_SUBSTRINGS = (
    "authorization:",
    "authorization=",
    "bearer ",
    "api_key",
    "set-cookie",
    "cookie=",
    "request_body",
    "response_body",
    "raw_payload",
    "raw_response",
    "traceback (most recent call last)",
)
NOT_LIVE_MARKERS = {
    "fallback",
    "stale",
    "mock",
    "synthetic",
    "fixture",
    "local_repaired",
    "synthetic_delayed",
}


def _load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def _normalize(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if hasattr(value, "value"):
        return getattr(value, "value")
    return value


def _provider_capability_payload(provider_id: str) -> dict[str, object]:
    capability = get_provider_capability(provider_id)
    assert capability is not None, f"unknown provider fixture id: {provider_id}"
    return {
        field: _normalize(getattr(capability, field))
        for field in PROVIDER_CAPABILITY_FIELDS
    }


def _usage_event_payload() -> dict[str, object]:
    event = ProviderUsageEvent(
        event_id="usage-budget-quick-1",
        timestamp=FIXED_USAGE_TIMESTAMP,
        research_mode="quick",
        symbol="orcl",
        market="us",
        analysis_context="analysis_provider_budget",
        category="news",
        provider="tavily",
        action="skipped_by_budget",
        outcome="skipped",
        reason_code="Authorization token=SECRET skipped_by_budget",
        budget_profile="quick",
        metadata={
            "safe": "visible",
            "notes": "optional budget skip",
            "api_key": "SECRET",
            "request_body": {"query": "ORCL"},
            "headers": {"Authorization": "Bearer SECRET"},
            "raw_payload": {"query": "ORCL"},
        },
    )
    return event.to_public_dict()


def _marketcache_boundary_payload() -> dict[str, object]:
    release_fetch = threading.Event()
    cold_cache = MarketCache(max_workers=1)

    def fetcher() -> dict[str, object]:
        release_fetch.wait(1)
        return {"source": "binance", "value": 2}

    cold_start_fallback_payload = cold_cache.get_or_refresh(
        "crypto",
        30,
        fetcher,
        fallback_factory=lambda: {
            "source": "fallback",
            "value": 1,
            "freshness": "fallback",
            "isFallback": True,
        },
        cold_start_timeout_seconds=0.01,
    )
    release_fetch.set()
    assert cold_cache.wait_for_refreshes(timeout=2)

    operations_cache = MarketCache(max_workers=1)
    operations_cache.set(
        "crypto",
        {
            "source": "fallback",
            "sourceLabel": "Fallback Snapshot",
            "freshness": "fallback",
            "updatedAt": "2026-05-06T10:00:00+08:00",
            "asOf": "2026-05-06T10:00:00+08:00",
            "isFallback": True,
            "fallbackUsed": True,
            "items": [
                {
                    "symbol": "BTCUSDT",
                    "price": 65000,
                    "freshness": "fallback",
                }
            ],
        },
        ttl_seconds=15,
    )
    entry = operations_cache.get("crypto")
    assert entry is not None
    entry.is_refreshing = True
    entry.last_error = (
        "provider timeout token=SECRET Authorization: Bearer abc "
        "raw_payload={secret}"
    )
    entry.fetched_at = FIXED_OPERATIONS_FETCHED_AT
    entry.expires_at = FIXED_OPERATIONS_FETCHED_AT + timedelta(seconds=15)

    service = MarketProviderOperationsService(
        cache=operations_cache,
        db=DatabaseManager.get_instance(),
    )
    with (
        patch.object(MarketProviderOperationsService, "_now", return_value=FIXED_OPERATIONS_NOW),
        patch.object(
            market_provider_operations_service_module.time,
            "monotonic",
            return_value=1000.0,
        ),
    ):
        operations = service.get_operations(window="24h")

    item = next(
        payload
        for payload in operations["items"]
        if payload["cacheKey"] == "crypto"
    )
    cache_state = next(
        payload
        for payload in operations["cacheStates"]
        if payload["cacheKey"] == "crypto"
    )
    return {
        "cold_start_fallback_payload": cold_start_fallback_payload,
        "operations_item": item,
        "cache_state": cache_state,
        "operations_metadata": operations["metadata"],
    }


def _assert_fixture_tree_is_sanitized(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized_key = str(key).strip().lower()
            assert normalized_key not in FORBIDDEN_FIXTURE_KEYS
            _assert_fixture_tree_is_sanitized(item)
        return
    if isinstance(value, list):
        for item in value:
            _assert_fixture_tree_is_sanitized(item)
        return
    if isinstance(value, str):
        lowered = value.lower()
        for forbidden in FORBIDDEN_FIXTURE_SUBSTRINGS:
            assert forbidden not in lowered


def _assert_not_live_when_degraded(value: object) -> None:
    if isinstance(value, Mapping):
        marker_values = []
        for field_name in ("freshness", "source", "provider", "status"):
            field_value = value.get(field_name)
            if isinstance(field_value, str):
                marker_values.append(field_value.lower())
        if (
            any(marker in NOT_LIVE_MARKERS for marker in marker_values)
            or bool(value.get("isFallback"))
            or bool(value.get("fallbackUsed"))
            or bool(value.get("isStale"))
        ):
            assert str(value.get("freshness") or "").lower() != "live"
            assert str(value.get("status") or "").lower() != "live"
        for item in value.values():
            _assert_not_live_when_degraded(item)
        return
    if isinstance(value, list):
        for item in value:
            _assert_not_live_when_degraded(item)


@pytest.fixture(autouse=True)
def _reset_provider_usage_ledger() -> None:
    get_provider_usage_ledger().clear_for_tests()
    yield
    get_provider_usage_ledger().clear_for_tests()


@pytest.fixture
def isolated_market_provider_db(tmp_path: Path) -> None:
    DatabaseManager.reset_instance()
    DatabaseManager(
        db_url=f"sqlite:///{tmp_path / 'provider-runtime-boundary.sqlite'}"
    )
    MarketProviderOperationsService.clear_summary_cache()
    yield
    MarketProviderOperationsService.clear_summary_cache()
    DatabaseManager.reset_instance()


def test_provider_capability_metadata_matches_boundary_fixture() -> None:
    fixture = _load_fixture("provider_capabilities_boundary.json")

    actual = {
        provider_id: _provider_capability_payload(provider_id)
        for provider_id in fixture
    }

    assert actual == fixture


def test_provider_budget_metadata_matches_boundary_fixture() -> None:
    fixture = _load_fixture("provider_budget_boundary.json")
    plan = build_analysis_provider_plan("AAPL", market="us")
    _, quick_budget = apply_research_budget_profile(
        plan,
        research_mode="quick",
        required_categories=[DataCategory.QUOTE],
    )
    actual = {
        "standard_news_advisory_plan": describe_provider_plan(
            "news",
            market="US",
            mode="standard",
        ),
        "scanner_news_advisory_plan": describe_provider_plan(
            "news",
            market="US",
            mode="scanner",
        ),
        "quick_budget_with_required_quote": _normalize(quick_budget),
    }

    assert actual == fixture
    assert actual["standard_news_advisory_plan"]["advisoryOnly"] is True
    assert actual["standard_news_advisory_plan"]["networkCallsEnabled"] is False
    assert actual["standard_news_advisory_plan"]["runtimeBehaviorChanged"] is False
    assert [
        candidate["providerId"]
        for candidate in actual["scanner_news_advisory_plan"]["candidates"]
    ] == ["local_cache", "local_news_cache"]
    assert all(
        candidate["liveProvider"] is False
        for candidate in actual["scanner_news_advisory_plan"]["candidates"]
    )
    assert "quote" not in actual["quick_budget_with_required_quote"][
        "budgetSkippedCategories"
    ]
    assert actual["quick_budget_with_required_quote"]["externalCallBudget"][
        "requiredCategoriesExcluded"
    ] == ["quote"]


def test_provider_usage_event_sanitization_matches_boundary_fixture() -> None:
    fixture = _load_fixture("provider_usage_event_boundary.json")
    actual = _usage_event_payload()

    assert actual == fixture
    dumped = json.dumps(actual, sort_keys=True).lower()
    assert "secret" not in dumped
    assert "authorization" not in dumped
    assert "api_key" not in dumped
    assert "raw_payload" not in dumped
    assert "request_body" not in dumped
    assert "headers" not in dumped


def test_marketcache_boundary_matches_fixture(
    isolated_market_provider_db: None,
) -> None:
    fixture = _load_fixture("marketcache_boundary.json")
    actual = _marketcache_boundary_payload()

    assert actual == fixture
    _assert_not_live_when_degraded(actual)
    assert actual["operations_metadata"]["externalProviderCalls"] is False
    assert actual["operations_metadata"]["cacheMutation"] is False
    assert actual["cache_state"]["ttlSeconds"] == 15
    assert actual["operations_item"]["isRefreshing"] is True


def test_provider_runtime_fixtures_are_sanitized() -> None:
    for fixture_path in sorted(FIXTURE_ROOT.glob("*.json")):
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        _assert_fixture_tree_is_sanitized(payload)

