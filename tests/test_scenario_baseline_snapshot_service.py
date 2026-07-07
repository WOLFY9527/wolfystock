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


def test_volatility_authority_snapshot_controls_scenario_baseline_eligibility() -> None:
    service = ScenarioBaselineSnapshotService()

    official_snapshot = service.create_snapshot(
        {
            "snapshotId": "baseline-vix-official",
            "scope": {"type": "market", "value": "US"},
            "createdAt": "2026-07-06T20:05:00Z",
            "source": {
                "dataState": "real_cached",
                "freshness": "delayed",
                "asOf": "2026-07-06T20:00:00Z",
                "sourceAuthorityAllowed": True,
                "volatilityAuthoritySnapshot": {
                    "snapshotId": "volatility:VIX:fred:VIXCLS:2026-07-06T20:00:00Z",
                    "authorityState": "official",
                    "coverageState": "available",
                    "proxyFallback": False,
                    "consumerEligibility": {
                        "marketOverview": True,
                        "liquidity": True,
                        "scenarioBaseline": True,
                    },
                    "scoreEligibility": {
                        "allowed": False,
                        "reason": "volatility_snapshot_score_default_closed",
                    },
                },
            },
            "categories": {
                "price": {"state": "available"},
                "marketRegime": {"state": "available"},
                "volatility": {"state": "available"},
                "flowPositioning": {"state": "available"},
                "optionsGreeks": {"state": "available"},
            },
        }
    )
    proxy_snapshot = service.create_snapshot(
        {
            "snapshotId": "baseline-vix-proxy",
            "scope": {"type": "market", "value": "US"},
            "createdAt": "2026-07-06T20:05:00Z",
            "source": {
                "dataState": "real_cached",
                "freshness": "delayed",
                "asOf": "2026-07-06T20:00:00Z",
                "sourceAuthorityAllowed": True,
                "volatilityAuthoritySnapshot": {
                    "snapshotId": "volatility:VIX:yfinance:^VIX:2026-07-06T20:00:00Z",
                    "authorityState": "proxy",
                    "coverageState": "available",
                    "proxyFallback": True,
                    "consumerEligibility": {
                        "marketOverview": True,
                        "liquidity": False,
                        "scenarioBaseline": False,
                    },
                    "scoreEligibility": {
                        "allowed": False,
                        "reason": "unofficial_proxy_not_score_grade",
                    },
                },
            },
            "categories": {
                "price": {"state": "available"},
                "marketRegime": {"state": "available"},
                "volatility": {"state": "available"},
                "flowPositioning": {"state": "available"},
                "optionsGreeks": {"state": "available"},
            },
        }
    )

    assert official_snapshot["status"] == "available"
    assert official_snapshot["comparisonReady"] is True
    assert official_snapshot["source"]["volatilityAuthoritySnapshot"] == {
        "snapshotId": "volatility:VIX:fred:VIXCLS:2026-07-06T20:00:00Z",
        "authorityState": "official",
        "coverageState": "available",
        "proxyFallback": False,
        "consumerEligibility": {
            "marketOverview": True,
            "liquidity": True,
            "scenarioBaseline": True,
        },
        "scoreEligibility": {
            "allowed": False,
            "reason": "volatility_snapshot_score_default_closed",
        },
    }
    assert proxy_snapshot["status"] == "partial"
    assert proxy_snapshot["reasonCode"] == "baseline_partial"
    assert proxy_snapshot["source"]["observationOnly"] is True
    assert proxy_snapshot["comparisonReady"] is False
    assert proxy_snapshot["source"]["volatilityAuthoritySnapshot"]["authorityState"] == "proxy"


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


def _durable_ready_payload(*, snapshot_id: str = "baseline-durable-us-open") -> dict[str, Any]:
    return {
        "snapshotId": snapshot_id,
        "scope": {"type": "market", "value": "US"},
        "createdAt": "2026-07-07T09:31:00Z",
        "asOf": "2026-07-07T09:30:00Z",
        "source": {
            "dataState": "real_cached",
            "freshness": "fresh",
            "asOf": "2026-07-07T09:30:00Z",
            "sourceAuthorityAllowed": True,
        },
        "categories": {
            "price": {"state": "available"},
            "marketRegime": {"state": "available"},
            "volatility": {"state": "available"},
            "flowPositioning": {"state": "available"},
            "optionsGreeks": {"state": "available"},
        },
        "inputSnapshotRefs": ["market-overview:2026-07-07T09:30:00Z", "decision-cockpit:2026-07-07T09:30:00Z"],
        "sourceAuthoritySummary": {
            "state": "authoritative",
            "allowed": True,
            "reasonCodes": ["target_environment_evidence_present"],
        },
        "freshnessSummary": {
            "state": "fresh",
            "asOf": "2026-07-07T09:30:00Z",
        },
        "targetEnvironmentEvidence": {
            "state": "present",
            "evidenceRefs": ["uat-runtime:scenario-baseline"],
        },
    }


