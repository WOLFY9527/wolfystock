# -*- coding: utf-8 -*-
"""Adoption smoke tests for the pure Research Packet v1 helper."""

from __future__ import annotations

import copy
import json
import re
from typing import Any

from src.services.research_packet_v1 import build_research_packet_v1


FORBIDDEN_VISIBLE_PATTERNS = (
    r"\bprovider\b",
    r"\bsource\b",
    r"\bcache\b",
    r"\bdebug\b",
    r"\breason\s*code\b",
    r"\breasoncode\b",
    r"\bbackend\b",
    r"\binternal\b",
    r"\badvice\b",
    r"\braw\b",
    r"\breasonfamilies\b",
    r"\bsourceauthorityallowed\b",
    r"\bscorecontributionallowed\b",
    r"\bsourcetype\b",
    r"\bsourcetier\b",
    r"\bofficial_public\b",
    r"\bauthorized_licensed_feed\b",
    r"\bpublic_proxy\b",
    r"\bunofficial_proxy\b",
    r"\bfallback_static\b",
    r"\bsynthetic_fixture\b",
    r"\bpolygon\b",
    r"\btushare\b",
)
FORBIDDEN_ACTION_PATTERNS = (
    r"\bbuy\b",
    r"\bsell\b",
    r"\bstop(?:[-\s]?loss)?\b",
    r"\btarget\b",
    r"\bposition[-\s]?sizing\b",
    r"\bguaranteed\b",
    "买入",
    "卖出",
    "止损",
    "止盈",
    "目标价",
    "仓位",
    "下单",
    "立即交易",
    "必买",
    "稳赚",
    "保证收益",
)
SNAKE_CASE_PATTERN = re.compile(r"\b[a-z]+_[a-z0-9_]+\b")
SAFE_CONSUMER_STATES = {"AVAILABLE", "UPDATING", "DELAYED", "PARTIAL", "INSUFFICIENT", "PAUSED", "UNAVAILABLE"}
EXPECTED_TOP_LEVEL_FIELDS = {
    "contractVersion",
    "packetIdentity",
    "runtimePosture",
    "lanes",
    "sourceProvenanceSummary",
    "evidenceCitations",
    "dataCoverageRows",
    "redactionPosture",
    "noAdviceBoundary",
    "consumerProjection",
}
EXPECTED_RUNTIME_POSTURE = {
    "diagnosticOnly": True,
    "observationOnly": True,
    "providerRuntimeCalled": False,
    "networkCallsEnabled": False,
    "marketCacheMutation": False,
    "authorityGrant": False,
}
SAFE_CITATION_FIELDS = {"id", "lane", "label", "summary", "asOf"}


