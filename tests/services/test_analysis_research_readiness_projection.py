# -*- coding: utf-8 -*-
"""Research-readiness projection tests for Home AI analysis responses."""

from __future__ import annotations

import json
from typing import Any

from api.v1.schemas.history import AnalysisReport, ReportDetails, ReportMeta, ReportSummary
from src.analyzer import AnalysisResult
from src.services.analysis_service import AnalysisService


def _result_with_quality(
    *,
    code: str = "AAPL",
    data_quality_report: dict[str, Any] | None = None,
    structured_overrides: dict[str, Any] | None = None,
    runtime_data: dict[str, Any] | None = None,
    score: int | None = 86,
) -> AnalysisResult:
    structured = {
        "technicals": {
            "status": "ok",
            "source": "polygon_us_grouped_daily",
            "sourceType": "authorized_licensed_feed",
            "sourceTier": "score_grade",
            "trustLevel": "score_grade",
            "freshness": "fresh",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
        },
        "fundamentals": {
            "status": "ok",
            "source": "fmp",
            "sourceType": "official_public",
            "sourceTier": "score_grade",
            "trustLevel": "score_grade",
            "freshness": "fresh",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "normalized": {
                "trailingPE": 24.8,
                "forwardPE": 22.1,
                "priceToBook": 8.7,
            },
        },
        "earnings_analysis": {
            "status": "ok",
            "field_sources": {"quarterly_series": "fmp_income_statement"},
            "summary_flags": ["quarterly_series_available"],
            "narrative_insights": ["盈利趋势稳定。"],
            "sourceTier": "score_grade",
            "freshness": "fresh",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
        },
        "sentiment_analysis": {
            "status": "ok",
            "source": "finnhub",
            "sourceType": "official_public",
            "sourceTier": "score_grade",
            "trustLevel": "score_grade",
            "freshness": "fresh",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
        },
        "catalyst": {
            "status": "ok",
            "source": "gnews",
            "sourceType": "official_public",
            "sourceTier": "score_grade",
            "trustLevel": "score_grade",
            "freshness": "fresh",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "relevance_type": "company_specific",
            "classified_items": [{"title": "Apple launches new hardware"}],
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
        },
        "data_quality_report": data_quality_report or {
            "dataQualityTier": "decision_grade",
            "requiredAvailable": True,
            "confidenceCap": 100,
            "missingRequiredDomains": [],
            "importantDomainsMissing": [],
            "scoreSuppressed": False,
            "stanceGuardrail": "none",
        },
    }
    if structured_overrides:
        structured.update(structured_overrides)
    return AnalysisResult(
        code=code,
        name=code,
        sentiment_score=score,
        trend_prediction="震荡",
        operation_advice="观望",
        decision_type="hold",
        confidence_level="中",
        report_language="zh",
        analysis_summary="研究摘要。",
        technical_analysis="技术面摘要。",
        fundamental_analysis="基本面摘要。",
        news_summary="新闻摘要。",
        risk_warning="风险提示。",
        dashboard={
            "structured_analysis": structured,
            "battle_plan": {"sniper_points": {}},
        },
        runtime_execution={
            "data_quality_report": structured["data_quality_report"],
            "data": runtime_data or {},
        },
    )


def _report_for(result: AnalysisResult) -> dict[str, Any]:
    return AnalysisService()._build_analysis_response(result, query_id="query-123")


def test_home_analysis_consumed_evidence_schema_preserves_sidecars_and_extra_fields() -> None:
    analysis_result = {
        "researchReadiness": {
            "researchReady": False,
            "readinessState": "observe_only",
            "missingEvidence": ["news"],
            "blockingReasons": ["provider_timeout"],
            "sourceAuthority": "observationOnly",
            "consumerActionBoundary": "no_advice",
            "historicalReadinessNote": "kept",
        },
        "evidenceCoverageFrame": {
            "news": {
                "status": "blocked",
                "fallbackOrProxy": True,
                "missingReasons": ["provider_timeout"],
                "nextEvidenceNeeded": ["news"],
                "historicalCoverageNote": "kept",
            }
        },
        "singleStockEvidencePacket": {
            "contractVersion": "single_stock_evidence_packet_v1",
            "symbol": "AAPL",
            "market": "us",
            "packetState": "degraded",
            "domains": {
                "news": {
                    "status": "blocked",
                    "sourceTier": "observation_only",
                    "providerAuthority": "observationOnly",
                    "freshness": "fallback",
                    "fallbackOrProxy": True,
                    "historicalDomainNote": "kept",
                }
            },
            "sourceSummary": {"news": {"status": "blocked", "historicalSummaryNote": "kept"}},
            "historicalPacketNote": "kept",
        },
        "evidenceCitationFrame": {
            "contractVersion": "home_report_evidence_citation_frame_v1",
            "frameState": "blocked",
            "symbol": "AAPL",
            "market": "us",
            "missingEvidence": ["news"],
            "blockingReasons": ["provider_timeout"],
            "noAdviceBoundary": True,
            "citedEvidence": [],
            "domainCoverage": [
                {
                    "domain": "news",
                    "status": "blocked",
                    "authorityLabel": "observationOnly",
                    "freshnessLabel": "fallback",
                    "historicalCitationCoverageNote": "kept",
                }
            ],
            "nextEvidenceNeeded": ["news"],
            "historicalCitationNote": "kept",
        },
        "sourceProvenanceFrame": [
            {
                "contractVersion": "source_provenance_v1",
                "sourceId": "unknown_source",
                "sourceLabel": "Unknown source",
                "evidenceDomain": "news",
                "authorityTier": "observationOnly",
                "freshnessState": "fallback",
                "sourceTier": "observation_only",
                "fallbackOrProxy": True,
                "observationOnly": True,
                "scoreContributionAllowed": False,
                "limitations": ["provider_timeout"],
                "nextEvidenceNeeded": ["news"],
                "debugRef": "analysis:test",
                "historicalProvenanceNote": "kept",
            }
        ],
    }

    report = AnalysisReport(
        meta=ReportMeta(query_id="query-123", stock_code="AAPL"),
        summary=ReportSummary(analysis_summary="Observation only."),
        details=ReportDetails(raw_result={"analysis_result": analysis_result}),
    )
    dumped = report.model_dump()

    for field in (
        "researchReadiness",
        "evidenceCoverageFrame",
        "singleStockEvidencePacket",
        "evidenceCitationFrame",
        "sourceProvenanceFrame",
    ):
        assert dumped[field] == analysis_result[field]
        assert dumped["meta"][field] == analysis_result[field]
        assert dumped["details"]["analysis_result"][field] == analysis_result[field]
    assert dumped["researchReadiness"]["historicalReadinessNote"] == "kept"
    assert dumped["evidenceCoverageFrame"]["news"]["historicalCoverageNote"] == "kept"
    assert dumped["singleStockEvidencePacket"]["domains"]["news"]["historicalDomainNote"] == "kept"
    assert dumped["evidenceCitationFrame"]["domainCoverage"][0]["historicalCitationCoverageNote"] == "kept"
    assert dumped["sourceProvenanceFrame"][0]["historicalProvenanceNote"] == "kept"


