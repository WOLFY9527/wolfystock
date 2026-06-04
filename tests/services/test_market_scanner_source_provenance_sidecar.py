# -*- coding: utf-8 -*-
"""Tests for the helper-only Scanner provenance sidecar builder."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from src.services.market_scanner_source_provenance_sidecar import (
    SCANNER_SOURCE_PROVENANCE_DOMAIN_ORDER,
    build_market_scanner_source_provenance_sidecar,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = REPO_ROOT / "src/services/market_scanner_source_provenance_sidecar.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "yfinance",
    "src.services.market_scanner_service",
    "src.services.market_cache",
    "src.settings",
)


def _helper_imports() -> set[str]:
    tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def _us_candidate() -> dict[str, object]:
    return {
        "symbol": "NVDA",
        "market": "us",
        "diagnostics": {
            "history": {
                "rows": 120,
                "latest_trade_date": "2026-06-04",
                "source": "polygon_us_grouped_daily",
                "sourceLabel": "Polygon grouped daily US equities",
                "sourceType": "authorized_licensed_feed",
                "sourceTier": "authorized_licensed_feed",
                "freshness": "fresh",
            },
            "quote_context": {
                "available": True,
                "source": "polygon_us_grouped_daily",
                "sourceLabel": "Polygon grouped daily US equities",
                "sourceType": "authorized_licensed_feed",
                "sourceTier": "authorized_licensed_feed",
                "freshness": "fresh",
            },
            "score_explainability": {
                "source_confidence": {
                    "source": "polygon_us_grouped_daily",
                    "sourceLabel": "Polygon grouped daily US equities",
                    "sourceType": "authorized_licensed_feed",
                    "sourceTier": "authorized_licensed_feed",
                    "freshness": "fresh",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                    "observationOnly": False,
                }
            },
            "fundamentals": {
                "source": "fmp",
                "sourceLabel": "Financial Modeling Prep",
                "sourceType": "official_public",
                "sourceTier": "official_public",
                "freshness": "fresh",
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
            },
            "news_context": {
                "source": "benzinga",
                "sourceLabel": "Benzinga News",
                "sourceType": "official_public",
                "sourceTier": "official_public",
                "freshness": "fresh",
            },
            "catalyst": {
                "source": "benzinga",
                "sourceLabel": "Benzinga News",
                "sourceType": "official_public",
                "sourceTier": "official_public",
                "freshness": "fresh",
            },
            "theme_context": {
                "source": "market_themes_snapshot",
                "sourceLabel": "Market themes snapshot",
                "sourceType": "cache_snapshot",
                "sourceTier": "cache_snapshot",
                "freshness": "cached",
            },
        },
    }


def _us_candidate_evidence_frame() -> dict[str, object]:
    return {
        "contractVersion": "scanner_candidate_evidence_v1",
        "coverageState": "available",
        "domains": {
            "priceHistory": {"state": "available", "observationOnly": False, "scoreGradeAllowed": True, "freshness": "fresh"},
            "liquidity": {"state": "available", "observationOnly": False, "scoreGradeAllowed": True, "freshness": "fresh"},
            "technicals": {"state": "available", "observationOnly": False, "scoreGradeAllowed": True, "freshness": "fresh"},
            "fundamentals": {"state": "available", "observationOnly": False, "scoreGradeAllowed": False, "freshness": "unknown"},
            "newsCatalyst": {"state": "available", "observationOnly": False, "scoreGradeAllowed": False, "freshness": "unknown"},
            "theme": {"state": "available", "observationOnly": False, "scoreGradeAllowed": True, "freshness": "cached"},
        },
        "coverage": {},
        "noAdviceBoundary": True,
    }


def _us_readiness() -> dict[str, object]:
    return {
        "contractVersion": "research_readiness_v1",
        "readinessState": "ready",
        "sourceAuthority": "scoreGradeAllowed",
        "providerAuthority": "scoreGradeAllowed",
        "freshness": "fresh",
        "freshnessFloor": "fresh",
        "market": "us",
        "nextEvidenceNeeded": [],
        "blockingReasons": [],
        "missingEvidence": [],
        "noAdviceBoundary": True,
    }


def _us_summary() -> dict[str, object]:
    return {
        "contractVersion": "scanner_candidate_research_summary_v1",
        "frameState": "ready",
        "topDownContextRefs": [
            {"key": "marketReadiness", "state": "ready", "label": "Top-down market context available"},
            {"key": "liquidityFrame", "state": "supportive", "label": "Liquidity context available"},
        ],
        "sourceAuthority": "scoreGradeAllowed",
        "freshness": "fresh",
    }


def _us_context() -> dict[str, object]:
    return {
        "marketReadiness": {
            "readinessState": "ready",
            "source": "market_breadth_snapshot",
            "sourceLabel": "Market breadth snapshot",
            "sourceType": "cache_snapshot",
            "sourceTier": "cache_snapshot",
            "freshness": "cached",
        },
        "liquidityFrame": {
            "state": "supportive",
            "source": "fred_liquidity_bundle",
            "sourceLabel": "FRED liquidity bundle",
            "sourceType": "official_public",
            "sourceTier": "official_public",
            "freshness": "fresh",
        },
        "noAdviceBoundary": True,
    }


def test_helper_is_pure_and_json_stable() -> None:
    imports = _helper_imports()
    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)

    summary = build_market_scanner_source_provenance_sidecar(
        _us_candidate(),
        candidate_evidence_frame=_us_candidate_evidence_frame(),
        candidate_research_readiness=_us_readiness(),
        candidate_research_summary_frame=_us_summary(),
        scanner_context_frame=_us_context(),
    )

    assert json.loads(json.dumps(summary, ensure_ascii=False, sort_keys=True)) == summary


def test_us_score_grade_inputs_build_expected_domains_without_runtime_integration() -> None:
    summary = build_market_scanner_source_provenance_sidecar(
        _us_candidate(),
        candidate_evidence_frame=_us_candidate_evidence_frame(),
        candidate_research_readiness=_us_readiness(),
        candidate_research_summary_frame=_us_summary(),
        scanner_context_frame=_us_context(),
    )

    entries_by_ref = {entry["debugRef"]: entry for entry in summary["entries"]}

    assert summary["entryCount"] == len(SCANNER_SOURCE_PROVENANCE_DOMAIN_ORDER)
    assert "source-provenance:scanner:pricehistory:polygon-us-grouped-daily" in entries_by_ref
    assert entries_by_ref["source-provenance:scanner:pricehistory:polygon-us-grouped-daily"]["authorityTier"] == "score_grade"
    assert entries_by_ref["source-provenance:scanner:pricehistory:polygon-us-grouped-daily"]["scoreContributionAllowed"] is True
    assert entries_by_ref["source-provenance:scanner:macroliquidity:fred-liquidity-bundle"]["sourceTier"] == "official_public"
    assert entries_by_ref["source-provenance:scanner:sectortheme:market-themes-snapshot"]["freshnessState"] == "cached"
    assert entries_by_ref["source-provenance:scanner:topdowncontext:market-breadth-snapshot"]["observationOnly"] is True


def test_cn_observation_only_and_fallback_sources_fail_closed() -> None:
    candidate = {
        "symbol": "600001",
        "market": "cn",
        "diagnostics": {
            "history": {
                "source": "akshare_proxy_cn_snapshot",
                "sourceLabel": "AKShare CN proxy snapshot",
                "sourceType": "public_proxy",
                "sourceTier": "public_proxy",
                "freshness": "fallback",
            },
            "score_explainability": {
                "source_confidence": {
                    "source": "akshare_proxy_cn_snapshot",
                    "sourceLabel": "AKShare CN proxy snapshot",
                    "sourceType": "public_proxy",
                    "sourceTier": "public_proxy",
                    "freshness": "fallback",
                    "sourceAuthorityAllowed": False,
                    "scoreContributionAllowed": False,
                    "observationOnly": True,
                }
            },
        },
    }
    evidence_frame = {
        "domains": {
            "priceHistory": {"state": "partial", "observationOnly": True, "scoreGradeAllowed": False, "freshness": "fallback"},
            "liquidity": {"state": "partial", "observationOnly": True, "scoreGradeAllowed": False, "freshness": "fallback"},
            "technicals": {"state": "partial", "observationOnly": True, "scoreGradeAllowed": False, "freshness": "fallback"},
            "fundamentals": {"state": "missing", "observationOnly": False, "scoreGradeAllowed": False, "freshness": "unknown"},
            "newsCatalyst": {"state": "missing", "observationOnly": False, "scoreGradeAllowed": False, "freshness": "unknown"},
            "theme": {"state": "missing", "observationOnly": False, "scoreGradeAllowed": False, "freshness": "unknown"},
        }
    }
    readiness = {
        "readinessState": "observe_only",
        "sourceAuthority": "observationOnly",
        "freshnessFloor": "fallback",
        "freshness": "fallback",
        "market": "cn",
        "nextEvidenceNeeded": ["补充来源授权证据"],
    }

    summary = build_market_scanner_source_provenance_sidecar(
        candidate,
        candidate_evidence_frame=evidence_frame,
        candidate_research_readiness=readiness,
        candidate_research_summary_frame={},
        scanner_context_frame={},
    )

    assert summary["scoreContributionAllowedCount"] == 0
    for entry in summary["entries"]:
        assert entry["observationOnly"] is True
        assert entry["scoreContributionAllowed"] is False
        if entry["sourceId"] != "unknown_source":
            assert "cn_observation_only" in entry["limitations"]


def test_blocked_scanner_context_forces_unavailable_top_down_entries() -> None:
    summary = build_market_scanner_source_provenance_sidecar(
        _us_candidate(),
        candidate_evidence_frame=_us_candidate_evidence_frame(),
        candidate_research_readiness={
            **_us_readiness(),
            "readinessState": "blocked",
            "sourceAuthority": "unavailable",
            "freshnessFloor": "unknown",
            "freshness": "unavailable",
            "nextEvidenceNeeded": ["补充宏观证据"],
        },
        candidate_research_summary_frame=_us_summary(),
        scanner_context_frame={
            "marketReadiness": {
                "readinessState": "blocked",
                "source": "market_context_proxy",
                "sourceLabel": "Market context proxy",
                "sourceType": "public_proxy",
                "sourceTier": "public_proxy",
                "freshness": "unavailable",
            },
            "liquidityFrame": {
                "state": "blocked",
                "source": "macro_demo",
                "sourceLabel": "Macro demo",
                "sourceType": "public_proxy",
                "sourceTier": "public_proxy",
                "freshness": "unavailable",
            },
        },
    )

    top_down = next(
        entry for entry in summary["entries"] if entry["debugRef"] == "source-provenance:scanner:topdowncontext:market-context-proxy"
    )
    macro = next(
        entry for entry in summary["entries"] if entry["debugRef"] == "source-provenance:scanner:macroliquidity:macro-demo"
    )

    assert top_down["freshnessState"] == "unavailable"
    assert top_down["authorityTier"] == "unknown"
    assert "blocked_runtime_context" in top_down["limitations"]
    assert macro["fallbackOrProxy"] is True
    assert macro["authorityTier"] == "fixture"
    assert macro["freshnessState"] == "synthetic"


def test_missing_candidate_evidence_fails_closed_to_unknown_source() -> None:
    summary = build_market_scanner_source_provenance_sidecar(
        {"symbol": "TSLA", "market": "us"},
        candidate_evidence_frame={
            "domains": {
                "priceHistory": {"state": "missing"},
                "liquidity": {"state": "missing"},
                "technicals": {"state": "missing"},
                "fundamentals": {"state": "missing"},
                "newsCatalyst": {"state": "missing"},
                "theme": {"state": "missing"},
            }
        },
        candidate_research_readiness={"market": "us", "nextEvidenceNeeded": ["补充技术面证据"]},
        candidate_research_summary_frame={},
        scanner_context_frame={},
    )

    assert summary["observationOnlyCount"] == len(SCANNER_SOURCE_PROVENANCE_DOMAIN_ORDER)
    assert summary["authorityTierCounts"]["unknown"] >= 1
    assert all("missing_candidate_evidence" in entry["limitations"] or entry["sourceId"] == "unknown_source" for entry in summary["entries"])


def test_leakage_guardrails_redact_sensitive_scanner_inputs() -> None:
    summary = build_market_scanner_source_provenance_sidecar(
        {
            "symbol": "META",
            "market": "us",
            "diagnostics": {
                "history": {
                    "source": "provider_payload_session_cookie",
                    "sourceLabel": "internal raw payload token",
                    "sourceType": "authorized_licensed_feed",
                    "sourceTier": "authorized_licensed_feed",
                    "freshness": "fresh",
                }
            },
        },
        candidate_evidence_frame={
            "domains": {
                "priceHistory": {"state": "available", "observationOnly": False, "scoreGradeAllowed": True, "freshness": "fresh"},
                "liquidity": {"state": "missing"},
                "technicals": {"state": "missing"},
                "fundamentals": {"state": "missing"},
                "newsCatalyst": {"state": "missing"},
                "theme": {"state": "missing"},
            }
        },
        candidate_research_readiness=_us_readiness(),
        candidate_research_summary_frame={},
        scanner_context_frame={},
    )

    consumer_values = json.dumps(summary, ensure_ascii=False).lower()
    for blocked in ("token", "cookie", "session", "payload", "internal", "raw"):
        assert blocked not in consumer_values

    first_entry = summary["entries"][0]
    assert first_entry["sourceId"] == "unknown_source"
    assert first_entry["sourceLabel"] == "未知来源"


def test_fixture_demo_inputs_fail_closed_to_synthetic_provenance() -> None:
    summary = build_market_scanner_source_provenance_sidecar(
        {
            "symbol": "DEMO",
            "market": "us",
            "diagnostics": {
                "theme_context": {
                    "source": "theme_fixture_demo",
                    "sourceLabel": "Theme fixture demo",
                    "sourceType": "synthetic_fixture",
                    "sourceTier": "synthetic_fixture",
                    "freshness": "synthetic",
                }
            },
        },
        candidate_evidence_frame={
            "domains": {
                "priceHistory": {"state": "missing"},
                "liquidity": {"state": "missing"},
                "technicals": {"state": "missing"},
                "fundamentals": {"state": "missing"},
                "newsCatalyst": {"state": "missing"},
                "theme": {"state": "available"},
            }
        },
        candidate_research_readiness={"market": "us"},
        candidate_research_summary_frame={},
        scanner_context_frame={},
    )

    theme_entry = next(entry for entry in summary["entries"] if "scanner:sectortheme" in entry["debugRef"])
    assert theme_entry["authorityTier"] == "fixture"
    assert theme_entry["freshnessState"] == "synthetic"
    assert theme_entry["scoreContributionAllowed"] is False
