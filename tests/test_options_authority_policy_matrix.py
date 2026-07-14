# -*- coding: utf-8 -*-
"""Pure contract tests for the inert options authority policy matrix."""

from __future__ import annotations

import pytest

from src.services.market_data_source_registry import project_source_registry_metadata
from src.services.options_authority_policy_matrix import (
    BLOCKED_OPTIONS_AUTHORITY_SOURCE_CLASSES,
    CURRENT_KNOWN_OPTIONS_AUTHORITY_PROVIDER_IDS,
    CURRENT_KNOWN_OPTIONS_AUTHORITY_SOURCE_TYPES,
    OPTIONS_AUTHORITY_SURFACES,
    build_options_event_calendar_source_candidate_gap,
    build_options_expiration_source_candidate_gap,
    build_options_iv_rank_source_candidate_gap,
    get_options_authority_policy_matrix,
    get_options_authority_surface_policy,
    is_options_authority_provider_granted,
    is_options_authority_source_blocked,
    is_options_authority_source_granted,
)
FORBIDDEN_AUTHORITY_FIELDS = (
    "providerDecisionAuthority",
    "recommendationAuthority",
    "decisionGrade",
    "gateDecision",
    "sourceAuthorityAllowed",
    "providerRouting",
    "liveCallEnablement",
)


def _normalize_entitlement_family(values: tuple[str, ...] | list[str]) -> set[str]:
    return {str(value).replace("decision_use_rights_evidence", "decision_use_rights") for value in values}


def _normalize_forbidden_authority_inputs(values: tuple[str, ...] | list[str]) -> set[str]:
    normalized: set[str] = set()
    for value in values:
        token = str(value)
        if token == "fixtures":
            token = "fixture"
        if token.startswith("current_provider_id:"):
            token = "current_provider_id"
        normalized.add(token)
    return normalized


def test_all_required_options_authority_surfaces_exist() -> None:
    matrix = get_options_authority_policy_matrix()

    assert OPTIONS_AUTHORITY_SURFACES == (
        "iv_rank",
        "event_calendar",
        "expiration_calendar",
    )
    assert tuple(matrix) == OPTIONS_AUTHORITY_SURFACES


def test_blocked_source_classes_are_blocked_for_all_surfaces() -> None:
    for surface in OPTIONS_AUTHORITY_SURFACES:
        for source_class in BLOCKED_OPTIONS_AUTHORITY_SOURCE_CLASSES:
            actual_blocked = is_options_authority_source_blocked(surface, source_class)
            actual_granted = is_options_authority_source_granted(surface, source_class)
            assert actual_blocked is True, (
                f"surface={surface}, source class={source_class}, "
                f"actual authority result: blocked={actual_blocked}"
            )
            assert actual_granted is False, (
                f"surface={surface}, source class={source_class}, "
                f"actual authority result: granted={actual_granted}"
            )


def test_current_known_providers_do_not_receive_authority() -> None:
    for surface in OPTIONS_AUTHORITY_SURFACES:
        for provider_id in CURRENT_KNOWN_OPTIONS_AUTHORITY_PROVIDER_IDS:
            actual_granted = is_options_authority_provider_granted(surface, provider_id)
            assert actual_granted is False, (
                f"surface={surface}, provider={provider_id}, "
                f"actual authority result: granted={actual_granted}"
            )


def test_current_known_source_types_do_not_receive_authority() -> None:
    for surface in OPTIONS_AUTHORITY_SURFACES:
        for source_type in CURRENT_KNOWN_OPTIONS_AUTHORITY_SOURCE_TYPES:
            actual_granted = is_options_authority_source_granted(surface, source_type)
            assert actual_granted is False, (
                f"surface={surface}, source type={source_type}, "
                f"actual authority result: granted={actual_granted}"
            )


@pytest.mark.parametrize("surface", OPTIONS_AUTHORITY_SURFACES)
def test_coverage_alone_is_not_authority(surface: str) -> None:
    policy = get_options_authority_surface_policy(surface)

    assert policy["coverage_alone_is_authority"] is False


