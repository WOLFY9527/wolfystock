# -*- coding: utf-8 -*-
"""Focused regression coverage for required-field contract completeness."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.services.data_quality_contract_validator import validate_data_quality_contract


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "data_quality_contracts"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "fixture_name",
    [
        "scanner_complete_local_history.json",
        "rotation_proxy_backed_complete.json",
        "options_live_complete.json",
        "backtest_local_ready.json",
        "ai_packet_complete.json",
        "portfolio_manual_replay_complete.json",
    ],
)
def test_representative_required_field_contracts_cover_all_engines(fixture_name: str) -> None:
    validation = validate_data_quality_contract(_fixture(fixture_name))

    assert validation.is_valid is True, validation.issues


@pytest.mark.parametrize(
    ("fixture_name", "field_key"),
    [
        ("scanner_complete_local_history.json", "quote.price"),
        ("rotation_proxy_backed_complete.json", "flow.evidence_boundary"),
        ("options_live_complete.json", "quote.bid_ask_mid"),
        ("backtest_local_ready.json", "trading_calendar.policy"),
        ("ai_packet_complete.json", "confidence.cap"),
        ("portfolio_manual_replay_complete.json", "holdings.lineage"),
    ],
)
def test_incomplete_contracts_fail_with_controlled_missing_field_diagnostics(
    fixture_name: str,
    field_key: str,
) -> None:
    contract = copy.deepcopy(_fixture(fixture_name))
    contract["required_fields"] = [
        field for field in contract["required_fields"] if field["field_key"] != field_key
    ]

    validation = validate_data_quality_contract(contract)

    assert validation.is_valid is False
    assert {
        "field": f"required_fields.{field_key}",
        "reasonCode": "missing_required_field_entry",
    } in validation.issues
