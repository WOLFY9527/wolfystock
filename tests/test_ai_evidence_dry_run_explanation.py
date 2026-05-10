# -*- coding: utf-8 -*-
"""Focused regression coverage for deterministic AI evidence dry-run explanations."""

from __future__ import annotations

import ast
import copy
import inspect
import json
from pathlib import Path

from src.services.ai_evidence_adapters import (
    backtest_readiness_to_ai_packet,
    options_gates_to_ai_packet,
    portfolio_risk_to_ai_packet,
    rotation_evidence_to_ai_packet,
)
from src.services.ai_evidence_dry_run_explanation import (
    compose_ai_evidence_dry_run_explanation,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "ai_evidence_adapters"
PACKET_FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "ai_evidence_packet"
FORBIDDEN_USER_TERMS = (
    "raw",
    "debug",
    "schema",
    "trace",
    "prompt",
    "token",
    "cookie",
    "authorization",
    "stack trace",
    "provider_timeout",
    "marketcache",
    "local_db",
    "fixture",
    "mock",
    "synthetic",
    "generatedcandidates",
    "failedcandidates",
)


def _adapter_fixture(name: str) -> dict:
    return json.loads((ADAPTER_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _packet_fixture(name: str) -> dict:
    return json.loads((PACKET_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _lowered_user_texts(payload: dict) -> str:
    return " ".join(
        [payload["safe_summary"], *payload["limitation_labels"]]
    ).lower()


def test_valid_scanner_packet_produces_deterministic_safe_chinese_summary() -> None:
    packet = _packet_fixture("valid_scanner_packet.json")

    result = compose_ai_evidence_dry_run_explanation(
        packet,
        generated_at="2026-05-10T00:00:00Z",
    ).to_dict()

    assert result["explanation_mode"] == "dry_run"
    assert result["engine"] == "scanner"
    assert result["validation_state"] == "valid"
    assert result["posture"] in {"allowed_metadata_only", "observe_only"}
    assert result["safe_summary"] == "当前证据链已校验，可用于观察，不提升任何判断强度。"
    assert "推荐" not in result["safe_summary"]
    assert "买入" not in result["safe_summary"]


def test_rotation_proxy_only_evidence_stays_cautious_and_never_claims_real_fund_flow() -> None:
    packet = rotation_evidence_to_ai_packet(_adapter_fixture("rotation_proxy_only_packet.json"))

    result = compose_ai_evidence_dry_run_explanation(
        packet,
        generated_at="2026-05-10T00:00:00Z",
    ).to_dict()

    assert result["engine"] == "rotation"
    assert result["posture"] == "observe_only"
    assert "真实资金流暂缺" in result["safe_summary"]
    assert "仅供观察" in result["safe_summary"]
    assert "真实资金流确认" not in result["safe_summary"]
    assert "真实资金流入" not in result["safe_summary"]


def test_options_fail_closed_evidence_blocks_judgment_without_recommendation_language() -> None:
    packet = options_gates_to_ai_packet(_adapter_fixture("options_fail_closed_packet.json"))

    result = compose_ai_evidence_dry_run_explanation(
        packet,
        generated_at="2026-05-10T00:00:00Z",
    ).to_dict()

    assert result["engine"] == "options"
    assert result["posture"] == "blocked"
    assert "数据不足，禁止判断" in result["safe_summary"]
    assert "推荐" not in result["safe_summary"]
    assert "可交易" not in result["safe_summary"]
    assert "优先策略" not in result["safe_summary"]


def test_backtest_research_prototype_stays_research_grade_only() -> None:
    packet = backtest_readiness_to_ai_packet(_adapter_fixture("backtest_research_prototype_packet.json"))

    result = compose_ai_evidence_dry_run_explanation(
        packet,
        generated_at="2026-05-10T00:00:00Z",
    ).to_dict()

    assert result["engine"] == "backtest"
    assert result["posture"] == "observe_only"
    assert "研究级回测" in result["safe_summary"]
    assert "专业量化" not in result["safe_summary"]


def test_portfolio_stale_fx_only_supports_risk_observation_wording() -> None:
    packet = portfolio_risk_to_ai_packet(_adapter_fixture("portfolio_stale_fx_packet.json"))

    result = compose_ai_evidence_dry_run_explanation(
        packet,
        generated_at="2026-05-10T00:00:00Z",
    ).to_dict()

    assert result["engine"] == "portfolio_risk"
    assert result["posture"] == "observe_only"
    assert "仅供风险观察" in result["safe_summary"]
    assert "FX 汇率已过期" in result["limitation_labels"]
    assert "强风险结论" not in result["safe_summary"]


def test_invalid_packet_returns_invalid_blocked_output() -> None:
    packet = _packet_fixture("missing_required_evidence_packet.json")

    result = compose_ai_evidence_dry_run_explanation(
        packet,
        generated_at="2026-05-10T00:00:00Z",
    ).to_dict()

    assert result["validation_state"] == "invalid"
    assert result["posture"] in {"blocked", "review_required"}
    assert "证据校验未通过" in result["safe_summary"]
    assert "禁止判断" in result["safe_summary"]


def test_unknown_future_packet_version_degrades_safely() -> None:
    packet = _packet_fixture("valid_scanner_packet.json")
    packet["evidence_version"] = "ai_evidence_packet_v9"
    packet["decision_status"] = "allowed"
    packet["confidence_cap"]["value"] = 100

    result = compose_ai_evidence_dry_run_explanation(
        packet,
        generated_at="2026-05-10T00:00:00Z",
    ).to_dict()

    assert result["source_packet_version"] == "ai_evidence_packet_v9"
    assert result["validation_state"] == "invalid"
    assert result["posture"] in {"blocked", "review_required"}
    assert result["confidence_cap"] <= 40


def test_output_never_exceeds_policy_confidence_cap() -> None:
    packet = _packet_fixture("valid_scanner_packet.json")
    packet["required_evidence"][0]["status"] = "stale"
    packet["required_evidence"][0]["freshness_class"] = "stale"
    packet["quality_flags"] = []
    packet["decision_status"] = "allowed"
    packet["confidence_cap"]["value"] = 100

    result = compose_ai_evidence_dry_run_explanation(
        packet,
        generated_at="2026-05-10T00:00:00Z",
    ).to_dict()

    assert result["validation_state"] == "invalid"
    assert result["confidence_cap"] <= 75
    assert result["posture"] in {"blocked", "review_required"}


def test_user_facing_text_never_contains_forbidden_internal_terms() -> None:
    packets = [
        _packet_fixture("valid_scanner_packet.json"),
        rotation_evidence_to_ai_packet(_adapter_fixture("rotation_proxy_only_packet.json")).to_dict(),
        options_gates_to_ai_packet(_adapter_fixture("options_fail_closed_packet.json")).to_dict(),
        backtest_readiness_to_ai_packet(_adapter_fixture("backtest_research_prototype_packet.json")).to_dict(),
        portfolio_risk_to_ai_packet(_adapter_fixture("portfolio_stale_fx_packet.json")).to_dict(),
    ]

    for packet in packets:
        result = compose_ai_evidence_dry_run_explanation(
            packet,
            generated_at="2026-05-10T00:00:00Z",
        ).to_dict()
        rendered = _lowered_user_texts(result)
        for forbidden in FORBIDDEN_USER_TERMS:
            assert forbidden not in rendered


def test_same_packet_with_same_generated_time_produces_identical_output() -> None:
    packet = rotation_evidence_to_ai_packet(_adapter_fixture("rotation_proxy_only_packet.json")).to_dict()

    first = compose_ai_evidence_dry_run_explanation(
        packet,
        generated_at="2026-05-10T00:00:00Z",
    ).to_dict()
    second = compose_ai_evidence_dry_run_explanation(
        copy.deepcopy(packet),
        generated_at="2026-05-10T00:00:00Z",
    ).to_dict()

    assert first == second


def test_composer_module_does_not_import_live_ai_or_provider_runtime_modules() -> None:
    module = inspect.getmodule(compose_ai_evidence_dry_run_explanation)
    assert module is not None
    source = inspect.getsource(module)
    tree = ast.parse(source)
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )

    forbidden_modules = {
        "src.services.ai_service",
        "src.services.options_lab_service",
        "src.services.provider_runtime",
        "src.services.market_cache",
        "src.services.llm_gateway",
    }

    assert forbidden_modules.isdisjoint(imported_modules)
