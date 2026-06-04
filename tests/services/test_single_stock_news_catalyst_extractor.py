# -*- coding: utf-8 -*-
"""Tests for the helper-only news/catalyst evidence extractor."""

from __future__ import annotations

import ast
import copy
import importlib
import json
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = REPO_ROOT / "src/services/single_stock_news_catalyst_extractor.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "yfinance",
    "src.core.pipeline",
    "src.search_service",
    "src.services.market_cache",
    "src.services.analysis_provider_planner",
    "src.services.provider_capability_matrix",
)
REQUIRED_TOP_LEVEL_FIELDS = {
    "contractVersion",
    "symbol",
    "market",
    "extractionState",
    "topNewsItems",
    "topCatalystItems",
    "sentimentSummary",
    "missingEvidence",
    "blockingReasons",
    "nextEvidenceNeeded",
    "sourceSummary",
    "noAdviceBoundary",
    "debugRef",
}
REQUIRED_EVIDENCE_FIELDS = {
    "id",
    "domain",
    "title",
    "summary",
    "sourceId",
    "sourceTier",
    "providerAuthority",
    "publishedAt",
    "freshness",
    "sentiment",
    "catalystType",
    "relevanceScore",
    "limitations",
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
    "buy now",
    "sell now",
    "prompt:",
    "broker",
    "bearer ",
    "token=",
)


def _load_helper_module() -> Any:
    try:
        return importlib.import_module("src.services.single_stock_news_catalyst_extractor")
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised in initial RED run
        pytest.fail(f"single_stock_news_catalyst_extractor helper missing: {exc}")


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


def _fullish_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "symbol": "AAPL",
        "market": "us",
        "debugRef": "analysis:home/aapl-2026-06-03",
        "noAdviceBoundary": True,
        "dataQualityReport": {
            "missingRequiredDomains": [],
            "importantDomainsMissing": [],
            "reasonCodes": [],
        },
        "structuredAnalysis": {
            "sentiment_analysis": {
                "status": "ok",
                "source": "finnhub",
                "sourceTier": "observation_only",
                "providerAuthority": "observationOnly",
                "freshness": "fresh",
                "sentiment_summary": "positive",
                "confidence": "medium",
                "relevance_type": "company_specific",
                "relevance_score": 0.91,
                "summary_flags": ["eligible_items_4"],
                "news_published_at": "2026-06-03T13:00:00Z",
                "top_positive_items": [
                    {
                        "id": "news-earnings",
                        "headline": "Apple beats earnings and raises guidance",
                        "summary": "季度盈利超预期，管理层上调指引。",
                        "source": "finnhub",
                        "published_at": "2026-06-03T13:00:00Z",
                        "sentiment": "positive",
                        "relevance_score": 0.96,
                    },
                    {
                        "id": "news-buyback",
                        "headline": "Apple expands buyback after record cash flow",
                        "summary": "回购与现金流改善。",
                        "source": "gnews",
                        "published_at": "2026-06-03T11:00:00Z",
                        "sentiment": "positive",
                        "relevance_score": 0.88,
                    },
                ],
                "top_negative_items": [
                    {
                        "id": "news-eu-fine",
                        "headline": "EU probes App Store policy changes",
                        "summary": "监管不确定性上升。",
                        "source": "gnews",
                        "published_at": "2026-06-03T10:00:00Z",
                        "sentiment": "negative",
                        "relevance_score": 0.83,
                    }
                ],
                "classified_items": [
                    {
                        "id": "news-earnings",
                        "title": "Apple beats earnings and raises guidance",
                        "summary": "季度盈利超预期，管理层上调指引。",
                        "source": "finnhub",
                        "sourceTier": "observation_only",
                        "providerAuthority": "observationOnly",
                        "news_published_at": "2026-06-03T13:00:00Z",
                        "relevance_type": "company_specific",
                        "relevance_score": 0.96,
                        "sentiment": "positive",
                    },
                    {
                        "id": "news-buyback",
                        "title": "Apple expands buyback after record cash flow",
                        "summary": "回购与现金流改善。",
                        "source": "gnews",
                        "sourceTier": "observation_only",
                        "providerAuthority": "observationOnly",
                        "news_published_at": "2026-06-03T11:00:00Z",
                        "relevance_type": "company_specific",
                        "relevance_score": 0.88,
                        "sentiment": "positive",
                    },
                    {
                        "id": "news-eu-fine",
                        "title": "EU probes App Store policy changes",
                        "summary": "监管不确定性上升。",
                        "source": "gnews",
                        "sourceTier": "observation_only",
                        "providerAuthority": "observationOnly",
                        "news_published_at": "2026-06-03T10:00:00Z",
                        "relevance_type": "regulatory",
                        "relevance_score": 0.83,
                        "sentiment": "negative",
                    },
                    {
                        "id": "news-wwdc",
                        "title": "WWDC reveals on-device AI roadmap",
                        "summary": "新品发布提升产品催化预期。",
                        "source": "gnews",
                        "sourceTier": "observation_only",
                        "providerAuthority": "observationOnly",
                        "news_published_at": "2026-06-03T09:00:00Z",
                        "relevance_type": "company_specific",
                        "relevance_score": 0.82,
                        "sentiment": "positive",
                        "catalyst_type": "product_launch",
                    },
                ],
            },
            "catalyst": {
                "status": "ok",
                "source": "gnews",
                "sourceTier": "observation_only",
                "providerAuthority": "observationOnly",
                "freshness": "fresh",
                "classified_items": [
                    {
                        "id": "cat-wwdc",
                        "headline": "WWDC reveals on-device AI roadmap",
                        "summary": "新品发布提升产品催化预期。",
                        "source": "gnews",
                        "published_at": "2026-06-03T09:00:00Z",
                        "relevance_score": 0.92,
                        "catalyst_type": "product_launch",
                        "sentiment": "positive",
                    },
                    {
                        "id": "cat-guidance",
                        "headline": "Apple raises full-year guidance",
                        "summary": "管理层上调全年业绩预期。",
                        "source": "finnhub",
                        "published_at": "2026-06-03T13:05:00Z",
                        "relevance_score": 0.95,
                        "catalyst_type": "guidance",
                        "sentiment": "positive",
                    },
                ],
                "topEvidenceRefs": ["catalyst:guidance", "catalyst:wwdc"],
            },
        },
        "runtimeData": {
            "news": {
                "status": "ok",
                "freshness": "fresh",
                "sourceTier": "observation_only",
                "providerAuthority": "observationOnly",
            },
            "sentiment": {
                "status": "ok",
                "freshness": "fresh",
                "sourceTier": "observation_only",
                "providerAuthority": "observationOnly",
            },
        },
        "news_context": (
            "Apple beats earnings and raises guidance. "
            "WWDC reveals on-device AI roadmap. "
            "EU probes App Store policy changes."
        ),
    }
    payload.update(overrides)
    return payload


