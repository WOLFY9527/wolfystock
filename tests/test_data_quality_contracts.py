# -*- coding: utf-8 -*-
"""Tests for inert data quality required-field contracts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.services.data_quality_contract_validator import validate_data_quality_contract
from src.services.data_quality_contracts import (
    CONTRACT_VERSION,
    DataQualityClass,
    DataQualityContractField,
    DataQualityStatus,
    EngineId,
    EngineRequiredFieldContract,
    EvidenceCriticality,
    evaluate_confidence_cap_effect,
    get_engine_required_field_contract,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "data_quality_contracts"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_registry_returns_contracts_for_all_engines() -> None:
    contracts = {engine.value: get_engine_required_field_contract(engine) for engine in EngineId}

    assert set(contracts) == {
        "scanner",
        "rotation",
        "options",
        "backtest",
        "ai_analysis",
        "portfolio_risk",
    }
    assert all(contract.contract_version == CONTRACT_VERSION for contract in contracts.values())


def test_all_registry_contracts_have_required_fields() -> None:
    for engine in EngineId:
        contract = get_engine_required_field_contract(engine)
        assert contract.required_fields
        assert all(field.criticality is EvidenceCriticality.REQUIRED for field in contract.required_fields)


def test_contract_classification_serializes_round_trip() -> None:
    contract = get_engine_required_field_contract(EngineId.OPTIONS)

    serialized = contract.to_dict()
    restored = EngineRequiredFieldContract.from_dict(json.loads(json.dumps(serialized, ensure_ascii=False)))

    assert [field.field_key for field in restored.required_fields] == [field.field_key for field in contract.required_fields]
    assert [field.criticality.value for field in restored.required_fields] == ["required"] * len(contract.required_fields)
    assert [field.criticality.value for field in restored.important_fields] == ["important"] * len(contract.important_fields)
    assert [field.criticality.value for field in restored.optional_fields] == ["optional"] * len(contract.optional_fields)


def test_data_quality_classes_serialize_round_trip() -> None:
    for data_quality_class in DataQualityClass:
        field = DataQualityContractField.from_dict(
            {
                "engine": "ai_analysis",
                "field_key": f"field.{data_quality_class.value}",
                "criticality": "optional",
                "data_quality_class": data_quality_class.value,
                "status": "available",
                "as_of": "2026-05-10T00:00:00Z",
                "source_ref_ids": ["src_1"],
                "reason_codes": ["ok"],
                "decision_grade": False,
                "confidence_cap_effect": "visible_gap_only",
            }
        )

        restored = DataQualityContractField.from_dict(json.loads(json.dumps(field.to_dict(), ensure_ascii=False)))

        assert restored.data_quality_class is data_quality_class


@pytest.mark.parametrize(
    "fixture_name",
    [
        "scanner_complete_local_history.json",
        "rotation_proxy_backed_complete.json",
        "backtest_local_ready.json",
        "ai_packet_complete.json",
        "portfolio_manual_replay_complete.json",
    ],
)
def test_validator_accepts_valid_contract_fixtures(fixture_name: str) -> None:
    result = validate_data_quality_contract(_fixture(fixture_name))

    assert result.is_valid is True
    assert result.issues == []


@pytest.mark.parametrize(
    ("fixture_name", "expected_reason_code"),
    [
        ("scanner_missing_quote.json", "required_field_missing"),
        ("rotation_taxonomy_only.json", "missing_required_field_entry"),
        ("backtest_missing_calendar.json", "required_field_missing"),
    ],
)
def test_validator_flags_missing_required_fields(fixture_name: str, expected_reason_code: str) -> None:
    result = validate_data_quality_contract(_fixture(fixture_name))
    reason_codes = {issue["reasonCode"] for issue in result.issues}

    assert result.is_valid is False
    assert expected_reason_code in reason_codes


@pytest.mark.parametrize(
    "fixture_name",
    [
        "options_fixture_chain.json",
        "options_missing_bid_ask.json",
    ],
)
def test_validator_rejects_required_fixture_synthetic_or_missing_marked_decision_grade(
    fixture_name: str,
) -> None:
    result = validate_data_quality_contract(_fixture(fixture_name))
    reason_codes = {issue["reasonCode"] for issue in result.issues}

    assert result.is_valid is False
    assert "invalid_required_decision_grade" in reason_codes


def test_optional_missing_evidence_does_not_block_by_itself() -> None:
    contract = get_engine_required_field_contract("ai_analysis")
    contract.required_fields = [
        DataQualityContractField.from_dict(
            {
                "engine": "ai_analysis",
                "field_key": field.field_key,
                "criticality": "required",
                "data_quality_class": "fresh",
                "status": "available",
                "as_of": "2026-05-10T09:30:00Z",
                "source_ref_ids": ["src_1"],
                "reason_codes": ["ok"],
                "decision_grade": True,
                "confidence_cap_effect": "none",
            }
        )
        for field in contract.required_fields
    ]
    contract.optional_fields = [
        DataQualityContractField.from_dict(
            {
                "engine": "ai_analysis",
                "field_key": "news.context",
                "criticality": "optional",
                "data_quality_class": "missing",
                "status": "missing",
                "as_of": None,
                "source_ref_ids": ["src_2"],
                "reason_codes": ["optional_news_missing"],
                "decision_grade": False,
                "confidence_cap_effect": evaluate_confidence_cap_effect(
                    DataQualityContractField.from_dict(
                        {
                            "engine": "ai_analysis",
                            "field_key": "news.context",
                            "criticality": "optional",
                            "data_quality_class": "missing",
                            "status": "missing",
                            "as_of": None,
                            "source_ref_ids": ["src_2"],
                            "reason_codes": ["optional_news_missing"],
                            "decision_grade": False,
                            "confidence_cap_effect": "visible_gap_only",
                        }
                    )
                ),
            }
        )
    ]
    contract.source_ref_policies = [
        {"source_ref_id": "src_1", "source_class": "local", "provider": "packet", "raw_payload_stored": False, "sanitized_reason_code": "ok"},
        {"source_ref_id": "src_2", "source_class": "local", "provider": "packet", "raw_payload_stored": False, "sanitized_reason_code": "optional_missing"},
    ]

    result = validate_data_quality_contract(contract)

    assert result.is_valid is True
    assert result.issues == []


def test_source_ref_sanitizer_rejects_raw_payload_request_response_and_prompt_like_keys() -> None:
    result = validate_data_quality_contract(_fixture("unsafe_raw_payload_rejected_contract.json"))
    reason_codes = {issue["reasonCode"] for issue in result.issues}

    assert result.is_valid is False
    assert "unsafe_source_ref_field" in reason_codes


def test_confidence_cap_policy_mapping_is_pure_and_matches_required_field_rules() -> None:
    required_missing = DataQualityContractField.from_dict(
        {
            "engine": "scanner",
            "field_key": "quote.price",
            "criticality": "required",
            "data_quality_class": "missing",
            "status": "missing",
            "as_of": None,
            "source_ref_ids": [],
            "reason_codes": ["missing_quote"],
            "decision_grade": False,
            "confidence_cap_effect": "block_decision_grade",
        }
    )
    optional_missing = DataQualityContractField.from_dict(
        {
            "engine": "scanner",
            "field_key": "news.context",
            "criticality": "optional",
            "data_quality_class": "missing",
            "status": "missing",
            "as_of": None,
            "source_ref_ids": [],
            "reason_codes": ["optional_news_missing"],
            "decision_grade": False,
            "confidence_cap_effect": "visible_gap_only",
        }
    )
    local_history = DataQualityContractField.from_dict(
        {
            "engine": "backtest",
            "field_key": "local_bars.coverage",
            "criticality": "required",
            "data_quality_class": "local_historical",
            "status": "available",
            "as_of": "2026-05-09T00:00:00Z",
            "source_ref_ids": ["src_backtest"],
            "reason_codes": ["coverage_pass"],
            "decision_grade": True,
            "confidence_cap_effect": "allow_local_historical",
        }
    )

    assert evaluate_confidence_cap_effect(required_missing) == "block_decision_grade"
    assert evaluate_confidence_cap_effect(optional_missing) == "visible_gap_only"
    assert evaluate_confidence_cap_effect(local_history) == "allow_local_historical"


def test_import_side_effects_are_inert() -> None:
    script = """
import sys
before = set(sys.modules)
import src.services.data_quality_contracts
import src.services.data_quality_contract_validator
after = set(sys.modules)
for forbidden in [
    "yfinance",
    "requests",
    "httpx",
    "openai",
    "src.core.pipeline",
    "src.services.market_scanner_service",
    "src.services.options_lab_service",
    "src.core.rule_backtest_engine",
    "src.services.portfolio_service",
    "src.services.portfolio_risk_service",
]:
    assert forbidden not in after - before, f"unexpected import side effect: {forbidden}"
print("data quality contract imports are inert")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "data quality contract imports are inert" in result.stdout


def test_strict_mode_raises_for_invalid_contract() -> None:
    with pytest.raises(ValueError):
        validate_data_quality_contract(_fixture("unsafe_raw_payload_rejected_contract.json"), strict=True)
