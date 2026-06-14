# -*- coding: utf-8 -*-
"""Build a bounded homepage intelligence metadata and fixture bundle."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.v1.schemas.homepage_intelligence import (
    HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF,
    HOMEPAGE_INTELLIGENCE_DEFAULT_SCENARIO,
    HOMEPAGE_INTELLIGENCE_NO_ADVICE_DISCLOSURE,
    HomepageIntelligenceDemoBundle,
    HomepageIntelligenceResponse,
)
from src.services.homepage_capabilities_service import HomepageCapabilitiesService
from src.services.homepage_demo_payload_service import (
    DEGRADED_EXAMPLE,
    HAPPY_PATH,
    HomepageDemoPayloadService,
)
from src.services.homepage_module_manifest_service import HomepageModuleManifestService
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


class HomepageIntelligenceService:
    """Assemble homepage-safe metadata and demo fixtures without runtime coupling."""

    def __init__(self) -> None:
        self._capabilities_service = HomepageCapabilitiesService()
        self._module_manifest_service = HomepageModuleManifestService()
        self._market_session_status_service = MarketSessionStatusService()
        self._demo_payload_service = HomepageDemoPayloadService()

    def build_bundle(self) -> dict[str, Any]:
        capabilities = self._capabilities_service.build_snapshot()
        module_manifest = self._module_manifest_service.build_manifest(
            as_of=HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF
        )
        module_manifest["noAdviceDisclosure"] = "仅供模块可用性与接入准备度观察，不构成投资建议。"
        session_status = self._market_session_status_service.build_status(
            {
                "market": "US",
                "sessionState": "unknown",
                "asOf": HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF,
            }
        )
        source_freshness = build_source_freshness_summary(_SOURCE_FRESHNESS_SAMPLE)
        demo_payloads = self._demo_payload_service.build_payloads()

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
            noAdviceDisclosure=HOMEPAGE_INTELLIGENCE_NO_ADVICE_DISCLOSURE,
        )
        return response.model_dump(mode="json")
