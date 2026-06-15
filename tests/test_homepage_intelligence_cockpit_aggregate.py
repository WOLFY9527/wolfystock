# -*- coding: utf-8 -*-
"""Contract tests for the homepage intelligence cockpit aggregate."""

from __future__ import annotations

import json
from typing import Any

from src.services.homepage_intelligence_service import HomepageIntelligenceService


EXPECTED_COCKPIT_SECTION_KEYS = (
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
FORBIDDEN_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "cache",
    "cookie",
    "debug",
    "diagnostic",
    "fallback",
    "provider",
    "raw",
    "secret",
    "sessionid",
    "source_url",
    "sourceurl",
    "token",
    "traceback",
    "url",
)
FORBIDDEN_TEXT_MARKERS = (
    "买入",
    "卖出",
    "下单",
    "立即交易",
    "交易信号",
    "交易指令",
    "目标价",
    "止损",
    "止盈",
    "provider",
    "fallback",
    "diagnostic",
    "debug",
    "raw",
    "traceback",
    "http://",
    "https://",
    "buy now",
    "sell now",
    "place order",
    "target price",
)
SAFE_DISCLOSURE_PHRASES = (
    "不包含交易建议",
    "不包含投资建议",
    "不包含交易指令",
    "不构成投资建议",
    "不构成个性化建议",
    "不构成个性化投资建议",
)


def _walk_key_paths(value: Any, prefix: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    if isinstance(value, dict):
        found: list[tuple[str, ...]] = []
        for key, item in value.items():
            path = (*prefix, str(key))
            found.append(path)
            found.extend(_walk_key_paths(item, path))
        return found
    if isinstance(value, list):
        found = []
        for index, item in enumerate(value):
            found.extend(_walk_key_paths(item, (*prefix, str(index))))
        return found
    return []


def _safe_serialized_text(value: object) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True).lower()
    for phrase in SAFE_DISCLOSURE_PHRASES:
        serialized = serialized.replace(phrase.lower(), "<safe-disclosure>")
    return serialized


def test_homepage_intelligence_bundle_exposes_public_safe_cockpit_aggregate() -> None:
    payload = HomepageIntelligenceService().build_bundle()

    assert {
        "schemaVersion",
        "status",
        "scope",
        "asOf",
        "sampleOnly",
        "capabilities",
        "moduleManifest",
        "sessionStatus",
        "sourceFreshness",
        "demo",
        "noAdviceDisclosure",
    } <= set(payload)
    assert "intelligenceCockpit" in payload

    cockpit = payload["intelligenceCockpit"]
    assert cockpit["schemaVersion"] == "homepage_intelligence_cockpit_v1"
    assert cockpit["status"] == "ready"
    assert cockpit["asOf"] == payload["asOf"]
    assert cockpit["sampleOnly"] is True
    assert cockpit["sectionOrder"] == list(EXPECTED_COCKPIT_SECTION_KEYS)

    sections = cockpit["sections"]
    assert [section["key"] for section in sections] == list(EXPECTED_COCKPIT_SECTION_KEYS)
    assert cockpit["sectionCount"] == len(EXPECTED_COCKPIT_SECTION_KEYS)
    assert len(sections) == len(EXPECTED_COCKPIT_SECTION_KEYS)

    for section in sections:
        assert set(section) == {
            "key",
            "label",
            "status",
            "asOf",
            "summary",
            "dataQuality",
            "evidenceQuality",
            "payload",
        }
        assert section["status"] in {"ready", "partial", "no_evidence", "unavailable"}
        assert section["asOf"]
        assert section["summary"]
        assert isinstance(section["payload"], dict)
        assert section["payload"]["asOf"] == section["asOf"]


def test_homepage_intelligence_cockpit_aggregate_is_deterministic_and_public_safe() -> None:
    first = HomepageIntelligenceService().build_bundle()["intelligenceCockpit"]
    second = HomepageIntelligenceService().build_bundle()["intelligenceCockpit"]

    assert first == second

    leaked_key_paths = [
        ".".join(path)
        for path in _walk_key_paths(first)
        if any(
            fragment in path[-1].replace("-", "").replace("_", "").lower()
            for fragment in FORBIDDEN_KEY_FRAGMENTS
        )
    ]
    assert leaked_key_paths == []

    serialized = _safe_serialized_text(first)
    leaked_text = [marker for marker in FORBIDDEN_TEXT_MARKERS if marker.lower() in serialized]
    assert leaked_text == []
