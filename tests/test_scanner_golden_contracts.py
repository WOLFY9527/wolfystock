# -*- coding: utf-8 -*-
"""Golden fixture contract tests for public scanner DTO boundaries."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from api.v1.schemas.scanner import ScannerCandidateResponse, ScannerRunDetailResponse


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "scanner"
FORBIDDEN_PUBLIC_TERMS = (
    "authorization",
    "bearer ",
    "cookie",
    "set-cookie",
    "session_id",
    "api_key",
    "access_token",
    "refresh_token",
    "password",
    "credential",
    "raw_provider_payload",
    "raw_payload",
    "provider_payload",
    "stack_trace",
    "traceback",
)
SCANNER_RUN_REQUIRED_KEYS = {
    "id",
    "market",
    "profile",
    "status",
    "run_at",
    "completed_at",
    "watchlist_date",
    "universe_size",
    "shortlist_size",
    "diagnostics",
    "summary",
    "candidates",
    "shortlist",
}
SCANNER_CANDIDATE_REQUIRED_KEYS = {
    "symbol",
    "name",
    "rank",
    "score",
    "quality_hint",
    "reason_summary",
    "reasons",
    "key_metrics",
    "feature_signals",
    "risk_notes",
    "watch_context",
    "ai_interpretation",
    "diagnostics",
}


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _iter_strings(item)
        return
    if isinstance(value, list):
        for item in value:
            yield from _iter_strings(item)
        return
    if isinstance(value, str):
        yield value


def _assert_iso_timestamp(value: str | None) -> None:
    assert value
    datetime.fromisoformat(value)


def _assert_no_sensitive_public_payload(value: Any) -> None:
    public_text = "\n".join(_iter_strings(value)).lower()
    for term in FORBIDDEN_PUBLIC_TERMS:
        assert term not in public_text


def _assert_fixture_source_labels_are_honest(value: Any) -> None:
    public_text = "\n".join(_iter_strings(value)).lower()
    assert "fixture" in public_text
    assert "source_used\": \"live" not in json.dumps(value, ensure_ascii=False).lower()
    assert "\"source\": \"live\"" not in json.dumps(value, ensure_ascii=False).lower()
    assert "\"is_live\": true" not in json.dumps(value, ensure_ascii=False).lower()


def test_scanner_run_summary_golden_fixture_matches_public_detail_contract() -> None:
    payload = _load_fixture("scanner_run_summary_dto.json")

    assert SCANNER_RUN_REQUIRED_KEYS <= set(payload)
    response = ScannerRunDetailResponse(**payload)
    public_payload = response.model_dump()

    assert public_payload["market"] == "us"
    assert public_payload["profile"] == "us_preopen_v1"
    assert public_payload["status"] == "completed"
    assert public_payload["failure_reason"] is None
    _assert_iso_timestamp(public_payload["run_at"])
    _assert_iso_timestamp(public_payload["completed_at"])

    summary = public_payload["summary"]
    coverage = public_payload["diagnostics"]["coverage_summary"]
    provider = public_payload["diagnostics"]["provider_diagnostics"]
    assert public_payload["universe_size"] == summary["universe_count"] == coverage["input_universe_size"]
    assert public_payload["shortlist_size"] == summary["selected_count"] == len(public_payload["shortlist"])
    assert coverage["shortlisted_count"] == len(public_payload["shortlist"])
    assert provider["providers_used"] == ["fixture_local_history"]
    assert provider["fallback_occurred"] is False
    assert provider["fallback_count"] == 0

    _assert_no_sensitive_public_payload(public_payload)
    _assert_fixture_source_labels_are_honest(public_payload)


def test_scanner_candidate_golden_fixture_matches_public_candidate_contract() -> None:
    payload = _load_fixture("scanner_candidate_dto.json")

    assert SCANNER_CANDIDATE_REQUIRED_KEYS <= set(payload)
    candidate = ScannerCandidateResponse(**payload).model_dump()

    assert candidate["symbol"] == "NVDA"
    assert candidate["rank"] == 1
    assert candidate["score"] == 91.25
    assert candidate["reason_summary"]
    assert candidate["reasons"]
    assert candidate["risk_notes"]
    assert candidate["watch_context"]
    assert candidate["key_metrics"]
    assert candidate["feature_signals"]
    _assert_iso_timestamp(candidate["scan_timestamp"])

    ai_payload = candidate["ai_interpretation"]
    assert ai_payload["available"] is True
    assert ai_payload["status"] == "generated"
    assert ai_payload["summary"]
    assert ai_payload["opportunity_type"]
    assert ai_payload["risk_interpretation"]
    assert ai_payload["watch_plan"]
    assert not ({"rank", "score", "selection_order", "selected_symbols"} & set(ai_payload))
    assert candidate["rank"] == 1
    assert candidate["score"] > 0

    _assert_no_sensitive_public_payload(candidate)
    _assert_fixture_source_labels_are_honest(candidate)


def test_scanner_diagnostic_candidates_freeze_bounded_failure_semantics() -> None:
    payload = ScannerRunDetailResponse(**_load_fixture("scanner_run_summary_dto.json")).model_dump()
    diagnostics_by_status = {item["status"]: item for item in payload["candidates"]}

    assert set(diagnostics_by_status) == {"selected", "rejected", "data_failed"}
    assert diagnostics_by_status["selected"]["failed_rules"] == []
    assert diagnostics_by_status["selected"]["missing_fields"] == []
    assert diagnostics_by_status["rejected"]["failed_rules"] == ["liquidity_below_profile_minimum"]
    assert diagnostics_by_status["rejected"]["missing_fields"] == []
    assert diagnostics_by_status["data_failed"]["failed_rules"] == []
    assert diagnostics_by_status["data_failed"]["missing_fields"] == ["history.close", "history.volume"]
    assert diagnostics_by_status["data_failed"]["score"] is None


def test_scanner_to_backtest_handoff_fixture_is_prefill_contract_only() -> None:
    payload = _load_fixture("scanner_to_backtest_handoff_dto.json")
    query = payload["query"]
    prefill = payload["prefill"]
    expected_query = {
        "source": "scanner",
        "symbol": "NVDA",
        "market": "US",
        "scannerRunId": "42",
        "scannerRank": "1",
        "scannerProfile": "us_preopen_v1",
        "themeId": "ai_semiconductors_us",
        "universeType": "theme",
    }
    expected_prefill = {
        "symbol": "NVDA",
        "market": "US",
        "source": "scanner",
        "scanner_run_id": 42,
        "scanner_rank": 1,
        "scanner_profile": "us_preopen_v1",
        "theme_id": "ai_semiconductors_us",
        "universe_type": "theme",
    }

    assert payload["route"] == "/backtest"
    assert set(query) == set(expected_query), "scanner handoff query must keep the stable /backtest prefill keys"
    assert query == expected_query
    assert set(prefill) == set(expected_prefill), "scanner handoff prefill must keep only the stable scanner context fields"
    assert prefill == expected_prefill
    assert not ({"engine_version", "calculation_engine", "trade_rows", "equity_curve", "backtest_run_id"} & set(prefill))
    _assert_no_sensitive_public_payload(payload)


def test_all_scanner_golden_fixtures_exclude_raw_secrets_and_provider_payloads() -> None:
    fixture_paths = sorted(FIXTURE_DIR.glob("*.json"))

    assert {path.name for path in fixture_paths} == {
        "scanner_candidate_dto.json",
        "scanner_run_summary_dto.json",
        "scanner_to_backtest_handoff_dto.json",
    }
    for path in fixture_paths:
        _assert_no_sensitive_public_payload(json.loads(path.read_text(encoding="utf-8")))
