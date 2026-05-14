# -*- coding: utf-8 -*-
"""Tests for inert custom source contract registry support."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.services.custom_source_contracts import (
    DEFAULT_CUSTOM_SOURCE_DISABLED_REASON,
    GENERIC_SAFE_PANEL_PARSER_ID,
    get_custom_source_parser_contract,
    list_custom_source_parser_contracts,
    normalize_custom_source_contract,
    parse_custom_source_fixture_payload,
)


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "custom_sources"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_parser_registry_contains_expected_generic_safe_shape() -> None:
    contracts = list_custom_source_parser_contracts()

    assert [item.parser_id for item in contracts] == [GENERIC_SAFE_PANEL_PARSER_ID]
    parser = get_custom_source_parser_contract(GENERIC_SAFE_PANEL_PARSER_ID)
    assert parser is not None
    assert parser.target_dto_family == "generic_panel_series_v1"
    assert parser.required_fields == ("symbol", "seriesId", "value", "asOf")
    assert parser.optional_fields == ("label", "unit")
    assert "missing_credentials" in parser.unavailable_reason_buckets


def test_fixture_parser_accepts_generic_safe_shape_without_runtime_wiring() -> None:
    payload = parse_custom_source_fixture_payload(
        GENERIC_SAFE_PANEL_PARSER_ID,
        _load_fixture("generic_safe_panel_payload.json"),
    )

    assert payload["parserId"] == GENERIC_SAFE_PANEL_PARSER_ID
    assert payload["targetDtoFamily"] == "generic_panel_series_v1"
    assert payload["isEvidence"] is True
    assert payload["unavailableReason"] is None
    assert payload["observations"] == [
        {
            "symbol": "MSFT",
            "seriesId": "close",
            "value": 401.25,
            "asOf": "2026-05-14T09:30:00+08:00",
            "label": "Close",
            "unit": "USD",
        },
        {
            "symbol": "AAPL",
            "seriesId": "close",
            "value": 210.1,
            "asOf": "2026-05-14T09:30:00+08:00",
            "label": "Close",
            "unit": "USD",
        },
    ]


def test_unknown_parser_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown parserId"):
        normalize_custom_source_contract(
            {
                "customSourceId": "demo-source",
                "panelId": "market_overview:demo",
                "parserId": "unknown-parser",
                "capability": "panel_snapshot",
                "allowedSymbols": ["MSFT"],
                "freshnessWindow": "PT15M",
                "credentialRef": "env:CUSTOM_SOURCE_DEMO",
            }
        )


def test_missing_mapping_is_rejected() -> None:
    with pytest.raises(ValueError, match="Missing symbol or series mapping"):
        normalize_custom_source_contract(
            {
                "customSourceId": "demo-source",
                "panelId": "market_overview:demo",
                "parserId": GENERIC_SAFE_PANEL_PARSER_ID,
                "capability": "panel_snapshot",
                "freshnessWindow": "PT15M",
                "credentialRef": "env:CUSTOM_SOURCE_DEMO",
            }
        )


def test_arbitrary_url_alone_is_not_runtime_eligible() -> None:
    normalized = normalize_custom_source_contract(
        {
            "customSourceId": "demo-source",
            "panelId": "market_overview:demo",
            "parserId": GENERIC_SAFE_PANEL_PARSER_ID,
            "capability": "panel_snapshot",
            "allowedSymbols": ["MSFT"],
            "freshnessWindow": "PT15M",
            "runtimeEligible": True,
            "baseUrl": "https://demo.example.test/api/v1/panel",
            "credentialRef": "env:CUSTOM_SOURCE_DEMO",
        }
    )

    assert normalized["sourceType"] == "custom"
    assert normalized["runtimeEligible"] is False
    assert normalized["disabledReason"] == DEFAULT_CUSTOM_SOURCE_DISABLED_REASON


def test_normalized_output_never_leaks_raw_credentials_or_secret_urls() -> None:
    normalized = normalize_custom_source_contract(
        {
            "customSourceId": "secret-source",
            "panelId": "market_overview:demo",
            "parserId": GENERIC_SAFE_PANEL_PARSER_ID,
            "capability": "panel_snapshot",
            "allowedSymbols": ["MSFT"],
            "seriesIds": ["close"],
            "freshnessWindow": "PT15M",
            "baseUrl": "https://alice:super-secret@example.test/panel?apikey=raw-key&token=raw-token",
            "credential": "raw-credential",
            "secret": "raw-secret",
            "credentialRef": "env:CUSTOM_SOURCE_SECRET",
        }
    )

    serialized = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    for forbidden in (
        "raw-key",
        "raw-token",
        "raw-credential",
        "raw-secret",
        "alice:super-secret",
        "apikey=",
        "token=",
    ):
        assert forbidden not in serialized
    assert normalized["credentialRef"] == "env:CUSTOM_SOURCE_SECRET"


def test_disabled_by_default_remains_true_even_when_input_requests_enablement() -> None:
    normalized = normalize_custom_source_contract(
        {
            "customSourceId": "demo-source",
            "panelId": "rotation:demo",
            "parserId": GENERIC_SAFE_PANEL_PARSER_ID,
            "capability": "panel_snapshot",
            "allowedSymbols": ["QQQ"],
            "seriesIds": ["breadth"],
            "freshnessWindow": "PT30M",
            "runtimeEligible": True,
            "disabledReason": "user requested enablement",
            "credentialRef": "env:CUSTOM_SOURCE_QQQ",
        }
    )

    assert normalized["runtimeEligible"] is False
    assert normalized["disabledReason"] == DEFAULT_CUSTOM_SOURCE_DISABLED_REASON


def test_registry_import_has_no_runtime_or_provider_side_effects() -> None:
    script = """
import json
import src.services.custom_source_contracts
blocked = [
    "src.services.market_overview_service",
    "src.services.liquidity_monitor_service",
    "src.services.market_rotation_radar_service",
    "src.services.market_scanner_service",
    "src.services.official_macro_transport",
    "src.services.market_cache",
    "api.v1.endpoints.market",
]
print(json.dumps({name: name in __import__('sys').modules for name in blocked}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    imported = json.loads(completed.stdout)
    assert imported == {name: False for name in imported}
