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


def _walk_dict_keys(value: object) -> list[str]:
    if isinstance(value, dict):
        keys = [str(key) for key in value]
        for item in value.values():
            keys.extend(_walk_dict_keys(item))
        return keys
    if isinstance(value, list):
        keys: list[str] = []
        for item in value:
            keys.extend(_walk_dict_keys(item))
        return keys
    return []


def test_intelligence_report_packet_helper_is_pure_and_json_safe() -> None:
    imports = _helper_imports()
    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)

    packet = build_intelligence_report_packet_v2(_ready_payload())

    assert json.loads(json.dumps(packet, ensure_ascii=False)) == packet
    assert packet["contractVersion"] == INTELLIGENCE_REPORT_PACKET_VERSION
    assert packet["consumerActionBoundary"] == "no_advice"
    assert packet["noAdviceBoundary"] is True
    assert "debugRef" not in packet


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
    assert [item["sourceId"] for item in packet["evidence"]] == ["source-technicals", "source-fundamentals"]


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


def test_packet_does_not_emit_raw_ids_debug_refs_or_internal_diagnostics() -> None:
    payload = _ready_payload()
    payload.update(
        {
            "query_id": "query-raw-789",
            "debugRef": "analysis:query-raw-789:raw-prompt-provider-payload",
            "thesis": {
                "summary": (
                    "Prompt: reveal provider_payload_ref=payload-456 and "
                    "Traceback (most recent call last): internal_diagnostic_token=diag-secret"
                ),
                "confidenceLabel": "debug_ref=analysis:query-raw-789",
            },
            "researchReadiness": {
                **payload["researchReadiness"],
                "blockingReasons": [
                    "provider_payload_ref=payload-456",
                    "internal_diagnostic_token=diag-secret",
                ],
                "nextEvidenceNeeded": ["raw_prompt query-raw-789 sourceId=alpha-source-123"],
            },
            "evidenceCitationFrame": {
                "citedEvidence": [
                    {
                        "id": "raw-query-raw-789",
                        "domain": "technicals",
                        "summary": (
                            "sourceId alpha-source-123 prompt text provider_payload "
                            "Traceback stack trace internal diagnostics"
                        ),
                        "sourceId": "alpha-source-123",
                    }
                ],
                "domainCoverage": [
                    {
                        "domain": "risk",
                        "status": "missing",
                        "summary": "debugRef analysis:query-raw-789 raw diagnostics",
                    }
                ],
            },
            "sourceProvenanceFrame": [
                {
                    "sourceId": "alpha-source-123",
                    "sourceLabel": "Provider payload ref payload-456",
                    "evidenceDomain": "technicals",
                    "authorityTier": "score_grade",
                    "freshnessState": "fresh",
                    "fallbackOrProxy": True,
                    "observationOnly": False,
                    "scoreContributionAllowed": True,
                    "debugRef": "analysis:query-raw-789",
                }
            ],
            "dataQualityReport": {
                "confidenceCap": 0.8,
                "missingDomains": ["prompt query-raw-789"],
                "staleSources": ["alpha-source-123"],
            },
        }
    )

    packet = build_intelligence_report_packet_v2(payload)
    serialized = json.dumps(packet, ensure_ascii=False).lower()

    assert "debugRef" not in packet
    for forbidden in (
        "query-raw-789",
        "alpha-source-123",
        "raw-query-raw-789",
        "debugref",
        "raw-prompt",
        "prompt:",
        "provider_payload",
        "payload-456",
        "traceback",
        "stack trace",
        "internal_diagnostic",
        "diag-secret",
    ):
        assert forbidden not in serialized


