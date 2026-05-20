# -*- coding: utf-8 -*-
"""Focused contracts for SEC sidecar injection into stock evidence."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from data_provider.sec_edgar_provider import parse_companyfacts_payload
from src.services.agent_stock_evidence_service import StockEvidenceService
from src.services.sec_edgar_evidence_service import (
    build_sec_filing_evidence_sidecar,
    project_sec_edgar_companyfacts_evidence,
)


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "sec_edgar" / "companyfacts_sample.json"


def _build_service() -> StockEvidenceService:
    return StockEvidenceService(
        fetcher_manager=MagicMock(get_realtime_quote=lambda symbol: None),
        stock_repo=MagicMock(get_recent_daily_rows=lambda code, limit=80: []),
        analysis_repo=MagicMock(get_latest_record=lambda code: None),
    )


def test_stock_evidence_output_is_unchanged_without_injected_sec_filing_evidence() -> None:
    service = _build_service()

    payload = service.get_stock_evidence(["AAPL"])

    assert payload["symbols"] == ["AAPL"]
    assert "secFilingEvidence" not in payload["items"][0]
    assert payload["items"][0]["quote"] == {
        "status": "unknown",
        "provider": "realtime_quote",
    }
    assert payload["items"][0]["technical"] == {
        "status": "missing",
        "provider": "stock_daily",
    }
    assert payload["items"][0]["fundamental"] == {
        "status": "missing",
        "marketCap": None,
        "peTtm": None,
        "pb": None,
        "beta": None,
        "revenueTtm": None,
        "netIncomeTtm": None,
        "fcfTtm": None,
        "provider": "realtime_quote",
        "updatedAt": None,
        "missingFields": [
            "marketCap",
            "peTtm",
            "pb",
            "beta",
            "revenueTtm",
            "netIncomeTtm",
            "fcfTtm",
        ],
    }
    assert payload["items"][0]["news"] == {
        "status": "unknown",
        "latestHeadline": None,
        "provider": None,
    }


def test_stock_evidence_accepts_injected_projected_sec_records_without_mutating_other_fields() -> None:
    service = _build_service()
    fixture_payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    parsed = parse_companyfacts_payload(fixture_payload)
    projected = project_sec_edgar_companyfacts_evidence(parsed)

    baseline = service.get_stock_evidence(["AAPL"])
    payload = service.get_stock_evidence(
        ["AAPL"],
        sec_filing_evidence_by_symbol={"AAPL": projected},
    )

    item = payload["items"][0]
    baseline_item = baseline["items"][0]

    assert item["quote"] == baseline_item["quote"]
    assert item["technical"] == baseline_item["technical"]
    assert item["fundamental"] == baseline_item["fundamental"]
    assert item["news"] == baseline_item["news"]
    assert item["secFilingEvidence"] == build_sec_filing_evidence_sidecar(projected).to_dict()
    assert item["secFilingEvidence"]["providerName"] == "SEC EDGAR"
    assert item["secFilingEvidence"]["providerId"] == "sec_edgar"
    assert item["secFilingEvidence"]["sourceTier"] == "official_public"
    assert item["secFilingEvidence"]["trustLevel"] == "reliable_for_filings_metadata"
    assert item["secFilingEvidence"]["freshnessExpectation"] == "filing_or_daily"
    assert item["secFilingEvidence"]["observationOnly"] is True
    assert item["secFilingEvidence"]["scoreContributionAllowed"] is False
    assert item["secFilingEvidence"]["rawPayloadStored"] is False
    assert len(item["secFilingEvidence"]["records"]) == 4
    assert "rawPayload" not in item["secFilingEvidence"]
    assert "facts" not in item["secFilingEvidence"]
    assert "headers" not in item["secFilingEvidence"]


def test_stock_evidence_accepts_injected_sec_filing_sidecar_instance() -> None:
    service = _build_service()
    fixture_payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    parsed = parse_companyfacts_payload(fixture_payload)
    sidecar = build_sec_filing_evidence_sidecar(project_sec_edgar_companyfacts_evidence(parsed))

    payload = service.get_stock_evidence(
        ["AAPL"],
        sec_filing_evidence_by_symbol={"aapl": sidecar},
    )

    assert payload["items"][0]["secFilingEvidence"] == sidecar.to_dict()
