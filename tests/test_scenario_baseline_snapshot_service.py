# -*- coding: utf-8 -*-
"""Contract tests for the Scenario baseline snapshot service seam."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from src.services.scenario_baseline_snapshot_service import ScenarioBaselineSnapshotService


FORBIDDEN_PUBLIC_MARKERS = (
    "providerClass",
    "providerName",
    "apiKey",
    "env",
    "token",
    "credential",
    "requestId",
    "traceId",
    "cacheKey",
    "rawPayload",
    "exceptionClass",
    "exceptionChain",
)


def _assert_no_forbidden_marker(payload: object) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    lowered = text.lower()
    for marker in FORBIDDEN_PUBLIC_MARKERS:
        assert marker not in text
        assert marker.lower() not in lowered


def test_create_normalizes_baseline_snapshot_from_fixture_data() -> None:
    service = ScenarioBaselineSnapshotService()

    snapshot = service.create_snapshot(
        {
            "snapshotId": "baseline-us-open-20260615",
            "scope": {"type": "symbol", "value": " aapl "},
            "createdAt": "2026-06-15T09:30:00Z",
            "source": {
                "dataState": "real_cached",
                "freshness": "fresh",
                "asOf": "2026-06-15T09:30:00Z",
                "sourceAuthorityAllowed": True,
            },
            "categories": {
                "price": {"state": "available"},
                "volatility": {"state": "available"},
                "flowPositioning": {"state": "missing", "reason": "not_collected"},
                "optionsGreeks": {"state": "missing"},
                "marketRegime": {"state": "available"},
            },
            "labels": ["UAT baseline", "Open snapshot"],
            "notes": "Research baseline for scenario comparison.",
        }
    )

    assert snapshot["schemaVersion"] == "scenario_baseline_snapshot.v1"
    assert snapshot["status"] == "partial"
    assert snapshot["reasonCode"] == "baseline_partial"
    assert snapshot["snapshotId"] == "baseline-us-open-20260615"
    assert snapshot["scope"] == {"type": "symbol", "value": "AAPL"}
    assert snapshot["createdAt"] == "2026-06-15T09:30:00Z"
    assert snapshot["source"] == {
        "dataState": "real_cached",
        "freshness": "fresh",
        "asOf": "2026-06-15T09:30:00Z",
        "sourceAuthorityAllowed": True,
        "observationOnly": False,
    }
    assert snapshot["availableDataCategories"] == ["market_price", "market_regime", "volatility"]
    assert snapshot["missingDataCategories"] == ["market_flow", "options_greeks"]
    assert snapshot["degradedDataCategories"] == []
    assert snapshot["labels"] == ["UAT baseline", "Open snapshot"]
    assert snapshot["notes"] == "Research baseline for scenario comparison."
    assert snapshot["observationOnly"] is True
    assert snapshot["comparisonReady"] is False
    assert "baselinePrice" not in snapshot
    assert "volatilityValue" not in snapshot


def test_baseline_missing_state_is_deterministic_without_throwing() -> None:
    service = ScenarioBaselineSnapshotService()

    snapshot = service.get_latest_snapshot(scope={"type": "market", "value": "US"})

    assert snapshot["status"] == "not_available"
    assert snapshot["reasonCode"] == "baseline_missing"
    assert snapshot["snapshotId"] is None
    assert snapshot["scope"] == {"type": "market", "value": "US"}
    assert snapshot["availableDataCategories"] == []
    assert snapshot["missingDataCategories"] == [
        "market_price",
        "market_regime",
        "volatility",
        "market_flow",
        "options_greeks",
    ]
    assert snapshot["degradedDataCategories"] == []
    assert snapshot["comparisonReady"] is False
    assert snapshot["source"]["dataState"] == "unavailable"


def test_partial_snapshot_keeps_degraded_categories_explicit() -> None:
    service = ScenarioBaselineSnapshotService()

    snapshot = service.create_snapshot(
        {
            "snapshotId": "baseline-market-20260615",
            "scope": {"type": "market", "value": "US"},
            "createdAt": "2026-06-15T09:30:00Z",
            "source": {"dataState": "request_supplied", "freshness": "stale"},
            "availableDataCategories": ["marketPrice", "marketRegime"],
            "degradedDataCategories": ["volatility"],
            "missingDataCategories": ["flowPositioning", "optionsGreeks"],
        }
    )

    assert snapshot["status"] == "partial"
    assert snapshot["reasonCode"] == "baseline_partial"
    assert snapshot["source"]["observationOnly"] is True
    assert snapshot["availableDataCategories"] == ["market_price", "market_regime"]
    assert snapshot["degradedDataCategories"] == ["volatility"]
    assert snapshot["missingDataCategories"] == ["market_flow", "options_greeks"]
    assert snapshot["comparisonReady"] is False


def test_consumer_safe_response_redacts_internal_provider_and_runtime_markers() -> None:
    service = ScenarioBaselineSnapshotService()

    snapshot = service.create_snapshot(
        {
            "snapshotId": "baseline-redaction",
            "scope": {"type": "symbol", "value": "MSFT"},
            "createdAt": "2026-06-15T09:30:00Z",
            "source": {
                "providerClass": "InternalProvider",
                "providerName": "secret-provider",
                "apiKey": "secret",
                "env": "LOCAL_ENV",
                "token": "secret-token",
                "credential": "secret-credential",
                "requestId": "req-1",
                "traceId": "trace-1",
                "cacheKey": "cache-key",
                "rawPayload": {"price": 123.45},
                "exceptionClass": "ProviderError",
                "exceptionChain": ["boom"],
                "freshness": "fresh",
            },
            "categories": {"price": {"state": "available"}},
            "labels": ["providerName must not leak", "Consumer baseline"],
            "notes": "traceId req-1 providerClass rawPayload token must not leak.",
        }
    )

    _assert_no_forbidden_marker(snapshot)
    assert snapshot["labels"] == ["Consumer baseline"]
    assert snapshot["notes"] == "Baseline snapshot note omitted."
    assert set(snapshot["source"]) == {
        "dataState",
        "freshness",
        "asOf",
        "sourceAuthorityAllowed",
        "observationOnly",
    }


def test_service_module_does_not_import_network_or_provider_runtime_domains() -> None:
    source_path = Path(__file__).resolve().parents[1] / "src" / "services" / "scenario_baseline_snapshot_service.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    forbidden_prefixes = (
        "requests",
        "httpx",
        "urllib",
        "aiohttp",
        "data_provider",
        "src.providers",
        "src.services.options_market_data_provider",
        "src.services.market_cache",
        "api.deps",
        "src.auth",
    )
    assert not [
        module
        for module in imported_modules
        if module == "socket" or any(module == prefix or module.startswith(f"{prefix}.") for prefix in forbidden_prefixes)
    ]
