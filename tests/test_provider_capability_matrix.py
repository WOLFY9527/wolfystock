# -*- coding: utf-8 -*-
"""Offline contracts for inert provider capability metadata."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from data_provider.baostock_fetcher import BaostockFetcher
from data_provider.akshare_fetcher import AkshareFetcher
from data_provider.pytdx_fetcher import PytdxFetcher
from src.contracts.source_confidence import SCORE_GRADE_TRUST_LEVELS
from src.services.provider_capability_matrix import (
    FreshnessClass,
    ProviderDomain,
    ProviderMarket,
    ProviderQuotaClass,
    ScannerUsage,
    BacktestUsage,
    get_provider_dry_run_probe_contract,
    get_provider_capability,
    get_provider_capability_support_contract,
    get_provider_fit_metadata,
    list_provider_capability_support_contracts,
    list_provider_dry_run_probe_contracts,
    list_provider_fit_metadata,
    is_provider_allowed_for_backtest,
    is_provider_allowed_for_scanner,
    list_provider_capabilities,
    providers_for_domain,
    recommended_ttl,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_CONFIG_TEXT = (REPO_ROOT / "src/config.py").read_text(encoding="utf-8")
PROVIDER_CAPABILITY_METADATA_DOC = (
    REPO_ROOT / "docs" / "operations" / "provider-capability-metadata.md"
)

EXPECTED_PROVIDER_IDS = {
    "local_cache",
    "local_ohlcv",
    "yahoo_yfinance",
    "akshare",
    "alpaca",
    "twelve_data",
    "fmp",
    "finnhub",
    "alpha_vantage",
    "gnews",
    "local_news_cache",
    "tavily",
    "social_sentiment",
    "local_inference",
}

KNOWN_SUPPORT_SOURCE_TYPES = {
    "missing",
    "official_public",
    "public_proxy",
}

KNOWN_SUPPORT_FRESHNESS_EXPECTATIONS = {
    "best_effort_public_web_quote_snapshot_and_daily_history",
    "best_effort_realtime_quote_and_daily_history",
    "continuous_session_or_delayed_fix_snapshot",
    "daily_or_intraday_sector_theme_flow_snapshot",
    "daily_or_weekly_public_release_lag",
    "extended_hours_delayed_or_realtime_index_futures",
    "licensed_daily_or_delayed_breadth_snapshot",
    "licensed_daily_or_delayed_fund_flow",
    "session_delayed_cross_border_flow_snapshot",
    "session_delayed_or_daily_official_fixing",
    "t_plus_1_or_delayed",
}

KNOWN_DIAGNOSTIC_FRESHNESS_EXPECTATIONS = {
    "authorized_or_cached_option_chain_with_bid_ask_and_freshness_evidence",
    "authorized_or_cached_option_chain_with_iv_greeks_and_freshness_evidence",
    "authorized_or_cached_option_chain_with_iv_rank_history_and_freshness_evidence",
    "authorized_or_cached_option_chain_with_oi_volume_and_freshness_evidence",
    "disabled_live_stub_diagnostic_only",
    "persisted_watchlist_refresh_window_and_freshness_audit",
    "persisted_watchlist_snapshot_with_explicit_scanner_score_context",
    "persisted_watchlist_source_confidence_and_cap_reason_preservation",
    "stored_snapshot_with_benchmark_lineage_freshness_and_non_fallback_history",
    "stored_snapshot_with_factor_lineage_freshness_and_non_fallback_inputs",
    "stored_snapshot_with_lineage_freshness_and_non_fallback_fx_evidence",
    "stored_snapshot_with_lineage_freshness_and_non_fallback_price_evidence",
    "stored_snapshot_with_sector_industry_lineage_and_non_fallback_mappings",
    "synthetic_fixture_and_dry_run_chain_only",
    "watchlist_missing_or_stale_score_gap_projection",
}

PROVENANCE_VOCABULARY_GUARD_TERMS = {
    "diagnosticOnly",
    "observationOnly",
    "authorityGrant",
    "sourceAuthorityAllowed",
    "scoreContributionAllowed",
    "scoreReliabilityAllowed",
    "score_grade_allowed",
    "scoreGradeEvidenceAllowed",
    "freshness",
    "stale",
    "partial",
    "fallback",
}

FUTURE_AUTHORIZED_SUPPORT_CONTRACTS = {
    ("authorized.us_etf_flow", "us_etf_flow_daily"),
    ("authorized.us_etf_flow", "us_etf_creation_redemption"),
    ("authorized.us_etf_flow", "us_sector_etf_flow"),
    ("official_or_authorized.us_market_breadth", "us_market_breadth_constituents"),
    ("official_or_authorized.us_market_breadth", "us_advancers_decliners"),
    ("official_or_authorized.us_market_breadth", "us_new_highs_lows"),
    ("official_or_authorized.us_market_breadth", "us_above_ma_breadth"),
    ("official_or_authorized.us_market_breadth", "us_sector_breadth"),
}


def test_provider_capability_matrix_contains_expected_providers() -> None:
    capabilities = list_provider_capabilities()

    assert {item.provider_id for item in capabilities} == EXPECTED_PROVIDER_IDS
    assert capabilities == tuple(sorted(capabilities, key=lambda item: item.provider_id))


def test_every_provider_has_required_typed_fields() -> None:
    valid_domains = {item.value for item in ProviderDomain}
    valid_markets = {item.value for item in ProviderMarket}
    valid_quota_classes = {item.value for item in ProviderQuotaClass}
    valid_freshness_classes = {item.value for item in FreshnessClass}

    for capability in list_provider_capabilities():
        assert capability.provider_id
        assert capability.display_name
        assert capability.domains
        assert capability.markets
        assert capability.quota_class.value in valid_quota_classes
        assert capability.freshness_class.value in valid_freshness_classes
        assert capability.scanner_usage
        assert capability.backtest_usage
        assert capability.operator_notes
        assert all(domain.value in valid_domains for domain in capability.domains)
        assert all(market.value in valid_markets for market in capability.markets)
        assert set(capability.recommended_ttl_seconds_by_domain).issubset(valid_domains)
        assert set(capability.default_priority_by_domain).issubset(valid_domains)
        assert all(value > 0 for value in capability.recommended_ttl_seconds_by_domain.values())
        assert all(value > 0 for value in capability.default_priority_by_domain.values())


def test_backtest_allows_only_local_or_cached_data_sources() -> None:
    allowed = {
        capability.provider_id
        for capability in list_provider_capabilities()
        if is_provider_allowed_for_backtest(capability.provider_id)
    }

    assert allowed == {"local_cache", "local_news_cache", "local_ohlcv", "local_inference"}
    for capability in list_provider_capabilities():
        if capability.provider_id not in allowed:
            assert capability.backtest_usage is BacktestUsage.NEVER


@pytest.mark.parametrize(
    "provider_id",
    ["fmp", "alpha_vantage", "gnews", "tavily", "social_sentiment"],
)
def test_scanner_wide_expensive_and_research_providers_are_not_allowed(provider_id: str) -> None:
    capability = get_provider_capability(provider_id)

    assert is_provider_allowed_for_scanner(provider_id) is False
    assert capability.scanner_usage in {ScannerUsage.TOP_N_ONLY, ScannerUsage.NEVER}


def test_alpha_vantage_is_deep_manual_last_resort_not_quick_or_scanner_default() -> None:
    capability = get_provider_capability("alpha_vantage")

    assert capability.quick_analysis_allowed is False
    assert capability.standard_analysis_allowed is False
    assert capability.deep_research_allowed is True
    assert capability.scanner_allowed is False
    assert capability.default_priority_by_domain[ProviderDomain.FUNDAMENTALS.value] >= 90
    assert capability.default_priority_by_domain[ProviderDomain.TECHNICALS.value] >= 90


def test_fmp_prioritizes_fundamentals_and_statements_over_ohlcv_and_technicals() -> None:
    capability = get_provider_capability("fmp")
    priority = capability.default_priority_by_domain

    assert priority[ProviderDomain.FUNDAMENTALS.value] < priority[ProviderDomain.OHLCV.value]
    assert priority[ProviderDomain.STATEMENTS.value] < priority[ProviderDomain.OHLCV.value]
    assert priority[ProviderDomain.FUNDAMENTALS.value] < priority[ProviderDomain.TECHNICALS.value]
    assert priority[ProviderDomain.STATEMENTS.value] < priority[ProviderDomain.TECHNICALS.value]
    assert capability.scanner_allowed is False


def test_local_inference_is_local_inferred_and_never_live_external_sentiment() -> None:
    capability = get_provider_capability("local_inference")

    assert capability.quota_class is ProviderQuotaClass.LOCAL
    assert capability.freshness_class is FreshnessClass.INFERRED
    assert capability.scanner_usage is ScannerUsage.LOCAL_ONLY
    assert capability.backtest_usage is BacktestUsage.LOCAL_ONLY
    assert capability.scanner_allowed is True
    assert ProviderDomain.SENTIMENT in capability.domains


def test_helper_functions_are_deterministic_and_do_not_expose_mutable_state() -> None:
    first = list_provider_capabilities()
    second = list_provider_capabilities()

    assert first == second
    assert first is not second
    assert get_provider_capability("fmp") == get_provider_capability("FMP")
    assert recommended_ttl("fmp", ProviderDomain.FUNDAMENTALS) == 12 * 60 * 60
    assert recommended_ttl("unknown", ProviderDomain.FUNDAMENTALS) is None
    assert get_provider_capability("missing") is None
    assert [item.provider_id for item in providers_for_domain(ProviderDomain.TECHNICALS)][0] == "local_ohlcv"


def test_future_authorized_us_flow_and_breadth_contracts_stay_metadata_only_and_unwired() -> None:
    expected_by_key = {
        ("authorized.us_etf_flow", "us_etf_flow_daily"): "authorized_us_etf_flow_feed_not_configured",
        ("authorized.us_etf_flow", "us_etf_creation_redemption"): "authorized_us_etf_flow_feed_not_configured",
        ("authorized.us_etf_flow", "us_sector_etf_flow"): "authorized_us_etf_flow_feed_not_configured",
        (
            "official_or_authorized.us_market_breadth",
            "us_market_breadth_constituents",
        ): "authorized_us_market_breadth_feed_not_configured",
        (
            "official_or_authorized.us_market_breadth",
            "us_sector_breadth",
        ): "authorized_us_market_breadth_feed_not_configured",
        (
            "official_or_authorized.us_market_breadth",
            "us_advancers_decliners",
        ): "authorized_us_market_breadth_feed_not_configured",
        (
            "official_or_authorized.us_market_breadth",
            "us_new_highs_lows",
        ): "authorized_us_market_breadth_feed_not_configured",
        (
            "official_or_authorized.us_market_breadth",
            "us_above_ma_breadth",
        ): "authorized_us_market_breadth_feed_not_configured",
    }

    assert get_provider_capability("authorized.us_etf_flow") is None
    assert get_provider_capability("official_or_authorized.us_market_breadth") is None

    for provider_id, capability in FUTURE_AUTHORIZED_SUPPORT_CONTRACTS:
        contract = get_provider_capability_support_contract(provider_id, capability)

        assert contract is not None
        assert contract.provider_id == provider_id
        assert contract.capability == capability
        assert contract.observation_only is True
        assert contract.score_contribution_allowed is False
        assert contract.paid_data_likely_required is True
        assert contract.key_required is True
        assert contract.cache_required is True
        assert contract.background_refresh_recommended is True
        assert contract.missing_provider_reason == expected_by_key[(provider_id, capability)]

    assert {
        (item.provider_id, item.capability)
        for item in list_provider_capability_support_contracts()
        if item.provider_id in {
            "authorized.us_etf_flow",
            "official_or_authorized.us_market_breadth",
        }
    } == FUTURE_AUTHORIZED_SUPPORT_CONTRACTS


def test_provider_capability_import_does_not_import_live_provider_clients() -> None:
    script = """
