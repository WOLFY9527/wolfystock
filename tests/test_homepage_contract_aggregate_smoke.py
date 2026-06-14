# -*- coding: utf-8 -*-
"""Aggregate smoke tests for homepage standalone contracts and overview composition."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import json
import re

import pytest

from src.services.dashboard_overview_service import DashboardOverviewService
from src.services.event_radar_service import build_no_evidence_event_radar_snapshot
from src.services.event_window_service import EventWindowService
from src.services.homepage_capabilities_service import HomepageCapabilitiesService
from src.services.homepage_demo_payload_service import HomepageDemoPayloadService
from src.services.homepage_explanation_service import HomepageExplanationService
from src.services.homepage_module_manifest_service import HomepageModuleManifestService
from src.services.market_pulse_service import MarketPulseService
from src.services.market_session_status_service import MarketSessionStatusService
from src.services.money_flow_service import MoneyFlowService
from src.services.personal_summary_service import PersonalSummaryService
from src.services.public_data_quality_service import build_public_data_quality_summary
from src.services.research_queue_service import ResearchQueueService
from src.services.sector_theme_strength_service import SectorThemeStrengthService
from src.services.source_freshness_summary_service import build_source_freshness_summary


FORBIDDEN_LITERAL_TERMS = (
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "清仓",
    "下单",
    "立即交易",
    "交易建议",
    "交易指令",
    "投资建议",
    "止损",
    "止盈",
    "目标价",
    "收益预测",
)
FORBIDDEN_CASE_INSENSITIVE_PATTERNS = (
    re.compile(r"\bbuy\b"),
    re.compile(r"\bsell\b"),
    re.compile(r"\badd position\b"),
    re.compile(r"\breduce position\b"),
    re.compile(r"\bplace order\b"),
    re.compile(r"\bsubmit order\b"),
    re.compile(r"\btrade execution\b"),
    re.compile(r"\btrading advice\b"),
    re.compile(r"\binvestment advice\b"),
    re.compile(r"\bfinancial advice\b"),
    re.compile(r"\btarget price\b"),
    re.compile(r"\bstop[\s-]?loss\b"),
    re.compile(r"\btake[\s-]?profit\b"),
    re.compile(r"\btraceback\b"),
    re.compile(r"\btoken\b"),
    re.compile(r"\bsession(?:id)?\b"),
    re.compile(r"\bapi[_ -]?key\b"),
    re.compile(r"\bsecret\b"),
    re.compile(r"\breasoncode\b"),
    re.compile(r"\btrustlevel\b"),
    re.compile(r"\bsourcetype\b"),
    re.compile(r"\bprovider\b"),
    re.compile(r"\binternal\b"),
    re.compile(r"\bdiagnostic(?:s)?\b"),
    re.compile(r"\bdebug\b"),
    re.compile(r"https?://"),
)
FORBIDDEN_LIVE_DEFAULT_PATTERNS = (
    re.compile(r"\blive data\b"),
    re.compile(r"\blive quote\b"),
    re.compile(r"\blive market\b"),
    re.compile(r"\breal[- ]time\b"),
    re.compile(r"实时数据"),
    re.compile(r"实时行情"),
)
DISCLOSURE_KEYS = {"noAdviceDisclosure", "demoDisclosure"}
SAFE_NEGATED_BOUNDARY_PHRASES = (
    "不包含交易建议",
    "不包含投资建议",
    "不包含交易指令",
    "不提供交易判断",
    "不构成交易指令",
)


def _serialize(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _scrub_disclosures(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            key: "<disclosure>" if key in DISCLOSURE_KEYS else _scrub_disclosures(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_scrub_disclosures(item) for item in value]
    return value


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


def _assert_json_serializable_and_bounded(payload: object, *, max_chars: int) -> None:
    serialized = _serialize(payload)
    assert len(serialized) <= max_chars


def _assert_no_forbidden_terms(payload: object) -> None:
    scrubbed = _scrub_disclosures(payload)
    serialized = _serialize(scrubbed)
    for phrase in SAFE_NEGATED_BOUNDARY_PHRASES:
        serialized = serialized.replace(phrase, "<safe-boundary>")
    lowered = serialized.lower()

    leaked = [term for term in FORBIDDEN_LITERAL_TERMS if term in serialized]
    for pattern in FORBIDDEN_CASE_INSENSITIVE_PATTERNS:
        match = pattern.search(lowered)
        if match:
            leaked.append(match.group(0))

    assert leaked == []


def _assert_no_live_claim_markers(payload: object) -> None:
    scrubbed = _scrub_disclosures(payload)
    lowered = _serialize(scrubbed).lower()
    leaked = [pattern.pattern for pattern in FORBIDDEN_LIVE_DEFAULT_PATTERNS if pattern.search(lowered)]
    assert leaked == []


def _assert_has_disclosure(payload: object) -> None:
    disclosures = _collect_disclosures(payload)
    assert disclosures
    assert all(isinstance(item, str) and item.strip() for item in disclosures)


def _build_dashboard_overview_payload() -> dict[str, object]:
    return DashboardOverviewService().get_market_intelligence_overview()


def _build_market_pulse_payload() -> dict[str, object]:
    return MarketPulseService().build_snapshot().model_dump(mode="json")


def _build_money_flow_payload() -> dict[str, object]:
    return MoneyFlowService().build_homepage_money_flow_proxy()


def _build_sector_theme_strength_payload() -> dict[str, object]:
    return SectorThemeStrengthService().build_summary().model_dump(mode="json")


def _build_event_radar_payload() -> dict[str, object]:
    return build_no_evidence_event_radar_snapshot().model_dump(mode="json")


def _build_personal_summary_payload() -> dict[str, object]:
    return PersonalSummaryService().build_summary().model_dump(mode="json")


def _build_research_queue_payload() -> dict[str, object]:
    return ResearchQueueService().build_queue().model_dump(mode="json")


def _build_public_data_quality_payload() -> dict[str, object]:
    return build_public_data_quality_summary({}).model_dump(by_alias=True)


def _build_market_session_status_payload() -> dict[str, object]:
    return MarketSessionStatusService().build_status().model_dump(mode="json")


def _build_event_window_payload() -> dict[str, object]:
    return EventWindowService().build_summary().model_dump(mode="json")


def _build_homepage_capabilities_payload() -> dict[str, object]:
    return HomepageCapabilitiesService().build_snapshot().model_dump(mode="json")


def _build_homepage_module_manifest_payload() -> dict[str, object]:
    return HomepageModuleManifestService().build_manifest(as_of="2026-06-14T09:30:00Z")


def _build_homepage_explanation_payload() -> dict[str, object]:
    return HomepageExplanationService().build_explanations().model_dump(mode="json")


def _build_source_freshness_summary_payload() -> dict[str, object]:
    return build_source_freshness_summary({}).model_dump(by_alias=True)


def _build_homepage_demo_payloads() -> dict[str, dict[str, object]]:
    return HomepageDemoPayloadService().build_payloads()


AGGREGATE_CASES: tuple[tuple[str, Callable[[], object], int], ...] = (
    ("dashboard_overview_service", _build_dashboard_overview_payload, 12000),
    ("market_pulse_service", _build_market_pulse_payload, 12000),
    ("money_flow_service", _build_money_flow_payload, 12000),
    ("sector_theme_strength_service", _build_sector_theme_strength_payload, 12000),
    ("event_radar_service", _build_event_radar_payload, 12000),
    ("personal_summary_service", _build_personal_summary_payload, 12000),
    ("research_queue_service", _build_research_queue_payload, 12000),
    ("public_data_quality_service", _build_public_data_quality_payload, 8000),
    ("market_session_status_service", _build_market_session_status_payload, 8000),
    ("event_window_service", _build_event_window_payload, 12000),
    ("homepage_capabilities_service", _build_homepage_capabilities_payload, 12000),
    ("homepage_module_manifest_service", _build_homepage_module_manifest_payload, 12000),
    ("homepage_explanation_service", _build_homepage_explanation_payload, 8000),
    ("source_freshness_summary_service", _build_source_freshness_summary_payload, 8000),
    ("homepage_demo_payload_service", _build_homepage_demo_payloads, 30000),
)


@pytest.mark.parametrize(
    ("case_name", "build_payload", "max_chars"),
    AGGREGATE_CASES,
    ids=[case_name for case_name, _, _ in AGGREGATE_CASES],
)
def test_homepage_contract_outputs_are_bounded_json_serializable_and_safe(
    case_name: str,
    build_payload: Callable[[], object],
    max_chars: int,
) -> None:
    payload = build_payload()

    assert isinstance(payload, dict), case_name
    _assert_json_serializable_and_bounded(payload, max_chars=max_chars)
    _assert_no_forbidden_terms(payload)
    _assert_no_live_claim_markers(payload)
    _assert_has_disclosure(payload)


def test_dashboard_overview_default_composition_stays_aligned_with_standalone_defaults() -> None:
    overview = DashboardOverviewService().get_market_intelligence_overview()
    market_pulse = MarketPulseService().build_snapshot().model_dump(mode="json")
    money_flow = MoneyFlowService().build_homepage_money_flow_proxy()
    sector_theme = SectorThemeStrengthService().build_summary().model_dump(mode="json")
    research_queue = ResearchQueueService().build_queue().model_dump(mode="json")

    assert overview["status"] == "partial"
    assert overview["marketPulse"]["sp500"]["label"] == market_pulse["indices"][0]["label"]
    assert overview["marketPulse"]["sp500"]["status"] == "no_evidence"
    assert overview["marketPulse"]["marketBreadth"]["status"] == "no_evidence"
    assert overview["moneyFlow"]["status"] == money_flow["status"] == "no_evidence"
    assert overview["moneyFlow"]["topInflows"] == []
    assert overview["moneyFlow"]["topOutflows"] == []
    assert overview["sectorThemeRotation"]["status"] == sector_theme["status"] == "no_evidence"
    assert overview["sectorThemeRotation"]["leadingThemes"] == []
    assert overview["sectorThemeRotation"]["laggingThemes"] == []
    assert overview["researchQueue"]["status"] == research_queue["status"] == "no_evidence"
    assert overview["researchQueue"]["items"] == []
    assert overview["liquidityRisk"]["status"] == "no_evidence"
    assert overview["marketBrief"]["status"] == "ready"
    assert overview["dataQuality"]["sections"] == {
        "marketPulse": "no_evidence",
        "marketBrief": "ready",
        "moneyFlow": "no_evidence",
        "liquidityRisk": "ready",
        "sectorThemeRotation": "no_evidence",
        "researchQueue": "no_evidence",
    }
