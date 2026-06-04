# -*- coding: utf-8 -*-
"""Tests for the Home/single-stock source capability authority matrix helper."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = REPO_ROOT / "src/services/single_stock_source_capability_matrix.py"
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
)
REQUIRED_SOURCE_IDS = {
    "local_us_parquet",
    "alpaca",
    "yfinance",
    "polygon",
    "alpha_vantage",
    "finnhub",
    "fmp",
    "twelvedata",
    "gnews",
    "fred",
    "treasury",
    "cache_local_fixture",
    "manual_unknown",
}
REQUIRED_DOMAINS = {
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
REQUIRED_AUTHORITY_TIERS = {
    "score_grade",
    "observation_only",
    "fallback",
    "fixture_demo",
    "unavailable",
    "unknown",
}
REQUIRED_FLAT_FIELDS = {
    "sourceId",
    "displayLabel",
    "domains",
    "authorityTier",
    "freshnessClass",
    "marketCoverage",
    "useCase",
    "limitations",
    "scoreContributionAllowed",
    "observationOnly",
    "fallbackOrProxy",
    "nextEvidenceNeeded",
}


def _load_helper_module() -> Any:
    try:
        return importlib.import_module("src.services.single_stock_source_capability_matrix")
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised in initial RED run
        pytest.fail(f"single_stock_source_capability_matrix helper missing: {exc}")


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


def test_source_capability_matrix_helper_is_pure_deterministic_and_json_safe() -> None:
    helper = _load_helper_module()
    imports = _helper_imports()
    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)

    first = helper.list_single_stock_source_capabilities()
    second = helper.list_single_stock_source_capabilities()

    assert first == second
    assert json.loads(json.dumps(first, ensure_ascii=False)) == first
    assert REQUIRED_SOURCE_IDS == {item["sourceId"] for item in first}
    assert first == sorted(first, key=lambda item: item["sourceId"])

    for item in first:
        assert {"sourceId", "displayLabel", "domains", "domainCapabilities"} <= set(item)
        assert set(item["domains"]) <= REQUIRED_DOMAINS
        for domain_name, domain_capability in item["domainCapabilities"].items():
            assert domain_name in REQUIRED_DOMAINS
            assert REQUIRED_FLAT_FIELDS <= set(domain_capability)
            assert domain_capability["sourceId"] == item["sourceId"]
            assert domain_capability["displayLabel"] == item["displayLabel"]
            assert domain_capability["authorityTier"] in REQUIRED_AUTHORITY_TIERS


def test_known_source_domain_capabilities_are_conservative_and_bounded() -> None:
    helper = _load_helper_module()

    fmp = helper.get_single_stock_source_domain_capability("fmp", "fundamentals")
    assert fmp["sourceId"] == "fmp"
    assert fmp["authorityTier"] == "score_grade"
    assert fmp["scoreContributionAllowed"] is True
    assert fmp["observationOnly"] is False
    assert fmp["fallbackOrProxy"] is False
    assert fmp["freshnessClass"] == "daily"
    assert fmp["marketCoverage"] == ["us", "global"]

    alpha = helper.get_single_stock_source_domain_capability("alpha_vantage", "technicals")
    assert alpha["authorityTier"] == "fallback"
    assert alpha["scoreContributionAllowed"] is False
    assert alpha["observationOnly"] is True
    assert alpha["fallbackOrProxy"] is True
    assert "quota" in " ".join(alpha["limitations"]).lower()

    yahoo = helper.get_single_stock_source_domain_capability("yahoo", "priceHistory")
    assert yahoo["sourceId"] == "yfinance"
    assert yahoo["authorityTier"] == "observation_only"
    assert yahoo["scoreContributionAllowed"] is False
    assert yahoo["freshnessClass"] == "delayed"


def test_unknown_source_and_unlisted_domain_fail_closed() -> None:
    helper = _load_helper_module()

    unknown_source = helper.get_single_stock_source_domain_capability("mystery_feed", "fundamentals")
    assert unknown_source["sourceId"] == "manual_unknown"
    assert unknown_source["authorityTier"] == "unknown"
    assert unknown_source["scoreContributionAllowed"] is False
    assert unknown_source["observationOnly"] is True
    assert unknown_source["freshnessClass"] == "unknown"
    assert unknown_source["nextEvidenceNeeded"]

    unsupported_domain = helper.get_single_stock_source_domain_capability("polygon", "earnings")
    assert unsupported_domain["sourceId"] == "polygon"
    assert unsupported_domain["authorityTier"] == "unknown"
    assert unsupported_domain["scoreContributionAllowed"] is False
    assert unsupported_domain["observationOnly"] is True
    assert "not proven" in " ".join(unsupported_domain["limitations"]).lower()


def test_domain_summary_prefers_stronger_authority_without_overclaiming() -> None:
    helper = _load_helper_module()

    summary = helper.summarize_source_capabilities_by_domain(
        {
            "fundamentals": ["fmp", "yfinance", {"sourceId": "manual"}],
            "news": {"sources": ["gnews", "unknown"]},
            "macroLiquidity": [{"sourceId": "fred"}, {"sourceId": "treasury"}],
            "valuation": [{"sourceId": "alpha_vantage"}, {"sourceId": "fmp"}],
        }
    )

    fundamentals = summary["fundamentals"]
    assert fundamentals["domain"] == "fundamentals"
    assert fundamentals["bestAuthorityTier"] == "score_grade"
    assert fundamentals["scoreContributionAllowed"] is True
    assert fundamentals["sourceIds"] == ["fmp", "yfinance", "manual_unknown"]

    news = summary["news"]
    assert news["bestAuthorityTier"] == "observation_only"
    assert news["scoreContributionAllowed"] is False
    assert news["observationOnly"] is True

    macro = summary["macroLiquidity"]
    assert macro["bestAuthorityTier"] == "observation_only"
    assert macro["freshnessClass"] == "daily"
    assert macro["marketCoverage"] == ["us", "macro"]

    valuation = summary["valuation"]
    assert valuation["bestAuthorityTier"] == "score_grade"
    assert valuation["sourceIds"] == ["alpha_vantage", "fmp"]


@pytest.mark.parametrize(
    ("source_id", "domain"),
    [
        ("yfinance", "priceHistory"),
        ("alpha_vantage", "fundamentals"),
        ("cache_local_fixture", "news"),
        ("manual_unknown", "technicals"),
    ],
)
def test_observation_fallback_fixture_and_unknown_never_allow_score_contribution(
    source_id: str,
    domain: str,
) -> None:
    helper = _load_helper_module()

    capability = helper.get_single_stock_source_domain_capability(source_id, domain)

    assert capability["scoreContributionAllowed"] is False
    assert capability["authorityTier"] in {"observation_only", "fallback", "fixture_demo", "unknown"}


def test_freshness_market_coverage_and_summary_serialization_are_stable() -> None:
    helper = _load_helper_module()

    fred = helper.get_single_stock_source_domain_capability("fred", "macroLiquidity")
    local_history = helper.get_single_stock_source_domain_capability("local_us_parquet", "priceHistory")

    assert fred["freshnessClass"] == "daily"
    assert fred["marketCoverage"] == ["us", "macro"]
    assert local_history["freshnessClass"] == "local"
    assert local_history["marketCoverage"] == ["us"]

    summary = helper.summarize_source_capabilities_by_domain(
        {
            "priceHistory": ["local_us_parquet", "yfinance"],
            "catalysts": ["gnews", "cache/local_fixture"],
        }
    )
    serialized = json.dumps(summary, ensure_ascii=False, sort_keys=True)
    assert json.loads(serialized) == summary
    assert summary["priceHistory"]["bestAuthorityTier"] == "score_grade"
    assert summary["catalysts"]["bestAuthorityTier"] == "observation_only"
