# -*- coding: utf-8 -*-
"""Tests for the producer-owned News/Catalyst lineage bundle."""

from __future__ import annotations

import ast
import importlib
from datetime import datetime
from pathlib import Path
from typing import Any

from src.search_service import SearchResponse, SearchResult, SearchService


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = REPO_ROOT / "src/services/news_catalyst_producer_lineage.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "aiohttp",
    "data_provider",
    "httpx",
    "requests",
    "src.search_service",
    "urllib",
    "yfinance",
)


def _load_helper_module() -> Any:
    return importlib.import_module("src.services.news_catalyst_producer_lineage")


def _helper_imports() -> set[str]:
    tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def _response(
    *,
    provider: str = "Finnhub",
    source: str = "Reuters",
    url: str = "https://example.com/aapl-product-update",
    published_date: str | None = "2026-07-10T09:15:00+08:00",
) -> SearchResponse:
    return SearchResponse(
        query="AAPL latest news",
        results=[
            SearchResult(
                title="Apple publishes a product update",
                snippet="A bounded producer result.",
                url=url,
                source=source,
                published_date=published_date,
            )
        ],
        provider=provider,
        success=True,
    )


def test_real_search_metadata_is_preserved_without_inventing_authority() -> None:
    helper = _load_helper_module()

    bundle = helper.build_news_catalyst_producer_lineage_bundle_v1(
        _response(),
        capability_family="stock_news",
    )

    assert bundle["contractVersion"] == helper.NEWS_CATALYST_PRODUCER_LINEAGE_VERSION
    assert bundle["producerBoundary"] == "search_service_response"
    assert bundle["capabilityFamily"] == "stock_news"
    assert bundle["sourceId"] == "Finnhub"
    assert bundle["sourceType"] == "search_proxy"
    assert bundle["authority"] == "non_authoritative"
    assert bundle["asOf"] is None
    assert bundle["eventTimestamp"] is None
    assert bundle["networkCallsEnabled"] is False
    assert bundle["runtimeProviderCalls"] is False
    assert bundle["itemCount"] == 1

    item = bundle["items"][0]
    assert item["itemId"].startswith("news_lineage_")
    assert item["capabilityFamily"] == "stock_news"
    assert item["sourceId"] == "Reuters"
    assert item["sourceType"] == "publisher_reference"
    assert item["authority"] is None
    assert item["evidenceRef"] == "https://example.com/aapl-product-update"
    assert item["publishedAt"] == "2026-07-10T09:15:00+08:00"
    assert item["eventTimestamp"] is None
    assert item["asOf"] is None
    assert item["timezone"] == "+08:00"
    assert "publisher_authority_not_established" in item["limitations"]
    assert "event_timestamp_missing" in item["limitations"]
    assert "as_of_missing" in item["limitations"]


def test_missing_lineage_fails_closed_without_placeholder_metadata() -> None:
    helper = _load_helper_module()

    bundle = helper.build_news_catalyst_producer_lineage_bundle_v1(
        _response(provider="None", source="", url="", published_date=None),
        capability_family="stock_news",
    )

    assert bundle["sourceId"] is None
    assert bundle["sourceType"] is None
    assert bundle["authority"] is None
    assert bundle["asOf"] is None
    assert bundle["timezone"] is None
    assert "producer_source_missing" in bundle["limitations"]

    item = bundle["items"][0]
    assert item["sourceId"] is None
    assert item["sourceType"] is None
    assert item["authority"] is None
    assert item["evidenceRef"] is None
    assert item["publishedAt"] is None
    assert item["eventTimestamp"] is None
    assert item["asOf"] is None
    assert item["timezone"] is None
    assert {
        "publisher_source_missing",
        "evidence_reference_missing",
        "published_at_missing",
        "event_timestamp_missing",
        "as_of_missing",
        "timezone_missing",
    } <= set(item["limitations"])


def test_explicit_as_of_is_preserved_but_missing_as_of_stays_missing() -> None:
    helper = _load_helper_module()
    response = _response()
    response.as_of = "2026-07-10T01:30:00Z"
    response.timezone = "UTC"

    explicit = helper.build_news_catalyst_producer_lineage_bundle_v1(
        response,
        capability_family="stock_news",
    )
    missing = helper.build_news_catalyst_producer_lineage_bundle_v1(
        _response(),
        capability_family="stock_news",
    )

    assert explicit["asOf"] == "2026-07-10T01:30:00Z"
    assert explicit["timezone"] == "UTC"
    assert explicit["items"][0]["asOf"] == "2026-07-10T01:30:00Z"
    assert missing["asOf"] is None
    assert missing["items"][0]["asOf"] is None


def test_sample_and_search_proxy_producers_remain_non_authoritative() -> None:
    helper = _load_helper_module()

    sample = helper.build_news_catalyst_producer_lineage_bundle_v1(
        _response(provider="fixture-news"),
        capability_family="stock_news",
    )
    proxy = helper.build_news_catalyst_producer_lineage_bundle_v1(
        _response(provider="Tavily"),
        capability_family="stock_news",
    )

    assert sample["sourceType"] == "sample"
    assert sample["authority"] == "non_authoritative"
    assert "sample_producer_non_authoritative" in sample["limitations"]
    assert proxy["sourceType"] == "search_proxy"
    assert proxy["authority"] == "non_authoritative"
    assert "search_proxy_non_authoritative" in proxy["limitations"]
    assert "official" not in str(sample).lower()
    assert "official" not in str(proxy).lower()


def test_bundle_builder_is_passive_and_has_no_transport_imports() -> None:
    helper = _load_helper_module()

    imports = _helper_imports()
    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)

    response = _response()
    before = repr(response)
    bundle = helper.build_news_catalyst_producer_lineage_bundle_v1(
        response,
        capability_family="stock_news",
    )

    assert repr(response) == before
    assert bundle["networkCallsEnabled"] is False
    assert bundle["runtimeProviderCalls"] is False


def test_search_normalization_preserves_raw_published_at_in_attached_bundle() -> None:
    raw_published_at = datetime.now().astimezone().replace(microsecond=0).isoformat()
    response = _response(published_date=raw_published_at)
    response.attempts = [{"provider": "Finnhub", "result": "succeeded"}]
    response.diagnostics = {"attempted_providers": 1}
    service = SearchService(searxng_public_instances_enabled=False)

    normalized = service._normalize_and_limit_response(response, max_results=1)
    filtered = service._filter_news_response(
        response,
        search_days=3,
        max_results=1,
        log_scope="test:stock_news",
    )

    expected_date = (
        datetime.fromisoformat(raw_published_at).astimezone().date().isoformat()
    )
    assert normalized.results[0].published_date == expected_date
    assert normalized.results[0].published_at == raw_published_at
    assert normalized.attempts == response.attempts
    assert normalized.diagnostics == response.diagnostics
    assert normalized.producer_lineage_bundle["items"][0]["publishedAt"] == raw_published_at
    assert normalized.producer_lineage_bundle["items"][0]["timezone"] is not None
    assert filtered.results[0].published_date == expected_date
    assert filtered.results[0].published_at == raw_published_at
    assert filtered.producer_lineage_bundle["items"][0]["publishedAt"] == raw_published_at
