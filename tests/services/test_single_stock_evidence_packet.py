# -*- coding: utf-8 -*-
"""Tests for the additive single-stock evidence packet contract helper."""

from __future__ import annotations

import ast
import copy
import importlib
import json
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = REPO_ROOT / "src/services/single_stock_evidence_packet.py"
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
REQUIRED_PACKET_FIELDS = {
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
}
REQUIRED_DOMAIN_KEYS = {
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
REQUIRED_DOMAIN_FIELDS = {
    "status",
    "sourceTier",
    "providerAuthority",
    "freshness",
    "fallbackOrProxy",
    "evidenceCount",
    "topEvidenceRefs",
    "missingReasons",
    "nextEvidenceNeeded",
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
    "broker",
    "submit order",
    "trade now",
)


def _load_helper_module() -> Any:
    try:
        return importlib.import_module("src.services.single_stock_evidence_packet")
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised in initial RED run
        pytest.fail(f"single_stock_evidence_packet helper missing: {exc}")


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
        "debugRef": "analysis:run-123",
        "noAdviceBoundary": True,
        "dataQualityReport": {
            "missingRequiredDomains": [],
            "importantDomainsMissing": [],
            "reasonCodes": [],
        },
        "structuredAnalysis": {
            "technicals": {
                "status": "ok",
                "source": "polygon_us_grouped_daily",
                "sourceTier": "score_grade",
                "providerAuthority": "scoreGradeAllowed",
                "freshness": "fresh",
                "topEvidenceRefs": ["price:daily-365d", "tech:rsi-ready"],
            },
            "fundamentals": {
                "status": "ok",
                "source": "fmp",
                "sourceTier": "score_grade",
                "providerAuthority": "scoreGradeAllowed",
                "freshness": "fresh",
                "normalized": {
                    "marketCap": 3000000000000,
                    "trailingPE": 24.8,
                    "priceToBook": 8.7,
                },
                "topEvidenceRefs": ["fund:market-cap", "fund:roe"],
            },
            "earnings_analysis": {
                "status": "ok",
                "source": "fmp_income_statement",
                "sourceTier": "score_grade",
                "providerAuthority": "scoreGradeAllowed",
                "freshness": "fresh",
                "summary_flags": ["quarterly_series_available"],
                "topEvidenceRefs": ["earnings:q1-2026"],
            },
            "filings": {
                "status": "ok",
                "source": "sec_10q",
                "sourceTier": "official_public",
                "providerAuthority": "scoreGradeAllowed",
                "freshness": "fresh",
                "topEvidenceRefs": ["filing:10-Q-2026Q1"],
            },
            "sentiment_analysis": {
                "status": "ok",
                "source": "finnhub",
                "sourceTier": "score_grade",
                "providerAuthority": "scoreGradeAllowed",
                "freshness": "fresh",
                "classified_items": [
                    {"id": "news-1", "headline": "Apple AI launch lifts sentiment"},
                    {"id": "news-2", "headline": "Apple supply chain stabilizes"},
                ],
                "top_positive_items": [
                    {"id": "news-1", "headline": "Apple AI launch lifts sentiment"},
                ],
                "top_negative_items": [],
                "topEvidenceRefs": ["news:1", "news:2"],
            },
            "catalyst": {
                "status": "ok",
                "source": "gnews",
                "sourceTier": "official_public",
                "providerAuthority": "scoreGradeAllowed",
                "freshness": "fresh",
                "classified_items": [{"id": "cat-1", "headline": "WWDC product event"}],
                "topEvidenceRefs": ["catalyst:wwdc"],
            },
            "realtime_context": {
                "price": 188.2,
                "volume_ratio": 1.24,
                "turnover_rate": 0.021,
                "source": "polygon_us_grouped_daily",
                "sourceTier": "score_grade",
                "providerAuthority": "scoreGradeAllowed",
                "freshness": "fresh",
            },
            "market_context": {
                "macro": {"regime": "risk_on"},
                "liquidity": {"usd": "stable"},
                "sectorTheme": {"sector": "software", "theme": "ai"},
                "source": "official_macro_bundle",
                "sourceTier": "official_public",
                "providerAuthority": "observationOnly",
                "freshness": "delayed",
                "topEvidenceRefs": ["macro:fred-weekly", "theme:software-ai"],
            },
            "fundamental_context": {
                "status": "supported",
                "market": "us",
                "valuation": {"data": {"trailingPE": 24.8, "priceToBook": 8.7}},
                "earnings": {"data": {"quarterly_series": [{"quarter": "2026Q1"}]}},
            },
        },
        "runtimeData": {
            "market": {
                "status": "ok",
                "freshness": "fresh",
                "sourceTier": "score_grade",
                "providerAuthority": "scoreGradeAllowed",
            },
            "fundamentals": {
                "status": "ok",
                "freshness": "fresh",
                "sourceTier": "score_grade",
                "providerAuthority": "scoreGradeAllowed",
            },
            "news": {
                "status": "ok",
                "freshness": "fresh",
                "sourceTier": "official_public",
                "providerAuthority": "scoreGradeAllowed",
            },
            "sentiment": {
                "status": "ok",
                "freshness": "fresh",
                "sourceTier": "official_public",
                "providerAuthority": "scoreGradeAllowed",
            },
        },
    }
    payload.update(overrides)
    return payload


