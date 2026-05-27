# -*- coding: utf-8 -*-
"""Diagnostic-only IV-rank authority projection for Options Lab."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


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
_REDACTED = "redacted"
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


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _sanitize_text(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    lowered = text.lower()
    if any(marker in lowered for marker in _BLOCKED_TEXT_MARKERS):
        return _REDACTED
    if len(text) > 120 or any(character.lower() not in _SAFE_TEXT_CHARS for character in text):
        return _REDACTED
    return text


def _normalized_text(value: Any) -> str:
    return (_sanitize_text(value) or "").lower().replace("-", "_")


def _value(data: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data:
            return data.get(key)
    return None


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on", "enabled"}:
            return True
        if lowered in {"0", "false", "no", "off", "disabled"}:
            return False
        return None
    return bool(value)


def _has_value(value: Any) -> bool:
    return value not in (None, "")


def _sanitize_sequence(value: Any) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    sanitized: list[Any] = []
    for item in value:
        if isinstance(item, Mapping):
            nested = _sanitize_mapping(item)
            if nested:
                sanitized.append(nested)
            continue
        if isinstance(item, (list, tuple)):
            nested = _sanitize_sequence(item)
            if nested:
                sanitized.append(nested)
            continue
        if isinstance(item, bool) or isinstance(item, (int, float)):
            sanitized.append(item)
            continue
        text = _sanitize_text(item)
        if text is not None:
            sanitized.append(text)
    return sanitized


def _sanitize_mapping(value: Any) -> dict[str, Any]:
    data = _mapping(value)
    sanitized: dict[str, Any] = {}
    for key, raw in data.items():
        safe_key = _sanitize_text(key)
        if safe_key is None:
            continue
        if isinstance(raw, Mapping):
            nested = _sanitize_mapping(raw)
            if nested:
                sanitized[safe_key] = nested
            continue
        if isinstance(raw, (list, tuple)):
            nested = _sanitize_sequence(raw)
            if nested:
                sanitized[safe_key] = nested
            continue
        if isinstance(raw, bool) or isinstance(raw, (int, float)):
            sanitized[safe_key] = raw
            continue
        text = _sanitize_text(raw)
        if text is not None:
            sanitized[safe_key] = text
    return sanitized


def _date_range(value: Any) -> dict[str, str] | None:
    data = _mapping(value)
    start = _sanitize_text(_value(data, "start", "from"))
    end = _sanitize_text(_value(data, "end", "to"))
    if not start and not end:
        return None
    result: dict[str, str] = {}
    if start:
        result["start"] = start
    if end:
        result["end"] = end
    return result or None


def _nested_mapping(data: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    for key in keys:
        value = _value(data, key)
        if isinstance(value, Mapping):
            return dict(value)
    return {}


def _flatten_text(values: Sequence[Any]) -> str:
    chunks: list[str] = []
    for value in values:
        if isinstance(value, Mapping):
            chunks.append(_flatten_text(list(value.values())))
            continue
        if isinstance(value, (list, tuple, set, frozenset)):
            chunks.append(_flatten_text(list(value)))
            continue
        text = _normalized_text(value)
        if text:
            chunks.append(text)
    return " ".join(chunks)


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
    provenance = _nested_mapping(data, "provenance")
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
    metadata = _nested_mapping(data, "methodologyMetadata", "methodologyDetails")
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


def _iv_rank_coverage_scope_present(
    data: Mapping[str, Any],
    coverage_metadata: Mapping[str, Any],
) -> bool:
    symbol_coverage = _sanitize_sequence(
        _value(data, "symbolCoverage", "symbol_coverage")
        or _value(coverage_metadata, "symbolCoverage", "symbol_coverage")
    )
    underlying_coverage = _sanitize_sequence(
        _value(data, "underlyingCoverage", "underlying_coverage")
        or _value(coverage_metadata, "underlyingCoverage", "underlying_coverage")
    )
    contract_universe_coverage = _sanitize_text(
        _value(data, "contractUniverseCoverage", "contract_universe_coverage")
        or _value(coverage_metadata, "contractUniverseCoverage", "contract_universe_coverage")
    )
    return bool(coverage_metadata) and bool(contract_universe_coverage) and bool(
        symbol_coverage or underlying_coverage
    )


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
    provenance_present = _iv_rank_provenance_present(data)
    entitlement_present = _iv_rank_entitlement_present(data, sandbox_or_production)
    sla_present = _iv_rank_sla_present(data, as_of, freshness)
    methodology_metadata_present = _iv_rank_methodology_metadata_present(data, methodology)
    coverage_scope_present = _iv_rank_coverage_scope_present(data, coverage_metadata)
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
    if not as_of or not freshness:
        reason_codes.append("iv_rank_asof_or_freshness_missing")
    if not lookback_window and not date_range:
        reason_codes.append("iv_rank_lookback_missing")
    if not methodology:
        reason_codes.append("iv_rank_methodology_missing")
    if not coverage_metadata:
        reason_codes.append("iv_rank_coverage_metadata_missing")
    if live_like_checklist_required:
        if not provenance_present:
            reason_codes.append("iv_rank_provenance_missing")
        if not entitlement_present:
            reason_codes.append("iv_rank_entitlement_missing")
        if not sla_present:
            reason_codes.append("iv_rank_sla_missing")
        if not methodology_metadata_present:
            reason_codes.append("iv_rank_methodology_metadata_missing")
        if not coverage_scope_present:
            reason_codes.append("iv_rank_coverage_scope_missing")
        if current_iv_or_greeks_context_only:
            reason_codes.append("iv_rank_current_iv_or_greeks_context_only")
        if underlying_realized_volatility_context_only:
            reason_codes.append("iv_rank_underlying_realized_volatility_context_only")

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
        and (not live_like_checklist_required or provenance_present)
        and (not live_like_checklist_required or entitlement_present)
        and (not live_like_checklist_required or sla_present)
        and (not live_like_checklist_required or methodology_metadata_present)
        and (not live_like_checklist_required or coverage_scope_present)
        and not current_iv_or_greeks_context_only
        and not underlying_realized_volatility_context_only
    )
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
    }