@pytest.mark.parametrize("surface", OPTIONS_AUTHORITY_SURFACES)
def test_provider_self_claim_alone_is_not_authority(surface: str) -> None:
    policy = get_options_authority_surface_policy(surface)

    assert policy["provider_self_claim_alone_is_authority"] is False


@pytest.mark.parametrize("surface", OPTIONS_AUTHORITY_SURFACES)
def test_required_evidence_includes_authority_policy_source(surface: str) -> None:
    policy = get_options_authority_surface_policy(surface)

    assert "authorityPolicySource" in policy["required_evidence"]
    assert policy["authority_grants"]["provider_ids"] == ()
    assert policy["authority_grants"]["source_types"] == ()
    assert policy["authoritative_by_default"] is False


def test_expiration_calendar_policy_encodes_future_authority_checklist_families() -> None:
    policy = get_options_authority_surface_policy("expiration_calendar")

    assert policy["required_future_evidence_families"] == {
        "provenance": (
            "occ",
            "opra",
            "exchange",
            "licensed_provider",
        ),
        "entitlement": (
            "options_entitlement",
            "live_delayed_status",
            "environment",
            "decision_use_rights",
            "redistribution_rights",
            "audit_timestamp",
        ),
        "sla_freshness": (
            "as_of",
            "freshness",
            "max_age_policy",
            "provider_sla_status",
            "freshness_seconds",
            "freshness_state",
            "latency_or_error_state",
        ),
        "expiration_taxonomy": (
            "weekly",
            "monthly",
            "quarterly",
            "standard",
            "leaps",
            "special_expirations",
            "classification_source",
        ),
        "adjusted_deliverable": (
            "occ_memo_or_equivalent",
            "effective_date",
            "adjusted_root_or_class",
            "deliverable_components",
            "multiplier",
            "cash_in_lieu",
            "standard_or_non_standard",
            "contract_symbol_mapping",
        ),
    }


def test_expiration_calendar_policy_gap_and_registry_metadata_stay_cross_contract_aligned() -> None:
    policy = get_options_authority_surface_policy("expiration_calendar")
    registry = project_source_registry_metadata("options_lab.expiration_calendar_candidate_evidence")
    gap = build_options_expiration_source_candidate_gap(registry["candidateSourceClass"])

    assert policy["surface"] == registry["surface"] == gap["surface"] == "expiration_calendar"
    assert registry["candidateSourceClass"] == gap["candidateSourceClass"]
    assert registry["diagnosticOnly"] is True
    assert registry["candidateOnly"] is True
    assert gap["diagnosticOnly"] is True
    assert gap["candidateOnly"] is True
    assert gap["authorityGrant"] is False

    assert tuple(registry["provenanceFamily"]) == policy["required_future_evidence_families"]["provenance"]
    assert _normalize_entitlement_family(registry["entitlementFamily"]) == set(
        policy["required_future_evidence_families"]["entitlement"]
    )
    assert set(gap["requiredEvidenceFamilies"]["entitlement_use_rights"]) <= _normalize_entitlement_family(
        registry["entitlementFamily"]
    )

    assert set(gap["requiredEvidenceFamilies"]["sla_freshness"]) <= set(registry["slaFreshnessFamily"])
    assert set(registry["slaFreshnessFamily"]) <= set(policy["required_future_evidence_families"]["sla_freshness"])
    assert set(policy["required_future_evidence_families"]["sla_freshness"]) - set(
        registry["slaFreshnessFamily"]
    ) == {"freshness_seconds"}

    assert tuple(registry["expirationTaxonomyFamily"]) == policy["required_future_evidence_families"][
        "expiration_taxonomy"
    ]
    assert set(gap["requiredEvidenceFamilies"]["expiration_taxonomy"]) == set(
        registry["expirationTaxonomyFamily"]
    )

    assert set(policy["required_future_evidence_families"]["adjusted_deliverable"]) <= set(
        registry["adjustedDeliverableCorporateActionFamily"]
    )
    assert set(gap["requiredEvidenceFamilies"]["adjusted_deliverable_corporate_action_evidence"]) == set(
        registry["adjustedDeliverableCorporateActionFamily"]
    )
    assert set(registry["adjustedDeliverableCorporateActionFamily"]) - set(
        policy["required_future_evidence_families"]["adjusted_deliverable"]
    ) == {"corporate_action_evidence"}

    assert _normalize_forbidden_authority_inputs(gap["forbiddenAuthorityInputs"]) <= set(
        registry["forbiddenAuthorityInputs"]
    )
    assert set(registry["forbiddenAuthorityInputs"]) - _normalize_forbidden_authority_inputs(
        gap["forbiddenAuthorityInputs"]
    ) == {"fallback", "synthetic"}

    for forbidden_field in (
        "providerDecisionAuthority",
        "recommendationAuthority",
        "decisionGrade",
        "gateDecision",
        "sourceAuthorityAllowed",
        "providerRouting",
        "liveCallEnablement",
    ):
        assert forbidden_field not in gap
        assert forbidden_field not in registry