def test_explicit_durable_snapshot_creation_records_reproducibility_contract(tmp_path: Path) -> None:
    store_path = tmp_path / "scenario-baselines.jsonl"
    service = ScenarioBaselineSnapshotService(store_path=store_path)

    snapshot = service.create_durable_snapshot(_durable_ready_payload(), owner_id="user-a")

    assert store_path.exists()
    assert snapshot["snapshotId"] == "baseline-durable-us-open"
    assert snapshot["ownerScope"] == {"type": "user", "value": "user-a"}
    assert snapshot["createdAt"] == "2026-07-07T09:31:00Z"
    assert snapshot["asOf"] == "2026-07-07T09:30:00Z"
    assert snapshot["readinessState"] == "ready"
    assert snapshot["status"] == "available"
    assert snapshot["observationOnly"] is False
    assert snapshot["comparisonReady"] is True
    assert snapshot["inputSnapshotRefs"] == [
        "market-overview:2026-07-07T09:30:00Z",
        "decision-cockpit:2026-07-07T09:30:00Z",
    ]
    assert snapshot["sourceAuthoritySummary"] == {
        "state": "authoritative",
        "allowed": True,
        "reasonCodes": ["target_environment_evidence_present"],
    }
    assert snapshot["freshnessSummary"] == {
        "state": "fresh",
        "asOf": "2026-07-07T09:30:00Z",
    }
    assert snapshot["missingInputList"] == []
    assert snapshot["contentHash"].startswith("sha256:")
    assert snapshot["contentVersionRef"] == f"scenario_baseline_snapshot.v2:{snapshot['contentHash']}"

    reloaded = ScenarioBaselineSnapshotService(store_path=store_path)
    assert reloaded.get_durable_snapshot(snapshot["snapshotId"], owner_id="user-a") == snapshot
    assert reloaded.get_latest_durable_snapshot(scope={"type": "market", "value": "US"}, owner_id="user-a") == snapshot


def test_durable_readback_is_side_effect_free_when_snapshot_is_missing(tmp_path: Path) -> None:
    store_path = tmp_path / "scenario-baselines.jsonl"
    service = ScenarioBaselineSnapshotService(store_path=store_path)

    before_exists = store_path.exists()
    missing = service.get_latest_durable_snapshot(scope={"type": "market", "value": "US"}, owner_id="user-a")

    assert before_exists is False
    assert store_path.exists() is False
    assert missing["status"] == "not_available"
    assert missing["reasonCode"] == "baseline_missing"
    assert missing["readinessState"] == "not_available"
    assert missing["ownerScope"] == {"type": "user", "value": "user-a"}
    assert missing["contentHash"] is None
    assert missing["inputSnapshotRefs"] == []


def test_durable_snapshot_readback_is_owner_isolated(tmp_path: Path) -> None:
    service = ScenarioBaselineSnapshotService(store_path=tmp_path / "scenario-baselines.jsonl")
    snapshot = service.create_durable_snapshot(_durable_ready_payload(), owner_id="user-a")

    assert service.get_durable_snapshot(snapshot["snapshotId"], owner_id="user-b") is None
    missing_latest = service.get_latest_durable_snapshot(scope={"type": "market", "value": "US"}, owner_id="user-b")
    assert missing_latest["status"] == "not_available"
    assert missing_latest["ownerScope"] == {"type": "user", "value": "user-b"}


def test_durable_snapshot_rejects_same_id_with_different_content(tmp_path: Path) -> None:
    service = ScenarioBaselineSnapshotService(store_path=tmp_path / "scenario-baselines.jsonl")
    service.create_durable_snapshot(_durable_ready_payload(), owner_id="user-a")
    changed = _durable_ready_payload()
    changed["asOf"] = "2026-07-07T09:45:00Z"
    changed["source"]["asOf"] = "2026-07-07T09:45:00Z"

    try:
        service.create_durable_snapshot(changed, owner_id="user-a")
    except ValueError as exc:
        assert "immutable_snapshot_conflict" in str(exc)
    else:  # pragma: no cover - defensive assertion for the contract test
        raise AssertionError("expected immutable_snapshot_conflict")


def test_request_supplied_static_sample_or_stale_durable_baselines_remain_observation_only(tmp_path: Path) -> None:
    service = ScenarioBaselineSnapshotService(store_path=tmp_path / "scenario-baselines.jsonl")
    payload = _durable_ready_payload(snapshot_id="baseline-request-supplied")
    payload["source"] = {
        "dataState": "request_supplied",
        "freshness": "stale",
        "asOf": "2026-07-06T09:30:00Z",
        "sourceAuthorityAllowed": True,
    }
    payload["sourceAuthoritySummary"] = {"state": "observation_only", "allowed": False}
    payload["freshnessSummary"] = {"state": "stale", "asOf": "2026-07-06T09:30:00Z"}

    snapshot = service.create_durable_snapshot(payload, owner_id="user-a")

    assert snapshot["status"] == "partial"
    assert snapshot["readinessState"] == "observation_only"
    assert snapshot["source"]["dataState"] == "request_supplied"
    assert snapshot["source"]["freshness"] == "stale"
    assert snapshot["sourceAuthoritySummary"]["state"] == "observation_only"
    assert snapshot["freshnessSummary"]["state"] == "stale"
    assert snapshot["observationOnly"] is True
    assert snapshot["comparisonReady"] is False
