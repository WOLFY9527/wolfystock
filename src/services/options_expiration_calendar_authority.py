# -*- coding: utf-8 -*-
"""Diagnostic-only expiration-calendar authority projection for Options Lab."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from src.services.options_authority_policy_matrix import (
    EXPIRATION_CALENDAR_REQUIRED_FUTURE_EVIDENCE_FAMILIES,
)


INTERNAL_OPTIONS_EXPIRATION_CALENDAR_AUTHORITY_POLICY_SOURCE = (
    "wolfystock_options_expiration_calendar_authority_policy_v1"
)
REQUIRED_FUTURE_EXPIRATION_CALENDAR_AUTHORITY_EVIDENCE_FIELDS = (
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
    "authorizedSourceMetadata",
    "sandboxOrProduction",
)
_SAFE_TEXT_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789_:-+./")
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
_URL_LIKE_HOST_RE = re.compile(r"^[a-z0-9-]+(?:\.[a-z0-9-]+)+(?::\d+)?(?:[/?#].*)?$")
_AUTHORITATIVE_SOURCE_AUTHORITIES = frozenset(
    {"authorized", "authoritative", "licensed", "internal_authorized", "provider_reported_authorized"}
)
_CHECKLIST_REASON_CODES = {
    "provenance": "expiration_calendar_provenance_evidence_missing",
    "entitlement": "expiration_calendar_entitlement_evidence_missing",
    "sla_freshness": "expiration_calendar_sla_evidence_missing",
    "expiration_taxonomy": "expiration_calendar_taxonomy_evidence_missing",
    "adjusted_deliverable": "expiration_calendar_adjusted_deliverable_evidence_missing",
}


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
    if _looks_like_url_text(text):
        return _REDACTED
    if len(text) > 120 or any(character.lower() not in _SAFE_TEXT_CHARS for character in text):
        return _REDACTED
    return text


def _looks_like_url_text(text: str) -> bool:
    lowered = text.lower()
    if lowered.startswith(("http://", "https://", "www.")):
        return True
    return bool(_URL_LIKE_HOST_RE.fullmatch(lowered))


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


def _non_negative_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


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


def _has_value(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_has_value(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_has_value(item) for item in value)
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return True
    return bool(_text(value))


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        sanitized = _sanitize_text(value)
        return [sanitized] if sanitized else []
    return [item for item in _sanitize_sequence(value) if isinstance(item, str)]


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
            _value(data, "expirationCalendarSource", "expiration_calendar_source"),
            _value(data, "notes"),
        ]
    )
    exact_markers = {
        _normalized_text(_value(data, "providerId", "provider_id")),
        _normalized_text(_value(data, "sourceType", "source_type")),
        _normalized_text(_value(data, "sourceAuthority", "source_authority")),
        _normalized_text(_value(data, "expirationCalendarSource", "expiration_calendar_source")),
    }
    reason_codes: list[str] = []
    if "proxy" in exact_markers:
        reason_codes.append("expiration_calendar_proxy_not_authoritative")
    if "provider_self_claim_only" in exact_markers:
        reason_codes.append("expiration_calendar_provider_self_claim_only_not_authoritative")
    if "fixture" in text:
        reason_codes.append("expiration_calendar_fixture_not_authoritative")
    if "synthetic" in text:
        reason_codes.append("expiration_calendar_synthetic_not_authoritative")
    if "fallback" in text:
        reason_codes.append("expiration_calendar_fallback_not_authoritative")
    if "dry_run" in text:
        reason_codes.append("expiration_calendar_dry_run_not_authoritative")
    if "stub" in text:
        reason_codes.append("expiration_calendar_stub_not_authoritative")
    if "adapter_contract" in text:
        reason_codes.append("expiration_calendar_adapter_contract_not_authoritative")
    if "request_supplied" in text or "request_payload" in text:
        reason_codes.append("expiration_calendar_request_supplied_not_authoritative")
    if (
        "request_shaped" in text
        or "request_style" in text
        or "request_shaped" in _normalized_text(_value(data, "sourceType", "source_type"))
    ):
        reason_codes.append("expiration_calendar_request_shaped_not_authoritative")
    return reason_codes


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


def _family_mapping(data: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    for key in keys:
        value = _value(data, key)
        if isinstance(value, Mapping):
            return _mapping(value)
    return {}


def _family_present_provenance(data: Mapping[str, Any]) -> bool:
    provenance = _family_mapping(
        data,
        "provenanceEvidence",
        "provenance_evidence",
        "authorityProvenanceEvidence",
        "authority_provenance_evidence",
    )
    primary_sources = _string_list(_value(provenance, "primarySources", "primary_sources"))
    calendar_source = _sanitize_text(_value(provenance, "calendarSource", "calendar_source"))
    allowed_sources = {"occ", "opra", "exchange", "licensed_provider"}
    return bool(primary_sources and allowed_sources.intersection({_normalized_text(item) for item in primary_sources}) and calendar_source)


def _family_present_entitlement(data: Mapping[str, Any]) -> bool:
    entitlement = _family_mapping(
        data,
        "entitlementMetadata",
        "entitlement_metadata",
        "authorityEntitlementMetadata",
        "authority_entitlement_metadata",
    )
    return all(
        _has_value(_value(entitlement, *keys))
        for keys in (
            ("optionsEntitlement", "options_entitlement"),
            ("liveDelayedStatus", "live_delayed_status"),
            ("environment",),
            ("decisionUseRights", "decision_use_rights"),
            ("redistributionRights", "redistribution_rights"),
            ("auditTimestamp", "audit_timestamp"),
        )
    )


def _family_present_sla(data: Mapping[str, Any], as_of: str | None, freshness: str | None) -> bool:
    sla = _family_mapping(
        data,
        "slaEvidence",
        "sla_evidence",
        "freshnessEvidence",
        "freshness_evidence",
    )
    has_latency_or_error_state = any(
        _has_value(_value(sla, *keys))
        for keys in (
            ("latencyState", "latency_state"),
            ("errorState", "error_state"),
        )
    )
    return bool(
        as_of
        and freshness
        and _has_value(_value(sla, "maxAgePolicy", "max_age_policy"))
        and _has_value(_value(sla, "providerSlaStatus", "provider_sla_status"))
        and _has_value(_value(sla, "freshnessSeconds", "freshness_seconds"))
        and _has_value(_value(sla, "freshnessState", "freshness_state"))
        and has_latency_or_error_state
    )


def _family_present_taxonomy(data: Mapping[str, Any]) -> bool:
    taxonomy = _family_mapping(
        data,
        "expirationTaxonomyEvidence",
        "expiration_taxonomy_evidence",
        "taxonomyEvidence",
        "taxonomy_evidence",
    )
    return all(
        _has_value(_value(taxonomy, *keys))
        for keys in (
            ("weekly",),
            ("monthly",),
            ("quarterly",),
            ("standard",),
            ("leaps", "LEAPS"),
            ("specialExpirations", "special_expirations"),
            ("classificationSource", "classification_source"),
        )
    )


def _family_present_adjusted_deliverable(data: Mapping[str, Any]) -> bool:
    adjusted = _family_mapping(
        data,
        "adjustedDeliverableEvidence",
        "adjusted_deliverable_evidence",
        "deliverableEvidence",
        "deliverable_evidence",
    )
    return all(
        _has_value(_value(adjusted, *keys))
        for keys in (
            ("occMemoReference", "occ_memo_reference", "equivalentReference", "equivalent_reference"),
            ("effectiveDate", "effective_date"),
            ("adjustedRootClass", "adjusted_root_class", "adjustedRootOrClass", "adjusted_root_or_class"),
            ("deliverableComponents", "deliverable_components"),
            ("multiplier",),
            ("cashInLieu", "cash_in_lieu"),
            ("standardContract", "standard_contract", "nonStandardFlag", "non_standard_flag"),
            ("contractSymbolMapping", "contract_symbol_mapping"),
        )
    )


def _build_authority_evidence_checklist(
    data: Mapping[str, Any],
    *,
    as_of: str | None,
    freshness: str | None,
) -> dict[str, dict[str, Any]]:
    family_presence = {
        "provenance": _family_present_provenance(data),
        "entitlement": _family_present_entitlement(data),
        "sla_freshness": _family_present_sla(data, as_of, freshness),
        "expiration_taxonomy": _family_present_taxonomy(data),
        "adjusted_deliverable": _family_present_adjusted_deliverable(data),
    }
    return {
        family: {
            "present": family_presence[family],
            "required": True,
            "fields": list(fields),
        }
        for family, fields in EXPIRATION_CALENDAR_REQUIRED_FUTURE_EVIDENCE_FAMILIES.items()
    }


def build_options_expiration_calendar_authority_diagnostic(
    evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    data = _mapping(evidence)
    provider_id = _sanitize_text(_value(data, "providerId", "provider_id"))
    source_type = _sanitize_text(_value(data, "sourceType", "source_type"))
    source_authority = _sanitize_text(_value(data, "sourceAuthority", "source_authority"))
    expiration_calendar_status = (
        _sanitize_text(_value(data, "expirationCalendarStatus", "expiration_calendar_status"))
        or "unavailable"
    )
    authority_policy_source = _sanitize_text(
        _value(data, "authorityPolicySource", "authority_policy_source")
    )
    as_of = _sanitize_text(_value(data, "asOf", "as_of"))
    freshness = _sanitize_text(_value(data, "freshness"))
    underlying = _sanitize_text(_value(data, "underlying"))
    symbol = _sanitize_text(_value(data, "symbol")) or underlying
    expiration_dates = _string_list(_value(data, "expirationDates", "expiration_dates"))
    expiration_count = _non_negative_int(_value(data, "expirationCount", "expiration_count"))
    if expiration_count is None and expiration_dates:
        expiration_count = len(expiration_dates)
    expiration_types = _string_list(_value(data, "expirationTypes", "expiration_types"))
    date_range = _date_range(_value(data, "dateRange", "date_range"))
    lookahead_window = _sanitize_text(_value(data, "lookaheadWindow", "lookahead_window"))
    coverage_metadata = _sanitize_mapping(_value(data, "coverageMetadata", "coverage_metadata"))
    exchange = _sanitize_text(_value(data, "exchange"))
    occ = _sanitize_text(_value(data, "occ", "OCC"))
    opra = _sanitize_text(_value(data, "opra", "OPRA"))
    authorized_source_metadata = _sanitize_mapping(
        _value(data, "authorizedSourceMetadata", "authorized_source_metadata")
    )
    sandbox_or_production = _sanitize_text(
        _value(data, "sandboxOrProduction", "sandbox_or_production")
    )
    checklist_requested = any(
        (
            authority_policy_source == INTERNAL_OPTIONS_EXPIRATION_CALENDAR_AUTHORITY_POLICY_SOURCE,
            isinstance(_value(data, "provenanceEvidence", "provenance_evidence"), Mapping),
            isinstance(_value(data, "entitlementMetadata", "entitlement_metadata"), Mapping),
            isinstance(_value(data, "slaEvidence", "sla_evidence"), Mapping),
            isinstance(
                _value(data, "expirationTaxonomyEvidence", "expiration_taxonomy_evidence"), Mapping
            ),
            isinstance(
                _value(data, "adjustedDeliverableEvidence", "adjusted_deliverable_evidence"), Mapping
            ),
        )
    )

    evidence_present = any(
        (
            provider_id,
            source_type,
            _normalized_text(expiration_calendar_status) == "available",
            underlying,
            symbol,
            bool(expiration_dates),
            expiration_count not in (None, 0),
            bool(expiration_types),
            date_range,
            lookahead_window,
            bool(coverage_metadata),
        )
    )
    reason_codes: list[str] = []
    if not evidence_present:
        reason_codes.extend(["expiration_calendar_authority_missing", "expiration_calendar_missing"])
    else:
        reason_codes.append("expiration_calendar_authority_missing")
        reason_codes.extend(_source_reason_codes(data))
    if _provider_self_claimed(data) and (
        authority_policy_source != INTERNAL_OPTIONS_EXPIRATION_CALENDAR_AUTHORITY_POLICY_SOURCE
    ):
        reason_codes.append("expiration_calendar_provider_self_claim_ignored")
    if not source_authority:
        reason_codes.append("expiration_calendar_source_authority_missing")
    if not as_of or not freshness:
        reason_codes.append("expiration_calendar_asof_or_freshness_missing")
    if not coverage_metadata:
        reason_codes.append("expiration_calendar_coverage_metadata_missing")
    if not date_range and not lookahead_window:
        reason_codes.append("expiration_calendar_date_range_missing")
    authority_evidence_checklist = (
        _build_authority_evidence_checklist(data, as_of=as_of, freshness=freshness)
        if checklist_requested
        else None
    )
    if authority_evidence_checklist:
        for family, checklist_entry in authority_evidence_checklist.items():
            if not checklist_entry["present"]:
                reason_codes.append(_CHECKLIST_REASON_CODES[family])

    authoritative = bool(
        evidence_present
        and authority_policy_source == INTERNAL_OPTIONS_EXPIRATION_CALENDAR_AUTHORITY_POLICY_SOURCE
        and _normalized_text(source_authority) in _AUTHORITATIVE_SOURCE_AUTHORITIES
        and as_of
        and freshness
        and (underlying or symbol)
        and (expiration_dates or expiration_count)
        and (date_range or lookahead_window)
        and coverage_metadata
        and authority_evidence_checklist
        and all(entry["present"] for entry in authority_evidence_checklist.values())
        and not _source_reason_codes(data)
    )
    if evidence_present and not authoritative and coverage_metadata.get("expirationCoverage"):
        reason_codes.append("expiration_calendar_coverage_not_authority")
    authority_state = "authoritative" if authoritative else ("non_authoritative" if evidence_present else "missing")

    return {
        "diagnosticOnly": True,
        "authorityState": authority_state,
        "authoritative": authoritative,
        "providerId": provider_id,
        "sourceType": source_type,
        "sourceAuthority": source_authority,
        "expirationCalendarStatus": expiration_calendar_status,
        "authorityPolicySource": authority_policy_source,
        "asOf": as_of,
        "freshness": freshness,
        "underlying": underlying,
        "symbol": symbol,
        "expirationDates": expiration_dates,
        "expirationCount": expiration_count,
        "expirationTypes": expiration_types,
        "dateRange": date_range,
        "lookaheadWindow": lookahead_window,
        "coverageMetadata": coverage_metadata,
        "exchange": exchange,
        "occ": occ,
        "opra": opra,
        "authorizedSourceMetadata": authorized_source_metadata,
        "sandboxOrProduction": sandbox_or_production,
        "reasonCodes": [] if authoritative else _dedupe(reason_codes),
        "requiredFutureAuthorityEvidence": list(
            REQUIRED_FUTURE_EXPIRATION_CALENDAR_AUTHORITY_EVIDENCE_FIELDS
        ),
        **(
            {"authorityEvidenceChecklist": authority_evidence_checklist}
            if authority_evidence_checklist
            else {}
        ),
    }
