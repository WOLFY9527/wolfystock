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
            "provenanceEvidence": {
                "primarySources": ["occ", "opra", "exchange", "licensed_provider"],
                "calendarSource": "listed_options_calendar",
            },
            "entitlementMetadata": {
                "optionsEntitlement": "enabled",
                "liveDelayedStatus": "delayed",
                "environment": "production",
                "decisionUseRights": "approved_internal_diagnostic_only",
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
            "expirationTaxonomyEvidence": {
                "weekly": True,
                "monthly": True,
                "quarterly": True,
                "standard": True,
                "leaps": True,
                "specialExpirations": False,
                "classificationSource": "occ_calendar_taxonomy",
            },
            "adjustedDeliverableEvidence": {
                "occMemoReference": "occ_memo_2026_042",
                "effectiveDate": "2026-05-20",
                "adjustedRootClass": "TEM1",
                "deliverableComponents": ["100 TEM"],
                "multiplier": 100,
                "cashInLieu": 0,
                "standardContract": False,
                "contractSymbolMapping": {
                    "preAdjustment": "TEM260619C00050000",
                    "postAdjustment": "TEM1260619C00050000",
                },
            },
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
    assert authorized["authorityEvidenceChecklist"] == {
        "provenance": {
            "present": True,
            "required": True,
            "fields": ["occ", "opra", "exchange", "licensed_provider"],
        },
        "entitlement": {
            "present": True,
            "required": True,
            "fields": [
                "options_entitlement",
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
        "expiration_taxonomy": {
            "present": True,
            "required": True,
            "fields": [
                "weekly",
                "monthly",
                "quarterly",
                "standard",
                "leaps",
                "special_expirations",
                "classification_source",
            ],
        },
        "adjusted_deliverable": {
            "present": True,
            "required": True,
            "fields": [
                "occ_memo_or_equivalent",
                "effective_date",
                "adjusted_root_or_class",
                "deliverable_components",
                "multiplier",
                "cash_in_lieu",
                "standard_or_non_standard",
                "contract_symbol_mapping",
            ],
        },
    }


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
        "expiration_calendar_provenance_evidence_missing",
        "expiration_calendar_entitlement_evidence_missing",
        "expiration_calendar_sla_evidence_missing",
        "expiration_calendar_taxonomy_evidence_missing",
        "expiration_calendar_adjusted_deliverable_evidence_missing",
        "expiration_calendar_coverage_not_authority",
    ]


def test_internal_policy_payload_without_checklist_evidence_stays_non_authoritative_even_when_coverage_looks_complete() -> None:
    diagnostic = build_options_expiration_calendar_authority_diagnostic(
        {
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
    )

    assert diagnostic["diagnosticOnly"] is True
    assert diagnostic["authorityState"] == "non_authoritative"
    assert diagnostic["authoritative"] is False
    assert diagnostic["reasonCodes"] == [
        "expiration_calendar_authority_missing",
        "expiration_calendar_provenance_evidence_missing",
        "expiration_calendar_entitlement_evidence_missing",
        "expiration_calendar_sla_evidence_missing",
        "expiration_calendar_taxonomy_evidence_missing",
        "expiration_calendar_adjusted_deliverable_evidence_missing",
        "expiration_calendar_coverage_not_authority",
    ]
    assert diagnostic["authorityEvidenceChecklist"] == {
        "provenance": {
            "present": False,
            "required": True,
            "fields": ["occ", "opra", "exchange", "licensed_provider"],
        },
        "entitlement": {
            "present": False,
            "required": True,
            "fields": [
                "options_entitlement",
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
        "expiration_taxonomy": {
            "present": False,
            "required": True,
            "fields": [
                "weekly",
                "monthly",
                "quarterly",
                "standard",
                "leaps",
                "special_expirations",
                "classification_source",
            ],
        },
        "adjusted_deliverable": {
            "present": False,
            "required": True,
            "fields": [
                "occ_memo_or_equivalent",
                "effective_date",
                "adjusted_root_or_class",
                "deliverable_components",
                "multiplier",
                "cash_in_lieu",
                "standard_or_non_standard",
                "contract_symbol_mapping",
            ],
        },
    }


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
        "expiration_calendar_provenance_evidence_missing",
        "expiration_calendar_entitlement_evidence_missing",
        "expiration_calendar_sla_evidence_missing",
        "expiration_calendar_taxonomy_evidence_missing",
        "expiration_calendar_adjusted_deliverable_evidence_missing",
        "expiration_calendar_coverage_not_authority",
    ]
