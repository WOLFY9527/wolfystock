from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from src.services.quote_snapshot_readiness import (
    QuoteSnapshot,
    QuoteSnapshotProviderResult,
    QuoteSnapshotReadinessRequest,
    QuoteSnapshotReadinessService,
)


class _FakeQuoteProvider:
    def __init__(self, snapshots=None, unavailable_reason: str = "provider_missing") -> None:
        self.snapshots = tuple(snapshots or ())
        self.unavailable_reason = unavailable_reason
        self.calls: list[QuoteSnapshotReadinessRequest] = []

    def fetch_quote_snapshots(self, request: QuoteSnapshotReadinessRequest) -> QuoteSnapshotProviderResult:
        self.calls.append(request)
        if self.snapshots:
            return QuoteSnapshotProviderResult.available(self.snapshots)
        return QuoteSnapshotProviderResult.unavailable(self.unavailable_reason)


def _snapshot(symbol: str, *, as_of: datetime | None = None, source: str = "local_cache") -> QuoteSnapshot:
    return QuoteSnapshot(
        symbol=symbol,
        market="us",
        last=100.0,
        previous_close=99.0,
        volume=1_000_000,
        as_of=as_of or datetime.now(timezone.utc),
        currency="USD",
        source=source,
    )


def test_missing_provider_fails_closed_without_network_or_mutation() -> None:
    service = QuoteSnapshotReadinessService()

    result = service.fetch(QuoteSnapshotReadinessRequest(symbols=("SPY", "QQQ"), market="us"))

    assert result.snapshots == []
    readiness = result.readiness
    assert readiness["availabilityState"] == "missing"
    assert readiness["freshnessState"] == "missing"
    assert readiness["missingSymbols"] == ["SPY", "QQQ"]
    assert readiness["availableSymbols"] == []
    assert readiness["providerState"] == "provider_missing"
    assert readiness["consumerSafe"] is True


def test_available_real_shaped_snapshots_report_available_without_raw_payload() -> None:
    provider = _FakeQuoteProvider([_snapshot("SPY"), _snapshot("QQQ")])
    service = QuoteSnapshotReadinessService(provider=provider)

    result = service.fetch(QuoteSnapshotReadinessRequest(symbols=("SPY", "QQQ"), market="us"))

    assert [item.symbol for item in result.snapshots] == ["SPY", "QQQ"]
    readiness = result.readiness
    assert readiness["availabilityState"] == "available"
    assert readiness["freshnessState"] == "available"
    assert readiness["availableSymbols"] == ["SPY", "QQQ"]
    assert readiness["missingSymbols"] == []
    assert readiness["staleSymbols"] == []
    assert readiness["sourceFamilies"] == ["local_cache"]
    serialized = json.dumps(readiness, ensure_ascii=False).lower()
    for forbidden in ("apikey", "requestid", "traceid", "cachekey", "raw", "payload", "secret"):
        assert forbidden not in serialized


def test_stale_snapshot_is_not_available_for_scanner_readiness() -> None:
    stale_as_of = datetime.now(timezone.utc) - timedelta(hours=30)
    provider = _FakeQuoteProvider([_snapshot("AAPL", as_of=stale_as_of)])
    service = QuoteSnapshotReadinessService(provider=provider)

    result = service.fetch(
        QuoteSnapshotReadinessRequest(symbols=("AAPL",), market="us", max_age_seconds=60 * 60)
    )

    readiness = result.readiness
    assert readiness["availabilityState"] == "stale"
    assert readiness["freshnessState"] == "stale"
    assert readiness["availableSymbols"] == []
    assert readiness["staleSymbols"] == ["AAPL"]
    assert readiness["missingSymbols"] == []
