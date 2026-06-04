# -*- coding: utf-8 -*-
"""Tests for the bounded Home LLM evidence input adapter."""

from __future__ import annotations

import ast
import importlib
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

if "litellm" not in sys.modules:
    sys.modules["litellm"] = MagicMock()

from src.core.pipeline import StockAnalysisPipeline


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = REPO_ROOT / "src/services/home_llm_evidence_input.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "yfinance",
    "src.services.market_cache",
    "src.services.data_source_router",
    "src.services.provider_capability_matrix",
    "src.services.analysis_provider_planner",
)
REQUIRED_FIELDS = {
    "contractVersion",
    "symbol",
    "market",
    "inputState",
    "domainSummaries",
    "evidenceIndex",
    "missingEvidence",
    "degradedEvidence",
    "blockedEvidence",
    "authorityNotes",
    "freshnessNotes",
    "noAdviceBoundary",
    "debugRef",
}
REQUIRED_INDEX_FIELDS = {
    "id",
    "domain",
    "label",
    "summary",
    "sourceId",
    "providerAuthority",
    "freshness",
    "asOf",
    "limitation",
}
FORBIDDEN_SERIALIZED_TOKENS = (
    "authorization",
    "api_key",
    "cookie",
    "stack trace",
    "traceback",
    "router_debug",
    "cache_key",
    "internal_env",
    "submit order",
    "trade now",
    "broker",
    "raw_prompt",
    "prompt_dump",
)


def _load_helper_module() -> Any:
    try:
        return importlib.import_module("src.services.home_llm_evidence_input")
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised in RED run
        pytest.fail(f"home_llm_evidence_input helper missing: {exc}")


