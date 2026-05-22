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

from src.services.provider_unavailable_reason_buckets import (
    explicit_unavailable_reason_bucket,
    safe_unavailable_reason_bucket,
)


US_BREADTH_SYMBOLS = (
    "ADVANCERS",
    "DECLINERS",
    "UNCHANGED",
    "ADVANCE_DECLINE_RATIO",
    "NEW_HIGHS",
    "NEW_LOWS",
    "HIGH_LOW_RATIO",
)

US_BREADTH_AUTHORITY_PROVIDER_ID = "official_or_authorized.us_market_breadth"
US_BREADTH_AUTHORITY_SOURCE_LABEL = "Official or Authorized US Market Breadth"
US_BREADTH_AUTHORITY_SOURCE_TIER = "official_or_authorized_licensed_feed"
US_BREADTH_SCORE_GRADE_TRUST_LEVEL = "score_grade_when_configured"
US_BREADTH_SCORE_GRADE_ACTIVATION_GATE = (
    "configured_official_or_authorized_feed_and_daily_freshness_and_min_coverage"
)
US_BREADTH_MISSING_PROVIDER_REASON = "authorized_us_market_breadth_feed_not_configured"
US_BREADTH_REPRESENTATIVE_SAMPLE_REASON = "representative_sample_not_full_market_breadth"
US_BREADTH_PROXY_PLACEHOLDER_REASON = "proxy_or_placeholder_not_authorized_breadth"
POLYGON_US_BREADTH_UNAUTHORIZED_REASON = "polygon_unauthorized"
POLYGON_US_BREADTH_RESPONSE_INVALID_REASON = "polygon_response_invalid"
POLYGON_US_BREADTH_COVERAGE_BELOW_THRESHOLD_REASON = "polygon_coverage_below_threshold"
POLYGON_US_BREADTH_EOD_STALE_REASON = "polygon_eod_stale"
POLYGON_US_BREADTH_HIGH_LOW_HISTORY_UNAVAILABLE_REASON = "polygon_high_low_history_unavailable"

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
class UsBreadthSourceContract:
    claim_class: str
    provider_id: str
    source_label: str
    source_tier: str
    trust_level: str
    source_authority_allowed: bool
    score_contribution_allowed: bool
    broad_market_claim_allowed: bool
    activation_gate: str
    source_authority_reason: str | None = None


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
        symbol="UNCHANGED",
        display_name="Unchanged",
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

_SOURCE_CONTRACTS = (
    UsBreadthSourceContract(
        claim_class="authorized_score_grade_breadth",
        provider_id=US_BREADTH_AUTHORITY_PROVIDER_ID,
        source_label=US_BREADTH_AUTHORITY_SOURCE_LABEL,
        source_tier=US_BREADTH_AUTHORITY_SOURCE_TIER,
        trust_level=US_BREADTH_SCORE_GRADE_TRUST_LEVEL,
        source_authority_allowed=True,
        score_contribution_allowed=True,
        broad_market_claim_allowed=True,
        activation_gate=US_BREADTH_SCORE_GRADE_ACTIVATION_GATE,
    ),
    UsBreadthSourceContract(
        claim_class="representative_sample_breadth",
        provider_id="bounded_representative_sample",
        source_label="Representative US Breadth Sample",
        source_tier="representative_sample",
        trust_level="observation_only",
        source_authority_allowed=False,
        score_contribution_allowed=False,
        broad_market_claim_allowed=False,
        activation_gate="sample_universe_documented_authorized_and_coverage_qualified",
        source_authority_reason=US_BREADTH_REPRESENTATIVE_SAMPLE_REASON,
    ),
    UsBreadthSourceContract(
        claim_class="proxy_placeholder_fallback_breadth",
        provider_id="yfinance_proxy",
        source_label="Yahoo Finance",
        source_tier="unofficial_proxy",
        trust_level="usable_with_caution",
        source_authority_allowed=False,
        score_contribution_allowed=False,
        broad_market_claim_allowed=False,
        activation_gate="not_score_grade_proxy_placeholder_or_fallback",
        source_authority_reason=US_BREADTH_PROXY_PLACEHOLDER_REASON,
    ),
    UsBreadthSourceContract(
        claim_class="missing_unavailable_breadth",
        provider_id=US_BREADTH_AUTHORITY_PROVIDER_ID,
        source_label=US_BREADTH_AUTHORITY_SOURCE_LABEL,
        source_tier=US_BREADTH_AUTHORITY_SOURCE_TIER,
        trust_level="unavailable",
        source_authority_allowed=False,
        score_contribution_allowed=False,
        broad_market_claim_allowed=False,
        activation_gate=US_BREADTH_SCORE_GRADE_ACTIVATION_GATE,
        source_authority_reason=US_BREADTH_MISSING_PROVIDER_REASON,
    ),
)

_SOURCE_CONTRACTS_BY_CLAIM = MappingProxyType(
    {item.claim_class: item for item in _SOURCE_CONTRACTS}
)


def list_us_breadth_contracts() -> tuple[UsBreadthContract, ...]:
    """Return deterministic US breadth contracts for future provider wiring."""
    return tuple(_CONTRACTS)


def get_us_breadth_contract(symbol: str | None) -> UsBreadthContract | None:
    """Look up a single US breadth contract by symbol."""
    normalized = _text(symbol).upper()
    if not normalized:
        return None
    return _CONTRACTS_BY_SYMBOL.get(normalized)


def list_us_breadth_source_contracts() -> tuple[UsBreadthSourceContract, ...]:
    """Return source-claim contracts for US breadth authority gates."""
    return tuple(_SOURCE_CONTRACTS)


def get_us_breadth_source_contract(claim_class: str | None) -> UsBreadthSourceContract | None:
    normalized = _text(claim_class).lower()
    if not normalized:
        return None
    return _SOURCE_CONTRACTS_BY_CLAIM.get(normalized)


def build_us_breadth_missing_authority_diagnostic() -> dict[str, Any]:
    """Return a sanitized fail-closed diagnostic for the missing authority feed."""
    return {
        "providerConstructed": False,
        "probePassed": False,
        "freshnessValid": False,
        "sourceMetadataValid": True,
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "fulfilledMetrics": [],
        "missingMetrics": list(US_BREADTH_SYMBOLS),
        "staleMetrics": [],
        "reason": US_BREADTH_MISSING_PROVIDER_REASON,
        "sourceLabel": US_BREADTH_AUTHORITY_SOURCE_LABEL,
        "sourceTier": US_BREADTH_AUTHORITY_SOURCE_TIER,
        "trustLevel": US_BREADTH_SCORE_GRADE_TRUST_LEVEL,
    }


def representative_sample_breadth_metadata() -> dict[str, Any]:
    """Return metadata that prevents representative samples from broad claims."""
    return {
        "breadthClaimType": "representative_sample_breadth",
        "representativeSample": True,
        "broadMarketClaimAllowed": False,
        "observationOnly": True,
        "sourceTier": "unofficial_proxy",
        "trustLevel": "usable_with_caution",
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "sourceAuthorityReason": US_BREADTH_REPRESENTATIVE_SAMPLE_REASON,
        "sourceAuthorityRouteRejected": False,
        "routeRejectedReasonCodes": [US_BREADTH_REPRESENTATIVE_SAMPLE_REASON],
    }


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
