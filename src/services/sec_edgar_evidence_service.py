# -*- coding: utf-8 -*-
"""Projection helpers for SEC EDGAR companyfacts evidence.

This module is backend-only and metadata-only. It converts already-parsed SEC
companyfacts records into stable evidence DTOs without network calls, runtime
provider wiring, scoring, or raw payload emission.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterable

if TYPE_CHECKING:
    from data_provider.sec_edgar_provider import SecEdgarCompanyFactsParseResult, SecEdgarFactRecord


def _coerce_records(
    parsed_or_records: Any,
) -> tuple[Any, ...]:
    if hasattr(parsed_or_records, "records"):
        return tuple(parsed_or_records.records)
    return tuple(parsed_or_records)


def _is_incomplete(record: SecEdgarFactRecord) -> bool:
    required_for_complete_projection = (
        record.cik,
        record.entity_name,
        record.accession_number,
        record.form,
        record.filed_at,
        record.fiscal_year,
        record.fiscal_period,
        record.period_end_date,
        record.fiscal_end_date,
        record.as_of,
        record.updated_at,
    )
    return any(value is None for value in required_for_complete_projection)


@dataclass(frozen=True, slots=True)
class SecEdgarCompanyFactEvidenceRecord:
    provider_name: str
    provider_id: str
    source: str
    source_tier: str
    trust_level: str
    freshness_expectation: str
    observation_only: bool
    score_contribution_allowed: bool
    evidence_type: str
    concept: str
    taxonomy: str
    unit: str
    value: Any
    accession_number: str | None
    form: str | None
    filed_at: str | None
    fiscal_year: int | None
    fiscal_period: str | None
    period_end_date: str | None
    fiscal_end_date: str | None
    frame: str | None
    entity_name: str | None
    cik: str | None
    as_of: str | None
    updated_at: str | None
    source_ref: str
    degradation_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "providerName": self.provider_name,
            "providerId": self.provider_id,
            "source": self.source,
            "sourceTier": self.source_tier,
            "trustLevel": self.trust_level,
            "freshnessExpectation": self.freshness_expectation,
            "observationOnly": self.observation_only,
            "scoreContributionAllowed": self.score_contribution_allowed,
            "evidenceType": self.evidence_type,
            "concept": self.concept,
            "taxonomy": self.taxonomy,
            "unit": self.unit,
            "value": self.value,
            "accessionNumber": self.accession_number,
            "form": self.form,
            "filedAt": self.filed_at,
            "fiscalYear": self.fiscal_year,
            "fiscalPeriod": self.fiscal_period,
            "periodEndDate": self.period_end_date,
            "fiscalEndDate": self.fiscal_end_date,
            "frame": self.frame,
            "entityName": self.entity_name,
            "cik": self.cik,
            "asOf": self.as_of,
            "updatedAt": self.updated_at,
            "sourceRef": self.source_ref,
            "degradationReason": self.degradation_reason,
        }


def project_sec_edgar_companyfacts_evidence(
    parsed_or_records: Any,
) -> tuple[SecEdgarCompanyFactEvidenceRecord, ...]:
    """Project parsed SEC EDGAR companyfacts records into stable evidence DTOs."""

    evidence_records = []
    for record in _coerce_records(parsed_or_records):
        evidence_records.append(
            SecEdgarCompanyFactEvidenceRecord(
                provider_name=record.provider_name,
                provider_id=record.provider_id,
                source=record.source,
                source_tier=record.source_tier,
                trust_level=record.trust_level,
                freshness_expectation=record.freshness_expectation,
                observation_only=True,
                score_contribution_allowed=False,
                evidence_type="official_company_fact",
                concept=record.concept,
                taxonomy=record.taxonomy,
                unit=record.unit,
                value=record.value,
                accession_number=record.accession_number,
                form=record.form,
                filed_at=record.filed_at,
                fiscal_year=record.fiscal_year,
                fiscal_period=record.fiscal_period,
                period_end_date=record.period_end_date,
                fiscal_end_date=record.fiscal_end_date,
                frame=record.frame,
                entity_name=record.entity_name,
                cik=record.cik,
                as_of=record.as_of,
                updated_at=record.updated_at,
                source_ref=record.source_ref,
                degradation_reason="incomplete_observation_metadata" if _is_incomplete(record) else None,
            )
        )
    return tuple(evidence_records)


__all__ = [
    "SecEdgarCompanyFactEvidenceRecord",
    "project_sec_edgar_companyfacts_evidence",
]
