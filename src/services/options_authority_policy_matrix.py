# -*- coding: utf-8 -*-
"""Pure inert policy matrix for future options authority evidence decisions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


OPTIONS_AUTHORITY_SURFACES = (
    "iv_rank",
    "event_calendar",
    "expiration_calendar",
)

BLOCKED_OPTIONS_AUTHORITY_SOURCE_CLASSES = (
    "fixture",
    "synthetic",
    "fallback",
    "dry_run",
    "stub",
    "adapter_contract",
    "request_shaped",
    "request_supplied",
    "proxy",
    "provider_self_claim_only",
)

CURRENT_KNOWN_OPTIONS_AUTHORITY_PROVIDER_IDS = (
    "tradier",
    "ibkr",
    "polygon",
)

CURRENT_KNOWN_OPTIONS_AUTHORITY_SOURCE_TYPES = (
    "live",
    "fixture",
    "synthetic",
    "fallback",
    "dry_run",
    "stub",
    "adapter_contract",
    "request_shaped",
    "request_supplied",
    "proxy",
    "provider_self_claim_only",
)

_IV_RANK_FUTURE_CANDIDATE_SOURCE_CLASSES = (
    "provider_reported_iv_rank",
    "approved_historical_option_iv_series",
)
_EVENT_CALENDAR_FUTURE_CANDIDATE_SOURCE_CLASSES = (
    "licensed_event_calendar_provider",
)
_EXPIRATION_CALENDAR_FUTURE_CANDIDATE_SOURCE_CLASSES = (
    "occ_opra_exchange_or_licensed_expiration_calendar",
)

_COMMON_POLICY_FLAGS = {
    "diagnostic_only": True,
    "authoritative_by_default": False,
    "authority_policy_source_required": True,
    "coverage_alone_is_authority": False,
    "provider_self_claim_alone_is_authority": False,
    "authority_grants": {
        "provider_ids": (),
        "source_types": (),
    },
    "blocked_source_classes": BLOCKED_OPTIONS_AUTHORITY_SOURCE_CLASSES,
    "current_known_provider_ids": CURRENT_KNOWN_OPTIONS_AUTHORITY_PROVIDER_IDS,
    "current_known_source_types": CURRENT_KNOWN_OPTIONS_AUTHORITY_SOURCE_TYPES,
}

_OPTIONS_AUTHORITY_POLICY_MATRIX = {
    "iv_rank": {
        **_COMMON_POLICY_FLAGS,
        "surface": "iv_rank",
        "required_evidence": (
            "providerId",
            "sourceType",
            "sourceAuthority",
            "authorityPolicySource",
            "asOf",
            "freshness",
            "lookbackWindow",
            "dateRange",
            "methodology",
            "providerReportedIvRank",
            "providerReportedIvPercentile",
            "approvedHistoricalOptionIvSeries",
            "coverageMetadata",
            "sandboxOrProduction",
        ),
        "future_candidate_source_classes": _IV_RANK_FUTURE_CANDIDATE_SOURCE_CLASSES,
    },
    "event_calendar": {
        **_COMMON_POLICY_FLAGS,
        "surface": "event_calendar",
        "required_evidence": (
            "providerId",
            "sourceType",
            "sourceAuthority",
            "authorityPolicySource",
            "asOf",
            "freshness",
            "eventTypesCovered",
            "symbolCoverage",
            "underlyingCoverage",
            "lookaheadWindow",
            "dateRange",
            "timezone",
            "sessionMetadata",
            "confirmationStatus",
            "eventId",
            "providerEventId",
            "coverageMetadata",
        ),
        "future_candidate_source_classes": _EVENT_CALENDAR_FUTURE_CANDIDATE_SOURCE_CLASSES,
    },
    "expiration_calendar": {
        **_COMMON_POLICY_FLAGS,
        "surface": "expiration_calendar",
        "required_evidence": (
            "providerId",
            "sourceType",
            "sourceAuthority",
            "authorityPolicySource",
            "asOf",
            "freshness",
            "underlying",
            "symbol",
            "expirationDates",
            "expirationCount",
            "expirationTypes",
            "dateRange",
            "lookaheadWindow",
            "coverageMetadata",
            "exchange",
            "occ",
            "opra",
            "licensedSourceMetadata",
            "adjustmentHandling",
            "deliverableHandling",
        ),
        "future_candidate_source_classes": _EXPIRATION_CALENDAR_FUTURE_CANDIDATE_SOURCE_CLASSES,
    },
}


def _normalize_token(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def get_options_authority_policy_matrix() -> dict[str, dict[str, Any]]:
    """Return a detached copy of the inert options authority policy matrix."""

    return deepcopy(_OPTIONS_AUTHORITY_POLICY_MATRIX)


def get_options_authority_surface_policy(surface: str) -> dict[str, Any]:
    """Return a detached copy of one surface policy."""

    normalized_surface = _normalize_token(surface)
    if normalized_surface not in _OPTIONS_AUTHORITY_POLICY_MATRIX:
        raise KeyError(f"Unknown options authority surface: {surface}")
    return deepcopy(_OPTIONS_AUTHORITY_POLICY_MATRIX[normalized_surface])


def is_options_authority_source_blocked(surface: str, source_type: str) -> bool:
    """Return whether the source class is explicitly blocked for the surface."""

    policy = get_options_authority_surface_policy(surface)
    normalized_source_type = _normalize_token(source_type)
    return normalized_source_type in {
        _normalize_token(item) for item in policy["blocked_source_classes"]
    }


def is_options_authority_source_granted(surface: str, source_type: str) -> bool:
    """Return whether the matrix grants authority to the source class."""

    policy = get_options_authority_surface_policy(surface)
    normalized_source_type = _normalize_token(source_type)
    return normalized_source_type in {
        _normalize_token(item) for item in policy["authority_grants"]["source_types"]
    }


def is_options_authority_provider_granted(surface: str, provider_id: str) -> bool:
    """Return whether the matrix grants authority to the provider id."""

    policy = get_options_authority_surface_policy(surface)
    normalized_provider_id = _normalize_token(provider_id)
    return normalized_provider_id in {
        _normalize_token(item) for item in policy["authority_grants"]["provider_ids"]
    }
