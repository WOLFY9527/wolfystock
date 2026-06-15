# -*- coding: utf-8 -*-
"""Cockpit workflow tests for the standalone homepage section layout contract."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from src.services.homepage_section_layout_service import HomepageSectionLayoutService


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "api/v1/schemas/homepage_section_layout.py"

EXPECTED_SECTION_GROUPS = [
    "dailyBrief",
    "marketPulse",
    "riskAndPricing",
    "crossAsset",
    "liquidityAndBreadth",
    "eventsAndCatalysts",
    "themesAndLeadership",
    "policyAndMacro",
    "researchQueue",
    "evidenceAndReadiness",
]
EXPECTED_MODULES_BY_GROUP = {
    "dailyBrief": ["daily_market_brief", "after_close_developments"],
    "marketPulse": ["market_breadth"],
    "riskAndPricing": ["risk_regime", "rates_pricing", "volatility_positioning"],
    "crossAsset": ["cross_asset_indicators"],
    "liquidityAndBreadth": ["liquidity_credit"],
    "eventsAndCatalysts": [
        "event_impact_map",
        "earnings_catalysts",
        "geopolitical_commodity_risk",
    ],
    "themesAndLeadership": [
        "theme_capital_flow",
        "style_leadership_rotation",
        "ai_capex_infrastructure",
    ],
    "policyAndMacro": ["policy_regulation_watch", "scenario_watchlist", "driver_chain"],
    "researchQueue": ["research_priorities", "pre_session_research_checklist"],
    "evidenceAndReadiness": ["evidence_quality"],
}
EXPECTED_MODULE_KEYS = [
    "daily_market_brief",
    "after_close_developments",
    "market_breadth",
    "risk_regime",
    "rates_pricing",
    "volatility_positioning",
    "cross_asset_indicators",
    "liquidity_credit",
    "event_impact_map",
    "earnings_catalysts",
    "geopolitical_commodity_risk",
    "theme_capital_flow",
    "style_leadership_rotation",
    "ai_capex_infrastructure",
    "policy_regulation_watch",
    "scenario_watchlist",
    "driver_chain",
    "research_priorities",
    "pre_session_research_checklist",
    "evidence_quality",
]
ALLOWED_REGIONS = {"top_strip", "main_left", "main_center", "main_right", "secondary", "utility"}
ALLOWED_DENSITIES = {"compact", "standard", "expanded"}


def _build_layout_payload() -> dict[str, object]:
    service = HomepageSectionLayoutService()
    return service.build_layout(as_of="2026-06-15T09:30:00Z")


def _dump_layout(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _load_schema_module():
    spec = importlib.util.spec_from_file_location("homepage_section_layout_schema", SCHEMA_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_cockpit_layout_groups_modules_into_market_workflow() -> None:
    payload = _build_layout_payload()

    assert list(payload) == ["status", "asOf", "sections", "noAdviceDisclosure", "dataQuality"]
    assert payload["status"] == "ready"
    assert payload["asOf"] == "2026-06-15T09:30:00Z"
    assert payload["noAdviceDisclosure"] == "仅用于市场研究编排与证据复核，不作为任何执行依据。"

    sections = payload["sections"]
    assert isinstance(sections, list)
    assert [section["key"] for section in sections] == EXPECTED_SECTION_GROUPS
    assert [section["priority"] for section in sections] == list(range(1, 11))

    modules_by_group = {
        section["key"]: [module["key"] for module in section["modules"]]
        for section in sections
    }
    assert modules_by_group == EXPECTED_MODULES_BY_GROUP
    flattened_module_keys = [
        module["key"]
        for section in sections
        for module in section["modules"]
    ]
    assert flattened_module_keys == EXPECTED_MODULE_KEYS
    assert len(flattened_module_keys) == len(set(flattened_module_keys))
    assert flattened_module_keys.count("driver_chain") == 1


def test_cockpit_layout_uses_public_research_labels_and_bounded_taxonomy() -> None:
    payload = _build_layout_payload()

    for section in payload["sections"]:
        assert section["label"]
        assert section["region"] in ALLOWED_REGIONS
        assert section["density"] in ALLOWED_DENSITIES
        assert isinstance(section["required"], bool)
        assert section["reviewPoint"]
        assert "复核" in section["reviewPoint"]
        assert section["modules"]

        for index, module in enumerate(section["modules"], start=1):
            assert module["priority"] == index
            assert module["label"]
            assert isinstance(module["required"], bool)
            assert module["reviewPoint"]
            assert "复核" in module["reviewPoint"]

    data_quality = payload["dataQuality"]
    assert data_quality == {
        "state": "ready",
        "label": "布局合同已就绪",
        "summary": "当前合同仅描述驾驶舱研究工作流顺序、密度与复核点，不包含实时行情、操作结论或数据质量核查注记。",
    }


def test_schema_defines_required_cockpit_group_and_module_taxonomy() -> None:
    schema = _load_schema_module()

    assert schema.ALLOWED_HOMEPAGE_SECTION_GROUPS == set(EXPECTED_SECTION_GROUPS)
    assert schema.ALLOWED_HOMEPAGE_SECTION_MODULES == set(EXPECTED_MODULE_KEYS)
    assert schema.ALLOWED_HOMEPAGE_SECTION_REGIONS == ALLOWED_REGIONS
    assert schema.ALLOWED_HOMEPAGE_SECTION_DENSITIES == ALLOWED_DENSITIES

    module = schema.HomepageSectionLayoutModule(
        key="pre_session_research_checklist",
        label="盘前研究清单",
        priority=1,
        required=True,
        reviewPoint="复核盘前问题是否保持研究口径。",
    )
    item = schema.HomepageSectionLayoutItem(
        key="researchQueue",
        label="研究队列",
        priority=9,
        region="main_right",
        density="standard",
        required=True,
        reviewPoint="复核研究队列是否聚焦待确认问题。",
        modules=[module],
    )
    assert item.to_dict()["modules"][0]["key"] == "pre_session_research_checklist"


def test_cockpit_layout_is_not_presented_as_trading_instructions() -> None:
    dumped = _dump_layout(_build_layout_payload()).lower()
    for forbidden in [
        "买入",
        "卖出",
        "加仓",
        "减仓",
        "清仓",
        "下单",
        "交易信号",
        "交易指令",
        "交易建议",
        "trading signal",
        "trading instruction",
        "buy now",
        "sell now",
        "target price",
        "止损",
        "止盈",
        "目标价",
        "收益预测",
        "ai recommends",
    ]:
        assert forbidden.lower() not in dumped

def test_cockpit_layout_does_not_leak_internal_provider_cache_or_secret_details() -> None:
    dumped = _dump_layout(_build_layout_payload()).lower()
    for forbidden in [
        "traceback",
        "provider",
        "cache",
        "fallback",
        "token",
        "sessionid",
        "session token",
        "secret",
        "apikey",
        "reasoncode",
        "trustlevel",
        "sourcetype",
        "raw",
        "debug",
        "internal.example",
        "cookie",
        "/tmp/",
    ]:
        assert forbidden.lower() not in dumped


def test_cockpit_layout_public_copy_does_not_include_internal_diagnostics_marker() -> None:
    dumped = _dump_layout(_build_layout_payload())

    assert "内部诊断" not in dumped
