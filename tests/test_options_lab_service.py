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
    "保证收益",
    "下单",
    "立即买入",
    "立即卖出",
    "guaranteed",
    "guaranteed profit",
    "best contract",
    "AI recommends you buy",
    "must buy",
    "must sell",
    "buy now",
    "sell now",
    "trade-ready",
    "trade ready",
    "you should buy",
    "you should sell",
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
    assert response.calls[0].multiplier == 100
    assert response.calls[0].moneyness == "itm"
    assert response.calls[1].moneyness == "otm"
    assert response.calls[0].spread_pct == 8.0
    assert response.calls[2].liquidity_bucket == "thin"
    assert response.calls[0].greeks is not None
    assert response.calls[0].freshness == "synthetic_delayed"
    assert response.calls[0].provider_quality == "synthetic_demo_only"
    assert response.calls[0].data_quality["tradeable"] is False
    assert response.limitations.no_order_placement is True
    assert response.metadata.provider_name == "synthetic_fixture"
    assert response.metadata.live_provider_enabled is False


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


def test_strategy_compare_returns_long_options_and_debit_spreads() -> None:
    response = _service().compare_strategies(
        {
            "symbol": "TEM",
            "direction": "bullish",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
            "riskProfile": "balanced",
            "strategies": ["long_call", "long_put", "bull_call_spread", "bear_put_spread"],
        }
    )

    assert [strategy.strategy_type for strategy in response.strategies] == [
        "long_call",
        "long_put",
        "bull_call_spread",
        "bear_put_spread",
    ]
    assert all(strategy.no_advice_disclosure for strategy in response.strategies)
    assert all(strategy.max_loss is not None for strategy in response.strategies)
    assert all(strategy.breakeven is not None for strategy in response.strategies)
    assert all(strategy.net_debit is not None for strategy in response.strategies)
    assert all(strategy.liquidity_warnings or strategy.iv_theta_notes or strategy.limitations for strategy in response.strategies)
    assert response.metadata.strategy_engine == "defined_risk_strategy_compare_v1"


def test_bull_call_spread_math_is_deterministic() -> None:
    response = _service().compare_strategies(
        {
            "symbol": "TEM",
            "direction": "bullish",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
            "riskProfile": "balanced",
            "strategies": ["bull_call_spread"],
        }
    )

    spread = response.strategies[0]
    assert [(leg.action, leg.side, leg.strike) for leg in spread.legs] == [
        ("buy", "call", 50.0),
        ("sell", "call", 55.0),
    ]
    assert spread.net_debit == 230
    assert spread.max_loss == 230
    assert spread.max_gain == 270
    assert spread.breakeven == 52.3
    assert spread.payoff_at_target == 270
    assert spread.risk_reward_ratio == 1.17


def test_bear_put_spread_math_and_target_payoff_are_deterministic() -> None:
    response = _service().compare_strategies(
        {
            "symbol": "TEM",
            "direction": "bearish",
            "targetPrice": 45,
            "targetDate": "2026-06-19",
            "riskProfile": "balanced",
            "strategies": ["bear_put_spread"],
        }
    )

    spread = response.strategies[0]
    assert [(leg.action, leg.side, leg.strike) for leg in spread.legs] == [
        ("buy", "put", 50.0),
        ("sell", "put", 45.0),
    ]
    assert spread.net_debit == 130
    assert spread.max_loss == 130
    assert spread.max_gain == 370
    assert spread.breakeven == 48.7
    assert spread.payoff_at_target == 370
    assert spread.risk_reward_ratio == 2.85


def test_strategy_compare_max_premium_filters_net_debit() -> None:
    response = _service().compare_strategies(
        {
            "symbol": "TEM",
            "direction": "neutral",
            "targetPrice": 52.4,
            "targetDate": "2026-06-19",
            "maxPremium": 150,
            "riskProfile": "conservative",
            "strategies": ["long_call", "long_put", "bull_call_spread", "bear_put_spread"],
        }
    )

    assert [strategy.strategy_type for strategy in response.strategies] == [
        "long_call",
        "long_put",
        "bear_put_spread",
    ]
    assert all(strategy.net_debit <= 150 for strategy in response.strategies)


