# -*- coding: utf-8 -*-
"""Consumed Home/analysis evidence DTO subset.

These models intentionally describe only the report evidence metadata already
emitted and consumed across Home/analysis boundaries. They are schema locks, not
runtime provenance generators.
"""

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, TypeAdapter, model_serializer, model_validator


_INTELLIGENCE_PACKET_DROP_KEYS = {
    "debugref",
    "debug_ref",
    "debugid",
    "debug_id",
    "diagnosticid",
    "diagnostic_id",
    "datasource",
    "data_source",
    "datasourceid",
    "data_source_id",
    "datasources",
    "data_sources",
    "internalid",
    "internal_id",
    "internalsource",
    "internal_source",
    "internalsourceid",
    "internal_source_id",
    "internalsourcelabel",
    "internal_source_label",
    "provider",
    "provider_id",
    "provider_key",
    "provider_label",
    "provider_name",
    "provider_ref",
    "providerid",
    "providerids",
    "providerkey",
    "providerkeys",
    "providerlabel",
    "providerlabels",
    "providername",
    "providernames",
    "providerref",
    "providerrefs",
    "providers",
    "provider_ids",
    "provider_keys",
    "provider_labels",
    "provider_names",
    "provider_refs",
    "queryid",
    "query_id",
    "rawqueryid",
    "raw_query_id",
    "routeid",
    "route_id",
    "routeids",
    "route_ids",
    "routekey",
    "route_key",
    "routekeys",
    "route_keys",
    "routelabel",
    "route_label",
    "routelabels",
    "route_labels",
    "routeref",
    "route_ref",
    "routerefs",
    "route_refs",
    "source",
    "source_id",
    "source_ids",
    "source_key",
    "source_keys",
    "source_label",
    "source_labels",
    "source_name",
    "source_names",
    "source_ref",
    "source_refs",
    "sourceid",
    "sourceids",
    "sourcekey",
    "sourcekeys",
    "sourcelabel",
    "sourcelabels",
    "sourcename",
    "sourcenames",
    "sourceref",
    "sourcerefs",
    "sources",
}
_INTELLIGENCE_PACKET_TEXT_REPLACEMENTS = (
    (re.compile(r"\bdebug[_\s-]?ref\b\s*[:=]?\s*[\w:./-]*", re.IGNORECASE), "reference label"),
    (re.compile(r"\braw[_\s-]?prompt\b\s*[:=]?\s*[\w:./-]*", re.IGNORECASE), "input text"),
    (re.compile(r"\bprompt\s*:\s*[^.;\n]+", re.IGNORECASE), "input text"),
    (re.compile(r"\bprovider[_\s-]?payload(?:[_\s-]?ref)?\b\s*[:=]?\s*[\w:./-]*", re.IGNORECASE), "internal reference"),
    (re.compile(r"\bpayload[-_:][A-Za-z0-9_.:-]+", re.IGNORECASE), "internal reference"),
    (re.compile(r"\btraceback\b(?:\s*\([^)]*\))?", re.IGNORECASE), "diagnostic trace"),
    (re.compile(r"\bstack\s+trace\b", re.IGNORECASE), "diagnostic trace"),
    (re.compile(r"\bmost recent call last\b", re.IGNORECASE), "diagnostic trace"),
    (re.compile(r"\binternal[_\s-]?diagnostic(?:[_\s-]?token)?\b\s*[:=]?\s*[\w:./-]*", re.IGNORECASE), "internal note"),
    (re.compile(r"\bdiag[-_][A-Za-z0-9_.:-]+", re.IGNORECASE), "internal note"),
    (re.compile(r"\bquery[-_][A-Za-z0-9_.:-]+", re.IGNORECASE), "request reference"),
    (re.compile(r"\bsource[_\s-]?(?:id|ref|key|label|name)\b\s*[:=]?\s*[\w:./-]*", re.IGNORECASE), "source label"),
    (re.compile(r"\b[A-Za-z]+-source-\d+[A-Za-z0-9_.:-]*\b", re.IGNORECASE), "source label"),
    (re.compile(r"\bprovider[_\s-]?(?:id|ref|key|label|name)\b\s*[:=]?\s*[\w:./-]*", re.IGNORECASE), "source label"),
    (re.compile(r"\broute[_\s-]?(?:id|ref|key|label)\b\s*[:=]?\s*[\w:./-]*", re.IGNORECASE), "source label"),
    (re.compile(r"\bdebug[_\s-]?id\b\s*[:=]?\s*[\w:./-]*", re.IGNORECASE), "internal note"),
    (re.compile(r"\b(?:fmp|polygon_us_grouped_daily)\b", re.IGNORECASE), "source label"),
    (re.compile(r"\b(?:authorization|bearer)\b\s*[:=]?\s*[\w:./-]*", re.IGNORECASE), "credential marker"),
    (re.compile(r"\btoken\s*=\s*[\w:./-]+", re.IGNORECASE), "credential marker"),
    (re.compile(r"\bsecret[-_][A-Za-z0-9_.:-]+\b", re.IGNORECASE), "credential marker"),
)


