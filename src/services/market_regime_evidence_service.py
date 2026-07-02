from __future__ import annotations

import json
import math
import statistics
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.services.local_quote_snapshot_provider import LocalQuoteSnapshotJsonProvider
from src.services.quote_snapshot_readiness import (
    QuoteSnapshotReadinessRequest,
    QuoteSnapshotReadinessService,
)
from src.services.starter_market_data import STARTER_MARKET_DATA_SYMBOLS


MARKET_REGIME_EVIDENCE_CONTRACT_VERSION = "market_regime_evidence_pack_v1"
MARKET_REGIME_NO_ADVICE_DISCLOSURE = (
    "Observation-only market structure evidence derived from local OHLCV inputs; "
    "not investment advice or an execution instruction."
)
DEFAULT_MARKET_REGIME_SYMBOLS = STARTER_MARKET_DATA_SYMBOLS
DEFAULT_BENCHMARK_SYMBOL = "SPY"
DEFAULT_GROWTH_PROXY_SYMBOL = "QQQ"
DEFAULT_REQUIRED_BARS = 60
DEFAULT_QUOTE_MAX_AGE_SECONDS = 60 * 60 * 24
DEFAULT_UNIVERSE_TIER = "tier1"
LEADERSHIP_SYMBOLS = ("QQQ", "AAPL", "MSFT", "NVDA", "TSLA")