def test_strategy_compare_rejects_unsupported_strategy_safely() -> None:
    with pytest.raises(ValueError) as exc_info:
        _service().compare_strategies(
            {
                "symbol": "TEM",
                "direction": "bullish",
                "targetPrice": 65,
                "targetDate": "2026-06-19",
                "riskProfile": "balanced",
                "strategies": ["short_call"],
            }
        )

    assert str(exc_info.value) == "Unsupported strategy requested for Options Lab Phase 4."


def test_strategy_compare_force_refresh_does_not_call_external_paths() -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("forbidden external path was called")

    with (
        patch("data_provider.base.DataFetcherManager.get_realtime_quote", side_effect=forbidden),
        patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
        patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
    ):
        response = _service().compare_strategies(
            {
                "symbol": "TEM",
                "direction": "bullish",
                "targetPrice": 65,
                "targetDate": "2026-06-19",
                "forceRefresh": True,
            }
        )

    assert response.metadata.force_refresh_ignored is True
    assert response.metadata.no_external_calls is True


def test_strategy_compare_response_excludes_raw_advice_and_order_fields() -> None:
    response = _service().compare_strategies(
        {
            "symbol": "TEM",
            "direction": "bullish",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
            "forceRefresh": True,
        }
    )

    text = _json_text(response).lower()
    for blocked in FORBIDDEN_TERMS + ["trade ticket", "order placement", "buy/sell cta"]:
        assert blocked.lower() not in text
    assert "rawproviderpayload" not in text


def test_decision_synthetic_fixture_forces_demo_only_insufficient_label() -> None:
    response = _service().evaluate_decision(
        {
            "symbol": "TEM",
            "strategy": "long_call",
            "expiration": "2026-06-19",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
            "riskBudget": 600,
            "forceRefresh": True,
        }
    )

    assert response.data_quality.data_quality_tier == "synthetic_demo_only"
    assert response.decision_label == "数据不足，禁止判断"
    assert response.trade_quality_score <= 35
    assert "synthetic_or_fixture_data_not_decision_grade" in response.data_quality.blocking_reasons
    assert response.metadata.no_external_calls is True
    assert response.optimizer.optimizer_label == "数据不足，禁止判断"
    assert response.optimizer.preferred_strategy_key is None
    assert response.gate_decision == "数据不足，禁止判断"
    assert response.decision_grade is False
    assert response.data_quality_gates is not None
    assert response.liquidity_gates is not None
    assert response.gate_issues
    assert response.fail_closed_reason_codes
    assert all(item.decision_label != "有条件可交易" for item in response.ranked_alternatives)


def test_decision_iv_rank_unavailable_returns_safe_status_no_crash(tmp_path: Path) -> None:
    fixture = json.loads(Path("tests/fixtures/options/tem_chain.json").read_text(encoding="utf-8"))
    fixture.pop("historicalIvProxy", None)
    path = tmp_path / "tem_no_iv_history.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")

    response = OptionsLabService(fixture_path=path).evaluate_decision(
        {
            "symbol": "TEM",
            "strategy": "bull_call_spread",
            "expiration": "2026-06-19",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
        }
    )

    assert response.iv_rank_status == "unavailable"
    assert response.iv_rank is None
    assert response.iv_percentile is None
    assert "iv_rank_unavailable" in response.iv_greeks.warnings
    assert "IV Rank 不可用，波动率位置置信度不足" in response.primary_reasons


def test_decision_iv_rank_synthetic_fixture_proxy_computes_rank_percentile() -> None:
    response = _service().evaluate_decision(
        {
            "symbol": "TEM",
            "strategy": "bull_call_spread",
            "expiration": "2026-06-19",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
        }
    )

    assert response.iv_rank_status == "available"
    assert response.iv_rank == 64.44
    assert response.iv_percentile == 71.43
    assert response.iv_greeks.iv_rank_source == "synthetic_fixture_proxy"
    assert response.iv_greeks.iv_rank_confidence == "test_only_low_confidence"


