# -*- coding: utf-8 -*-
"""Tests for the helper-only fundamentals/earnings evidence normalizer."""

from __future__ import annotations

import ast
import copy
import importlib
import json
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = REPO_ROOT / "src/services/single_stock_fundamentals_earnings_normalizer.py"
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
    "src.services.provider_capability_matrix",
    "src.services.analysis_provider_planner",
)
REQUIRED_TOP_LEVEL_FIELDS = {
    "contractVersion",
    "symbol",
    "market",
    "normalizerState",
    "domains",
    "evidenceRefs",
    "missingEvidence",
    "blockingReasons",
    "nextEvidenceNeeded",
    "sourceSummary",
    "noAdviceBoundary",
    "debugRef",
}
REQUIRED_DOMAIN_KEYS = {"fundamentals", "earnings", "valuation", "filings"}
REQUIRED_DOMAIN_FIELDS = {
    "domain",
    "status",
    "evidenceCount",
    "sourceIds",
    "bestAuthorityTier",
    "freshness",
    "scoreContributionAllowed",
    "limitations",
}
REQUIRED_EVIDENCE_FIELDS = {
    "id",
    "domain",
    "label",
    "value",
    "period",
    "asOf",
    "sourceId",
    "sourceTier",
    "providerAuthority",
    "freshness",
    "confidence",
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
)


def _load_helper_module() -> Any:
    try:
        return importlib.import_module("src.services.single_stock_fundamentals_earnings_normalizer")
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised in initial RED run
        pytest.fail(f"single_stock_fundamentals_earnings_normalizer helper missing: {exc}")


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
        "debugRef": "analysis:home/aapl-2026q1",
        "noAdviceBoundary": True,
        "dataQualityReport": {
            "missingRequiredDomains": [],
            "importantDomainsMissing": [],
            "reasonCodes": [],
        },
        "structuredAnalysis": {
            "fundamental_context": {
                "status": "supported",
                "market": "us",
                "valuation": {
                    "data": {
                        "trailingPE": 24.8,
                        "priceToBook": 8.7,
                        "marketCap": 3010000000000,
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
                        "dividend": {
                            "dividendYield": 0.0046,
                            "dividendPerShare": 0.25,
                            "asOfDate": "2026-03-31",
                        },
                    }
                },
            },
            "fundamentals": {
                "status": "ok",
                "source": "fmp",
                "sourceTier": "score_grade",
                "providerAuthority": "scoreGradeAllowed",
                "freshness": "fresh",
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
                "summary_flags": ["high_growth", "cashflow_healthy"],
            },
            "earnings_analysis": {
                "status": "ok",
                "source": "fmp_income_statement",
                "sourceTier": "score_grade",
                "providerAuthority": "scoreGradeAllowed",
                "freshness": "fresh",
                "reporting_basis": "latest_quarter",
                "summary_basis": "yoy",
                "summary_flags": ["quarterly_series_available", "financial_report_available", "dividend_metrics_available"],
                "derived_metrics": {
                    "yoy_revenue_growth": 0.08,
                    "yoy_net_income_change": 0.06,
                    "qoq_revenue_growth": 0.03,
                },
                "quarterly_series": [
                    {
                        "quarter": "2026Q1",
                        "fiscalDateEnding": "2026-03-31",
                        "revenue": 90340000000,
                        "net_income": 21400000000,
                    },
                    {
                        "quarter": "2025Q4",
                        "fiscalDateEnding": "2025-12-31",
                        "revenue": 87600000000,
                        "net_income": 20800000000,
                    },
                ],
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
        },
    }
    payload.update(overrides)
    return payload


