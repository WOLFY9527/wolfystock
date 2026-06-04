# -*- coding: utf-8 -*-
"""Tests for the helper-only Home provenance sidecar builder."""

from __future__ import annotations

import ast
import copy
import importlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = REPO_ROOT / "src/services/home_source_provenance_sidecar.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "yfinance",
    "src.services.market_cache",
    "src.services.analysis_service",
    "src.settings",
)
REQUIRED_ENTRY_FIELDS = {
    "contractVersion",
    "sourceId",
    "sourceLabel",
    "evidenceDomain",
    "authorityTier",
    "freshnessState",
    "sourceTier",
    "fallbackOrProxy",
    "observationOnly",
    "scoreContributionAllowed",
    "limitations",
    "nextEvidenceNeeded",
    "debugRef",
}
DOMAIN_ORDER = [
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


def _load_helper_module() -> Any:
    try:
        return importlib.import_module("src.services.home_source_provenance_sidecar")
    except ModuleNotFoundError as exc:  # pragma: no cover
        pytest.fail(f"home_source_provenance_sidecar helper missing: {exc}")


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


def _fullish_payload() -> dict[str, Any]:
    return {
        "debugRef": "analysis:home-aapl-001",
        "singleStockEvidencePacket": {
            "contractVersion": "single_stock_evidence_packet_v1",
            "symbol": "AAPL",
            "market": "us",
            "debugRef": "analysis:home-aapl-001",
            "domains": {
                "priceHistory": {
                    "status": "available",
                    "sourceTier": "score_grade",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "fresh",
                    "fallbackOrProxy": False,
                    "missingReasons": [],
                    "nextEvidenceNeeded": [],
                },
                "technicals": {
                    "status": "available",
                    "sourceTier": "score_grade",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "fresh",
                    "fallbackOrProxy": False,
                    "missingReasons": [],
                    "nextEvidenceNeeded": [],
                },
                "fundamentals": {
                    "status": "available",
                    "sourceTier": "score_grade",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "fresh",
                    "fallbackOrProxy": False,
                    "missingReasons": [],
                    "nextEvidenceNeeded": [],
                },
                "earnings": {
                    "status": "available",
                    "sourceTier": "score_grade",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "fresh",
                    "fallbackOrProxy": False,
                    "missingReasons": [],
                    "nextEvidenceNeeded": [],
                },
                "filings": {
                    "status": "available",
                    "sourceTier": "official_public",
                    "providerAuthority": "observationOnly",
                    "freshness": "fresh",
                    "fallbackOrProxy": False,
                    "missingReasons": [],
                    "nextEvidenceNeeded": [],
                },
                "news": {
                    "status": "available",
                    "sourceTier": "official_public",
                    "providerAuthority": "observationOnly",
                    "freshness": "fresh",
                    "fallbackOrProxy": False,
                    "missingReasons": [],
                    "nextEvidenceNeeded": [],
                },
                "catalysts": {
                    "status": "available",
                    "sourceTier": "official_public",
                    "providerAuthority": "observationOnly",
                    "freshness": "fresh",
                    "fallbackOrProxy": False,
                    "missingReasons": [],
                    "nextEvidenceNeeded": [],
                },
                "sentiment": {
                    "status": "available",
                    "sourceTier": "official_public",
                    "providerAuthority": "observationOnly",
                    "freshness": "fresh",
                    "fallbackOrProxy": False,
                    "missingReasons": [],
                    "nextEvidenceNeeded": [],
                },
                "valuation": {
                    "status": "available",
                    "sourceTier": "score_grade",
                    "providerAuthority": "scoreGradeAllowed",
                    "freshness": "fresh",
                    "fallbackOrProxy": False,
                    "missingReasons": [],
                    "nextEvidenceNeeded": [],
                },
                "sectorTheme": {
                    "status": "degraded",
                    "sourceTier": "official_public",
                    "providerAuthority": "observationOnly",
                    "freshness": "delayed",
                    "fallbackOrProxy": False,
                    "missingReasons": ["observation_only_evidence"],
                    "nextEvidenceNeeded": ["补充行业主题证据"],
                },
                "macroLiquidity": {
                    "status": "degraded",
                    "sourceTier": "official_public",
                    "providerAuthority": "observationOnly",
                    "freshness": "delayed",
                    "fallbackOrProxy": False,
                    "missingReasons": ["observation_only_evidence"],
                    "nextEvidenceNeeded": ["补充宏观流动性证据"],
                },
            },
        },
        "evidenceCitationFrame": {
            "contractVersion": "home_report_evidence_citation_frame_v1",
            "domainCoverage": [
                {"domain": "fundamentals", "status": "available", "authorityLabel": "scoreGrade", "freshnessLabel": "fresh"},
                {"domain": "earnings", "status": "available", "authorityLabel": "scoreGrade", "freshnessLabel": "fresh"},
                {"domain": "news", "status": "available", "authorityLabel": "observationOnly", "freshnessLabel": "fresh"},
                {"domain": "sectorTheme", "status": "degraded", "authorityLabel": "observationOnly", "freshnessLabel": "delayed", "notes": ["观察性行业主题"]},
            ],
            "citedEvidence": [
                {"id": "fund-1", "domain": "fundamentals", "sourceId": "fmp", "freshness": "fresh"},
                {"id": "earn-1", "domain": "earnings", "sourceId": "fmp_income_statement", "freshness": "fresh"},
                {"id": "news-1", "domain": "news", "sourceId": "finnhub_news", "freshness": "fresh"},
            ],
        },
        "sourceMetadataByDomain": {
            "priceHistory": {
                "sourceId": "polygon_us_grouped_daily",
                "sourceLabel": "Polygon grouped daily",
                "sourceTier": "authorized_licensed_feed",
                "providerAuthority": "scoreGradeAllowed",
                "freshness": "fresh",
                "scoreContributionAllowed": True,
            },
            "technicals": {
                "sourceId": "polygon_us_grouped_daily",
                "sourceLabel": "Polygon grouped daily",
                "sourceTier": "authorized_licensed_feed",
                "providerAuthority": "scoreGradeAllowed",
                "freshness": "fresh",
                "scoreContributionAllowed": True,
            },
            "fundamentals": {
                "sourceId": "fmp",
                "sourceLabel": "Financial Modeling Prep",
                "sourceTier": "authorized_licensed_feed",
                "providerAuthority": "scoreGradeAllowed",
                "freshness": "fresh",
                "scoreContributionAllowed": True,
            },
            "earnings": {
                "sourceId": "fmp_income_statement",
                "sourceLabel": "FMP income statement",
                "sourceTier": "authorized_licensed_feed",
                "providerAuthority": "scoreGradeAllowed",
                "freshness": "fresh",
                "scoreContributionAllowed": True,
            },
            "filings": {
                "sourceId": "sec_edgar",
                "sourceLabel": "SEC EDGAR",
                "sourceTier": "official_public",
                "providerAuthority": "observationOnly",
                "freshness": "fresh",
            },
            "news": {
                "sourceId": "finnhub_news",
                "sourceLabel": "Finnhub news",
                "sourceTier": "official_public",
                "providerAuthority": "observationOnly",
                "freshness": "fresh",
            },
            "catalysts": {
                "sourceId": "gnews",
                "sourceLabel": "GNews",
                "sourceTier": "official_public",
                "providerAuthority": "observationOnly",
                "freshness": "fresh",
            },
            "sentiment": {
                "sourceId": "finnhub_sentiment",
                "sourceLabel": "Finnhub sentiment",
                "sourceTier": "official_public",
                "providerAuthority": "observationOnly",
                "freshness": "fresh",
            },
            "valuation": {
                "sourceId": "fmp_ratios",
                "sourceLabel": "FMP ratios",
                "sourceTier": "authorized_licensed_feed",
                "providerAuthority": "scoreGradeAllowed",
                "freshness": "fresh",
                "scoreContributionAllowed": True,
            },
            "sectorTheme": {
                "sourceId": "official_macro_bundle",
                "sourceLabel": "Official macro bundle",
                "sourceTier": "official_public",
                "providerAuthority": "observationOnly",
                "freshness": "delayed",
                "nextEvidenceNeeded": ["补充行业主题证据"],
            },
            "macroLiquidity": {
                "sourceId": "official_macro_bundle",
                "sourceLabel": "Official macro bundle",
                "sourceTier": "official_public",
                "providerAuthority": "observationOnly",
                "freshness": "delayed",
                "nextEvidenceNeeded": ["补充宏观流动性证据"],
            },
        },
    }


def test_home_source_provenance_sidecar_is_pure_deterministic_and_json_stable() -> None:
    helper = _load_helper_module()
    imports = _helper_imports()
    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)

    payload = _fullish_payload()
    original = copy.deepcopy(payload)

    first = helper.build_home_source_provenance_sidecar_v1(payload)
    second = helper.build_home_source_provenance_sidecar_v1(payload)

    assert payload == original
    assert first == second
    assert json.loads(json.dumps(first, ensure_ascii=False)) == first
    assert [entry["evidenceDomain"] for entry in first] == DOMAIN_ORDER
    for entry in first:
        assert set(entry) == REQUIRED_ENTRY_FIELDS


