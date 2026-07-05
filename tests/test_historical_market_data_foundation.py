from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from src.repositories.historical_market_data_repo import HistoricalMarketDataRepository
from src.services.historical_market_data_foundation import (
    HistoricalBarQualityOutcome,
    HistoricalMarketDataFoundation,
    normalize_provider_historical_bars,
)


RAW_YFINANCE_FIXTURE = {
    "provider": "yfinance",
    "market": "US",
    "symbol": "aapl",
    "interval": "1d",
    "currency": "USD",
    "adjusted": True,
    "observedAt": "2026-01-07T21:05:00Z",
    "asOf": "2026-01-07T21:05:00Z",
    "rows": [
        {
            "Date": "2026-01-05",
            "Open": 100.0,
            "High": 102.0,
            "Low": 99.5,
            "Close": 101.0,
            "Volume": 1000,
            "Adj Close": 101.0,
        },
        {
            "Date": "2026-01-06",
            "Open": 101.0,
            "High": 103.0,
            "Low": 100.0,
            "Close": 102.0,
            "Volume": 1100,
            "Adj Close": 102.0,
        },
        {
            "Date": "2026-01-07",
            "Open": 102.0,
            "High": 104.0,
            "Low": 101.0,
            "Close": 103.0,
            "Volume": 1200,
            "Adj Close": 103.0,
        },
    ],
}


def _foundation(tmp_path) -> HistoricalMarketDataFoundation:
    return HistoricalMarketDataFoundation(
        repository=HistoricalMarketDataRepository.sqlite(tmp_path / "history.db")
    )


def test_vertical_fixture_ingests_canonicalizes_persists_and_reads_provenance(tmp_path) -> None:
    foundation = _foundation(tmp_path)

    result = foundation.ingest_provider_payload(RAW_YFINANCE_FIXTURE)
    retry = foundation.ingest_provider_payload(RAW_YFINANCE_FIXTURE)

    assert result.quality.state == "usable"
    assert result.quality.reason_codes == []
    assert result.persisted.inserted == 3
    assert result.persisted.updated == 0
    assert result.persisted.conflicts == 0
    assert retry.persisted.inserted == 0
    assert retry.persisted.updated == 0
    assert retry.persisted.duplicates == 3

    bars = foundation.query_bars(symbol="AAPL", market="US", interval="1d", start=date(2026, 1, 5), end=date(2026, 1, 7))
    assert [bar.session_date.isoformat() for bar in bars] == ["2026-01-05", "2026-01-06", "2026-01-07"]
    assert bars[0].canonical_symbol == "AAPL"
    assert bars[0].market == "US"
    assert bars[0].venue == "XNYS"
    assert bars[0].timezone == "America/New_York"
    assert bars[0].interval == "1d"
    assert bars[0].adjustment_status == "adjusted"
    assert bars[0].currency == "USD"
    assert bars[0].provider == "yfinance"
    assert bars[0].normalization_version
    assert bars[0].lineage_id
    assert bars[0].as_of == datetime(2026, 1, 7, 21, 5, tzinfo=timezone.utc)

    latest = foundation.latest_bar(symbol="AAPL", market="US", interval="1d")
    assert latest is not None
    assert latest.session_date == date(2026, 1, 7)

    coverage = foundation.coverage_range(symbol="AAPL", market="US", interval="1d")
    assert coverage == {"start": "2026-01-05", "end": "2026-01-07", "barCount": 3}

    freshness = foundation.freshness_summary(symbol="AAPL", market="US", interval="1d")
    assert freshness["freshnessState"] == "fresh"
    assert freshness["qualityState"] == "usable"
    assert freshness["asOf"] == "2026-01-07T21:05:00+00:00"
    assert freshness["coveredDateRange"] == {"start": "2026-01-05", "end": "2026-01-07"}

    provenance = foundation.provenance_summary(symbol="AAPL", market="US", interval="1d")
    assert provenance["provider"] == "yfinance"
    assert provenance["market"] == "US"
    assert provenance["canonicalSymbol"] == "AAPL"
    assert provenance["normalizationVersion"] == bars[0].normalization_version
    assert provenance["sourceObservationRange"] == {"start": "2026-01-05", "end": "2026-01-07"}
    assert provenance["qualityState"] == "usable"


