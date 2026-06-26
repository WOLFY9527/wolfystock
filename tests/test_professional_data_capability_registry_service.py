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
    assert payload["crossAssetDriverReadiness"]["contractVersion"] == "cross_asset_driver_readiness_v1"
    assert {
        "equities_index",
        "rates",
        "usd",
        "oil_energy",
        "gold",
        "volatility",
        "credit",
        "crypto",
        "sectors",
    } == {item["category"] for item in payload["crossAssetDriverReadiness"]["drivers"]}

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
        "macro.fred.rates",
        "macro.fred.inflation",
        "macro.fred.labor",
        "macro.fred.growth",
        "macro.fred.liquidity",
        "macro.fred.credit",
        "macro.fred.usd_currency",
        "macro.fred.recession",
        "macro.volatility_liquidity_credit",
        "stock.fundamentals",
        "stock.earnings_calendar",
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
    earnings_calendar = capabilities["stock.earnings_calendar"]
    assert earnings_calendar["status"] == "configured_missing"
    assert earnings_calendar["earningsCalendarReadiness"]["overallState"] == "not_configured"
    assert set(earnings_calendar["earningsCalendarReadiness"]["components"]) == {
        "nextEarningsDate",
        "lastReport",
        "epsEstimate",
        "reportedEps",
        "companyGuidance",
        "callTranscript",
        "eventFreshness",
    }
    assert all(
        component["state"] == "not_configured"
        for component in earnings_calendar["earningsCalendarReadiness"]["components"].values()
    )
    assert capabilities["macro.fred.rates"]["status"] == "configured_missing"
    assert capabilities["macro.fred.rates"]["category"] == "macro_cross_asset_regime"
    assert "no macro conclusion" in capabilities["macro.fred.rates"]["reason"]
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
    cross_asset_serialized = json.dumps(payload["crossAssetDriverReadiness"], ensure_ascii=False).lower()
    for marker in (
        "risk-on",
        "risk-off",
        "liquidity",
        "inflation",
        "recession",
        "rawpayload",
        "cachekey",
    ):
        assert marker not in cross_asset_serialized

    capabilities = {
        item["capabilityId"]: item
        for item in payload["capabilities"]
    }
    earnings_readiness = json.dumps(
        capabilities["stock.earnings_calendar"]["earningsCalendarReadiness"],
        ensure_ascii=False,
    )
    earnings_readiness_lowered = earnings_readiness.lower()
    for marker in (
        "2026-07-30",
        "epsestimatevalue",
        "reportedEpsValue",
        "guidanceSummary",
        "transcriptSummary",
        "buy",
        "sell",
        "recommendation",
        "target",
        "position",
    ):
        assert marker not in earnings_readiness
        assert marker.lower() not in earnings_readiness_lowered


def test_professional_registry_admin_projection_adds_bounded_diagnostics() -> None:
    payload = build_professional_data_capability_registry(
        include_admin_diagnostics=True
    )

    assert payload["consumerSafe"] is False
    assert payload["crossAssetDriverReadiness"]["consumerSafe"] is True
    assert payload["crossAssetDriverReadiness"]["networkCallsEnabled"] is False
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


def test_professional_registry_admin_projection_includes_macro_readiness_without_secret_values() -> None:
    payload = build_professional_data_capability_registry(
        include_admin_diagnostics=True,
        macro_env={"FRED_MACRO_PROVIDER_ENABLED": "true"},
    )

    macro_readiness = payload["macroReadiness"]
    assert macro_readiness["contractVersion"] == "macro_provider_readiness_v1"
    assert macro_readiness["provider"]["providerKey"] == "fred"
    assert macro_readiness["provider"]["state"] == "missing_env"
    assert macro_readiness["admin"]["requiredEnvVars"] == ["FRED_API_KEY"]
    assert macro_readiness["admin"]["requiredFlags"] == ["FRED_MACRO_PROVIDER_ENABLED"]

    macro_capability = next(
        item for item in payload["capabilities"]
        if item["capabilityId"] == "macro.fred.inflation"
    )
    assert macro_capability["adminDiagnostics"]["macroReadinessState"] == "missing_env"
    assert macro_capability["adminDiagnostics"]["nextAction"]

    serialized = json.dumps(payload, ensure_ascii=False)
    assert "FRED_API_KEY" in serialized
    assert "FRED_MACRO_PROVIDER_ENABLED" in serialized
    for marker in (
        "fred-secret",
        "apiKeyPresent",
        "endpointHost",
        "requestId",
        "traceId",
        "cacheKey",
        "rawPayload",
        "raw_payload",
        "token",
    ):
        assert marker not in serialized
