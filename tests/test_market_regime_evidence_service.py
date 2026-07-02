from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.services.market_regime_evidence_service import (
    DEFAULT_MARKET_REGIME_SYMBOLS,
    build_market_regime_evidence_pack,
)


START_DATE = date(2026, 1, 2)
SYMBOLS = list(DEFAULT_MARKET_REGIME_SYMBOLS)


def _series(start: float, step: float, bars: int = 60) -> list[float]:
    return [round(start + (index * step), 4) for index in range(bars)]


def _write_ohlcv(
    cache_dir: Path,
    values_by_symbol: dict[str, list[float]],
    *,
    adjusted_symbols: Iterable[str] | None = None,
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    adjusted_set = set(adjusted_symbols if adjusted_symbols is not None else values_by_symbol)
    for symbol, closes in values_by_symbol.items():
        rows = []
        for index, close in enumerate(closes):
            row = {
                "date": (START_DATE + timedelta(days=index)).isoformat(),
                "open": close - 0.5,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 1_000_000 + index,
            }
            if symbol in adjusted_set:
                row["adjusted_close"] = close
            rows.append(row)
        pd.DataFrame(rows).to_parquet(cache_dir / f"{symbol}.parquet", index=False)


def _write_quote_cache(cache_path: Path, symbols: Iterable[str]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "symbol": symbol,
            "market": "us",
            "last": 100.0 + index,
            "previousClose": 99.5 + index,
            "volume": 1_000_000 + index,
            "asOf": datetime.now(timezone.utc).isoformat(),
            "currency": "USD",
            "source": "local_quote_snapshot_cache",
        }
        for index, symbol in enumerate(symbols)
    ]
    cache_path.write_text(json.dumps({"quotes": rows}), encoding="utf-8")


def _full_values() -> dict[str, list[float]]:
    return {
        "SPY": _series(100, 1.0),
        "QQQ": _series(100, 1.25),
        "AAPL": _series(90, 0.9),
        "MSFT": _series(95, 1.1),
        "NVDA": _series(110, 1.4),
        "TSLA": _series(80, 0.7),
    }


def _build_pack(
    tmp_path: Path,
    *,
    values_by_symbol: dict[str, list[float]] | None = None,
    adjusted_symbols: Iterable[str] | None = None,
    quote_symbols: Iterable[str] | None = SYMBOLS,
    requested_symbols: Iterable[str] = SYMBOLS,
    quote_required: bool = True,
) -> dict:
    ohlcv_dir = tmp_path / "us-parquet-cache"
    quote_path = tmp_path / "quote-snapshot-cache" / "us-starter-quotes.json"
    _write_ohlcv(
        ohlcv_dir,
        values_by_symbol or _full_values(),
        adjusted_symbols=adjusted_symbols,
    )
    if quote_symbols is not None:
        _write_quote_cache(quote_path, quote_symbols)
    return build_market_regime_evidence_pack(
        market="US",
        symbols=list(requested_symbols),
        benchmark_symbol="SPY",
        growth_proxy_symbol="QQQ",
        required_bars=60,
        ohlcv_cache_dir=ohlcv_dir,
        quote_snapshot_cache_path=quote_path if quote_required else None,
        require_adjusted=True,
    )


def test_full_adjusted_ohlcv_and_quote_snapshot_returns_ok_risk_on_confirming(tmp_path: Path) -> None:
    pack = _build_pack(tmp_path)

    assert pack["consumerSafe"] is True
    assert pack["contractVersion"] == "market_regime_evidence_pack_v1"
    assert pack["status"] == "ready"
    assert pack["readiness"] == "ready"
    assert pack["market"] == "US"
    assert pack["tier"] == "tier1"
    assert pack["universe"] == {"market": "US", "tier": "tier1", "symbols": SYMBOLS}
    assert pack["evaluatedSymbols"] == SYMBOLS
    assert pack["generatedAt"]
    assert pack["asOf"] == pack["evidence"]["indexTrend"]["usableRange"]["end"]
    assert pack["noAdviceDisclosure"]
    assert pack["availableDataClasses"] == [
        "historical_ohlcv",
        "adjusted_prices",
        "benchmark_trend",
        "growth_risk_proxy",
        "breadth_proxy",
        "volatility_proxy",
        "quote_snapshot",
    ]
    assert pack["missingDataFamilies"] == []
    assert pack["blockedProductSurfaces"] == []
    assert pack["regimeSummary"]["label"] == "risk_on"
    assert pack["regimeSummary"]["status"] == "ready"
    assert 0.0 < pack["regimeSummary"]["confidence"] <= 1.0
    assert pack["regimeSummary"]["explanation"]
    assert pack["benchmarkEvidence"]["symbol"] == "SPY"
    assert pack["benchmarkEvidence"]["return20d"] > 0
    assert pack["benchmarkEvidence"]["closeVsMa20"] == "above"
    assert pack["evidence"]["indexTrend"]["symbol"] == "SPY"
    assert pack["evidence"]["momentum"]["shortWindowReturn"] == pack["benchmarkEvidence"]["return20d"]
    assert pack["evidence"]["momentum"]["mediumWindowReturn"] == pack["benchmarkEvidence"]["return60d"]
    assert pack["evidence"]["breadth"]["aboveMovingAverageCount"] == len(SYMBOLS)
    assert pack["evidence"]["volatilityRisk"]["realizedVolatility20d"] is not None
    assert pack["evidence"]["concentrationLeadership"]["state"] in {"leaders_ahead", "leaders_inline", "leaders_lagging"}
    assert pack["evidence"]["dataCoverage"]["usedSymbols"] == SYMBOLS
    assert pack["evidence"]["dataCoverage"]["skippedSymbols"] == []
    assert pack["evidence"]["growthRiskProxy"]["relativeReturn20d"] >= 0
    assert pack["evidence"]["breadthProxy"]["percentAboveMa20"] == 1.0
    assert pack["quoteSnapshotEvidence"]["availableSymbols"] == SYMBOLS


