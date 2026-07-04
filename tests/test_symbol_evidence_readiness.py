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
            "核心行情、技术面、基本面与新闻资讯证据已返回，未见过期标记。"
        ],
        "suggestedResearchPath": [
            "继续一起复核行情、技术面、基本面与新闻资讯证据。",
            "后续研究假设继续与交易指令保持分离。",
        ],
        "observationOnly": True,
        "noAdviceDisclosure": "仅供研究观察，不构成个性化行动指令。",
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
    assert "待补证据类别：技术面、基本面、新闻资讯。" in readiness["dataQualityNotes"]
    assert readiness["staleInputs"] == ["quote"]
    assert readiness["suggestedResearchPath"] == [
        "补充近期 K 线或技术面上下文。",
        "补充基本面证据后再复核研究主线。",
        "补充近期新闻或公告语境后再复核催化因素。",
        "刷新过期或延迟输入后再比较研究场景。",
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
    assert "待补证据类别：行情、技术面、基本面、新闻资讯。" in readiness["dataQualityNotes"]
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
    assert "quote, fundamental, news" not in serialized.lower()
