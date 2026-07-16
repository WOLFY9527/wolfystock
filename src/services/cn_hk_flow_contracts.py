# -*- coding: utf-8 -*-
"""Inert CN/HK flow contracts and mocked fixture parsers.

This module is metadata and cache-payload projection only. It must not import
provider clients, call networks, read credentials, mutate MarketCache, change
liquidity scoring, or alter provider ordering.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from src.services.market_observation_time import normalize_authoritative_market_time
from src.services.provider_unavailable_reason_buckets import (
    NO_PROVIDER_SELECTION_REASON_BUCKET_RULES,
    explicit_unavailable_reason_bucket,
    safe_unavailable_reason_bucket,
)


AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID = "authorized.cn_hk_connect_flow"
AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_NAME = "Authorized CN/HK Connect Flow"
AUTHORIZED_CN_HK_CONNECT_FLOW_SOURCE_TYPE = "authorized_licensed_feed"
AUTHORIZED_CN_HK_CONNECT_FLOW_SOURCE_TIER = "authorized_licensed_feed"
AUTHORIZED_CN_HK_CONNECT_FLOW_CACHE_ONLY_MODE = "cache_only"
AUTHORIZED_CN_HK_CONNECT_FLOW_REQUIRED_SYMBOLS = ("NORTHBOUND", "SOUTHBOUND")
AUTHORIZED_CN_HK_CONNECT_FLOW_MAX_DELAY_MINUTES = 24 * 60

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
    "disabled_provider",
    "stale_data",
    "low_coverage",
)

_SOURCE_CLASS_DISABLED = "disabled_live_stub"
_DEFAULT_REASON_BUCKETS = tuple(SAFE_UNAVAILABLE_REASON_BUCKETS)
_REQUIRED_SYMBOLS = frozenset(CN_HK_FLOW_SYMBOLS)
_AUTHORIZED_REQUIRED_SYMBOLS = frozenset(AUTHORIZED_CN_HK_CONNECT_FLOW_REQUIRED_SYMBOLS)
_AUTHORIZED_ALL_SYMBOLS = frozenset(CN_HK_FLOW_SYMBOLS)
_AUTHORIZED_MIN_COVERAGE_RATIO = len(_AUTHORIZED_REQUIRED_SYMBOLS) / len(_AUTHORIZED_ALL_SYMBOLS)
_CN_TZ = timezone(timedelta(hours=8))
_SOURCE_AUTHORITY_STATE_AVAILABLE = "available"
_SOURCE_AUTHORITY_STATE_UNAVAILABLE = "unavailable"
_SCORE_CONTRIBUTION_DISABLED_REASON = "score_contribution_disabled"
_AUTHORIZED_UNAVAILABLE_REASON_BUCKET_RULES = (
    (
        "disabled_provider",
        (
            "disabled_provider",
            "provider_disabled",
            "disabled",
            "not enabled",
            "not_enabled",
        ),
    ),
    *NO_PROVIDER_SELECTION_REASON_BUCKET_RULES,
    (
        "stale_data",
        (
            "stale_data",
            "stale",
            "expired",
        ),
    ),
    (
        "low_coverage",
        (
            "low_coverage",
            "coverage",
            "missing required",
        ),
    ),
)
_AUTHORIZED_SUCCESS_REASON_CODE = "authorized_cn_hk_connect_flow_diagnostic_only"


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


class CnHkFlowProviderUnavailable(RuntimeError):
    """Sanitized fail-closed unavailable state for the authorized flow path."""

    def __init__(self, reason_codes: Sequence[str] | str) -> None:
        if isinstance(reason_codes, str):
            reason_values = (reason_codes,)
        else:
            reason_values = tuple(reason_codes)
        sanitized = tuple(dict.fromkeys(_safe_reason_bucket(reason) for reason in reason_values))
        self.reason_codes = sanitized or ("malformed_payload",)
        super().__init__(
            f"{AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID}_unavailable:"
            f"{','.join(self.reason_codes)}"
        )

    def to_dict(self) -> dict[str, Any]:
        reason = self.reason_codes[0] if self.reason_codes else "malformed_payload"
        return {
            "providerId": AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID,
            "providerName": AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_NAME,
            "source": "unavailable",
            "sourceLabel": "未接入",
            "sourceType": "missing",
            "sourceTier": _SOURCE_CLASS_DISABLED,
            "sourceClass": _SOURCE_CLASS_DISABLED,
            "trustLevel": "unavailable",
            "available": False,
            "reasonCodes": list(self.reason_codes),
            "freshness": "unavailable",
            "freshnessState": "unavailable",
            "isFallback": False,
            "fallbackUsed": False,
            "isUnavailable": True,
            "isProxy": False,
            "proxyIdentity": None,
            "observationOnly": True,
            "sourceAuthorityAllowed": False,
            "sourceAuthorityState": _SOURCE_AUTHORITY_STATE_UNAVAILABLE,
            "scoreContributionAllowed": False,
            "scoreAuthorityEligible": False,
            "authorityGrant": False,
            "decisionGrade": False,
            "degradationReason": reason,
            "unavailableReason": reason,
            "sourceConfidence": "unavailable",
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
        item_as_of = as_of or _extract_as_of(raw_item)
        if item_as_of is None:
            return build_unavailable_cn_hk_flow_observations("malformed_payload", as_of=None)
        parsed[symbol] = ParsedCnHkFlowObservation(
            symbol=symbol,
            value=value,
            as_of=item_as_of,
            is_evidence=True,
        )

    if set(parsed) != _REQUIRED_SYMBOLS:
        empty_like = not parsed and all(not isinstance(item, Mapping) or not item for item in observations)
        reason = "empty_payload" if empty_like else "malformed_payload"
        return build_unavailable_cn_hk_flow_observations(reason, as_of=as_of)

    return tuple(parsed[symbol] for symbol in CN_HK_FLOW_SYMBOLS)


def build_authorized_cn_hk_connect_flow_snapshot(
    payload: Any,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Project a cache-only authorized CN/HK flow payload into endpoint diagnostics.

    The input must already be an injected/cache result. This function never
    fetches providers, reads credentials, or promotes the data to scoring use.
    """
    now_dt = _normalize_datetime(now) or datetime.now(_CN_TZ)
    reason = _authorized_explicit_reason_bucket(payload)
    if reason is not None:
        raise CnHkFlowProviderUnavailable(reason)
    if not isinstance(payload, Mapping):
        raise CnHkFlowProviderUnavailable("malformed_payload")

    _validate_authorized_source_metadata(payload)
    observations = payload.get("observations")
    if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
        raise CnHkFlowProviderUnavailable("malformed_payload")
    if not observations:
        raise CnHkFlowProviderUnavailable("empty_payload")

    as_of_text = _extract_as_of(payload)
    as_of_dt = _parse_datetime(as_of_text)
    if as_of_dt is None:
        raise CnHkFlowProviderUnavailable("malformed_payload")
    delay_minutes = _delay_minutes(as_of_dt, now_dt)
    if delay_minutes > AUTHORIZED_CN_HK_CONNECT_FLOW_MAX_DELAY_MINUTES:
        raise CnHkFlowProviderUnavailable("stale_data")

    freshness = _authorized_freshness(payload)
    parsed = _parse_authorized_observations(observations, as_of_text=as_of_text)
    coverage_ratio = round(len(parsed) / len(CN_HK_FLOW_SYMBOLS), 2)
    if not _AUTHORIZED_REQUIRED_SYMBOLS.issubset(parsed) or coverage_ratio < _AUTHORIZED_MIN_COVERAGE_RATIO:
        raise CnHkFlowProviderUnavailable("low_coverage")

    fulfilled_metrics = [symbol for symbol in CN_HK_FLOW_SYMBOLS if symbol in parsed]
    missing_metrics = [symbol for symbol in CN_HK_FLOW_SYMBOLS if symbol not in parsed]
    trading_date = _text(payload.get("tradingDate") or payload.get("trading_date") or as_of_text[:10])
    session = _text(payload.get("session") or payload.get("tradingSession") or payload.get("trading_session"))
    source_freshness_evidence = {
        "providerId": AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID,
        "source": AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID,
        "sourceType": AUTHORIZED_CN_HK_CONNECT_FLOW_SOURCE_TYPE,
        "sourceClass": AUTHORIZED_CN_HK_CONNECT_FLOW_SOURCE_TYPE,
        "freshness": freshness,
        "freshnessState": freshness,
        "asOf": as_of_text,
        "tradingDate": trading_date or None,
        "session": session or None,
        "delayMinutes": delay_minutes,
        "cacheOnly": True,
        "externalProviderCalls": False,
        "isFallback": False,
        "isStale": False,
        "isPartial": coverage_ratio < 1.0,
        "isUnavailable": False,
        "isProxy": False,
        "proxyIdentity": None,
        "sourceAuthorityState": _SOURCE_AUTHORITY_STATE_AVAILABLE,
        "scoreAuthorityEligible": False,
    }
    items = [
        _authorized_metric_item(
            parsed[symbol],
            freshness=freshness,
            trading_date=trading_date,
            session=session,
            source_freshness_evidence=source_freshness_evidence,
        )
        for symbol in fulfilled_metrics
    ]
    return {
        "providerId": AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID,
        "providerName": AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_NAME,
        "source": AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID,
        "sourceLabel": f"{AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_NAME} diagnostic cache",
        "sourceType": AUTHORIZED_CN_HK_CONNECT_FLOW_SOURCE_TYPE,
        "sourceTier": AUTHORIZED_CN_HK_CONNECT_FLOW_SOURCE_TIER,
        "sourceClass": AUTHORIZED_CN_HK_CONNECT_FLOW_SOURCE_TYPE,
        "retrievalMode": AUTHORIZED_CN_HK_CONNECT_FLOW_CACHE_ONLY_MODE,
        "cacheOnly": True,
        "externalProviderCalls": False,
        "updatedAt": _text(payload.get("updatedAt") or payload.get("updated_at") or as_of_text),
        "asOf": as_of_text,
        "tradingDate": trading_date or None,
        "session": session or None,
        "freshness": freshness,
        "freshnessState": freshness,
        "sourceFreshnessEvidence": source_freshness_evidence,
        "items": items,
        "fulfilledMetrics": fulfilled_metrics,
        "missingMetrics": missing_metrics,
        "coverageRatio": coverage_ratio,
        "coverage": coverage_ratio,
        "isPartial": coverage_ratio < 1.0,
        "fallbackUsed": False,
        "isFallback": False,
        "isUnavailable": False,
        "isProxy": False,
        "proxyIdentity": None,
        "observationOnly": True,
        "sourceAuthorityAllowed": True,
        "sourceAuthorityState": _SOURCE_AUTHORITY_STATE_AVAILABLE,
        "scoreContributionAllowed": False,
        "scoreAuthorityEligible": False,
        "authorityGrant": False,
        "decisionGrade": False,
        "degradationReason": _SCORE_CONTRIBUTION_DISABLED_REASON,
        "capReason": _SCORE_CONTRIBUTION_DISABLED_REASON,
        "unavailableReason": None,
        "sourceConfidence": "limited",
        "reasonCodes": [_AUTHORIZED_SUCCESS_REASON_CODE],
        "warning": "Authorized CN/HK connect-flow diagnostic cache; scoring remains disabled.",
    }


