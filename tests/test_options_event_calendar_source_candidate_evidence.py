# -*- coding: utf-8 -*-
"""Pure contract tests for event-calendar source candidate evidence."""

from __future__ import annotations

from src.services.options_event_calendar_source_candidate_evidence import (
    FORBIDDEN_AUTHORITY_OUTPUTS,
    REQUIRED_EVIDENCE_FAMILIES,
    build_event_calendar_source_candidate_evidence,
)


def test_empty_candidate_evidence_stays_diagnostic_candidate_only_and_non_authoritative() -> None:
    contract = build_event_calendar_source_candidate_evidence(None)

    assert contract["diagnosticOnly"] is True
    assert contract["candidateOnly"] is True
    assert contract["authorityGrant"] is False
    assert contract["sourceIdentity"] == {}
    assert contract["provenance"] == {}
    assert contract["entitlement"] == {}
    assert contract["freshnessSla"] == {}
    assert contract["eventCoverage"] == {}
    assert contract["eventTaxonomy"] == {}
    assert contract["confirmationEvidence"] == {}
    assert contract["eventIdentityEvidence"] == {}
    assert contract["timezoneSessionEvidence"] == {}
    assert contract["errorAuditState"] == {}
    assert contract["missingEvidenceFamilies"] == list(REQUIRED_EVIDENCE_FAMILIES)
    assert contract["forbiddenAuthorityOutputs"] == list(FORBIDDEN_AUTHORITY_OUTPUTS)


