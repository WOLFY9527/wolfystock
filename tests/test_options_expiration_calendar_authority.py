# -*- coding: utf-8 -*-
"""Diagnostic-only expiration-calendar authority contract tests."""

from __future__ import annotations

from src.services.options_expiration_calendar_authority import (
    INTERNAL_OPTIONS_EXPIRATION_CALENDAR_AUTHORITY_POLICY_SOURCE,
    REQUIRED_FUTURE_EXPIRATION_CALENDAR_AUTHORITY_EVIDENCE_FIELDS,
    build_options_expiration_calendar_authority_diagnostic,
)


def test_missing_expiration_calendar_authority_is_distinct_from_non_authoritative_proxy_data() -> None:
    diagnostic = build_options_expiration_calendar_authority_diagnostic(None)

    assert diagnostic["diagnosticOnly"] is True
    assert diagnostic["authorityState"] == "missing"
    assert diagnostic["authoritative"] is False
    assert diagnostic["reasonCodes"] == [
        "expiration_calendar_authority_missing",
        "expiration_calendar_missing",
        "expiration_calendar_source_authority_missing",
        "expiration_calendar_asof_or_freshness_missing",
        "expiration_calendar_coverage_metadata_missing",
        "expiration_calendar_date_range_missing",
    ]
    assert diagnostic["requiredFutureAuthorityEvidence"] == list(
        REQUIRED_FUTURE_EXPIRATION_CALENDAR_AUTHORITY_EVIDENCE_FIELDS
    )


def test_fixture_expiration_calendar_stays_non_authoritative_even_when_coverage_is_complete() -> None:
    diagnostic = build_options_expiration_calendar_authority_diagnostic(
        {
            "providerId": "synthetic_options_lab_fixture",
            "sourceType": "fixture",
            "expirationCalendarStatus": "available",
            "underlying": "TEM",
            "expirationDates": ["2026-06-19", "2026-08-21"],
            "expirationCount": 2,
            "expirationTypes": ["monthly"],
            "dateRange": {"start": "2026-06-19", "end": "2026-08-21"},
            "coverageMetadata": {
                "expirationCoverage": "complete",
                "expirationCount": 2,
                "chainAvailability": "complete",
            },
            "sandboxOrProduction": "not_provider_sourced",
        }
    )

    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert diagnostic["providerId"] == "synthetic_options_lab_fixture"
    assert diagnostic["sourceType"] == "fixture"
    assert diagnostic["expirationCalendarStatus"] == "available"
    assert diagnostic["coverageMetadata"]["expirationCoverage"] == "complete"
    assert diagnostic["reasonCodes"] == [
        "expiration_calendar_authority_missing",
        "expiration_calendar_fixture_not_authoritative",
        "expiration_calendar_synthetic_not_authoritative",
        "expiration_calendar_source_authority_missing",
        "expiration_calendar_asof_or_freshness_missing",
        "expiration_calendar_coverage_not_authority",
    ]


def test_request_shaped_expiration_calendar_remains_non_authoritative_even_if_fully_shaped() -> None:
    diagnostic = build_options_expiration_calendar_authority_diagnostic(
        {
            "providerId": "request_payload",
            "sourceType": "request_supplied",
            "sourceAuthority": "provider_self_claim",
            "authorityPolicySource": "provider_documentation",
            "expirationCalendarStatus": "available",
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
            "underlying": "TEM",
            "expirationDates": ["2026-06-19", "2026-08-21", "2027-01-15"],
            "expirationCount": 3,
            "expirationTypes": ["weekly", "monthly", "leaps"],
            "dateRange": {"start": "2026-06-19", "end": "2027-01-15"},
            "lookaheadWindow": "234d",
            "coverageMetadata": {
                "expirationCoverage": "complete",
                "expirationCount": 3,
                "dateRangeDays": 234,
            },
            "exchange": "OPRA",
            "authorizedSourceMetadata": {"venue": "opra"},
            "sandboxOrProduction": "production",
            "providerDecisionAuthorityClaim": True,
            "recommendationAuthorityClaim": True,
            "notes": ["request_shaped"],
        }
    )

    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert diagnostic["reasonCodes"] == [
        "expiration_calendar_authority_missing",
        "expiration_calendar_request_supplied_not_authoritative",
        "expiration_calendar_request_shaped_not_authoritative",
        "expiration_calendar_provider_self_claim_ignored",
        "expiration_calendar_coverage_not_authority",
    ]


