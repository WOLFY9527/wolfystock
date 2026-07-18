# -*- coding: utf-8 -*-
"""Safety tests for the standalone homepage capabilities contract."""

from __future__ import annotations

import json

from api.v1.schemas.homepage_capabilities import HomepageCapabilitiesSnapshot
from src.services.homepage_capabilities_service import (
    HOMEPAGE_CAPABILITIES_CONTRACT_VERSION,
    HOMEPAGE_CAPABILITIES_NO_ADVICE_DISCLOSURE,
    HomepageCapabilitiesService,
)


EXPECTED_SECTION_KEYS = (
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
LEGACY_CAPABILITY_KEYS = (
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
EXPECTED_CAPABILITY_KEYS = (*EXPECTED_SECTION_KEYS, *LEGACY_CAPABILITY_KEYS)
FORBIDDEN_MARKERS = (
    "route",
    "router",
    "endpoint",
    "admin",
    "diagnostic",
    "debug",
    "provider",
    "traceback",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "rawpayload",
    "sessionid",
    "api_key",
    "secret",
    "buy",
    "sell",
    "place order",
    "trade execution",
    "交易指令",
    "交易执行",
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
    "交易建议",
    "投资建议",
)
FORBIDDEN_PUBLIC_COPY = (
    "Market Pulse",
    "Money Flow Proxy",
    "stable",
    "Static metadata only",
    "not personalized financial advice",
)


def _build_payload() -> dict[str, object]:
    return HomepageCapabilitiesService().build_snapshot().model_dump(mode="json")


def test_homepage_capabilities_contract_serializes_stable_version_and_capabilities() -> None:
    payload = _build_payload()

    assert list(payload.keys()) == [
        "schemaVersion",
        "status",
        "sections",
        "capabilities",
        "dataQuality",
        "noAdviceDisclosure",
    ]
    assert payload["schemaVersion"] == HOMEPAGE_CAPABILITIES_CONTRACT_VERSION
    assert payload["status"] == "partial"
    assert [section["key"] for section in payload["sections"]] == list(EXPECTED_SECTION_KEYS)
    assert list(payload["capabilities"].keys()) == list(EXPECTED_CAPABILITY_KEYS)
    assert payload["dataQuality"] == {
        "status": "partial",
        "label": "部分缺失",
        "available": False,
        "description": "首页能力信息已整理，样本、代理观察与暂无证据边界已标记。",
    }
    assert _build_payload() == payload
    assert payload["noAdviceDisclosure"] == HOMEPAGE_CAPABILITIES_NO_ADVICE_DISCLOSURE
    assert HomepageCapabilitiesSnapshot.model_validate(payload).schemaVersion == HOMEPAGE_CAPABILITIES_CONTRACT_VERSION


def test_homepage_capabilities_default_flags_are_bounded() -> None:
    payload = _build_payload()

    assert set(payload["capabilities"].keys()) == set(EXPECTED_CAPABILITY_KEYS)
    assert all(isinstance(value, bool) for value in payload["capabilities"].values())
    assert all(section["supported"] is True for section in payload["sections"])
    assert all(section["status"] in {"partial", "no_evidence"} for section in payload["sections"])
    assert payload["sections"][6]["status"] == "no_evidence"
    assert all(section["status"] == "partial" for index, section in enumerate(payload["sections"]) if index != 6)
    assert payload["dataQuality"]["available"] is False
    assert {payload["status"], payload["dataQuality"]["status"]} <= {
        "ready",
        "partial",
        "no_evidence",
        "unavailable",
    }


def test_homepage_capabilities_response_has_no_internal_diagnostics_or_secrets() -> None:
    serialized = json.dumps(_build_payload(), ensure_ascii=False).lower()

    for marker in FORBIDDEN_MARKERS:
        assert marker.lower() not in serialized


def test_homepage_capabilities_response_has_no_trading_advice_language() -> None:
    serialized = json.dumps(_build_payload(), ensure_ascii=False).lower()

    assert "仅供研究观察" in serialized
    assert "不构成个性化建议" in serialized
    for marker in FORBIDDEN_MARKERS:
        assert marker.lower() not in serialized


def test_homepage_capabilities_response_uses_bounded_public_chinese_copy() -> None:
    serialized = json.dumps(_build_payload(), ensure_ascii=False)

    for marker in FORBIDDEN_PUBLIC_COPY:
        assert marker not in serialized
