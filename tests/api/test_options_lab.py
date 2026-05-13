# -*- coding: utf-8 -*-
"""Options Lab API contract tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints import options
from api.v1.schemas.options import OptionsMetadata
from src.services.options_lab_domain_models import (
    BreakevenAssessment,
    DecisionAlternativeModel,
    DecisionDataQualityAssessment,
    DecisionEvaluationResult,
    DecisionFreshnessModel,
    ExpectedMoveEstimate,
    IvGreeksAssessment,
    LiquidityAssessment,
    OptimizerCandidate,
    OptimizerResult,
    RiskRewardAssessment,
)
from src.services.options_lab_service import OptionsLabService


SAFETY_BLOCKED_MARKERS = [
    "rawproviderpayload",
    "raw_provider_payload",
    "raw provider payload",
    "debugschema",
    "debug_schema",
    "rawschema",
    "raw_schema",
    "traceback",
    "stack trace",
    "api_key",
    "apikey",
    "api key",
    "token=",
    "password",
    "session=",
    "cookie",
    "authorization",
    "bearer",
    "provider.example",
    "provider credential",
    "credential payload",
    "必买",
    "稳赚",
    "保证收益",
    "下单",
    "立即买入",
    "立即卖出",
    "guaranteed",
    "guaranteed profit",
    "best contract",
    "ai recommends you buy",
    "must buy",
    "must sell",
    "buy now",
    "sell now",
    "trade-ready",
    "trade ready",
    "you should buy",
    "you should sell",
]


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(options.router, prefix="/api/v1/options")
    return TestClient(app)


def _json_text(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _assert_no_safety_leaks(payload) -> None:
    text = _json_text(payload).lower()
    for value in SAFETY_BLOCKED_MARKERS:
        assert value not in text


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


def test_chain_endpoint_matches_service_alias_contract() -> None:
    request_params = {
        "expiration": "2026-06-19",
        "side": "call",
        "minOpenInterest": 100,
        "maxSpreadPct": 20,
        "includeGreeks": "false",
        "forceRefresh": "true",
    }

    client = _client()
    try:
        response = client.get("/api/v1/options/underlyings/TEM/chain", params=request_params)
        assert response.status_code == 200

        expected_payload = OptionsLabService(
            fixture_path=Path("tests/fixtures/options/tem_chain.json")
        ).get_chain(
            "TEM",
            expiration="2026-06-19",
            side="call",
            min_open_interest=100,
            max_spread_pct=20,
            include_greeks=False,
            force_refresh=True,
        ).model_dump(by_alias=True)
        assert response.json() == expected_payload
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
        for value in ("api_key", "apikey", "token=", "secret", "requesturl", "env"):
            assert value not in text
    finally:
        client.close()


def test_options_launch_surfaces_reject_live_provider_selection_safely_without_mutations() -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("forbidden runtime path was called")

    requests = [
        ("get", "/api/v1/options/underlyings/TEM/summary", None, {"marketDataProvider": "tradier"}),
        ("get", "/api/v1/options/underlyings/TEM/expirations", None, {"marketDataProvider": "tradier"}),
        ("get", "/api/v1/options/underlyings/TEM/chain", None, {"marketDataProvider": "tradier"}),
        (
            "post",
            "/api/v1/options/analyze",
            {
                "symbol": "TEM",
                "marketDataProvider": "tradier",
                "direction": "bullish",
                "targetPrice": 65,
                "targetDate": "2026-06-19",
            },
            None,
        ),
        (
            "post",
            "/api/v1/options/scenario",
            {
                "symbol": "TEM",
                "marketDataProvider": "tradier",
                "strategy": "long_call",
                "contractSymbol": "TEM260619C00055000",
                "targetPrice": 65,
            },
            None,
        ),
        (
            "post",
            "/api/v1/options/strategies/compare",
            {
                "symbol": "TEM",
                "marketDataProvider": "tradier",
                "direction": "bullish",
                "targetPrice": 65,
                "targetDate": "2026-06-19",
                "riskProfile": "balanced",
            },
            None,
        ),
        (
            "post",
            "/api/v1/options/decision/evaluate",
            {
                "symbol": "TEM",
                "marketDataProvider": "tradier",
                "strategy": "bull_call_spread",
                "expiration": "2026-06-19",
                "targetPrice": 65,
                "targetDate": "2026-06-19",
            },
            None,
        ),
    ]

    client = _client()
    try:
        with (
            patch("data_provider.base.DataFetcherManager.get_realtime_quote", side_effect=forbidden),
            patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
            patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
            patch("src.services.portfolio_service.PortfolioService.add_lot", side_effect=forbidden, create=True),
        ):
            for method, path, json_payload, params in requests:
                response = (
                    client.get(path, params=params)
                    if method == "get"
                    else client.post(path, json=json_payload)
                )
                assert response.status_code == 400
                assert response.json()["detail"] == {
                    "error": "options_provider_disabled",
                    "message": "Requested Options Lab provider is fixture-only, disabled, or not implemented.",
                }
                _assert_no_safety_leaks(response.json())
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
        for value in SAFETY_BLOCKED_MARKERS:
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


def test_analyze_endpoint_matches_service_alias_contract() -> None:
    request_payload = {
        "symbol": "TEM",
        "direction": "bullish",
        "targetPrice": 65,
        "targetDate": "2026-08-21",
        "riskProfile": "balanced",
        "strategies": ["long_call"],
        "forceRefresh": True,
    }

    client = _client()
    try:
        response = client.post("/api/v1/options/analyze", json=request_payload)
        assert response.status_code == 200

        expected_payload = OptionsLabService(
            fixture_path=Path("tests/fixtures/options/tem_chain.json")
        ).analyze(request_payload).model_dump(by_alias=True)
        assert response.json() == expected_payload
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


def test_scenario_endpoint_matches_service_alias_contract() -> None:
    request_payload = {
        "symbol": "TEM",
        "strategy": "long_put",
        "contractSymbol": "TEM260619P00050000",
        "targetPrice": 45,
    }

    client = _client()
    try:
        response = client.post("/api/v1/options/scenario", json=request_payload)
        assert response.status_code == 200

        expected_payload = OptionsLabService(
            fixture_path=Path("tests/fixtures/options/tem_chain.json")
        ).scenario(request_payload).model_dump(by_alias=True)
        assert response.json() == expected_payload
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
        assert all(strategy["maxLoss"] is not None for strategy in payload["strategies"])
        assert all(strategy["breakeven"] is not None for strategy in payload["strategies"])
        assert all(strategy["noAdviceDisclosure"] for strategy in payload["strategies"])
        assert all(strategy["liquidityWarnings"] or strategy["ivThetaNotes"] or strategy["limitations"] for strategy in payload["strategies"])
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


def test_strategy_compare_endpoint_matches_service_alias_contract() -> None:
    request_payload = {
        "symbol": "TEM",
        "direction": "bullish",
        "targetPrice": 65,
        "targetDate": "2026-06-19",
        "riskProfile": "balanced",
        "strategies": ["long_call", "long_put", "bull_call_spread", "bear_put_spread"],
        "forceRefresh": True,
    }

    client = _client()
    try:
        response = client.post("/api/v1/options/strategies/compare", json=request_payload)
        assert response.status_code == 200

        expected_payload = OptionsLabService(
            fixture_path=Path("tests/fixtures/options/tem_chain.json")
        ).compare_strategies(request_payload).model_dump(by_alias=True)
        assert response.json() == expected_payload
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
        for value in SAFETY_BLOCKED_MARKERS + ["trade ticket"]:
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
        assert payload["gateDecision"] == "数据不足，禁止判断"
        assert payload["decisionGrade"] is False
        assert payload["dataQualityGates"]["status"] == "blocked"
        assert payload["liquidityGates"]["status"] in {"blocked", "manual_review"}
        assert payload["gateIssues"]
        assert payload["failClosedReasonCodes"]
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
        for value in SAFETY_BLOCKED_MARKERS + ["trade ticket"]:
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
        for value in ("api_key", "apikey", "token=", "secret", "requesturl", "traceback", "stack trace"):
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
        assert payload["decisionGrade"] is False
        assert payload["gateDecision"] in {"数据不足，禁止判断", "仅观察", "需人工复核"}
        assert all(item["decisionLabel"] != "有条件可交易" for item in payload["rankedAlternatives"])
    finally:
        client.close()


def test_decision_endpoint_matches_service_alias_contract() -> None:
    request_payload = {
        "symbol": "TEM",
        "strategy": "bull_call_spread",
        "expiration": "2026-06-19",
        "targetPrice": 65,
        "targetDate": "2026-06-19",
        "riskBudget": 600,
    }

    client = _client()
    try:
        response = client.post("/api/v1/options/decision/evaluate", json=request_payload)
        assert response.status_code == 200

        expected_result = OptionsLabService(
            fixture_path=Path("tests/fixtures/options/tem_chain.json")
        ).evaluate_decision(request_payload)
        expected_payload = options._map_decision_response(expected_result).model_dump(by_alias=True)
        actual_payload = response.json()

        assert actual_payload == expected_payload
        assert actual_payload["rankedAlternatives"] == actual_payload["optimizer"]["alternatives"]
    finally:
        client.close()


def test_decision_endpoint_no_trade_payload_matches_service_alias_contract(tmp_path: Path) -> None:
    fixture = json.loads(Path("tests/fixtures/options/tem_chain.json").read_text(encoding="utf-8"))
    for contract in fixture["contracts"]:
        contract["volume"] = 0
        contract["openInterest"] = 0
        contract["bid"] = 0.1
        contract["ask"] = 2.5
        contract["impliedVolatility"] = 1.4
    path = tmp_path / "tem_weak_candidates.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")

    weak_service = OptionsLabService(fixture_path=path)
    request_payload = {
        "symbol": "TEM",
        "strategy": "long_call",
        "expiration": "2026-06-19",
        "targetPrice": 52.5,
        "targetDate": "2026-06-19",
    }

    client = _client()
    try:
        with patch.object(options, "_service", return_value=weak_service):
            response = client.post("/api/v1/options/decision/evaluate", json=request_payload)

        assert response.status_code == 200
        expected_payload = options._map_decision_response(
            weak_service.evaluate_decision(request_payload)
        ).model_dump(by_alias=True)
        actual_payload = response.json()

        assert actual_payload == expected_payload
        assert set(actual_payload["optimizer"].keys()) == {
            "preferredStrategyKey",
            "optimizerLabel",
            "alternatives",
            "noTradeReason",
        }
        assert actual_payload["optimizer"]["preferredStrategyKey"] is None
        assert actual_payload["optimizer"]["noTradeReason"] is not None
        assert actual_payload["rankedAlternatives"] == actual_payload["optimizer"]["alternatives"]
    finally:
        client.close()


def test_decision_endpoint_mapper_preserves_existing_alias_shape() -> None:
    result = DecisionEvaluationResult(
        symbol="TEM",
        strategy="bull_call_spread",
        data_quality=DecisionDataQualityAssessment(
            data_quality_score=82.5,
            data_quality_tier="delayed_usable",
            source_type="delayed",
            as_of_age_minutes=18.5,
            blocking_reasons=["synthetic_or_fixture_data_not_decision_grade"],
            warnings=["missing_iv"],
        ),
        liquidity=LiquidityAssessment(
            liquidity_score=71.25,
            spread_pct=9.5,
            liquidity_warnings=["low_or_missing_volume"],
        ),
        iv_greeks=IvGreeksAssessment(
            iv_readiness=68.0,
            iv_rank_status="available",
            iv_rank=64.44,
            iv_percentile=71.43,
            iv_rank_source="synthetic_fixture_proxy",
            iv_rank_confidence="test_only_low_confidence",
            warnings=["missing_greeks"],
            dte_bucket="standard",
        ),
        expected_move=ExpectedMoveEstimate(
            expected_move_abs=7.5,
            expected_move_pct=14.31,
            expected_move_source="straddle_mid",
            expected_move_warnings=["expected_move_uses_fixture_mid_prices"],
        ),
        optimizer=OptimizerResult(
            preferred_strategy_key=None,
            optimizer_label="数据不足，禁止判断",
            alternatives=[
                OptimizerCandidate(
                    strategy_key="bull_call_spread",
                    data_quality_tier="delayed_usable",
                    liquidity_score=71.25,
                    breakeven_pressure=10.11,
                    max_loss=230,
                    max_gain=270,
                    risk_reward_ratio=1.17,
                    expected_move_alignment=58.0,
                    iv_readiness=68.0,
                    trade_quality_score=61.25,
                    decision_label="仅观察",
                    primary_reasons=["数据质量、流动性与风险回报需同时复核"],
                    risk_warnings=["expected_move_does_not_cover_breakeven_pressure"],
                )
            ],
            no_trade_reason="data_quality_not_decision_grade",
        ),
        breakeven=BreakevenAssessment(
            breakeven=57.7,
            required_move_pct=10.11,
            target_price_status="target_above_breakeven",
            score=74.0,
        ),
        risk_reward=RiskRewardAssessment(
            max_loss=230,
            max_gain=270,
            risk_reward_ratio=1.17,
            score=66.5,
            warnings=["max_gain_not_defined_for_long_option"],
        ),
        trade_quality_score=61.25,
        decision_label="仅观察",
        primary_reasons=["数据质量、流动性与风险回报需同时复核"],
        risk_warnings=["expected_move_does_not_cover_breakeven_pressure"],
        data_quality_gates={
            "status": "blocked",
            "issueCodes": ["synthetic_or_fixture_data_not_decision_grade"],
            "decisionGrade": False,
            "legDiagnostics": [],
        },
        liquidity_gates={
            "status": "manual_review",
            "issueCodes": ["low_or_missing_volume"],
            "decisionGrade": False,
            "legDiagnostics": [],
        },
        gate_decision="数据不足，禁止判断",
        gate_issues=[
            {
                "code": "synthetic_or_fixture_data_not_decision_grade",
                "category": "data_quality",
                "status": "blocked",
                "label": "Synthetic data is not decision grade",
                "decisionGrade": False,
                "legIndex": None,
                "contractSymbol": None,
            }
        ],
        decision_grade=False,
        fail_closed_reason_codes=["synthetic_or_fixture_data_not_decision_grade"],
        better_alternative=DecisionAlternativeModel(
            strategy_type="bull_call_spread",
            reason="定义风险结构或更低权利金暴露可能降低单合约风险",
            max_loss=230,
            risk_reward_ratio=1.17,
        ),
        no_advice_disclosure=(
            "Analytical output under explicit assumptions only; not personalized financial advice "
            "and not an instruction to trade."
        ),
        freshness=DecisionFreshnessModel(
            source="synthetic_fixture",
            freshness="synthetic_delayed",
            as_of="2026-05-06T16:00:00Z",
        ),
        metadata=OptionsMetadata(
            forceRefreshIgnored=True,
            scoringEngine="options_decision_engine_r2",
            strategyEngine="options_decision_engine_r2",
            providerName="synthetic_fixture",
            providerCapabilities={"liveEnabled": False},
            liveProviderEnabled=False,
        ),
    )

    payload = options._map_decision_response(result).model_dump(by_alias=True)

    assert payload["dataQuality"] == {
        "dataQualityScore": 82.5,
        "dataQualityTier": "delayed_usable",
        "sourceType": "delayed",
        "asOfAgeMinutes": 18.5,
        "blockingReasons": ["synthetic_or_fixture_data_not_decision_grade"],
        "warnings": ["missing_iv"],
    }
    assert payload["liquidity"] == {
        "liquidityScore": 71.25,
        "spreadPct": 9.5,
        "liquidityWarnings": ["low_or_missing_volume"],
    }
    assert payload["ivGreeks"] == {
        "ivReadiness": 68.0,
        "ivRankStatus": "available",
        "ivRank": 64.44,
        "ivPercentile": 71.43,
        "ivRankSource": "synthetic_fixture_proxy",
        "ivRankConfidence": "test_only_low_confidence",
        "warnings": ["missing_greeks"],
        "dteBucket": "standard",
    }
    assert payload["breakeven"] == {
        "breakeven": 57.7,
        "requiredMovePct": 10.11,
        "targetPriceStatus": "target_above_breakeven",
        "score": 74.0,
    }
    assert payload["riskReward"] == {
        "maxLoss": 230.0,
        "maxGain": 270.0,
        "riskRewardRatio": 1.17,
        "score": 66.5,
        "warnings": ["max_gain_not_defined_for_long_option"],
    }
    assert payload["expectedMove"] == {
        "expectedMoveAbs": 7.5,
        "expectedMovePct": 14.31,
        "expectedMoveSource": "straddle_mid",
        "expectedMoveWarnings": ["expected_move_uses_fixture_mid_prices"],
    }
    assert payload["betterAlternative"] == {
        "strategyType": "bull_call_spread",
        "reason": "定义风险结构或更低权利金暴露可能降低单合约风险",
        "maxLoss": 230.0,
        "riskRewardRatio": 1.17,
    }
    assert payload["optimizer"] == {
        "preferredStrategyKey": None,
        "optimizerLabel": "数据不足，禁止判断",
        "alternatives": [
            {
                "strategyKey": "bull_call_spread",
                "dataQualityTier": "delayed_usable",
                "liquidityScore": 71.25,
                "breakevenPressure": 10.11,
                "maxLoss": 230.0,
                "maxGain": 270.0,
                "riskRewardRatio": 1.17,
                "expectedMoveAlignment": 58.0,
                "ivReadiness": 68.0,
                "tradeQualityScore": 61.25,
                "decisionLabel": "仅观察",
                "primaryReasons": ["数据质量、流动性与风险回报需同时复核"],
                "riskWarnings": ["expected_move_does_not_cover_breakeven_pressure"],
            }
        ],
        "noTradeReason": "data_quality_not_decision_grade",
    }
    assert payload["rankedAlternatives"] == payload["optimizer"]["alternatives"]


def test_options_launch_source_does_not_import_broker_order_or_portfolio_mutation_paths() -> None:
    source_paths = [
        "api/v1/endpoints/options.py",
        "src/services/options_lab_service.py",
        "src/services/options_market_data_provider.py",
    ]
    forbidden_imports = [
        "from src.services.portfolio_service",
        "import portfolio_service",
        "from src.services.broker",
        "import broker",
        "from src.services.order",
        "import order_service",
    ]
    forbidden_calls = [
        ".add_lot(",
        ".place_order(",
        ".submit_order(",
        ".create_order(",
        ".execute_order(",
        ".mutate_portfolio(",
        ".sync_broker(",
    ]

    for path in source_paths:
        source = Path(path).read_text(encoding="utf-8")
        for marker in forbidden_imports + forbidden_calls:
            assert marker not in source
