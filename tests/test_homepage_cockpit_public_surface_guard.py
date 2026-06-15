# -*- coding: utf-8 -*-
"""Focused public-surface guard for the homepage cockpit module set."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import json
import re

import pytest
from pydantic import BaseModel

from tests.test_homepage_schema_serialization_stress import PUBLIC_HOMEPAGE_OUTPUTS


T1589_T1608_PUBLIC_MODULES = frozenset(
    {
        "HomepageDailyMarketBriefService.build_daily_market_brief",
        "HomepageRiskRegimeService.build_snapshot",
        "HomepageCrossAssetIndicatorsService.build_snapshot",
        "HomepageEventImpactMapService.build_event_impact_map",
        "HomepageDriverChainService.build_snapshot",
        "HomepageThemeCapitalFlowService.build_snapshot",
        "HomepageResearchPrioritiesService.build_contract",
        "HomepageEvidenceQualityService.build_projection",
        "HomepageRatesPricingService.build_snapshot",
        "HomepageVolatilityPositioningService.build_snapshot",
        "HomepageLiquidityCreditService.build_snapshot",
        "HomepageMarketBreadthService.build_snapshot",
        "HomepageAfterCloseDevelopmentsService.build_snapshot",
        "HomepageScenarioWatchlistService.build_snapshot",
        "HomepageEarningsCatalystsService.build_snapshot",
        "HomepageGeopoliticalCommodityRiskService.build_snapshot",
        "HomepageAICapexInfrastructureService.build_snapshot",
        "HomepagePolicyRegulationWatchService.build_snapshot",
        "HomepageStyleLeadershipRotationService.build_snapshot",
        "HomepagePreSessionResearchChecklistService.build_snapshot",
    }
)

COCKPIT_PUBLIC_OUTPUTS: tuple[tuple[str, Callable[[], object]], ...] = tuple(
    (case_name, builder)
    for case_name, builder in PUBLIC_HOMEPAGE_OUTPUTS
    if case_name in T1589_T1608_PUBLIC_MODULES
)

FORBIDDEN_LITERAL_TERMS = (
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
)

FORBIDDEN_PUBLIC_SURFACE_PATTERNS = (
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\bwww\.", re.IGNORECASE),
    re.compile(r"\bapi[_ -]?key\b", re.IGNORECASE),
    re.compile(r"\bbearer\s+[a-z0-9._-]+", re.IGNORECASE),
    re.compile(r"\bbroker\b", re.IGNORECASE),
    re.compile(r"\bcache\b", re.IGNORECASE),
    re.compile(r"\bcookie\b", re.IGNORECASE),
    re.compile(r"\bdebug\b", re.IGNORECASE),
    re.compile(r"\bdiagnostic(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bexception\b", re.IGNORECASE),
    re.compile(r"\bexecution\b", re.IGNORECASE),
    re.compile(r"\bfallback\b", re.IGNORECASE),
    re.compile(r"\binternal\b", re.IGNORECASE),
    re.compile(r"\border\b", re.IGNORECASE),
    re.compile(r"\bpassword\b", re.IGNORECASE),
    re.compile(r"\bplace order\b", re.IGNORECASE),
    re.compile(r"\bprovider\b", re.IGNORECASE),
    re.compile(r"\braw(?:[_ -]?(?:error|payload|result|diagnostic|diagnostics))?\b", re.IGNORECASE),
    re.compile(r"\breason[_ -]?code\b", re.IGNORECASE),
    re.compile(r"\bruntime\b", re.IGNORECASE),
    re.compile(r"\bsecret\b", re.IGNORECASE),
    re.compile(r"\bsession[_ -]?id\b", re.IGNORECASE),
    re.compile(r"\bsource[_ -]?url\b", re.IGNORECASE),
    re.compile(r"\bsubmit order\b", re.IGNORECASE),
    re.compile(r"\btake[\s-]?profit\b", re.IGNORECASE),
    re.compile(r"\btarget price\b", re.IGNORECASE),
    re.compile(r"\btoken\b", re.IGNORECASE),
    re.compile(r"\btraceback\b", re.IGNORECASE),
    re.compile(r"\btrade execution\b", re.IGNORECASE),
    re.compile(r"\btrading advice\b", re.IGNORECASE),
    re.compile(r"\btrust[_ -]?level\b", re.IGNORECASE),
    re.compile(r"内部诊断"),
)


def _json_compatible(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_compatible(item) for item in value]
    if isinstance(value, tuple):
        return [_json_compatible(item) for item in value]
    return value


def _serialize_public_output(case_name: str, build_output: Callable[[], object]) -> str:
    try:
        payload = _json_compatible(build_output())
    except Exception as exc:  # pragma: no cover - exercised only on contract drift
        pytest.fail(f"{case_name} could not build a public homepage output: {type(exc).__name__}: {exc}")

    assert isinstance(payload, (dict, list)), f"{case_name} did not produce a public JSON object/list"

    try:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        pytest.fail(f"{case_name} could not serialize as public JSON: {type(exc).__name__}: {exc}")

    assert json.loads(encoded) == payload, case_name
    return encoded


def _find_forbidden_public_surface_markers(serialized: str) -> list[str]:
    leaked = [term for term in FORBIDDEN_LITERAL_TERMS if term in serialized]
    for pattern in FORBIDDEN_PUBLIC_SURFACE_PATTERNS:
        match = pattern.search(serialized)
        if match is not None:
            leaked.append(match.group(0))
    return sorted(set(leaked))


def test_homepage_cockpit_guard_covers_t1589_through_t1608_public_modules() -> None:
    covered = {case_name for case_name, _ in COCKPIT_PUBLIC_OUTPUTS}

    assert covered == T1589_T1608_PUBLIC_MODULES


@pytest.mark.parametrize(
    ("case_name", "build_output"),
    COCKPIT_PUBLIC_OUTPUTS,
    ids=[case_name for case_name, _ in COCKPIT_PUBLIC_OUTPUTS],
)
def test_homepage_cockpit_public_outputs_do_not_leak_internal_or_execution_language(
    case_name: str,
    build_output: Callable[[], object],
) -> None:
    serialized = _serialize_public_output(case_name, build_output)

    assert _find_forbidden_public_surface_markers(serialized) == []
