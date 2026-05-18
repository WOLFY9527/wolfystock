# -*- coding: utf-8 -*-
"""Pure parameter-grid and stability-surface helpers for backtest diagnostics."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from itertools import product
from typing import Any, Mapping, Sequence


PARAMETER_STABILITY_CONTRACT_VERSION = "v1"
PARAMETER_STABILITY_CONTRACT_KIND = "backtest_parameter_stability_surface_scaffold"

DEFAULT_PARAMETER_STABILITY_METRIC_KEYS = (
    "total_return_pct",
    "max_drawdown_pct",
    "sharpe_ratio",
    "trade_count",
)

_HIGHER_IS_BETTER_METRICS = {
    "annualized_return_pct",
    "final_equity",
    "profit_loss_ratio",
    "sharpe_ratio",
    "sortino_ratio",
    "total_return_pct",
    "trade_count",
    "win_rate_pct",
}
_LOWER_IS_BETTER_METRICS = {
    "commission_cost",
    "max_drawdown_pct",
    "slippage_cost",
    "spread_cost",
    "total_cost",
    "volatility_pct",
}


@dataclass(frozen=True, slots=True)
class ParameterStabilityGridSpec:
    """Normalized input for planning a diagnostic parameter stability surface."""

    parameters: Mapping[str, Sequence[Any]]
    metric_keys: tuple[str, ...] = DEFAULT_PARAMETER_STABILITY_METRIC_KEYS
    primary_metric: str = "total_return_pct"
    risk_metric: str = "max_drawdown_pct"
    min_completed_runs: int = 2
    robust_region: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "parameters": copy.deepcopy(dict(self.parameters)),
            "metric_keys": list(self.metric_keys),
            "primary_metric": self.primary_metric,
            "risk_metric": self.risk_metric,
            "min_completed_runs": self.min_completed_runs,
        }
        if self.robust_region is not None:
            payload["robust_region"] = copy.deepcopy(dict(self.robust_region))
        return payload


def build_parameter_stability_plan(
    *,
    strategy_id: str,
    parameter_grid: Mapping[str, Sequence[Any]] | ParameterStabilityGridSpec,
    base_parameters: Mapping[str, Any] | None = None,
    dataset_id: str | None = None,
    metric_keys: Sequence[str] | None = None,
    primary_metric: str | None = None,
    risk_metric: str | None = None,
    robust_region: Mapping[str, Any] | None = None,
    min_completed_runs: int | None = None,
) -> dict[str, Any]:
    """Build a deterministic parameter grid plan without running a strategy."""

    raw_spec = _coerce_grid_spec(
        parameter_grid=parameter_grid,
        metric_keys=metric_keys,
        primary_metric=primary_metric,
        risk_metric=risk_metric,
        robust_region=robust_region,
        min_completed_runs=min_completed_runs,
    )
    parameter_specs = _normalize_parameter_grid(raw_spec["parameters"])
    resolved_metric_keys = _normalize_metric_keys(raw_spec.get("metric_keys"))
    resolved_primary_metric = str(raw_spec.get("primary_metric") or resolved_metric_keys[0])
    resolved_risk_metric = str(raw_spec.get("risk_metric") or "max_drawdown_pct")
    resolved_robust_region = _normalize_robust_region(raw_spec.get("robust_region"))
    resolved_min_completed_runs = _positive_int(raw_spec.get("min_completed_runs"), "min_completed_runs")
    base_parameter_payload = _normalize_mapping(base_parameters)

    grid_runs = _build_grid_runs(
        strategy_id=strategy_id,
        dataset_id=dataset_id,
        base_parameters=base_parameter_payload,
        parameter_specs=parameter_specs,
    )
    grid_spec_payload = {
        "parameters": [
            {"parameter_key": spec["parameter_key"], "values": copy.deepcopy(spec["values"])}
            for spec in parameter_specs
        ],
        "parameter_count": len(parameter_specs),
        "grid_size": len(grid_runs),
        "metric_keys": resolved_metric_keys,
        "primary_metric": resolved_primary_metric,
        "risk_metric": resolved_risk_metric,
        "robust_region": resolved_robust_region,
        "min_completed_runs": resolved_min_completed_runs,
    }
    insufficient_data = _plan_insufficient_data(parameter_specs=parameter_specs, grid_runs=grid_runs)
    state = "insufficient_data" if insufficient_data else "ready"

    return {
        "contract_kind": PARAMETER_STABILITY_CONTRACT_KIND,
        "contract_version": PARAMETER_STABILITY_CONTRACT_VERSION,
        "state": state,
        "diagnostic_only": True,
        "strategy_id": str(strategy_id),
        "dataset_id": dataset_id,
        "base_parameters": base_parameter_payload,
        "grid_spec": grid_spec_payload,
        "grid_runs": grid_runs,
        "insufficient_data": insufficient_data,
        "execution_semantics": _execution_semantics(),
        "reproducibility": _build_reproducibility_metadata(
            strategy_id=strategy_id,
            dataset_id=dataset_id,
            base_parameters=base_parameter_payload,
            grid_spec=grid_spec_payload,
        ),
        "contract_metadata": build_parameter_stability_contract_metadata(),
    }


def aggregate_parameter_stability_results(
    *,
    plan: Mapping[str, Any],
    run_results: Sequence[Mapping[str, Any]] | Mapping[str, Any],
    metric_keys: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Aggregate caller-supplied grid run results into a diagnostic surface."""

    plan_payload = copy.deepcopy(dict(plan or {}))
    grid_spec = copy.deepcopy(dict(plan_payload.get("grid_spec") or {}))
    grid_runs = sorted(
        [copy.deepcopy(dict(item or {})) for item in list(plan_payload.get("grid_runs") or [])],
        key=lambda item: int(item.get("grid_index") or 0),
    )
    resolved_metric_keys = _normalize_metric_keys(metric_keys or grid_spec.get("metric_keys"))
    primary_metric = str(grid_spec.get("primary_metric") or resolved_metric_keys[0])
    risk_metric = str(grid_spec.get("risk_metric") or "max_drawdown_pct")
    min_completed_runs = _positive_int(grid_spec.get("min_completed_runs", 1), "min_completed_runs")
    robust_region = _normalize_robust_region(grid_spec.get("robust_region"))
    results_by_run_id = _normalize_run_results(run_results)

    rows: list[dict[str, Any]] = []
    row_order: list[str] = []
    completed_run_count = 0
    missing_result_run_count = 0
    missing_metric_counts = {metric_key: 0 for metric_key in resolved_metric_keys}

    for grid_run in grid_runs:
        planned_run_id = str(grid_run.get("planned_run_id") or "")
        row_order.append(planned_run_id)
        result = results_by_run_id.get(planned_run_id)
        if result is None:
            missing_result_run_count += 1
            row_state = "missing_result"
            metrics_payload = {
                metric_key: {"state": "missing_result", "value": None}
                for metric_key in resolved_metric_keys
            }
            external_run_id = None
        else:
            row_state = str(result.get("state") or "completed")
            external_run_id = result.get("external_run_id")
            metrics_payload = _build_row_metrics(
                metrics=result.get("metrics"),
                metric_keys=resolved_metric_keys,
                missing_metric_counts=missing_metric_counts,
            )
            if row_state == "completed":
                completed_run_count += 1

        rows.append(
            {
                "planned_run_id": planned_run_id,
                "grid_index": int(grid_run.get("grid_index") or 0),
                "state": row_state,
                "external_run_id": external_run_id,
                "parameter_values": copy.deepcopy(dict(grid_run.get("parameter_values") or {})),
                "metrics": metrics_payload,
            }
        )

    top_state = _surface_state(
        plan_state=str(plan_payload.get("state") or ""),
        completed_run_count=completed_run_count,
        min_completed_runs=min_completed_runs,
    )
    insufficient_data = _aggregate_insufficient_data(
        plan_payload=plan_payload,
        top_state=top_state,
        min_completed_runs=min_completed_runs,
        completed_run_count=completed_run_count,
        missing_result_run_count=missing_result_run_count,
    )
    metric_surface = {
        "state": top_state,
        "metric_keys": resolved_metric_keys,
        "row_order": row_order,
        "rows": rows,
        "completed_run_count": completed_run_count,
        "missing_result_run_count": missing_result_run_count,
        "missing_metric_counts": missing_metric_counts,
        "metric_aggregates": _aggregate_metric_surface(rows=rows, metric_keys=resolved_metric_keys),
    }

    return {
        "contract_kind": PARAMETER_STABILITY_CONTRACT_KIND,
        "contract_version": PARAMETER_STABILITY_CONTRACT_VERSION,
        "state": top_state,
        "diagnostic_only": True,
        "strategy_id": plan_payload.get("strategy_id"),
        "dataset_id": plan_payload.get("dataset_id"),
        "grid_spec": grid_spec,
        "metric_surface": metric_surface,
        "best_summary": _build_best_summary(rows=rows, primary_metric=primary_metric),
        "robust_region_summary": _build_robust_region_summary(
            rows=rows,
            parameter_keys=[str(item.get("parameter_key")) for item in grid_spec.get("parameters") or []],
            primary_metric=primary_metric,
            risk_metric=risk_metric,
            robust_region=robust_region,
            top_state=top_state,
        ),
        "insufficient_data": insufficient_data,
        "execution_semantics": _execution_semantics(),
        "reproducibility": _augment_result_reproducibility(plan_payload.get("reproducibility")),
        "contract_metadata": copy.deepcopy(
            plan_payload.get("contract_metadata") or build_parameter_stability_contract_metadata()
        ),
    }


