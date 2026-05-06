# -*- coding: utf-8 -*-
"""Options Lab API contract tests."""

from __future__ import annotations

import json
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints import options


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(options.router, prefix="/api/v1/options")
    return TestClient(app)


def _json_text(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def test_summary_endpoint_returns_safe_normalized_fixture_response() -> None:
    client = _client()
    try:
        response = client.get("/api/v1/options/underlyings/tem/summary", params={"forceRefresh": "true"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["symbol"] == "TEM"
        assert payload["market"] == "us"
        assert payload["metadata"]["fixtureBacked"] is True
        assert payload["metadata"]["noExternalCalls"] is True
        assert payload["metadata"]["noOrderPlacement"] is True
        assert payload["limitations"]["optionsAreHighRisk"] is True
        assert payload["limitations"]["dataMayBeDelayedOrStale"] is True
    finally:
        client.close()


def test_expirations_endpoint_returns_fixture_expirations() -> None:
    client = _client()
    try:
        response = client.get("/api/v1/options/underlyings/TEM/expirations")
        assert response.status_code == 200
        payload = response.json()
        assert [item["date"] for item in payload["expirations"]] == ["2026-06-19", "2026-08-21"]
        assert payload["expirations"][0]["chainAvailable"] is True
    finally:
        client.close()


def test_chain_endpoint_filters_side_expiration_liquidity_and_spread() -> None:
    client = _client()
    try:
        response = client.get(
            "/api/v1/options/underlyings/TEM/chain",
            params={
                "expiration": "2026-06-19",
                "side": "call",
                "minOpenInterest": 100,
                "maxSpreadPct": 20,
                "includeGreeks": "false",
                "forceRefresh": "true",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert [item["contractSymbol"] for item in payload["calls"]] == [
            "TEM260619C00050000",
            "TEM260619C00055000",
        ]
        assert payload["puts"] == []
        assert all(item["greeks"] is None for item in payload["calls"])
        assert payload["filtersApplied"]["forceRefresh"] is True
        assert payload["metadata"]["forceRefreshIgnored"] is True
    finally:
        client.close()


def test_chain_endpoint_can_return_puts_only() -> None:
    client = _client()
    try:
        response = client.get(
            "/api/v1/options/underlyings/TEM/chain",
            params={"expiration": "2026-06-19", "side": "put"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["calls"] == []
        assert [item["side"] for item in payload["puts"]] == ["put", "put"]
    finally:
        client.close()


def test_unsupported_symbol_returns_sanitized_error() -> None:
    client = _client()
    try:
        response = client.get("/api/v1/options/underlyings/hk00700/chain")
        assert response.status_code == 404
        assert response.json()["detail"] == {
            "error": "unsupported_symbol_or_market",
            "message": "Options Lab Phase 1 supports fixture-backed US listed equity options only.",
        }
    finally:
        client.close()


def test_endpoint_does_not_call_live_provider_llm_market_cache_or_mutation_paths() -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("forbidden runtime path was called")

    client = _client()
    try:
        with (
            patch("data_provider.base.DataFetcherManager.get_realtime_quote", side_effect=forbidden),
            patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
            patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
            patch("src.services.portfolio_service.PortfolioService.add_lot", side_effect=forbidden, create=True),
        ):
            response = client.get(
                "/api/v1/options/underlyings/TEM/chain",
                params={"forceRefresh": "true"},
            )

        assert response.status_code == 200
        assert response.json()["metadata"]["noExternalCalls"] is True
    finally:
        client.close()


def test_endpoint_response_excludes_raw_provider_and_recommendation_language() -> None:
    client = _client()
    try:
        responses = [
            client.get("/api/v1/options/underlyings/TEM/summary"),
            client.get("/api/v1/options/underlyings/TEM/expirations"),
            client.get("/api/v1/options/underlyings/TEM/chain"),
        ]
        assert all(response.status_code == 200 for response in responses)
        text = "\n".join(_json_text(response.json()) for response in responses).lower()
        blocked = [
            "rawproviderpayload",
            "api_key",
            "apikey",
            "token",
            "secret",
            "requesturl",
            "必买",
            "稳赚",
            "guaranteed",
            "buy now",
        ]
        for value in blocked:
            assert value not in text
    finally:
        client.close()
