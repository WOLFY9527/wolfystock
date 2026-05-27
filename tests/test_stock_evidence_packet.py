# -*- coding: utf-8 -*-
"""Focused contracts for the pure stock evidence packet projector."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from src.services.single_stock_evidence_contract import build_single_stock_evidence_contract
from src.services.stock_evidence_packet import project_stock_evidence_packet


REPO_ROOT = Path(__file__).resolve().parents[1]


def _strong_item() -> dict[str, Any]:
    return {
        "symbol": "AAPL",
        "market": "US",
        "quote": {
            "status": "available",
            "price": 190.12,
            "changePct": 1.25,
            "provider": "alpaca",
            "sourceType": "live",
            "freshness": "fresh",
            "updatedAt": "2026-05-20T13:45:00Z",
        },
        "technical": {
            "status": "available",
            "trend": "bullish",
            "ma20": 184.2,
            "rsi14": 58.1,
            "support": 181.0,
            "resistance": 193.4,
            "provider": "stock_daily",
            "freshness": "fresh",
            "updatedAt": "2026-05-20",
        },
        "fundamental": {
            "status": "available",
            "marketCap": 2800000000000,
            "peTtm": 28.5,
            "pb": 36.2,
            "beta": 1.1,
            "revenueTtm": 390000000000,
            "netIncomeTtm": 97000000000,
            "fcfTtm": 90000000000,
            "missingFields": [],
            "provider": "analysis_history",
            "freshness": "fresh",
            "updatedAt": "2026-05-19T08:00:00Z",
        },
        "news": {
            "status": "available",
            "latestHeadline": "Apple expands supply agreement",
            "provider": "news_cache",
            "freshness": "fresh",
            "updatedAt": "2026-05-20T11:00:00Z",
        },
    }


def _sec_sidecar() -> dict[str, Any]:
    return {
        "status": "available",
        "providerName": "SEC EDGAR",
        "providerId": "sec_edgar",
        "sourceTier": "official_public",
        "trustLevel": "reliable_for_filings_metadata",
        "freshnessExpectation": "filing_or_daily",
        "observationOnly": True,
        "scoreContributionAllowed": False,
        "rawPayloadStored": False,
        "records": [
            {
                "evidenceType": "official_company_fact",
                "concept": "Revenues",
                "taxonomy": "us-gaap",
                "unit": "USD",
                "value": 390000000000,
                "accessionNumber": "0000320193-24-000123",
                "form": "10-K",
                "filedAt": "2024-11-01",
                "periodEndDate": "2024-09-28",
                "asOf": "2024-09-28",
                "updatedAt": "2024-11-01T14:00:00Z",
                "sourceRef": "sec_edgar:companyfacts:0000320193:revenues",
                "rawPayload": {"secret": "must-not-emit"},
                "headers": {"Authorization": "Bearer must-not-emit"},
                "apiKey": "must-not-emit",
            }
        ],
        "facts": {"must": "not_emit"},
        "headers": {"Cookie": "must-not-emit"},
    }


def test_complete_strong_fixture_has_higher_confidence_and_is_not_advice() -> None:
    packet = project_stock_evidence_packet(
        {"items": [_strong_item()], "meta": {"generatedAt": "2026-05-20T14:00:00Z"}}
    )

    assert packet["schemaVersion"] == "stock_evidence_packet_v1"
    assert packet["symbol"] == "AAPL"
    assert packet["market"] == "US"
    assert packet["asOf"] == "2026-05-20T14:00:00Z"
    assert packet["notInvestmentAdvice"] is True
    assert packet["confidenceCap"]["value"] >= 80
    assert packet["confidenceLabel"] == "high"
    assert packet["dataGaps"] == []
    assert {item["evidenceClass"] for item in packet["scoreEligibleEvidence"]} == {
        "quote",
        "technical",
        "fundamental",
        "news",
    }
    assert "AAPL evidence packet:" in packet["promptSummary"]
    assert "quote=available" in packet["promptSummary"]
    assert "LLM" not in packet["promptSummary"]


def test_missing_quote_fundamentals_and_unknown_news_create_gaps_and_lower_confidence() -> None:
    item = {
        "symbol": "AAPL",
        "market": "US",
        "quote": {"status": "unknown", "provider": "realtime_quote"},
        "technical": {"status": "missing", "provider": "stock_daily"},
        "fundamental": {
            "status": "missing",
            "provider": "realtime_quote",
            "missingFields": ["marketCap", "peTtm", "revenueTtm"],
        },
        "news": {"status": "unknown", "latestHeadline": None, "provider": None},
    }

    packet = project_stock_evidence_packet(item)

    assert packet["confidenceCap"]["value"] <= 35
    assert packet["confidenceLabel"] == "low"
    assert packet["thesisEligibility"]["status"] == "blocked"
    assert {gap["evidenceClass"] for gap in packet["dataGaps"]} == {
        "quote",
        "technical",
        "fundamental",
        "news",
    }
    blocked = {boundary["claim"]: boundary for boundary in packet["claimBoundaries"] if not boundary["allowed"]}
    assert blocked["price_is_live"]["reasonCode"] == "quote_freshness_not_proven"
    assert blocked["fundamentals_are_complete"]["reasonCode"] == "fundamentals_missing_or_fallback"
    assert blocked["news_catalyst_exists"]["reasonCode"] == "news_unknown_or_placeholder"


def test_sec_sidecar_remains_observation_only_non_scoring_and_sanitized() -> None:
    item = _strong_item()
    item["secFilingEvidence"] = _sec_sidecar()

    packet = project_stock_evidence_packet(item)

    assert all(item["evidenceClass"] != "sec_filing_evidence" for item in packet["scoreEligibleEvidence"])
    assert packet["observationOnlyEvidence"] == [
        {
            "evidenceClass": "sec_filing_evidence",
            "sourceRefIds": ["sec_filing_evidence:sec_edgar"],
            "reasonCodes": ["observation_only", "score_contribution_not_allowed"],
        }
    ]
    sec_required = next(item for item in packet["requiredEvidence"] if item["evidenceClass"] == "sec_filing_evidence")
    assert sec_required["observationOnly"] is True
    assert sec_required["scoreContributionAllowed"] is False

    serialized = json.dumps(packet, sort_keys=True)
    for forbidden in ["rawPayload", "facts", "headers", "Authorization", "apiKey", "must-not-emit"]:
        assert forbidden not in serialized


def test_weak_fallback_unknown_provider_data_cannot_support_strong_claim_boundaries() -> None:
    item = _strong_item()
    item["quote"].update({"provider": "fallback_cache", "sourceType": "fallback", "freshness": "stale"})
    item["fundamental"].update(
        {"provider": "fallback_fundamentals", "status": "partial", "missingFields": ["fcfTtm"]}
    )
    item["news"].update(
        {"status": "unknown", "latestHeadline": "No recent headlines available", "provider": "placeholder"}
    )
    item["secFilingEvidence"] = _sec_sidecar()

    packet = project_stock_evidence_packet(item)

    assert packet["confidenceCap"]["value"] <= 55
    blocked = {boundary["claim"]: boundary for boundary in packet["claimBoundaries"] if not boundary["allowed"]}
    assert blocked["price_is_live"]["reasonCode"] == "quote_freshness_not_proven"
    assert blocked["fundamentals_are_complete"]["reasonCode"] == "fundamentals_missing_or_fallback"
    assert blocked["sec_filing_supports_trading_signal"]["reasonCode"] == "sec_observation_only_non_scoring"
    assert blocked["news_catalyst_exists"]["reasonCode"] == "news_unknown_or_placeholder"
    assert "weak_or_fallback_provider_evidence" in packet["confidenceCap"]["reasonCodes"]


def test_quote_source_refs_preserve_degraded_provenance_parity_with_single_stock_contract() -> None:
    item = _strong_item()
    item["quote"] = {
        "status": "available",
        "price": 190.12,
        "provider": "fallback_cache",
        "sourceType": "fallback",
        "freshness": "stale",
        "updatedAt": "2026-05-20T13:45:00Z",
    }

    packet = project_stock_evidence_packet(item)
    contract = build_single_stock_evidence_contract(
        {
            "domain": "quote",
            "symbol": "AAPL",
            "providerId": "fallback_cache",
            "sourceType": "fallback",
            "asOf": "2026-05-20T13:45:00Z",
            "freshness": "stale",
            "isStale": True,
        }
    )

    quote_ref = next(ref for ref in packet["sourceRefs"] if ref["evidenceClass"] == "quote")
    packet_boundary = next(boundary for boundary in packet["claimBoundaries"] if boundary["claim"] == "price_is_live")
    contract_boundary = next(
        boundary for boundary in contract["claimBoundaries"] if boundary["claim"] == "live_or_fresh_reliable"
    )

    assert quote_ref["provider"] == contract["providerId"]
    assert quote_ref["sourceType"] == contract["sourceType"]
    assert quote_ref["freshness"] == contract["freshness"]
    assert quote_ref["asOf"] == contract["asOf"]
    assert packet_boundary["allowed"] is False
    assert contract_boundary["allowed"] is False
    assert "weak_or_fallback_provider_evidence" in packet["confidenceCap"]["reasonCodes"]


def test_projector_import_is_inert_and_does_not_pull_provider_or_llm_runtime() -> None:
    script = """
import sys
before = set(sys.modules)
import src.services.stock_evidence_packet
after = set(sys.modules)
for forbidden in [
    "data_provider.base",
    "src.services.agent_stock_evidence_service",
    "src.services.sec_edgar_evidence_service",
    "openai",
    "requests",
    "httpx",
]:
    assert forbidden not in after - before, f"unexpected import side effect: {forbidden}"
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
