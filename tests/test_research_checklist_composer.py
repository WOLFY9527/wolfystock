# -*- coding: utf-8 -*-
"""Focused tests for the standalone research checklist composer."""

from __future__ import annotations

import copy
import json

from src.services.research_checklist_composer import compose_research_checklist


EXPECTED_TOP_LEVEL_KEYS = ["researchChecklist"]
EXPECTED_ITEM_KEYS = [
    "checklistItemId",
    "evidenceGap",
    "whyItMatters",
    "suggestedResearchStep",
    "priorityTier",
    "blockingStatus",
    "observationOnly",
]
FORBIDDEN_OUTPUT_TERMS = (
    "buy",
    "sell",
    "hold",
    "recommend",
    "target",
    "stop",
    "position sizing",
    "provider",
    "fallback",
    "raw",
    "debug",
    "traceback",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "diagnostic",
    "http://",
    "https://",
    "/users/",
    "api_key",
    "secret",
    "token",
    "cookie",
)


def _serialized(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def test_composes_research_checklist_from_evidence_gaps() -> None:
    payload = compose_research_checklist(
        [
            {
                "evidenceGap": "fresh_evidence",
                "priorityTier": "medium",
                "blockingStatus": "non_blocking",
            },
            {
                "evidenceGap": "provider_timeout",
                "priorityTier": "critical",
                "blockingStatus": "blocking",
                "whyItMatters": "debug provider raw payload",
                "suggestedResearchStep": "open internal diagnostics",
            },
        ]
    )

    assert list(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert [list(item.keys()) for item in payload["researchChecklist"]] == [
        EXPECTED_ITEM_KEYS,
        EXPECTED_ITEM_KEYS,
    ]
    assert payload["researchChecklist"] == [
        {
            "checklistItemId": "research-checklist-evidence-availability",
            "evidenceGap": "Evidence availability needs review.",
            "whyItMatters": "The research context cannot support higher confidence until this evidence path is checked.",
            "suggestedResearchStep": "Check the relevant evidence path and confirm whether the gap is resolved.",
            "priorityTier": "high",
            "blockingStatus": "blocking",
            "observationOnly": True,
        },
        {
            "checklistItemId": "research-checklist-evidence-freshness",
            "evidenceGap": "Evidence freshness is not confirmed.",
            "whyItMatters": "Delayed or stale context can make the next review less reliable.",
            "suggestedResearchStep": "Confirm the latest review time and compare it with the current research window.",
            "priorityTier": "medium",
            "blockingStatus": "non_blocking",
            "observationOnly": True,
        },
    ]


def test_composer_accepts_string_gaps_and_deduplicates_stable_ids() -> None:
    payload = compose_research_checklist(
        [
            "scanner_score_evidence",
            {"evidenceGap": "scanner_score_evidence", "priorityTier": "low"},
            "local_ohlcv_evidence",
        ]
    )

    assert [item["checklistItemId"] for item in payload["researchChecklist"]] == [
        "research-checklist-price-history-evidence",
        "research-checklist-scoring-evidence",
    ]
    assert [item["priorityTier"] for item in payload["researchChecklist"]] == [
        "high",
        "medium",
    ]
    assert all(item["observationOnly"] is True for item in payload["researchChecklist"])


def test_composer_does_not_mutate_inputs() -> None:
    gaps = [
        {
            "evidenceGap": "watchlist_research_context",
            "whyItMatters": "Review context is missing.",
            "suggestedResearchStep": "Review the research note attached to this context.",
            "priorityTier": "low",
        }
    ]
    original = copy.deepcopy(gaps)

    compose_research_checklist(gaps)

    assert gaps == original


def test_composer_excludes_advice_and_raw_diagnostic_terms_from_output() -> None:
    payload = compose_research_checklist(
        [
            {
                "evidenceGap": "source_confidence",
                "whyItMatters": "traceback trustLevel sourceType raw diagnostics",
                "suggestedResearchStep": "open http://internal.example.test/users/me with api_key",
                "priorityTier": "attention",
            }
        ]
    )

    serialized = _serialized(payload)
    leaked = [term for term in FORBIDDEN_OUTPUT_TERMS if term in serialized]

    assert leaked == []
    assert payload["researchChecklist"][0] == {
        "checklistItemId": "research-checklist-evidence-confidence",
        "evidenceGap": "Evidence confidence context needs review.",
        "whyItMatters": "The research context cannot support higher confidence until this evidence path is checked.",
        "suggestedResearchStep": "Check the relevant evidence path and confirm whether the gap is resolved.",
        "priorityTier": "high",
        "blockingStatus": "blocking",
        "observationOnly": True,
    }


def test_composer_returns_empty_checklist_for_missing_gaps() -> None:
    assert compose_research_checklist(None) == {"researchChecklist": []}
    assert compose_research_checklist([]) == {"researchChecklist": []}
