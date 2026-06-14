# -*- coding: utf-8 -*-
"""Focused tests for the standalone homepage section layout contract."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from src.services.homepage_section_layout_service import HomepageSectionLayoutService


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "api/v1/schemas/homepage_section_layout.py"
EXPECTED_SECTION_KEYS = [
    "market_pulse",
    "market_brief",
    "money_flow",
    "research_queue",
    "event_radar",
    "sector_theme_strength",
    "portfolio_watchlist",
    "data_quality",
    "homepage_intelligence",
]
ALLOWED_REGIONS = {"top_strip", "main_left", "main_center", "main_right", "secondary", "utility"}
ALLOWED_DENSITIES = {"compact", "standard", "expanded"}


def _build_layout_payload() -> dict[str, object]:
    service = HomepageSectionLayoutService()
    return service.build_layout(as_of="2026-06-14T09:30:00Z")


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


def test_default_layout_serializes_stable_frontend_uat_contract() -> None:
    payload = _build_layout_payload()

    assert list(payload) == ["status", "asOf", "sections", "noAdviceDisclosure", "dataQuality"]
    assert payload["status"] == "ready"
    assert payload["asOf"] == "2026-06-14T09:30:00Z"
    assert payload["noAdviceDisclosure"] == "仅用于首页区块布局验收参考，不构成投资建议或交易指令。"

    sections = payload["sections"]
    assert isinstance(sections, list)
    assert [section["key"] for section in sections] == EXPECTED_SECTION_KEYS
    assert [section["priority"] for section in sections] == list(range(1, 10))

    data_quality = payload["dataQuality"]
    assert data_quality == {
        "state": "ready",
        "label": "布局合同已就绪",
        "summary": "当前合同仅描述首页区块顺序、密度与复核点，不包含实时行情、交易建议或内部诊断。",
    }


def test_layout_sections_use_public_chinese_labels_and_bounded_taxonomy() -> None:
    payload = _build_layout_payload()

    for section in payload["sections"]:
        assert section["label"]
        assert not section["label"].isascii()
        assert section["region"] in ALLOWED_REGIONS
        assert section["density"] in ALLOWED_DENSITIES
        assert isinstance(section["required"], bool)
        assert section["reviewPoint"]
        assert "复核" in section["reviewPoint"]

    by_key = {section["key"]: section for section in payload["sections"]}
    assert by_key["market_pulse"]["region"] == "top_strip"
    assert by_key["market_brief"]["region"] == "main_center"
    assert by_key["money_flow"]["region"] == "main_left"
    assert by_key["research_queue"]["region"] == "main_right"
    assert by_key["data_quality"]["density"] == "compact"
    assert by_key["homepage_intelligence"]["required"] is False


def test_schema_file_defines_standalone_bounded_taxonomy() -> None:
    schema = _load_schema_module()

    assert schema.ALLOWED_HOMEPAGE_SECTION_REGIONS == ALLOWED_REGIONS
    assert schema.ALLOWED_HOMEPAGE_SECTION_DENSITIES == ALLOWED_DENSITIES
    assert schema.ALLOWED_HOMEPAGE_SECTION_LAYOUT_STATUSES == {
        "ready",
        "partial",
        "no_evidence",
        "unavailable",
    }

    item = schema.HomepageSectionLayoutItem(
        key="market_pulse",
        label="市场脉搏",
        priority=1,
        region="top_strip",
        density="compact",
        required=True,
        reviewPoint="复核首页顶部市场观察区块。",
    )
    assert item.to_dict()["key"] == "market_pulse"


def test_layout_is_not_presented_as_trading_advice() -> None:
    dumped = _dump_layout(_build_layout_payload()).lower()
    for forbidden in [
        "买入",
        "卖出",
        "下单",
        "交易信号",
        "trading signal",
        "buy now",
        "sell now",
        "target price",
        "止损",
        "止盈",
    ]:
        assert forbidden.lower() not in dumped


def test_layout_does_not_leak_internal_diagnostics_or_secrets() -> None:
    dumped = _dump_layout(_build_layout_payload()).lower()
    for forbidden in [
        "traceback",
        "provider",
        "token",
        "session",
        "secret",
        "apiKey",
        "reasonCode",
        "trustLevel",
        "sourceType",
        "raw",
        "debug",
        "internal.example",
        "cookie",
        "/tmp/",
    ]:
        assert forbidden.lower() not in dumped


def test_layout_avoids_navigation_or_launcher_semantics() -> None:
    dumped = _dump_layout(_build_layout_payload()).lower()
    for forbidden in [
        "打开",
        "进入",
        "跳转",
        "导航",
        "入口",
        "launch",
        "launcher",
        "navigate",
        "open module",
    ]:
        assert forbidden.lower() not in dumped