def test_home_analysis_response_adds_research_readiness_ready_path() -> None:
    response = _report_for(_result_with_quality())

    readiness = response["researchReadiness"]

    assert response["report"]["researchReadiness"] == readiness
    assert response["report"]["meta"]["researchReadiness"] == readiness
    assert response["report"]["details"]["analysis_result"]["researchReadiness"] == readiness
    assert readiness["researchReady"] is True
    assert readiness["readinessState"] == "ready"
    assert readiness["missingEvidence"] == []
    assert readiness["sourceAuthority"] == "scoreGradeAllowed"
    assert readiness["consumerActionBoundary"] == "no_advice"


def test_home_analysis_partial_orcl_like_path_completes_but_is_not_research_ready() -> None:
    result = _result_with_quality(
        code="ORCL",
        data_quality_report={
            "dataQualityTier": "analysis_grade",
            "requiredAvailable": True,
            "confidenceCap": 70,
            "importantDomainsMissing": ["fundamentals"],
            "scoreSuppressed": False,
            "stanceGuardrail": "observe_only",
            "reasonCodes": ["important_data_missing"],
        },
    )

    response = _report_for(result)
    readiness = response["researchReadiness"]

    assert response["stock_code"] == "ORCL"
    assert response["report"]["details"]["analysis_result"]["score_state"] == "capped"
    assert readiness["researchReady"] is False
    assert readiness["readinessState"] == "insufficient"
    assert "fundamentals" in readiness["missingEvidence"]
    assert "score_cap_active" in readiness["blockingReasons"]


def test_home_analysis_missing_fundamentals_news_and_catalyst_blocks_research_ready() -> None:
    result = _result_with_quality(
        data_quality_report={
            "dataQualityTier": "partial",
            "requiredAvailable": True,
            "confidenceCap": 65,
            "importantDomainsMissing": ["fundamentals", "catalyst_news_event"],
            "optionalMissing": ["news", "sentiment", "detailed_fundamentals"],
            "scoreSuppressed": False,
            "stanceGuardrail": "observe_only",
        },
        structured_overrides={
            "fundamentals": {"status": "missing", "source": None},
            "sentiment_analysis": {"status": "missing", "source": None},
            "catalyst": {"status": "missing", "source": None},
        },
    )

    readiness = _report_for(result)["researchReadiness"]

    assert readiness["researchReady"] is False
    assert readiness["readinessState"] == "insufficient"
    assert readiness["missingEvidence"] == ["fundamentals", "news", "catalyst"]
    assert "missing_required_evidence" in readiness["blockingReasons"]


def test_home_analysis_stale_fallback_proxy_inputs_cap_to_observe_only() -> None:
    result = _result_with_quality(
        data_quality_report={
            "dataQualityTier": "analysis_grade",
            "requiredAvailable": True,
            "confidenceCap": 75,
            "staleSources": ["quote"],
            "reasonCodes": ["stale_required_source", "non_live_required_source"],
            "scoreSuppressed": False,
            "stanceGuardrail": "observe_only",
        },
        structured_overrides={
            "technicals": {
                "status": "partial",
                "source": "yfinance_proxy",
                "sourceType": "public_proxy",
                "freshness": "stale",
                "proxyOnly": True,
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
            },
            "fundamentals": {
                "status": "partial",
                "source": "fallback_cache",
                "sourceType": "fallback",
                "freshness": "fallback",
                "isFallback": True,
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
            },
        },
    )

    readiness = _report_for(result)["researchReadiness"]

    assert readiness["researchReady"] is False
    assert readiness["readinessState"] == "observe_only"
    assert readiness["freshnessFloor"] == "fallback"
    assert readiness["sourceAuthority"] == "observationOnly"
    assert "public_proxy_evidence" in readiness["blockingReasons"]
    assert "stale_evidence" in readiness["blockingReasons"]
    assert "fallback_evidence" in readiness["blockingReasons"]


def test_home_analysis_response_adds_evidence_coverage_frame_across_public_payloads() -> None:
    response = _report_for(_result_with_quality())

    frame = response["evidenceCoverageFrame"]

    assert response["report"]["evidenceCoverageFrame"] == frame
    assert response["report"]["meta"]["evidenceCoverageFrame"] == frame
    assert response["report"]["details"]["analysis_result"]["evidenceCoverageFrame"] == frame
    assert set(frame) == {
        "priceHistory",
        "technicals",
        "fundamentals",
        "earnings",
        "news",
        "catalysts",
        "sentiment",
        "valuation",
        "liquidityContext",
        "macroContext",
    }
    assert frame["priceHistory"]["status"] == "available"
    assert frame["technicals"]["status"] == "available"
    assert frame["fundamentals"]["status"] == "available"
    assert frame["earnings"]["status"] == "available"
    assert frame["news"]["status"] == "available"
    assert frame["catalysts"]["status"] == "available"
    assert frame["sentiment"]["status"] == "available"
    assert frame["valuation"]["status"] == "available"
    assert frame["liquidityContext"]["status"] == "available"
    assert frame["macroContext"]["status"] in {"missing", "degraded"}


