# -*- coding: utf-8 -*-
"""Inert futures contracts and mocked fixture parsers.

This module is metadata and fixture parsing only. It must not import provider
clients, call networks, read credentials, or change Market Overview runtime,
MarketCache behavior, liquidity scoring, or API response shapes.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from src.services.provider_unavailable_reason_buckets import (
    explicit_unavailable_reason_bucket,
    safe_unavailable_reason_bucket,
)


FUTURES_SYMBOLS = (
    "NQ",
    "ES",
    "YM",
    "RTY",
)

SAFE_UNAVAILABLE_REASON_BUCKETS = (
    "provider_not_selected",
    "missing_credentials",
    "permission_denied",
    "empty_payload",
    "malformed_payload",
)

_SOURCE_CLASS_DISABLED = "disabled_live_stub"
_DEFAULT_REASON_BUCKETS = tuple(SAFE_UNAVAILABLE_REASON_BUCKETS)
_REQUIRED_SYMBOLS = frozenset(FUTURES_SYMBOLS)


@dataclass(frozen=True)
class FuturesContract:
    symbol: str
    display_name: str
    expected_unit: str
    expected_cadence: str
    source_class: str
    freshness_window: str
    safe_fallback_reason_buckets: tuple[str, ...]
    delayed_proxy_eligible: bool
    live_premarket_eligible: bool


@dataclass(frozen=True)
class ParsedFuturesObservation:
    symbol: str
    value: float | None
    as_of: str | None
    is_evidence: bool
    unavailable_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "value": self.value,
            "asOf": self.as_of,
            "isEvidence": self.is_evidence,
            "unavailableReason": self.unavailable_reason,
        }


_CONTRACTS = (
    FuturesContract(
        symbol="NQ",
        display_name="E-mini Nasdaq 100",
        expected_unit="index_points",
        expected_cadence="extended_hours_snapshot",
        source_class=_SOURCE_CLASS_DISABLED,
        freshness_window="Delayed or proxy futures snapshot only after an approved Nasdaq futures provider audit; live premarket stays disabled by default.",
        safe_fallback_reason_buckets=_DEFAULT_REASON_BUCKETS,
        delayed_proxy_eligible=True,
        live_premarket_eligible=False,
    ),
    FuturesContract(
        symbol="ES",
        display_name="E-mini S&P 500",
        expected_unit="index_points",
        expected_cadence="extended_hours_snapshot",
        source_class=_SOURCE_CLASS_DISABLED,
        freshness_window="Delayed or proxy futures snapshot only after an approved S&P futures provider audit; live premarket stays disabled by default.",
        safe_fallback_reason_buckets=_DEFAULT_REASON_BUCKETS,
        delayed_proxy_eligible=True,
        live_premarket_eligible=False,
    ),
    FuturesContract(
        symbol="YM",
        display_name="Mini Dow Jones",
        expected_unit="index_points",
        expected_cadence="extended_hours_snapshot",
        source_class=_SOURCE_CLASS_DISABLED,
        freshness_window="Delayed or proxy futures snapshot only after an approved Dow futures provider audit; live premarket stays disabled by default.",
        safe_fallback_reason_buckets=_DEFAULT_REASON_BUCKETS,
        delayed_proxy_eligible=True,
        live_premarket_eligible=False,
    ),
    FuturesContract(
        symbol="RTY",
        display_name="E-mini Russell 2000",
        expected_unit="index_points",
        expected_cadence="extended_hours_snapshot",
        source_class=_SOURCE_CLASS_DISABLED,
        freshness_window="Delayed or proxy futures snapshot only after an approved Russell futures provider audit; live premarket stays disabled by default.",
        safe_fallback_reason_buckets=_DEFAULT_REASON_BUCKETS,
        delayed_proxy_eligible=True,
        live_premarket_eligible=False,
    ),
)

_CONTRACTS_BY_SYMBOL = MappingProxyType({item.symbol: item for item in _CONTRACTS})


def list_futures_contracts() -> tuple[FuturesContract, ...]:
    """Return deterministic futures contracts for future provider wiring."""
    return tuple(_CONTRACTS)


def get_futures_contract(symbol: str | None) -> FuturesContract | None:
    """Look up a single futures contract by symbol."""
    normalized = _text(symbol).upper()
    if not normalized:
        return None
    return _CONTRACTS_BY_SYMBOL.get(normalized)


def build_unavailable_futures_observations(
    reason_bucket: str,
    *,
    as_of: str | None = None,
) -> tuple[ParsedFuturesObservation, ...]:
    """Build a full non-evidence observation set for a safe unavailable reason."""
    normalized_reason = _safe_reason_bucket(reason_bucket)
    return tuple(
        ParsedFuturesObservation(
            symbol=contract.symbol,
            value=None,
            as_of=as_of,
            is_evidence=False,
            unavailable_reason=normalized_reason,
        )
        for contract in _CONTRACTS
    )


def parse_mocked_futures_payload(payload: Any) -> tuple[ParsedFuturesObservation, ...]:
    """Parse mocked provider-shaped futures payloads into contract observations."""
    as_of = _extract_as_of(payload)
    explicit_reason = _explicit_reason_bucket(payload)
    if explicit_reason is not None:
        return build_unavailable_futures_observations(explicit_reason, as_of=as_of)

    if not isinstance(payload, Mapping):
        return build_unavailable_futures_observations("malformed_payload", as_of=as_of)

    observations = payload.get("observations")
    if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
        return build_unavailable_futures_observations("malformed_payload", as_of=as_of)
    if not observations:
        return build_unavailable_futures_observations("empty_payload", as_of=as_of)

    parsed: dict[str, ParsedFuturesObservation] = {}
    for raw_item in observations:
        if not isinstance(raw_item, Mapping):
            return build_unavailable_futures_observations("malformed_payload", as_of=as_of)
        symbol = _text(raw_item.get("symbol")).upper()
        contract = _CONTRACTS_BY_SYMBOL.get(symbol)
        if contract is None:
            continue
        value = _parse_number(raw_item.get("value"))
        if value is None:
            return build_unavailable_futures_observations("malformed_payload", as_of=as_of)
        unit = _text(raw_item.get("unit"))
        if unit and unit != contract.expected_unit:
            return build_unavailable_futures_observations("malformed_payload", as_of=as_of)
        parsed[symbol] = ParsedFuturesObservation(
            symbol=symbol,
            value=value,
            as_of=as_of or _extract_as_of(raw_item),
            is_evidence=True,
        )

    if set(parsed) != _REQUIRED_SYMBOLS:
        empty_like = not parsed and all(not isinstance(item, Mapping) or not item for item in observations)
        reason = "empty_payload" if empty_like else "malformed_payload"
        return build_unavailable_futures_observations(reason, as_of=as_of)

    return tuple(parsed[symbol] for symbol in FUTURES_SYMBOLS)


def _explicit_reason_bucket(payload: Any) -> str | None:
    return explicit_unavailable_reason_bucket(payload)


def _safe_reason_bucket(value: Any) -> str:
    return safe_unavailable_reason_bucket(value, SAFE_UNAVAILABLE_REASON_BUCKETS)


def _extract_as_of(payload: Any) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    for key in ("as_of", "asOf", "updated_at", "updatedAt"):
        value = _text(payload.get(key))
        if value:
            return value
    return None


def _parse_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    return str(value or "").strip()
