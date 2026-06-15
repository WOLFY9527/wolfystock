# -*- coding: utf-8 -*-
"""Safety tests for the standalone homepage event impact map contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.v1.schemas.homepage_event_impact_map import (
    HOMEPAGE_EVENT_IMPACT_MAP_DEFAULT_AS_OF,
    HOMEPAGE_EVENT_IMPACT_MAP_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_EVENT_IMPACT_MAP_SCHEMA_VERSION,
    HomepageEventImpactMapResponse,
)
from src.services.homepage_event_impact_map_service import HomepageEventImpactMapService


EXPECTED_TOP_LEVEL_KEYS = [
    "schemaVersion",
    "asOf",
    "eventWindow",
    "events",
    "affectedAssets",
    "affectedSectors",
    "affectedThemes",
    "implication",
    "confidence",
    "evidenceQuality",
    "monitorNext",
    "relatedMacroVariables",
    "relatedResearchAreas",
    "dataQuality",
    "noAdviceDisclosure",
]
EXPECTED_EVENT_KEYS = {
    "fed_speech_rates_repricing",
    "inflation_jobs_print",
    "treasury_auction",
    "ai_capex_update",
    "semiconductor_supply_chain",
    "oil_inventory_geopolitical_premium",
    "hormuz_strait_path",
    "china_policy_event",
    "major_earnings_catalyst",
}
FORBIDDEN_MARKERS = (
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
    "broker",
    "order",
    "execution",
    "target price",
    "stop loss",
    "take profit",
    "place order",
    "submit order",
    "trading advice",
    "investment advice",
    "financial advice",
    "guaranteed",
    "position sizing",
    "provider",
    "internal",
    "diagnostic",
    "debug",
    "traceback",
    "fallback",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "raw",
    "http://",
    "https://",
    "/users/",
    "/tmp/",
    "api_key",
    "secret",
    "token",
)
FORBIDDEN_NEWS_FEED_FIELDS = {
    "url",
    "source",
    "provider",
    "headline",
    "publishedAt",
    "rawNews",
    "newsUrl",
}
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "src.providers",
    "aiohttp",
    "httpx",
    "requests",
    "urllib",
    "urllib3",
    "api.deps",
    "api.middlewares.auth",
    "src.auth",
    "src.auth_context",
    "src.admin_rbac",
    "src.services.homepage_intelligence_service",
    "src.services.dashboard_overview_service",
)
REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_payload() -> dict[str, object]:
    return HomepageEventImpactMapService().build_event_impact_map()


def test_event_impact_map_has_stable_top_level_shape() -> None:
    payload = _build_payload()

    assert list(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["schemaVersion"] == HOMEPAGE_EVENT_IMPACT_MAP_SCHEMA_VERSION
    assert payload["asOf"] == HOMEPAGE_EVENT_IMPACT_MAP_DEFAULT_AS_OF
    assert payload["noAdviceDisclosure"] == HOMEPAGE_EVENT_IMPACT_MAP_NO_ADVICE_DISCLOSURE
    assert HomepageEventImpactMapResponse.model_validate(payload).schemaVersion == (
        HOMEPAGE_EVENT_IMPACT_MAP_SCHEMA_VERSION
    )


def test_event_impact_map_is_deterministic() -> None:
    first = _build_payload()
    second = _build_payload()

    assert first == second
    assert json.dumps(first, ensure_ascii=False, sort_keys=True) == json.dumps(
        second,
        ensure_ascii=False,
        sort_keys=True,
    )


def test_event_impact_map_covers_required_event_examples() -> None:
    payload = _build_payload()
    events = payload["events"]

    assert {event["key"] for event in events} == EXPECTED_EVENT_KEYS
    assert len(events) == 9
    for event in events:
        assert event["observation"]
        assert event["affectedAssets"]
        assert event["affectedSectors"]
        assert event["affectedThemes"]
        assert event["implication"]
        assert event["monitorNext"]
        assert event["confidence"] in {"medium", "needs_confirmation", "scenario"}
        assert event["evidenceQuality"] in {"placeholder", "needs_confirmation", "scenario"}


def test_event_impact_map_is_impact_map_not_generic_news_feed() -> None:
    payload = _build_payload()

    serialized = json.dumps(payload, ensure_ascii=False)
    for forbidden_field in FORBIDDEN_NEWS_FEED_FIELDS:
        assert f'"{forbidden_field}"' not in serialized

    assert payload["affectedAssets"]
    assert payload["affectedSectors"]
    assert payload["affectedThemes"]
    assert payload["relatedMacroVariables"]
    assert payload["relatedResearchAreas"]
    assert payload["dataQuality"]["status"] == "placeholder"


def test_event_impact_map_excludes_advice_execution_diagnostics_and_urls() -> None:
    serialized = json.dumps(_build_payload(), ensure_ascii=False).lower()

    leaked = [marker for marker in FORBIDDEN_MARKERS if marker.lower() in serialized]

    assert leaked == []


def test_schema_rejects_forbidden_public_text() -> None:
    payload = _build_payload()
    payload["implication"] = "debug provider raw payload"

    with pytest.raises(ValidationError):
        HomepageEventImpactMapResponse.model_validate(payload)


def test_service_has_no_live_provider_http_or_protected_runtime_imports() -> None:
    service_path = REPO_ROOT / "src" / "services" / "homepage_event_impact_map_service.py"
    tree = ast.parse(service_path.read_text(encoding="utf-8"), filename=str(service_path))
    imported_modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
            continue
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported_modules.add(node.module)
            imported_modules.update(
                f"{node.module}.{alias.name}" for alias in node.names if alias.name != "*"
            )

    violations = sorted(
        module
        for module in imported_modules
        if any(
            module == prefix or module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_IMPORT_PREFIXES
        )
    )
    assert violations == []
