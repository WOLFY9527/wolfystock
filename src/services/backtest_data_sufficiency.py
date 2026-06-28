# -*- coding: utf-8 -*-
"""Consumer-safe data sufficiency gate for backtest outputs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from src.services.historical_ohlcv_readiness import (
    BACKTEST_HISTORICAL_OHLCV_READINESS_CONTRACT_VERSION,
    build_backtest_historical_ohlcv_readiness,
)


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
_BLOCKING_STATUSES = frozenset({"insufficient_history", "missing_benchmark", "provider_missing", "entitlement_required"})
_ENTITLEMENT_TOKENS = ("entitlement", "unauthorized", "forbidden", "permission", "redisplay")
_GENERIC_OHLCV_READINESS_KEYS = frozenset(
    {
        "contractVersion",
        "symbol",
        "market",
        "timeframe",
        "requestedRange",
        "lookbackBars",
        "requiredBars",
        "usableBars",
        "missingBars",
        "usableRange",
        "freshnessState",
        "adjustmentState",
        "benchmarkState",
        "benchmarkSymbol",
        "benchmarkUsableBars",
        "benchmarkMissingBars",
        "benchmarkUsableRange",
        "providerState",
        "overallState",
        "missingRequirements",
        "consumerSafe",
    }
)
_SAFE_OHLCV_READINESS_KEYS = frozenset(
    {
        "contractVersion",
        "status",
        "executable",
        "requestedSymbol",
        "requestedMarket",
        "requestedDateRange",
        "requestedRange",
        "usableRange",
        "requiredBarCount",
        "availableBarCount",
        "symbolBarsAvailable",
        "benchmarkBarsAvailable",
        "missingDateCoverage",
        "adjustedDataRequirement",
        "benchmarkReadiness",
        "historicalOhlcvRuntimeStatus",
        "operatorNextAction",
        "nextOperatorAction",
        "consumerSafeMessage",
        "blockedExecutionReason",
        "missingDataClasses",
        "missingDataFamilies",
        "sourceReadiness",
        "symbol",
        "market",
        "timeframe",
        "requestedRange",
        "lookbackBars",
        "requiredBars",
        "usableBars",
        "missingBars",
        "freshnessState",
        "adjustmentState",
        "benchmarkState",
        "providerState",
        "overallState",
        "missingRequirements",
        "consumerSafe",
    }
)


def assess_backtest_data_sufficiency(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Build a small, sanitized sufficiency payload from existing backtest metadata."""

    source = dict(payload or {})
    data_quality = _mapping(source.get("data_quality"))
    benchmark_summary = _mapping(source.get("benchmark_summary"))
    factor_inputs = _mapping(source.get("factor_inputs") or source.get("factorInputs"))
    professional = _mapping(source.get("professionalReadiness") or source.get("professional_readiness"))
    ohlcv_readiness = _sanitize_ohlcv_readiness(
        _mapping(
            source.get("historicalOhlcvReadiness")
            or source.get("historical_ohlcv_readiness")
            or source.get("ohlcv_readiness")
            or data_quality.get("historicalOhlcvReadiness")
            or data_quality.get("historical_ohlcv_readiness")
            or data_quality.get("ohlcv_readiness")
        )
    )
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

    _apply_ohlcv_readiness(
        ohlcv_readiness,
        blocked=blocked,
        degraded=degraded,
    )

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
    result = {
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
    if ohlcv_readiness:
        result["ohlcv_readiness"] = ohlcv_readiness
    return result


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


def _sanitize_ohlcv_readiness(readiness: Mapping[str, Any]) -> dict[str, Any]:
    if not readiness:
        return {}
    sanitized = {
        key: value
        for key, value in readiness.items()
        if key in _SAFE_OHLCV_READINESS_KEYS
    }
    if not sanitized:
        return {}
    sanitized["missingRequirements"] = _dedupe(_text_list(sanitized.get("missingRequirements")))
    for key in ("requiredBars", "usableBars", "missingBars", "lookbackBars", "requiredBarCount", "availableBarCount"):
        if key in sanitized:
            sanitized[key] = _safe_int(sanitized.get(key))
    for key in ("symbolBarsAvailable", "benchmarkBarsAvailable", "benchmarkUsableBars", "benchmarkMissingBars"):
        if key in sanitized:
            sanitized[key] = _safe_int(sanitized.get(key))
    if isinstance(sanitized.get("sourceReadiness"), Mapping):
        sanitized["sourceReadiness"] = _sanitize_source_readiness(sanitized.get("sourceReadiness"))
    sanitized["consumerSafe"] = True
    if (
        sanitized.get("contractVersion") == BACKTEST_HISTORICAL_OHLCV_READINESS_CONTRACT_VERSION
        or "requestedDateRange" in sanitized
        or "requiredBarCount" in sanitized
    ):
        return sanitized
    projection = build_backtest_historical_ohlcv_readiness(sanitized)
    for key in _GENERIC_OHLCV_READINESS_KEYS:
        if key in sanitized and key not in projection:
            projection[key] = sanitized[key]
    projection["consumerSafe"] = True
    return projection


def _sanitize_source_readiness(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    sanitized = {
        key: nested_value
        for key, nested_value in value.items()
        if key in _GENERIC_OHLCV_READINESS_KEYS
    }
    sanitized["missingRequirements"] = _dedupe(_text_list(sanitized.get("missingRequirements")))
    for key in ("requiredBars", "usableBars", "missingBars", "lookbackBars"):
        if key in sanitized:
            sanitized[key] = _safe_int(sanitized.get(key))
    sanitized["consumerSafe"] = True
    return sanitized


def _apply_ohlcv_readiness(
    readiness: Mapping[str, Any],
    *,
    blocked: list[str],
    degraded: list[str],
) -> None:
    if not readiness:
        return
    provider_state = _text(readiness.get("providerState")).lower()
    overall_state = _text(readiness.get("overallState")).lower()
    backtest_status = _text(readiness.get("status")).lower()
    runtime_status = _text(readiness.get("historicalOhlcvRuntimeStatus")).lower()
    blocked_execution_reason = _text(readiness.get("blockedExecutionReason")).lower()
    freshness_state = _text(readiness.get("freshnessState")).lower()
    adjustment_state = _text(readiness.get("adjustmentState")).lower()
    benchmark_state = _text(readiness.get("benchmarkState")).lower()
    missing_bars = _safe_int(readiness.get("missingBars")) or 0
    missing_requirements = _text_list(readiness.get("missingRequirements"))
    missing_data_classes = _text_list(readiness.get("missingDataClasses"))
    if isinstance(readiness.get("missingDateCoverage"), Mapping):
        missing_bars = max(missing_bars, _safe_int(readiness["missingDateCoverage"].get("missingBarCount")) or 0)
    if isinstance(readiness.get("adjustedDataRequirement"), Mapping):
        adjustment_state = adjustment_state or _text(readiness["adjustedDataRequirement"].get("state")).lower()
    if isinstance(readiness.get("benchmarkReadiness"), Mapping):
        benchmark_state = benchmark_state or _text(readiness["benchmarkReadiness"].get("status")).lower()

    if (
        provider_state == "provider_missing"
        or backtest_status == "not_configured"
        or runtime_status == "not_configured"
        or (runtime_status == "missing" and "historical_ohlcv" in missing_data_classes)
        or (backtest_status == "missing" and "historical_ohlcv" in missing_data_classes)
    ):
        blocked.append("provider_missing")
    elif provider_state == "entitlement_required":
        blocked.append("entitlement_required")
    elif provider_state in {"provider_unavailable", "not_available", "unavailable"} or backtest_status == "unavailable" or runtime_status == "unavailable":
        degraded.append("provider_missing")

    benchmark_coverage_blocked = (
        backtest_status == "insufficient_coverage"
        and "benchmark_ohlcv" in missing_data_classes
        and "symbol_ohlcv" not in missing_data_classes
    )
    if benchmark_coverage_blocked:
        blocked.append("missing_benchmark")
    elif missing_bars > 0 or "insufficient_history" in missing_requirements or backtest_status == "insufficient_coverage":
        blocked.append("insufficient_history")
    if freshness_state == "stale" or "stale_data" in missing_requirements or backtest_status == "stale" or runtime_status == "stale":
        degraded.append("stale_data")
    if adjustment_state == "missing" or "missing_adjustments" in missing_requirements:
        degraded.append("missing_adjustments")
    if benchmark_state in {"missing", "insufficient_coverage"} or "missing_benchmark" in missing_requirements:
        blocked.append("missing_benchmark")
    if "missing_factor_inputs" in missing_requirements:
        degraded.append("missing_factor_inputs")
    if (
        blocked_execution_reason.startswith("historical_ohlcv_")
        and "historical_ohlcv" in missing_data_classes
        and not blocked
    ):
        degraded.append("provider_missing")
    if overall_state == "blocked" and not any(
        item in blocked
        for item in ("provider_missing", "entitlement_required", "insufficient_history")
    ):
        degraded.append("provider_missing")


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
        "provider_missing",
        "entitlement_required",
        "insufficient_history",
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
    if status == "provider_missing":
        return "missing"
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
