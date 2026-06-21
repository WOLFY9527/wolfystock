# -*- coding: utf-8 -*-
"""Contract tests for the data source gap registry service."""

from __future__ import annotations

import json

from src.services.data_source_gap_registry_service import build_data_source_gap_registry


EXPECTED_FAMILY_KEYS = {
    "stock_quote_spine",
    "fundamentals",
    "etf_index_coverage",
    "macro_rates",
    "fed_liquidity",
    "credit_stress",
    "vix_volatility",
    "breadth_flows_positioning",
    "options_chains",
    "options_strategy_analytics",
    "gamma_dealer_positioning",
    "backtest_dataset_lineage",
    "scenario_baselines",
    "portfolio_valuation_lineage",
}


def test_data_source_gap_registry_is_deterministic_and_fail_closed() -> None:
    first = build_data_source_gap_registry()
    second = build_data_source_gap_registry()

    assert first == second
    assert first["contractVersion"] == "data_source_gap_registry_v1"
    assert first["diagnosticOnly"] is True
    assert first["providerRuntimeCalled"] is False
    assert first["networkCallsEnabled"] is False
    assert first["scoreAuthorityAllowed"] is False

    families = {item["familyKey"]: item for item in first["families"]}
    assert set(families) == EXPECTED_FAMILY_KEYS
    assert families["stock_quote_spine"]["status"] == "partial"
    assert families["stock_quote_spine"]["authorityState"] == "blocked"
    assert families["stock_quote_spine"]["providerHydrationAllowed"] is True
    assert families["stock_quote_spine"]["scoreTradingAuthorityAllowed"] is False
    assert families["options_chains"]["status"] == "unauthorized"
    assert families["options_chains"]["authorityState"] == "unauthorized"
    assert families["options_chains"]["providerHydrationAllowed"] is False
    assert families["options_chains"]["scoreTradingAuthorityAllowed"] is False
    assert families["scenario_baselines"]["status"] == "planned"
    assert families["scenario_baselines"]["authorityState"] == "planned"
    assert families["scenario_baselines"]["providerHydrationAllowed"] is False
    assert families["scenario_baselines"]["scoreTradingAuthorityAllowed"] is False
    assert families["portfolio_valuation_lineage"]["status"] == "partial"
    assert families["portfolio_valuation_lineage"]["authorityState"] == "blocked"
    assert families["portfolio_valuation_lineage"]["providerHydrationAllowed"] is True
    assert families["portfolio_valuation_lineage"]["scoreTradingAuthorityAllowed"] is False

    assert first["summary"]["readyCount"] == 0
    assert first["summary"]["scoreTradingAuthorityAllowedCount"] == 0

    serialized = json.dumps(first, ensure_ascii=False).lower()
    for forbidden in (
        "providerid",
        "providername",
        "rawpayload",
        "traceid",
        "requestid",
        "api_key",
        "secret",
        "cookie",
        "alpaca",
        "yfinance",
        "polygon",
        "tushare",
        "akshare",
        "finnhub",
    ):
        assert forbidden not in serialized
