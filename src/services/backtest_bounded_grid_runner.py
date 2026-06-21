# -*- coding: utf-8 -*-
"""Pure bounded runner for diagnostic backtest parameter-grid bundles."""

from __future__ import annotations

import copy
import time
from datetime import date
from typing import Any, Mapping, Sequence

from src.core.rule_backtest_engine import ParsedStrategy, RuleBacktestEngine
from src.services.backtest_parameter_stability import aggregate_parameter_stability_results

BOUNDED_GRID_RUNNER_CONTRACT_KIND = "backtest_bounded_parameter_grid_diagnostic_result"
BOUNDED_GRID_RUNNER_CONTRACT_VERSION = "v1"
DEFAULT_MAX_GRID_COMBINATIONS = 10
DEFAULT_OVERFLOW_POLICY = "reject"
SAFE_PARAMETER_PATH_PREFIXES = ("strategy_spec.signal.", "strategy_spec.risk.")
_DESCRIPTOR_FLAGS = ("optimizer_executed", "winner_promotion", "decision_grade")
_FORBIDDEN_REQUEST_IDENTITY_FIELDS = ("external_run_id", "request_id", "run_id", "single_run_id")


def run_bounded_parameter_grid_diagnostic(
    *,
    parameter_grid_request_bundle: Mapping[str, Any] | None = None,
    parameter_stability_plan: Mapping[str, Any] | None = None,
    parameter_grid_descriptor: Mapping[str, Any] | None = None,
    parsed_strategy: ParsedStrategy,
    bars: Sequence[Any],
    code: str,
    start_date: date,
    end_date: date,
    lookback_bars: int,
    initial_capital: float,
    fee_bps: float,
    slippage_bps: float,
    max_combinations: int = DEFAULT_MAX_GRID_COMBINATIONS,
    overflow_policy: str = DEFAULT_OVERFLOW_POLICY,
    total_timeout_seconds: float | None = None,
    engine: RuleBacktestEngine | None = None,
    include_parameter_stability_surface: bool = True,
) -> dict[str, Any]:
    """Execute accepted request descriptors against RuleBacktestEngine v1.

    The descriptor/request bundle remains immutable input. Actual execution
    evidence is returned only in this runner-local result object.
    """

    plan_payload = copy.deepcopy(dict(parameter_stability_plan or {}))
    request_bundle = _resolve_request_bundle(
        parameter_grid_request_bundle=parameter_grid_request_bundle,
        parameter_stability_plan=plan_payload,
    )
    descriptor_payload = copy.deepcopy(
        dict(parameter_grid_descriptor or plan_payload.get("parameter_grid_descriptor") or {})
    )
    result = _base_result(
        request_bundle=request_bundle,
        max_combinations=max_combinations,
        overflow_policy=overflow_policy,
        total_timeout_seconds=total_timeout_seconds,
    )

    validation_error = _validate_runner_inputs(
        request_bundle=request_bundle,
        descriptor=descriptor_payload,
        max_combinations=max_combinations,
        overflow_policy=overflow_policy,
        total_timeout_seconds=total_timeout_seconds,
        start_date=start_date,
        end_date=end_date,
        code=code,
    )
    if validation_error is not None:
        return _reject(
            result,
            validation_error["reasonCode"],
            validation_error,
            requests=_request_descriptors(request_bundle),
        )

    requests = _request_descriptors(request_bundle)
    path_error = _validate_request_parameter_paths(requests)
    if path_error is not None:
        return _reject(result, path_error["reasonCode"], path_error, requests=requests)
    path_application_error = _validate_strategy_parameter_application(
        parsed_strategy=parsed_strategy,
        requests=requests,
    )
    if path_application_error is not None:
        return _reject(
            result,
            path_application_error["reasonCode"],
            path_application_error,
            requests=requests,
        )

    timeout_budget = _normalize_timeout_budget(total_timeout_seconds)
    if timeout_budget == 0:
        return _timeout_result(
            result,
            reason_code="total_timeout_budget_exhausted_before_execution",
            requests=requests,
        )

    resolved_engine = engine or RuleBacktestEngine()
    started_at = time.monotonic()
    run_results_for_surface: list[dict[str, Any]] = []
    executed_request_ids: set[str] = set()

    for request in requests:
        if _timeout_budget_exhausted(started_at=started_at, total_timeout_seconds=timeout_budget):
            result["timeout"]["exhausted"] = True
            result["timeout"]["reasonCode"] = "total_timeout_budget_exhausted"
            break

        parameter_values = copy.deepcopy(dict(request.get("parameter_values") or {}))
        planned_run_id = str(request.get("planned_run_id") or "")
        request_index = int(request.get("request_index") or len(result["requestResults"]) + 1)
        run_strategy = _copy_strategy_with_parameter_values(parsed_strategy, parameter_values)
        executed_request_ids.add(planned_run_id)
        engine_result = resolved_engine.run(
            code=str(code),
            parsed_strategy=run_strategy,
            bars=bars,
            initial_capital=float(initial_capital),
            fee_bps=float(fee_bps),
            slippage_bps=float(slippage_bps),
            lookback_bars=int(lookback_bars),
            start_date=start_date,
            end_date=end_date,
        )
        payload = _engine_result_to_dict(engine_result)
        run_state = "blocked" if payload.get("no_result_reason") else "completed"
        metrics = copy.deepcopy(dict(payload.get("metrics") or {}))
        row = {
            "requestIndex": request_index,
            "plannedRunId": planned_run_id,
            "state": run_state,
            "parameterValues": parameter_values,
            "metrics": metrics,
            "reasonCode": payload.get("no_result_reason"),
            "reasonMessage": payload.get("no_result_message"),
            "noResultReason": payload.get("no_result_reason"),
            "noResultMessage": payload.get("no_result_message"),
            "warningCount": len(list(payload.get("warnings") or [])),
        }
        result["requestResults"].append(row)
        if run_state == "blocked":
            result["blockedRows"].append(copy.deepcopy(row))
        run_results_for_surface.append(
            {
                "planned_run_id": planned_run_id,
                "state": run_state,
                "metrics": metrics,
            }
        )

    _append_skipped_rows(
        result,
        requests=requests,
        executed_request_ids=executed_request_ids,
        reason_code=(
            "total_timeout_budget_exhausted"
            if result["timeout"]["exhausted"]
            else "not_executed"
        ),
    )
    _finalize_counts(result)
    if result["timeout"]["exhausted"]:
        result["state"] = "timeout_budget_exhausted"
    elif result["summary"]["completedCount"] == result["acceptedRequestCount"]:
        result["state"] = "completed"
    elif result["summary"]["blockedCount"] == result["acceptedRequestCount"]:
        result["state"] = "blocked"
    elif result["gridExecutionCount"] > 0:
        result["state"] = "partial"
    else:
        result["state"] = "rejected"
        result["failClosedReasonCode"] = "no_requests_executed"

    if include_parameter_stability_surface and plan_payload:
        result["parameterStabilitySurface"] = aggregate_parameter_stability_results(
            plan=plan_payload,
            run_results=run_results_for_surface,
        )
        result["parameterStabilityAggregation"] = {
            "state": "available",
            "reasonCode": None,
        }
    else:
        result["parameterStabilityAggregation"] = {
            "state": "skipped",
            "reasonCode": "parameter_stability_plan_not_supplied",
        }
    return result


