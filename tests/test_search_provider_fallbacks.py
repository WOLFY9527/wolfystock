# -*- coding: utf-8 -*-
"""Tests for Finnhub/GNews provider integration and dimension fallback."""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

if "newspaper" not in sys.modules:
    mock_np = MagicMock()
    mock_np.Article = MagicMock()
    mock_np.Config = MagicMock()
    sys.modules["newspaper"] = mock_np

from src.search_service import (
    SearchResponse,
    SearchResult,
    SearchService,
    TavilySearchProvider,
    fetch_url_content,
    reset_url_content_cache,
)


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class SearchProviderFallbacksTestCase(unittest.TestCase):
    def setUp(self) -> None:
        reset_url_content_cache()

    @patch("src.search_service.Article")
    def test_fetch_url_content_reuses_cached_body_for_same_url(self, mock_article) -> None:
        article = MagicMock()
        article.text = "第一行\n第二行"
        mock_article.return_value = article

        url = "https://example.com/news/1"
        first = fetch_url_content(url, article_factory=mock_article)
        second = fetch_url_content(url, article_factory=mock_article)

        self.assertEqual(first, second)
        self.assertTrue(first)
        self.assertEqual(mock_article.call_count, 1)
        article.download.assert_called_once()
        article.parse.assert_called_once()

    @patch("src.search_service.Article")
    def test_fetch_url_content_caches_failure_for_repeat_url(self, mock_article) -> None:
        article = MagicMock()
        article.download.side_effect = RuntimeError("network down")
        mock_article.return_value = article

        url = "https://example.com/news/fail"
        first = fetch_url_content(url, article_factory=mock_article)
        second = fetch_url_content(url, article_factory=mock_article)

        self.assertEqual(first, "")
        self.assertEqual(second, "")
        self.assertEqual(mock_article.call_count, 1)
        article.download.assert_called_once()

    @patch("src.search_service.requests.get")
    def test_search_stock_news_uses_finnhub_company_news(self, mock_get) -> None:
        published_at = datetime.now(timezone.utc) - timedelta(hours=6)
        published_ts = int(published_at.timestamp())
        mock_get.return_value = _FakeResponse(
            [
                {
                    "headline": "NVIDIA raises guidance",
                    "summary": "Company updated revenue outlook.",
                    "url": "https://example.com/nvda-guidance",
                    "source": "Reuters",
                    "datetime": published_ts,
                }
            ]
        )
        service = SearchService(
            finnhub_keys=["fh-key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short",
            http_transport=mock_get,
        )

        resp = service.search_stock_news("NVDA", "NVIDIA", max_results=2)
        self.assertTrue(resp.success)
        self.assertEqual(resp.provider, "Finnhub")
        self.assertEqual(len(resp.results), 1)
        self.assertEqual(
            resp.results[0].published_date,
            service._normalize_news_publish_date(published_ts).isoformat(),
        )

    @patch("src.search_service.requests.get")
    def test_uat_no_live_providers_blocks_search_news_before_http(self, mock_get) -> None:
        service = SearchService(
            finnhub_keys=["fh-key"],
            gnews_keys=["gnews-key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short",
        )

        with patch.dict(os.environ, {"WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS": "true"}, clear=False):
            resp = service.search_stock_news("NVDA", "NVIDIA", max_results=2)

        self.assertFalse(resp.success)
        self.assertIn("uat_no_live_providers", resp.error_message or "")
        mock_get.assert_not_called()

    def test_uat_no_live_providers_blocks_tavily_topic_route_before_client_import(self) -> None:
        provider = TavilySearchProvider(["tv-key"])

        with patch.dict(os.environ, {"WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS": "true"}, clear=False):
            resp = provider.search("AAPL news", max_results=2, topic="news")

        self.assertFalse(resp.success)
        self.assertEqual(resp.error_message, "uat_no_live_providers")
        self.assertEqual(resp.diagnostics["blocked_by_uat"], 1)

    @patch("src.search_service.requests.get")
    def test_search_stock_news_falls_back_from_finnhub_to_gnews(self, mock_get) -> None:
        published_at = (datetime.now(timezone.utc) - timedelta(hours=3)).replace(microsecond=0)

        def _side_effect(url, params=None, headers=None, timeout=10):
            if "finnhub.io" in url:
                return _FakeResponse([])
            if "gnews.io" in url:
                return _FakeResponse(
                    {
                        "articles": [
                            {
                                "title": "Oracle signs major cloud deal",
                                "description": "New enterprise cloud order announced.",
                                "url": "https://example.com/orcl-cloud",
                                "publishedAt": published_at.isoformat().replace("+00:00", "Z"),
                                "source": {"name": "GNewsSource"},
                            }
                        ]
                    }
                )
            raise AssertionError(f"Unexpected URL: {url}")

        mock_get.side_effect = _side_effect
        service = SearchService(
            finnhub_keys=["fh-key"],
            gnews_keys=["gnews-key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short",
            http_transport=mock_get,
        )

        resp = service.search_stock_news("ORCL", "Oracle", max_results=2)
        self.assertTrue(resp.success)
        self.assertEqual(resp.provider, "GNews")
        self.assertEqual(len(resp.results), 1)
        self.assertEqual(
            resp.results[0].published_date,
            service._normalize_news_publish_date(published_at.isoformat().replace("+00:00", "Z")).isoformat(),
        )

    def test_search_comprehensive_intel_tries_next_provider_for_dimension(self) -> None:
        service = SearchService(searxng_public_instances_enabled=False)
        p1 = SimpleNamespace(
            is_available=True,
            name="P1",
            search_news=MagicMock(
                return_value=SearchResponse(
                    query="q1",
                    results=[],
                    provider="P1",
                    success=False,
                    error_message="boom",
                )
            ),
        )
        p2 = SimpleNamespace(
            is_available=True,
            name="P2",
            search_news=MagicMock(
                return_value=SearchResponse(
                    query="q2",
                    results=[
                        SearchResult(
                            title="Oracle coverage",
                            snippet="Fresh item",
                            url="https://example.com/orcl",
                            source="example.com",
                            published_date="2026-03-27",
                        )
                    ],
                    provider="P2",
                    success=True,
                )
            ),
        )
        service._providers = [p1, p2]

        intel = service.search_comprehensive_intel("ORCL", "Oracle", max_searches=1)
        self.assertIn("latest_news", intel)
        self.assertEqual(intel["latest_news"].provider, "P2")
        p1.search_news.assert_called_once()
        p2.search_news.assert_called_once()


if __name__ == "__main__":
    unittest.main()