def build_parameter_stability_contract_metadata() -> dict[str, Any]:
    return {
        "contract_kind": PARAMETER_STABILITY_CONTRACT_KIND,
        "contract_version": PARAMETER_STABILITY_CONTRACT_VERSION,
        "diagnostic_only": True,
        "parameter_grid_expansion": "deterministic_cartesian_product",
        "parameter_ordering": "parameter_key_ascending",
        "value_ordering": "canonical_value_ascending",
        "run_id_policy": "stable_sha256_from_strategy_dataset_base_parameters_and_parameter_values",
        "result_source": "caller_supplied_results_only",
        "hidden_optimizer_executed": False,
        "automatic_winner_promotion": False,
        "live_strategy_selection": False,
        "engine_math_changed": False,
        "provider_behavior_changed": False,
        "runtime_defaults_changed": False,
        "portfolio_allocation_backtest_executed": False,
    }


def _coerce_grid_spec(
    *,
    parameter_grid: Mapping[str, Sequence[Any]] | ParameterStabilityGridSpec,
    metric_keys: Sequence[str] | None,
    primary_metric: str | None,
    risk_metric: str | None,
    robust_region: Mapping[str, Any] | None,
    min_completed_runs: int | None,
) -> dict[str, Any]:
    if isinstance(parameter_grid, ParameterStabilityGridSpec):
        raw = parameter_grid.to_dict()
    elif isinstance(parameter_grid, Mapping):
        raw = {"parameters": copy.deepcopy(dict(parameter_grid))}
    else:
        raise ValueError("parameter_grid must be a mapping or ParameterStabilityGridSpec.")

    if metric_keys is not None:
        raw["metric_keys"] = list(metric_keys)
    raw.setdefault("metric_keys", list(DEFAULT_PARAMETER_STABILITY_METRIC_KEYS))
    if primary_metric is not None:
        raw["primary_metric"] = primary_metric
    raw.setdefault("primary_metric", "total_return_pct")
    if risk_metric is not None:
        raw["risk_metric"] = risk_metric
    raw.setdefault("risk_metric", "max_drawdown_pct")
    if robust_region is not None:
        raw["robust_region"] = copy.deepcopy(dict(robust_region))
    if min_completed_runs is not None:
        raw["min_completed_runs"] = min_completed_runs
    raw.setdefault("min_completed_runs", 2)
    return raw


