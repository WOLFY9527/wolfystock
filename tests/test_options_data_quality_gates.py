# -*- coding: utf-8 -*-
"""Options Lab data-quality gate diagnostics tests."""

from __future__ import annotations

import json
from pathlib import Path

from src.services.options_data_quality_gates import evaluate_options_data_quality_gates
from src.services.options_lab_service import OptionsLabService


def _service() -> OptionsLabService:
    return OptionsLabService(fixture_path=Path("tests/fixtures/options/tem_chain.json"))


def _decision_grade_contract(contract_symbol: str):
    chain = _service().get_chain("TEM", expiration="2026-06-19", side="both", include_greeks=True)
    contract = next(
        contract
        for contract in [*chain.calls, *chain.puts]
        if contract.contract_symbol == contract_symbol
    )
    return contract.model_copy(
        update={
            "source": "approved_live_chain",
            "freshness": "fresh",
            "provider_quality": "decision_grade_candidate",
            "data_quality": {"tradeable": True, "tier": "live_usable", "hints": []},
        }
    )


def _issue_codes(diagnostics) -> set[str]:
    return {issue.code for issue in diagnostics.gate_issues}


def test_missing_bid_ask_fails_closed() -> None:
    contract = _decision_grade_contract("TEM260619C00055000").model_copy(
        update={"bid": None, "ask": None, "mid": None}
    )

    diagnostics = evaluate_options_data_quality_gates(
        strategy_key="long_call",
        contracts=[contract],
        chain_as_of="2026-05-06T13:45:00Z",
        source_type="live",
        iv_rank_status="available",
        iv_rank_source="approved_live_iv_history",
        iv_percentile=68.0,
        expected_move_source="straddle_mid",
    )

    assert diagnostics.gate_decision == "数据不足，禁止判断"
    assert diagnostics.decision_grade is False
    assert "missing_bid_ask" in diagnostics.fail_closed_reason_codes
    assert "missing_bid_ask" in _issue_codes(diagnostics)
    assert diagnostics.liquidity_gates.status == "blocked"


def test_missing_volume_and_open_interest_fail_closed() -> None:
    contract = _decision_grade_contract("TEM260619C00055000").model_copy(
        update={"volume": None, "open_interest": None}
    )

    diagnostics = evaluate_options_data_quality_gates(
        strategy_key="long_call",
        contracts=[contract],
        chain_as_of="2026-05-06T13:45:00Z",
        source_type="live",
        iv_rank_status="available",
        iv_rank_source="approved_live_iv_history",
        iv_percentile=68.0,
        expected_move_source="straddle_mid",
    )

    assert diagnostics.gate_decision == "数据不足，禁止判断"
    assert diagnostics.decision_grade is False
    assert {"missing_volume", "missing_open_interest"}.issubset(diagnostics.fail_closed_reason_codes)
    assert {"missing_volume", "missing_open_interest"}.issubset(_issue_codes(diagnostics))


def test_fixture_fallback_dry_run_stale_and_unknown_freshness_are_not_decision_grade() -> None:
    scenarios = [
        ("synthetic_options_lab_fixture", "synthetic_delayed", "synthetic_source_not_decision_grade"),
        ("fallback_provider_snapshot", "fallback", "fallback_source_not_decision_grade"),
        ("tradier_dry_run_fixture", "delayed_dry_run", "dry_run_source_not_decision_grade"),
        ("review_live_snapshot", "stale", "stale_freshness_not_decision_grade"),
        ("review_live_snapshot", "unknown", "unknown_freshness_not_decision_grade"),
    ]

    for source, freshness, expected_code in scenarios:
        contract = _decision_grade_contract("TEM260619C00055000").model_copy(
            update={
                "source": source,
                "freshness": freshness,
                "provider_quality": f"{freshness}_fixture",
                "data_quality": {"tradeable": False, "tier": "insufficient", "hints": [expected_code]},
            }
        )

        diagnostics = evaluate_options_data_quality_gates(
            strategy_key="long_call",
            contracts=[contract],
            chain_as_of="2026-05-06T13:45:00Z",
            source_type="live",
            iv_rank_status="available",
            iv_rank_source="approved_live_iv_history",
            iv_percentile=68.0,
            expected_move_source="straddle_mid",
        )

        assert diagnostics.decision_grade is False
        assert diagnostics.gate_decision == "数据不足，禁止判断"
        assert expected_code in diagnostics.fail_closed_reason_codes