def _resolve_request_bundle(
    *,
    parameter_grid_request_bundle: Mapping[str, Any] | None,
    parameter_stability_plan: Mapping[str, Any],
) -> dict[str, Any]:
    if parameter_grid_request_bundle is not None:
        return copy.deepcopy(dict(parameter_grid_request_bundle))
    return copy.deepcopy(dict(parameter_stability_plan.get("parameter_grid_request_bundle") or {}))


def _base_result(
    *,
    request_bundle: Mapping[str, Any],
    max_combinations: int,
    overflow_policy: str,
    total_timeout_seconds: float | None,
) -> dict[str, Any]:
    requests = _request_descriptors(request_bundle)
    return {
        "contractKind": BOUNDED_GRID_RUNNER_CONTRACT_KIND,
        "contractVersion": BOUNDED_GRID_RUNNER_CONTRACT_VERSION,
        "state": "pending",
        "diagnosticOnly": True,
        "requestBundleId": str(request_bundle.get("request_bundle_id") or ""),
        "requestBundleState": str(request_bundle.get("state") or ""),
        "maxCombinations": int(max_combinations),
        "overflowPolicy": str(overflow_policy or DEFAULT_OVERFLOW_POLICY).strip().lower(),
        "acceptedRequestCount": len(requests),
        "gridExecutionCount": 0,
        "skippedRequestCount": len(requests),
        "requestResults": [],
        "skippedRows": [],
        "failedRows": [],
        "blockedRows": [],
        "summary": {
            "totalParameterSets": len(requests),
            "runCount": 0,
            "executedCount": 0,
            "completedCount": 0,
            "blockedCount": 0,
            "failedCount": 0,
            "noResultCount": 0,
            "skippedCount": len(requests),
        },
        "parameterStabilitySurface": None,
        "parameterStabilityAggregation": {
            "state": "pending",
            "reasonCode": None,
        },
        "timeout": {
            "mode": "synchronous_between_request_budget",
            "totalTimeoutSeconds": total_timeout_seconds,
            "exhausted": False,
            "reasonCode": None,
        },
        "executionSemantics": {
            "enginePath": "RuleBacktestEngine.run",
            "engineVersion": "v1",
            "callerSuppliedBarsOnly": True,
            "oneSymbol": True,
            "oneBarsDataset": True,
            "fixedWindow": True,
            "descriptorMutation": False,
            "providerCallsExecuted": False,
            "marketCacheAccessed": False,
            "storageMutation": False,
            "storedRunIdentityCreated": False,
            "apiBehaviorChanged": False,
            "optimizerExecuted": False,
            "winnerPromotion": False,
            "decisionGrade": False,
        },
        "failClosedReasonCode": None,
        "failClosedDiagnostics": {},
    }


