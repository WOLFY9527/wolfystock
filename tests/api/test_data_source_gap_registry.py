# -*- coding: utf-8 -*-
"""API contract tests for the data source gap registry endpoint."""

from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints import market


EXPECTED_TOP_LEVEL_FIELDS = {
    "contractVersion",
    "diagnosticOnly",
    "providerRuntimeCalled",
    "networkCallsEnabled",
    "scoreAuthorityAllowed",
    "summary",
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
}


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
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

    families = {item["familyKey"]: item for item in payload["families"]}
    assert {
        "stock_quote_spine",
        "fundamentals",
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
    ):
        assert forbidden not in serialized