def test_home_analysis_response_adds_single_stock_evidence_packet_across_public_payloads() -> None:
    result = _result_with_quality(
        runtime_data={
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
        structured_overrides={
            "fundamentals": {
                "status": "ok",
                "source": "fmp",
                "sourceType": "official_public",
                "sourceTier": "score_grade",
                "trustLevel": "score_grade",
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
                "narrative_insights": ["盈利趋势稳定。"],
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
            "filings": {
                "status": "ok",
                "source": "sec_10q",
                "sourceTier": "official_public",
                "providerAuthority": "scoreGradeAllowed",
                "freshness": "fresh",
                "items": [
                    {
                        "formType": "10-Q",
                        "filedAt": "2026-04-30",
                        "periodEnd": "2026-03-31",
                        "accessionNumber": "0000320193-26-000077",
                    }
                ],
                "topEvidenceRefs": ["filing:10-Q-2026Q1"],
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
                        "summary": "季度盈利超预期，管理层上调指引。",
                        "source": "finnhub",
                        "published_at": "2026-06-03T13:00:00Z",
                        "sentiment": "positive",
                        "relevance_score": 0.96,
                    }
                ],
                "top_negative_items": [],
                "classified_items": [
                    {
                        "id": "news-earnings",
                        "title": "Apple beats earnings and raises guidance",
                        "summary": "季度盈利超预期，管理层上调指引。",
                        "source": "finnhub",
                        "news_published_at": "2026-06-03T13:00:00Z",
                        "sentiment": "positive",
                        "relevance_score": 0.96,
                    },
                    {
                        "id": "news-wwdc",
                        "title": "WWDC reveals on-device AI roadmap",
                        "summary": "新品发布提升产品催化预期。",
                        "source": "gnews",
                        "news_published_at": "2026-06-03T09:00:00Z",
                        "sentiment": "positive",
                        "relevance_score": 0.82,
                        "catalyst_type": "product_launch",
                    },
                ],
                "topEvidenceRefs": ["news:earnings", "news:wwdc"],
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
                        "summary": "管理层上调全年业绩预期。",
                        "source": "finnhub",
                        "published_at": "2026-06-03T13:05:00Z",
                        "relevance_score": 0.95,
                        "catalyst_type": "guidance",
                        "sentiment": "positive",
                    }
                ],
                "topEvidenceRefs": ["catalyst:guidance"],
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
        },
    )

    response = _report_for(result)
    packet = response["singleStockEvidencePacket"]

    assert response["report"]["singleStockEvidencePacket"] == packet
    assert response["report"]["meta"]["singleStockEvidencePacket"] == packet
    assert response["report"]["details"]["analysis_result"]["singleStockEvidencePacket"] == packet
    assert packet["contractVersion"] == "single_stock_evidence_packet_v1"
    assert packet["symbol"] == "AAPL"
    assert packet["market"] == "us"
    assert packet["packetState"] == "available"
    assert packet["fundamentalsEarnings"]["normalizerState"] == "ready"
    assert packet["newsCatalysts"]["extractionState"] == "ready"
    assert packet["newsCatalysts"]["topNewsItems"][0]["id"] == "news-earnings"
    assert packet["newsCatalysts"]["topCatalystItems"][0]["id"] == "cat-guidance"
    assert packet["domains"]["fundamentals"]["status"] == "available"
    assert packet["domains"]["earnings"]["status"] == "available"
    assert packet["domains"]["news"]["status"] == "available"
    assert packet["domains"]["catalysts"]["status"] == "available"
    assert set(packet) == {
        "contractVersion",
        "symbol",
        "market",
        "packetState",
        "domains",
        "sourceSummary",
        "missingEvidence",
        "blockingReasons",
        "nextEvidenceNeeded",
        "noAdviceBoundary",
        "debugRef",
        "fundamentalsEarnings",
        "newsCatalysts",
    }
    assert set(packet["domains"]) == {
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
    }
    assert packet["fundamentalsEarnings"]["contractVersion"] == "single_stock_fundamentals_earnings_normalizer_v1"
    assert packet["newsCatalysts"]["contractVersion"] == "single_stock_news_catalyst_extractor_v1"

