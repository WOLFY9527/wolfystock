# -*- coding: utf-8 -*-
"""Offline contracts for provider usage ledger diagnostics."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from src.services.analysis_provider_planner import (
    DataCategory,
    apply_research_budget_profile,
    build_fast_decision_provider_plan,
)
from src.services.provider_usage_ledger import (
    ProviderUsageEvent,
    ProviderUsageLedger,
    get_provider_usage_ledger,
)


def test_ledger_records_snapshot_and_filters_by_research_mode() -> None:
    ledger = ProviderUsageLedger(max_events=10)
    ledger.record(
        ProviderUsageEvent(
            research_mode="quick",
            symbol=" orcl ",
            market="US",
            analysis_context="analysis",
            category="news",
            provider="gnews",
            action="skipped_by_budget",
            outcome="skipped",
            reason_code="skipped_by_budget",
            budget_profile="quick",
            metadata={"note": "optional"},
        )
    )
    ledger.record(
        ProviderUsageEvent(
            research_mode="deep",
            category="fundamentals",
            provider="fmp",
            action="success",
            outcome="ok",
        )
    )

    quick_events = ledger.snapshot(research_mode="quick")

    assert len(quick_events) == 1
    assert quick_events[0]["researchMode"] == "quick"
    assert quick_events[0]["symbol"] == "ORCL"
    assert quick_events[0]["category"] == "news"
    assert quick_events[0]["action"] == "skipped_by_budget"
    assert quick_events[0]["metadata"] == {"note": "optional"}


def test_ledger_bounded_ring_buffer_drops_old_events() -> None:
    ledger = ProviderUsageLedger(max_events=3)

    for index in range(5):
        ledger.record(
            ProviderUsageEvent(
                category="quote",
                provider=f"provider_{index}",
                action="attempted",
                outcome="ok",
            )
        )

    events = ledger.snapshot(limit=10)

    assert [event["provider"] for event in events] == ["provider_2", "provider_3", "provider_4"]


def test_metadata_sanitization_drops_sensitive_keys_and_truncates_values() -> None:
    ledger = ProviderUsageLedger(max_events=10)
    ledger.record(
        ProviderUsageEvent(
            category="quote",
            provider="alpaca",
            action="failure",
            outcome="failed",
            reason_code="auth_error token=SECRET",
            metadata={
                "token": "SECRET",
                "api_key": "SECRET",
                "headers": {"Authorization": "Bearer SECRET"},
                "raw_payload": {"price": 1},
                "response_body": "SECRET",
                "safe_note": "x" * 400,
                "nested": {"cookie": "SECRET", "safe": "ok"},
            },
        )
    )

    event = ledger.snapshot()[0]
    dumped = json.dumps(event, sort_keys=True)

    assert "SECRET" not in dumped
    assert "api_key" not in dumped
    assert "headers" not in dumped
    assert "raw_payload" not in dumped
    assert "response_body" not in dumped
    assert event["reasonCode"] == "auth_error"
    assert event["metadata"]["safe_note"].endswith("...")
    assert len(event["metadata"]["safe_note"]) <= 180
    assert event["metadata"]["nested"] == {"safe": "ok"}


def test_metadata_sanitization_drops_url_cookie_session_and_exception_text_values() -> None:
    ledger = ProviderUsageLedger(max_events=10)
    ledger.record(
        ProviderUsageEvent(
            category="quote",
            provider="alpaca",
            action="failure",
            outcome="failed",
            reason_code="raw exception https://provider.example.test/raw?token=SECRET",
            metadata={
                "safe_summary": "provider_error_bucket",
                "diagnostic_ref": "probe:quote:alpaca:network_error",
                "safe_url_like_note": "https://provider.example.test/raw?token=SECRET&session_id=raw-session",
                "safe_cookie_note": "cookie=raw-cookie session_id=raw-session",
                "safe_exception_note": "ProviderError(SECRET) raw_exception_message=SECRET",
                "safe_stack_note": "Traceback (most recent call last): SECRET",
                "nested": {
                    "safe": "ok",
                    "note": "Authorization: Bearer SECRET",
                },
            },
        )
    )

    event = ledger.snapshot()[0]
    dumped = json.dumps(event, sort_keys=True).lower()

    assert event["metadata"] == {
        "safe_summary": "provider_error_bucket",
        "diagnostic_ref": "probe:quote:alpaca:network_error",
        "nested": {"safe": "ok"},
    }
    assert event["reasonCode"] == "raw_exception"
    for blocked in (
        "secret",
        "provider.example.test",
        "https://",
        "?token=",
        "session_id",
        "raw-session",
        "cookie=",
        "raw-cookie",
        "authorization",
        "bearer",
        "providererror(",
        "raw_exception_message",
        "traceback",
    ):
        assert blocked not in dumped


def test_summary_groups_by_action_provider_category_and_mode() -> None:
    ledger = ProviderUsageLedger(max_events=10)
    ledger.record(
        ProviderUsageEvent(
            research_mode="quick",
            category="news",
            provider="gnews",
            action="skipped_by_budget",
            outcome="skipped",
        )
    )
    ledger.record(
        ProviderUsageEvent(
            research_mode="quick",
            category="quote",
            provider="alpaca",
            action="cache_hit",
            outcome="ok",
        )
    )
    ledger.record(
        ProviderUsageEvent(
            research_mode="standard",
            category="quote",
            provider="alpaca",
            action="timeout",
            outcome="failed",
        )
    )

    summary = ledger.summarize(window_seconds=3600)

    assert summary["totalEvents"] == 3
    assert summary["byAction"]["skipped_by_budget"] == 1
    assert summary["byProvider"]["alpaca"] == 2
    assert summary["byCategory"]["quote"] == 2
    assert summary["byResearchMode"]["quick"] == 2
    assert summary["skippedByBudget"] == 1
    assert summary["timeout"] == 1
    assert summary["cacheHit"] == 1


def test_snapshot_since_filter_uses_event_timestamps() -> None:
    ledger = ProviderUsageLedger(max_events=10)
    old_time = datetime.now(timezone.utc) - timedelta(hours=2)
    ledger.record(ProviderUsageEvent(timestamp=old_time, category="quote", action="attempted", outcome="ok"))
    ledger.record(ProviderUsageEvent(category="news", action="failure", outcome="failed"))

    events = ledger.snapshot(since=datetime.now(timezone.utc) - timedelta(minutes=5))

    assert len(events) == 1
    assert events[0]["category"] == "news"


def test_research_budget_profile_records_skipped_optional_categories_without_no_mode_noise() -> None:
    ledger = get_provider_usage_ledger()
    ledger.clear_for_tests()
    plan = build_fast_decision_provider_plan(
        "ORCL",
        market="us",
        categories=[DataCategory.QUOTE, DataCategory.NEWS, DataCategory.SENTIMENT],
    )

    budgeted, metadata = apply_research_budget_profile(
        plan,
        research_mode="quick",
        required_categories={DataCategory.QUOTE},
    )

    events = ledger.snapshot(research_mode="quick")
    assert budgeted.categories[DataCategory.QUOTE] == plan.categories[DataCategory.QUOTE]
    assert {event["category"] for event in events} == {"news", "sentiment"}
    assert {event["action"] for event in events} == {"skipped_by_budget", "skipped_by_mode"}
    assert metadata["usageLedgerHints"]

    ledger.clear_for_tests()
    apply_research_budget_profile(plan, research_mode=None, required_categories={DataCategory.QUOTE})

    assert ledger.snapshot() == []


def test_required_categories_are_not_recorded_as_budget_skips() -> None:
    ledger = get_provider_usage_ledger()
    ledger.clear_for_tests()
    plan = build_fast_decision_provider_plan(
        "ORCL",
        market="us",
        categories=[DataCategory.QUOTE, DataCategory.NEWS],
    )

    apply_research_budget_profile(
        plan,
        research_mode="quick",
        required_categories={DataCategory.QUOTE, DataCategory.NEWS},
    )

    assert ledger.snapshot() == []


def test_provider_usage_ledger_import_does_not_import_live_provider_clients() -> None:
    script = """
import json
import src.services.provider_usage_ledger
blocked = [
    "data_provider.alpaca_fetcher",
    "data_provider.twelve_data_fetcher",
    "data_provider.alphavantage_provider",
    "data_provider.us_fundamentals_provider",
    "data_provider.yfinance_fetcher",
    "src.services.market_cache",
    "src.core.pipeline",
]
print(json.dumps({name: name in __import__("sys").modules for name in blocked}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    imported = json.loads(completed.stdout)
    assert imported == {name: False for name in imported}


def test_provider_usage_ledger_import_has_no_runtime_planner_side_effect() -> None:
    planner = importlib.import_module("src.services.analysis_provider_planner")
    before = planner.build_analysis_provider_plan("AAPL", market="us").categories

    importlib.import_module("src.services.provider_usage_ledger")
    after = planner.build_analysis_provider_plan("AAPL", market="us").categories

    assert before == after