def test_fullish_packet_maps_all_home_domains_into_source_provenance_entries() -> None:
    helper = _load_helper_module()

    entries = helper.build_home_source_provenance_sidecar_v1(_fullish_payload())
    by_domain = {entry["evidenceDomain"]: entry for entry in entries}

    assert by_domain["priceHistory"]["sourceId"] == "polygon_us_grouped_daily"
    assert by_domain["priceHistory"]["authorityTier"] == "score_grade"
    assert by_domain["priceHistory"]["sourceTier"] == "authorized_feed"
    assert by_domain["priceHistory"]["freshnessState"] == "fresh"
    assert by_domain["priceHistory"]["scoreContributionAllowed"] is True

    assert by_domain["fundamentals"]["sourceId"] == "fmp"
    assert by_domain["fundamentals"]["authorityTier"] == "score_grade"
    assert by_domain["fundamentals"]["scoreContributionAllowed"] is True

    assert by_domain["filings"]["sourceId"] == "sec_edgar"
    assert by_domain["filings"]["authorityTier"] == "observation_only"
    assert by_domain["filings"]["sourceTier"] == "official_public"
    assert by_domain["filings"]["scoreContributionAllowed"] is False

    assert by_domain["macroLiquidity"]["sourceId"] == "official_macro_bundle"
    assert by_domain["macroLiquidity"]["freshnessState"] == "delayed"
    assert by_domain["macroLiquidity"]["observationOnly"] is True
    assert "补充宏观流动性证据" in by_domain["macroLiquidity"]["nextEvidenceNeeded"]


