from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.services.market_regime_read_model_service import build_market_regime_read_model


START_DATE = date(2026, 1, 2)
SYMBOLS = ["SPY", "QQQ", "AAPL", "MSFT"]
FORBIDDEN_TEXT = (
    "buy",
    "sell",
    "hold",
    "recommendation",
    "target price",
    "stop loss",
    "enter",
    "exit",
    "accumulate",
    "reduce",
    "long",
    "short",
)


def _series(start: float, step: float, bars: int = 60) -> list[float]:
    return [round(start + (index * step), 4) for index in range(bars)]


def _full_values() -> dict[str, list[float]]:
    return {
        "SPY": _series(100, 1.0),
        "QQQ": _series(100, 1.25),
        "AAPL": _series(90, 0.9),
        "MSFT": _series(95, 1.1),
    }


def _risk_off_values() -> dict[str, list[float]]:
    return {
        "SPY": _series(160, -1.0),
        "QQQ": _series(160, -1.2),
        "AAPL": _series(150, -0.8),
        "MSFT": _series(155, -0.9),
    }


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


def _write_stale_quote_cache(cache_path: Path, symbols: Iterable[str]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "symbol": symbol,
            "market": "us",
            "last": 100.0 + index,
            "previousClose": 99.5 + index,
            "volume": 1_000_000 + index,
            "asOf": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
            "currency": "USD",
            "source": "local_quote_snapshot_cache",
        }
        for index, symbol in enumerate(symbols)
    ]
    cache_path.write_text(json.dumps({"quotes": rows}), encoding="utf-8")


def _build_model(
    tmp_path: Path,
    *,
    values_by_symbol: dict[str, list[float]] | None = None,
    adjusted_symbols: Iterable[str] | None = None,
    quote_symbols: Iterable[str] | None = SYMBOLS,
    quote_required: bool = True,
    ohlcv_cache_dir: Path | None = None,
    quote_cache_path: Path | None = None,
) -> dict:
    ohlcv_dir = ohlcv_cache_dir or tmp_path / "us-parquet-cache"
    quote_path = quote_cache_path or tmp_path / "quote-snapshot-cache" / "us-starter-quotes.json"
    if values_by_symbol is not None or ohlcv_cache_dir is None:
        _write_ohlcv(
            ohlcv_dir,
            values_by_symbol or _full_values(),
            adjusted_symbols=adjusted_symbols,
        )
    if quote_symbols is not None:
        _write_quote_cache(quote_path, quote_symbols)
    return build_market_regime_read_model(
        market="US",
        symbols=SYMBOLS,
        benchmark_symbol="SPY",
        growth_proxy_symbol="QQQ",
        required_bars=60,
        ohlcv_cache_dir=ohlcv_dir,
        quote_snapshot_cache_path=quote_path if quote_required else None,
        require_adjusted=True,
    )


def _card_by_id(model: dict, card_id: str) -> dict:
    return {card["id"]: card for card in model["evidenceCards"]}[card_id]


def _assert_no_forbidden_advice_text(payload: dict) -> None:
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in FORBIDDEN_TEXT:
        assert forbidden not in serialized


def test_ok_source_evidence_returns_product_ready_read_model(tmp_path: Path) -> None:
    model = _build_model(tmp_path)

    assert model["contractVersion"] == "market_regime_read_model_v1"
    assert model["sourceEvidenceContractVersion"] == "market_regime_evidence_pack_v1"
    assert model["status"] == "ok"
    assert model["readiness"]["label"] == "product_ready"
    assert model["consumerSafe"] is True
    assert model["noAdvice"] is True
    assert model["networkCallsEnabled"] is False
    assert model["mutationEnabled"] is False
    assert model["providerCallsEnabled"] is False
    assert model["missingDataFamilies"] == []
    assert model["blockedProductSurfaces"] == []
    assert {card["id"] for card in model["evidenceCards"]} == {
        "benchmark_trend",
        "growth_risk_proxy",
        "breadth",
        "volatility",
        "quote_snapshot",
        "data_quality",
    }
    assert {card["cardId"] for card in model["evidenceCards"]} == {
        "benchmark_trend",
        "growth_risk_proxy",
        "breadth",
        "volatility",
        "quote_snapshot",
        "data_quality",
    }
    assert model["surfaceHints"][0]["statusHint"] == "evidence_available"
    assert {hint["surfaceName"] for hint in model["surfaceHints"]} >= {
        "Market Overview",
        "Research Radar",
        "Scanner",
    }


