# -*- coding: utf-8 -*-
"""Focused tests for the standalone homepage research priorities contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from src.services.homepage_research_priorities_service import (
    EXPECTED_HOMEPAGE_RESEARCH_PRIORITY_LEVELS,
    HomepageResearchPrioritiesService,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = REPO_ROOT / "src" / "services" / "homepage_research_priorities_service.py"

EXPECTED_TOP_LEVEL_KEYS = {
    "schemaVersion",
    "asOf",
    "researchPriorities",
    "evidenceQuality",
    "dataQuality",
    "noAdviceDisclosure",
}
EXPECTED_PRIORITY_KEYS = {
    "priorityLevel",
    "theme",
    "whyNow",
    "evidenceStatus",
    "supportingSignals",
    "missingConfirmation",
    "relatedEvents",
    "relatedMacroDrivers",
    "reviewModule",
}
ALLOWED_PUBLIC_PHRASES = (
    "今日重点观察",
    "优先复核",
    "研究队列",
    "需要确认",
    "证据增强",
    "证据不足",
    "适合继续观察",
    "观察主题",
    "复核方向",
)
FORBIDDEN_ADVICE_TERMS = (
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
    "buy",
    "sell",
    "add position",
    "reduce position",
    "clear position",
    "stop-loss",
    "stop loss",
    "take-profit",
    "take profit",
    "target price",
    "broker",
    "order",
    "execution",
)
FORBIDDEN_INTERNAL_TERMS = (
    "fallback",
    "provider",
    "diagnostic",
    "debug",
    "traceback",
    "raw",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "cache",
    "runtime",
    "token",
    "secret",
    "cookie",
    "session",
    "api_key",
    "apikey",
    "http://",
    "https://",
    "/users/",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "requests",
    "httpx",
    "aiohttp",
    "urllib",
    "data_provider",
    "src.services.market_cache",
    "src.services.homepage_intelligence_service",
    "src.services.dashboard_overview_service",
    "src.auth",
)


def _serialized_values(value: object) -> str:
    if isinstance(value, dict):
        return " ".join(_serialized_values(item) for item in value.values()).lower()
    if isinstance(value, list):
        return " ".join(_serialized_values(item) for item in value).lower()
    return json.dumps(value, ensure_ascii=False, sort_keys=True).lower()


def _service_imports() -> set[str]:
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"), filename=str(SERVICE_PATH))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def test_build_contract_returns_stable_research_priorities_shape() -> None:
    payload = HomepageResearchPrioritiesService().build_contract().model_dump(mode="json")

    assert set(payload) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["schemaVersion"] == "homepage_research_priorities_v1"
    assert payload["asOf"] == "2026-06-15T09:30:00Z"
    assert payload["noAdviceDisclosure"] == "仅供今日研究观察，不替代自主判断。"
    assert payload["evidenceQuality"] == {
        "status": "证据增强",
        "summary": "今日重点观察已按公开研究线索整理，仍需复核方向确认。",
    }
    assert payload["dataQuality"] == {
        "status": "需要确认",
        "summary": "使用固定研究支持样例，不包含来源细节或后台字段。",
    }

    assert [item["priorityLevel"] for item in payload["researchPriorities"]] == list(
        EXPECTED_HOMEPAGE_RESEARCH_PRIORITY_LEVELS
    )
    for item in payload["researchPriorities"]:
        assert set(item) == EXPECTED_PRIORITY_KEYS
        assert item["theme"].startswith("观察主题：")
        assert item["reviewModule"].startswith("复核方向：")
        assert item["whyNow"]
        assert item["supportingSignals"]
        assert item["missingConfirmation"]


def test_contract_uses_allowed_observation_language_without_advice_or_internal_leakage() -> None:
    payload = HomepageResearchPrioritiesService().build_contract().model_dump(mode="json")
    serialized_values = _serialized_values(payload)

    assert any(phrase in serialized_values for phrase in ALLOWED_PUBLIC_PHRASES)
    assert all(item["priorityLevel"] in ALLOWED_PUBLIC_PHRASES for item in payload["researchPriorities"])
    assert all(item["evidenceStatus"] in ALLOWED_PUBLIC_PHRASES for item in payload["researchPriorities"])

    advice_hits = [term for term in FORBIDDEN_ADVICE_TERMS if term.lower() in serialized_values]
    internal_hits = [term for term in FORBIDDEN_INTERNAL_TERMS if term.lower() in serialized_values]
    assert advice_hits == []
    assert internal_hits == []


def test_schema_rejects_unsafe_priority_copy() -> None:
    from api.v1.schemas.homepage_research_priorities import HomepageResearchPriority

    with pytest.raises(ValueError):
        HomepageResearchPriority(
            priorityLevel="今日重点观察",
            theme="观察主题：建议买入",
            whyNow="目标价上调，需要交易执行。",
            evidenceStatus="证据增强",
            supportingSignals=["provider fallback raw payload"],
            missingConfirmation=["止损条件"],
            relatedEvents=["http://internal.example"],
            relatedMacroDrivers=["debug trace"],
            reviewModule="复核方向：交易指令",
        )


def test_service_is_standalone_and_has_no_provider_or_network_imports() -> None:
    imported_modules = _service_imports()

    assert imported_modules == {
        "__future__",
        "api.v1.schemas.homepage_research_priorities",
    }
    for module in imported_modules:
        assert not module.startswith(FORBIDDEN_IMPORT_PREFIXES)
