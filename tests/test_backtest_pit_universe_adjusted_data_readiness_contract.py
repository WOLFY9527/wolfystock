# -*- coding: utf-8 -*-
"""Fixture-only contract for PIT universe / adjusted-data backtest readiness."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "backtest"
    / "rule_backtest_pit_adjusted_data_readiness_v1.json"
)
EXPECTED_TOP_LEVEL_KEYS = [
    "fixture_kind",
    "fixture_version",
    "fixture_scope",
    "readiness_posture",
    "claims",
    "determinism",
]
EXPECTED_CLAIMS = {
    "point_in_time_universe_membership": {
        "state": "unavailable",
        "reason_code": "pit_universe_membership_missing",
    },
    "survivorship_bias_safe_universe_evidence": {
        "state": "unavailable",
        "reason_code": "survivorship_bias_evidence_missing",
    },
    "delisting_inactive_symbol_handling": {
        "state": "unavailable",
        "reason_code": "delisting_inactive_symbol_contract_missing",
    },
    "adjusted_ohlc_lineage": {
        "state": "unavailable",
        "reason_code": "adjusted_ohlc_lineage_missing",
    },
    "adjustment_methodology_version": {
        "state": "unavailable",
        "reason_code": "adjustment_methodology_missing",
    },
    "exchange_calendar_session_alignment": {
        "state": "unavailable",
        "reason_code": "exchange_calendar_session_contract_missing",
    },
    "symbol_identifier_lineage": {
        "state": "unavailable",
        "reason_code": "symbol_identifier_lineage_missing",
    },
    "vendor_source_provenance": {
        "state": "unavailable",
        "reason_code": "vendor_source_provenance_missing",
    },
    "as_of_timestamp_policy": {
        "state": "unavailable",
        "reason_code": "as_of_timestamp_policy_missing",
    },
    "missing_stale_bar_policy": {
        "state": "unavailable",
        "reason_code": "missing_stale_bar_policy_missing",
    },
    "historical_snapshot_reproducibility": {
        "state": "unavailable",
        "reason_code": "historical_snapshot_reproducibility_missing",
    },
    "decision_grade_institutional_readiness": {
        "state": "not_ready",
        "reason_code": "decision_grade_institutional_contract_missing",
    },
}


def _load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _assert_claim_shape(claim: dict[str, Any]) -> None:
    assert list(claim) == ["state", "ready", "reason_code", "summary"]
    assert claim["ready"] is False
    assert isinstance(claim["summary"], str)
    assert claim["summary"]


def _assert_no_promotional_or_runtime_semantics(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
    for forbidden in (
        '"provider_calls_executed": true',
        '"data_ingestion_executed": true',
        '"engine_math_changed": true',
        '"strategy_execution_implied": true',
        '"decision_grade": true',
        "winner",
        "authoritative",
        "institutional proof",
        "survivorship-bias safe",
        "survivorship bias safe",
    ):
        assert forbidden not in serialized, forbidden
    assert "authority" not in serialized


def test_pit_adjusted_data_readiness_fixture_schema_and_invariants_are_stable() -> None:
    payload = _load_fixture()

    assert list(payload) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["fixture_kind"] == "backtest_pit_adjusted_data_readiness_contract"
    assert payload["fixture_version"] == "v1"
    assert payload["fixture_scope"] == {
        "scope": "local_static_fixture",
        "diagnostic_only": True,
        "provider_calls_executed": False,
        "data_ingestion_executed": False,
        "engine_math_changed": False,
        "strategy_execution_implied": False,
        "decision_grade": False,
    }
    assert payload["readiness_posture"] == {
        "overall_state": "research_diagnostic_only",
        "pit_adjusted_institutional_ready": False,
        "survivorship_bias_safe": False,
        "historical_snapshot_reproducible": False,
        "notes": "Static fixture only; no PIT universe, adjusted-data lineage, or decision-grade claim is available.",
    }
    assert payload["determinism"] == {
        "json_safe": True,
        "deterministic_fixture": True,
        "offline_static_fixture": True,
        "generated_artifacts_required": False,
        "database_writes": False,
        "live_provider_calls": False,
    }


def test_pit_adjusted_data_readiness_high_risk_claims_remain_unavailable_or_not_ready() -> None:
    claims = _load_fixture()["claims"]

    assert list(claims) == list(EXPECTED_CLAIMS)
    for key, expected in EXPECTED_CLAIMS.items():
        claim = claims[key]
        _assert_claim_shape(claim)
        assert claim["state"] == expected["state"]
        assert claim["reason_code"] == expected["reason_code"]


def test_pit_adjusted_data_readiness_fixture_is_json_safe_deterministic_and_non_promotional() -> None:
    payload = _load_fixture()

    round_tripped = json.loads(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    assert round_tripped == payload
    _assert_no_promotional_or_runtime_semantics(payload)
