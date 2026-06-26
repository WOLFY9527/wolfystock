# -*- coding: utf-8 -*-
"""API contract tests for the data source gap registry endpoint."""

from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from api.v1.endpoints import market


EXPECTED_TOP_LEVEL_FIELDS = {
    "contractVersion",
    "diagnosticOnly",
    "providerRuntimeCalled",
    "networkCallsEnabled",
    "scoreAuthorityAllowed",
    "summary",
    "acquisitionPriorityQueue",
    "families",
    "metadata",
}
EXPECTED_FAMILY_FIELDS = {
    "familyKey",
    "consumerLabel",
    "status",
    "authorityState",
    "freshnessState",
    "entitlementOrLicensingBlocker",
    "integrationBlocker",
    "sourceEvidenceState",
    "nextIntegrationStep",
    "providerHydrationAllowed",
    "scoreTradingAuthorityAllowed",
    "consumerSafeDescription",
    "capabilityMap",
    "surfaceImpactMatrix",
    "integrationActionPlan",
}
EXPECTED_ACTION_FIELDS = {
    "actionKey",
    "actionLabel",
    "actionType",
    "priority",
    "status",
    "reason",
    "requiredEvidence",
    "blockedBy",
    "affectedSurfacesOrCapabilities",
    "nextConcreteStep",
    "requiresExternalProviderLicenseWork",
    "requiresProtectedDomainReview",
}
EXPECTED_QUEUE_FIELDS = {
    "familyKey",
    "familyLabel",
    "priority",
    "priorityReason",
    "readinessState",
    "primaryBlockerType",
    "affectedSurfaceCount",
    "blockedOrDegradedCapabilityCount",
    "externalEntitlementRequired",
    "protectedDomainReviewRequired",
    "nextConcreteStep",
    "requiredEvidence",
    "consumerSafeWarning",
}


def _admin_user() -> CurrentUser:
    return CurrentUser(
        user_id="admin-1",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=("ops:providers:read",),
    )


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    app.dependency_overrides[get_current_user] = _admin_user
    return TestClient(app)


def test_data_source_gap_registry_route_is_exposed() -> None:
    with _client() as client:
        response = client.get("/api/v1/market/data-source-gap-registry")

    assert response.status_code == 200
    assert response.json()["diagnosticOnly"] is True


