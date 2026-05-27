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
IV_RANK_REQUIRED_FUTURE_EVIDENCE_FAMILIES = {
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
_EVENT_CALENDAR_FUTURE_CANDIDATE_SOURCE_CLASSES = (
    "licensed_event_calendar_provider",
)
EVENT_CALENDAR_REQUIRED_FUTURE_EVIDENCE_FAMILIES = {
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
_EVENT_CALENDAR_SOURCE_CANDIDATE_GAP_REQUIRED_EVIDENCE_FAMILIES = {
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
_EVENT_CALENDAR_SOURCE_CANDIDATE_GAP_MISSING_EVIDENCE_FAMILIES = (
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
)
_EVENT_CALENDAR_SOURCE_CANDIDATE_GAP_FORBIDDEN_AUTHORITY_INPUTS = (
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
)
_EVENT_CALENDAR_SOURCE_CANDIDATE_GAP_CONTRACT = {
    "diagnosticOnly": True,
    "surface": "event_calendar",
    "candidateOnly": True,
    "authorityGrant": False,
    "candidateSourceClass": "",
    "missingEvidenceFamilies": _EVENT_CALENDAR_SOURCE_CANDIDATE_GAP_MISSING_EVIDENCE_FAMILIES,
    "forbiddenAuthorityInputs": _EVENT_CALENDAR_SOURCE_CANDIDATE_GAP_FORBIDDEN_AUTHORITY_INPUTS,
    "requiredEvidenceFamilies": _EVENT_CALENDAR_SOURCE_CANDIDATE_GAP_REQUIRED_EVIDENCE_FAMILIES,
    "nextSafeStep": "collect_observation_only_metadata_without_granting_authority",
}
_EXPIRATION_CALENDAR_FUTURE_CANDIDATE_SOURCE_CLASSES = (
    "occ_opra_exchange_or_licensed_expiration_calendar",
)
EXPIRATION_CALENDAR_REQUIRED_FUTURE_EVIDENCE_FAMILIES = {
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
_EXPIRATION_CALENDAR_SOURCE_CANDIDATE_GAP_REQUIRED_EVIDENCE_FAMILIES = {
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
_EXPIRATION_CALENDAR_SOURCE_CANDIDATE_GAP_MISSING_EVIDENCE_FAMILIES = (
    "internal_policy_grant_missing",
    "source_authority_provenance_missing",
    "occ_opra_exchange_licensed_source_metadata_missing",
    "entitlement_use_rights_missing",
    "sla_freshness_missing",
    "expiration_taxonomy_missing",
    "adjusted_deliverable_corporate_action_evidence_missing",
)
_EXPIRATION_CALENDAR_SOURCE_CANDIDATE_GAP_FORBIDDEN_AUTHORITY_INPUTS = (
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
)
_EXPIRATION_CALENDAR_SOURCE_CANDIDATE_GAP_CONTRACT = {
    "diagnosticOnly": True,
    "surface": "expiration_calendar",
    "candidateOnly": True,
    "authorityGrant": False,
    "candidateSourceClass": "",
    "missingEvidenceFamilies": _EXPIRATION_CALENDAR_SOURCE_CANDIDATE_GAP_MISSING_EVIDENCE_FAMILIES,
    "forbiddenAuthorityInputs": _EXPIRATION_CALENDAR_SOURCE_CANDIDATE_GAP_FORBIDDEN_AUTHORITY_INPUTS,
    "requiredEvidenceFamilies": _EXPIRATION_CALENDAR_SOURCE_CANDIDATE_GAP_REQUIRED_EVIDENCE_FAMILIES,
    "nextSafeStep": "collect_observation_only_metadata_without_granting_authority",
}

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
        "required_future_evidence_families": IV_RANK_REQUIRED_FUTURE_EVIDENCE_FAMILIES,
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
        "required_future_evidence_families": EVENT_CALENDAR_REQUIRED_FUTURE_EVIDENCE_FAMILIES,
        "future_candidate_source_classes": _EVENT_CALENDAR_FUTURE_CANDIDATE_SOURCE_CLASSES,
        "source_candidate_gap_contract": _EVENT_CALENDAR_SOURCE_CANDIDATE_GAP_CONTRACT,
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
        "required_future_evidence_families": EXPIRATION_CALENDAR_REQUIRED_FUTURE_EVIDENCE_FAMILIES,
        "future_candidate_source_classes": _EXPIRATION_CALENDAR_FUTURE_CANDIDATE_SOURCE_CLASSES,
        "source_candidate_gap_contract": _EXPIRATION_CALENDAR_SOURCE_CANDIDATE_GAP_CONTRACT,
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


def build_options_expiration_source_candidate_gap(
    candidate_source_class: str,
) -> dict[str, Any]:
    """Return inert expiration-calendar source-candidate gap metadata."""

    policy = get_options_authority_surface_policy("expiration_calendar")
    contract = deepcopy(policy["source_candidate_gap_contract"])
    normalized_source_class = _normalize_token(candidate_source_class)
    approved_candidate_classes = {
        _normalize_token(item) for item in policy["future_candidate_source_classes"]
    }
    missing_evidence_families = list(contract["missingEvidenceFamilies"])

    contract["candidateSourceClass"] = normalized_source_class

    if normalized_source_class not in approved_candidate_classes:
        missing_evidence_families.insert(1, "non_blocked_source_class_missing")

    contract["missingEvidenceFamilies"] = tuple(dict.fromkeys(missing_evidence_families))
    contract["authorityGrant"] = False
    contract["candidateOnly"] = True
    contract["diagnosticOnly"] = True
    contract["surface"] = "expiration_calendar"
    return contract


def build_options_event_calendar_source_candidate_gap(
    candidate_source_class: str,
) -> dict[str, Any]:
    """Return inert event-calendar source-candidate gap metadata."""

    policy = get_options_authority_surface_policy("event_calendar")
    contract = deepcopy(policy["source_candidate_gap_contract"])
    normalized_source_class = _normalize_token(candidate_source_class)
    approved_candidate_classes = {
        _normalize_token(item) for item in policy["future_candidate_source_classes"]
    }
    missing_evidence_families = list(contract["missingEvidenceFamilies"])

    contract["candidateSourceClass"] = normalized_source_class

    if normalized_source_class not in approved_candidate_classes:
        missing_evidence_families.insert(1, "non_blocked_source_class_missing")

    contract["missingEvidenceFamilies"] = tuple(dict.fromkeys(missing_evidence_families))
    contract["authorityGrant"] = False
    contract["candidateOnly"] = True
    contract["diagnosticOnly"] = True
    contract["surface"] = "event_calendar"
    return contract
