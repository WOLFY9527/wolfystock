# -*- coding: utf-8 -*-
"""Tests for consumer-safe issue label normalization."""

from __future__ import annotations

import json
import re
from typing import Any

from src.services.consumer_issue_labels import build_consumer_issues, build_consumer_message


RAW_CODES = (
    "freshness_blocked:fallback",
    "freshness_blocked:unavailable",
    "proxy_or_sample_evidence_blocked",
    "source_authority_or_score_gate_blocked",
    "live_gex_not_implemented_v1",
    "option_chain_unavailable",
    "observation_only_not_decision_grade",
    "observation_only_evidence_blocked",
    "event_evidence_missing",
    "missing_spot_reference",
    "missing_contracts",
    "insufficient_usable_contracts",
    "methodology_approval_missing",
    "provider_authority_missing",
    "redistribution_rights_missing",
    "decision_use_rights_missing",
    "deliverable_handling_missing",
    "coverage_thresholds_missing",
    "limited_source_quality_present",
    "non_score_grade_freshness_present",
    "observation_only_evidence_present",
    "proxy_or_sample_evidence_present",
    "research_candidates_unavailable",
    "avoidLowEvidence",
    "low_liquidity",
    "missing_evidence",
    "fundamentals",
    "news",
    "catalyst",
    "freshness",
)
FORBIDDEN_ADVICE_RE = re.compile(
    r"\b(buy|sell|hold|recommendation|target|stop|position\s*sizing)\b|买入|卖出|持有|目标价|止损|仓位",
    re.IGNORECASE,
)
INTERNAL_CODE_RE = re.compile(r"[a-z][a-z0-9]*_[a-z0-9_]+|[a-zA-Z]+:[a-zA-Z0-9_.-]+|=")


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result: list[str] = []
        for nested in value.values():
            result.extend(_strings(nested))
        return result
    if isinstance(value, (list, tuple)):
        result = []
        for nested in value:
            result.extend(_strings(nested))
        return result
    return []


def test_known_raw_codes_map_to_consumer_safe_issue_labels_without_echoing_codes() -> None:
    issues = build_consumer_issues(RAW_CODES)

    labels = {issue["label"] for issue in issues}
    assert "Freshness is limited" in labels
    assert "Options gamma unavailable" in labels
    assert "Options chain unavailable" in labels
    assert "Research candidates unavailable" in labels
    assert "Low-evidence filter active" in labels
    assert "Fundamental evidence missing" in labels

    serialized = json.dumps(issues, ensure_ascii=False).lower()
    for raw_code in RAW_CODES:
        if INTERNAL_CODE_RE.search(raw_code) or raw_code != raw_code.lower():
            assert raw_code.lower() not in serialized
    for text in _strings(issues):
        assert INTERNAL_CODE_RE.search(text) is None
        assert FORBIDDEN_ADVICE_RE.search(text) is None


def test_unknown_internal_looking_code_uses_generic_consumer_copy() -> None:
    issues = build_consumer_issues(["provider_runtime:error=timeout", "source_authority_unknown"])

    assert issues == [
        {
            "label": "Evidence needs review",
            "message": "Some quality checks are not fully cleared yet.",
            "severity": "info",
            "category": "evidence",
        }
    ]
    serialized = json.dumps(issues, ensure_ascii=False).lower()
    assert "provider_runtime" not in serialized
    assert "source_authority_unknown" not in serialized
    for text in _strings(issues):
        assert ":" not in text
        assert "=" not in text


def test_consumer_message_summarizes_safe_labels_without_advice_language() -> None:
    issues = build_consumer_issues(["missing_contracts", "low_liquidity"])
    message = build_consumer_message(issues)

    assert message == "Option contracts missing; Liquidity is limited."
    assert FORBIDDEN_ADVICE_RE.search(message) is None
    assert INTERNAL_CODE_RE.search(message) is None
