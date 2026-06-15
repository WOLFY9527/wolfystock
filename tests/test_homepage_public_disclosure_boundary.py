# -*- coding: utf-8 -*-
"""Focused disclosure-boundary guard for homepage public cockpit outputs."""

from __future__ import annotations

from collections.abc import Mapping
import json
import re

from src.services.homepage_intelligence_service import HomepageIntelligenceService


DISCLOSURE_KEYS = {"demoDisclosure", "noAdviceDisclosure", "no_advice_disclosure"}
SAFE_NO_ADVICE_BOUNDARY_PHRASES = (
    "不包含交易建议",
    "不包含投资建议",
    "不包含交易指令",
    "不提供交易判断",
    "不构成交易指令",
    "不构成投资建议",
    "不构成个性化建议",
    "不构成个性化投资建议",
    "不构成个性化决策依据",
    "不作为任何个性化决策或执行依据",
)
FORBIDDEN_DIRECT_ACTION_TERMS = (
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "清仓",
    "下单",
    "立即交易",
    "立即买入",
    "止损",
    "止盈",
    "目标价",
    "收益预测",
    "AI推荐",
    "智能选股",
)
FORBIDDEN_DIRECT_ACTION_PATTERNS = (
    re.compile(r"\bbuy(?: now)?\b", re.IGNORECASE),
    re.compile(r"\bsell(?: now)?\b", re.IGNORECASE),
    re.compile(r"\badd position\b", re.IGNORECASE),
    re.compile(r"\breduce position\b", re.IGNORECASE),
    re.compile(r"\bplace order\b", re.IGNORECASE),
    re.compile(r"\bsubmit order\b", re.IGNORECASE),
    re.compile(r"\btrade execution\b", re.IGNORECASE),
    re.compile(r"\btrading advice\b", re.IGNORECASE),
    re.compile(r"\binvestment advice\b", re.IGNORECASE),
    re.compile(r"\bfinancial advice\b", re.IGNORECASE),
    re.compile(r"\btarget price\b", re.IGNORECASE),
    re.compile(r"\bstop[\s-]?loss\b", re.IGNORECASE),
    re.compile(r"\btake[\s-]?profit\b", re.IGNORECASE),
    re.compile(r"\bexecution ready\b", re.IGNORECASE),
)


def _build_bundle() -> dict[str, object]:
    payload = HomepageIntelligenceService().build_bundle()
    assert isinstance(payload, dict)
    return payload


def _collect_disclosures(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in DISCLOSURE_KEYS and isinstance(item, str):
                found.append(item)
            found.extend(_collect_disclosures(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_collect_disclosures(item))
    return found


def _scrub_disclosures(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): "<disclosure>" if key in DISCLOSURE_KEYS else _scrub_disclosures(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_scrub_disclosures(item) for item in value]
    return value


def _normalize_allowed_boundary_copy(serialized: str) -> str:
    normalized = serialized
    for phrase in SAFE_NO_ADVICE_BOUNDARY_PHRASES:
        normalized = normalized.replace(phrase, "<safe-boundary>")
    return normalized


def _find_direct_action_hits(serialized: str) -> list[str]:
    hits = [term for term in FORBIDDEN_DIRECT_ACTION_TERMS if term in serialized]
    for pattern in FORBIDDEN_DIRECT_ACTION_PATTERNS:
        match = pattern.search(serialized)
        if match is not None:
            hits.append(match.group(0))
    return sorted(set(hits))


def _collect_module_text(payload: dict[str, object]) -> str:
    cockpit_payload = {
        "cockpitModules": payload["cockpitModules"],
        "intelligenceCockpit": payload["intelligenceCockpit"],
        "sectionLayout": payload["sectionLayout"],
        "uatReadiness": payload["uatReadiness"],
    }
    scrubbed = _scrub_disclosures(cockpit_payload)
    return json.dumps(scrubbed, ensure_ascii=False, sort_keys=True)


def test_homepage_intelligence_bundle_keeps_no_advice_copy_in_explicit_boundary_fields() -> None:
    payload = _build_bundle()

    disclosures = _collect_disclosures(payload)
    assert disclosures

    serialized = _normalize_allowed_boundary_copy(
        json.dumps(disclosures, ensure_ascii=False, sort_keys=True)
    )

    assert "<safe-boundary>" in serialized
    assert _find_direct_action_hits(serialized) == []


def test_homepage_intelligence_cockpit_non_disclosure_content_excludes_boundary_and_action_copy() -> None:
    payload = _build_bundle()

    serialized = _collect_module_text(payload)

    assert _find_direct_action_hits(serialized) == []
    assert all(phrase not in serialized for phrase in SAFE_NO_ADVICE_BOUNDARY_PHRASES)
