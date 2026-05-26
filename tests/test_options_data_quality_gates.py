# -*- coding: utf-8 -*-
"""Options Lab data-quality gate diagnostics tests."""

from __future__ import annotations

import json
import re
from pathlib import Path

from src.services.options_data_quality_gates import (
    INTERNAL_OPTIONS_PROVIDER_AUTHORITY_POLICY_SOURCE,
    build_options_provider_authority_contract,
    build_options_provider_live_evidence_contract,
    evaluate_options_data_quality_gates,
)
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


def _clear_gate_contract(contract_symbol: str = "TEM260619C00055000"):
    return _decision_grade_contract(contract_symbol).model_copy(
        update={"bid": 2.60, "ask": 2.70, "mid": 2.65, "spread_pct": 3.77}
    )


def _authorized_live_provider_authority() -> dict[str, object]:
    return {
        "providerId": "approved_live_test_provider",
        "sourceType": "live",
        "fixtureOnly": False,
        "liveEnabled": True,
        "tradeableData": True,
        "authorityPolicySource": INTERNAL_OPTIONS_PROVIDER_AUTHORITY_POLICY_SOURCE,
        "authorityTier": "decision_grade",
    }


def _complete_live_evidence(**overrides) -> dict[str, object]:
    payload = {
        "provider_id": "approved_live_test_provider",
        "provider_kind": "market_data",
        "source_type": "live",
        "live_enabled": True,
        "tradeable_data": True,
        "quote_freshness": "fresh",
        "quote_as_of": "2026-05-06T13:45:00Z",
        "chain_freshness": "fresh",
        "chain_as_of": "2026-05-06T13:45:00Z",
        "expiration_coverage": "complete",
        "bid_ask_coverage": "complete",
        "open_interest_coverage": "complete",
        "volume_coverage": "complete",
        "iv_coverage": "complete",
        "greeks_coverage": "complete",
        "iv_rank_authority": "authorized_live",
        "event_calendar_authority": "authorized_live",
        "provider_sla_status": "unknown",
        "sandbox_or_production": "sandbox",
    }
    payload.update(overrides)
    return build_options_provider_live_evidence_contract(**payload)


def _evaluate_single_contract(contract, **overrides):
    params = {
        "strategy_key": "long_call",
        "contracts": [contract],
        "chain_as_of": "2026-05-06T13:45:00Z",
        "source_type": "live",
        "iv_rank_status": "available",
        "iv_rank_source": "approved_live_iv_history",
        "iv_percentile": 68.0,
        "expected_move_source": "straddle_mid",
        "provider_authority": _authorized_live_provider_authority(),
    }
    params.update(overrides)
    return evaluate_options_data_quality_gates(**params)


def _issue_codes(diagnostics) -> set[str]:
    return {issue.code for issue in diagnostics.gate_issues}


def test_complete_tradier_live_evidence_still_cannot_override_internal_observation_only_policy() -> None:
    provider_authority = build_options_provider_authority_contract(
        provider_id="tradier",
        source_type="live",
        fixture_only=False,
        live_enabled=True,
        tradeable_data=True,
    )
    evidence = _complete_live_evidence(provider_id="tradier")

    diagnostics = _evaluate_single_contract(
        _clear_gate_contract(),
        provider_authority=provider_authority,
        provider_live_evidence=evidence,
    )

    assert evidence["analysisReady"] is True
    assert evidence["decisionReady"] is True
    assert "decisionGrade" not in evidence
    assert provider_authority["authorityTier"] == "live_observation_only"
    assert diagnostics.decision_grade is False
    assert diagnostics.gate_decision == "数据不足，禁止判断"
    assert diagnostics.fail_closed_reason_codes == ["provider_authority_tier_observation_only"]


def test_live_evidence_identifies_missing_freshness_coverage_and_authority_gaps() -> None:
    evidence = _complete_live_evidence(
        quote_freshness=None,
        chain_freshness="unknown",
        iv_coverage="missing",
        greeks_coverage="missing",
        iv_rank_authority=None,
        event_calendar_authority=None,
        requires_event_calendar=True,
    )

    assert evidence["analysisReady"] is False
    assert evidence["decisionReady"] is False
    assert evidence["reasonCodes"] == [
        "live_evidence_quote_freshness_missing",
        "live_evidence_chain_freshness_unknown",
        "live_evidence_iv_coverage_missing",
        "live_evidence_greeks_coverage_missing",
        "live_evidence_iv_rank_authority_missing",
        "live_evidence_event_calendar_authority_missing",
    ]
    assert all(re.fullmatch(r"[a-z][a-z0-9_]{2,80}", code) for code in evidence["reasonCodes"])


