# -*- coding: utf-8 -*-
"""Tests for inert US breadth contracts and mocked fixture parsing."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys

import pytest

from src.services.market_data_source_registry import CANONICAL_SOURCE_TYPES
from src.services.us_breadth_contracts import (
    SAFE_UNAVAILABLE_REASON_BUCKETS,
    US_BREADTH_SYMBOLS,
    build_us_breadth_missing_authority_diagnostic,
    get_us_breadth_source_contract,
    get_us_breadth_contract,
    list_us_breadth_source_contracts,
    list_us_breadth_contracts,
    parse_mocked_us_breadth_payload,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "us_breadth"
MODULE_PATH = REPO_ROOT / "src" / "services" / "us_breadth_contracts.py"
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


def test_us_breadth_contract_registry_keeps_expected_symbols_in_order() -> None:
    contracts = list_us_breadth_contracts()

    assert [item.symbol for item in contracts] == list(US_BREADTH_SYMBOLS)


def test_us_breadth_contracts_remain_inert_disabled_live_stubs() -> None:
    for contract in list_us_breadth_contracts():
        assert contract.display_name
        assert contract.expected_unit
        assert contract.expected_cadence
        assert contract.source_class == "disabled_live_stub"
        assert contract.source_class in CANONICAL_SOURCE_TYPES
        assert contract.freshness_window
        assert contract.entitlement_config_category
        assert contract.safe_fallback_reason_buckets == SAFE_UNAVAILABLE_REASON_BUCKETS


def test_us_breadth_source_contracts_distinguish_score_grade_sample_proxy_and_missing() -> None:
    contracts = {item.claim_class: item for item in list_us_breadth_source_contracts()}

    assert set(contracts) == {
        "authorized_score_grade_breadth",
        "representative_sample_breadth",
        "proxy_placeholder_fallback_breadth",
        "missing_unavailable_breadth",
    }

    authorized = contracts["authorized_score_grade_breadth"]
    assert authorized.provider_id == "official_or_authorized.us_market_breadth"
    assert authorized.source_authority_allowed is True
    assert authorized.score_contribution_allowed is True
    assert authorized.broad_market_claim_allowed is True
    assert authorized.activation_gate == "configured_official_or_authorized_feed_and_daily_freshness_and_min_coverage"

    representative = get_us_breadth_source_contract("representative_sample_breadth")
    assert representative is not None
    assert representative.source_authority_allowed is False
    assert representative.score_contribution_allowed is False
    assert representative.broad_market_claim_allowed is False
    assert representative.source_authority_reason == "representative_sample_not_full_market_breadth"

    for claim_class in ("proxy_placeholder_fallback_breadth", "missing_unavailable_breadth"):
        contract = contracts[claim_class]
        assert contract.source_authority_allowed is False
        assert contract.score_contribution_allowed is False
        assert contract.broad_market_claim_allowed is False


def test_us_breadth_missing_authority_diagnostic_is_sanitized_and_fail_closed() -> None:
    diagnostic = build_us_breadth_missing_authority_diagnostic()

    assert diagnostic["providerConstructed"] is False
    assert diagnostic["probePassed"] is False
    assert diagnostic["freshnessValid"] is False
    assert diagnostic["sourceMetadataValid"] is True
    assert diagnostic["sourceAuthorityAllowed"] is False
    assert diagnostic["scoreContributionAllowed"] is False
    assert diagnostic["fulfilledMetrics"] == []
    assert diagnostic["missingMetrics"] == list(US_BREADTH_SYMBOLS)
    assert diagnostic["staleMetrics"] == []
    assert diagnostic["reason"] == "authorized_us_market_breadth_feed_not_configured"
    assert diagnostic["sourceLabel"] == "Official or Authorized US Market Breadth"
    assert diagnostic["sourceTier"] == "official_or_authorized_licensed_feed"
    assert diagnostic["trustLevel"] == "score_grade_when_configured"

    serialized = json.dumps(diagnostic, ensure_ascii=False, sort_keys=True)
    assert "SECRET" not in serialized
    assert "Authorization" not in serialized
    assert "providerPayload" not in serialized


def test_get_us_breadth_contract_is_case_insensitive() -> None:
    contract = get_us_breadth_contract("advance_decline_ratio")

    assert contract is not None
    assert contract.symbol == "ADVANCE_DECLINE_RATIO"
    assert contract.display_name == "Advance/Decline Ratio"
    assert contract.expected_unit == "ratio"


def test_parse_mocked_us_breadth_fixture_returns_complete_contract_set() -> None:
    observations = parse_mocked_us_breadth_payload(_load_json_fixture("valid_exchange_breadth_snapshot.json"))

    assert [item.symbol for item in observations] == list(US_BREADTH_SYMBOLS)
    assert all(item.is_evidence for item in observations)
    assert all(item.unavailable_reason is None for item in observations)
    assert [item.to_dict() for item in observations] == [
        {
            "symbol": "ADVANCERS",
            "value": 3210.0,
            "asOf": "2026-05-14T09:30:00-04:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
        {
            "symbol": "DECLINERS",
            "value": 1490.0,
            "asOf": "2026-05-14T09:30:00-04:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
        {
            "symbol": "UNCHANGED",
            "value": 180.0,
            "asOf": "2026-05-14T09:30:00-04:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
        {
            "symbol": "ADVANCE_DECLINE_RATIO",
            "value": 2.154,
            "asOf": "2026-05-14T09:30:00-04:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
        {
            "symbol": "NEW_HIGHS",
            "value": 245.0,
            "asOf": "2026-05-14T09:30:00-04:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
        {
            "symbol": "NEW_LOWS",
            "value": 38.0,
            "asOf": "2026-05-14T09:30:00-04:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
        {
            "symbol": "HIGH_LOW_RATIO",
            "value": 6.447,
            "asOf": "2026-05-14T09:30:00-04:00",
            "isEvidence": True,
            "unavailableReason": None,
        },
    ]


def test_yfinance_sector_proxy_fixture_cannot_be_parsed_as_real_exchange_breadth() -> None:
    observations = parse_mocked_us_breadth_payload(_load_json_fixture("yfinance_sector_proxy_fixture.json"))

    assert [item.symbol for item in observations] == list(US_BREADTH_SYMBOLS)
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
def test_mocked_us_breadth_fixtures_map_to_sanitized_unavailable_reasons(
    fixture_name: str,
    expected_reason: str,
) -> None:
    observations = parse_mocked_us_breadth_payload(_load_json_fixture(fixture_name))

    assert [item.symbol for item in observations] == list(US_BREADTH_SYMBOLS)
    assert all(not item.is_evidence for item in observations)
    assert all(item.value is None for item in observations)
    assert all(item.unavailable_reason == expected_reason for item in observations)


def test_unavailable_outputs_do_not_leak_tokens_urls_or_provider_payloads() -> None:
    observations = parse_mocked_us_breadth_payload(_load_json_fixture("permission_denied.json"))

    serialized = json.dumps([item.to_dict() for item in observations], ensure_ascii=False, sort_keys=True)
    assert "SECRET" not in serialized
    assert "https://api.exchange.test/raw" not in serialized
    assert "providerPayload" not in serialized
    assert "ExchangeStatsCo" not in serialized


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
import src.services.us_breadth_contracts
blocked = [
    "src.services.market_overview_service",
    "src.services.market_cache",
    "src.services.liquidity_monitor_service",
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
