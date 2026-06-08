# -*- coding: utf-8 -*-
"""Tests for Backtest + Factor Lab report-safe readiness summaries."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any

from src.services.backtest_factor_lab_consumer_projection import (
    project_backtest_factor_lab_consumer_readiness,
)
from src.services.backtest_factor_lab_readiness import (
    build_backtest_factor_lab_readiness_packet,
)
from src.services.backtest_factor_lab_report_summary import (
    build_backtest_factor_lab_report_summary,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = REPO_ROOT / "src/services/backtest_factor_lab_report_summary.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "api",
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib",
    "urllib3",
    "yfinance",
    "src.core",
    "src.repositories",
    "src.storage",
    "src.services.market_cache",
    "src.services.backtest_service",
    "src.services.rule_backtest_service",
)
FORBIDDEN_OUTPUT_TERMS = (
    "professionalready",
    "productstate",
    "blockingdimensionids",
    "dimensioncounts",
    "missingreasoncodes",
    "sourceauthority",
    "sourceauthorityallowed",
    "reasoncode",
    "provider",
    "cache",
    "storage",
    "engine",
    "fallback",
    "raw json",
    "pit_as_of",
    "transaction_cost_realism",
    "dataset_snapshot_version_source_authority",
    "p0",
    "p1",
    "institution",
    "institutional",
    "live trading",
    "professional",
)


def _all_prerequisites_present_packet() -> dict[str, Any]:
    return build_backtest_factor_lab_readiness_packet(
        backtest_readiness={
            "point_in_time_universe_membership": "available",
            "as_of_timestamp_policy": "available",
            "survivorship_bias_safe_universe_evidence": "available",
            "delisting_inactive_symbol_handling": "available",
            "corporate_action_adjusted_ohlc_lineage": "available",
            "exchange_calendar_session_alignment": "available",
            "session_constraints": "available",
            "halt_constraints": "available",
            "transaction_cost_model": "available",
            "slippage_model": "available",
            "market_impact_model": "available",
            "portfolio_rebalance_model": "available",
            "oos_walk_forward": "available",
            "parameter_stability": "available",
        },
        factor_metrics_availability={
            "decile_returns": "available",
            "forward_return_generation": "available",
            "neutralization": "available",
            "factor_correlation": "available",
            "parameter_stability": "available",
        },
        bridge_manifest={
            "panel_contract": "available",
            "multi_factor_composition": "available",
            "oos_walk_forward": "available",
        },
        data_lineage={
            "dataset_snapshot": "available",
            "dataset_version": "available",
            "source_authority": "available",
        },
    )


def _missing_p0_packet() -> dict[str, Any]:
    return build_backtest_factor_lab_readiness_packet(
        backtest_readiness={
            "point_in_time_universe_membership": "available",
            "as_of_timestamp_policy": "available",
            "survivorship_bias_safe_universe_evidence": "available",
            "delisting_inactive_symbol_handling": "available",
            "corporate_action_adjusted_ohlc_lineage": "available",
            "exchange_calendar_session_alignment": "available",
            "session_constraints": "available",
            "halt_constraints": "available",
            "transaction_cost_model": "missing",
            "slippage_model": "missing",
            "market_impact_model": "missing",
            "portfolio_rebalance_model": "available",
            "oos_walk_forward": "available",
            "parameter_stability": "available",
        },
        factor_metrics_availability={
            "decile_returns": "available",
            "forward_return_generation": "available",
            "neutralization": "available",
            "factor_correlation": "available",
            "parameter_stability": "available",
        },
        bridge_manifest={
            "panel_contract": "available",
            "multi_factor_composition": "available",
            "oos_walk_forward": "available",
        },
        data_lineage={
            "dataset_snapshot": "available",
            "dataset_version": "available",
            "source_authority": "available",
        },
    )


def _missing_p1_packet() -> dict[str, Any]:
    return build_backtest_factor_lab_readiness_packet(
        backtest_readiness={
            "point_in_time_universe_membership": "available",
            "as_of_timestamp_policy": "available",
            "survivorship_bias_safe_universe_evidence": "available",
            "delisting_inactive_symbol_handling": "available",
            "corporate_action_adjusted_ohlc_lineage": "available",
            "exchange_calendar_session_alignment": "available",
            "session_constraints": "available",
            "halt_constraints": "available",
            "transaction_cost_model": "available",
            "slippage_model": "available",
            "market_impact_model": "available",
            "portfolio_rebalance_model": "available",
            "oos_walk_forward": "available",
        },
        factor_metrics_availability={
            "decile_returns": "available",
            "forward_return_generation": "available",
            "neutralization": "available",
            "factor_correlation": "available",
            "parameter_stability": "missing",
        },
        bridge_manifest={
            "panel_contract": "available",
            "multi_factor_composition": "available",
            "oos_walk_forward": "available",
        },
        data_lineage={
            "dataset_snapshot": "available",
            "dataset_version": "available",
            "source_authority": "available",
        },
    )


def _serialize(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _assert_report_safe(summary: dict[str, Any]) -> None:
    serialized = _serialize(summary)
    lowered = serialized.lower()

    assert json.loads(serialized) == summary
    assert set(summary) == {
        "title",
        "shortStatus",
        "observeOnlyWording",
        "limitations",
        "missingPrerequisiteGroups",
    }
    assert "仅供观察" in serialized
    assert "不构成投资建议" in serialized
    assert "不构成买卖建议" in serialized
    for forbidden in FORBIDDEN_OUTPUT_TERMS:
        assert forbidden not in lowered, forbidden
    for forbidden in ("买入按钮", "下单", "立即交易", "必买", "稳赚", "保证收益", "guaranteed"):
        assert forbidden not in serialized, forbidden


def _helper_imports() -> set[str]:
    tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def test_report_summary_maps_p0_blockers_to_safe_observe_only_summary() -> None:
    packet = _missing_p0_packet()
    projection = project_backtest_factor_lab_consumer_readiness(packet)

    summary = build_backtest_factor_lab_report_summary(
        readiness_packet=packet,
        consumer_projection=projection,
    )

    assert summary["title"] == "回测与因子研究资料摘要"
    assert summary["shortStatus"] == "关键资料不足，仅供观察"
    assert summary["limitations"] == [
        "关键研究资料仍不完整，当前结果更适合作为观察参考。",
        "本摘要不构成投资建议，不构成买卖建议，也不构成执行指令。",
    ]
    assert summary["missingPrerequisiteGroups"] == [
        {
            "name": "基础研究资料",
            "status": "待补充",
            "items": ["交易成本、滑点与冲击约束"],
        },
    ]
    _assert_report_safe(summary)


def test_report_summary_maps_p1_blockers_to_safe_partial_summary() -> None:
    packet = _missing_p1_packet()

    summary = build_backtest_factor_lab_report_summary(readiness_packet=packet)

    assert summary["shortStatus"] == "扩展验证不完整，仅供观察"
    assert summary["limitations"] == [
        "基础研究资料已具备，但扩展验证仍不完整，置信度受限。",
        "本摘要不构成投资建议，不构成买卖建议，也不构成执行指令。",
    ]
    assert summary["missingPrerequisiteGroups"] == [
        {
            "name": "扩展验证资料",
            "status": "待补充",
            "items": ["参数稳定性检查"],
        },
    ]
    _assert_report_safe(summary)


def test_report_summary_maps_complete_metadata_without_promoting_actionability() -> None:
    packet = _all_prerequisites_present_packet()
    packet_before = copy.deepcopy(packet)

    summary = build_backtest_factor_lab_report_summary(readiness_packet=packet)

    assert packet == packet_before
    assert summary["shortStatus"] == "资料较完整，仍以观察为主"
    assert summary["limitations"] == [
        "资料较完整仍不代表未来表现承诺。",
        "本摘要不构成投资建议，不构成买卖建议，也不构成执行指令。",
    ]
    assert summary["missingPrerequisiteGroups"] == []
    _assert_report_safe(summary)


def test_report_summary_fails_closed_for_malformed_or_polluted_input() -> None:
    malformed_packet = {
        "professionalReady": True,
        "dimensionCounts": {"p0": "bad"},
        "dimensions": {
            "p0": [
                {
                    "id": "provider_cache_storage_engine",
                    "state": "missing",
                    "label": "provider cache storage engine diagnostics",
                },
            ],
        },
    }
    polluted_projection = {
        "consumerState": "AVAILABLE",
        "shortExplanation": "provider cache storage engine raw JSON",
    }

    summary = build_backtest_factor_lab_report_summary(
        readiness_packet=malformed_packet,
        consumer_projection=polluted_projection,
    )

    assert summary["shortStatus"] == "资料状态待确认，仅供观察"
    assert summary["limitations"] == [
        "输入资料缺失或格式无法确认，默认按资料不足处理。",
        "本摘要不构成投资建议，不构成买卖建议，也不构成执行指令。",
    ]
    assert summary["missingPrerequisiteGroups"] == [
        {
            "name": "基础研究资料",
            "status": "待确认",
            "items": ["资料状态待确认"],
        },
        {
            "name": "扩展验证资料",
            "status": "待确认",
            "items": ["资料状态待确认"],
        },
    ]
    _assert_report_safe(summary)


def test_report_summary_can_use_consumer_projection_without_readiness_packet() -> None:
    summary = build_backtest_factor_lab_report_summary(
        consumer_projection={
            "consumerState": "PARTIAL",
            "confidencePosture": "置信度受限，仅供观察",
            "shortExplanation": "基础研究资料已具备，但扩展验证仍不完整。",
        },
    )

    assert summary["shortStatus"] == "扩展验证不完整，仅供观察"
    assert summary["missingPrerequisiteGroups"] == [
        {
            "name": "扩展验证资料",
            "status": "待确认",
            "items": ["扩展验证资料待确认"],
        },
    ]
    _assert_report_safe(summary)


def test_report_summary_module_imports_stay_pure_and_away_from_protected_domains() -> None:
    imports = _helper_imports()

    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)
