# -*- coding: utf-8 -*-
"""Build compact report evidence exports from already-present report sidecars."""

from collections.abc import Mapping
from typing import Any, Dict, Optional


REPORT_EVIDENCE_EXPORT_CONTRACT_VERSION = "report_evidence_export_v1"
REPORT_EVIDENCE_EXPORT_PAYLOAD_CLASS = "compact"

REPORT_EVIDENCE_SIDECAR_FIELDS = (
    "researchReadiness",
    "evidenceCoverageFrame",
    "singleStockEvidencePacket",
    "evidenceCitationFrame",
    "sourceProvenanceFrame",
)

_REDACT_NORMALIZED_KEYS = {
    "apikey",
    "cachekey",
    "cachestate",
    "circuitstate",
    "contextsnapshot",
    "cookie",
    "credential",
    "credentials",
    "debugref",
    "internaldiagnostics",
    "latencybucket",
    "latencybuckets",
    "llmpayload",
    "llmresponse",
    "maintainerremediation",
    "password",
    "prompt",
    "providerpayload",
    "quotabucket",
    "quotabuckets",
    "rawairesponse",
    "rawllmpayload",
    "rawllmresponse",
    "rawproviderpayload",
    "rawproviderpayloads",
    "rawresult",
    "rawresponse",
    "reasoncode",
    "reasoncodes",
    "reasonfamilies",
    "retrystate",
    "routerinternals",
    "sessionid",
    "sourcerefid",
    "stacktrace",
    "token",
    "traceid",
}


def _normalize_key(key: Any) -> str:
    return "".join(ch for ch in str(key).lower() if ch.isalnum())


def _is_redacted_key(key: Any) -> bool:
    normalized = _normalize_key(key)
    return normalized in _REDACT_NORMALIZED_KEYS or normalized.startswith(
        ("raw", "debuginternal")
    )


def _sanitize_compact(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized: Dict[str, Any] = {}
        for key, item in value.items():
            if _is_redacted_key(key):
                continue
            sanitized[str(key)] = _sanitize_compact(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_compact(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_compact(item) for item in value]
    return value


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _first_present(*values: Any) -> Optional[Any]:
    for value in values:
        if value is not None:
            return value
    return None


def _camel_report_identity(report: Mapping[str, Any]) -> Dict[str, Any]:
    meta = _mapping(report.get("meta"))
    return {
        "queryId": _first_present(
            meta.get("query_id"),
            meta.get("queryId"),
            report.get("query_id"),
            report.get("queryId"),
        ),
        "stockCode": _first_present(
            meta.get("stock_code"),
            meta.get("stockCode"),
            report.get("stock_code"),
            report.get("stockCode"),
        ),
        "stockName": _first_present(
            meta.get("stock_name"),
            meta.get("stockName"),
            report.get("stock_name"),
            report.get("stockName"),
        ),
        "companyName": _first_present(
            meta.get("company_name"),
            meta.get("companyName"),
            report.get("company_name"),
            report.get("companyName"),
        ),
        "reportType": _first_present(
            meta.get("report_type"),
            meta.get("reportType"),
            report.get("report_type"),
            report.get("reportType"),
        ),
        "reportLanguage": _first_present(
            meta.get("report_language"),
            meta.get("reportLanguage"),
            report.get("report_language"),
            report.get("reportLanguage"),
        ),
        "createdAt": _first_present(
            meta.get("created_at"),
            meta.get("createdAt"),
            report.get("created_at"),
            report.get("createdAt"),
        ),
        "reportGeneratedAt": _first_present(
            meta.get("report_generated_at"),
            meta.get("reportGeneratedAt"),
            meta.get("generated_at"),
            meta.get("generatedAt"),
            report.get("report_generated_at"),
            report.get("reportGeneratedAt"),
        ),
    }


def _analysis_result(report: Mapping[str, Any]) -> Dict[str, Any]:
    details = _mapping(report.get("details"))
    return _mapping(details.get("analysis_result") or details.get("analysisResult"))


def _extract_sidecar(report: Mapping[str, Any], field_name: str) -> Any:
    meta = _mapping(report.get("meta"))
    analysis_result = _analysis_result(report)
    for container in (report, meta, analysis_result):
        if field_name in container:
            return container.get(field_name)
    return None


def _build_availability(sidecars: Mapping[str, Any]) -> Dict[str, Any]:
    present = [
        field
        for field in REPORT_EVIDENCE_SIDECAR_FIELDS
        if sidecars.get(field) is not None
    ]
    missing = [field for field in REPORT_EVIDENCE_SIDECAR_FIELDS if field not in present]
    if len(present) == len(REPORT_EVIDENCE_SIDECAR_FIELDS):
        state = "available"
    elif present:
        state = "partial"
    else:
        state = "unavailable"
    return {
        "state": state,
        "presentSidecars": present,
        "missingSidecars": missing,
    }


def _build_redaction_posture() -> Dict[str, str]:
    return {
        "payloadPolicy": "allowlisted_report_sidecars_with_recursive_internal_field_redaction",
        "rawProviderPayloads": "excluded",
        "rawPromptPayloads": "excluded",
        "rawLlmPayloads": "excluded",
        "credentialsAndSecrets": "excluded",
        "debugAndInternalFields": "excluded",
        "cacheAndRouterInternals": "excluded",
    }


def _build_no_advice_boundary(sidecars: Mapping[str, Any]) -> Dict[str, Any]:
    packet = _mapping(sidecars.get("singleStockEvidencePacket"))
    if "noAdviceBoundary" in packet:
        return {
            "state": "available",
            "sourceSidecar": "singleStockEvidencePacket",
            "sourceField": "noAdviceBoundary",
            "value": packet.get("noAdviceBoundary"),
        }

    citation_frame = _mapping(sidecars.get("evidenceCitationFrame"))
    if "noAdviceBoundary" in citation_frame:
        return {
            "state": "available",
            "sourceSidecar": "evidenceCitationFrame",
            "sourceField": "noAdviceBoundary",
            "value": citation_frame.get("noAdviceBoundary"),
        }

    readiness = _mapping(sidecars.get("researchReadiness"))
    if "consumerActionBoundary" in readiness:
        return {
            "state": "available",
            "sourceSidecar": "researchReadiness",
            "sourceField": "consumerActionBoundary",
            "value": readiness.get("consumerActionBoundary"),
        }

    return {
        "state": "unavailable",
        "sourceSidecar": None,
        "sourceField": None,
        "value": None,
    }


def build_report_evidence_export(report_payload: Mapping[str, Any] | None) -> Dict[str, Any]:
    """Wrap existing report evidence sidecars in a compact read-only export.

    The helper only reads fields already present on the supplied report payload,
    its meta block, or its details.analysis_result mirror. Missing sidecars are
    represented through availability metadata and are never reconstructed.
    """

    report = report_payload if isinstance(report_payload, Mapping) else {}
    sidecars = {
        field_name: _sanitize_compact(_extract_sidecar(report, field_name))
        for field_name in REPORT_EVIDENCE_SIDECAR_FIELDS
    }
    return {
        "contractVersion": REPORT_EVIDENCE_EXPORT_CONTRACT_VERSION,
        "payloadClass": REPORT_EVIDENCE_EXPORT_PAYLOAD_CLASS,
        "reportIdentity": _camel_report_identity(report),
        "availability": _build_availability(sidecars),
        "redactionPosture": _build_redaction_posture(),
        "noAdviceBoundary": _build_no_advice_boundary(sidecars),
        "sidecars": sidecars,
    }
