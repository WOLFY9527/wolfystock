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
    ]

    text = "\n".join(_json_text(payload) for payload in payloads).lower()
    for blocked in FORBIDDEN_TERMS:
        assert blocked.lower() not in text
