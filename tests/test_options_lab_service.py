# -*- coding: utf-8 -*-
"""Options Lab fixture-backed service tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.services.options_lab_service import OptionsLabService, OptionsLabUnsupportedSymbol


FORBIDDEN_TERMS = [
    "rawProviderPayload",
    "api_key",
    "apikey",
    "token",
    "secret",
    "requestUrl",
    "provider.example",
    "必买",
    "稳赚",
    "guaranteed",
    "best contract",
    "AI recommends you buy",
    "buy now",
]


def _service() -> OptionsLabService:
    return OptionsLabService(fixture_path=Path("tests/fixtures/options/tem_chain.json"))


def _json_text(payload) -> str:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(by_alias=True)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def test_tem_summary_uses_synthetic_fixture_and_risk_metadata() -> None:
    summary = _service().get_summary("tem", force_refresh=True)

    assert summary.symbol == "TEM"
    assert summary.market == "us"
    assert summary.underlying["price"] == 52.4
    assert summary.options_availability["supported"] is True
    assert summary.options_availability["provider"] == "synthetic_fixture"
    assert summary.metadata.no_external_calls is True
    assert summary.metadata.no_order_placement is True
    assert summary.metadata.read_only is True
    assert summary.limitations.options_are_high_risk is True
    assert summary.limitations.long_options_can_lose_100_percent_premium is True
    assert summary.limitations.analytical_only_not_investment_advice is True


def test_tem_expirations_are_normalized_and_sorted() -> None:
    response = _service().get_expirations("TEM")

    assert [item.date for item in response.expirations] == ["2026-06-19", "2026-08-21"]
    assert response.expirations[0].dte == 44
    assert response.expirations[0].chain_available is True
    assert response.metadata.fixture_backed is True
    assert "synthetic_fixture_data" in response.expirations[0].warnings


def test_tem_chain_returns_calls_puts_and_safe_derived_fields() -> None:
    response = _service().get_chain("TEM", expiration="2026-06-19", side="both", include_greeks=True)

    assert response.symbol == "TEM"
    assert response.expiration == "2026-06-19"
    assert [contract.side for contract in response.calls] == ["call", "call", "call"]
    assert [contract.side for contract in response.puts] == ["put", "put"]
    assert response.calls[0].mid == 5.0
    assert response.calls[0].moneyness == "itm"
    assert response.calls[1].moneyness == "otm"
    assert response.calls[0].spread_pct == 8.0
    assert response.calls[2].liquidity_bucket == "thin"
    assert response.calls[0].greeks is not None
    assert response.limitations.no_order_placement is True


def test_chain_filters_side_expiration_liquidity_spread_and_greeks() -> None:
    response = _service().get_chain(
        "tem",
        expiration="2026-06-19",
        side="call",
        min_open_interest=100,
        max_spread_pct=20,
        include_greeks=False,
    )

    assert [contract.contract_symbol for contract in response.calls] == [
        "TEM260619C00050000",
        "TEM260619C00055000",
    ]
    assert response.puts == []
    assert all(contract.greeks is None for contract in response.calls)
    assert response.filters_applied["side"] == "call"
    assert response.filters_applied["minOpenInterest"] == 100
    assert response.filters_applied["maxSpreadPct"] == 20


def test_unsupported_symbol_and_market_are_rejected_without_provider_calls() -> None:
    with pytest.raises(OptionsLabUnsupportedSymbol) as exc_info:
        _service().get_chain("600519", force_refresh=True)

    assert exc_info.value.symbol == "600519"
    assert "unsupported_symbol_or_market" in exc_info.value.code


def test_force_refresh_does_not_call_providers_llm_or_market_cache() -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("forbidden external path was called")

    with (
        patch("data_provider.base.DataFetcherManager.get_realtime_quote", side_effect=forbidden),
        patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
        patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
    ):
        response = _service().get_chain("TEM", force_refresh=True)

    assert len(response.calls) > 0
    assert response.metadata.force_refresh_ignored is True


def test_responses_do_not_expose_raw_or_recommendation_fields() -> None:
    service = _service()
    payloads = [
        service.get_summary("TEM"),
        service.get_expirations("TEM"),
        service.get_chain("TEM", expiration="2026-06-19"),
        service.analyze(
            {
                "symbol": "TEM",
                "direction": "bullish",
                "targetPrice": 65,
                "targetDate": "2026-08-21",
                "maxPremium": 600,
                "riskProfile": "balanced",
                "strategies": ["long_call"],
                "forceRefresh": True,
            }
        ),
        service.scenario(
            {
                "symbol": "TEM",
                "strategy": "long_call",
                "contractSymbol": "TEM260619C00055000",
                "targetPrice": 65,
                "forceRefresh": True,
            }
        ),
    ]

    text = "\n".join(_json_text(payload) for payload in payloads).lower()
    for blocked in FORBIDDEN_TERMS:
        assert blocked.lower() not in text


def test_analyze_bullish_tem_returns_ranked_call_candidates() -> None:
    response = _service().analyze(
        {
            "symbol": "TEM",
            "direction": "bullish",
            "targetPrice": 65,
            "targetDate": "2026-08-21",
            "riskProfile": "balanced",
            "strategies": ["long_call"],
        }
    )

    assert response.symbol == "TEM"
    assert [candidate.contract.side for candidate in response.candidate_contracts] == ["call", "call", "call", "call"]
    scores = [candidate.score for candidate in response.candidate_contracts]
    assert scores == sorted(scores, reverse=True)
    assert response.candidate_contracts[0].strategy == "long_call"
    assert response.candidate_contracts[0].scoring.sub_scores.directional_fit == 100
    assert response.metadata.scoring_engine == "deterministic_fixture_scoring_v1"
    assert "phase4_spreads_deferred" in response.limitations


def test_analyze_bearish_tem_returns_ranked_put_candidates() -> None:
    response = _service().analyze(
        {
            "symbol": "TEM",
            "direction": "bearish",
            "targetPrice": 45,
            "targetDate": "2026-06-19",
            "riskProfile": "balanced",
            "strategies": ["long_put"],
        }
    )

    assert [candidate.contract.side for candidate in response.candidate_contracts] == ["put", "put", "put"]
    assert all(candidate.strategy == "long_put" for candidate in response.candidate_contracts)
    assert response.candidate_contracts[0].score >= response.candidate_contracts[-1].score


def test_analyze_max_premium_filters_expensive_contracts() -> None:
    response = _service().analyze(
        {
            "symbol": "TEM",
            "direction": "bullish",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
            "maxPremium": 300,
            "riskProfile": "balanced",
            "strategies": ["long_call"],
        }
    )

    assert [candidate.contract.contract_symbol for candidate in response.candidate_contracts] == [
        "TEM260619C00055000",
        "TEM260619C00065000",
    ]
    assert all(candidate.premium_at_risk <= 300 for candidate in response.candidate_contracts)


def test_analyze_penalizes_wide_spread_and_low_oi() -> None:
    response = _service().analyze(
        {
            "symbol": "TEM",
            "direction": "bullish",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
            "riskProfile": "balanced",
            "strategies": ["long_call"],
        }
    )

    thin = next(
        candidate
        for candidate in response.candidate_contracts
        if candidate.contract.contract_symbol == "TEM260619C00065000"
    )
    liquid = next(
        candidate
        for candidate in response.candidate_contracts
        if candidate.contract.contract_symbol == "TEM260619C00055000"
    )
    assert thin.scoring.sub_scores.liquidity_score < liquid.scoring.sub_scores.liquidity_score
    assert thin.scoring.sub_scores.oi_volume_confidence < liquid.scoring.sub_scores.oi_volume_confidence
    assert thin.scoring.sub_scores.spread_penalty < liquid.scoring.sub_scores.spread_penalty
    assert thin.score < liquid.score


def test_analyze_target_price_affects_score_ordering() -> None:
    lower_target = _service().analyze(
        {
            "symbol": "TEM",
            "direction": "bullish",
            "targetPrice": 55,
            "targetDate": "2026-06-19",
            "riskProfile": "balanced",
            "strategies": ["long_call"],
        }
    )
    higher_target = _service().analyze(
        {
            "symbol": "TEM",
            "direction": "bullish",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
            "riskProfile": "balanced",
            "strategies": ["long_call"],
        }
    )

    assert lower_target.candidate_contracts[0].contract.contract_symbol == "TEM260619C00050000"
    assert higher_target.candidate_contracts[0].contract.contract_symbol == "TEM260619C00055000"


def test_scenario_payoff_is_deterministic_at_expiration() -> None:
    response = _service().scenario(
        {
            "symbol": "TEM",
            "strategy": "long_call",
            "contractSymbol": "TEM260619C00055000",
            "targetPrice": 65,
        }
    )

    assert response.contract.contract_symbol == "TEM260619C00055000"
    assert response.expiration_payoff_grid[0].label == "down_20_pct"
    target = next(row for row in response.expiration_payoff_grid if row.label == "custom_target")
    assert target.underlying_price == 65
    assert target.gross_payoff == 1000
    assert target.net_payoff == 730
    assert response.risk.premium_at_risk == 270
    assert response.risk.breakeven == 57.7
    assert response.pre_expiration_theoretical_pricing["available"] is False


def test_analyze_force_refresh_does_not_call_external_paths() -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("forbidden external path was called")

    with (
        patch("data_provider.base.DataFetcherManager.get_realtime_quote", side_effect=forbidden),
        patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
        patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
    ):
        response = _service().analyze(
            {
                "symbol": "TEM",
                "direction": "bullish",
                "targetPrice": 65,
                "targetDate": "2026-08-21",
                "forceRefresh": True,
            }
        )

    assert response.metadata.force_refresh_ignored is True


def test_scenario_unsupported_symbol_uses_sanitized_error() -> None:
    with pytest.raises(OptionsLabUnsupportedSymbol) as exc_info:
        _service().scenario({"symbol": "HK00700", "strategy": "long_call"})

    assert exc_info.value.code == "unsupported_symbol_or_market"
