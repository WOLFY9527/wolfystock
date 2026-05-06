# -*- coding: utf-8 -*-
"""Options market data provider adapter contract tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.options_lab_service import OptionsLabProviderUnavailable, OptionsLabService
from src.services.options_market_data_provider import (
    DelayedFixtureOptionsProvider,
    MalformedGreeksFixtureOptionsProvider,
    SyntheticFixtureOptionsProvider,
    create_options_market_data_provider,
)


FIXTURE_PATH = Path("tests/fixtures/options/tem_chain.json")


def test_synthetic_fixture_provider_exposes_contract_methods_without_live_calls() -> None:
    provider = SyntheticFixtureOptionsProvider(fixture_path=FIXTURE_PATH)

    expirations = provider.get_expirations("TEM")
    quote = provider.get_underlying_quote("TEM")
    chain = provider.get_chain("TEM", expiration="2026-06-19")

    assert provider.provider_name == "synthetic_fixture"
    assert provider.capabilities.live_enabled is False
    assert provider.capabilities.fixture_only is True
    assert provider.capabilities.tradeable_data is False
    assert [item["date"] for item in expirations] == ["2026-06-19", "2026-08-21"]
    assert quote["source"] == "synthetic_options_lab_fixture"
    assert quote["freshness"] == "synthetic_delayed"
    assert chain["providerName"] == "synthetic_fixture"
    assert chain["providerCapabilities"]["supportsGreeks"] is True
    assert all(contract["expiration"] == "2026-06-19" for contract in chain["contracts"])


def test_delayed_fixture_provider_is_real_shaped_but_not_tradeable() -> None:
    service = OptionsLabService(
        market_data_provider=DelayedFixtureOptionsProvider(fixture_path=FIXTURE_PATH),
        provider_name="delayed_fixture",
    )

    chain = service.get_chain("TEM")
    decision = service.evaluate_decision(
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

    assert chain.metadata.provider_name == "delayed_fixture"
    assert chain.metadata.live_provider_enabled is False
    assert chain.calls[0].source == "delayed_provider_fixture"
    assert chain.calls[0].freshness == "delayed"
    assert chain.calls[0].provider_quality == "delayed_fixture_only"
    assert chain.calls[0].data_quality["tradeable"] is False
    assert decision.data_quality.data_quality_tier == "delayed_usable"
    assert decision.decision_label != "有条件可交易"
    assert all(item.decision_label != "有条件可交易" for item in decision.ranked_alternatives)


def test_malformed_missing_greeks_provider_normalizes_missing_fields_and_caps_decision() -> None:
    service = OptionsLabService(
        market_data_provider=MalformedGreeksFixtureOptionsProvider(fixture_path=FIXTURE_PATH),
        provider_name="malformed_fixture",
    )

    chain = service.get_chain("TEM", expiration="2026-06-19")
    decision = service.evaluate_decision(
        {
            "symbol": "TEM",
            "marketDataProvider": "malformed_fixture",
            "strategy": "long_call",
            "expiration": "2026-06-19",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
        }
    )

    assert chain.metadata.provider_name == "malformed_fixture"
    assert chain.calls[0].greeks is None
    assert chain.calls[0].implied_volatility is None
    assert chain.calls[0].data_quality["hints"] == ["missing_iv", "missing_greeks"]
    assert decision.iv_greeks.iv_readiness <= 45
    assert "missing_greeks" in decision.iv_greeks.warnings
    assert decision.decision_label == "数据不足，禁止判断"


def test_live_provider_names_are_explicitly_disabled() -> None:
    with pytest.raises(OptionsLabProviderUnavailable) as exc_info:
        OptionsLabService(provider_name="tradier")

    assert exc_info.value.code == "options_provider_not_implemented"


def test_provider_factory_rejects_unknown_provider_without_fallback() -> None:
    with pytest.raises(ValueError) as exc_info:
        create_options_market_data_provider("unknown_options_provider")

    assert "disabled or not implemented" in str(exc_info.value)
