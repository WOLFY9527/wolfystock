# -*- coding: utf-8 -*-
"""Diagnostic-only IV-rank authority projection for Options Lab."""

from __future__ import annotations

from functools import partial
from typing import Any, Mapping, Sequence

from src.services.options_authority_policy_matrix import (
    CURRENT_KNOWN_OPTIONS_AUTHORITY_PROVIDER_IDS,
    IV_RANK_REQUIRED_FUTURE_EVIDENCE_FAMILIES,
)
from src.services.options_authority_sanitizers import (
    coerce_bool,
    flatten_text,
    mapping,
    normalized_text,
    sanitize_authority_text,
    sanitize_date_range,
    sanitize_mapping,
    sanitize_sequence,
    text,
    value,
)


INTERNAL_OPTIONS_IV_RANK_AUTHORITY_POLICY_SOURCE = "wolfystock_options_iv_rank_authority_policy_v1"
REQUIRED_FUTURE_IV_RANK_AUTHORITY_EVIDENCE_FIELDS = (
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
    "historicalOptionIvSeriesAvailable",
    "coverageMetadata",
    "sandboxOrProduction",
)
_SAFE_TEXT_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789_:-+.")
_BLOCKED_TEXT_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "header",
    "password",
    "secret",
    "token",
)
_AUTHORITATIVE_SOURCE_AUTHORITIES = frozenset(
    {"authorized", "authoritative", "licensed", "internal_authorized", "provider_reported_authorized"}
)
_CHECKLIST_REASON_CODES = {
    "provenance": "iv_rank_provenance_evidence_missing",
    "entitlement": "iv_rank_entitlement_evidence_missing",
    "sla_freshness": "iv_rank_sla_evidence_missing",
    "methodology": "iv_rank_methodology_evidence_missing",
    "lookback_date_range": "iv_rank_lookback_evidence_missing",
    "option_iv_evidence": "iv_rank_option_iv_evidence_missing",
    "coverage_scope": "iv_rank_coverage_scope_evidence_missing",
}


def _sanitize_text(value: Any) -> str | None:
    return sanitize_authority_text(
        value,
        safe_chars=_SAFE_TEXT_CHARS,
        blocked_markers=_BLOCKED_TEXT_MARKERS,
    )


_mapping = mapping
_text = text
_value = value
_bool = coerce_bool
_normalized_text = partial(normalized_text, sanitize_text=_sanitize_text)
_sanitize_sequence = partial(sanitize_sequence, sanitize_text=_sanitize_text)
_sanitize_mapping = partial(sanitize_mapping, sanitize_text=_sanitize_text)
_date_range = partial(sanitize_date_range, sanitize_text=_sanitize_text)
_flatten_text = partial(flatten_text, sanitize_text=_sanitize_text)


def _has_value(value: Any) -> bool:
    return value not in (None, "")


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        sanitized = _sanitize_text(value)
        return [sanitized] if sanitized else []
    return [item for item in _sanitize_sequence(value) if isinstance(item, str)]


