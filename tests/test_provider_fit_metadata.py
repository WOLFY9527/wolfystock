# -*- coding: utf-8 -*-
"""Offline contracts for T-221B provider-fit metadata and dry-run probes."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from src.contracts.source_confidence import ProviderDryRunProbeContract, ProviderFitMetadataContract
from src.services.provider_capability_matrix import (
    get_provider_capability_support_contract,
    get_provider_dry_run_probe_contract,
    get_provider_fit_metadata,
    get_provider_scoring_contract,
    list_provider_capability_support_contracts,
    list_provider_dry_run_probe_contracts,
    list_provider_fit_metadata,
)


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


def test_provider_fit_metadata_covers_all_audited_candidates_and_stays_sorted() -> None:
    entries = list_provider_fit_metadata()

    assert {item.provider_id for item in entries} == EXPECTED_PROVIDER_IDS
    assert entries == tuple(sorted(entries, key=lambda item: item.provider_id))
    assert all(isinstance(item, ProviderFitMetadataContract) for item in entries)


@pytest.mark.parametrize(
    ("provider_id", "expected"),
    [
        (
            "sec_edgar",
            {
                "providerCategory": "filings_reference",
                "sourceTier": "official_public",
                "trustLevel": "reliable_for_filings_metadata",
                "freshnessExpectation": "filing_or_daily",
                "paidDataLikelyRequired": False,
                "keyRequired": False,
            },
        ),
        (
            "coinbase_public",
            {
                "providerCategory": "exchange_reference",
                "sourceTier": "exchange_public",
                "trustLevel": "usable_with_caution",
                "freshnessExpectation": "near_real_time_venue_scoped",
                "paidDataLikelyRequired": False,
                "keyRequired": False,
            },
        ),
        (
            "finnhub",
            {
                "providerCategory": "market_data_api",
                "sourceTier": "gated_public_api",
                "trustLevel": "usable_with_caution",
                "freshnessExpectation": "plan_dependent_delayed_or_daily",
                "paidDataLikelyRequired": True,
                "keyRequired": True,
            },
        ),
        (
            "authorized.us_etf_flow",
            {
                "providerCategory": "authorized_flow_dataset",
                "sourceTier": "authorized_licensed_feed",
                "trustLevel": "score_grade_when_configured",
                "freshnessExpectation": "licensed_daily_or_delayed_fund_flow",
                "paidDataLikelyRequired": True,
                "keyRequired": True,
            },
        ),
        (
            "official_public.fed_liquidity",
            {
                "providerCategory": "official_macro_liquidity_contract",
                "sourceTier": "official_public",
                "trustLevel": "score_grade_when_configured",
                "freshnessExpectation": "daily_or_weekly_public_release_lag",
                "paidDataLikelyRequired": False,
                "keyRequired": False,
            },
        ),
        (
            "official_public.cn_money_market_rates",
            {
                "providerCategory": "official_macro_liquidity_contract",
                "sourceTier": "official_public",
                "trustLevel": "score_grade_when_configured",
                "freshnessExpectation": "session_delayed_or_daily_official_fixing",
                "paidDataLikelyRequired": False,
                "keyRequired": False,
            },
        ),
        (
            "official_or_authorized.fx_dxy",
            {
                "providerCategory": "authorized_fx_macro_dataset",
                "sourceTier": "official_or_authorized_fx_feed",
                "trustLevel": "score_grade_when_configured",
                "freshnessExpectation": "continuous_session_or_delayed_fix_snapshot",
                "paidDataLikelyRequired": True,
                "keyRequired": True,
            },
        ),
        (
            "baostock",
            {
                "providerCategory": "cn_delayed_observation",
                "sourceTier": "third_party_free_api",
                "trustLevel": "usable_with_caution",
                "freshnessExpectation": "t_plus_1_or_delayed",
                "paidDataLikelyRequired": False,
                "keyRequired": False,
            },
        ),
        (
            "official_or_authorized.us_market_breadth",
            {
                "providerCategory": "authorized_breadth_dataset",
                "sourceTier": "official_or_authorized_licensed_feed",
                "trustLevel": "score_grade_when_configured",
                "freshnessExpectation": "licensed_daily_or_delayed_breadth_snapshot",
                "paidDataLikelyRequired": True,
                "keyRequired": True,
            },
        ),
        (
            "authorized.cn_hk_connect_flow",
            {
                "providerCategory": "authorized_cross_border_flow_dataset",
                "sourceTier": "authorized_licensed_feed",
                "trustLevel": "score_grade_when_configured",
                "freshnessExpectation": "session_delayed_cross_border_flow_snapshot",
                "paidDataLikelyRequired": True,
                "keyRequired": True,
            },
        ),
        (
            "exchange_or_broker_authorized.index_futures",
            {
                "providerCategory": "authorized_index_futures_dataset",
                "sourceTier": "exchange_or_broker_authorized_feed",
                "trustLevel": "score_grade_when_configured",
                "freshnessExpectation": "extended_hours_delayed_or_realtime_index_futures",
                "paidDataLikelyRequired": True,
                "keyRequired": True,
            },
        ),
        (
            "authorized.real_sector_theme_flow",
            {
                "providerCategory": "authorized_rotation_flow_dataset",
                "sourceTier": "authorized_licensed_feed",
                "trustLevel": "score_grade_when_configured",
                "freshnessExpectation": "daily_or_intraday_sector_theme_flow_snapshot",
                "paidDataLikelyRequired": True,
                "keyRequired": True,
            },
        ),
        (
            "yfinance_current_baseline",
            {
                "providerCategory": "baseline_proxy_observation",
                "sourceTier": "unofficial_public_api",
                "trustLevel": "weak",
                "freshnessExpectation": "delayed_public_proxy",
                "paidDataLikelyRequired": False,
                "keyRequired": False,
            },
        ),
        (
            "openbb_reference_only",
            {
                "providerCategory": "integration_reference",
                "sourceTier": "reference_wrapper",
                "trustLevel": "reference_only",
                "freshnessExpectation": "plan_dependent_reference_only",
                "paidDataLikelyRequired": False,
                "keyRequired": False,
            },
        ),
        (
            "pytdx_existing_baseline",
            {
                "providerCategory": "cn_hk_existing_baseline",
                "sourceTier": "unofficial_public_api",
                "trustLevel": "usable_with_caution",
                "freshnessExpectation": "best_effort_realtime_quote_and_daily_history",
                "paidDataLikelyRequired": False,
                "keyRequired": False,
            },
        ),
        (
            "akshare_existing_baseline",
            {
                "providerCategory": "cn_hk_existing_baseline",
                "sourceTier": "unofficial_public_api",
                "trustLevel": "weak",
                "freshnessExpectation": "best_effort_public_web_quote_snapshot_and_daily_history",
                "paidDataLikelyRequired": False,
                "keyRequired": False,
            },
        ),
    ],
)
def test_provider_fit_metadata_uses_truthful_inert_defaults(
    provider_id: str,
    expected: dict[str, object],
) -> None:
    entry = get_provider_fit_metadata(provider_id)

    assert entry is not None
    assert entry.provider_id == provider_id
    assert entry.to_dict()["providerId"] == provider_id
    assert entry.provider_name
    assert entry.observation_only is True
    assert entry.score_contribution_allowed is False
    assert entry.enabled_by_default is False
    assert entry.live_tests_avoided is True
    assert entry.degradation_reason == "provider_fit_metadata_only"
    assert entry.best_use_cases
    assert entry.not_recommended_for
    for key, value in expected.items():
        assert entry.to_dict()[key] == value


def test_provider_fit_metadata_keeps_all_entries_inert_and_non_scoring() -> None:
    entries = list_provider_fit_metadata()

    assert {item.observation_only for item in entries} == {True}
    assert {item.score_contribution_allowed for item in entries} == {False}
    assert {item.enabled_by_default for item in entries} == {False}
    assert {item.live_tests_avoided for item in entries} == {True}
    assert "reliable" not in {item.trust_level for item in entries}
    assert get_provider_fit_metadata("missing_provider") is None


def test_authorized_us_flow_and_breadth_metadata_carry_coverage_and_score_gate_requirements() -> None:
    etf_entry = get_provider_fit_metadata("authorized.us_etf_flow")
    breadth_entry = get_provider_fit_metadata("official_or_authorized.us_market_breadth")

    assert etf_entry is not None
    assert {
        "daily_net_flow_authority",
        "creation_redemption_evidence",
        "sector_flow_authority",
        "licensed_us_etf_universe_coverage",
    }.issubset(set(etf_entry.best_use_cases))
    assert {"freshness_unqualified", "coverage_unqualified"}.issubset(set(etf_entry.rejected_for))
    assert "partial_coverage_scoring" in etf_entry.not_recommended_for

    assert breadth_entry is not None
    assert {
        "advancers_decliners_authority",
        "new_highs_lows_authority",
        "above_ma_breadth_authority",
        "sector_breadth_confirmation",
        "nyse_nasdaq_exchange_coverage",
    }.issubset(set(breadth_entry.best_use_cases))
    assert {"freshness_unqualified", "coverage_unqualified"}.issubset(set(breadth_entry.rejected_for))
    assert "partial_coverage_scoring" in breadth_entry.not_recommended_for


def test_official_liquidity_contract_metadata_carries_release_and_session_gates() -> None:
    fed_entry = get_provider_fit_metadata("official_public.fed_liquidity")
    cn_entry = get_provider_fit_metadata("official_public.cn_money_market_rates")
    dxy_entry = get_provider_fit_metadata("official_or_authorized.fx_dxy")

    assert fed_entry is not None
    assert {
        "fed_rrp_balance_authority",
        "treasury_general_account_authority",
        "reserve_balances_authority",
        "federal_liquidity_release_calendar",
    }.issubset(set(fed_entry.best_use_cases))
    assert {
        "runtime_unconfigured",
        "release_lag_unqualified",
        "coverage_unqualified",
    }.issubset(set(fed_entry.rejected_for))
    assert "score_inputs_without_full_official_cache" in fed_entry.not_recommended_for

    assert cn_entry is not None
    assert {
        "dr007_authority",
        "shibor_authority",
        "repo_liquidity_rate_authority",
        "cn_money_market_session_calendar",
    }.issubset(set(cn_entry.best_use_cases))
    assert {
        "runtime_unconfigured",
        "session_unqualified",
        "coverage_unqualified",
    }.issubset(set(cn_entry.rejected_for))
    assert "score_inputs_without_full_official_cache" in cn_entry.not_recommended_for

    assert dxy_entry is not None
    assert {
        "dxy_reference_authority",
        "usd_macro_context_authority",
        "major_fx_pair_crosscheck",
    }.issubset(set(dxy_entry.best_use_cases))
    assert {
        "runtime_unconfigured",
        "session_unqualified",
        "coverage_unqualified",
    }.issubset(set(dxy_entry.rejected_for))
    assert "proxy_replacements" in dxy_entry.not_recommended_for


def test_official_liquidity_contract_supports_and_scoring_gates_stay_missing_and_fail_closed() -> None:
    for provider_id, capability, expected_universe, expected_cadence, expected_reason in (
        (
            "official_public.fed_liquidity",
            "fed_liquidity",
            "rrp_tga_reserve_balances_release_bundle",
            "daily_weekly",
            "official_fed_liquidity_contract_not_configured",
        ),
        (
            "official_public.cn_money_market_rates",
            "cn_money_market_rates",
            "dr007_shibor_repo_liquidity_rate_bundle",
            "session_daily",
            "official_cn_money_market_rates_contract_not_configured",
        ),
    ):
        support = get_provider_capability_support_contract(provider_id, capability)
        scoring = get_provider_scoring_contract(provider_id, capability)

        assert support is not None
        expected_source_type = (
            "official_public"
            if provider_id == "official_public.fed_liquidity"
            else "missing"
        )
        assert support.source_type == expected_source_type
        assert support.source_tier == "official_public"
        assert support.observation_only is True
        assert support.score_contribution_allowed is False
        assert support.paid_data_likely_required is False
        assert support.key_required is False
        assert support.cache_required is True
        assert support.background_refresh_recommended is True
        assert support.missing_provider_reason == expected_reason

        assert scoring is not None
        assert scoring.coverage_universe == expected_universe
        assert scoring.cadence == expected_cadence
        assert scoring.freshness_floor == "delayed"
        assert scoring.coverage_ratio_floor == 1.0
        assert scoring.required_source_tier == "official_public"

    dxy_support = get_provider_capability_support_contract("official_or_authorized.fx_dxy", "fx_dxy")
    dxy_scoring = get_provider_scoring_contract("official_or_authorized.fx_dxy", "fx_dxy")
    assert dxy_support is not None
    assert dxy_support.source_type == "missing"
    assert dxy_support.source_tier == "official_or_authorized_fx_feed"
    assert dxy_support.observation_only is True
    assert dxy_support.score_contribution_allowed is False
    assert dxy_support.paid_data_likely_required is True
    assert dxy_support.key_required is True
    assert dxy_support.cache_required is True
    assert dxy_support.background_refresh_recommended is True
    assert dxy_support.missing_provider_reason == "authorized_dxy_feed_not_configured"

    assert dxy_scoring is not None
    assert dxy_scoring.coverage_universe == "dxy_reference_pair_bundle"
    assert dxy_scoring.cadence == "continuous_session"
    assert dxy_scoring.freshness_floor == "delayed"
    assert dxy_scoring.coverage_ratio_floor == 1.0
    assert dxy_scoring.required_source_tier == "official_or_authorized_fx_feed"


def test_authorized_us_flow_and_breadth_support_contracts_cover_required_capabilities() -> None:
    breadth_supports = list_provider_capability_support_contracts(
        "official_or_authorized.us_market_breadth"
    )
    breadth_capabilities = {item.capability for item in breadth_supports}
    assert {
        "us_market_breadth_constituents",
        "us_advancers_decliners",
        "us_new_highs_lows",
        "us_above_ma_breadth",
        "us_sector_breadth",
    } == breadth_capabilities

    for provider_id, capability, expected_universe, expected_source_tier in (
        (
            "authorized.us_etf_flow",
            "us_etf_flow_daily",
            "licensed_us_listed_etf_universe",
            "authorized_licensed_feed",
        ),
        (
            "authorized.us_etf_flow",
            "us_sector_etf_flow",
            "licensed_us_sector_etf_universe",
            "authorized_licensed_feed",
        ),
        (
            "official_or_authorized.us_market_breadth",
            "us_advancers_decliners",
            "nyse_nasdaq_listed_equity_universe",
            "official_or_authorized_licensed_feed",
        ),
        (
            "official_or_authorized.us_market_breadth",
            "us_above_ma_breadth",
            "configured_index_or_exchange_breadth_universe",
            "official_or_authorized_licensed_feed",
        ),
    ):
        support = get_provider_capability_support_contract(provider_id, capability)
        scoring = get_provider_scoring_contract(provider_id, capability)

        assert support is not None
        assert support.source_type == "missing"
        assert support.observation_only is True
        assert support.score_contribution_allowed is False
        assert support.cache_required is True
        assert support.key_required is True

        assert scoring is not None
        assert scoring.coverage_universe == expected_universe
        assert scoring.cadence == "daily"
        assert scoring.freshness_floor == "daily"
        assert scoring.coverage_ratio_floor == pytest.approx(0.8)
        assert scoring.required_source_tier == expected_source_tier
        assert "min_coverage" in scoring.score_eligibility_gate


def test_provider_fit_dry_run_probe_contracts_stay_disabled_and_secret_safe() -> None:
    entries = list_provider_fit_metadata()
    probes = list_provider_dry_run_probe_contracts()

    assert {item.provider_id for item in probes} == EXPECTED_PROVIDER_IDS
    assert probes == tuple(sorted(probes, key=lambda item: item.provider_id))
    assert all(isinstance(item, ProviderDryRunProbeContract) for item in probes)

    for entry in entries:
        probe = get_provider_dry_run_probe_contract(entry.provider_id)
        assert probe is not None
        assert probe.provider_id == entry.provider_id
        assert probe.provider_name == entry.provider_name
        assert probe.enabled_by_default is False
        assert probe.reason_code == "provider_fit_metadata_only"
        assert probe.network_call_executed is False
        assert probe.no_default_live_http_calls is True
        assert probe.http_method == "NONE"
        assert probe.key_required is entry.key_required
        assert probe.required_credential_count == (1 if entry.key_required else 0)
        assert probe.configured_credential_count == 0
        assert probe.requires_credential_presence_only is entry.key_required
        assert probe.live_tests_avoided is True
        assert probe.cache_required is entry.cache_required
        assert probe.background_refresh_recommended is entry.background_refresh_recommended
        assert probe.observation_only is True
        assert probe.score_contribution_allowed is False
        assert probe.raw_credential_values_included is False
        assert probe.provider_payload_values_included is False
        assert probe.response_bodies_included is False
        assert probe.degradation_reason == "provider_fit_metadata_only"
        assert probe.missing_provider_reason == (
            entry.missing_provider_reason if entry.key_required else None
        )


def test_provider_fit_imports_are_metadata_only() -> None:
    script = """
import json
import sys
import src.services.provider_capability_matrix

blocked = [
    "requests",
    "httpx",
    "yfinance",
    "akshare",
    "baostock",
    "tushare",
    "openbb",
    "pandas_datareader",
    "data_provider.alpaca_fetcher",
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
