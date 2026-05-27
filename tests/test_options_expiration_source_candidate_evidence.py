# -*- coding: utf-8 -*-
"""Pure contract tests for expiration source candidate evidence."""

from __future__ import annotations

from src.services.options_expiration_source_candidate_evidence import (
    FORBIDDEN_AUTHORITY_OUTPUTS,
    REQUIRED_EVIDENCE_FAMILIES,
    build_expiration_calendar_source_candidate_evidence,
)


def test_empty_candidate_evidence_stays_diagnostic_candidate_only_and_non_authoritative() -> None:
    contract = build_expiration_calendar_source_candidate_evidence(None)

    assert contract["diagnosticOnly"] is True
    assert contract["candidateOnly"] is True
    assert contract["authorityGrant"] is False
    assert contract["sourceIdentity"] == {}
    assert contract["provenance"] == {}
    assert contract["entitlement"] == {}
    assert contract["freshnessSla"] == {}
    assert contract["expirationCoverage"] == {}
    assert contract["expirationTaxonomy"] == {}
    assert contract["adjustedDeliverableEvidence"] == {}
    assert contract["missingEvidenceFamilies"] == list(REQUIRED_EVIDENCE_FAMILIES)
    assert contract["forbiddenAuthorityOutputs"] == list(FORBIDDEN_AUTHORITY_OUTPUTS)


