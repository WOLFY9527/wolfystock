# -*- coding: utf-8 -*-
"""Pure walk-forward / out-of-sample validation scaffold for backtests."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping, Sequence


WALK_FORWARD_OOS_CONTRACT_VERSION = "v1"
WALK_FORWARD_OOS_CONTRACT_KIND = "backtest_walk_forward_oos_validation_scaffold"
DEFAULT_WALK_FORWARD_OOS_METRIC_KEYS = (
    "total_return_pct",
    "max_drawdown_pct",
    "win_rate_pct",
    "trade_count",
)


@dataclass(frozen=True, slots=True)
class WalkForwardOOSConfig:
    train_window: int
    test_window: int
    step: int = 1
    max_folds: int | None = None
    metric_keys: tuple[str, ...] = DEFAULT_WALK_FORWARD_OOS_METRIC_KEYS

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "train_window": self.train_window,
            "test_window": self.test_window,
            "step": self.step,
            "metric_keys": list(self.metric_keys),
        }
        if self.max_folds is not None:
            payload["max_folds"] = self.max_folds
        return payload


@dataclass(frozen=True, slots=True)
class _ObservationMarker:
    label: str
    sort_key: tuple[int, str, int]
    source_index: int


def build_walk_forward_oos_contract_metadata(
    *,
    strategy_id: str | None = None,
    observation_count: int | None = None,
    train_window: int | None = None,
    test_window: int | None = None,
    step: int | None = None,
    max_folds: int | None = None,
) -> dict[str, Any]:
    del strategy_id, observation_count, train_window, test_window, step, max_folds
    return {
        "contract_kind": WALK_FORWARD_OOS_CONTRACT_KIND,
        "contract_version": WALK_FORWARD_OOS_CONTRACT_VERSION,
        "diagnostic_only": True,
        "optimizer_executed": False,
        "parameter_sweep_executed": False,
        "portfolio_allocation_backtest_executed": False,
        "engine_math_changed": False,
        "provider_behavior_changed": False,
        "strategy_selection_mode": "placeholder_input_strategy_reuse",
        "fold_ordering": "fold_index_ascending",
        "fold_id_policy": "stable_from_window_bounds",
    }


def build_walk_forward_oos_validation_plan(
    *,
    observations: Sequence[Any],
    strategy_id: str,
    config: Mapping[str, Any] | WalkForwardOOSConfig,
    dataset_id: str | None = None,
    run_id: str | int | None = None,
) -> dict[str, Any]:
    resolved_config = _normalize_config(config)
    ordered_observations = _normalize_observations(observations)
    train_window = int(resolved_config["train_window"])
    test_window = int(resolved_config["test_window"])
    step = int(resolved_config["step"])
    max_folds = resolved_config.get("max_folds")
    metric_keys = list(resolved_config["metric_keys"])
    observation_count = len(ordered_observations)
    strategy_selection = _strategy_selection_placeholder(strategy_id)
    reproducibility = _build_reproducibility_metadata(
        config=resolved_config,
        dataset_id=dataset_id,
        run_id=run_id,
        observation_count=observation_count,
    )
    base_payload: dict[str, Any] = {
        "contract_kind": WALK_FORWARD_OOS_CONTRACT_KIND,
        "contract_version": WALK_FORWARD_OOS_CONTRACT_VERSION,
        "state": "ready",
        "diagnostic_only": True,
        "strategy_id": str(strategy_id),
        "configuration": resolved_config,
        "observation_count": observation_count,
        "fold_count": 0,
        "folds": [],
        "insufficient_data": {},
        "strategy_selection": strategy_selection,
        "oos_result_summary": _empty_oos_result_summary("pending_results", metric_keys),
        "reproducibility": reproducibility,
        "contract_metadata": build_walk_forward_oos_contract_metadata(
            strategy_id=strategy_id,
            observation_count=observation_count,
            train_window=train_window,
            test_window=test_window,
            step=step,
            max_folds=int(max_folds) if max_folds is not None else None,
        ),
    }

    required_observations = train_window + test_window
    if observation_count < required_observations:
        base_payload["state"] = "insufficient_data"
        base_payload["insufficient_data"] = {
            "reason_code": "insufficient_observations_for_initial_fold",
            "required_observations": required_observations,
            "available_observations": observation_count,
            "train_window": train_window,
            "test_window": test_window,
        }
        base_payload["oos_result_summary"] = _empty_oos_result_summary("insufficient_data", metric_keys)
        return base_payload

    folds: list[dict[str, Any]] = []
    max_start = observation_count - required_observations
    for zero_based_index, start_index in enumerate(range(0, max_start + 1, step)):
        if max_folds is not None and zero_based_index >= int(max_folds):
            break
        fold_index = zero_based_index + 1
        folds.append(
            _build_validation_fold(
                fold_index=fold_index,
                start_index=start_index,
                train_window=train_window,
                test_window=test_window,
                observations=ordered_observations,
                strategy_selection=strategy_selection,
            )
        )

    if not folds:
        base_payload["state"] = "insufficient_data"
        base_payload["insufficient_data"] = {
            "reason_code": "no_validation_folds_constructed",
            "required_observations": required_observations,
            "available_observations": observation_count,
            "train_window": train_window,
            "test_window": test_window,
        }
        base_payload["oos_result_summary"] = _empty_oos_result_summary("insufficient_data", metric_keys)
        return base_payload

    base_payload["fold_count"] = len(folds)
    base_payload["folds"] = folds
    return base_payload


def aggregate_walk_forward_oos_results(
    *,
    plan: Mapping[str, Any],
    fold_results: Sequence[Mapping[str, Any]] | Mapping[str, Any],
    metric_keys: Sequence[str] | None = None,
) -> dict[str, Any]:
    plan_payload = copy.deepcopy(dict(plan or {}))
    folds = sorted(
        [copy.deepcopy(dict(item or {})) for item in list(plan_payload.get("folds") or [])],
        key=lambda item: int(item.get("fold_index") or 0),
    )
    config = dict(plan_payload.get("configuration") or {})
    resolved_metric_keys = list(metric_keys or config.get("metric_keys") or DEFAULT_WALK_FORWARD_OOS_METRIC_KEYS)
    results_by_fold_id = _normalize_fold_results(fold_results)
    fold_order: list[str] = []
    ordered_fold_results: list[dict[str, Any]] = []
    completed_metric_snapshots: list[dict[str, float]] = []
    missing_result_count = 0

    for fold in folds:
        fold_id = str(fold.get("fold_id") or "")
        fold_order.append(fold_id)
        result = results_by_fold_id.get(fold_id)
        if result is None:
            state = "missing_result"
            metrics: dict[str, float] = {}
            missing_result_count += 1
        else:
            state = str(result.get("state") or "completed")
            metrics = _extract_metric_snapshot(result.get("metrics"), resolved_metric_keys)
            if state == "completed":
                completed_metric_snapshots.append(metrics)

        ordered_fold_results.append(
            {
                "fold_id": fold_id,
                "fold_index": int(fold.get("fold_index") or 0),
                "state": state,
                "train_window": copy.deepcopy(fold.get("train_window") or {}),
                "test_window": copy.deepcopy(fold.get("test_window") or {}),
                "strategy_selection": copy.deepcopy(
                    fold.get("strategy_selection")
                    or plan_payload.get("strategy_selection")
                    or _strategy_selection_placeholder(str(plan_payload.get("strategy_id") or "input_strategy"))
                ),
                "metrics": metrics,
            }
        )

    oos_result_summary = {
        "state": "available" if completed_metric_snapshots else "insufficient_results",
        "completed_fold_count": len(completed_metric_snapshots),
        "missing_result_fold_count": missing_result_count,
        "metric_keys": resolved_metric_keys,
        "metric_aggregates": _aggregate_metric_snapshots(completed_metric_snapshots, resolved_metric_keys),
    }
    if completed_metric_snapshots:
        state = "available"
    else:
        plan_state = str(plan_payload.get("state") or "")
        state = plan_state if plan_state in {"insufficient_data", "insufficient_results"} else "insufficient_results"
    return {
        "contract_kind": WALK_FORWARD_OOS_CONTRACT_KIND,
        "contract_version": WALK_FORWARD_OOS_CONTRACT_VERSION,
        "state": state,
        "diagnostic_only": True,
        "fold_order": fold_order,
        "fold_results": ordered_fold_results,
        "strategy_selection": copy.deepcopy(
            plan_payload.get("strategy_selection")
            or _strategy_selection_placeholder(str(plan_payload.get("strategy_id") or "input_strategy"))
        ),
        "oos_result_summary": oos_result_summary,
        "reproducibility": _augment_result_reproducibility(plan_payload.get("reproducibility")),
        "contract_metadata": copy.deepcopy(
            plan_payload.get("contract_metadata")
            or build_walk_forward_oos_contract_metadata()
        ),
    }


def _normalize_config(config: Mapping[str, Any] | WalkForwardOOSConfig) -> dict[str, Any]:
    if isinstance(config, WalkForwardOOSConfig):
        raw_config = config.to_dict()
    elif isinstance(config, Mapping):
        raw_config = copy.deepcopy(dict(config))
    else:
        raise ValueError("walk-forward OOS config must be a mapping or WalkForwardOOSConfig.")

    metric_keys = raw_config.get("metric_keys") or DEFAULT_WALK_FORWARD_OOS_METRIC_KEYS
    if isinstance(metric_keys, str):
        metric_keys = [metric_keys]
    resolved: dict[str, Any] = {
        "train_window": _positive_int(raw_config.get("train_window"), "train_window"),
        "test_window": _positive_int(raw_config.get("test_window"), "test_window"),
        "step": _positive_int(raw_config.get("step", 1), "step"),
        "metric_keys": [str(item) for item in list(metric_keys)],
    }
    max_folds = raw_config.get("max_folds", raw_config.get("max_windows"))
    if max_folds is not None:
        resolved["max_folds"] = _positive_int(max_folds, "max_folds")
    return resolved


def _positive_int(value: Any, name: str) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer.") from exc
    if resolved < 1:
        raise ValueError(f"{name} must be a positive integer.")
    return resolved


def _normalize_observations(observations: Sequence[Any]) -> list[_ObservationMarker]:
    normalized: list[_ObservationMarker] = []
    for source_index, observation in enumerate(list(observations or [])):
        label = _observation_date_label(observation)
        if label is None:
            label = f"index_{source_index:06d}"
            sort_key = (1, f"{source_index:06d}", source_index)
        else:
            sort_key = (0, label, source_index)
        normalized.append(_ObservationMarker(label=label, sort_key=sort_key, source_index=source_index))
    return sorted(normalized, key=lambda item: item.sort_key)


def _observation_date_label(observation: Any) -> str | None:
    value: Any = None
    if isinstance(observation, Mapping):
        for key in ("date", "trading_date", "timestamp", "datetime"):
            if observation.get(key) is not None:
                value = observation.get(key)
                break
    else:
        for key in ("date", "trading_date", "timestamp", "datetime"):
            if hasattr(observation, key):
                value = getattr(observation, key)
                break
    return _date_label(value)


def _date_label(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        try:
            return datetime.fromisoformat(normalized.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            try:
                return date.fromisoformat(normalized).isoformat()
            except ValueError:
                return normalized
    return str(value)


def _build_validation_fold(
    *,
    fold_index: int,
    start_index: int,
    train_window: int,
    test_window: int,
    observations: Sequence[_ObservationMarker],
    strategy_selection: Mapping[str, Any],
) -> dict[str, Any]:
    train_start_index = start_index
    train_end_index = start_index + train_window - 1
    test_start_index = train_end_index + 1
    test_end_index = test_start_index + test_window - 1
    train_start = observations[train_start_index]
    train_end = observations[train_end_index]
    test_start = observations[test_start_index]
    test_end = observations[test_end_index]
    fold_id = _build_fold_id(
        fold_index=fold_index,
        train_start=train_start.label,
        train_end=train_end.label,
        test_start=test_start.label,
        test_end=test_end.label,
    )
    return {
        "fold_id": fold_id,
        "fold_index": fold_index,
        "state": "planned",
        "train_window": {
            "start_index": train_start_index,
            "end_index": train_end_index,
            "start_date": train_start.label,
            "end_date": train_end.label,
            "size": train_window,
        },
        "test_window": {
            "start_index": test_start_index,
            "end_index": test_end_index,
            "start_date": test_start.label,
            "end_date": test_end.label,
            "size": test_window,
        },
        "strategy_selection": copy.deepcopy(dict(strategy_selection)),
    }


def _build_fold_id(
    *,
    fold_index: int,
    train_start: str,
    train_end: str,
    test_start: str,
    test_end: str,
) -> str:
    return (
        f"wf_oos_fold_{fold_index:04d}"
        f"_train_{_slug_window_bound(train_start)}_{_slug_window_bound(train_end)}"
        f"_test_{_slug_window_bound(test_start)}_{_slug_window_bound(test_end)}"
    )


def _slug_window_bound(value: str) -> str:
    slug = "".join(char.lower() for char in str(value) if char.isalnum())
    return slug or "unknown"


def _strategy_selection_placeholder(strategy_id: str) -> dict[str, Any]:
    return {
        "state": "diagnostic_only_placeholder",
        "selected_strategy_id": str(strategy_id),
        "selection_rule": "reuse_input_strategy_without_optimizer_search",
        "candidate_count": 1,
        "optimizer_executed": False,
        "parameter_sweep_executed": False,
        "portfolio_allocation_backtest_executed": False,
        "winner_selection_executed": False,
    }


def _empty_oos_result_summary(state: str, metric_keys: Sequence[str]) -> dict[str, Any]:
    return {
        "state": state,
        "completed_fold_count": 0,
        "missing_result_fold_count": 0,
        "metric_keys": list(metric_keys),
        "metric_aggregates": {},
    }


def _build_reproducibility_metadata(
    *,
    config: Mapping[str, Any],
    dataset_id: str | None,
    run_id: str | int | None,
    observation_count: int,
) -> dict[str, Any]:
    config_payload = copy.deepcopy(dict(config))
    serialized_config = json.dumps(config_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "contract_version": WALK_FORWARD_OOS_CONTRACT_VERSION,
        "dataset_id": dataset_id,
        "run_id": run_id,
        "observation_count": observation_count,
        "input_ordering": "ascending_observation_date_then_source_index",
        "fold_ordering": "fold_index_ascending",
        "fold_id_policy": "stable_from_window_bounds",
        "config": config_payload,
        "config_hash_sha256": hashlib.sha256(serialized_config.encode("utf-8")).hexdigest(),
    }


def _augment_result_reproducibility(reproducibility: Any) -> dict[str, Any]:
    payload = copy.deepcopy(dict(reproducibility or {})) if isinstance(reproducibility, Mapping) else {}
    payload.setdefault("contract_version", WALK_FORWARD_OOS_CONTRACT_VERSION)
    payload.setdefault("fold_ordering", "fold_index_ascending")
    payload.setdefault("fold_id_policy", "stable_from_window_bounds")
    payload["result_ordering"] = "fold_index_ascending"
    return payload


def _normalize_fold_results(
    fold_results: Sequence[Mapping[str, Any]] | Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    if isinstance(fold_results, Mapping):
        if "fold_id" in fold_results:
            items = [copy.deepcopy(dict(fold_results))]
        else:
            items = []
            for fold_id, result in fold_results.items():
                if isinstance(result, Mapping):
                    item = copy.deepcopy(dict(result))
                    item.setdefault("fold_id", str(fold_id))
                    items.append(item)
    else:
        items = [copy.deepcopy(dict(item or {})) for item in list(fold_results or [])]

    results_by_fold_id: dict[str, dict[str, Any]] = {}
    for item in items:
        fold_id = item.get("fold_id")
        if fold_id:
            results_by_fold_id[str(fold_id)] = item
    return results_by_fold_id


def _extract_metric_snapshot(metrics: Any, metric_keys: Sequence[str]) -> dict[str, float]:
    if not isinstance(metrics, Mapping):
        return {}
    snapshot: dict[str, float] = {}
    for key in metric_keys:
        value = metrics.get(key)
        if isinstance(value, bool) or value is None:
            continue
        try:
            snapshot[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return snapshot


def _aggregate_metric_snapshots(
    snapshots: Sequence[Mapping[str, float]],
    metric_keys: Sequence[str],
) -> dict[str, dict[str, float | int]]:
    aggregates: dict[str, dict[str, float | int]] = {}
    for key in metric_keys:
        values = [
            float(snapshot[key])
            for snapshot in snapshots
            if key in snapshot and not isinstance(snapshot.get(key), bool)
        ]
        if not values:
            continue
        aggregates[str(key)] = {
            "count": len(values),
            "min": round(min(values), 6),
            "max": round(max(values), 6),
            "mean": round(sum(values) / len(values), 6),
        }
    return aggregates
