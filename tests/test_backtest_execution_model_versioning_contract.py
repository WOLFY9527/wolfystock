# -*- coding: utf-8 -*-
"""Fixture contract for current/default rule backtest execution-model metadata."""

from __future__ import annotations

import json
from pathlib import Path

from api.v1.schemas.backtest import _default_rule_backtest_execution_model
from src.core.rule_backtest_engine import RuleBacktestEngine
from src.services import rule_backtest_support_exports


FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "backtest"
    / "rule_backtest_execution_model_v1_metadata.json"
)
RUNTIME_SHARED_FIELDS = (
    "version",
    "timeframe",
    "signal_evaluation_timing",
    "entry_timing",
    "exit_timing",
    "entry_fill_price_basis",
    "exit_fill_price_basis",
    "position_sizing",
    "fee_model",
    "fee_bps_per_side",
    "slippage_model",
    "slippage_bps_per_side",
)


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _assert_no_forbidden_promotions(payload: dict) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
    for forbidden in (
        '"decision_grade": true',
        '"institutional_execution_realism": true',
        '"provider_calls_required": true',
        '"live_provider_calls_required": true',
        '"winner_promotion": true',
        '"optimizer_executed": true',
        '"parameter_sweep_executed": true',
        '"provider_calls_executed": true',
        '"silent_runtime_semantic_change_allowed": true',
    ):
        assert forbidden not in serialized, forbidden


def test_rule_backtest_execution_model_fixture_locks_current_default_metadata_contract() -> None:
    payload = _load_fixture()

    assert payload["fixture_kind"] == "rule_backtest_execution_model_metadata"
    assert payload["fixture_version"] == "v1"

    execution_model = payload["execution_model"]
    semantics = payload["semantics"]
    guardrails = payload["guardrails"]

    assert execution_model["model_id"] == "rule_backtest_default_execution_model_v1"
    assert execution_model["version"] == payload["fixture_version"]

    engine_default = RuleBacktestEngine._build_execution_model(
        timeframe="daily",
        fee_bps=0.0,
        slippage_bps=0.0,
        strategy_type="rule_conditions",
    ).to_dict()
    fixture_runtime_fields = {
        field: execution_model[field]
        for field in (*RUNTIME_SHARED_FIELDS, "market_rules")
    }
    assert fixture_runtime_fields == engine_default

    schema_default = _default_rule_backtest_execution_model().model_dump()
    assert {
        field: execution_model[field]
        for field in RUNTIME_SHARED_FIELDS
    } == {
        field: schema_default[field]
        for field in RUNTIME_SHARED_FIELDS
    }

    assert semantics == {
        "engine_identity": "existing_rule_backtest_behavior",
        "cost_realism": "baseline_bps_assumptions_only_when_present",
        "institutional_execution_realism": False,
        "market_impact_model": "not_modelled",
        "spread_simulation": "not_modelled",
        "partial_fills_supported": False,
        "halt_limit_up_limit_down_model": "not_modelled",
        "tax_model": "not_modelled",
        "stamp_duty_model": "not_modelled",
        "volume_participation_cap": "unavailable",
        "point_in_time_universe_guarantee": "unavailable",
        "adjusted_data_guarantee": "unavailable",
        "provider_calls_required": False,
        "live_provider_calls_required": False,
        "diagnostic_only": True,
        "readiness_only": True,
        "decision_grade": False,
    }
    assert guardrails == {
        "winner_promotion": False,
        "optimizer_executed": False,
        "parameter_sweep_executed": False,
        "provider_calls_executed": False,
        "silent_runtime_semantic_change_allowed": False,
        "future_semantic_changes_require_new_version": True,
        "future_versions_must_be_additive": True,
    }

    _assert_no_forbidden_promotions(payload)


def test_rule_backtest_execution_model_export_projection_matches_fixture_contract() -> None:
    assert hasattr(rule_backtest_support_exports, "build_execution_model_metadata_export")

    payload = _load_fixture()
    export_payload = rule_backtest_support_exports.build_execution_model_metadata_export(
        {
            "id": 42,
            "code": "AAPL",
            "status": "completed",
            "timeframe": "daily",
        }
    )

    assert export_payload["export_kind"] == "rule_backtest_execution_model_metadata"
    assert export_payload["version"] == payload["fixture_version"]
    assert export_payload["run_id"] == 42
    assert export_payload["code"] == "AAPL"
    assert export_payload["status"] == "completed"
    assert export_payload["timeframe"] == "daily"
    assert export_payload["execution_model"] == payload["execution_model"]
    assert export_payload["semantics"] == payload["semantics"]
    assert export_payload["guardrails"] == payload["guardrails"]

    _assert_no_forbidden_promotions(export_payload)
