# -*- coding: utf-8 -*-
"""API contract tests for the provider-fit advisor diagnostic endpoint."""

from __future__ import annotations

import json
from typing import Callable

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
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
    "options_lab.bid_ask_liquidity_gate",
    "options_lab.disabled_live_provider_stubs",
    "options_lab.iv_greeks_gate",
    "options_lab.iv_rank_history",
    "options_lab.oi_volume_gate",
    "options_lab.synthetic_fixture_chain",
    "portfolio.benchmark_return_history",
    "portfolio.factor_risk_metrics",
    "portfolio.fx_provenance",
    "portfolio.price_provenance",
    "portfolio.sector_industry_exposure",
    "watchlist.no_score_stale_state",
    "watchlist.scanner_score_snapshot",
    "watchlist.score_refresh_freshness",
    "watchlist.source_confidence_preservation",
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

def _provider_read_admin() -> CurrentUser:
    return CurrentUser(
        user_id="bootstrap-admin",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=("ops:providers:read",),
    )


def _admin_without_provider_read() -> CurrentUser:
    return CurrentUser(
        user_id="bootstrap-admin",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=("users:read",),
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


def _client_for(user_factory: Callable[[], CurrentUser]) -> TestClient:
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    app.dependency_overrides[get_current_user] = user_factory
    return TestClient(app)


def test_provider_fit_advisor_route_is_hidden_from_public_openapi() -> None:
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
    assert "/api/v1/market/provider-fit-advisor" not in app.openapi()["paths"]


def test_provider_fit_advisor_route_requires_admin_provider_read_capability() -> None:
    user_client = _client_for(_regular_user)
    user_response = user_client.get("/api/v1/market/provider-fit-advisor")
    assert user_response.status_code == 403
    assert user_response.json()["detail"]["error"] == "admin_required"

    no_capability_client = _client_for(_admin_without_provider_read)
    no_capability_response = no_capability_client.get("/api/v1/market/provider-fit-advisor")
    assert no_capability_response.status_code == 403
    assert no_capability_response.json()["detail"]["error"] == "admin_capability_required"
    assert "ops:providers:read" not in no_capability_response.text


def test_provider_fit_advisor_route_returns_metadata_only_snapshot_for_provider_admin() -> None:
    client = _client_for(_provider_read_admin)

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