def _adoption_sidecars() -> dict[str, Any]:
    return {
        "symbol": "AAPL",
        "market": "us",
        "generatedAt": "2026-06-08T09:30:00Z",
        "asOf": "2026-06-08",
        "reportLanguage": "zh",
        "researchReadiness": {
            "contractVersion": "research_readiness_v1",
            "researchReady": False,
            "readinessState": "observe_only",
            "missingEvidence": ["earnings", "macroLiquidity"],
            "blockingReasons": ["provider_timeout", "partial_cache_hit"],
            "sourceAuthority": "scoreGradeAllowed",
            "freshnessFloor": "fresh",
            "nextEvidenceNeeded": ["补充研究证据"],
        },
        "evidenceCoverageFrame": {
            "priceHistory": {"status": "available", "evidenceRefIds": ["price-ref-1"]},
            "fundamentals": {
                "status": "degraded",
                "missingReasons": ["stale_evidence", "provider_timeout"],
                "evidenceRefIds": ["fundamentals-ref-1"],
            },
            "earnings": {"status": "missing"},
            "news": {"status": "partial", "evidenceRefIds": ["news-ref-1"]},
            "sectorTheme": {"status": "partial", "evidenceRefIds": ["theme-ref-1"]},
            "macroLiquidity": {"status": "degraded", "evidenceRefIds": ["macro-ref-1"]},
        },
        "singleStockEvidencePacket": {
            "contractVersion": "single_stock_evidence_packet_v1",
            "symbol": "AAPL",
            "market": "us",
            "packetState": "degraded",
            "domains": {
                "priceHistory": {
                    "status": "available",
                    "sourceTier": "official_public",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "fresh",
                    "fallbackOrProxy": False,
                    "evidenceCount": 1,
                    "topEvidenceRefs": ["price-ref-1"],
                    "missingReasons": [],
                    "nextEvidenceNeeded": [],
                },
                "fundamentals": {
                    "status": "degraded",
                    "sourceTier": "authorized_licensed_feed",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "stale",
                    "fallbackOrProxy": True,
                    "evidenceCount": 1,
                    "topEvidenceRefs": ["fundamentals-ref-1"],
                    "missingReasons": ["provider_timeout", "fallback_proxy_evidence"],
                    "nextEvidenceNeeded": ["补充基本面证据"],
                },
                "earnings": {
                    "status": "missing",
                    "sourceTier": "unknown",
                    "providerAuthority": "unavailable",
                    "freshness": "unknown",
                    "fallbackOrProxy": False,
                    "evidenceCount": 0,
                    "topEvidenceRefs": [],
                    "missingReasons": ["missing_required_evidence"],
                    "nextEvidenceNeeded": ["补充财报证据"],
                },
                "news": {
                    "status": "partial",
                    "sourceTier": "public_proxy",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "partial",
                    "fallbackOrProxy": True,
                    "evidenceCount": 1,
                    "topEvidenceRefs": ["news-ref-1"],
                    "missingReasons": ["cache_refresh_pending"],
                    "nextEvidenceNeeded": ["补充新闻证据"],
                },
                "catalysts": {
                    "status": "degraded",
                    "sourceTier": "public_proxy",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "stale",
                    "fallbackOrProxy": True,
                    "evidenceCount": 1,
                    "topEvidenceRefs": ["catalyst-ref-1"],
                    "missingReasons": ["provider_timeout"],
                    "nextEvidenceNeeded": ["补充催化剂证据"],
                },
                "sectorTheme": {
                    "status": "partial",
                    "sourceTier": "official_public",
                    "providerAuthority": "observationOnly",
                    "freshness": "unknown",
                    "fallbackOrProxy": False,
                    "evidenceCount": 1,
                    "topEvidenceRefs": ["theme-ref-1"],
                    "missingReasons": ["debug_context_only"],
                    "nextEvidenceNeeded": ["补充行业主题证据"],
                },
                "macroLiquidity": {
                    "status": "degraded",
                    "sourceTier": "fallback_static",
                    "providerAuthority": "observationOnly",
                    "freshness": "fallback",
                    "fallbackOrProxy": True,
                    "evidenceCount": 1,
                    "topEvidenceRefs": ["macro-ref-1"],
                    "missingReasons": ["provider_timeout", "fallback_static"],
                    "nextEvidenceNeeded": ["补充宏观流动性证据"],
                },
            },
        },
        "evidenceCitationFrame": {
            "contractVersion": "home_report_evidence_citation_frame_v1",
            "frameState": "observe_only",
            "citedEvidence": [
                {
                    "id": "fundamentals-citation-1",
                    "domain": "fundamentals",
                    "label": "基本面更新",
                    "summary": "provider cache debug reasonCode backend internal_advice",
                    "sourceId": "Polygon",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "stale",
                    "asOf": "2026-06-08",
                    "limitation": "raw trace payload",
                },
                {
                    "id": "news-citation-1",
                    "domain": "news",
                    "label": "新闻观察",
                    "summary": "partial context with provider_timeout",
                    "sourceId": "Tushare",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "partial",
                    "asOf": "2026-06-08",
                },
            ],
            "domainCoverage": [
                {"domain": "fundamentals", "status": "degraded", "evidenceRefIds": ["fundamentals-citation-1"]},
                {"domain": "news", "status": "partial", "evidenceRefIds": ["news-citation-1"]},
            ],
        },
        "sourceProvenanceFrame": [
            {
                "contractVersion": "source_provenance_v1",
                "sourceId": "fundamentals-fallback",
                "sourceLabel": "Polygon",
                "evidenceDomain": "fundamentals",
                "authorityTier": "score_grade",
                "freshnessState": "fallback",
                "sourceTier": "authorized_licensed_feed",
                "fallbackOrProxy": True,
                "observationOnly": False,
                "scoreContributionAllowed": True,
                "sourceAuthorityAllowed": True,
                "limitations": ["provider_timeout", "cache_key=abc"],
                "nextEvidenceNeeded": ["补充基本面证据"],
                "debugRef": "trace:fundamentals",
            },
            {
                "contractVersion": "source_provenance_v1",
                "sourceId": "macro-fallback",
                "sourceLabel": "Tushare",
                "evidenceDomain": "macroLiquidity",
                "authorityTier": "score_grade",
                "freshnessState": "fallback",
                "sourceTier": "fallback_static",
                "fallbackOrProxy": True,
                "observationOnly": False,
                "scoreContributionAllowed": True,
                "sourceAuthorityAllowed": True,
                "limitations": ["backend_reason=provider_timeout"],
                "nextEvidenceNeeded": ["补充宏观流动性证据"],
                "debugRef": "trace:macro",
            },
        ],
        "dataCoverageRows": [
            {
                "surfaceId": "single_stock",
                "fieldKey": "fundamental_context",
                "evidenceFamily": "fundamentals",
                "freshnessState": "stale",
                "rightToDisplay": "granted",
                "isStale": True,
                "isPartial": True,
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "authorityGrant": True,
                "decisionGrade": True,
                "observationOnly": False,
                "providerId": "polygon",
                "sourceType": "authorized_licensed_feed",
            },
            {
                "surfaceId": "single_stock",
                "fieldKey": "news_context",
                "evidenceFamily": "newsCatalysts",
                "freshnessState": "partial",
                "rightToDisplay": "granted",
                "isPartial": True,
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "authorityGrant": True,
                "decisionGrade": True,
                "observationOnly": False,
                "providerId": "tushare",
                "sourceType": "public_proxy",
            },
            {
                "surfaceId": "single_stock",
                "fieldKey": "sector_theme_context",
                "evidenceFamily": "sectorTheme",
                "freshnessState": "unknown",
                "rightToDisplay": "granted",
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "authorityGrant": True,
                "decisionGrade": True,
                "observationOnly": False,
                "providerId": "polygon",
                "sourceType": "official_public",
            },
            {
                "surfaceId": "single_stock",
                "fieldKey": "macro_liquidity_context",
                "evidenceFamily": "macroLiquidity",
                "freshnessState": "fallback",
                "rightToDisplay": "granted",
                "isPartial": True,
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "authorityGrant": True,
                "decisionGrade": True,
                "observationOnly": False,
                "providerId": "tushare",
                "sourceType": "fallback_static",
            },
        ],
    }


