# -*- coding: utf-8 -*-
"""Tests for inert CN/HK flow contracts and mocked fixture parsing."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys

import pytest

from src.services.cn_hk_flow_contracts import (
    CN_HK_FLOW_SYMBOLS,
    SAFE_UNAVAILABLE_REASON_BUCKETS,
    get_cn_hk_flow_contract,
    list_cn_hk_flow_contracts,
    parse_mocked_cn_hk_flow_payload,
)
from src.services.market_data_source_registry import CANONICAL_SOURCE_TYPES


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "cn_hk_flows"
MODULE_PATH = REPO_ROOT / "src" / "services" / "cn_hk_flow_contracts.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "src.services.market_overview_service",
    "src.services.market_cache",
    "src.services.liquidity_monitor_service",
    "src.services.market_rotation_radar_service",
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


def test_cn_hk_flow_contract_registry_keeps_expected_symbols_in_order() -> None:
    contracts = list_cn_hk_flow_contracts()

    assert [item.symbol for item in contracts] == list(CN_HK_FLOW_SYMBOLS)


def test_cn_hk_flow_contracts_remain_inert_disabled_live_stubs() -> None:
    for contract in list_cn_hk_flow_contracts():
        assert contract.display_name
        assert contract.expected_unit
        assert contract.expected_cadence
        assert contract.source_class == "disabled_live_stub"
        assert contract.source_class in CANONICAL_SOURCE_TYPES
        assert contract.freshness_window
        assert contract.entitlement_config_category
        assert contract.safe_fallback_reason_buckets == SAFE_UNAVAILABLE_REASON_BUCKETS


def test_get_cn_hk_flow_contract_is_case_insensitive() -> None:
    contract = get_cn_hk_flow_contract("northbound")

    assert contract is not None
    assert contract.symbol == "NORTHBOUND"
    assert contract.display_name == "北向资金"
    assert contract.expected_unit == "亿 CNY"


def test_parse_mocked_cn_hk_flow_fixture_returns_complete_contract_set() -> None:
    observations = parse_mocked_cn_hk_flow_payload(_load_json_fixture("valid_flow_snapshot.json"))

    assert [item.symbol for item in observations] == list(CN_HK_FLOW_SYMBOLS)
    assert all(item.is_evidence for item in observations)
    assert all(item.unavailable_reason is None for item in observations)
    assert [item.to_dict() for item in observations] == [
        {
            "symbol": "NORTHBOUND",
            "value": 42.6,
            "asOf": "2026-05-14T09:30:00+08:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
        {
            "symbol": "SOUTHBOUND",
            "value": 28.4,
            "asOf": "2026-05-14T09:30:00+08:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
        {
            "symbol": "MAINLAND_MAIN",
            "value": -63.5,
            "asOf": "2026-05-14T09:30:00+08:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
        {
            "symbol": "CN_ETF",
            "value": 15.8,
            "asOf": "2026-05-14T09:30:00+08:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
        {
            "symbol": "MARGIN_BALANCE",
            "value": 31.2,
            "asOf": "2026-05-14T09:30:00+08:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
    ]


def test_tickflow_breadth_fixture_cannot_be_parsed_as_flow_evidence() -> None:
    observations = parse_mocked_cn_hk_flow_payload(_load_json_fixture("tickflow_breadth_fixture.json"))

    assert [item.symbol for item in observations] == list(CN_HK_FLOW_SYMBOLS)
    assert all(not item.is_evidence for item in observations)
    assert all(item.value is None for item in observations)
    assert all(item.unavailable_reason == "malformed_payload" for item in observations)


@pytest.mark.parametrize(
    ("fixture_name", "expected_reason"),
    [
        ("missing_credentials.json", "missing_credentials"),
        ("permission_denied.json", "permission_denied"),
        ("empty_payload.json", "empty_payload"),
        ("malformed_payload.json", "malformed_payload"),
    ],
)
def test_mocked_cn_hk_flow_fixtures_map_to_sanitized_unavailable_reasons(
    fixture_name: str,
    expected_reason: str,
) -> None:
    observations = parse_mocked_cn_hk_flow_payload(_load_json_fixture(fixture_name))

    assert [item.symbol for item in observations] == list(CN_HK_FLOW_SYMBOLS)
    assert all(not item.is_evidence for item in observations)
    assert all(item.value is None for item in observations)
    assert all(item.unavailable_reason == expected_reason for item in observations)


def test_unavailable_outputs_do_not_leak_tokens_urls_or_provider_payloads() -> None:
    observations = parse_mocked_cn_hk_flow_payload(_load_json_fixture("permission_denied.json"))

    serialized = json.dumps([item.to_dict() for item in observations], ensure_ascii=False, sort_keys=True)
    assert "SECRET" not in serialized
    assert "https://api.tickflow.test/raw" not in serialized
    assert "providerPayload" not in serialized
    assert "TickFlow" not in serialized


def test_contract_module_stays_stdlib_only_and_out_of_provider_runtime() -> None:
    forbidden_imports = sorted(
        module
        for module in _module_imports()
        if any(module == prefix or module.startswith(prefix + ".") for prefix in FORBIDDEN_IMPORT_PREFIXES)
    )
    assert forbidden_imports == []


def test_contract_module_import_has_no_runtime_side_effects() -> None:
    script = """
import json
import src.services.cn_hk_flow_contracts
blocked = [
    "src.services.market_overview_service",
    "src.services.market_cache",
    "src.services.liquidity_monitor_service",
    "src.services.market_rotation_radar_service",
    "data_provider.tickflow_fetcher",
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
