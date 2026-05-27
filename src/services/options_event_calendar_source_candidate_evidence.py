# -*- coding: utf-8 -*-
"""Pure observation-only contract for event-calendar source candidate evidence."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence


REDACTED = "redacted"
REQUIRED_EVIDENCE_FAMILIES = (
    "source_identity_and_provenance_chain",
    "licensed_provider_exchange_issuer_official_calendar_backing",
    "entitlement_license_and_use_rights",
    "redistribution_and_decision_use_rights",
    "production_vs_sandbox",
    "delayed_vs_live_status",
    "as_of_freshness_sla_max_age_policy",
    "event_taxonomy",
    "confirmation_status",
    "event_date_time_session_timezone",
    "provider_event_id_and_event_identity",
    "coverage_scope",
    "sanitized_error_and_audit_state",
)
FORBIDDEN_AUTHORITY_OUTPUTS = (
    "authorityGrant true",
    "providerDecisionAuthority",
    "recommendationAuthority",
    "decisionGrade",
    "gateDecision",
    "sourceAuthorityAllowed",
    "provider routing",
    "live-call enablement",
)

_SAFE_TEXT_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789_:-+./ ")
_SECRET_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "password",
    "secret",
    "token",
)
_URL_LIKE_HOST_RE = re.compile(r"^[a-z0-9-]+(?:\.[a-z0-9-]+)+(?::\d+)?(?:[/?#].*)?$")
_EVENT_TAXONOMY_KEYS = (
    "earnings",
    "dividends",
    "exDividend",
    "splits",
    "corporateActions",
    "fomcMacroContext",
)
_EVENT_TAXONOMY_ALLOWED_STATES = {"proven", "missing", "partial", "unverified"}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _looks_like_url_text(text: str) -> bool:
    lowered = text.lower()
    if lowered.startswith(("http://", "https://", "www.")):
        return True
    return bool(_URL_LIKE_HOST_RE.fullmatch(lowered))


def _sanitize_text(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    lowered = text.lower()
    if any(marker in lowered for marker in _SECRET_MARKERS):
        return REDACTED
    if _looks_like_url_text(text):
        return REDACTED
    if any(marker in text for marker in ("{", "}", "[", "]")):
        return REDACTED
    if len(text) > 160:
        return REDACTED
    if any(character.lower() not in _SAFE_TEXT_CHARS for character in text):
        return REDACTED
    return text


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _sanitize_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return _sanitize_sequence(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    return _sanitize_text(value)


def _sanitize_mapping(value: Any) -> dict[str, Any]:
    data = _mapping(value)
    sanitized: dict[str, Any] = {}
    for key, raw in data.items():
        safe_key = _sanitize_text(key)
        if not safe_key:
            continue
        safe_value = _sanitize_value(raw)
        if safe_value in (None, "", [], {}):
            continue
        sanitized[safe_key] = safe_value
    return sanitized


def _sanitize_sequence(value: Any) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    sanitized: list[Any] = []
    for item in value:
        safe_value = _sanitize_value(item)
        if safe_value in (None, "", [], {}):
            continue
        sanitized.append(safe_value)
    return sanitized


def _get_text(data: Mapping[str, Any], key: str) -> str | None:
    return _sanitize_text(data.get(key))


def _get_int(data: Mapping[str, Any], key: str) -> int | None:
    value = data.get(key)
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _get_bool(data: Mapping[str, Any], key: str) -> bool | None:
    value = data.get(key)
    return value if isinstance(value, bool) else None


def _has_text_fields(section: Mapping[str, Any], keys: Sequence[str]) -> bool:
    return all(_sanitize_text(section.get(key)) for key in keys)


def _build_source_identity(data: Mapping[str, Any]) -> dict[str, Any]:
    identity = {
        "candidateSourceName": _get_text(data, "candidateSourceName"),
        "providerName": _get_text(data, "providerName"),
        "providerId": _get_text(data, "providerId"),
        "distributorName": _get_text(data, "distributorName"),
        "sourceClass": _get_text(data, "sourceClass"),
        "marketRegionCoverageClaim": _get_text(data, "marketRegionCoverageClaim"),
        "evidenceCaptureMethod": _get_text(data, "evidenceCaptureMethod"),
        "documentReference": _get_text(data, "documentReference"),
        "productName": _get_text(data, "productName"),
    }
    return {key: value for key, value in identity.items() if value is not None}


def _build_backing_entry(
    data: Mapping[str, Any],
    claim_key: str,
    proof_key: str,
) -> dict[str, Any]:
    claim = data.get(claim_key)
    proof_reference = _get_text(data, proof_key)
    result: dict[str, Any] = {}
    if isinstance(claim, bool):
        result["claimed"] = claim
    elif claim not in (None, ""):
        sanitized = _sanitize_text(claim)
        if sanitized is not None:
            result["claimed"] = sanitized
    if proof_reference is not None:
        result["proofReference"] = proof_reference
    return result


def _build_provenance(data: Mapping[str, Any]) -> dict[str, Any]:
    provenance_chain = _sanitize_sequence(data.get("provenanceChain"))
    backing = {
        "licensedProvider": _build_backing_entry(
            data,
            "licensedProviderBackingClaim",
            "licensedProviderProofReference",
        ),
        "exchange": _build_backing_entry(
            data,
            "exchangeBackingClaim",
            "exchangeProofReference",
        ),
        "issuer": _build_backing_entry(
            data,
            "issuerBackingClaim",
            "issuerProofReference",
        ),
        "officialCalendar": _build_backing_entry(
            data,
            "officialCalendarBackingClaim",
            "officialCalendarProofReference",
        ),
    }
    backing = {key: value for key, value in backing.items() if value}
    provenance: dict[str, Any] = {}
    if provenance_chain:
        provenance["provenanceChain"] = provenance_chain
    if backing:
        provenance["backing"] = backing
    return provenance


def _build_entitlement(data: Mapping[str, Any]) -> dict[str, Any]:
    entitlement = {
        "entitlementRequirements": _get_text(data, "entitlementRequirements"),
        "licenseTier": _get_text(data, "licenseTier"),
        "allowedInternalUse": _get_text(data, "allowedInternalUse"),
        "accountBoundary": _get_text(data, "accountBoundary"),
        "redistributionRights": _get_text(data, "redistributionRights"),
        "internalDecisionUseRights": _get_text(data, "internalDecisionUseRights"),
        "storageRights": _get_text(data, "storageRights"),
        "explicitRestrictions": _sanitize_sequence(data.get("explicitRestrictions")),
        "environmentType": _get_text(data, "environmentType"),
        "environmentEvidenceSource": _get_text(data, "environmentEvidenceSource"),
        "liveDelayedStatus": _get_text(data, "liveDelayedStatus"),
        "delayWindow": _get_text(data, "delayWindow"),
        "delayDisclaimer": _get_text(data, "delayDisclaimer"),
    }
    return {key: value for key, value in entitlement.items() if value not in (None, [], {})}


def _build_freshness_sla(data: Mapping[str, Any]) -> dict[str, Any]:
    freshness_sla = {
        "asOf": _get_text(data, "asOf"),
        "freshnessStatement": _get_text(data, "freshnessStatement"),
        "serviceLevelExpectation": _get_text(data, "serviceLevelExpectation"),
        "maxAgePolicy": _get_text(data, "maxAgePolicy"),
        "staleDataHandling": _get_text(data, "staleDataHandling"),
    }
    return {key: value for key, value in freshness_sla.items() if value is not None}


def _build_event_coverage(data: Mapping[str, Any]) -> dict[str, Any]:
    coverage = {
        "coverageType": _get_text(data, "coverageType"),
        "lookaheadWindow": _get_text(data, "lookaheadWindow"),
        "observedEventCount": _get_int(data, "observedEventCount"),
        "supportedRegions": _sanitize_sequence(data.get("supportedRegions")),
        "unsupportedRegions": _sanitize_sequence(data.get("unsupportedRegions")),
        "eventDateRange": _sanitize_mapping(data.get("eventDateRange")),
        "timelineCoverageNotes": _sanitize_sequence(data.get("timelineCoverageNotes")),
        "macroContextNotes": _sanitize_sequence(data.get("macroContextNotes")),
    }
    return {key: value for key, value in coverage.items() if value not in (None, [], {})}


def _build_event_taxonomy(data: Mapping[str, Any]) -> dict[str, str]:
    raw_taxonomy = _mapping(data.get("eventTaxonomy"))
    taxonomy: dict[str, str] = {}
    macro_policy_scope = _get_text(data, "macroPolicyScope")
    for key in _EVENT_TAXONOMY_KEYS:
        if key == "fomcMacroContext" and not macro_policy_scope:
            continue
        value = _sanitize_text(raw_taxonomy.get(key))
        if value is None:
            continue
        normalized = value.lower()
        if normalized in _EVENT_TAXONOMY_ALLOWED_STATES:
            taxonomy[key] = normalized
    return taxonomy


def _build_confirmation_evidence(data: Mapping[str, Any]) -> dict[str, Any]:
    evidence = {
        "confirmationStatusModel": _get_text(data, "confirmationStatusModel"),
        "confirmationEvidenceSource": _get_text(data, "confirmationEvidenceSource"),
        "statusChangeHandling": _get_text(data, "statusChangeHandling"),
    }
    return {key: value for key, value in evidence.items() if value is not None}


def _build_event_identity_evidence(data: Mapping[str, Any]) -> dict[str, Any]:
    evidence = {
        "providerEventIdField": _get_text(data, "providerEventIdField"),
        "eventIdentitySemantics": _get_text(data, "eventIdentitySemantics"),
        "dedupeRules": _get_text(data, "dedupeRules"),
        "correctionHandling": _get_text(data, "correctionHandling"),
    }
    return {key: value for key, value in evidence.items() if value is not None}


def _build_timezone_session_evidence(data: Mapping[str, Any]) -> dict[str, Any]:
    evidence = {
        "eventDateField": _get_text(data, "eventDateField"),
        "eventTimeField": _get_text(data, "eventTimeField"),
        "tradingSessionField": _get_text(data, "tradingSessionField"),
        "timezoneField": _get_text(data, "timezoneField"),
        "timezoneNormalizationNotes": _get_text(data, "timezoneNormalizationNotes"),
        "sessionInterpretationNotes": _get_text(data, "sessionInterpretationNotes"),
    }
    return {key: value for key, value in evidence.items() if value is not None}


def _build_error_audit_state(data: Mapping[str, Any]) -> dict[str, Any]:
    state = {
        "sanitizedErrorClasses": _sanitize_sequence(data.get("sanitizedErrorClasses")),
        "auditCaptureTimestamp": _get_text(data, "auditCaptureTimestamp"),
        "reviewer": _get_text(data, "reviewer"),
        "unresolvedAmbiguityNotes": _sanitize_sequence(data.get("unresolvedAmbiguityNotes")),
        "blockedOrMissingEvidenceReasons": _sanitize_sequence(
            data.get("blockedOrMissingEvidenceReasons")
        ),
        "externalClaimOnly": _get_bool(data, "externalClaimOnly"),
    }
    return {key: value for key, value in state.items() if value not in (None, [], {})}


def _missing_evidence_families(contract: Mapping[str, Any]) -> list[str]:
    missing: list[str] = []
    source_identity = _mapping(contract.get("sourceIdentity"))
    provenance = _mapping(contract.get("provenance"))
    entitlement = _mapping(contract.get("entitlement"))
    freshness_sla = _mapping(contract.get("freshnessSla"))
    event_coverage = _mapping(contract.get("eventCoverage"))
    event_taxonomy = _mapping(contract.get("eventTaxonomy"))
    confirmation = _mapping(contract.get("confirmationEvidence"))
    event_identity = _mapping(contract.get("eventIdentityEvidence"))
    timezone_session = _mapping(contract.get("timezoneSessionEvidence"))
    error_audit_state = _mapping(contract.get("errorAuditState"))

    if not source_identity or not provenance.get("provenanceChain"):
        missing.append("source_identity_and_provenance_chain")
    if not _mapping(provenance.get("backing")):
        missing.append("licensed_provider_exchange_issuer_official_calendar_backing")
    if not _has_text_fields(
        entitlement,
        ("entitlementRequirements", "allowedInternalUse", "accountBoundary"),
    ):
        missing.append("entitlement_license_and_use_rights")
    if not _has_text_fields(
        entitlement,
        ("redistributionRights", "internalDecisionUseRights"),
    ):
        missing.append("redistribution_and_decision_use_rights")
    if not _get_text(entitlement, "environmentType"):
        missing.append("production_vs_sandbox")
    if not _get_text(entitlement, "liveDelayedStatus") or not (
        _get_text(entitlement, "delayWindow") or _get_text(entitlement, "delayDisclaimer")
    ):
        missing.append("delayed_vs_live_status")
    if not _has_text_fields(
        freshness_sla,
        ("asOf", "freshnessStatement", "maxAgePolicy"),
    ):
        missing.append("as_of_freshness_sla_max_age_policy")
    if not event_taxonomy:
        missing.append("event_taxonomy")
    if not _has_text_fields(
        confirmation,
        ("confirmationStatusModel", "confirmationEvidenceSource"),
    ):
        missing.append("confirmation_status")
    if not _has_text_fields(
        timezone_session,
        ("eventDateField", "eventTimeField", "tradingSessionField", "timezoneField"),
    ):
        missing.append("event_date_time_session_timezone")
    if not _has_text_fields(
        event_identity,
        ("providerEventIdField", "eventIdentitySemantics"),
    ):
        missing.append("provider_event_id_and_event_identity")
    if not _get_text(event_coverage, "coverageType") or event_coverage.get(
        "observedEventCount"
    ) is None or not _mapping(event_coverage.get("eventDateRange")):
        missing.append("coverage_scope")
    if not error_audit_state:
        missing.append("sanitized_error_and_audit_state")
    return missing


def build_event_calendar_source_candidate_evidence(
    candidate_evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return a sanitized observation-only candidate evidence contract."""

    data = _mapping(candidate_evidence)
    contract = {
        "diagnosticOnly": True,
        "candidateOnly": True,
        "authorityGrant": False,
        "sourceIdentity": _build_source_identity(data),
        "provenance": _build_provenance(data),
        "entitlement": _build_entitlement(data),
        "freshnessSla": _build_freshness_sla(data),
        "eventCoverage": _build_event_coverage(data),
        "eventTaxonomy": _build_event_taxonomy(data),
        "confirmationEvidence": _build_confirmation_evidence(data),
        "eventIdentityEvidence": _build_event_identity_evidence(data),
        "timezoneSessionEvidence": _build_timezone_session_evidence(data),
        "errorAuditState": _build_error_audit_state(data),
        "forbiddenAuthorityOutputs": list(FORBIDDEN_AUTHORITY_OUTPUTS),
    }
    contract["missingEvidenceFamilies"] = _missing_evidence_families(contract)
    contract["authorityGrant"] = False
    contract["candidateOnly"] = True
    contract["diagnosticOnly"] = True
    return contract
