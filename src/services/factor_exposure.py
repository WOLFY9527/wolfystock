# -*- coding: utf-8 -*-
"""Offline-only factor exposure helpers for Alpha Factory research."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from api.v1.schemas.factors import FactorObservation, normalize_factor_id


@dataclass(frozen=True)
class FactorExposureWindow:
    as_of_start: str | None = None
    as_of_end: str | None = None
    as_of_count: int = 0
    observation_count: int = 0


@dataclass(frozen=True)
class FactorExposureCoverage:
    total_positions: int = 0
    eligible_positions: int = 0
    invalid_weight_count: int = 0
    zero_weight_count: int = 0
    gross_weight: float = 0.0
    net_weight: float = 0.0


@dataclass(frozen=True)
class FactorExposureSummary:
    factor_id: str
    exposure: float | None
    weighted_exposure: float
    gross_exposure: float
    net_exposure: float
    sample_size: int
    coverage: float
    missing_factor_count: int
    window: FactorExposureWindow
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class FactorExposureReport:
    scope: str
    coverage: FactorExposureCoverage
    factors: tuple[FactorExposureSummary, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class FactorLongShortExposureSummary:
    factor_id: str
    exposure: float | None
    weighted_exposure: float
    gross_exposure: float
    net_exposure: float
    long_exposure: float
    short_exposure: float
    sample_size: int
    coverage: float
    missing_factor_count: int
    window: FactorExposureWindow
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class FactorLongShortExposureReport:
    scope: str
    long_report: FactorExposureReport
    short_report: FactorExposureReport
    factors: tuple[FactorLongShortExposureSummary, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class _NormalizedObservation:
    factor_id: str | None
    symbol: str
    as_of: str
    exposure_value: float | None


def build_factor_exposure_report(
    observations: Sequence[FactorObservation | Mapping[str, Any] | object],
    weights: Sequence[Mapping[str, Any] | object] | Mapping[str, Any],
    *,
    scope: str = "portfolio",
) -> FactorExposureReport:
    """Build deterministic offline factor exposures from weighted symbols."""
    normalized_weights, coverage, coverage_warnings = _normalize_weights(weights)
    observation_index = _index_observations(observations)

    factors: list[FactorExposureSummary] = []
    for factor_id in sorted(observation_index):
        factor_observations = observation_index[factor_id]
        weighted_exposure = 0.0
        gross_exposure = 0.0
        covered_weight = 0.0
        sample_size = 0
        missing_factor_count = 0
        invalid_observation_value = 0
        warning_flags = {
            "missing_factor_observation": False,
            "invalid_observation_value": False,
        }
        for symbol, weight in sorted(normalized_weights.items()):
            observation = factor_observations.get(symbol)
            if observation is None:
                missing_factor_count += 1
                warning_flags["missing_factor_observation"] = True
                continue
            if observation.exposure_value is None:
                invalid_observation_value += 1
                warning_flags["invalid_observation_value"] = True
                continue
            sample_size += 1
            covered_weight += weight
            weighted_exposure += weight * observation.exposure_value
            gross_exposure += weight * abs(observation.exposure_value)

        warnings = tuple(
            key
            for key in ("missing_factor_observation", "invalid_observation_value")
            if warning_flags[key]
        )
        factors.append(
            FactorExposureSummary(
                factor_id=factor_id,
                exposure=(weighted_exposure / covered_weight) if covered_weight > 0 else None,
                weighted_exposure=weighted_exposure,
                gross_exposure=gross_exposure,
                net_exposure=weighted_exposure,
                sample_size=sample_size,
                coverage=(sample_size / len(normalized_weights)) if normalized_weights else 0.0,
                missing_factor_count=missing_factor_count + invalid_observation_value,
                window=_build_window(factor_observations.values()),
                warnings=warnings,
            )
        )

    report_warnings = tuple(
        key for key in ("invalid_weight", "zero_weight") if key in coverage_warnings
    )
    return FactorExposureReport(
        scope=scope,
        coverage=coverage,
        factors=tuple(factors),
        warnings=report_warnings,
    )


def build_long_short_factor_exposure_report(
    observations: Sequence[FactorObservation | Mapping[str, Any] | object],
    *,
    long_weights: Sequence[Mapping[str, Any] | object] | Mapping[str, Any],
    short_weights: Sequence[Mapping[str, Any] | object] | Mapping[str, Any],
    long_scope: str = "long",
    short_scope: str = "short",
) -> FactorLongShortExposureReport:
    """Build additive long/short factor basket summaries from offline inputs."""
    long_report = build_factor_exposure_report(observations, long_weights, scope=long_scope)
    short_report = build_factor_exposure_report(observations, short_weights, scope=short_scope)
    long_by_factor = {item.factor_id: item for item in long_report.factors}
    short_by_factor = {item.factor_id: item for item in short_report.factors}

    factors: list[FactorLongShortExposureSummary] = []
    total_gross_weight = long_report.coverage.gross_weight + short_report.coverage.gross_weight
    total_eligible_positions = long_report.coverage.eligible_positions + short_report.coverage.eligible_positions
    factor_ids = sorted(set(long_by_factor) | set(short_by_factor))
    for factor_id in factor_ids:
        long_summary = long_by_factor.get(factor_id)
        short_summary = short_by_factor.get(factor_id)
        long_exposure = long_summary.weighted_exposure if long_summary is not None else 0.0
        short_exposure = short_summary.weighted_exposure if short_summary is not None else 0.0
        net_exposure = long_exposure - short_exposure
        gross_exposure = abs(long_exposure) + abs(short_exposure)
        sample_size = (long_summary.sample_size if long_summary else 0) + (short_summary.sample_size if short_summary else 0)
        missing_factor_count = (
            (long_summary.missing_factor_count if long_summary else long_report.coverage.eligible_positions)
            + (short_summary.missing_factor_count if short_summary else short_report.coverage.eligible_positions)
        )
        warnings = _merge_warning_tuples(
            long_summary.warnings if long_summary is not None else (),
            short_summary.warnings if short_summary is not None else (),
        )
        factors.append(
            FactorLongShortExposureSummary(
                factor_id=factor_id,
                exposure=(net_exposure / total_gross_weight) if total_gross_weight > 0 else None,
                weighted_exposure=net_exposure,
                gross_exposure=gross_exposure,
                net_exposure=net_exposure,
                long_exposure=long_exposure,
                short_exposure=short_exposure,
                sample_size=sample_size,
                coverage=(sample_size / total_eligible_positions) if total_eligible_positions > 0 else 0.0,
                missing_factor_count=missing_factor_count,
                window=_merge_windows(
                    long_summary.window if long_summary is not None else None,
                    short_summary.window if short_summary is not None else None,
                ),
                warnings=warnings,
            )
        )

    return FactorLongShortExposureReport(
        scope="long_short",
        long_report=long_report,
        short_report=short_report,
        factors=tuple(factors),
        warnings=_merge_warning_tuples(long_report.warnings, short_report.warnings),
    )


def _normalize_weights(
    weights: Sequence[Mapping[str, Any] | object] | Mapping[str, Any],
) -> tuple[dict[str, float], FactorExposureCoverage, tuple[str, ...]]:
    totals: dict[str, float] = {}
    invalid_weight_count = 0
    zero_weight_count = 0
    total_positions = 0

    items: Sequence[Any]
    if isinstance(weights, Mapping):
        items = [{"symbol": symbol, "weight": weight} for symbol, weight in weights.items()]
    else:
        items = list(weights)

    for item in items:
        total_positions += 1
        symbol = _normalize_symbol(_field(item, "symbol"))
        weight = _coerce_finite_number(_field(item, "weight"))
        if not symbol or weight is None or weight < 0:
            invalid_weight_count += 1
            continue
        if math.isclose(weight, 0.0, abs_tol=1e-12):
            zero_weight_count += 1
            continue
        totals[symbol] = totals.get(symbol, 0.0) + weight

    coverage = FactorExposureCoverage(
        total_positions=total_positions,
        eligible_positions=len(totals),
        invalid_weight_count=invalid_weight_count,
        zero_weight_count=zero_weight_count,
        gross_weight=sum(totals.values()),
        net_weight=sum(totals.values()),
    )
    warnings = []
    if invalid_weight_count:
        warnings.append("invalid_weight")
    if zero_weight_count:
        warnings.append("zero_weight")
    return totals, coverage, tuple(warnings)


def _index_observations(
    observations: Sequence[FactorObservation | Mapping[str, Any] | object],
) -> dict[str, dict[str, _NormalizedObservation]]:
    indexed: dict[str, dict[str, _NormalizedObservation]] = {}
    for raw_item in observations:
        item = _normalize_observation(raw_item)
        if not item.factor_id or not item.symbol:
            continue
        factor_entries = indexed.setdefault(item.factor_id, {})
        current = factor_entries.get(item.symbol)
        if current is None or _should_replace(current, item):
            factor_entries[item.symbol] = item
    return {factor_id: indexed[factor_id] for factor_id in sorted(indexed)}


def _normalize_observation(
    value: FactorObservation | Mapping[str, Any] | object,
) -> _NormalizedObservation:
    if isinstance(value, FactorObservation):
        return _NormalizedObservation(
            factor_id=value.factor_id,
            symbol=value.symbol,
            as_of=value.as_of,
            exposure_value=float(value.value),
        )

    if isinstance(value, Mapping):
        row = dict(value)
        observation_raw = row.get("observation", row)
        if isinstance(observation_raw, FactorObservation):
            neutralized_value = _coerce_finite_number(row.get("neutralized_value"))
            exposure_value = neutralized_value if neutralized_value is not None else float(observation_raw.value)
            return _NormalizedObservation(
                factor_id=observation_raw.factor_id,
                symbol=observation_raw.symbol,
                as_of=observation_raw.as_of,
                exposure_value=exposure_value,
            )
        observation = observation_raw if isinstance(observation_raw, Mapping) else {}
        neutralized_value = _coerce_finite_number(row.get("neutralized_value"))
        raw_value = _coerce_finite_number(observation.get("value"))
        return _NormalizedObservation(
            factor_id=_normalize_factor_id(observation.get("factor_id")),
            symbol=_normalize_symbol(observation.get("symbol")),
            as_of=str(observation.get("as_of") or ""),
            exposure_value=neutralized_value if neutralized_value is not None else raw_value,
        )

    neutralized_value = _coerce_finite_number(_field(value, "neutralized_value"))
    raw_value = _coerce_finite_number(_field(value, "original_value"))
    if raw_value is None:
        raw_value = _coerce_finite_number(_field(value, "value"))
    return _NormalizedObservation(
        factor_id=_normalize_factor_id(_field(value, "factor_id")),
        symbol=_normalize_symbol(_field(value, "symbol")),
        as_of=str(_field(value, "as_of") or ""),
        exposure_value=neutralized_value if neutralized_value is not None else raw_value,
    )


def _build_window(items: Sequence[_NormalizedObservation]) -> FactorExposureWindow:
    observations = [item for item in items if item.as_of]
    as_ofs = sorted({item.as_of for item in observations})
    return FactorExposureWindow(
        as_of_start=as_ofs[0] if as_ofs else None,
        as_of_end=as_ofs[-1] if as_ofs else None,
        as_of_count=len(as_ofs),
        observation_count=len(items),
    )


def _merge_windows(
    left: FactorExposureWindow | None,
    right: FactorExposureWindow | None,
) -> FactorExposureWindow:
    items = [item for item in (left, right) if item is not None]
    if not items:
        return FactorExposureWindow()
    as_ofs = sorted(
        {
            value
            for item in items
            for value in (item.as_of_start, item.as_of_end)
            if value
        }
    )
    return FactorExposureWindow(
        as_of_start=as_ofs[0] if as_ofs else None,
        as_of_end=as_ofs[-1] if as_ofs else None,
        as_of_count=max((item.as_of_count for item in items), default=0),
        observation_count=sum(item.observation_count for item in items),
    )


def _should_replace(current: _NormalizedObservation, candidate: _NormalizedObservation) -> bool:
    if candidate.as_of != current.as_of:
        return candidate.as_of > current.as_of
    if current.exposure_value is None and candidate.exposure_value is not None:
        return True
    return False


def _normalize_factor_id(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return normalize_factor_id(text)


def _normalize_symbol(value: Any) -> str:
    return str(value or "").strip().upper()


def _coerce_finite_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _field(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _merge_warning_tuples(*warning_groups: tuple[str, ...]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for group in warning_groups:
        for item in group:
            if item in seen:
                continue
            seen.add(item)
            ordered.append(item)
    return tuple(ordered)


__all__ = [
    "FactorExposureCoverage",
    "FactorExposureReport",
    "FactorExposureSummary",
    "FactorExposureWindow",
    "FactorLongShortExposureReport",
    "FactorLongShortExposureSummary",
    "build_factor_exposure_report",
    "build_long_short_factor_exposure_report",
]
