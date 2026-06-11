# -*- coding: utf-8 -*-
"""Tests for Intelligence Report Engine v2 packet composition."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from api.v1.schemas.history import AnalysisReport
from src.services.intelligence_report_packet import (
    INTELLIGENCE_REPORT_PACKET_VERSION,
    build_intelligence_report_packet_v2,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = REPO_ROOT / "src/services/intelligence_report_packet.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "yfinance",
    "litellm",
    "src.config",
    "src.services.litellm_runtime",
    "src.services.analysis_provider_planner",
)
FORBIDDEN_CONSUMER_TEXT = (
    "buy",
    "sell",
    "order",
    "trade",
    "position sizing",
    "stop loss",
    "target price",
    "买入",
    "卖出",
    "下单",
    "交易建议",
    "投资建议",
    "止损",
    "目标价",
    "仓位建议",
)


def _helper_imports() -> set[str]:
    tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def _ready_payload() -> dict:
    return {
        "symbol": "AAPL",
        "market": "us",
        "thesis": "Revenue growth is improving, while price structure still needs confirmation.",
        "standardReport": {
            "summaryPanel": {
                "oneSentence": "Revenue growth is improving, while price structure still needs confirmation.",
                "operationAdvice": "Observe only",
                "trendPrediction": "Positive observation",
            },
            "reasonLayer": {
                "coreReasons": [
                    "Quarterly revenue accelerated.",
                    "MA20 support remains intact.",
                ],
                "topRisk": "Valuation remains elevated.",
                "topCatalyst": "Product cycle demand remains visible.",
                "latestKeyUpdate": "Latest filing confirmed higher backlog.",
            },
            "highlights": {
                "riskAlerts": ["Valuation remains elevated."],
                "positiveCatalysts": ["Product cycle demand remains visible."],
            },
            "coverageNotes": {
                "coverageGaps": [],
                "conflictNotes": [],
                "methodNotes": ["Evidence was normalized from existing report metadata."],
            },
            "decisionPanel": {
                "confidence": "medium",
                "marketStructure": "Price is above MA20 but volume confirmation is pending.",
            },
        },
        "researchReadiness": {
            "contractVersion": "research_readiness_v1",
            "researchReady": True,
            "readinessState": "ready",
            "blockingReasons": [],
            "missingEvidence": [],
            "evidenceCoverage": {
                "scoreGradeCount": 3,
                "observationOnlyCount": 0,
                "missingCount": 0,
                "totalCount": 3,
            },
            "sourceAuthority": "scoreGradeAllowed",
            "freshnessFloor": "fresh",
            "consumerActionBoundary": "no_advice",
            "nextEvidenceNeeded": [],
        },
        "evidenceCitationFrame": {
            "citedEvidence": [
                {"id": "e-price", "domain": "technicals", "summary": "MA20 support remains intact."},
                {"id": "e-fundamentals", "domain": "fundamentals", "summary": "Quarterly revenue accelerated."},
            ],
            "domainCoverage": [
                {"domain": "technicals", "status": "ready"},
                {"domain": "fundamentals", "status": "ready"},
            ],
        },
        "sourceProvenanceFrame": [
            {
                "sourceId": "fmp",
                "sourceLabel": "FMP Statements",
                "evidenceDomain": "fundamentals",
                "authorityTier": "score_grade",
                "freshnessState": "fresh",
                "sourceTier": "official_public",
                "fallbackOrProxy": False,
                "observationOnly": False,
                "scoreContributionAllowed": True,
            },
            {
                "sourceId": "polygon_us_grouped_daily",
                "sourceLabel": "US grouped daily",
                "evidenceDomain": "market_data",
                "authorityTier": "score_grade",
                "freshnessState": "fresh",
                "sourceTier": "authorized_feed",
                "fallbackOrProxy": False,
                "observationOnly": False,
                "scoreContributionAllowed": True,
            },
        ],
        "dataQualityReport": {"confidenceCap": 1.0, "missingDomains": []},
        "debugRef": "analysis:q-ready",
    }


def _combined_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False).lower()


def test_intelligence_report_packet_helper_is_pure_and_json_safe() -> None:
    imports = _helper_imports()
    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)

    packet = build_intelligence_report_packet_v2(_ready_payload())

    assert json.loads(json.dumps(packet, ensure_ascii=False)) == packet
    assert packet["contractVersion"] == INTELLIGENCE_REPORT_PACKET_VERSION
    assert packet["consumerActionBoundary"] == "no_advice"
    assert packet["noAdviceBoundary"] is True


def test_ready_packet_exposes_required_structured_sections() -> None:
    packet = build_intelligence_report_packet_v2(_ready_payload())

    assert packet["packetState"] == "ready"
    assert set(packet) >= {
        "thesis",
        "evidence",
        "counterEvidence",
        "missingData",
        "confidence",
        "sourceAuthority",
        "freshness",
        "scenarioRisks",
        "nextVerificationSteps",
    }
    assert packet["thesis"]["summary"].startswith("Revenue growth")
    assert packet["confidence"]["highConfidenceAllowed"] is True
    assert packet["confidence"]["cap"] == pytest.approx(1.0)
    assert packet["sourceAuthority"]["state"] == "scoreGradeAllowed"
    assert packet["freshness"]["floor"] == "fresh"
    assert [item["domain"] for item in packet["evidence"]] == ["technicals", "fundamentals"]


def test_unsafe_evidence_cannot_be_promoted_to_high_confidence_conclusion() -> None:
    payload = _ready_payload()
    payload["thesis"] = "Buy now, stop loss below 115 and target price 140."
    payload["researchReadiness"] = {
        **payload["researchReadiness"],
        "researchReady": False,
        "readinessState": "observe_only",
        "blockingReasons": ["observation_only", "stale_evidence", "source_authority_not_score_grade"],
        "missingEvidence": ["source_authority"],
        "evidenceCoverage": {
            "scoreGradeCount": 0,
            "observationOnlyCount": 2,
            "missingCount": 1,
            "totalCount": 3,
        },
        "sourceAuthority": "observationOnly",
        "freshnessFloor": "stale",
        "consumerActionBoundary": "observe_only",
        "nextEvidenceNeeded": ["补充来源授权证据"],
    }
    payload["sourceProvenanceFrame"] = [
        {
            "sourceId": "yfinance_proxy",
            "sourceLabel": "Public proxy",
            "evidenceDomain": "market_data",
            "authorityTier": "observation_only",
            "freshnessState": "stale",
            "sourceTier": "proxy",
            "fallbackOrProxy": True,
            "observationOnly": True,
            "scoreContributionAllowed": False,
        }
    ]
    payload["dataQualityReport"] = {"confidenceCap": 0.9, "missingDomains": ["source_authority"]}

    packet = build_intelligence_report_packet_v2(payload)

    assert packet["packetState"] == "observe_only"
    assert packet["confidence"]["highConfidenceAllowed"] is False
    assert packet["confidence"]["cap"] <= 0.4
    assert "unsafe_conclusion_text_sanitized" in packet["confidence"]["cappedBy"]
    assert "source_authority_not_score_grade" in packet["confidence"]["cappedBy"]
    assert packet["sourceAuthority"]["state"] == "observationOnly"
    assert packet["freshness"]["floor"] == "stale"
    assert packet["missingData"] == ["source_authority"]
    assert all(term not in _combined_text(packet) for term in FORBIDDEN_CONSUMER_TEXT)


def test_missing_data_and_stale_freshness_cap_packet_even_when_score_is_high() -> None:
    payload = _ready_payload()
    payload["researchReadiness"] = {
        **payload["researchReadiness"],
        "researchReady": False,
        "readinessState": "insufficient",
        "blockingReasons": ["missing_required_evidence", "score_cap_active"],
        "missingEvidence": ["news", "freshness"],
        "freshnessFloor": "fallback",
        "nextEvidenceNeeded": ["补充新闻证据", "补充新鲜度证据"],
    }
    payload["dataQualityReport"] = {"confidenceCap": 0.85, "missingDomains": ["news"], "staleSources": ["news"]}

    packet = build_intelligence_report_packet_v2(payload)

    assert packet["packetState"] == "insufficient"
    assert packet["confidence"]["highConfidenceAllowed"] is False
    assert packet["confidence"]["cap"] <= 0.6
    assert "missing_required_evidence" in packet["confidence"]["cappedBy"]
    assert "fallback_freshness" in packet["confidence"]["cappedBy"]
    assert packet["missingData"] == ["news", "freshness"]
    assert packet["nextVerificationSteps"][:2] == ["补充新闻证据", "补充新鲜度证据"]


def test_history_report_schema_hydrates_intelligence_packet_from_analysis_result() -> None:
    packet = build_intelligence_report_packet_v2(_ready_payload())

    report = AnalysisReport.model_validate(
        {
            "meta": {
                "query_id": "q-schema-packet",
                "stock_code": "AAPL",
                "stock_name": "Apple",
                "report_type": "full",
                "created_at": "2026-06-11T00:00:00Z",
            },
            "summary": {
                "analysis_summary": "Observation-only packet.",
                "operation_advice": "Observe only",
                "trend_prediction": "Positive observation",
                "sentiment_score": 61,
            },
            "details": {
                "analysis_result": {
                    "intelligencePacket": packet,
                },
            },
        }
    )

    assert report.intelligencePacket is not None
    assert report.meta.intelligencePacket is not None
    assert report.intelligencePacket.contractVersion == INTELLIGENCE_REPORT_PACKET_VERSION
    assert report.meta.intelligencePacket.packetState == "ready"
