# -*- coding: utf-8 -*-
"""Pure local projection for backtest PIT/adjusted data provenance posture."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


PROJECTION_VERSION = "backtest_data_provenance_projection_v1"
_SOURCE_LABEL_KEYS = {
    "datasetLabel",
    "freshness",
    "provider",
    "provenanceLabel",
    "source",
    "sourceLabel",
}
_CAPABILITY_DEFINITIONS = (
    (
        "pointInTimeUniverseMembership",
        "unavailable",
        "pit_universe_membership_contract_missing",
        "Versioned point-in-time universe membership with effective dates.",
        "No point-in-time universe membership contract is present.",
    ),
    (
        "survivorshipBiasSafeUniverseEvidence",
        "unavailable",
        "survivorship_bias_safe_universe_evidence_missing",
        "Survivorship-bias-safe universe evidence covering inactive and delisted symbols.",
        "No survivorship-bias-safe universe evidence is present.",
    ),
    (
        "delistingInactiveSymbolHandling",
        "unavailable",
        "delisting_inactive_symbol_handling_contract_missing",
        "Explicit delisting and inactive-symbol handling policy.",
        "No delisting or inactive-symbol handling contract is present.",
    ),
    (
        "splitDividendCorporateActionAdjustedOhlcLineage",
        "unavailable",
        "corporate_action_adjusted_ohlc_lineage_missing",
        "Split, dividend, and corporate-action adjusted OHLC lineage.",
        "No adjusted OHLC lineage for splits, dividends, or corporate actions is present.",
    ),
    (
        "adjustmentMethodologyVersion",
        "unavailable",
        "adjustment_methodology_version_missing",
        "Adjustment methodology and version contract.",
        "No adjustment methodology or version is present.",
    ),
    (
        "exchangeCalendarSessionAlignment",
        "unavailable",
        "exchange_calendar_session_alignment_missing",
        "Exchange calendar and session alignment contract.",
        "No exchange calendar or session alignment contract is present.",
    ),
    (
        "symbolIdentifierLineage",
        "unavailable",
        "symbol_identifier_lineage_missing",
        "Symbol, identifier, and symbol-change lineage.",
        "No symbol or identifier lineage contract is present.",
    ),
    (
        "vendorSourceProvenance",
        "unavailable",
        "vendor_source_provenance_missing",
        "Vendor/source provenance for historical bars and universe membership.",
        "No vendor or source provenance contract is present.",
    ),
    (
        "asOfTimestampPolicy",
        "unavailable",
        "as_of_timestamp_policy_missing",
        "As-of timestamp policy for historical data and metadata.",
        "No as-of timestamp policy is present.",
    ),
    (
        "missingStaleBarPolicy",
        "unavailable",
        "missing_stale_bar_policy_missing",
        "Missing-bar and stale-bar policy.",
        "No missing-bar or stale-bar policy is present.",
    ),
    (
        "historicalSnapshotReproducibility",
        "unavailable",
        "historical_snapshot_reproducibility_missing",
        "Historical snapshot reproducibility proof.",
        "No historical snapshot reproducibility proof is present.",
    ),
    (
        "decisionGradeInstitutionalReadiness",
        "not_ready",
        "decision_grade_institutional_readiness_contract_missing",
        "Approved PIT, adjusted data, provenance, reproducibility, and institutional readiness contract.",
        "Decision-grade institutional readiness is not approved.",
    ),
)
_READINESS_CLAIM_KEYS = {
    "adjustmentMethodologyVersion",
    "apiSchemaChanged",
    "asOfTimestampPolicy",
    "authorityGrant",
    "corporateActionAdjustedDataReady",
    "dataIngestionExecuted",
    "decisionGrade",
    "decisionGradeInstitutionalReadiness",
    "delistingInactiveSymbolHandling",
    "engineMathChanged",
    "exchangeCalendarSessionAlignment",
    "exportReadbackWiringChanged",
    "historicalSnapshotReproducibility",
    "historicalSnapshotReproducible",
    "institutionalReadinessApproved",
    "missingStaleBarPolicy",
    "pitAdjustedInstitutionalReady",
    "pointInTimeUniverseMembership",
    "professionalReadinessApproved",
    "providerCallsExecuted",
    "runtimeWiringChanged",
    "splitDividendCorporateActionAdjustedOhlcLineage",
    "survivorshipBiasSafe",
    "survivorshipBiasSafeUniverseEvidence",
    "symbolIdentifierLineage",
    "vendorSourceProvenance",
}
_READINESS_CLAIM_KEYS_LOWER = {key.lower() for key in _READINESS_CLAIM_KEYS}


def build_backtest_data_provenance_projection(
    local_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic diagnostic-only provenance posture projection."""

    return {
        "projectionVersion": PROJECTION_VERSION,
        "projectionKind": "backtest_data_provenance_projection",
        "diagnosticOnly": True,
        "authorityGrant": False,
        "decisionGrade": False,
        "institutionalReadinessApproved": False,
        "professionalReadinessApproved": False,
        "providerCallsExecuted": False,
        "dataIngestionExecuted": False,
        "engineMathChanged": False,
        "runtimeWiringChanged": False,
        "apiSchemaChanged": False,
        "exportReadbackWiringChanged": False,
        "posture": {
            "overallState": "research_diagnostic_only",
            "pitAdjustedInstitutionalReady": False,
            "survivorshipBiasSafe": False,
            "corporateActionAdjustedDataReady": False,
            "historicalSnapshotReproducible": False,
            "summary": (
                "Diagnostic projection only; no PIT universe, survivorship-bias-safe universe, "
                "adjusted OHLC lineage, snapshot reproducibility, or decision-grade institutional "
                "readiness evidence is available."
            ),
        },
        "metadataObservations": _build_metadata_observations(local_metadata),
        "capabilities": _build_capabilities(),
        "limitations": [
            "diagnostic_projection_only",
            "no_point_in_time_universe_membership",
            "no_survivorship_bias_safe_universe_evidence",
            "no_delisting_inactive_symbol_handling",
            "no_corporate_action_adjusted_ohlc_lineage",
            "no_adjustment_methodology_version",
            "no_exchange_calendar_session_alignment",
            "no_symbol_identifier_lineage",
            "no_vendor_source_provenance",
            "no_as_of_timestamp_policy",
            "no_missing_stale_bar_policy",
            "no_historical_snapshot_reproducibility",
            "no_decision_grade_institutional_readiness",
        ],
    }