def test_ohlcv_present_but_adjusted_missing_blocks_confident_regime(tmp_path: Path) -> None:
    pack = _build_pack(tmp_path, adjusted_symbols=[])

    assert pack["status"] == "partial"
    assert "adjusted_prices" in pack["missingDataFamilies"]
    assert pack["regimeSummary"]["label"] == "insufficient_data"
    assert pack["benchmarkEvidence"]["adjustedClose"] is None
    assert set(pack["dataQuality"]["missingAdjustedData"]) == set(SYMBOLS)


def test_benchmark_below_moving_average_and_weak_breadth_returns_risk_off(tmp_path: Path) -> None:
    values = {
        "SPY": _series(160, -1.0),
        "QQQ": _series(160, -1.2),
        "AAPL": _series(150, -0.8),
        "MSFT": _series(155, -0.9),
        "NVDA": _series(170, -1.4),
        "TSLA": _series(140, -1.1),
    }

    pack = _build_pack(tmp_path, values_by_symbol=values)

    assert pack["status"] == "ready"
    assert pack["regimeSummary"]["label"] == "risk_off"
    assert pack["benchmarkEvidence"]["return20d"] < 0
    assert pack["benchmarkEvidence"]["closeVsMa20"] == "below"
    assert pack["evidence"]["breadthProxy"]["percentAboveMa20"] == 0.0


def test_mixed_benchmark_breadth_and_relative_strength_returns_mixed(tmp_path: Path) -> None:
    values = {
        "SPY": _series(100, 1.0),
        "QQQ": _series(100, 0.2),
        "AAPL": _series(150, -0.7),
        "MSFT": _series(95, 0.7),
        "NVDA": _series(125, -0.3),
        "TSLA": _series(85, 0.4),
    }

    pack = _build_pack(tmp_path, values_by_symbol=values)

    assert pack["status"] == "ready"
    assert pack["regimeSummary"]["label"] == "mixed"
    assert pack["benchmarkEvidence"]["return20d"] > 0
    assert pack["evidence"]["growthRiskProxy"]["relativeReturn20d"] < 0


def test_quote_snapshot_missing_when_quote_path_required_reports_quote_snapshot(tmp_path: Path) -> None:
    pack = _build_pack(tmp_path, quote_symbols=["SPY", "QQQ", "MSFT", "NVDA", "TSLA"])

    assert pack["status"] == "partial"
    assert "quote_snapshot" in pack["missingDataFamilies"]
    assert pack["regimeSummary"]["label"] == "insufficient_data"
    assert pack["quoteSnapshotEvidence"]["missingSymbols"] == ["AAPL"]
    assert pack["dataQuality"]["missingQuoteSnapshot"] == ["AAPL"]


def test_quote_snapshot_path_is_optional_and_not_required_for_status_ok(tmp_path: Path) -> None:
    pack = _build_pack(tmp_path, quote_symbols=None, quote_required=False)

    assert pack["status"] == "ready"
    assert "quote_snapshot" not in pack["missingDataFamilies"]
    assert "quote_snapshot" not in pack["availableDataClasses"]
    assert pack["quoteSnapshotEvidence"]["availabilityState"] == "not_requested"
    assert pack["quoteSnapshotEvidence"]["missingSymbols"] == []


