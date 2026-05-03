# -*- coding: utf-8 -*-
"""Persistent last-known-good snapshots for market overview panels."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from src.services.market_cache import market_cache
from src.services.market_overview_service import MarketOverviewService
from src.storage import DatabaseManager


@pytest.fixture(autouse=True)
def isolated_market_overview_snapshot_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MARKET_OVERVIEW_SNAPSHOT_TEST_DB", "1")
    DatabaseManager.reset_instance()
    DatabaseManager(db_url=f"sqlite:///{tmp_path / 'market-overview.sqlite'}")
    market_cache.clear()
    MarketOverviewService._market_data_cache.clear()
    yield
    market_cache.clear()
    MarketOverviewService._market_data_cache.clear()
    DatabaseManager.reset_instance()


def _live_payload(value: float = 5120.25) -> dict:
    return {
        "source": "yahoo",
        "sourceLabel": "Yahoo Finance",
        "updatedAt": "2026-05-04T09:30:00+08:00",
        "asOf": "2026-05-04T09:30:00+08:00",
        "freshness": "live",
        "items": [
            {
                "symbol": "SPX",
                "label": "S&P 500",
                "value": value,
                "changePercent": 0.42,
                "source": "yahoo",
                "freshness": "live",
            }
        ],
    }


def test_successful_fetch_saves_persistent_snapshot() -> None:
    service = MarketOverviewService()

    payload = service._cached_payload(
        "indices",
        Mock(return_value=_live_payload()),
        Mock(return_value={"source": "fallback", "items": []}),
    )

    row = DatabaseManager.get_instance().get_market_overview_snapshot("market_overview:indices")
    assert payload["items"][0]["symbol"] == "SPX"
    assert row is not None
    assert row["payload"]["items"][0]["value"] == 5120.25
    assert row["source"] == "yahoo"
    assert row["freshness"] == "live"


def test_failed_fetch_returns_previous_snapshot_as_stale() -> None:
    service = MarketOverviewService()
    service._cached_payload(
        "indices",
        Mock(return_value=_live_payload()),
        Mock(return_value={"source": "fallback", "items": []}),
    )
    market_cache.clear()
    MarketOverviewService._market_data_cache.clear()

    payload = service._cached_payload(
        "indices",
        Mock(side_effect=RuntimeError("indices request timed out after 3 seconds with provider traceback details")),
        Mock(return_value={"source": "fallback", "items": []}),
    )

    assert payload["items"][0]["symbol"] == "SPX"
    assert payload["isStale"] is True
    assert payload["isFromSnapshot"] is True
    assert payload["freshness"] == "stale"
    assert payload["lastSuccessfulAt"] == "2026-05-04T09:30:00+08:00"
    assert "indices request timed out" in payload["refreshError"]
    assert len(payload["refreshError"]) <= 180


def test_failed_fetch_without_snapshot_returns_honest_fallback() -> None:
    service = MarketOverviewService()

    payload = service._cached_payload(
        "indices",
        Mock(side_effect=RuntimeError("indices unavailable")),
        Mock(return_value={"source": "fallback", "items": [], "freshness": "fallback", "isFallback": True}),
    )

    assert payload["items"] == []
    assert payload.get("isFromSnapshot") is not True
    assert payload["source"] == "fallback"


def test_error_only_payload_does_not_overwrite_good_snapshot() -> None:
    service = MarketOverviewService()
    service._cached_payload(
        "indices",
        Mock(return_value=_live_payload(5200.0)),
        Mock(return_value={"source": "fallback", "items": []}),
    )
    market_cache.clear()
    MarketOverviewService._market_data_cache.clear()

    service._cached_payload(
        "indices",
        Mock(return_value={"source": "error", "freshness": "error", "error": "provider down", "items": []}),
        Mock(return_value={"source": "fallback", "items": []}),
    )

    row = DatabaseManager.get_instance().get_market_overview_snapshot("market_overview:indices")
    assert row is not None
    assert row["payload"]["items"][0]["value"] == 5200.0
    assert row["source"] == "yahoo"


def test_fallback_snapshot_returned_after_failure_is_not_marked_live() -> None:
    db = DatabaseManager.get_instance()
    db.save_market_overview_snapshot(
        key="market_overview:indices",
        payload={
            **_live_payload(3000.0),
            "source": "fallback",
            "freshness": "fallback",
            "isFallback": True,
            "items": [{**_live_payload(3000.0)["items"][0], "source": "fallback", "freshness": "fallback", "isFallback": True}],
        },
    )

    payload = MarketOverviewService()._cached_payload(
        "indices",
        Mock(side_effect=RuntimeError("indices request timed out")),
        Mock(return_value={"source": "fallback", "items": []}),
    )

    assert payload["isFromSnapshot"] is True
    assert payload["isFallback"] is True
    assert payload["freshness"] != "live"
    assert payload["items"][0]["isFallback"] is True
