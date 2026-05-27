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
        "event_calendar_synthetic_not_authoritative",
        "event_calendar_source_authority_missing",
        "event_calendar_asof_or_freshness_missing",
        "event_calendar_confirmation_status_missing",
        "event_calendar_event_identity_missing",
        "event_calendar_coverage_not_authority",
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
        "event_calendar_coverage_not_authority",
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
            "provenanceEvidence": {
                "primarySources": ["licensed_provider", "official_calendar"],
                "sourceReference": "issuer_calendar_feed",
            },
            "entitlementMetadata": {
                "eventCalendarEntitlement": "licensed",
                "liveDelayedStatus": "delayed",
                "environment": "production",
                "decisionUseRights": "allowed",
                "redistributionRights": "internal_only",
                "auditTimestamp": "2026-05-26T12:00:10Z",
            },
            "slaEvidence": {
                "maxAgePolicy": "pt15m",
                "providerSlaStatus": "within_policy",
                "freshnessSeconds": 32,
                "freshnessState": "fresh",
                "latencyState": "nominal",
                "errorState": "none",
            },
            "eventTaxonomyEvidence": {
                "earnings": True,
                "dividendsExDividend": True,
                "splits": True,
                "corporateActions": True,
                "macroContextRelevance": "not_applicable",
            },
            "confirmationEvidence": {
                "confirmedOrEstimated": "confirmed",
                "eventDate": "2026-06-12",
                "eventTime": "08:30:00",
                "session": "regular",
                "timezone": "America/New_York",
                "providerEventIdentity": "provider-evt-001",
            },
            "coverageScopeEvidence": {
                "symbolCoverage": ["TEM"],
                "underlyingCoverage": ["TEM"],
                "lookaheadWindow": "30d",
                "dateRange": {"start": "2026-05-26", "end": "2026-06-26"},
                "coverageMetadata": {"eventCount": 4, "coverage": "complete"},
            },
            "sandboxOrProduction": "production",
        }
    )

    assert claimed["authoritative"] is False
    assert claimed["authorityState"] == "non_authoritative"
    assert "event_calendar_provider_self_claim_ignored" in claimed["reasonCodes"]
    assert "event_calendar_coverage_not_authority" in claimed["reasonCodes"]

    assert authorized["authoritative"] is True
    assert authorized["authorityState"] == "authoritative"
    assert authorized["reasonCodes"] == []
    assert authorized["authorityEvidenceChecklist"] == {
        "provenance": {
            "present": True,
            "required": True,
            "fields": [
                "licensed_provider",
                "exchange",
                "issuer",
                "official_calendar",
                "approved_internal_source",
            ],
        },
        "entitlement": {
            "present": True,
            "required": True,
            "fields": [
                "event_calendar_entitlement",
                "live_delayed_status",
                "environment",
                "decision_use_rights",
                "redistribution_rights",
                "audit_timestamp",
            ],
        },
        "sla_freshness": {
            "present": True,
            "required": True,
            "fields": [
                "as_of",
                "freshness",
                "max_age_policy",
                "provider_sla_status",
                "freshness_seconds",
                "freshness_state",
                "latency_or_error_state",
            ],
        },
        "event_taxonomy": {
            "present": True,
            "required": True,
            "fields": [
                "earnings",
                "dividends_ex_dividend",
                "splits",
                "corporate_actions",
                "macro_context_relevance",
            ],
        },
        "confirmation": {
            "present": True,
            "required": True,
            "fields": [
                "confirmed_or_estimated",
                "event_date_or_time",
                "session",
                "timezone",
                "provider_event_id_or_event_identity",
            ],
        },
        "coverage_scope": {
            "present": True,
            "required": True,
            "fields": [
                "symbol_or_underlying_coverage",
                "lookahead_window_or_date_range",
                "coverage_metadata",
            ],
        },
    }