def test_decision_expected_move_from_iv_dte_when_straddle_mid_missing(tmp_path: Path) -> None:
    fixture = json.loads(Path("tests/fixtures/options/tem_chain.json").read_text(encoding="utf-8"))
    for contract in fixture["contracts"]:
        if contract["side"] != "call":
            contract["bid"] = None
            contract["ask"] = None
    path = tmp_path / "tem_iv_expected_move.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")

    response = OptionsLabService(fixture_path=path).evaluate_decision(
        {
            "symbol": "TEM",
            "strategy": "long_call",
            "expiration": "2026-06-19",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
            "legs": [
                {
                    "action": "buy",
                    "side": "call",
                    "contractSymbol": "TEM260619C00055000",
                    "expiration": "2026-06-19",
                    "strike": 55,
                }
            ],
        }
    )

    assert response.expected_move.expected_move_source == "iv_dte"
    assert response.expected_move.expected_move_abs == 12.01
    assert response.expected_move.expected_move_pct == 22.92


def test_decision_expected_move_unavailable_reduces_confidence(tmp_path: Path) -> None:
    fixture = json.loads(Path("tests/fixtures/options/tem_chain.json").read_text(encoding="utf-8"))
    for contract in fixture["contracts"]:
        contract["bid"] = None
        contract["ask"] = None
        contract["impliedVolatility"] = None
    path = tmp_path / "tem_no_expected_move.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")

    response = OptionsLabService(fixture_path=path).evaluate_decision(
        {
            "symbol": "TEM",
            "strategy": "long_call",
            "expiration": "2026-06-19",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
        }
    )

    assert response.expected_move.expected_move_source == "unavailable"
    assert response.expected_move.expected_move_abs is None
    assert response.trade_quality_score <= 35
    assert "expected_move_unavailable_degrade_confidence" in response.risk_warnings


def test_decision_optimizer_ranks_debit_spread_over_long_call_when_risk_reward_is_better() -> None:
    response = _service().evaluate_decision(
        {
            "symbol": "TEM",
            "strategy": "long_call",
            "expiration": "2026-06-19",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
            "riskBudget": 600,
        }
    )

    keys = [item.strategy_key for item in response.ranked_alternatives]
    assert keys.index("bull_call_spread") < keys.index("long_call")
    spread = next(item for item in response.ranked_alternatives if item.strategy_key == "bull_call_spread")
    long_call = next(item for item in response.ranked_alternatives if item.strategy_key == "long_call")
    assert spread.risk_reward_ratio is not None
    assert long_call.risk_reward_ratio is None
    assert response.optimizer.no_trade_reason == "data_quality_not_decision_grade"


def test_decision_optimizer_returns_no_trade_when_all_candidates_are_weak(tmp_path: Path) -> None:
    fixture = json.loads(Path("tests/fixtures/options/tem_chain.json").read_text(encoding="utf-8"))
    for contract in fixture["contracts"]:
        contract["volume"] = 0
        contract["openInterest"] = 0
        contract["bid"] = 0.1
        contract["ask"] = 2.5
        contract["impliedVolatility"] = 1.4
    path = tmp_path / "tem_weak_candidates.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")

    response = OptionsLabService(fixture_path=path).evaluate_decision(
        {
            "symbol": "TEM",
            "strategy": "long_call",
            "expiration": "2026-06-19",
            "targetPrice": 52.5,
            "targetDate": "2026-06-19",
        }
    )

    assert response.optimizer.preferred_strategy_key is None
    assert response.optimizer.optimizer_label in {"数据不足，禁止判断", "不建议交易", "仅观察"}
    assert response.optimizer.no_trade_reason is not None


def test_decision_missing_greeks_caps_score_and_warns() -> None:
    response = _service().evaluate_decision(
        {
            "symbol": "TEM",
            "strategy": "long_call",
            "expiration": "2026-06-19",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
            "legs": [
                {
                    "action": "buy",
                    "side": "call",
                    "contractSymbol": "TEM260619C00055000",
                    "expiration": "2026-06-19",
                    "strike": 55,
                    "quantity": 1,
                }
            ],
            "scenarioAssumptions": {"omitGreeks": True},
        }
    )

    assert response.iv_greeks.iv_readiness <= 45
    assert "missing_greeks" in response.iv_greeks.warnings
    assert response.trade_quality_score <= 35
    assert "missing_greeks_degrade_confidence" in response.risk_warnings
    assert response.gate_decision == "数据不足，禁止判断"
    assert "missing_greeks" in response.fail_closed_reason_codes


