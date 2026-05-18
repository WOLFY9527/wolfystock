# -*- coding: utf-8 -*-
"""US rotation radar quote provider with configured-provider and yfinance fallback."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from time import monotonic
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence

import pandas as pd

from data_provider.alpaca_fetcher import AlpacaFetcher
from data_provider.provider_credentials import get_provider_credentials
from src.services.market_overview_yfinance_transport import fetch_yfinance_quote_history_frame

QuoteProvider = Callable[[Iterable[str]], Mapping[str, Any]]

_QUOTE_SOURCE = "yfinance_proxy"
_QUOTE_SOURCE_LABEL = "Yahoo Finance"
_QUOTE_MODE = "proxy"
_QUOTE_SOURCE_TYPE = "unofficial_public_api"
_QUOTE_SOURCE_TIER = "unofficial_public_api"
_QUOTE_PROVIDER_TIER = "tier_2_delayed_proxy"
_QUOTE_CONFIDENCE_WEIGHT = 0.5
_CONFIGURED_SOURCE = "alpaca"
_CONFIGURED_SOURCE_TYPE = "official_public"
_CONFIGURED_SOURCE_TIER = "broker_authorized"
_CONFIGURED_PROVIDER_TIER = "tier_1_configured"
_CONFIGURED_CONFIDENCE_WEIGHT = 0.9
_CONFIGURED_PROVIDER_ID = "alpaca"
_QUOTE_PROVIDER_ORDER = ("alpaca", "yfinance")
_ALPACA_TIMEFRAMES = {
    "5m": ("5Min", timedelta(hours=2), 48),
    "15m": ("15Min", timedelta(hours=6), 48),
    "60m": ("1Hour", timedelta(days=3), 72),
    "1d": ("1Day", timedelta(days=45), 45),
}
_INTRADAY_WINDOWS = ("5m", "15m", "60m")
_FAILED_SYMBOL_LIST_LIMIT = 8
_QUOTE_PROVIDER_MAX_WORKERS = 6
_QUOTE_PROVIDER_REQUEST_TIMEOUT_SECONDS = 2.5
_UNAVAILABLE_SYMBOL_COOLDOWN_SECONDS = 1800.0
_UNAVAILABLE_SYMBOL_STATE: Dict[str, Dict[str, Any]] = {}


@dataclass
class _ProviderAttempt:
    quotes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    failed_symbol_reasons: Dict[str, str] = field(default_factory=dict)
    status: str = "not_configured"
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_rotation_radar_quote_provider() -> QuoteProvider:
    return load_rotation_radar_quotes


def load_rotation_radar_quotes(symbols: Iterable[str]) -> Dict[str, Any]:
    requested_symbols = tuple(dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()))
    configured_attempt = _load_configured_provider_quotes(requested_symbols)
    quotes: Dict[str, Dict[str, Any]] = dict(configured_attempt.quotes)
    yfinance_symbols = [symbol for symbol in requested_symbols if symbol not in quotes]
    yfinance_attempt = _load_yfinance_quotes(yfinance_symbols)
    quotes.update(yfinance_attempt.quotes)

    failed_symbol_reasons = {
        symbol: reason
        for symbol, reason in {
            **configured_attempt.failed_symbol_reasons,
            **yfinance_attempt.failed_symbol_reasons,
        }.items()
        if symbol not in quotes
    }
    provider_metadata = _quote_metadata(
        requested_symbols=requested_symbols,
        quotes=quotes,
        failed_symbol_reasons=failed_symbol_reasons,
        configured_attempt=configured_attempt,
        yfinance_attempt=yfinance_attempt,
    )

    return {
        "quotes": quotes,
        "metadata": provider_metadata,
    }


def _load_configured_provider_quotes(symbols: Sequence[str]) -> _ProviderAttempt:
    credentials = get_provider_credentials(_CONFIGURED_PROVIDER_ID)
    metadata = {
        "configuredProvider": _CONFIGURED_PROVIDER_ID,
        "configuredProviderStatus": "not_configured",
    }
    if credentials.is_partial:
        metadata["configuredProviderStatus"] = "incomplete_credentials"
        metadata["missingCredentialFields"] = list(credentials.missing_fields)
        return _ProviderAttempt(status="incomplete_credentials", metadata=metadata)
    if not credentials.is_configured:
        return _ProviderAttempt(status="not_configured", metadata=metadata)

    data_feed = str(credentials.extras.get("data_feed") or "iex").strip().lower() or "iex"
    metadata.update({
        "configuredProviderStatus": "configured",
        "configuredProviderFeed": data_feed,
    })
    try:
        fetcher = AlpacaFetcher(
            api_key_id=str(credentials.key_id or ""),
            secret_key=str(credentials.secret_key or ""),
            data_feed=data_feed,
            timeout=max(1, int(float(_QUOTE_PROVIDER_REQUEST_TIMEOUT_SECONDS))),
        )
    except Exception:
        return _ProviderAttempt(
            status="provider_unavailable",
            failed_symbol_reasons={symbol: "provider_unavailable" for symbol in symbols},
            metadata={**metadata, "configuredProviderStatus": "provider_unavailable"},
        )

    timeout_seconds = max(float(_QUOTE_PROVIDER_REQUEST_TIMEOUT_SECONDS), 0.001)
    max_workers = max(1, min(int(_QUOTE_PROVIDER_MAX_WORKERS), len(symbols) or 1))
    quotes: Dict[str, Dict[str, Any]] = {}
    failed_symbol_reasons: Dict[str, str] = {}
    executor = ThreadPoolExecutor(max_workers=max_workers)
    future_to_symbol = {
        executor.submit(_quote_from_alpaca_fetcher, fetcher, symbol, data_feed): symbol
        for symbol in symbols
    }
    try:
        for future in as_completed(future_to_symbol, timeout=timeout_seconds):
            symbol = future_to_symbol[future]
            try:
                quote = future.result()
            except Exception as exc:
                reason = _sanitize_unavailable_reason(str(exc))
                failed_symbol_reasons[symbol] = reason
                continue
            if quote is None:
                failed_symbol_reasons[symbol] = "symbol_unavailable"
                continue
            quotes[symbol] = quote
    except FuturesTimeoutError:
        pending_symbols = [
            future_to_symbol[future]
            for future in future_to_symbol
            if not future.done()
        ]
        for symbol in pending_symbols:
            failed_symbol_reasons[symbol] = "quote_fetch_failed"
            future = next(
                (candidate for candidate, candidate_symbol in future_to_symbol.items() if candidate_symbol == symbol),
                None,
            )
            if future is not None:
                future.cancel()
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    if quotes and failed_symbol_reasons:
        status = "partial"
    elif quotes:
        status = "success"
    else:
        status = "fallback" if symbols else "success"
    return _ProviderAttempt(
        quotes=quotes,
        failed_symbol_reasons=failed_symbol_reasons,
        status=status,
        metadata={
            **metadata,
            "configuredProviderStatus": status if status != "success" else "success",
            "configuredProviderFeed": data_feed,
        },
    )


def _load_yfinance_quotes(symbols: Sequence[str]) -> _ProviderAttempt:
    quotes: Dict[str, Dict[str, Any]] = {}
    failed_symbols: list[str] = []
    failed_symbol_count = 0
    failed_symbol_reasons: Dict[str, str] = {}
    unavailable_reason_counts: Dict[str, int] = {}
    now_monotonic = monotonic()

    for symbol in symbols:
        cooldown_reason = _cooldown_reason(symbol, now_monotonic)
        if cooldown_reason:
            failed_symbol_count = _record_failed_symbol(
                symbol=symbol,
                reason=cooldown_reason,
                failed_symbols=failed_symbols,
                failed_symbol_count=failed_symbol_count,
                unavailable_reason_counts=unavailable_reason_counts,
                failed_symbol_reasons=failed_symbol_reasons,
            )
            continue

    fetch_symbols = [symbol for symbol in symbols if symbol not in failed_symbols]
    timeout_seconds = max(float(_QUOTE_PROVIDER_REQUEST_TIMEOUT_SECONDS), 0.001)
    max_workers = max(1, min(int(_QUOTE_PROVIDER_MAX_WORKERS), len(fetch_symbols) or 1))
    executor = ThreadPoolExecutor(max_workers=max_workers)
    future_to_symbol = {
        executor.submit(fetch_yfinance_quote_history_frame, symbol): symbol
        for symbol in fetch_symbols
    }
    try:
        for future in as_completed(future_to_symbol, timeout=timeout_seconds):
            symbol = future_to_symbol[future]
            try:
                frame = future.result()
            except Exception as exc:
                reason = _sanitize_unavailable_reason(str(exc))
                if reason in {"symbol_unavailable", "quote_unavailable"}:
                    _mark_symbol_unavailable(symbol, reason, now_monotonic)
                failed_symbol_count = _record_failed_symbol(
                    symbol=symbol,
                    reason=reason,
                    failed_symbols=failed_symbols,
                    failed_symbol_count=failed_symbol_count,
                    unavailable_reason_counts=unavailable_reason_counts,
                    failed_symbol_reasons=failed_symbol_reasons,
                )
                continue
            quote = _quote_from_history_frame(symbol, frame)
            if quote is None:
                reason = "symbol_unavailable"
                _mark_symbol_unavailable(symbol, reason, now_monotonic)
                failed_symbol_count = _record_failed_symbol(
                    symbol=symbol,
                    reason=reason,
                    failed_symbols=failed_symbols,
                    failed_symbol_count=failed_symbol_count,
                    unavailable_reason_counts=unavailable_reason_counts,
                    failed_symbol_reasons=failed_symbol_reasons,
                )
                continue
            quotes[symbol] = quote
    except FuturesTimeoutError:
        pending_symbols = [
            future_to_symbol[future]
            for future in future_to_symbol
            if not future.done()
        ]
        for symbol in pending_symbols:
            failed_symbol_count = _record_failed_symbol(
                symbol=symbol,
                reason="quote_fetch_failed",
                failed_symbols=failed_symbols,
                failed_symbol_count=failed_symbol_count,
                unavailable_reason_counts=unavailable_reason_counts,
                failed_symbol_reasons=failed_symbol_reasons,
            )
            future = next(
                (candidate for candidate, candidate_symbol in future_to_symbol.items() if candidate_symbol == symbol),
                None,
            )
            if future is not None:
                future.cancel()
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    if quotes and failed_symbol_count:
        status = "partial"
    elif quotes:
        status = "success"
    else:
        status = "fallback" if symbols else "not_requested"
    unavailable_reason = _dominant_label(unavailable_reason_counts, default="symbol_unavailable") if unavailable_reason_counts else None
    return _ProviderAttempt(
        quotes=quotes,
        failed_symbol_reasons=failed_symbol_reasons,
        status=status,
        metadata={
            "unavailableReason": unavailable_reason,
            "failedSymbols": _bounded_unique_symbols(failed_symbols),
            "failedSymbolCount": failed_symbol_count,
        },
    )


def _quote_metadata(
    *,
    requested_symbols: Sequence[str],
    quotes: Mapping[str, Dict[str, Any]],
    failed_symbol_reasons: Mapping[str, str],
    configured_attempt: _ProviderAttempt,
    yfinance_attempt: _ProviderAttempt,
) -> Dict[str, Any]:
    freshness_counts: Dict[str, int] = {}
    source_counts: Dict[str, int] = {}
    source_label_counts: Dict[str, int] = {}
    source_tier_counts: Dict[str, int] = {}
    window_coverage = {window: 0 for window in ("5m", "15m", "60m", "1d")}
    as_of_candidates: list[str] = []
    for quote in quotes.values():
        freshness = str(quote.get("freshness") or "unknown")
        freshness_counts[freshness] = freshness_counts.get(freshness, 0) + 1
        source = str(quote.get("source") or "unknown")
        source_counts[source] = source_counts.get(source, 0) + 1
        source_label = str(quote.get("sourceLabel") or source)
        source_label_counts[source_label] = source_label_counts.get(source_label, 0) + 1
        source_tier = str(quote.get("sourceTier") or "unknown")
        source_tier_counts[source_tier] = source_tier_counts.get(source_tier, 0) + 1
        for window, slot in (quote.get("timeWindows") or {}).items():
            if window in window_coverage and isinstance(slot, Mapping) and slot.get("available", True):
                window_coverage[window] += 1
        if quote.get("asOf"):
            as_of_candidates.append(str(quote["asOf"]))

    requested_symbol_count = len(requested_symbols)
    usable_symbol_count = len(quotes)
    coverage_percent = round((usable_symbol_count / requested_symbol_count) * 100, 1) if requested_symbol_count else 0.0
    failed_symbol_count = len(failed_symbol_reasons)
    if usable_symbol_count == 0 and requested_symbol_count:
        status = "fallback"
    elif failed_symbol_count:
        status = "partial"
    else:
        status = "success"
    quote_mode = _metadata_quote_mode(quotes)
    source_summary = _metadata_source_summary(quotes)
    freshness = _metadata_freshness(
        quotes=quotes,
        failed_symbol_count=failed_symbol_count,
        fallback_used=bool(yfinance_attempt.quotes and configured_attempt.quotes),
    )
    confidence_weight = _confidence_weight(
        quotes=quotes,
        coverage_percent=coverage_percent,
        failed_symbol_count=failed_symbol_count,
    )
    unavailable_reason = (
        _dominant_label(_count_values(failed_symbol_reasons.values()), default="symbol_unavailable")
        if failed_symbol_reasons else None
    )
    return {
        "status": status,
        "quoteMode": quote_mode,
        "source": source_summary["source"],
        "sourceLabel": source_summary["sourceLabel"],
        "sourceType": source_summary["sourceType"],
        "sourceTier": source_summary["sourceTier"],
        "providerTier": source_summary["providerTier"],
        "freshness": freshness,
        "asOf": max(as_of_candidates) if as_of_candidates else None,
        "confidenceWeight": confidence_weight,
        "degradationReasons": _degradation_reasons(
            coverage_percent=coverage_percent,
            failed_symbol_count=failed_symbol_count,
            source_summary=source_summary,
            freshness=freshness,
        ),
        "providerOrder": list(_QUOTE_PROVIDER_ORDER),
        "providerTimeoutSeconds": float(_QUOTE_PROVIDER_REQUEST_TIMEOUT_SECONDS),
        "configuredProviderStatus": configured_attempt.metadata.get("configuredProviderStatus", configured_attempt.status),
        "configuredProvider": _CONFIGURED_PROVIDER_ID,
        "configuredProviderFeed": configured_attempt.metadata.get("configuredProviderFeed"),
        "configuredProviderFailedSymbols": _bounded_unique_symbols(list(configured_attempt.failed_symbol_reasons)),
        "configuredProviderFailedSymbolCount": len(configured_attempt.failed_symbol_reasons),
        "configuredProviderFailedSymbolReasons": {
            symbol: configured_attempt.failed_symbol_reasons[symbol]
            for symbol in _bounded_unique_symbols(list(configured_attempt.failed_symbol_reasons))
        },
        "yfinanceProviderStatus": yfinance_attempt.status,
        "noExternalCalls": False,
        "failedSymbols": _bounded_unique_symbols(list(failed_symbol_reasons)),
        "failedSymbolCount": failed_symbol_count,
        "failedSymbolReasons": {
            symbol: failed_symbol_reasons[symbol]
            for symbol in _bounded_unique_symbols(list(failed_symbol_reasons))
        },
        "unavailableReason": unavailable_reason,
        "coverage": {
            "requestedSymbolCount": requested_symbol_count,
            "usableSymbolCount": usable_symbol_count,
            "coveragePercent": coverage_percent,
        },
        "windowCoverage": {
            window: {
                "requestedSymbolCount": requested_symbol_count,
                "usableSymbolCount": count,
                "coveragePercent": round((count / requested_symbol_count) * 100, 1) if requested_symbol_count else 0.0,
            }
            for window, count in window_coverage.items()
        },
        "sourceCounts": source_counts,
        "sourceLabelCounts": source_label_counts,
        "sourceTierCounts": source_tier_counts,
        "freshnessCounts": freshness_counts,
    }


def _record_failed_symbol(
    *,
    symbol: str,
    reason: str,
    failed_symbols: list[str],
    failed_symbol_count: int,
    unavailable_reason_counts: Dict[str, int],
    failed_symbol_reasons: Optional[Dict[str, str]] = None,
) -> int:
    failed_symbols.append(symbol)
    unavailable_reason_counts[reason] = unavailable_reason_counts.get(reason, 0) + 1
    if failed_symbol_reasons is not None:
        failed_symbol_reasons[symbol] = reason
    return failed_symbol_count + 1


def _quote_from_alpaca_fetcher(fetcher: AlpacaFetcher, symbol: str, data_feed: str) -> Optional[Dict[str, Any]]:
    end_dt = datetime.now(timezone.utc)
    windows: Dict[str, Dict[str, Any]] = {}
    window_sources: Dict[str, Dict[str, Any]] = {}
    for window, (timeframe, lookback, limit) in _ALPACA_TIMEFRAMES.items():
        try:
            bars = fetcher.get_bars(
                symbol,
                timeframe=timeframe,
                start=(end_dt - lookback).isoformat(),
                end=end_dt.isoformat(),
                limit=limit,
            )
        except Exception:
            continue
        slot = _window_from_alpaca_bars(symbol, window, bars, data_feed=data_feed)
        if slot is not None:
            windows[window] = slot
            window_sources[window] = {
                "bars": bars,
                "slot": slot,
            }

    if not windows:
        return None

    preferred_window = next((window for window in ("1d", "60m", "15m", "5m") if window in windows), None)
    if preferred_window is None:
        return None
    preferred_slot = windows[preferred_window]
    preferred_bars = window_sources[preferred_window]["bars"]
    last_bar = _last_bar(preferred_bars)
    if last_bar is None:
        return None
    close = _number(_field(last_bar, "c", "close", "Close"))
    if close is None:
        return None
    high = _number(_field(last_bar, "h", "high", "High"))
    low = _number(_field(last_bar, "l", "low", "Low"))
    volume = _number(_field(last_bar, "v", "volume", "Volume"))
    average_volume = _average_bar_volume(preferred_bars)
    vwap = _number(_field(last_bar, "vw", "vwap", "VWAP"))
    if vwap is None and None not in {high, low, close}:
        vwap = round((float(high) + float(low) + float(close)) / 3, 3)

    volume_ratio = None
    if volume is not None and average_volume not in {None, 0}:
        volume_ratio = round(float(volume) / float(average_volume), 3)

    freshness = _freshest_configured_freshness(windows.values())
    as_of = str(preferred_slot.get("asOf") or "")
    source_label = _configured_source_label(data_feed)
    return {
        "symbol": symbol,
        "name": symbol,
        "price": close,
        "changePercent": preferred_slot.get("changePercent"),
        "volume": volume,
        "averageVolume": average_volume,
        "volumeRatio": volume_ratio,
        "vwap": vwap,
        "trend": _trend_from_bars(preferred_bars),
        "timeWindows": windows,
        "freshness": freshness,
        "isFallback": False,
        "isStale": freshness == "stale",
        "source": _CONFIGURED_SOURCE,
        "sourceLabel": source_label,
        "sourceType": _CONFIGURED_SOURCE_TYPE,
        "sourceTier": _CONFIGURED_SOURCE_TIER,
        "providerTier": _CONFIGURED_PROVIDER_TIER,
        "confidenceWeight": _CONFIGURED_CONFIDENCE_WEIGHT,
        "asOf": as_of or None,
    }


def _window_from_alpaca_bars(
    symbol: str,
    window: str,
    bars: Any,
    *,
    data_feed: str,
) -> Optional[Dict[str, Any]]:
    materialized = _materialize_bars(bars)
    if not materialized:
        return None
    first_bar = materialized[0]
    last_bar = materialized[-1]
    first_close = _number(_field(first_bar, "c", "close", "Close"))
    close = _number(_field(last_bar, "c", "close", "Close"))
    if close is None:
        return None
    change_percent = None
    if first_close not in {None, 0}:
        change_percent = round(((float(close) - float(first_close)) / float(first_close)) * 100, 3)
    volume = _number(_field(last_bar, "v", "volume", "Volume"))
    average_volume = _average_bar_volume(materialized)
    relative_volume = None
    if volume is not None and average_volume not in {None, 0}:
        relative_volume = round(float(volume) / float(average_volume), 3)
    as_of = _as_of_from_bar(last_bar)
    freshness = _configured_freshness_from_as_of(as_of, data_feed=data_feed, window=window)
    return {
        "window": window,
        "available": change_percent is not None or relative_volume is not None,
        "changePercent": change_percent,
        "relativeVolume": relative_volume,
        "freshness": freshness,
        "isFallback": False,
        "isStale": freshness == "stale",
        "source": _CONFIGURED_SOURCE,
        "sourceLabel": _configured_source_label(data_feed),
        "sourceType": _CONFIGURED_SOURCE_TYPE,
        "sourceTier": _CONFIGURED_SOURCE_TIER,
        "providerTier": _CONFIGURED_PROVIDER_TIER,
        "asOf": as_of,
        "reason": None if change_percent is not None or relative_volume is not None else "window_unavailable",
    }


def _materialize_bars(bars: Any) -> list[Any]:
    if bars is None:
        return []
    if isinstance(bars, pd.DataFrame):
        if bars.empty:
            return []
        return [row for _, row in bars.iterrows()]
    if isinstance(bars, Mapping):
        raw_bars = bars.get("bars")
        if isinstance(raw_bars, Sequence) and not isinstance(raw_bars, (str, bytes)):
            return list(raw_bars)
        return []
    if isinstance(bars, Sequence) and not isinstance(bars, (str, bytes)):
        return list(bars)
    return []


def _last_bar(bars: Any) -> Optional[Any]:
    materialized = _materialize_bars(bars)
    return materialized[-1] if materialized else None


def _average_bar_volume(bars: Any) -> Optional[float]:
    volumes = [
        value
        for value in (_number(_field(bar, "v", "volume", "Volume")) for bar in _materialize_bars(bars))
        if value is not None
    ]
    if len(volumes) > 1:
        volumes = volumes[:-1]
    if not volumes:
        return None
    return round(sum(volumes) / len(volumes), 3)


def _trend_from_bars(bars: Any) -> list[float]:
    values: list[float] = []
    for bar in _materialize_bars(bars):
        close = _number(_field(bar, "c", "close", "Close"))
        if close is not None:
            values.append(close)
    return values


def _as_of_from_bar(bar: Any) -> str:
    raw = _field(bar, "t", "timestamp", "date", "Date")
    if raw is None:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        timestamp = pd.Timestamp(raw)
    except Exception:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(timezone.utc)
    else:
        timestamp = timestamp.tz_convert(timezone.utc)
    return timestamp.isoformat()


def _configured_freshness_from_as_of(as_of: str, *, data_feed: str, window: str) -> str:
    try:
        parsed = datetime.fromisoformat(str(as_of).replace("Z", "+00:00"))
    except Exception:
        return "delayed"
    current = datetime.now(timezone.utc)
    age_seconds = (current - parsed.astimezone(timezone.utc)).total_seconds()
    if age_seconds < 0:
        age_seconds = 0
    if age_seconds >= 3 * 24 * 60 * 60:
        return "stale"
    if window in _INTRADAY_WINDOWS and data_feed.lower() == "sip" and age_seconds <= 20 * 60:
        return "live"
    return "delayed"


def _freshest_configured_freshness(slots: Iterable[Mapping[str, Any]]) -> str:
    values = [str(slot.get("freshness") or "") for slot in slots]
    for candidate in ("live", "delayed", "cached", "stale", "fallback"):
        if candidate in values:
            return candidate
    return "delayed"


def _configured_source_label(data_feed: str) -> str:
    feed = str(data_feed or "iex").strip().upper() or "IEX"
    return f"Alpaca {feed}"


def _metadata_quote_mode(quotes: Mapping[str, Dict[str, Any]]) -> str:
    sources = {str(quote.get("source") or "") for quote in quotes.values()}
    if not quotes:
        return "fallback"
    if sources == {_CONFIGURED_SOURCE}:
        return "configured"
    if sources == {_QUOTE_SOURCE}:
        return _QUOTE_MODE
    return "mixed"


def _metadata_source_summary(quotes: Mapping[str, Dict[str, Any]]) -> Dict[str, str]:
    if not quotes:
        return {
            "source": "fallback",
            "sourceLabel": "备用数据",
            "sourceType": "fallback_static",
            "sourceTier": "static_fallback",
            "providerTier": "fallback",
        }
    sources = {str(quote.get("source") or "") for quote in quotes.values()}
    if sources == {_CONFIGURED_SOURCE}:
        label = _dominant_label(
            _count_values(str(quote.get("sourceLabel") or _configured_source_label("iex")) for quote in quotes.values()),
            default=_configured_source_label("iex"),
        )
        return {
            "source": _CONFIGURED_SOURCE,
            "sourceLabel": label,
            "sourceType": _CONFIGURED_SOURCE_TYPE,
            "sourceTier": _CONFIGURED_SOURCE_TIER,
            "providerTier": _CONFIGURED_PROVIDER_TIER,
        }
    if sources == {_QUOTE_SOURCE}:
        return {
            "source": _QUOTE_SOURCE,
            "sourceLabel": _QUOTE_SOURCE_LABEL,
            "sourceType": _QUOTE_SOURCE_TYPE,
            "sourceTier": _QUOTE_SOURCE_TIER,
            "providerTier": _QUOTE_PROVIDER_TIER,
        }
    return {
        "source": "mixed",
        "sourceLabel": "Alpaca + Yahoo Finance",
        "sourceType": "mixed",
        "sourceTier": _QUOTE_SOURCE_TIER,
        "providerTier": "mixed_configured_and_tier_2",
    }


def _metadata_freshness(
    *,
    quotes: Mapping[str, Dict[str, Any]],
    failed_symbol_count: int,
    fallback_used: bool,
) -> str:
    if not quotes:
        return "fallback"
    if failed_symbol_count or fallback_used:
        return "partial"
    return _dominant_label(_count_values(str(quote.get("freshness") or "unknown") for quote in quotes.values()), default="fallback")


def _confidence_weight(
    *,
    quotes: Mapping[str, Dict[str, Any]],
    coverage_percent: float,
    failed_symbol_count: int,
) -> float:
    if not quotes:
        return 0.0
    base = min(float(quote.get("confidenceWeight") or _QUOTE_CONFIDENCE_WEIGHT) for quote in quotes.values())
    coverage_ratio = max(0.0, min(1.0, coverage_percent / 100.0))
    penalty = 0.1 if failed_symbol_count else 0.0
    return round(max(0.0, min(1.0, base * coverage_ratio - penalty)), 2)


def _degradation_reasons(
    *,
    coverage_percent: float,
    failed_symbol_count: int,
    source_summary: Mapping[str, str],
    freshness: str,
) -> list[str]:
    reasons: list[str] = []
    if failed_symbol_count:
        reasons.append("symbol_failures")
    if coverage_percent <= 0:
        reasons.append("no_coverage")
    elif coverage_percent < 80:
        reasons.append("partial_coverage")
    if source_summary.get("providerTier") == _QUOTE_PROVIDER_TIER:
        reasons.append("tier_2_delayed_proxy")
    elif source_summary.get("providerTier") == "mixed_configured_and_tier_2":
        reasons.append("mixed_provider_tiers")
    if freshness in {"partial", "stale", "fallback"}:
        reasons.append(f"{freshness}_freshness")
    return list(dict.fromkeys(reasons))


def _count_values(values: Iterable[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        counts[text] = counts.get(text, 0) + 1
    return counts


def _quote_from_history_frame(symbol: str, frame: Any) -> Optional[Dict[str, Any]]:
    if frame is None or getattr(frame, "empty", True):
        return None
    try:
        last_row = frame.iloc[-1]
    except Exception:
        return None

    close = _number(_field(last_row, "Close", "close", "Adj Close", "adj_close"))
    previous_row = frame.iloc[-2] if len(frame) >= 2 else last_row
    previous_close = _number(_field(previous_row, "Close", "close", "Adj Close", "adj_close"))
    high = _number(_field(last_row, "High", "high"))
    low = _number(_field(last_row, "Low", "low"))
    volume = _number(_field(last_row, "Volume", "volume"))
    average_volume = _average_volume(frame)
    vwap = _number(_field(last_row, "VWAP", "vwap"))
    if vwap is None and None not in {high, low, close}:
        vwap = round((float(high) + float(low) + float(close)) / 3, 3)
    if close is None:
        return None

    change_percent = None
    if previous_close not in {None, 0}:
        change_percent = round(((float(close) - float(previous_close)) / float(previous_close)) * 100, 3)

    volume_ratio = None
    if volume is not None and average_volume not in {None, 0}:
        volume_ratio = round(float(volume) / float(average_volume), 3)

    as_of = _as_of_from_index(frame.index[-1] if len(frame.index) else None)
    freshness = _freshness_from_as_of(as_of)
    is_stale = freshness == "stale"

    time_windows = {
        "1d": {
            "changePercent": change_percent,
            "relativeVolume": volume_ratio,
            "freshness": freshness,
            "asOf": as_of,
        }
    }

    return {
        "symbol": symbol,
        "name": symbol,
        "price": close,
        "changePercent": change_percent,
        "volume": volume,
        "averageVolume": average_volume,
        "volumeRatio": volume_ratio,
        "vwap": vwap,
        "trend": _trend_from_frame(frame),
        "timeWindows": time_windows,
        "freshness": freshness,
        "isFallback": False,
        "isStale": is_stale,
        "source": _QUOTE_SOURCE,
        "sourceLabel": _QUOTE_SOURCE_LABEL,
        "sourceType": _QUOTE_SOURCE_TYPE,
        "sourceTier": _QUOTE_SOURCE_TIER,
        "providerTier": _QUOTE_PROVIDER_TIER,
        "confidenceWeight": _QUOTE_CONFIDENCE_WEIGHT,
        "asOf": as_of,
    }


def _field(row: Any, *names: str) -> Any:
    for name in names:
        if isinstance(row, Mapping) and name in row:
            return row.get(name)
        try:
            value = row[name]
        except Exception:
            continue
        if value is not None:
            return value
    return None


def _number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except Exception:
        return None
    if number != number:
        return None
    return number


def _average_volume(frame: Any) -> Optional[float]:
    try:
        volumes = [float(value) for value in frame.get("Volume", []) if value is not None]
    except Exception:
        return None
    if len(volumes) > 1:
        volumes = volumes[:-1]
    if not volumes:
        return None
    return round(sum(volumes) / len(volumes), 3)


def _trend_from_frame(frame: Any) -> list[float]:
    try:
        close_series = frame.get("Close", [])
    except Exception:
        return []
    values = []
    for value in close_series:
        number = _number(value)
        if number is not None:
            values.append(number)
    return values


def _as_of_from_index(index_value: Any) -> str:
    if index_value is None:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        timestamp = pd.Timestamp(index_value)
    except Exception:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(timezone.utc)
    else:
        timestamp = timestamp.tz_convert(timezone.utc)
    return timestamp.isoformat()


def _freshness_from_as_of(as_of: str) -> str:
    try:
        parsed = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    except Exception:
        return "delayed"
    current = datetime.now(timezone.utc)
    return "stale" if (current - parsed).days >= 3 else "delayed"


def _dominant_label(counts: Mapping[str, int], *, default: str) -> str:
    if not counts:
        return default
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]


def _bounded_unique_symbols(symbols: Sequence[str]) -> list[str]:
    bounded: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized = str(symbol).strip().upper()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        bounded.append(normalized)
        if len(bounded) >= _FAILED_SYMBOL_LIST_LIMIT:
            break
    return bounded


def _sanitize_unavailable_reason(raw_reason: str) -> str:
    normalized = str(raw_reason or "").strip().lower()
    if not normalized:
        return "quote_unavailable"
    if "delisted" in normalized or "no price data" in normalized or "no data" in normalized:
        return "symbol_unavailable"
    if "timeout" in normalized or "request" in normalized or "fetch" in normalized:
        return "quote_fetch_failed"
    return "quote_unavailable"


def _cooldown_reason(symbol: str, now_monotonic: float) -> Optional[str]:
    state = _UNAVAILABLE_SYMBOL_STATE.get(symbol)
    if not state:
        return None
    retry_after = state.get("retryAfterMonotonic")
    if not isinstance(retry_after, (int, float)) or retry_after <= now_monotonic:
        _UNAVAILABLE_SYMBOL_STATE.pop(symbol, None)
        return None
    return str(state.get("reason") or "symbol_unavailable")


def _mark_symbol_unavailable(symbol: str, reason: str, now_monotonic: float) -> None:
    _UNAVAILABLE_SYMBOL_STATE[symbol] = {
        "reason": reason,
        "retryAfterMonotonic": now_monotonic + _UNAVAILABLE_SYMBOL_COOLDOWN_SECONDS,
    }
