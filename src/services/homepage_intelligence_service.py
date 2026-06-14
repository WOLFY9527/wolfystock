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

    def _metadata_text(self, value: Any, *, fallback: str, max_length: int) -> str:
        text = str(value or "").strip()
        compact = text.lower().replace("_", "").replace(" ", "").replace("-", "")
        if not text or any(
            marker in compact
            for marker in (
                "交易指令",
                "交易信号",
                "买入",
                "卖出",
                "下单",
                "targetprice",
                "placorder",
                "placeorder",
                "buynow",
                "sellnow",
                "livedata",
                "realtime",
                "real-time",
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