def build_market_regime_evidence_pack(
    *,
    market: str = "US",
    symbols: Sequence[str] | None = None,
    benchmark_symbol: str = DEFAULT_BENCHMARK_SYMBOL,
    growth_proxy_symbol: str = DEFAULT_GROWTH_PROXY_SYMBOL,
    required_bars: int = DEFAULT_REQUIRED_BARS,
    ohlcv_cache_dir: str | Path | None,
    quote_snapshot_cache_path: str | Path | None = None,
    require_adjusted: bool = True,
    explicit_universe: Sequence[str] | None = None,
    quote_max_age_seconds: int = DEFAULT_QUOTE_MAX_AGE_SECONDS,
) -> dict[str, Any]:
    normalized_market = _normalize_market(market)
    requested_symbols = _normalize_symbols(symbols or DEFAULT_MARKET_REGIME_SYMBOLS)
    benchmark = _normalize_symbol(benchmark_symbol) or DEFAULT_BENCHMARK_SYMBOL
    growth_proxy = _normalize_symbol(growth_proxy_symbol) or DEFAULT_GROWTH_PROXY_SYMBOL
    required = max(1, int(required_bars or DEFAULT_REQUIRED_BARS))
    universe = _normalize_symbols(explicit_universe or requested_symbols)

    base = _base_payload(
        market=normalized_market,
        symbols=requested_symbols,
        benchmark_symbol=benchmark,
        growth_proxy_symbol=growth_proxy,
        required_bars=required,
        require_adjusted=require_adjusted,
    )
    validation_errors = _validate_inputs(
        market=normalized_market,
        symbols=requested_symbols,
        benchmark_symbol=benchmark,
        growth_proxy_symbol=growth_proxy,
        explicit_universe=universe,
        ohlcv_cache_dir=ohlcv_cache_dir,
        quote_snapshot_cache_path=quote_snapshot_cache_path,
    )
    if validation_errors:
        reasons = [item["code"] for item in validation_errors]
        empty_evidence = _evidence_sections(
            historical_coverage=_empty_historical_coverage(required_bars=required),
            benchmark_trend=_empty_trend_evidence(benchmark),
            growth_proxy={},
            breadth={},
            volatility={},
            symbol_evidence={},
            required_bars=required,
            benchmark_symbol=benchmark,
        )
        return _sanitize_pack(
            {
                **base,
                "status": "failed_closed",
                "readiness": "failed_closed",
                "availableDataClasses": [],
                "missingDataFamilies": _fail_closed_missing_families(reasons),
                "blockedProductSurfaces": ["Scanner", "Market Overview", "Watchlist", "Research Radar"],
                "nextOperatorAction": _fail_closed_operator_action(reasons),
                "evidence": empty_evidence,
                "regimeSummary": _regime_summary(
                    "insufficient_data",
                    status="failed_closed",
                    confidence=0.0,
                    explanation="Local market regime inputs failed validation, so no regime evidence is published.",
                ),
                "symbolEvidence": {},
                "benchmarkEvidence": _empty_trend_evidence(benchmark),
                "quoteSnapshotEvidence": _empty_quote_evidence(requested_symbols),
                "dataQuality": {
                    "status": "failed_closed",
                    "summary": "Local market regime inputs failed validation.",
                    "missingBars": {},
                    "missingAdjustedData": [],
                    "missingQuoteSnapshot": requested_symbols,
                    "staleOrUnknownFreshness": requested_symbols,
                    "failClosedReasons": reasons,
                    "reasonCodes": reasons,
                },
            }
        )

    frames = _load_symbol_frames(Path(str(ohlcv_cache_dir)).expanduser(), requested_symbols)
    symbol_evidence = {
        symbol: _build_symbol_evidence(
            symbol,
            frames.get(symbol),
            required_bars=required,
            require_adjusted=require_adjusted,
        )
        for symbol in requested_symbols
    }
    benchmark_evidence = dict(symbol_evidence.get(benchmark) or _empty_symbol_evidence(benchmark, required))
    benchmark_trend = dict(benchmark_evidence.get("trend") or _empty_trend_evidence(benchmark))
    growth_proxy_evidence = _growth_proxy_evidence(
        benchmark_frame=frames.get(benchmark),
        growth_frame=frames.get(growth_proxy),
        benchmark_symbol=benchmark,
        growth_proxy_symbol=growth_proxy,
    )
    breadth = _breadth_evidence(symbol_evidence)
    volatility = _volatility_evidence(frames.get(benchmark), benchmark_symbol=benchmark)
    quote = _quote_snapshot_evidence(
        symbols=requested_symbols,
        market=normalized_market,
        quote_snapshot_cache_path=quote_snapshot_cache_path,
        quote_max_age_seconds=quote_max_age_seconds,
    )
    data_quality = _data_quality(
        symbol_evidence=symbol_evidence,
        quote=quote,
    )
    missing_families = _missing_data_families(
        symbol_evidence=symbol_evidence,
        benchmark_symbol=benchmark,
        growth_proxy_symbol=growth_proxy,
        benchmark_trend=benchmark_trend,
        growth_proxy=growth_proxy_evidence,
        breadth=breadth,
        volatility=volatility,
        quote=quote,
        require_adjusted=require_adjusted,
    )
    available_classes = _available_data_classes(
        symbol_evidence=symbol_evidence,
        benchmark_symbol=benchmark,
        growth_proxy_symbol=growth_proxy,
        benchmark_trend=benchmark_trend,
        growth_proxy=growth_proxy_evidence,
        breadth=breadth,
        volatility=volatility,
        quote=quote,
        missing_families=missing_families,
        require_adjusted=require_adjusted,
    )
    status = _status_from_evidence(symbol_evidence=symbol_evidence, missing_families=missing_families)
    regime_label = _derive_regime_label(
        status=status,
        missing_families=missing_families,
        benchmark_trend=benchmark_trend,
        growth_proxy=growth_proxy_evidence,
        breadth=breadth,
    )
    confidence = _regime_confidence(
        status=status,
        regime_label=regime_label,
        missing_families=missing_families,
        benchmark_trend=benchmark_trend,
        growth_proxy=growth_proxy_evidence,
        breadth=breadth,
        volatility=volatility,
    )
    historical_coverage = _historical_coverage(symbol_evidence, required)
    evidence_sections = _evidence_sections(
        historical_coverage=historical_coverage,
        benchmark_trend=benchmark_trend,
        growth_proxy=growth_proxy_evidence,
        breadth=breadth,
        volatility=volatility,
        symbol_evidence=symbol_evidence,
        required_bars=required,
        benchmark_symbol=benchmark,
    )
    if status == "failed_closed":
        evidence_sections = _evidence_sections(
            historical_coverage=historical_coverage,
            benchmark_trend=_empty_trend_evidence(benchmark),
            growth_proxy={},
            breadth={},
            volatility={},
            symbol_evidence=symbol_evidence,
            required_bars=required,
            benchmark_symbol=benchmark,
        )
    data_quality = {
        **data_quality,
        "status": status,
        "summary": _data_quality_summary(status=status, missing_families=missing_families, data_quality=data_quality),
        "reasonCodes": _reason_codes(status=status, missing_families=missing_families, data_quality=data_quality),
    }
    payload = {
        **base,
        "status": status,
        "readiness": status,
        "asOf": evidence_sections["dataCoverage"].get("asOf"),
        "availableDataClasses": available_classes,
        "missingDataFamilies": missing_families,
        "blockedProductSurfaces": _blocked_surfaces(missing_families),
        "nextOperatorAction": _next_operator_action(status=status, missing_families=missing_families),
        "evidence": evidence_sections,
        "regimeSummary": _regime_summary(
            regime_label,
            status=status,
            confidence=confidence,
            explanation=_regime_explanation(regime_label, status=status),
        ),
        "symbolEvidence": symbol_evidence,
        "benchmarkEvidence": evidence_sections["benchmarkTrend"],
        "quoteSnapshotEvidence": quote,
        "dataQuality": data_quality,
    }
    return _sanitize_pack(payload)


def _base_payload(
    *,
    market: str,
    symbols: Sequence[str],
    benchmark_symbol: str,
    growth_proxy_symbol: str,
    required_bars: int,
    require_adjusted: bool,
) -> dict[str, Any]:
    return {
        "consumerSafe": True,
        "contractVersion": MARKET_REGIME_EVIDENCE_CONTRACT_VERSION,
        "status": "failed_closed",
        "readiness": "failed_closed",
        "market": market,
        "tier": DEFAULT_UNIVERSE_TIER,
        "universe": {"market": market, "tier": DEFAULT_UNIVERSE_TIER, "symbols": list(symbols)},
        "evaluatedSymbols": list(symbols),
        "symbols": list(symbols),
        "benchmarkSymbol": benchmark_symbol,
        "growthProxySymbol": growth_proxy_symbol,
        "requiredBars": required_bars,
        "requireAdjusted": bool(require_adjusted),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "asOf": None,
        "noAdviceDisclosure": MARKET_REGIME_NO_ADVICE_DISCLOSURE,
        "networkCallsEnabled": False,
        "mutationEnabled": False,
        "providerCallsEnabled": False,
    }


