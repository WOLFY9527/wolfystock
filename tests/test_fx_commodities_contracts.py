# -*- coding: utf-8 -*-
"""Tests for inert FX / commodities contracts and mocked fixture parsing."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from src.services.fx_commodities_contracts import (
    FX_COMMODITY_SYMBOLS,
    SAFE_UNAVAILABLE_REASON_BUCKETS,
    get_fx_commodity_contract,
    list_fx_commodity_contracts,
    parse_mocked_fx_commodities_payload,
)
from src.services.market_data_source_registry import CANONICAL_SOURCE_TYPES


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "fx_commodities"
MODULE_PATH = REPO_ROOT / "src" / "services" / "fx_commodities_contracts.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "src.services.market_overview_service",
    "src.services.market_cache",
    "src.services.liquidity_monitor_service",
)


def _load_json_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _module_imports() -> set[str]:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"), filename=str(MODULE_PATH))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def test_fx_commodities_contract_registry_keeps_expected_symbols_in_order() -> None:
    contracts = list_fx_commodity_contracts()

    assert [item.symbol for item in contracts] == list(FX_COMMODITY_SYMBOLS)


def test_fx_commodities_contracts_remain_inert_disabled_live_stubs() -> None:
    for contract in list_fx_commodity_contracts():
        assert contract.display_name
        assert contract.expected_unit
        assert contract.expected_cadence
        assert contract.source_class == "disabled_live_stub"
        assert contract.source_class in CANONICAL_SOURCE_TYPES
        assert contract.freshness_window
        assert contract.safe_fallback_reason_buckets == SAFE_UNAVAILABLE_REASON_BUCKETS
        assert contract.delayed_proxy_eligible is True
        assert contract.live_premarket_eligible is False


def test_get_fx_commodity_contract_is_case_insensitive_and_keeps_dxy_identity() -> None:
    contract = get_fx_commodity_contract("dxy")

    assert contract is not None
    assert contract.symbol == "DXY"
    assert contract.display_name == "US Dollar Index (DXY)"
    assert contract.expected_unit == "index_points"


def test_parse_mocked_fx_commodities_fixture_returns_complete_contract_set() -> None:
    observations = parse_mocked_fx_commodities_payload(_load_json_fixture("valid_fx_commodities_snapshot.json"))

    assert [item.symbol for item in observations] == list(FX_COMMODITY_SYMBOLS)
    assert all(item.is_evidence for item in observations)
    assert all(item.unavailable_reason is None for item in observations)
    assert [item.to_dict() for item in observations] == [
        {
            "symbol": "DXY",
            "value": 104.32,
            "asOf": "2026-05-14T09:30:00-04:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
        {
            "symbol": "USDCNH",
            "value": 7.2381,
            "asOf": "2026-05-14T09:30:00-04:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
        {
            "symbol": "USDJPY",
            "value": 155.42,
            "asOf": "2026-05-14T09:30:00-04:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
        {
            "symbol": "EURUSD",
            "value": 1.0834,
            "asOf": "2026-05-14T09:30:00-04:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
        {
            "symbol": "GOLD",
            "value": 2368.7,
            "asOf": "2026-05-14T09:30:00-04:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
        {
            "symbol": "WTI",
            "value": 78.45,
            "asOf": "2026-05-14T09:30:00-04:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
        {
            "symbol": "BRENT",
            "value": 82.11,
            "asOf": "2026-05-14T09:30:00-04:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
        {
            "symbol": "COPPER",
            "value": 4.63,
            "asOf": "2026-05-14T09:30:00-04:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
    ]


def test_dxy_identity_guard_rejects_relabelled_usd_index_payloads() -> None:
    payload = copy.deepcopy(_load_json_fixture("valid_fx_commodities_snapshot.json"))
    payload["observations"][0]["symbol"] = "USDX"

    observations = parse_mocked_fx_commodities_payload(payload)

    assert [item.symbol for item in observations] == list(FX_COMMODITY_SYMBOLS)
    assert all(not item.is_evidence for item in observations)
    assert all(item.value is None for item in observations)
    assert all(item.unavailable_reason == "malformed_payload" for item in observations)


def test_yfinance_style_proxy_fixture_cannot_be_parsed_as_official_fx_commodities_evidence() -> None:
    observations = parse_mocked_fx_commodities_payload(_load_json_fixture("yfinance_proxy_fixture.json"))

    assert [item.symbol for item in observations] == list(FX_COMMODITY_SYMBOLS)
    assert all(not item.is_evidence for item in observations)
    assert all(item.value is None for item in observations)
    assert all(item.unavailable_reason == "malformed_payload" for item in observations)


@pytest.mark.parametrize(
    ("fixture_name", "expected_reason"),
    [
        ("provider_not_selected.json", "provider_not_selected"),
        ("missing_credentials.json", "missing_credentials"),
        ("permission_denied.json", "permission_denied"),
        ("empty_payload.json", "empty_payload"),
        ("malformed_payload.json", "malformed_payload"),
    ],
)
def test_mocked_fx_commodities_fixtures_map_to_sanitized_unavailable_reasons(
    fixture_name: str,
    expected_reason: str,
) -> None:
    observations = parse_mocked_fx_commodities_payload(_load_json_fixture(fixture_name))

    assert [item.symbol for item in observations] == list(FX_COMMODITY_SYMBOLS)
    assert all(not item.is_evidence for item in observations)
    assert all(item.value is None for item in observations)
    assert all(item.unavailable_reason == expected_reason for item in observations)


def test_unavailable_fx_commodities_outputs_do_not_leak_tokens_urls_or_provider_payloads() -> None:
    observations = parse_mocked_fx_commodities_payload(_load_json_fixture("permission_denied.json"))

    serialized = json.dumps([item.to_dict() for item in observations], ensure_ascii=False, sort_keys=True)
    assert "SECRET" not in serialized
    assert "https://proxy.vendor.test/raw" not in serialized
    assert "providerPayload" not in serialized
    assert "MacroVendor" not in serialized


def test_fx_commodities_contract_module_stays_stdlib_only_and_out_of_provider_runtime() -> None:
    forbidden_imports = sorted(
        module
        for module in _module_imports()
        if any(module == prefix or module.startswith(prefix + ".") for prefix in FORBIDDEN_IMPORT_PREFIXES)
    )
    assert forbidden_imports == []


def test_fx_commodities_contract_module_import_has_no_runtime_side_effects() -> None:
    script = """
import json
import src.services.fx_commodities_contracts
blocked = [
    "src.services.market_overview_service",
    "src.services.market_cache",
    "src.services.liquidity_monitor_service",
    "data_provider.yfinance_fetcher",
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
