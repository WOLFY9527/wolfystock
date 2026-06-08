# -*- coding: utf-8 -*-
"""Read-only report evidence export contract.

The export shape intentionally wraps already-present report sidecars. It is a
schema lock for downstream API usage, not an evidence generator.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ReportEvidenceReportIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queryId: Optional[str] = Field(None, description="Report query id")
    stockCode: Optional[str] = Field(None, description="Report stock code")
    stockName: Optional[str] = Field(None, description="Report stock name")
    companyName: Optional[str] = Field(None, description="Report company name")
    reportType: Optional[str] = Field(None, description="Report type")
    reportLanguage: Optional[str] = Field(None, description="Report language")
    createdAt: Optional[str] = Field(None, description="Report creation timestamp")
    reportGeneratedAt: Optional[str] = Field(None, description="Report generation timestamp")


class ReportEvidenceAvailability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str = Field(..., description="available | partial | unavailable")
    presentSidecars: List[str] = Field(
        default_factory=list,
        description="Existing sidecars included in export",
    )
    missingSidecars: List[str] = Field(
        default_factory=list,
        description="Expected sidecars missing from report payload",
    )


class ReportEvidenceRedactionPosture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payloadPolicy: str = Field(..., description="Export redaction policy")
    rawProviderPayloads: str = Field("excluded", description="Raw provider payload posture")
    rawPromptPayloads: str = Field("excluded", description="Raw prompt payload posture")
    rawLlmPayloads: str = Field("excluded", description="Raw LLM payload posture")
    credentialsAndSecrets: str = Field("excluded", description="Credential and secret posture")
    debugAndInternalFields: str = Field("excluded", description="Debug/internal field posture")
    cacheAndRouterInternals: str = Field("excluded", description="Cache/router internal posture")


class ReportEvidenceNoAdviceBoundary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str = Field(..., description="available | unavailable")
    sourceSidecar: Optional[str] = Field(
        None,
        description="Sidecar that carried the no-advice marker",
    )
    sourceField: Optional[str] = Field(
        None,
        description="Field that carried the no-advice marker",
    )
    value: Optional[Any] = Field(None, description="Existing no-advice marker value")


class ReportEvidenceSidecars(BaseModel):
    model_config = ConfigDict(extra="forbid")

    researchReadiness: Optional[Dict[str, Any]] = None
    evidenceCoverageFrame: Optional[Dict[str, Any]] = None
    singleStockEvidencePacket: Optional[Dict[str, Any]] = None
    evidenceCitationFrame: Optional[Dict[str, Any]] = None
    sourceProvenanceFrame: Optional[List[Dict[str, Any]]] = None


class ReportEvidenceExport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contractVersion: str = Field(
        "report_evidence_export_v1",
        description="Report evidence export contract version",
    )
    payloadClass: str = Field("compact", description="Compact export class")
    reportIdentity: ReportEvidenceReportIdentity
    availability: ReportEvidenceAvailability
    redactionPosture: ReportEvidenceRedactionPosture
    noAdviceBoundary: ReportEvidenceNoAdviceBoundary
    sidecars: ReportEvidenceSidecars