def test_full_mocked_candidate_evidence_remains_observation_only_without_authority() -> None:
    contract = build_expiration_calendar_source_candidate_evidence(
        {
            "candidateSourceName": "listed_options_calendar_packet",
            "providerName": "licensed_calendar_vendor",
            "providerId": "future_vendor",
            "distributorName": "exchange_distribution_partner",
            "sourceClass": "licensed_source_candidate",
            "marketRegionCoverageClaim": "us_listed_options",
            "evidenceCaptureMethod": "contractual_review",
            "documentReference": "doc_ref_2026_q2",
            "provenanceChain": [
                "vendor_contract",
                "licensed_redistributor",
                "exchange_calendar_notice",
            ],
            "occBackingClaim": True,
            "occProofReference": "occ_ref_2026_042",
            "opraBackingClaim": True,
            "opraProofReference": "opra_notice_2026_05",
            "exchangeBackingClaim": True,
            "exchangeProofReference": "cboe_calendar_spec",
            "licensedSourceBackingClaim": True,
            "licensedSourceProofReference": "license_schedule_a",
            "venueFamily": "us_options_exchanges",
            "symbolUniverse": ["TEM", "AAPL"],
            "productClass": "listed_equity_options",
            "calendarScopeBoundaries": "listed_equity_options_only",
            "unsupportedVenueGaps": ["futures_options"],
            "entitlementRequirements": "options_level_1",
            "licenseTier": "internal_analytics",
            "redistributionRights": "internal_only",
            "storageRetentionLimits": "90d",
            "internalDisplayRights": "allowed",
            "internalDecisionUseRights": "not_approved",
            "explicitRestrictions": ["no_external_distribution"],
            "environmentType": "production",
            "environmentEvidenceSource": "signed_order_form",
            "environmentLimitations": ["no_retail_redistribution"],
            "liveDelayedStatus": "delayed",
            "delayPolicy": "15m",
            "delayedLabels": ["delayed_options_data"],
            "liveStatusProven": True,
            "asOf": "2026-05-27T09:30:00Z",
            "freshnessStatement": "fresh_within_documented_delay",
            "updateCadence": "intraday",
            "serviceLevelExpectation": "published_daily_plus_intraday_notices",
            "maxAgePolicy": "pt15m",
            "staleDataHandlingNotes": "flag_if_older_than_policy",
            "sampleExpirationDates": ["2026-06-19", "2026-06-26", "2027-01-15"],
            "observedExpirationCount": 3,
            "observedDateRange": {"start": "2026-06-19", "end": "2027-01-15"},
            "symbolLevelVariationNotes": ["leaps_not_universal"],
            "missingDateOrTruncationEvidence": "none_observed",
            "expirationTaxonomy": {
                "weekly": "proven",
                "monthly": "proven",
                "quarterly": "proven",
                "standard": "proven",
                "leaps": "proven",
                "specialExpirations": "partial",
            },
            "splitAdjustmentHandlingEvidence": "occ_adjustment_memos_reviewed",
            "adjustedDeliverableEvidence": "non_standard_contracts_documented",
            "contractMultiplierHandlingEvidence": "multiplier_rules_documented",
            "corporateActionImpactNotes": ["reverse_split_case_reviewed"],
            "knownLimitationsOrUnknowns": ["specials_need_manual_review"],
            "occMemoReference": "occ_memo_2026_042",
            "equivalentAdjustmentNotice": "exchange_adjustment_notice_17",
            "referenceCitation": "citation_2026_05_27",
            "sanitizedErrorClasses": ["none"],
            "blockedOrMissingEvidenceReasons": [],
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
    assert contract["sourceIdentity"]["providerId"] == "future_vendor"
    assert contract["provenance"]["backing"]["occ"]["claimed"] is True
    assert contract["entitlement"]["internalDecisionUseRights"] == "not_approved"
    assert contract["freshnessSla"]["maxAgePolicy"] == "pt15m"
    assert contract["expirationCoverage"]["observedExpirationCount"] == 3
    assert contract["expirationTaxonomy"]["specialExpirations"] == "partial"
    assert contract["adjustedDeliverableEvidence"]["occMemoReference"] == "occ_memo_2026_042"
    assert contract["forbiddenAuthorityOutputs"] == list(FORBIDDEN_AUTHORITY_OUTPUTS)


def test_coverage_alone_does_not_remove_provenance_entitlement_sla_taxonomy_or_adjusted_gaps() -> None:
    contract = build_expiration_calendar_source_candidate_evidence(
        {
            "sampleExpirationDates": ["2026-06-19", "2026-06-26"],
            "observedExpirationCount": 2,
            "observedDateRange": {"start": "2026-06-19", "end": "2026-06-26"},
            "symbolLevelVariationNotes": ["single_underlying_only"],
        }
    )

    assert contract["authorityGrant"] is False
    assert "expiration_dates_count_and_range" not in contract["missingEvidenceFamilies"]
    assert "source_identity_and_provenance_chain" in contract["missingEvidenceFamilies"]
    assert "licensed_source_backing" in contract["missingEvidenceFamilies"]
    assert "venue_and_calendar_scope" in contract["missingEvidenceFamilies"]
    assert "entitlement_and_decision_use_rights" in contract["missingEvidenceFamilies"]
    assert "production_vs_sandbox" in contract["missingEvidenceFamilies"]
    assert "delayed_vs_live_status" in contract["missingEvidenceFamilies"]
    assert "freshness_sla_and_max_age" in contract["missingEvidenceFamilies"]
    assert "expiration_taxonomy" in contract["missingEvidenceFamilies"]
    assert "adjusted_deliverable_and_corporate_action_proof" in contract["missingEvidenceFamilies"]
    assert "occ_memo_or_equivalent_reference" in contract["missingEvidenceFamilies"]


def test_provider_self_claims_and_current_provider_ids_do_not_grant_authority() -> None:
    contract = build_expiration_calendar_source_candidate_evidence(
        {
            "providerId": "tradier",
            "providerName": "tradier",
            "sourceClass": "provider_self_claim_only",
            "marketRegionCoverageClaim": "broad_coverage",
            "documentReference": "provider_docs",
            "providerDecisionAuthority": True,
            "recommendationAuthority": True,
            "sourceAuthorityAllowed": True,
            "liveCallEnablement": True,
            "entitlementRequirements": "claimed",
            "environmentType": "production",
            "liveDelayedStatus": "live",
            "sampleExpirationDates": ["2026-06-19"],
            "observedExpirationCount": 1,
            "observedDateRange": {"start": "2026-06-19", "end": "2026-06-19"},
        }
    )

    assert contract["authorityGrant"] is False
    assert contract["sourceIdentity"]["providerId"] == "tradier"
    assert contract["sourceIdentity"]["providerName"] == "tradier"
    assert "entitlement_and_decision_use_rights" in contract["missingEvidenceFamilies"]
    assert "freshness_sla_and_max_age" in contract["missingEvidenceFamilies"]
    assert "providerDecisionAuthority" not in contract
    assert "recommendationAuthority" not in contract
    assert "sourceAuthorityAllowed" not in contract
    assert "liveCallEnablement" not in contract


def test_url_like_secret_and_payload_shaped_strings_are_sanitized_or_rejected() -> None:
    contract = build_expiration_calendar_source_candidate_evidence(
        {
            "candidateSourceName": "{\"raw_payload\": true}",
            "providerName": "https://provider.example.com/private?token=abc",
            "documentReference": "Authorization: Bearer super-secret",
            "provenanceChain": [
                "licensed_vendor",
                "api_key=abc123",
                "https://exchange.example.com",
            ],
            "occProofReference": "https://occ.example.com/memo/123",
            "referenceCitation": "{\"headers\": {\"authorization\": \"secret\"}}",
            "reviewer": "ops@example.com",
        }
    )

    assert contract["sourceIdentity"]["candidateSourceName"] == "redacted"
    assert contract["sourceIdentity"]["providerName"] == "redacted"
    assert contract["sourceIdentity"]["documentReference"] == "redacted"
    assert contract["provenance"]["provenanceChain"] == ["licensed_vendor", "redacted", "redacted"]
    assert contract["provenance"]["backing"]["occ"]["proofReference"] == "redacted"
    assert contract["adjustedDeliverableEvidence"]["referenceCitation"] == "redacted"
    assert contract["errorAuditState"]["reviewer"] == "redacted"


def test_no_forbidden_authority_outputs_are_emitted() -> None:
    contract = build_expiration_calendar_source_candidate_evidence(
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
