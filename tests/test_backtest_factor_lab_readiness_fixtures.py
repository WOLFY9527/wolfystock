# -*- coding: utf-8 -*-
"""Fixture catalog tests for Backtest + Factor Lab readiness packet states."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from src.services.backtest_factor_lab_readiness import (
    build_backtest_factor_lab_readiness_packet,
)


def _all_prerequisites_present_inputs() -> dict[str, Any]:
    return {
        "backtest_readiness": {
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
        "factor_metrics_availability": {
            "decile_returns": "available",
            "forward_return_generation": "available",
            "neutralization": "available",
            "factor_correlation": "available",
            "parameter_stability": "available",
        },
        "bridge_manifest": {
            "panel_contract": "available",
            "multi_factor_composition": "available",
            "oos_walk_forward": "available",
        },
        "data_lineage": {
            "dataset_snapshot": "available",
            "dataset_version": "available",
            "source_authority": "available",
        },
    }


def _prototype_ready_inputs() -> dict[str, Any]:
    inputs = _all_prerequisites_present_inputs()
    del inputs["backtest_readiness"]["oos_walk_forward"]
    del inputs["backtest_readiness"]["parameter_stability"]
    del inputs["factor_metrics_availability"]["parameter_stability"]
    del inputs["bridge_manifest"]["oos_walk_forward"]
    return inputs


def _missing_p0_inputs() -> dict[str, Any]:
    inputs = _all_prerequisites_present_inputs()
    inputs["backtest_readiness"]["transaction_cost_model"] = "missing"
    inputs["backtest_readiness"]["slippage_model"] = "missing"
    inputs["backtest_readiness"]["market_impact_model"] = "missing"
    return inputs


def _missing_p1_inputs() -> dict[str, Any]:
    inputs = _all_prerequisites_present_inputs()
    del inputs["backtest_readiness"]["parameter_stability"]
    inputs["factor_metrics_availability"]["parameter_stability"] = "missing"
    return inputs


def _ambiguous_lineage_inputs() -> dict[str, Any]:
    inputs = _all_prerequisites_present_inputs()
    inputs["data_lineage"]["dataset_version"] = ["available", "unknown"]
    return inputs


FIXTURE_CATALOG = {
    "prototype_ready": {
        "inputs": _prototype_ready_inputs(),
        "expected_professional_ready": False,
        "expected_product_state": "observe_only_not_professional_ready",
        "expected_blocking_priority": "P1",
        "expected_blocking_dimension_ids": ["oos_walk_forward", "parameter_stability"],
        "expected_dimension_counts": {
            "p0": {"available": 7, "missing": 0, "ambiguous": 0},
            "p1": {"available": 6, "missing": 0, "ambiguous": 2},
        },
        "expected_states": {
            "transaction_cost_realism": "available",
            "oos_walk_forward": "ambiguous",
            "parameter_stability": "ambiguous",
        },
    },
    "missing_p0": {
        "inputs": _missing_p0_inputs(),
        "expected_professional_ready": False,
        "expected_product_state": "observe_only_not_professional_ready",
        "expected_blocking_priority": "P0",
        "expected_blocking_dimension_ids": ["transaction_cost_realism"],
        "expected_dimension_counts": {
            "p0": {"available": 6, "missing": 1, "ambiguous": 0},
            "p1": {"available": 8, "missing": 0, "ambiguous": 0},
        },
        "expected_states": {
            "transaction_cost_realism": "missing",
            "oos_walk_forward": "available",
            "parameter_stability": "available",
        },
    },
    "missing_p1": {
        "inputs": _missing_p1_inputs(),
        "expected_professional_ready": False,
        "expected_product_state": "observe_only_not_professional_ready",
        "expected_blocking_priority": "P1",
        "expected_blocking_dimension_ids": ["parameter_stability"],
        "expected_dimension_counts": {
            "p0": {"available": 7, "missing": 0, "ambiguous": 0},
            "p1": {"available": 7, "missing": 1, "ambiguous": 0},
        },
        "expected_states": {
            "transaction_cost_realism": "available",
            "oos_walk_forward": "available",
            "parameter_stability": "missing",
        },
    },
    "ambiguous_lineage": {
        "inputs": _ambiguous_lineage_inputs(),
        "expected_professional_ready": False,
        "expected_product_state": "observe_only_not_professional_ready",
        "expected_blocking_priority": "P0",
        "expected_blocking_dimension_ids": ["dataset_snapshot_version_source_authority"],
        "expected_dimension_counts": {
            "p0": {"available": 6, "missing": 0, "ambiguous": 1},
            "p1": {"available": 8, "missing": 0, "ambiguous": 0},
        },
        "expected_states": {
            "dataset_snapshot_version_source_authority": "ambiguous",
            "oos_walk_forward": "available",
            "parameter_stability": "available",
        },
    },
    "all_prerequisites_present": {
        "inputs": _all_prerequisites_present_inputs(),
        "expected_professional_ready": True,
        "expected_product_state": "observe_only_prerequisites_present",
        "expected_blocking_priority": "none",
        "expected_blocking_dimension_ids": [],
        "expected_dimension_counts": {
            "p0": {"available": 7, "missing": 0, "ambiguous": 0},
            "p1": {"available": 8, "missing": 0, "ambiguous": 0},
        },
        "expected_states": {
            "dataset_snapshot_version_source_authority": "available",
            "transaction_cost_realism": "available",
            "oos_walk_forward": "available",
            "parameter_stability": "available",
        },
    },
}


def _dimension_map(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["id"]: item
        for priority in ("p0", "p1")
        for item in packet["dimensions"][priority]
    }


def test_fixture_catalog_covers_required_packet_states() -> None:
    assert set(FIXTURE_CATALOG) == {
        "prototype_ready",
        "missing_p0",
        "missing_p1",
        "ambiguous_lineage",
        "all_prerequisites_present",
    }


@pytest.mark.parametrize("fixture_name", list(FIXTURE_CATALOG))
def test_fixture_catalog_matches_expected_packet_states(fixture_name: str) -> None:
    fixture = FIXTURE_CATALOG[fixture_name]
    packet = build_backtest_factor_lab_readiness_packet(**deepcopy(fixture["inputs"]))
    dimension_map = _dimension_map(packet)

    assert packet["observeOnly"] is True
    assert packet["professionalReady"] is fixture["expected_professional_ready"]
    assert packet["productState"] == fixture["expected_product_state"]
    assert packet["blockingPriority"] == fixture["expected_blocking_priority"]
    assert packet["blockingDimensionIds"] == fixture["expected_blocking_dimension_ids"]
    assert packet["dimensionCounts"] == fixture["expected_dimension_counts"]
    for dimension_id, expected_state in fixture["expected_states"].items():
        assert dimension_map[dimension_id]["state"] == expected_state


def test_professional_ready_remains_false_until_every_p0_and_p1_dimension_is_explicit() -> None:
    for fixture_name, fixture in FIXTURE_CATALOG.items():
        packet = build_backtest_factor_lab_readiness_packet(**deepcopy(fixture["inputs"]))
        if fixture_name == "all_prerequisites_present":
            assert packet["professionalReady"] is True
            assert packet["blockingDimensionIds"] == []
            continue
        assert packet["professionalReady"] is False, fixture_name
        assert packet["observeOnly"] is True, fixture_name
        assert packet["blockingDimensionIds"], fixture_name


def test_ambiguous_lineage_fixture_stays_fail_closed_on_mixed_dataset_version_evidence() -> None:
    packet = build_backtest_factor_lab_readiness_packet(
        **deepcopy(FIXTURE_CATALOG["ambiguous_lineage"]["inputs"])
    )
    dimension = _dimension_map(packet)["dataset_snapshot_version_source_authority"]
    component_map = {
        component["id"]: component
        for component in dimension["components"]
    }

    assert packet["professionalReady"] is False
    assert dimension["state"] == "ambiguous"
    assert dimension["missingReasonCodes"] == [
        "dataset_snapshot_version_source_authority_missing_or_ambiguous",
    ]
    assert component_map["dataset_version"]["state"] == "ambiguous"
    assert component_map["dataset_version"]["missingReasonCodes"] == [
        "dataset_version_conflicting_evidence",
    ]
    assert component_map["dataset_version"]["evidencePaths"] == [
        "data_lineage.dataset_version",
        "data_lineage.dataset_version.0",
        "data_lineage.dataset_version.1",
    ]