def _nested_mapping(data: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    for key in keys:
        value = _value(data, key)
        if isinstance(value, Mapping):
            return dict(value)
    return {}


def _source_reason_codes(data: Mapping[str, Any]) -> list[str]:
    text = _flatten_text(
        [
            _value(data, "providerId", "provider_id"),
            _value(data, "sourceType", "source_type"),
            _value(data, "sourceAuthority", "source_authority"),
            _value(data, "ivRankSource", "iv_rank_source"),
            _value(data, "notes"),
        ]
    )
    exact_markers = {
        _normalized_text(_value(data, "providerId", "provider_id")),
        _normalized_text(_value(data, "sourceType", "source_type")),
        _normalized_text(_value(data, "sourceAuthority", "source_authority")),
        _normalized_text(_value(data, "ivRankSource", "iv_rank_source")),
    }
    reason_codes: list[str] = []
    if "proxy" in exact_markers:
        reason_codes.append("iv_rank_proxy_not_authoritative")
    if "provider_self_claim_only" in exact_markers:
        reason_codes.append("iv_rank_provider_self_claim_only_not_authoritative")
    if "synthetic_fixture_proxy" in text:
        reason_codes.extend(["iv_rank_synthetic_fixture_proxy", "iv_rank_fixture_not_authoritative"])
    else:
        if "synthetic" in text:
            reason_codes.append("iv_rank_synthetic_not_authoritative")
        if "fixture" in text:
            reason_codes.append("iv_rank_fixture_not_authoritative")
    if "fallback" in text:
        reason_codes.append("iv_rank_fallback_not_authoritative")
    if "dry_run" in text:
        reason_codes.append("iv_rank_dry_run_not_authoritative")
    if "stub" in text:
        reason_codes.append("iv_rank_stub_not_authoritative")
    if "adapter_contract" in text:
        reason_codes.append("iv_rank_adapter_contract_not_authoritative")
    if "request_supplied" in text or "request_payload" in text:
        reason_codes.append("iv_rank_request_supplied_not_authoritative")
    if (
        "request_shaped" in text
        or "request_style" in text
        or "request_shaped" in _normalized_text(_value(data, "sourceType", "source_type"))
    ):
        reason_codes.append("iv_rank_request_shaped_not_authoritative")
    return reason_codes


def _iv_rank_provenance_present(data: Mapping[str, Any]) -> bool:
    provenance = _nested_mapping(data, "provenance", "provenanceEvidence", "provenance_evidence")
    return any(
        (
            _sanitize_text(_value(provenance, "approvedProvider", "approved_provider")),
            _sanitize_text(_value(provenance, "licensedSource", "licensed_source")),
            _sanitize_text(
                _value(
                    provenance,
                    "approvedInternalDerivedSource",
                    "approved_internal_derived_source",
                )
            ),
        )
    )


def _iv_rank_entitlement_present(data: Mapping[str, Any], sandbox_or_production: str | None) -> bool:
    entitlement = _nested_mapping(data, "entitlementMetadata", "entitlement")
    return all(
        (
            _bool(
                _value(
                    entitlement,
                    "optionsIvHistoryEntitlement",
                    "options_iv_history_entitlement",
                )
            )
            is True,
            _sanitize_text(_value(entitlement, "liveDelayedStatus", "live_delayed_status")),
            _sanitize_text(_value(entitlement, "environment")) or sandbox_or_production,
            _bool(_value(entitlement, "decisionUseRights", "decision_use_rights")) is True,
            _bool(_value(entitlement, "redistributionRights", "redistribution_rights")) is True,
            _sanitize_text(_value(entitlement, "auditTimestamp", "audit_timestamp")),
        )
    )


def _iv_rank_sla_present(data: Mapping[str, Any], as_of: str | None, freshness: str | None) -> bool:
    sla_metadata = _nested_mapping(data, "slaMetadata", "sla")
    freshness_seconds = _value(sla_metadata, "freshnessSeconds", "freshness_seconds")
    freshness_state = _sanitize_text(_value(sla_metadata, "freshnessState", "freshness_state"))
    return all(
        (
            as_of,
            freshness,
            _sanitize_text(_value(sla_metadata, "maxAgePolicy", "max_age_policy")),
            _sanitize_text(_value(sla_metadata, "providerSlaStatus", "provider_sla_status")),
            _has_value(freshness_seconds) or freshness_state,
        )
    )


def _iv_rank_methodology_metadata_present(data: Mapping[str, Any], methodology: str | None) -> bool:
    metadata = _nested_mapping(
        data,
        "methodologyMetadata",
        "methodologyDetails",
        "methodologyEvidence",
        "methodology_evidence",
    )
    return all(
        (
            methodology,
            _sanitize_text(_value(metadata, "methodologyVersion", "methodology_version")),
            _sanitize_text(_value(metadata, "calculationBasis", "calculation_basis")),
            _sanitize_text(
                _value(
                    metadata,
                    "percentileRankDefinition",
                    "percentile_rank_definition",
                    "rankDefinition",
                    "rank_definition",
                )
            ),
        )
    )


def _iv_rank_methodology_family_present(
    data: Mapping[str, Any],
    methodology: str | None,
    *,
    provider_reported_iv_rank_available: bool,
    provider_reported_iv_percentile_available: bool,
) -> bool:
    metadata = _nested_mapping(
        data,
        "methodologyMetadata",
        "methodologyDetails",
        "methodologyEvidence",
        "methodology_evidence",
    )
    calculation_basis = _sanitize_text(_value(metadata, "calculationBasis", "calculation_basis"))
    methodology_text = " ".join(
        chunk
        for chunk in (
            _normalized_text(methodology),
            _normalized_text(calculation_basis),
            _normalized_text(_value(metadata, "methodType", "method_type")),
        )
        if chunk
    )
    deterministic_derived = (
        _bool(_value(metadata, "deterministicDerivedIvRank", "deterministic_derived_iv_rank")) is True
        or "deterministic_derived" in methodology_text
        or "derived_iv_rank" in methodology_text
    )
    return bool(
        _iv_rank_methodology_metadata_present(data, methodology)
        and (provider_reported_iv_rank_available or provider_reported_iv_percentile_available or deterministic_derived)
    )


def _iv_rank_date_range_present(date_range: Mapping[str, Any] | None) -> bool:
    return bool(date_range and date_range.get("start") and date_range.get("end"))


def _iv_rank_lookback_family_present(
    lookback_window: str | None,
    date_range: Mapping[str, Any] | None,
) -> bool:
    return bool(lookback_window or _iv_rank_date_range_present(date_range))


def _iv_rank_option_iv_evidence_present(
    *,
    provider_reported_iv_rank_available: bool,
    provider_reported_iv_percentile_available: bool,
    historical_option_iv_series_available: bool,
) -> bool:
    return bool(
        historical_option_iv_series_available
        or provider_reported_iv_rank_available
        or provider_reported_iv_percentile_available
    )


def _iv_rank_coverage_scope_present(
    data: Mapping[str, Any],
    coverage_metadata: Mapping[str, Any],
) -> bool:
    coverage_scope = _nested_mapping(data, "coverageScopeEvidence", "coverage_scope_evidence")
    symbol_coverage = _string_list(
        _value(coverage_scope, "symbolCoverage", "symbol_coverage")
        or _value(data, "symbolCoverage", "symbol_coverage")
        or _value(coverage_metadata, "symbolCoverage", "symbol_coverage")
    )
    underlying_coverage = _string_list(
        _value(coverage_scope, "underlyingCoverage", "underlying_coverage")
        or _value(data, "underlyingCoverage", "underlying_coverage")
        or _value(coverage_metadata, "underlyingCoverage", "underlying_coverage")
    )
    contract_universe_coverage = _sanitize_text(
        _value(coverage_scope, "contractUniverseCoverage", "contract_universe_coverage")
        or _value(data, "contractUniverseCoverage", "contract_universe_coverage")
        or _value(coverage_metadata, "contractUniverseCoverage", "contract_universe_coverage")
    )
    moneyness_selection_rules = _sanitize_text(
        _value(coverage_scope, "moneynessSelectionRules", "moneyness_selection_rules")
        or _value(data, "moneynessSelectionRules", "moneyness_selection_rules")
        or _value(coverage_metadata, "moneynessSelectionRules", "moneyness_selection_rules")
    )
    expiry_selection_rules = _sanitize_text(
        _value(coverage_scope, "expirySelectionRules", "expiry_selection_rules")
        or _value(data, "expirySelectionRules", "expiry_selection_rules")
        or _value(coverage_metadata, "expirySelectionRules", "expiry_selection_rules")
    )
    missing_data_policy = _sanitize_text(
        _value(coverage_scope, "missingDataPolicy", "missing_data_policy")
        or _value(data, "missingDataPolicy", "missing_data_policy")
        or _value(coverage_metadata, "missingDataPolicy", "missing_data_policy")
    )
    return bool(coverage_metadata) and bool(contract_universe_coverage) and bool(
        symbol_coverage or underlying_coverage
    ) and bool(moneyness_selection_rules) and bool(expiry_selection_rules) and bool(missing_data_policy)


def _build_authority_evidence_checklist(
    data: Mapping[str, Any],
    *,
    as_of: str | None,
    freshness: str | None,
    lookback_window: str | None,
    date_range: Mapping[str, Any] | None,
    methodology: str | None,
    provider_reported_iv_rank_available: bool,
    provider_reported_iv_percentile_available: bool,
    historical_option_iv_series_available: bool,
    coverage_metadata: Mapping[str, Any],
    sandbox_or_production: str | None,
) -> dict[str, dict[str, Any]]:
    family_presence = {
        "provenance": _iv_rank_provenance_present(data),
        "entitlement": _iv_rank_entitlement_present(data, sandbox_or_production),
        "sla_freshness": _iv_rank_sla_present(data, as_of, freshness),
        "methodology": _iv_rank_methodology_family_present(
            data,
            methodology,
            provider_reported_iv_rank_available=provider_reported_iv_rank_available,
            provider_reported_iv_percentile_available=provider_reported_iv_percentile_available,
        ),
        "lookback_date_range": _iv_rank_lookback_family_present(lookback_window, date_range),
        "option_iv_evidence": _iv_rank_option_iv_evidence_present(
            provider_reported_iv_rank_available=provider_reported_iv_rank_available,
            provider_reported_iv_percentile_available=provider_reported_iv_percentile_available,
            historical_option_iv_series_available=historical_option_iv_series_available,
        ),
        "coverage_scope": _iv_rank_coverage_scope_present(data, coverage_metadata),
    }
    return {
        family: {
            "present": family_presence[family],
            "required": True,
            "fields": list(fields),
        }
        for family, fields in IV_RANK_REQUIRED_FUTURE_EVIDENCE_FAMILIES.items()
    }


def _current_known_provider_live_path(provider_id: str | None, source_type: str | None) -> bool:
    return _normalized_text(source_type) == "live" and _normalized_text(provider_id) in {
        _normalized_text(item) for item in CURRENT_KNOWN_OPTIONS_AUTHORITY_PROVIDER_IDS
    }


def _iv_rank_current_iv_or_greeks_context_only(data: Mapping[str, Any]) -> bool:
    text = _flatten_text(
        [
            _value(data, "ivRankSource", "iv_rank_source"),
            _value(data, "methodology"),
            _value(data, "currentIvSource", "current_iv_source"),
            _nested_mapping(data, "methodologyMetadata", "methodologyDetails"),
            _nested_mapping(data, "coverageMetadata", "coverage_metadata"),
        ]
    )
    if any(
        key in data
        for key in (
            "selectedContractIv",
            "selected_contract_iv",
            "currentIv",
            "current_iv",
            "greeks",
            "selectedContractGreeks",
            "selected_contract_greeks",
        )
    ):
        return True
    return any(
        marker in text
        for marker in (
            "selected_contract",
            "current_iv",
            "greeks",
            "mid_iv",
        )
    )


def _iv_rank_underlying_realized_volatility_context_only(data: Mapping[str, Any]) -> bool:
    text = _flatten_text(
        [
            _value(data, "ivRankSource", "iv_rank_source"),
            _value(data, "methodology"),
            _nested_mapping(data, "methodologyMetadata", "methodologyDetails"),
        ]
    )
    if any(
        key in data
        for key in (
            "underlyingRealizedVolatility",
            "underlying_realized_volatility",
            "realizedVolatility",
            "realized_volatility",
            "underlyingHistoricalVolatility",
            "underlying_historical_volatility",
        )
    ):
        return True
    return any(
        marker in text
        for marker in (
            "underlying_realized_volatility",
            "realized_volatility",
            "historical_volatility",
        )
    )


def _provider_self_claimed(data: Mapping[str, Any]) -> bool:
    return any(
        _bool(_value(data, *keys)) is True
        for keys in (
            ("providerDecisionAuthority", "provider_decision_authority"),
            ("providerDecisionAuthorityClaim", "provider_decision_authority_claim"),
            ("recommendationAuthority", "recommendation_authority"),
            ("recommendationAuthorityClaim", "recommendation_authority_claim"),
        )
    )


def _dedupe(codes: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for code in codes:
        normalized = _normalized_text(code)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def build_options_iv_rank_authority_diagnostic(
    evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    data = _mapping(evidence)
    provider_id = _sanitize_text(_value(data, "providerId", "provider_id"))
    source_type = _sanitize_text(_value(data, "sourceType", "source_type"))
    source_authority = _sanitize_text(_value(data, "sourceAuthority", "source_authority"))
    iv_rank_status = _sanitize_text(_value(data, "ivRankStatus", "iv_rank_status")) or "unavailable"
    iv_rank_source = _sanitize_text(_value(data, "ivRankSource", "iv_rank_source"))
    authority_policy_source = _sanitize_text(
        _value(data, "authorityPolicySource", "authority_policy_source")
    )
    as_of = _sanitize_text(_value(data, "asOf", "as_of"))
    freshness = _sanitize_text(_value(data, "freshness"))
    lookback_window = _sanitize_text(_value(data, "lookbackWindow", "lookback_window"))
    date_range = _date_range(_value(data, "dateRange", "date_range"))
    methodology = _sanitize_text(_value(data, "methodology"))
    provider_reported_iv_rank_available = _has_value(
        _value(data, "providerReportedIvRank", "provider_reported_iv_rank")
    )
    provider_reported_iv_percentile_available = _has_value(
        _value(data, "providerReportedIvPercentile", "provider_reported_iv_percentile")
    )
    historical_option_iv_series_available = (
        _bool(_value(data, "historicalOptionIvSeriesAvailable", "historical_option_iv_series_available"))
        is True
    )
    coverage_metadata = _sanitize_mapping(_value(data, "coverageMetadata", "coverage_metadata"))
    sandbox_or_production = _sanitize_text(
        _value(data, "sandboxOrProduction", "sandbox_or_production")
    )
    source_reason_codes = _source_reason_codes(data)
    live_like_checklist_required = bool(
        evidence_present := any(
            (
                provider_id,
                source_type,
                iv_rank_source,
                _normalized_text(iv_rank_status) == "available",
                methodology,
                historical_option_iv_series_available,
                provider_reported_iv_rank_available,
                provider_reported_iv_percentile_available,
                bool(coverage_metadata),
            )
        )
    ) and not source_reason_codes and _normalized_text(source_type) == "live"
    checklist_requested = any(
        (
            authority_policy_source == INTERNAL_OPTIONS_IV_RANK_AUTHORITY_POLICY_SOURCE,
            isinstance(_value(data, "provenance", "provenanceEvidence", "provenance_evidence"), Mapping),
            isinstance(_value(data, "entitlementMetadata", "entitlement", "entitlement_metadata"), Mapping),
            isinstance(_value(data, "slaMetadata", "sla", "slaEvidence", "sla_evidence"), Mapping),
            isinstance(
                _value(
                    data,
                    "methodologyMetadata",
                    "methodologyDetails",
                    "methodologyEvidence",
                    "methodology_evidence",
                ),
                Mapping,
            ),
            isinstance(_value(data, "coverageScopeEvidence", "coverage_scope_evidence"), Mapping),
        )
    )
    current_iv_or_greeks_context_only = live_like_checklist_required and (
        _iv_rank_current_iv_or_greeks_context_only(data)
        and not (
            provider_reported_iv_rank_available
            or provider_reported_iv_percentile_available
            or historical_option_iv_series_available
        )
    )
    underlying_realized_volatility_context_only = live_like_checklist_required and (
        _iv_rank_underlying_realized_volatility_context_only(data)
    )
    authority_evidence_checklist = (
        _build_authority_evidence_checklist(
            data,
            as_of=as_of,
            freshness=freshness,
            lookback_window=lookback_window,
            date_range=date_range,
            methodology=methodology,
            provider_reported_iv_rank_available=provider_reported_iv_rank_available,
            provider_reported_iv_percentile_available=provider_reported_iv_percentile_available,
            historical_option_iv_series_available=historical_option_iv_series_available,
            coverage_metadata=coverage_metadata,
            sandbox_or_production=sandbox_or_production,
        )
        if checklist_requested
        else None
    )
    authority_evidence_gap_families = (
        [family for family, entry in authority_evidence_checklist.items() if not entry["present"]]
        if authority_evidence_checklist
        else []
    )
    current_known_provider_live_path = _current_known_provider_live_path(provider_id, source_type)
    reason_codes: list[str] = []
    if not evidence_present:
        reason_codes.extend(["iv_rank_authority_missing", "iv_rank_source_unknown_or_missing"])
    else:
        reason_codes.append("iv_rank_authority_missing")
        reason_codes.extend(source_reason_codes)
        if not source_type and not iv_rank_source:
            reason_codes.append("iv_rank_source_unknown_or_missing")
    if _provider_self_claimed(data) and authority_policy_source != INTERNAL_OPTIONS_IV_RANK_AUTHORITY_POLICY_SOURCE:
        reason_codes.append("iv_rank_provider_self_claim_ignored")
    if not historical_option_iv_series_available:
        reason_codes.append("iv_rank_historical_option_iv_series_missing")
    if not provider_reported_iv_rank_available and not provider_reported_iv_percentile_available:
        reason_codes.append("iv_rank_provider_reported_percentile_missing")
    if not source_authority:
        reason_codes.append("iv_rank_source_authority_missing")
    if not checklist_requested and (not as_of or not freshness):
        reason_codes.append("iv_rank_asof_or_freshness_missing")
    if not checklist_requested and not lookback_window and not date_range:
        reason_codes.append("iv_rank_lookback_missing")
    if not checklist_requested and not methodology:
        reason_codes.append("iv_rank_methodology_missing")
    if not coverage_metadata:
        reason_codes.append("iv_rank_coverage_metadata_missing")
    if authority_evidence_checklist:
        for family in authority_evidence_gap_families:
            reason_codes.append(_CHECKLIST_REASON_CODES[family])
    if live_like_checklist_required:
        if current_iv_or_greeks_context_only:
            reason_codes.append("iv_rank_current_iv_or_greeks_context_only")
        if underlying_realized_volatility_context_only:
            reason_codes.append("iv_rank_underlying_realized_volatility_context_only")
    if current_known_provider_live_path and not source_reason_codes:
        reason_codes.append("iv_rank_current_provider_not_authoritative")

    authoritative = bool(
        evidence_present
        and authority_policy_source == INTERNAL_OPTIONS_IV_RANK_AUTHORITY_POLICY_SOURCE
        and _normalized_text(source_authority) in _AUTHORITATIVE_SOURCE_AUTHORITIES
        and as_of
        and freshness
        and (lookback_window or date_range)
        and methodology
        and coverage_metadata
        and (
            provider_reported_iv_rank_available
            or provider_reported_iv_percentile_available
            or historical_option_iv_series_available
        )
        and not source_reason_codes
        and not current_known_provider_live_path
        and authority_evidence_checklist
        and not authority_evidence_gap_families
        and not current_iv_or_greeks_context_only
        and not underlying_realized_volatility_context_only
    )
    if authority_evidence_checklist and evidence_present and not authoritative and (
        coverage_metadata
        or provider_reported_iv_rank_available
        or provider_reported_iv_percentile_available
        or historical_option_iv_series_available
    ):
        reason_codes.append("iv_rank_coverage_not_authority")
    authority_state = "authoritative" if authoritative else ("non_authoritative" if evidence_present else "missing")

    return {
        "diagnosticOnly": True,
        "authorityState": authority_state,
        "authoritative": authoritative,
        "providerId": provider_id,
        "sourceType": source_type,
        "sourceAuthority": source_authority,
        "ivRankStatus": iv_rank_status,
        "ivRankSource": iv_rank_source,
        "authorityPolicySource": authority_policy_source,
        "asOf": as_of,
        "freshness": freshness,
        "lookbackWindow": lookback_window,
        "dateRange": date_range,
        "methodology": methodology,
        "providerReportedIvRankAvailable": provider_reported_iv_rank_available,
        "providerReportedIvPercentileAvailable": provider_reported_iv_percentile_available,
        "historicalOptionIvSeriesAvailable": historical_option_iv_series_available,
        "coverageMetadata": coverage_metadata,
        "sandboxOrProduction": sandbox_or_production,
        "reasonCodes": [] if authoritative else _dedupe(reason_codes),
        "requiredFutureAuthorityEvidence": list(REQUIRED_FUTURE_IV_RANK_AUTHORITY_EVIDENCE_FIELDS),
        **(
            {
                "authorityEvidenceChecklist": authority_evidence_checklist,
                "authorityEvidenceGapFamilies": authority_evidence_gap_families,
            }
            if authority_evidence_checklist
            else {}
        ),
    }
