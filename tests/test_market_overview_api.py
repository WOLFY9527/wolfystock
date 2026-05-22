# -*- coding: utf-8 -*-
"""Contract tests for independent market overview endpoints."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from api.v1.endpoints import market_overview


class MarketOverviewApiTestCase(unittest.TestCase):
    def _service(self) -> MagicMock:
        service = MagicMock()
        service.get_indices.return_value = {
            "panel_name": "IndexTrendsCard",
            "last_refresh_at": "2026-04-29T10:00:00",
            "source": "yfinance",
            "sourceLabel": "Yahoo Finance",
            "updatedAt": "2026-04-29T10:00:05",
            "asOf": "2026-04-29T10:00:00",
            "freshness": "delayed",
            "isFallback": False,
            "status": "success",
            "items": [
                {
                    "symbol": "SPX",
                    "label": "S&P 500",
                    "value": 5200.12,
                    "change_pct": 0.42,
                    "risk_direction": "decreasing",
                    "trend": [5180.0, 5200.12],
                    "source": "yfinance",
                    "sourceLabel": "Yahoo Finance",
                    "updatedAt": "2026-04-29T10:00:05",
                    "asOf": "2026-04-29T10:00:00",
                    "freshness": "delayed",
                    "isFallback": False,
                }
            ],
            "log_session_id": "log-1",
        }
        service.get_volatility.return_value = {
            "panel_name": "VolatilityCard",
            "last_refresh_at": "2026-04-29T10:00:00",
            "status": "success",
            "items": [{"symbol": "VIX", "label": "VIX", "value": 16.2, "change_pct": -2.1, "risk_direction": "decreasing", "trend": [17.0, 16.2]}],
            "log_session_id": "log-2",
        }
        service.get_sentiment.return_value = {
            "panel_name": "MarketSentimentCard",
            "last_refresh_at": "2026-04-29T10:00:00",
            "status": "success",
            "items": [{"symbol": "FGI", "label": "CNN Fear & Greed", "value": 52, "unit": "score", "risk_direction": "neutral"}],
            "log_session_id": "log-3",
        }
        service.get_funds_flow.return_value = {
            "panel_name": "FundsFlowCard",
            "last_refresh_at": "2026-04-29T10:00:00",
            "status": "success",
            "items": [{"symbol": "ETF", "label": "ETF flow proxy", "value": 1.2, "unit": "B USD", "risk_direction": "decreasing"}],
            "log_session_id": "log-4",
        }
        service.get_macro.return_value = {
            "panel_name": "MacroIndicatorsCard",
            "last_refresh_at": "2026-04-29T10:00:00",
            "status": "success",
            "items": [{"symbol": "US10Y", "label": "10Y yield", "value": 4.2, "unit": "%", "risk_direction": "increasing"}],
            "log_session_id": "log-5",
        }
        return service

    def test_market_overview_endpoints_return_panel_contracts(self) -> None:
        service = self._service()
        with patch("api.v1.endpoints.market_overview.MarketOverviewService", return_value=service):
            indices = market_overview.get_indices()
            volatility = market_overview.get_volatility()
            sentiment = market_overview.get_sentiment()
            funds_flow = market_overview.get_funds_flow()
            macro = market_overview.get_macro()

        self.assertEqual(indices["panel_name"], "IndexTrendsCard")
        self.assertEqual(volatility["panel_name"], "VolatilityCard")
        self.assertEqual(sentiment["panel_name"], "MarketSentimentCard")
        self.assertEqual(funds_flow["panel_name"], "FundsFlowCard")
        self.assertEqual(macro["panel_name"], "MacroIndicatorsCard")
        for payload in (indices, volatility, sentiment, funds_flow, macro):
            self.assertEqual(payload["status"], "success")
            self.assertTrue(payload["last_refresh_at"])
            self.assertTrue(payload["items"])
            self.assertTrue(payload["log_session_id"])
        self.assertEqual(indices["sourceLabel"], "Yahoo Finance")
        self.assertEqual(indices["updatedAt"], "2026-04-29T10:00:05")
        self.assertEqual(indices["asOf"], "2026-04-29T10:00:00")
        self.assertEqual(indices["freshness"], "delayed")
        self.assertFalse(indices["isFallback"])
        self.assertEqual(indices["items"][0]["sourceLabel"], "Yahoo Finance")
        self.assertEqual(indices["items"][0]["updatedAt"], "2026-04-29T10:00:05")
        self.assertEqual(indices["items"][0]["asOf"], "2026-04-29T10:00:00")
        self.assertEqual(indices["items"][0]["freshness"], "delayed")
        self.assertFalse(indices["items"][0]["isFallback"])


if __name__ == "__main__":
    unittest.main()
