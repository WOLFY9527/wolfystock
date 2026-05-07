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
        assert payload["calls"][0]["multiplier"] == 100
        assert payload["calls"][0]["freshness"] == "synthetic_delayed"
        assert payload["calls"][0]["providerQuality"] == "synthetic_demo_only"
        assert payload["calls"][0]["dataQuality"]["tradeable"] is False
        assert payload["filtersApplied"]["forceRefresh"] is True
        assert payload["metadata"]["forceRefreshIgnored"] is True
        assert payload["metadata"]["providerName"] == "synthetic_fixture"
        assert payload["metadata"]["liveProviderEnabled"] is False
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


def test_chain_endpoint_rejects_live_provider_selection_without_live_calls() -> None:
    client = _client()
    try:
        response = client.get(
            "/api/v1/options/underlyings/TEM/chain",
            params={"marketDataProvider": "tradier"},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == {
            "error": "options_provider_disabled",
            "message": "Requested Options Lab provider is fixture-only, disabled, or not implemented.",
        }
    finally:
        client.close()


def test_live_provider_stub_selection_does_not_call_external_paths_or_expose_secrets() -> None:
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
                params={"marketDataProvider": "polygon"},
            )

        assert response.status_code == 400
        text = _json_text(response.json()).lower()
        assert "options_provider_disabled" in text
        for value in ("api_key", "apikey", "token", "secret", "requesturl", "env"):
            assert value not in text
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
            client.post(
                "/api/v1/options/analyze",
                json={
                    "symbol": "TEM",
                    "direction": "bullish",
                    "targetPrice": 65,
                    "targetDate": "2026-08-21",
                    "maxPremium": 600,
                    "riskProfile": "balanced",
                    "strategies": ["long_call"],
                    "forceRefresh": True,
                },
            ),
            client.post(
                "/api/v1/options/scenario",
                json={
                    "symbol": "TEM",
                    "strategy": "long_call",
                    "contractSymbol": "TEM260619C00055000",
                    "targetPrice": 65,
                    "forceRefresh": True,
                },
            ),
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
            "guaranteed profit",
            "best contract",
            "ai recommends you buy",
            "must buy",
            "must sell",
            "buy now",
            "sell now",
            "you should buy",
            "you should sell",
        ]
        for value in blocked:
            assert value not in text
    finally:
        client.close()