def test_internal_policy_is_required_before_any_expiration_calendar_payload_can_be_authoritative() -> None:
    claimed = build_options_expiration_calendar_authority_diagnostic(
        {
            "providerId": "tradier",
            "sourceType": "adapter_contract",
            "sourceAuthority": "provider_reported",
            "expirationCalendarStatus": "available",
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
            "underlying": "TEM",
            "expirationDates": ["2026-06-19", "2026-08-21"],
            "expirationCount": 2,
            "expirationTypes": ["monthly"],
            "dateRange": {"start": "2026-06-19", "end": "2026-08-21"},
            "coverageMetadata": {"expirationCoverage": "complete", "expirationCount": 2},
            "exchange": "OPRA",
            "sandboxOrProduction": "sandbox",
            "providerDecisionAuthorityClaim": True,
        }
    )
    authorized = build_options_expiration_calendar_authority_diagnostic(
        {
            "providerId": "future_authorized_provider",
            "sourceType": "live",
            "sourceAuthority": "authorized",
            "authorityPolicySource": INTERNAL_OPTIONS_EXPIRATION_CALENDAR_AUTHORITY_POLICY_SOURCE,
            "expirationCalendarStatus": "available",
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
            "underlying": "TEM",
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
    )

    assert claimed["authoritative"] is False
    assert claimed["authorityState"] == "non_authoritative"
    assert "expiration_calendar_provider_self_claim_ignored" in claimed["reasonCodes"]
    assert "expiration_calendar_coverage_not_authority" in claimed["reasonCodes"]

    assert authorized["authoritative"] is True
    assert authorized["authorityState"] == "authoritative"
    assert authorized["reasonCodes"] == []


def test_provider_id_marker_keeps_expiration_calendar_non_authoritative_even_when_other_fields_look_authoritative() -> None:
    diagnostic = build_options_expiration_calendar_authority_diagnostic(
        {
            "providerId": "fallback_provider_snapshot",
            "sourceType": "live",
            "sourceAuthority": "authorized",
            "authorityPolicySource": INTERNAL_OPTIONS_EXPIRATION_CALENDAR_AUTHORITY_POLICY_SOURCE,
            "expirationCalendarStatus": "available",
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
            "underlying": "TEM",
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
    )

    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert diagnostic["reasonCodes"] == [
        "expiration_calendar_authority_missing",
        "expiration_calendar_fallback_not_authoritative",
        "expiration_calendar_coverage_not_authority",
    ]


def test_snake_case_provider_self_claim_alias_is_ignored_for_expiration_calendar() -> None:
    diagnostic = build_options_expiration_calendar_authority_diagnostic(
        {
            "providerId": "request_payload",
            "sourceType": "request_supplied",
            "sourceAuthority": "provider_self_claim",
            "authorityPolicySource": "provider_documentation",
            "expirationCalendarStatus": "available",
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
            "underlying": "TEM",
            "expirationDates": ["2026-06-19", "2026-08-21", "2027-01-15"],
            "expirationCount": 3,
            "expirationTypes": ["weekly", "monthly", "leaps"],
            "dateRange": {"start": "2026-06-19", "end": "2027-01-15"},
            "lookaheadWindow": "234d",
            "coverageMetadata": {
                "expirationCoverage": "complete",
                "expirationCount": 3,
                "dateRangeDays": 234,
            },
            "exchange": "OPRA",
            "authorizedSourceMetadata": {"venue": "opra"},
            "sandboxOrProduction": "production",
            "provider_decision_authority_claim": True,
            "recommendation_authority_claim": True,
            "notes": ["request_shaped"],
        }
    )

    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert diagnostic["reasonCodes"] == [
        "expiration_calendar_authority_missing",
        "expiration_calendar_request_supplied_not_authoritative",
        "expiration_calendar_request_shaped_not_authoritative",
        "expiration_calendar_provider_self_claim_ignored",
        "expiration_calendar_coverage_not_authority",
    ]


def test_url_shaped_expiration_calendar_labels_are_redacted_but_safe_labels_remain() -> None:
    diagnostic = build_options_expiration_calendar_authority_diagnostic(
        {
            "providerId": "https://provider.example/expirations",
            "sourceType": "www.provider.example",
            "sourceAuthority": "http://provider.example/policy",
            "expirationCalendarStatus": "available",
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
            "underlying": "TEM",
            "expirationDates": ["2026-06-19", "2026-08-21"],
            "expirationCount": 2,
            "expirationTypes": ["monthly"],
            "dateRange": {"start": "2026-06-19", "end": "2026-08-21"},
            "coverageMetadata": {
                "providerLabel": "tradier",
                "sourceUrl": "https://provider.example/expirations?token=demo",
            },
            "authorizedSourceMetadata": {
                "calendarLandingPage": "www.provider.example/calendar",
                "providerLabel": "tradier",
            },
            "exchange": "OPRA",
            "sandboxOrProduction": "sandbox",
        }
    )

    assert diagnostic["diagnosticOnly"] is True
    assert diagnostic["authoritative"] is False
    assert diagnostic["providerId"] == "redacted"
    assert diagnostic["sourceType"] == "redacted"
    assert diagnostic["sourceAuthority"] == "redacted"
    assert diagnostic["coverageMetadata"]["providerLabel"] == "tradier"
    assert diagnostic["coverageMetadata"]["sourceUrl"] == "redacted"
    assert diagnostic["authorizedSourceMetadata"]["calendarLandingPage"] == "redacted"
    assert diagnostic["authorizedSourceMetadata"]["providerLabel"] == "tradier"


def test_proxy_expiration_calendar_and_provider_self_claim_only_marker_stay_non_authoritative() -> None:
    diagnostic = build_options_expiration_calendar_authority_diagnostic(
        {
            "providerId": "future_authorized_provider",
            "sourceType": "proxy",
            "sourceAuthority": "provider_self_claim_only",
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
    )

    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert diagnostic["reasonCodes"] == [
        "expiration_calendar_authority_missing",
        "expiration_calendar_proxy_not_authoritative",
        "expiration_calendar_provider_self_claim_only_not_authoritative",
        "expiration_calendar_coverage_not_authority",
    ]