def _validate_runner_inputs(
    *,
    request_bundle: Mapping[str, Any],
    descriptor: Mapping[str, Any],
    max_combinations: int,
    overflow_policy: str,
    total_timeout_seconds: float | None,
    start_date: date,
    end_date: date,
    code: str,
) -> dict[str, Any] | None:
    if not request_bundle:
        return {"reasonCode": "request_bundle_missing"}
    if str(overflow_policy or "").strip().lower() != DEFAULT_OVERFLOW_POLICY:
        return {"reasonCode": "unsupported_overflow_policy", "overflowPolicy": overflow_policy}
    if int(max_combinations) > DEFAULT_MAX_GRID_COMBINATIONS:
        return {
            "reasonCode": "max_combinations_above_runner_hard_cap",
            "maxCombinations": int(max_combinations),
            "hardCap": DEFAULT_MAX_GRID_COMBINATIONS,
        }
    if int(max_combinations) <= 0:
        return {"reasonCode": "max_combinations_must_be_positive", "maxCombinations": int(max_combinations)}
    timeout_budget = _normalize_timeout_budget(total_timeout_seconds)
    if timeout_budget is not None and timeout_budget < 0:
        return {"reasonCode": "total_timeout_seconds_must_be_non_negative"}
    if not str(code or "").strip():
        return {"reasonCode": "code_required"}
    if start_date is None or end_date is None:
        return {"reasonCode": "fixed_start_date_end_date_required"}
    if not bool(request_bundle.get("diagnostic_only", False)):
        return {"reasonCode": "request_bundle_not_diagnostic_only"}
    for flag in _DESCRIPTOR_FLAGS:
        if request_bundle.get(flag, False) is not False:
            return {"reasonCode": "request_bundle_decision_flags_not_safe", "flag": flag}
        if descriptor and descriptor.get(flag, False) is not False:
            return {"reasonCode": "descriptor_decision_flags_not_safe", "flag": flag}
    requests = _request_descriptors(request_bundle)
    boundedness = dict(request_bundle.get("boundedness") or {})
    requested_combinations = int(boundedness.get("requested_combinations") or len(requests))
    accepted_combinations = int(boundedness.get("accepted_combinations") or len(requests))
    if str(request_bundle.get("state") or "") == "rejected":
        return {
            "reasonCode": str(boundedness.get("reason_code") or "request_bundle_rejected"),
            "requestedCombinations": requested_combinations,
            "acceptedCombinations": accepted_combinations,
        }
    if (
        requested_combinations > int(max_combinations)
        or accepted_combinations > int(max_combinations)
        or len(requests) > int(max_combinations)
    ):
        return {
            "reasonCode": "max_combinations_rejected",
            "requestedCombinations": requested_combinations,
            "acceptedCombinations": accepted_combinations,
            "requestCount": len(requests),
            "maxCombinations": int(max_combinations),
        }
    if str(request_bundle.get("state") or "") == "truncated":
        return {
            "reasonCode": "truncated_request_bundle_rejected_by_default",
            "requestedCombinations": requested_combinations,
            "acceptedCombinations": accepted_combinations,
        }
    if not requests:
        return {"reasonCode": "request_bundle_has_no_requests"}
    for request in requests:
        for flag in _DESCRIPTOR_FLAGS:
            if request.get(flag, False) is not False:
                return {"reasonCode": "request_decision_flags_not_safe", "flag": flag}
        for field_name in _FORBIDDEN_REQUEST_IDENTITY_FIELDS:
            if request.get(field_name) not in (None, ""):
                return {
                    "reasonCode": "request_identity_fields_not_allowed",
                    "fieldName": field_name,
                    "requestIndex": int(request.get("request_index") or 0),
                }
    return None