def test_normalizer_helper_is_pure_deterministic_and_json_safe() -> None:
    helper = _load_helper_module()
    imports = _helper_imports()
    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)

    payload = _fullish_payload()
    original = copy.deepcopy(payload)

    first = helper.build_single_stock_fundamentals_earnings_normalizer_v1(payload)
    second = helper.build_single_stock_fundamentals_earnings_normalizer_v1(payload)

    assert payload == original
    assert first == second
    assert json.loads(json.dumps(first, ensure_ascii=False)) == first
    assert REQUIRED_TOP_LEVEL_FIELDS <= set(first)
    assert set(first["domains"]) == REQUIRED_DOMAIN_KEYS
    for domain in REQUIRED_DOMAIN_KEYS:
        assert REQUIRED_DOMAIN_FIELDS <= set(first["domains"][domain])
    for ref in first["evidenceRefs"]:
        assert REQUIRED_EVIDENCE_FIELDS <= set(ref)
    assert first["contractVersion"] == helper.SINGLE_STOCK_FUNDAMENTALS_EARNINGS_NORMALIZER_VERSION


def test_fullish_payload_normalizes_four_domains_into_bounded_evidence_refs() -> None:
    helper = _load_helper_module()

    contract = helper.build_single_stock_fundamentals_earnings_normalizer_v1(_fullish_payload())

    assert contract["symbol"] == "AAPL"
    assert contract["market"] == "us"
    assert contract["normalizerState"] == "ready"
    assert contract["missingEvidence"] == []
    assert contract["blockingReasons"] == []
    assert contract["noAdviceBoundary"] == {
        "state": "no_advice",
        "label": "仅研究，不构成投资建议",
    }
    assert {item["domain"] for item in contract["evidenceRefs"]} == REQUIRED_DOMAIN_KEYS
    assert contract["domains"]["fundamentals"]["status"] == "available"
    assert contract["domains"]["earnings"]["status"] == "available"
    assert contract["domains"]["valuation"]["status"] == "available"
    assert contract["domains"]["filings"]["status"] == "available"
    assert contract["domains"]["fundamentals"]["bestAuthorityTier"] == "score_grade"
    assert contract["domains"]["filings"]["bestAuthorityTier"] in {"score_grade", "observation_only"}
    assert contract["domains"]["fundamentals"]["scoreContributionAllowed"] is True
    assert contract["sourceSummary"]["fundamentals"]["sourceIds"] == ["fmp"]
    assert contract["sourceSummary"]["earnings"]["sourceIds"] == ["fmp"]
    assert contract["sourceSummary"]["valuation"]["sourceIds"] == ["fmp"]
    serialized = json.dumps(contract, ensure_ascii=False).lower()
    for token in FORBIDDEN_SERIALIZED_TOKENS:
        assert token not in serialized


@pytest.mark.parametrize("market", ["us", "hk"])
def test_orcl_like_missing_or_unsupported_fundamental_context_fails_closed(market: str) -> None:
    helper = _load_helper_module()
    symbol = "ORCL" if market == "us" else "0700.HK"

    contract = helper.build_single_stock_fundamentals_earnings_normalizer_v1(
        _fullish_payload(
            symbol=symbol,
            market=market,
            structuredAnalysis={
                "fundamental_context": {
                    "status": "market not supported",
                    "market": market,
                    "reason": "fundamental_context unavailable",
                },
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
                "filings": {
                    "status": "missing",
                    "source": None,
                    "freshness": "unknown",
                    "items": [],
                },
            },
            dataQualityReport={
                "missingRequiredDomains": ["fundamentals", "earnings"],
                "importantDomainsMissing": ["valuation"],
                "reasonCodes": ["fundamental_context_unavailable"],
            },
        )
    )

    assert contract["normalizerState"] == "insufficient"
    assert contract["domains"]["fundamentals"]["status"] == "missing"
    assert contract["domains"]["earnings"]["status"] == "missing"
    assert contract["domains"]["valuation"]["status"] == "missing"
    assert "fundamentals" in contract["missingEvidence"]
    assert "earnings" in contract["missingEvidence"]
    assert "valuation" in contract["missingEvidence"]
    assert "fundamental_context_unavailable" in contract["blockingReasons"]
    assert "补充基本面证据" in contract["nextEvidenceNeeded"]