def test_home_single_stock_evidence_packet_preserves_orcl_like_partial_without_raw_leakage() -> None:
    result = _result_with_quality(
        code="ORCL",
        data_quality_report={
            "dataQualityTier": "analysis_grade",
            "requiredAvailable": True,
            "confidenceCap": 70,
            "missingRequiredDomains": ["fundamentals", "earnings", "news", "catalyst_news_event"],
            "importantDomainsMissing": ["valuation", "sentiment"],
            "scoreSuppressed": False,
            "stanceGuardrail": "observe_only",
            "reasonCodes": ["fundamental_context_unavailable", "provider_timeout", "fallback_proxy_evidence"],
        },
        structured_overrides={
            "fundamentals": {
                "status": "missing",
                "source": None,
                "freshness": "unknown",
                "normalized": {},
            },
            "earnings_analysis": {
                "status": "missing",
                "source": None,
                "freshness": "unknown",
                "quarterly_series": [],
                "summary_flags": ["earnings_data_unavailable"],
            },
            "fundamental_context": {
                "status": "market not supported",
                "market": "us",
                "reason": "fundamental_context unavailable",
            },
            "sentiment_analysis": {
                "status": "partial",
                "source": "tavily",
                "sourceTier": "observation_only",
                "providerAuthority": "observationOnly",
                "freshness": "delayed",
                "sentiment_summary": "no_reliable_news",
                "top_positive_items": [],
                "top_negative_items": [],
                "classified_items": [],
                "raw_payload": {"headline": "do not leak"},
                "stack_trace": "Traceback: secret",
                "article_body": "Full article body should not leak into packet output.",
                "prompt": "buy now before the market opens",
            },
            "catalyst": {
                "status": "missing",
                "source": None,
                "freshness": "unknown",
                "classified_items": [],
            },
        },
        runtime_data={
            "market": {
                "status": "ok",
                "truth": "actual",
                "source": "polygon_us_grouped_daily",
                "fallback_occurred": False,
                "freshness": "fresh",
            },
            "fundamentals": {
                "status": "missing",
                "truth": "unavailable",
                "source": None,
                "fallback_occurred": False,
                "freshness": "unknown",
            },
            "news": {
                "status": "timeout",
                "truth": "unavailable",
                "source": None,
                "fallback_occurred": False,
                "freshness": "unknown",
                "error": "provider_timeout after 8s Authorization: Bearer secret",
                "final_reason": "finnhub timeout via cache_router token=secret",
                "router_debug": "news_router>provider_a",
            },
            "sentiment": {
                "status": "fallback",
                "truth": "unavailable",
                "source": "fallback_cache",
                "fallback_occurred": True,
                "freshness": "fallback",
                "final_reason": "traceback token=secret-value",
            },
        },
        score=72,
    )

    response = _report_for(result)
    packet = response["singleStockEvidencePacket"]
    serialized = str(packet).lower()

    assert response["report"]["details"]["analysis_result"]["score_state"] == "capped"
    assert packet["symbol"] == "ORCL"
    assert packet["packetState"] == "degraded"
    assert packet["domains"]["priceHistory"]["status"] == "available"
    assert packet["domains"]["technicals"]["status"] == "available"
    assert packet["domains"]["fundamentals"]["status"] == "missing"
    assert packet["domains"]["earnings"]["status"] == "missing"
    assert packet["domains"]["valuation"]["status"] == "missing"
    assert packet["domains"]["news"]["status"] == "blocked"
    assert packet["domains"]["catalysts"]["status"] in {"missing", "degraded"}
    assert packet["domains"]["sentiment"]["status"] == "degraded"
    assert packet["fundamentalsEarnings"]["normalizerState"] == "insufficient"
    assert packet["newsCatalysts"]["extractionState"] == "blocked"
    assert packet["newsCatalysts"]["topNewsItems"] == []
    assert "fundamental_context_unavailable" in packet["blockingReasons"]
    assert "fundamental_context_unavailable" in packet["fundamentalsEarnings"]["blockingReasons"]
    assert "provider_timeout" in packet["newsCatalysts"]["blockingReasons"]
    assert "authorization" not in serialized
    assert "bearer" not in serialized
    assert "cache_router" not in serialized
    assert "traceback" not in serialized
    assert "secret-value" not in serialized
    assert "article body" not in serialized
    assert "prompt:" not in serialized
    assert "buy now" not in serialized
    assert "sell now" not in serialized
    assert "submit order" not in serialized
    assert "trade now" not in serialized
    assert packet["newsCatalysts"]["sourceSummary"]["news"]["status"] == "blocked"
    assert packet["newsCatalysts"]["sourceSummary"]["catalysts"]["status"] in {"missing", "blocked"}
    assert packet["newsCatalysts"]["sourceSummary"]["sentiment"]["status"] == "missing"


def test_home_single_stock_evidence_packet_fails_closed_for_unsupported_hk_fundamental_context() -> None:
    result = _result_with_quality(
        code="HK00700",
        data_quality_report={
            "dataQualityTier": "analysis_grade",
            "requiredAvailable": True,
            "confidenceCap": 68,
            "missingRequiredDomains": ["fundamentals", "earnings", "news"],
            "importantDomainsMissing": ["valuation", "catalyst_news_event"],
            "scoreSuppressed": False,
            "stanceGuardrail": "observe_only",
            "reasonCodes": ["fundamental_context_unavailable", "provider_timeout"],
        },
        structured_overrides={
            "fundamentals": {
                "status": "missing",
                "source": None,
                "freshness": "unknown",
                "normalized": {},
            },
            "earnings_analysis": {
                "status": "missing",
                "source": None,
                "freshness": "unknown",
                "quarterly_series": [],
                "summary_flags": ["earnings_data_unavailable"],
            },
            "fundamental_context": {
                "status": "market not supported",
                "market": "hk",
                "reason": "fundamental_context unavailable",
            },
            "sentiment_analysis": {
                "status": "missing",
                "source": None,
                "freshness": "unknown",
                "top_positive_items": [],
                "top_negative_items": [],
                "classified_items": [],
            },
            "catalyst": {
                "status": "missing",
                "source": None,
                "freshness": "unknown",
                "classified_items": [],
            },
        },
        runtime_data={
            "market": {
                "status": "ok",
                "truth": "actual",
                "source": "twelve_data",
                "fallback_occurred": False,
                "freshness": "fresh",
            },
            "fundamentals": {
                "status": "missing",
                "truth": "unavailable",
                "source": None,
                "fallback_occurred": False,
                "freshness": "unknown",
            },
            "news": {
                "status": "timeout",
                "truth": "unavailable",
                "source": None,
                "fallback_occurred": False,
                "freshness": "unknown",
                "error": "provider_timeout after 8s",
            },
            "sentiment": {
                "status": "missing",
                "truth": "unavailable",
                "source": None,
                "fallback_occurred": False,
                "freshness": "unknown",
            },
        },
        score=66,
    )

    packet = _report_for(result)["singleStockEvidencePacket"]

    assert packet["market"] == "hk"
    assert packet["domains"]["priceHistory"]["status"] == "available"
    assert packet["domains"]["technicals"]["status"] == "available"
    assert packet["domains"]["fundamentals"]["status"] == "missing"
    assert packet["domains"]["earnings"]["status"] == "missing"
    assert packet["domains"]["valuation"]["status"] == "missing"
    assert packet["domains"]["news"]["status"] == "blocked"
    assert packet["fundamentalsEarnings"]["normalizerState"] == "insufficient"
    assert packet["newsCatalysts"]["extractionState"] == "blocked"
    assert "fundamental_context_unavailable" in packet["blockingReasons"]
    assert "fundamental_context_unavailable" in packet["fundamentalsEarnings"]["blockingReasons"]
    assert "fundamentals" in packet["fundamentalsEarnings"]["missingEvidence"]
    assert "provider_timeout" in packet["newsCatalysts"]["blockingReasons"]
    assert packet["newsCatalysts"]["topNewsItems"] == []
    assert packet["newsCatalysts"]["topCatalystItems"] == []


