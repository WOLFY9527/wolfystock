# -*- coding: utf-8 -*-
"""Parity tests between the inert options authority policy matrix and helper diagnostics."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from src.services.options_authority_policy_matrix import (
    BLOCKED_OPTIONS_AUTHORITY_SOURCE_CLASSES,
    OPTIONS_AUTHORITY_SURFACES,
    get_options_authority_surface_policy,
    is_options_authority_source_blocked,
)
from src.services.options_event_calendar_authority import (
    INTERNAL_OPTIONS_EVENT_CALENDAR_AUTHORITY_POLICY_SOURCE,
    build_options_event_calendar_authority_diagnostic,
)
from src.services.options_expiration_calendar_authority import (
    INTERNAL_OPTIONS_EXPIRATION_CALENDAR_AUTHORITY_POLICY_SOURCE,
    build_options_expiration_calendar_authority_diagnostic,
)
from src.services.options_iv_rank_authority import (
    INTERNAL_OPTIONS_IV_RANK_AUTHORITY_POLICY_SOURCE,
    build_options_iv_rank_authority_diagnostic,
)


def _iv_rank_evidence(**overrides: Any) -> dict[str, Any]:
    evidence = {
        "providerId": "future_authorized_provider",
        "sourceType": "live",
        "sourceAuthority": "authorized",
        "authorityPolicySource": INTERNAL_OPTIONS_IV_RANK_AUTHORITY_POLICY_SOURCE,
        "ivRankStatus": "available",
        "ivRankSource": "provider_reported",
        "providerReportedIvRank": 61.0,
        "providerReportedIvPercentile": 63.0,
        "historicalOptionIvSeriesAvailable": True,
        "asOf": "2026-05-26T12:00:00Z",
        "freshness": "fresh",
        "lookbackWindow": "252d",
        "methodology": "provider_reported_iv_percentile",
        "coverageMetadata": {"contractsCovered": 84},
        "sandboxOrProduction": "sandbox",
    }
    evidence.update(overrides)
    return evidence


def _event_calendar_evidence(**overrides: Any) -> dict[str, Any]:
    evidence = {
        "providerId": "future_authorized_provider",
        "sourceType": "live",
        "sourceAuthority": "authorized",
        "authorityPolicySource": INTERNAL_OPTIONS_EVENT_CALENDAR_AUTHORITY_POLICY_SOURCE,
        "eventCalendarStatus": "available",
        "asOf": "2026-05-26T12:00:00Z",
        "freshness": "fresh",
        "eventTypesCovered": ["earnings", "dividends", "splits", "corporate_actions"],
        "underlyingCoverage": ["TEM"],
        "dateRange": {"start": "2026-05-26", "end": "2026-06-26"},
        "timezone": "America/New_York",
        "sessionMetadata": {"session": "regular"},
        "confirmationStatus": "confirmed",
        "eventId": "evt-001",
        "providerEventId": "provider-evt-001",
        "coverageMetadata": {"eventCount": 4},
        "sandboxOrProduction": "production",
    }
    evidence.update(overrides)
    return evidence


def _expiration_calendar_evidence(**overrides: Any) -> dict[str, Any]:
    evidence = {
        "providerId": "future_authorized_provider",
        "sourceType": "live",
        "sourceAuthority": "authorized",
        "authorityPolicySource": INTERNAL_OPTIONS_EXPIRATION_CALENDAR_AUTHORITY_POLICY_SOURCE,
        "expirationCalendarStatus": "available",
        "asOf": "2026-05-26T12:00:00Z",
        "freshness": "fresh",
        "underlying": "TEM",
        "symbol": "TEM",
        "expirationDates": ["2026-06-19", "2026-06-26", "2026-08-21", "2027-01-15"],
        "expirationCount": 4,
        "expirationTypes": ["weekly", "monthly", "quarterly", "leaps"],
        "dateRange": {"start": "2026-06-19", "end": "2027-01-15"},
        "lookaheadWindow": "210d",
        "coverageMetadata": {
            "expirationCoverage": "complete",
            "expirationCount": 4,
            "chainAvailability": "complete",
        },
        "exchange": "OPRA",
        "authorizedSourceMetadata": {"venue": "opra", "calendarType": "listed_options"},
        "sandboxOrProduction": "production",
    }
    evidence.update(overrides)
    return evidence


SURFACE_CASES: tuple[
    tuple[
        str,
        Callable[[dict[str, Any]], dict[str, Any]],
        Callable[..., dict[str, Any]],
        str,
        str,
    ],
    ...,
] = (
    (
        "iv_rank",
        build_options_iv_rank_authority_diagnostic,
        _iv_rank_evidence,
        INTERNAL_OPTIONS_IV_RANK_AUTHORITY_POLICY_SOURCE,
        "iv_rank",
    ),
    (
        "event_calendar",
        build_options_event_calendar_authority_diagnostic,
        _event_calendar_evidence,
        INTERNAL_OPTIONS_EVENT_CALENDAR_AUTHORITY_POLICY_SOURCE,
        "event_calendar",
    ),
    (
        "expiration_calendar",
        build_options_expiration_calendar_authority_diagnostic,
        _expiration_calendar_evidence,
        INTERNAL_OPTIONS_EXPIRATION_CALENDAR_AUTHORITY_POLICY_SOURCE,
        "expiration_calendar",
    ),
)


@pytest.mark.parametrize(
    ("surface", "builder", "evidence_factory", "policy_source", "reason_prefix"),
    SURFACE_CASES,
    ids=OPTIONS_AUTHORITY_SURFACES,
)
@pytest.mark.parametrize("blocked_source_class", BLOCKED_OPTIONS_AUTHORITY_SOURCE_CLASSES)
def test_policy_blocked_source_classes_remain_non_authoritative_in_helpers(
    surface: str,
    builder: Callable[[dict[str, Any]], dict[str, Any]],
    evidence_factory: Callable[..., dict[str, Any]],
    policy_source: str,
    reason_prefix: str,
    blocked_source_class: str,
) -> None:
    diagnostic = builder(
        evidence_factory(
            sourceType=blocked_source_class,
            sourceAuthority="authorized",
            authorityPolicySource=policy_source,
        )
    )

    assert is_options_authority_source_blocked(surface, blocked_source_class) is True
    assert diagnostic["diagnosticOnly"] is True
    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert diagnostic["sourceType"] == blocked_source_class
    assert f"{reason_prefix}_{blocked_source_class}_not_authoritative" in diagnostic["reasonCodes"]


@pytest.mark.parametrize(
    ("surface", "builder", "evidence_factory"),
    tuple((surface, builder, evidence_factory) for surface, builder, evidence_factory, _, _ in SURFACE_CASES),
    ids=OPTIONS_AUTHORITY_SURFACES,
)
def test_future_candidate_source_classes_are_not_authority_grants_by_themselves(
    surface: str,
    builder: Callable[[dict[str, Any]], dict[str, Any]],
    evidence_factory: Callable[..., dict[str, Any]],
) -> None:
    policy = get_options_authority_surface_policy(surface)

    for candidate_source_class in policy["future_candidate_source_classes"]:
        diagnostic = builder(
            evidence_factory(
                sourceType=candidate_source_class,
                sourceAuthority="authorized",
                authorityPolicySource="wolfystock_internal_policy_candidate_only",
            )
        )

        assert diagnostic["diagnosticOnly"] is True
        assert diagnostic["authorityState"] == "non_authoritative"
        assert diagnostic["authoritative"] is False
        assert diagnostic["sourceType"] == candidate_source_class


@pytest.mark.parametrize(
    ("builder", "evidence_factory"),
    tuple((builder, evidence_factory) for _, builder, evidence_factory, _, _ in SURFACE_CASES),
    ids=OPTIONS_AUTHORITY_SURFACES,
)
def test_required_future_authority_evidence_includes_authority_policy_source_for_every_surface(
    builder: Callable[[dict[str, Any]], dict[str, Any]],
    evidence_factory: Callable[..., dict[str, Any]],
) -> None:
    diagnostic = builder(evidence_factory(authorityPolicySource="wolfystock_internal_policy_candidate_only"))

    assert "authorityPolicySource" in diagnostic["requiredFutureAuthorityEvidence"]
