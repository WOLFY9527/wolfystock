# -*- coding: utf-8 -*-
"""Consumer-safe market breadth readiness contract.

This module is intentionally inert: it does not inspect environment variables,
call providers, read cache keys, or fetch external data. It only projects
already-built breadth snapshots into a readiness shape.
"""

from __future__ import annotations

from typing import Any, Mapping


MARKET_BREADTH_READINESS_CONTRACT_VERSION = "market_breadth_readiness_v1"
MARKET_BREADTH_READINESS_STATES = (
    "available",
    "missing",
    "stale",
    "not_configured",
    "disabled_by_flag",
)
MARKET_BREADTH_MARKETS = ("US", "CN", "HK")
MARKET_BREADTH_MEASURE_IDS = (
    "advance_decline",
    "new_highs_lows",
    "percent_above_ma",
    "sector_participation",
    "volume_breadth",
    "equal_weight_cap_weight_proxy",
)

_MEASURE_LABELS = {
    "advance_decline": "Advance / decline",
    "new_highs_lows": "New highs / lows",
    "percent_above_ma": "Percent above moving averages",
    "sector_participation": "Sector participation",
    "volume_breadth": "Volume breadth",
    "equal_weight_cap_weight_proxy": "Equal-weight vs cap-weight proxy",
}

_REQUIRED_SYMBOLS = {
    "advance_decline": ({"ADVANCERS", "DECLINERS"}, {"ADVANCE_DECLINE_RATIO", "ADV_RATIO"}),
    "new_highs_lows": ({"NEW_HIGHS", "NEW_LOWS"}, {"HIGH_LOW_RATIO"}),
    "percent_above_ma": ({"PERCENT_ABOVE_50DMA"}, set()),
    "sector_participation": ({"SECTORS_UP", "SECTORS_DOWN"}, set()),
    "volume_breadth": ({"ADVANCING_VOLUME", "DECLINING_VOLUME"}, set()),
    "equal_weight_cap_weight_proxy": ({"RSP_SPY"}, set()),
}

_MISSING_PROVIDER_SOURCES = {"", "fallback", "missing", "unavailable", "disabled"}
_STALE_FRESHNESS = {"cached", "stale"}


def _normalize_market(market: str) -> str:
    normalized = str(market or "").strip().upper()
    if normalized in {"USA", "NYSE", "NASDAQ"}:
        return "US"
    if normalized in {"CHINA", "MAINLAND"}:
        return "CN"
    if normalized in {"HONG_KONG"}:
        return "HK"
    return normalized


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _item_symbols(snapshot: Mapping[str, Any]) -> set[str]:
    symbols: set[str] = set()
    for item in snapshot.get("items") or ():
        item_map = _mapping(item)
        symbol = str(item_map.get("symbol") or "").strip().upper()
        if symbol and item_map.get("value") is not None:
            symbols.add(symbol)
    for symbol in snapshot.get("fulfilledMetrics") or ():
        normalized = str(symbol or "").strip().upper()
        if normalized:
            symbols.add(normalized)
    return symbols


def _provider_is_configured(snapshot: Mapping[str, Any]) -> bool:
    source = str(snapshot.get("source") or "").strip().lower()
    source_type = str(snapshot.get("sourceType") or "").strip().lower()
    if bool(snapshot.get("disabledByFlag")):
        return False
    if source in _MISSING_PROVIDER_SOURCES or source_type == "missing":
        return False
    return bool(snapshot)


def _provider_state(
    market_snapshots: Mapping[str, Mapping[str, Any]],
    *,
    provider_disabled: bool,
) -> dict[str, Any]:
    if provider_disabled:
        return {
            "state": "disabled",
            "reason": "breadth_provider_disabled_by_flag",
        }
    if any(_provider_is_configured(snapshot) for snapshot in market_snapshots.values()):
        return {
            "state": "configured",
            "reason": "breadth_provider_snapshot_observed",
        }
    return {
        "state": "missing",
        "reason": "authorized_market_breadth_provider_not_configured",
    }


def _snapshot_is_stale(snapshot: Mapping[str, Any]) -> bool:
    freshness = str(snapshot.get("freshness") or "").strip().lower()
    provider_health = _mapping(snapshot.get("providerHealth"))
    provider_status = str(provider_health.get("status") or "").strip().lower()
    return (
        freshness in _STALE_FRESHNESS
        or provider_status in _STALE_FRESHNESS
        or bool(snapshot.get("isStale"))
    )


