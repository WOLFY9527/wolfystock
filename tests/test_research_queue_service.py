# -*- coding: utf-8 -*-
"""Focused contract tests for the homepage research queue scaffold."""

from __future__ import annotations

import json

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
