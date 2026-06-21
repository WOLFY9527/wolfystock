# -*- coding: utf-8 -*-
"""Offline-only factor research report aggregation helpers for Alpha Factory."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
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
    build_factor_exposure_report,
    build_long_short_factor_exposure_report,
)
from src.services.factor_metrics import build_factor_metrics_report
from src.services.factor_neutralization import FactorNeutralizationReport
from src.services.factor_neutralization import (
    build_market_cap_bucket_neutralization_report,
    build_sector_neutralization_report,
)
from src.services.factor_registry import get_factor_definition


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


def build_factor_research_report_pilot(
    observations: Sequence[FactorObservation | Mapping[str, Any] | object] | None,
    *,
    metric_observations: Sequence[Mapping[str, Any] | object] | None = None,
    portfolio_weights: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None = None,
    long_weights: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None = None,
    short_weights: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None = None,
    neutralization_axes: Sequence[str] | None = None,
    min_group_size: int = 2,
    market_cap_bucket_count: int = 5,
) -> dict[str, Any]:
    """Build the DATA-040 supplied-input factor research report pilot."""
    normalized_observations = list(observations or ())
    normalized_metric_observations = list(metric_observations or ())
    extra_missing_reasons: list[FactorResearchMissingDataReason] = []

    metrics_report = None
    if normalized_metric_observations:
        metrics_report = build_factor_metrics_report(normalized_metric_observations)
        extra_missing_reasons.extend(_missing_forward_return_reasons(normalized_metric_observations))

    neutralization_reports = _build_pilot_neutralization_reports(
        normalized_observations,
        axes=neutralization_axes or (),
        min_group_size=min_group_size,
        market_cap_bucket_count=market_cap_bucket_count,
        missing_data_reasons=extra_missing_reasons,
    )
    exposure_reports = _build_pilot_exposure_reports(
        normalized_observations,
        portfolio_weights=portfolio_weights,
        long_weights=long_weights,
        short_weights=short_weights,
        missing_data_reasons=extra_missing_reasons,
    )

    report = build_factor_research_report(
        normalized_observations,
        metrics_report=metrics_report,
        neutralization_reports=neutralization_reports or None,
        exposure_reports=exposure_reports or None,
    )
    report_payload = _to_plain(report)
    missing_data_reasons = _dedupe_missing_reasons(
        [
            *report.missing_data_reasons,
            *extra_missing_reasons,
        ]
    )
    report_payload["missing_data_reasons"] = [_to_plain(item) for item in missing_data_reasons]

    warnings = _collect_warning_names(missing_data_reasons)
    report_payload["warnings"] = list(warnings)
    factor_ids = _collect_report_factor_ids(
        normalized_observations,
        normalized_metric_observations,
        report_payload,
    )
    input_shape = _build_pilot_input_shape(
        observations=normalized_observations,
        metric_observations=normalized_metric_observations,
        portfolio_weights=portfolio_weights,
        long_weights=long_weights,
        short_weights=short_weights,
        neutralization_axes=neutralization_axes or (),
        min_group_size=min_group_size,
        market_cap_bucket_count=market_cap_bucket_count,
    )

    return {
        "status": _resolve_pilot_status(
            observation_count=input_shape["observation_count"],
            missing_data_reasons=missing_data_reasons,
        ),
        "boundary": _pilot_boundary(),
        "factor_metadata": _build_factor_metadata(factor_ids),
        "input_shape": input_shape,
        "report": report_payload,
        "missing_data_reasons": [_to_plain(item) for item in missing_data_reasons],
        "warnings": list(warnings),
    }


def _build_pilot_neutralization_reports(
    observations: Sequence[FactorObservation | Mapping[str, Any] | object],
    *,
    axes: Sequence[str],
    min_group_size: int,
    market_cap_bucket_count: int,
    missing_data_reasons: list[FactorResearchMissingDataReason],
) -> list[FactorNeutralizationReport]:
    reports: list[FactorNeutralizationReport] = []
    normalized_axes = _normalize_axes(axes)
    if not normalized_axes:
        return reports

    factor_ids = _factor_ids_from_observations(observations)
    for axis in normalized_axes:
        if axis not in {"sector", "market_cap_bucket"}:
            missing_data_reasons.append(
                FactorResearchMissingDataReason(
                    section="neutralization",
                    reason="unsupported_neutralization_axis",
                    context=axis,
                )
            )
            continue
        for factor_id in factor_ids:
            factor_observations = [
                item
                for item in observations
                if _observation_factor_id(item) == factor_id
            ]
            if not factor_observations:
                continue
            if axis == "sector":
                reports.append(
                    build_sector_neutralization_report(
                        factor_observations,
                        min_group_size=min_group_size,
                    )
                )
            else:
                reports.append(
                    build_market_cap_bucket_neutralization_report(
                        factor_observations,
                        bucket_count=market_cap_bucket_count,
                        min_group_size=min_group_size,
                    )
                )
    return reports


def _build_pilot_exposure_reports(
    observations: Sequence[FactorObservation | Mapping[str, Any] | object],
    *,
    portfolio_weights: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None,
    long_weights: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None,
    short_weights: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None,
    missing_data_reasons: list[FactorResearchMissingDataReason],
) -> list[FactorExposureReport | FactorLongShortExposureReport]:
    reports: list[FactorExposureReport | FactorLongShortExposureReport] = []
    if portfolio_weights is not None:
        reports.append(
            build_factor_exposure_report(
                observations,
                portfolio_weights,
                scope="portfolio",
            )
        )

    if long_weights is None and short_weights is None:
        return reports
    if long_weights is None or short_weights is None:
        missing_data_reasons.append(
            FactorResearchMissingDataReason(
                section="exposure",
                reason="incomplete_long_short_weights",
                context="long_short",
            )
        )
        return reports

    reports.append(
        build_long_short_factor_exposure_report(
            observations,
            long_weights=long_weights,
            short_weights=short_weights,
        )
    )
    return reports


def _missing_forward_return_reasons(
    metric_observations: Sequence[Mapping[str, Any] | object],
) -> list[FactorResearchMissingDataReason]:
    factor_ids = _factor_ids_from_observations(metric_observations)
    factors_with_returns: set[str] = set()
    for item in metric_observations:
        factor_id = _observation_factor_id(item)
        if not factor_id:
            continue
        forward_returns = _metric_forward_returns(item)
        if any(_is_finite_number(value) for value in forward_returns.values()):
            factors_with_returns.add(factor_id)

    return [
        FactorResearchMissingDataReason(
            section="metrics",
            reason="missing_forward_returns",
            factor_id=factor_id,
        )
        for factor_id in factor_ids
        if factor_id not in factors_with_returns
    ]


def _build_factor_metadata(factor_ids: Sequence[str]) -> list[dict[str, Any]]:
    metadata: list[dict[str, Any]] = []
    for factor_id in factor_ids:
        definition = get_factor_definition(factor_id)
        if definition is None:
            metadata.append(
                {
                    "factor_id": factor_id,
                    "registry_state": "not_registered",
                }
            )
            continue
        payload = definition.model_dump(mode="json")
        payload["registry_state"] = "registered"
        metadata.append(payload)
    return metadata


def _build_pilot_input_shape(
    *,
    observations: Sequence[FactorObservation | Mapping[str, Any] | object],
    metric_observations: Sequence[Mapping[str, Any] | object],
    portfolio_weights: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None,
    long_weights: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None,
    short_weights: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None,
    neutralization_axes: Sequence[str],
    min_group_size: int,
    market_cap_bucket_count: int,
) -> dict[str, Any]:
    observation_factor_ids = _factor_ids_from_observations(observations)
    metric_factor_ids = _factor_ids_from_observations(metric_observations)
    symbols = sorted(
        {
            symbol
            for item in [*observations, *metric_observations]
            if (symbol := _observation_symbol(item))
        }
    )
    as_ofs = sorted(
        {
            as_of
            for item in [*observations, *metric_observations]
            if (as_of := _observation_as_of(item))
        }
    )
    horizons = sorted(
        {
            horizon
            for item in metric_observations
            for horizon, value in _metric_forward_returns(item).items()
            if _is_finite_number(value)
        }
    )
    shape = {
        "observation_count": len(observations),
        "metric_observation_count": len(metric_observations),
        "forward_return_observation_count": sum(
            1
            for item in metric_observations
            if any(_is_finite_number(value) for value in _metric_forward_returns(item).values())
        ),
        "factor_count": len(sorted({*observation_factor_ids, *metric_factor_ids})),
        "factor_ids": sorted({*observation_factor_ids, *metric_factor_ids}),
        "symbol_count": len(symbols),
        "symbols": symbols,
        "as_of_start": as_ofs[0] if as_ofs else None,
        "as_of_end": as_ofs[-1] if as_ofs else None,
        "as_of_count": len(as_ofs),
        "forward_return_horizons": horizons,
        "portfolio_weight_count": _weight_count(portfolio_weights),
        "long_weight_count": _weight_count(long_weights),
        "short_weight_count": _weight_count(short_weights),
        "neutralization_axes": _normalize_axes(neutralization_axes),
        "min_group_size": min_group_size,
        "market_cap_bucket_count": market_cap_bucket_count,
        "hash_algorithm": "sha256",
    }
    shape["input_content_hash"] = _hash_payload(
        {
            "observations": _to_plain(observations),
            "metric_observations": _to_plain(metric_observations),
            "portfolio_weights": _to_plain(portfolio_weights),
            "long_weights": _to_plain(long_weights),
            "short_weights": _to_plain(short_weights),
            "neutralization_axes": shape["neutralization_axes"],
            "min_group_size": min_group_size,
            "market_cap_bucket_count": market_cap_bucket_count,
        }
    )
    return shape


def _pilot_boundary() -> dict[str, Any]:
    return {
        "purpose": "diagnostic factor report",
        "research_only": True,
        "diagnostic_only": True,
        "supplied_observations_only": True,
        "portfolio_optimizer": False,
        "professional_readiness_claimed": False,
        "forward_returns_required_for_performance": True,
        "external_data_hydration_executed": False,
        "live_quote_hydration_executed": False,
        "forward_returns_computed": False,
    }


def _resolve_pilot_status(
    *,
    observation_count: int,
    missing_data_reasons: Sequence[FactorResearchMissingDataReason],
) -> str:
    if observation_count == 0:
        return "blocked"
    if missing_data_reasons:
        return "partial"
    return "ready"


def _collect_report_factor_ids(
    observations: Sequence[FactorObservation | Mapping[str, Any] | object],
    metric_observations: Sequence[Mapping[str, Any] | object],
    report_payload: Mapping[str, Any],
) -> list[str]:
    factor_ids = {
        *_factor_ids_from_observations(observations),
        *_factor_ids_from_observations(metric_observations),
    }
    for section in ("factor_coverage", "metrics_summary", "neutralization_summary", "exposure_summary"):
        for item in report_payload.get(section, []) or []:
            factor_id = item.get("factor_id") if isinstance(item, Mapping) else None
            if factor_id:
                factor_ids.add(str(factor_id))
    return sorted(factor_ids)


def _dedupe_missing_reasons(
    reasons: Sequence[FactorResearchMissingDataReason],
) -> tuple[FactorResearchMissingDataReason, ...]:
    deduped: list[FactorResearchMissingDataReason] = []
    seen: set[tuple[str | None, str | None, str | None, str | None]] = set()
    for item in reasons:
        key = (item.section, item.reason, item.factor_id, item.context)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return tuple(deduped)


def _factor_ids_from_observations(
    observations: Sequence[FactorObservation | Mapping[str, Any] | object],
) -> list[str]:
    return sorted(
        {
            factor_id
            for item in observations
            if (factor_id := _observation_factor_id(item))
        }
    )


def _observation_factor_id(value: FactorObservation | Mapping[str, Any] | object) -> str | None:
    try:
        return _normalize_observation(value).factor_id
    except Exception:
        return None


def _observation_symbol(value: FactorObservation | Mapping[str, Any] | object) -> str | None:
    try:
        return _normalize_observation(value).symbol
    except Exception:
        return None


def _observation_as_of(value: FactorObservation | Mapping[str, Any] | object) -> str | None:
    try:
        return _normalize_observation(value).as_of
    except Exception:
        return None


def _metric_forward_returns(value: Mapping[str, Any] | object) -> Mapping[str, Any]:
    raw = _field(value, "forward_returns")
    if raw is None:
        raw = _field(value, "forwardReturns")
    return raw if isinstance(raw, Mapping) else {}


def _normalize_axes(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip().lower()
        if normalized == "market_cap":
            normalized = "market_cap_bucket"
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _weight_count(value: Sequence[Mapping[str, Any] | object] | Mapping[str, Any] | None) -> int:
    if value is None:
        return 0
    if isinstance(value, Mapping):
        return len(value)
    return len(list(value))


def _is_finite_number(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    return numeric == numeric and numeric not in {float("inf"), float("-inf")}


def _hash_payload(value: Any) -> str:
    payload = json.dumps(_to_plain(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _to_plain(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _to_plain(getattr(value, field.name))
            for field in fields(value)
        }
    if hasattr(value, "model_dump"):
        try:
            return _to_plain(value.model_dump(mode="json"))
        except TypeError:
            return _to_plain(value.model_dump())
    if isinstance(value, Mapping):
        return {str(key): _to_plain(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_to_plain(item) for item in value]
    if isinstance(value, list):
        return [_to_plain(item) for item in value]
    return value


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
    "build_factor_research_report_pilot",
]
