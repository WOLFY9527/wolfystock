# -*- coding: utf-8 -*-
"""Consumer-safe data sufficiency gate for backtest outputs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


SUFFICIENCY_STATUSES = frozenset(
    {
        "sufficient",
        "insufficient_history",
        "missing_adjustments",
        "missing_benchmark",
        "missing_factor_inputs",
        "stale_data",
        "provider_missing",
        "entitlement_required",
    }
)
_BLOCKING_STATUSES = frozenset({"insufficient_history", "entitlement_required"})
_ENTITLEMENT_TOKENS = ("entitlement", "unauthorized", "forbidden", "permission", "redisplay")


def assess_backtest_data_sufficiency(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Build a small, sanitized sufficiency payload from existing backtest metadata."""

    source = dict(payload or {})
    data_quality = _mapping(source.get("data_quality"))
    benchmark_summary = _mapping(source.get("benchmark_summary"))
    factor_inputs = _mapping(source.get("factor_inputs") or source.get("factorInputs"))
    professional = _mapping(source.get("professionalReadiness") or source.get("professional_readiness"))
    no_result_reason = _text(source.get("no_result_reason")).lower()
    blocked: list[str] = []
    degraded: list[str] = []

    bar_count = _safe_int(data_quality.get("bar_count"))
    authority_reasons = _text_list(data_quality.get("authority_reason_codes"))
    authority_status = _text(data_quality.get("authority_status")).lower()
    authority_source_type = _text(data_quality.get("authority_source_type")).lower()

    if no_result_reason in {"insufficient_history", "insufficient_data"} or (
        bar_count is not None and bar_count <= 0 and no_result_reason
    ):
        blocked.append("insufficient_history")

    if _has_entitlement_reason(authority_reasons) or _has_entitlement_reason(
        _text_list(data_quality.get("reason_codes"))
    ):
        blocked.append("entitlement_required")
    elif authority_source_type == "missing" or "source_authority_unknown" in authority_reasons:
        degraded.append("provider_missing")

    if _is_stale(data_quality):
        degraded.append("stale_data")

    if _benchmark_missing(benchmark_summary):
        degraded.append("missing_benchmark")

    if _adjustments_missing(data_quality, professional):
        degraded.append("missing_adjustments")

    if _factor_inputs_missing(factor_inputs):
        degraded.append("missing_factor_inputs")

    status = _primary_status(blocked=blocked, degraded=degraded)
    calculation_state = _calculation_state(status=status, blocked=blocked, degraded=degraded)
    return {
        "contract_version": "v1",
        "status": status,
        "calculation_state": calculation_state,
        "availability_state": "available" if calculation_state == "executable" else calculation_state,
        "blocked_reasons": _dedupe(blocked),
        "degraded_reasons": _dedupe(degraded),
        "missing_requirements": _dedupe([*blocked, *degraded]),
        "metric_policy": _metric_policy(calculation_state),
        "consumer_summary": _consumer_summary(status, calculation_state),
        "input_states": {
            "history": _history_state(status=status, bar_count=bar_count),
            "adjustments": "missing" if "missing_adjustments" in degraded else "available",
            "benchmark": "missing" if "missing_benchmark" in degraded else "available",
            "factor_inputs": "missing" if "missing_factor_inputs" in degraded else "not_requested",
            "freshness": "stale" if "stale_data" in degraded else "current_or_unknown",
            "provider": _provider_state(status=status, authority_status=authority_status),
        },
        "consumer_safe": True,
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [_text(item) for item in value if _text(item)]


def _dedupe(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = _text(value)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _has_entitlement_reason(values: Sequence[str]) -> bool:
    joined = " ".join(_text(item).lower() for item in values)
    return any(token in joined for token in _ENTITLEMENT_TOKENS)


def _is_stale(data_quality: Mapping[str, Any]) -> bool:
    values = " ".join(
        _text(data_quality.get(key)).lower()
        for key in ("freshness_status", "freshness", "source", "data_status")
    )
    if "stale" in values:
        return True
    for warning in data_quality.get("warnings") or []:
        warning_payload = _mapping(warning)
        code = _text(warning_payload.get("code") or warning_payload.get("reason")).lower()
        if "stale" in code:
            return True
    return False


def _benchmark_missing(benchmark_summary: Mapping[str, Any]) -> bool:
    if not benchmark_summary:
        return False
    resolved_mode = _text(benchmark_summary.get("resolved_mode")).lower()
    method = _text(benchmark_summary.get("method")).lower()
    requested = resolved_mode not in {"", "none", "same_symbol_buy_and_hold"}
    if not requested and method != "benchmark_security":
        return False
    return bool(benchmark_summary.get("unavailable_reason")) or (
        benchmark_summary.get("return_pct") is None
        and benchmark_summary.get("start_date") is None
        and benchmark_summary.get("end_date") is None
    )


def _adjustments_missing(data_quality: Mapping[str, Any], professional: Mapping[str, Any]) -> bool:
    adjustment_mode = _text(data_quality.get("adjustment_mode") or professional.get("adjusted_data_state")).lower()
    dividends = _text(data_quality.get("dividends_handled")).lower()
    splits = _text(data_quality.get("splits_handled")).lower()
    if adjustment_mode in {
        "adjusted",
        "adjusted_ohlc",
        "adjusted_ohlcv",
        "fully_adjusted",
        "split_dividend_adjusted",
        "total_return_adjusted",
    } and dividends in {"handled", "ready", "true", "yes"} and splits in {"handled", "ready", "true", "yes"}:
        return False
    categories = _mapping(professional.get("categories"))
    corporate = _mapping(categories.get("corporate_actions"))
    adjusted = _mapping(categories.get("adjusted_data"))
    blockers = [*_text_list(corporate.get("blockers")), *_text_list(adjusted.get("blockers"))]
    if blockers:
        return True
    return adjustment_mode in {"", "unknown", "unknown_or_mixed"} or dividends in {"", "unknown"} or splits in {"", "unknown"}


def _factor_inputs_missing(factor_inputs: Mapping[str, Any]) -> bool:
    if not factor_inputs:
        return False
    state = _text(factor_inputs.get("state") or factor_inputs.get("readiness_state")).lower()
    if state in {"missing", "not_available", "blocked", "insufficient"}:
        return True
    return bool(factor_inputs.get("missing_reasons") or factor_inputs.get("missingDataReasons"))


def _primary_status(*, blocked: Sequence[str], degraded: Sequence[str]) -> str:
    for status in (
        "insufficient_history",
        "entitlement_required",
        "provider_missing",
        "stale_data",
        "missing_benchmark",
        "missing_adjustments",
        "missing_factor_inputs",
    ):
        if status in blocked or status in degraded:
            return status
    return "sufficient"


def _calculation_state(*, status: str, blocked: Sequence[str], degraded: Sequence[str]) -> str:
    if status in _BLOCKING_STATUSES or blocked:
        return "not_available"
    if degraded:
        return "degraded"
    return "executable"


def _metric_policy(calculation_state: str) -> str:
    if calculation_state == "not_available":
        return "do_not_emit_performance_metrics"
    if calculation_state == "degraded":
        return "emit_calculation_metrics_with_missing_input_reasons"
    return "emit_calculation_metrics"


def _consumer_summary(status: str, calculation_state: str) -> str:
    if calculation_state == "not_available":
        return "数据不足，暂不形成结论。"
    if calculation_state == "degraded":
        return "计算可执行，但关键输入存在缺口，结果仅供观察。"
    return "数据充分性检查通过，计算结果可作为研究诊断输入。"


def _history_state(*, status: str, bar_count: int | None) -> str:
    if status == "insufficient_history":
        return "insufficient"
    if bar_count is None:
        return "unknown"
    return "available" if bar_count > 0 else "missing"


def _provider_state(*, status: str, authority_status: str) -> str:
    if status == "entitlement_required":
        return "entitlement_required"
    if status == "provider_missing":
        return "missing"
    return authority_status or "unknown"


__all__ = ["SUFFICIENCY_STATUSES", "assess_backtest_data_sufficiency"]
