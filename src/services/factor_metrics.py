# -*- coding: utf-8 -*-
"""Offline-only factor metric helpers for fixture and in-memory research."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

from api.v1.schemas.factors import (
    FactorDecayPoint,
    FactorMetricEstimate,
    FactorMetricObservation,
    FactorMetricsReport,
    FactorMetricsResult,
    FactorMetricWindow,
    FactorPeerCorrelation,
)


def coerce_factor_metric_observation(
    value: FactorMetricObservation | Mapping[str, Any],
) -> FactorMetricObservation:
    """Normalize arbitrary payloads into the offline factor-metrics input DTO."""
    if isinstance(value, FactorMetricObservation):
        return value
    return FactorMetricObservation.model_validate(value)


def build_factor_metrics_report(
    observations: Sequence[FactorMetricObservation | Mapping[str, Any]],
) -> FactorMetricsReport:
    """Build a deterministic offline factor-metrics report from in-memory observations."""
    normalized = [coerce_factor_metric_observation(item) for item in observations]
    items_by_factor: dict[str, list[FactorMetricObservation]] = defaultdict(list)
    for item in normalized:
        items_by_factor[item.observation.factor_id].append(item)

    factor_ids = sorted(items_by_factor)
    results: list[FactorMetricsResult] = []
    for factor_id in factor_ids:
        factor_items = sorted(
            items_by_factor[factor_id],
            key=lambda item: (item.observation.as_of, item.observation.symbol),
        )
        horizons = _sorted_horizons(_collect_horizons(factor_items))
        ic = [_build_return_metric(factor_items, horizon, rank=False) for horizon in horizons]
        rank_ic = [_build_return_metric(factor_items, horizon, rank=True) for horizon in horizons]
        decay = _build_decay_points(ic)
        turnover = _build_turnover_metric(factor_items)
        factor_correlation = [
            _build_peer_correlation_metric(factor_items, items_by_factor[peer_factor_id], peer_factor_id)
            for peer_factor_id in factor_ids
            if peer_factor_id != factor_id
        ]
        results.append(
            FactorMetricsResult(
                factor_id=factor_id,
                window=_build_window(factor_items),
                ic=ic,
                rank_ic=rank_ic,
                decay=decay,
                turnover=turnover,
                factor_correlation=factor_correlation,
            )
        )

    return FactorMetricsReport(factors=results)


def _build_window(items: Sequence[FactorMetricObservation]) -> FactorMetricWindow:
    as_ofs = sorted({item.observation.as_of for item in items})
    return FactorMetricWindow(
        as_of_start=as_ofs[0] if as_ofs else None,
        as_of_end=as_ofs[-1] if as_ofs else None,
        as_of_count=len(as_ofs),
        observation_count=len(items),
    )


def _collect_horizons(items: Sequence[FactorMetricObservation]) -> set[str]:
    horizons: set[str] = set()
    for item in items:
        horizons.update(item.forward_returns)
    return horizons


def _sorted_horizons(horizons: Iterable[str]) -> list[str]:
    def horizon_key(value: str) -> tuple[int, str]:
        match = re.match(r"^(\d+)", value.strip().lower())
        number = int(match.group(1)) if match else math.inf
        return number, value

    return sorted(horizons, key=horizon_key)


def _build_return_metric(
    items: Sequence[FactorMetricObservation],
    horizon: str,
    *,
    rank: bool,
) -> FactorMetricEstimate:
    correlations: list[float] = []
    for as_of, date_items in _group_by_as_of(items).items():
        del as_of
        factor_values: list[float] = []
        return_values: list[float] = []
        for item in date_items:
            factor_value = item.observation.value
            forward_return = item.forward_returns.get(horizon)
            if not _is_finite_number(factor_value) or not _is_finite_number(forward_return):
                continue
            factor_values.append(float(factor_value))
            return_values.append(float(forward_return))
        correlation = _correlation(
            _average_ranks(factor_values) if rank else factor_values,
            _average_ranks(return_values) if rank else return_values,
        )
        if correlation is not None:
            correlations.append(correlation)

    if not correlations:
        return FactorMetricEstimate(
            horizon=horizon,
            sample_size=0,
            insufficient_reason="insufficient_cross_sections",
        )

    return FactorMetricEstimate(
        horizon=horizon,
        value=_mean(correlations),
        sample_size=len(correlations),
    )


def _build_decay_points(ic_metrics: Sequence[FactorMetricEstimate]) -> list[FactorDecayPoint]:
    if not ic_metrics:
        return []

    valid_metrics = [item for item in ic_metrics if item.value is not None]
    if len(valid_metrics) < 2:
        return [
            FactorDecayPoint(
                horizon=item.horizon or "",
                ic_value=item.value,
                sample_size=item.sample_size,
                insufficient_reason="requires_multiple_horizons",
            )
            for item in ic_metrics
        ]

    base_metric = valid_metrics[0]
    if base_metric.value is None or math.isclose(base_metric.value, 0.0, abs_tol=1e-12):
        return [
            FactorDecayPoint(
                horizon=item.horizon or "",
                ic_value=item.value,
                sample_size=item.sample_size,
                insufficient_reason="zero_base_ic",
            )
            for item in ic_metrics
        ]

    decay_points: list[FactorDecayPoint] = []
    for item in ic_metrics:
        if item.value is None:
            decay_points.append(
                FactorDecayPoint(
                    horizon=item.horizon or "",
                    sample_size=item.sample_size,
                    insufficient_reason=item.insufficient_reason or "insufficient_cross_sections",
                )
            )
            continue
        decay_points.append(
            FactorDecayPoint(
                horizon=item.horizon or "",
                ic_value=item.value,
                decay_ratio=item.value / base_metric.value,
                sample_size=item.sample_size,
            )
        )
    return decay_points


def _build_turnover_metric(items: Sequence[FactorMetricObservation]) -> FactorMetricEstimate:
    ranked_by_as_of: dict[str, list[str]] = {}
    for as_of, date_items in _group_by_as_of(items).items():
        ranked_symbols = [
            item.observation.symbol
            for item in sorted(
                (item for item in date_items if _is_finite_number(item.observation.value)),
                key=lambda item: (-float(item.observation.value), item.observation.symbol),
            )
        ]
        if ranked_symbols:
            ranked_by_as_of[as_of] = ranked_symbols

    as_ofs = sorted(ranked_by_as_of)
    turnovers: list[float] = []
    for left_as_of, right_as_of in zip(as_ofs, as_ofs[1:]):
        left_symbols = ranked_by_as_of[left_as_of]
        right_symbols = ranked_by_as_of[right_as_of]
        bucket_size = max(1, min(len(left_symbols), len(right_symbols)) // 2)
        if bucket_size <= 0:
            continue
        left_bucket = set(left_symbols[:bucket_size])
        right_bucket = set(right_symbols[:bucket_size])
        turnovers.append(1.0 - (len(left_bucket & right_bucket) / bucket_size))

    if not turnovers:
        return FactorMetricEstimate(
            sample_size=0,
            insufficient_reason="insufficient_turnover_pairs",
        )

    return FactorMetricEstimate(
        value=_mean(turnovers),
        sample_size=len(turnovers),
    )


def _build_peer_correlation_metric(
    factor_items: Sequence[FactorMetricObservation],
    peer_items: Sequence[FactorMetricObservation],
    peer_factor_id: str,
) -> FactorPeerCorrelation:
    factor_by_as_of_symbol = _index_factor_values(factor_items)
    peer_by_as_of_symbol = _index_factor_values(peer_items)
    correlations: list[float] = []
    for as_of in sorted(set(factor_by_as_of_symbol) & set(peer_by_as_of_symbol)):
        factor_symbols = factor_by_as_of_symbol[as_of]
        peer_symbols = peer_by_as_of_symbol[as_of]
        common_symbols = sorted(set(factor_symbols) & set(peer_symbols))
        left_values = [factor_symbols[symbol] for symbol in common_symbols]
        right_values = [peer_symbols[symbol] for symbol in common_symbols]
        correlation = _correlation(left_values, right_values)
        if correlation is not None:
            correlations.append(correlation)

    if not correlations:
        return FactorPeerCorrelation(
            peer_factor_id=peer_factor_id,
            sample_size=0,
            insufficient_reason="insufficient_peer_overlap",
        )

    return FactorPeerCorrelation(
        peer_factor_id=peer_factor_id,
        value=_mean(correlations),
        sample_size=len(correlations),
    )


def _group_by_as_of(
    items: Sequence[FactorMetricObservation],
) -> dict[str, list[FactorMetricObservation]]:
    grouped: dict[str, list[FactorMetricObservation]] = defaultdict(list)
    for item in items:
        grouped[item.observation.as_of].append(item)
    return {as_of: grouped[as_of] for as_of in sorted(grouped)}


def _index_factor_values(
    items: Sequence[FactorMetricObservation],
) -> dict[str, dict[str, float]]:
    indexed: dict[str, dict[str, float]] = defaultdict(dict)
    for item in items:
        if not _is_finite_number(item.observation.value):
            continue
        indexed[item.observation.as_of][item.observation.symbol] = float(item.observation.value)
    return {as_of: indexed[as_of] for as_of in sorted(indexed)}


def _average_ranks(values: Sequence[float]) -> list[float]:
    size = len(values)
    if size == 0:
        return []
    ordered = sorted(enumerate(values), key=lambda item: (item[1], item[0]))
    ranks = [0.0] * size
    index = 0
    while index < size:
        next_index = index + 1
        while next_index < size and ordered[next_index][1] == ordered[index][1]:
            next_index += 1
        average_rank = ((index + 1) + next_index) / 2.0
        for offset in range(index, next_index):
            ranks[ordered[offset][0]] = average_rank
        index = next_index
    return ranks


def _correlation(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = _mean(left)
    right_mean = _mean(right)
    left_var = sum((value - left_mean) ** 2 for value in left)
    right_var = sum((value - right_mean) ** 2 for value in right)
    if math.isclose(left_var, 0.0, abs_tol=1e-12) or math.isclose(right_var, 0.0, abs_tol=1e-12):
        return None
    covariance = sum((lx - left_mean) * (rx - right_mean) for lx, rx in zip(left, right))
    return max(-1.0, min(1.0, covariance / math.sqrt(left_var * right_var)))


def _is_finite_number(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


__all__ = [
    "build_factor_metrics_report",
    "coerce_factor_metric_observation",
]