def test_extractor_helper_is_pure_deterministic_and_json_safe() -> None:
    helper = _load_helper_module()
    imports = _helper_imports()
    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)

    payload = _fullish_payload()
    original = copy.deepcopy(payload)

    first = helper.build_single_stock_news_catalyst_extractor_v1(payload)
    second = helper.build_single_stock_news_catalyst_extractor_v1(payload)

    assert payload == original
    assert first == second
    assert json.loads(json.dumps(first, ensure_ascii=False)) == first
    assert REQUIRED_TOP_LEVEL_FIELDS <= set(first)
    for item in first["topNewsItems"] + first["topCatalystItems"]:
        assert REQUIRED_EVIDENCE_FIELDS <= set(item)
    assert first["contractVersion"] == helper.SINGLE_STOCK_NEWS_CATALYST_EXTRACTOR_VERSION


def test_fullish_payload_extracts_bounded_news_catalysts_and_sentiment_summary() -> None:
    helper = _load_helper_module()

    contract = helper.build_single_stock_news_catalyst_extractor_v1(_fullish_payload())

    assert contract["symbol"] == "AAPL"
    assert contract["market"] == "us"
    assert contract["extractionState"] == "ready"
    assert contract["missingEvidence"] == []
    assert contract["blockingReasons"] == []
    assert contract["noAdviceBoundary"] == {
        "state": "no_advice",
        "label": "仅研究，不构成投资建议",
    }
    assert [item["id"] for item in contract["topNewsItems"]] == [
        "news-earnings",
        "news-buyback",
        "news-eu-fine",
        "news-wwdc",
    ]
    assert [item["id"] for item in contract["topCatalystItems"]] == [
        "cat-guidance",
        "cat-wwdc",
    ]
    assert contract["sentimentSummary"]["status"] == "available"
    assert contract["sentimentSummary"]["label"] == "positive"
    assert contract["sentimentSummary"]["scoreContributionAllowed"] is False
    assert contract["sourceSummary"]["news"]["bestAuthorityTier"] == "observation_only"
    assert contract["sourceSummary"]["catalysts"]["bestAuthorityTier"] == "observation_only"


