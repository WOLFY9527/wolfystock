# -*- coding: utf-8 -*-
"""Tests for research gap prioritization."""

from __future__ import annotations

import copy
import json
import re
from typing import Any

from src.services.research_gap_prioritizer import prioritize_research_gaps


FORBIDDEN_RAW_RE = re.compile(
    r"_blocked|_gate|freshness_blocked|source_authority|score_gate|"
    r"sourceRefs|reasonCodes|sourceRefId|rawCode|provider_runtime|"
    r"alpha_router_rejected|buy now|sell now|target price|stop loss",
    re.IGNORECASE,
)
FORBIDDEN_ADVICE_RE = re.compile(
    r"\b(buy|sell|hold|recommendation|target|stop|position\s*sizing)\b|"
    r"买入|卖出|持有|目标价|止损|仓位",
    re.IGNORECASE,
)


def _serialized(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def test_prioritizes_blocking_source_gaps_before_stale_context_gaps() -> None:
    packet = {
        "missingEvidence": [
            "freshness_blocked:fallback",
            "source_authority_or_score_gate_blocked",
            "watchlist_research_context",
        ],
        "candidateResearchReadiness": {
            "missingEvidence": ["local_ohlcv_evidence"],
            "nextEvidenceNeeded": ["Refresh local price history before raising confidence."],
        },
        "dataQuality": {
            "status": "partial",
            "confidenceCapReasons": ["proxy_or_sample_evidence_blocked"],
        },
        "sourceRefs": [{"id": "raw-provider-ref"}],
        "reasonCodes": ["score_gate"],
    }

    result = prioritize_research_gaps(packet)

    gaps = result["prioritizedResearchGaps"]
    assert gaps
    assert gaps[0]["safeGapLabel"] == "当前数据源权威性或评分级别不足，暂不能形成可靠研究结论"
    assert gaps[0]["gapFamily"] == "evidence"
    assert gaps[0]["impactOnResearchQuality"] == "critical"
    assert gaps[0]["blockingLevel"] == "blocking"
    assert gaps[0]["observationOnly"] is True

    for gap in gaps:
        assert set(gap) == {
            "gapId",
            "gapFamily",
            "safeGapLabel",
            "impactOnResearchQuality",
            "blockingLevel",
            "suggestedVerificationStep",
            "staleOrMissingReason",
            "observationOnly",
        }
        assert gap["gapId"].startswith("gap-")
        assert gap["suggestedVerificationStep"]
        assert gap["staleOrMissingReason"]

    serialized = _serialized(result)
    assert FORBIDDEN_RAW_RE.search(serialized) is None
    assert FORBIDDEN_ADVICE_RE.search(serialized) is None


def test_collects_overlay_and_symbol_packet_gaps_without_mutating_input() -> None:
    packet = {
        "items": [
            {
                "ticker": "AAPL",
                "evidenceGaps": ["Local price history missing", "fresh_evidence"],
                "freshness": {"state": "stale_or_cached"},
                "consumerIssues": [{"label": "Local price history missing"}],
            },
            {
                "symbol": "MSFT",
                "candidateResearchSummaryFrame": {
                    "missingEvidence": ["scanner_score_evidence", "local_ohlcv_evidence"],
                },
                "consumerDiagnostics": {
                    "missingEvidence": ["scanner_score_evidence"],
                },
            },
        ],
        "symbolPacket": {
            "researchReadiness": {
                "readinessState": "blocked",
                "missingEvidence": ["fundamentals", "news"],
            }
        },
    }
    before = copy.deepcopy(packet)

    result = prioritize_research_gaps(packet, limit=4)

    assert packet == before
    gaps = result["prioritizedResearchGaps"]
    assert len(gaps) == 4
    labels = [gap["safeGapLabel"] for gap in gaps]
    assert "Local price history missing" in labels or "Local price history missing".title() in labels
    assert len({gap["gapId"] for gap in gaps}) == len(gaps)
    assert all(gap["observationOnly"] is True for gap in gaps)


def test_unknown_internal_codes_and_advice_like_text_are_redacted_to_safe_copy() -> None:
    packet = {
        "missingEvidence": [
            "alpha_router_rejected:missing_v2",
            "_blocked",
            "sourceRefs",
            "buy now",
        ],
        "dataQuality": {
            "reasonCodes": ["provider_runtime:error=timeout"],
        },
    }

    result = prioritize_research_gaps(packet)

    assert result["prioritizedResearchGaps"] == [
        {
            "gapId": result["prioritizedResearchGaps"][0]["gapId"],
            "gapFamily": "evidence",
            "safeGapLabel": "Evidence needs review",
            "impactOnResearchQuality": "medium",
            "blockingLevel": "moderate",
            "suggestedVerificationStep": "Verify the missing supporting evidence before raising research confidence.",
            "staleOrMissingReason": "Supporting evidence is missing, stale, or not strong enough.",
            "observationOnly": True,
        }
    ]
    assert FORBIDDEN_RAW_RE.search(_serialized(result)) is None
    assert FORBIDDEN_ADVICE_RE.search(_serialized(result)) is None


def test_nested_reason_families_project_to_safe_gap_labels() -> None:
    packet = {
        "evidenceSnapshot": {
            "reasonFamilies": [
                {
                    "rawCode": "source_authority_blocked",
                    "family": "source_authority_blocked",
                    "scope": "score_gate",
                    "sourceField": "sourceAuthorityAllowed",
                }
            ],
            "sourceAuthorityAllowed": False,
        }
    }

    result = prioritize_research_gaps(packet)

    assert result["prioritizedResearchGaps"][0]["safeGapLabel"] == "证据来源级别不足"
    serialized = _serialized(result)
    assert "sourceAuthorityAllowed" not in serialized
    assert FORBIDDEN_RAW_RE.search(serialized) is None