def test_decision_wide_spread_caps_score_and_warns() -> None:
    response = _service().evaluate_decision(
        {
            "symbol": "TEM",
            "strategy": "long_call",
            "expiration": "2026-06-19",
            "targetPrice": 70,
            "targetDate": "2026-06-19",
            "legs": [
                {
                    "action": "buy",
                    "side": "call",
                    "contractSymbol": "TEM260619C00065000",
                    "expiration": "2026-06-19",
                    "strike": 65,
                    "quantity": 1,
                }
            ],
        }
    )

    assert response.liquidity.spread_pct >= 90
    assert "wide_bid_ask_spread" in response.liquidity.liquidity_warnings
    assert response.trade_quality_score <= 35
    assert response.gate_decision in {"数据不足，禁止判断", "需人工复核"}
    assert "wide_bid_ask_spread" in response.fail_closed_reason_codes


def test_decision_delayed_non_live_data_cannot_emit_tradeable_label(tmp_path: Path) -> None:
    fixture = json.loads(Path("tests/fixtures/options/tem_chain.json").read_text(encoding="utf-8"))
    fixture["source"] = "delayed_provider_fixture"
    fixture["underlying"]["source"] = "delayed_provider_fixture"
    fixture["underlying"]["freshness"] = "delayed"
    path = tmp_path / "tem_delayed.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")

    response = OptionsLabService(fixture_path=path).evaluate_decision(
        {
            "symbol": "TEM",
            "strategy": "bull_call_spread",
            "expiration": "2026-06-19",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
            "riskBudget": 600,
        }
    )

    assert response.data_quality.data_quality_tier == "delayed_usable"
    assert response.decision_label != "有条件可交易"
    assert response.trade_quality_score <= 75


def test_decision_stale_live_shaped_data_is_degraded_not_full_confidence(tmp_path: Path) -> None:
    fixture = json.loads(Path("tests/fixtures/options/tem_chain.json").read_text(encoding="utf-8"))
    fixture["source"] = "live_options_provider"
    fixture["providerQuality"] = "live_provider_stale"
    fixture["providerCapabilities"] = {
        "providerName": "review_fixture",
        "sourceType": "live",
        "fixtureOnly": False,
        "liveEnabled": True,
        "delayed": False,
        "tradeableData": True,
    }
    fixture["underlying"]["source"] = "live_options_provider"
    fixture["underlying"]["freshness"] = "stale"
    path = tmp_path / "tem_stale_live_shaped.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")

    response = OptionsLabService(fixture_path=path).evaluate_decision(
        {
            "symbol": "TEM",
            "strategy": "bull_call_spread",
            "expiration": "2026-06-19",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
            "riskBudget": 600,
        }
    )

    assert response.data_quality.source_type == "delayed"
    assert response.data_quality.data_quality_tier == "delayed_usable"
    assert response.freshness.freshness == "stale"
    assert response.decision_label != "有条件可交易"
    assert response.trade_quality_score <= 75
    assert all(item.decision_label != "有条件可交易" for item in response.ranked_alternatives)


@pytest.mark.parametrize(
    ("source", "freshness", "expected_source_type", "expected_tier"),
    [
        ("cached_provider_snapshot", "cached", "delayed", "delayed_usable"),
        ("fallback_provider_snapshot", "fallback", "fallback", "synthetic_demo_only"),
        ("synthetic_options_lab_fixture", "synthetic_delayed", "synthetic", "synthetic_demo_only"),
    ],
)
def test_decision_cached_fallback_and_synthetic_sources_remain_non_trade_ready(
    tmp_path: Path,
    source: str,
    freshness: str,
    expected_source_type: str,
    expected_tier: str,
) -> None:
    fixture = json.loads(Path("tests/fixtures/options/tem_chain.json").read_text(encoding="utf-8"))
    fixture["source"] = source
    fixture["providerQuality"] = f"{expected_source_type}_not_tradeable"
    fixture["underlying"]["source"] = source
    fixture["underlying"]["freshness"] = freshness
    for contract in fixture["contracts"]:
        contract["source"] = source
        contract["freshness"] = freshness
        contract["dataQuality"] = {
            "tier": expected_tier,
            "tradeable": False,
            "hints": [f"{expected_source_type}_not_decision_grade"],
        }
    path = tmp_path / f"tem_{expected_source_type}_source.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")

    response = OptionsLabService(fixture_path=path).evaluate_decision(
        {
            "symbol": "TEM",
            "strategy": "bull_call_spread",
            "expiration": "2026-06-19",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
            "riskBudget": 600,
        }
    )

    assert response.data_quality.source_type == expected_source_type
    assert response.data_quality.data_quality_tier == expected_tier
    assert response.decision_label != "有条件可交易"
    assert response.optimizer.optimizer_label != "有条件可交易"
    assert response.metadata.live_provider_enabled is False
    assert all(item.decision_label != "有条件可交易" for item in response.ranked_alternatives)
    text = _json_text(response).lower()
    for blocked in ["有条件可交易", "trade-ready", "trade ready", "best contract", "guaranteed", "must buy", "must sell"]:
        assert blocked.lower() not in text