def test_valuation_only_partial_stays_insufficient() -> None:
    helper = _load_helper_module()

    contract = helper.build_single_stock_fundamentals_earnings_normalizer_v1(
        _fullish_payload(
            structuredAnalysis={
                "fundamental_context": {
                    "status": "supported",
                    "market": "us",
                    "valuation": {"data": {"trailingPE": 31.2, "priceToBook": 6.1}},
                    "earnings": {"data": {}},
                },
                "fundamentals": {
                    "status": "missing",
                    "source": None,
                    "freshness": "unknown",
                    "normalized": {},
                },
                "earnings_analysis": {
                    "status": "partial",
                    "source": None,
                    "freshness": "unknown",
                    "quarterly_series": [],
                    "summary_flags": ["earnings_data_unavailable"],
                },
                "filings": {
                    "status": "missing",
                    "source": None,
                    "freshness": "unknown",
                    "items": [],
                },
            },
            dataQualityReport={
                "missingRequiredDomains": ["fundamentals", "earnings"],
                "importantDomainsMissing": [],
                "reasonCodes": ["valuation_only_snapshot"],
            },
        )
    )

    assert contract["normalizerState"] == "insufficient"
    assert contract["domains"]["valuation"]["status"] == "available"
    assert contract["domains"]["fundamentals"]["status"] == "missing"
    assert contract["domains"]["earnings"]["status"] in {"missing", "degraded"}
    assert contract["missingEvidence"][:2] == ["fundamentals", "earnings"]


def test_stale_fallback_proxy_evidence_downgrades_to_observe_only() -> None:
    helper = _load_helper_module()

    contract = helper.build_single_stock_fundamentals_earnings_normalizer_v1(
        _fullish_payload(
            structuredAnalysis={
                **_fullish_payload()["structuredAnalysis"],
                "fundamentals": {
                    "status": "partial",
                    "source": "yfinance_proxy",
                    "sourceTier": "unofficial_public_api",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "stale",
                    "proxyOnly": True,
                    "normalized": {
                        "marketCap": 145000000000,
                        "revenueGrowth": 0.04,
                    },
                    "field_sources": {
                        "marketCap": "yfinance",
                        "revenueGrowth": "yfinance",
                    },
                    "field_periods": {
                        "marketCap": "latest",
                        "revenueGrowth": "latest_quarter_yoy",
                    },
                },
                "earnings_analysis": {
                    "status": "partial",
                    "source": "alpha_vantage_income_statement",
                    "sourceTier": "fallback",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "fallback",
                    "quarterly_series": [
                        {
                            "quarter": "2026Q1",
                            "fiscalDateEnding": "2026-03-31",
                            "revenue": 1200000000,
                            "net_income": 60000000,
                        }
                    ],
                    "summary_flags": ["quarterly_series_available"],
                },
                "filings": {
                    "status": "partial",
                    "source": "cache/local_fixture",
                    "sourceTier": "fixture_demo",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "fixture",
                    "items": [
                        {"formType": "10-Q", "filedAt": "2026-04-01", "periodEnd": "2026-03-31"}
                    ],
                },
            },
            dataQualityReport={
                "missingRequiredDomains": [],
                "importantDomainsMissing": [],
                "reasonCodes": ["stale_required_source", "fallback_proxy_evidence"],
            },
        )
    )

    assert contract["normalizerState"] == "observe_only"
    assert contract["domains"]["fundamentals"]["status"] == "degraded"
    assert contract["domains"]["fundamentals"]["scoreContributionAllowed"] is False
    assert contract["domains"]["earnings"]["scoreContributionAllowed"] is False
    assert contract["sourceSummary"]["fundamentals"]["bestAuthorityTier"] == "observation_only"
    assert contract["sourceSummary"]["earnings"]["bestAuthorityTier"] == "fallback"
    assert all(
        ref["providerAuthority"] == "observationOnly"
        for ref in contract["evidenceRefs"]
        if ref["domain"] in {"fundamentals", "earnings", "filings"}
    )


