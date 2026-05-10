# -*- coding: utf-8 -*-
"""Compatibility and unknown-version coverage for evidence packet contracts."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.services.ai_evidence_adapters import (
    normalize_engine_evidence_to_ai_packet,
    portfolio_risk_to_ai_packet,
    rotation_evidence_to_ai_packet,
    scanner_evidence_to_ai_packet,
)
from src.services.ai_evidence_packet import AI_EVIDENCE_PACKET_VERSION, AiEvidenceDecisionStatus
from src.services.ai_evidence_packet_validator import validate_ai_evidence_packet
from src.services.data_quality_contract_validator import validate_data_quality_contract
from src.services.data_quality_contracts import CONTRACT_VERSION
from src.services.rotation_state_evidence import ROTATION_STATE_EVIDENCE_SCHEMA_VERSION
from src.services.scanner_evidence_packet import SCANNER_EVIDENCE_VERSION


REPO_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "ai_evidence_adapters"
PACKET_FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "ai_evidence_packet"
CONTRACT_FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "data_quality_contracts"


def _adapter_fixture(name: str) -> dict:
    return json.loads((ADAPTER_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _packet_fixture(name: str) -> dict:
    return json.loads((PACKET_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _contract_fixture(name: str) -> dict:
    return json.loads((CONTRACT_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_known_v1_versions_remain_the_explicit_compatibility_baseline() -> None:
    scanner_packet = scanner_evidence_to_ai_packet(_adapter_fixture("scanner_candidate_packet.json"))
    rotation_packet = rotation_evidence_to_ai_packet(_adapter_fixture("rotation_proxy_only_packet.json"))
    ai_packet = _packet_fixture("valid_scanner_packet.json")
    contract = _contract_fixture("scanner_complete_local_history.json")

    assert scanner_packet.evidence_version == AI_EVIDENCE_PACKET_VERSION
    assert scanner_packet.admin_diagnostics["source_packet_version"] == SCANNER_EVIDENCE_VERSION
    assert rotation_packet.evidence_version == AI_EVIDENCE_PACKET_VERSION
    assert rotation_packet.admin_diagnostics["engine_schema_version"] == ROTATION_STATE_EVIDENCE_SCHEMA_VERSION
    assert ai_packet["evidence_version"] == AI_EVIDENCE_PACKET_VERSION
    assert validate_ai_evidence_packet(ai_packet).is_valid is True
    assert contract["contract_version"] == CONTRACT_VERSION
    assert validate_data_quality_contract(contract).is_valid is True


def test_unknown_ai_packet_version_is_rejected_without_silent_promotion() -> None:
    payload = _packet_fixture("valid_scanner_packet.json")
    payload["evidence_version"] = "ai_evidence_packet_v9"
    payload["decision_status"] = "allowed"
    payload["confidence_cap"]["value"] = 100

    validation = validate_ai_evidence_packet(payload)

    assert validation.is_valid is False
    assert "invalid_evidence_version" in {issue["reasonCode"] for issue in validation.issues}
    with pytest.raises(ValueError, match="unsupported engine evidence payload"):
        normalize_engine_evidence_to_ai_packet(payload)


def test_unknown_contract_version_is_rejected_by_validator() -> None:
    contract = _contract_fixture("scanner_complete_local_history.json")
    contract["contract_version"] = "data_quality_contract_v9"

    validation = validate_data_quality_contract(contract)

    assert validation.is_valid is False
    assert "invalid_contract_version" in {issue["reasonCode"] for issue in validation.issues}


def test_unknown_scanner_packet_version_degrades_to_caution_and_version_flag() -> None:
    payload = _adapter_fixture("scanner_candidate_packet.json")
    payload["diagnostics"]["evidence_packet"]["evidenceVersion"] = "scanner_evidence_v9"
    payload["diagnostics"]["evidence_packet"]["dataQualityState"] = "complete"
    payload["diagnostics"]["evidence_packet"]["freshnessState"] = "complete"
    payload["diagnostics"]["evidence_packet"]["freshnessDetail"]["quoteState"] = "complete"
    payload["diagnostics"]["evidence_packet"]["freshnessDetail"]["historyState"] = "complete"
    payload["diagnostics"]["evidence_packet"]["warningFlags"] = []
    payload["diagnostics"]["evidence_packet"]["adminReasonCodes"] = []

    packet = scanner_evidence_to_ai_packet(payload)

    assert packet.admin_diagnostics["source_packet_version"] == "scanner_evidence_v9"
    assert packet.decision_status is AiEvidenceDecisionStatus.CAUTION
    assert packet.confidence_cap.value <= 60
    assert "unknown_source_packet_version" in packet.quality_flags
    assert "unsupported_source_packet_version" in packet.confidence_cap.reason_codes


def test_unknown_rotation_schema_version_degrades_to_caution_and_version_flag() -> None:
    payload = _adapter_fixture("rotation_proxy_only_packet.json")
    payload["rotationStateEvidence"]["schemaVersion"] = "rotation_state_evidence_v9"
    payload["rotationStateEvidence"]["flowLanguageAllowed"] = True
    payload["rotationStateEvidence"]["stateConfidence"] = 0.92
    payload["rotationStateEvidence"]["requiredDataStatus"]["hasSufficientEvidence"] = True

    packet = rotation_evidence_to_ai_packet(payload)

    assert packet.admin_diagnostics["engine_schema_version"] == "rotation_state_evidence_v9"
    assert packet.decision_status is AiEvidenceDecisionStatus.CAUTION
    assert packet.confidence_cap.value <= 60
    assert "unknown_engine_schema_version" in packet.quality_flags
    assert "unsupported_engine_schema_version" in packet.confidence_cap.reason_codes


def test_unknown_nested_portfolio_packet_version_is_rejected_explicitly() -> None:
    payload = copy.deepcopy(_adapter_fixture("portfolio_stale_fx_packet.json"))
    payload["portfolioRiskEvidence"]["evidence_version"] = "ai_evidence_packet_v9"

    with pytest.raises(ValueError, match="unsupported engine evidence payload"):
        portfolio_risk_to_ai_packet(payload)
