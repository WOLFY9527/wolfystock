# -*- coding: utf-8 -*-
"""Offline contracts for inert provider capability metadata."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys

import pytest

from src.services.provider_capability_matrix import (
    FreshnessClass,
    ProviderDomain,
    ProviderMarket,
    ProviderQuotaClass,
    ScannerUsage,
    BacktestUsage,
    get_provider_capability,
    is_provider_allowed_for_backtest,
    is_provider_allowed_for_scanner,
    list_provider_capabilities,
    providers_for_domain,
    recommended_ttl,
)


EXPECTED_PROVIDER_IDS = {
    "local_cache",
    "local_ohlcv",
    "yahoo_yfinance",
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
