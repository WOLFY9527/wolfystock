# -*- coding: utf-8 -*-
"""Pure batch builder for inert Data Coverage Matrix v1 rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Iterable, Mapping

from src.services.data_coverage_matrix_builder import build_data_coverage_matrix_row


DATA_COVERAGE_MATRIX_BATCH_GUARD_POSTURE: Final[dict[str, bool]] = {
    "diagnosticOnly": True,
    "providerRuntimeCalled": False,
    "networkCallsEnabled": False,
    "marketCacheMutation": False,
}


@dataclass(frozen=True, slots=True)
class DataCoverageMatrixBatchRowError:
    row_index: int
    surface_id: str
    field_key: str
    error_type: str
    codes: tuple[str, ...]
    messages: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rowIndex": self.row_index,
            "surfaceId": self.surface_id,
            "fieldKey": self.field_key,
            "errorType": self.error_type,
            "codes": list(self.codes),
            "messages": list(self.messages),
        }


@dataclass(frozen=True, slots=True)
class DataCoverageMatrixBatchResult:
    rows: tuple[dict[str, Any], ...]
    errors: tuple[DataCoverageMatrixBatchRowError, ...]
    input_count: int
    valid_row_count: int

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def invalid_row_count(self) -> int:
        return len(self.errors)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows": [dict(row) for row in self.rows],
            "errors": [error.to_dict() for error in self.errors],
            "rowCounts": {
                "input": self.input_count,
                "built": self.row_count,
                "valid": self.valid_row_count,
                "invalid": self.invalid_row_count,
                "errors": self.error_count,
            },
            "guardPosture": dict(DATA_COVERAGE_MATRIX_BATCH_GUARD_POSTURE),
        }


class DataCoverageMatrixBatchBuildError(ValueError):
    def __init__(self, result: DataCoverageMatrixBatchResult) -> None:
        super().__init__(f"Data Coverage Matrix batch has {result.error_count} row error(s).")
        self.result = result


def build_data_coverage_matrix_batch(
    row_metadata: Iterable[Mapping[str, Any]] | None,
    *,
    raise_on_error: bool = False,
) -> DataCoverageMatrixBatchResult:
    input_rows = tuple(row_metadata or ())
    rows: list[dict[str, Any]] = []
    errors: list[DataCoverageMatrixBatchRowError] = []
    valid_row_count = 0

    for index, row in enumerate(input_rows):
        metadata = _coerce_metadata(row)
        surface_id = _text(_get(metadata, "surfaceId", "surface_id"))
        field_key = _text(_get(metadata, "fieldKey", "field_key"))

        try:
            build_result = build_data_coverage_matrix_row(
                metadata,
                surface_id=surface_id,
                field_key=field_key,
            )
        except LookupError as exc:
            errors.append(
                DataCoverageMatrixBatchRowError(
                    row_index=index,
                    surface_id=surface_id,
                    field_key=field_key,
                    error_type="lookup_error",
                    codes=("unknown_surface_field",),
                    messages=(str(exc),),
                )
            )
            continue

        row_payload = build_result.to_dict()
        rows.append(row_payload)

        if build_result.validation.is_valid:
            valid_row_count += 1
            continue

        errors.append(
            DataCoverageMatrixBatchRowError(
                row_index=index,
                surface_id=row_payload["surfaceId"],
                field_key=row_payload["fieldKey"],
                error_type="validation_error",
                codes=tuple(issue.code for issue in build_result.validation.issues),
                messages=tuple(issue.message for issue in build_result.validation.issues),
            )
        )

    result = DataCoverageMatrixBatchResult(
        rows=tuple(rows),
        errors=tuple(errors),
        input_count=len(input_rows),
        valid_row_count=valid_row_count,
    )
    if raise_on_error and result.errors:
        raise DataCoverageMatrixBatchBuildError(result)
    return result


def _coerce_metadata(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _get(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