def test_expiration_calendar_source_candidate_gap_contract_is_inert_and_observation_only() -> None:
    contract = build_options_expiration_source_candidate_gap(
        "occ_opra_exchange_or_licensed_expiration_calendar"
    )

    assert contract["diagnosticOnly"] is True
    assert contract["surface"] == "expiration_calendar"
    assert contract["candidateOnly"] is True
    assert contract["authorityGrant"] is False
    assert contract["candidateSourceClass"] == "occ_opra_exchange_or_licensed_expiration_calendar"
    assert set(contract["missingEvidenceFamilies"]) >= {
        "internal_policy_grant_missing",
        "source_authority_provenance_missing",
        "occ_opra_exchange_licensed_source_metadata_missing",
        "entitlement_use_rights_missing",
        "sla_freshness_missing",
        "expiration_taxonomy_missing",
        "adjusted_deliverable_corporate_action_evidence_missing",
    }
    assert set(contract["forbiddenAuthorityInputs"]) >= {
        "coverage_completeness",
        "provider_self_claims",
        "provider_capabilities",
        "fixtures",
        "dry_run",
        "adapter_contract",
        "request_shaped_evidence",
        "proxy",
        "current_provider_id:tradier",
        "current_provider_id:ibkr",
        "current_provider_id:polygon",
    }
    assert contract["requiredEvidenceFamilies"] == {
        "internal_policy_grant": (
            "wolfystock_internal_policy_grant",
            "surface_authority_approval",
        ),
        "source_authority_provenance": (
            "source_authority",
            "provenance_chain",
            "approved_source_class",
        ),
        "occ_opra_exchange_licensed_source_metadata": (
            "occ_or_opra_or_exchange_or_licensed_source",
            "venue",
            "calendar_scope",
            "source_license",
        ),
        "entitlement_use_rights": (
            "options_entitlement",
            "decision_use_rights",
            "redistribution_rights",
            "environment",
        ),
        "sla_freshness": (
            "as_of",
            "freshness",
            "max_age_policy",
            "provider_sla_status",
        ),
        "expiration_taxonomy": (
            "weekly",
            "monthly",
            "quarterly",
            "standard",
            "leaps",
            "special_expirations",
            "classification_source",
        ),
        "adjusted_deliverable_corporate_action_evidence": (
            "occ_memo_or_equivalent",
            "effective_date",
            "adjusted_root_or_class",
            "deliverable_components",
            "multiplier",
            "cash_in_lieu",
            "standard_or_non_standard",
            "contract_symbol_mapping",
            "corporate_action_evidence",
        ),
    }
    assert contract["nextSafeStep"] == "collect_observation_only_metadata_without_granting_authority"


