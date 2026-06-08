# -*- coding: utf-8 -*-
"""Pure builder for inert Data Coverage Matrix v1 rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from src.services.data_coverage_matrix_contract import (
    DataCoverageMatrixContract,
    DataCoverageValidationResult,
    coerce_data_coverage_matrix_contract,
    validate_data_coverage_matrix_contract,
)
from src.services.data_coverage_surface_registry import (
    DATA_COVERAGE_SURFACE_REGISTRY_BY_SURFACE_FIELD,
    SurfaceRegistryEntry,
)


@dataclass(frozen=True, slots=True)
class DataCoverageMatrixBuildResult:
    registry_entry: SurfaceRegistryEntry
    raw_contract: DataCoverageMatrixContract
    normalized_contract: DataCoverageMatrixContract
    validation: DataCoverageValidationResult

    def to_dict(self) -> dict[str, Any]:
        return self.normalized_contract.to_dict()


def build_data_coverage_matrix_row(
    metadata: Mapping[str, Any] | None = None,
    *,
    registry_entry: SurfaceRegistryEntry | None = None,
    surface_id: str | None = None,
    field_key: str | None = None,
) -> DataCoverageMatrixBuildResult:
    entry = resolve_data_coverage_surface_registry_entry(
        registry_entry=registry_entry,
        surface_id=surface_id,
        field_key=field_key,
    )
    payload = _coerce_metadata(metadata)
    payload.update(_base_payload_for_entry(entry))

    raw_contract = DataCoverageMatrixContract.from_dict(payload)
    validation = validate_data_coverage_matrix_contract(raw_contract)
    normalized_contract = coerce_data_coverage_matrix_contract(payload)
    return DataCoverageMatrixBuildResult(
        registry_entry=entry,
        raw_contract=raw_contract,
        normalized_contract=normalized_contract,
        validation=validation,
    )


def resolve_data_coverage_surface_registry_entry(
    *,
    registry_entry: SurfaceRegistryEntry | None = None,
    surface_id: str | None = None,
    field_key: str | None = None,
) -> SurfaceRegistryEntry:
    if registry_entry is not None:
        return registry_entry

    lookup_key = (_text(surface_id), _text(field_key))
    entry = DATA_COVERAGE_SURFACE_REGISTRY_BY_SURFACE_FIELD.get(lookup_key)
    if entry is None:
        raise LookupError(
            f"Unknown data coverage surface registry entry for surface_id={lookup_key[0]!r} "
            f"field_key={lookup_key[1]!r}."
        )
    return entry


def _base_payload_for_entry(entry: SurfaceRegistryEntry) -> dict[str, Any]:
    return {
        "surfaceId": entry.surface_id,
        "routeId": entry.route_id,
        "audience": entry.audience.value,
        "fieldKey": entry.field_key,
        "evidenceFamily": entry.evidence_family,
    }


def _coerce_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, Mapping):
        return {}
    return dict(metadata)


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text
