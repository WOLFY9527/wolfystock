# -*- coding: utf-8 -*-
"""Cross-engine regression coverage for metadata-only AI evidence adapters."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.services.ai_evidence_adapters import (
    backtest_readiness_to_ai_packet,
    normalize_engine_evidence_to_ai_packet,
    options_gates_to_ai_packet,
    portfolio_risk_to_ai_packet,
    rotation_evidence_to_ai_packet,
    scanner_evidence_to_ai_packet,
)
from src.services.ai_evidence_packet import AI_EVIDENCE_PACKET_VERSION, AiEvidenceDecisionStatus
from src.services.ai_evidence_packet_validator import validate_ai_evidence_packet


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "ai_evidence_adapters"
FORBIDDEN_USER_FACT_TERMS = (
    "authorization",
    "cookie",
    "token",
    "prompt",
    "headers",
    "response_body",
    "adminreasoncodes",
    "failclosedreasoncodes",
    "gateissues",
    "provider_calls",
)


def _fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("fixture_name", "adapter", "expected_engine", "expected_max_cap"),
    [
        ("scanner_candidate_packet.json", scanner_evidence_to_ai_packet, "scanner", 75),
        ("rotation_proxy_only_packet.json", rotation_evidence_to_ai_packet, "rotation", 60),
        ("options_fail_closed_packet.json", options_gates_to_ai_packet, "options", 35),
        ("backtest_research_prototype_packet.json", backtest_readiness_to_ai_packet, "backtest", 55),
        ("portfolio_stale_fx_packet.json", portfolio_risk_to_ai_packet, "portfolio_risk", 75),
    ],
)
def test_cross_engine_adapters_emit_versioned_sanitized_metadata_only_packets(
    fixture_name: str,
    adapter,
    expected_engine: str,
    expected_max_cap: int,
) -> None:
    payload = _fixture(fixture_name)

    packet = adapter(payload)
    validation = validate_ai_evidence_packet(packet.to_dict())
    explainable_text = json.dumps([item.to_dict() for item in packet.explainable_facts], ensure_ascii=False).lower()

    assert validation.is_valid is True, validation.issues
    assert packet.engine.value == expected_engine
    assert packet.evidence_version == AI_EVIDENCE_PACKET_VERSION
    assert packet.confidence_cap.value <= expected_max_cap
    assert packet.confidence_cap.policy_version == "confidence_cap_policy_v1"
    assert packet.source_refs
    assert len(packet.source_refs) <= 2
    assert all(source_ref.raw_payload_stored is False for source_ref in packet.source_refs)
    assert all(len(source_ref.provider_usage_event_ids) <= 1 for source_ref in packet.source_refs)
    for forbidden in FORBIDDEN_USER_FACT_TERMS:
        assert forbidden not in explainable_text


@pytest.mark.parametrize(
    ("fixture_name", "expected_engine"),
    [
        ("scanner_candidate_packet.json", "scanner"),
        ("rotation_proxy_only_packet.json", "rotation"),
        ("options_fail_closed_packet.json", "options"),
        ("backtest_research_prototype_packet.json", "backtest"),
        ("portfolio_stale_fx_packet.json", "portfolio_risk"),
    ],
)
def test_normalize_engine_evidence_dispatches_all_supported_engine_packets(
    fixture_name: str,
    expected_engine: str,
) -> None:
    payload = _fixture(fixture_name)

    packet = normalize_engine_evidence_to_ai_packet(payload)

    assert packet.engine.value == expected_engine
    assert packet.evidence_version == AI_EVIDENCE_PACKET_VERSION


def test_reason_code_and_quality_flag_regressions_stay_stable_for_incomplete_evidence() -> None:
    scanner_packet = scanner_evidence_to_ai_packet(_fixture("scanner_candidate_packet.json"))
    rotation_packet = rotation_evidence_to_ai_packet(_fixture("rotation_proxy_only_packet.json"))
    options_packet = options_gates_to_ai_packet(_fixture("options_fail_closed_packet.json"))
    backtest_packet = backtest_readiness_to_ai_packet(_fixture("backtest_research_prototype_packet.json"))
    portfolio_packet = portfolio_risk_to_ai_packet(_fixture("portfolio_stale_fx_packet.json"))

    assert scanner_packet.decision_status is AiEvidenceDecisionStatus.CAUTION
    assert set(scanner_packet.quality_flags) == {"optional_enrichment_missing", "stale_required_data"}
    assert set(scanner_packet.confidence_cap.reason_codes) == {
        "scanner_evidence_metadata_only",
        "stale_required_data",
    }

    assert rotation_packet.decision_status is AiEvidenceDecisionStatus.CAUTION
    assert rotation_packet.confidence_cap.reason_codes == ["rotation_proxy_only_flow_boundary"]
    assert rotation_packet.quality_flags == ["optional_enrichment_missing"]

    assert options_packet.decision_status is AiEvidenceDecisionStatus.FORBIDDEN
    assert set(options_packet.confidence_cap.reason_codes) == {
        "options_gate_metadata_only",
        "fixture_or_synthetic_required_evidence",
        "required_data_missing",
    }
    assert "fixture_data" in options_packet.quality_flags

    assert backtest_packet.decision_status is AiEvidenceDecisionStatus.CAUTION
    assert backtest_packet.confidence_cap.reason_codes == ["research_prototype_only"]
    assert backtest_packet.admin_diagnostics["overall_state"] == "research_prototype"

    assert portfolio_packet.decision_status is AiEvidenceDecisionStatus.CAUTION
    assert set(portfolio_packet.confidence_cap.reason_codes) == {"stale_fx", "stale_required_data"}
    assert "stale_required_data" in portfolio_packet.quality_flags


def test_ai_boundary_guard_keeps_cross_engine_packets_non_decisional() -> None:
    packets = [
        scanner_evidence_to_ai_packet(_fixture("scanner_candidate_packet.json")),
        rotation_evidence_to_ai_packet(_fixture("rotation_proxy_only_packet.json")),
        options_gates_to_ai_packet(_fixture("options_fail_closed_packet.json")),
        backtest_readiness_to_ai_packet(_fixture("backtest_research_prototype_packet.json")),
        portfolio_risk_to_ai_packet(_fixture("portfolio_stale_fx_packet.json")),
    ]

    serialized = json.dumps([packet.to_dict() for packet in packets], ensure_ascii=False).lower()

    assert "prompt" not in serialized
    assert "routing" not in serialized
    assert "weighting" not in serialized
    assert "decision-ready" not in serialized
    assert "dry-run-ready" not in serialized
    assert all(packet.decision_status is not AiEvidenceDecisionStatus.ALLOWED for packet in packets)
    assert all(packet.confidence_cap.value < 100 for packet in packets)
