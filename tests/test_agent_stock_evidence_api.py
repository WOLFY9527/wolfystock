# -*- coding: utf-8 -*-
"""Tests for lightweight Decision Desk stock evidence."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from api.v1.endpoints import agent


class AgentStockEvidenceApiTestCase(unittest.TestCase):
    def test_stock_evidence_endpoint_returns_quote_technical_and_fundamental_statuses(self) -> None:
        service = MagicMock()
        service.get_stock_evidence.return_value = {
            "symbols": ["HOOD"],
            "items": [
                {
                    "symbol": "HOOD",
                    "market": "US",
                    "quote": {"status": "available", "price": 73.67, "provider": "alpaca"},
                    "technical": {"status": "available", "ma20": 79.42, "rsi14": 43.5},
                    "fundamental": {"status": "partial", "peTtm": 35.21, "missingFields": ["marketCap"]},
                    "news": {"status": "unknown"},
                }
            ],
            "meta": {"source": "read_only_evidence_v2", "generatedAt": "2026-05-04T00:00:00Z"},
        }

        with patch("api.v1.endpoints.agent.StockEvidenceService", return_value=service):
            payload = asyncio.run(
                agent.get_stock_evidence(
                    symbols="HOOD",
                    current_user=SimpleNamespace(user_id="user-1"),
                )
            )

        self.assertEqual(payload["items"][0]["quote"]["status"], "available")
        self.assertEqual(payload["items"][0]["technical"]["status"], "available")
        self.assertEqual(payload["items"][0]["fundamental"]["status"], "partial")
        self.assertEqual(payload["items"][0]["news"]["status"], "unknown")
        self.assertEqual(service.get_stock_evidence.call_args.kwargs["symbols"], ["HOOD"])

    def test_stock_evidence_endpoint_handles_multiple_symbols_and_no_llm(self) -> None:
        service = MagicMock()
        service.get_stock_evidence.return_value = {
            "symbols": ["HOOD", "ORCL"],
            "items": [
                {
                    "symbol": "HOOD",
                    "market": "US",
                    "quote": {"status": "unknown"},
                    "technical": {"status": "missing"},
                    "fundamental": {"status": "missing"},
                    "news": {"status": "unknown"},
                },
                {
                    "symbol": "ORCL",
                    "market": "US",
                    "quote": {"status": "unknown"},
                    "technical": {"status": "missing"},
                    "fundamental": {"status": "missing"},
                    "news": {"status": "unknown"},
                },
            ],
            "meta": {"source": "read_only_evidence_v2", "generatedAt": "2026-05-04T00:00:00Z"},
        }

        with patch("api.v1.endpoints.agent.StockEvidenceService", return_value=service), \
             patch("src.agent.executor.AgentExecutor.chat", side_effect=AssertionError("LLM must not be called")):
            payload = asyncio.run(
                agent.get_stock_evidence(
                    symbols="HOOD,ORCL,NVDA,AAPL",
                    current_user=SimpleNamespace(user_id="user-1"),
                )
            )

        self.assertEqual(payload["symbols"], ["HOOD", "ORCL"])
        self.assertEqual(len(payload["items"]), 2)
        self.assertNotIn("api_key", str(payload).lower())
        self.assertNotIn("raw prompt", str(payload).lower())

    def test_stock_evidence_endpoint_returns_unknown_payload_on_service_error(self) -> None:
        service = MagicMock()
        service.get_stock_evidence.side_effect = RuntimeError("provider unavailable")

        with patch("api.v1.endpoints.agent.StockEvidenceService", return_value=service):
            payload = asyncio.run(
                agent.get_stock_evidence(
                    symbols="HOOD",
                    current_user=SimpleNamespace(user_id="user-1"),
                )
            )

        item = payload["items"][0]
        self.assertEqual(item["quote"]["status"], "error")
        self.assertEqual(item["technical"]["status"], "unknown")
        self.assertEqual(item["fundamental"]["status"], "unknown")
        self.assertEqual(item["news"]["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
