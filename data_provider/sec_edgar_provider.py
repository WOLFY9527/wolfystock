# -*- coding: utf-8 -*-
"""Pure SEC EDGAR companyfacts fixture parser.

This module is parser-only. It accepts already-loaded companyfacts payloads and
returns normalized observation-only fact records plus deterministic parse
warnings. It must not read env vars, perform network calls, or affect runtime
provider wiring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


SEC_EDGAR_PROVIDER_NAME = "SEC EDGAR"
SEC_EDGAR_PROVIDER_ID = "sec_edgar"
SEC_EDGAR_SOURCE_TIER = "official_public"
SEC_EDGAR_TRUST_LEVEL = "reliable_for_filings_metadata"
SEC_EDGAR_FRESHNESS_EXPECTATION = "filing_or_daily"


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_cik(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return text
    return digits.zfill(10)


def _normalize_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_unit(value: Any) -> str | None:
    unit = _clean_text(value)
    return unit


def _normalize_date_like(value: Any) -> str | None:
    return _clean_text(value)


def _build_source_ref(
    cik: str | None,
    taxonomy: str,
    concept: str,
    unit: str,
    accession_number: str | None,
    period_end_date: str | None,
    frame: str | None,
) -> str:
    parts = [
        SEC_EDGAR_PROVIDER_ID,
        "companyfacts",
        cik or "unknown_cik",
        taxonomy,
        concept,
        unit,
        accession_number or "no_accession",
        period_end_date or "no_period_end",
        frame or "no_frame",
    ]
    return ":".join(parts)


@dataclass(frozen=True, slots=True)
class SecEdgarParseWarning:
    code: str
    message: str
    taxonomy: str | None = None
    concept: str | None = None
    unit: str | None = None
    row_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "taxonomy": self.taxonomy,
            "concept": self.concept,
            "unit": self.unit,
            "rowIndex": self.row_index,
        }


@dataclass(frozen=True, slots=True)
class SecEdgarFactRecord:
    cik: str | None
    entity_name: str | None
    taxonomy: str
    concept: str
    label: str | None
    description: str | None
    unit: str
    value: Any
    accession_number: str | None
    form: str | None
    filed_at: str | None
    fiscal_year: int | None
    fiscal_period: str | None
    fiscal_end_date: str | None
    period_end_date: str | None
    frame: str | None
    as_of: str | None
    updated_at: str | None
    source_ref: str
    provider_name: str = SEC_EDGAR_PROVIDER_NAME
    provider_id: str = SEC_EDGAR_PROVIDER_ID
    source: str = SEC_EDGAR_PROVIDER_ID
    source_tier: str = SEC_EDGAR_SOURCE_TIER
    trust_level: str = SEC_EDGAR_TRUST_LEVEL
    freshness_expectation: str = SEC_EDGAR_FRESHNESS_EXPECTATION
    observation_only: bool = True
    score_contribution_allowed: bool = False

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
            "cik": self.cik,
            "entityName": self.entity_name,
            "taxonomy": self.taxonomy,
            "concept": self.concept,
            "label": self.label,
            "description": self.description,
            "unit": self.unit,
            "value": self.value,
            "accessionNumber": self.accession_number,
            "form": self.form,
            "filedAt": self.filed_at,
            "fiscalYear": self.fiscal_year,
            "fiscalPeriod": self.fiscal_period,
            "fiscalEndDate": self.fiscal_end_date,
            "periodEndDate": self.period_end_date,
            "frame": self.frame,
            "asOf": self.as_of,
            "updatedAt": self.updated_at,
            "sourceRef": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class SecEdgarCompanyFactsParseResult:
    records: tuple[SecEdgarFactRecord, ...]
    warnings: tuple[SecEdgarParseWarning, ...]
    provider_name: str = SEC_EDGAR_PROVIDER_NAME
    provider_id: str = SEC_EDGAR_PROVIDER_ID
    source_tier: str = SEC_EDGAR_SOURCE_TIER
    trust_level: str = SEC_EDGAR_TRUST_LEVEL
    freshness_expectation: str = SEC_EDGAR_FRESHNESS_EXPECTATION
    observation_only: bool = True
    score_contribution_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "providerName": self.provider_name,
            "providerId": self.provider_id,
            "sourceTier": self.source_tier,
            "trustLevel": self.trust_level,
            "freshnessExpectation": self.freshness_expectation,
            "observationOnly": self.observation_only,
            "scoreContributionAllowed": self.score_contribution_allowed,
            "records": [record.to_dict() for record in self.records],
            "warnings": [warning.to_dict() for warning in self.warnings],
        }


def parse_companyfacts_payload(payload: Mapping[str, Any] | dict[str, Any]) -> SecEdgarCompanyFactsParseResult:
    """Parse a local SEC companyfacts payload into observation-only records."""

    cik = _normalize_cik(payload.get("cik")) if isinstance(payload, Mapping) else None
    entity_name = _clean_text(payload.get("entityName")) if isinstance(payload, Mapping) else None
    payload_updated_at = _normalize_date_like(payload.get("updatedAt")) if isinstance(payload, Mapping) else None
    facts = payload.get("facts") if isinstance(payload, Mapping) else None

    records: list[SecEdgarFactRecord] = []
    warnings: list[SecEdgarParseWarning] = []

    if not isinstance(facts, Mapping):
        return SecEdgarCompanyFactsParseResult(records=(), warnings=())

    for taxonomy, concepts in facts.items():
        taxonomy_name = _clean_text(taxonomy)
        if taxonomy_name is None or not isinstance(concepts, Mapping):
            continue

        for concept, concept_payload in concepts.items():
            concept_name = _clean_text(concept)
            if concept_name is None or not isinstance(concept_payload, Mapping):
                continue

            label = _clean_text(concept_payload.get("label"))
            description = _clean_text(concept_payload.get("description"))
            units = concept_payload.get("units")
            if not isinstance(units, Mapping):
                continue

            for unit, rows in units.items():
                normalized_unit = _normalize_unit(unit)
                if normalized_unit is None:
                    warnings.append(
                        SecEdgarParseWarning(
                            code="invalid_unit_key",
                            message="Skipped SEC fact unit with an empty unit key.",
                            taxonomy=taxonomy_name,
                            concept=concept_name,
                        )
                    )
                    continue
                if not isinstance(rows, list):
                    warnings.append(
                        SecEdgarParseWarning(
                            code="invalid_unit_rows",
                            message="Skipped SEC fact unit whose rows were not a list.",
                            taxonomy=taxonomy_name,
                            concept=concept_name,
                            unit=normalized_unit,
                        )
                    )
                    continue

                for row_index, row in enumerate(rows):
                    if not isinstance(row, Mapping):
                        warnings.append(
                            SecEdgarParseWarning(
                                code="invalid_fact_row",
                                message="Skipped SEC fact row that was not an object.",
                                taxonomy=taxonomy_name,
                                concept=concept_name,
                                unit=normalized_unit,
                                row_index=row_index,
                            )
                        )
                        continue

                    value = row.get("val")
                    if value is None:
                        warnings.append(
                            SecEdgarParseWarning(
                                code="invalid_fact_row",
                                message="Skipped SEC fact row missing a value.",
                                taxonomy=taxonomy_name,
                                concept=concept_name,
                                unit=normalized_unit,
                                row_index=row_index,
                            )
                        )
                        continue

                    period_end_date = _normalize_date_like(row.get("periodEndDate") or row.get("end"))
                    fiscal_end_date = _normalize_date_like(row.get("fiscalEndDate") or period_end_date)
                    filed_at = _normalize_date_like(row.get("filed"))
                    accession_number = _clean_text(row.get("accn") or row.get("accessionNumber"))
                    fiscal_period = _clean_text(row.get("fp") or row.get("fiscalPeriod"))
                    frame = _clean_text(row.get("frame"))
                    updated_at = _normalize_date_like(row.get("updated") or row.get("updatedAt") or payload_updated_at)
                    as_of = _normalize_date_like(row.get("asOf") or period_end_date or filed_at)

                    records.append(
                        SecEdgarFactRecord(
                            cik=cik,
                            entity_name=entity_name,
                            taxonomy=taxonomy_name,
                            concept=concept_name,
                            label=label,
                            description=description,
                            unit=normalized_unit,
                            value=value,
                            accession_number=accession_number,
                            form=_clean_text(row.get("form")),
                            filed_at=filed_at,
                            fiscal_year=_normalize_int(row.get("fy") or row.get("fiscalYear")),
                            fiscal_period=fiscal_period,
                            fiscal_end_date=fiscal_end_date,
                            period_end_date=period_end_date,
                            frame=frame,
                            as_of=as_of,
                            updated_at=updated_at,
                            source_ref=_build_source_ref(
                                cik=cik,
                                taxonomy=taxonomy_name,
                                concept=concept_name,
                                unit=normalized_unit,
                                accession_number=accession_number,
                                period_end_date=period_end_date,
                                frame=frame,
                            ),
                        )
                    )

    records.sort(key=lambda item: item.source_ref)
    records.sort(key=lambda item: item.frame or "", reverse=True)
    records.sort(key=lambda item: item.accession_number or "", reverse=True)
    records.sort(key=lambda item: item.filed_at or "", reverse=True)
    records.sort(key=lambda item: item.period_end_date or "", reverse=True)
    records.sort(key=lambda item: item.unit)
    records.sort(key=lambda item: item.concept)
    records.sort(key=lambda item: item.taxonomy)

    return SecEdgarCompanyFactsParseResult(records=tuple(records), warnings=tuple(warnings))


__all__ = [
    "SEC_EDGAR_FRESHNESS_EXPECTATION",
    "SEC_EDGAR_PROVIDER_ID",
    "SEC_EDGAR_PROVIDER_NAME",
    "SEC_EDGAR_SOURCE_TIER",
    "SEC_EDGAR_TRUST_LEVEL",
    "SecEdgarCompanyFactsParseResult",
    "SecEdgarFactRecord",
    "SecEdgarParseWarning",
    "parse_companyfacts_payload",
]
