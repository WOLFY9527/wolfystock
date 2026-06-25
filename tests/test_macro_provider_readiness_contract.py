# -*- coding: utf-8 -*-
"""Macro/FRED provider readiness contract tests."""

from __future__ import annotations

import json

from src.services.macro_provider_readiness_service import (
    MACRO_PROVIDER_READINESS_CONTRACT_VERSION,
    build_macro_provider_readiness_contract,
)


EXPECTED_CATEGORY_KEYS = {
    "rates",
    "inflation",
    "labor",
    "growth",
    "liquidity",
    "credit",
    "usd_currency",
    "recession",
}


FORBIDDEN_PUBLIC_MARKERS = (
    "endpointHost",
    "requestId",
    "traceId",
    "cacheKey",
    "rawPayload",
    "raw_payload",
    "apiKeyPresent",
    "credential",
    "token",
    "secret",
    "FRED_API_KEY=",
    "fred-secret",
)


def _categories_by_key(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        str(item["categoryKey"]): item
        for item in payload["categories"]  # type: ignore[index]
    }


def test_macro_readiness_defaults_to_disabled_without_enabling_fred() -> None:
    payload = build_macro_provider_readiness_contract(env={})

    assert payload["contractVersion"] == MACRO_PROVIDER_READINESS_CONTRACT_VERSION
    assert payload["provider"]["providerKey"] == "fred"
    assert payload["provider"]["state"] == "disabled_by_flag"
    assert payload["provider"]["configured"] is False
    assert payload["provider"]["enabled"] is False
    assert payload["networkCallsEnabled"] is False
    assert payload["runtimeProviderCalls"] is False

    categories = _categories_by_key(payload)
    assert set(categories) == EXPECTED_CATEGORY_KEYS
    assert categories["rates"]["seriesIds"] == ["DGS2", "DGS10", "DGS30", "DFF", "SOFR", "T10Y2Y", "T10Y3M"]
    assert categories["inflation"]["seriesIds"] == ["CPIAUCSL", "PPIACO"]
    assert categories["liquidity"]["seriesIds"] == ["WALCL", "RRPONTSYD", "WTREGEN", "WRESBAL"]
    assert categories["usd_currency"]["seriesIds"] == ["DTWEXBGS"]
    assert {item["state"] for item in categories.values()} == {"disabled_by_flag"}

    serialized = json.dumps(payload, ensure_ascii=False)
    assert "requiredEnvVars" not in serialized
    assert "requiredFlags" not in serialized
    for marker in FORBIDDEN_PUBLIC_MARKERS:
        assert marker not in serialized


def test_macro_readiness_admin_lists_required_names_without_values_when_env_missing() -> None:
    payload = build_macro_provider_readiness_contract(
        env={"FRED_MACRO_PROVIDER_ENABLED": "true"},
        include_admin_diagnostics=True,
    )

    assert payload["provider"]["state"] == "missing_env"
    assert payload["admin"]["requiredEnvVars"] == ["FRED_API_KEY"]
    assert payload["admin"]["requiredFlags"] == ["FRED_MACRO_PROVIDER_ENABLED"]
    assert payload["admin"]["nextActions"]
    assert all("nextAction" in item for item in payload["categories"])

    serialized = json.dumps(payload, ensure_ascii=False)
    assert "FRED_API_KEY" in serialized
    assert "FRED_MACRO_PROVIDER_ENABLED" in serialized
    assert "true" not in serialized
    for marker in ("apiKeyPresent", "endpointHost", "requestId", "traceId", "rawPayload", "fred-secret"):
        assert marker not in serialized


def test_macro_readiness_states_are_derived_from_injected_series_statuses_without_values() -> None:
    payload = build_macro_provider_readiness_contract(
        env={
            "FRED_MACRO_PROVIDER_ENABLED": "true",
            "FRED_API_KEY": "fred-secret-test-key",
        },
        series_states={
            "DGS2": "available",
            "DGS10": "available",
            "DGS30": "available",
            "DFF": "available",
            "SOFR": "available",
            "T10Y2Y": "available",
            "T10Y3M": "available",
            "CPIAUCSL": "missing",
            "PPIACO": "missing",
            "WALCL": "stale",
            "RRPONTSYD": "available",
            "WTREGEN": "available",
            "WRESBAL": "available",
            "BAMLH0A0HYM2": "available",
            "DTWEXBGS": "available",
        },
        include_admin_diagnostics=True,
    )

    categories = _categories_by_key(payload)
    assert categories["rates"]["state"] == "available"
    assert categories["inflation"]["state"] == "missing"
    assert categories["liquidity"]["state"] == "stale"
    assert categories["credit"]["state"] == "available"
    assert categories["usd_currency"]["state"] == "available"
    assert categories["labor"]["state"] == "not_configured"
    assert categories["growth"]["state"] == "not_configured"
    assert categories["recession"]["state"] == "not_configured"
    assert payload["provider"]["state"] == "stale"

    serialized = json.dumps(payload, ensure_ascii=False)
    for fake_value in ("4.41", "321.0", "5.33", "3.7", "unemployment rate", "recession probability", "macro score"):
        assert fake_value not in serialized.lower()
    for marker in FORBIDDEN_PUBLIC_MARKERS:
        assert marker not in serialized