import json
import src.services.provider_capability_matrix
blocked = [
    "data_provider.alpaca_fetcher",
    "data_provider.twelve_data_fetcher",
    "data_provider.alphavantage_provider",
    "data_provider.us_fundamentals_provider",
    "data_provider.yfinance_fetcher",
    "src.services.market_cache",
    "src.services.analysis_provider_planner",
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


def test_provider_capability_import_has_no_runtime_planner_side_effect() -> None:
    planner = importlib.import_module("src.services.analysis_provider_planner")
    before = planner.build_analysis_provider_plan("AAPL", market="us").categories

    importlib.import_module("src.services.provider_capability_matrix")
    after = planner.build_analysis_provider_plan("AAPL", market="us").categories

    assert before == after


def test_akshare_remains_an_advisory_cn_hk_provider_and_other_runtime_only_ids_stay_absent() -> None:
    akshare = get_provider_capability("akshare")

    assert akshare is not None
    assert akshare.markets == (ProviderMarket.CN, ProviderMarket.HK)
    assert akshare.domains == (
        ProviderDomain.QUOTE,
        ProviderDomain.OHLCV,
        ProviderDomain.TECHNICALS,
    )
    assert akshare.freshness_class is FreshnessClass.DELAYED
    assert akshare.scanner_usage is ScannerUsage.TOP_N_ONLY
    assert akshare.backtest_usage is BacktestUsage.NEVER

    for provider_id in ("tickflow", "efinance", "tushare", "binance", "fred", "treasury", "ny_fed"):
        assert get_provider_capability(provider_id) is None


def test_hk_quote_and_ohlcv_provider_matrix_remains_bounded_to_current_metadata() -> None:
    hk_quote_providers = {
        capability.provider_id
        for capability in providers_for_domain(ProviderDomain.QUOTE)
        if ProviderMarket.HK in capability.markets
    }
    hk_ohlcv_providers = {
        capability.provider_id
        for capability in providers_for_domain(ProviderDomain.OHLCV)
        if ProviderMarket.HK in capability.markets
    }

    assert hk_quote_providers == {
        "akshare",
        "local_cache",
        "twelve_data",
        "yahoo_yfinance",
    }
    assert hk_ohlcv_providers == {
        "akshare",
        "local_cache",
        "local_ohlcv",
        "twelve_data",
        "yahoo_yfinance",
    }

    twelve_data = get_provider_capability("twelve_data")
    assert twelve_data is not None
    assert twelve_data.scanner_usage is ScannerUsage.TOP_N_ONLY
    assert twelve_data.freshness_class is FreshnessClass.DELAYED


def test_provider_capability_matrix_preserves_category_boundaries_for_local_no_key_and_registry_only_sources() -> None:
    fallback_static_only = {
        "local_cache": FreshnessClass.CACHED,
        "local_ohlcv": FreshnessClass.CACHED,
        "local_news_cache": FreshnessClass.CACHED,
        "local_inference": FreshnessClass.INFERRED,
    }
    configured_and_wired = {"alpaca", "twelve_data", "fmp", "finnhub"}

    for provider_id, freshness_class in fallback_static_only.items():
        capability = get_provider_capability(provider_id)
        assert capability is not None
        assert capability.quota_class is ProviderQuotaClass.LOCAL
        assert capability.freshness_class is freshness_class
        assert capability.backtest_usage is BacktestUsage.LOCAL_ONLY

    yahoo = get_provider_capability("yahoo_yfinance")
    assert yahoo is not None
    assert yahoo.quota_class is ProviderQuotaClass.CHEAP
    assert yahoo.freshness_class is FreshnessClass.DELAYED
    assert yahoo.scanner_usage is ScannerUsage.TOP_N_ONLY

    for provider_id in configured_and_wired:
        capability = get_provider_capability(provider_id)
        assert capability is not None
        assert capability.quota_class is not ProviderQuotaClass.LOCAL
        assert capability.quick_analysis_allowed or capability.standard_analysis_allowed

    alpha_vantage = get_provider_capability("alpha_vantage")
    assert alpha_vantage is not None
    assert alpha_vantage.quick_analysis_allowed is False
    assert alpha_vantage.standard_analysis_allowed is False
    assert alpha_vantage.deep_research_allowed is True
    assert alpha_vantage.freshness_class is FreshnessClass.MANUAL_REVIEW
    assert "alpha_vantage_api_key" not in SRC_CONFIG_TEXT
    assert "alpha_vantage_api_keys" not in SRC_CONFIG_TEXT


@pytest.mark.parametrize(
    ("provider_id", "fetcher", "expected_trust_level", "expected_source_tier"),
    [
        ("pytdx", PytdxFetcher, "usable_with_caution", "unofficial_public_api"),
        ("akshare", AkshareFetcher, "weak", "unofficial_public_api"),
        ("baostock", BaostockFetcher, "usable_with_caution", "third_party_free_api"),
    ],
)
def test_cn_provider_probe_contract_metadata_stays_in_lockstep(
    provider_id: str,
    fetcher: type,
    expected_trust_level: str,
    expected_source_tier: str,
) -> None:
    contract_capabilities = tuple(
        sorted(item.capability for item in list_provider_capability_support_contracts(provider_id))
    )
    supported_capabilities = tuple(sorted(fetcher.SUPPORTED_CAPABILITIES))

    assert contract_capabilities == supported_capabilities
    assert set(contract_capabilities).isdisjoint(fetcher.UNSUPPORTED_CAPABILITIES)

    contracts = list_provider_capability_support_contracts(provider_id)
    assert contracts
    assert {item.observation_only for item in contracts} == {True}
    assert {item.score_contribution_allowed for item in contracts} == {False}
    assert {item.key_required for item in contracts} == {False}
    assert {item.cache_required for item in contracts} == {True}
    assert {item.background_refresh_recommended for item in contracts} == {True}
    assert {item.source_type for item in contracts} == {"public_proxy"}
    assert {item.source_tier for item in contracts} == {expected_source_tier}
    assert {item.trust_level for item in contracts} == {expected_trust_level}
    assert "reliable" not in {item.trust_level for item in contracts}
    assert "official_public" not in {item.source_type for item in contracts}
    assert "exchange_authorized" not in {item.source_tier for item in contracts}


def test_unsupported_capability_is_distinct_from_provider_activation_or_credentials() -> None:
    assert get_provider_capability_support_contract("baostock", "options_chain") is None

    supported = get_provider_capability_support_contract("baostock", "cn_history_daily")

    assert supported is not None
    assert supported.capability == "cn_history_daily"
    assert supported.key_required is False
    assert supported.missing_provider_reason == "baostock_not_installed"


def test_provider_capability_support_contracts_use_known_onboarding_vocabulary() -> None:
    contracts = list_provider_capability_support_contracts()

    assert {item.source_type for item in contracts} == KNOWN_SUPPORT_SOURCE_TYPES
    assert {item.freshness_expectation for item in contracts} == KNOWN_SUPPORT_FRESHNESS_EXPECTATIONS
    assert {item.observation_only for item in contracts} == {True}
    assert {item.score_contribution_allowed for item in contracts} == {False}


def test_provider_capability_metadata_documents_provenance_vocabulary_parity_guard() -> None:
    text = PROVIDER_CAPABILITY_METADATA_DOC.read_text(encoding="utf-8")

    assert "## Provenance vocabulary parity guard" in text
    assert "not interchangeable" in text
    assert "must not be used as aliases" in text
    assert all(term in text for term in PROVENANCE_VOCABULARY_GUARD_TERMS)


def test_provider_fit_metadata_helpers_are_deterministic_and_do_not_modify_runtime_capability_ids() -> None:
    first = list_provider_fit_metadata()
    second = list_provider_fit_metadata()

    assert first == second
    assert first is not second
    assert get_provider_fit_metadata("SEC_EDGAR") == get_provider_fit_metadata("sec_edgar")
    assert get_provider_fit_metadata("sec_edgar") is not None
    assert get_provider_dry_run_probe_contract("coinbase_public") is not None
    assert get_provider_dry_run_probe_contract("missing") is None
    assert len(list_provider_dry_run_probe_contracts()) == len(first)
    assert get_provider_capability("sec_edgar") is None
    assert get_provider_capability("coinbase_public") is None


def test_diagnostic_fit_metadata_rows_remain_observation_only_and_non_authoritative() -> None:
    diagnostic_rows = tuple(
        item for item in list_provider_fit_metadata() if item.provider_category.endswith("_diagnostic_gap")
    )

    assert diagnostic_rows
    assert {item.freshness_expectation for item in diagnostic_rows} == KNOWN_DIAGNOSTIC_FRESHNESS_EXPECTATIONS

    for item in diagnostic_rows:
        probe = get_provider_dry_run_probe_contract(item.provider_id)

        assert item.observation_only is True
        assert item.score_contribution_allowed is False
        assert item.trust_level not in SCORE_GRADE_TRUST_LEVELS
        assert item.degradation_reason == "provider_fit_metadata_only"
        assert probe is not None
        assert probe.observation_only is True
        assert probe.score_contribution_allowed is False
        assert probe.network_call_executed is False
        assert probe.no_default_live_http_calls is True


def test_provider_fit_metadata_includes_portfolio_watchlist_and_options_gap_rows() -> None:
    expected = {
        "portfolio.price_provenance": {
            "provider_category": "portfolio_diagnostic_gap",
            "surface": "portfolio",
            "paid_data_likely_required": False,
            "key_required": False,
            "cache_required": True,
        },
        "portfolio.fx_provenance": {
            "provider_category": "portfolio_diagnostic_gap",
            "surface": "portfolio",
            "paid_data_likely_required": False,
            "key_required": False,
            "cache_required": True,
        },
        "portfolio.sector_industry_exposure": {
            "provider_category": "portfolio_diagnostic_gap",
            "surface": "portfolio",
            "paid_data_likely_required": False,
            "key_required": False,
            "cache_required": True,
        },
        "portfolio.factor_risk_metrics": {
            "provider_category": "portfolio_diagnostic_gap",
            "surface": "portfolio",
            "paid_data_likely_required": False,
            "key_required": False,
            "cache_required": True,
        },
        "portfolio.benchmark_return_history": {
            "provider_category": "portfolio_diagnostic_gap",
            "surface": "portfolio",
            "paid_data_likely_required": False,
            "key_required": False,
            "cache_required": True,
        },
        "watchlist.scanner_score_snapshot": {
            "provider_category": "watchlist_diagnostic_gap",
            "surface": "watchlist",
            "paid_data_likely_required": False,
            "key_required": False,
            "cache_required": True,
        },
        "watchlist.score_refresh_freshness": {
            "provider_category": "watchlist_diagnostic_gap",
            "surface": "watchlist",
            "paid_data_likely_required": False,
            "key_required": False,
            "cache_required": True,
        },
        "watchlist.no_score_stale_state": {
            "provider_category": "watchlist_diagnostic_gap",
            "surface": "watchlist",
            "paid_data_likely_required": False,
            "key_required": False,
            "cache_required": True,
        },
        "watchlist.source_confidence_preservation": {
            "provider_category": "watchlist_diagnostic_gap",
            "surface": "watchlist",
            "paid_data_likely_required": False,
            "key_required": False,
            "cache_required": True,
        },
        "options_lab.synthetic_fixture_chain": {
            "provider_category": "options_lab_diagnostic_gap",
            "surface": "options_lab",
            "paid_data_likely_required": False,
            "key_required": False,
            "cache_required": True,
        },
        "options_lab.disabled_live_provider_stubs": {
            "provider_category": "options_lab_diagnostic_gap",
            "surface": "options_lab",
            "paid_data_likely_required": False,
            "key_required": False,
            "cache_required": False,
        },
        "options_lab.bid_ask_liquidity_gate": {
            "provider_category": "options_lab_diagnostic_gap",
            "surface": "options_lab",
            "paid_data_likely_required": True,
            "key_required": True,
            "cache_required": True,
        },
        "options_lab.oi_volume_gate": {
            "provider_category": "options_lab_diagnostic_gap",
            "surface": "options_lab",
            "paid_data_likely_required": True,
            "key_required": True,
            "cache_required": True,
        },
        "options_lab.iv_greeks_gate": {
            "provider_category": "options_lab_diagnostic_gap",
            "surface": "options_lab",
            "paid_data_likely_required": True,
            "key_required": True,
            "cache_required": True,
        },
        "options_lab.iv_rank_history": {
            "provider_category": "options_lab_diagnostic_gap",
            "surface": "options_lab",
            "paid_data_likely_required": True,
            "key_required": True,
            "cache_required": True,
        },
    }

    for provider_id, entry in expected.items():
        metadata = get_provider_fit_metadata(provider_id)
        probe = get_provider_dry_run_probe_contract(provider_id)

        assert metadata is not None
        assert probe is not None
        assert get_provider_capability(provider_id) is None
        assert metadata.provider_category == entry["provider_category"]
        assert metadata.observation_only is True
        assert metadata.score_contribution_allowed is False
        assert metadata.best_use_cases[0] == entry["surface"]
        assert metadata.paid_data_likely_required is entry["paid_data_likely_required"]
        assert metadata.key_required is entry["key_required"]
        assert metadata.cache_required is entry["cache_required"]
        assert probe.no_default_live_http_calls is True
        assert probe.network_call_executed is False
        assert probe.observation_only is True
        assert probe.score_contribution_allowed is False