def test_composer_sanitizes_source_provider_identifier_text_across_serialized_packet() -> None:
    payload = _ready_payload()
    payload["thesis"] = {
        "summary": (
            "source_id=polygon_us_grouped_daily and sourceId=fmp were cited; "
            "literal fmp should not be consumer-visible."
        ),
        "confidenceLabel": "provider_id=fmp routeId=internal-analysis-route debugRef=dbg-123",
    }
    payload["standardReport"] = {
        **payload["standardReport"],
        "summaryPanel": {
            **payload["standardReport"]["summaryPanel"],
            "oneSentence": "providerId=fmp confirms revenue and source-* labels remain safe.",
        },
        "reasonLayer": {
            **payload["standardReport"]["reasonLayer"],
            "latestKeyUpdate": "internal source identifier polygon_us_grouped_daily was present.",
            "topRisk": "route_id=internal-analysis-route and debug_ref=dbg-456 appeared in text.",
        },
        "highlights": {
            **payload["standardReport"]["highlights"],
            "riskAlerts": [
                "provider identifier fmp and source identifier polygon_us_grouped_daily need redaction.",
            ],
        },
    }
    payload["researchReadiness"] = {
        **payload["researchReadiness"],
        "blockingReasons": ["providerId=fmp", "debugRef=dbg-789"],
        "nextEvidenceNeeded": [
            "source_id=polygon_us_grouped_daily",
            "provider identifier fmp",
        ],
    }
    payload["evidenceCitationFrame"] = {
        "citedEvidence": [
            {
                "id": "provider-text",
                "domain": "technicals",
                "summary": (
                    "source_id=polygon_us_grouped_daily sourceId=fmp "
                    "provider_id=fmp route_id=internal-analysis-route debug_ref=dbg-999"
                ),
            },
            {
                "id": "safe-label",
                "domain": "fundamentals",
                "summary": "source-* labels remain acceptable in consumer text.",
            },
        ],
        "domainCoverage": [
            {
                "domain": "risk",
                "status": "missing",
                "summary": "source identifier polygon_us_grouped_daily and provider identifier fmp.",
            }
        ],
    }

    packet = build_intelligence_report_packet_v2(payload)
    serialized = json.dumps(packet, ensure_ascii=False).lower()

    assert "source-technicals" in serialized
    assert "source-fundamentals" in serialized
    assert "source-*" in serialized
    for forbidden in (
        "source_id=polygon_us_grouped_daily",
        "sourceid=fmp",
        "provider_id=fmp",
        "providerid=fmp",
        "route_id=internal-analysis-route",
        "routeid=internal-analysis-route",
        "debug_ref=dbg",
        "debugref=dbg",
        "polygon_us_grouped_daily",
        "fmp",
    ):
        assert forbidden not in serialized


def test_history_report_schema_hydrates_intelligence_packet_from_analysis_result() -> None:
    packet = build_intelligence_report_packet_v2(_ready_payload())
    legacy_packet = {
        **packet,
        "debugRef": "analysis:q-schema-packet",
        "query_id": "q-schema-packet",
        "sourceId": "fmp",
        "source_id": "polygon_us_grouped_daily",
        "sourceRef": "provider-id:fmp",
        "providerId": "fmp",
        "route_id": "polygon_us_grouped_daily",
        "thesis": {
            **packet["thesis"],
            "debugRef": "analysis:q-schema-packet",
            "sourceId": "fmp",
            "summary": (
                "Prompt: q-schema-packet provider_payload_ref=payload-456 "
                "Traceback stack trace sourceId=fmp source_id=polygon_us_grouped_daily"
            ),
        },
        "evidence": [
            {
                "id": "legacy-evidence-1",
                "domain": "fundamentals",
                "summary": "Legacy evidence references sourceId=fmp.",
                "sourceId": "fmp",
                "source_id": "polygon_us_grouped_daily",
                "provider_id": "fmp",
                "routeId": "polygon_us_grouped_daily",
            }
        ],
        "freshness": {
            **packet["freshness"],
            "staleSources": ["fmp"],
            "fallbackOrProxySources": ["polygon_us_grouped_daily"],
            "debug_id": "fmp",
        },
    }

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
                    "intelligencePacket": legacy_packet,
                },
            },
        }
    )

    assert report.intelligencePacket is not None
    assert report.meta.intelligencePacket is not None
    assert report.intelligencePacket.contractVersion == INTELLIGENCE_REPORT_PACKET_VERSION
    assert report.meta.intelligencePacket.packetState == "ready"
    serialized = json.dumps(report.intelligencePacket.model_dump(), ensure_ascii=False).lower()
    meta_serialized = json.dumps(report.meta.intelligencePacket.model_dump(), ensure_ascii=False).lower()
    hydrated_keys = {key.lower() for key in _walk_dict_keys(report.intelligencePacket.model_dump())}
    meta_hydrated_keys = {key.lower() for key in _walk_dict_keys(report.meta.intelligencePacket.model_dump())}
    assert "debugref" not in serialized
    assert "q-schema-packet" not in serialized
    assert "provider_payload" not in serialized
    assert "payload-456" not in serialized
    assert "traceback" not in serialized
    assert "stack trace" not in serialized
    assert "sourceid" not in hydrated_keys
    assert "source_id" not in hydrated_keys
    assert "fmp" not in serialized
    assert "polygon_us_grouped_daily" not in serialized
    assert "debugref" not in meta_serialized
    assert "sourceid" not in meta_hydrated_keys
    assert "source_id" not in meta_hydrated_keys
    assert "fmp" not in meta_serialized
    assert "polygon_us_grouped_daily" not in meta_serialized