@pytest.mark.parametrize("market", ["us", "hk"])
def test_orcl_like_empty_positive_negative_lists_fail_closed_with_explicit_missing_evidence(
    market: str,
) -> None:
    helper = _load_helper_module()
    symbol = "ORCL" if market == "us" else "0700.HK"

    contract = helper.build_single_stock_news_catalyst_extractor_v1(
        _fullish_payload(
            symbol=symbol,
            market=market,
            structuredAnalysis={
                "sentiment_analysis": {
                    "status": "weak",
                    "source": "finnhub",
                    "sourceTier": "observation_only",
                    "providerAuthority": "observationOnly",
                    "freshness": "fresh",
                    "sentiment_summary": "no_reliable_news",
                    "top_positive_items": [],
                    "top_negative_items": [],
                    "classified_items": [],
                    "relevance_type": "low_relevance",
                    "relevance_score": 0.0,
                    "summary_flags": ["no_reliable_news"],
                },
                "catalyst": {
                    "status": "missing",
                    "source": None,
                    "freshness": "unknown",
                    "classified_items": [],
                },
            },
            dataQualityReport={
                "missingRequiredDomains": ["news", "catalysts", "sentiment"],
                "importantDomainsMissing": ["news", "catalysts"],
                "reasonCodes": ["no_reliable_news"],
            },
            news_context="",
        )
    )

    assert contract["extractionState"] == "insufficient"
    assert contract["topNewsItems"] == []
    assert contract["topCatalystItems"] == []
    assert "news" in contract["missingEvidence"]
    assert "catalysts" in contract["missingEvidence"]
    assert "sentiment" in contract["missingEvidence"]
    assert "补充结构化新闻证据" in contract["nextEvidenceNeeded"]


