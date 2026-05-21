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
