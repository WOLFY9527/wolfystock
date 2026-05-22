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
from src.services.provider_capability_matrix import get_provider_fit_metadata


EXPECTED_PROVIDER_IDS = {
    "authorized.us_etf_flow",
    "authorized.cn_hk_connect_flow",
    "authorized.real_sector_theme_flow",
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
    "exchange_or_broker_authorized.index_futures",
    "official_public.cn_money_market_rates",
    "official_public.fed_liquidity",
    "official_or_authorized.fx_dxy",
    "official_or_authorized.us_market_breadth",
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
        "authorized.us_etf_flow",
        "authorized.cn_hk_connect_flow",
        "authorized.real_sector_theme_flow",
        "alpha_vantage",
        "exchange_or_broker_authorized.index_futures",
        "finnhub",
        "marketstack",
        "nasdaq_data_link",
        "official_or_authorized.fx_dxy",
        "official_or_authorized.us_market_breadth",
        "tushare_pro",
        "twelve_data",
    }
    assert all(
        get_provider_fit_advisor_entry(provider_id).missing_provider_reason
        == get_provider_fit_metadata(provider_id).missing_provider_reason
        for provider_id in key_required_ids
    )


def test_provider_fit_advisor_paid_or_plan_dependent_entries_do_not_become_runtime_safe() -> None:
    expected_paid_flags = {
        "authorized.us_etf_flow": True,
        "authorized.cn_hk_connect_flow": True,
        "authorized.real_sector_theme_flow": True,
        "alpha_vantage": True,
        "exchange_or_broker_authorized.index_futures": True,
        "finnhub": True,
        "marketstack": True,
        "nasdaq_data_link": True,
        "official_public.cn_money_market_rates": False,
        "official_public.fed_liquidity": False,
        "official_or_authorized.fx_dxy": True,
        "official_or_authorized.us_market_breadth": True,
        "tushare_pro": True,
        "twelve_data": True,
    }

    for provider_id, paid_required in expected_paid_flags.items():
        entry = get_provider_fit_advisor_entry(provider_id)

        assert entry is not None
        assert entry.paid_data_likely_required is paid_required
        assert entry.adoption_status == "paid_required"
        assert entry.recommended_next_step == "require_license_review"
        assert entry.score_contribution_allowed is False
        assert entry.enabled_by_default is False


def test_provider_fit_advisor_missing_authority_contracts_stay_fail_closed_and_precise() -> None:
    expected = {
        "authorized.us_etf_flow": {
            "missing_reason": "authorized_us_etf_flow_feed_not_configured",
            "paid_data_likely_required": True,
            "key_required": True,
        },
        "authorized.cn_hk_connect_flow": {
            "missing_reason": "authorized_cn_hk_connect_flow_feed_not_configured",
            "paid_data_likely_required": True,
            "key_required": True,
        },
        "authorized.real_sector_theme_flow": {
            "missing_reason": "authorized_real_sector_theme_flow_not_configured",
            "paid_data_likely_required": True,
            "key_required": True,
        },
        "exchange_or_broker_authorized.index_futures": {
            "missing_reason": "authorized_index_futures_feed_not_configured",
            "paid_data_likely_required": True,
            "key_required": True,
        },
        "official_public.cn_money_market_rates": {
            "missing_reason": "official_cn_money_market_rates_contract_not_configured",
            "paid_data_likely_required": False,
            "key_required": False,
        },
        "official_public.fed_liquidity": {
            "missing_reason": "official_fed_liquidity_contract_not_configured",
            "paid_data_likely_required": False,
            "key_required": False,
        },
        "official_or_authorized.fx_dxy": {
            "missing_reason": "authorized_dxy_feed_not_configured",
            "paid_data_likely_required": True,
            "key_required": True,
        },
        "official_or_authorized.us_market_breadth": {
            "missing_reason": "authorized_us_market_breadth_feed_not_configured",
            "paid_data_likely_required": True,
            "key_required": True,
        },
    }

    for provider_id, contract in expected.items():
        entry = get_provider_fit_advisor_entry(provider_id)

        assert entry is not None
        assert entry.paid_data_likely_required is contract["paid_data_likely_required"]
        assert entry.key_required is contract["key_required"]
        assert entry.cache_required is True
        assert entry.background_refresh_recommended is True
        assert entry.observation_only is True
        assert entry.score_contribution_allowed is False
        assert entry.network_call_executed is False
        assert entry.no_default_live_http_calls is True
        assert entry.adoption_status == "paid_required"
        assert entry.recommended_next_step == "require_license_review"
        assert entry.missing_provider_reason == contract["missing_reason"]
        assert entry.missing_provider_reason == get_provider_fit_metadata(provider_id).missing_provider_reason


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