def test_live_evidence_blocks_fixture_dry_run_stub_adapter_and_synthetic_sources() -> None:
    scenarios = [
        ({"fixture": True}, "live_evidence_fixture_blocked"),
        ({"dry_run": True}, "live_evidence_dry_run_blocked"),
        ({"stub": True}, "live_evidence_stub_blocked"),
        ({"adapter_contract": True}, "live_evidence_adapter_contract_blocked"),
        ({"synthetic": True}, "live_evidence_synthetic_blocked"),
    ]

    for flags, expected_code in scenarios:
        evidence = _complete_live_evidence(**flags)

        assert evidence["analysisReady"] is False
        assert evidence["decisionReady"] is False
        assert expected_code in evidence["reasonCodes"]
        assert "decisionGrade" not in evidence


def test_provider_self_claims_cannot_override_live_evidence_contract() -> None:
    complete_claimed_evidence = _complete_live_evidence(
        provider_decision_authority_claim=True,
        recommendation_authority_claim=True,
    )
    evidence = _complete_live_evidence(
        provider_decision_authority_claim=True,
        recommendation_authority_claim=True,
        quote_freshness=None,
    )

    diagnostics = _evaluate_single_contract(
        _clear_gate_contract(),
        provider_live_evidence=evidence,
    )

    assert complete_claimed_evidence["analysisReady"] is True
    assert complete_claimed_evidence["decisionReady"] is False
    assert complete_claimed_evidence["reasonCodes"] == ["live_evidence_provider_self_claim_ignored"]
    assert evidence["analysisReady"] is False
    assert evidence["decisionReady"] is False
    assert "live_evidence_provider_self_claim_ignored" in evidence["reasonCodes"]
    assert "live_evidence_quote_freshness_missing" in evidence["reasonCodes"]
    assert diagnostics.decision_grade is False
    assert "live_evidence_quote_freshness_missing" in diagnostics.fail_closed_reason_codes


def test_required_event_calendar_missing_fails_closed() -> None:
    diagnostics = _evaluate_single_contract(
        _clear_gate_contract(),
        requires_event_calendar=True,
        event_calendar=None,
    )

    assert diagnostics.gate_decision == "数据不足，禁止判断"
    assert diagnostics.decision_grade is False
    assert diagnostics.fail_closed_reason_codes == ["missing_event_calendar"]
    assert _issue_codes(diagnostics) == {"missing_event_calendar"}
    assert diagnostics.data_quality_gates.status == "blocked"


def test_required_event_calendar_present_satisfies_event_requirement() -> None:
    diagnostics = _evaluate_single_contract(
        _clear_gate_contract(),
        requires_event_calendar=True,
        event_calendar={"events": [{"date": "2026-06-01", "type": "earnings"}]},
    )

    assert diagnostics.decision_grade is True
    assert diagnostics.fail_closed_reason_codes == []
    assert "missing_event_calendar" not in _issue_codes(diagnostics)
    assert diagnostics.data_quality_gates.status == "clear"
    assert diagnostics.liquidity_gates.status == "clear"


def test_otherwise_clean_live_shaped_contract_without_provider_authority_fails_closed() -> None:
    diagnostics = _evaluate_single_contract(_clear_gate_contract(), provider_authority=None)

    assert diagnostics.gate_decision == "数据不足，禁止判断"
    assert diagnostics.decision_grade is False
    assert diagnostics.fail_closed_reason_codes == ["provider_authority_missing"]
    assert _issue_codes(diagnostics) == {"provider_authority_missing"}
    assert diagnostics.data_quality_gates.status == "clear"
    assert diagnostics.data_quality_gates.decision_grade is True
    assert diagnostics.liquidity_gates.status == "clear"
    assert diagnostics.liquidity_gates.decision_grade is True


