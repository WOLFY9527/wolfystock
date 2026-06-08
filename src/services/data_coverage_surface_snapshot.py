# -*- coding: utf-8 -*-
"""Pure surface-level snapshots for validated Data Coverage Matrix rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from src.services.data_coverage_matrix_contract import (
    ConsumerProductStatus,
    DataCoverageMatrixContract,
    coerce_data_coverage_matrix_contract,
    project_consumer_data_coverage,
)


DATA_COVERAGE_SURFACE_SNAPSHOT_VERSION = "data_coverage_surface_snapshot_v1"

_UNAVAILABLE_STATES = frozenset({ConsumerProductStatus.UNAVAILABLE})
_BLOCKED_STATES = frozenset({ConsumerProductStatus.INSUFFICIENT, ConsumerProductStatus.PAUSED})
_LIMITED_STATES = frozenset(
    {
        ConsumerProductStatus.UPDATING,
        ConsumerProductStatus.DELAYED,
        ConsumerProductStatus.PARTIAL,
    }
)
_AGGREGATE_PRIORITY = (
    ConsumerProductStatus.UNAVAILABLE,
    ConsumerProductStatus.INSUFFICIENT,
    ConsumerProductStatus.PAUSED,
    ConsumerProductStatus.UPDATING,
    ConsumerProductStatus.PARTIAL,
    ConsumerProductStatus.DELAYED,
)


@dataclass(frozen=True, slots=True)
class DataCoverageSurfaceSnapshot:
    surface_id: str
    route_id: str
    audience: str
    consumer_state: ConsumerProductStatus
    confidence_posture: ConsumerProductStatus
    as_of: str | None = None
    last_updated: str | None = None
    row_count: int = 0
    available_row_count: int = 0
    limited_row_count: int = 0
    blocked_row_count: int = 0
    unavailable_row_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "snapshotVersion": DATA_COVERAGE_SURFACE_SNAPSHOT_VERSION,
            "surfaceId": self.surface_id,
            "routeId": self.route_id,
            "audience": self.audience,
            "consumerState": self.consumer_state.value,
            "confidencePosture": self.confidence_posture.value,
            "consumerSummary": self.consumer_state.value,
            "rowCount": self.row_count,
            "availableRowCount": self.available_row_count,
            "limitedRowCount": self.limited_row_count,
            "blockedRowCount": self.blocked_row_count,
            "unavailableRowCount": self.unavailable_row_count,
        }
        if self.as_of is not None:
            payload["asOf"] = self.as_of
        if self.last_updated is not None:
            payload["lastUpdated"] = self.last_updated
        return payload


@dataclass(frozen=True, slots=True)
class _SurfaceRowSnapshot:
    contract: DataCoverageMatrixContract
    consumer_state: ConsumerProductStatus
    as_of: str | None
    last_updated: str | None


def build_data_coverage_surface_snapshot(
    rows: Iterable[Mapping[str, Any] | DataCoverageMatrixContract] | None,
) -> DataCoverageSurfaceSnapshot:
    row_snapshots = tuple(_coerce_row_snapshot(row) for row in (rows or ()))
    row_count = len(row_snapshots)
    surface_id = _single_value(row.contract.surface_id for row in row_snapshots)
    route_id = _single_value(row.contract.route_id for row in row_snapshots)
    audience = _single_value(row.contract.audience for row in row_snapshots)
    identifiers_agree = bool(row_count and surface_id and route_id and audience)

    if not identifiers_agree:
        return DataCoverageSurfaceSnapshot(
            surface_id=surface_id,
            route_id=route_id,
            audience=audience,
            consumer_state=ConsumerProductStatus.UNAVAILABLE,
            confidence_posture=ConsumerProductStatus.UNAVAILABLE,
            as_of=_latest_text(row.as_of for row in row_snapshots),
            last_updated=_latest_text(row.last_updated for row in row_snapshots),
            row_count=row_count,
            unavailable_row_count=row_count,
        )

    available_row_count = 0
    limited_row_count = 0
    blocked_row_count = 0
    unavailable_row_count = 0
    states: list[ConsumerProductStatus] = []

    for row in row_snapshots:
        state = row.consumer_state
        states.append(state)
        if state in _UNAVAILABLE_STATES:
            unavailable_row_count += 1
        elif state in _BLOCKED_STATES:
            blocked_row_count += 1
        elif state in _LIMITED_STATES:
            limited_row_count += 1
        else:
            available_row_count += 1

    consumer_state = _aggregate_consumer_state(states)
    return DataCoverageSurfaceSnapshot(
        surface_id=surface_id,
        route_id=route_id,
        audience=audience,
        consumer_state=consumer_state,
        confidence_posture=_confidence_posture_for(consumer_state),
        as_of=_latest_text(row.as_of for row in row_snapshots),
        last_updated=_latest_text(row.last_updated for row in row_snapshots),
        row_count=row_count,
        available_row_count=available_row_count,
        limited_row_count=limited_row_count,
        blocked_row_count=blocked_row_count,
        unavailable_row_count=unavailable_row_count,
    )


def _coerce_row_snapshot(row: Mapping[str, Any] | DataCoverageMatrixContract) -> _SurfaceRowSnapshot:
    payload = _row_payload(row)
    contract_input: Mapping[str, Any] | DataCoverageMatrixContract = payload or row
    contract = coerce_data_coverage_matrix_contract(contract_input)
    projection = project_consumer_data_coverage(contract)
    return _SurfaceRowSnapshot(
        contract=contract,
        consumer_state=projection.status,
        as_of=projection.as_of,
        last_updated=_optional_text(_get(payload, "lastUpdated", "last_updated")),
    )


def _row_payload(row: Any) -> Mapping[str, Any]:
    if isinstance(row, Mapping):
        return row
    to_dict = getattr(row, "to_dict", None)
    if callable(to_dict):
        value = to_dict()
        if isinstance(value, Mapping):
            return value
    return {}


def _aggregate_consumer_state(states: Iterable[ConsumerProductStatus]) -> ConsumerProductStatus:
    state_set = set(states)
    for state in _AGGREGATE_PRIORITY:
        if state in state_set:
            return state
    return ConsumerProductStatus.AVAILABLE


def _confidence_posture_for(state: ConsumerProductStatus) -> ConsumerProductStatus:
    if state is ConsumerProductStatus.AVAILABLE:
        return ConsumerProductStatus.AVAILABLE
    if state in _LIMITED_STATES:
        return ConsumerProductStatus.PARTIAL
    if state in _BLOCKED_STATES:
        return ConsumerProductStatus.INSUFFICIENT
    return ConsumerProductStatus.UNAVAILABLE


def _single_value(values: Iterable[str]) -> str:
    present = {_optional_text(value) for value in values}
    present.discard(None)
    if len(present) == 1:
        return next(iter(present))
    return ""


def _latest_text(values: Iterable[str | None]) -> str | None:
    present = tuple(value for value in (_optional_text(value) for value in values) if value is not None)
    if not present:
        return None
    return max(present)


def _get(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