def test_missing_parquet_file_fails_safely_without_raw_stack_trace(tmp_path: Path) -> None:
    values = _full_values()
    values.pop("AAPL")

    pack = _build_pack(tmp_path, values_by_symbol=values)

    assert pack["status"] == "blocked"
    assert "historical_ohlcv" in pack["missingDataFamilies"]
    assert pack["symbolEvidence"]["AAPL"]["coverage"]["state"] == "missing"
    assert pack["evidence"]["dataCoverage"]["skippedSymbols"] == [
        {"symbol": "AAPL", "reason": "missing"}
    ]
    serialized = json.dumps(pack, ensure_ascii=False).lower()
    for forbidden in ("traceback", "exception", "filenotfounderror", "rawpayload"):
        assert forbidden not in serialized


def test_requested_symbol_outside_explicit_universe_fails_closed(tmp_path: Path) -> None:
    ohlcv_dir = tmp_path / "us-parquet-cache"
    quote_path = tmp_path / "quote-snapshot-cache" / "us-starter-quotes.json"
    _write_ohlcv(ohlcv_dir, _full_values())
    _write_quote_cache(quote_path, SYMBOLS)

    pack = build_market_regime_evidence_pack(
        market="US",
        symbols=["SPY", "QQQ", "AAPL", "ORCL"],
        benchmark_symbol="SPY",
        growth_proxy_symbol="QQQ",
        required_bars=60,
        ohlcv_cache_dir=ohlcv_dir,
        quote_snapshot_cache_path=quote_path,
        require_adjusted=True,
        explicit_universe=SYMBOLS,
    )

    assert pack["status"] == "failed_closed"
    assert pack["regimeSummary"]["label"] == "insufficient_data"
    assert pack["missingDataFamilies"] == ["invalid_symbols"]
    assert pack["dataQuality"]["failClosedReasons"] == ["symbol_outside_explicit_universe"]


def test_consumer_safe_output_contains_no_trading_advice_terms(tmp_path: Path) -> None:
    pack = _build_pack(tmp_path)

    serialized = json.dumps(pack, ensure_ascii=False).lower()
    for forbidden in ("buy", "sell", "hold", "recommendation", "target price", "stop loss"):
        assert forbidden not in serialized


def test_evidence_generation_does_not_write_cache_or_enable_provider_calls(tmp_path: Path, monkeypatch) -> None:
    ohlcv_dir = tmp_path / "us-parquet-cache"
    quote_path = tmp_path / "quote-snapshot-cache" / "us-starter-quotes.json"
    _write_ohlcv(ohlcv_dir, _full_values())
    _write_quote_cache(quote_path, SYMBOLS)

    def forbidden_to_parquet(*_args, **_kwargs):
        raise AssertionError("evidence generation must not write parquet")

    def forbidden_write_text(*_args, **_kwargs):
        raise AssertionError("evidence generation must not write files")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", forbidden_to_parquet)
    monkeypatch.setattr(Path, "write_text", forbidden_write_text)

    pack = build_market_regime_evidence_pack(
        market="US",
        symbols=SYMBOLS,
        benchmark_symbol="SPY",
        growth_proxy_symbol="QQQ",
        required_bars=60,
        ohlcv_cache_dir=ohlcv_dir,
        quote_snapshot_cache_path=quote_path,
        require_adjusted=True,
    )

    assert pack["status"] == "ready"
    assert pack["providerCallsEnabled"] is False
    assert pack["networkCallsEnabled"] is False
    assert pack["mutationEnabled"] is False


def test_malformed_ohlcv_fails_closed_without_computed_claims(tmp_path: Path) -> None:
    ohlcv_dir = tmp_path / "us-parquet-cache"
    quote_path = tmp_path / "quote-snapshot-cache" / "us-starter-quotes.json"
    _write_ohlcv(ohlcv_dir, _full_values())
    pd.DataFrame([{"date": START_DATE.isoformat(), "close": "not-a-number"}]).to_parquet(
        ohlcv_dir / "AAPL.parquet",
        index=False,
    )
    _write_quote_cache(quote_path, SYMBOLS)

    pack = build_market_regime_evidence_pack(
        market="US",
        symbols=SYMBOLS,
        benchmark_symbol="SPY",
        growth_proxy_symbol="QQQ",
        required_bars=60,
        ohlcv_cache_dir=ohlcv_dir,
        quote_snapshot_cache_path=quote_path,
        require_adjusted=True,
    )

    assert pack["status"] == "failed_closed"
    assert pack["regimeSummary"]["label"] == "insufficient_data"
    assert "malformed_ohlcv" in pack["missingDataFamilies"]
    assert pack["symbolEvidence"]["AAPL"]["coverage"]["state"] == "malformed"
    assert pack["evidence"]["dataCoverage"]["skippedSymbols"] == [
        {"symbol": "AAPL", "reason": "malformed"}
    ]
    assert pack["evidence"]["indexTrend"]["return20d"] is None
    serialized = json.dumps(pack, ensure_ascii=False).lower()
    for forbidden in ("traceback", "exception", "rawpayload", str(ohlcv_dir).lower()):
        assert forbidden not in serialized
