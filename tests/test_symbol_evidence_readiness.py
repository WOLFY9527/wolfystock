# -*- coding: utf-8 -*-
"""Focused contracts for the symbol evidence readiness projector."""

from __future__ import annotations

import json

from src.services.symbol_evidence_readiness import build_symbol_evidence_readiness


def _complete_item() -> dict:
    return {
        "symbol": "AAPL",
        "quote": {
            "status": "available",
            "price": 190.12,
            "sourceType": "live",
            "freshness": "fresh",
        },
        "technical": {
            "status": "available",
            "trend": "bullish",
            "ma20": 184.2,
            "rsi14": 58.1,
        },
        "fundamental": {
            "status": "available",
            "marketCap": 2800000000000,
            "peTtm": 28.5,
            "missingFields": [],
        },
        "news": {
            "status": "available",
            "latestHeadline": "Apple expands supply agreement",
            "provider": "news_cache",
        },
    }


def test_symbol_evidence_readiness_marks_clean_complete_evidence_sufficient() -> None:
    readiness = build_symbol_evidence_readiness(_complete_item())

    assert readiness == {
        "symbolEvidenceReadiness": True,
        "symbol": "AAPL",
        "readinessTier": "sufficient",
        "evidenceUsed": ["quote", "technical", "fundamental", "news"],
        "evidenceMissing": [],
        "staleInputs": [],
        "conflictingEvidence": [],
        "dataQualityNotes": [
            "Core quote, technical, fundamental, and news evidence are present without stale markers."
        ],
        "suggestedResearchPath": [
            "Continue by reviewing quote, technical, fundamental, and news evidence together.",
            "Keep any downstream thesis work separate from trading instructions.",
        ],
        "observationOnly": True,
        "noAdviceDisclosure": "Observation-only research readiness; not personalized financial advice or an instruction.",
    }


def test_symbol_evidence_readiness_marks_partial_without_fabricating_missing_news() -> None:
    item = _complete_item()
    item["quote"]["freshness"] = "stale"
    item["technical"] = {"status": "missing"}
    item["fundamental"] = {
        "status": "partial",
        "marketCap": 1234,
        "missingFields": ["peTtm", "fcfTtm"],
    }
    item["news"] = {"status": "unknown", "latestHeadline": None, "provider": None}

    readiness = build_symbol_evidence_readiness(item)

    assert readiness["readinessTier"] == "partial"
    assert readiness["evidenceUsed"] == ["quote", "fundamental"]
    assert readiness["evidenceMissing"] == ["technical", "fundamental", "news"]
    assert readiness["staleInputs"] == ["quote"]
    assert readiness["suggestedResearchPath"] == [
        "Add recent OHLC or technical context.",
        "Add fundamental coverage before business-quality review.",
        "Add recent news or filing context before catalyst review.",
        "Refresh stale or delayed inputs before comparing research scenarios.",
    ]


def test_symbol_evidence_readiness_fails_closed_for_sparse_evidence_and_redacts_raw_detail() -> None:
    item = {
        "symbol": "orcl",
        "quote": {
            "status": "unknown",
            "provider": "must-not-emit",
            "rawPayload": {"token": "must-not-emit"},
        },
        "technical": {"status": "missing", "debug": "must-not-emit"},
        "fundamental": {"status": "missing", "reasonCode": "must-not-emit"},
        "news": {"status": "unknown", "latestHeadline": "No recent headlines available"},
        "secFilingEvidence": {
            "status": "available",
            "providerId": "sec_edgar",
            "records": [{"accessionNumber": "must-not-emit"}],
            "rawPayloadStored": False,
        },
    }

    readiness = build_symbol_evidence_readiness(item)

    assert readiness["symbol"] == "ORCL"
    assert readiness["readinessTier"] == "insufficient"
    assert readiness["evidenceUsed"] == ["secFilingEvidence"]
    assert readiness["evidenceMissing"] == ["quote", "technical", "fundamental", "news"]
    serialized = json.dumps(readiness, sort_keys=True)
    for forbidden in (
        "must-not-emit",
        "rawPayload",
        "reasonCode",
        "debug",
        "providerId",
        "accessionNumber",
    ):
        assert forbidden not in serialized
    for forbidden in ("buy", "sell", "target price", "stop loss", "position sizing"):
        assert forbidden not in serialized.lower()
