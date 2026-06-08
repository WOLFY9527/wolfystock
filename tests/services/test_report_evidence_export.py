from __future__ import annotations

import ast
import json
from pathlib import Path

from api.v1.schemas.report_evidence_export import ReportEvidenceExport
from src.services.report_evidence_export import build_report_evidence_export


def _complete_report() -> dict:
    return {
        "meta": {
            "query_id": "report-001",
            "stock_code": "AAPL",
            "stock_name": "Apple",
            "report_type": "detailed",
            "report_language": "en",
            "created_at": "2026-06-08T12:00:00+08:00",
            "report_generated_at": "2026-06-08T12:01:00+08:00",
        },
        "researchReadiness": {
            "researchReady": False,
            "readinessState": "observe_only",
            "consumerActionBoundary": "no_advice",
            "historicalReadinessNote": "preserved",
        },
        "evidenceCoverageFrame": {
            "technicals": {
                "status": "available",
                "sourceTier": "score_grade",
                "historicalCoverageNote": "preserved",
            }
        },
        "singleStockEvidencePacket": {
            "contractVersion": "single_stock_evidence_packet_v1",
            "symbol": "AAPL",
            "packetState": "partial",
            "noAdviceBoundary": {"state": "observation_only"},
            "domains": {"news": {"status": "available", "historicalDomainNote": "preserved"}},
        },
        "evidenceCitationFrame": {
            "contractVersion": "home_report_evidence_citation_frame_v1",
            "frameState": "ready",
            "noAdviceBoundary": True,
            "citedEvidence": [{"id": "news-1", "domain": "news", "sourceId": "bounded-news"}],
        },
        "sourceProvenanceFrame": [
            {
                "contractVersion": "source_provenance_v1",
                "sourceId": "bounded-news",
                "sourceLabel": "News source",
                "evidenceDomain": "news",
                "observationOnly": True,
            }
        ],
    }


def test_report_evidence_export_preserves_existing_sidecars_and_identity() -> None:
    report = _complete_report()

    payload = build_report_evidence_export(report)
    validated = ReportEvidenceExport.model_validate(payload)

    assert validated.contractVersion == "report_evidence_export_v1"
    assert validated.payloadClass == "compact"
    assert validated.reportIdentity.queryId == "report-001"
    assert validated.reportIdentity.stockCode == "AAPL"
    assert validated.availability.state == "available"
    assert validated.availability.presentSidecars == [
        "researchReadiness",
        "evidenceCoverageFrame",
        "singleStockEvidencePacket",
        "evidenceCitationFrame",
        "sourceProvenanceFrame",
    ]
    assert validated.availability.missingSidecars == []
    assert validated.sidecars.researchReadiness == report["researchReadiness"]
    assert validated.sidecars.evidenceCoverageFrame == report["evidenceCoverageFrame"]
    assert validated.sidecars.singleStockEvidencePacket == report["singleStockEvidencePacket"]
    assert validated.sidecars.evidenceCitationFrame == report["evidenceCitationFrame"]
    assert validated.sidecars.sourceProvenanceFrame == report["sourceProvenanceFrame"]
    assert validated.noAdviceBoundary.state == "available"
    assert validated.noAdviceBoundary.sourceSidecar == "singleStockEvidencePacket"
    assert validated.noAdviceBoundary.value == {"state": "observation_only"}


def test_report_evidence_export_reports_partial_and_unavailable_without_fabricating_sidecars() -> None:
    partial_payload = build_report_evidence_export(
        {
            "meta": {"query_id": "partial-001", "stock_code": "MSFT"},
            "details": {
                "analysis_result": {
                    "researchReadiness": {
                        "readinessState": "insufficient",
                        "consumerActionBoundary": "no_advice",
                    }
                }
            },
        }
    )

    partial = ReportEvidenceExport.model_validate(partial_payload)
    assert partial.availability.state == "partial"
    assert partial.availability.presentSidecars == ["researchReadiness"]
    assert "singleStockEvidencePacket" in partial.availability.missingSidecars
    assert partial.sidecars.researchReadiness == {
        "readinessState": "insufficient",
        "consumerActionBoundary": "no_advice",
    }
    assert partial.sidecars.singleStockEvidencePacket is None

    unavailable = ReportEvidenceExport.model_validate(
        build_report_evidence_export({"meta": {"query_id": "empty"}})
    )
    assert unavailable.availability.state == "unavailable"
    assert unavailable.availability.presentSidecars == []
    assert unavailable.sidecars.researchReadiness is None
    assert unavailable.noAdviceBoundary.state == "unavailable"


def test_report_evidence_export_redacts_raw_internal_fields_recursively() -> None:
    report = _complete_report()
    report["singleStockEvidencePacket"]["debugRef"] = "debug-ref-secret"
    report["singleStockEvidencePacket"]["domains"]["news"]["rawProviderPayload"] = {
        "apiKey": "secret-api-key",
        "headline": "must not leak from raw payload",
    }
    report["evidenceCitationFrame"]["citedEvidence"][0]["reasonCode"] = "internal_reason_code"
    report["sourceProvenanceFrame"][0]["cacheKey"] = "cache-key-secret"
    report["sourceProvenanceFrame"][0]["traceId"] = "trace-secret"
    report["details"] = {
        "raw_result": {"token": "raw-result-token"},
        "raw_ai_response": "raw llm body",
        "context_snapshot": {"routerInternals": "internal-router-state"},
    }

    payload = ReportEvidenceExport.model_validate(
        build_report_evidence_export(report)
    ).model_dump(mode="json")
    rendered = json.dumps(payload, sort_keys=True)

    assert "debug-ref-secret" not in rendered
    assert "secret-api-key" not in rendered
    assert "must not leak from raw payload" not in rendered
    assert "internal_reason_code" not in rendered
    assert "cache-key-secret" not in rendered
    assert "trace-secret" not in rendered
    assert "raw-result-token" not in rendered
    assert "raw llm body" not in rendered
    assert "internal-router-state" not in rendered
    assert payload["sidecars"]["singleStockEvidencePacket"]["domains"]["news"]["status"] == "available"
    assert payload["sidecars"]["sourceProvenanceFrame"][0]["sourceId"] == "bounded-news"


def test_report_evidence_export_helper_has_no_provider_runtime_cache_imports() -> None:
    source_path = Path("src/services/report_evidence_export.py")
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    forbidden_roots = {
        "data_provider",
        "src.providers",
        "src.services.analysis_service",
        "src.services.analysis_provider_planner",
        "src.services.market_cache",
        "src.storage",
        "src.cache",
    }
    assert not any(
        module == forbidden or module.startswith(f"{forbidden}.")
        for module in imported_modules
        for forbidden in forbidden_roots
    )
