# -*- coding: utf-8 -*-
"""Focused regression coverage for Market Overview evidence snapshots."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src.services.market_overview_service import MarketOverviewService


CN_TZ = timezone(timedelta(hours=8))


def _iso_now() -> str:
    return datetime.now(CN_TZ).isoformat(timespec="seconds")


class MarketOverviewEvidenceSnapshotTestCase(unittest.TestCase):
    def setUp(self) -> None:
        MarketOverviewService._market_cache.clear()
        MarketOverviewService._market_data_cache.clear()

    def test_live_panel_projects_evidence_snapshot(self) -> None:
        service = MarketOverviewService()
        as_of = _iso_now()

        with patch.object(
            service,
            "_fetch_indices",
            return_value={
                "source": "yfinance",
                "sourceLabel": "Yahoo Finance",
                "updatedAt": as_of,
                "asOf": as_of,
                "items": [
                    {
                        "symbol": "SPX",
                        "label": "S&P 500",
                        "value": 5200.12,
                        "changePercent": 0.42,
                        "trend": [5180.0, 5200.12],
                        "source": "yfinance",
                        "sourceLabel": "Yahoo Finance",
                        "updatedAt": as_of,
                        "asOf": as_of,
                    }
                ],
            },
        ):
            payload = service.get_indices()

        assert payload["evidenceSnapshot"] == {
            "source": "yfinance",
            "sourceLabel": "Yahoo Finance",
            "asOf": as_of,
            "freshness": "live",
            "isFallback": False,
            "isStale": False,
            "isPartial": False,
            "isSynthetic": False,
            "isUnavailable": False,
            "confidenceWeight": 0.7,
            "coverage": 1.0,
            "degradationReason": None,
            "capReason": None,
        }

    def test_fallback_panel_projects_evidence_snapshot(self) -> None:
        service = MarketOverviewService()

        with patch.object(service, "_fetch_cn_breadth_snapshot", side_effect=RuntimeError("provider down")):
            payload = service.get_cn_breadth()

        evidence = payload["evidenceSnapshot"]
        assert evidence["source"] == "fallback"
        assert evidence["freshness"] == "fallback"
        assert evidence["isFallback"] is True
        assert evidence["isStale"] is False
        assert evidence["isPartial"] is False
        assert evidence["isUnavailable"] is False
        assert evidence["coverage"] == 0.0
        assert evidence["confidenceWeight"] == 0.0
        assert evidence["degradationReason"] == "provider_unavailable"
        assert evidence["capReason"] == "fallback_source"

    def test_stale_panel_projects_evidence_snapshot(self) -> None:
        service = MarketOverviewService()
        as_of = (datetime.now(CN_TZ) - timedelta(days=2)).isoformat(timespec="seconds")

        with patch.object(
            service,
            "_fetch_indices",
            return_value={
                "source": "yfinance",
                "sourceLabel": "Yahoo Finance",
                "updatedAt": as_of,
                "asOf": as_of,
                "items": [
                    {
                        "symbol": "SPX",
                        "label": "S&P 500",
                        "value": 5200.12,
                        "changePercent": 0.42,
                        "trend": [5180.0, 5200.12],
                        "source": "yfinance",
                        "sourceLabel": "Yahoo Finance",
                        "updatedAt": as_of,
                        "asOf": as_of,
                    }
                ],
            },
        ):
            payload = service.get_indices()

        evidence = payload["evidenceSnapshot"]
        assert evidence["source"] == "yfinance"
        assert evidence["asOf"] == as_of
        assert evidence["freshness"] == "stale"
        assert evidence["isFallback"] is False
        assert evidence["isStale"] is True
        assert evidence["isPartial"] is False
        assert evidence["isUnavailable"] is False
        assert evidence["coverage"] == 1.0
        assert evidence["confidenceWeight"] == 0.6
        assert evidence["degradationReason"] == "stale_source"
        assert evidence["capReason"] == "stale_source"

    def test_partial_panel_projects_evidence_snapshot(self) -> None:
        service = MarketOverviewService()
        as_of = _iso_now()

        with patch.object(
            service,
            "_fetch_cn_indices_snapshot",
            return_value={
                "source": "mixed",
                "sourceLabel": "多来源",
                "updatedAt": as_of,
                "asOf": as_of,
                "fallbackUsed": True,
                "items": [
                    {
                        "name": "上证指数",
                        "symbol": "000001.SH",
                        "value": 4107.51,
                        "change": 28.88,
                        "changePercent": 0.71,
                        "sparkline": [4078.63, 4107.51],
                        "source": "sina",
                        "sourceLabel": "新浪财经",
                        "updatedAt": as_of,
                        "asOf": as_of,
                    },
                    {
                        "name": "深证成指",
                        "symbol": "399001.SZ",
                        "value": 9820.42,
                        "change": 52.18,
                        "changePercent": 0.53,
                        "sparkline": [9722.0, 9820.42],
                        "source": "fallback",
                        "sourceLabel": "备用数据",
                        "updatedAt": as_of,
                        "asOf": as_of,
                        "freshness": "fallback",
                        "isFallback": True,
                    },
                ],
            },
        ):
            payload = service.get_cn_indices()

        evidence = payload["evidenceSnapshot"]
        assert evidence["source"] == "mixed"
        assert evidence["asOf"] == as_of
        assert evidence["freshness"] == "partial"
        assert evidence["isFallback"] is False
        assert evidence["isStale"] is False
        assert evidence["isPartial"] is True
        assert evidence["isUnavailable"] is False
        assert evidence["coverage"] == 0.5
        assert evidence["confidenceWeight"] == 0.45
        assert evidence["degradationReason"] == "partial_coverage"
        assert evidence["capReason"] == "partial_coverage"

    def test_unavailable_panel_projects_evidence_snapshot(self) -> None:
        service = MarketOverviewService()

        with patch.object(service, "_latest_quote", side_effect=RuntimeError("provider down")):
            payload = service.get_us_breadth()

        evidence = payload["evidenceSnapshot"]
        assert evidence["source"] == "unavailable"
        assert evidence["freshness"] == "unavailable"
        assert evidence["isFallback"] is True
        assert evidence["isStale"] is False
        assert evidence["isPartial"] is False
        assert evidence["isUnavailable"] is True
        assert evidence["coverage"] == 0.0
        assert evidence["confidenceWeight"] == 0.0
        assert evidence["degradationReason"] == "provider_unavailable"
        assert evidence["capReason"] == "unavailable_source"
