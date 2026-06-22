# -*- coding: utf-8 -*-
"""Contract tests for the data source gap registry service."""

from __future__ import annotations

import json

from src.services import data_source_gap_registry_service as registry_service
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
EXPECTED_QUEUE_FIELDS = {
    "familyKey",
    "familyLabel",
    "priority",
    "priorityReason",
    "readinessState",
    "primaryBlockerType",
    "affectedSurfaceCount",
    "blockedOrDegradedCapabilityCount",
    "externalEntitlementRequired",
    "protectedDomainReviewRequired",
    "nextConcreteStep",
    "requiredEvidence",
    "consumerSafeWarning",
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

    queue = first["acquisitionPriorityQueue"]
    assert [item["familyKey"] for item in queue] == [
        item["familyKey"] for item in second["acquisitionPriorityQueue"]
    ]
    assert {item["familyKey"] for item in queue} == EXPECTED_FAMILY_KEYS
    assert all(set(item) == EXPECTED_QUEUE_FIELDS for item in queue)
    queue_by_key = {item["familyKey"]: item for item in queue}
    assert queue_by_key["stock_quote_spine"]["priority"] == "critical"
    assert queue_by_key["stock_quote_spine"]["primaryBlockerType"] == (
        "provider-integration"
    )
    assert queue_by_key["stock_quote_spine"]["affectedSurfaceCount"] == 5
    assert (
        queue_by_key["stock_quote_spine"]["blockedOrDegradedCapabilityCount"] == 4
    )
    assert queue_by_key["stock_quote_spine"]["externalEntitlementRequired"] is False
    assert queue_by_key["stock_quote_spine"]["protectedDomainReviewRequired"] is True
    assert "5 个产品面" in queue_by_key["stock_quote_spine"]["priorityReason"]
    assert "工程补数队列" in queue_by_key["stock_quote_spine"]["consumerSafeWarning"]
    assert queue_by_key["portfolio_valuation_lineage"]["priority"] == "high"
    assert (
        queue.index(queue_by_key["stock_quote_spine"])
        < queue.index(queue_by_key["portfolio_valuation_lineage"])
    )
    assert queue_by_key["scenario_baselines"]["primaryBlockerType"] == (
        "schema-contract"
    )
    assert queue_by_key["scenario_baselines"]["priority"] == "medium"

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
    for family_key in (
        "options_chains",
        "options_strategy_analytics",
        "gamma_dealer_positioning",
    ):
        assert queue_by_key[family_key]["priority"] == "critical"
        assert queue_by_key[family_key]["primaryBlockerType"] == "entitlement"
        assert queue_by_key[family_key]["readinessState"] in {
            "blocked",
            "unauthorized",
        }
        assert queue_by_key[family_key]["externalEntitlementRequired"] is True
        assert queue_by_key[family_key]["protectedDomainReviewRequired"] is True
        assert "授权" in queue_by_key[family_key]["nextConcreteStep"]
        assert "已就绪" not in queue_by_key[family_key]["priorityReason"]
        assert "ready" not in queue_by_key[family_key]["priorityReason"].lower()
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
        "trading advice",
        "investment advice",
        "recommended",
        "winner",
    ):
        assert forbidden not in serialized


def test_ready_family_only_produces_low_priority_monitoring_queue_item(
    monkeypatch,
) -> None:
    ready_family = registry_service.DataSourceGapRegistryFamily(
        family_key="ready_family",
        consumer_label="Ready Family",
        status="ready",
        authority_state="allowed",
        freshness_state="fresh",
        entitlement_or_licensing_blocker=None,
        integration_blocker=None,
        source_evidence_state="validated",
        next_integration_step="Keep monitoring.",
        provider_hydration_allowed=True,
        score_trading_authority_allowed=True,
        consumer_safe_description="Ready data family.",
        surface_impact_matrix=(
            registry_service.DataSourceSurfaceImpact(
                surface_key="market_overview",
                consumer_label="Market Overview",
                impact_state="unlocked",
                impact_reason="Validated.",
                affected_capability="Validated capability.",
                next_evidence_step="Keep monitoring.",
            ),
        ),
    )
    monkeypatch.setattr(registry_service, "_FAMILIES", (ready_family,))

    payload = registry_service.build_data_source_gap_registry()

    assert payload["summary"]["readyCount"] == 1
    assert payload["acquisitionPriorityQueue"] == [
        {
            "familyKey": "ready_family",
            "familyLabel": "Ready Family",
            "priority": "low",
            "priorityReason": (
                "低优先级监控：影响 1 个产品面，0 项能力阻断或降级；"
                "当前行动为 保持证据监控。"
            ),
            "readinessState": "ready",
            "primaryBlockerType": "evidence-validation",
            "affectedSurfaceCount": 1,
            "blockedOrDegradedCapabilityCount": 0,
            "externalEntitlementRequired": False,
            "protectedDomainReviewRequired": False,
            "nextConcreteStep": "保持只读监控，不新增阻断行动。",
            "requiredEvidence": ["周期性 freshness 检查"],
            "consumerSafeWarning": "当前家族已就绪，仅保留工程监控。",
        }
    ]
    assert payload["acquisitionPriorityQueue"][0]["priority"] != "critical"