def test_unknown_source_fails_closed_to_manual_unknown_and_bounded_output() -> None:
    helper = _load_helper_module()

    contract = helper.build_single_stock_fundamentals_earnings_normalizer_v1(
        _fullish_payload(
            structuredAnalysis={
                "fundamental_context": {
                    "status": "supported",
                    "market": "us",
                    "valuation": {"data": {"trailingPE": 18.2}},
                    "earnings": {"data": {"quarterly_series": [{"quarter": "2026Q1", "revenue": 80, "net_income": 6}]}},
                },
                "fundamentals": {
                    "status": "ok",
                    "source": "mystery_feed",
                    "freshness": "unknown",
                    "normalized": {"marketCap": 12500000000, "revenueGrowth": 0.12},
                    "field_sources": {"marketCap": "mystery_feed", "revenueGrowth": "mystery_feed"},
                    "field_periods": {"marketCap": "latest", "revenueGrowth": "ttm_yoy"},
                },
                "earnings_analysis": {
                    "status": "ok",
                    "source": "mystery_feed",
                    "freshness": "unknown",
                    "quarterly_series": [{"quarter": "2026Q1", "revenue": 80, "net_income": 6}],
                    "summary_flags": ["quarterly_series_available"],
                },
                "filings": {
                    "status": "ok",
                    "source": "mystery_feed",
                    "freshness": "unknown",
                    "items": [{"formType": "10-Q", "filedAt": "2026-05-01"}],
                },
            },
        )
    )

    assert contract["normalizerState"] == "observe_only"
    assert contract["sourceSummary"]["fundamentals"]["sourceIds"] == ["manual_unknown"]
    assert contract["sourceSummary"]["fundamentals"]["bestAuthorityTier"] == "unknown"
    assert contract["domains"]["fundamentals"]["scoreContributionAllowed"] is False
    assert all(ref["sourceId"] == "manual_unknown" for ref in contract["evidenceRefs"])
    assert all(ref["providerAuthority"] == "observationOnly" for ref in contract["evidenceRefs"])


def test_no_advice_boundary_fails_closed_when_missing() -> None:
    helper = _load_helper_module()

    contract = helper.build_single_stock_fundamentals_earnings_normalizer_v1(
        _fullish_payload(
            noAdviceBoundary=False,
            dataQualityReport={
                "missingRequiredDomains": [],
                "importantDomainsMissing": [],
                "reasonCodes": [],
            },
        )
    )

    assert contract["normalizerState"] == "blocked"
    assert contract["noAdviceBoundary"] == {
        "state": "blocked",
        "label": "仅研究，禁止转化为交易或执行建议",
    }
    assert "no_advice_boundary_missing" in contract["blockingReasons"]


def test_json_serialization_stability_and_no_raw_leakage() -> None:
    helper = _load_helper_module()

    contract = helper.build_single_stock_fundamentals_earnings_normalizer_v1(
        _fullish_payload(
            debugRef="debug://internal/router?token=secret",
            structuredAnalysis={
                **_fullish_payload()["structuredAnalysis"],
                "fundamentals": {
                    **_fullish_payload()["structuredAnalysis"]["fundamentals"],
                    "raw_payload": {"authorization": "Bearer secret", "router_debug": "abc"},
                    "stack_trace": "Traceback: internal",
                    "summary_text": "buy now before earnings",
                },
            },
        )
    )

    serialized = json.dumps(contract, ensure_ascii=False, sort_keys=True)
    assert json.loads(serialized) == contract
    assert contract["debugRef"] == "redacted"
    lowered = serialized.lower()
    for token in FORBIDDEN_SERIALIZED_TOKENS:
        assert token not in lowered
