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
    assert all(
        family["integrationActionPlan"]
        for family in families.values()
    )
    assert all(
        set(action) == {
            "actionKey",
            "actionLabel",
            "actionType",
            "priority",
            "status",
            "reason",
            "requiredEvidence",
            "blockedBy",
            "affectedSurfacesOrCapabilities",
            "nextConcreteStep",
            "requiresExternalProviderLicenseWork",
            "requiresProtectedDomainReview",
        }
        for family in families.values()
        for action in family["integrationActionPlan"]
    )
    assert {
        action["actionType"]
        for family_key in (
            "options_chains",
            "options_strategy_analytics",
            "gamma_dealer_positioning",
        )
        for action in families[family_key]["integrationActionPlan"]
    } <= {"provider-entitlement", "evidence-validation", "manual-review", "blocked"}
    assert {
        action["status"]
        for family_key in (
            "options_chains",
            "options_strategy_analytics",
            "gamma_dealer_positioning",
        )
        for action in families[family_key]["integrationActionPlan"]
    } <= {"waiting-entitlement", "waiting-evidence", "planned", "blocked"}
    assert all(
        action["requiresExternalProviderLicenseWork"] is True
        for family_key in (
            "options_chains",
            "options_strategy_analytics",
            "gamma_dealer_positioning",
        )
        for action in families[family_key]["integrationActionPlan"]
        if action["actionType"] == "provider-entitlement"
    )
    assert all(
        "ready" not in action["actionKey"]
        and "unlocked" not in action["actionKey"]
        and "就绪" not in action["actionLabel"]
        and "解锁" not in action["actionLabel"]
        for family_key in (
            "options_chains",
            "options_strategy_analytics",
            "gamma_dealer_positioning",
        )
        for action in families[family_key]["integrationActionPlan"]
    )
    assert {
        action["actionType"]
        for action in families["stock_quote_spine"]["integrationActionPlan"]
    } >= {"provider-integration", "evidence-validation"}
    assert {
        action["actionType"]
        for action in families["portfolio_valuation_lineage"]["integrationActionPlan"]
    } >= {"provider-integration", "evidence-validation"}
    assert all(
        action["actionType"] != "blocked" or action["priority"] not in {"critical", "high"}
        for family in families.values()
        if family["status"] == "ready"
        for action in family["integrationActionPlan"]
    )
    assert all(
        impact["impactState"]
        in {"unlocked", "degraded", "observation-only", "blocked", "planned", "unknown"}
        for family in families.values()
        for impact in family["surfaceImpactMatrix"]
    )

    quote_surfaces = {
        impact["surfaceKey"]: impact["impactState"]
        for impact in families["stock_quote_spine"]["surfaceImpactMatrix"]
    }
    assert quote_surfaces["watchlist"] == "degraded"
    assert quote_surfaces["stock_detail"] == "degraded"
    assert quote_surfaces["portfolio"] == "degraded"
    assert quote_surfaces["backtest_parameter_sweep"] == "observation-only"

    for family_key in (
        "options_chains",
        "options_strategy_analytics",
        "gamma_dealer_positioning",
    ):
        assert all(
            impact["impactState"] != "unlocked"
            for impact in families[family_key]["surfaceImpactMatrix"]
        )

    backtest_impacts = families["backtest_dataset_lineage"]["surfaceImpactMatrix"]
    assert {impact["surfaceKey"] for impact in backtest_impacts} == {
        "backtest_parameter_sweep",
        "factor_research",
    }
    assert {impact["impactState"] for impact in backtest_impacts} == {
        "observation-only",
    }

    scenario_impacts = {
        impact["surfaceKey"]: impact["impactState"]
        for impact in families["scenario_baselines"]["surfaceImpactMatrix"]
    }
    assert scenario_impacts["scenario_lab"] == "planned"
    assert scenario_impacts["evidence_harness"] == "planned"

    portfolio_impacts = {
        impact["surfaceKey"]: impact
        for impact in families["portfolio_valuation_lineage"]["surfaceImpactMatrix"]
    }
    assert portfolio_impacts["portfolio"]["impactState"] == "degraded"
    assert "估值置信度" in portfolio_impacts["portfolio"]["affectedCapability"]

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