def test_home_evidence_coverage_frame_marks_orcl_like_partial_domains_truthfully() -> None:
    result = _result_with_quality(
        code="ORCL",
        data_quality_report={
            "dataQualityTier": "analysis_grade",
            "requiredAvailable": True,
            "confidenceCap": 70,
            "importantDomainsMissing": ["fundamentals", "news", "catalyst_news_event"],
            "scoreSuppressed": False,
            "stanceGuardrail": "observe_only",
            "reasonCodes": ["important_data_missing"],
        },
        structured_overrides={
            "fundamentals": {
                "status": "partial",
                "source": "fmp_fallback_chain",
                "sourceType": "official_public",
                "sourceTier": "score_grade",
                "freshness": "delayed",
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": False,
                "missing_fields": ["netIncome", "freeCashflow"],
                "normalized": {"trailingPE": 18.0},
            },
            "earnings_analysis": {
                "status": "partial",
                "summary_flags": ["earnings_partial"],
                "field_sources": {},
            },
            "sentiment_analysis": {
                "status": "weak",
                "source": "gnews",
                "sourceType": "public_api",
                "freshness": "delayed",
                "classified_items": [],
                "relevance_type": "low_relevance",
            },
            "catalyst": {"status": "missing", "source": None},
        },
        runtime_data={
            "market": {"status": "ok", "truth": "actual", "source": "polygon_us_grouped_daily", "fallback_occurred": False},
            "fundamentals": {"status": "partial", "truth": "actual", "source": "fmp", "fallback_occurred": True},
            "news": {"status": "partial", "truth": "actual", "source": "gnews", "fallback_occurred": True},
            "sentiment": {"status": "partial", "truth": "actual", "source": "gnews", "fallback_occurred": True},
        },
    )

    frame = _report_for(result)["evidenceCoverageFrame"]

    assert frame["priceHistory"]["status"] == "available"
    assert frame["technicals"]["status"] == "available"
    assert frame["fundamentals"]["status"] == "degraded"
    assert frame["earnings"]["status"] == "degraded"
    assert frame["news"]["status"] == "degraded"
    assert frame["catalysts"]["status"] in {"degraded", "missing"}
    assert frame["sentiment"]["status"] == "degraded"
    assert frame["valuation"]["status"] == "degraded"


def test_home_evidence_coverage_frame_marks_missing_fundamentals_news_and_catalysts() -> None:
    result = _result_with_quality(
        data_quality_report={
            "dataQualityTier": "partial",
            "requiredAvailable": True,
            "confidenceCap": 65,
            "importantDomainsMissing": ["fundamentals", "catalyst_news_event"],
            "optionalMissing": ["news", "sentiment", "detailed_fundamentals"],
            "scoreSuppressed": False,
            "stanceGuardrail": "observe_only",
        },
        structured_overrides={
            "fundamentals": {"status": "missing", "source": None, "normalized": {}},
            "earnings_analysis": {"status": "partial", "field_sources": {}, "summary_flags": ["earnings_data_unavailable"]},
            "sentiment_analysis": {"status": "missing", "source": None, "classified_items": []},
            "catalyst": {"status": "missing", "source": None},
        },
        runtime_data={
            "market": {"status": "ok", "truth": "actual", "source": "polygon_us_grouped_daily", "fallback_occurred": False},
            "fundamentals": {"status": "missing", "truth": "unavailable", "source": None, "fallback_occurred": False},
            "news": {"status": "missing", "truth": "unavailable", "source": None, "fallback_occurred": False},
            "sentiment": {"status": "missing", "truth": "unavailable", "source": None, "fallback_occurred": False},
        },
    )

    frame = _report_for(result)["evidenceCoverageFrame"]

    assert frame["fundamentals"]["status"] == "missing"
    assert frame["news"]["status"] == "missing"
    assert frame["catalysts"]["status"] == "missing"
    assert frame["fundamentals"]["missingReasons"]
    assert frame["news"]["missingReasons"]
    assert frame["catalysts"]["missingReasons"]


