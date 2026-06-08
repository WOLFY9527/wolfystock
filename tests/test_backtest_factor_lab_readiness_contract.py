# -*- coding: utf-8 -*-
"""Contract tests for the observe-only Backtest + Factor Lab readiness packet."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any

from src.services.backtest_factor_lab_readiness import (
    build_backtest_factor_lab_readiness_packet,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = REPO_ROOT / "src/services/backtest_factor_lab_readiness.py"
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
    "src.services.backtest_professional_readiness",
)
EXPECTED_P0_DIMENSIONS = [
    "pit_as_of",
    "survivorship_delisted",
    "corporate_actions",
    "calendar_session_halt_constraints",
    "transaction_cost_realism",
    "portfolio_rebalance_model",
    "dataset_snapshot_version_source_authority",
]
EXPECTED_P1_DIMENSIONS = [
    "decile_returns",
    "panel_contract",
    "forward_return_generation",
    "neutralization",
    "factor_correlation",
    "multi_factor_composition",
    "oos_walk_forward",
    "parameter_stability",
]


def _dimension_map(payload: dict[str, Any], priority: str) -> dict[str, dict[str, Any]]:
    return {
        item["id"]: item
        for item in payload["dimensions"][priority]
    }


def _helper_imports() -> set[str]:
    tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def _assert_packet_guardrails(payload: dict[str, Any]) -> None:
    assert payload["packetKind"] == "backtest_factor_lab_readiness_packet"
    assert payload["packetVersion"] == "backtest_factor_lab_readiness_v1"
    assert payload["observeOnly"] is True
    assert payload["professionalReady"] is False
    assert payload["productState"] == "observe_only_not_professional_ready"


def _assert_no_recommendation_language(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
    for forbidden in (
        "buy",
        "sell",
        "order",
        "recommended trade",
        "decision-grade",
        "actionable",
        "execute now",
    ):
        assert forbidden not in serialized, forbidden


def test_packet_defaults_fail_closed_when_inputs_are_missing() -> None:
    packet = build_backtest_factor_lab_readiness_packet()

    _assert_packet_guardrails(packet)
    _assert_no_recommendation_language(packet)
    assert packet["dimensionCounts"] == {
        "p0": {"available": 0, "missing": 0, "ambiguous": 7},
        "p1": {"available": 0, "missing": 0, "ambiguous": 8},
    }
    assert packet["blockingPriority"] == "P0"
    assert packet["blockingDimensionIds"] == [
        "pit_as_of",
        "survivorship_delisted",
        "corporate_actions",
        "calendar_session_halt_constraints",
        "transaction_cost_realism",
        "portfolio_rebalance_model",
        "dataset_snapshot_version_source_authority",
        "decile_returns",
        "panel_contract",
        "forward_return_generation",
        "neutralization",
        "factor_correlation",
        "multi_factor_composition",
        "oos_walk_forward",
        "parameter_stability",
    ]
    p0_dimensions = _dimension_map(packet, "p0")
    p1_dimensions = _dimension_map(packet, "p1")
    assert list(p0_dimensions) == EXPECTED_P0_DIMENSIONS
    assert list(p1_dimensions) == EXPECTED_P1_DIMENSIONS
    assert all(item["state"] == "ambiguous" for item in p0_dimensions.values())
    assert all(item["state"] == "ambiguous" for item in p1_dimensions.values())


def test_explicit_missing_or_ambiguous_prerequisites_fail_closed() -> None:
    packet = build_backtest_factor_lab_readiness_packet(
        backtest_readiness={
            "point_in_time_universe_membership": "available",
            "as_of_timestamp_policy": "unknown",
            "exchange_calendar_session_alignment": "available",
            "halt_constraints": "modelled",
        },
        factor_metrics_availability={
            "decile_returns": "ready",
            "factor_correlation": "available",
        },
        bridge_manifest={
            "panel_contract": "available",
            "multi_factor_composition": "supported",
        },
        data_lineage={
            "dataset_snapshot": "available",
            "dataset_version": "unknown",
            "source_authority": "available",
        },
        missing_professional_prerequisites=[
            "survivorship_delisted",
            "parameter_stability",
        ],
    )

    _assert_packet_guardrails(packet)
    p0_dimensions = _dimension_map(packet, "p0")
    p1_dimensions = _dimension_map(packet, "p1")
    assert p0_dimensions["pit_as_of"]["state"] == "ambiguous"
    assert p0_dimensions["pit_as_of"]["missingReasonCodes"] == [
        "pit_as_of_missing_or_ambiguous",
    ]
    assert p0_dimensions["survivorship_delisted"]["state"] == "missing"
    assert "survivorship_delisted_listed_missing" in p0_dimensions["survivorship_delisted"]["missingReasonCodes"]
    assert p0_dimensions["dataset_snapshot_version_source_authority"]["state"] == "ambiguous"
    assert p1_dimensions["parameter_stability"]["state"] == "missing"
    assert "parameter_stability_listed_missing" in p1_dimensions["parameter_stability"]["missingReasonCodes"]
    assert p1_dimensions["decile_returns"]["state"] == "available"
    assert p1_dimensions["panel_contract"]["state"] == "available"


def test_all_required_prerequisites_must_be_explicit_to_mark_professional_ready() -> None:
    packet = build_backtest_factor_lab_readiness_packet(
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

    assert packet["professionalReady"] is True
    assert packet["productState"] == "observe_only_prerequisites_present"
    assert packet["blockingPriority"] == "none"
    assert packet["blockingDimensionIds"] == []
    assert packet["dimensionCounts"] == {
        "p0": {"available": 7, "missing": 0, "ambiguous": 0},
        "p1": {"available": 8, "missing": 0, "ambiguous": 0},
    }
    assert all(item["state"] == "available" for item in packet["dimensions"]["p0"])
    assert all(item["state"] == "available" for item in packet["dimensions"]["p1"])


def test_packet_is_deterministic_json_safe_and_does_not_mutate_inputs() -> None:
    inputs = {
        "backtest_readiness": {
            "point_in_time_universe_membership": "available",
            "as_of_timestamp_policy": "available",
        },
        "factor_metrics_availability": {
            "decile_returns": "available",
        },
        "bridge_manifest": {
            "panel_contract": "available",
        },
        "data_lineage": {
            "dataset_snapshot": "available",
        },
        "missing_professional_prerequisites": ["oos_walk_forward"],
    }
    original = copy.deepcopy(inputs)

    first = build_backtest_factor_lab_readiness_packet(**inputs)
    second = build_backtest_factor_lab_readiness_packet(**inputs)

    assert inputs == original
    assert first == second
    assert json.loads(json.dumps(first, ensure_ascii=False, sort_keys=True)) == first


def test_helper_imports_stay_pure_and_away_from_protected_domains() -> None:
    imports = _helper_imports()

    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)
