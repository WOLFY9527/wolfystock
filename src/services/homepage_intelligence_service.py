# -*- coding: utf-8 -*-
"""Build a bounded homepage intelligence metadata and fixture bundle."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.v1.schemas.homepage_intelligence import (
    HOMEPAGE_COCKPIT_MODULES_SCHEMA_VERSION,
    HOMEPAGE_INTELLIGENCE_COCKPIT_SCHEMA_VERSION,
    HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF,
    HOMEPAGE_INTELLIGENCE_DEFAULT_SCENARIO,
    HOMEPAGE_INTELLIGENCE_NO_ADVICE_DISCLOSURE,
    HomepageCockpitModule,
    HomepageCockpitModulesAggregate,
    HomepageIntelligenceCockpitAggregate,
    HomepageIntelligenceCockpitSection,
    HomepageIntelligenceDemoBundle,
    HomepageIntelligenceResponse,
)
from src.services.homepage_after_close_developments_service import (
    HomepageAfterCloseDevelopmentsService,
)
from src.services.homepage_ai_capex_infrastructure_service import (
    HomepageAICapexInfrastructureService,
)
from src.services.homepage_capabilities_service import HomepageCapabilitiesService
from src.services.homepage_cross_asset_indicators_service import HomepageCrossAssetIndicatorsService
from src.services.homepage_daily_market_brief_service import HomepageDailyMarketBriefService
from src.services.homepage_demo_payload_service import (
    DEGRADED_EXAMPLE,
    HAPPY_PATH,
    HomepageDemoPayloadService,
)
from src.services.homepage_driver_chain_service import HomepageDriverChainService
from src.services.homepage_earnings_catalysts_service import HomepageEarningsCatalystsService
from src.services.homepage_event_impact_map_service import HomepageEventImpactMapService
from src.services.homepage_evidence_quality_service import HomepageEvidenceQualityService
from src.services.homepage_geopolitical_commodity_risk_service import (
    HomepageGeopoliticalCommodityRiskService,
)
from src.services.homepage_liquidity_credit_service import HomepageLiquidityCreditService
from src.services.homepage_market_breadth_service import HomepageMarketBreadthService
from src.services.homepage_module_manifest_service import HomepageModuleManifestService
from src.services.homepage_policy_regulation_watch_service import HomepagePolicyRegulationWatchService
from src.services.homepage_pre_session_research_checklist_service import (
    HomepagePreSessionResearchChecklistService,
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
from src.services.homepage_volatility_positioning_service import (
    HomepageVolatilityPositioningService,
)
from src.services.market_session_status_service import MarketSessionStatusService
from src.services.source_freshness_summary_service import build_source_freshness_summary


_SOURCE_FRESHNESS_SAMPLE = {
    "asOf": HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF,
    "message": "固定来源新鲜度样例，仅用于界面状态联调。",
    "sources": [
        {
            "key": "market_fixture",
            "label": "市场样例",
            "category": "market",
            "freshness": "recent",
            "asOf": HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF,
            "publicMessage": "固定市场样例仍适合状态展示。",
        },
        {
            "key": "research_fixture",
            "label": "研究样例",
            "category": "research",
            "freshness": "stale",
            "asOf": HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF,
            "publicMessage": "固定研究样例用于演示谨慎观察状态。",
        },
        {
            "key": "event_fixture",
            "label": "事件样例",
            "category": "event",
            "freshness": "no_evidence",
            "publicMessage": "固定事件样例用于演示暂无证据状态。",
        },
    ],
}

_COCKPIT_SECTION_LABELS = {
    "dailyMarketBrief": "Daily market brief",
    "riskRegime": "Risk regime",
    "crossAssetIndicators": "Cross-asset indicators",
    "eventImpactMap": "Event impact map",
    "driverChain": "Driver chain",
    "themeCapitalFlow": "Theme capital flow",
    "researchPriorities": "Research priorities",
    "evidenceQuality": "Evidence quality",
    "ratesPricing": "Rates pricing",
    "volatilityPositioning": "Volatility positioning",
    "liquidityCredit": "Liquidity credit",
    "marketBreadth": "Market breadth",
    "afterCloseDevelopments": "After-close developments",
    "scenarioWatchlist": "Scenario watchlist",
    "earningsCatalysts": "Earnings catalysts",
    "geopoliticalCommodityRisk": "Geopolitical commodity risk",
    "aiCapexInfrastructure": "AI capex infrastructure",
    "policyRegulationWatch": "Policy regulation watch",
    "styleLeadershipRotation": "Style leadership rotation",
    "preSessionResearchChecklist": "Pre-session research checklist",
}


class HomepageIntelligenceService:
    """Assemble homepage-safe metadata and demo fixtures without runtime coupling."""

    def __init__(self) -> None:
        self._capabilities_service = HomepageCapabilitiesService()
        self._module_manifest_service = HomepageModuleManifestService()
        self._market_session_status_service = MarketSessionStatusService()
        self._demo_payload_service = HomepageDemoPayloadService()
        self._section_layout_service = HomepageSectionLayoutService()
        self._uat_readiness_service = HomepageUatReadinessService()

    def build_bundle(self) -> dict[str, Any]:
        capabilities = self._project_capabilities(self._capabilities_service.build_snapshot())
        module_manifest = self._project_module_manifest(
            self._module_manifest_service.build_manifest(as_of=HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF)
        )
        session_status = self._market_session_status_service.build_status(
            {
                "market": "US",
                "sessionState": "unknown",
                "asOf": HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF,
            }
        ).model_dump(mode="json")
        source_freshness = build_source_freshness_summary(_SOURCE_FRESHNESS_SAMPLE).model_dump(
            mode="json", by_alias=True
        )
        demo_payloads = self._demo_payload_service.build_payloads()
        section_layout = self._project_section_layout(
            self._section_layout_service.build_layout(as_of=HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF)
        )
        uat_readiness = self._project_uat_readiness(
            self._uat_readiness_service.build_checklist(as_of=HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF)
        )
        cockpit_modules = self._build_cockpit_modules()
        intelligence_cockpit = self._build_intelligence_cockpit(cockpit_modules)

        response = HomepageIntelligenceResponse(
            status="ready",
            scope="homepage_ui_uat_metadata",
            asOf=HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF,
            sampleOnly=True,
            capabilities=capabilities,
            moduleManifest=module_manifest,
            sessionStatus=session_status,
            sourceFreshness=source_freshness,
            demo=HomepageIntelligenceDemoBundle(
                defaultScenario=HOMEPAGE_INTELLIGENCE_DEFAULT_SCENARIO,
                scenarios={
                    HAPPY_PATH: deepcopy(demo_payloads[HAPPY_PATH]),
                    DEGRADED_EXAMPLE: deepcopy(demo_payloads[DEGRADED_EXAMPLE]),
                },
            ),
            intelligenceCockpit=intelligence_cockpit,
            sectionLayout=section_layout,
            uatReadiness=uat_readiness,
            cockpitModules=cockpit_modules,
            noAdviceDisclosure=HOMEPAGE_INTELLIGENCE_NO_ADVICE_DISCLOSURE,
        )
        return response.model_dump(mode="json")

    def _build_cockpit_modules(self) -> dict[str, Any]:
        section_payloads = (
            (
                "dailyMarketBrief",
                HomepageDailyMarketBriefService().build_daily_market_brief(
                    as_of=HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF
                ),
            ),
            ("riskRegime", HomepageRiskRegimeService().build_snapshot()),
            ("crossAssetIndicators", HomepageCrossAssetIndicatorsService().build_snapshot()),
            ("eventImpactMap", HomepageEventImpactMapService().build_event_impact_map()),
            ("driverChain", HomepageDriverChainService().build_snapshot()),
            ("themeCapitalFlow", HomepageThemeCapitalFlowService().build_snapshot()),
            ("researchPriorities", HomepageResearchPrioritiesService().build_contract()),
            ("evidenceQuality", HomepageEvidenceQualityService().build_projection()),
            ("ratesPricing", HomepageRatesPricingService().build_snapshot()),
            ("volatilityPositioning", HomepageVolatilityPositioningService().build_snapshot()),
            ("liquidityCredit", HomepageLiquidityCreditService().build_snapshot()),
            ("marketBreadth", HomepageMarketBreadthService().build_snapshot()),
            ("afterCloseDevelopments", HomepageAfterCloseDevelopmentsService().build_snapshot()),
            ("scenarioWatchlist", HomepageScenarioWatchlistService().build_snapshot()),
            ("earningsCatalysts", HomepageEarningsCatalystsService().build_snapshot()),
            (
                "geopoliticalCommodityRisk",
                HomepageGeopoliticalCommodityRiskService().build_snapshot(),
            ),
            ("aiCapexInfrastructure", HomepageAICapexInfrastructureService().build_snapshot()),
            ("policyRegulationWatch", HomepagePolicyRegulationWatchService().build_snapshot()),
            ("styleLeadershipRotation", HomepageStyleLeadershipRotationService().build_snapshot()),
            (
                "preSessionResearchChecklist",
                HomepagePreSessionResearchChecklistService().build_snapshot(),
            ),
        )
        modules = [
            self._project_cockpit_module(key=key, payload=self._json_payload(payload))
            for key, payload in section_payloads
        ]
        aggregate = HomepageCockpitModulesAggregate(
            schemaVersion=HOMEPAGE_COCKPIT_MODULES_SCHEMA_VERSION,
            status="ready",
            asOf=HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF,
            sampleOnly=True,
            moduleCount=len(modules),
            moduleOrder=[module.key for module in modules],
            modules=modules,
            noAdviceDisclosure="仅供首页市场智能观察，不构成个性化建议。",
        )
        return aggregate.model_dump(mode="json")

    def _build_intelligence_cockpit(self, cockpit_modules: dict[str, Any]) -> dict[str, Any]:
        sections = [
            self._project_cockpit_section(module)
            for module in cockpit_modules.get("modules", [])
            if isinstance(module, dict)
        ]
        aggregate = HomepageIntelligenceCockpitAggregate(
            schemaVersion=HOMEPAGE_INTELLIGENCE_COCKPIT_SCHEMA_VERSION,
            status="ready",
            asOf=HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF,
            sampleOnly=True,
            sectionCount=len(sections),
            sectionOrder=[section.key for section in sections],
            sections=sections,
            noAdviceDisclosure="仅供首页市场智能观察，不构成个性化建议。",
        )
        return aggregate.model_dump(mode="json")

    def _project_section_layout(self, payload: dict[str, Any]) -> dict[str, Any]:
        sections: list[dict[str, Any]] = []
        for section in payload.get("sections", []):
            if not isinstance(section, dict):
                continue
            sections.append(
                {
                    "key": str(section.get("key", ""))[:64],
                    "label": str(section.get("label", ""))[:80],
                    "priority": int(section.get("priority", 100)),
                    "region": str(section.get("region") or "secondary")[:32],
                    "density": str(section.get("density") or "standard")[:32],
                    "required": bool(section.get("required", False)),
                    "reviewPoint": self._metadata_text(
                        section.get("reviewPoint"),
                        fallback="复核该首页区块的公开观察边界。",
                        max_length=120,
                    ),
                }
            )
        return {
            "status": self._bounded_status(payload.get("status")),
            "asOf": HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF,
            "sampleOnly": True,
            "sections": sections,
            "dataQuality": self._project_quality(payload.get("dataQuality")),
            "noAdviceDisclosure": "仅供首页区块布局验收观察，不构成个性化建议。",
        }

    def _project_uat_readiness(self, payload: dict[str, Any]) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        for check in payload.get("checks", []):
            if not isinstance(check, dict):
                continue
            checks.append(
                {
                    "key": str(check.get("key", ""))[:64],
                    "label": str(check.get("label", ""))[:80],
                    "status": self._bounded_uat_status(check.get("status")),
                    "publicMessage": self._metadata_text(
                        check.get("publicMessage"),
                        fallback="该验收项需要公开界面复核。",
                        max_length=120,
                    ),
                    "ownerArea": str(check.get("ownerArea") or "qa")[:40],
                    "required": bool(check.get("required", False)),
                }
            )
        data_quality = payload.get("dataQuality") if isinstance(payload.get("dataQuality"), dict) else {}
        return {
            "status": self._bounded_uat_status(payload.get("status")),
            "asOf": HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF,
            "sampleOnly": True,
            "summary": self._metadata_text(
                payload.get("summary"),
                fallback="首页验收准备度仅供人工复核排队。",
                max_length=120,
            ),
            "checks": checks,
            "dataQuality": {
                "status": self._bounded_uat_status(data_quality.get("status")),
                "label": str(data_quality.get("label") or "需复核")[:40],
                "publicMessage": self._metadata_text(
                    data_quality.get("publicMessage"),
                    fallback="静态验收清单仅用于公开界面复核。",
                    max_length=120,
                ),
            },
            "noAdviceDisclosure": "仅供首页视觉验收准备度观察，不构成个性化建议。",
        }

    def _project_cockpit_module(
        self,
        *,
        key: str,
        payload: dict[str, Any],
    ) -> HomepageCockpitModule:
        payload = deepcopy(payload)
        payload.setdefault("asOf", HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF)
        label = _COCKPIT_SECTION_LABELS[key]
        return HomepageCockpitModule(
            key=key,
            label=label,
            status=self._section_status(payload),
            asOf=str(payload["asOf"]),
            summary=self._section_summary(payload, label=label),
            dataQuality=self._project_quality(payload.get("dataQuality")),
            evidenceQuality=self._project_quality(payload.get("evidenceQuality")),
            sampleOnly=True,
            observationOnly=True,
            noLiveAvailabilityClaim=True,
        )

    def _project_cockpit_section(
        self,
        module: dict[str, Any],
    ) -> HomepageIntelligenceCockpitSection:
        snapshot = {
            "asOf": str(module.get("asOf") or HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF),
            "sampleOnly": bool(module.get("sampleOnly", True)),
            "observationOnly": bool(module.get("observationOnly", True)),
            "noLiveAvailabilityClaim": bool(module.get("noLiveAvailabilityClaim", True)),
            "summary": self._metadata_text(
                module.get("summary"),
                fallback="该模块已整理为公开观察摘要。",
                max_length=180,
            ),
        }
        return HomepageIntelligenceCockpitSection(
            key=str(module.get("key", ""))[:64],
            label=str(module.get("label", ""))[:120],
            status=self._bounded_status(module.get("status")),
            asOf=snapshot["asOf"],
            summary=snapshot["summary"],
            dataQuality=self._project_quality(module.get("dataQuality")),
            evidenceQuality=self._project_quality(module.get("evidenceQuality")),
            payload=snapshot,
        )

    def _json_payload(self, value: Any) -> dict[str, Any]:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if isinstance(value, dict):
            return deepcopy(value)
        return dict(value)

    def _section_status(self, payload: dict[str, Any]) -> str:
        data_quality = payload.get("dataQuality") if isinstance(payload.get("dataQuality"), dict) else {}
        evidence_quality = (
            payload.get("evidenceQuality") if isinstance(payload.get("evidenceQuality"), dict) else {}
        )
        return self._bounded_status(
            payload.get("status")
            or data_quality.get("state")
            or data_quality.get("status")
            or evidence_quality.get("state")
            or evidence_quality.get("status")
        )

    def _section_summary(self, payload: dict[str, Any], *, label: str) -> str:
        for key in (
            "headline",
            "summary",
            "marketNarrative",
            "implication",
            "monitorNext",
            "ratePathSummary",
            "riskAssetImplication",
            "overnightContext",
            "leadershipRegime",
            "capexSignal",
        ):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return self._metadata_text(
                    value,
                    fallback=f"{label} 已整理为公开观察项。",
                    max_length=180,
                )
        return f"{label} 已整理为公开观察项。"

    def _project_capabilities(self, snapshot: Any) -> dict[str, Any]:
        payload = snapshot.model_dump(mode="json") if hasattr(snapshot, "model_dump") else dict(snapshot)
        return {
            "schemaVersion": payload.get("schemaVersion", "homepage_capabilities_v1"),
            "status": payload.get("status", "ready"),
            "sections": [
                {
                    "key": str(section.get("key", ""))[:40],
                    "label": str(section.get("label", ""))[:80],
                    "supported": bool(section.get("supported", False)),
                    "status": section.get("status", "no_evidence"),
                    "description": self._metadata_text(
                        section.get("description"),
                        fallback="提供首页能力状态观察。",
                        max_length=120,
                    ),
                }
                for section in payload.get("sections", [])
                if isinstance(section, dict)
            ],
            "capabilities": {
                key: bool(value)
                for key, value in dict(payload.get("capabilities", {})).items()
                if key
                in {
                    "marketPulse",
                    "moneyFlowProxy",
                    "eventRadar",
                    "personalSummary",
                    "researchQueue",
                    "publicDataQuality",
                    "sessionStatus",
                    "eventWindows",
                    "noAdviceBoundary",
                }
            },
            "dataQuality": {
                "status": dict(payload.get("dataQuality", {})).get("status", "ready"),
                "label": dict(payload.get("dataQuality", {})).get("label", "正常"),
                "available": bool(dict(payload.get("dataQuality", {})).get("available", True)),
                "description": self._metadata_text(
                    dict(payload.get("dataQuality", {})).get("description"),
                    fallback="首页能力状态已整理为公开元数据。",
                    max_length=120,
                ),
            },
            "noAdviceDisclosure": "仅供首页能力状态观察，不构成个性化建议。",
        }

    def _project_module_manifest(self, payload: dict[str, Any]) -> dict[str, Any]:
        modules: list[dict[str, Any]] = []
        for module in payload.get("modules", []):
            if not isinstance(module, dict):
                continue
            modules.append(
                {
                    "key": str(module.get("key", ""))[:48],
                    "label": str(module.get("label", ""))[:80],
                    "category": module.get("category", "overview"),
                    "availability": self._bounded_availability(module.get("availability")),
                    "integrationStatus": self._bounded_integration(module.get("integrationStatus")),
                    "publicStatus": module.get("publicStatus", "public"),
                    "reviewPoint": self._metadata_text(
                        module.get("reviewPoint"),
                        fallback="复核该模块的公开展示边界。",
                        max_length=120,
                    ),
                    "dataQuality": self._project_quality(module.get("dataQuality")),
                }
            )

        return {
            "status": self._bounded_status(payload.get("status")),
            "asOf": HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF,
            "modules": modules,
            "dataQuality": self._project_quality(payload.get("dataQuality")),
            "noAdviceDisclosure": "仅供模块可用性与接入准备度观察，不构成个性化建议。",
        }

    def _project_quality(self, value: Any) -> dict[str, str]:
        payload = value if isinstance(value, dict) else {}
        return {
            "state": self._bounded_status(payload.get("state") or payload.get("status")),
            "label": str(payload.get("label") or "正常")[:40],
            "summary": self._metadata_text(
                payload.get("summary") or payload.get("description"),
                fallback="公开状态字段已整理为安全元数据。",
                max_length=120,
            ),
        }

    def _bounded_status(self, value: Any) -> str:
        text = str(value or "ready")
        return text if text in {"ready", "partial", "no_evidence", "unavailable"} else "partial"

    def _bounded_availability(self, value: Any) -> str:
        text = str(value or "ready")
        return text if text in {"ready", "partial", "no_evidence", "unavailable"} else "partial"

    def _bounded_integration(self, value: Any) -> str:
        text = str(value or "standalone")
        return text if text in {"standalone", "wired", "pending", "unavailable"} else "pending"

    def _bounded_uat_status(self, value: Any) -> str:
        text = str(value or "review")
        return text if text in {"pass", "review", "blocked", "no_evidence"} else "review"

    def _metadata_text(self, value: Any, *, fallback: str, max_length: int) -> str:
        text = str(value or "").strip()
        compact = text.lower().replace("_", "").replace(" ", "").replace("-", "")
        if not text or any(
            marker in compact
            for marker in (
                "交易指令",
                "交易信号",
                "交易建议",
                "投资建议",
                "买入",
                "卖出",
                "下单",
                "targetprice",
                "placorder",
                "placeorder",
                "buynow",
                "sellnow",
                "recommendation",
                "investmentadvice",
                "tradingadvice",
                "livedata",
                "livequote",
                "livemarket",
                "realtime",
                "real-time",
                "实时行情",
                "实时数据",
                "内部诊断",
                "http://",
                "https://",
                "provider",
                "raw",
                "traceback",
                "reasoncode",
                "trustlevel",
                "sourcetype",
                "fallback",
                "scaffold",
            )
        ):
            return fallback
        return text[:max_length]
