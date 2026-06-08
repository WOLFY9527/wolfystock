# -*- coding: utf-8 -*-
"""Tests for the pure Backtest + Factor Lab consumer projection helper."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any

from src.services.backtest_factor_lab_readiness import (
    build_backtest_factor_lab_readiness_packet,
)
from src.services.backtest_factor_lab_consumer_projection import (
    project_backtest_factor_lab_consumer_readiness,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = REPO_ROOT / "src/services/backtest_factor_lab_consumer_projection.py"
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
    "src.services.rule_backtest_service",
    "src.services.backtest_service",
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


def _build_missing_p0_packet() -> dict[str, Any]:
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


def _build_missing_p1_packet() -> dict[str, Any]:
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


def _helper_imports() -> set[str]:
    tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def test_projection_defaults_fail_closed_into_product_safe_observation_copy() -> None:
    projection = project_backtest_factor_lab_consumer_readiness({})

    assert projection == {
        "consumerState": "INSUFFICIENT",
        "confidencePosture": "当前仅供观察",
        "shortExplanation": "关键研究资料仍不完整，当前结果更适合用作观察参考。",
        "blockedDimensionSummary": "基础研究条件仍有 7 项待补充，扩展研究条件仍有 8 项待补充。",
    }


def test_projection_maps_p0_blockers_to_insufficient_observation_only_copy() -> None:
    projection = project_backtest_factor_lab_consumer_readiness(_build_missing_p0_packet())

    assert projection == {
        "consumerState": "INSUFFICIENT",
        "confidencePosture": "当前仅供观察",
        "shortExplanation": "关键研究资料仍不完整，当前结果更适合用作观察参考。",
        "blockedDimensionSummary": "基础研究条件仍有 1 项待补充。",
    }


def test_projection_maps_p1_blockers_to_partial_observation_only_copy() -> None:
    projection = project_backtest_factor_lab_consumer_readiness(_build_missing_p1_packet())

    assert projection == {
        "consumerState": "PARTIAL",
        "confidencePosture": "置信度受限，仅供观察",
        "shortExplanation": "基础研究资料已具备，但扩展验证仍不完整。",
        "blockedDimensionSummary": "扩展研究条件仍有 1 项待补充。",
    }


def test_projection_maps_complete_packet_to_available_product_copy() -> None:
    projection = project_backtest_factor_lab_consumer_readiness(_all_prerequisites_present_packet())

    assert projection == {
        "consumerState": "AVAILABLE",
        "confidencePosture": "资料较完整，仍以研究观察为主",
        "shortExplanation": "当前回测与因子研究资料较完整，可继续查看结果与对比。",
        "blockedDimensionSummary": "当前未发现明显资料缺口。",
    }


def test_projection_is_json_safe_deterministic_and_does_not_mutate_input() -> None:
    packet = _build_missing_p1_packet()
    original = copy.deepcopy(packet)

    first = project_backtest_factor_lab_consumer_readiness(packet)
    second = project_backtest_factor_lab_consumer_readiness(packet)

    assert packet == original
    assert first == second
    assert json.loads(json.dumps(first, ensure_ascii=False, sort_keys=True)) == first
    assert set(first) == {
        "consumerState",
        "confidencePosture",
        "shortExplanation",
        "blockedDimensionSummary",
    }


def test_projection_output_stays_product_safe_and_hides_internal_fields() -> None:
    projection = project_backtest_factor_lab_consumer_readiness(_build_missing_p0_packet())
    serialized = json.dumps(projection, ensure_ascii=False, sort_keys=True).lower()

    for forbidden in (
        "profession",
        "institution",
        "sourceauthority",
        "professionalready",
        "productstate",
        "blockingdimensionids",
        "dimensioncounts",
        "missingreasoncodes",
        "pit_as_of",
        "transaction_cost_realism",
        "p0",
        "p1",
        "provider",
        "cache",
        "storage",
        "engine",
    ):
        assert forbidden not in serialized, forbidden


def test_projection_module_imports_stay_pure_and_away_from_protected_domains() -> None:
    imports = _helper_imports()

    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)