def _measure_available(measure_id: str, snapshot: Mapping[str, Any]) -> bool:
    symbols = _item_symbols(snapshot)
    required_groups = _REQUIRED_SYMBOLS.get(measure_id, ())
    return all(not group or bool(symbols.intersection(group)) for group in required_groups)


def _market_measure_state(
    measure_id: str,
    snapshot: Mapping[str, Any] | None,
    *,
    provider_disabled: bool,
) -> str:
    if provider_disabled:
        return "disabled_by_flag"
    if not snapshot or not _provider_is_configured(snapshot):
        return "not_configured"
    if not _measure_available(measure_id, snapshot):
        return "missing"
    if _snapshot_is_stale(snapshot):
        return "stale"
    return "available"


def _aggregate_state(market_states: Mapping[str, str]) -> str:
    states = set(market_states.values())
    if states == {"disabled_by_flag"}:
        return "disabled_by_flag"
    if "available" in states:
        return "available"
    if "stale" in states:
        return "stale"
    if "missing" in states:
        return "missing"
    return "not_configured"


def _state_reason(state: str) -> str:
    if state == "available":
        return "breadth_measure_observed"
    if state == "stale":
        return "breadth_measure_observed_but_stale"
    if state == "disabled_by_flag":
        return "breadth_provider_disabled_by_flag"
    if state == "not_configured":
        return "authorized_breadth_provider_not_configured"
    return "breadth_measure_not_observed"


def build_market_breadth_readiness_contract(
    *,
    market_snapshots: Mapping[str, Mapping[str, Any]] | None = None,
    provider_disabled: bool = False,
) -> dict[str, Any]:
    """Build a sanitized readiness contract for market breadth consumers."""

    snapshots = {
        _normalize_market(market): _mapping(snapshot)
        for market, snapshot in dict(market_snapshots or {}).items()
    }

    measures: list[dict[str, Any]] = []
    market_measure_states: dict[str, dict[str, str]] = {
        market: {} for market in MARKET_BREADTH_MARKETS
    }
    for measure_id in MARKET_BREADTH_MEASURE_IDS:
        market_states = {
            market: _market_measure_state(
                measure_id,
                snapshots.get(market),
                provider_disabled=provider_disabled,
            )
            for market in MARKET_BREADTH_MARKETS
        }
        for market, state in market_states.items():
            market_measure_states[market][measure_id] = state
        supported_markets = [
            market
            for market, state in market_states.items()
            if state in {"available", "stale"}
        ]
        measures.append(
            {
                "measureId": measure_id,
                "label": _MEASURE_LABELS[measure_id],
                "state": _aggregate_state(market_states),
                "marketStates": market_states,
                "supportedMarkets": supported_markets,
                "missingMarkets": [
                    market
                    for market in MARKET_BREADTH_MARKETS
                    if market not in supported_markets
                ],
                "reason": _state_reason(_aggregate_state(market_states)),
            }
        )

    markets: list[dict[str, Any]] = []
    for market in MARKET_BREADTH_MARKETS:
        states = market_measure_states[market]
        supported_measures = [
            measure_id
            for measure_id, state in states.items()
            if state in {"available", "stale"}
        ]
        market_state = _aggregate_state(states)
        markets.append(
            {
                "market": market,
                "state": market_state,
                "supportedMeasures": supported_measures,
                "missingMeasures": [
                    measure_id
                    for measure_id in MARKET_BREADTH_MEASURE_IDS
                    if measure_id not in supported_measures
                ],
                "reason": _state_reason(market_state),
            }
        )

    return {
        "contractVersion": MARKET_BREADTH_READINESS_CONTRACT_VERSION,
        "consumerSafe": True,
        "providerState": _provider_state(snapshots, provider_disabled=provider_disabled),
        "readinessStates": list(MARKET_BREADTH_READINESS_STATES),
        "markets": markets,
        "measures": measures,
        "scoreEligible": False,
        "noFakeBreadthMetrics": True,
    }


__all__ = [
    "MARKET_BREADTH_MEASURE_IDS",
    "MARKET_BREADTH_READINESS_CONTRACT_VERSION",
    "MARKET_BREADTH_READINESS_STATES",
    "build_market_breadth_readiness_contract",
]
