# -*- coding: utf-8 -*-
"""Focused contract tests for the homepage research queue scaffold."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from api.v1.schemas.event_radar import EVENT_RADAR_SNAPSHOT_CONTRACT_VERSION
from api.v1.schemas.money_flow import (
    ConsumerDataQualityModel,
    HomeMoneyFlowProxyResponse,
    MoneyFlowBiasModel,
    MoneyFlowItemModel,
    MoneyFlowSourceStatusModel,
)
from api.v1.schemas.personal_summary import (
    PersonalSummaryDataQuality,
    PersonalSummaryPortfolioSnapshot,
    PersonalSummaryResearchCoverage,
    PersonalSummaryResponse,
    PersonalSummaryReviewQueue,
    PersonalSummaryReviewQueueItem,
    PersonalSummaryWatchlistException,
    PersonalSummaryWatchlistExceptions,
)
from api.v1.schemas.research_queue import ResearchQueueBuildInputs
from src.services.research_queue_service import ResearchQueueService


FORBIDDEN_ADVICE_TERMS = (
    "buy",
    "sell",
    "add position",
    "reduce position",
    "clear position",
    "stop-loss",
    "stop loss",
    "take-profit",
    "take profit",
    "target-price",
    "target price",
    "predicted-return",
    "predicted return",
    "ai recommendation",
    "intelligent stock picking",
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "清仓",
    "止损",
    "止盈",
    "目标价",
    "预测收益",
    "智能选股",
)

FORBIDDEN_LEAK_TERMS = (
    "traceback",
    "http://",
    "https://",
    "token",
    "session",
    "api_key",
    "apikey",
    "secret",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "fallback",
)


def _serialized(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def test_research_queue_serializes_stable_item_shape() -> None:
    queue = ResearchQueueService().build_queue(
        ResearchQueueBuildInputs(
            asOf="2026-06-14T09:30:00Z",
            market=[
                {
                    "title": "广度复核",
                    "reason": "主要指数与行业扩散需要复核，保持研究观察。",
                    "status": "review",
                    "evidenceStatus": "available",
                    "relatedSymbols": ["000300.SH"],
                    "relatedThemes": ["宽基"],
                }
            ],
            watchlist=[
                {
                    "title": "Watchlist 证据补齐",
                    "reason": "候选标的资料不完整，需要补齐后再继续研究。",
                    "status": "observe",
                    "evidenceStatus": "partial",
                    "relatedSymbols": ["NVDA"],
                    "relatedThemes": ["AI"],
                }
            ],
        )
    ).model_dump(mode="json")

    assert queue["status"] == "ready"
    assert queue["asOf"] == "2026-06-14T09:30:00Z"
    assert len(queue["items"]) == 2
    assert set(queue["items"][0]) == {
        "id",
        "priority",
        "title",
        "reason",
        "category",
        "reviewModule",
        "status",
        "relatedSymbols",
        "relatedThemes",
        "evidenceStatus",
        "noAdviceDisclosure",
    }
    assert queue["dataQuality"]["status"] == "partial"
    assert queue["noAdviceDisclosure"]


def test_research_queue_priorities_are_bounded_and_ordered() -> None:
    queue = ResearchQueueService().build_queue(
        ResearchQueueBuildInputs(
            asOf="2026-06-14T09:30:00Z",
            market=[
                {
                    "title": "广度复核",
                    "reason": "市场扩散需要复核。",
                    "status": "review",
                    "evidenceStatus": "available",
                    "priorityHint": 5,
                }
            ],
            portfolio=[
                {
                    "title": "组合集中度检查",
                    "reason": "组合暴露需要先复核。",
                    "status": "high_attention",
                    "evidenceStatus": "partial",
                    "priorityHint": 1,
                }
            ],
            dataQuality=[
                {
                    "title": "资料完整性检查",
                    "reason": "关键字段未完全接入。",
                    "status": "no_evidence",
                    "evidenceStatus": "no_evidence",
                    "priorityHint": 9,
                }
            ],
        )
    ).model_dump(mode="json")

    priorities = [item["priority"] for item in queue["items"]]
    titles = [item["title"] for item in queue["items"]]

    assert priorities == [1, 2, 3]
    assert titles[0] == "组合集中度检查"
    assert titles[-1] == "资料完整性检查"


def test_research_queue_excludes_no_advice_and_prohibited_terms() -> None:
    queue = ResearchQueueService().build_queue(
        ResearchQueueBuildInputs(
            asOf="2026-06-14T09:30:00Z",
            research=[
                {
                    "title": "AI recommendation buy now",
                    "reason": "target price 100, predicted return 20%, 建议加仓。",
                    "status": "review",
                    "evidenceStatus": "available",
                    "reviewModule": "https://unsafe.example/token",
                    "relatedSymbols": ["AAPL", "session-unsafe"],
                    "relatedThemes": ["secret-plan"],
                }
            ]
        )
    ).model_dump(mode="json")

    serialized = _serialized(queue)
    leaked = [term for term in FORBIDDEN_ADVICE_TERMS if term in serialized]
    assert leaked == []
    assert "no advice" in queue["noAdviceDisclosure"].lower()
    assert "no advice" in queue["items"][0]["noAdviceDisclosure"].lower()


def test_research_queue_empty_no_evidence_queue_is_valid() -> None:
    queue = ResearchQueueService().build_queue(
        ResearchQueueBuildInputs(asOf="2026-06-14T09:30:00Z")
    ).model_dump(mode="json")

    assert queue["status"] == "no_evidence"
    assert queue["asOf"] == "2026-06-14T09:30:00Z"
    assert queue["items"] == []
    assert queue["dataQuality"]["status"] == "no_evidence"
    assert "未接入" in queue["dataQuality"]["summary"]


def test_research_queue_excludes_internal_diagnostics_and_secret_like_markers() -> None:
    queue = ResearchQueueService().build_queue(
        ResearchQueueBuildInputs(
            asOf="2026-06-14T09:30:00Z",
            event=[
                {
                    "id": "traceback-http://unsafe",
                    "title": "关键事件复核",
                    "reason": "traceback: provider_url leaked with api_key=123 and sourceType=fallback.",
                    "status": "review",
                    "evidenceStatus": "partial",
                    "reviewModule": "internal/session/token/debug",
                    "relatedSymbols": ["TSLA", "api_key"],
                    "relatedThemes": ["sourceType", "fallback"],
                }
            ]
        )
    ).model_dump(mode="json")

    serialized = _serialized(queue)
    leaked = [term for term in FORBIDDEN_LEAK_TERMS if term in serialized]
    assert leaked == []
    assert queue["items"][0]["id"] == "event-1"
    assert queue["items"][0]["reviewModule"] == "event_review"


def test_research_queue_adapters_accept_safe_mappings_and_typed_models_in_order() -> None:
    queue = ResearchQueueService().build_queue(
        ResearchQueueBuildInputs(
            asOf="2026-06-14T09:30:00Z",
            moneyFlowSummary=HomeMoneyFlowProxyResponse(
                status="ready",
                asOf="2026-06-14T09:10:00Z",
                topInflows=[
                    MoneyFlowItemModel(
                        name="半导体",
                        category="sector",
                        direction="inflow",
                        strength="strong",
                        breadth="broadening",
                        relativeMove="strengthening",
                        interpretation="半导体资金流延续，仍需继续研究观察。",
                        dataQuality="ready",
                    )
                ],
                topOutflows=[],
                styleBias=MoneyFlowBiasModel(
                    bias="growth",
                    interpretation="成长风格相对占优，仍需复核。",
                    dataQuality=ConsumerDataQualityModel(
                        state="ready",
                        label="正常",
                        available=True,
                    ),
                ),
                offensiveDefensiveBias=MoneyFlowBiasModel(
                    bias="offensive",
                    interpretation="进攻风格相对活跃，保持研究观察。",
                    dataQuality=ConsumerDataQualityModel(
                        state="ready",
                        label="正常",
                        available=True,
                    ),
                ),
                interpretation="资金流延续性仍需复核，仅供研究观察。",
                sourceStatus=MoneyFlowSourceStatusModel(summary="Observed flow proxy only."),
                dataQuality=ConsumerDataQualityModel(
                    state="ready",
                    label="正常",
                    available=True,
                ),
                noAdviceDisclosure="仅供研究观察，不构成投资建议",
            ),
            eventRadarSummary={
                "schemaVersion": EVENT_RADAR_SNAPSHOT_CONTRACT_VERSION,
                "asOf": datetime(2026, 6, 14, 9, 20, 0),
                "sourceStatus": "ready",
                "freshness": "fresh",
                "summary": "重点事件进入复核窗口，继续保留研究观察。",
                "itemCount": 1,
                "items": [
                    {
                        "id": "evt-1",
                        "title": "重点财报窗口",
                        "category": "earnings",
                        "impactStatus": "high_attention",
                        "affectedSectors": ["半导体"],
                        "affectedThemes": ["AI硬件"],
                        "relatedSymbols": ["NVDA"],
                        "relatedMarketSignals": ["财报窗口"],
                        "reviewModules": ["earnings_calendar"],
                        "sourceStatus": "ready",
                        "freshness": "fresh",
                        "summary": "重点财报窗口需要二次复核。",
                        "noAdviceDisclosure": "Research only.",
                    }
                ],
                "noAdviceDisclosure": "Research only.",
            },
            personalSummary=PersonalSummaryResponse(
                status="partial",
                portfolioSnapshot=PersonalSummaryPortfolioSnapshot(
                    connected=True,
                    riskStatus="observe",
                    concentrationStatus="review",
                ),
                watchlistExceptions=PersonalSummaryWatchlistExceptions(
                    status="partial",
                    items=[
                        PersonalSummaryWatchlistException(
                            symbol="TSLA",
                            displayName="Tesla",
                            evidenceStatus="observe",
                            researchStatus="review",
                            reviewReason="观察名单条目仍需补齐公开证据。",
                        )
                    ],
                    staleCount=1,
                    noEvidenceCount=0,
                ),
                researchCoverage=PersonalSummaryResearchCoverage(
                    status="partial",
                    missingSymbols=["TSLA"],
                    staleSymbols=[],
                    coveredSymbols=["AAPL"],
                ),
                reviewQueue=PersonalSummaryReviewQueue(
                    status="partial",
                    items=[
                        PersonalSummaryReviewQueueItem(
                            symbol="TSLA",
                            displayName="Tesla",
                            priorityStatus="observe",
                            evidenceStatus="observe",
                            researchStatus="review",
                            reviewReason="组合与关注列表需要复核。",
                        )
                    ],
                ),
                dataQuality=PersonalSummaryDataQuality(
                    status="partial",
                    portfolioStatus="ready",
                    watchlistStatus="partial",
                    researchStatus="partial",
                    connected=True,
                ),
            ),
            dataQualitySummary={
                "status": "no_evidence",
                "label": "暂无证据",
                "suitableForResearchObservation": False,
                "asOf": "2026-06-14T09:25:00Z",
                "updatedModules": ["homepage"],
                "affectedModules": ["watchlist", "research"],
                "message": "暂无足够证据生成公开摘要",
                "noAdviceDisclosure": "仅供研究观察，不构成投资建议",
            },
        )
    ).model_dump(mode="json")

    assert [item["title"] for item in queue["items"]] == [
        "关键事件复核",
        "资金流延续性观察",
        "组合/关注列表复核",
        "数据质量复核",
    ]
    assert [item["priority"] for item in queue["items"]] == [1, 2, 3, 4]
    assert [item["category"] for item in queue["items"]] == [
        "event",
        "money_flow",
        "watchlist",
        "data_quality",
    ]
    assert queue["items"][0]["status"] == "high_attention"
    assert queue["items"][1]["status"] == "review"
    assert queue["items"][2]["status"] == "observe"
    assert queue["items"][3]["status"] == "no_evidence"
    assert queue["status"] == "ready"
    assert queue["dataQuality"]["status"] == "partial"


def test_research_queue_adapters_sanitize_unsafe_titles_reasons_and_leaks() -> None:
    queue = ResearchQueueService().build_queue(
        ResearchQueueBuildInputs(
            asOf="2026-06-14T09:30:00Z",
            moneyFlowSummary={
                "status": "ready",
                "topInflows": [
                    {
                        "name": "半导体",
                        "category": "sector",
                        "direction": "inflow",
                        "interpretation": "buy now and target price 100",
                        "dataQuality": "ready",
                    }
                ],
                "interpretation": "api_key leaked and predicted return 20%",
                "sourceStatus": {"summary": "token leaked"},
            },
            personalSummary={
                "status": "partial",
                "portfolioSnapshot": {
                    "connected": True,
                    "riskStatus": "observe",
                    "concentrationStatus": "review",
                },
                "watchlistExceptions": {
                    "status": "partial",
                    "items": [
                        {
                            "symbol": "TSLA",
                            "reviewReason": "buy secret://path",
                            "researchStatus": "review",
                            "evidenceStatus": "observe",
                        }
                    ],
                },
                "researchCoverage": {
                    "status": "partial",
                    "missingSymbols": ["TSLA"],
                    "staleSymbols": [],
                    "coveredSymbols": [],
                },
                "reviewQueue": {
                    "status": "partial",
                    "items": [
                        {
                            "symbol": "TSLA",
                            "priorityStatus": "observe",
                            "researchStatus": "review",
                            "evidenceStatus": "observe",
                            "reviewReason": "session secret fallback",
                        }
                    ],
                },
                "dataQuality": {
                    "status": "partial",
                    "portfolioStatus": "ready",
                    "watchlistStatus": "partial",
                    "researchStatus": "partial",
                    "connected": True,
                },
            },
        )
    ).model_dump(mode="json")

    serialized = _serialized(queue)
    assert queue["items"][0]["title"] == "资金流延续性观察"
    assert queue["items"][1]["title"] == "组合/关注列表复核"
    assert "资金流" in queue["items"][0]["reason"]
    assert "组合" in queue["items"][1]["reason"]
    assert [term for term in FORBIDDEN_ADVICE_TERMS if term in serialized] == []
    assert [term for term in FORBIDDEN_LEAK_TERMS if term in serialized] == []


def test_research_queue_adapters_fail_closed_for_unsafe_input_shapes() -> None:
    queue = ResearchQueueService().build_queue(
        {
            "asOf": "2026-06-14T09:30:00Z",
            "moneyFlowSummary": 123,
            "eventRadarSummary": ["unsafe"],
            "personalSummary": "secret",
            "dataQualitySummary": object(),
        }
    ).model_dump(mode="json")

    assert queue["status"] == "no_evidence"
    assert queue["items"] == []
    assert queue["dataQuality"]["status"] == "no_evidence"


def test_research_queue_service_does_not_import_cross_domain_or_dashboard_modules() -> None:
    source = Path("src/services/research_queue_service.py").read_text(encoding="utf-8")

    for forbidden in (
        "api.v1.schemas.event_radar",
        "api.v1.schemas.money_flow",
        "api.v1.schemas.personal_summary",
        "api.v1.schemas.public_data_quality",
        "src.services.event_radar_service",
        "src.services.money_flow_service",
        "src.services.personal_summary_service",
        "src.services.public_data_quality_service",
        "dashboard",
    ):
        assert forbidden not in source