def _validate_inputs(
    *,
    market: str,
    symbols: Sequence[str],
    benchmark_symbol: str,
    growth_proxy_symbol: str,
    explicit_universe: Sequence[str],
    ohlcv_cache_dir: str | Path | None,
    quote_snapshot_cache_path: str | Path | None,
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    universe = set(explicit_universe)
    if market != "US":
        errors.append({"field": "market", "code": "unsupported_market"})
    if not symbols:
        errors.append({"field": "symbols", "code": "empty_symbols"})
    if any(symbol not in universe for symbol in symbols):
        errors.append({"field": "symbols", "code": "symbol_outside_explicit_universe"})
    if benchmark_symbol not in universe:
        errors.append({"field": "benchmarkSymbol", "code": "symbol_outside_explicit_universe"})
    if growth_proxy_symbol not in universe:
        errors.append({"field": "growthProxySymbol", "code": "symbol_outside_explicit_universe"})
    cache_dir = Path(str(ohlcv_cache_dir or "")).expanduser()
    if not str(ohlcv_cache_dir or "").strip() or not cache_dir.is_dir():
        errors.append({"field": "ohlcvCacheDir", "code": "unreadable_ohlcv_cache"})
    if quote_snapshot_cache_path is not None:
        quote_path = Path(str(quote_snapshot_cache_path)).expanduser()
        if quote_path.is_file() and not _quote_json_shape_is_valid(quote_path):
            errors.append({"field": "quoteSnapshotCachePath", "code": "malformed_quote_snapshot"})
    return errors


def _quote_json_shape_is_valid(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    rows = payload.get("quotes") if isinstance(payload, Mapping) else payload
    return isinstance(rows, list)


def _load_symbol_frames(cache_dir: Path, symbols: Sequence[str]) -> dict[str, pd.DataFrame | None]:
    result: dict[str, pd.DataFrame | None] = {}
    for symbol in symbols:
        path = cache_dir / f"{symbol}.parquet"
        if not path.is_file():
            result[symbol] = None
            continue
        try:
            normalized = _normalize_ohlcv_frame(pd.read_parquet(path))
            result[symbol] = normalized if normalized is not None else pd.DataFrame()
        except Exception:
            result[symbol] = pd.DataFrame()
    return result


def _normalize_ohlcv_frame(frame: pd.DataFrame | None) -> pd.DataFrame | None:
    if frame is None or frame.empty:
        return None
    df = frame.copy()
    if "trade_date" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"trade_date": "date"})
    for candidate in ("adjusted_close", "adjustedClose", "adj_close", "Adj Close", "Adjusted Close"):
        if candidate in df.columns:
            if candidate != "adjusted_close":
                df = df.rename(columns={candidate: "adjusted_close"})
            break
    required = {"date", "open", "high", "low", "close", "volume"}
    if not required.issubset(set(df.columns)):
        return None
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for column in ("open", "high", "low", "close", "volume", "adjusted_close"):
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=["date", "open", "high", "low", "close"]).copy()
    if df.empty:
        return None
    return df.sort_values("date").reset_index(drop=True)


def _build_symbol_evidence(
    symbol: str,
    frame: pd.DataFrame | None,
    *,
    required_bars: int,
    require_adjusted: bool,
) -> dict[str, Any]:
    if frame is None:
        return _empty_symbol_evidence(symbol, required_bars)
    if frame.empty:
        evidence = _empty_symbol_evidence(symbol, required_bars)
        evidence["coverage"]["state"] = "malformed"
        return evidence

    usable = int(len(frame))
    coverage_state = "available" if usable >= required_bars else "insufficient_history"
    adjusted_available = _adjusted_available(frame)
    adjusted_state = "available" if adjusted_available else "missing" if require_adjusted else "not_required"
    latest = frame.iloc[-1]
    trend = _trend_evidence(symbol, frame)
    trend["adjustedClose"] = _round_or_none(latest.get("adjusted_close")) if adjusted_available else None
    return {
        "symbol": symbol,
        "coverage": {
            "requiredBars": required_bars,
            "usableBars": usable,
            "missingBars": max(0, required_bars - usable),
            "usableRange": _usable_range(frame),
            "adjustedCoverageState": adjusted_state,
            "state": coverage_state,
        },
        "trend": trend,
    }


def _trend_evidence(symbol: str, frame: pd.DataFrame | None) -> dict[str, Any]:
    if frame is None or frame.empty:
        return _empty_trend_evidence(symbol)
    closes = [float(value) for value in frame["close"].dropna().tolist()]
    latest_close = closes[-1] if closes else None
    ma20 = _moving_average(closes, 20)
    ma50 = _moving_average(closes, 50)
    return {
        "symbol": symbol,
        "latestClose": _round_or_none(latest_close),
        "adjustedClose": None,
        "return20d": _return_over(closes, 20),
        "return60d": _return_over(closes, 60),
        "movingAverage20d": _round_or_none(ma20),
        "movingAverage50d": _round_or_none(ma50),
        "closeVsMa20": _close_vs_ma(latest_close, ma20),
        "closeVsMa50": _close_vs_ma(latest_close, ma50),
    }