def _explicit_reason_bucket(payload: Any) -> str | None:
    return explicit_unavailable_reason_bucket(
        payload,
        reason_bucket_rules=NO_PROVIDER_SELECTION_REASON_BUCKET_RULES,
    )


def _authorized_explicit_reason_bucket(payload: Any) -> str | None:
    if isinstance(payload, Mapping):
        if payload.get("enabled") is False or payload.get("providerEnabled") is False:
            return "disabled_provider"
    return explicit_unavailable_reason_bucket(
        payload,
        reason_bucket_rules=_AUTHORIZED_UNAVAILABLE_REASON_BUCKET_RULES,
    )


def _validate_authorized_source_metadata(payload: Mapping[str, Any]) -> None:
    provider_id = _text(payload.get("providerId") or payload.get("provider_id") or payload.get("source")).lower()
    if provider_id != AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID:
        raise CnHkFlowProviderUnavailable("malformed_payload")
    source = _text(payload.get("source") or payload.get("providerId") or payload.get("provider_id")).lower()
    if source != AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID:
        raise CnHkFlowProviderUnavailable("malformed_payload")
    source_type = _text(payload.get("sourceType") or payload.get("source_type")).lower()
    source_tier = _text(payload.get("sourceTier") or payload.get("source_tier")).lower()
    if source_type != AUTHORIZED_CN_HK_CONNECT_FLOW_SOURCE_TYPE:
        raise CnHkFlowProviderUnavailable("malformed_payload")
    if source_tier != AUTHORIZED_CN_HK_CONNECT_FLOW_SOURCE_TIER:
        raise CnHkFlowProviderUnavailable("malformed_payload")