@pytest.mark.parametrize(
    "source_class",
    tuple(
        dict.fromkeys(
            (
                *CURRENT_KNOWN_OPTIONS_AUTHORITY_SOURCE_TYPES,
                *BLOCKED_OPTIONS_AUTHORITY_SOURCE_CLASSES,
                *get_options_authority_surface_policy("expiration_calendar")[
                    "future_candidate_source_classes"
                ],
            )
        )
    ),
)
def test_expiration_calendar_source_candidate_gap_never_grants_authority(
    source_class: str,
) -> None:
    contract = build_options_expiration_source_candidate_gap(source_class)

    assert contract["authorityGrant"] is False
    assert contract["candidateOnly"] is True
    assert contract["candidateSourceClass"] == source_class

    if source_class not in get_options_authority_surface_policy("expiration_calendar")[
        "future_candidate_source_classes"
    ]:
        assert "non_blocked_source_class_missing" in contract["missingEvidenceFamilies"]


def test_event_calendar_policy_encodes_future_authority_checklist_families() -> None:
    policy = get_options_authority_surface_policy("event_calendar")

    assert policy["required_future_evidence_families"] == {
        "provenance": (
            "licensed_provider",
            "exchange",
            "issuer",
            "official_calendar",
            "approved_internal_source",
        ),
        "entitlement": (
            "event_calendar_entitlement",
            "live_delayed_status",
            "environment",
            "decision_use_rights",
            "redistribution_rights",
            "audit_timestamp",
        ),
        "sla_freshness": (
            "as_of",
            "freshness",
            "max_age_policy",
            "provider_sla_status",
            "freshness_seconds",
            "freshness_state",
            "latency_or_error_state",
        ),
        "event_taxonomy": (
            "earnings",
            "dividends_ex_dividend",
            "splits",
            "corporate_actions",
            "macro_context_relevance",
        ),
        "confirmation": (
            "confirmed_or_estimated",
            "event_date_or_time",
            "session",
            "timezone",
            "provider_event_id_or_event_identity",
        ),
        "coverage_scope": (
            "symbol_or_underlying_coverage",
            "lookahead_window_or_date_range",
            "coverage_metadata",
        ),
    }


def test_event_calendar_source_candidate_gap_contract_is_inert_and_observation_only() -> None:
    policy = get_options_authority_surface_policy("event_calendar")
    contract = build_options_event_calendar_source_candidate_gap(
        "licensed_event_calendar_provider"
    )

    assert policy["source_candidate_gap_contract"]["surface"] == "event_calendar"
    assert contract["diagnosticOnly"] is True
    assert contract["surface"] == "event_calendar"
    assert contract["candidateOnly"] is True
    assert contract["authorityGrant"] is False
    assert contract["candidateSourceClass"] == "licensed_event_calendar_provider"
    assert set(contract["missingEvidenceFamilies"]) >= {
        "internal_policy_grant_missing",
        "source_identity_provenance_chain_missing",
        "licensed_backing_missing",
        "entitlement_use_rights_missing",
        "sla_freshness_missing",
        "event_taxonomy_missing",
        "confirmation_status_missing",
        "event_identity_missing",
        "timezone_session_missing",
        "coverage_scope_missing",
    }
    assert set(contract["forbiddenAuthorityInputs"]) >= {
        "event_presence",
        "event_count",
        "event_type",
        "timeline_evidence",
        "generic_macro_context",
        "provider_capabilities",
        "source_labels",
        "provider_self_claims",
        "fixture",
        "synthetic",
        "fallback",
        "dry_run",
        "stub",
        "adapter_contract",
        "request_shaped_evidence",
        "proxy",
        "current_provider_id:tradier",
        "current_provider_id:ibkr",
        "current_provider_id:polygon",
    }
    assert contract["requiredEvidenceFamilies"] == {
        "internal_policy_grant": (
            "wolfystock_internal_policy_grant",
            "surface_authority_approval",
        ),
        "source_identity_provenance_chain": (
            "non_blocked_source_class",
            "source_identity",
            "source_authority",
            "provenance_chain",
        ),
        "licensed_backing": (
            "licensed_provider",
            "exchange",
            "issuer",
            "official_calendar",
            "approved_calendar_scope",
        ),
        "entitlement_use_rights": (
            "event_calendar_entitlement",
            "decision_use_rights",
            "redistribution_rights",
            "live_delayed_status",
            "sandbox_or_production",
        ),
        "sla_freshness": (
            "as_of",
            "freshness",
            "max_age_policy",
            "provider_sla_status",
        ),
        "event_taxonomy": (
            "earnings",
            "dividends",
            "ex_dividend",
            "splits",
            "corporate_actions",
            "fomc_macro_context_policy_scope",
        ),
        "confirmation_status": (
            "confirmed_or_estimated",
            "announcement_status",
        ),
        "event_identity": (
            "provider_event_id",
            "event_identity",
        ),
        "timezone_session": (
            "event_date",
            "event_time",
            "session",
            "timezone",
        ),
        "coverage_scope": (
            "symbol_or_underlying_coverage",
            "lookahead_window_or_date_range",
            "coverage_metadata",
        ),
    }
    assert contract["nextSafeStep"] == "collect_observation_only_metadata_without_granting_authority"


