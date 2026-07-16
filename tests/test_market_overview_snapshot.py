# -*- coding: utf-8 -*-
"""Persistent last-known-good snapshots for market overview panels."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.services.market_cache import market_cache
from src.services.market_overview_service import MarketOverviewService
from src.services.market_persistence_snapshot_store import normalize_persistence_snapshot
from src.storage import DatabaseManager


CN_TZ = timezone(timedelta(hours=8))


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


def test_cached_payload_uses_stale_while_revalidate_contract() -> None:
    service = MarketOverviewService()
    cache = Mock()
    expected_payload = {"source": "fallback", "items": [], "freshness": "fallback", "isFallback": True}
    cache.get_or_refresh.return_value = expected_payload
    service._market_cache = cache

    payload = service._cached_payload(
        "indices",
        Mock(return_value=_live_payload()),
        Mock(return_value={"source": "fallback", "items": [], "freshness": "fallback", "isFallback": True}),
    )

    assert payload is expected_payload
    cache.get_or_refresh.assert_called_once()
    args, kwargs = cache.get_or_refresh.call_args
    assert args[0] == "indices"
    assert args[1] == service._ttl_for_cache_key("indices")
    assert callable(args[2])
    assert callable(kwargs["fallback_factory"])
    assert kwargs["allow_stale"] is True
    assert kwargs["background_refresh"] is True
    assert kwargs["cold_start_timeout_seconds"] == service.MARKET_COLD_START_TIMEOUT_SECONDS


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
    assert payload["source"] == "yahoo"
    assert payload["sourceLabel"] == "Yahoo Finance"
    assert payload["isStale"] is True
    assert payload["isFallback"] is False
    assert payload["isFromSnapshot"] is True
    assert payload["freshness"] == "stale"
    assert payload["items"][0]["freshness"] == "stale"
    assert payload["items"][0]["isStale"] is True
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
    assert payload["freshness"] == "fallback"
    assert payload["freshness"] != "live"
    assert payload["items"][0]["isFallback"] is True
    assert payload["items"][0]["freshness"] == "fallback"


def test_old_official_snapshot_recomputes_freshness_from_observation_time() -> None:
    observed_at = "2020-01-02T16:00:00+08:00"
    payload = {
        "snapshotId": "rates:2020-01-02",
        "lineageReference": "market_overview:rates",
        "source": "fred",
        "sourceLabel": "FRED",
        "sourceType": "official_public",
        "asOf": observed_at,
        "updatedAt": datetime.now(CN_TZ).isoformat(timespec="seconds"),
        "freshness": "delayed",
        "items": [
            {
                "symbol": "US10Y",
                "value": 1.88,
                "source": "fred",
                "sourceId": "fred:DGS10",
                "sourceType": "official_public",
                "asOf": observed_at,
                "officialObservationDate": "2020-01-02",
                "freshness": "delayed",
                "sourceAuthorityAllowed": True,
            }
        ],
    }
    saved = DatabaseManager.get_instance().save_market_overview_snapshot(
        key="market_overview:rates",
        payload=payload,
    )

    loaded = MarketOverviewService()._load_persistent_snapshot("rates")

    assert saved["as_of"] == observed_at
    assert loaded is not None
    assert loaded["snapshotId"] == "rates:2020-01-02"
    assert loaded["lineageReference"] == "market_overview:rates"
    assert loaded["asOf"] == observed_at
    assert loaded["source"] == "fred"
    assert loaded["freshness"] == "stale"
    assert loaded["isStale"] is True
    assert loaded["items"][0]["asOf"] == observed_at
    assert loaded["items"][0]["freshness"] == "stale"
    assert loaded["items"][0]["isStale"] is True
    assert loaded["items"][0]["sourceAuthorityAllowed"] is True


def test_recent_official_snapshot_stays_within_observation_age_boundary() -> None:
    observed_at = datetime.now(CN_TZ).replace(microsecond=0).isoformat()
    observation_date = datetime.now(CN_TZ).date().isoformat()
    DatabaseManager.get_instance().save_market_overview_snapshot(
        key="market_overview:rates",
        payload={
            "source": "mixed",
            "asOf": observed_at,
            "freshness": "live",
            "items": [
                {
                    "symbol": "US10Y",
                    "value": 4.25,
                    "source": "fred",
                    "sourceId": "fred:DGS10",
                    "sourceType": "official_public",
                    "asOf": observed_at,
                    "officialObservationDate": observation_date,
                    "freshness": "live",
                }
            ],
        },
    )

    loaded = MarketOverviewService()._load_persistent_snapshot("rates")

    assert loaded is not None
    assert loaded["asOf"] == observed_at
    assert loaded["freshness"] == "delayed"
    assert loaded["isStale"] is False
    assert loaded["items"][0]["freshness"] == "delayed"
    assert loaded["items"][0]["isStale"] is False


@pytest.mark.parametrize(
    ("payload_overrides", "expected_freshness", "expected_stale"),
    [
        (
            {"source": "yfinance_proxy", "sourceType": "unofficial_proxy"},
            "delayed",
            False,
        ),
        (
            {"source": "fallback", "isFallback": True, "freshness": "fallback"},
            "fallback",
            False,
        ),
        (
            {"source": "sina", "freshness": "stale", "isStale": True},
            "stale",
            True,
        ),
    ],
)
def test_snapshot_reload_preserves_proxy_fallback_and_stale_semantics(
    payload_overrides: dict,
    expected_freshness: str,
    expected_stale: bool,
) -> None:
    observed_at = datetime.now(CN_TZ).replace(microsecond=0).isoformat()
    source = payload_overrides["source"]
    payload = {
        "snapshotId": f"indices:{source}",
        "source": source,
        "asOf": observed_at,
        "freshness": "live",
        "items": [
            {
                "symbol": "SPX",
                "value": 5120.25,
                "source": source,
                "asOf": observed_at,
                "freshness": payload_overrides.get("freshness", "live"),
                "sourceType": payload_overrides.get("sourceType"),
                "isFallback": payload_overrides.get("isFallback", False),
                "sourceAuthorityAllowed": False if source == "yfinance_proxy" else None,
            }
        ],
        **payload_overrides,
    }
    DatabaseManager.get_instance().save_market_overview_snapshot(
        key="market_overview:indices",
        payload=payload,
    )

    loaded = MarketOverviewService()._load_persistent_snapshot("indices")

    assert loaded is not None
    assert loaded["snapshotId"] == f"indices:{source}"
    assert loaded["asOf"] == (None if source == "fallback" else observed_at)
    assert loaded["freshness"] == expected_freshness
    assert loaded["isStale"] is expected_stale
    assert loaded["items"][0]["freshness"] == expected_freshness
    assert loaded["items"][0]["isStale"] is expected_stale
    if source == "yfinance_proxy":
        assert loaded["items"][0]["sourceAuthorityAllowed"] is False


def test_missing_observation_time_round_trip_does_not_fabricate_as_of() -> None:
    receipt_time = datetime.now(CN_TZ).replace(microsecond=0).isoformat()
    db = DatabaseManager.get_instance()
    saved = db.save_market_overview_snapshot(
        key="market_overview:indices",
        payload={
            "snapshotId": "indices:missing-observation",
            "source": "sina",
            "updatedAt": receipt_time,
            "freshness": "live",
            "items": [
                {
                    "symbol": "000001.SH",
                    "value": 3200.0,
                    "source": "sina",
                    "updatedAt": receipt_time,
                    "freshness": "live",
                }
            ],
        },
    )

    assert saved["as_of"] is None
    assert saved["payload"].get("asOf") is None

    loaded = MarketOverviewService()._load_persistent_snapshot("indices")

    assert loaded is not None
    assert loaded["snapshotId"] == "indices:missing-observation"
    assert loaded.get("asOf") is None
    assert loaded["freshness"] == "stale"
    assert loaded["items"][0].get("asOf") is None
    assert loaded["items"][0]["freshness"] == "stale"
    assert receipt_time not in {loaded.get("asOf"), loaded["items"][0].get("asOf")}

    trend_snapshot = normalize_persistence_snapshot(
        {
            "surface": "market_overview",
            "metricKey": "000001.SH",
            "source": "sina",
            "sourceType": "public_api",
            "sourceTier": "public_api",
            "freshness": "live",
            "asOf": None,
            "updatedAt": receipt_time,
            "snapshotCreatedAt": receipt_time,
        }
    )
    assert trend_snapshot.effective_timestamp is None
    assert trend_snapshot.score_grade_eligible is False
