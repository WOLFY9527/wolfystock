from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.app import create_app
from api.v1.schemas.report_evidence_export import ReportEvidenceExport
from src.analyzer import AnalysisResult
from src.services.report_evidence_export import build_report_evidence_export
from src.services.analysis_service import AnalysisService
from src.services.task_queue import AnalysisTaskQueue


@pytest.fixture(autouse=True)
def disable_auth():
    auth._auth_enabled = None
    with patch("api.middlewares.auth.is_auth_enabled", return_value=False), patch(
        "api.deps.is_auth_enabled", return_value=False
    ), patch("src.auth.is_auth_enabled", return_value=False):
        yield
    auth._auth_enabled = None


@pytest.fixture
def client(tmp_path):
    app = create_app(static_dir=tmp_path)
    with TestClient(app) as test_client:
        yield test_client


def _assert_no_forbidden_keys(value: object, forbidden_keys: tuple[str, ...]) -> None:
    normalized_forbidden = {
        "".join(ch for ch in key.lower() if ch.isalnum())
        for key in forbidden_keys
    }
    found: list[str] = []

    def walk(node: object, path: str = "$") -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                normalized_key = "".join(ch for ch in str(key).lower() if ch.isalnum())
                child_path = f"{path}.{key}"
                if normalized_key in normalized_forbidden:
                    found.append(child_path)
                walk(child, child_path)
        elif isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{path}[{index}]")

    walk(value)
    assert found == []