def test_single_stock_evidence_packet_helper_is_pure_deterministic_and_json_safe() -> None:
    helper = _load_helper_module()
    imports = _helper_imports()
    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)

    payload = _fullish_payload()
    original = copy.deepcopy(payload)

    first = helper.build_single_stock_evidence_packet_v1(payload)
    second = helper.build_single_stock_evidence_packet_v1(payload)

    assert payload == original
    assert first == second
    assert json.loads(json.dumps(first, ensure_ascii=False)) == first
    assert REQUIRED_PACKET_FIELDS <= set(first)
    assert set(first["domains"]) == REQUIRED_DOMAIN_KEYS
    for domain in REQUIRED_DOMAIN_KEYS:
        assert REQUIRED_DOMAIN_FIELDS <= set(first["domains"][domain])
    assert first["contractVersion"] == helper.SINGLE_STOCK_EVIDENCE_PACKET_VERSION


def test_fullish_packet_reports_available_domains_and_no_advice_boundary() -> None:
    helper = _load_helper_module()

    packet = helper.build_single_stock_evidence_packet_v1(_fullish_payload())

    assert packet["symbol"] == "AAPL"
    assert packet["market"] == "us"
    assert packet["packetState"] == "available"
    assert packet["missingEvidence"] == []
    assert packet["blockingReasons"] == []
    assert packet["nextEvidenceNeeded"] == []
    assert packet["noAdviceBoundary"] == {
        "state": "no_advice",
        "label": "仅研究，不构成投资建议",
    }
    assert packet["domains"]["priceHistory"]["status"] == "available"
    assert packet["domains"]["technicals"]["status"] == "available"
    assert packet["domains"]["fundamentals"]["status"] == "available"
    assert packet["domains"]["earnings"]["status"] == "available"
    assert packet["domains"]["filings"]["status"] == "available"
    assert packet["domains"]["valuation"]["status"] == "available"
    assert packet["domains"]["sectorTheme"]["status"] == "available"
    assert packet["domains"]["macroLiquidity"]["status"] == "degraded"
    assert packet["domains"]["news"]["topEvidenceRefs"] == ["news:1", "news:2"]
    assert packet["sourceSummary"] == {
        "availableCount": 10,
        "degradedCount": 1,
        "missingCount": 0,
        "blockedCount": 0,
        "pendingCount": 0,
    }


@pytest.mark.parametrize("market", ["us", "hk"])
def test_partial_packet_preserves_orcl_like_truth_when_fundamental_context_is_unsupported(market: str) -> None:
    helper = _load_helper_module()
    symbol = "ORCL" if market == "us" else "0700.HK"

    packet = helper.build_single_stock_evidence_packet_v1(
        _fullish_payload(
            symbol=symbol,
            market=market,
            structuredAnalysis={
                **_fullish_payload()["structuredAnalysis"],
                "fundamentals": {
                    "status": "missing",
                    "source": None,
                    "freshness": "unknown",
                },
                "earnings_analysis": {
                    "status": "missing",
                    "source": None,
                    "freshness": "unknown",
                },
                "fundamental_context": {
                    "status": "market not supported",
                    "market": market,
                    "reason": "fundamental_context unavailable",
                },
                "sentiment_analysis": {
                    "status": "missing",
                    "source": None,
                    "freshness": "unknown",
                    "top_positive_items": [],
                    "top_negative_items": [],
                },
                "catalyst": {
                    "status": "missing",
                    "source": None,
                    "freshness": "unknown",
                    "classified_items": [],
                },
            },
            runtimeData={
                "market": {"status": "ok", "freshness": "fresh"},
                "fundamentals": {"status": "missing", "freshness": "unknown"},
                "news": {"status": "missing", "freshness": "unknown"},
                "sentiment": {"status": "missing", "freshness": "unknown"},
            },
            dataQualityReport={
                "missingRequiredDomains": ["fundamentals", "earnings", "news", "catalysts"],
                "importantDomainsMissing": ["valuation"],
                "reasonCodes": ["fundamental_context_unavailable"],
            },
        )
    )

    assert packet["packetState"] == "degraded"
    assert packet["domains"]["priceHistory"]["status"] == "available"
    assert packet["domains"]["technicals"]["status"] == "available"
    assert packet["domains"]["fundamentals"]["status"] == "missing"
    assert packet["domains"]["earnings"]["status"] == "missing"
    assert packet["domains"]["valuation"]["status"] == "missing"
    assert packet["domains"]["news"]["status"] == "missing"
    assert packet["domains"]["catalysts"]["status"] == "missing"
    assert "fundamentals" in packet["missingEvidence"]
    assert "earnings" in packet["missingEvidence"]
    assert "valuation" in packet["missingEvidence"]
    assert "news" in packet["missingEvidence"]
    assert "catalysts" in packet["missingEvidence"]
    assert "fundamental_context_unavailable" in packet["blockingReasons"]
    assert "补充基本面证据" in packet["nextEvidenceNeeded"]