def test_home_evidence_coverage_frame_marks_provider_timeout_and_fallback_without_raw_leakage() -> None:
    result = _result_with_quality(
        data_quality_report={
            "dataQualityTier": "analysis_grade",
            "requiredAvailable": False,
            "confidenceCap": 55,
            "missingRequiredDomains": ["news", "catalyst_news_event"],
            "scoreSuppressed": True,
            "scoreSuppressedReason": "required_evidence_missing",
            "reasonCodes": ["required_data_missing", "stale_required_source"],
            "stanceGuardrail": "no_score",
        },
        structured_overrides={
            "fundamentals": {
                "status": "partial",
                "source": "fallback_cache",
                "sourceType": "fallback",
                "sourceTier": "score_grade",
                "freshness": "fallback",
                "isFallback": True,
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": False,
                "normalized": {"trailingPE": 19.2},
            },
            "sentiment_analysis": {
                "status": "weak",
                "source": "gnews",
                "sourceType": "public_api",
                "freshness": "stale",
                "classified_items": [],
                "relevance_type": "low_relevance",
            },
            "catalyst": {"status": "missing", "source": None},
        },
        runtime_data={
            "market": {"status": "ok", "truth": "actual", "source": "polygon_us_grouped_daily", "fallback_occurred": False},
            "fundamentals": {"status": "partial", "truth": "actual", "source": "fallback_cache", "fallback_occurred": True},
            "news": {
                "status": "failed",
                "truth": "unavailable",
                "source": None,
                "fallback_occurred": False,
                "final_reason": "finnhub timeout after 5s via cache_router stage=hot_path",
            },
            "sentiment": {
                "status": "failed",
                "truth": "unavailable",
                "source": None,
                "fallback_occurred": False,
                "final_reason": "traceback token=secret-value",
            },
        },
    )

    frame = _report_for(result)["evidenceCoverageFrame"]
    serialized = str(frame).lower()

    assert frame["fundamentals"]["status"] == "degraded"
    assert frame["fundamentals"]["fallbackOrProxy"] is True
    assert frame["news"]["status"] == "blocked"
    assert frame["sentiment"]["status"] == "blocked"
    assert "provider_timeout" in frame["news"]["missingReasons"]
    assert "fallback_proxy_evidence" in frame["fundamentals"]["missingReasons"]
    assert "timeout after 5s" not in serialized
    assert "cache_router" not in serialized
    assert "traceback" not in serialized
    assert "secret-value" not in serialized


def test_home_analysis_response_adds_evidence_citation_frame_across_public_payloads() -> None:
    result = _result_with_quality(
        runtime_data={
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
        structured_overrides={
            "fundamentals": {
                "status": "ok",
                "source": "fmp",
                "sourceType": "official_public",
                "sourceTier": "score_grade",
                "trustLevel": "score_grade",
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
            },
            "earnings_analysis": {
                "status": "ok",
                "source": "fmp_income_statement",
                "field_sources": {"quarterly_series": "fmp_income_statement"},
                "summary_flags": ["quarterly_series_available", "financial_report_available"],
                "narrative_insights": ["盈利趋势稳定。"],
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
            "filings": {
                "status": "ok",
                "source": "sec_10q",
                "sourceTier": "official_public",
                "providerAuthority": "scoreGradeAllowed",
                "freshness": "fresh",
                "items": [
                    {
                        "formType": "10-Q",
                        "filedAt": "2026-04-30",
                        "periodEnd": "2026-03-31",
                        "accessionNumber": "0000320193-26-000077",
                    }
                ],
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
                        "summary": "季度盈利超预期，管理层上调指引。",
                        "source": "finnhub",
                        "published_at": "2026-06-03T13:00:00Z",
                        "sentiment": "positive",
                        "relevance_score": 0.96,
                    }
                ],
                "top_negative_items": [],
                "classified_items": [
                    {
                        "id": "news-earnings",
                        "title": "Apple beats earnings and raises guidance",
                        "summary": "季度盈利超预期，管理层上调指引。",
                        "source": "finnhub",
                        "news_published_at": "2026-06-03T13:00:00Z",
                        "sentiment": "positive",
                        "relevance_score": 0.96,
                    },
                    {
                        "id": "news-wwdc",
                        "title": "WWDC reveals on-device AI roadmap",
                        "summary": "新品发布提升产品催化预期。",
                        "source": "gnews",
                        "news_published_at": "2026-06-03T09:00:00Z",
                        "sentiment": "positive",
                        "relevance_score": 0.82,
                        "catalyst_type": "product_launch",
                    },
                ],
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
                        "summary": "管理层上调全年业绩预期。",
                        "source": "finnhub",
                        "published_at": "2026-06-03T13:05:00Z",
                        "relevance_score": 0.95,
                        "catalyst_type": "guidance",
                        "sentiment": "positive",
                    }
                ],
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
            },
        },
    )

    response = _report_for(result)
    frame = response["evidenceCitationFrame"]

    assert response["report"]["evidenceCitationFrame"] == frame
    assert response["report"]["meta"]["evidenceCitationFrame"] == frame
    assert response["report"]["details"]["analysis_result"]["evidenceCitationFrame"] == frame
    assert frame["contractVersion"] == "home_report_evidence_citation_frame_v1"
    assert frame["frameState"] == "ready"
    assert frame["symbol"] == "AAPL"
    assert frame["market"] == "us"
    assert frame["missingEvidence"] == []
    assert frame["blockingReasons"] == []
    assert frame["noAdviceBoundary"] is True
    assert isinstance(frame["citedEvidence"], list)
    assert {item["domain"] for item in frame["citedEvidence"]} >= {
        "fundamentals",
        "earnings",
        "valuation",
        "news",
        "catalysts",
        "sentiment",
    }
    assert isinstance(frame["domainCoverage"], list)
    assert isinstance(frame["nextEvidenceNeeded"], list)
    assert {item["domain"] for item in frame["domainCoverage"]} >= {
        "fundamentals",
        "earnings",
        "news",
        "catalysts",
    }