def _helper_imports() -> set[str]:
    if not HELPER_PATH.exists():
        pytest.fail(f"helper file missing: {HELPER_PATH}")
    tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def _payload_orcl_partial() -> dict[str, Any]:
    return {
        "singleStockEvidencePacket": {
            "contractVersion": "single_stock_evidence_packet_v1",
            "symbol": "ORCL",
            "market": "us",
            "packetState": "degraded",
            "domains": {
                "priceHistory": {
                    "status": "available",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "fresh",
                    "missingReasons": [],
                },
                "technicals": {
                    "status": "available",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "fresh",
                    "missingReasons": [],
                },
                "fundamentals": {
                    "status": "missing",
                    "providerAuthority": "observationOnly",
                    "freshness": "unknown",
                    "missingReasons": ["fundamental_context_unavailable"],
                },
                "earnings": {
                    "status": "degraded",
                    "providerAuthority": "observationOnly",
                    "freshness": "stale",
                    "missingReasons": ["stale_evidence"],
                },
                "filings": {
                    "status": "missing",
                    "providerAuthority": "observationOnly",
                    "freshness": "unknown",
                    "missingReasons": [],
                },
                "news": {
                    "status": "blocked",
                    "providerAuthority": "observationOnly",
                    "freshness": "unknown",
                    "missingReasons": ["provider_timeout"],
                },
                "catalysts": {
                    "status": "missing",
                    "providerAuthority": "observationOnly",
                    "freshness": "unknown",
                    "missingReasons": ["no_structured_items"],
                },
                "sentiment": {
                    "status": "missing",
                    "providerAuthority": "observationOnly",
                    "freshness": "unknown",
                    "missingReasons": ["no_structured_items"],
                },
                "valuation": {
                    "status": "degraded",
                    "providerAuthority": "observationOnly",
                    "freshness": "delayed",
                    "missingReasons": ["fallback_proxy_evidence"],
                },
                "sectorTheme": {
                    "status": "missing",
                    "providerAuthority": "observationOnly",
                    "freshness": "unknown",
                    "missingReasons": [],
                },
                "macroLiquidity": {
                    "status": "missing",
                    "providerAuthority": "observationOnly",
                    "freshness": "unknown",
                    "missingReasons": [],
                },
            },
            "sourceSummary": {
                "availableCount": 2,
                "degradedCount": 2,
                "missingCount": 5,
                "blockedCount": 1,
                "pendingCount": 0,
            },
            "missingEvidence": ["fundamentals", "news", "catalysts", "sentiment"],
            "blockingReasons": [
                "fundamental_context_unavailable",
                "provider_timeout",
                "fallback_proxy_evidence",
                "stale_evidence",
            ],
            "nextEvidenceNeeded": [
                "补充基本面证据",
                "补充新闻证据",
                "补充催化剂证据",
            ],
            "noAdviceBoundary": {"state": "ready"},
            "debugRef": "analysis:orcl-001",
        },
        "fundamentalsEarnings": {
            "contractVersion": "single_stock_fundamentals_earnings_normalizer_v1",
            "symbol": "ORCL",
            "market": "us",
            "normalizerState": "insufficient",
            "domains": {
                "fundamentals": {
                    "status": "missing",
                    "reasonCodes": ["fundamental_context_unavailable"],
                    "freshness": "unknown",
                    "bestAuthorityTier": "unknown",
                },
                "earnings": {
                    "status": "degraded",
                    "reasonCodes": ["stale_evidence"],
                    "freshness": "stale",
                    "bestAuthorityTier": "observation_only",
                },
                "valuation": {
                    "status": "degraded",
                    "reasonCodes": ["fallback_proxy_evidence"],
                    "freshness": "delayed",
                    "bestAuthorityTier": "observation_only",
                },
                "filings": {
                    "status": "missing",
                    "reasonCodes": [],
                    "freshness": "unknown",
                    "bestAuthorityTier": "unknown",
                },
            },
            "evidenceRefs": [
                {
                    "id": "earnings-q1",
                    "domain": "earnings",
                    "label": "Latest quarter",
                    "value": {"revenue": 14500000000, "netIncome": 2200000000},
                    "period": "2026Q1",
                    "asOf": "2026-03-31",
                    "sourceId": "fmp_income_statement",
                    "sourceTier": "score_grade",
                    "providerAuthority": "observationOnly",
                    "freshness": "stale",
                    "confidence": "medium",
                    "limitations": [
                        "Stale evidence only.",
                        "authorization: should be removed",
                    ],
                },
                {
                    "id": "valuation-pe",
                    "domain": "valuation",
                    "label": "Trailing PE",
                    "value": 21.7,
                    "period": "latest",
                    "asOf": "2026-06-03",
                    "sourceId": "yfinance",
                    "sourceTier": "observation_only",
                    "providerAuthority": "observationOnly",
                    "freshness": "delayed",
                    "confidence": "medium",
                    "limitations": ["Proxy fallback evidence."],
                },
            ],
            "missingEvidence": ["fundamentals"],
            "blockingReasons": [
                "fundamental_context_unavailable",
                "stale_evidence",
                "fallback_proxy_evidence",
            ],
            "nextEvidenceNeeded": ["补充基本面证据"],
            "sourceSummary": {},
            "noAdviceBoundary": {"state": "ready"},
            "debugRef": "analysis:orcl-001",
        },
        "newsCatalysts": {
            "contractVersion": "single_stock_news_catalyst_extractor_v1",
            "symbol": "ORCL",
            "market": "us",
            "extractionState": "blocked",
            "topNewsItems": [],
            "topCatalystItems": [],
            "sentimentSummary": {
                "status": "missing",
                "label": "neutral",
                "sourceIds": ["manual_unknown"],
                "bestAuthorityTier": "unknown",
                "freshness": "unknown",
                "scoreContributionAllowed": False,
                "limitations": ["No structured news items were available."],
            },
            "missingEvidence": ["news", "catalysts", "sentiment"],
            "blockingReasons": ["provider_timeout", "news_context_only"],
            "nextEvidenceNeeded": ["补充新闻证据"],
            "sourceSummary": {
                "news": {"status": "blocked", "bestAuthorityTier": "unknown", "freshnessClass": "unknown"},
                "catalysts": {"status": "missing", "bestAuthorityTier": "unknown", "freshnessClass": "unknown"},
                "sentiment": {"status": "missing", "bestAuthorityTier": "unknown", "freshnessClass": "unknown"},
            },
            "noAdviceBoundary": {"state": "ready"},
            "debugRef": "analysis:orcl-001",
        },
        "researchReadiness": {
            "readinessState": "insufficient",
            "missingEvidence": ["fundamentals", "news", "catalyst"],
            "blockingReasons": ["missing_required_evidence"],
        },
        "evidenceCoverageFrame": {
            "fundamentals": {
                "status": "missing",
                "sourceAuthority": "observationOnly",
                "freshness": "unknown",
                "missingReasons": ["fundamental_context_unavailable"],
            },
            "earnings": {
                "status": "degraded",
                "sourceAuthority": "observationOnly",
                "freshness": "stale",
                "missingReasons": ["stale_evidence"],
            },
            "news": {
                "status": "blocked",
                "sourceAuthority": "observationOnly",
                "freshness": "unknown",
                "missingReasons": ["provider_timeout"],
            },
        },
        "dataQualityReport": {
            "dataQualityTier": "analysis_grade",
            "confidenceCap": 70,
            "reasonCodes": ["stale_required_source", "partial_optional_enrichment"],
            "freshness": {"marketTimestamp": "2026-06-04T09:30:00-04:00"},
        },
        "debugRef": "analysis:orcl-001",
    }