def test_missing_iv_greeks_and_iv_rank_block_recommendation_grade_output() -> None:
    contract = _decision_grade_contract("TEM260619C00055000").model_copy(
        update={"implied_volatility": None, "greeks": None}
    )

    diagnostics = evaluate_options_data_quality_gates(
        strategy_key="long_call",
        contracts=[contract],
        chain_as_of="2026-05-06T13:45:00Z",
        source_type="live",
        iv_rank_status="unavailable",
        iv_rank_source=None,
        iv_percentile=None,
        expected_move_source="iv_dte",
    )

    assert diagnostics.gate_decision == "数据不足，禁止判断"
    assert diagnostics.decision_grade is False
    assert {
        "missing_iv",
        "missing_greeks",
        "missing_iv_rank_or_percentile",
    }.issubset(_issue_codes(diagnostics))


def test_snapshot_mapped_contract_preserves_gate_decision() -> None:
    service = _service()
    fixture = service._fixture_for_symbol("TEM")
    snapshot = next(
        contract
        for contract in service._contract_snapshots_for_fixture(fixture, include_greeks=True)
        if contract.contract_symbol == "TEM260619C00055000"
    )
    updates = {
        "source": "approved_live_chain",
        "freshness": "fresh",
        "provider_quality": "decision_grade_candidate",
        "data_quality": {"tradeable": True, "tier": "live_usable", "hints": []},
    }
    direct_contract = _decision_grade_contract("TEM260619C00055000")
    snapshot_contract = service._map_contract_snapshot_to_api_contract(snapshot).model_copy(update=updates)

    direct_diagnostics = evaluate_options_data_quality_gates(
        strategy_key="long_call",
        contracts=[direct_contract],
        chain_as_of="2026-05-06T13:45:00Z",
        source_type="live",
        iv_rank_status="available",
        iv_rank_source="approved_live_iv_history",
        iv_percentile=68.0,
        expected_move_source="straddle_mid",
    )
    snapshot_diagnostics = evaluate_options_data_quality_gates(
        strategy_key="long_call",
        contracts=[snapshot_contract],
        chain_as_of="2026-05-06T13:45:00Z",
        source_type="live",
        iv_rank_status="available",
        iv_rank_source="approved_live_iv_history",
        iv_percentile=68.0,
        expected_move_source="straddle_mid",
    )

    assert snapshot_diagnostics.to_dict() == direct_diagnostics.to_dict()


def test_unsupported_strategy_returns_fail_closed_diagnostics() -> None:
    contract = _decision_grade_contract("TEM260619C00055000")

    diagnostics = evaluate_options_data_quality_gates(
        strategy_key="short_call",
        contracts=[contract],
        chain_as_of="2026-05-06T13:45:00Z",
        source_type="live",
        iv_rank_status="available",
        iv_rank_source="approved_live_iv_history",
        iv_percentile=68.0,
        expected_move_source="straddle_mid",
    )

    assert diagnostics.gate_decision == "数据不足，禁止判断"
    assert diagnostics.decision_grade is False
    assert diagnostics.fail_closed_reason_codes == ["unsupported_strategy"]
    assert _issue_codes(diagnostics) == {"unsupported_strategy"}


def test_gate_diagnostics_do_not_expose_raw_provider_payloads_or_secrets() -> None:
    contract = _decision_grade_contract("TEM260619C00055000").model_copy(
        update={
            "source": "review_live_snapshot?authorization=Bearer should-not-leak",
            "provider_quality": "token=real-secret",
        }
    )

    diagnostics = evaluate_options_data_quality_gates(
        strategy_key="long_call",
        contracts=[contract],
        chain_as_of="2026-05-06T13:45:00Z",
        source_type="live",
        iv_rank_status="available",
        iv_rank_source="approved_live_iv_history",
        iv_percentile=68.0,
        expected_move_source="straddle_mid",
    )

    text = json.dumps(diagnostics.to_dict(), ensure_ascii=False, sort_keys=True).lower()
    for blocked in ("authorization", "bearer", "token=", "secret", "request", "response", "header", "cookie"):
        assert blocked not in text
