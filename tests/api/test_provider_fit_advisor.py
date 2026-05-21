# -*- coding: utf-8 -*-
"""API contract tests for the provider-fit advisor diagnostic endpoint."""

from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints import market


EXPECTED_PROVIDER_IDS = {
    "finnhub",
    "alpha_vantage",
    "twelve_data",
    "marketstack",
    "nasdaq_data_link",
    "sec_edgar",
    "pandas_datareader_fred",
    "pandas_datareader_oecd",
    "pandas_datareader_world_bank",
    "pandas_datareader_stooq",
    "yahooquery",
    "yfinance_current_baseline",
    "openbb_reference_only",
    "tushare_pro",
    "baostock",
    "efinance",
    "qstock",
    "ashare",
    "pytdx_existing_baseline",
    "akshare_existing_baseline",
    "binance_public",
    "coinbase_public",
    "fred_existing_baseline",
    "treasury_existing_baseline",
    "authorized.us_etf_flow",
    "authorized.cn_hk_connect_flow",
    "authorized.real_sector_theme_flow",
    "exchange_or_broker_authorized.index_futures",
    "official_or_authorized.us_market_breadth",
    "official_public.cn_money_market_rates",
    "official_public.fed_liquidity",
    "official_or_authorized.fx_dxy",
}
EXPECTED_ENTRY_FIELDS = {
    "providerName",
    "providerId",
    "providerCategory",
    "sourceTier",
    "trustLevel",
    "freshnessExpectation",
    "observationOnly",
    "scoreContributionAllowed",
    "paidDataLikelyRequired",
    "keyRequired",
    "enabledByDefault",
    "liveTestsAvoided",
    "cacheRequired",
    "backgroundRefreshRecommended",
    "networkCallExecuted",
    "noDefaultLiveHttpCalls",
    "bestUseCases",
    "rejectedFor",
    "notRecommendedFor",
    "missingProviderReason",
    "degradationReason",
    "adoptionStatus",
    "recommendedNextStep",
}
FORBIDDEN_ENTRY_FIELDS = {
    "quotes",
    "quote",
    "kline",
    "klines",
    "symbols",
    "score",
    "ranking",
    "rankings",
    "rawPayload",
    "providerPayload",
    "apiUrl",
    "token",
    "apiKey",
    "secret",
}


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    return TestClient(app)


def test_provider_fit_advisor_route_is_exposed() -> None:
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    routes = {
        (method, route.path)
        for route in app.routes
        if hasattr(route, "methods")
        for method in (route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    }

    assert ("GET", "/api/v1/market/provider-fit-advisor") in routes


def test_provider_fit_advisor_route_returns_metadata_only_snapshot() -> None:
    client = _client()

    try:
        response = client.get("/api/v1/market/provider-fit-advisor")

        assert response.status_code == 200
        payload = response.json()

        assert payload["advisoryOnly"] is True
        assert payload["runtimeBehaviorChanged"] is False
        assert payload["networkCallsEnabled"] is False

        entries = payload["entries"]
        assert isinstance(entries, list)
        assert {item["providerId"] for item in entries} == EXPECTED_PROVIDER_IDS
        assert [item["providerId"] for item in entries] == sorted(EXPECTED_PROVIDER_IDS)
        assert all(set(item) == EXPECTED_ENTRY_FIELDS for item in entries)
        assert all(not FORBIDDEN_ENTRY_FIELDS.intersection(item) for item in entries)

        assert all(item["observationOnly"] is True for item in entries)
        assert all(item["scoreContributionAllowed"] is False for item in entries)
        assert all(item["enabledByDefault"] is False for item in entries)
        assert all(item["networkCallExecuted"] is False for item in entries)
        assert all(item["noDefaultLiveHttpCalls"] is True for item in entries)

        openbb = next(item for item in entries if item["providerId"] == "openbb_reference_only")
        assert openbb["trustLevel"] == "reference_only"
        assert openbb["adoptionStatus"] == "reference_only"
        assert openbb["recommendedNextStep"] == "do_not_integrate_runtime"

        for provider_id in ("efinance", "qstock", "yahooquery", "yfinance_current_baseline"):
            entry = next(item for item in entries if item["providerId"] == provider_id)
            assert entry["trustLevel"] == "weak"
            assert entry["scoreContributionAllowed"] is False

        for provider_id in (
            "sec_edgar",
            "pandas_datareader_fred",
            "pandas_datareader_oecd",
            "pandas_datareader_world_bank",
            "binance_public",
            "coinbase_public",
        ):
            entry = next(item for item in entries if item["providerId"] == provider_id)
            assert entry["enabledByDefault"] is False
            assert entry["scoreContributionAllowed"] is False

        text = json.dumps(payload, ensure_ascii=False).lower()
        for marker in (
            "api_key",
            "token=",
            "secret",
            "password",
            "cookie",
            "session_id",
            "raw_payload",
            "provider_payload",
            "market quotes",
            "k-lines",
        ):
            assert marker not in text
    finally:
        client.close()
