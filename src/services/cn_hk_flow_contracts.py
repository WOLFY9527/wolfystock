# -*- coding: utf-8 -*-
"""Inert CN/HK flow contracts and mocked fixture parsers.

This module is metadata and fixture parsing only. It must not import provider
clients, call networks, read credentials, or change Market Overview runtime,
MarketCache behavior, liquidity scoring, rotation radar semantics, or API
response shapes.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence


CN_HK_FLOW_SYMBOLS = (
    "NORTHBOUND",
    "SOUTHBOUND",
    "MAINLAND_MAIN",
    "CN_ETF",
    "MARGIN_BALANCE",
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
_REQUIRED_SYMBOLS = frozenset(CN_HK_FLOW_SYMBOLS)


@dataclass(frozen=True)
class CnHkFlowContract:
    symbol: str
    display_name: str
    expected_unit: str
    expected_cadence: str
    source_class: str
    freshness_window: str
    entitlement_config_category: str
    safe_fallback_reason_buckets: tuple[str, ...]


@dataclass(frozen=True)
class ParsedCnHkFlowObservation:
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
    CnHkFlowContract(
        symbol="NORTHBOUND",
        display_name="北向资金",
        expected_unit="亿 CNY",
        expected_cadence="trading_session_snapshot",
        source_class=_SOURCE_CLASS_DISABLED,
        freshness_window="Same-session delayed snapshot only after an approved CN/HK flow provider audit.",
        entitlement_config_category="cn_hk_cross_border_flow_access",
        safe_fallback_reason_buckets=_DEFAULT_REASON_BUCKETS,
    ),
    CnHkFlowContract(
        symbol="SOUTHBOUND",
        display_name="南向资金",
        expected_unit="亿 HKD",
        expected_cadence="trading_session_snapshot",
        source_class=_SOURCE_CLASS_DISABLED,
        freshness_window="Same-session delayed snapshot only after an approved CN/HK flow provider audit.",
        entitlement_config_category="cn_hk_cross_border_flow_access",
        safe_fallback_reason_buckets=_DEFAULT_REASON_BUCKETS,
    ),
    CnHkFlowContract(
        symbol="MAINLAND_MAIN",
        display_name="主力资金",
        expected_unit="亿 CNY",
        expected_cadence="trading_session_snapshot",
        source_class=_SOURCE_CLASS_DISABLED,
        freshness_window="Same-session delayed snapshot only after an approved mainland flow provider audit.",
        entitlement_config_category="cn_mainland_flow_dataset_access",
        safe_fallback_reason_buckets=_DEFAULT_REASON_BUCKETS,
    ),
    CnHkFlowContract(
        symbol="CN_ETF",
        display_name="ETF 净申购",
        expected_unit="亿 CNY",
        expected_cadence="trading_session_snapshot",
        source_class=_SOURCE_CLASS_DISABLED,
        freshness_window="Same-session delayed snapshot only after an approved mainland ETF flow provider audit.",
        entitlement_config_category="cn_etf_flow_dataset_access",
        safe_fallback_reason_buckets=_DEFAULT_REASON_BUCKETS,
    ),
    CnHkFlowContract(
        symbol="MARGIN_BALANCE",
        display_name="融资余额变化",
        expected_unit="亿 CNY",
        expected_cadence="daily_close_or_latest_snapshot",
        source_class=_SOURCE_CLASS_DISABLED,
        freshness_window="Daily or latest delayed snapshot only after an approved margin balance provider audit.",
        entitlement_config_category="cn_margin_balance_dataset_access",
        safe_fallback_reason_buckets=_DEFAULT_REASON_BUCKETS,
    ),
)

_CONTRACTS_BY_SYMBOL = MappingProxyType({item.symbol: item for item in _CONTRACTS})


def list_cn_hk_flow_contracts() -> tuple[CnHkFlowContract, ...]:
    """Return deterministic CN/HK flow contracts for future provider wiring."""
    return tuple(_CONTRACTS)


def get_cn_hk_flow_contract(symbol: str | None) -> CnHkFlowContract | None:
    """Look up a single CN/HK flow contract by symbol."""
    normalized = _text(symbol).upper()
    if not normalized:
        return None
    return _CONTRACTS_BY_SYMBOL.get(normalized)


def build_unavailable_cn_hk_flow_observations(
    reason_bucket: str,
    *,
    as_of: str | None = None,
) -> tuple[ParsedCnHkFlowObservation, ...]:
    """Build a full non-evidence observation set for a safe unavailable reason."""
    normalized_reason = _safe_reason_bucket(reason_bucket)
    return tuple(
        ParsedCnHkFlowObservation(
            symbol=contract.symbol,
            value=None,
            as_of=as_of,
            is_evidence=False,
            unavailable_reason=normalized_reason,
        )
        for contract in _CONTRACTS
    )


def parse_mocked_cn_hk_flow_payload(payload: Any) -> tuple[ParsedCnHkFlowObservation, ...]:
    """Parse mocked provider-shaped CN/HK flow payloads into contract observations.

    The parser is intentionally strict and only accepts the mocked
    ``observations`` shape defined for test fixtures. Unsupported shapes fail
    closed into sanitized unavailable buckets.
    """
    as_of = _extract_as_of(payload)
    explicit_reason = _explicit_reason_bucket(payload)
    if explicit_reason is not None:
        return build_unavailable_cn_hk_flow_observations(explicit_reason, as_of=as_of)

    if not isinstance(payload, Mapping):
        return build_unavailable_cn_hk_flow_observations("malformed_payload", as_of=as_of)

    observations = payload.get("observations")
    if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
        return build_unavailable_cn_hk_flow_observations("malformed_payload", as_of=as_of)
    if not observations:
        return build_unavailable_cn_hk_flow_observations("empty_payload", as_of=as_of)

    parsed: dict[str, ParsedCnHkFlowObservation] = {}
    for raw_item in observations:
        if not isinstance(raw_item, Mapping):
            return build_unavailable_cn_hk_flow_observations("malformed_payload", as_of=as_of)
        symbol = _text(raw_item.get("symbol")).upper()
        contract = _CONTRACTS_BY_SYMBOL.get(symbol)
        if contract is None:
            continue
        value = _parse_number(raw_item.get("value"))
        if value is None:
            return build_unavailable_cn_hk_flow_observations("malformed_payload", as_of=as_of)
        unit = _text(raw_item.get("unit"))
        if unit and unit != contract.expected_unit:
            return build_unavailable_cn_hk_flow_observations("malformed_payload", as_of=as_of)
        parsed[symbol] = ParsedCnHkFlowObservation(
            symbol=symbol,
            value=value,
            as_of=as_of or _extract_as_of(raw_item),
            is_evidence=True,
        )

    if set(parsed) != _REQUIRED_SYMBOLS:
        empty_like = not parsed and all(not isinstance(item, Mapping) or not item for item in observations)
        reason = "empty_payload" if empty_like else "malformed_payload"
        return build_unavailable_cn_hk_flow_observations(reason, as_of=as_of)

    return tuple(parsed[symbol] for symbol in CN_HK_FLOW_SYMBOLS)


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
    if any(token in normalized for token in ("missing_credentials", "credential missing", "missing api key", "not_configured", "api_key_missing", "missing token")):
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