def test_news_timeout_fallback_and_empty_sentiment_lists_degrade_without_raw_leakage() -> None:
    helper = _load_helper_module()

    packet = helper.build_single_stock_evidence_packet_v1(
        _fullish_payload(
            structuredAnalysis={
                **_fullish_payload()["structuredAnalysis"],
                "sentiment_analysis": {
                    "status": "partial",
                    "source": "tavily",
                    "sourceTier": "observation_only",
                    "providerAuthority": "observationOnly",
                    "freshness": "delayed",
                    "top_positive_items": [],
                    "top_negative_items": [],
                    "classified_items": [],
                    "raw_payload": {"headline": "do not leak"},
                    "stack_trace": "Traceback: secret",
                },
                "catalyst": {
                    "status": "partial",
                    "source": "gnews",
                    "sourceTier": "observation_only",
                    "providerAuthority": "observationOnly",
                    "freshness": "fallback",
                    "classified_items": [],
                    "topEvidenceRefs": [],
                },
            },
            runtimeData={
                **_fullish_payload()["runtimeData"],
                "news": {
                    "status": "timeout",
                    "freshness": "unknown",
                    "providerAuthority": "observationOnly",
                    "error": "provider_timeout after 8s",
                    "authorization": "Bearer secret",
                    "router_debug": "news_router>provider_a",
                },
                "sentiment": {
                    "status": "fallback",
                    "freshness": "fallback",
                    "providerAuthority": "observationOnly",
                },
            },
            dataQualityReport={
                "missingRequiredDomains": [],
                "importantDomainsMissing": ["news", "catalysts", "sentiment"],
                "reasonCodes": ["provider_timeout", "fallback_proxy_evidence"],
            },
        )
    )

    assert packet["domains"]["news"]["status"] == "blocked"
    assert packet["domains"]["catalysts"]["status"] == "degraded"
    assert packet["domains"]["sentiment"]["status"] == "degraded"
    assert packet["domains"]["news"]["topEvidenceRefs"] == []
    assert "provider_timeout" in packet["domains"]["news"]["missingReasons"]
    assert "fallback_proxy_evidence" in packet["domains"]["catalysts"]["missingReasons"]
    serialized = json.dumps(packet, ensure_ascii=False).lower()
    for token in FORBIDDEN_SERIALIZED_TOKENS:
        assert token not in serialized


def test_stale_fallback_proxy_downgrade_is_fail_closed_for_authority() -> None:
    helper = _load_helper_module()

    packet = helper.build_single_stock_evidence_packet_v1(
        _fullish_payload(
            structuredAnalysis={
                **_fullish_payload()["structuredAnalysis"],
                "technicals": {
                    "status": "partial",
                    "source": "yfinance_proxy",
                    "sourceTier": "unofficial_public_api",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "stale",
                    "proxyOnly": True,
                    "topEvidenceRefs": ["price:delayed-proxy"],
                },
                "fundamentals": {
                    "status": "partial",
                    "source": "fallback_cache",
                    "sourceTier": "fallback",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "fallback",
                    "isFallback": True,
                    "normalized": {},
                    "topEvidenceRefs": ["fund:cached-summary"],
                },
            },
            dataQualityReport={
                "missingRequiredDomains": [],
                "importantDomainsMissing": ["valuation"],
                "reasonCodes": ["stale_required_source", "fallback_proxy_evidence"],
            },
        )
    )

    assert packet["packetState"] == "degraded"
    assert packet["domains"]["priceHistory"]["status"] == "degraded"
    assert packet["domains"]["technicals"]["status"] == "degraded"
    assert packet["domains"]["technicals"]["providerAuthority"] == "observationOnly"
    assert packet["domains"]["technicals"]["fallbackOrProxy"] is True
    assert packet["domains"]["fundamentals"]["status"] == "degraded"
    assert packet["domains"]["fundamentals"]["providerAuthority"] == "observationOnly"
    assert packet["domains"]["valuation"]["status"] == "missing"
    assert "stale_evidence" in packet["blockingReasons"]
    assert "fallback_proxy_evidence" in packet["blockingReasons"]


def test_no_advice_boundary_fails_closed_when_missing() -> None:
    helper = _load_helper_module()

    packet = helper.build_single_stock_evidence_packet_v1(
        _fullish_payload(
            noAdviceBoundary=False,
            dataQualityReport={
                "missingRequiredDomains": [],
                "importantDomainsMissing": [],
                "reasonCodes": [],
            },
        )
    )

    assert packet["packetState"] == "blocked"
    assert packet["noAdviceBoundary"] == {
        "state": "blocked",
        "label": "仅研究，禁止转化为交易或执行建议",
    }
    assert "no_advice_boundary_missing" in packet["blockingReasons"]