def _service_response_for_api_contract() -> dict:
    result = AnalysisResult(
        code="AAPL",
        name="Apple",
        sentiment_score=74,
        trend_prediction="Bullish bias with bounded risk",
        operation_advice="Observe only",
        decision_type="hold",
        confidence_level="中",
        report_language="en",
        analysis_summary="Observation only while evidence remains consumer-safe.",
        technical_analysis="Trend remains constructive with fresh price history.",
        fundamental_analysis="Fundamentals and earnings are available from bounded sources.",
        news_summary="Recent earnings and guidance coverage remain relevant.",
        risk_warning="Risk remains elevated if evidence freshness degrades.",
        dashboard={
            "battle_plan": {"sniper_points": {"ideal_buy": "184-186", "stop_loss": "179", "take_profit": "195-198"}},
            "structured_analysis": {
                "technicals": {
                    "status": "ok",
                    "source": "polygon_us_grouped_daily",
                    "sourceType": "authorized_licensed_feed",
                    "sourceTier": "score_grade",
                    "freshness": "fresh",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                },
                "fundamentals": {
                    "status": "ok",
                    "source": "fmp",
                    "sourceType": "official_public",
                    "sourceTier": "score_grade",
                    "freshness": "fresh",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                    "asOf": "2026-04-28",
                    "normalized": {
                        "marketCap": 3010000000000,
                        "trailingPE": 24.8,
                        "forwardPE": 22.1,
                        "priceToBook": 8.7,
                        "revenueGrowth": 0.11,
                        "freeCashflow": 108000000000,
                        "returnOnEquity": 1.48,
                    },
                    "field_sources": {
                        "marketCap": "fmp",
                        "trailingPE": "fmp",
                        "forwardPE": "fmp",
                        "priceToBook": "fmp",
                        "revenueGrowth": "fmp",
                        "freeCashflow": "fmp",
                        "returnOnEquity": "fmp",
                    },
                    "field_periods": {
                        "marketCap": "latest",
                        "trailingPE": "ttm",
                        "forwardPE": "consensus",
                        "priceToBook": "latest",
                        "revenueGrowth": "ttm_yoy",
                        "freeCashflow": "ttm",
                        "returnOnEquity": "ttm",
                    },
                    "topEvidenceRefs": ["fund:market-cap", "fund:roe"],
                },
                "earnings_analysis": {
                    "status": "ok",
                    "source": "fmp_income_statement",
                    "field_sources": {"quarterly_series": "fmp_income_statement"},
                    "summary_flags": ["quarterly_series_available", "financial_report_available"],
                    "narrative_insights": ["Earnings trend remains stable."],
                    "sourceTier": "score_grade",
                    "freshness": "fresh",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                    "reporting_basis": "latest_quarter",
                    "summary_basis": "yoy",
                    "derived_metrics": {
                        "yoy_revenue_growth": 0.08,
                        "yoy_net_income_change": 0.06,
                    },
                    "quarterly_series": [
                        {
                            "quarter": "2026Q1",
                            "fiscalDateEnding": "2026-03-31",
                            "revenue": 90340000000,
                            "net_income": 21400000000,
                        }
                    ],
                    "topEvidenceRefs": ["earnings:q1-2026"],
                },
                "fundamental_context": {
                    "status": "supported",
                    "market": "us",
                    "valuation": {
                        "data": {
                            "marketCap": 3010000000000,
                            "trailingPE": 24.8,
                            "priceToBook": 8.7,
                        }
                    },
                    "earnings": {
                        "data": {
                            "quarterly_series": [
                                {
                                    "quarter": "2026Q1",
                                    "fiscalDateEnding": "2026-03-31",
                                    "revenue": 90340000000,
                                    "net_income": 21400000000,
                                }
                            ],
                            "financial_report": {
                                "reportDate": "2026-03-31",
                                "revenue": 90340000000,
                                "netIncome": 21400000000,
                            },
                        }
                    },
                },
                "sentiment_analysis": {
                    "status": "ok",
                    "source": "finnhub",
                    "sourceType": "official_public",
                    "sourceTier": "observation_only",
                    "trustLevel": "observation_only",
                    "freshness": "fresh",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": False,
                    "sentiment_summary": "positive",
                    "top_positive_items": [
                        {
                            "id": "news-earnings",
                            "headline": "Apple beats earnings and raises guidance",
                            "summary": "Quarterly earnings beat expectations and guidance increased.",
                            "source": "finnhub",
                            "published_at": "2026-06-03T13:00:00Z",
                            "sentiment": "positive",
                            "relevance_score": 0.96,
                        }
                    ],
                    "top_negative_items": [],
                    "classified_items": [],
                    "topEvidenceRefs": ["news:earnings"],
                },
                "catalyst": {
                    "status": "ok",
                    "source": "gnews",
                    "sourceType": "official_public",
                    "sourceTier": "observation_only",
                    "trustLevel": "observation_only",
                    "freshness": "fresh",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": False,
                    "classified_items": [
                        {
                            "id": "cat-guidance",
                            "headline": "Apple raises full-year guidance",
                            "summary": "Management raised the full-year outlook.",
                            "source": "finnhub",
                            "published_at": "2026-06-03T13:05:00Z",
                            "relevance_score": 0.95,
                            "catalyst_type": "guidance",
                            "sentiment": "positive",
                        }
                    ],
                    "topEvidenceRefs": ["catalyst:guidance"],
                },
                "realtime_context": {
                    "price": 188.2,
                    "volume_ratio": 1.24,
                    "turnover_rate": 0.021,
                    "source": "polygon_us_grouped_daily",
                    "freshness": "fresh",
                },
                "market_context": {
                    "today": {"close": 188.2, "ma20": 184.0},
                    "yesterday": {"close": 186.4},
                    "sectorTheme": {"sector": "software", "theme": "ai"},
                    "macro": {"regime": "risk_on"},
                    "liquidity": {"usd": "stable"},
                    "source": "official_macro_bundle",
                    "sourceTier": "official_public",
                    "providerAuthority": "observationOnly",
                    "freshness": "delayed",
                    "topEvidenceRefs": ["macro:fred-weekly", "theme:software-ai"],
                },
                "data_quality_report": {
                    "dataQualityTier": "decision_grade",
                    "requiredAvailable": True,
                    "confidenceCap": 100,
                    "missingRequiredDomains": [],
                    "importantDomainsMissing": [],
                    "scoreSuppressed": False,
                    "stanceGuardrail": "none",
                },
            },
        },
        runtime_execution={
            "data_quality_report": {
                "dataQualityTier": "decision_grade",
                "requiredAvailable": True,
                "confidenceCap": 100,
                "missingRequiredDomains": [],
                "importantDomainsMissing": [],
                "scoreSuppressed": False,
                "stanceGuardrail": "none",
            },
            "data": {
                "market": {
                    "status": "ok",
                    "truth": "actual",
                    "source": "polygon",
                    "freshness": "fresh",
                    "sourceTier": "score_grade",
                    "providerAuthority": "scoreGradeAllowed",
                },
                "fundamentals": {
                    "status": "ok",
                    "truth": "actual",
                    "source": "fmp",
                    "freshness": "fresh",
                    "sourceTier": "score_grade",
                    "providerAuthority": "scoreGradeAllowed",
                },
                "news": {
                    "status": "ok",
                    "truth": "actual",
                    "source": "gnews",
                    "freshness": "fresh",
                    "sourceTier": "observation_only",
                    "providerAuthority": "observationOnly",
                },
                "sentiment": {
                    "status": "ok",
                    "truth": "actual",
                    "source": "finnhub",
                    "freshness": "fresh",
                    "sourceTier": "observation_only",
                    "providerAuthority": "observationOnly",
                },
            },
        },
    )
    return AnalysisService()._build_analysis_response(result, query_id="api-contract-001")