def test_risk_off_cards_are_negative_or_warning_without_advice_text(tmp_path: Path) -> None:
    model = _build_model(tmp_path, values_by_symbol=_risk_off_values())

    assert model["regime"]["label"] == "risk_off"
    assert _card_by_id(model, "benchmark_trend")["status"] == "negative"
    assert _card_by_id(model, "benchmark_trend")["severity"] == "warning"
    assert _card_by_id(model, "breadth")["status"] == "negative"
    assert _card_by_id(model, "breadth")["severity"] == "warning"
    assert _card_by_id(model, "growth_risk_proxy")["status"] == "negative"
    assert _card_by_id(model, "growth_risk_proxy")["severity"] == "watch"
    assert "risk-off evidence is currently dominant" in model["productSummary"].lower()
    _assert_no_forbidden_advice_text(model)


def test_missing_adjusted_prices_preserves_missing_family_and_blocks_readiness(tmp_path: Path) -> None:
    model = _build_model(tmp_path, adjusted_symbols=[])

    assert model["status"] == "partial"
    assert model["readiness"]["label"] == "blocked"
    assert "adjusted_prices" in model["missingDataFamilies"]
    assert model["dataQuality"]["adjustedCoverageState"] == "missing"
    assert model["regime"]["label"] == "insufficient_data"
    assert _card_by_id(model, "data_quality")["severity"] == "blocker"


def test_missing_quote_snapshot_preserves_source_state_and_marks_quote_card_blocker(tmp_path: Path) -> None:
    model = _build_model(tmp_path, quote_symbols=["SPY", "QQQ", "MSFT"])

    assert model["status"] == "partial"
    assert model["readiness"]["label"] == "blocked"
    assert "quote_snapshot" in model["missingDataFamilies"]
    quote_card = _card_by_id(model, "quote_snapshot")
    assert quote_card["status"] == "unavailable"
    assert quote_card["severity"] == "blocker"
    assert model["dataQuality"]["quoteSnapshotCoverage"]["state"] == "partial"
    assert model["dataQuality"]["quoteSnapshotCoverage"]["missingSymbols"] == ["AAPL"]
    assert model["surfaceHints"][0]["statusHint"] == "quote_snapshot_missing"


def test_stale_quote_snapshot_is_consumed_and_degraded_not_not_requested(tmp_path: Path) -> None:
    ohlcv_dir = tmp_path / "us-parquet-cache"
    quote_path = tmp_path / "quote-snapshot-cache" / "us-starter-quotes.json"
    _write_ohlcv(ohlcv_dir, _full_values())
    _write_stale_quote_cache(quote_path, SYMBOLS)

    model = build_market_regime_read_model(
        market="US",
        symbols=SYMBOLS,
        benchmark_symbol="SPY",
        growth_proxy_symbol="QQQ",
        required_bars=60,
        ohlcv_cache_dir=ohlcv_dir,
        quote_snapshot_cache_path=quote_path,
        require_adjusted=True,
    )

    assert model["dataQuality"]["ohlcvCoverage"]["state"] == "available"
    quote_coverage = model["dataQuality"]["quoteSnapshotCoverage"]
    assert quote_coverage["state"] == "stale"
    assert quote_coverage["availabilityState"] == "stale"
    assert quote_coverage["staleSymbols"] == SYMBOLS
    assert quote_coverage["state"] != "not_requested"
    quote_card = _card_by_id(model, "quote_snapshot")
    assert quote_card["cardId"] == "quote_snapshot"
    assert quote_card["status"] == "degraded"
    assert model["surfaceHints"]
    assert all(hint.get("statusHint") for hint in model["surfaceHints"])


def test_invalid_source_input_fails_closed_without_raw_exception_leakage(tmp_path: Path) -> None:
    missing_dir = tmp_path / "missing-cache"
    model = build_market_regime_read_model(
        market="US",
        symbols=SYMBOLS,
        benchmark_symbol="SPY",
        growth_proxy_symbol="QQQ",
        required_bars=60,
        ohlcv_cache_dir=missing_dir,
        quote_snapshot_cache_path=tmp_path / "missing-quotes.json",
        require_adjusted=True,
    )

    assert model["status"] == "failed_closed"
    assert model["readiness"]["label"] == "failed_closed"
    assert model["regime"]["label"] == "insufficient_data"
    serialized = json.dumps(model, ensure_ascii=False).lower()
    for forbidden in ("traceback", "exception", "filenotfounderror", "rawpayload", str(missing_dir).lower()):
        assert forbidden not in serialized


def test_symbol_context_contains_trend_and_coverage_without_ranking_fields(tmp_path: Path) -> None:
    model = _build_model(tmp_path)

    assert [row["symbol"] for row in model["symbolContext"]] == SYMBOLS
    first = model["symbolContext"][0]
    assert set(first) == {
        "symbol",
        "coverageState",
        "latestClose",
        "adjustedClose",
        "return20d",
        "closeVsMa20",
        "closeVsMa50",
        "missingBars",
        "adjustedCoverageState",
    }
    serialized_keys = json.dumps(list(first), ensure_ascii=False).lower()
    assert "rank" not in serialized_keys
    assert "recommendation" not in serialized_keys
    assert "target" not in serialized_keys