def test_otherwise_clean_live_shaped_contract_without_decision_authority_fails_closed() -> None:
    provider_authority = {
        **_authorized_live_provider_authority(),
        "authorityTier": "live_analysis_grade",
    }

    diagnostics = _evaluate_single_contract(
        _clear_gate_contract(),
        provider_authority=provider_authority,
    )

    assert diagnostics.decision_grade is False
    assert diagnostics.fail_closed_reason_codes == ["provider_authority_tier_analysis_only"]
    assert _issue_codes(diagnostics) == {"provider_authority_tier_analysis_only"}
    assert diagnostics.data_quality_gates.status == "clear"
    assert diagnostics.liquidity_gates.status == "clear"


def test_provider_payload_self_authority_claim_cannot_self_authorize_without_internal_policy() -> None:
    diagnostics = _evaluate_single_contract(
        _clear_gate_contract(),
        provider_authority={
            "providerId": "over_eager_provider",
            "sourceType": "live",
            "fixtureOnly": False,
            "liveEnabled": True,
            "tradeableData": True,
            "providerDecisionAuthority": True,
        },
    )

    assert diagnostics.gate_decision == "数据不足，禁止判断"
    assert diagnostics.decision_grade is False
    assert "provider_self_authority_ignored" in diagnostics.fail_closed_reason_codes
    assert "provider_authority_tier_missing" in diagnostics.fail_closed_reason_codes
    assert diagnostics.data_quality_gates.status == "clear"
    assert diagnostics.liquidity_gates.status == "clear"


def test_provider_capability_recommendation_claim_cannot_self_authorize_without_internal_policy() -> None:
    diagnostics = _evaluate_single_contract(
        _clear_gate_contract(),
        provider_authority={
            "providerId": "over_eager_provider",
            "sourceType": "live",
            "fixtureOnly": False,
            "liveEnabled": True,
            "tradeableData": True,
            "recommendationAuthority": True,
        },
    )

    assert diagnostics.gate_decision == "数据不足，禁止判断"
    assert diagnostics.decision_grade is False
    assert "provider_self_authority_ignored" in diagnostics.fail_closed_reason_codes
    assert "provider_authority_tier_missing" in diagnostics.fail_closed_reason_codes
    assert diagnostics.data_quality_gates.status == "clear"
    assert diagnostics.liquidity_gates.status == "clear"


def test_live_probe_success_alone_cannot_authorize_decision_grade() -> None:
    diagnostics = _evaluate_single_contract(
        _clear_gate_contract(),
        provider_authority={
            "providerId": "tradier",
            "sourceType": "live",
            "fixtureOnly": False,
            "liveEnabled": True,
            "tradeableData": True,
            "liveProbe": {
                "enabled": True,
                "reasonCode": "options_provider_live_probe_operator_opt_in_ready",
                "networkCallExecuted": False,
            },
        },
    )

    assert diagnostics.gate_decision == "数据不足，禁止判断"
    assert diagnostics.decision_grade is False
    assert "provider_authority_tier_missing" in diagnostics.fail_closed_reason_codes
    assert diagnostics.data_quality_gates.status == "clear"
    assert diagnostics.liquidity_gates.status == "clear"


def test_internal_policy_keeps_current_provider_ids_below_decision_grade() -> None:
    current_provider_ids = [
        "synthetic_fixture",
        "delayed_fixture",
        "malformed_fixture",
        "tradier",
        "ibkr",
        "polygon",
    ]

    for provider_id in current_provider_ids:
        provider_authority = build_options_provider_authority_contract(
            provider_id=provider_id,
            source_type="live",
            fixture_only=False,
            live_enabled=True,
            tradeable_data=True,
        )

        diagnostics = _evaluate_single_contract(
            _clear_gate_contract(),
            provider_authority=provider_authority,
        )

        assert provider_authority["authorityTier"] == "live_observation_only"
        assert diagnostics.decision_grade is False
        assert "provider_authority_tier_observation_only" in diagnostics.fail_closed_reason_codes
        assert diagnostics.data_quality_gates.status == "clear"
        assert diagnostics.liquidity_gates.status == "clear"


def test_provider_authority_requires_live_enabled_and_tradeable_data() -> None:
    provider_authority = {
        **_authorized_live_provider_authority(),
        "liveEnabled": False,
        "tradeableData": False,
    }

    diagnostics = _evaluate_single_contract(
        _clear_gate_contract(),
        provider_authority=provider_authority,
    )

    assert diagnostics.decision_grade is False
    assert diagnostics.fail_closed_reason_codes == [
        "provider_live_disabled",
        "provider_tradeable_data_false",
    ]
    assert _issue_codes(diagnostics) == {
        "provider_live_disabled",
        "provider_tradeable_data_false",
    }


