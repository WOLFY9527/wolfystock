# -*- coding: utf-8 -*-
"""Pure observation-only contract for expiration source candidate evidence."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence


REDACTED = "redacted"
REQUIRED_EVIDENCE_FAMILIES = (
    "source_identity_and_provenance_chain",
    "licensed_source_backing",
    "venue_and_calendar_scope",
    "entitlement_and_decision_use_rights",
    "production_vs_sandbox",
    "delayed_vs_live_status",
    "freshness_sla_and_max_age",
    "expiration_dates_count_and_range",
    "expiration_taxonomy",
    "adjusted_deliverable_and_corporate_action_proof",
    "occ_memo_or_equivalent_reference",
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
_TAXONOMY_KEYS = (
    "weekly",
    "monthly",
    "quarterly",
    "standard",
    "leaps",
    "specialExpirations",
)
_TAXONOMY_ALLOWED_STATES = {"proven", "missing", "partial", "unverified"}


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
        "occ": _build_backing_entry(data, "occBackingClaim", "occProofReference"),
        "opra": _build_backing_entry(data, "opraBackingClaim", "opraProofReference"),
        "exchange": _build_backing_entry(
            data,
            "exchangeBackingClaim",
            "exchangeProofReference",
        ),
        "licensedSource": _build_backing_entry(
            data,
            "licensedSourceBackingClaim",
            "licensedSourceProofReference",
        ),
    }
    backing = {key: value for key, value in backing.items() if value}
    venue_calendar_scope = {
        "venueFamily": _get_text(data, "venueFamily"),
        "symbolUniverse": _sanitize_sequence(data.get("symbolUniverse")),
        "productClass": _get_text(data, "productClass"),
        "calendarScopeBoundaries": _get_text(data, "calendarScopeBoundaries"),
        "unsupportedVenueGaps": _sanitize_sequence(data.get("unsupportedVenueGaps")),
    }
    venue_calendar_scope = {
        key: value for key, value in venue_calendar_scope.items() if value not in (None, [], {})
    }
    provenance: dict[str, Any] = {}
    if provenance_chain:
        provenance["provenanceChain"] = provenance_chain
    if backing:
        provenance["backing"] = backing
    if venue_calendar_scope:
        provenance["venueCalendarScope"] = venue_calendar_scope
    return provenance


def _build_entitlement(data: Mapping[str, Any]) -> dict[str, Any]:
    entitlement = {
        "entitlementRequirements": _get_text(data, "entitlementRequirements"),
        "licenseTier": _get_text(data, "licenseTier"),
        "redistributionRights": _get_text(data, "redistributionRights"),
        "storageRetentionLimits": _get_text(data, "storageRetentionLimits"),
        "internalDisplayRights": _get_text(data, "internalDisplayRights"),
        "internalDecisionUseRights": _get_text(data, "internalDecisionUseRights"),
        "explicitRestrictions": _sanitize_sequence(data.get("explicitRestrictions")),
        "environmentType": _get_text(data, "environmentType"),
        "environmentEvidenceSource": _get_text(data, "environmentEvidenceSource"),
        "environmentLimitations": _sanitize_sequence(data.get("environmentLimitations")),
        "liveDelayedStatus": _get_text(data, "liveDelayedStatus"),
        "delayPolicy": _get_text(data, "delayPolicy"),
        "delayedLabels": _sanitize_sequence(data.get("delayedLabels")),
        "liveStatusProven": data.get("liveStatusProven")
        if isinstance(data.get("liveStatusProven"), bool)
        else None,
    }
    return {key: value for key, value in entitlement.items() if value not in (None, [], {})}


def _build_freshness_sla(data: Mapping[str, Any]) -> dict[str, Any]:
    freshness_sla = {
        "asOf": _get_text(data, "asOf"),
        "freshnessStatement": _get_text(data, "freshnessStatement"),
        "updateCadence": _get_text(data, "updateCadence"),
        "serviceLevelExpectation": _get_text(data, "serviceLevelExpectation"),
        "maxAgePolicy": _get_text(data, "maxAgePolicy"),
        "staleDataHandlingNotes": _get_text(data, "staleDataHandlingNotes"),
    }
    return {key: value for key, value in freshness_sla.items() if value is not None}


def _build_expiration_coverage(data: Mapping[str, Any]) -> dict[str, Any]:
    observed_date_range = _sanitize_mapping(data.get("observedDateRange"))
    coverage = {
        "sampleExpirationDates": _sanitize_sequence(data.get("sampleExpirationDates")),
        "observedExpirationCount": _get_int(data, "observedExpirationCount"),
        "observedDateRange": observed_date_range,
        "symbolLevelVariationNotes": _sanitize_sequence(data.get("symbolLevelVariationNotes")),
        "missingDateOrTruncationEvidence": _get_text(data, "missingDateOrTruncationEvidence"),
    }
    return {key: value for key, value in coverage.items() if value not in (None, [], {})}


def _build_expiration_taxonomy(data: Mapping[str, Any]) -> dict[str, str]:
    raw_taxonomy = _mapping(data.get("expirationTaxonomy"))
    taxonomy: dict[str, str] = {}
    for key in _TAXONOMY_KEYS:
        value = _sanitize_text(raw_taxonomy.get(key))
        if value is None:
            continue
        normalized = value.lower()
        if normalized in _TAXONOMY_ALLOWED_STATES:
            taxonomy[key] = normalized
    return taxonomy


def _build_adjusted_deliverable_evidence(data: Mapping[str, Any]) -> dict[str, Any]:
    evidence = {
        "splitAdjustmentHandlingEvidence": _get_text(data, "splitAdjustmentHandlingEvidence"),
        "adjustedDeliverableEvidence": _get_text(data, "adjustedDeliverableEvidence"),
        "contractMultiplierHandlingEvidence": _get_text(
            data,
            "contractMultiplierHandlingEvidence",
        ),
        "corporateActionImpactNotes": _sanitize_sequence(data.get("corporateActionImpactNotes")),
        "knownLimitationsOrUnknowns": _sanitize_sequence(data.get("knownLimitationsOrUnknowns")),
        "occMemoReference": _get_text(data, "occMemoReference"),
        "equivalentAdjustmentNotice": _get_text(data, "equivalentAdjustmentNotice"),
        "referenceCitation": _get_text(data, "referenceCitation"),
    }
    return {key: value for key, value in evidence.items() if value not in (None, [], {})}


def _build_error_audit_state(data: Mapping[str, Any]) -> dict[str, Any]:
    state = {
        "sanitizedErrorClasses": _sanitize_sequence(data.get("sanitizedErrorClasses")),
        "blockedOrMissingEvidenceReasons": _sanitize_sequence(
            data.get("blockedOrMissingEvidenceReasons")
        ),
        "auditCaptureTimestamp": _get_text(data, "auditCaptureTimestamp"),
        "reviewer": _get_text(data, "reviewer"),
        "unresolvedAmbiguityNotes": _sanitize_sequence(data.get("unresolvedAmbiguityNotes")),
    }
    return {key: value for key, value in state.items() if value not in (None, [], {})}


def _missing_evidence_families(contract: Mapping[str, Any]) -> list[str]:
    missing: list[str] = []
    source_identity = _mapping(contract.get("sourceIdentity"))
    provenance = _mapping(contract.get("provenance"))
    entitlement = _mapping(contract.get("entitlement"))
    freshness_sla = _mapping(contract.get("freshnessSla"))
    expiration_coverage = _mapping(contract.get("expirationCoverage"))
    expiration_taxonomy = _mapping(contract.get("expirationTaxonomy"))
    adjusted = _mapping(contract.get("adjustedDeliverableEvidence"))
    error_audit_state = _mapping(contract.get("errorAuditState"))

    if not source_identity or not provenance.get("provenanceChain"):
        missing.append("source_identity_and_provenance_chain")
    if not _mapping(provenance.get("backing")):
        missing.append("licensed_source_backing")
    if not _mapping(provenance.get("venueCalendarScope")):
        missing.append("venue_and_calendar_scope")
    if not _has_text_fields(
        entitlement,
        ("entitlementRequirements", "redistributionRights", "internalDecisionUseRights"),
    ):
        missing.append("entitlement_and_decision_use_rights")
    if not _get_text(entitlement, "environmentType"):
        missing.append("production_vs_sandbox")
    if not _get_text(entitlement, "liveDelayedStatus") or not (
        _get_text(entitlement, "delayPolicy")
        or entitlement.get("liveStatusProven") is True
        or entitlement.get("delayedLabels")
    ):
        missing.append("delayed_vs_live_status")
    if not _has_text_fields(
        freshness_sla,
        ("asOf", "freshnessStatement", "maxAgePolicy"),
    ):
        missing.append("freshness_sla_and_max_age")
    if not expiration_coverage.get("sampleExpirationDates") or expiration_coverage.get(
        "observedExpirationCount"
    ) is None or not _mapping(expiration_coverage.get("observedDateRange")):
        missing.append("expiration_dates_count_and_range")
    if not expiration_taxonomy:
        missing.append("expiration_taxonomy")
    if not _has_text_fields(
        adjusted,
        (
            "splitAdjustmentHandlingEvidence",
            "adjustedDeliverableEvidence",
            "contractMultiplierHandlingEvidence",
        ),
    ):
        missing.append("adjusted_deliverable_and_corporate_action_proof")
    if not (
        _get_text(adjusted, "occMemoReference")
        or _get_text(adjusted, "equivalentAdjustmentNotice")
        or _get_text(adjusted, "referenceCitation")
    ):
        missing.append("occ_memo_or_equivalent_reference")
    if not error_audit_state:
        missing.append("sanitized_error_and_audit_state")
    return missing


def build_expiration_calendar_source_candidate_evidence(
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
        "expirationCoverage": _build_expiration_coverage(data),
        "expirationTaxonomy": _build_expiration_taxonomy(data),
        "adjustedDeliverableEvidence": _build_adjusted_deliverable_evidence(data),
        "errorAuditState": _build_error_audit_state(data),
        "forbiddenAuthorityOutputs": list(FORBIDDEN_AUTHORITY_OUTPUTS),
    }
    contract["missingEvidenceFamilies"] = _missing_evidence_families(contract)
    contract["authorityGrant"] = False
    contract["candidateOnly"] = True
    contract["diagnosticOnly"] = True
    return contract