def test_data_source_gap_registry_returns_static_fail_closed_family_inventory() -> None:
    with _client() as client:
        response = client.get("/api/v1/market/data-source-gap-registry")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == EXPECTED_TOP_LEVEL_FIELDS
    assert payload["contractVersion"] == "data_source_gap_registry_v1"
    assert payload["diagnosticOnly"] is True
    assert payload["providerRuntimeCalled"] is False
    assert payload["networkCallsEnabled"] is False
    assert payload["scoreAuthorityAllowed"] is False
    assert all(
        set(item) == EXPECTED_QUEUE_FIELDS
        for item in payload["acquisitionPriorityQueue"]
    )
    queue_by_key = {
        item["familyKey"]: item
        for item in payload["acquisitionPriorityQueue"]
    }

    families = {item["familyKey"]: item for item in payload["families"]}
    assert {
        "stock_quote_spine",
        "fundamentals",
        "news_catalyst_intelligence",
        "etf_index_coverage",
        "macro_rates",
        "fed_liquidity",
        "credit_stress",
        "vix_volatility",
        "breadth_flows_positioning",
        "options_chains",
        "options_strategy_analytics",
        "gamma_dealer_positioning",
        "backtest_dataset_lineage",
        "scenario_baselines",
        "portfolio_valuation_lineage",
    } == set(families)
    assert all(set(item) == EXPECTED_FAMILY_FIELDS for item in families.values())

    assert families["stock_quote_spine"]["status"] == "partial"
    assert families["stock_quote_spine"]["providerHydrationAllowed"] is True
    assert families["stock_quote_spine"]["scoreTradingAuthorityAllowed"] is False
    assert families["options_chains"]["status"] == "unauthorized"
    assert families["options_chains"]["authorityState"] == "unauthorized"
    assert families["options_chains"]["providerHydrationAllowed"] is False
    assert families["options_chains"]["scoreTradingAuthorityAllowed"] is False
    assert families["scenario_baselines"]["status"] == "planned"
    assert families["scenario_baselines"]["providerHydrationAllowed"] is False
    assert families["scenario_baselines"]["scoreTradingAuthorityAllowed"] is False
    assert families["portfolio_valuation_lineage"]["status"] == "partial"
    assert families["portfolio_valuation_lineage"]["providerHydrationAllowed"] is True
    assert families["portfolio_valuation_lineage"]["scoreTradingAuthorityAllowed"] is False
    assert families["news_catalyst_intelligence"]["status"] == "missing"
    assert families["news_catalyst_intelligence"]["authorityState"] == "not_configured"
    assert families["news_catalyst_intelligence"]["providerHydrationAllowed"] is False
    assert families["news_catalyst_intelligence"]["scoreTradingAuthorityAllowed"] is False
    assert {
        item["capabilityKey"]: item["state"]
        for item in families["news_catalyst_intelligence"]["capabilityMap"]
    } == {
        "stock_news": "not_configured",
        "market_news": "missing",
        "earnings_calendar": "missing",
        "macro_policy_catalyst": "stale",
        "company_developments": "not_configured",
    }
    assert set(queue_by_key) == set(families)
    assert queue_by_key["stock_quote_spine"]["priority"] == "critical"
    assert queue_by_key["stock_quote_spine"]["primaryBlockerType"] == (
        "provider-integration"
    )
    assert queue_by_key["stock_quote_spine"]["affectedSurfaceCount"] == 5
    assert queue_by_key["stock_quote_spine"]["blockedOrDegradedCapabilityCount"] == 4
    assert queue_by_key["stock_quote_spine"]["protectedDomainReviewRequired"] is True
    assert queue_by_key["portfolio_valuation_lineage"]["priority"] == "high"
    assert queue_by_key["news_catalyst_intelligence"]["readinessState"] == "missing"
    assert queue_by_key["news_catalyst_intelligence"]["primaryBlockerType"] == "schema-contract"
    assert (
        payload["acquisitionPriorityQueue"].index(
            queue_by_key["stock_quote_spine"]
        )
        < payload["acquisitionPriorityQueue"].index(
            queue_by_key["portfolio_valuation_lineage"]
        )
    )
    assert queue_by_key["scenario_baselines"]["primaryBlockerType"] == (
        "schema-contract"
    )
    assert all(
        family["integrationActionPlan"]
        for family in families.values()
    )
    assert all(
        set(action) == EXPECTED_ACTION_FIELDS
        for family in families.values()
        for action in family["integrationActionPlan"]
    )
    assert families["options_chains"]["integrationActionPlan"][0]["actionType"] == "provider-entitlement"
    assert families["options_chains"]["integrationActionPlan"][0]["status"] == "waiting-entitlement"
    assert families["options_chains"]["integrationActionPlan"][0]["requiresExternalProviderLicenseWork"] is True
    for family_key in (
        "options_chains",
        "options_strategy_analytics",
        "gamma_dealer_positioning",
    ):
        assert queue_by_key[family_key]["priority"] == "critical"
        assert queue_by_key[family_key]["primaryBlockerType"] == "entitlement"
        assert queue_by_key[family_key]["readinessState"] in {
            "blocked",
            "unauthorized",
        }
        assert queue_by_key[family_key]["externalEntitlementRequired"] is True
        assert queue_by_key[family_key]["protectedDomainReviewRequired"] is True
        assert "已就绪" not in queue_by_key[family_key]["priorityReason"]
        assert "ready" not in queue_by_key[family_key]["priorityReason"].lower()
    assert all(
        action["status"] != "ready-to-start"
        for family_key in (
            "options_chains",
            "options_strategy_analytics",
            "gamma_dealer_positioning",
        )
        for action in families[family_key]["integrationActionPlan"]
    )
    assert {
        action["actionType"]
        for action in families["stock_quote_spine"]["integrationActionPlan"]
    } >= {"provider-integration", "evidence-validation"}
    assert {
        action["actionType"]
        for action in families["portfolio_valuation_lineage"]["integrationActionPlan"]
    } >= {"provider-integration", "evidence-validation"}
    assert families["stock_quote_spine"]["surfaceImpactMatrix"][0] == {
        "surfaceKey": "scanner",
        "consumerLabel": "Scanner",
        "impactState": "degraded",
        "impactReason": "报价、日线和成交量血缘不统一，候选池只能保守解释缺口。",
        "affectedCapability": "候选发现、成交量过滤、空跑阻断桶",
        "nextEvidenceStep": "补齐有界报价和日线快照，并记录来源权限、时效和覆盖状态。",
    }
    assert {
        impact["surfaceKey"]: impact["impactState"]
        for impact in families["stock_quote_spine"]["surfaceImpactMatrix"]
    }["portfolio"] == "degraded"
    assert all(
        impact["impactState"] != "unlocked"
        for family_key in (
            "options_chains",
            "options_strategy_analytics",
            "gamma_dealer_positioning",
        )
        for impact in families[family_key]["surfaceImpactMatrix"]
    )
    assert {
        impact["surfaceKey"]: impact["impactState"]
        for impact in families["scenario_baselines"]["surfaceImpactMatrix"]
    }["scenario_lab"] == "planned"
    assert {
        impact["surfaceKey"]: impact["impactState"]
        for impact in families["news_catalyst_intelligence"]["surfaceImpactMatrix"]
    }["market_overview"] == "blocked"
    assert payload["summary"]["readyCount"] == 0
    assert payload["summary"]["scoreTradingAuthorityAllowedCount"] == 0

    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in (
        "providerid",
        "providername",
        "api_key",
        "access_token",
        "refresh_token",
        "cookie",
        "traceid",
        "requestid",
        "rawpayload",
        "alpaca",
        "yfinance",
        "polygon",
        "tushare",
        "akshare",
        "finnhub",
        "marketstack",
        "trading advice",
        "investment advice",
        "recommended",
        "winner",
        "fake headline",
        "breaking news",
        "latest news",
        "newswire",
    ):
        assert forbidden not in serialized