def test_full_mocked_candidate_evidence_remains_observation_only_without_authority() -> None:
    contract = build_event_calendar_source_candidate_evidence(
        {
            "candidateSourceName": "licensed_event_packet",
            "providerName": "licensed_event_vendor",
            "providerId": "future_event_vendor",
            "distributorName": "issuer_calendar_distributor",
            "sourceClass": "licensed_source_candidate",
            "marketRegionCoverageClaim": "us_equities",
            "evidenceCaptureMethod": "contract_review",
            "documentReference": "event_doc_ref_2026_q2",
            "productName": "issuer_event_calendar",
            "provenanceChain": [
                "issuer_notice",
                "licensed_redistributor",
                "internal_packet_review",
            ],
            "licensedProviderBackingClaim": True,
            "licensedProviderProofReference": "license_ref_a",
            "exchangeBackingClaim": True,
            "exchangeProofReference": "exchange_notice_17",
            "issuerBackingClaim": True,
            "issuerProofReference": "issuer_ir_calendar",
            "officialCalendarBackingClaim": True,
            "officialCalendarProofReference": "official_calendar_ref",
            "entitlementRequirements": "internal_research",
            "licenseTier": "analytics",
            "allowedInternalUse": "internal_display",
            "accountBoundary": "team_workspace",
            "redistributionRights": "internal_only",
            "internalDecisionUseRights": "not_approved",
            "storageRights": "90d_retention",
            "explicitRestrictions": ["no_external_distribution"],
            "environmentType": "production",
            "environmentEvidenceSource": "signed_order_form",
            "liveDelayedStatus": "delayed",
            "delayWindow": "15m",
            "delayDisclaimer": "delayed_event_feed",
            "asOf": "2026-05-27T09:30:00Z",
            "freshnessStatement": "updated_after_publisher_confirmation",
            "serviceLevelExpectation": "published_before_market_open_when_available",
            "maxAgePolicy": "pt15m",
            "staleDataHandling": "mark_stale_after_policy_window",
            "coverageType": "issuer_event_calendar",
            "lookaheadWindow": "next_90d",
            "observedEventCount": 5,
            "supportedRegions": ["us"],
            "unsupportedRegions": ["hk"],
            "eventDateRange": {"start": "2026-06-01", "end": "2026-08-29"},
            "timelineCoverageNotes": ["earnings_and_dividends_sampled"],
            "eventTaxonomy": {
                "earnings": "proven",
                "dividends": "proven",
                "exDividend": "proven",
                "splits": "partial",
                "corporateActions": "partial",
                "fomcMacroContext": "proven",
            },
            "macroPolicyScope": "options_macro_context_only",
            "confirmationStatusModel": "confirmed_estimated_announced",
            "confirmationEvidenceSource": "issuer_notice_plus_vendor_mapping",
            "statusChangeHandling": "correction_events_replace_prior_status",
            "providerEventIdField": "vendor_event_id",
            "eventIdentitySemantics": "event_key_per_symbol_type_date_time",
            "dedupeRules": "provider_id_plus_symbol_plus_type_plus_timestamp",
            "correctionHandling": "latest_revision_wins",
            "eventDateField": "event_date",
            "eventTimeField": "event_time",
            "tradingSessionField": "session_label",
            "timezoneField": "timezone_name",
            "timezoneNormalizationNotes": "normalize_to_exchange_timezone",
            "sessionInterpretationNotes": "bmo_amc_intraday_mapped",
            "sanitizedErrorClasses": ["none"],
            "auditCaptureTimestamp": "2026-05-27T10:00:00Z",
            "reviewer": "options_ops",
            "unresolvedAmbiguityNotes": [],
            "providerDecisionAuthority": True,
            "decisionGrade": "A",
        }
    )

    assert contract["authorityGrant"] is False
    assert contract["diagnosticOnly"] is True
    assert contract["candidateOnly"] is True
    assert contract["missingEvidenceFamilies"] == []
    assert contract["sourceIdentity"]["providerId"] == "future_event_vendor"
    assert contract["provenance"]["backing"]["issuer"]["claimed"] is True
    assert contract["entitlement"]["internalDecisionUseRights"] == "not_approved"
    assert contract["freshnessSla"]["maxAgePolicy"] == "pt15m"
    assert contract["eventCoverage"]["observedEventCount"] == 5
    assert contract["eventTaxonomy"]["earnings"] == "proven"
    assert contract["eventTaxonomy"]["fomcMacroContext"] == "proven"
    assert contract["confirmationEvidence"]["confirmationStatusModel"] == (
        "confirmed_estimated_announced"
    )
    assert contract["eventIdentityEvidence"]["providerEventIdField"] == "vendor_event_id"
    assert contract["timezoneSessionEvidence"]["timezoneField"] == "timezone_name"
    assert contract["forbiddenAuthorityOutputs"] == list(FORBIDDEN_AUTHORITY_OUTPUTS)
    assert "providerDecisionAuthority" not in contract
    assert "decisionGrade" not in contract


def test_event_presence_count_type_timeline_and_generic_macro_context_do_not_remove_gaps() -> None:
    contract = build_event_calendar_source_candidate_evidence(
        {
            "coverageType": "timeline_sample",
            "observedEventCount": 4,
            "eventDateRange": {"start": "2026-06-01", "end": "2026-06-30"},
            "timelineCoverageNotes": ["earnings_timeline_present"],
            "eventTaxonomy": {
                "earnings": "proven",
                "dividends": "partial",
                "exDividend": "partial",
                "fomcMacroContext": "proven",
            },
            "macroContextNotes": ["fomc_calendar_seen"],
        }
    )

    assert contract["authorityGrant"] is False
    assert "coverage_scope" not in contract["missingEvidenceFamilies"]
    assert "source_identity_and_provenance_chain" in contract["missingEvidenceFamilies"]
    assert (
        "licensed_provider_exchange_issuer_official_calendar_backing"
        in contract["missingEvidenceFamilies"]
    )
    assert "entitlement_license_and_use_rights" in contract["missingEvidenceFamilies"]
    assert "redistribution_and_decision_use_rights" in contract["missingEvidenceFamilies"]
    assert "production_vs_sandbox" in contract["missingEvidenceFamilies"]
    assert "delayed_vs_live_status" in contract["missingEvidenceFamilies"]
    assert "as_of_freshness_sla_max_age_policy" in contract["missingEvidenceFamilies"]
    assert "confirmation_status" in contract["missingEvidenceFamilies"]
    assert "provider_event_id_and_event_identity" in contract["missingEvidenceFamilies"]
    assert "event_date_time_session_timezone" in contract["missingEvidenceFamilies"]