def test_home_analysis_response_adds_source_provenance_frame_across_public_payloads() -> None:
    result = _result_with_quality(
        runtime_data={
            "market": {
                "status": "ok",
                "truth": "actual",
                "source": "polygon_us_grouped_daily",
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
        structured_overrides={
            "fundamentals": {
                "status": "ok",
                "source": "fmp",
                "sourceType": "official_public",
                "sourceTier": "score_grade",
                "trustLevel": "score_grade",
                "freshness": "fresh",
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "normalized": {"marketCap": 3010000000000, "trailingPE": 24.8},
            },
            "earnings_analysis": {
                "status": "ok",
                "source": "fmp_income_statement",
                "field_sources": {"quarterly_series": "fmp_income_statement"},
                "summary_flags": ["quarterly_series_available"],
                "narrative_insights": ["盈利趋势稳定。"],
                "sourceTier": "score_grade",
                "freshness": "fresh",
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "quarterly_series": [{"quarter": "2026Q1", "revenue": 90340000000}],
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
                "classified_items": [{"id": "news-earnings", "title": "Apple beats earnings", "source": "finnhub"}],
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
                "classified_items": [{"id": "cat-guidance", "headline": "Apple raises guidance", "source": "gnews"}],
            },
        },
    )

    response = _report_for(result)
    frame = response["sourceProvenanceFrame"]
    report = response["report"]

    assert report["sourceProvenanceFrame"] == frame
    assert report["meta"]["sourceProvenanceFrame"] == frame
    assert report["details"]["analysis_result"]["sourceProvenanceFrame"] == frame
    assert frame == response["sourceProvenanceFrame"]
    assert frame == json.loads(json.dumps(frame, ensure_ascii=False))
    assert [entry["evidenceDomain"] for entry in frame] == [
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
    by_domain = {entry["evidenceDomain"]: entry for entry in frame}
    assert by_domain["priceHistory"]["contractVersion"] == "source_provenance_v1"
    assert by_domain["priceHistory"]["sourceId"] == "polygon_us_grouped_daily"
    assert by_domain["priceHistory"]["scoreContributionAllowed"] is True
    assert by_domain["fundamentals"]["sourceId"] == "fmp"
    assert by_domain["fundamentals"]["scoreContributionAllowed"] is True
    assert by_domain["news"]["observationOnly"] is True
    assert by_domain["news"]["scoreContributionAllowed"] is False
    assert response["singleStockEvidencePacket"]["domains"]["fundamentals"]["status"] == "available"
    assert response["evidenceCitationFrame"]["frameState"] == "ready"
    assert response["researchReadiness"]["consumerActionBoundary"] == "no_advice"


def test_home_evidence_citation_frame_preserves_orcl_like_partial_without_raw_leakage() -> None:
    result = _result_with_quality(
        code="ORCL",
        data_quality_report={
            "dataQualityTier": "analysis_grade",
            "requiredAvailable": True,
            "confidenceCap": 70,
            "missingRequiredDomains": ["fundamentals", "earnings", "news", "catalyst_news_event"],
            "importantDomainsMissing": ["valuation", "sentiment"],
            "scoreSuppressed": False,
            "stanceGuardrail": "observe_only",
            "reasonCodes": ["fundamental_context_unavailable", "provider_timeout", "fallback_proxy_evidence"],
        },
        structured_overrides={
            "fundamentals": {
                "status": "missing",
                "source": None,
                "freshness": "unknown",
                "normalized": {},
            },
            "earnings_analysis": {
                "status": "missing",
                "source": None,
                "freshness": "unknown",
                "quarterly_series": [],
                "summary_flags": ["earnings_data_unavailable"],
            },
            "fundamental_context": {
                "status": "market not supported",
                "market": "us",
                "reason": "fundamental_context unavailable",
            },
            "sentiment_analysis": {
                "status": "partial",
                "source": "tavily",
                "sourceTier": "observation_only",
                "providerAuthority": "observationOnly",
                "freshness": "delayed",
                "sentiment_summary": "no_reliable_news",
                "top_positive_items": [],
                "top_negative_items": [],
                "classified_items": [],
                "raw_payload": {"headline": "do not leak"},
                "stack_trace": "Traceback: secret",
                "article_body": "Full article body should not leak into packet output.",
                "prompt": "buy now before the market opens",
            },
            "catalyst": {
                "status": "missing",
                "source": None,
                "freshness": "unknown",
                "classified_items": [],
            },
        },
        runtime_data={
            "market": {
                "status": "ok",
                "truth": "actual",
                "source": "polygon_us_grouped_daily",
                "fallback_occurred": False,
                "freshness": "fresh",
            },
            "fundamentals": {
                "status": "missing",
                "truth": "unavailable",
                "source": None,
                "fallback_occurred": False,
                "freshness": "unknown",
            },
            "news": {
                "status": "timeout",
                "truth": "unavailable",
                "source": None,
                "fallback_occurred": False,
                "freshness": "unknown",
                "error": "provider_timeout after 8s Authorization: Bearer secret",
                "final_reason": "finnhub timeout via cache_router token=secret",
                "router_debug": "news_router>provider_a",
            },
            "sentiment": {
                "status": "fallback",
                "truth": "unavailable",
                "source": "fallback_cache",
                "fallback_occurred": True,
                "freshness": "fallback",
                "final_reason": "traceback token=secret-value",
            },
        },
        score=72,
    )

    response = _report_for(result)
    frame = response["evidenceCitationFrame"]
    serialized = str(frame).lower()

    assert frame["frameState"] == "blocked"
    assert frame["symbol"] == "ORCL"
    assert "fundamentals" in frame["missingEvidence"]
    assert "news" in frame["missingEvidence"]
    assert "fundamental_context_unavailable" in frame["blockingReasons"]
    assert "provider_timeout" in frame["blockingReasons"]
    assert frame["citedEvidence"] == []
    assert frame["nextEvidenceNeeded"]
    assert "authorization" not in serialized
    assert "bearer" not in serialized
    assert "cache_router" not in serialized
    assert "traceback" not in serialized
    assert "secret-value" not in serialized
    assert "article body" not in serialized
    assert "prompt:" not in serialized
    assert "buy now" not in serialized
    assert "sell now" not in serialized
    assert "submit order" not in serialized
    assert "trade now" not in serialized


def test_home_source_provenance_frame_preserves_orcl_like_partial_fail_closed_without_raw_leakage() -> None:
    result = _result_with_quality(
        code="ORCL",
        data_quality_report={
            "dataQualityTier": "analysis_grade",
            "requiredAvailable": True,
            "confidenceCap": 70,
            "missingRequiredDomains": ["fundamentals", "earnings", "news", "catalyst_news_event"],
            "importantDomainsMissing": ["valuation", "sentiment"],
            "scoreSuppressed": False,
            "stanceGuardrail": "observe_only",
            "reasonCodes": ["fundamental_context_unavailable", "provider_timeout", "fallback_proxy_evidence"],
        },
        structured_overrides={
            "fundamentals": {
                "status": "missing",
                "source": None,
                "freshness": "unknown",
                "normalized": {},
            },
            "earnings_analysis": {
                "status": "missing",
                "source": None,
                "freshness": "unknown",
                "quarterly_series": [],
                "summary_flags": ["earnings_data_unavailable"],
            },
            "fundamental_context": {
                "status": "market not supported",
                "market": "us",
                "reason": "fundamental_context unavailable",
            },
            "sentiment_analysis": {
                "status": "partial",
                "source": "tavily",
                "sourceTier": "observation_only",
                "providerAuthority": "observationOnly",
                "freshness": "delayed",
                "classified_items": [],
                "raw_payload": {"headline": "do not leak"},
                "stack_trace": "Traceback: secret",
                "article_body": "Full article body should not leak into packet output.",
                "prompt": "buy now before the market opens",
            },
            "catalyst": {
                "status": "missing",
                "source": None,
                "freshness": "unknown",
                "classified_items": [],
            },
        },
        runtime_data={
            "market": {
                "status": "ok",
                "truth": "actual",
                "source": "polygon_us_grouped_daily",
                "fallback_occurred": False,
                "freshness": "fresh",
            },
            "fundamentals": {
                "status": "missing",
                "truth": "unavailable",
                "source": None,
                "fallback_occurred": False,
                "freshness": "unknown",
            },
            "news": {
                "status": "timeout",
                "truth": "unavailable",
                "source": None,
                "fallback_occurred": False,
                "freshness": "unknown",
                "error": "provider_timeout after 8s Authorization: Bearer secret",
                "final_reason": "finnhub timeout via cache_router token=secret",
                "router_debug": "news_router>provider_a",
            },
            "sentiment": {
                "status": "fallback",
                "truth": "unavailable",
                "source": "fallback_cache",
                "fallback_occurred": True,
                "freshness": "fallback",
                "final_reason": "traceback token=secret-value",
            },
        },
        score=72,
    )

    response = _report_for(result)
    frame = response["sourceProvenanceFrame"]
    by_domain = {entry["evidenceDomain"]: entry for entry in frame}
    serialized = json.dumps(frame, ensure_ascii=False).lower()

    assert response["report"]["sourceProvenanceFrame"] == frame
    assert response["report"]["meta"]["sourceProvenanceFrame"] == frame
    assert response["report"]["details"]["analysis_result"]["sourceProvenanceFrame"] == frame
    assert by_domain["fundamentals"]["sourceId"] == "unknown_source"
    assert by_domain["fundamentals"]["freshnessState"] == "unknown"
    assert by_domain["fundamentals"]["scoreContributionAllowed"] is False
    assert "fundamental_context_unavailable" in by_domain["fundamentals"]["limitations"]
    assert by_domain["news"]["sourceId"] == "unknown_source"
    assert by_domain["news"]["scoreContributionAllowed"] is False
    assert "provider_timeout" in by_domain["news"]["limitations"]
    assert by_domain["sentiment"]["fallbackOrProxy"] is True
    assert by_domain["sentiment"]["scoreContributionAllowed"] is False
    for forbidden in (
        "authorization",
        "bearer",
        "cache_router",
        "traceback",
        "secret-value",
        "article body",
        "prompt:",
        "buy now",
        "sell now",
        "submit order",
        "trade now",
    ):
        assert forbidden not in serialized


def test_home_evidence_citation_frame_fails_closed_for_unsupported_hk_fundamental_context() -> None:
    result = _result_with_quality(
        code="HK00700",
        data_quality_report={
            "dataQualityTier": "analysis_grade",
            "requiredAvailable": True,
            "confidenceCap": 68,
            "missingRequiredDomains": ["fundamentals", "earnings", "news"],
            "importantDomainsMissing": ["valuation", "catalyst_news_event"],
            "scoreSuppressed": False,
            "stanceGuardrail": "observe_only",
            "reasonCodes": ["fundamental_context_unavailable", "provider_timeout"],
        },
        structured_overrides={
            "fundamentals": {
                "status": "missing",
                "source": None,
                "freshness": "unknown",
                "normalized": {},
            },
            "earnings_analysis": {
                "status": "missing",
                "source": None,
                "freshness": "unknown",
                "quarterly_series": [],
                "summary_flags": ["earnings_data_unavailable"],
            },
            "fundamental_context": {
                "status": "market not supported",
                "market": "hk",
                "reason": "fundamental_context unavailable",
            },
            "sentiment_analysis": {
                "status": "missing",
                "source": None,
                "freshness": "unknown",
                "top_positive_items": [],
                "top_negative_items": [],
                "classified_items": [],
            },
            "catalyst": {
                "status": "missing",
                "source": None,
                "freshness": "unknown",
                "classified_items": [],
            },
        },
        runtime_data={
            "market": {
                "status": "ok",
                "truth": "actual",
                "source": "twelve_data",
                "fallback_occurred": False,
                "freshness": "fresh",
            },
            "fundamentals": {
                "status": "missing",
                "truth": "unavailable",
                "source": None,
                "fallback_occurred": False,
                "freshness": "unknown",
            },
            "news": {
                "status": "timeout",
                "truth": "unavailable",
                "source": None,
                "fallback_occurred": False,
                "freshness": "unknown",
                "error": "provider_timeout after 8s",
            },
            "sentiment": {
                "status": "missing",
                "truth": "unavailable",
                "source": None,
                "fallback_occurred": False,
                "freshness": "unknown",
            },
        },
        score=66,
    )

    frame = _report_for(result)["evidenceCitationFrame"]

    assert frame["market"] == "hk"
    assert frame["frameState"] == "blocked"
    assert "fundamentals" in frame["missingEvidence"]
    assert "news" in frame["missingEvidence"]
    assert "fundamental_context_unavailable" in frame["blockingReasons"]
    assert "provider_timeout" in frame["blockingReasons"]
    assert frame["citedEvidence"] == []