def test_event_calendar_policy_gap_and_registry_metadata_stay_cross_contract_aligned() -> None:
    policy = get_options_authority_surface_policy("event_calendar")
    registry = project_source_registry_metadata("options_lab.event_calendar_candidate_evidence")
    gap = build_options_event_calendar_source_candidate_gap(registry["candidateSourceClass"])

    assert policy["surface"] == registry["surface"] == gap["surface"] == "event_calendar"
    assert registry["candidateSourceClass"] == gap["candidateSourceClass"]
    assert registry["diagnosticOnly"] is True
    assert registry["candidateOnly"] is True
    assert gap["diagnosticOnly"] is True
    assert gap["candidateOnly"] is True
    assert gap["authorityGrant"] is False
    assert "authorityGrant" not in registry

    assert tuple(registry["provenanceFamily"]) == policy["required_future_evidence_families"]["provenance"]
    assert set(policy["required_future_evidence_families"]["entitlement"]) <= _normalize_entitlement_family(
        registry["entitlementFamily"]
    )
    assert set(gap["requiredEvidenceFamilies"]["entitlement_use_rights"]) <= _normalize_entitlement_family(
        registry["entitlementFamily"]
    )

    assert set(gap["requiredEvidenceFamilies"]["sla_freshness"]) <= set(registry["slaFreshnessFamily"])
    assert set(registry["slaFreshnessFamily"]) <= set(policy["required_future_evidence_families"]["sla_freshness"])
    assert set(policy["required_future_evidence_families"]["sla_freshness"]) - set(
        registry["slaFreshnessFamily"]
    ) == {"freshness_seconds"}

    assert set(policy["required_future_evidence_families"]["event_taxonomy"]) <= set(registry["eventTaxonomyFamily"])
    assert set(gap["requiredEvidenceFamilies"]["event_taxonomy"]) <= set(registry["eventTaxonomyFamily"])

    assert set(gap["requiredEvidenceFamilies"]["confirmation_status"]) == set(registry["confirmationFamily"])
    assert set(gap["requiredEvidenceFamilies"]["event_identity"]) == set(registry["eventIdentityFamily"])
    assert set(gap["requiredEvidenceFamilies"]["timezone_session"]) == set(registry["timezoneSessionFamily"])
    assert set(policy["required_future_evidence_families"]["coverage_scope"]) == set(
        registry["coverageScopeFamily"]
    )
    assert set(gap["requiredEvidenceFamilies"]["coverage_scope"]) == set(registry["coverageScopeFamily"])

    assert _normalize_forbidden_authority_inputs(gap["forbiddenAuthorityInputs"]) <= set(
        registry["forbiddenAuthorityInputs"]
    )
    assert {
        "event_presence",
        "event_count",
        "event_type",
        "timeline_evidence",
        "generic_macro_context",
        "provider_capabilities",
        "provider_capability_metadata",
        "candidate_gap_metadata",
        "provider_self_claims",
        "current_provider_id",
    } <= set(registry["forbiddenAuthorityInputs"])
    for forbidden_field in FORBIDDEN_AUTHORITY_FIELDS:
        assert forbidden_field not in gap
        assert forbidden_field not in registry