def test_fixture_dry_run_stub_and_adapter_contract_authority_flags_fail_closed() -> None:
    scenarios = [
        (
            {"providerId": "synthetic_fixture", "sourceType": "synthetic", "fixtureOnly": True},
            "provider_fixture_not_decision_grade",
        ),
        (
            {"providerId": "tradier", "sourceType": "delayed_dry_run", "dryRun": True},
            "provider_dry_run_not_decision_grade",
        ),
        (
            {"providerId": "tradier", "sourceType": "live_stub", "stub": True},
            "provider_stub_not_decision_grade",
        ),
        (
            {"providerId": "tradier", "sourceType": "tradier_adapter_contract", "adapterContract": True},
            "provider_adapter_contract_not_decision_grade",
        ),
    ]

    for provider_authority, expected_code in scenarios:
        diagnostics = _evaluate_single_contract(
            _clear_gate_contract(),
            provider_authority={
                **provider_authority,
                "liveEnabled": True,
                "tradeableData": True,
                "providerDecisionAuthority": True,
            },
        )

        assert diagnostics.decision_grade is False
        assert expected_code in diagnostics.fail_closed_reason_codes
        assert diagnostics.data_quality_gates.status == "clear"
        assert diagnostics.liquidity_gates.status == "clear"


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
        provider_authority=_authorized_live_provider_authority(),
    )

    assert diagnostics.gate_decision == "数据不足，禁止判断"
    assert diagnostics.decision_grade is False
    assert "missing_bid_ask" in diagnostics.fail_closed_reason_codes
    assert "missing_bid_ask" in _issue_codes(diagnostics)
    assert diagnostics.liquidity_gates.status == "blocked"


def test_invalid_bid_ask_fails_closed() -> None:
    contract = _clear_gate_contract().model_copy(
        update={"bid": 2.80, "ask": 2.60, "mid": 2.70, "spread_pct": None}
    )

    diagnostics = _evaluate_single_contract(contract)

    assert diagnostics.gate_decision == "数据不足，禁止判断"
    assert diagnostics.decision_grade is False
    assert "invalid_bid_ask" in diagnostics.fail_closed_reason_codes
    assert "invalid_bid_ask" in _issue_codes(diagnostics)
    assert "missing_bid_ask" not in _issue_codes(diagnostics)
    assert diagnostics.liquidity_gates.status == "blocked"


def test_missing_dte_fails_closed() -> None:
    contract = _clear_gate_contract().model_copy(update={"dte": None})

    diagnostics = _evaluate_single_contract(contract)

    assert diagnostics.gate_decision == "数据不足，禁止判断"
    assert diagnostics.decision_grade is False
    assert diagnostics.fail_closed_reason_codes == ["missing_dte"]
    assert _issue_codes(diagnostics) == {"missing_dte"}
    assert diagnostics.data_quality_gates.status == "blocked"


def test_missing_contract_identity_fails_closed() -> None:
    contract = _clear_gate_contract().model_copy(update={"expiration": ""})

    diagnostics = _evaluate_single_contract(contract)

    assert diagnostics.gate_decision == "数据不足，禁止判断"
    assert diagnostics.decision_grade is False
    assert diagnostics.fail_closed_reason_codes == ["missing_contract_identity"]
    assert _issue_codes(diagnostics) == {"missing_contract_identity"}
    assert diagnostics.data_quality_gates.status == "blocked"


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
        provider_authority=_authorized_live_provider_authority(),
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
            provider_authority=_authorized_live_provider_authority(),
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
        provider_authority=_authorized_live_provider_authority(),
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
        provider_authority=_authorized_live_provider_authority(),
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
        provider_authority=_authorized_live_provider_authority(),
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
        provider_authority=_authorized_live_provider_authority(),
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
        provider_authority=_authorized_live_provider_authority(),
    )

    text = json.dumps(diagnostics.to_dict(), ensure_ascii=False, sort_keys=True).lower()
    assert all(re.fullmatch(r"[a-z][a-z0-9_]{2,80}", code) for code in diagnostics.fail_closed_reason_codes)
    for blocked in ("authorization", "bearer", "token=", "secret", "request", "response", "header", "cookie"):
        assert blocked not in text