def _normalize_parameter_grid(parameter_grid: Mapping[str, Sequence[Any]]) -> list[dict[str, Any]]:
    if not isinstance(parameter_grid, Mapping):
        raise ValueError("parameter_grid.parameters must be a mapping.")

    specs: list[dict[str, Any]] = []
    for raw_key in sorted(parameter_grid.keys(), key=lambda item: str(item)):
        parameter_key = str(raw_key or "").strip()
        if not parameter_key:
            raise ValueError("parameter key must not be empty.")
        values = _normalize_parameter_values(parameter_grid.get(raw_key))
        specs.append({"parameter_key": parameter_key, "values": values})
    return specs


def _normalize_parameter_values(raw_values: Any) -> list[Any]:
    if raw_values is None:
        values: list[Any] = []
    elif isinstance(raw_values, (str, bytes)) or not isinstance(raw_values, Sequence):
        values = [raw_values]
    else:
        values = list(raw_values)

    deduped: list[Any] = []
    seen: set[str] = set()
    for value in values:
        normalized = _json_safe(value)
        fingerprint = _canonical_json(normalized)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        deduped.append(normalized)
    return sorted(deduped, key=_value_sort_key)


def _normalize_metric_keys(metric_keys: Sequence[str] | None) -> list[str]:
    raw_keys = metric_keys or DEFAULT_PARAMETER_STABILITY_METRIC_KEYS
    if isinstance(raw_keys, str):
        raw_keys = [raw_keys]
    resolved: list[str] = []
    seen: set[str] = set()
    for raw_key in list(raw_keys):
        metric_key = str(raw_key or "").strip()
        if not metric_key or metric_key in seen:
            continue
        seen.add(metric_key)
        resolved.append(metric_key)
    return resolved or list(DEFAULT_PARAMETER_STABILITY_METRIC_KEYS)


