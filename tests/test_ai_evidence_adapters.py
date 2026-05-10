# -*- coding: utf-8 -*-
"""Focused tests for inert AI evidence metadata adapters."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.services.ai_evidence_packet import AiEvidenceDecisionStatus, AiEvidencePacket
from src.services.ai_evidence_packet_validator import validate_ai_evidence_packet
from src.services.ai_evidence_adapters import (
    backtest_readiness_to_ai_packet,
    normalize_engine_evidence_to_ai_packet,
    options_gates_to_ai_packet,
    portfolio_risk_to_ai_packet,
    rotation_evidence_to_ai_packet,
    scanner_evidence_to_ai_packet,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "ai_evidence_adapters"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _assert_valid(packet: AiEvidencePacket) -> dict:
    payload = packet.to_dict()
    result = validate_ai_evidence_packet(payload)
    assert result.is_valid is True, result.issues
    return payload


def test_scanner_adapter_returns_valid_packet_and_keeps_rank_as_metadata_only() -> None:
    payload = _fixture("scanner_candidate_packet.json")

    packet = scanner_evidence_to_ai_packet(payload)
    serialized = json.dumps(_assert_valid(packet), ensure_ascii=False)

    assert packet.engine.value == "scanner"
    assert packet.admin_diagnostics["scanner_rank_metadata"] == {
        "rank": 1,
        "score": 81.6,
        "advisory_only": True,
    }
    assert "rank" not in {item.key for item in packet.required_evidence}
    assert "score" not in {item.key for item in packet.required_evidence}
    assert "recommend" not in serialized.lower()


def test_rotation_proxy_only_input_never_emits_real_fund_flow_wording() -> None:
    payload = _fixture("rotation_proxy_only_packet.json")

    packet = rotation_evidence_to_ai_packet(payload)
    serialized = json.dumps(_assert_valid(packet), ensure_ascii=False)

    assert packet.engine.value == "rotation"
    assert packet.decision_status is AiEvidenceDecisionStatus.CAUTION
    assert packet.confidence_cap.value <= 60
    for forbidden in ("真实资金流", "资金流入确认", "主力资金确认", "ETF 申赎确认"):
        assert forbidden not in serialized
    assert "轮动代理证据" in serialized


def test_options_fail_closed_input_maps_to_forbidden_judgment() -> None:
    payload = _fixture("options_fail_closed_packet.json")

    packet = options_gates_to_ai_packet(payload)
    _assert_valid(packet)

    assert packet.engine.value == "options"
    assert packet.decision_status is AiEvidenceDecisionStatus.FORBIDDEN
    assert packet.confidence_cap.value <= 35
    assert "fixture_or_synthetic_required_evidence" in packet.confidence_cap.reason_codes


def test_backtest_research_prototype_stays_research_grade_only() -> None:
    payload = _fixture("backtest_research_prototype_packet.json")

    packet = backtest_readiness_to_ai_packet(payload)
    serialized = json.dumps(_assert_valid(packet), ensure_ascii=False)

    assert packet.engine.value == "backtest"
    assert packet.decision_status is AiEvidenceDecisionStatus.CAUTION
    assert packet.confidence_cap.value <= 55
    assert "研究级" in serialized
    assert "professional validation" not in serialized.lower()
    assert packet.admin_diagnostics["professional_quant_ready"] is False


def test_portfolio_stale_fx_maps_to_cap_and_limitation() -> None:
    payload = _fixture("portfolio_stale_fx_packet.json")

    packet = portfolio_risk_to_ai_packet(payload)
    serialized = json.dumps(_assert_valid(packet), ensure_ascii=False)

    assert packet.engine.value == "portfolio_risk"
    assert packet.decision_status is AiEvidenceDecisionStatus.CAUTION
    assert packet.confidence_cap.value <= 75
    assert "FX 汇率已过期" in serialized
    assert "stale_required_data" in packet.quality_flags


def test_unsafe_raw_admin_diagnostics_are_sanitized() -> None:
    payload = _fixture("unsafe_raw_admin_diagnostics_packet.json")

    packet = normalize_engine_evidence_to_ai_packet(payload)
    normalized = _assert_valid(packet)
    serialized = json.dumps(normalized, ensure_ascii=False).lower()

    for forbidden in (
        "authorization",
        "set-cookie",
        "cookie",
        "token",
        "response_body",
        "headers",
    ):
        assert forbidden not in serialized
    assert normalized["source_refs"][0]["raw_payload_stored"] is False
    assert "sanitized metadata only" in serialized


def test_optional_missing_does_not_raise_confidence() -> None:
    payload = {
        "engine": "analysis",
        "entity": {"type": "symbol", "id": "analysis:AAPL", "symbol": "AAPL", "market": "US"},
        "run_id": "analysis_optional_001",
        "evidence_version": "ai_evidence_packet_v1",
        "required_evidence": [
            {
                "key": "evidence.packet",
                "criticality": "required",
                "status": "available",
                "value_class": "metadata",
                "source_ref_ids": ["src_packet"],
                "as_of": "2026-05-10T10:00:00Z",
                "freshness_class": "fresh",
                "reason_codes": []
            }
        ],
        "optional_evidence": [
            {
                "key": "news.context",
                "criticality": "optional",
                "status": "missing",
                "value_class": "document",
                "source_ref_ids": ["src_news"],
                "as_of": None,
                "freshness_class": "missing",
                "reason_codes": ["optional_news_missing"]
            }
        ],
        "freshness": {"packet": {"as_of": "2026-05-10T10:00:00Z", "freshness_class": "fresh"}},
        "quality_flags": ["optional_enrichment_missing"],
        "decision_status": "allowed",
        "confidence_cap": {"value": 88, "policy_version": "confidence_cap_policy_v1", "reason_codes": []},
        "source_refs": [
            {
                "source_ref_id": "src_packet",
                "provider": "analysis_adapter",
                "category": "analysis",
                "source_class": "local",
                "cache_hit": True,
                "provider_usage_event_ids": [],
                "sanitized_reason_code": "ok",
                "raw_payload_stored": False
            },
            {
                "source_ref_id": "src_news",
                "provider": "analysis_adapter",
                "category": "news",
                "source_class": "inferred",
                "cache_hit": False,
                "provider_usage_event_ids": [],
                "sanitized_reason_code": "optional_news_missing",
                "raw_payload_stored": False
            }
        ],
        "explainable_facts": [
            {
                "fact_id": "fact_packet",
                "statement": "Required packet evidence is fresh.",
                "source_ref_ids": ["src_packet"],
                "criticality": "required",
                "confidence_class": "high",
                "user_visible": True
            }
        ],
        "admin_diagnostics": {"safe_summary": "optional gap only"}
    }

    packet = normalize_engine_evidence_to_ai_packet(payload)
    _assert_valid(packet)

    assert packet.decision_status is AiEvidenceDecisionStatus.ALLOWED
    assert packet.confidence_cap.value == 88


def test_import_side_effects_are_inert() -> None:
    script = """
import sys
before = set(sys.modules)
import src.services.ai_evidence_adapters
after = set(sys.modules)
for forbidden in [
    "yfinance",
    "requests",
    "httpx",
    "openai",
    "src.core.pipeline",
    "src.services.market_scanner_service",
    "src.services.market_rotation_radar_service",
    "src.services.options_lab_service",
    "src.core.rule_backtest_engine",
    "src.services.portfolio_service",
    "src.services.portfolio_risk_service",
    "src.services.market_cache",
]:
    assert forbidden not in after - before, f"unexpected import side effect: {forbidden}"
print("ai evidence adapters imports are inert")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