def _growth_proxy_evidence(
    *,
    benchmark_frame: pd.DataFrame | None,
    growth_frame: pd.DataFrame | None,
    benchmark_symbol: str,
    growth_proxy_symbol: str,
) -> dict[str, Any]:
    benchmark_closes = _closes(benchmark_frame)
    growth_closes = _closes(growth_frame)
    benchmark20 = _return_over(benchmark_closes, 20)
    growth20 = _return_over(growth_closes, 20)
    benchmark60 = _return_over(benchmark_closes, 60)
    growth60 = _return_over(growth_closes, 60)
    return {
        "benchmarkSymbol": benchmark_symbol,
        "growthProxySymbol": growth_proxy_symbol,
        "relativeReturn20d": _relative_return(growth20, benchmark20),
        "relativeReturn60d": _relative_return(growth60, benchmark60),
        "state": "available" if benchmark20 is not None and growth20 is not None else "insufficient_data",
    }


def _breadth_evidence(symbol_evidence: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    available = 0
    missing = 0
    above_ma20 = 0
    positive_return20 = 0
    for evidence in symbol_evidence.values():
        coverage = evidence.get("coverage") if isinstance(evidence, Mapping) else {}
        trend = evidence.get("trend") if isinstance(evidence, Mapping) else {}
        if not isinstance(coverage, Mapping) or coverage.get("state") != "available":
            missing += 1
            continue
        if not isinstance(trend, Mapping):
            missing += 1
            continue
        if trend.get("closeVsMa20") in {"above", "below", "at"} and trend.get("return20d") is not None:
            available += 1
            if trend.get("closeVsMa20") == "above":
                above_ma20 += 1
            if float(trend.get("return20d") or 0.0) > 0:
                positive_return20 += 1
        else:
            missing += 1
    return {
        "percentAboveMa20": _ratio(above_ma20, available),
        "percentPositiveReturn20d": _ratio(positive_return20, available),
        "availableCount": available,
        "missingCount": missing,
        "state": "available" if available > 0 else "insufficient_data",
    }


def _volatility_evidence(frame: pd.DataFrame | None, *, benchmark_symbol: str) -> dict[str, Any]:
    closes = _closes(frame)
    returns = [
        (closes[index] / closes[index - 1]) - 1.0
        for index in range(1, len(closes))
        if closes[index - 1] > 0
    ]
    window = returns[-20:]
    realized = statistics.pstdev(window) * math.sqrt(252) if len(window) >= 2 else None
    state = _volatility_state(realized)
    return {
        "symbol": benchmark_symbol,
        "realizedVolatility20d": _round_or_none(realized),
        "volatilityState": state,
        "stateBands": {"lowBelow": 0.12, "normalAtOrBelow": 0.25, "elevatedAbove": 0.25},
        "state": "available" if realized is not None else "insufficient_data",
    }


def _quote_snapshot_evidence(
    *,
    symbols: Sequence[str],
    market: str,
    quote_snapshot_cache_path: str | Path | None,
    quote_max_age_seconds: int,
) -> dict[str, Any]:
    if quote_snapshot_cache_path is None:
        return _empty_quote_evidence(symbols)
    result = QuoteSnapshotReadinessService(
        provider=LocalQuoteSnapshotJsonProvider(cache_path=quote_snapshot_cache_path)
    ).fetch(
        QuoteSnapshotReadinessRequest(
            symbols=tuple(symbols),
            market=market.lower(),
            max_age_seconds=max(1, int(quote_max_age_seconds or DEFAULT_QUOTE_MAX_AGE_SECONDS)),
        )
    )
    readiness = dict(result.readiness)
    return {
        "availableSymbols": list(readiness.get("availableSymbols") or []),
        "missingSymbols": list(readiness.get("missingSymbols") or []),
        "staleSymbols": list(readiness.get("staleSymbols") or []),
        "freshnessState": str(readiness.get("freshnessState") or "unknown"),
        "availabilityState": str(readiness.get("availabilityState") or "missing"),
        "sourceFamilies": list(readiness.get("sourceFamilies") or []),
        "providerCallsEnabled": False,
        "state": (
            "available"
            if readiness.get("availabilityState") == "available"
            else "stale"
            if readiness.get("availabilityState") == "stale"
            else "partial"
            if readiness.get("availabilityState") == "partial"
            else "missing"
        ),
    }


def _historical_coverage(
    symbol_evidence: Mapping[str, Mapping[str, Any]],
    required_bars: int,
) -> dict[str, Any]:
    rows = {}
    available_symbols: list[str] = []
    missing_symbols: list[str] = []
    adjusted_symbols: list[str] = []
    for symbol, evidence in symbol_evidence.items():
        coverage = dict(evidence.get("coverage") or {})
        rows[symbol] = coverage
        if coverage.get("state") == "available":
            available_symbols.append(symbol)
        else:
            missing_symbols.append(symbol)
        if coverage.get("adjustedCoverageState") == "available":
            adjusted_symbols.append(symbol)
    return {
        "requiredBars": required_bars,
        "usableBars": {
            symbol: int((rows.get(symbol) or {}).get("usableBars") or 0)
            for symbol in symbol_evidence
        },
        "usableRange": {
            symbol: dict((rows.get(symbol) or {}).get("usableRange") or {})
            for symbol in symbol_evidence
        },
        "adjustedCoverageState": "available"
        if len(adjusted_symbols) == len(symbol_evidence)
        else "missing",
        "availableSymbols": available_symbols,
        "missingSymbols": missing_symbols,
    }


def _empty_historical_coverage(*, required_bars: int) -> dict[str, Any]:
    return {
        "requiredBars": required_bars,
        "usableBars": {},
        "usableRange": {},
        "adjustedCoverageState": "missing",
        "availableSymbols": [],
        "missingSymbols": [],
    }


def _evidence_sections(
    *,
    historical_coverage: Mapping[str, Any],
    benchmark_trend: Mapping[str, Any],
    growth_proxy: Mapping[str, Any],
    breadth: Mapping[str, Any],
    volatility: Mapping[str, Any],
    symbol_evidence: Mapping[str, Mapping[str, Any]],
    required_bars: int,
    benchmark_symbol: str,
) -> dict[str, Any]:
    trend = dict(benchmark_trend or _empty_trend_evidence(benchmark_symbol))
    coverage = _data_coverage(symbol_evidence=symbol_evidence, required_bars=required_bars)
    usable_ranges = dict(historical_coverage.get("usableRange") or {})
    if trend.get("symbol") and isinstance(usable_ranges.get(str(trend.get("symbol"))), Mapping):
        trend["usableRange"] = dict(usable_ranges[str(trend.get("symbol"))])
    return {
        "historicalOhlcvCoverage": dict(historical_coverage),
        "benchmarkTrend": trend,
        "growthRiskProxy": dict(growth_proxy),
        "breadthProxy": dict(breadth),
        "volatilityProxy": dict(volatility),
        "indexTrend": trend,
        "breadth": _breadth_section(breadth),
        "momentum": _momentum_section(trend),
        "volatilityRisk": dict(volatility),
        "concentrationLeadership": _concentration_leadership(symbol_evidence=symbol_evidence, benchmark_trend=trend),
        "dataCoverage": coverage,
    }


def _breadth_section(breadth: Mapping[str, Any]) -> dict[str, Any]:
    available_count = int(breadth.get("availableCount") or 0)
    percent_above = breadth.get("percentAboveMa20")
    above_count = None if percent_above is None else int(round(float(percent_above) * available_count))
    positive_return = breadth.get("percentPositiveReturn20d")
    positive_count = None if positive_return is None else int(round(float(positive_return) * available_count))
    return {
        "percentAboveMovingAverage": percent_above,
        "aboveMovingAverageCount": above_count,
        "percentPositiveMomentum": positive_return,
        "positiveMomentumCount": positive_count,
        "evaluatedCount": available_count,
        "skippedCount": int(breadth.get("missingCount") or 0),
        "state": str(breadth.get("state") or "insufficient_data"),
    }


def _momentum_section(index_trend: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "symbol": index_trend.get("symbol"),
        "shortWindow": "20d",
        "shortWindowReturn": index_trend.get("return20d"),
        "mediumWindow": "60d",
        "mediumWindowReturn": index_trend.get("return60d"),
        "state": "available" if index_trend.get("return20d") is not None else "insufficient_data",
    }


def _concentration_leadership(
    *,
    symbol_evidence: Mapping[str, Mapping[str, Any]],
    benchmark_trend: Mapping[str, Any],
) -> dict[str, Any]:
    benchmark_return = benchmark_trend.get("return20d")
    leader_returns: list[float] = []
    evaluated: list[str] = []
    skipped: list[str] = []
    for symbol in LEADERSHIP_SYMBOLS:
        evidence = dict(symbol_evidence.get(symbol) or {})
        trend = dict(evidence.get("trend") or {})
        value = trend.get("return20d")
        if value is None:
            skipped.append(symbol)
            continue
        leader_returns.append(float(value))
        evaluated.append(symbol)
    average = round(sum(leader_returns) / len(leader_returns), 6) if leader_returns else None
    relative = _relative_return(average, float(benchmark_return)) if average is not None and benchmark_return is not None else None
    if relative is None:
        state = "insufficient_data"
    elif relative > 0.01:
        state = "leaders_ahead"
    elif relative < -0.01:
        state = "leaders_lagging"
    else:
        state = "leaders_inline"
    return {
        "leadershipSymbols": list(LEADERSHIP_SYMBOLS),
        "evaluatedSymbols": evaluated,
        "skippedSymbols": skipped,
        "averageLeaderReturn20d": average,
        "benchmarkReturn20d": benchmark_return,
        "relativeReturn20d": relative,
        "state": state,
    }


def _data_coverage(
    *,
    symbol_evidence: Mapping[str, Mapping[str, Any]],
    required_bars: int,
) -> dict[str, Any]:
    used: list[str] = []
    skipped: list[dict[str, str]] = []
    ranges: dict[str, Mapping[str, str]] = {}
    as_of_values: list[str] = []
    for symbol, evidence in symbol_evidence.items():
        coverage = dict(evidence.get("coverage") or {})
        state = str(coverage.get("state") or "missing")
        usable_range = dict(coverage.get("usableRange") or {})
        if state == "available":
            used.append(symbol)
            ranges[symbol] = usable_range
            if usable_range.get("end"):
                as_of_values.append(str(usable_range["end"]))
        else:
            skipped.append({"symbol": symbol, "reason": state})
    return {
        "requiredBars": required_bars,
        "usedSymbols": used,
        "skippedSymbols": skipped,
        "coverageBySymbol": {
            symbol: dict((evidence.get("coverage") if isinstance(evidence, Mapping) else {}) or {})
            for symbol, evidence in symbol_evidence.items()
        },
        "usableRangeBySymbol": ranges,
        "asOf": max(as_of_values) if as_of_values else None,
        "state": "available" if used and not skipped else "partial" if used else "missing",
    }


def _data_quality(
    *,
    symbol_evidence: Mapping[str, Mapping[str, Any]],
    quote: Mapping[str, Any],
) -> dict[str, Any]:
    missing_bars: dict[str, int] = {}
    missing_adjusted: list[str] = []
    for symbol, evidence in symbol_evidence.items():
        coverage = dict(evidence.get("coverage") or {})
        count = int(coverage.get("missingBars") or 0)
        if count > 0 or coverage.get("state") != "available":
            missing_bars[symbol] = count
        if coverage.get("adjustedCoverageState") == "missing":
            missing_adjusted.append(symbol)
    freshness_symbols = list(quote.get("staleSymbols") or [])
    if quote.get("freshnessState") in {"missing", "unknown"}:
        freshness_symbols = list(symbol_evidence.keys())
    return {
        "missingBars": missing_bars,
        "missingAdjustedData": missing_adjusted,
        "missingQuoteSnapshot": list(quote.get("missingSymbols") or []),
        "staleOrUnknownFreshness": freshness_symbols,
        "failClosedReasons": [],
    }


def _missing_data_families(
    *,
    symbol_evidence: Mapping[str, Mapping[str, Any]],
    benchmark_symbol: str,
    growth_proxy_symbol: str,
    benchmark_trend: Mapping[str, Any],
    growth_proxy: Mapping[str, Any],
    breadth: Mapping[str, Any],
    volatility: Mapping[str, Any],
    quote: Mapping[str, Any],
    require_adjusted: bool,
) -> list[str]:
    families: list[str] = []

    def add(value: str) -> None:
        if value not in families:
            families.append(value)

    for evidence in symbol_evidence.values():
        coverage = dict(evidence.get("coverage") or {})
        if coverage.get("state") == "malformed":
            add("malformed_ohlcv")
            continue
        if coverage.get("state") != "available":
            add("historical_ohlcv")
        if require_adjusted and coverage.get("adjustedCoverageState") != "available":
            add("adjusted_prices")
    if benchmark_symbol not in symbol_evidence or benchmark_trend.get("return20d") is None:
        add("benchmark_ohlcv")
    if growth_proxy_symbol not in symbol_evidence or growth_proxy.get("state") != "available":
        add("growth_proxy_ohlcv")
    if breadth.get("state") != "available":
        add("breadth_proxy")
    if volatility.get("state") != "available":
        add("volatility_proxy")
    if quote.get("availabilityState") not in {"available", "not_requested", "stale"}:
        add("quote_snapshot")
    return families


def _status_from_evidence(
    *,
    symbol_evidence: Mapping[str, Mapping[str, Any]],
    missing_families: Sequence[str],
) -> str:
    states = {
        str(dict(evidence.get("coverage") or {}).get("state") or "missing")
        for evidence in symbol_evidence.values()
    }
    if "malformed" in states or "malformed_ohlcv" in set(missing_families):
        return "failed_closed"
    if "historical_ohlcv" in set(missing_families):
        return "blocked"
    if missing_families:
        return "partial"
    return "ready"


def _available_data_classes(
    *,
    symbol_evidence: Mapping[str, Mapping[str, Any]],
    benchmark_symbol: str,
    growth_proxy_symbol: str,
    benchmark_trend: Mapping[str, Any],
    growth_proxy: Mapping[str, Any],
    breadth: Mapping[str, Any],
    volatility: Mapping[str, Any],
    quote: Mapping[str, Any],
    missing_families: Sequence[str],
    require_adjusted: bool,
) -> list[str]:
    missing = set(missing_families)
    values: list[str] = []
    if "historical_ohlcv" not in missing:
        values.append("historical_ohlcv")
    if require_adjusted and "adjusted_prices" not in missing:
        values.append("adjusted_prices")
    if benchmark_symbol in symbol_evidence and benchmark_trend.get("return20d") is not None:
        values.append("benchmark_trend")
    if growth_proxy_symbol in symbol_evidence and growth_proxy.get("state") == "available":
        values.append("growth_risk_proxy")
    if breadth.get("state") == "available":
        values.append("breadth_proxy")
    if volatility.get("state") == "available":
        values.append("volatility_proxy")
    if quote.get("availabilityState") == "available":
        values.append("quote_snapshot")
    return values


def _derive_regime_label(
    *,
    status: str,
    missing_families: Sequence[str],
    benchmark_trend: Mapping[str, Any],
    growth_proxy: Mapping[str, Any],
    breadth: Mapping[str, Any],
) -> str:
    if status != "ready" or any(
        family in set(missing_families)
        for family in ("historical_ohlcv", "adjusted_prices", "benchmark_ohlcv", "quote_snapshot")
    ):
        return "insufficient_data"
    benchmark20 = benchmark_trend.get("return20d")
    close_vs_ma20 = benchmark_trend.get("closeVsMa20")
    breadth_ma20 = breadth.get("percentAboveMa20")
    relative20 = growth_proxy.get("relativeReturn20d")
    if (
        _gt(benchmark20, 0)
        and close_vs_ma20 == "above"
        and _gte(breadth_ma20, 0.60)
        and _gte(relative20, 0)
    ):
        return "risk_on"
    if _lt(benchmark20, 0) and close_vs_ma20 == "below" and _lte(breadth_ma20, 0.40):
        return "risk_off"
    return "mixed"


def _regime_summary(
    label: str,
    *,
    status: str,
    confidence: float = 0.0,
    explanation: str | None = None,
) -> dict[str, Any]:
    return {
        "label": label,
        "status": "partial" if label == "insufficient_data" and status not in {"failed_closed", "blocked"} else status,
        "confidence": max(0.0, min(1.0, round(float(confidence or 0.0), 3))),
        "explanation": explanation or _regime_explanation(label, status=status),
        "derivation": "deterministic_evidence_fields",
    }


def _regime_confidence(
    *,
    status: str,
    regime_label: str,
    missing_families: Sequence[str],
    benchmark_trend: Mapping[str, Any],
    growth_proxy: Mapping[str, Any],
    breadth: Mapping[str, Any],
    volatility: Mapping[str, Any],
) -> float:
    if status != "ready" or regime_label == "insufficient_data":
        return 0.0 if status == "failed_closed" else 0.25
    inputs = [
        benchmark_trend.get("return20d") is not None,
        benchmark_trend.get("closeVsMa20") in {"above", "below", "at"},
        growth_proxy.get("relativeReturn20d") is not None,
        breadth.get("percentAboveMa20") is not None,
        volatility.get("realizedVolatility20d") is not None,
    ]
    coverage_score = sum(1 for item in inputs if item) / float(len(inputs))
    penalty = min(0.4, 0.08 * len(set(missing_families)))
    return max(0.1, min(0.85, coverage_score - penalty))


def _regime_explanation(label: str, *, status: str) -> str:
    if status == "failed_closed":
        return "One or more local OHLCV inputs were malformed, so no market-regime conclusion is published."
    if status == "blocked":
        return "Required local OHLCV coverage is missing or insufficient, so the regime label remains insufficient_data."
    if label == "risk_on":
        return "Benchmark trend, breadth, and growth proxy evidence are aligned positively from local OHLCV inputs."
    if label == "risk_off":
        return "Benchmark trend and breadth evidence are aligned negatively from local OHLCV inputs."
    if label == "mixed":
        return "Observable OHLCV evidence is available but benchmark, breadth, and leadership signals are not aligned."
    return "Observable evidence is insufficient for a market-regime label."


def _next_operator_action(*, status: str, missing_families: Sequence[str]) -> str:
    if status == "ready":
        return "Market regime evidence is available from local adjusted OHLCV and quote snapshot inputs."
    missing = set(missing_families)
    if "malformed_ohlcv" in missing:
        return "Replace malformed local OHLCV parquet files with valid cache files, then rerun."
    if "historical_ohlcv" in missing:
        return "Provide local OHLCV parquet coverage for every explicitly requested symbol, then rerun."
    if "adjusted_prices" in missing:
        return "Provide adjusted close coverage through the existing local OHLCV cache workflow, then rerun."
    if "quote_snapshot" in missing:
        return "Provide quote snapshot JSON coverage for every explicitly requested symbol, then rerun."
    return "Review missing local market regime evidence families, then rerun."


def _blocked_surfaces(missing_families: Sequence[str]) -> list[str]:
    if not missing_families:
        return []
    blocked: list[str] = []
    missing = set(missing_families)
    if missing & {"historical_ohlcv", "adjusted_prices", "quote_snapshot"}:
        blocked.extend(["Scanner", "Market Overview", "Watchlist", "Research Radar"])
    elif missing:
        blocked.extend(["Market Overview", "Research Radar"])
    return blocked


def _fail_closed_missing_families(reasons: Sequence[str]) -> list[str]:
    if "symbol_outside_explicit_universe" in reasons:
        return ["invalid_symbols"]
    if "malformed_quote_snapshot" in reasons:
        return ["quote_snapshot"]
    return ["historical_ohlcv"]


def _data_quality_summary(
    *,
    status: str,
    missing_families: Sequence[str],
    data_quality: Mapping[str, Any],
) -> str:
    if status == "ready":
        return "All requested local OHLCV evidence sections were computed from available fixture/cache inputs."
    if status == "failed_closed":
        return "At least one local OHLCV input was malformed or unreadable, so evidence generation failed closed."
    if "historical_ohlcv" in set(missing_families):
        return "Required local OHLCV coverage is missing or insufficient for at least one requested symbol."
    if data_quality.get("missingAdjustedData"):
        return "Adjusted close coverage is missing for at least one requested symbol."
    if data_quality.get("missingQuoteSnapshot"):
        return "Quote snapshot coverage is missing for at least one requested symbol."
    return "Market regime evidence is partial because one or more evidence families are unavailable."


def _reason_codes(
    *,
    status: str,
    missing_families: Sequence[str],
    data_quality: Mapping[str, Any],
) -> list[str]:
    codes: list[str] = []
    if status == "ready":
        return []
    missing = set(missing_families)
    if "malformed_ohlcv" in missing:
        codes.append("malformed_ohlcv")
    if "historical_ohlcv" in missing:
        codes.append("historical_ohlcv_missing_or_insufficient")
    if data_quality.get("missingAdjustedData"):
        codes.append("adjusted_prices_missing")
    if data_quality.get("missingQuoteSnapshot"):
        codes.append("quote_snapshot_missing")
    for family in missing_families:
        if family not in codes and family not in {
            "malformed_ohlcv",
            "historical_ohlcv",
            "adjusted_prices",
            "quote_snapshot",
        }:
            codes.append(str(family))
    return codes


def _fail_closed_operator_action(reasons: Sequence[str]) -> str:
    if "symbol_outside_explicit_universe" in reasons:
        return "Use only symbols from the explicit bounded universe, then rerun."
    if "malformed_quote_snapshot" in reasons:
        return "Provide readable quote snapshot JSON with a top-level quote row list, then rerun."
    return "Provide a readable local OHLCV parquet cache directory, then rerun."


def _empty_evidence(*, required_bars: int) -> dict[str, Any]:
    return {
        "historicalOhlcvCoverage": {
            "requiredBars": required_bars,
            "usableBars": {},
            "usableRange": {},
            "adjustedCoverageState": "missing",
            "availableSymbols": [],
            "missingSymbols": [],
        },
        "benchmarkTrend": {},
        "growthRiskProxy": {},
        "breadthProxy": {},
        "volatilityProxy": {},
    }


def _empty_symbol_evidence(symbol: str, required_bars: int) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "coverage": {
            "requiredBars": required_bars,
            "usableBars": 0,
            "missingBars": required_bars,
            "usableRange": {},
            "adjustedCoverageState": "missing",
            "state": "missing",
        },
        "trend": _empty_trend_evidence(symbol),
    }


