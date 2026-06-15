# -*- coding: utf-8 -*-
"""Serialization stress coverage for current homepage public contracts."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import json
import re
from typing import Any

import pytest
from pydantic import BaseModel

from src.services.homepage_after_close_developments_service import (
    HomepageAfterCloseDevelopmentsService,
)
from src.services.homepage_ai_capex_infrastructure_service import (
    HomepageAICapexInfrastructureService,
)
from src.services.homepage_capabilities_service import HomepageCapabilitiesService
from src.services.homepage_cross_asset_indicators_service import HomepageCrossAssetIndicatorsService
from src.services.homepage_daily_market_brief_service import HomepageDailyMarketBriefService
from src.services.homepage_driver_chain_service import HomepageDriverChainService
from src.services.homepage_empty_state_service import HomepageEmptyStateService
from src.services.homepage_earnings_catalysts_service import HomepageEarningsCatalystsService
from src.services.homepage_event_impact_map_service import HomepageEventImpactMapService
from src.services.homepage_evidence_quality_service import HomepageEvidenceQualityService
from src.services.homepage_geopolitical_commodity_risk_service import (
    HomepageGeopoliticalCommodityRiskService,
)
from src.services.homepage_intelligence_service import HomepageIntelligenceService
from src.services.homepage_liquidity_credit_service import HomepageLiquidityCreditService
from src.services.homepage_market_breadth_service import HomepageMarketBreadthService
from src.services.homepage_module_manifest_service import HomepageModuleManifestService
from src.services.homepage_policy_regulation_watch_service import HomepagePolicyRegulationWatchService
from src.services.homepage_pre_session_research_checklist_service import (
    HomepagePreSessionResearchChecklistService,
)
from src.services.homepage_public_copy import (
    HOMEPAGE_PUBLIC_COPY_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_PUBLIC_STATUS_LABELS,
    sanitize_public_copy,
)
from src.services.homepage_rates_pricing_service import HomepageRatesPricingService
from src.services.homepage_research_priorities_service import HomepageResearchPrioritiesService
from src.services.homepage_risk_regime_service import HomepageRiskRegimeService
from src.services.homepage_scenario_watchlist_service import HomepageScenarioWatchlistService
from src.services.homepage_section_layout_service import HomepageSectionLayoutService
from src.services.homepage_style_leadership_rotation_service import (
    HomepageStyleLeadershipRotationService,
)
from src.services.homepage_theme_capital_flow_service import HomepageThemeCapitalFlowService
from src.services.homepage_uat_readiness_service import HomepageUatReadinessService
from src.services.homepage_volatility_positioning_service import HomepageVolatilityPositioningService


FIXED_AS_OF = "2026-06-15T00:00:00Z"
DISCLOSURE_KEYS = {"demoDisclosure", "noAdviceDisclosure", "no_advice_disclosure"}
SAFE_BOUNDARY_PHRASES = (
    "不包含交易建议",
    "不包含投资建议",
    "不包含交易指令",
    "不包含实时行情、交易建议或内部诊断",
    "不提供交易判断",
    "不构成交易指令",
    "不构成投资建议",
    "不构成个性化建议",
    "不构成个性化投资建议",
    "不作为任何个性化决策或执行依据",
    "不表达交易指令",
    "not personalized financial advice",
)
FORBIDDEN_KEY_FRAGMENTS = (
    "apikey",
    "api_key",
    "broker",
    "cache",
    "cookie",
    "debug",
    "diagnostic",
    "fallback",
    "provider",
    "raw",
    "runtime",
    "secret",
    "sessionid",
    "sourceurl",
    "source_url",
    "token",
    "traceback",
    "url",
)
FORBIDDEN_LITERAL_TERMS = (
    "交易指令",
    "交易执行",
    "交易建议",
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "清仓",
    "止损",
    "止盈",
    "目标价",
    "收益预测",
    "AI推荐",
    "智能选股",
)
FORBIDDEN_PATTERNS = (
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\bwww\.", re.IGNORECASE),
    re.compile(r"\bapi[_ -]?key\b", re.IGNORECASE),
    re.compile(r"\bbearer\s+[a-z0-9._-]+", re.IGNORECASE),
    re.compile(r"\bbroker\b", re.IGNORECASE),
    re.compile(r"\bcache\b", re.IGNORECASE),
    re.compile(r"\bcookie\b", re.IGNORECASE),
    re.compile(r"\bdebug\b", re.IGNORECASE),
    re.compile(r"\bdiagnostic(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bexception\b", re.IGNORECASE),
    re.compile(r"\bexecution\b", re.IGNORECASE),
    re.compile(r"\bfallback\b", re.IGNORECASE),
    re.compile(r"\binternal\b", re.IGNORECASE),
    re.compile(r"\border\b", re.IGNORECASE),
    re.compile(r"\bplace order\b", re.IGNORECASE),
    re.compile(r"\bprovider\b", re.IGNORECASE),
    re.compile(r"\braw(?:[_ -]?error|[_ -]?payload)?\b", re.IGNORECASE),
    re.compile(r"\breason[_ -]?code\b", re.IGNORECASE),
    re.compile(r"\bruntime\b", re.IGNORECASE),
    re.compile(r"\bsecret\b", re.IGNORECASE),
    re.compile(r"\bsession[_ -]?id\b", re.IGNORECASE),
    re.compile(r"\bsource[_ -]?type\b", re.IGNORECASE),
    re.compile(r"\bsubmit order\b", re.IGNORECASE),
    re.compile(r"\btake[\s-]?profit\b", re.IGNORECASE),
    re.compile(r"\btarget price\b", re.IGNORECASE),
    re.compile(r"\btoken\b", re.IGNORECASE),
    re.compile(r"\btraceback\b", re.IGNORECASE),
    re.compile(r"\btrade execution\b", re.IGNORECASE),
    re.compile(r"\btrading advice\b", re.IGNORECASE),
    re.compile(r"\btrust[_ -]?level\b", re.IGNORECASE),
    re.compile(r"内部诊断"),
)


def _json_payload(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_json_payload(item) for item in value]
    return value


def _scrub_public_boundaries(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): "<disclosure>" if key in DISCLOSURE_KEYS else _scrub_public_boundaries(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_scrub_public_boundaries(item) for item in value]
    return value


def _collect_key_paths(value: object, prefix: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    if isinstance(value, Mapping):
        found: list[tuple[str, ...]] = []
        for key, item in value.items():
            path = (*prefix, str(key))
            found.append(path)
            found.extend(_collect_key_paths(item, path))
        return found
    if isinstance(value, list):
        found = []
        for index, item in enumerate(value):
            found.extend(_collect_key_paths(item, (*prefix, str(index))))
        return found
    return []


def _serialize_public_output(case_name: str, build_output: Callable[[], object]) -> object:
    try:
        payload = _json_payload(build_output())
    except Exception as exc:  # pragma: no cover - exercised only on contract drift
        pytest.fail(f"{case_name} could not build a public homepage output: {type(exc).__name__}: {exc}")

    try:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        pytest.fail(f"{case_name} could not serialize as public JSON: {type(exc).__name__}: {exc}")

    decoded = json.loads(encoded)
    assert decoded == payload, case_name
    return payload


def _safe_serialized_text(payload: object) -> str:
    scrubbed = _scrub_public_boundaries(payload)
    serialized = json.dumps(scrubbed, ensure_ascii=False, sort_keys=True)
    for phrase in SAFE_BOUNDARY_PHRASES:
        serialized = serialized.replace(phrase, "<safe-boundary>")
    return serialized


def _assert_no_forbidden_key_paths(case_name: str, payload: object) -> None:
    leaked_paths: list[str] = []
    for path in _collect_key_paths(payload):
        normalized = path[-1].replace("-", "").replace("_", "").lower()
        if any(fragment in normalized for fragment in FORBIDDEN_KEY_FRAGMENTS):
            leaked_paths.append(".".join(path))

    assert leaked_paths == [], f"{case_name} leaked internal key paths: {leaked_paths}"


def _assert_no_forbidden_public_text(case_name: str, payload: object) -> None:
    serialized = _safe_serialized_text(payload)
    leaked = [term for term in FORBIDDEN_LITERAL_TERMS if term in serialized]
    for pattern in FORBIDDEN_PATTERNS:
        match = pattern.search(serialized)
        if match is not None:
            leaked.append(match.group(0))

    assert sorted(set(leaked)) == [], f"{case_name} leaked forbidden public markers: {sorted(set(leaked))}"


def _build_homepage_intelligence_bundle() -> object:
    return HomepageIntelligenceService().build_bundle()


def _build_homepage_capabilities_snapshot() -> object:
    return HomepageCapabilitiesService().build_snapshot()


def _build_homepage_module_manifest() -> object:
    return HomepageModuleManifestService().build_manifest(as_of=FIXED_AS_OF)


def _build_homepage_public_copy_helper_payload() -> dict[str, object]:
    return {
        "noAdviceDisclosure": HOMEPAGE_PUBLIC_COPY_NO_ADVICE_DISCLOSURE,
        "statusLabels": list(HOMEPAGE_PUBLIC_STATUS_LABELS),
        "sanitizedExample": sanitize_public_copy(
            "fallback trustLevel sourceType reasonCode raw provider traceback scaffold happy-path "
            "UAT https://example.invalid 买入 卖出 交易建议 正常"
        ),
    }


def _build_homepage_empty_state_contract() -> object:
    return HomepageEmptyStateService().build_contract()


def _build_homepage_section_layout() -> object:
    return HomepageSectionLayoutService().build_layout(as_of=FIXED_AS_OF)


def _build_homepage_uat_readiness() -> object:
    return HomepageUatReadinessService().build_checklist(as_of=FIXED_AS_OF)


def _build_homepage_daily_market_brief() -> object:
    return HomepageDailyMarketBriefService().build_daily_market_brief(as_of=FIXED_AS_OF)


def _build_homepage_risk_regime() -> object:
    return HomepageRiskRegimeService().build_snapshot()


def _build_homepage_cross_asset_indicators() -> object:
    return HomepageCrossAssetIndicatorsService().build_snapshot()


def _build_homepage_event_impact_map() -> object:
    return HomepageEventImpactMapService().build_event_impact_map()


def _build_homepage_driver_chain() -> object:
    return HomepageDriverChainService().build_snapshot()


def _build_homepage_theme_capital_flow() -> object:
    return HomepageThemeCapitalFlowService().build_snapshot()


def _build_homepage_research_priorities() -> object:
    return HomepageResearchPrioritiesService().build_contract()


def _build_homepage_evidence_quality() -> object:
    return HomepageEvidenceQualityService().build_projection()


def _build_homepage_rates_pricing() -> object:
    return HomepageRatesPricingService().build_snapshot()


def _build_homepage_volatility_positioning() -> object:
    return HomepageVolatilityPositioningService().build_snapshot()


def _build_homepage_liquidity_credit() -> object:
    return HomepageLiquidityCreditService().build_snapshot()


def _build_homepage_market_breadth() -> object:
    return HomepageMarketBreadthService().build_snapshot()


def _build_homepage_after_close_developments() -> object:
    return HomepageAfterCloseDevelopmentsService().build_snapshot()


def _build_homepage_scenario_watchlist() -> object:
    return HomepageScenarioWatchlistService().build_snapshot()


def _build_homepage_earnings_catalysts() -> object:
    return HomepageEarningsCatalystsService().build_snapshot()


def _build_homepage_geopolitical_commodity_risk() -> object:
    return HomepageGeopoliticalCommodityRiskService().build_snapshot()


def _build_homepage_ai_capex_infrastructure() -> object:
    return HomepageAICapexInfrastructureService().build_snapshot()


def _build_homepage_policy_regulation_watch() -> object:
    return HomepagePolicyRegulationWatchService().build_snapshot()


def _build_homepage_style_leadership_rotation() -> object:
    return HomepageStyleLeadershipRotationService().build_snapshot()


def _build_homepage_pre_session_research_checklist() -> object:
    return HomepagePreSessionResearchChecklistService().build_snapshot()


PUBLIC_HOMEPAGE_OUTPUTS: tuple[tuple[str, Callable[[], object]], ...] = (
    ("HomepageIntelligenceService.build_bundle", _build_homepage_intelligence_bundle),
    ("HomepageCapabilitiesService.build_snapshot", _build_homepage_capabilities_snapshot),
    ("HomepageModuleManifestService.build_manifest", _build_homepage_module_manifest),
    ("homepage_public_copy_helper_output", _build_homepage_public_copy_helper_payload),
    ("HomepageEmptyStateService.build_contract", _build_homepage_empty_state_contract),
    ("HomepageSectionLayoutService.build_layout", _build_homepage_section_layout),
    ("HomepageUatReadinessService.build_checklist", _build_homepage_uat_readiness),
    ("HomepageDailyMarketBriefService.build_daily_market_brief", _build_homepage_daily_market_brief),
    ("HomepageRiskRegimeService.build_snapshot", _build_homepage_risk_regime),
    ("HomepageCrossAssetIndicatorsService.build_snapshot", _build_homepage_cross_asset_indicators),
    ("HomepageEventImpactMapService.build_event_impact_map", _build_homepage_event_impact_map),
    ("HomepageDriverChainService.build_snapshot", _build_homepage_driver_chain),
    ("HomepageThemeCapitalFlowService.build_snapshot", _build_homepage_theme_capital_flow),
    ("HomepageResearchPrioritiesService.build_contract", _build_homepage_research_priorities),
    ("HomepageEvidenceQualityService.build_projection", _build_homepage_evidence_quality),
    ("HomepageRatesPricingService.build_snapshot", _build_homepage_rates_pricing),
    ("HomepageVolatilityPositioningService.build_snapshot", _build_homepage_volatility_positioning),
    ("HomepageLiquidityCreditService.build_snapshot", _build_homepage_liquidity_credit),
    ("HomepageMarketBreadthService.build_snapshot", _build_homepage_market_breadth),
    ("HomepageAfterCloseDevelopmentsService.build_snapshot", _build_homepage_after_close_developments),
    ("HomepageScenarioWatchlistService.build_snapshot", _build_homepage_scenario_watchlist),
    ("HomepageEarningsCatalystsService.build_snapshot", _build_homepage_earnings_catalysts),
    (
        "HomepageGeopoliticalCommodityRiskService.build_snapshot",
        _build_homepage_geopolitical_commodity_risk,
    ),
    ("HomepageAICapexInfrastructureService.build_snapshot", _build_homepage_ai_capex_infrastructure),
    ("HomepagePolicyRegulationWatchService.build_snapshot", _build_homepage_policy_regulation_watch),
    ("HomepageStyleLeadershipRotationService.build_snapshot", _build_homepage_style_leadership_rotation),
    (
        "HomepagePreSessionResearchChecklistService.build_snapshot",
        _build_homepage_pre_session_research_checklist,
    ),
)


@pytest.mark.parametrize(
    ("case_name", "build_output"),
    PUBLIC_HOMEPAGE_OUTPUTS,
    ids=[case_name for case_name, _ in PUBLIC_HOMEPAGE_OUTPUTS],
)
def test_homepage_public_contracts_serialize_to_json_without_leaking_internal_or_trading_copy(
    case_name: str,
    build_output: Callable[[], object],
) -> None:
    payload = _serialize_public_output(case_name, build_output)

    _assert_no_forbidden_key_paths(case_name, payload)
    _assert_no_forbidden_public_text(case_name, payload)
