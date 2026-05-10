# -*- coding: utf-8 -*-
"""Tests for additive AI evidence packet schema and offline validator."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.services.ai_evidence_packet import (
    AiEvidenceDecisionStatus,
    AiEvidencePacket,
    evaluate_evidence_policy,
)
from src.services.ai_evidence_packet_validator import validate_ai_evidence_packet


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "ai_evidence_packet"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_valid_packet_passes_validator() -> None:
    packet = AiEvidencePacket.from_dict(_fixture("valid_scanner_packet.json"))

    result = validate_ai_evidence_packet(packet)

    assert result.is_valid is True
    assert result.issues == []


def test_missing_required_evidence_caps_confidence_and_blocks_decision() -> None:
    payload = _fixture("missing_required_evidence_packet.json")

    policy = evaluate_evidence_policy(payload)
    result = validate_ai_evidence_packet(payload)
    reason_codes = {issue["reasonCode"] for issue in result.issues}

    assert policy.decision_status is AiEvidenceDecisionStatus.FORBIDDEN
    assert policy.confidence_cap.value <= 40
    assert result.is_valid is False
    assert "decision_status_exceeds_policy" in reason_codes
    assert "confidence_cap_exceeds_policy" in reason_codes


def test_fixture_required_evidence_fails_closed() -> None:
    payload = _fixture("fixture_required_evidence_packet.json")

    policy = evaluate_evidence_policy(payload)
    result = validate_ai_evidence_packet(payload)
    reason_codes = {issue["reasonCode"] for issue in result.issues}

    assert policy.decision_status is AiEvidenceDecisionStatus.FORBIDDEN
    assert policy.confidence_cap.value <= 35
    assert result.is_valid is False
    assert "fixture_required_evidence_forbidden" in reason_codes


def test_optional_missing_does_not_reduce_confidence_by_itself() -> None:
    payload = _fixture("optional_missing_no_cap_penalty_packet.json")

    policy = evaluate_evidence_policy(payload)
    result = validate_ai_evidence_packet(payload)

    assert policy.decision_status is AiEvidenceDecisionStatus.ALLOWED
    assert policy.confidence_cap.value == 92
    assert result.is_valid is True


def test_explainable_facts_must_reference_source_refs() -> None:
    result = validate_ai_evidence_packet(_fixture("unreferenced_explainable_fact_packet.json"))
    reason_codes = {issue["reasonCode"] for issue in result.issues}

    assert result.is_valid is False
    assert "user_visible_fact_missing_source_ref" in reason_codes


def test_raw_payload_and_prompt_like_fields_are_rejected() -> None:
    result = validate_ai_evidence_packet(_fixture("unsafe_raw_payload_rejected_packet.json"))
    reason_codes = {issue["reasonCode"] for issue in result.issues}

    assert result.is_valid is False
    assert "unsafe_source_ref_field" in reason_codes


def test_serialization_round_trip_is_stable() -> None:
    packet = AiEvidencePacket.from_dict(_fixture("valid_scanner_packet.json"))

    serialized = packet.to_dict()
    restored = AiEvidencePacket.from_dict(json.loads(json.dumps(serialized, ensure_ascii=False)))

    assert restored.to_dict() == serialized


def test_imports_are_inert_and_do_not_pull_runtime_engines() -> None:
    script = """
import sys
before = set(sys.modules)
import src.services.ai_evidence_packet
import src.services.ai_evidence_packet_validator
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
]:
    assert forbidden not in after - before, f"unexpected import side effect: {forbidden}"
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_strict_mode_raises_for_invalid_packet() -> None:
    with pytest.raises(ValueError):
        validate_ai_evidence_packet(_fixture("unsafe_raw_payload_rejected_packet.json"), strict=True)