def _empty_trend_evidence(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "latestClose": None,
        "adjustedClose": None,
        "return20d": None,
        "return60d": None,
        "movingAverage20d": None,
        "movingAverage50d": None,
        "closeVsMa20": "insufficient_data",
        "closeVsMa50": "insufficient_data",
    }


def _empty_quote_evidence(symbols: Sequence[str]) -> dict[str, Any]:
    return {
        "availableSymbols": [],
        "missingSymbols": [],
        "staleSymbols": [],
        "freshnessState": "not_requested",
        "availabilityState": "not_requested",
        "sourceFamilies": [],
        "providerCallsEnabled": False,
        "state": "not_requested",
    }


def _usable_range(frame: pd.DataFrame) -> dict[str, str]:
    if frame is None or frame.empty:
        return {}
    return {
        "start": frame.iloc[0]["date"].date().isoformat(),
        "end": frame.iloc[-1]["date"].date().isoformat(),
    }


def _adjusted_available(frame: pd.DataFrame) -> bool:
    return "adjusted_close" in frame.columns and bool(frame["adjusted_close"].notna().all())


def _closes(frame: pd.DataFrame | None) -> list[float]:
    if frame is None or frame.empty or "close" not in frame.columns:
        return []
    return [float(value) for value in frame["close"].dropna().tolist()]