def _sanitize_intelligence_packet_value(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = re.sub(r"[^a-z0-9_]+", "", str(key).lower())
            if normalized_key in _INTELLIGENCE_PACKET_DROP_KEYS:
                continue
            sanitized[key] = _sanitize_intelligence_packet_value(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_intelligence_packet_value(item) for item in value]
    if isinstance(value, str):
        text = value
        for pattern, replacement in _INTELLIGENCE_PACKET_TEXT_REPLACEMENTS:
            text = pattern.sub(replacement, text)
        return text
    return value


class _HomeEvidenceBase(BaseModel):
    """Allow historical/additive keys without serializing unset defaults."""

    model_config = ConfigDict(extra="allow")

    @model_serializer(mode="wrap")
    def _serialize_without_unset_defaults(self, handler: Any) -> Dict[str, Any]:
        data = handler(self)
        return {
            key: value
            for key, value in data.items()
            if key in self.model_fields_set or value is not None
        }


class HomeResearchReadiness(_HomeEvidenceBase):
    researchReady: Optional[bool] = None
    readinessState: Optional[str] = None
    missingEvidence: Optional[List[str]] = None
    blockingReasons: Optional[List[str]] = None
    sourceAuthority: Optional[str] = None
    consumerActionBoundary: Optional[str] = None
    freshnessFloor: Optional[str] = None


class HomeEvidenceCoverageDomain(_HomeEvidenceBase):
    status: Optional[str] = None
    sourceTier: Optional[str] = None
    providerAuthority: Optional[str] = None
    freshness: Optional[str] = None
    fallbackOrProxy: Optional[bool] = None
    missingReasons: Optional[List[str]] = None
    nextEvidenceNeeded: Optional[List[str]] = None


class HomeSingleStockEvidenceDomain(_HomeEvidenceBase):
    status: Optional[str] = None
    sourceTier: Optional[str] = None
    providerAuthority: Optional[str] = None
    freshness: Optional[str] = None
    fallbackOrProxy: Optional[bool] = None
    missingReasons: Optional[List[str]] = None
    nextEvidenceNeeded: Optional[List[str]] = None


class HomeSingleStockEvidencePacket(_HomeEvidenceBase):
    contractVersion: Optional[str] = None
    symbol: Optional[str] = None
    market: Optional[str] = None
    packetState: Optional[str] = None
    domains: Optional[Dict[str, HomeSingleStockEvidenceDomain]] = None
    sourceSummary: Optional[Dict[str, Any]] = None
    missingEvidence: Optional[List[str]] = None
    blockingReasons: Optional[List[str]] = None
    nextEvidenceNeeded: Optional[List[str]] = None
    noAdviceBoundary: Optional[Any] = None
    debugRef: Optional[str] = None
    fundamentalsEarnings: Optional[Dict[str, Any]] = None
    newsCatalysts: Optional[Dict[str, Any]] = None


class HomeEvidenceCitationCoverage(_HomeEvidenceBase):
    domain: Optional[str] = None
    status: Optional[str] = None
    authorityLabel: Optional[str] = None
    freshnessLabel: Optional[str] = None
    notes: Optional[List[str]] = None


class HomeCitedEvidence(_HomeEvidenceBase):
    id: Optional[str] = None
    domain: Optional[str] = None
    sourceId: Optional[str] = None
    freshness: Optional[str] = None


class HomeEvidenceCitationFrame(_HomeEvidenceBase):
    contractVersion: Optional[str] = None
    frameState: Optional[str] = None
    symbol: Optional[str] = None
    market: Optional[str] = None
    missingEvidence: Optional[List[str]] = None
    blockingReasons: Optional[List[str]] = None
    noAdviceBoundary: Optional[bool] = None
    citedEvidence: Optional[List[HomeCitedEvidence]] = None
    domainCoverage: Optional[List[HomeEvidenceCitationCoverage]] = None
    nextEvidenceNeeded: Optional[List[str]] = None


class HomeSourceProvenanceEntry(_HomeEvidenceBase):
    contractVersion: Optional[str] = None
    sourceId: Optional[str] = None
    sourceLabel: Optional[str] = None
    evidenceDomain: Optional[str] = None
    authorityTier: Optional[str] = None
    freshnessState: Optional[str] = None
    sourceTier: Optional[str] = None
    fallbackOrProxy: Optional[bool] = None
    observationOnly: Optional[bool] = None
    scoreContributionAllowed: Optional[bool] = None
    limitations: Optional[List[str]] = None
    nextEvidenceNeeded: Optional[List[str]] = None
    debugRef: Optional[str] = None


class IntelligenceReportPacketThesis(_HomeEvidenceBase):
    summary: Optional[str] = None
    confidenceLabel: Optional[str] = None


class IntelligenceReportPacketEvidenceItem(_HomeEvidenceBase):
    id: Optional[str] = None
    domain: Optional[str] = None
    summary: Optional[str] = None
    sourceId: Optional[str] = None
    authority: Optional[str] = None
    freshness: Optional[str] = None


class IntelligenceReportPacketConfidence(_HomeEvidenceBase):
    cap: Optional[float] = None
    label: Optional[str] = None
    highConfidenceAllowed: Optional[bool] = None
    cappedBy: Optional[List[str]] = None


class IntelligenceReportPacketSourceAuthority(_HomeEvidenceBase):
    state: Optional[str] = None
    scoreGradeCount: Optional[int] = None
    observationOnlyCount: Optional[int] = None
    missingCount: Optional[int] = None
    sourceCount: Optional[int] = None


class IntelligenceReportPacketFreshness(_HomeEvidenceBase):
    floor: Optional[str] = None
    staleSources: Optional[List[str]] = None
    fallbackOrProxySources: Optional[List[str]] = None


class IntelligenceReportPacketV2(_HomeEvidenceBase):
    @model_validator(mode="before")
    @classmethod
    def _sanitize_legacy_internal_refs(cls, value: Any) -> Any:
        return _sanitize_intelligence_packet_value(value)

    contractVersion: Optional[str] = None
    packetState: Optional[str] = None
    consumerActionBoundary: Optional[str] = None
    noAdviceBoundary: Optional[bool] = None
    thesis: Optional[IntelligenceReportPacketThesis] = None
    evidence: Optional[List[IntelligenceReportPacketEvidenceItem]] = None
    counterEvidence: Optional[List[IntelligenceReportPacketEvidenceItem]] = None
    missingData: Optional[List[str]] = None
    confidence: Optional[IntelligenceReportPacketConfidence] = None
    sourceAuthority: Optional[IntelligenceReportPacketSourceAuthority] = None
    freshness: Optional[IntelligenceReportPacketFreshness] = None
    scenarioRisks: Optional[List[str]] = None
    nextVerificationSteps: Optional[List[str]] = None


HomeEvidenceCoverageFrame = Dict[str, HomeEvidenceCoverageDomain]
HomeSourceProvenanceFrame = List[HomeSourceProvenanceEntry]

HOME_ANALYSIS_CONSUMED_EVIDENCE_FIELDS = (
    "researchReadiness",
    "evidenceCoverageFrame",
    "singleStockEvidencePacket",
    "evidenceCitationFrame",
    "sourceProvenanceFrame",
    "intelligencePacket",
)

_FIELD_ADAPTERS = {
    "researchReadiness": TypeAdapter(HomeResearchReadiness),
    "evidenceCoverageFrame": TypeAdapter(HomeEvidenceCoverageFrame),
    "singleStockEvidencePacket": TypeAdapter(HomeSingleStockEvidencePacket),
    "evidenceCitationFrame": TypeAdapter(HomeEvidenceCitationFrame),
    "sourceProvenanceFrame": TypeAdapter(HomeSourceProvenanceFrame),
    "intelligencePacket": TypeAdapter(IntelligenceReportPacketV2),
}


def validate_home_evidence_field(field_name: str, value: Any) -> Any:
    """Validate a consumed evidence sidecar while preserving additive keys."""

    adapter = _FIELD_ADAPTERS.get(field_name)
    if adapter is None or value is None:
        return value
    return adapter.validate_python(value)
