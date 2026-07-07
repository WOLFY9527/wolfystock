from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from src.repositories.quote_ohlcv_snapshot_repository import QuoteOhlcvSnapshotRepository
from src.services.historical_ohlcv_readiness import HistoricalOhlcvBar
from src.services.provider_capability_matrix import providers_for_domain, ProviderDomain
from src.services.quote_ohlcv_snapshot_lineage import (
    QUOTE_OHLCV_SNAPSHOT_CONTRACT_VERSION,
    QuoteOhlcvSnapshotSpine,
    SnapshotLineageError,
    build_ohlcv_snapshot_from_bar,
    build_quote_snapshot_from_readiness,
)
from src.services.quote_snapshot_readiness import QuoteSnapshot


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_quote_snapshot_contract_persists_explicit_lineage_without_provider_order_change(tmp_path) -> None:
    provider_order_before = [item.provider_id for item in providers_for_domain(ProviderDomain.QUOTE)]
    spine = QuoteOhlcvSnapshotSpine(QuoteOhlcvSnapshotRepository.sqlite(tmp_path / "snapshots.db"))

    snapshot = build_quote_snapshot_from_readiness(
        QuoteSnapshot(
            symbol="aapl",
            market="us",
            last=214.55,
            previous_close=212.2,
            volume=1_000_000,
            currency="usd",
            as_of=_dt("2026-07-06T20:00:00Z"),
            source="local_quote_snapshot_cache",
        ),
        retrieval_time=_dt("2026-07-06T20:01:00Z"),
        authority_state="advisory_only",
        display_state="limited",
        freshness_state="cached",
        coverage_state="available",
        lineage_ref="quote-cache:2026-07-06:AAPL",
    )

    result = spine.persist_snapshot(snapshot)
    loaded = spine.get_snapshot(result.snapshot_id)

    assert result.inserted is True
    assert loaded is not None
    payload = loaded.as_read_model()
    assert payload["contractVersion"] == QUOTE_OHLCV_SNAPSHOT_CONTRACT_VERSION
    assert payload["snapshotId"] == result.snapshot_id
    assert payload["symbol"] == "AAPL"
    assert payload["market"] == "US"
    assert payload["instrumentIdentity"]["canonicalSymbol"] == "AAPL"
    assert payload["quoteAsOf"] == "2026-07-06T20:00:00+00:00"
    assert payload["retrievalTime"] == "2026-07-06T20:01:00+00:00"
    assert payload["sourceId"] == "local_quote_snapshot_cache"
    assert payload["sourceType"] == "cache_snapshot"
    assert payload["authorityState"] == "advisory_only"
    assert payload["displayState"] == "limited"
    assert payload["freshnessState"] == "cached"
    assert payload["coverageState"] == "available"
    assert payload["missingFieldSummary"] == []
    assert payload["ohlcvBasis"] is None
    assert payload["lineageRef"] == "quote-cache:2026-07-06:AAPL"
    assert [item.provider_id for item in providers_for_domain(ProviderDomain.QUOTE)] == provider_order_before


def test_quote_snapshot_contract_preserves_missing_field_summary_and_latest_read(tmp_path) -> None:
    repo = QuoteOhlcvSnapshotRepository.sqlite(tmp_path / "snapshots.db")
    spine = QuoteOhlcvSnapshotSpine(repo)

    snapshot = build_quote_snapshot_from_readiness(
        QuoteSnapshot(
            symbol="AAPL",
            market="US",
            last=214.55,
            as_of=_dt("2026-07-06T20:00:00Z"),
            source="local_quote_snapshot_cache",
        ),
        retrieval_time=_dt("2026-07-06T20:01:00Z"),
        authority_state="advisory_only",
        display_state="limited",
        freshness_state="cached",
        coverage_state="partial",
        missing_field_summary=("previous_close", "volume", "currency"),
        lineage_ref="quote-cache:2026-07-06:AAPL",
    )

    spine.persist_snapshot(snapshot)
    latest = spine.latest_for_symbol(symbol="AAPL", market="US", snapshot_kind="quote")

    assert latest is not None
    assert latest.snapshot_id == snapshot.snapshot_id
    payload = latest.as_read_model()
    assert payload["coverageState"] == "partial"
    assert payload["missingFieldSummary"] == ["previous_close", "volume", "currency"]


@pytest.mark.parametrize(
    ("symbol", "market", "expected_symbol", "expected_market", "expected_venue"),
    [
        ("AAPL", "US", "AAPL", "US", "XNYS"),
        ("SH600519", "CN", "600519", "CN", "XSHG"),
        ("hk00700", "HK", "00700", "HK", "XHKG"),
    ],
)
def test_ohlcv_snapshot_contract_normalizes_cross_market_identity(
    tmp_path,
    symbol: str,
    market: str,
    expected_symbol: str,
    expected_market: str,
    expected_venue: str,
) -> None:
    spine = QuoteOhlcvSnapshotSpine(QuoteOhlcvSnapshotRepository.sqlite(tmp_path / "snapshots.db"))
    bar = HistoricalOhlcvBar(
        date=date(2026, 7, 6),
        open=10.0,
        high=11.0,
        low=9.5,
        close=10.5,
        volume=1000.0,
        adjusted_close=10.4,
    )

    snapshot = build_ohlcv_snapshot_from_bar(
        symbol=symbol,
        market=market,
        bar=bar,
        retrieval_time=_dt("2026-07-06T21:00:00Z"),
        source_id="local_ohlcv",
        authority_state="advisory_only",
        display_state="limited",
        freshness_state="fresh",
        coverage_state="available",
        lineage_ref=f"local-ohlcv:{expected_market}:{expected_symbol}:2026-07-06",
    )

    persisted = spine.persist_snapshot(snapshot)
    loaded = spine.get_snapshot(persisted.snapshot_id)

    assert loaded is not None
    payload = loaded.as_read_model()
    assert payload["symbol"] == expected_symbol
    assert payload["market"] == expected_market
    assert payload["instrumentIdentity"] == {
        "canonicalSymbol": expected_symbol,
        "market": expected_market,
        "venue": expected_venue,
    }
    assert payload["barTradeDateTime"] == "2026-07-06"
    assert payload["retrievalTime"] == "2026-07-06T21:00:00+00:00"
    assert payload["sourceId"] == "local_ohlcv"
    assert payload["sourceType"] == "cache_snapshot"
    assert payload["ohlcvBasis"] == "adjusted"
    assert payload["missingFieldSummary"] == []


@pytest.mark.parametrize(
    "missing_kwargs",
    [
        {"lineage_ref": ""},
        {"source_id": ""},
        {"authority_state": ""},
        {"freshness_state": ""},
        {"coverage_state": ""},
    ],
)
def test_snapshot_contract_fails_closed_when_required_provenance_is_missing(missing_kwargs) -> None:
    kwargs = {
        "symbol": "AAPL",
        "market": "US",
        "bar": HistoricalOhlcvBar(
            date=date(2026, 7, 6),
            open=10.0,
            high=11.0,
            low=9.5,
            close=10.5,
            volume=1000.0,
        ),
        "retrieval_time": _dt("2026-07-06T21:00:00Z"),
        "source_id": "local_ohlcv",
        "authority_state": "advisory_only",
        "display_state": "unavailable",
        "freshness_state": "fresh",
        "coverage_state": "available",
        "lineage_ref": "local-ohlcv:US:AAPL:2026-07-06",
    }
    kwargs.update(missing_kwargs)

    with pytest.raises(SnapshotLineageError):
        build_ohlcv_snapshot_from_bar(**kwargs)