def _parse_authorized_observations(
    observations: Sequence[Any],
    *,
    as_of_text: str,
) -> dict[str, ParsedCnHkFlowObservation]:
    parsed: dict[str, ParsedCnHkFlowObservation] = {}
    for raw_item in observations:
        if not isinstance(raw_item, Mapping):
            raise CnHkFlowProviderUnavailable("malformed_payload")
        symbol = _text(raw_item.get("symbol")).upper()
        contract = _CONTRACTS_BY_SYMBOL.get(symbol)
        if contract is None:
            continue
        value = _parse_number(raw_item.get("value"))
        if value is None:
            raise CnHkFlowProviderUnavailable("malformed_payload")
        unit = _text(raw_item.get("unit"))
        if unit != contract.expected_unit:
            raise CnHkFlowProviderUnavailable("malformed_payload")
        parsed[symbol] = ParsedCnHkFlowObservation(
            symbol=symbol,
            value=value,
            as_of=_extract_as_of(raw_item) or as_of_text,
            is_evidence=True,
        )
    if not parsed:
        raise CnHkFlowProviderUnavailable("empty_payload")
    return parsed


def _authorized_metric_item(
    observation: ParsedCnHkFlowObservation,
    *,
    freshness: str,
    trading_date: str,
    session: str,
    source_freshness_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    contract = _CONTRACTS_BY_SYMBOL[observation.symbol]
    currency = _currency_for_unit(contract.expected_unit)
    return {
        "name": contract.display_name,
        "label": contract.display_name,
        "symbol": observation.symbol,
        "value": observation.value,
        "price": observation.value,
        "change": None,
        "changePercent": None,
        "change_text": None,
        "sparkline": [],
        "trend": [],
        "unit": contract.expected_unit,
        "currency": currency,
        "source": AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID,
        "sourceLabel": f"{AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_NAME} diagnostic cache",
        "sourceType": AUTHORIZED_CN_HK_CONNECT_FLOW_SOURCE_TYPE,
        "sourceTier": AUTHORIZED_CN_HK_CONNECT_FLOW_SOURCE_TIER,
        "sourceClass": AUTHORIZED_CN_HK_CONNECT_FLOW_SOURCE_TYPE,
        "providerId": AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID,
        "providerClass": AUTHORIZED_CN_HK_CONNECT_FLOW_PROVIDER_ID,
        "activationHint": "authorized_cn_hk_connect_flow_cache_diagnostic",
        "asOf": observation.as_of,
        "updatedAt": observation.as_of,
        "tradingDate": trading_date or None,
        "session": session or None,
        "freshness": freshness,
        "freshnessState": freshness,
        "isFallback": False,
        "fallbackUsed": False,
        "isUnavailable": False,
        "isProxy": False,
        "proxyIdentity": None,
        "observationOnly": True,
        "sourceAuthorityAllowed": True,
        "sourceAuthorityState": _SOURCE_AUTHORITY_STATE_AVAILABLE,
        "scoreContributionAllowed": False,
        "scoreAuthorityEligible": False,
        "authorityGrant": False,
        "decisionGrade": False,
        "degradationReason": _SCORE_CONTRIBUTION_DISABLED_REASON,
        "capReason": _SCORE_CONTRIBUTION_DISABLED_REASON,
        "unavailableReason": None,
        "sourceConfidence": "limited",
        "reasonCodes": [_AUTHORIZED_SUCCESS_REASON_CODE],
        "sourceFreshnessEvidence": dict(source_freshness_evidence),
        "risk_direction": "neutral",
        "hover_details": ["Authorized diagnostic cache; score contribution disabled."],
    }


def _authorized_freshness(payload: Mapping[str, Any]) -> str:
    freshness = _text(payload.get("freshness") or payload.get("sourceFreshness")).lower()
    if freshness in {"live", "fresh", "realtime"}:
        raise CnHkFlowProviderUnavailable("malformed_payload")
    if freshness in {"delayed", "cached", "stale"}:
        return freshness
    return "delayed"


def _parse_datetime(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _normalize_datetime(parsed)


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=_CN_TZ)
    return value.astimezone(_CN_TZ)


def _delay_minutes(as_of: datetime, now: datetime) -> int:
    delay = int((now - as_of).total_seconds() // 60)
    return max(0, delay)


def _currency_for_unit(unit: str) -> str | None:
    normalized = unit.upper()
    if "CNY" in normalized:
        return "CNY"
    if "HKD" in normalized:
        return "HKD"
    return None


def _safe_reason_bucket(value: Any) -> str:
    return safe_unavailable_reason_bucket(value, SAFE_UNAVAILABLE_REASON_BUCKETS)


def _extract_as_of(payload: Any) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    for key in ("observed_at", "observedAt", "as_of", "asOf", "observationDate"):
        value = _text(payload.get(key))
        if value and normalize_authoritative_market_time(value) is not None:
            return value
    return None


def _parse_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    return str(value or "").strip()
