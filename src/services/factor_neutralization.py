# -*- coding: utf-8 -*-
"""Offline-only factor neutralization helpers for Alpha Factory research."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from api.v1.schemas.factors import FactorObservation, normalize_factor_id


@dataclass(frozen=True)
class FactorNeutralizationWindow:
    as_of_start: str | None = None
    as_of_end: str | None = None
    as_of_count: int = 0
    observation_count: int = 0


@dataclass(frozen=True)
class FactorNeutralizationCoverage:
    total_observations: int = 0
    neutralized_observations: int = 0
    missing_group_metadata: int = 0
    insufficient_group_observations: int = 0
    invalid_observation_values: int = 0


@dataclass(frozen=True)
class FactorNeutralizationGroupCoverage:
    as_of: str
    group_key: str
    sample_size: int
    neutralized_count: int
    insufficient_reason: str | None = None


@dataclass(frozen=True)
class FactorNeutralizedValue:
    factor_id: str
    symbol: str
    as_of: str
    original_value: float | None
    neutralized_value: float | None
    group_key: str | None
    sample_size: int
    insufficient_reason: str | None = None


@dataclass(frozen=True)
class FactorNeutralizationReport:
    factor_id: str | None
    axis: str
    neutralization_method: str
    sample_size: int
    window: FactorNeutralizationWindow
    coverage: FactorNeutralizationCoverage
    group_coverage: tuple[FactorNeutralizationGroupCoverage, ...]
    values: tuple[FactorNeutralizedValue, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class _NormalizedObservation:
    factor_id: str | None
    symbol: str
    as_of: str
    value: float | None
    sector: str | None
    market_cap: float | None


def build_sector_neutralization_report(
    observations: Sequence[FactorObservation | Mapping[str, Any]],
    *,
    min_group_size: int = 2,
) -> FactorNeutralizationReport:
    """Build sector-neutral factor residuals from fixture or in-memory rows."""
    return _build_report(
        observations,
        axis="sector",
        neutralization_method="sector_residual",
        min_group_size=min_group_size,
        bucket_count=None,
    )


def build_market_cap_bucket_neutralization_report(
    observations: Sequence[FactorObservation | Mapping[str, Any]],
    *,
    bucket_count: int = 5,
    min_group_size: int = 2,
) -> FactorNeutralizationReport:
    """Build market-cap-bucket-neutral residuals from fixture or in-memory rows."""
    return _build_report(
        observations,
        axis="market_cap_bucket",
        neutralization_method="market_cap_bucket_residual",
        min_group_size=min_group_size,
        bucket_count=bucket_count,
    )


def _build_report(
    observations: Sequence[FactorObservation | Mapping[str, Any]],
    *,
    axis: str,
    neutralization_method: str,
    min_group_size: int,
    bucket_count: int | None,
) -> FactorNeutralizationReport:
    if min_group_size < 1:
        raise ValueError("min_group_size must be >= 1")
    if bucket_count is not None and bucket_count < 1:
        raise ValueError("bucket_count must be >= 1")

    normalized = [_normalize_observation(item) for item in observations]
    factor_id = next((item.factor_id for item in normalized if item.factor_id), None)
    window = _build_window(normalized)
    grouped_by_as_of: dict[str, list[_NormalizedObservation]] = defaultdict(list)
    for item in normalized:
        grouped_by_as_of[item.as_of].append(item)

    report_values: list[FactorNeutralizedValue] = []
    group_coverage: list[FactorNeutralizationGroupCoverage] = []
    coverage = FactorNeutralizationCoverage(total_observations=len(normalized))
    warning_flags = {
        "missing_group_metadata": False,
        "insufficient_group_size": False,
        "invalid_observation_value": False,
    }

    for as_of in sorted(grouped_by_as_of):
        date_items = sorted(grouped_by_as_of[as_of], key=lambda item: item.symbol)
        group_keys = _resolve_group_keys(date_items, axis=axis, bucket_count=bucket_count)
        valid_values_by_group: dict[str, list[float]] = defaultdict(list)
        groups_seen: set[str] = set()
        for item in date_items:
            group_key = group_keys[item.symbol]
            if group_key is None:
                continue
            groups_seen.add(group_key)
            if _is_finite_number(item.value):
                valid_values_by_group[group_key].append(float(item.value))

        group_sizes = {key: len(valid_values_by_group.get(key, [])) for key in groups_seen}
        group_means = {
            key: (sum(values) / len(values))
            for key, values in valid_values_by_group.items()
            if values
        }
        for group_key in sorted(groups_seen):
            sample_size = group_sizes[group_key]
            group_coverage.append(
                FactorNeutralizationGroupCoverage(
                    as_of=as_of,
                    group_key=group_key,
                    sample_size=sample_size,
                    neutralized_count=sample_size if sample_size >= min_group_size else 0,
                    insufficient_reason=None if sample_size >= min_group_size else "insufficient_group_size",
                )
            )

        for item in date_items:
            group_key = group_keys[item.symbol]
            sample_size = group_sizes.get(group_key or "", 0) if group_key is not None else 0
            if group_key is None:
                coverage = _replace_coverage(
                    coverage,
                    missing_group_metadata=coverage.missing_group_metadata + 1,
                )
                warning_flags["missing_group_metadata"] = True
                report_values.append(
                    FactorNeutralizedValue(
                        factor_id=item.factor_id or "",
                        symbol=item.symbol,
                        as_of=item.as_of,
                        original_value=item.value,
                        neutralized_value=None,
                        group_key=None,
                        sample_size=0,
                        insufficient_reason="missing_group_metadata",
                    )
                )
                continue
            if not _is_finite_number(item.value):
                coverage = _replace_coverage(
                    coverage,
                    invalid_observation_values=coverage.invalid_observation_values + 1,
                )
                warning_flags["invalid_observation_value"] = True
                report_values.append(
                    FactorNeutralizedValue(
                        factor_id=item.factor_id or "",
                        symbol=item.symbol,
                        as_of=item.as_of,
                        original_value=item.value,
                        neutralized_value=None,
                        group_key=group_key,
                        sample_size=sample_size,
                        insufficient_reason="invalid_observation_value",
                    )
                )
                continue
            if sample_size < min_group_size:
                coverage = _replace_coverage(
                    coverage,
                    insufficient_group_observations=coverage.insufficient_group_observations + 1,
                )
                warning_flags["insufficient_group_size"] = True
                report_values.append(
                    FactorNeutralizedValue(
                        factor_id=item.factor_id or "",
                        symbol=item.symbol,
                        as_of=item.as_of,
                        original_value=float(item.value),
                        neutralized_value=None,
                        group_key=group_key,
                        sample_size=sample_size,
                        insufficient_reason="insufficient_group_size",
                    )
                )
                continue
            coverage = _replace_coverage(
                coverage,
                neutralized_observations=coverage.neutralized_observations + 1,
            )
            report_values.append(
                FactorNeutralizedValue(
                    factor_id=item.factor_id or "",
                    symbol=item.symbol,
                    as_of=item.as_of,
                    original_value=float(item.value),
                    neutralized_value=float(item.value) - group_means[group_key],
                    group_key=group_key,
                    sample_size=sample_size,
                )
            )

    warnings = tuple(
        key
        for key in ("missing_group_metadata", "insufficient_group_size", "invalid_observation_value")
        if warning_flags[key]
    )
    return FactorNeutralizationReport(
        factor_id=factor_id,
        axis=axis,
        neutralization_method=neutralization_method,
        sample_size=coverage.neutralized_observations,
        window=window,
        coverage=coverage,
        group_coverage=tuple(group_coverage),
        values=tuple(sorted(report_values, key=lambda item: (item.as_of, item.symbol))),
        warnings=warnings,
    )


def _build_window(items: Sequence[_NormalizedObservation]) -> FactorNeutralizationWindow:
    as_ofs = sorted({item.as_of for item in items if item.as_of})
    return FactorNeutralizationWindow(
        as_of_start=as_ofs[0] if as_ofs else None,
        as_of_end=as_ofs[-1] if as_ofs else None,
        as_of_count=len(as_ofs),
        observation_count=len(items),
    )


def _resolve_group_keys(
    items: Sequence[_NormalizedObservation],
    *,
    axis: str,
    bucket_count: int | None,
) -> dict[str, str | None]:
    if axis == "sector":
        return {item.symbol: item.sector for item in items}
    if axis != "market_cap_bucket":
        raise ValueError(f"unsupported axis: {axis}")
    assert bucket_count is not None

    assignments: dict[str, str | None] = {item.symbol: None for item in items}
    ranked = sorted(
        (item for item in items if _is_finite_number(item.market_cap)),
        key=lambda item: (float(item.market_cap), item.symbol),
    )
    total = len(ranked)
    for index, item in enumerate(ranked):
        bucket_index = min(bucket_count - 1, (index * bucket_count) // total)
        assignments[item.symbol] = f"bucket_{bucket_index + 1}"
    return assignments


def _normalize_observation(value: FactorObservation | Mapping[str, Any]) -> _NormalizedObservation:
    if isinstance(value, FactorObservation):
        return _NormalizedObservation(
            factor_id=value.factor_id,
            symbol=value.symbol,
            as_of=value.as_of,
            value=float(value.value),
            sector=None,
            market_cap=None,
        )

    row = dict(value)
    observation_raw = row.get("observation", row)
    if isinstance(observation_raw, FactorObservation):
        observation = observation_raw
        return _NormalizedObservation(
            factor_id=observation.factor_id,
            symbol=observation.symbol,
            as_of=observation.as_of,
            value=float(observation.value),
            sector=_normalize_text(row.get("sector")),
            market_cap=_coerce_finite_number(row.get("market_cap")),
        )

    observation_mapping = observation_raw if isinstance(observation_raw, Mapping) else {}
    return _NormalizedObservation(
        factor_id=_normalize_factor_id(observation_mapping.get("factor_id")),
        symbol=_normalize_symbol(observation_mapping.get("symbol")),
        as_of=str(observation_mapping.get("as_of") or ""),
        value=_coerce_finite_number(observation_mapping.get("value")),
        sector=_normalize_text(row.get("sector")),
        market_cap=_coerce_finite_number(row.get("market_cap")),
    )


def _normalize_factor_id(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return normalize_factor_id(text)


def _normalize_symbol(value: Any) -> str:
    return str(value or "").strip().upper()


def _normalize_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _coerce_finite_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _is_finite_number(value: Any) -> bool:
    return _coerce_finite_number(value) is not None


def _replace_coverage(
    coverage: FactorNeutralizationCoverage,
    *,
    total_observations: int | None = None,
    neutralized_observations: int | None = None,
    missing_group_metadata: int | None = None,
    insufficient_group_observations: int | None = None,
    invalid_observation_values: int | None = None,
) -> FactorNeutralizationCoverage:
    return FactorNeutralizationCoverage(
        total_observations=coverage.total_observations if total_observations is None else total_observations,
        neutralized_observations=(
            coverage.neutralized_observations
            if neutralized_observations is None
            else neutralized_observations
        ),
        missing_group_metadata=(
            coverage.missing_group_metadata if missing_group_metadata is None else missing_group_metadata
        ),
        insufficient_group_observations=(
            coverage.insufficient_group_observations
            if insufficient_group_observations is None
            else insufficient_group_observations
        ),
        invalid_observation_values=(
            coverage.invalid_observation_values
            if invalid_observation_values is None
            else invalid_observation_values
        ),
    )


__all__ = [
    "FactorNeutralizationCoverage",
    "FactorNeutralizationGroupCoverage",
    "FactorNeutralizationReport",
    "FactorNeutralizationWindow",
    "FactorNeutralizedValue",
    "build_market_cap_bucket_neutralization_report",
    "build_sector_neutralization_report",
]
