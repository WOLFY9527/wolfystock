from __future__ import annotations

import json
from datetime import datetime, timezone

from src.services.local_quote_snapshot_provider import LocalQuoteSnapshotJsonProvider
from src.services.quote_snapshot_readiness import QuoteSnapshotReadinessRequest


def test_local_quote_snapshot_provider_reads_json_rows_without_mutation(tmp_path) -> None:
    cache_path = tmp_path / "quotes.json"
    cache_path.write_text(
        json.dumps(
            {
                "quotes": [
                    {
                        "symbol": "SPY",
                        "market": "us",
                        "last": 500.25,
                        "previousClose": 498.0,
                        "volume": 123456,
                        "asOf": datetime.now(timezone.utc).isoformat(),
                        "currency": "USD",
                        "source": "operator_cache",
                        "rawPayload": {"token": "secret"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    provider = LocalQuoteSnapshotJsonProvider(cache_path=cache_path)

    result = provider.fetch_quote_snapshots(QuoteSnapshotReadinessRequest(symbols=("SPY", "AAPL"), market="us"))

    assert [snapshot.symbol for snapshot in result.snapshots] == ["SPY"]
    assert result.unavailable_reason is None
    assert not hasattr(provider, "save")


def test_local_quote_snapshot_provider_missing_path_fails_closed(tmp_path) -> None:
    provider = LocalQuoteSnapshotJsonProvider(cache_path=tmp_path / "missing.json")

    result = provider.fetch_quote_snapshots(QuoteSnapshotReadinessRequest(symbols=("SPY",), market="us"))

    assert result.snapshots == ()
    assert result.unavailable_reason == "provider_missing"