def test_orcl_like_partial_unsupported_fundamentals_fail_closed_to_unknown() -> None:
    helper = _load_helper_module()
    payload = _fullish_payload()
    payload["singleStockEvidencePacket"]["symbol"] = "ORCL"
    payload["singleStockEvidencePacket"]["domains"]["fundamentals"] = {
        "status": "missing",
        "sourceTier": "unknown",
        "providerAuthority": "observationOnly",
        "freshness": "unknown",
        "fallbackOrProxy": False,
        "missingReasons": ["fundamental_context_unavailable"],
        "nextEvidenceNeeded": ["补充基本面证据"],
    }
    payload["sourceMetadataByDomain"]["fundamentals"] = {}

    entries = helper.build_home_source_provenance_sidecar_v1(payload)
    fundamentals = {entry["evidenceDomain"]: entry for entry in entries}["fundamentals"]

    assert fundamentals["sourceId"] == "unknown_source"
    assert fundamentals["sourceLabel"] == "未知来源"
    assert fundamentals["authorityTier"] == "unknown"
    assert fundamentals["freshnessState"] == "unknown"
    assert fundamentals["scoreContributionAllowed"] is False
    assert "fundamental_context_unavailable" in fundamentals["limitations"]
    assert "补充基本面证据" in fundamentals["nextEvidenceNeeded"]


