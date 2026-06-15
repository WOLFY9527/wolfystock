# -*- coding: utf-8 -*-
"""Focused consistency guard for homepage cockpit module coverage."""

from __future__ import annotations

from collections import Counter

from src.services.homepage_capabilities_service import HomepageCapabilitiesService
from src.services.homepage_intelligence_service import HomepageIntelligenceService
from src.services.homepage_module_manifest_service import HomepageModuleManifestService
from src.services.homepage_section_layout_service import HomepageSectionLayoutService
from src.services.homepage_uat_readiness_service import HomepageUatReadinessService
from tests.test_homepage_schema_serialization_stress import PUBLIC_HOMEPAGE_OUTPUTS


FIXED_LAYOUT_AS_OF = "2026-06-15T09:30:00Z"
FIXED_MANIFEST_AS_OF = "2026-06-15T00:00:00Z"
CANONICAL_COCKPIT_MODULE_KEYS = (
    "dailyMarketBrief",
    "riskRegime",
    "crossAssetIndicators",
    "eventImpactMap",
    "driverChain",
    "themeCapitalFlow",
    "researchPriorities",
    "evidenceQuality",
    "ratesPricing",
    "volatilityPositioning",
    "liquidityCredit",
    "marketBreadth",
    "afterCloseDevelopments",
    "scenarioWatchlist",
    "earningsCatalysts",
    "geopoliticalCommodityRisk",
    "aiCapexInfrastructure",
    "policyRegulationWatch",
    "styleLeadershipRotation",
    "preSessionResearchChecklist",
)
CANONICAL_SNAKE_CASE_BY_CAMEL = {
    "dailyMarketBrief": "daily_market_brief",
    "riskRegime": "risk_regime",
    "crossAssetIndicators": "cross_asset_indicators",
    "eventImpactMap": "event_impact_map",
    "driverChain": "driver_chain",
    "themeCapitalFlow": "theme_capital_flow",
    "researchPriorities": "research_priorities",
    "evidenceQuality": "evidence_quality",
    "ratesPricing": "rates_pricing",
    "volatilityPositioning": "volatility_positioning",
    "liquidityCredit": "liquidity_credit",
    "marketBreadth": "market_breadth",
    "afterCloseDevelopments": "after_close_developments",
    "scenarioWatchlist": "scenario_watchlist",
    "earningsCatalysts": "earnings_catalysts",
    "geopoliticalCommodityRisk": "geopolitical_commodity_risk",
    "aiCapexInfrastructure": "ai_capex_infrastructure",
    "policyRegulationWatch": "policy_regulation_watch",
    "styleLeadershipRotation": "style_leadership_rotation",
    "preSessionResearchChecklist": "pre_session_research_checklist",
}
CANONICAL_CAMEL_BY_SNAKE_CASE = {
    snake_case: camel_case
    for camel_case, snake_case in CANONICAL_SNAKE_CASE_BY_CAMEL.items()
}
# Homepage capabilities keeps legacy compatibility flags in addition to the current
# cockpit module set. They are documented here so new extras fail closed.
DOCUMENTED_LEGACY_CAPABILITY_FLAGS = (
    "marketPulse",
    "moneyFlowProxy",
    "eventRadar",
    "personalSummary",
    "researchQueue",
    "publicDataQuality",
    "sessionStatus",
    "eventWindows",
    "noAdviceBoundary",
)
REQUIRED_SERIALIZATION_STRESS_CASES = {
    "HomepageIntelligenceService.build_bundle",
    "HomepageCapabilitiesService.build_snapshot",
    "HomepageModuleManifestService.build_manifest",
    "HomepageSectionLayoutService.build_layout",
    "HomepageUatReadinessService.build_checklist",
}


def _normalize_snake_case_keys(keys: list[str]) -> list[str]:
    return [CANONICAL_CAMEL_BY_SNAKE_CASE[key] for key in keys]


def test_canonical_cockpit_module_set_stays_aligned_across_capabilities_manifest_and_aggregate() -> None:
    capabilities_payload = HomepageCapabilitiesService().build_snapshot().model_dump(mode="json")
    manifest_payload = HomepageModuleManifestService().build_manifest(as_of=FIXED_MANIFEST_AS_OF)
    intelligence_payload = HomepageIntelligenceService().build_bundle()

    capabilities_section_keys = [section["key"] for section in capabilities_payload["sections"]]
    manifest_module_keys = [module["key"] for module in manifest_payload["modules"]]
    aggregate_module_keys = [module["key"] for module in intelligence_payload["cockpitModules"]["modules"]]

    assert capabilities_section_keys == list(CANONICAL_COCKPIT_MODULE_KEYS)
    assert manifest_module_keys == list(CANONICAL_COCKPIT_MODULE_KEYS)
    assert intelligence_payload["cockpitModules"]["moduleOrder"] == list(CANONICAL_COCKPIT_MODULE_KEYS)
    assert aggregate_module_keys == list(CANONICAL_COCKPIT_MODULE_KEYS)
    assert intelligence_payload["cockpitModules"]["moduleCount"] == len(CANONICAL_COCKPIT_MODULE_KEYS)

    enabled_capability_flags = {
        key
        for key, value in capabilities_payload["capabilities"].items()
        if value is True
    }
    assert enabled_capability_flags == (
        set(CANONICAL_COCKPIT_MODULE_KEYS) | set(DOCUMENTED_LEGACY_CAPABILITY_FLAGS)
    )


def test_section_layout_represents_each_canonical_module_exactly_once() -> None:
    layout_payload = HomepageSectionLayoutService().build_layout(as_of=FIXED_LAYOUT_AS_OF)

    flattened_layout_keys = [
        module["key"]
        for section in layout_payload["sections"]
        for module in section["modules"]
    ]
    layout_key_counts = Counter(_normalize_snake_case_keys(flattened_layout_keys))
    missing_layout_keys = sorted(set(CANONICAL_COCKPIT_MODULE_KEYS) - set(layout_key_counts))
    extra_layout_keys = sorted(set(layout_key_counts) - set(CANONICAL_COCKPIT_MODULE_KEYS))
    duplicated_layout_keys = {
        key: count
        for key, count in layout_key_counts.items()
        if count != 1
    }

    assert missing_layout_keys == [], f"layout missing canonical cockpit modules: {missing_layout_keys}"
    assert extra_layout_keys == [], f"layout has undocumented cockpit modules: {extra_layout_keys}"
    assert duplicated_layout_keys == {}, f"layout must represent each module exactly once: {duplicated_layout_keys}"


def test_uat_readiness_covers_the_same_canonical_module_set_without_extras() -> None:
    readiness_payload = HomepageUatReadinessService().build_checklist(as_of=FIXED_LAYOUT_AS_OF)

    readiness_module_keys = _normalize_snake_case_keys(
        [module["key"] for module in readiness_payload["cockpitModules"]]
    )

    assert readiness_payload["moduleSummary"]["totalModules"] == len(CANONICAL_COCKPIT_MODULE_KEYS)
    assert readiness_module_keys == list(CANONICAL_COCKPIT_MODULE_KEYS)


def test_serialization_stress_keeps_core_cockpit_public_contract_cases_registered() -> None:
    registered_case_names = {case_name for case_name, _ in PUBLIC_HOMEPAGE_OUTPUTS}

    assert REQUIRED_SERIALIZATION_STRESS_CASES <= registered_case_names