def _moving_average(values: Sequence[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return sum(values[-window:]) / float(window)


def _return_over(values: Sequence[float], window: int) -> float | None:
    if len(values) < window:
        return None
    start = float(values[-window])
    end = float(values[-1])
    if start <= 0:
        return None
    return round((end / start) - 1.0, 6)


def _relative_return(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return round(left - right, 6)


def _close_vs_ma(close: float | None, average: float | None) -> str:
    if close is None or average is None:
        return "insufficient_data"
    if close > average:
        return "above"
    if close < average:
        return "below"
    return "at"


def _volatility_state(realized: float | None) -> str:
    if realized is None:
        return "insufficient_data"
    if realized < 0.12:
        return "low"
    if realized <= 0.25:
        return "normal"
    return "elevated"


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 6)


def _round_or_none(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def _gt(value: Any, limit: float) -> bool:
    return value is not None and float(value) > limit


def _gte(value: Any, limit: float) -> bool:
    return value is not None and float(value) >= limit


def _lt(value: Any, limit: float) -> bool:
    return value is not None and float(value) < limit


def _lte(value: Any, limit: float) -> bool:
    return value is not None and float(value) <= limit


def _normalize_symbols(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        symbol = _normalize_symbol(value)
        if symbol and symbol not in result:
            result.append(symbol)
    return result


def _normalize_symbol(value: Any) -> str:
    symbol = str(value or "").strip().upper()
    if not symbol:
        return ""
    if not all(ch.isalnum() or ch in {".", "-", "_"} for ch in symbol):
        return ""
    return symbol[:16]


def _normalize_market(value: Any) -> str:
    return "US" if str(value or "").strip().upper() == "US" else "UNKNOWN"


def _sanitize_pack(payload: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False, default=str))


__all__ = [
    "DEFAULT_BENCHMARK_SYMBOL",
    "DEFAULT_GROWTH_PROXY_SYMBOL",
    "DEFAULT_MARKET_REGIME_SYMBOLS",
    "DEFAULT_REQUIRED_BARS",
    "MARKET_REGIME_EVIDENCE_CONTRACT_VERSION",
    "MARKET_REGIME_NO_ADVICE_DISCLOSURE",
    "build_market_regime_evidence_pack",
]
