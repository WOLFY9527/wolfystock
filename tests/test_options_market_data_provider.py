# -*- coding: utf-8 -*-
"""Options market data provider adapter contract tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.services.options_lab_service import OptionsLabProviderUnavailable, OptionsLabService
from src.services.options_market_data_provider import (
    ALLOWED_OPTIONS_PROVIDER_KEYS,
    DelayedFixtureOptionsProvider,
    LIVE_OPTIONS_PROVIDER_NAMES,
    MalformedGreeksFixtureOptionsProvider,
    OptionsLiveProviderConfig,
    OptionsProviderUnavailable,
    SyntheticFixtureOptionsProvider,
    TradierOptionsProviderStub,
    build_options_provider_live_readiness_preflight,
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


@pytest.mark.parametrize("provider_name", ["tradier", "ibkr", "polygon"])
def test_live_provider_stubs_are_disabled_by_default(provider_name: str) -> None:
    provider = create_options_market_data_provider(provider_name)

    assert provider.provider_name == provider_name
    assert provider.capabilities.live_enabled is False
    assert provider.capabilities.fixture_only is False
    assert provider.capabilities.tradeable_data is False
    assert "live_stub" in provider.capabilities.notes

    with pytest.raises(OptionsProviderUnavailable) as exc_info:
        provider.get_chain("TEM")

    assert exc_info.value.provider_name == provider_name
    assert exc_info.value.code == "options_provider_disabled"


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
    assert chain["providerName"] == "tradier"
    assert chain["source"] == "tradier_dry_run_fixture"
    assert chain["providerCapabilities"]["liveEnabled"] is False
    assert chain["providerCapabilities"]["tradeableData"] is False
    assert chain["dataQuality"]["tradeable"] is False
    assert [item["date"] for item in expirations] == ["2026-06-19", "2026-08-21"]
    assert {contract["side"] for contract in chain["contracts"]} == {"call", "put"}
    assert all(contract["expiration"] == "2026-06-19" for contract in chain["contracts"])
    assert chain["contracts"][0]["impliedVolatility"] == 0.62
    assert chain["contracts"][0]["greeks"]["delta"] == 0.61
    assert all(contract["dataQuality"]["tradeable"] is False for contract in chain["contracts"])
    assert all(contract["freshness"] == "delayed_dry_run" for contract in chain["contracts"])


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
    assert preflight["brokerOrderPathEnabled"] is False
    assert preflight["portfolioMutationPathEnabled"] is False
    assert preflight["tradeableData"] is False
    assert preflight["providerCapabilities"]["liveEnabled"] is False
    assert preflight["providerCapabilities"]["tradeableData"] is False
    assert preflight["providerSlaReadiness"]["latencyState"] == "unknown"
    assert preflight["providerSlaReadiness"]["errorState"] == "unknown"
    assert preflight["providerSlaReadiness"]["freshnessState"] == "unknown"
    assert preflight["providerSlaReadiness"]["recentErrors"] == []


def test_options_provider_preflight_disabled_state_is_fail_closed() -> None:
    preflight = build_options_provider_live_readiness_preflight("tradier")

    assert preflight["providerName"] == "tradier"
    assert preflight["readinessState"] == "disabled"
    assert preflight["reasonCode"] == "options_provider_disabled"
    assert preflight["checks"]["disabledByDefault"] is True
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
    assert preflight["payloadMappable"] is None
    request_mock.assert_not_called()
    text = _json_lower(preflight)
    for blocked in ("api_key", "apikey", "token", "secret", "password", "authorization"):
        assert blocked not in text
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
