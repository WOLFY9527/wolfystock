# -*- coding: utf-8 -*-
"""Offline-only factor research report aggregation helpers for Alpha Factory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from api.v1.schemas.factors import (
    FactorDecayPoint,
    FactorMetricEstimate,
    FactorMetricsReport,
    FactorObservation,
    FactorPeerCorrelation,
)
from src.services.factor_exposure import (
    FactorExposureReport,
    FactorLongShortExposureReport,
)
from src.services.factor_neutralization import FactorNeutralizationReport


@dataclass(frozen=True)
class FactorResearchWindow:
    as_of_start: str | None = None
    as_of_end: str | None = None
    as_of_count: int = 0
    observation_count: int = 0


@dataclass(frozen=True)
class FactorResearchCoverageItem:
    factor_id: str
    observation_count: int
    symbol_count: int
    window: FactorResearchWindow


@dataclass(frozen=True)
class FactorResearchMetricsSummary:
    factor_id: str
    window: Any
    ic: tuple[FactorMetricEstimate, ...]
    rank_ic: tuple[FactorMetricEstimate, ...]
    decay: tuple[FactorDecayPoint, ...]
    turnover: FactorMetricEstimate
    factor_correlation: tuple[FactorPeerCorrelation, ...]


@dataclass(frozen=True)
class FactorResearchNeutralizationSummary:
    factor_id: str
    axis: str
    neutralization_method: str
    sample_size: int
    total_observations: int
    neutralized_observations: int
    missing_group_metadata: int
    insufficient_group_observations: int
    invalid_observation_values: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class FactorResearchExposureSummary:
    scope: str
    factor_id: str
    exposure: float | None
    weighted_exposure: float
    gross_exposure: float
    net_exposure: float
    sample_size: int
    coverage: float
    missing_factor_count: int
    window: Any
    warnings: tuple[str, ...]
    long_exposure: float | None = None
    short_exposure: float | None = None


@dataclass(frozen=True)
class FactorResearchMissingDataReason:
    section: str
    reason: str
    factor_id: str | None = None
    context: str | None = None


@dataclass(frozen=True)
class FactorResearchReport:
    window: FactorResearchWindow
    factor_coverage: tuple[FactorResearchCoverageItem, ...]
    metrics_summary: tuple[FactorResearchMetricsSummary, ...]
    neutralization_summary: tuple[FactorResearchNeutralizationSummary, ...]
    exposure_summary: tuple[FactorResearchExposureSummary, ...]
    missing_data_reasons: tuple[FactorResearchMissingDataReason, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class _NormalizedObservation:
    factor_id: str
    symbol: str
    as_of: str


def build_factor_research_report(
    observations: Sequence[FactorObservation | Mapping[str, Any] | object],
    *,
    metrics_report: FactorMetricsReport | Mapping[str, Any] | None = None,
    neutralization_reports: Sequence[FactorNeutralizationReport] | None = None,
    exposure_reports: Sequence[FactorExposureReport | FactorLongShortExposureReport] | None = None,
) -> FactorResearchReport:
    """Aggregate offline factor helper outputs into a deterministic research summary."""
    normalized_observations = [_normalize_observation(item) for item in observations]
    normalized_metrics = _coerce_metrics_report(metrics_report)

    factor_coverage = _build_factor_coverage(normalized_observations)
    missing_data_reasons: list[FactorResearchMissingDataReason] = []

    metrics_summary: tuple[FactorResearchMetricsSummary, ...]
    if normalized_metrics is None or not normalized_metrics.factors:
        metrics_summary = ()
        if normalized_observations:
            missing_data_reasons.append(
                FactorResearchMissingDataReason(
                    section="metrics",
                    reason="missing_metrics_report",
                )
            )
    else:
        metrics_summary = _build_metrics_summary(normalized_metrics, missing_data_reasons)

    neutralization_items = tuple(neutralization_reports or ())
    if not neutralization_items:
        neutralization_summary = ()
        if normalized_observations:
            missing_data_reasons.append(
                FactorResearchMissingDataReason(
                    section="neutralization",
                    reason="missing_neutralization_report",
                )
            )
    else:
        neutralization_summary = _build_neutralization_summary(neutralization_items, missing_data_reasons)

    exposure_items = tuple(exposure_reports or ())
    if not exposure_items:
        exposure_summary = ()
        if normalized_observations:
            missing_data_reasons.append(
                FactorResearchMissingDataReason(
                    section="exposure",
                    reason="missing_exposure_report",
                )
            )
    else:
        exposure_summary = _build_exposure_summary(exposure_items, missing_data_reasons)

    return FactorResearchReport(
        window=_build_window(normalized_observations),
        factor_coverage=factor_coverage,
        metrics_summary=metrics_summary,
        neutralization_summary=neutralization_summary,
        exposure_summary=exposure_summary,
        missing_data_reasons=tuple(missing_data_reasons),
        warnings=_collect_warning_names(missing_data_reasons),
    )


def _build_factor_coverage(
    observations: Sequence[_NormalizedObservation],
) -> tuple[FactorResearchCoverageItem, ...]:
    grouped: dict[str, list[_NormalizedObservation]] = {}
    for item in observations:
        grouped.setdefault(item.factor_id, []).append(item)

    summaries: list[FactorResearchCoverageItem] = []
    for factor_id in sorted(grouped):
        factor_items = sorted(grouped[factor_id], key=lambda item: (item.as_of, item.symbol))
        summaries.append(
            FactorResearchCoverageItem(
                factor_id=factor_id,
                observation_count=len(factor_items),
                symbol_count=len({item.symbol for item in factor_items}),
                window=_build_window(factor_items),
            )
        )
    return tuple(summaries)


def _build_metrics_summary(
    metrics_report: FactorMetricsReport,
    missing_data_reasons: list[FactorResearchMissingDataReason],
) -> tuple[FactorResearchMetricsSummary, ...]:
    summaries: list[FactorResearchMetricsSummary] = []
    for factor_result in sorted(metrics_report.factors, key=lambda item: item.factor_id):
        summaries.append(
            FactorResearchMetricsSummary(
                factor_id=factor_result.factor_id,
                window=factor_result.window,
                ic=tuple(factor_result.ic),
                rank_ic=tuple(factor_result.rank_ic),
                decay=tuple(factor_result.decay),
                turnover=factor_result.turnover,
                factor_correlation=tuple(
                    sorted(factor_result.factor_correlation, key=lambda item: item.peer_factor_id)
                ),
            )
        )
        for estimate in factor_result.ic:
            _append_metric_reason(missing_data_reasons, factor_result.factor_id, estimate.insufficient_reason, f"ic:{estimate.horizon}")
        for estimate in factor_result.rank_ic:
            _append_metric_reason(
                missing_data_reasons,
                factor_result.factor_id,
                estimate.insufficient_reason,
                f"rank_ic:{estimate.horizon}",
            )
        for point in factor_result.decay:
            _append_metric_reason(missing_data_reasons, factor_result.factor_id, point.insufficient_reason, "decay")
        _append_metric_reason(
            missing_data_reasons,
            factor_result.factor_id,
            factor_result.turnover.insufficient_reason,
            "turnover",
        )
        for item in factor_result.factor_correlation:
            _append_metric_reason(
                missing_data_reasons,
                factor_result.factor_id,
                item.insufficient_reason,
                f"correlation:{item.peer_factor_id}",
            )
    return tuple(summaries)


def _build_neutralization_summary(
    reports: Sequence[FactorNeutralizationReport],
    missing_data_reasons: list[FactorResearchMissingDataReason],
) -> tuple[FactorResearchNeutralizationSummary, ...]:
    summaries: list[FactorResearchNeutralizationSummary] = []
    for report in sorted(reports, key=lambda item: (item.factor_id or "", item.axis, item.neutralization_method)):
        factor_id = report.factor_id or ""
        summaries.append(
            FactorResearchNeutralizationSummary(
                factor_id=factor_id,
                axis=report.axis,
                neutralization_method=report.neutralization_method,
                sample_size=report.sample_size,
                total_observations=report.coverage.total_observations,
                neutralized_observations=report.coverage.neutralized_observations,
                missing_group_metadata=report.coverage.missing_group_metadata,
                insufficient_group_observations=report.coverage.insufficient_group_observations,
                invalid_observation_values=report.coverage.invalid_observation_values,
                warnings=tuple(report.warnings),
            )
        )
        for warning in report.warnings:
            missing_data_reasons.append(
                FactorResearchMissingDataReason(
                    section="neutralization",
                    reason=warning,
                    factor_id=factor_id or None,
                    context=report.axis,
                )
            )
    return tuple(summaries)


def _build_exposure_summary(
    reports: Sequence[FactorExposureReport | FactorLongShortExposureReport],
    missing_data_reasons: list[FactorResearchMissingDataReason],
) -> tuple[FactorResearchExposureSummary, ...]:
    summaries: list[FactorResearchExposureSummary] = []
    for report in reports:
        if isinstance(report, FactorLongShortExposureReport):
            for factor in report.factors:
                summaries.append(
                    FactorResearchExposureSummary(
                        scope=report.scope,
                        factor_id=factor.factor_id,
                        exposure=factor.exposure,
                        weighted_exposure=factor.weighted_exposure,
                        gross_exposure=factor.gross_exposure,
                        net_exposure=factor.net_exposure,
                        sample_size=factor.sample_size,
                        coverage=factor.coverage,
                        missing_factor_count=factor.missing_factor_count,
                        window=factor.window,
                        warnings=tuple(factor.warnings),
                        long_exposure=factor.long_exposure,
                        short_exposure=factor.short_exposure,
                    )
                )
                for warning in factor.warnings:
                    missing_data_reasons.append(
                        FactorResearchMissingDataReason(
                            section="exposure",
                            reason=warning,
                            factor_id=factor.factor_id,
                            context=report.scope,
                        )
                    )
            continue

        for factor in report.factors:
            summaries.append(
                FactorResearchExposureSummary(
                    scope=report.scope,
                    factor_id=factor.factor_id,
                    exposure=factor.exposure,
                    weighted_exposure=factor.weighted_exposure,
                    gross_exposure=factor.gross_exposure,
                    net_exposure=factor.net_exposure,
                    sample_size=factor.sample_size,
                    coverage=factor.coverage,
                    missing_factor_count=factor.missing_factor_count,
                    window=factor.window,
                    warnings=tuple(factor.warnings),
                )
            )
            for warning in factor.warnings:
                missing_data_reasons.append(
                    FactorResearchMissingDataReason(
                        section="exposure",
                        reason=warning,
                        factor_id=factor.factor_id,
                        context=report.scope,
                    )
                )

    return tuple(sorted(summaries, key=lambda item: (item.scope, item.factor_id)))


def _append_metric_reason(
    missing_data_reasons: list[FactorResearchMissingDataReason],
    factor_id: str,
    reason: str | None,
    context: str,
) -> None:
    if not reason:
        return
    missing_data_reasons.append(
        FactorResearchMissingDataReason(
            section="metrics",
            reason=reason,
            factor_id=factor_id,
            context=context,
        )
    )


def _build_window(observations: Sequence[_NormalizedObservation]) -> FactorResearchWindow:
    as_ofs = sorted({item.as_of for item in observations if item.as_of})
    return FactorResearchWindow(
        as_of_start=as_ofs[0] if as_ofs else None,
        as_of_end=as_ofs[-1] if as_ofs else None,
        as_of_count=len(as_ofs),
        observation_count=len(observations),
    )


def _collect_warning_names(
    missing_data_reasons: Sequence[FactorResearchMissingDataReason],
) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in missing_data_reasons:
        if item.reason in seen:
            continue
        seen.add(item.reason)
        ordered.append(item.reason)
    return tuple(ordered)


def _coerce_metrics_report(
    value: FactorMetricsReport | Mapping[str, Any] | None,
) -> FactorMetricsReport | None:
    if value is None or isinstance(value, FactorMetricsReport):
        return value
    return FactorMetricsReport.model_validate(value)


def _normalize_observation(value: FactorObservation | Mapping[str, Any] | object) -> _NormalizedObservation:
    if isinstance(value, FactorObservation):
        return _NormalizedObservation(
            factor_id=value.factor_id,
            symbol=value.symbol,
            as_of=value.as_of,
        )

    if isinstance(value, Mapping):
        observation_raw = value.get("observation", value)
    else:
        observation_raw = getattr(value, "observation", value)

    if isinstance(observation_raw, FactorObservation):
        observation = observation_raw
    elif isinstance(observation_raw, Mapping):
        observation = FactorObservation.model_validate(observation_raw)
    else:
        observation = FactorObservation.model_validate(
            {
                "factor_id": _field(observation_raw, "factor_id"),
                "symbol": _field(observation_raw, "symbol"),
                "value": _field(observation_raw, "value"),
                "source_name": _field(observation_raw, "source_name"),
                "source_type": _field(observation_raw, "source_type"),
                "as_of": _field(observation_raw, "as_of"),
                "observed_at": _field(observation_raw, "observed_at"),
                "freshness_status": _field(observation_raw, "freshness_status"),
                "confidence": _field(observation_raw, "confidence"),
                "is_fallback": _field(observation_raw, "is_fallback"),
                "is_stale": _field(observation_raw, "is_stale"),
                "is_partial": _field(observation_raw, "is_partial"),
                "percentile": _field(observation_raw, "percentile"),
                "z_score": _field(observation_raw, "z_score"),
                "basis": _field(observation_raw, "basis"),
                "evidences": _field(observation_raw, "evidences"),
            }
        )

    return _NormalizedObservation(
        factor_id=observation.factor_id,
        symbol=observation.symbol,
        as_of=observation.as_of,
    )


def _field(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


__all__ = [
    "FactorResearchCoverageItem",
    "FactorResearchExposureSummary",
    "FactorResearchMetricsSummary",
    "FactorResearchMissingDataReason",
    "FactorResearchNeutralizationSummary",
    "FactorResearchReport",
    "FactorResearchWindow",
    "build_factor_research_report",
]