def test_provider_self_claims_and_current_provider_ids_do_not_grant_authority() -> None:
    contract = build_event_calendar_source_candidate_evidence(
        {
            "providerId": "tradier",
            "providerName": "tradier",
            "sourceClass": "provider_self_claim_only",
            "documentReference": "provider_docs",
            "providerDecisionAuthority": True,
            "recommendationAuthority": True,
            "sourceAuthorityAllowed": True,
            "liveCallEnablement": True,
            "allowedInternalUse": "claimed",
            "environmentType": "production",
            "liveDelayedStatus": "live",
            "coverageType": "provider_marketing_claim",
            "observedEventCount": 2,
            "eventDateRange": {"start": "2026-06-01", "end": "2026-06-02"},
        }
    )

    assert contract["authorityGrant"] is False
    assert contract["sourceIdentity"]["providerId"] == "tradier"
    assert contract["sourceIdentity"]["providerName"] == "tradier"
    assert "entitlement_license_and_use_rights" in contract["missingEvidenceFamilies"]
    assert "redistribution_and_decision_use_rights" in contract["missingEvidenceFamilies"]
    assert "as_of_freshness_sla_max_age_policy" in contract["missingEvidenceFamilies"]
    assert "providerDecisionAuthority" not in contract
    assert "recommendationAuthority" not in contract
    assert "sourceAuthorityAllowed" not in contract
    assert "liveCallEnablement" not in contract


def test_url_like_secret_and_payload_shaped_strings_are_sanitized_or_rejected() -> None:
    contract = build_event_calendar_source_candidate_evidence(
        {
            "candidateSourceName": "{\"raw_payload\": true}",
            "providerName": "https://provider.example.com/private?token=abc",
            "documentReference": "Authorization: Bearer super-secret",
            "provenanceChain": [
                "licensed_vendor",
                "api_key=abc123",
                "https://exchange.example.com",
            ],
            "licensedProviderProofReference": "https://provider.example.com/license",
            "confirmationEvidenceSource": "{\"headers\": {\"authorization\": \"secret\"}}",
            "reviewer": "ops@example.com",
        }
    )

    assert contract["sourceIdentity"]["candidateSourceName"] == "redacted"
    assert contract["sourceIdentity"]["providerName"] == "redacted"
    assert contract["sourceIdentity"]["documentReference"] == "redacted"
    assert contract["provenance"]["provenanceChain"] == ["licensed_vendor", "redacted", "redacted"]
    assert contract["provenance"]["backing"]["licensedProvider"]["proofReference"] == "redacted"
    assert contract["confirmationEvidence"]["confirmationEvidenceSource"] == "redacted"
    assert contract["errorAuditState"]["reviewer"] == "redacted"


def test_no_forbidden_authority_outputs_are_emitted() -> None:
    contract = build_event_calendar_source_candidate_evidence(
        {
            "providerDecisionAuthority": True,
            "recommendationAuthority": True,
            "decisionGrade": "tradeable",
            "gateDecision": "pass",
            "sourceAuthorityAllowed": True,
            "providerRouting": {"target": "tradier"},
            "liveCallEnablement": True,
        }
    )

    assert contract["forbiddenAuthorityOutputs"] == [
        "authorityGrant true",
        "providerDecisionAuthority",
        "recommendationAuthority",
        "decisionGrade",
        "gateDecision",
        "sourceAuthorityAllowed",
        "provider routing",
        "live-call enablement",
    ]
    assert "providerDecisionAuthority" not in contract
    assert "recommendationAuthority" not in contract
    assert "decisionGrade" not in contract
    assert "gateDecision" not in contract
    assert "sourceAuthorityAllowed" not in contract
    assert "providerRouting" not in contract
    assert "liveCallEnablement" not in contract
