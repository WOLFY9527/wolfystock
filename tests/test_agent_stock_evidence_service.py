# -*- coding: utf-8 -*-
"""Focused contracts for SEC sidecar injection into stock evidence."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from data_provider.realtime_types import RealtimeSource, UnifiedRealtimeQuote
from data_provider.sec_edgar_provider import parse_companyfacts_payload
from src.services.agent_stock_evidence_service import StockEvidenceService
from src.services.data_source_router import DataSourceRoutePlan, ProviderRouteCandidate
from src.services.sec_edgar_evidence_service import (
    SecEdgarCompanyFactEvidenceRecord,
    SecEdgarFilingEvidenceSidecar,
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


def test_stock_evidence_base_fields_are_preserved_with_packet_without_sec_sidecar() -> None:
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
    packet = payload["items"][0]["stockEvidencePacket"]
    assert packet["schemaVersion"] == "stock_evidence_packet_v1"
    assert packet["symbol"] == "AAPL"
    assert packet["dataGaps"]
    assert "secFilingEvidence" not in payload["items"][0]


def test_stock_evidence_packet_is_additive_and_sec_remains_observation_only() -> None:
    service = _build_service()
    fixture_payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    parsed = parse_companyfacts_payload(fixture_payload)
    projected = project_sec_edgar_companyfacts_evidence(parsed)

    payload = service.get_stock_evidence(
        ["AAPL"],
        sec_filing_evidence_by_symbol={"AAPL": projected},
    )

    item = payload["items"][0]
    packet = item["stockEvidencePacket"]
    assert item["secFilingEvidence"] == build_sec_filing_evidence_sidecar(projected).to_dict()
    assert packet["symbol"] == "AAPL"
    assert all(
        evidence["evidenceClass"] != "sec_filing_evidence"
        for evidence in packet["scoreEligibleEvidence"]
    )
    assert packet["observationOnlyEvidence"] == [
        {
            "evidenceClass": "sec_filing_evidence",
            "sourceRefIds": ["sec_filing_evidence:sec_edgar"],
            "reasonCodes": ["observation_only", "score_contribution_not_allowed"],
        }
    ]
    serialized = json.dumps(packet, sort_keys=True)
    for forbidden in ["rawPayload", "facts", "headers", "Authorization", "apiKey"]:
        assert forbidden not in serialized


def test_stock_evidence_omits_packet_when_projector_fails_without_breaking_payload() -> None:
    service = _build_service()

    with patch(
        "src.services.agent_stock_evidence_service.project_stock_evidence_packet",
        side_effect=RuntimeError("projector exploded"),
    ):
        payload = service.get_stock_evidence(["AAPL"])

    item = payload["items"][0]
    assert item["quote"] == {"status": "unknown", "provider": "realtime_quote"}
    assert item["technical"] == {"status": "missing", "provider": "stock_daily"}
    assert item["fundamental"]["status"] == "missing"
    assert item["news"] == {"status": "unknown", "latestHeadline": None, "provider": None}
    assert "stockEvidencePacket" not in item


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


def test_stock_evidence_routes_injected_sec_sidecar_through_router_without_network_or_cik_lookup() -> None:
    service = _build_service()
    fixture_payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    parsed = parse_companyfacts_payload(fixture_payload)
    projected = project_sec_edgar_companyfacts_evidence(parsed)
    route_plan = DataSourceRoutePlan(
        primary_candidates=(
            ProviderRouteCandidate(
                provider_id="sec_edgar",
                provider_name="SEC EDGAR",
                capability="companyfacts",
                source_type="official_public",
                source_tier="official_public",
                trust_level="reliable_for_filings_metadata",
                freshness_expectation="filing_or_daily",
                observation_only=True,
                score_contribution_allowed=False,
            ),
        ),
        observation_candidates=(),
        forbidden_providers=(),
        cache_required=True,
        background_refresh_required=True,
        score_contribution_allowed=False,
        degradation_policy="use_cached_evidence_or_explicit_unavailable",
        required_source_types=("official_public", "cache_snapshot"),
        freshness_floor="daily",
        trust_floor="filings_evidence",
        reason_codes={"plan": ("cache_required",)},
    )

    with patch(
        "src.services.agent_stock_evidence_service.DataSourceRouter.resolve",
        return_value=route_plan,
    ) as resolve:
        payload = service.get_stock_evidence(
            ["AAPL"],
            sec_filing_evidence_by_symbol={"AAPL": projected},
        )

    assert payload["items"][0]["secFilingEvidence"]["providerId"] == "sec_edgar"
    request = resolve.call_args.args[0]
    assert request.market == "US"
    assert request.asset_type == "stock"
    assert request.use_case == "stock_evidence"
    assert request.capability == "companyfacts"
    assert request.freshness_need == "daily"
    assert request.scoring_allowed is False
    assert request.symbol == "AAPL"
    assert request.cik is None
    assert request.allow_network is False
    assert request.reproducibility_required is False


def test_stock_evidence_degrades_sec_sidecar_that_attempts_scoring_or_quote_authority() -> None:
    service = _build_service()
    sidecar = SecEdgarFilingEvidenceSidecar(
        status="available",
        provider_name="SEC EDGAR",
        provider_id="sec_edgar",
        source_tier="official_public",
        trust_level="reliable_for_filings_metadata",
        freshness_expectation="filing_or_daily",
        observation_only=False,
        score_contribution_allowed=True,
        raw_payload_stored=False,
        records=(
            SecEdgarCompanyFactEvidenceRecord(
                provider_name="SEC EDGAR",
                provider_id="sec_edgar",
                source="sec_edgar",
                source_tier="official_public",
                trust_level="reliable_for_filings_metadata",
                freshness_expectation="filing_or_daily",
                observation_only=False,
                score_contribution_allowed=True,
                evidence_type="quote_authority",
                concept="EntityCommonStockSharesOutstanding",
                taxonomy="dei",
                unit="shares",
                value=15204137000,
                accession_number="0000320193-24-000123",
                form="10-K",
                filed_at="2024-11-01",
                fiscal_year=2024,
                fiscal_period="FY",
                period_end_date="2024-09-28",
                fiscal_end_date="2024-09-28",
                frame="CY2024Q3I",
                entity_name="Apple Inc.",
                cik="0000320193",
                as_of="2024-09-28",
                updated_at="2024-11-01T14:00:00Z",
                source_ref="sec_edgar:companyfacts:malicious",
                degradation_reason=None,
            ),
        ),
        degradation_reason=None,
    )

    payload = service.get_stock_evidence(
        ["AAPL"],
        sec_filing_evidence_by_symbol={"AAPL": sidecar},
    )

    item = payload["items"][0]
    assert item["quote"] == {"status": "unknown", "provider": "realtime_quote"}
    assert item["fundamental"]["provider"] == "realtime_quote"
    assert item["secFilingEvidence"] == {
        "status": "rejected",
        "providerName": "SEC EDGAR",
        "providerId": "sec_edgar",
        "sourceTier": "official_public",
        "trustLevel": "reliable_for_filings_metadata",
        "freshnessExpectation": "filing_or_daily",
        "observationOnly": True,
        "scoreContributionAllowed": False,
        "rawPayloadStored": False,
        "records": [],
        "degradationReason": "sec_sidecar_authority_not_allowed",
    }


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


def test_service_packet_keeps_quote_provenance_but_blocks_live_claim_without_freshness_metadata() -> None:
    service = StockEvidenceService(
        fetcher_manager=MagicMock(
            get_realtime_quote=lambda symbol: UnifiedRealtimeQuote(
                code=symbol,
                name="Apple",
                source=RealtimeSource.ALPACA,
                price=214.55,
                change_pct=1.23,
                total_mv=None,
                pe_ratio=None,
                pb_ratio=None,
                market_timestamp="2026-05-13T08:30:00Z",
            )
        ),
        stock_repo=MagicMock(get_recent_daily_rows=lambda code, limit=80: []),
        analysis_repo=MagicMock(get_latest_record=lambda code: None),
    )

    payload = service.get_stock_evidence(["AAPL"])

    item = payload["items"][0]
    packet = item["stockEvidencePacket"]
    quote_ref = next(ref for ref in packet["sourceRefs"] if ref["evidenceClass"] == "quote")
    blocked = {boundary["claim"]: boundary for boundary in packet["claimBoundaries"] if not boundary["allowed"]}

    assert item["quote"] == {
        "status": "available",
        "price": 214.55,
        "changePct": 1.23,
        "currency": "USD",
        "provider": "alpaca",
        "updatedAt": "2026-05-13T08:30:00Z",
    }
    assert quote_ref["status"] == "available"
    assert quote_ref["provider"] == "alpaca"
    assert quote_ref["asOf"] == "2026-05-13T08:30:00Z"
    assert quote_ref["sourceType"] == "local_or_reported"
    assert quote_ref["freshness"] == "unknown"
    assert blocked["price_is_live"]["reasonCode"] == "quote_freshness_not_proven"
