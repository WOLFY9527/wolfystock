# -*- coding: utf-8 -*-
"""Tests for inert futures contracts and mocked fixture parsing."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys

import pytest

from src.services.futures_contracts import (
    FUTURES_SYMBOLS,
    SAFE_UNAVAILABLE_REASON_BUCKETS,
    get_futures_contract,
    list_futures_contracts,
    parse_mocked_futures_payload,
)
from src.services.market_data_source_registry import CANONICAL_SOURCE_TYPES


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "futures"
MODULE_PATH = REPO_ROOT / "src" / "services" / "futures_contracts.py"
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


def test_futures_contract_registry_keeps_expected_symbols_in_order() -> None:
    contracts = list_futures_contracts()

    assert [item.symbol for item in contracts] == list(FUTURES_SYMBOLS)


def test_futures_contracts_default_to_delayed_proxy_eligibility_not_live_premarket() -> None:
    for contract in list_futures_contracts():
        assert contract.display_name
        assert contract.expected_unit
        assert contract.expected_cadence
        assert contract.source_class == "disabled_live_stub"
        assert contract.source_class in CANONICAL_SOURCE_TYPES
        assert contract.freshness_window
        assert contract.safe_fallback_reason_buckets == SAFE_UNAVAILABLE_REASON_BUCKETS
        assert contract.delayed_proxy_eligible is True
        assert contract.live_premarket_eligible is False


def test_get_futures_contract_is_case_insensitive() -> None:
    contract = get_futures_contract("nq")

    assert contract is not None
    assert contract.symbol == "NQ"
    assert contract.display_name == "E-mini Nasdaq 100"
    assert contract.expected_unit == "index_points"


def test_parse_mocked_futures_fixture_returns_complete_contract_set() -> None:
    observations = parse_mocked_futures_payload(_load_json_fixture("valid_futures_snapshot.json"))

    assert [item.symbol for item in observations] == list(FUTURES_SYMBOLS)
    assert all(item.is_evidence for item in observations)
    assert all(item.unavailable_reason is None for item in observations)
    assert [item.to_dict() for item in observations] == [
        {
            "symbol": "NQ",
            "value": 18420.5,
            "asOf": "2026-05-14T08:15:00-04:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
        {
            "symbol": "ES",
            "value": 5236.25,
            "asOf": "2026-05-14T08:15:00-04:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
        {
            "symbol": "YM",
            "value": 39520.0,
            "asOf": "2026-05-14T08:15:00-04:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
        {
            "symbol": "RTY",
            "value": 2068.4,
            "asOf": "2026-05-14T08:15:00-04:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
    ]


def test_yfinance_style_proxy_fixture_cannot_be_parsed_as_live_futures_evidence() -> None:
    observations = parse_mocked_futures_payload(_load_json_fixture("yfinance_proxy_fixture.json"))

    assert [item.symbol for item in observations] == list(FUTURES_SYMBOLS)
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
def test_mocked_futures_fixtures_map_to_sanitized_unavailable_reasons(
    fixture_name: str,
    expected_reason: str,
) -> None:
    observations = parse_mocked_futures_payload(_load_json_fixture(fixture_name))

    assert [item.symbol for item in observations] == list(FUTURES_SYMBOLS)
    assert all(not item.is_evidence for item in observations)
    assert all(item.value is None for item in observations)
    assert all(item.unavailable_reason == expected_reason for item in observations)


def test_unavailable_futures_outputs_do_not_leak_tokens_urls_or_provider_payloads() -> None:
    observations = parse_mocked_futures_payload(_load_json_fixture("permission_denied.json"))

    serialized = json.dumps([item.to_dict() for item in observations], ensure_ascii=False, sort_keys=True)
    assert "SECRET" not in serialized
    assert "https://premarket.proxy.test/raw" not in serialized
    assert "providerPayload" not in serialized
    assert "FuturesFeedCo" not in serialized


def test_futures_contract_module_stays_stdlib_only_and_out_of_provider_runtime() -> None:
    forbidden_imports = sorted(
        module
        for module in _module_imports()
        if any(module == prefix or module.startswith(prefix + ".") for prefix in FORBIDDEN_IMPORT_PREFIXES)
    )
    assert forbidden_imports == []


def test_futures_contract_module_import_has_no_runtime_side_effects() -> None:
    script = """
import json
import src.services.futures_contracts
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