def _payload_for_trimming() -> dict[str, Any]:
    payload = _payload_orcl_partial()
    packet = payload["singleStockEvidencePacket"]
    packet["symbol"] = "AAPL"
    packet["market"] = "us"
    packet["packetState"] = "available"
    packet["missingEvidence"] = []
    packet["blockingReasons"] = []
    packet["domains"]["fundamentals"]["status"] = "available"
    packet["domains"]["fundamentals"]["providerAuthority"] = "scoreGradeAllowed"
    packet["domains"]["fundamentals"]["freshness"] = "fresh"
    packet["domains"]["fundamentals"]["missingReasons"] = []
    packet["domains"]["earnings"]["status"] = "available"
    packet["domains"]["earnings"]["providerAuthority"] = "scoreGradeAllowed"
    packet["domains"]["earnings"]["freshness"] = "fresh"
    packet["domains"]["earnings"]["missingReasons"] = []
    packet["domains"]["news"]["status"] = "available"
    packet["domains"]["news"]["providerAuthority"] = "observationOnly"
    packet["domains"]["news"]["freshness"] = "fresh"
    packet["domains"]["news"]["missingReasons"] = []
    packet["domains"]["catalysts"]["status"] = "available"
    packet["domains"]["catalysts"]["providerAuthority"] = "observationOnly"
    packet["domains"]["catalysts"]["freshness"] = "fresh"
    packet["domains"]["catalysts"]["missingReasons"] = []
    packet["domains"]["sentiment"]["status"] = "degraded"
    packet["domains"]["sentiment"]["missingReasons"] = ["news_context_only"]
    payload["fundamentalsEarnings"]["normalizerState"] = "observe_only"
    payload["fundamentalsEarnings"]["domains"]["fundamentals"]["status"] = "available"
    payload["fundamentalsEarnings"]["domains"]["earnings"]["status"] = "available"
    payload["fundamentalsEarnings"]["domains"]["valuation"]["status"] = "available"
    payload["fundamentalsEarnings"]["evidenceRefs"] = [
        {
            "id": f"fund-{idx}",
            "domain": "fundamentals",
            "label": f"Fund Metric {idx}",
            "value": {"metric": idx, "raw_prompt": "must disappear"},
            "period": "latest",
            "asOf": f"2026-06-0{idx}",
            "sourceId": "fmp",
            "sourceTier": "score_grade",
            "providerAuthority": "scoreGradeAllowed",
            "freshness": "fresh",
            "confidence": "high",
            "limitations": [f"safe limitation {idx}", "cookie=secret"],
        }
        for idx in range(1, 6)
    ] + [
        {
            "id": "earn-1",
            "domain": "earnings",
            "label": "Earnings trend",
            "value": {"yoyRevenueGrowth": 0.12},
            "period": "2026Q1",
            "asOf": "2026-03-31",
            "sourceId": "fmp_income_statement",
            "sourceTier": "score_grade",
            "providerAuthority": "scoreGradeAllowed",
            "freshness": "fresh",
            "confidence": "high",
            "limitations": ["safe earnings note"],
        },
        {
            "id": "earn-2",
            "domain": "earnings",
            "label": "Quarter summary",
            "value": {"revenue": 10},
            "period": "2025Q4",
            "asOf": "2025-12-31",
            "sourceId": "fmp_income_statement",
            "sourceTier": "score_grade",
            "providerAuthority": "scoreGradeAllowed",
            "freshness": "fresh",
            "confidence": "high",
            "limitations": ["safe earnings note 2"],
        },
        {
            "id": "earn-3",
            "domain": "earnings",
            "label": "Trim me",
            "value": {"revenue": 11},
            "period": "2025Q3",
            "asOf": "2025-09-30",
            "sourceId": "fmp_income_statement",
            "sourceTier": "score_grade",
            "providerAuthority": "scoreGradeAllowed",
            "freshness": "fresh",
            "confidence": "high",
            "limitations": ["safe earnings note 3"],
        },
        {
            "id": "val-1",
            "domain": "valuation",
            "label": "Trailing PE",
            "value": 24.8,
            "period": "latest",
            "asOf": "2026-06-04",
            "sourceId": "fmp",
            "sourceTier": "score_grade",
            "providerAuthority": "scoreGradeAllowed",
            "freshness": "fresh",
            "confidence": "high",
            "limitations": ["safe valuation note"],
        },
        {
            "id": "val-2",
            "domain": "valuation",
            "label": "Price to Book",
            "value": 8.7,
            "period": "latest",
            "asOf": "2026-06-04",
            "sourceId": "fmp",
            "sourceTier": "score_grade",
            "providerAuthority": "scoreGradeAllowed",
            "freshness": "fresh",
            "confidence": "high",
            "limitations": ["safe valuation note 2"],
        },
        {
            "id": "val-3",
            "domain": "valuation",
            "label": "Trim me val",
            "value": 9.1,
            "period": "latest",
            "asOf": "2026-06-04",
            "sourceId": "fmp",
            "sourceTier": "score_grade",
            "providerAuthority": "scoreGradeAllowed",
            "freshness": "fresh",
            "confidence": "high",
            "limitations": ["safe valuation note 3"],
        },
    ]
    payload["newsCatalysts"]["extractionState"] = "observe_only"
    payload["newsCatalysts"]["topNewsItems"] = [
        {
            "id": f"news-{idx}",
            "domain": "news",
            "title": f"Apple headline {idx}",
            "summary": "A" * 260,
            "sourceId": "gnews",
            "sourceTier": "official_public",
            "providerAuthority": "observationOnly",
            "publishedAt": f"2026-06-0{idx}T08:00:00Z",
            "freshness": "fresh",
            "sentiment": "positive",
            "catalystType": "unknown",
            "relevanceScore": 0.9 - idx * 0.01,
            "limitations": ["public news citation", "traceback should disappear"],
        }
        for idx in range(1, 6)
    ]
    payload["newsCatalysts"]["topCatalystItems"] = [
        {
            "id": f"cat-{idx}",
            "domain": "catalysts",
            "title": f"Apple catalyst {idx}",
            "summary": f"Catalyst summary {idx}",
            "sourceId": "gnews",
            "sourceTier": "official_public",
            "providerAuthority": "observationOnly",
            "publishedAt": f"2026-06-0{idx}T09:00:00Z",
            "freshness": "fresh",
            "sentiment": "positive",
            "catalystType": "guidance",
            "relevanceScore": 0.8 - idx * 0.01,
            "limitations": ["public catalyst citation"],
        }
        for idx in range(1, 4)
    ]
    payload["newsCatalysts"]["sentimentSummary"] = {
        "status": "degraded",
        "label": "positive",
        "sourceIds": ["gnews"],
        "bestAuthorityTier": "observation_only",
        "freshness": "fresh",
        "scoreContributionAllowed": False,
        "limitations": ["Context-only sentiment."],
    }
    payload["researchReadiness"]["readinessState"] = "observe_only"
    payload["researchReadiness"]["missingEvidence"] = []
    payload["researchReadiness"]["blockingReasons"] = ["observation_only_evidence"]
    return payload