def test_provider_id_marker_keeps_event_calendar_non_authoritative_even_when_other_fields_look_authoritative() -> None:
    diagnostic = build_options_event_calendar_authority_diagnostic(
        {
            "providerId": "request_payload",
            "sourceType": "live",
            "sourceAuthority": "authorized",
            "authorityPolicySource": INTERNAL_OPTIONS_EVENT_CALENDAR_AUTHORITY_POLICY_SOURCE,
            "eventCalendarStatus": "available",
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
            "eventTypesCovered": ["earnings", "dividends", "splits", "fomc"],
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

    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert diagnostic["reasonCodes"] == [
        "event_calendar_authority_missing",
        "event_calendar_request_supplied_not_authoritative",
        "event_calendar_provenance_evidence_missing",
        "event_calendar_entitlement_evidence_missing",
        "event_calendar_sla_evidence_missing",
        "event_calendar_event_taxonomy_evidence_missing",
        "event_calendar_confirmation_evidence_missing",
        "event_calendar_coverage_scope_evidence_missing",
        "event_calendar_coverage_not_authority",
    ]


def test_snake_case_provider_self_claim_alias_is_ignored_for_event_calendar() -> None:
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
            "provider_decision_authority_claim": True,
            "recommendation_authority_claim": True,
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
        "event_calendar_coverage_not_authority",
    ]


def test_event_presence_count_and_types_do_not_grant_authority_without_checklist_evidence() -> None:
    diagnostic = build_options_event_calendar_authority_diagnostic(
        {
            "providerId": "future_authorized_provider",
            "sourceType": "live",
            "sourceAuthority": "authorized",
            "authorityPolicySource": INTERNAL_OPTIONS_EVENT_CALENDAR_AUTHORITY_POLICY_SOURCE,
            "eventCalendarStatus": "available",
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
            "eventTypesCovered": ["earnings", "dividends", "splits", "macro"],
            "symbolCoverage": ["TEM"],
            "underlyingCoverage": ["TEM"],
            "lookaheadWindow": "30d",
            "dateRange": {"start": "2026-05-26", "end": "2026-06-26"},
            "timezone": "America/New_York",
            "sessionMetadata": {"session": "pre_market"},
            "confirmationStatus": "confirmed",
            "eventId": "evt-001",
            "providerEventId": "provider-evt-001",
            "coverageMetadata": {
                "eventCount": 4,
                "coverage": "complete",
                "eventTypesCovered": ["earnings", "dividends", "splits", "macro"],
            },
            "sandboxOrProduction": "production",
        }
    )

    assert diagnostic["diagnosticOnly"] is True
    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert diagnostic["reasonCodes"] == [
        "event_calendar_authority_missing",
        "event_calendar_provenance_evidence_missing",
        "event_calendar_entitlement_evidence_missing",
        "event_calendar_sla_evidence_missing",
        "event_calendar_event_taxonomy_evidence_missing",
        "event_calendar_confirmation_evidence_missing",
        "event_calendar_coverage_scope_evidence_missing",
        "event_calendar_coverage_not_authority",
    ]
    assert diagnostic["authorityEvidenceChecklist"] == {
        "provenance": {
            "present": False,
            "required": True,
            "fields": [
                "licensed_provider",
                "exchange",
                "issuer",
                "official_calendar",
                "approved_internal_source",
            ],
        },
        "entitlement": {
            "present": False,
            "required": True,
            "fields": [
                "event_calendar_entitlement",
                "live_delayed_status",
                "environment",
                "decision_use_rights",
                "redistribution_rights",
                "audit_timestamp",
            ],
        },
        "sla_freshness": {
            "present": False,
            "required": True,
            "fields": [
                "as_of",
                "freshness",
                "max_age_policy",
                "provider_sla_status",
                "freshness_seconds",
                "freshness_state",
                "latency_or_error_state",
            ],
        },
        "event_taxonomy": {
            "present": False,
            "required": True,
            "fields": [
                "earnings",
                "dividends_ex_dividend",
                "splits",
                "corporate_actions",
                "macro_context_relevance",
            ],
        },
        "confirmation": {
            "present": False,
            "required": True,
            "fields": [
                "confirmed_or_estimated",
                "event_date_or_time",
                "session",
                "timezone",
                "provider_event_id_or_event_identity",
            ],
        },
        "coverage_scope": {
            "present": False,
            "required": True,
            "fields": [
                "symbol_or_underlying_coverage",
                "lookahead_window_or_date_range",
                "coverage_metadata",
            ],
        },
    }


def test_complete_coverage_without_confirmation_or_identity_stays_non_authoritative() -> None:
    diagnostic = build_options_event_calendar_authority_diagnostic(
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
            "coverageMetadata": {"eventCount": 4, "coverage": "complete"},
            "sandboxOrProduction": "production",
        }
    )

    assert diagnostic["diagnosticOnly"] is True
    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert "event_calendar_confirmation_status_missing" in diagnostic["reasonCodes"]
    assert "event_calendar_event_identity_missing" in diagnostic["reasonCodes"]
    assert "event_calendar_provenance_evidence_missing" in diagnostic["reasonCodes"]
    assert "event_calendar_entitlement_evidence_missing" in diagnostic["reasonCodes"]
    assert "event_calendar_sla_evidence_missing" in diagnostic["reasonCodes"]
    assert "event_calendar_event_taxonomy_evidence_missing" in diagnostic["reasonCodes"]
    assert "event_calendar_confirmation_evidence_missing" in diagnostic["reasonCodes"]
    assert "event_calendar_coverage_scope_evidence_missing" in diagnostic["reasonCodes"]
    assert "event_calendar_coverage_not_authority" in diagnostic["reasonCodes"]