def _build_capabilities() -> dict[str, dict[str, Any]]:
    return {
        key: {
            "state": state,
            "ready": False,
            "available": False,
            "reasonCode": reason_code,
            "evidenceRequired": evidence_required,
            "summary": summary,
        }
        for key, state, reason_code, evidence_required, summary in _CAPABILITY_DEFINITIONS
    }


def _build_metadata_observations(local_metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(local_metadata, Mapping) or not local_metadata:
        return {
            "callerSupplied": False,
            "acceptedAsReadinessEvidence": False,
            "recognizedKeys": [],
            "sourceLabels": [],
            "ignoredReadinessClaimKeys": [],
        }

    recognized_keys = sorted(_safe_text(key) for key in local_metadata)
    source_labels = _source_labels(local_metadata)
    ignored_claim_keys = sorted(key for key in recognized_keys if _is_readiness_claim_key(key))
    return {
        "callerSupplied": True,
        "acceptedAsReadinessEvidence": False,
        "recognizedKeys": recognized_keys,
        "sourceLabels": source_labels,
        "ignoredReadinessClaimKeys": ignored_claim_keys,
    }


def _source_labels(local_metadata: Mapping[str, Any]) -> list[str]:
    labels: list[str] = []
    for key in sorted(_SOURCE_LABEL_KEYS):
        if key not in local_metadata:
            continue
        labels.extend(_bounded_text_values(local_metadata[key]))
    return _dedupe_sorted(labels)


def _bounded_text_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [_safe_text(value)]
    if isinstance(value, Mapping):
        return []
    if isinstance(value, set):
        return [_safe_text(item) for item in sorted(value, key=_safe_text)]
    if _is_iterable(value):
        return [_safe_text(item) for item in value]
    return [_safe_text(value)]


def _is_iterable(value: Any) -> bool:
    return isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray))


def _dedupe_sorted(values: Iterable[str]) -> list[str]:
    return sorted({value for value in values if value})


def _is_readiness_claim_key(key: str) -> bool:
    return key.lower() in _READINESS_CLAIM_KEYS_LOWER


def _safe_text(value: Any) -> str:
    text = " ".join(str(value or "").strip().split())
    return text[:96]