@pytest.mark.parametrize(
    "source_class",
    tuple(
        dict.fromkeys(
            (
                *CURRENT_KNOWN_OPTIONS_AUTHORITY_SOURCE_TYPES,
                *BLOCKED_OPTIONS_AUTHORITY_SOURCE_CLASSES,
                *get_options_authority_surface_policy("event_calendar")[
                    "future_candidate_source_classes"
                ],
            )
        )
    ),
)
def test_event_calendar_source_candidate_gap_never_grants_authority(
    source_class: str,
) -> None:
    contract = build_options_event_calendar_source_candidate_gap(source_class)

    assert contract["authorityGrant"] is False
    assert contract["candidateOnly"] is True
    assert contract["candidateSourceClass"] == source_class

    if source_class not in get_options_authority_surface_policy("event_calendar")[
        "future_candidate_source_classes"
    ]:
        assert "non_blocked_source_class_missing" in contract["missingEvidenceFamilies"]


def test_iv_rank_policy_encodes_future_authority_checklist_families() -> None:
    policy = get_options_authority_surface_policy("iv_rank")

    assert policy["required_future_evidence_families"] == {
        "provenance": (
            "approved_provider",
            "licensed_source",
            "approved_internal_derived_source",
        ),
        "entitlement": (
            "options_iv_history_entitlement",
            "live_delayed_status",
            "environment",
            "decision_use_rights",
            "redistribution_rights",
            "audit_timestamp",
        ),
        "sla_freshness": (
            "as_of",
            "freshness",
            "max_age_policy",
            "provider_sla_status",
            "freshness_seconds",
            "freshness_state",
            "latency_or_error_state",
        ),
        "methodology": (
            "provider_reported_iv_rank_or_percentile",
            "deterministic_derived_iv_rank",
            "methodology_version",
            "percentile_or_rank_definition",
            "calculation_basis",
        ),
        "lookback_date_range": (
            "lookback_window",
            "date_range_start",
            "date_range_end",
        ),
        "option_iv_evidence": (
            "approved_historical_option_iv_series_availability",
            "provider_reported_iv_rank",
            "provider_reported_iv_percentile",
        ),
        "coverage_scope": (
            "symbol_or_underlying_coverage",
            "contract_universe_coverage",
            "moneyness_selection_rules",
            "expiry_selection_rules",
            "missing_data_policy",
            "coverage_metadata",
        ),
    }