def test_progress_status_updates_include_meaningful_data_stages():
    execution = None
    for stage, detail in [
        ("detecting_market", "Detecting market"),
        ("loading_quote", "Loading quote"),
        ("loading_fundamentals", "Loading fundamentals"),
        ("loading_news", "Loading news"),
        ("analyzing_signals", "Running AI analysis"),
    ]:
        execution = AnalysisTaskQueue._merge_execution_stage(
            execution,
            stage_key=stage,
            detail=detail,
        )

    steps = {step["key"]: step for step in execution["steps"]}

    assert steps["data_fetch"]["status"] == "ok"
    assert steps["data_fetch"]["detail"] == "Loading news"
    assert steps["ai_analysis"]["status"] == "partial"
    assert steps["ai_analysis"]["detail"] == "Running AI analysis"


def test_sync_analysis_api_preserves_home_evidence_packet_contract(client) -> None:
    service_response = _service_response_for_api_contract()
    service_report = service_response["report"]

    with patch("api.v1.endpoints.analysis._raise_if_llm_model_unavailable", return_value=None), patch(
        "src.services.analysis_service.AnalysisService.analyze_stock",
        return_value=service_response,
    ), patch(
        "api.v1.endpoints.analysis._load_sync_fundamental_sources",
        return_value=(None, None),
    ):
        response = client.post(
            "/api/v1/analysis/analyze",
            json={"stock_code": "AAPL", "stock_name": "Apple", "async_mode": False},
        )

    assert response.status_code == 200
    payload = response.json()
    report = payload["report"]
    serialized_payload = json.dumps(payload, sort_keys=True)
    assert report["summary"]["operation_advice"] == "Observe only"
    assert report["strategy"]["ideal_buy"] == "184-186"
    assert report["strategy"]["stop_loss"] == "179"
    assert report["strategy"]["take_profit"] == "195-198"
    assert report["details"]["analysis_result"] is not None
    assert "report_evidence_export_v1" not in serialized_payload
    assert "reportEvidenceExport" not in serialized_payload
    assert "report_evidence_export" not in serialized_payload
    assert "evidenceExport" not in serialized_payload
    assert "evidence_export" not in serialized_payload
    assert "redactionPosture" not in serialized_payload
    assert "payloadClass" not in serialized_payload
    for forbidden_marker in (
        "researchPacketV1",
        "researchPacket",
        "research_packet_v1",
        "runtimePosture",
        "dataCoverageRows",
        '"lanes"',
    ):
        assert forbidden_marker not in serialized_payload
    _assert_no_forbidden_keys(
        payload,
        (
            "researchPacketV1",
            "researchPacket",
            "research_packet_v1",
            "runtimePosture",
            "dataCoverageRows",
            "lanes",
            "laneInternals",
            "laneDiagnostics",
            "rawProviderPayload",
            "rawSourcePayload",
            "rawCachePayload",
            "rawLaneInternals",
            "providerRoute",
            "cacheDebug",
            "cacheKey",
            "reasonCode",
            "reasonFamilies",
            "backendTrace",
            "backendDiagnostics",
            "internalDiagnostics",
            "routerInternals",
        ),
    )
    packet = report["singleStockEvidencePacket"]
    citation_frame = report["evidenceCitationFrame"]
    provenance_frame = report["sourceProvenanceFrame"]

    assert report["researchReadiness"] == service_report["researchReadiness"]
    assert report["evidenceCoverageFrame"] == service_report["evidenceCoverageFrame"]
    assert report["singleStockEvidencePacket"] == service_report["singleStockEvidencePacket"]
    assert report["evidenceCitationFrame"] == service_report["evidenceCitationFrame"]
    assert report["sourceProvenanceFrame"] == service_report["sourceProvenanceFrame"]
    assert report["meta"]["researchReadiness"] == report["researchReadiness"]
    assert report["meta"]["evidenceCoverageFrame"] == report["evidenceCoverageFrame"]
    assert report["meta"]["singleStockEvidencePacket"] == packet
    assert report["meta"]["evidenceCitationFrame"] == citation_frame
    assert report["meta"]["sourceProvenanceFrame"] == provenance_frame
    assert report["details"]["analysis_result"]["researchReadiness"] == report["researchReadiness"]
    assert report["details"]["analysis_result"]["evidenceCoverageFrame"] == report["evidenceCoverageFrame"]
    assert report["details"]["analysis_result"]["singleStockEvidencePacket"] == packet
    assert report["details"]["analysis_result"]["evidenceCitationFrame"] == citation_frame
    assert report["details"]["analysis_result"]["sourceProvenanceFrame"] == provenance_frame
    assert packet["contractVersion"] == "single_stock_evidence_packet_v1"
    assert packet["fundamentalsEarnings"]["normalizerState"] == "ready"
    assert packet["newsCatalysts"]["extractionState"] == "ready"
    assert packet["newsCatalysts"]["topNewsItems"][0]["id"] == "news-earnings"
    assert packet["newsCatalysts"]["topCatalystItems"][0]["id"] == "cat-guidance"
    assert citation_frame["contractVersion"] == "home_report_evidence_citation_frame_v1"
    assert citation_frame["noAdviceBoundary"] is True
    assert [entry["evidenceDomain"] for entry in provenance_frame] == [
        "priceHistory",
        "technicals",
        "fundamentals",
        "earnings",
        "filings",
        "news",
        "catalysts",
        "sentiment",
        "valuation",
        "sectorTheme",
        "macroLiquidity",
    ]

    export_payload = build_report_evidence_export(report)
    validated_export = ReportEvidenceExport.model_validate(export_payload)
    assert validated_export.contractVersion == "report_evidence_export_v1"
    assert validated_export.payloadClass == "compact"
    assert validated_export.availability.state == "available"
    export_packet = validated_export.sidecars.singleStockEvidencePacket
    assert export_packet["contractVersion"] == packet["contractVersion"]
    assert export_packet["symbol"] == packet["symbol"]
    assert export_packet["packetState"] == packet["packetState"]
    assert export_packet["domains"]["news"]["status"] == packet["domains"]["news"]["status"]
    assert export_packet["noAdviceBoundary"] == packet["noAdviceBoundary"]