def _normalize_robust_region(value: Any) -> dict[str, float]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("robust_region must be a mapping.")
    resolved: dict[str, float] = {}
    for key in ("primary_metric_min", "primary_metric_max", "risk_metric_min", "risk_metric_max"):
        if value.get(key) is None:
            continue
        numeric = _safe_float(value.get(key))
        if numeric is None:
            raise ValueError(f"robust_region.{key} must be numeric.")
        resolved[key] = float(numeric)
    return resolved


def _normalize_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("base_parameters must be a mapping.")
    return copy.deepcopy(dict(value))


def _build_grid_runs(
    *,
    strategy_id: str,
    dataset_id: str | None,
    base_parameters: Mapping[str, Any],
    parameter_specs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if not parameter_specs or any(not spec.get("values") for spec in parameter_specs):
        return []

    keys = [str(spec["parameter_key"]) for spec in parameter_specs]
    value_sets = [list(spec.get("values") or []) for spec in parameter_specs]
    grid_runs: list[dict[str, Any]] = []
    for zero_based_index, values in enumerate(product(*value_sets)):
        parameter_values = {key: copy.deepcopy(value) for key, value in zip(keys, values)}
        planned_run_id = _build_planned_run_id(
            strategy_id=strategy_id,
            dataset_id=dataset_id,
            base_parameters=base_parameters,
            parameter_values=parameter_values,
        )
        grid_runs.append(
            {
                "planned_run_id": planned_run_id,
                "grid_index": zero_based_index + 1,
                "state": "planned",
                "parameter_values": parameter_values,
                "execution_semantics": _execution_semantics(),
            }
        )
    return grid_runs


def _build_planned_run_id(
    *,
    strategy_id: str,
    dataset_id: str | None,
    base_parameters: Mapping[str, Any],
    parameter_values: Mapping[str, Any],
) -> str:
    payload = {
        "contract_kind": PARAMETER_STABILITY_CONTRACT_KIND,
        "contract_version": PARAMETER_STABILITY_CONTRACT_VERSION,
        "strategy_id": str(strategy_id),
        "dataset_id": dataset_id,
        "base_parameters": _json_safe(base_parameters),
        "parameter_values": _json_safe(parameter_values),
    }
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()[:16]
    return f"bt_param_stability_{digest}"


def _plan_insufficient_data(
    *,
    parameter_specs: Sequence[Mapping[str, Any]],
    grid_runs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not parameter_specs:
        return {
            "reason_code": "parameter_grid_empty",
            "required_grid_points": 1,
            "available_grid_points": 0,
        }
    missing_value_keys = [str(spec.get("parameter_key")) for spec in parameter_specs if not spec.get("values")]
    if missing_value_keys:
        return {
            "reason_code": "parameter_values_missing",
            "parameter_keys": missing_value_keys,
            "required_grid_points": 1,
            "available_grid_points": 0,
        }
    if not grid_runs:
        return {
            "reason_code": "parameter_grid_expansion_empty",
            "required_grid_points": 1,
            "available_grid_points": 0,
        }
    return {}


def _normalize_run_results(
    run_results: Sequence[Mapping[str, Any]] | Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    if isinstance(run_results, Mapping):
        if any(key in run_results for key in ("planned_run_id", "parameter_stability_run_id", "grid_run_id")):
            items = [copy.deepcopy(dict(run_results))]
        else:
            items = []
            for run_id, result in run_results.items():
                if not isinstance(result, Mapping):
                    continue
                item = copy.deepcopy(dict(result))
                item.setdefault("planned_run_id", str(run_id))
                items.append(item)
    else:
        items = [copy.deepcopy(dict(item or {})) for item in list(run_results or [])]

    results_by_run_id: dict[str, dict[str, Any]] = {}
    for item in items:
        planned_run_id = (
            item.get("planned_run_id")
            or item.get("parameter_stability_run_id")
            or item.get("grid_run_id")
        )
        if planned_run_id:
            results_by_run_id[str(planned_run_id)] = item
    return results_by_run_id


def _build_row_metrics(
    *,
    metrics: Any,
    metric_keys: Sequence[str],
    missing_metric_counts: dict[str, int],
) -> dict[str, dict[str, Any]]:
    metric_payload = metrics if isinstance(metrics, Mapping) else {}
    resolved: dict[str, dict[str, Any]] = {}
    for metric_key in metric_keys:
        value = _safe_float(metric_payload.get(metric_key))
        if value is None:
            missing_metric_counts[metric_key] = int(missing_metric_counts.get(metric_key, 0)) + 1
            resolved[metric_key] = {"state": "missing_metric", "value": None}
        else:
            resolved[metric_key] = {"state": "available", "value": _round(value)}
    return resolved


def _surface_state(
    *,
    plan_state: str,
    completed_run_count: int,
    min_completed_runs: int,
) -> str:
    if plan_state == "insufficient_data":
        return "insufficient_data"
    if completed_run_count < min_completed_runs:
        return "insufficient_results"
    return "available"


def _aggregate_insufficient_data(
    *,
    plan_payload: Mapping[str, Any],
    top_state: str,
    min_completed_runs: int,
    completed_run_count: int,
    missing_result_run_count: int,
) -> dict[str, Any]:
    if top_state == "insufficient_data":
        return copy.deepcopy(dict(plan_payload.get("insufficient_data") or {}))
    if top_state == "insufficient_results":
        return {
            "reason_code": "insufficient_completed_runs",
            "required_completed_runs": int(min_completed_runs),
            "completed_run_count": int(completed_run_count),
            "missing_result_run_count": int(missing_result_run_count),
        }
    return {}


def _aggregate_metric_surface(
    *,
    rows: Sequence[Mapping[str, Any]],
    metric_keys: Sequence[str],
) -> dict[str, dict[str, float | int]]:
    aggregates: dict[str, dict[str, float | int]] = {}
    for metric_key in metric_keys:
        values = [
            float(cell["value"])
            for row in rows
            if row.get("state") == "completed"
            for cell_key, cell in dict(row.get("metrics") or {}).items()
            if cell_key == metric_key and dict(cell).get("state") == "available"
        ]
        if not values:
            continue
        aggregates[str(metric_key)] = {
            "count": len(values),
            "min": _round(min(values)),
            "max": _round(max(values)),
            "mean": _round(sum(values) / len(values)),
        }
    return aggregates


def _build_best_summary(
    *,
    rows: Sequence[Mapping[str, Any]],
    primary_metric: str,
) -> dict[str, Any]:
    preference = _metric_preference(primary_metric)
    candidates: list[tuple[str, float]] = []
    for row in rows:
        if row.get("state") != "completed":
            continue
        metric_cell = dict(dict(row.get("metrics") or {}).get(primary_metric) or {})
        if metric_cell.get("state") != "available":
            continue
        candidates.append((str(row.get("planned_run_id") or ""), float(metric_cell.get("value"))))

    if not candidates:
        return {
            "state": "insufficient_metrics",
            "selection_rule": "diagnostic_primary_metric_leader_only",
            "primary_metric": primary_metric,
            "preference": preference,
            "candidate_count": 0,
            "best_run_ids": [],
            "best_value": None,
            "automatic_winner_promotion": False,
            "live_strategy_selection": False,
        }

    best_value = (
        max(value for _, value in candidates)
        if preference == "higher_is_better"
        else min(value for _, value in candidates)
    )
    best_run_ids = [run_id for run_id, value in candidates if value == best_value]
    return {
        "state": "available",
        "selection_rule": "diagnostic_primary_metric_leader_only",
        "primary_metric": primary_metric,
        "preference": preference,
        "candidate_count": len(candidates),
        "best_run_ids": best_run_ids,
        "best_value": _round(best_value),
        "automatic_winner_promotion": False,
        "live_strategy_selection": False,
    }


def _build_robust_region_summary(
    *,
    rows: Sequence[Mapping[str, Any]],
    parameter_keys: Sequence[str],
    primary_metric: str,
    risk_metric: str,
    robust_region: Mapping[str, float],
    top_state: str,
) -> dict[str, Any]:
    base_payload: dict[str, Any] = {
        "selection_rule": "configured_threshold_filter",
        "primary_metric": primary_metric,
        "risk_metric": risk_metric,
        "thresholds": copy.deepcopy(dict(robust_region or {})),
        "member_run_ids": [],
        "member_count": 0,
        "parameter_ranges": {},
        "automatic_winner_promotion": False,
        "live_strategy_selection": False,
    }
    if not robust_region:
        return {"state": "not_configured", **base_payload}
    if top_state in {"insufficient_data", "insufficient_results"}:
        return {"state": top_state, **base_payload}

    members: list[Mapping[str, Any]] = []
    for row in rows:
        if row.get("state") != "completed":
            continue
        metric_cells = dict(row.get("metrics") or {})
        primary_cell = dict(metric_cells.get(primary_metric) or {})
        risk_cell = dict(metric_cells.get(risk_metric) or {})
        if primary_cell.get("state") != "available" or risk_cell.get("state") != "available":
            continue
        if _passes_robust_thresholds(
            primary_value=float(primary_cell.get("value")),
            risk_value=float(risk_cell.get("value")),
            robust_region=robust_region,
        ):
            members.append(row)

    member_run_ids = [str(row.get("planned_run_id") or "") for row in members]
    return {
        "state": "available" if members else "empty",
        **base_payload,
        "member_run_ids": member_run_ids,
        "member_count": len(member_run_ids),
        "parameter_ranges": _build_parameter_ranges(members=members, parameter_keys=parameter_keys),
    }


def _passes_robust_thresholds(
    *,
    primary_value: float,
    risk_value: float,
    robust_region: Mapping[str, float],
) -> bool:
    primary_min = robust_region.get("primary_metric_min")
    primary_max = robust_region.get("primary_metric_max")
    risk_min = robust_region.get("risk_metric_min")
    risk_max = robust_region.get("risk_metric_max")
    if primary_min is not None and primary_value < float(primary_min):
        return False
    if primary_max is not None and primary_value > float(primary_max):
        return False
    if risk_min is not None and risk_value < float(risk_min):
        return False
    if risk_max is not None and risk_value > float(risk_max):
        return False
    return True


def _build_parameter_ranges(
    *,
    members: Sequence[Mapping[str, Any]],
    parameter_keys: Sequence[str],
) -> dict[str, dict[str, Any]]:
    ranges: dict[str, dict[str, Any]] = {}
    for parameter_key in parameter_keys:
        values = [
            copy.deepcopy(dict(row.get("parameter_values") or {}).get(parameter_key))
            for row in members
            if parameter_key in dict(row.get("parameter_values") or {})
        ]
        if not values:
            continue
        ordered_values = _dedupe_ordered_values(values)
        numeric_values = [value for value in ordered_values if _safe_float(value) is not None]
        if len(numeric_values) == len(ordered_values):
            numeric = [float(value) for value in numeric_values]
            min_value: Any = _preserve_int_if_possible(min(numeric))
            max_value: Any = _preserve_int_if_possible(max(numeric))
        else:
            min_value = ordered_values[0]
            max_value = ordered_values[-1]
        ranges[str(parameter_key)] = {
            "min": min_value,
            "max": max_value,
            "values": ordered_values,
        }
    return ranges


def _dedupe_ordered_values(values: Sequence[Any]) -> list[Any]:
    deduped: list[Any] = []
    seen: set[str] = set()
    for value in sorted([_json_safe(item) for item in values], key=_value_sort_key):
        fingerprint = _canonical_json(value)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        deduped.append(_preserve_int_if_possible(value) if isinstance(value, float) else value)
    return deduped


def _build_reproducibility_metadata(
    *,
    strategy_id: str,
    dataset_id: str | None,
    base_parameters: Mapping[str, Any],
    grid_spec: Mapping[str, Any],
) -> dict[str, Any]:
    fingerprint_payload = {
        "strategy_id": str(strategy_id),
        "dataset_id": dataset_id,
        "base_parameters": _json_safe(base_parameters),
        "grid_spec": _json_safe(grid_spec),
    }
    return {
        "contract_version": PARAMETER_STABILITY_CONTRACT_VERSION,
        "dataset_id": dataset_id,
        "input_ordering": "parameter_key_ascending_then_canonical_value_ascending",
        "grid_run_ordering": "grid_index_ascending",
        "run_id_policy": "stable_sha256_from_strategy_dataset_base_parameters_and_parameter_values",
        "grid_spec_hash_sha256": hashlib.sha256(_canonical_json(fingerprint_payload).encode("utf-8")).hexdigest(),
    }


def _augment_result_reproducibility(reproducibility: Any) -> dict[str, Any]:
    payload = copy.deepcopy(dict(reproducibility or {})) if isinstance(reproducibility, Mapping) else {}
    payload.setdefault("contract_version", PARAMETER_STABILITY_CONTRACT_VERSION)
    payload.setdefault("grid_run_ordering", "grid_index_ascending")
    payload.setdefault("run_id_policy", "stable_sha256_from_strategy_dataset_base_parameters_and_parameter_values")
    payload["result_ordering"] = "grid_index_ascending"
    return payload


def _execution_semantics() -> dict[str, Any]:
    return {
        "execution_mode": "caller_supplied_results_only",
        "strategy_execution_count": 0,
        "provider_calls_executed": False,
        "hidden_optimizer_executed": False,
        "automatic_winner_promotion": False,
        "live_strategy_selection": False,
        "engine_math_changed": False,
        "runtime_defaults_changed": False,
        "portfolio_allocation_backtest_executed": False,
    }


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a positive integer.")
    try:
        resolved = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer.") from exc
    if resolved < 1:
        raise ValueError(f"{name} must be a positive integer.")
    return resolved


def _metric_preference(metric_key: str) -> str:
    normalized = str(metric_key or "").strip()
    if normalized in _LOWER_IS_BETTER_METRICS:
        return "lower_is_better"
    if normalized in _HIGHER_IS_BETTER_METRICS:
        return "higher_is_better"
    return "higher_is_better"


def _safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def _preserve_int_if_possible(value: Any) -> Any:
    numeric = _safe_float(value)
    if numeric is None:
        return value
    if float(numeric).is_integer():
        return int(numeric)
    return _round(float(numeric))


def _value_sort_key(value: Any) -> tuple[int, Any, str]:
    if value is None:
        return (4, "", "")
    if isinstance(value, bool):
        return (3, int(value), _canonical_json(value))
    numeric = _safe_float(value)
    if numeric is not None and not isinstance(value, str):
        return (0, float(numeric), _canonical_json(value))
    if isinstance(value, str):
        return (1, value, _canonical_json(value))
    return (2, _canonical_json(value), _canonical_json(value))


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(value[key]) for key in sorted(value.keys(), key=lambda item: str(item))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


__all__ = [
    "PARAMETER_STABILITY_CONTRACT_KIND",
    "PARAMETER_STABILITY_CONTRACT_VERSION",
    "DEFAULT_PARAMETER_STABILITY_METRIC_KEYS",
    "ParameterStabilityGridSpec",
    "aggregate_parameter_stability_results",
    "build_parameter_stability_contract_metadata",
    "build_parameter_stability_plan",
]