def test_decision_delayed_fixture_provider_selection_cannot_emit_tradeable_label() -> None:
    response = _service().evaluate_decision(
        {
            "symbol": "TEM",
            "marketDataProvider": "delayed_fixture",
            "strategy": "bull_call_spread",
            "expiration": "2026-06-19",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
            "riskBudget": 600,
        }
    )

    assert response.metadata.provider_name == "delayed_fixture"
    assert response.metadata.provider_capabilities["liveEnabled"] is False
    assert response.data_quality.data_quality_tier == "delayed_usable"
    assert response.freshness.freshness == "delayed"
    assert response.decision_label != "有条件可交易"
    assert all(item.decision_label != "有条件可交易" for item in response.ranked_alternatives)


def test_decision_long_call_breakeven_realism_calculation() -> None:
    response = _service().evaluate_decision(
        {
            "symbol": "TEM",
            "strategy": "long_call",
            "expiration": "2026-06-19",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
            "legs": [
                {
                    "action": "buy",
                    "side": "call",
                    "contractSymbol": "TEM260619C00055000",
                    "expiration": "2026-06-19",
                    "strike": 55,
                    "quantity": 1,
                }
            ],
        }
    )

    assert response.breakeven.breakeven == 57.7
    assert response.breakeven.required_move_pct == 10.11
    assert response.breakeven.target_price_status == "target_above_breakeven"


def test_decision_bull_call_spread_risk_reward_calculation() -> None:
    response = _service().evaluate_decision(
        {
            "symbol": "TEM",
            "strategy": "bull_call_spread",
            "expiration": "2026-06-19",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
        }
    )

    assert response.risk_reward.max_loss == 230
    assert response.risk_reward.max_gain == 270
    assert response.risk_reward.risk_reward_ratio == 1.17
    assert response.better_alternative is not None


def test_decision_response_excludes_raw_provider_secret_and_live_paths() -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("forbidden external path was called")

    with (
        patch("data_provider.base.DataFetcherManager.get_realtime_quote", side_effect=forbidden),
        patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
        patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
    ):
        response = _service().evaluate_decision(
            {
                "symbol": "TEM",
                "strategy": "bull_call_spread",
                "expiration": "2026-06-19",
                "targetPrice": 65,
                "targetDate": "2026-06-19",
                "forceRefresh": True,
            }
        )

    text = _json_text(response).lower()
    for blocked in FORBIDDEN_TERMS + ["traceback", "stack trace", "raw payload"]:
        assert blocked.lower() not in text
    assert response.metadata.force_refresh_ignored is True


def test_decision_response_adds_gate_diagnostics_without_removing_existing_fields() -> None:
    response = _service().evaluate_decision(
        {
            "symbol": "TEM",
            "strategy": "bull_call_spread",
            "expiration": "2026-06-19",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
            "riskBudget": 600,
        }
    )

    payload = response.model_dump(by_alias=True)
    for key in [
        "dataQuality",
        "liquidity",
        "ivGreeks",
        "expectedMove",
        "optimizer",
        "rankedAlternatives",
        "tradeQualityScore",
        "decisionLabel",
    ]:
        assert key in payload
    for key in [
        "dataQualityGates",
        "liquidityGates",
        "gateDecision",
        "gateIssues",
        "decisionGrade",
        "failClosedReasonCodes",
    ]:
        assert key in payload
