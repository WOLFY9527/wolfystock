# -*- coding: utf-8 -*-
"""Cross-homepage backend language-safety regression tests."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import json
import re

import pytest

from src.services.dashboard_overview_service import DashboardOverviewService
from src.services.event_radar_service import EVENT_RADAR_NO_ADVICE_DISCLOSURE, EventRadarService
from src.services.market_pulse_service import MarketPulseService
from src.services.money_flow_service import MoneyFlowService
from src.services.personal_summary_service import PersonalSummaryService
from src.services.public_data_quality_service import build_public_data_quality_summary
from src.services.research_queue_service import ResearchQueueService
from src.services.sector_theme_strength_service import SectorThemeStrengthService


FORBIDDEN_LITERAL_TERMS = (
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
    "交易执行",
)
FORBIDDEN_CASE_INSENSITIVE_PATTERNS = (
    re.compile(r"\bbuy\b"),
    re.compile(r"\bsell\b"),
    re.compile(r"\btarget price\b"),
    re.compile(r"\btake[\s-]?profit\b"),
    re.compile(r"\bstop[\s-]?loss\b"),
    re.compile(r"\bbroker execution\b"),
    re.compile(r"\bplace order\b"),
    re.compile(r"traceback"),
    re.compile(r"reasoncode"),
    re.compile(r"trustlevel"),
    re.compile(r"sourcetype"),
    re.compile(r"fallback"),
    re.compile(r"raw[_ -]?confidence"),
    re.compile(r"\btoken\b"),
    re.compile(r"\bsession(?:id)?\b"),
    re.compile(r"api[_ -]?key"),
    re.compile(r"\bsecret\b"),
    re.compile(r"providerurl"),
    re.compile(r"https?://"),
)


def _serialize(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _assert_language_safe(case_name: str, payload: object) -> None:
    serialized = _serialize(payload)
    lowered = serialized.lower()
    findings: list[str] = []

    for term in FORBIDDEN_LITERAL_TERMS:
        if term in serialized:
            findings.append(term)

    for pattern in FORBIDDEN_CASE_INSENSITIVE_PATTERNS:
        match = pattern.search(lowered)
        if match:
            findings.append(match.group(0))

    assert findings == [], f"{case_name} leaked forbidden markers: {sorted(set(findings))}"


def _build_dashboard_overview_payload() -> dict[str, object]:
    return DashboardOverviewService().get_market_intelligence_overview()


def _build_market_pulse_payload() -> dict[str, object]:
    return (
        MarketPulseService()
        .build_snapshot(
            {
                "asOf": "2026-06-14T09:30:00Z",
                "sp500": {"value": 5300.25, "change": 0.8},
                "nasdaq": {"value": 18880.4, "change": 1.1, "state": "走强"},
                "russell2000": {"value": 2110.2, "change": -0.2, "state": "中性"},
                "vix": {"value": 13.4, "change": -0.7, "state": "ready"},
                "tenYearYield": {"value": 4.31, "change": 0.03, "dataQuality": "ready"},
                "dollarIndex": {"value": 104.2, "change": -0.1},
                "marketBreadth": {"value": 56.0, "change": 2.5},
                "liquidityState": {"state": "ready", "interpretation": "适合研究观察"},
            }
        )
        .model_dump(mode="json")
    )


def _build_money_flow_payload() -> dict[str, object]:
    return MoneyFlowService().build_homepage_money_flow_proxy(
        as_of="2026-06-14T09:30:00Z",
        top_inflows=[
            {
                "name": "算力链",
                "category": "theme",
                "strength": "strong",
                "breadth": "broadening",
                "relativeMove": "strengthening",
                "dataQuality": "partial",
            }
        ],
        top_outflows=[
            {
                "name": "高股息防御",
                "category": "sector",
                "strength": "moderate",
                "breadth": "converging",
                "relativeMove": "weakening",
                "dataQuality": "partial",
            }
        ],
        style_bias={
            "bias": "growth",
            "interpretation": "成长 observed flow proxy 相对更强，继续观察并复核。",
            "dataQuality": "partial",
        },
        offensive_defensive_bias={
            "bias": "defensive",
            "interpretation": "防守 observed flow proxy 暂时更占优，继续观察并复核。",
            "dataQuality": "partial",
        },
    )


def _build_sector_theme_strength_payload() -> dict[str, object]:
    return (
        SectorThemeStrengthService()
        .build_summary(
            {
                "asOf": "2026-06-14T09:30:00Z",
                "strongest": [
                    {
                        "name": "半导体",
                        "category": "sector",
                        "relativeStrength": 0.82,
                        "breadth": 0.74,
                        "diffusionStatus": "diffusing",
                        "leadershipStatus": "stronger",
                        "observation": "相对强弱领先且扩散到更多成员，仅供观察。",
                        "dataQuality": {"status": "ready", "observation": "example/test data only"},
                    }
                ],
                "weakest": [
                    {
                        "name": "公用事业",
                        "category": "sector",
                        "relativeStrength": -0.41,
                        "breadth": 0.28,
                        "diffusionStatus": "narrowing",
                        "leadershipStatus": "weaker",
                        "observation": "相对强弱偏弱且扩散不足，仅供观察。",
                        "dataQuality": {"status": "ready", "observation": "example/test data only"},
                    }
                ],
                "leadership": {
                    "status": "concentrated",
                    "observation": "当前强势主要集中在少数龙头，扩散仍待继续观察。",
                    "dataQuality": {"status": "ready", "observation": "example/test data only"},
                },
                "diffusion": {
                    "status": "diffusing",
                    "observation": "强势从龙头向更多成员扩散，但仍仅供观察。",
                    "dataQuality": {"status": "ready", "observation": "example/test data only"},
                },
                "concentration": {
                    "status": "concentrated",
                    "observation": "龙头集中度偏高，需继续观察集中是否缓解。",
                    "dataQuality": {"status": "ready", "observation": "example/test data only"},
                },
                "dataQuality": {"status": "ready", "observation": "example/test data only"},
            }
        )
        .model_dump(mode="json")
    )


def _build_event_radar_payload() -> dict[str, object]:
    return (
        EventRadarService()
        .build_snapshot(
            as_of=datetime(2026, 6, 14, 9, 30, tzinfo=timezone.utc),
            items=[
                {
                    "id": "evt-radar-macro-001",
                    "title": "US CPI surprise raises valuation review pressure across rate-sensitive groups",
                    "category": "macro",
                    "impactStatus": "high_attention",
                    "impactDirection": "negative",
                    "affectedSectors": ["software", "semiconductors"],
                    "affectedThemes": ["rate_sensitivity", "duration_risk"],
                    "relatedSymbols": ["QQQ", "SMH", "AAPL"],
                    "relatedMarketSignals": ["rates", "sector_rotation", "watchlist"],
                    "reviewModules": ["macro_context", "home_overview", "watchlist_context"],
                    "sourceStatus": "ready",
                    "freshness": "delayed",
                    "summary": (
                        "Macro release pressure may affect discount-rate assumptions and sector leadership, "
                        "so impacted holdings and watchlist names should be reviewed."
                    ),
                    "noAdviceDisclosure": EVENT_RADAR_NO_ADVICE_DISCLOSURE,
                }
            ],
        )
        .model_dump(mode="json")
    )


def _build_personal_summary_payload() -> dict[str, object]:
    return (
        PersonalSummaryService()
        .build_summary(
            portfolio_snapshot={
                "total_equity": 250000.0,
                "daily_change": 1800.5,
                "cash_percent": 12.5,
                "largest_exposure": 28.1,
                "risk_score": 41.0,
                "risk_status": "observe",
                "concentration_status": "observe",
                "account_count": 1,
                "data_status": "ready",
            },
            watchlist_items=[
                {
                    "symbol": "NVDA",
                    "displayName": "NVIDIA",
                    "symbolStatus": "review",
                    "movementStatus": "stronger",
                    "relativeStrengthStatus": "stronger",
                    "volumeStatus": "volume_expanded",
                    "evidenceStatus": "review",
                    "researchStatus": "review",
                    "lastReviewedAt": "2026-06-14T08:00:00Z",
                    "reviewReason": "Momentum evidence changed and requires review.",
                },
                {
                    "symbol": "TSLA",
                    "displayName": "Tesla",
                    "evidenceStatus": "no_evidence",
                    "researchStatus": "no_evidence",
                },
            ],
            portfolio_connected=True,
        )
        .model_dump(mode="json")
    )


def _build_research_queue_payload() -> dict[str, object]:
    return (
        ResearchQueueService()
        .build_queue(
            {
                "asOf": "2026-06-14T09:30:00Z",
                "market": [
                    {
                        "title": "广度复核",
                        "reason": "主要指数与行业扩散需要复核，保持研究观察。",
                        "status": "review",
                        "evidenceStatus": "available",
                        "relatedSymbols": ["000300.SH"],
                        "relatedThemes": ["宽基"],
                    }
                ],
                "watchlist": [
                    {
                        "title": "Watchlist 证据补齐",
                        "reason": "候选标的资料不完整，需要补齐后再继续研究。",
                        "status": "observe",
                        "evidenceStatus": "partial",
                        "relatedSymbols": ["NVDA"],
                        "relatedThemes": ["AI"],
                    }
                ],
            }
        )
        .model_dump(mode="json")
    )


def _build_public_data_quality_payload() -> dict[str, object]:
    return (
        build_public_data_quality_summary(
            {
                "moduleStates": [
                    {"module": "home", "status": "ready"},
                    {"module": "market_overview", "state": "fresh"},
                    {"name": "scanner", "qualityState": "updated"},
                ]
            }
        )
        .model_dump(by_alias=True)
    )


CASE_BUILDERS: tuple[tuple[str, Callable[[], object]], ...] = (
    ("dashboard_overview_service", _build_dashboard_overview_payload),
    ("market_pulse_service", _build_market_pulse_payload),
    ("money_flow_service", _build_money_flow_payload),
    ("sector_theme_strength_service", _build_sector_theme_strength_payload),
    ("event_radar_service", _build_event_radar_payload),
    ("personal_summary_service", _build_personal_summary_payload),
    ("research_queue_service", _build_research_queue_payload),
    ("public_data_quality_service", _build_public_data_quality_payload),
)


@pytest.mark.parametrize(
    ("case_name", "build_payload"),
    CASE_BUILDERS,
    ids=[case_name for case_name, _ in CASE_BUILDERS],
)
def test_homepage_scaffold_serialized_outputs_remain_language_safe(
    case_name: str,
    build_payload: Callable[[], object],
) -> None:
    payload = build_payload()

    _assert_language_safe(case_name, payload)