def test_news_context_only_fallback_extracts_bounded_items_without_provider_calls() -> None:
    helper = _load_helper_module()

    contract = helper.build_single_stock_news_catalyst_extractor_v1(
        _fullish_payload(
            structuredAnalysis={
                "sentiment_analysis": {
                    "status": "partial",
                    "source": "manual",
                    "freshness": "unknown",
                    "sentiment_summary": "neutral",
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
            news_context=(
                "Oracle earnings beat expectations. "
                "Management raised annual guidance. "
                "Cloud demand remains stable."
            ),
        )
    )

    assert contract["extractionState"] == "observe_only"
    assert len(contract["topNewsItems"]) >= 2
    assert contract["topCatalystItems"][0]["catalystType"] == "guidance"
    assert all(item["sourceId"] == "manual_unknown" for item in contract["topNewsItems"])
    assert contract["sourceSummary"]["news"]["scoreContributionAllowed"] is False


def test_timeout_and_blocked_news_fail_closed_without_raw_leakage() -> None:
    helper = _load_helper_module()

    contract = helper.build_single_stock_news_catalyst_extractor_v1(
        _fullish_payload(
            structuredAnalysis={
                "sentiment_analysis": {
                    "status": "partial",
                    "source": "tavily",
                    "freshness": "unknown",
                    "top_positive_items": [],
                    "top_negative_items": [],
                    "classified_items": [],
                    "sentiment_summary": "no_reliable_news",
                    "raw_payload": {"headline": "do not leak"},
                    "stack_trace": "Traceback: secret",
                },
                "catalyst": {
                    "status": "partial",
                    "source": "gnews",
                    "freshness": "unknown",
                    "classified_items": [],
                },
            },
            runtimeData={
                "news": {
                    "status": "timeout",
                    "freshness": "unknown",
                    "error": "provider_timeout token=SECRET Authorization: Bearer abc",
                    "authorization": "Bearer abc",
                    "router_debug": "news_router>provider_a",
                },
                "sentiment": {
                    "status": "timeout",
                    "freshness": "unknown",
                },
            },
            dataQualityReport={
                "missingRequiredDomains": ["news"],
                "importantDomainsMissing": ["news", "catalysts", "sentiment"],
                "reasonCodes": ["provider_timeout"],
            },
            news_context="",
        )
    )

    assert contract["extractionState"] == "blocked"
    assert contract["topNewsItems"] == []
    assert "provider_timeout" in contract["blockingReasons"]
    assert contract["sentimentSummary"]["status"] == "blocked"
    serialized = json.dumps(contract, ensure_ascii=False).lower()
    for token in FORBIDDEN_SERIALIZED_TOKENS:
        assert token not in serialized


def test_stale_fallback_proxy_sources_downgrade_to_observe_only() -> None:
    helper = _load_helper_module()

    contract = helper.build_single_stock_news_catalyst_extractor_v1(
        _fullish_payload(
            structuredAnalysis={
                "sentiment_analysis": {
                    "status": "partial",
                    "source": "yfinance_proxy",
                    "sourceTier": "unofficial_public_api",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "stale",
                    "sentiment_summary": "negative",
                    "top_positive_items": [],
                    "top_negative_items": [
                        {
                            "id": "news-delay",
                            "headline": "Delayed proxy headline",
                            "summary": "Proxy-only delayed evidence.",
                            "source": "yfinance_proxy",
                            "published_at": "2026-05-30T09:00:00Z",
                            "sentiment": "negative",
                            "relevance_score": 0.78,
                            "proxyOnly": True,
                        }
                    ],
                    "classified_items": [],
                    "proxyOnly": True,
                    "isFallback": True,
                },
                "catalyst": {
                    "status": "partial",
                    "source": "fallback_cache",
                    "sourceTier": "fallback",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "fallback",
                    "isFallback": True,
                    "classified_items": [
                        {
                            "id": "cat-cache",
                            "headline": "Cached fallback catalyst",
                            "summary": "Fallback cache should not claim authority.",
                            "source": "fallback_cache",
                            "published_at": "2026-05-29T08:00:00Z",
                            "relevance_score": 0.72,
                            "sentiment": "neutral",
                            "catalyst_type": "fallback_event",
                        }
                    ],
                },
            },
            dataQualityReport={
                "missingRequiredDomains": [],
                "importantDomainsMissing": ["news", "catalysts"],
                "reasonCodes": ["stale_required_source", "fallback_proxy_evidence"],
            },
        )
    )

    assert contract["extractionState"] == "observe_only"
    assert contract["topNewsItems"][0]["providerAuthority"] == "observationOnly"
    assert contract["topCatalystItems"][0]["providerAuthority"] == "observationOnly"
    assert contract["sourceSummary"]["news"]["bestAuthorityTier"] in {"unknown", "observation_only"}
    assert contract["sourceSummary"]["catalysts"]["bestAuthorityTier"] == "unknown"


def test_unknown_source_fails_closed_to_manual_unknown() -> None:
    helper = _load_helper_module()

    contract = helper.build_single_stock_news_catalyst_extractor_v1(
        _fullish_payload(
            structuredAnalysis={
                "sentiment_analysis": {
                    "status": "ok",
                    "source": "mystery_feed",
                    "freshness": "unknown",
                    "sentiment_summary": "neutral",
                    "top_positive_items": [
                        {
                            "id": "news-1",
                            "headline": "Unknown source headline",
                            "summary": "Should fail closed.",
                            "source": "mystery_feed",
                            "published_at": "2026-06-01T12:00:00Z",
                            "sentiment": "neutral",
                            "relevance_score": 0.81,
                        }
                    ],
                    "top_negative_items": [],
                    "classified_items": [],
                },
                "catalyst": {
                    "status": "ok",
                    "source": "mystery_feed",
                    "freshness": "unknown",
                    "classified_items": [],
                },
            },
        )
    )

    assert contract["extractionState"] == "observe_only"
    assert contract["sourceSummary"]["news"]["sourceIds"] == ["manual_unknown"]
    assert contract["sourceSummary"]["news"]["scoreContributionAllowed"] is False
    assert all(item["sourceId"] == "manual_unknown" for item in contract["topNewsItems"])
    assert all(item["providerAuthority"] == "observationOnly" for item in contract["topNewsItems"])


def test_max_items_is_bounded_and_deterministic() -> None:
    helper = _load_helper_module()

    positive_items = [
        {
            "id": f"news-{index}",
            "headline": f"Headline {index}",
            "summary": f"Summary {index}",
            "source": "gnews",
            "published_at": f"2026-06-{index:02d}T10:00:00Z",
            "sentiment": "positive",
            "relevance_score": 1 - (index * 0.01),
        }
        for index in range(1, 9)
    ]

    contract = helper.build_single_stock_news_catalyst_extractor_v1(
        _fullish_payload(
            structuredAnalysis={
                **_fullish_payload()["structuredAnalysis"],
                "sentiment_analysis": {
                    **_fullish_payload()["structuredAnalysis"]["sentiment_analysis"],
                    "top_positive_items": positive_items,
                    "top_negative_items": [],
                    "classified_items": [],
                },
            },
            news_context="",
        ),
        max_items_per_domain=5,
    )

    assert len(contract["topNewsItems"]) == 5
    assert [item["id"] for item in contract["topNewsItems"]] == [
        "news-1",
        "news-2",
        "news-3",
        "news-4",
        "news-5",
    ]


def test_no_advice_boundary_fails_closed_when_missing() -> None:
    helper = _load_helper_module()

    contract = helper.build_single_stock_news_catalyst_extractor_v1(
        _fullish_payload(
            noAdviceBoundary=False,
            dataQualityReport={
                "missingRequiredDomains": [],
                "importantDomainsMissing": [],
                "reasonCodes": [],
            },
        )
    )

    assert contract["extractionState"] == "blocked"
    assert contract["noAdviceBoundary"] == {
        "state": "blocked",
        "label": "仅研究，禁止转化为交易或执行建议",
    }
    assert "no_advice_boundary_missing" in contract["blockingReasons"]