def test_url_shaped_event_calendar_labels_are_redacted_but_safe_labels_remain() -> None:
    diagnostic = build_options_event_calendar_authority_diagnostic(
        {
            "providerId": "https://provider.example/events",
            "sourceType": "www.provider.example",
            "sourceAuthority": "http://provider.example/policy",
            "eventCalendarStatus": "available",
            "asOf": "2026-05-26T12:00:00Z",
            "freshness": "fresh",
            "eventTypesCovered": ["earnings"],
            "underlyingCoverage": ["TEM"],
            "dateRange": {"start": "2026-05-26", "end": "2026-06-26"},
            "timezone": "America/New_York",
            "confirmationStatus": "confirmed",
            "eventId": "evt-001",
            "providerEventId": "provider-evt-001",
            "coverageMetadata": {
                "providerLabel": "tradier",
                "sourceUrl": "https://provider.example/events?token=demo",
            },
            "sessionMetadata": {
                "calendarLandingPage": "www.provider.example/calendar",
                "providerLabel": "tradier",
            },
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
    assert diagnostic["sessionMetadata"]["calendarLandingPage"] == "redacted"
    assert diagnostic["sessionMetadata"]["providerLabel"] == "tradier"


def test_proxy_event_calendar_and_provider_self_claim_only_marker_stay_non_authoritative() -> None:
    diagnostic = build_options_event_calendar_authority_diagnostic(
        {
            "providerId": "future_authorized_provider",
            "sourceType": "proxy",
            "sourceAuthority": "provider_self_claim_only",
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

    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert diagnostic["reasonCodes"] == [
        "event_calendar_authority_missing",
        "event_calendar_proxy_not_authoritative",
        "event_calendar_provider_self_claim_only_not_authoritative",
        "event_calendar_provenance_evidence_missing",
        "event_calendar_entitlement_evidence_missing",
        "event_calendar_sla_evidence_missing",
        "event_calendar_event_taxonomy_evidence_missing",
        "event_calendar_confirmation_evidence_missing",
        "event_calendar_coverage_scope_evidence_missing",
        "event_calendar_coverage_not_authority",
    ]