def test_helper_imports_stay_pure_and_do_not_pull_provider_runtime() -> None:
    imports = _helper_imports()
    for module in imports:
        assert not module.startswith(FORBIDDEN_IMPORT_PREFIXES)


def test_adapter_contract_marks_partial_orcl_input_blocked_without_fake_readiness() -> None:
    helper = _load_helper_module()

    payload = _payload_orcl_partial()
    adapter = helper.build_home_llm_evidence_input_v1(payload)

    assert set(adapter) == REQUIRED_FIELDS
    assert adapter["contractVersion"] == "home_llm_evidence_input_v1"
    assert adapter["symbol"] == "ORCL"
    assert adapter["market"] == "us"
    assert adapter["inputState"] == "blocked"
    assert adapter["missingEvidence"]
    assert adapter["blockedEvidence"]
    assert adapter["degradedEvidence"]
    assert all("ready" not in json.dumps(item, ensure_ascii=False).lower() for item in adapter["missingEvidence"])
    assert any(item["reasonCode"] == "fundamental_context_unavailable" for item in adapter["missingEvidence"])
    assert any(item["reasonCode"] == "provider_timeout" for item in adapter["blockedEvidence"])
    assert adapter["noAdviceBoundary"]


def test_adapter_trims_to_deterministic_small_top_n_and_scrubs_raw_leakage() -> None:
    helper = _load_helper_module()

    adapter = helper.build_home_llm_evidence_input_v1(_payload_for_trimming())
    evidence_index = adapter["evidenceIndex"]

    assert len([item for item in evidence_index if item["domain"] == "fundamentals"]) == 3
    assert len([item for item in evidence_index if item["domain"] == "earnings"]) == 2
    assert len([item for item in evidence_index if item["domain"] == "valuation"]) == 2
    assert len([item for item in evidence_index if item["domain"] == "news"]) == 3
    assert len([item for item in evidence_index if item["domain"] == "catalysts"]) == 2
    assert len([item for item in evidence_index if item["domain"] == "sentiment"]) == 1
    assert {key for item in evidence_index for key in item} == REQUIRED_INDEX_FIELDS

    serialized = json.dumps(adapter, ensure_ascii=False, sort_keys=False)
    for token in FORBIDDEN_SERIALIZED_TOKENS:
        assert token not in serialized.lower()
    assert "A" * 200 not in serialized
    assert '"id": "fund-4"' not in serialized
    assert '"id": "news-4"' not in serialized
    assert '"id": "cat-3"' not in serialized