def _validate_request_parameter_paths(requests: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    for request in requests:
        parameter_values = dict(request.get("parameter_values") or {})
        for parameter_path in parameter_values:
            if not _is_safe_parameter_path(str(parameter_path)):
                return {
                    "reasonCode": "unsafe_parameter_path",
                    "parameterPath": str(parameter_path),
                    "allowedPrefixes": list(SAFE_PARAMETER_PATH_PREFIXES),
                }
    return None


def _validate_strategy_parameter_application(
    *,
    parsed_strategy: ParsedStrategy,
    requests: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    for request in requests:
        try:
            _copy_strategy_with_parameter_values(
                parsed_strategy,
                dict(request.get("parameter_values") or {}),
            )
        except ValueError as exc:
            return {
                "reasonCode": "parameter_path_application_failed",
                "plannedRunId": str(request.get("planned_run_id") or ""),
                "message": str(exc),
            }
    return None


def _is_safe_parameter_path(parameter_path: str) -> bool:
    parts = parameter_path.split(".")
    if any(not part or part.startswith("__") for part in parts):
        return False
    return any(
        parameter_path.startswith(prefix) and len(parameter_path) > len(prefix)
        for prefix in SAFE_PARAMETER_PATH_PREFIXES
    )


def _request_descriptors(request_bundle: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        copy.deepcopy(dict(item))
        for item in list(request_bundle.get("requests") or [])
        if isinstance(item, Mapping)
    ]


def _copy_strategy_with_parameter_values(
    parsed_strategy: ParsedStrategy,
    parameter_values: Mapping[str, Any],
) -> ParsedStrategy:
    strategy = copy.deepcopy(parsed_strategy)
    strategy_spec = copy.deepcopy(dict(getattr(strategy, "strategy_spec", {}) or {}))
    for parameter_path, value in parameter_values.items():
        _set_strategy_spec_path(strategy_spec, str(parameter_path).split(".")[1:], value)
    strategy.strategy_spec = strategy_spec
    return strategy


def _set_strategy_spec_path(strategy_spec: dict[str, Any], path_parts: Sequence[str], value: Any) -> None:
    if len(path_parts) < 2:
        raise ValueError("safe parameter path must target a strategy_spec leaf.")
    target = strategy_spec
    for part in path_parts[:-1]:
        if part not in target:
            raise ValueError("safe parameter path must target an existing strategy_spec field.")
        current = target.get(part)
        if not isinstance(current, dict):
            raise ValueError("safe parameter path conflicts with a non-mapping strategy_spec value.")
        target = current
    if str(path_parts[-1]) not in target:
        raise ValueError("safe parameter path must target an existing strategy_spec field.")
    target[str(path_parts[-1])] = copy.deepcopy(value)


def _engine_result_to_dict(engine_result: Any) -> dict[str, Any]:
    if isinstance(engine_result, Mapping):
        return copy.deepcopy(dict(engine_result))
    if hasattr(engine_result, "to_dict"):
        return copy.deepcopy(dict(engine_result.to_dict()))
    raise TypeError("RuleBacktestEngine.run must return a mapping or object with to_dict().")


def _normalize_timeout_budget(total_timeout_seconds: float | None) -> float | None:
    if total_timeout_seconds is None:
        return None
    return float(total_timeout_seconds)


def _timeout_budget_exhausted(*, started_at: float, total_timeout_seconds: float | None) -> bool:
    if total_timeout_seconds is None:
        return False
    return (time.monotonic() - started_at) >= float(total_timeout_seconds)


def _reject(
    result: dict[str, Any],
    reason_code: str,
    diagnostics: Mapping[str, Any],
    *,
    requests: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    result["state"] = "rejected"
    result["failClosedReasonCode"] = reason_code
    result["failClosedDiagnostics"] = copy.deepcopy(dict(diagnostics))
    _append_skipped_rows(
        result,
        requests=list(requests or []),
        executed_request_ids=set(),
        reason_code=reason_code,
    )
    _finalize_counts(result)
    result["parameterStabilityAggregation"] = {
        "state": "skipped",
        "reasonCode": reason_code,
    }
    return result


def _timeout_result(
    result: dict[str, Any],
    *,
    reason_code: str,
    requests: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    result["state"] = "timeout_budget_exhausted"
    result["timeout"]["exhausted"] = True
    result["timeout"]["reasonCode"] = reason_code
    result["failClosedReasonCode"] = reason_code
    _append_skipped_rows(
        result,
        requests=list(requests or []),
        executed_request_ids=set(),
        reason_code=reason_code,
    )
    _finalize_counts(result)
    result["parameterStabilityAggregation"] = {
        "state": "skipped",
        "reasonCode": reason_code,
    }
    return result


def _append_skipped_rows(
    result: dict[str, Any],
    *,
    requests: Sequence[Mapping[str, Any]],
    executed_request_ids: set[str],
    reason_code: str,
) -> None:
    existing = {
        str(row.get("plannedRunId") or "")
        for row in list(result.get("skippedRows") or [])
    }
    for request in requests:
        planned_run_id = str(request.get("planned_run_id") or "")
        if planned_run_id in executed_request_ids or planned_run_id in existing:
            continue
        row = {
            "requestIndex": int(request.get("request_index") or 0),
            "plannedRunId": planned_run_id,
            "state": "skipped",
            "parameterValues": copy.deepcopy(dict(request.get("parameter_values") or {})),
            "metrics": {},
            "reasonCode": reason_code,
            "reasonMessage": "Parameter set was not executed by the bounded diagnostic runner.",
            "warningCount": 0,
        }
        result["skippedRows"].append(row)
        existing.add(planned_run_id)


def _finalize_counts(result: dict[str, Any]) -> None:
    rows = list(result.get("requestResults") or [])
    skipped_rows = list(result.get("skippedRows") or [])
    failed_rows = list(result.get("failedRows") or [])
    blocked_rows = list(result.get("blockedRows") or [])
    completed_count = sum(1 for row in rows if str(row.get("state") or "") == "completed")
    blocked_count = len(blocked_rows)
    failed_count = len(failed_rows)
    executed_count = len(rows)
    skipped_count = len(skipped_rows)
    result["gridExecutionCount"] = executed_count
    result["skippedRequestCount"] = skipped_count
    result["summary"] = {
        "totalParameterSets": int(result.get("acceptedRequestCount") or 0),
        "runCount": executed_count,
        "executedCount": executed_count,
        "completedCount": completed_count,
        "blockedCount": blocked_count,
        "failedCount": failed_count,
        "noResultCount": blocked_count,
        "skippedCount": skipped_count,
    }


__all__ = [
    "BOUNDED_GRID_RUNNER_CONTRACT_KIND",
    "BOUNDED_GRID_RUNNER_CONTRACT_VERSION",
    "DEFAULT_MAX_GRID_COMBINATIONS",
    "DEFAULT_OVERFLOW_POLICY",
    "SAFE_PARAMETER_PATH_PREFIXES",
    "run_bounded_parameter_grid_diagnostic",
]
