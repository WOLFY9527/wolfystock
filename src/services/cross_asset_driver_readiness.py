# -*- coding: utf-8 -*-
"""Provider-neutral cross-asset driver readiness contract.

This module only projects configured identifiers and already-built cache
preflight summaries. It does not call providers, read cache contents, or infer a
market regime conclusion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


CROSS_ASSET_DRIVER_READINESS_CONTRACT_VERSION = "cross_asset_driver_readiness_v1"
CROSS_ASSET_DRIVER_SUPPORTED_STATES = (
    "available",
    "missing",
    "stale",
    "insufficient_history",
    "not_configured",
)
DEFAULT_REQUIRED_BARS = 60


@dataclass(frozen=True, slots=True)
class CrossAssetDriverSpec:
    category: str
    label: str
    identifiers: tuple[Mapping[str, str], ...]
    cache_required: bool = True


@dataclass(frozen=True, slots=True)
class CrossAssetDriverReadiness:
    drivers: tuple[Mapping[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        counts = {state: 0 for state in CROSS_ASSET_DRIVER_SUPPORTED_STATES}
        for driver in self.drivers:
            state = str(driver.get("state") or "missing")
            if state in counts:
                counts[state] += 1
        return {
            "contractVersion": CROSS_ASSET_DRIVER_READINESS_CONTRACT_VERSION,
            "consumerSafe": True,
            "diagnosticOnly": True,
            "networkCallsEnabled": False,
            "externalProviderCalls": False,
            "mutationEnabled": False,
            "supportedStates": list(CROSS_ASSET_DRIVER_SUPPORTED_STATES),
            "consumerSummary": (
                "Cross-asset drivers are reported as data-readiness inputs only; no market conclusion is inferred."
            ),
            "summary": {
                "totalDrivers": len(self.drivers),
                "availableCount": counts["available"],
                "missingCount": counts["missing"],
                "staleCount": counts["stale"],
                "insufficientHistoryCount": counts["insufficient_history"],
                "notConfiguredCount": counts["not_configured"],
            },
            "drivers": [dict(driver) for driver in self.drivers],
        }


_DRIVER_SPECS: tuple[CrossAssetDriverSpec, ...] = (
    CrossAssetDriverSpec(
        category="equities_index",
        label="Equities/index trend",
        identifiers=(
            {"kind": "symbol", "value": "SPY", "market": "us"},
            {"kind": "symbol", "value": "QQQ", "market": "us"},
            {"kind": "symbol", "value": "IWM", "market": "us"},
        ),
    ),
    CrossAssetDriverSpec(
        category="rates",
        label="Rates/yields",
        identifiers=(
            {"kind": "series", "value": "DGS2", "market": "us"},
            {"kind": "series", "value": "DGS10", "market": "us"},
            {"kind": "series", "value": "DGS30", "market": "us"},
            {"kind": "series", "value": "T10Y2Y", "market": "us"},
            {"kind": "series", "value": "T10Y3M", "market": "us"},
        ),
        cache_required=False,
    ),
    CrossAssetDriverSpec(
        category="usd",
        label="USD",
        identifiers=({"kind": "symbol", "value": "DXY", "market": "us"},),
    ),
    CrossAssetDriverSpec(
        category="oil_energy",
        label="Oil/energy",
        identifiers=({"kind": "symbol", "value": "USO", "market": "us"},),
    ),
    CrossAssetDriverSpec(
        category="gold",
        label="Gold",
        identifiers=({"kind": "symbol", "value": "GLD", "market": "us"},),
    ),
    CrossAssetDriverSpec(
        category="volatility",
        label="Volatility/VIX",
        identifiers=(
            {"kind": "symbol", "value": "VIX", "market": "us"},
            {"kind": "series", "value": "VIXCLS", "market": "us"},
        ),
    ),
    CrossAssetDriverSpec(
        category="credit",
        label="Credit spreads",
        identifiers=(),
        cache_required=False,
    ),
    CrossAssetDriverSpec(
        category="crypto",
        label="Crypto risk proxy",
        identifiers=({"kind": "symbol", "value": "BTC-USD", "market": "us"},),
    ),
    CrossAssetDriverSpec(
        category="sectors",
        label="Sector rotation",
        identifiers=(
            {"kind": "symbol", "value": "XLK", "market": "us"},
            {"kind": "symbol", "value": "XLF", "market": "us"},
        ),
    ),
)


def build_cross_asset_driver_readiness(
    *,
    historical_ohlcv_cache_preflight: Mapping[str, Any] | None = None,
    required_bars: int = DEFAULT_REQUIRED_BARS,
) -> CrossAssetDriverReadiness:
    """Build a provider-neutral driver readiness packet from cached summaries."""

    cache_index = _cache_index(historical_ohlcv_cache_preflight)
    drivers = tuple(
        _driver_payload(spec, cache_index=cache_index, required_bars=required_bars)
        for spec in _DRIVER_SPECS
    )
    return CrossAssetDriverReadiness(drivers=drivers)


def cross_asset_driver_cache_symbols() -> tuple[str, ...]:
    """Return configured US symbols that can be checked through OHLCV preflight."""

    symbols: list[str] = []
    for spec in _DRIVER_SPECS:
        if not spec.cache_required:
            continue
        for identifier in spec.identifiers:
            if identifier.get("kind") == "symbol" and identifier.get("market") == "us":
                symbols.append(str(identifier.get("value") or "").strip().upper())
    return tuple(dict.fromkeys(symbol for symbol in symbols if symbol))


def _driver_payload(
    spec: CrossAssetDriverSpec,
    *,
    cache_index: Mapping[str, Mapping[str, Any]],
    required_bars: int,
) -> dict[str, Any]:
    configured_identifiers = [dict(identifier) for identifier in spec.identifiers]
    if not configured_identifiers:
        return {
            "category": spec.category,
            "label": spec.label,
            "supported": False,
            "state": "not_configured",
            "configuredIdentifiers": [],
            "cachedOhlcv": _empty_cached_ohlcv(required_bars=required_bars),
            "missingReasons": ["not_configured"],
            "consumerSafeSummary": "Driver category is not configured for readiness evaluation.",
        }

    symbol_values = [
        str(identifier.get("value") or "").strip().upper()
        for identifier in spec.identifiers
        if identifier.get("kind") == "symbol" and spec.cache_required
    ]
    symbol_values = [symbol for symbol in symbol_values if symbol]
    cached_ohlcv = _aggregate_cached_ohlcv(
        symbol_values,
        cache_index=cache_index,
        required_bars=required_bars,
    )
    state = _state_from_cache(symbol_values, cached_ohlcv, cache_required=spec.cache_required)
    return {
        "category": spec.category,
        "label": spec.label,
        "supported": True,
        "state": state,
        "configuredIdentifiers": configured_identifiers,
        "cachedOhlcv": cached_ohlcv,
        "missingReasons": _missing_reasons(state),
        "consumerSafeSummary": _consumer_summary(state),
    }


def _cache_index(payload: Mapping[str, Any] | None) -> dict[str, Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        return {}
    markets = payload.get("markets")
    if not isinstance(markets, Mapping):
        return {}
    index: dict[str, Mapping[str, Any]] = {}
    for market_payload in markets.values():
        if not isinstance(market_payload, Mapping):
            continue
        symbols = market_payload.get("symbols")
        if not isinstance(symbols, Sequence) or isinstance(symbols, (str, bytes, bytearray)):
            continue
        for item in symbols:
            if not isinstance(item, Mapping):
                continue
            symbol = str(item.get("symbol") or "").strip().upper()
            if symbol:
                index[symbol] = item
    return index


def _aggregate_cached_ohlcv(
    symbols: Sequence[str],
    *,
    cache_index: Mapping[str, Mapping[str, Any]],
    required_bars: int,
) -> dict[str, Any]:
    if not symbols:
        return _empty_cached_ohlcv(required_bars=required_bars)

    items = [cache_index.get(symbol, {}) for symbol in symbols]
    cached_bars = [_int(item.get("cachedBars")) for item in items]
    usable_bars = min(cached_bars) if cached_bars else 0
    latest_dates = [
        str(item.get("latestBarDate") or "").strip()
        for item in items
        if str(item.get("latestBarDate") or "").strip()
    ]
    states = [str(item.get("dataState") or "").strip().lower() for item in items]
    freshness_states = [str(item.get("freshnessState") or "").strip().lower() for item in items]
    if any(state == "stale" for state in states) or any(state == "stale" for state in freshness_states):
        freshness_state = "stale"
    elif any(state == "fresh" for state in states) or any(state == "fresh" for state in freshness_states):
        freshness_state = "fresh"
    else:
        freshness_state = "unknown"

    return {
        "requiredBars": max(0, int(required_bars or 0)),
        "usableBars": usable_bars,
        "missingBars": max(0, int(required_bars or 0) - usable_bars),
        "cacheState": "cache_hit" if usable_bars > 0 else "cache_missing",
        "freshnessState": freshness_state,
        "latestBarDate": max(latest_dates) if latest_dates else None,
    }


def _state_from_cache(
    symbols: Sequence[str],
    cached_ohlcv: Mapping[str, Any],
    *,
    cache_required: bool,
) -> str:
    if not cache_required:
        return "missing"
    if symbols and str(cached_ohlcv.get("cacheState") or "") != "cache_hit":
        return "missing"
    if str(cached_ohlcv.get("freshnessState") or "") == "stale":
        return "stale"
    if _int(cached_ohlcv.get("missingBars")) > 0:
        return "insufficient_history"
    return "available"


def _empty_cached_ohlcv(*, required_bars: int) -> dict[str, Any]:
    return {
        "requiredBars": max(0, int(required_bars or 0)),
        "usableBars": 0,
        "missingBars": max(0, int(required_bars or 0)),
        "cacheState": "not_applicable",
        "freshnessState": "unknown",
        "latestBarDate": None,
    }


def _missing_reasons(state: str) -> list[str]:
    if state == "available":
        return []
    if state == "not_configured":
        return ["not_configured"]
    if state == "stale":
        return ["stale"]
    if state == "insufficient_history":
        return ["insufficient_history"]
    return ["missing"]


def _consumer_summary(state: str) -> str:
    if state == "available":
        return "Configured data is present for readiness evaluation."
    if state == "stale":
        return "Configured data exists but is stale for readiness evaluation."
    if state == "insufficient_history":
        return "Configured data exists but lacks required history."
    if state == "not_configured":
        return "Driver category is not configured for readiness evaluation."
    return "Configured data is missing for readiness evaluation."


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


__all__ = [
    "CROSS_ASSET_DRIVER_READINESS_CONTRACT_VERSION",
    "build_cross_asset_driver_readiness",
    "cross_asset_driver_cache_symbols",
]
