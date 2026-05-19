# -*- coding: utf-8 -*-
"""Offline contracts for provider-fit advisor snapshots."""

from __future__ import annotations

import json
import subprocess
import sys

from src.services.provider_fit_advisor_service import (
    build_provider_fit_advisor_snapshot,
    get_provider_fit_advisor_entry,
    list_provider_fit_advisor_entries,
)


EXPECTED_PROVIDER_IDS = {
    "finnhub",
    "alpha_vantage",
    "twelve_data",
    "marketstack",
    "nasdaq_data_link",
    "sec_edgar",
    "pandas_datareader_fred",
    "pandas_datareader_oecd",
    "pandas_datareader_world_bank",
    "pandas_datareader_stooq",
    "yahooquery",
    "yfinance_current_baseline",
    "openbb_reference_only",
    "tushare_pro",
    "baostock",
    "efinance",
    "qstock",
    "ashare",
    "pytdx_existing_baseline",
    "akshare_existing_baseline",
    "binance_public",
    "coinbase_public",
    "fred_existing_baseline",
    "treasury_existing_baseline",
}


def test_provider_fit_advisor_snapshot_covers_all_t221b_providers() -> None:
    snapshot = build_provider_fit_advisor_snapshot()
    entries = snapshot.entries

    assert snapshot.advisory_only is True
    assert snapshot.runtime_behavior_changed is False
    assert snapshot.network_calls_enabled is False
    assert {entry.provider_id for entry in entries} == EXPECTED_PROVIDER_IDS
    assert entries == tuple(sorted(entries, key=lambda entry: entry.provider_id))


def test_provider_fit_advisor_entries_stay_observation_only_and_non_scoring() -> None:
    entries = list_provider_fit_advisor_entries()

    assert {entry.observation_only for entry in entries} == {True}
    assert {entry.score_contribution_allowed for entry in entries} == {False}
    assert {entry.network_call_executed for entry in entries} == {False}
    assert {entry.no_default_live_http_calls for entry in entries} == {True}
    assert {entry.enabled_by_default for entry in entries} == {False}


def test_provider_fit_advisor_key_required_entries_remain_secret_safe() -> None:
    key_required_ids = {
        entry.provider_id
        for entry in list_provider_fit_advisor_entries()
        if entry.key_required
    }

    assert key_required_ids == {
        "alpha_vantage",
        "finnhub",
        "marketstack",
        "nasdaq_data_link",
        "tushare_pro",
        "twelve_data",
    }
    assert all(
        get_provider_fit_advisor_entry(provider_id).missing_provider_reason.endswith("_key_not_configured")
        for provider_id in key_required_ids
    )


def test_provider_fit_advisor_paid_or_plan_dependent_entries_do_not_become_runtime_safe() -> None:
    for provider_id in (
        "alpha_vantage",
        "finnhub",
        "marketstack",
        "nasdaq_data_link",
        "tushare_pro",
        "twelve_data",
    ):
        entry = get_provider_fit_advisor_entry(provider_id)

        assert entry is not None
        assert entry.paid_data_likely_required is True
        assert entry.adoption_status == "paid_required"
        assert entry.recommended_next_step == "require_license_review"
        assert entry.score_contribution_allowed is False
        assert entry.enabled_by_default is False


def test_provider_fit_advisor_openbb_stays_reference_only_not_source_of_truth() -> None:
    entry = get_provider_fit_advisor_entry("openbb_reference_only")

    assert entry is not None
    assert entry.trust_level == "reference_only"
    assert entry.adoption_status == "reference_only"
    assert entry.recommended_next_step == "do_not_integrate_runtime"
    assert "source_of_truth" in entry.rejected_for


def test_provider_fit_advisor_public_proxy_entries_remain_weak_and_inert() -> None:
    for provider_id in ("efinance", "qstock", "yahooquery", "yfinance_current_baseline"):
        entry = get_provider_fit_advisor_entry(provider_id)

        assert entry is not None
        assert entry.trust_level == "weak"
        assert entry.source_tier in {"public_proxy", "unofficial_public_api"}
        assert entry.adoption_status == "inert_metadata_only"
        assert entry.recommended_next_step == "do_not_integrate_runtime"
        assert entry.score_contribution_allowed is False


def test_provider_fit_advisor_official_and_exchange_sources_remain_default_non_scoring() -> None:
    for provider_id in (
        "sec_edgar",
        "pandas_datareader_fred",
        "pandas_datareader_oecd",
        "pandas_datareader_world_bank",
        "binance_public",
        "coinbase_public",
        "fred_existing_baseline",
        "treasury_existing_baseline",
    ):
        entry = get_provider_fit_advisor_entry(provider_id)

        assert entry is not None
        assert entry.adoption_status in {"candidate", "existing_baseline"}
        assert entry.score_contribution_allowed is False
        assert entry.observation_only is True
        assert entry.enabled_by_default is False


def test_provider_fit_advisor_existing_baselines_stay_fallback_only() -> None:
    for provider_id in (
        "pytdx_existing_baseline",
        "akshare_existing_baseline",
        "fred_existing_baseline",
        "treasury_existing_baseline",
    ):
        entry = get_provider_fit_advisor_entry(provider_id)

        assert entry is not None
        assert entry.adoption_status == "existing_baseline"
        assert entry.recommended_next_step == "keep_as_fallback"


def test_provider_fit_advisor_import_is_metadata_only() -> None:
    script = """
import json
import sys
import src.services.provider_fit_advisor_service

blocked = [
    "requests",
    "httpx",
    "yfinance",
    "akshare",
    "baostock",
    "tushare",
    "openbb",
    "pandas_datareader",
    "src.config",
    "src.core.pipeline",
    "src.services.market_cache",
]
print(json.dumps({name: name in sys.modules for name in blocked}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    imported = json.loads(completed.stdout)
    assert imported == {name: False for name in imported}
