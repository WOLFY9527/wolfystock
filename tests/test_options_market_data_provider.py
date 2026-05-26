# -*- coding: utf-8 -*-
"""Options market data provider adapter contract tests."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

from src.services.options_lab_service import OptionsLabProviderUnavailable, OptionsLabService
from src.services.options_market_data_provider import (
    ALLOWED_OPTIONS_PROVIDER_KEYS,
    ALLOWED_STAGING_PROBE_ARTIFACT_KEYS,
    DelayedFixtureOptionsProvider,
    LIVE_OPTIONS_PROVIDER_NAMES,
    MalformedGreeksFixtureOptionsProvider,
    OptionsLiveProviderConfig,
    OptionsProviderUnavailable,
    SyntheticFixtureOptionsProvider,
    TradierOptionsHttpTransport,
    TradierOptionsProviderStub,
    build_options_provider_live_readiness_preflight,
    create_options_market_data_provider,
)
from src.services.provider_circuit_observer import ProviderCircuitObserver
from src.storage import DatabaseManager


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
    assert decision.decision_grade is False
    assert "provider_fixture_not_decision_grade" in decision.fail_closed_reason_codes
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


@pytest.mark.parametrize("provider_name", ["tradier", "ibkr", "polygon"])
def test_live_provider_stubs_are_disabled_by_default(provider_name: str) -> None:
    provider = create_options_market_data_provider(provider_name)

    assert provider.provider_name == provider_name
    assert provider.capabilities.source_type == "live_stub"
    assert provider.capabilities.live_enabled is False
    assert provider.capabilities.fixture_only is False
    assert provider.capabilities.tradeable_data is False
    assert "live_stub" in provider.capabilities.notes
    assert "no_external_calls" in provider.capabilities.notes

    with patch("requests.sessions.Session.request") as request_mock:
        with pytest.raises(OptionsProviderUnavailable) as exc_info:
            provider.get_chain("TEM")

    assert exc_info.value.provider_name == provider_name
    assert exc_info.value.code == "options_provider_disabled"
    request_mock.assert_not_called()


@pytest.mark.parametrize("provider_name", ["tradier", "ibkr", "polygon"])
def test_live_provider_stubs_expose_no_trade_or_score_grade_surface(provider_name: str) -> None:
    provider = create_options_market_data_provider(provider_name)
    exposed_names = {name.lower() for name in dir(provider)}

    assert provider.capabilities.live_enabled is False
    assert provider.capabilities.tradeable_data is False
    for forbidden_name in (
        "decision_grade",
        "evaluate_decision",
        "place_order",
        "score_contract",
        "submit_order",
        "trade_quality_score",
    ):
        assert forbidden_name not in exposed_names

    with patch("requests.sessions.Session.request") as request_mock:
        for method_name in ("get_expirations", "get_underlying_quote", "get_chain"):
            with pytest.raises(OptionsProviderUnavailable) as exc_info:
                getattr(provider, method_name)("TEM")
            assert exc_info.value.code == "options_provider_disabled"

    request_mock.assert_not_called()


@pytest.mark.parametrize("provider_name", ["tradier", "ibkr", "polygon"])
def test_live_provider_stubs_require_provider_enable_flag(provider_name: str) -> None:
    provider = create_options_market_data_provider(
        provider_name,
        live_provider_config=OptionsLiveProviderConfig(live_providers_enabled=True),
    )

    with pytest.raises(OptionsProviderUnavailable) as exc_info:
        provider.get_expirations("TEM")

    assert exc_info.value.code == "options_provider_not_enabled"


@pytest.mark.parametrize("provider_name", ["tradier", "ibkr", "polygon"])
def test_live_provider_stubs_require_credentials_without_exposing_values(provider_name: str) -> None:
    provider = create_options_market_data_provider(
        provider_name,
        live_provider_config=OptionsLiveProviderConfig(
            live_providers_enabled=True,
            enabled_provider_keys=frozenset({provider_name}),
            credentialed_provider_keys=frozenset(),
        ),
    )

    with pytest.raises(OptionsProviderUnavailable) as exc_info:
        provider.get_underlying_quote("TEM")

    assert exc_info.value.code == "options_provider_credentials_missing"
    serialized_error = str(exc_info.value).lower()
    assert "api_key" not in serialized_error
    assert "token" not in serialized_error
    assert "secret" not in serialized_error
    assert "env" not in serialized_error


def test_options_provider_selection_contract_keeps_fixture_default_and_allowed_keys() -> None:
    provider = create_options_market_data_provider("")

    assert provider.provider_name == "synthetic_fixture"
    assert {
        "synthetic_fixture",
        "delayed_fixture",
        "malformed_fixture",
        "tradier",
        "ibkr",
        "polygon",
    }.issubset(ALLOWED_OPTIONS_PROVIDER_KEYS)


@pytest.mark.parametrize("provider_name", ["tradier", "ibkr", "polygon"])
def test_options_lab_service_surfaces_live_stub_safe_errors(provider_name: str) -> None:
    service = OptionsLabService()

    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(OptionsLabProviderUnavailable) as exc_info:
            service.get_chain("TEM", market_data_provider=provider_name)

    assert exc_info.value.provider_name == provider_name
    assert exc_info.value.code == "options_provider_disabled"


def test_provider_factory_rejects_unknown_provider_without_fallback() -> None:
    with pytest.raises(ValueError) as exc_info:
        create_options_market_data_provider("unknown_options_provider")

    assert "disabled or not implemented" in str(exc_info.value)


def test_tradier_dry_run_maps_provider_shaped_chain_without_live_or_tradeable_flags() -> None:
    provider = TradierOptionsProviderStub(
        config=OptionsLiveProviderConfig(
            live_providers_enabled=True,
            enabled_provider_keys=frozenset({"tradier"}),
            credentialed_provider_keys=frozenset({"tradier"}),
            dry_run_provider_keys=frozenset({"tradier"}),
        )
    )

    quote = provider.get_underlying_quote("TEM")
    chain = provider.get_chain("TEM", expiration="2026-06-19")
    expirations = provider.get_expirations("TEM")

    assert provider.capabilities.live_enabled is False
    assert provider.capabilities.tradeable_data is False
    assert provider.capabilities.delayed is True
    assert quote["source"] == "tradier_dry_run_fixture"
    assert quote["freshness"] == "delayed_dry_run"
    assert set(quote).issuperset(
        {"price", "changePct", "asOf", "source", "freshness", "providerQuality"}
    )
    assert chain["providerName"] == "tradier"
    assert chain["source"] == "tradier_dry_run_fixture"
    assert chain["providerQuality"] == "tradier_dry_run_not_tradeable"
    assert chain["dataQuality"]["tier"] == "delayed_usable"
    assert chain["providerCapabilities"]["liveEnabled"] is False
    assert chain["providerCapabilities"]["tradeableData"] is False
    assert chain["providerCapabilities"]["sourceType"] == "delayed_dry_run"
    assert chain["dataQuality"]["tradeable"] is False
    assert "not_tradeable" in chain["dataQuality"]["hints"]
    assert set(chain).issuperset(
        {
            "symbol",
            "market",
            "currency",
            "underlying",
            "chainAsOf",
            "source",
            "providerName",
            "providerQuality",
            "dataQuality",
            "providerCapabilities",
            "expirations",
            "contracts",
        }
    )
    assert [item["date"] for item in expirations] == ["2026-06-19", "2026-08-21"]
    assert set(expirations[0]).issuperset(
        {"date", "dte", "type", "chainAvailable", "asOf", "source", "freshness", "warnings"}
    )
    assert {contract["side"] for contract in chain["contracts"]} == {"call", "put"}
    assert all(contract["expiration"] == "2026-06-19" for contract in chain["contracts"])
    assert chain["contracts"][0]["impliedVolatility"] == 0.62
    assert chain["contracts"][0]["greeks"]["delta"] == 0.61
    assert set(chain["contracts"][0]).issuperset(
        {
            "contractSymbol",
            "side",
            "expiration",
            "strike",
            "bid",
            "ask",
            "last",
            "volume",
            "openInterest",
            "impliedVolatility",
            "greeks",
            "multiplier",
            "source",
            "freshness",
            "providerQuality",
            "dataQuality",
            "warnings",
        }
    )
    assert all(contract["dataQuality"]["tradeable"] is False for contract in chain["contracts"])
    assert all(contract["freshness"] == "delayed_dry_run" for contract in chain["contracts"])


def test_tradier_dry_run_fixture_remains_non_decision_grade_in_service() -> None:
    provider = TradierOptionsProviderStub(
        config=OptionsLiveProviderConfig(
            live_providers_enabled=True,
            enabled_provider_keys=frozenset({"tradier"}),
            credentialed_provider_keys=frozenset({"tradier"}),
            dry_run_provider_keys=frozenset({"tradier"}),
        )
    )
    service = OptionsLabService(market_data_provider=provider, provider_name="tradier")

    with patch("requests.sessions.Session.request") as request_mock:
        decision = service.evaluate_decision(
            {
                "symbol": "TEM",
                "marketDataProvider": "tradier",
                "strategy": "long_call",
                "expiration": "2026-06-19",
                "targetPrice": 65,
                "targetDate": "2026-06-19",
                "riskBudget": 600,
            }
        )

    assert decision.metadata.provider_name == "tradier"
    assert decision.metadata.live_provider_enabled is False
    assert decision.metadata.provider_capabilities["liveEnabled"] is False
    assert decision.metadata.provider_capabilities["tradeableData"] is False
    assert decision.data_quality.data_quality_tier == "delayed_usable"
    assert decision.decision_grade is False
    assert decision.decision_label == "数据不足，禁止判断"
    assert "dry_run_source_not_decision_grade" in decision.fail_closed_reason_codes
    assert "provider_dry_run_not_decision_grade" in decision.fail_closed_reason_codes
    assert all(item.decision_label != "有条件可交易" for item in decision.ranked_alternatives)
    request_mock.assert_not_called()


class _FakeTradierOptionsTransport:
    def __init__(
        self,
        *,
        quote_payload: dict | None = None,
        expirations_payload: dict | None = None,
        chain_payload: dict | None = None,
    ) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.quote_payload = quote_payload or _tradier_quote_payload()
        self.expirations_payload = expirations_payload or _tradier_expirations_payload()
        self.chain_payload = chain_payload or _tradier_chain_payload()

    def get_quote(self, symbol: str) -> dict:
        self.calls.append(("quote", symbol))
        return self.quote_payload

    def get_expirations(self, symbol: str) -> dict:
        self.calls.append(("expirations", symbol))
        return self.expirations_payload

    def get_chain(self, symbol: str, expiration: str | None = None) -> dict:
        self.calls.append(("chain", symbol, expiration or ""))
        return self.chain_payload


def _tradier_enabled_config() -> OptionsLiveProviderConfig:
    return OptionsLiveProviderConfig.from_env(
        {
            "OPTIONS_LIVE_PROVIDERS_ENABLED": "1",
            "OPTIONS_LIVE_PROVIDER_KEYS": "tradier",
            "TRADIER_API_TOKEN": "valid_synthetic_readiness_value_contract_1234567890",
        }
    )


def _tradier_runtime_env(credential: str = "valid_synthetic_readiness_value_contract_1234567890") -> dict[str, str]:
    return {
        "OPTIONS_LIVE_PROVIDERS_ENABLED": "1",
        "OPTIONS_LIVE_PROVIDER_KEYS": "tradier",
        "TRADIER_API_TOKEN": credential,
    }


def _tradier_quote_payload() -> dict:
    return {
        "quotes": {
            "quote": {
                "symbol": "TEM",
                "last": "52.40",
                "change_percentage": "1.15",
                "trade_date": "2026-05-06T13:45:00Z",
            }
        }
    }


def _tradier_expirations_payload() -> dict:
    return {"expirations": {"date": ["2026-06-19", "2026-08-21"]}}


def _tradier_chain_payload(contract_overrides: dict | None = None) -> dict:
    base_contract = {
        "symbol": "TEM260619C00050000",
        "option_type": "call",
        "expiration_date": "2026-06-19",
        "strike": "50.0",
        "bid": "4.80",
        "ask": "5.20",
        "last": "5.00",
        "volume": "320",
        "open_interest": "1480",
        "greeks": {
            "mid_iv": "0.62",
            "delta": "0.61",
            "gamma": "0.044",
            "theta": "-0.072",
            "vega": "0.118",
            "rho": "0.031",
        },
    }
    if contract_overrides:
        base_contract.update(contract_overrides)
    return {"options": {"option": [base_contract]}}


class _FakeTradierHttpResponse:
    def __init__(
        self,
        payload: object | None = None,
        *,
        status_code: int = 200,
        json_error: Exception | None = None,
        http_error: Exception | None = None,
    ) -> None:
        self.payload = payload if payload is not None else {}
        self.status_code = status_code
        self.json_error = json_error
        self.http_error = http_error

    def raise_for_status(self) -> None:
        if self.http_error is not None:
            raise self.http_error

    def json(self) -> object:
        if self.json_error is not None:
            raise self.json_error
        return self.payload


class _FakeTradierHttpSession:
    def __init__(self, *responses: object) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def request(self, method: str, url: str, **kwargs: object) -> object:
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            raise AssertionError("unexpected HTTP request")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_tradier_http_transport_uses_expected_market_data_paths_headers_and_timeout() -> None:
    credential = "synthetic_tradier_http_credential_1234567890"
    session = _FakeTradierHttpSession(
        _FakeTradierHttpResponse(_tradier_quote_payload()),
        _FakeTradierHttpResponse(_tradier_expirations_payload()),
        _FakeTradierHttpResponse(_tradier_chain_payload()),
    )
    transport = TradierOptionsHttpTransport(
        api_token=credential,
        base_url="https://sandbox.tradier.example/v1/",
        timeout_seconds=1.75,
        session=session,
    )

    assert transport.get_quote("TEM") == _tradier_quote_payload()
    assert transport.get_expirations("TEM") == _tradier_expirations_payload()
    assert transport.get_chain("TEM", expiration="2026-06-19") == _tradier_chain_payload()

    assert [call["method"] for call in session.calls] == ["GET", "GET", "GET"]
    assert [call["url"] for call in session.calls] == [
        "https://sandbox.tradier.example/v1/markets/quotes",
        "https://sandbox.tradier.example/v1/markets/options/expirations",
        "https://sandbox.tradier.example/v1/markets/options/chains",
    ]
    assert [call["params"] for call in session.calls] == [
        {"symbols": "TEM"},
        {"symbol": "TEM"},
        {"symbol": "TEM", "expiration": "2026-06-19", "greeks": "true"},
    ]
    assert all(call["timeout"] == 1.75 for call in session.calls)
    for call in session.calls:
        headers = call["headers"]
        assert headers["Accept"] == "application/json"
        assert headers["Authorization"] == f"Bearer {credential}"


def test_tradier_http_transport_exposes_no_broker_order_or_portfolio_mutation_path() -> None:
    transport = TradierOptionsHttpTransport(
        api_token="synthetic_tradier_http_credential_1234567890",
        session=_FakeTradierHttpSession(),
    )
    exposed_names = {name.lower() for name in dir(transport)}

    assert "place_order" not in exposed_names
    assert "submit_order" not in exposed_names
    assert "create_order" not in exposed_names
    assert "mutate_portfolio" not in exposed_names
    assert "sync_broker" not in exposed_names
    assert "get_chain" in exposed_names
    assert "get_quote" in exposed_names
    assert "get_expirations" in exposed_names


def test_tradier_http_transport_converts_http_errors_to_sanitized_provider_errors() -> None:
    credential = "synthetic_tradier_http_credential_1234567890"
    session = _FakeTradierHttpSession(
        _FakeTradierHttpResponse(
            {},
            status_code=403,
            http_error=requests.HTTPError(
                f"403 authorization bearer {credential} https://provider.invalid/raw"
            ),
        )
    )
    transport = TradierOptionsHttpTransport(api_token=credential, session=session)

    with pytest.raises(OptionsProviderUnavailable) as exc_info:
        transport.get_quote("TEM")

    assert exc_info.value.code == "options_provider_http_error"
    text = str(exc_info.value).lower()
    for blocked in (credential.lower(), "authorization", "bearer", "provider.invalid", "raw"):
        assert blocked not in text


def test_tradier_http_transport_converts_malformed_json_to_sanitized_provider_errors() -> None:
    credential = "synthetic_tradier_http_credential_1234567890"
    session = _FakeTradierHttpSession(
        _FakeTradierHttpResponse(
            json_error=ValueError(f"malformed json for {credential}")
        )
    )
    transport = TradierOptionsHttpTransport(api_token=credential, session=session)

    with pytest.raises(OptionsProviderUnavailable) as exc_info:
        transport.get_expirations("TEM")

    assert exc_info.value.code == "options_provider_payload_unmappable"
    assert credential.lower() not in str(exc_info.value).lower()


def test_tradier_http_transport_normalizes_valid_mocked_response_without_decision_grade() -> None:
    credential = "synthetic_tradier_http_credential_1234567890"
    session = _FakeTradierHttpSession(
        _FakeTradierHttpResponse(_tradier_quote_payload()),
        _FakeTradierHttpResponse(_tradier_expirations_payload()),
        _FakeTradierHttpResponse(_tradier_chain_payload()),
    )
    provider = TradierOptionsProviderStub(
        config=_tradier_enabled_config(),
        transport=TradierOptionsHttpTransport(api_token=credential, session=session),
    )

    chain = provider.get_chain("TEM", expiration="2026-06-19")

    assert provider.capabilities.live_enabled is True
    assert provider.capabilities.tradeable_data is False
    assert provider.capabilities.source_type == "tradier_adapter_contract"
    contract = chain["contracts"][0]
    assert contract["contractSymbol"] == "TEM260619C00050000"
    assert contract["side"] == "call"
    assert contract["expiration"] == "2026-06-19"
    assert contract["strike"] == 50.0
    assert contract["bid"] == 4.8
    assert contract["ask"] == 5.2
    assert contract["volume"] == 320
    assert contract["openInterest"] == 1480
    assert contract["impliedVolatility"] == 0.62
    assert contract["greeks"] == {
        "delta": 0.61,
        "gamma": 0.044,
        "theta": -0.072,
        "vega": 0.118,
        "rho": 0.031,
    }
    assert chain["expirations"][0]["date"] == "2026-06-19"
    assert chain["dataQuality"]["tradeable"] is False
    assert "not_decision_grade" in chain["dataQuality"]["hints"]
    assert credential.lower() not in _json_lower(chain)


def test_tradier_default_factory_does_not_construct_or_call_http_transport() -> None:
    with patch.dict(os.environ, {}, clear=True):
        provider = create_options_market_data_provider(
            "tradier",
            live_provider_config=_tradier_enabled_config(),
        )

    with patch("requests.sessions.Session.request") as request_mock:
        with pytest.raises(OptionsProviderUnavailable) as exc_info:
            provider.get_chain("TEM")

    assert exc_info.value.code == "options_provider_dry_run_not_enabled"
    assert provider.capabilities.live_enabled is False
    assert provider.capabilities.tradeable_data is False
    assert "decision_grade" not in {name.lower() for name in dir(provider)}
    request_mock.assert_not_called()


def test_tradier_factory_opt_in_constructs_http_transport_and_uses_mocked_market_data() -> None:
    credential = "synthetic_tradier_runtime_credential_1234567890"
    with patch.dict(os.environ, _tradier_runtime_env(credential), clear=True):
        provider = create_options_market_data_provider(
            "tradier",
            live_provider_config=OptionsLiveProviderConfig.from_env(),
        )

    assert isinstance(provider, TradierOptionsProviderStub)
    assert isinstance(provider.transport, TradierOptionsHttpTransport)
    assert provider.capabilities.provider_name == "tradier"
    assert provider.capabilities.source_type == "tradier_adapter_contract"
    assert provider.capabilities.live_enabled is True
    assert provider.capabilities.tradeable_data is False
    assert "decision_grade" not in {name.lower() for name in dir(provider)}

    with patch(
        "requests.sessions.Session.request",
        side_effect=[
            _FakeTradierHttpResponse(_tradier_quote_payload()),
            _FakeTradierHttpResponse(_tradier_expirations_payload()),
            _FakeTradierHttpResponse(_tradier_chain_payload()),
        ],
    ) as request_mock:
        chain = provider.get_chain("TEM", expiration="2026-06-19")

    assert request_mock.call_count == 3
    assert [call.kwargs["params"] for call in request_mock.call_args_list] == [
        {"symbols": "TEM"},
        {"symbol": "TEM"},
        {"symbol": "TEM", "expiration": "2026-06-19", "greeks": "true"},
    ]
    assert all(call.kwargs["headers"]["Authorization"] == f"Bearer {credential}" for call in request_mock.call_args_list)
    assert chain["providerName"] == "tradier"
    assert chain["providerCapabilities"]["liveEnabled"] is True
    assert chain["providerCapabilities"]["tradeableData"] is False
    assert chain["providerCapabilities"].get("providerDecisionAuthority") is not True
    assert chain["providerCapabilities"].get("recommendationAuthority") is not True
    assert chain["dataQuality"]["tradeable"] is False
    assert chain["contracts"][0]["contractSymbol"] == "TEM260619C00050000"
    assert credential.lower() not in _json_lower(chain)


def test_tradier_factory_opt_in_missing_credentials_fails_closed_without_network() -> None:
    with patch.dict(
        os.environ,
        {
            "OPTIONS_LIVE_PROVIDERS_ENABLED": "1",
            "OPTIONS_LIVE_PROVIDER_KEYS": "tradier",
        },
        clear=True,
    ):
        provider = create_options_market_data_provider(
            "tradier",
            live_provider_config=OptionsLiveProviderConfig.from_env(),
        )

    assert isinstance(provider, TradierOptionsProviderStub)
    assert provider.transport is None
    with patch("requests.sessions.Session.request") as request_mock:
        with pytest.raises(OptionsProviderUnavailable) as exc_info:
            provider.get_chain("TEM")

    assert exc_info.value.code == "options_provider_credentials_missing"
    text = str(exc_info.value).lower()
    for blocked in ("tradier_api_token", "api_token", "token=", "secret", "authorization", "bearer"):
        assert blocked not in text
    request_mock.assert_not_called()


def test_tradier_factory_http_error_is_sanitized_and_fails_closed() -> None:
    credential = "synthetic_tradier_runtime_credential_1234567890"
    with patch.dict(os.environ, _tradier_runtime_env(credential), clear=True):
        provider = create_options_market_data_provider(
            "tradier",
            live_provider_config=OptionsLiveProviderConfig.from_env(),
        )

    with patch(
        "requests.sessions.Session.request",
        return_value=_FakeTradierHttpResponse(
            {},
            status_code=503,
            http_error=requests.HTTPError(f"503 bearer {credential} https://tradier.invalid/raw"),
        ),
    ) as request_mock:
        with pytest.raises(OptionsProviderUnavailable) as exc_info:
            provider.get_chain("TEM")

    assert exc_info.value.code == "options_provider_http_error"
    text = str(exc_info.value).lower()
    for blocked in (credential.lower(), "authorization", "bearer", "tradier.invalid", "raw"):
        assert blocked not in text
    assert request_mock.call_count == 1


def test_tradier_mock_transport_normalizes_quote_expirations_and_chain_without_default_network() -> None:
    transport = _FakeTradierOptionsTransport()
    provider = TradierOptionsProviderStub(config=_tradier_enabled_config(), transport=transport)

    with patch("requests.sessions.Session.request") as request_mock:
        quote = provider.get_underlying_quote("TEM")
        expirations = provider.get_expirations("TEM")
        chain = provider.get_chain("TEM", expiration="2026-06-19")

    assert transport.calls == [
        ("quote", "TEM"),
        ("expirations", "TEM"),
        ("quote", "TEM"),
        ("expirations", "TEM"),
        ("chain", "TEM", "2026-06-19"),
    ]
    request_mock.assert_not_called()
    assert provider.capabilities.provider_name == "tradier"
    assert provider.capabilities.live_enabled is False
    assert provider.capabilities.tradeable_data is False
    assert provider.capabilities.source_type == "tradier_adapter_contract"
    assert provider.capabilities.notes == (
        "tradier_adapter_contract",
        "mock_transport_only",
        "not_tradeable",
        "not_decision_grade",
    )

    assert quote == {
        "price": 52.4,
        "changePct": 1.15,
        "asOf": "2026-05-06T13:45:00Z",
        "source": "tradier_adapter_contract",
        "freshness": "unknown",
        "providerQuality": "tradier_adapter_contract_not_tradeable",
    }
    assert [item["date"] for item in expirations] == ["2026-06-19", "2026-08-21"]
    assert all(item["source"] == "tradier_adapter_contract" for item in expirations)
    assert all(item["freshness"] == "unknown" for item in expirations)
    assert chain["providerName"] == "tradier"
    assert chain["source"] == "tradier_adapter_contract"
    assert chain["providerQuality"] == "tradier_adapter_contract_not_tradeable"
    assert chain["providerCapabilities"]["providerName"] == "tradier"
    assert chain["providerCapabilities"]["liveEnabled"] is False
    assert chain["providerCapabilities"]["tradeableData"] is False
    assert chain["dataQuality"] == {
        "tier": "insufficient",
        "tradeable": False,
        "hints": ["tradier_adapter_contract", "mock_transport_only", "not_tradeable", "not_decision_grade"],
    }
    contract = chain["contracts"][0]
    assert contract["contractSymbol"] == "TEM260619C00050000"
    assert contract["side"] == "call"
    assert contract["expiration"] == "2026-06-19"
    assert contract["strike"] == 50.0
    assert contract["bid"] == 4.8
    assert contract["ask"] == 5.2
    assert contract["volume"] == 320
    assert contract["openInterest"] == 1480
    assert contract["impliedVolatility"] == 0.62
    assert contract["greeks"] == {
        "delta": 0.61,
        "gamma": 0.044,
        "theta": -0.072,
        "vega": 0.118,
        "rho": 0.031,
    }
    assert contract["dataQuality"]["tradeable"] is False
    assert contract["freshness"] == "unknown"
    text = _json_lower(chain)
    for blocked in (
        "valid_synthetic_readiness_value_contract",
        "tradier_api_token",
        "api_token",
        "token",
        "secret",
        "authorization",
    ):
        assert blocked not in text


def test_tradier_adapter_contract_remains_non_decision_grade_with_clean_payload() -> None:
    provider = TradierOptionsProviderStub(
        config=_tradier_enabled_config(),
        transport=_FakeTradierOptionsTransport(),
    )
    service = OptionsLabService(market_data_provider=provider, provider_name="tradier")

    with patch("requests.sessions.Session.request") as request_mock:
        decision = service.evaluate_decision(
            {
                "symbol": "TEM",
                "marketDataProvider": "tradier",
                "strategy": "long_call",
                "expiration": "2026-06-19",
                "targetPrice": 65,
                "targetDate": "2026-06-19",
                "riskBudget": 600,
            }
        )

    assert decision.metadata.provider_name == "tradier"
    assert decision.metadata.provider_capabilities["sourceType"] == "tradier_adapter_contract"
    assert decision.metadata.provider_capabilities["liveEnabled"] is False
    assert decision.metadata.provider_capabilities["tradeableData"] is False
    assert decision.decision_grade is False
    assert decision.decision_label == "数据不足，禁止判断"
    assert "provider_adapter_contract_not_decision_grade" in decision.fail_closed_reason_codes
    assert all(item.decision_label != "有条件可交易" for item in decision.ranked_alternatives)
    request_mock.assert_not_called()


@pytest.mark.parametrize(
    ("contract_overrides", "expected_code"),
    [
        ({"bid": None, "ask": None}, "missing_bid_ask"),
        ({"greeks": {}, "implied_volatility": None}, "missing_greeks"),
    ],
)
def test_tradier_mock_transport_missing_market_fields_remain_data_quality_blocked(
    contract_overrides: dict,
    expected_code: str,
) -> None:
    provider = TradierOptionsProviderStub(
        config=_tradier_enabled_config(),
        transport=_FakeTradierOptionsTransport(
            chain_payload=_tradier_chain_payload(contract_overrides=contract_overrides)
        ),
    )
    service = OptionsLabService(market_data_provider=provider, provider_name="tradier")

    with patch("requests.sessions.Session.request") as request_mock:
        decision = service.evaluate_decision(
            {
                "symbol": "TEM",
                "marketDataProvider": "tradier",
                "strategy": "long_call",
                "expiration": "2026-06-19",
                "targetPrice": 65,
                "targetDate": "2026-06-19",
                "riskBudget": 600,
            }
        )

    assert decision.metadata.provider_name == "tradier"
    assert decision.metadata.live_provider_enabled is False
    assert decision.metadata.provider_capabilities["sourceType"] == "tradier_adapter_contract"
    assert decision.metadata.provider_capabilities["tradeableData"] is False
    assert decision.decision_grade is False
    assert decision.decision_label == "数据不足，禁止判断"
    assert expected_code in decision.fail_closed_reason_codes
    assert decision.data_quality.data_quality_tier == "insufficient"
    request_mock.assert_not_called()


def test_tradier_dry_run_sanitizes_provider_mapping_errors() -> None:
    provider = TradierOptionsProviderStub(
        config=OptionsLiveProviderConfig(
            live_providers_enabled=True,
            enabled_provider_keys=frozenset({"tradier"}),
            credentialed_provider_keys=frozenset({"tradier"}),
            dry_run_provider_keys=frozenset({"tradier"}),
        ),
        dry_run_response={
            "underlying": {"symbol": "TEM", "last": 52.4},
            "options": {"option": [{"symbol": "Bearer real-token-leak", "option_type": "call"}]},
        },
    )

    with pytest.raises(OptionsProviderUnavailable) as exc_info:
        provider.get_chain("TEM")

    assert exc_info.value.code == "options_provider_payload_unmappable"
    text = str(exc_info.value).lower()
    for blocked in ("real-token-leak", "bearer", "api_key", "apikey", "token", "secret", "request"):
        assert blocked not in text


def test_tradier_provider_exposes_no_broker_order_or_portfolio_mutation_path() -> None:
    provider = TradierOptionsProviderStub(
        config=OptionsLiveProviderConfig(
            live_providers_enabled=True,
            enabled_provider_keys=frozenset({"tradier"}),
            credentialed_provider_keys=frozenset({"tradier"}),
            dry_run_provider_keys=frozenset({"tradier"}),
        )
    )

    exposed_names = {name.lower() for name in dir(provider)}

    assert "place_order" not in exposed_names
    assert "submit_order" not in exposed_names
    assert "create_order" not in exposed_names
    assert "mutate_portfolio" not in exposed_names
    assert "sync_broker" not in exposed_names


def _assert_preflight_safety_contract(preflight: dict) -> None:
    assert preflight["liveHttpCallsEnabled"] is False
    assert preflight["liveProbe"]["networkCallExecuted"] is False
    assert preflight["liveProbe"]["noDefaultLiveHttpCalls"] is True
    assert preflight["liveProbe"]["rawCredentialValuesIncluded"] is False
    assert preflight["liveProbe"]["providerPayloadValuesIncluded"] is False
    assert preflight["liveProbe"]["responseBodiesIncluded"] is False
    assert preflight["brokerOrderPathEnabled"] is False
    assert preflight["portfolioMutationPathEnabled"] is False
    assert preflight["tradeableData"] is False
    assert preflight["providerCapabilities"]["liveEnabled"] is False
    assert preflight["providerCapabilities"]["tradeableData"] is False
    assert preflight["providerSlaReadiness"]["latencyState"] == "unknown"
    assert preflight["providerSlaReadiness"]["errorState"] == "unknown"
    assert preflight["providerSlaReadiness"]["freshnessState"] == "unknown"
    assert preflight["providerSlaReadiness"]["recentErrors"] == []
    assert preflight["providerSlaReadiness"]["readOnly"] is True
    assert preflight["providerSlaReadiness"]["noExternalCalls"] is True
    assert preflight["providerSlaReadiness"]["liveEnforcement"] is False
    assert preflight["checks"]["noLiveHttpCalls"] is True
    assert preflight["checks"]["noBrokerOrders"] is True
    assert preflight["checks"]["noPortfolioMutations"] is True
    assert preflight["checks"]["tradeableDataBlocked"] is True
    assert preflight["checks"]["rawPayloadReturned"] is False
    assert set(preflight["stagingCredentialProbeArtifact"]) == ALLOWED_STAGING_PROBE_ARTIFACT_KEYS
    text = _json_lower(preflight["stagingCredentialProbeArtifact"])
    for blocked in ("api_key", "apikey", "token", "secret", "password", "authorization", "dsn"):
        assert blocked not in text


def test_options_provider_preflight_disabled_state_is_fail_closed() -> None:
    preflight = build_options_provider_live_readiness_preflight("tradier")

    assert preflight["providerName"] == "tradier"
    assert preflight["readinessState"] == "disabled"
    assert preflight["reasonCode"] == "options_provider_disabled"
    assert preflight["checks"]["disabledByDefault"] is True
    assert preflight["liveProbe"] == {
        "enabled": False,
        "explicitOptIn": False,
        "reasonCode": "options_provider_live_probe_disabled_by_default",
        "timeoutSeconds": 2.0,
        "httpMethod": "HEAD_OR_GET",
        "networkCallExecuted": False,
        "noDefaultLiveHttpCalls": True,
        "requiresCredentialPresenceOnly": True,
        "rawCredentialValuesIncluded": False,
        "providerPayloadValuesIncluded": False,
        "responseBodiesIncluded": False,
    }
    _assert_preflight_safety_contract(preflight)


def test_options_provider_preflight_missing_credentials_state_is_sanitized() -> None:
    preflight = build_options_provider_live_readiness_preflight(
        "tradier",
        config=OptionsLiveProviderConfig(
            live_providers_enabled=True,
            enabled_provider_keys=frozenset({"tradier"}),
            credentialed_provider_keys=frozenset(),
        ),
    )

    assert preflight["readinessState"] == "missing_credentials"
    assert preflight["reasonCode"] == "options_provider_credentials_missing"
    assert preflight["credentialsPresent"] is False
    assert preflight["credentialContract"]["state"] == "missing"
    assert preflight["credentialContract"]["requiredCredentialCount"] == 1
    assert preflight["credentialContract"]["configuredCredentialCount"] == 0
    assert "credentials are not configured" in preflight["message"].lower()
    _assert_preflight_safety_contract(preflight)


@pytest.mark.parametrize("provider_name", sorted(LIVE_OPTIONS_PROVIDER_NAMES))
@pytest.mark.parametrize(
    ("credential_state", "expected_readiness", "expected_reason"),
    [
        ("missing", "missing_credentials", "options_provider_credentials_missing"),
        ("malformed", "malformed_credentials", "options_provider_credentials_malformed"),
        ("partial", "partial_credentials", "options_provider_credentials_partial"),
    ],
)
def test_live_provider_preflight_credential_contract_fails_closed_for_staging_states(
    provider_name: str,
    credential_state: str,
    expected_readiness: str,
    expected_reason: str,
) -> None:
    credentialed = frozenset({provider_name}) if credential_state == "present" else frozenset()
    malformed = frozenset({provider_name}) if credential_state == "malformed" else frozenset()
    partial = frozenset({provider_name}) if credential_state == "partial" else frozenset()

    with patch("requests.sessions.Session.request") as request_mock:
        preflight = build_options_provider_live_readiness_preflight(
            provider_name,
            config=OptionsLiveProviderConfig(
                live_providers_enabled=True,
                enabled_provider_keys=frozenset({provider_name}),
                credentialed_provider_keys=credentialed,
                malformed_credential_provider_keys=malformed,
                partial_credential_provider_keys=partial,
            ),
        )

    assert preflight["providerName"] == provider_name
    assert preflight["readinessState"] == expected_readiness
    assert preflight["reasonCode"] == expected_reason
    assert preflight["credentialsPresent"] is False
    assert preflight["credentialContract"] == {
        "state": credential_state,
        "reasonCode": expected_reason,
        "requiredCredentialCount": 1,
        "configuredCredentialCount": 0,
        "invalidCredentialCount": 1 if credential_state == "malformed" else 0,
        "partialCredentialCount": 1 if credential_state == "partial" else 0,
    }
    request_mock.assert_not_called()
    text = _json_lower(preflight)
    for blocked in ("api_key", "apikey", "token", "secret", "password", "authorization"):
        assert blocked not in text
    _assert_preflight_safety_contract(preflight)


@pytest.mark.parametrize("provider_name", sorted(LIVE_OPTIONS_PROVIDER_NAMES))
def test_live_provider_preflight_present_credentials_are_sanitized_and_still_non_live(provider_name: str) -> None:
    with patch("requests.sessions.Session.request") as request_mock:
        preflight = build_options_provider_live_readiness_preflight(
            provider_name,
            config=OptionsLiveProviderConfig(
                live_providers_enabled=True,
                enabled_provider_keys=frozenset({provider_name}),
                credentialed_provider_keys=frozenset({provider_name}),
            ),
        )

    assert preflight["providerName"] == provider_name
    assert preflight["readinessState"] == "live_credentials_present_live_calls_disabled"
    assert preflight["reasonCode"] == "options_provider_live_calls_disabled"
    assert preflight["credentialsPresent"] is True
    assert preflight["credentialContract"] == {
        "state": "present",
        "reasonCode": "options_provider_credentials_present",
        "requiredCredentialCount": 1,
        "configuredCredentialCount": 1,
        "invalidCredentialCount": 0,
        "partialCredentialCount": 0,
    }
    assert preflight["liveProbe"]["enabled"] is False
    assert preflight["liveProbe"]["explicitOptIn"] is False
    assert preflight["liveProbe"]["reasonCode"] == "options_provider_live_probe_disabled_by_default"
    assert preflight["payloadMappable"] is None
    request_mock.assert_not_called()
    text = _json_lower(preflight)
    for blocked in ("api_key", "apikey", "token", "secret", "password", "authorization"):
        assert blocked not in text
    _assert_preflight_safety_contract(preflight)


def test_live_provider_preflight_operator_live_probe_opt_in_requires_credentials_without_calling_network() -> None:
    with patch("requests.sessions.Session.request") as request_mock:
        preflight = build_options_provider_live_readiness_preflight(
            "tradier",
            config=OptionsLiveProviderConfig(
                live_providers_enabled=True,
                enabled_provider_keys=frozenset({"tradier"}),
                malformed_credential_provider_keys=frozenset({"tradier"}),
                live_probe_provider_keys=frozenset({"tradier"}),
                live_probe_timeout_seconds=4.5,
            ),
        )

    assert preflight["readinessState"] == "malformed_credentials"
    assert preflight["liveProbe"]["enabled"] is False
    assert preflight["liveProbe"]["explicitOptIn"] is True
    assert preflight["liveProbe"]["reasonCode"] == "options_provider_credentials_malformed"
    assert preflight["liveProbe"]["timeoutSeconds"] == 4.5
    request_mock.assert_not_called()
    text = _json_lower(preflight)
    for blocked in ("api_key", "apikey", "token", "secret", "password", "authorization"):
        assert blocked not in text
    _assert_preflight_safety_contract(preflight)


def test_live_provider_preflight_operator_live_probe_ready_is_opt_in_and_non_executing() -> None:
    with patch("requests.sessions.Session.request") as request_mock:
        preflight = build_options_provider_live_readiness_preflight(
            "tradier",
            config=OptionsLiveProviderConfig(
                live_providers_enabled=True,
                enabled_provider_keys=frozenset({"tradier"}),
                credentialed_provider_keys=frozenset({"tradier"}),
                live_probe_provider_keys=frozenset({"tradier"}),
                live_probe_timeout_seconds=30,
            ),
        )

    assert preflight["readinessState"] == "live_credentials_present_live_calls_disabled"
    assert preflight["liveHttpCallsEnabled"] is False
    assert preflight["liveProbe"]["enabled"] is False
    assert preflight["liveProbe"]["explicitOptIn"] is True
    assert preflight["liveProbe"]["reasonCode"] == "options_provider_staging_probe_artifact_missing"
    assert preflight["liveProbe"]["timeoutSeconds"] == 5.0
    assert preflight["liveProbe"]["networkCallExecuted"] is False
    assert preflight["stagingCredentialProbeArtifact"]["status"] == "missing"
    request_mock.assert_not_called()
    _assert_preflight_safety_contract(preflight)


def test_options_provider_preflight_env_live_probe_opt_in_is_presence_only_and_sanitized() -> None:
    config = OptionsLiveProviderConfig.from_env(
        {
            "OPTIONS_LIVE_PROVIDERS_ENABLED": "1",
            "OPTIONS_LIVE_PROVIDER_KEYS": "tradier",
            "OPTIONS_LIVE_PROVIDER_PROBE_KEYS": "tradier",
            "OPTIONS_LIVE_PROVIDER_PROBE_TIMEOUT_SECONDS": "0.01",
            "TRADIER_API_TOKEN": "valid_synthetic_readiness_value_1234567890",
        }
    )

    with patch("requests.sessions.Session.request") as request_mock:
        preflight = build_options_provider_live_readiness_preflight("tradier", config=config)

    assert preflight["credentialsPresent"] is True
    assert preflight["liveProbe"]["enabled"] is False
    assert preflight["liveProbe"]["explicitOptIn"] is True
    assert preflight["liveProbe"]["reasonCode"] == "options_provider_staging_probe_artifact_missing"
    assert preflight["liveProbe"]["timeoutSeconds"] == 0.25
    assert preflight["stagingCredentialProbeArtifact"]["status"] == "missing"
    request_mock.assert_not_called()
    text = _json_lower(preflight)
    for blocked in ("valid_synthetic_readiness_value", "tradier_api_token", "api_token", "token"):
        assert blocked not in text
    _assert_preflight_safety_contract(preflight)


def test_legacy_tradier_env_toggles_remain_fail_closed_without_live_calls_or_secret_leakage() -> None:
    config = OptionsLiveProviderConfig.from_env(
        {
            "OPTIONS_TRADIER_ENABLED": "1",
            "OPTIONS_TRADIER_DRY_RUN_ENABLED": "1",
            "OPTIONS_TRADIER_LIVE_PROBE_ENABLED": "1",
            "TRADIER_API_TOKEN": "valid_synthetic_readiness_value_legacy_1234567890",
        }
    )

    with patch("requests.sessions.Session.request") as request_mock:
        preflight = build_options_provider_live_readiness_preflight("tradier", config=config)

    assert preflight["liveProvidersEnabled"] is False
    assert preflight["providerEnabled"] is True
    assert preflight["credentialsPresent"] is True
    assert preflight["dryRunEnabled"] is True
    assert preflight["readinessState"] == "disabled"
    assert preflight["reasonCode"] == "options_provider_disabled"
    assert preflight["liveProbe"]["enabled"] is False
    assert preflight["liveProbe"]["explicitOptIn"] is True
    assert preflight["liveProbe"]["reasonCode"] == "options_provider_disabled"
    assert preflight["payloadMappable"] is None
    request_mock.assert_not_called()
    text = _json_lower(preflight)
    for blocked in (
        "valid_synthetic_readiness_value_legacy",
        "tradier_api_token",
        "api_token",
        "token",
        "secret",
    ):
        assert blocked not in text
    _assert_preflight_safety_contract(preflight)


def test_staging_probe_artifact_accepts_sanitized_operator_evidence_and_enables_probe_contract_only() -> None:
    artifact = {
        "providerId": "TRADIER",
        "status": "passed",
        "timestamp": "2026-05-06T12:34:56Z",
        "timeoutSeconds": 3,
        "reasonCodes": [
            "named_staging_provider_recorded",
            "live_probe_opt_in_recorded",
            "probe_result_sanitized",
        ],
    }

    with patch("requests.sessions.Session.request") as request_mock:
        preflight = build_options_provider_live_readiness_preflight(
            "tradier",
            config=OptionsLiveProviderConfig(
                live_providers_enabled=True,
                enabled_provider_keys=frozenset({"tradier"}),
                credentialed_provider_keys=frozenset({"tradier"}),
                live_probe_provider_keys=frozenset({"tradier"}),
                live_probe_timeout_seconds=3,
            ),
            staging_probe_artifact=artifact,
        )

    artifact_status = preflight["stagingCredentialProbeArtifact"]
    assert set(artifact_status) == ALLOWED_STAGING_PROBE_ARTIFACT_KEYS
    assert artifact_status == {
        "providerId": "tradier",
        "status": "accepted",
        "timestamp": "2026-05-06T12:34:56+00:00",
        "timeoutSeconds": 3.0,
        "reasonCodes": [
            "named_staging_provider_recorded",
            "live_probe_opt_in_recorded",
            "probe_result_sanitized",
        ],
    }
    assert preflight["checks"]["stagingProbeArtifactAccepted"] is True
    assert preflight["liveProbe"]["enabled"] is True
    assert preflight["liveProbe"]["reasonCode"] == "options_provider_live_probe_operator_opt_in_ready"
    assert preflight["liveProbe"]["networkCallExecuted"] is False
    assert preflight["liveHttpCallsEnabled"] is False
    request_mock.assert_not_called()
    _assert_preflight_safety_contract(preflight)


@pytest.mark.parametrize(
    "artifact",
    [
        {
            "providerId": "tradier",
            "status": "passed",
            "timestamp": "2026-05-06T12:34:56Z",
            "timeoutSeconds": 3,
            "reasonCodes": ["probe_result_sanitized"],
            "apiKey": "must-not-leak",
        },
        {
            "providerId": "tradier",
            "status": "passed",
            "timestamp": "2026-05-06T12:34:56Z",
            "timeoutSeconds": 3,
            "reasonCodes": ["probe_result_sanitized"],
            "env": "TRADIER_API_TOKEN=must-not-leak",
        },
        {
            "providerId": "tradier",
            "status": "passed",
            "timestamp": "2026-05-06T12:34:56Z",
            "timeoutSeconds": 3,
            "reasonCodes": ["probe_result_sanitized"],
            "dsn": "postgres://user:pass@db.internal/provider",
        },
        {
            "providerId": "tradier",
            "status": "passed",
            "timestamp": "2026-05-06T12:34:56Z",
            "timeoutSeconds": 3,
            "reasonCodes": ["probe_result_sanitized"],
            "providerPayload": {"authorization": "Bearer must-not-leak"},
        },
        {
            "providerId": "tradier",
            "status": "passed",
            "timestamp": "2026-05-06T12:34:56Z",
            "timeoutSeconds": 3,
            "reasonCodes": ["token_probe_passed"],
        },
    ],
)
def test_staging_probe_artifact_rejects_secret_env_dsn_and_provider_payload_values(artifact: dict) -> None:
    with patch("requests.sessions.Session.request") as request_mock:
        preflight = build_options_provider_live_readiness_preflight(
            "tradier",
            config=OptionsLiveProviderConfig(
                live_providers_enabled=True,
                enabled_provider_keys=frozenset({"tradier"}),
                credentialed_provider_keys=frozenset({"tradier"}),
                live_probe_provider_keys=frozenset({"tradier"}),
            ),
            staging_probe_artifact=artifact,
        )

    artifact_status = preflight["stagingCredentialProbeArtifact"]
    assert set(artifact_status) == ALLOWED_STAGING_PROBE_ARTIFACT_KEYS
    assert artifact_status["status"] in {"rejected", "malformed"}
    assert preflight["liveProbe"]["enabled"] is False
    assert preflight["liveHttpCallsEnabled"] is False
    request_mock.assert_not_called()
    text = _json_lower(preflight)
    for blocked in ("must-not-leak", "tradier_api_token", "api_key", "apikey", "token_probe", "postgres://", "bearer"):
        assert blocked not in text
    _assert_preflight_safety_contract(preflight)


@pytest.mark.parametrize(
    ("artifact", "expected_status", "expected_reason"),
    [
        (None, "missing", "options_provider_staging_probe_artifact_missing"),
        ("not-a-mapping", "malformed", "options_provider_staging_probe_artifact_malformed"),
        (
            {
                "providerId": "ibkr",
                "status": "passed",
                "timestamp": "2026-05-06T12:34:56Z",
                "timeoutSeconds": 3,
                "reasonCodes": ["probe_result_sanitized"],
            },
            "rejected",
            "options_provider_staging_probe_artifact_provider_mismatch",
        ),
        (
            {
                "providerId": "tradier",
                "status": "passed",
                "timestamp": "not-a-date",
                "timeoutSeconds": 3,
                "reasonCodes": ["probe_result_sanitized"],
            },
            "malformed",
            "options_provider_staging_probe_artifact_timestamp_invalid",
        ),
        (
            {
                "providerId": "tradier",
                "status": "passed",
                "timestamp": "2026-05-06T12:34:56Z",
                "timeoutSeconds": 30,
                "reasonCodes": ["probe_result_sanitized"],
            },
            "malformed",
            "options_provider_staging_probe_artifact_timeout_invalid",
        ),
    ],
)
def test_staging_probe_artifact_missing_or_malformed_remains_non_accepted(
    artifact: dict | str | None,
    expected_status: str,
    expected_reason: str,
) -> None:
    with patch("requests.sessions.Session.request") as request_mock:
        preflight = build_options_provider_live_readiness_preflight(
            "tradier",
            config=OptionsLiveProviderConfig(
                live_providers_enabled=True,
                enabled_provider_keys=frozenset({"tradier"}),
                credentialed_provider_keys=frozenset({"tradier"}),
                live_probe_provider_keys=frozenset({"tradier"}),
            ),
            staging_probe_artifact=artifact,  # type: ignore[arg-type]
        )

    artifact_status = preflight["stagingCredentialProbeArtifact"]
    assert artifact_status["status"] == expected_status
    assert artifact_status["reasonCodes"] == [expected_reason]
    assert preflight["checks"]["stagingProbeArtifactAccepted"] is False
    assert preflight["liveProbe"]["enabled"] is False
    assert preflight["liveProbe"]["reasonCode"] == expected_reason
    request_mock.assert_not_called()
    _assert_preflight_safety_contract(preflight)


def test_options_provider_preflight_malformed_credentials_fail_closed_without_live_calls() -> None:
    with patch("requests.sessions.Session.request") as request_mock:
        preflight = build_options_provider_live_readiness_preflight(
            "tradier",
            config=OptionsLiveProviderConfig(
                live_providers_enabled=True,
                enabled_provider_keys=frozenset({"tradier"}),
                malformed_credential_provider_keys=frozenset({"tradier"}),
            ),
        )

    assert preflight["readinessState"] == "malformed_credentials"
    assert preflight["reasonCode"] == "options_provider_credentials_malformed"
    assert preflight["credentialsPresent"] is False
    assert preflight["credentialContract"]["state"] == "malformed"
    assert preflight["credentialContract"]["invalidCredentialCount"] == 1
    assert preflight["credentialContract"]["partialCredentialCount"] == 0
    request_mock.assert_not_called()
    text = _json_lower(preflight)
    for blocked in ("api_key", "apikey", "token", "secret", "must-not-leak"):
        assert blocked not in text
    _assert_preflight_safety_contract(preflight)


def test_options_provider_preflight_partial_credentials_fail_closed_without_live_calls() -> None:
    with patch("requests.sessions.Session.request") as request_mock:
        preflight = build_options_provider_live_readiness_preflight(
            "tradier",
            config=OptionsLiveProviderConfig(
                live_providers_enabled=True,
                enabled_provider_keys=frozenset({"tradier"}),
                partial_credential_provider_keys=frozenset({"tradier"}),
            ),
        )

    assert preflight["readinessState"] == "partial_credentials"
    assert preflight["reasonCode"] == "options_provider_credentials_partial"
    assert preflight["credentialsPresent"] is False
    assert preflight["credentialContract"]["state"] == "partial"
    assert preflight["credentialContract"]["configuredCredentialCount"] == 0
    assert preflight["credentialContract"]["partialCredentialCount"] == 1
    request_mock.assert_not_called()
    _assert_preflight_safety_contract(preflight)


def test_options_provider_preflight_env_malformed_credentials_are_classified_without_values() -> None:
    config = OptionsLiveProviderConfig.from_env(
        {
            "OPTIONS_LIVE_PROVIDERS_ENABLED": "1",
            "OPTIONS_LIVE_PROVIDER_KEYS": "tradier",
            "TRADIER_API_TOKEN": "placeholder",
        }
    )

    preflight = build_options_provider_live_readiness_preflight("tradier", config=config)

    assert preflight["readinessState"] == "malformed_credentials"
    assert preflight["reasonCode"] == "options_provider_credentials_malformed"
    assert preflight["credentialContract"]["state"] == "malformed"
    text = _json_lower(preflight)
    for blocked in ("placeholder", "tradier_api_token", "api_token", "token", "secret"):
        assert blocked not in text
    _assert_preflight_safety_contract(preflight)


def test_options_provider_preflight_dry_run_enabled_never_marks_data_live_or_tradeable() -> None:
    with patch("requests.sessions.Session.request") as request_mock:
        preflight = build_options_provider_live_readiness_preflight(
            "tradier",
            config=OptionsLiveProviderConfig(
                live_providers_enabled=True,
                enabled_provider_keys=frozenset({"tradier"}),
                credentialed_provider_keys=frozenset({"tradier"}),
                dry_run_provider_keys=frozenset({"tradier"}),
            ),
        )

    assert preflight["readinessState"] == "dry_run_enabled"
    assert preflight["reasonCode"] == "options_provider_dry_run_enabled"
    assert preflight["dryRunEnabled"] is True
    assert preflight["payloadMappable"] is True
    assert preflight["providerCapabilities"]["sourceType"] == "delayed_dry_run"
    assert preflight["dryRunDataQuality"]["tradeable"] is False
    assert preflight["dryRunFreshness"] == "delayed_dry_run"
    assert preflight["providerSlaReadiness"]["readOnly"] is True
    request_mock.assert_not_called()
    _assert_preflight_safety_contract(preflight)


def test_options_provider_preflight_live_credentials_present_still_blocks_live_calls() -> None:
    preflight = build_options_provider_live_readiness_preflight(
        "tradier",
        config=OptionsLiveProviderConfig(
            live_providers_enabled=True,
            enabled_provider_keys=frozenset({"tradier"}),
            credentialed_provider_keys=frozenset({"tradier"}),
            dry_run_provider_keys=frozenset(),
        ),
    )

    assert preflight["readinessState"] == "live_credentials_present_live_calls_disabled"
    assert preflight["reasonCode"] == "options_provider_live_calls_disabled"
    assert preflight["credentialsPresent"] is True
    assert preflight["credentialContract"]["state"] == "present"
    assert preflight["credentialContract"]["configuredCredentialCount"] == 1
    assert preflight["dryRunEnabled"] is False
    _assert_preflight_safety_contract(preflight)


def test_options_provider_preflight_malformed_payload_returns_sanitized_state() -> None:
    preflight = build_options_provider_live_readiness_preflight(
        "tradier",
        config=OptionsLiveProviderConfig(
            live_providers_enabled=True,
            enabled_provider_keys=frozenset({"tradier"}),
            credentialed_provider_keys=frozenset({"tradier"}),
            dry_run_provider_keys=frozenset({"tradier"}),
        ),
        dry_run_response={
            "underlying": {"symbol": "TEM", "last": 52.4},
            "options": {"option": [{"symbol": "Bearer real-token-leak", "option_type": "call"}]},
        },
    )

    assert preflight["readinessState"] == "malformed_provider_payload"
    assert preflight["reasonCode"] == "options_provider_payload_unmappable"
    assert preflight["payloadMappable"] is False
    text = _json_lower(preflight)
    for blocked in ("real-token-leak", "bearer", "api_key", "apikey", "token", "secret", "requesturl"):
        assert blocked not in text
    _assert_preflight_safety_contract(preflight)


def test_controlled_circuit_block_evidence_does_not_make_live_provider_available() -> None:
    DatabaseManager.reset_instance()
    db = DatabaseManager(db_url="sqlite:///:memory:")
    observer = ProviderCircuitObserver(db=db)
    db.transition_provider_circuit_state(
        provider="tradier",
        provider_category="options",
        route_family="options_lab",
        to_state="open",
        reason_bucket="timeout",
    )
    provider = create_options_market_data_provider(
        "tradier",
        live_provider_config=OptionsLiveProviderConfig(
            live_providers_enabled=True,
            enabled_provider_keys=frozenset({"tradier"}),
            credentialed_provider_keys=frozenset({"tradier"}),
        ),
    )

    try:
        with patch("requests.sessions.Session.request") as request_mock:
            decision = observer.build_controlled_enforcement_decision(
                provider="tradier",
                provider_category="options",
                route_family="options_lab",
                controlled_enforcement_enabled=True,
                controlled_provider_categories=("options",),
                controlled_route_families=("options_lab",),
            )
            with pytest.raises(OptionsProviderUnavailable) as exc_info:
                provider.get_chain("TEM")

        assert decision["controlled_enforcement_status"] == "blocked"
        assert decision["would_block_call"] is True
        assert decision["would_block_if_enforced"] is True
        assert decision["enforcement_block_reason_code"] == "timeout"
        assert exc_info.value.code == "options_provider_dry_run_not_enabled"
        request_mock.assert_not_called()
    finally:
        DatabaseManager.reset_instance()


def test_options_provider_preflight_sanitizes_provider_error_text() -> None:
    preflight = build_options_provider_live_readiness_preflight(
        "ibkr",
        config=OptionsLiveProviderConfig(
            live_providers_enabled=True,
            enabled_provider_keys=frozenset({"ibkr"}),
            credentialed_provider_keys=frozenset({"ibkr"}),
            dry_run_provider_keys=frozenset({"ibkr"}),
        ),
    )

    assert preflight["readinessState"] == "sanitized_provider_error"
    assert preflight["reasonCode"] == "options_provider_not_enabled"
    assert preflight["message"] == "Options live provider adapter has no network implementation."
    text = _json_lower(preflight)
    for blocked in ("sk-live-token", "provider.example", "apikey=secret", "authorization: bearer", "rawproviderpayload"):
        assert blocked not in text
    _assert_preflight_safety_contract(preflight)


def test_options_provider_preflight_keeps_non_tradeable_status_explicit_on_disabled_live_providers() -> None:
    preflight = build_options_provider_live_readiness_preflight(
        "tradier",
        config=OptionsLiveProviderConfig(
            live_providers_enabled=True,
            enabled_provider_keys=frozenset({"tradier"}),
            credentialed_provider_keys=frozenset({"tradier"}),
        ),
    )

    assert preflight["providerSlaReadiness"]["readOnly"] is True
    assert preflight["providerSlaReadiness"]["noExternalCalls"] is True
    assert preflight["providerSlaReadiness"]["liveEnforcement"] is False
    assert preflight["tradeableData"] is False
    assert preflight["providerCapabilities"]["tradeableData"] is False


def _json_lower(payload: dict) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
