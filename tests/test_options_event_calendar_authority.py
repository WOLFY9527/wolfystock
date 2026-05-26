# -*- coding: utf-8 -*-
"""Diagnostic-only event-calendar authority contract tests."""

from __future__ import annotations

from src.services.options_event_calendar_authority import (
    INTERNAL_OPTIONS_EVENT_CALENDAR_AUTHORITY_POLICY_SOURCE,
    REQUIRED_FUTURE_EVENT_CALENDAR_AUTHORITY_EVIDENCE_FIELDS,
    build_options_event_calendar_authority_diagnostic,
)


def test_missing_event_calendar_authority_is_distinct_from_non_authoritative_proxy_data() -> None:
    diagnostic = build_options_event_calendar_authority_diagnostic(None)

    assert diagnostic["diagnosticOnly"] is True
    assert diagnostic["authorityState"] == "missing"
    assert diagnostic["authoritative"] is False
    assert diagnostic["reasonCodes"] == [
        "event_calendar_authority_missing",
        "event_calendar_missing",
        "event_calendar_source_authority_missing",
        "event_calendar_asof_or_freshness_missing",
        "event_calendar_coverage_metadata_missing",
        "event_calendar_confirmation_status_missing",
        "event_calendar_event_identity_missing",
    ]
    assert diagnostic["requiredFutureAuthorityEvidence"] == list(
        REQUIRED_FUTURE_EVENT_CALENDAR_AUTHORITY_EVIDENCE_FIELDS
    )


def test_fixture_event_calendar_stays_non_authoritative_with_explicit_gap_codes() -> None:
    diagnostic = build_options_event_calendar_authority_diagnostic(
        {
            "providerId": "synthetic_options_lab_fixture",
            "sourceType": "fixture",
            "eventCalendarStatus": "available",
            "eventTypesCovered": ["earnings", "dividends"],
            "symbolCoverage": ["TEM"],
            "lookaheadWindow": "45d",
            "timezone": "America/New_York",
            "coverageMetadata": {
                "eventCount": 2,
                "eventSources": ["fixture_seed"],
            },
            "sandboxOrProduction": "not_provider_sourced",
        }
    )

    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert diagnostic["providerId"] == "synthetic_options_lab_fixture"
    assert diagnostic["sourceType"] == "fixture"
    assert diagnostic["eventCalendarStatus"] == "available"
    assert diagnostic["reasonCodes"] == [
        "event_calendar_authority_missing",
        "event_calendar_fixture_not_authoritative",
        "event_calendar_source_authority_missing",
        "event_calendar_asof_or_freshness_missing",
        "event_calendar_confirmation_status_missing",
        "event_calendar_event_identity_missing",
    ]


def test_request_shaped_event_calendar_remains_non_authoritative_even_if_fully_shaped() -> None:
    diagnostic = build_options_event_calendar_authority_diagnostic(
        {
            "providerId": "request_payload",
            "sourceType": "request_supplied",
            "sourceAuthority": "provider_self_claim",
            "authorityPolicySource": "provider_documentation",
            "eventCalendarStatus": "available",
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
            "eventTypesCovered": ["earnings", "dividends", "splits", "fomc"],
            "symbolCoverage": ["TEM"],
            "lookaheadWindow": "30d",
            "timezone": "America/New_York",
            "sessionMetadata": {"session": "pre_market"},
            "confirmationStatus": "confirmed",
            "eventId": "evt-001",
            "providerEventId": "provider-evt-001",
            "coverageMetadata": {"eventCount": 4},
            "sandboxOrProduction": "production",
            "providerDecisionAuthorityClaim": True,
            "recommendationAuthorityClaim": True,
            "notes": ["request_shaped"],
        }
    )

    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert diagnostic["reasonCodes"] == [
        "event_calendar_authority_missing",
        "event_calendar_request_supplied_not_authoritative",
        "event_calendar_request_shaped_not_authoritative",
        "event_calendar_provider_self_claim_ignored",
    ]


def test_internal_policy_is_required_before_any_event_calendar_payload_can_be_authoritative() -> None:
    claimed = build_options_event_calendar_authority_diagnostic(
        {
            "providerId": "tradier",
            "sourceType": "live",
            "sourceAuthority": "provider_reported",
            "eventCalendarStatus": "available",
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
            "eventTypesCovered": ["earnings", "dividends"],
            "underlyingCoverage": ["TEM"],
            "dateRange": {"start": "2026-05-26", "end": "2026-06-26"},
            "timezone": "America/New_York",
            "confirmationStatus": "confirmed",
            "eventId": "evt-001",
            "providerEventId": "provider-evt-001",
            "coverageMetadata": {"eventCount": 2},
            "sandboxOrProduction": "sandbox",
            "providerDecisionAuthorityClaim": True,
        }
    )
    authorized = build_options_event_calendar_authority_diagnostic(
        {
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
    )

    assert claimed["authoritative"] is False
    assert claimed["authorityState"] == "non_authoritative"
    assert "event_calendar_provider_self_claim_ignored" in claimed["reasonCodes"]

    assert authorized["authoritative"] is True
    assert authorized["authorityState"] == "authoritative"
    assert authorized["reasonCodes"] == []