def test_adapter_serialization_is_stable_and_domain_summaries_are_bounded() -> None:
    helper = _load_helper_module()
    payload = _payload_for_trimming()

    first = helper.build_home_llm_evidence_input_v1(payload)
    second = helper.build_home_llm_evidence_input_v1(payload)

    assert json.dumps(first, ensure_ascii=False, sort_keys=False) == json.dumps(
        second,
        ensure_ascii=False,
        sort_keys=False,
    )
    assert len(first["domainSummaries"]) == 11
    for summary in first["domainSummaries"]:
        assert len(summary["notes"]) <= 3
        assert len(summary["evidenceRefIds"]) <= 3


def test_prompt_section_render_and_pipeline_append_keep_existing_news_context_bounded() -> None:
    helper = _load_helper_module()
    adapter = helper.build_home_llm_evidence_input_v1(_payload_for_trimming())

    section = helper.format_home_llm_evidence_input_prompt_section(adapter)
    merged = StockAnalysisPipeline._append_home_llm_evidence_input_to_news_context(
        "Recent company-specific developments.",
        adapter,
    )

    assert "STRUCTURED_HOME_EVIDENCE_INPUT_V1" in section
    assert "Recent company-specific developments." in merged
    assert section in merged
    assert "singleStockEvidencePacket" not in merged
    assert "top_positive_items" not in merged