def test_iv_rank_policy_gap_and_registry_metadata_stay_cross_contract_aligned() -> None:
    policy = get_options_authority_surface_policy("iv_rank")
    registry = project_source_registry_metadata("options_lab.iv_rank_candidate_evidence")
    primary_gap = build_options_iv_rank_source_candidate_gap(registry["candidateSourceClass"])

    assert policy["surface"] == registry["surface"] == primary_gap["surface"] == "iv_rank"
    assert registry["candidateSourceClass"] == "provider_reported_iv_rank"
    assert set(registry["candidateSourceClasses"]) == {
        "provider_reported_iv_rank",
        "approved_historical_option_iv_series",
    }
    assert registry["diagnosticOnly"] is True
    assert registry["candidateOnly"] is True
    assert primary_gap["diagnosticOnly"] is True
    assert primary_gap["candidateOnly"] is True
    assert primary_gap["authorityGrant"] is False

    assert tuple(registry["provenanceFamily"]) == policy["required_future_evidence_families"]["provenance"]
    assert _normalize_entitlement_family(registry["entitlementFamily"]) >= set(
        policy["required_future_evidence_families"]["entitlement"]
    )
    assert set(primary_gap["requiredEvidenceFamilies"]["entitlement_use_rights"]) <= _normalize_entitlement_family(
        registry["entitlementFamily"]
    )

    assert set(primary_gap["requiredEvidenceFamilies"]["sla_freshness"]) <= set(registry["slaFreshnessFamily"])
    assert set(registry["slaFreshnessFamily"]) <= set(policy["required_future_evidence_families"]["sla_freshness"])
    assert set(policy["required_future_evidence_families"]["sla_freshness"]) - set(
        registry["slaFreshnessFamily"]
    ) == {"freshness_seconds"}

    assert tuple(registry["methodologyFamily"]) == policy["required_future_evidence_families"]["methodology"]
    assert set(primary_gap["requiredEvidenceFamilies"]["methodology"]) <= set(registry["methodologyFamily"])

    assert tuple(registry["lookbackDateRangeFamily"]) == policy["required_future_evidence_families"][
        "lookback_date_range"
    ]
    assert set(primary_gap["requiredEvidenceFamilies"]["lookback_date_range"]) == set(
        registry["lookbackDateRangeFamily"]
    )

    assert tuple(registry["optionIvEvidenceFamily"]) == policy["required_future_evidence_families"][
        "option_iv_evidence"
    ]
    assert {
        "provider_reported_iv_rank_or_percentile",
        "approved_historical_option_iv_series",
    } <= set(primary_gap["requiredEvidenceFamilies"]["iv_rank_source_authority"])

    assert tuple(registry["coverageScopeFamily"]) == policy["required_future_evidence_families"]["coverage_scope"]
    assert set(primary_gap["requiredEvidenceFamilies"]["coverage_scope"]) <= set(registry["coverageScopeFamily"])
    assert {
        "contract_universe_coverage",
        "moneyness_selection_rules",
        "expiry_selection_rules",
        "missing_data_policy",
    } <= set(registry["coverageScopeFamily"])

    assert _normalize_forbidden_authority_inputs(primary_gap["forbiddenAuthorityInputs"]) <= set(
        registry["forbiddenAuthorityInputs"]
    )
    assert {
        "current_iv",
        "selected_contract_iv",
        "greeks",
        "historicalIvProxy",
        "underlying_realized_volatility",
        "provider_capability_metadata",
        "provider_capabilities",
        "provider_self_claims",
        "current_provider_id",
        "docs_only_evidence",
        "request_shaped_evidence",
        "proxy",
        "coverage_completeness",
    } <= set(registry["forbiddenAuthorityInputs"])

    for source_class in registry["candidateSourceClasses"]:
        gap = build_options_iv_rank_source_candidate_gap(source_class)
        assert gap["authorityGrant"] is False
        assert gap["candidateOnly"] is True

    for forbidden_field in (
        "providerDecisionAuthority",
        "recommendationAuthority",
        "decisionGrade",
        "gateDecision",
        "sourceAuthorityAllowed",
        "providerRouting",
        "liveCallEnablement",
    ):
        assert forbidden_field not in primary_gap
        assert forbidden_field not in registry


