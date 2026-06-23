# -*- coding: utf-8 -*-
"""Professional data capability registry service tests."""

from __future__ import annotations

import json

from src.services.professional_data_capability_registry_service import (
    PROFESSIONAL_DATA_CAPABILITY_CONTRACT_VERSION,
    build_professional_data_capability_registry,
)


ALLOWED_STATUSES = {
    "live",
    "degraded",
    "entitlement_required",
    "configured_missing",
    "not_implemented",
}

EXPECTED_CATEGORIES = {
    "options_structure",
    "market_breadth_flows",
    "sector_rotation",
    "macro_cross_asset_regime",
    "stock_research_data",
    "backtest_data_availability",
}

FORBIDDEN_CONSUMER_MARKERS = (
    "requiredProviderClass",
    "sourceAuthorityAllowed",
    "scoreContributionAllowed",
    "providerClass",
    "providerName",
    "providerAttempted",
    "sourceAuthorityRouter",
    "endpointHost",
    "apiKeyPresent",
    "exceptionClass",
    "exceptionChain",
    "requestId",
    "traceId",
    "cacheKey",
    "rawPayload",
    "raw_payload",
    "credential",
    "token",
    "env",
)


def test_professional_registry_returns_expected_categories_and_capabilities() -> None:
    payload = build_professional_data_capability_registry()

    assert payload["contractVersion"] == PROFESSIONAL_DATA_CAPABILITY_CONTRACT_VERSION
    assert payload["consumerSafe"] is True
    assert set(payload["categories"]) == EXPECTED_CATEGORIES

    capabilities = {
        item["capabilityId"]: item
        for item in payload["capabilities"]
    }
    assert {
        "options.chain",
        "options.greeks",
        "options.gex",
        "options.gamma_flip",
        "options.vanna_charm",
        "options.0dte",
        "market.breadth_flows",
        "market.sector_rotation",
        "macro.cross_asset_regime",
        "macro.volatility_liquidity_credit",
        "stock.fundamentals",
        "stock.technicals",
        "stock.news",
        "backtest.data_availability",
    } == set(capabilities)

    assert capabilities["options.chain"]["status"] == "entitlement_required"
    assert capabilities["options.greeks"]["status"] == "entitlement_required"
    assert capabilities["options.gex"]["status"] == "entitlement_required"
    assert capabilities["options.gamma_flip"]["status"] == "not_implemented"
    assert capabilities["options.vanna_charm"]["status"] == "not_implemented"
    assert capabilities["market.breadth_flows"]["status"] == "degraded"
    assert capabilities["market.sector_rotation"]["category"] == "sector_rotation"
    assert capabilities["stock.news"]["status"] == "configured_missing"
    assert capabilities["backtest.data_availability"]["status"] == "degraded"


def test_professional_registry_statuses_are_allowed_enum() -> None:
    payload = build_professional_data_capability_registry()

    statuses = {
        item["status"]
        for item in payload["capabilities"]
    }
    assert statuses <= ALLOWED_STATUSES
    assert payload["summary"]["totalCapabilities"] == len(payload["capabilities"])
    assert payload["summary"]["degradedCount"] > 0
    assert payload["summary"]["entitlementRequiredCount"] > 0
    assert payload["summary"]["configuredMissingCount"] > 0
    assert payload["summary"]["notImplementedCount"] > 0


def test_professional_registry_consumer_projection_redacts_internal_diagnostics() -> None:
    payload = build_professional_data_capability_registry()

    assert all("adminDiagnostics" not in item for item in payload["capabilities"])
    serialized = json.dumps(payload, ensure_ascii=False)
    lowered = serialized.lower()
    for marker in FORBIDDEN_CONSUMER_MARKERS:
        assert marker not in serialized
        assert marker.lower() not in lowered


def test_professional_registry_admin_projection_adds_bounded_diagnostics() -> None:
    payload = build_professional_data_capability_registry(
        include_admin_diagnostics=True
    )

    assert payload["consumerSafe"] is False
    assert all("adminDiagnostics" in item for item in payload["capabilities"])
    sample = payload["capabilities"][0]["adminDiagnostics"]
    assert set(sample) == {
        "sourceFamilyKey",
        "sourceFamilyLabel",
        "sourceReadinessState",
        "sourceAuthorityState",
        "sourceFreshnessState",
        "sourceEvidenceState",
        "nextEvidenceStep",
        "scoreUseAllowed",
        "staticRegistryOnly",
        "runtimeCalled",
        "networkCallsEnabled",
    }

    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for marker in (
        "apikeypresent",
        "endpointhost",
        "exceptionchain",
        "rawpayload",
        "raw_payload",
        "credential",
        "token",
    ):
        assert marker not in serialized