def test_stale_fallback_proxy_sources_downgrade_fail_closed() -> None:
    helper = _load_helper_module()
    payload = _fullish_payload()
    payload["singleStockEvidencePacket"]["domains"]["technicals"] = {
        "status": "partial",
        "sourceTier": "unofficial_public_api",
        "providerAuthority": "scoreGradeAllowed",
        "freshness": "stale",
        "fallbackOrProxy": True,
        "missingReasons": ["stale_evidence", "fallback_proxy_evidence"],
        "nextEvidenceNeeded": ["补充技术面证据"],
    }
    payload["sourceMetadataByDomain"]["technicals"] = {
        "sourceId": "yfinance_proxy",
        "sourceLabel": "Yahoo Finance proxy",
        "sourceTier": "unofficial_public_api",
        "providerAuthority": "scoreGradeAllowed",
        "freshness": "stale",
        "fallbackOrProxy": True,
    }

    entries = helper.build_home_source_provenance_sidecar_v1(payload)
    technicals = {entry["evidenceDomain"]: entry for entry in entries}["technicals"]

    assert technicals["sourceId"] == "yfinance_proxy"
    assert technicals["sourceTier"] == "proxy"
    assert technicals["freshnessState"] == "stale"
    assert technicals["fallbackOrProxy"] is True
    assert technicals["observationOnly"] is True
    assert technicals["scoreContributionAllowed"] is False
    assert "stale_evidence" in technicals["limitations"]
    assert "fallback_proxy_evidence" in technicals["limitations"]


def test_news_timeout_and_fixture_demo_sources_fail_closed_without_leakage() -> None:
    helper = _load_helper_module()
    payload = _fullish_payload()
    payload["singleStockEvidencePacket"]["domains"]["news"] = {
        "status": "blocked",
        "sourceTier": "unknown",
        "providerAuthority": "observationOnly",
        "freshness": "unknown",
        "fallbackOrProxy": False,
        "missingReasons": ["provider_timeout", "authorization_secret"],
        "nextEvidenceNeeded": ["补充新闻证据"],
    }
    payload["singleStockEvidencePacket"]["domains"]["catalysts"] = {
        "status": "degraded",
        "sourceTier": "synthetic_fixture",
        "providerAuthority": "observationOnly",
        "freshness": "demo",
        "fallbackOrProxy": True,
        "missingReasons": ["demo_only"],
        "nextEvidenceNeeded": ["补充催化剂证据"],
    }
    payload["sourceMetadataByDomain"]["news"] = {}
    payload["sourceMetadataByDomain"]["catalysts"] = {
        "sourceId": "fixture_demo",
        "sourceLabel": "Fixture Demo token dump",
        "sourceTier": "synthetic_fixture",
        "providerAuthority": "fixture",
        "freshness": "synthetic",
        "fallbackOrProxy": True,
        "debugRef": "session:token",
    }

    entries = helper.build_home_source_provenance_sidecar_v1(payload)
    by_domain = {entry["evidenceDomain"]: entry for entry in entries}

    assert by_domain["news"]["sourceId"] == "unknown_source"
    assert by_domain["news"]["scoreContributionAllowed"] is False
    assert "provider_timeout" in by_domain["news"]["limitations"]
    assert "补充新闻证据" in by_domain["news"]["nextEvidenceNeeded"]

    assert by_domain["catalysts"]["authorityTier"] == "fixture"
    assert by_domain["catalysts"]["freshnessState"] == "synthetic"
    assert by_domain["catalysts"]["fallbackOrProxy"] is True
    assert by_domain["catalysts"]["scoreContributionAllowed"] is False

    serialized = json.dumps(entries, ensure_ascii=False).lower()
    for blocked in ("authorization", "token", "session", "payload", "secret", "trade", "broker"):
        assert blocked not in serialized


def test_json_output_stays_stable_with_fixed_domain_order() -> None:
    helper = _load_helper_module()

    first = helper.build_home_source_provenance_sidecar_v1(_fullish_payload())
    second = helper.build_home_source_provenance_sidecar_v1(_fullish_payload())

    assert json.dumps(first, ensure_ascii=False, sort_keys=False) == json.dumps(
        second,
        ensure_ascii=False,
        sort_keys=False,
    )


def test_helper_has_no_runtime_integration_references() -> None:
    result = subprocess.run(
        ["rg", "-n", "build_home_source_provenance_sidecar_v1|home_source_provenance_sidecar"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]

    assert lines
    assert all(
        line.startswith("src/services/home_source_provenance_sidecar.py:")
        or line.startswith("tests/services/test_home_source_provenance_sidecar.py:")
        for line in lines
    )