def test_analyze_endpoint_returns_ranked_call_candidates() -> None:
    client = _client()
    try:
        response = client.post(
            "/api/v1/options/analyze",
            json={
                "symbol": "TEM",
                "direction": "bullish",
                "targetPrice": 65,
                "targetDate": "2026-08-21",
                "riskProfile": "balanced",
                "strategies": ["long_call"],
                "forceRefresh": True,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["underlying"]["price"] == 52.4
        assert [item["contract"]["side"] for item in payload["candidateContracts"]] == ["call", "call", "call", "call"]
        assert payload["candidateContracts"][0]["score"] >= payload["candidateContracts"][-1]["score"]
        assert payload["metadata"]["forceRefreshIgnored"] is True
        assert payload["metadata"]["noExternalCalls"] is True
        assert payload["metadata"]["scoringEngine"] == "deterministic_fixture_scoring_v1"
    finally:
        client.close()


def test_analyze_endpoint_filters_max_premium_and_does_not_call_external_paths() -> None:
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
            response = client.post(
                "/api/v1/options/analyze",
                json={
                    "symbol": "TEM",
                    "direction": "bullish",
                    "targetPrice": 65,
                    "targetDate": "2026-06-19",
                    "maxPremium": 300,
                    "riskProfile": "balanced",
                    "strategies": ["long_call"],
                    "forceRefresh": True,
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert [item["contract"]["contractSymbol"] for item in payload["candidateContracts"]] == [
            "TEM260619C00055000",
            "TEM260619C00065000",
        ]
        assert all(item["premiumAtRisk"] <= 300 for item in payload["candidateContracts"])
    finally:
        client.close()


def test_scenario_endpoint_returns_expiration_payoff_grid() -> None:
    client = _client()
    try:
        response = client.post(
            "/api/v1/options/scenario",
            json={
                "symbol": "TEM",
                "strategy": "long_put",
                "contractSymbol": "TEM260619P00050000",
                "targetPrice": 45,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["contract"]["contractSymbol"] == "TEM260619P00050000"
        assert payload["risk"]["premiumAtRisk"] == 250
        assert payload["risk"]["breakeven"] == 47.5
        target = next(row for row in payload["expirationPayoffGrid"] if row["label"] == "custom_target")
        assert target["grossPayoff"] == 500
        assert target["netPayoff"] == 250
        assert payload["preExpirationTheoreticalPricing"]["available"] is False
        assert payload["metadata"]["noOrderPlacement"] is True
    finally:
        client.close()


def test_analyze_unsupported_symbol_returns_sanitized_error() -> None:
    client = _client()
    try:
        response = client.post(
            "/api/v1/options/analyze",
            json={"symbol": "HK00700", "direction": "bullish", "targetPrice": 65, "targetDate": "2026-08-21"},
        )
        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "unsupported_symbol_or_market"
        assert "HK00700" not in _json_text(response.json())
    finally:
        client.close()


def test_strategy_compare_endpoint_returns_defined_risk_structures() -> None:
    client = _client()
    try:
        response = client.post(
            "/api/v1/options/strategies/compare",
            json={
                "symbol": "TEM",
                "direction": "bullish",
                "targetPrice": 65,
                "targetDate": "2026-06-19",
                "riskProfile": "balanced",
                "strategies": ["long_call", "long_put", "bull_call_spread", "bear_put_spread"],
                "forceRefresh": True,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert [strategy["strategyType"] for strategy in payload["strategies"]] == [
            "long_call",
            "long_put",
            "bull_call_spread",
            "bear_put_spread",
        ]
        bull = next(strategy for strategy in payload["strategies"] if strategy["strategyType"] == "bull_call_spread")
        assert bull["netDebit"] == 230
        assert bull["maxLoss"] == 230
        assert bull["maxGain"] == 270
        assert bull["breakeven"] == 52.3
        assert bull["payoffAtTarget"] == 270
        assert payload["metadata"]["forceRefreshIgnored"] is True
        assert payload["metadata"]["noBrokerConnection"] is True
        assert payload["metadata"]["noPortfolioMutation"] is True
    finally:
        client.close()


def test_strategy_compare_endpoint_filters_max_premium_and_rejects_unsupported_strategy() -> None:
    client = _client()
    try:
        filtered = client.post(
            "/api/v1/options/strategies/compare",
            json={
                "symbol": "TEM",
                "direction": "neutral",
                "targetPrice": 52.4,
                "targetDate": "2026-06-19",
                "maxPremium": 150,
                "riskProfile": "conservative",
                "strategies": ["long_call", "long_put", "bull_call_spread", "bear_put_spread"],
            },
        )
        assert filtered.status_code == 200
        filtered_strategies = filtered.json()["strategies"]
        assert [strategy["strategyType"] for strategy in filtered_strategies] == [
            "long_call",
            "long_put",
            "bear_put_spread",
        ]
        assert all(strategy["netDebit"] <= 150 for strategy in filtered_strategies)

        unsupported = client.post(
            "/api/v1/options/strategies/compare",
            json={
                "symbol": "TEM",
                "direction": "bullish",
                "targetPrice": 65,
                "targetDate": "2026-06-19",
                "riskProfile": "balanced",
                "strategies": ["short_call"],
            },
        )
        assert unsupported.status_code == 400
        assert unsupported.json()["detail"] == {
            "error": "validation_error",
            "message": "Unsupported strategy requested for Options Lab Phase 4.",
        }
    finally:
        client.close()


def test_strategy_compare_endpoint_does_not_call_external_or_mutating_paths() -> None:
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
            response = client.post(
                "/api/v1/options/strategies/compare",
                json={
                    "symbol": "TEM",
                    "direction": "bullish",
                    "targetPrice": 65,
                    "targetDate": "2026-06-19",
                    "forceRefresh": True,
                },
            )

        assert response.status_code == 200
        text = _json_text(response.json()).lower()
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
            "guaranteed profit",
            "best contract",
            "ai recommends you buy",
            "must buy",
            "must sell",
            "buy now",
            "sell now",
            "you should buy",
            "you should sell",
            "trade ticket",
        ]
        for value in blocked:
            assert value not in text
    finally:
        client.close()


def test_decision_endpoint_returns_safe_demo_only_contract_quality() -> None:
    client = _client()
    try:
        response = client.post(
            "/api/v1/options/decision/evaluate",
            json={
                "symbol": "TEM",
                "strategy": "long_call",
                "expiration": "2026-06-19",
                "targetPrice": 65,
                "targetDate": "2026-06-19",
                "riskBudget": 600,
                "forceRefresh": True,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["dataQuality"]["dataQualityTier"] == "synthetic_demo_only"
        assert payload["decisionLabel"] == "数据不足，禁止判断"
        assert payload["tradeQualityScore"] <= 35
        assert payload["ivRankStatus"] == "available"
        assert payload["ivRank"] == 68.89
        assert payload["ivPercentile"] == 71.43
        assert payload["expectedMove"]["expectedMoveSource"] == "straddle_mid"
        assert payload["expectedMove"]["expectedMoveAbs"] == 7.5
        assert payload["optimizer"]["optimizerLabel"] == "数据不足，禁止判断"
        assert payload["optimizer"]["preferredStrategyKey"] is None
        assert payload["rankedAlternatives"]
        assert payload["metadata"]["noExternalCalls"] is True
        assert payload["metadata"]["noOrderPlacement"] is True
        assert "not personalized financial advice" in payload["noAdviceDisclosure"]
    finally:
        client.close()


def test_decision_endpoint_excludes_raw_payloads_and_live_provider_paths() -> None:
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
            response = client.post(
                "/api/v1/options/decision/evaluate",
                json={
                    "symbol": "TEM",
                    "strategy": "bull_call_spread",
                    "expiration": "2026-06-19",
                    "targetPrice": 65,
                    "targetDate": "2026-06-19",
                    "forceRefresh": True,
                },
            )

        assert response.status_code == 200
        text = _json_text(response.json()).lower()
        for value in [
            "rawproviderpayload",
            "api_key",
            "apikey",
            "token",
            "secret",
            "requesturl",
            "traceback",
            "stack trace",
            "必买",
            "稳赚",
            "保证收益",
            "guaranteed",
            "guaranteed profit",
            "best contract",
            "ai recommends you buy",
            "must buy",
            "must sell",
            "buy now",
            "sell now",
            "you should buy",
            "you should sell",
            "trade ticket",
        ]:
            assert value not in text
    finally:
        client.close()


def test_decision_endpoint_live_provider_unavailable_fails_closed_without_secret_leakage() -> None:
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
            response = client.post(
                "/api/v1/options/decision/evaluate",
                json={
                    "symbol": "TEM",
                    "marketDataProvider": "tradier",
                    "strategy": "bull_call_spread",
                    "expiration": "2026-06-19",
                    "targetPrice": 65,
                    "targetDate": "2026-06-19",
                    "riskBudget": 600,
                },
            )

        assert response.status_code == 400
        payload = response.json()
        assert payload["detail"]["error"] == "options_provider_disabled"
        text = _json_text(payload).lower()
        assert "live confidence" not in text
        for value in ("api_key", "apikey", "token", "secret", "requesturl", "traceback", "stack trace"):
            assert value not in text
    finally:
        client.close()


def test_decision_endpoint_delayed_fixture_keeps_tradeability_cap() -> None:
    client = _client()
    try:
        response = client.post(
            "/api/v1/options/decision/evaluate",
            json={
                "symbol": "TEM",
                "marketDataProvider": "delayed_fixture",
                "strategy": "bull_call_spread",
                "expiration": "2026-06-19",
                "targetPrice": 65,
                "targetDate": "2026-06-19",
                "riskBudget": 600,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["metadata"]["providerName"] == "delayed_fixture"
        assert payload["metadata"]["providerCapabilities"]["liveEnabled"] is False
        assert payload["dataQuality"]["dataQualityTier"] == "delayed_usable"
        assert payload["freshness"]["freshness"] == "delayed"
        assert payload["decisionLabel"] != "有条件可交易"
        assert all(item["decisionLabel"] != "有条件可交易" for item in payload["rankedAlternatives"])
    finally:
        client.close()