def test_symbol_and_time_normalization_use_repository_market_identity() -> None:
    bars = normalize_provider_historical_bars(
        {
            "provider": "akshare_cn_daily",
            "market": "cn",
            "symbol": "SH600519",
            "interval": "daily",
            "observedAt": "2026-01-08T16:00:00+08:00",
            "rows": [
                {"日期": "2026-01-08", "开盘": 10, "最高": 11, "最低": 9, "收盘": 10.5, "成交量": 100}
            ],
        }
    )

    assert len(bars) == 1
    bar = bars[0]
    assert bar.canonical_symbol == "600519"
    assert bar.market == "CN"
    assert bar.venue == "XSHG"
    assert bar.timezone == "Asia/Shanghai"
    assert bar.interval == "1d"
    assert bar.session_date == date(2026, 1, 8)
    assert bar.timestamp is None
    assert bar.observed_at == datetime(2026, 1, 8, 8, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("rows", "reason_code"),
    [
        (
            [
                {"Date": "2026-01-06", "Open": 10, "High": 11, "Low": 9, "Close": 10, "Volume": 1},
                {"Date": "2026-01-05", "Open": 10, "High": 11, "Low": 9, "Close": 10, "Volume": 1},
            ],
            "non_monotonic_ordering",
        ),
        (
            [{"Date": "2026-01-05", "Open": 10, "High": 9, "Low": 8, "Close": 10, "Volume": 1}],
            "invalid_ohlc_relationship",
        ),
        (
            [{"Date": "2026-01-05", "Open": 10, "High": 11, "Low": 9, "Close": 10, "Volume": -1}],
            "negative_volume",
        ),
        (
            [{"Date": "not-a-date", "Open": 10, "High": 11, "Low": 9, "Close": 10, "Volume": 1}],
            "malformed_timestamp",
        ),
    ],
)
def test_quality_rejects_unusable_payloads(rows, reason_code) -> None:
    outcome = HistoricalBarQualityOutcome.evaluate(
        normalize_provider_historical_bars(
            {
                "provider": "unit_fixture",
                "market": "US",
                "symbol": "AAPL",
                "interval": "1d",
                "observedAt": "2026-01-07T21:05:00Z",
                "rows": rows,
            },
            preserve_provider_order=True,
        )
    )

    assert outcome.state == "rejected"
    assert reason_code in outcome.reason_codes
    assert outcome.product_readable is False


def test_quality_degrades_but_does_not_fabricate_missing_sessions() -> None:
    bars = normalize_provider_historical_bars(
        {
            "provider": "unit_fixture",
            "market": "US",
            "symbol": "AAPL",
            "interval": "1d",
            "observedAt": "2026-01-07T21:05:00Z",
            "rows": [
                {"Date": "2026-01-05", "Open": 10, "High": 11, "Low": 9, "Close": 10, "Volume": 1},
                {"Date": "2026-01-07", "Open": 10, "High": 11, "Low": 9, "Close": 10, "Volume": 1},
            ],
        }
    )

    outcome = HistoricalBarQualityOutcome.evaluate(bars)

    assert outcome.state == "degraded"
    assert "missing_session_gap" in outcome.reason_codes
    assert outcome.product_readable is True
    assert [bar.session_date.isoformat() for bar in bars] == ["2026-01-05", "2026-01-07"]


def test_conflicting_duplicate_is_rejected_and_not_persisted(tmp_path) -> None:
    foundation = _foundation(tmp_path)
    payload = {
        "provider": "unit_fixture",
        "market": "US",
        "symbol": "AAPL",
        "interval": "1d",
        "observedAt": "2026-01-07T21:05:00Z",
        "rows": [
            {"Date": "2026-01-05", "Open": 10, "High": 11, "Low": 9, "Close": 10, "Volume": 1},
            {"Date": "2026-01-05", "Open": 99, "High": 101, "Low": 98, "Close": 100, "Volume": 2},
        ],
    }

    result = foundation.ingest_provider_payload(payload)

    assert result.quality.state == "rejected"
    assert "conflicting_duplicate_bar" in result.quality.reason_codes
    assert result.persisted.inserted == 0
    assert foundation.query_bars(symbol="AAPL", market="US", interval="1d", start=date(2026, 1, 5), end=date(2026, 1, 5)) == []


def test_repository_conflict_policy_preserves_existing_canonical_bar(tmp_path) -> None:
    foundation = _foundation(tmp_path)
    foundation.ingest_provider_payload(RAW_YFINANCE_FIXTURE)

    changed = dict(RAW_YFINANCE_FIXTURE)
    changed["rows"] = [
        {
            "Date": "2026-01-05",
            "Open": 100.0,
            "High": 999.0,
            "Low": 99.5,
            "Close": 101.0,
            "Volume": 1000,
            "Adj Close": 101.0,
        }
    ]
    result = foundation.ingest_provider_payload(changed)

    assert result.quality.state == "rejected"
    assert result.persisted.conflicts == 1
    existing = foundation.query_bars(symbol="AAPL", market="US", interval="1d", start=date(2026, 1, 5), end=date(2026, 1, 5))
    assert len(existing) == 1
    assert existing[0].high == 102.0


def test_migration_upgrade_creates_required_tables_and_indexes(tmp_path) -> None:
    repo = HistoricalMarketDataRepository.sqlite(tmp_path / "migration.db")

    report = repo.migration_report()

    assert report["schemaVersion"] == "historical_market_data_foundation_v1"
    assert report["tables"]["historical_bars"] == "present"
    assert report["indexes"]["uix_historical_bars_natural_key"] == "present"
    assert report["rollback"] == {
        "supported": True,
        "strategy": "drop historical_bar_quality_runs then historical_bars before production backfill",
    }