def test_iv_rank_source_candidate_gap_contract_is_inert_and_observation_only() -> None:
    policy = get_options_authority_surface_policy("iv_rank")
    contract = build_options_iv_rank_source_candidate_gap("provider_reported_iv_rank")

    assert policy["source_candidate_gap_contract"]["surface"] == "iv_rank"
    assert contract["diagnosticOnly"] is True
    assert contract["surface"] == "iv_rank"
    assert contract["candidateOnly"] is True
    assert contract["authorityGrant"] is False
    assert contract["candidateSourceClass"] == "provider_reported_iv_rank"
    assert set(contract["missingEvidenceFamilies"]) >= {
        "internal_policy_grant_missing",
        "source_identity_provenance_chain_missing",
        "entitlement_use_rights_missing",
        "license_use_rights_missing",
        "decision_redistribution_use_rights_missing",
        "sla_freshness_missing",
        "methodology_missing",
        "lookback_date_range_missing",
        "option_iv_evidence_missing",
        "provider_reported_iv_rank_or_percentile_missing",
        "approved_historical_option_iv_series_missing",
        "contract_universe_missing",
        "moneyness_expiry_selection_rules_missing",
        "moneyness_selection_rules_missing",
        "expiry_selection_rules_missing",
        "missing_data_policy_missing",
        "coverage_scope_missing",
    }
    assert set(contract["forbiddenAuthorityInputs"]) >= {
        "current_iv",
        "selected_contract_iv",
        "greeks",
        "historicalIvProxy",
        "underlying_realized_volatility",
        "source_labels",
        "provider_capability_metadata",
        "provider_capabilities",
        "provider_self_claims",
        "current_provider_id:tradier",
        "current_provider_id:ibkr",
        "current_provider_id:polygon",
        "docs_only_evidence",
        "fixtures",
        "request_shaped_evidence",
        "proxy",
        "coverage_completeness",
    }
    assert contract["requiredEvidenceFamilies"] == {
        "internal_policy_grant": (
            "wolfystock_internal_policy_grant",
            "surface_authority_approval",
        ),
        "source_identity_provenance_chain": (
            "non_blocked_source_class",
            "source_identity",
            "source_authority",
            "provenance_chain",
        ),
        "iv_rank_source_authority": (
            "provider_reported_iv_rank_or_percentile",
            "approved_historical_option_iv_series",
        ),
        "entitlement_use_rights": (
            "options_iv_history_entitlement",
            "decision_use_rights",
            "redistribution_rights",
            "live_delayed_status",
            "sandbox_or_production",
        ),
        "sla_freshness": (
            "as_of",
            "freshness",
            "max_age_policy",
            "provider_sla_status",
        ),
        "methodology": (
            "methodology_version",
            "percentile_or_rank_definition",
            "calculation_basis",
        ),
        "lookback_date_range": (
            "lookback_window",
            "date_range_start",
            "date_range_end",
        ),
        "contract_universe": (
            "contract_universe",
            "option_chain_scope",
        ),
        "moneyness_expiry_selection_rules": (
            "moneyness_selection_rules",
            "expiry_selection_rules",
        ),
        "missing_data_policy": (
            "missing_data_policy",
            "outlier_policy",
        ),
        "coverage_scope": (
            "symbol_or_underlying_coverage",
            "contract_universe_coverage",
            "coverage_metadata",
        ),
    }
    assert contract["nextSafeStep"] == "collect_observation_only_metadata_without_granting_authority"


@pytest.mark.parametrize(
    "source_class",
    tuple(
        dict.fromkeys(
            (
                *CURRENT_KNOWN_OPTIONS_AUTHORITY_SOURCE_TYPES,
                *BLOCKED_OPTIONS_AUTHORITY_SOURCE_CLASSES,
                *(
                    f"current_provider_id:{provider_id}"
                    for provider_id in CURRENT_KNOWN_OPTIONS_AUTHORITY_PROVIDER_IDS
                ),
                *get_options_authority_surface_policy("iv_rank")[
                    "future_candidate_source_classes"
                ],
            )
        )
    ),
)
def test_iv_rank_source_candidate_gap_never_grants_authority(
    source_class: str,
) -> None:
    contract = build_options_iv_rank_source_candidate_gap(source_class)

    assert contract["diagnosticOnly"] is True
    assert contract["authorityGrant"] is False
    assert contract["candidateOnly"] is True
    assert contract["candidateSourceClass"] == source_class

    if source_class not in get_options_authority_surface_policy("iv_rank")[
        "future_candidate_source_classes"
    ]:
        assert "non_blocked_source_class_missing" in contract["missingEvidenceFamilies"]
