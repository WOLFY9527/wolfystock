# -*- coding: utf-8 -*-
"""Inert US breadth contracts and mocked fixture parsers.

This module is metadata and fixture parsing only. It must not import provider
clients, call networks, read credentials, or change Market Overview runtime,
MarketCache behavior, liquidity scoring, or API response shapes.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence


US_BREADTH_SYMBOLS = (
    "ADVANCERS",
    "DECLINERS",
    "ADVANCE_DECLINE_RATIO",
    "NEW_HIGHS",
    "NEW_LOWS",
    "HIGH_LOW_RATIO",
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
_REQUIRED_SYMBOLS = frozenset(US_BREADTH_SYMBOLS)


@dataclass(frozen=True)
class UsBreadthContract:
    symbol: str
    display_name: str
    expected_unit: str
    expected_cadence: str
    source_class: str
    freshness_window: str
    entitlement_config_category: str
    safe_fallback_reason_buckets: tuple[str, ...]


@dataclass(frozen=True)
class ParsedUsBreadthObservation:
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
    UsBreadthContract(
        symbol="ADVANCERS",
        display_name="Advancers",
        expected_unit="stocks",
        expected_cadence="trading_session_snapshot",
        source_class=_SOURCE_CLASS_DISABLED,
        freshness_window="Same-session delayed breadth statistics only after an approved US breadth provider audit.",
        entitlement_config_category="us_breadth_advance_decline_dataset_access",
        safe_fallback_reason_buckets=_DEFAULT_REASON_BUCKETS,
    ),
    UsBreadthContract(
        symbol="DECLINERS",
        display_name="Decliners",
        expected_unit="stocks",
        expected_cadence="trading_session_snapshot",
        source_class=_SOURCE_CLASS_DISABLED,
        freshness_window="Same-session delayed breadth statistics only after an approved US breadth provider audit.",
        entitlement_config_category="us_breadth_advance_decline_dataset_access",
        safe_fallback_reason_buckets=_DEFAULT_REASON_BUCKETS,
    ),
    UsBreadthContract(
        symbol="ADVANCE_DECLINE_RATIO",
        display_name="Advance/Decline Ratio",
        expected_unit="ratio",
        expected_cadence="trading_session_snapshot",
        source_class=_SOURCE_CLASS_DISABLED,
        freshness_window="Same-session delayed breadth statistics only after an approved US breadth provider audit.",
        entitlement_config_category="us_breadth_advance_decline_dataset_access",
        safe_fallback_reason_buckets=_DEFAULT_REASON_BUCKETS,
    ),
    UsBreadthContract(
        symbol="NEW_HIGHS",
        display_name="New Highs",
        expected_unit="stocks",
        expected_cadence="daily_close_or_latest_snapshot",
        source_class=_SOURCE_CLASS_DISABLED,
        freshness_window="Daily close or delayed latest snapshot only after an approved US highs/lows breadth provider audit.",
        entitlement_config_category="us_breadth_high_low_dataset_access",
        safe_fallback_reason_buckets=_DEFAULT_REASON_BUCKETS,
    ),
    UsBreadthContract(
        symbol="NEW_LOWS",
        display_name="New Lows",
        expected_unit="stocks",
        expected_cadence="daily_close_or_latest_snapshot",
        source_class=_SOURCE_CLASS_DISABLED,
        freshness_window="Daily close or delayed latest snapshot only after an approved US highs/lows breadth provider audit.",
        entitlement_config_category="us_breadth_high_low_dataset_access",
        safe_fallback_reason_buckets=_DEFAULT_REASON_BUCKETS,
    ),
    UsBreadthContract(
        symbol="HIGH_LOW_RATIO",
        display_name="High/Low Ratio",
        expected_unit="ratio",
        expected_cadence="daily_close_or_latest_snapshot",
        source_class=_SOURCE_CLASS_DISABLED,
        freshness_window="Daily close or delayed latest snapshot only after an approved US highs/lows breadth provider audit.",
        entitlement_config_category="us_breadth_high_low_dataset_access",
        safe_fallback_reason_buckets=_DEFAULT_REASON_BUCKETS,
    ),
)

_CONTRACTS_BY_SYMBOL = MappingProxyType({item.symbol: item for item in _CONTRACTS})


def list_us_breadth_contracts() -> tuple[UsBreadthContract, ...]:
    """Return deterministic US breadth contracts for future provider wiring."""
    return tuple(_CONTRACTS)


def get_us_breadth_contract(symbol: str | None) -> UsBreadthContract | None:
    """Look up a single US breadth contract by symbol."""
    normalized = _text(symbol).upper()
    if not normalized:
        return None
    return _CONTRACTS_BY_SYMBOL.get(normalized)


def build_unavailable_us_breadth_observations(
    reason_bucket: str,
    *,
    as_of: str | None = None,
) -> tuple[ParsedUsBreadthObservation, ...]:
    """Build a full non-evidence observation set for a safe unavailable reason."""
    normalized_reason = _safe_reason_bucket(reason_bucket)
    return tuple(
        ParsedUsBreadthObservation(
            symbol=contract.symbol,
            value=None,
            as_of=as_of,
            is_evidence=False,
            unavailable_reason=normalized_reason,
        )
        for contract in _CONTRACTS
    )


def parse_mocked_us_breadth_payload(payload: Any) -> tuple[ParsedUsBreadthObservation, ...]:
    """Parse mocked provider-shaped US breadth payloads into contract observations.

    The parser is intentionally strict and only accepts the mocked
    ``observations`` shape defined for test fixtures. Unsupported shapes fail
    closed into sanitized unavailable buckets.
    """
    as_of = _extract_as_of(payload)
    explicit_reason = _explicit_reason_bucket(payload)
    if explicit_reason is not None:
        return build_unavailable_us_breadth_observations(explicit_reason, as_of=as_of)

    if not isinstance(payload, Mapping):
        return build_unavailable_us_breadth_observations("malformed_payload", as_of=as_of)

    observations = payload.get("observations")
    if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
        return build_unavailable_us_breadth_observations("malformed_payload", as_of=as_of)
    if not observations:
        return build_unavailable_us_breadth_observations("empty_payload", as_of=as_of)

    parsed: dict[str, ParsedUsBreadthObservation] = {}
    for raw_item in observations:
        if not isinstance(raw_item, Mapping):
            return build_unavailable_us_breadth_observations("malformed_payload", as_of=as_of)
        symbol = _text(raw_item.get("symbol")).upper()
        contract = _CONTRACTS_BY_SYMBOL.get(symbol)
        if contract is None:
            continue
        value = _parse_number(raw_item.get("value"))
        if value is None:
            return build_unavailable_us_breadth_observations("malformed_payload", as_of=as_of)
        unit = _text(raw_item.get("unit"))
        if unit and unit != contract.expected_unit:
            return build_unavailable_us_breadth_observations("malformed_payload", as_of=as_of)
        parsed[symbol] = ParsedUsBreadthObservation(
            symbol=symbol,
            value=value,
            as_of=as_of or _extract_as_of(raw_item),
            is_evidence=True,
        )

    if set(parsed) != _REQUIRED_SYMBOLS:
        empty_like = not parsed and all(not isinstance(item, Mapping) or not item for item in observations)
        reason = "empty_payload" if empty_like else "malformed_payload"
        return build_unavailable_us_breadth_observations(reason, as_of=as_of)

    return tuple(parsed[symbol] for symbol in US_BREADTH_SYMBOLS)


def _explicit_reason_bucket(payload: Any) -> str | None:
    if not isinstance(payload, Mapping):
        return None

    observations = payload.get("observations")
    if isinstance(observations, Sequence) and not isinstance(observations, (str, bytes)) and len(observations) == 0:
        return "empty_payload"

    markers = [
        payload.get("unavailable_reason"),
        payload.get("unavailableReason"),
        payload.get("reason"),
        payload.get("reasonCode"),
        payload.get("errorCode"),
        payload.get("status"),
        payload.get("credentialState"),
        payload.get("credential_state"),
        payload.get("message"),
    ]
    error = payload.get("error")
    if isinstance(error, Mapping):
        markers.extend(
            [
                error.get("reason"),
                error.get("reasonCode"),
                error.get("errorCode"),
                error.get("status"),
                error.get("message"),
            ]
        )
    elif error is not None:
        markers.append(error)

    normalized = " ".join(_text(marker).lower() for marker in markers if marker is not None)
    if not normalized:
        return None
    if any(
        token in normalized
        for token in (
            "provider_not_selected",
            "provider not selected",
            "not_selected",
            "deferred",
        )
    ):
        return "provider_not_selected"
    if any(
        token in normalized
        for token in (
            "missing_credentials",
            "credential missing",
            "missing api key",
            "not_configured",
            "api_key_missing",
            "missing token",
        )
    ):
        return "missing_credentials"
    if any(token in normalized for token in ("permission_denied", "permission denied", "forbidden", "403", "unauthorized_scope")):
        return "permission_denied"
    if any(token in normalized for token in ("empty_payload", "empty response", "empty dataset", "no_data", "no data")):
        return "empty_payload"
    if any(token in normalized for token in ("malformed_payload", "malformed", "invalid", "schema")):
        return "malformed_payload"
    return None


def _safe_reason_bucket(value: Any) -> str:
    normalized = _text(value).lower()
    if normalized in SAFE_UNAVAILABLE_REASON_BUCKETS:
        return normalized
    return "malformed_payload"


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