def _visible_strings(value: Any) -> list[str]:
    strings: list[str] = []
    if isinstance(value, str):
        strings.append(value)
    elif isinstance(value, dict):
        for nested in value.values():
            strings.extend(_visible_strings(nested))
    elif isinstance(value, list):
        for nested in value:
            strings.extend(_visible_strings(nested))
    return strings


def test_build_research_packet_v1_adopts_sidecars_without_authority_escalation() -> None:
    packet = build_research_packet_v1(_adoption_sidecars())

    assert set(packet) == EXPECTED_TOP_LEVEL_FIELDS
    assert packet["runtimePosture"] == EXPECTED_RUNTIME_POSTURE
    assert packet["sourceProvenanceSummary"]["observationOnly"] is True
    assert packet["sourceProvenanceSummary"]["authorityGrant"] is False
    assert packet["noAdviceBoundary"]["analysisOnly"] is True
    assert packet["noAdviceBoundary"]["personalizedAdviceAllowed"] is False
    assert packet["noAdviceBoundary"]["actionableInstructionAllowed"] is False

    affected_lanes = {
        "fundamentals": packet["lanes"]["fundamentals"],
        "earnings": packet["lanes"]["earnings"],
        "newsCatalysts": packet["lanes"]["newsCatalysts"],
        "sectorTheme": packet["lanes"]["sectorTheme"],
        "macroLiquidity": packet["lanes"]["macroLiquidity"],
    }
    assert affected_lanes["fundamentals"]["freshness"] == "fallback"
    assert affected_lanes["earnings"]["freshness"] == "unknown"
    assert affected_lanes["newsCatalysts"]["freshness"] == "stale"
    assert affected_lanes["sectorTheme"]["freshness"] == "unknown"
    assert affected_lanes["macroLiquidity"]["freshness"] == "fallback"

    for lane_name, lane in affected_lanes.items():
        assert lane["rightToDisplay"] != "granted", lane_name
        assert lane["consumerState"] != "AVAILABLE", lane_name
        assert lane["status"] != "available", lane_name

    assert packet["consumerProjection"]["status"] != "AVAILABLE"
    assert set(item["state"] for item in packet["consumerProjection"]["lanes"]) <= SAFE_CONSUMER_STATES
    assert "trust" not in json.dumps(packet["consumerProjection"], ensure_ascii=False, sort_keys=True).lower()
    assert "badge" not in json.dumps(packet["consumerProjection"], ensure_ascii=False, sort_keys=True).lower()

    sanitized_rows = {row["lane"]: row for row in packet["dataCoverageRows"]}
    assert sanitized_rows["fundamentals"]["freshness"] == "stale"
    assert sanitized_rows["newsCatalysts"]["freshness"] == "partial"
    assert sanitized_rows["sectorTheme"]["freshness"] == "unknown"
    assert sanitized_rows["macroLiquidity"]["freshness"] == "fallback"
    for lane_name in ("fundamentals", "newsCatalysts", "sectorTheme", "macroLiquidity"):
        row = sanitized_rows[lane_name]
        assert row["observationOnly"] is True
        assert row["rightToDisplay"] in {"limited", "unavailable"}
        assert row["consumerState"] != "AVAILABLE"
        assert "authorityGrant" not in row
        assert "decisionGrade" not in row
        assert "sourceAuthorityAllowed" not in row
        assert "scoreContributionAllowed" not in row
        assert "providerId" not in row
        assert "sourceType" not in row

    for citation in packet["evidenceCitations"]:
        assert set(citation) <= SAFE_CITATION_FIELDS


def test_build_research_packet_v1_redacts_visible_runtime_and_internal_vocabulary() -> None:
    packet = build_research_packet_v1(_adoption_sidecars())

    visible_payload = {
        "consumerProjection": packet["consumerProjection"],
        "evidenceCitations": packet["evidenceCitations"],
        "dataCoverageRows": packet["dataCoverageRows"],
        "laneMessages": {
            lane_name: {
                "limitations": lane["limitations"],
                "nextEvidenceNeeded": lane["nextEvidenceNeeded"],
            }
            for lane_name, lane in packet["lanes"].items()
        },
        "noAdviceSummary": packet["noAdviceBoundary"]["summary"],
    }
    visible_text = " ".join(_visible_strings(visible_payload)).lower()

    for pattern in (*FORBIDDEN_VISIBLE_PATTERNS, *FORBIDDEN_ACTION_PATTERNS):
        assert re.search(pattern, visible_text) is None
    assert SNAKE_CASE_PATTERN.search(visible_text) is None

    serialized_citations = json.dumps(packet["evidenceCitations"], ensure_ascii=False, sort_keys=True).lower()
    for forbidden in ("sourceid", "providerauthority", "sourcetier", "reasoncode", "provider_timeout"):
        assert forbidden not in serialized_citations


def test_build_research_packet_v1_adoption_output_is_deterministic_json_safe_and_non_mutating() -> None:
    sidecars = _adoption_sidecars()
    original = copy.deepcopy(sidecars)

    first = build_research_packet_v1(sidecars)
    second = build_research_packet_v1(copy.deepcopy(sidecars))

    assert sidecars == original
    assert first == second

    encoded = json.dumps(first, ensure_ascii=False, sort_keys=True)
    assert json.loads(encoded) == first
