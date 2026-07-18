# -*- coding: utf-8 -*-
"""Canonical registry and request gate for rule-backtest execution models."""

from __future__ import annotations

import math
import re
from typing import Any, Mapping

DEFAULT_RULE_BACKTEST_EXECUTION_MODEL_VERSION = "v1"
CURRENT_RULE_BACKTEST_EXECUTION_MODEL_VERSION = DEFAULT_RULE_BACKTEST_EXECUTION_MODEL_VERSION
CURRENT_RULE_BACKTEST_EXECUTION_MODEL_ID = "rule_backtest_default_execution_model_v1"
PERIODIC_RULE_BACKTEST_EXECUTION_MODEL_ID = "rule_backtest_periodic_execution_model_v1"
FUTURE_RULE_BACKTEST_EXECUTION_MODEL_ID = "rule_backtest_default_execution_model_v2"
UNSUPPORTED_EXECUTION_MODEL_ERROR = "unsupported_execution_model"

_SUPPORTED_VERSIONS = ("v1",)
_SUPPORTED_MODEL_IDS = {
    CURRENT_RULE_BACKTEST_EXECUTION_MODEL_ID: "v1",
    PERIODIC_RULE_BACKTEST_EXECUTION_MODEL_ID: "v1",
}
_KNOWN_MODEL_IDS = {
    **_SUPPORTED_MODEL_IDS,
    FUTURE_RULE_BACKTEST_EXECUTION_MODEL_ID: "v2",
}
_REQUEST_VERSION_KEYS = (
    "version",
    "modelVersion",
    "executionModelVersion",
    "execution_model_version",
)
_REQUEST_MODEL_ID_KEYS = (
    "model_id",
    "modelId",
    "id",
    "executionModelId",
    "execution_model_id",
)
_ALLOWED_REQUEST_KEYS = frozenset((*_REQUEST_VERSION_KEYS, *_REQUEST_MODEL_ID_KEYS))
_SAFE_REQUESTED_VERSION = re.compile(r"[^a-z0-9_.:-]+")


class RuleBacktestExecutionModelUnsupportedError(ValueError):
    """Stable fail-closed request error for unsupported execution models."""

    def __init__(
        self,
        requested_version: str,
        *,
        unsupported_fields: list[str] | None = None,
    ):
        self.requested_version = _sanitize_requested_version(requested_version)
        self.unsupported_fields = sorted(set(unsupported_fields or []))
        super().__init__(
            "Unsupported rule backtest execution model. Current supported execution model is v1."
        )

    def to_error_detail(self) -> dict[str, Any]:
        return {
            "error": UNSUPPORTED_EXECUTION_MODEL_ERROR,
            "message": str(self),
            "requested_version": self.requested_version,
            "supported_versions": list(_SUPPORTED_VERSIONS),
            "unsupported_fields": list(self.unsupported_fields),
        }


def _sanitize_requested_version(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "unknown"
    text = _SAFE_REQUESTED_VERSION.sub("_", text)[:48]
    return text or "unknown"


def _request_mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _single_requested_value(payload: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    values = [payload.get(key) for key in keys if payload.get(key) not in (None, "")]
    if not values:
        return None
    normalized = {str(value).strip() for value in values}
    if len(normalized) != 1:
        raise RuleBacktestExecutionModelUnsupportedError("conflicting_request_fields")
    return values[0]


def _validate_request_payload(request_payload: Any) -> tuple[str | None, str | None]:
    if request_payload is None:
        return None, None
    if isinstance(request_payload, str):
        return _sanitize_requested_version(request_payload), None

    payload = _request_mapping(request_payload)
    if payload is None:
        raise RuleBacktestExecutionModelUnsupportedError("unknown")
    if not payload:
        return None, None

    unsupported_fields = sorted(str(key) for key in payload if key not in _ALLOWED_REQUEST_KEYS)
    requested_version_value = _single_requested_value(payload, _REQUEST_VERSION_KEYS)
    requested_model_id_value = _single_requested_value(payload, _REQUEST_MODEL_ID_KEYS)
    requested_version = (
        _sanitize_requested_version(requested_version_value)
        if requested_version_value not in (None, "")
        else None
    )
    requested_model_id = (
        str(requested_model_id_value).strip()
        if requested_model_id_value not in (None, "")
        else None
    )
    if unsupported_fields:
        raise RuleBacktestExecutionModelUnsupportedError(
            requested_version or _KNOWN_MODEL_IDS.get(requested_model_id or "", "unknown"),
            unsupported_fields=unsupported_fields,
        )
    if requested_model_id is not None:
        model_version = _KNOWN_MODEL_IDS.get(requested_model_id)
        if model_version is None:
            raise RuleBacktestExecutionModelUnsupportedError("unknown")
        if requested_version is not None and requested_version != model_version:
            raise RuleBacktestExecutionModelUnsupportedError(requested_version)
        requested_version = model_version
    return requested_version, requested_model_id


def _cost_configuration(
    *,
    fee_bps: float,
    slippage_bps: float,
    fee_bps_configured: bool | None,
    slippage_bps_configured: bool | None,
) -> dict[str, Any]:
    def _item(value: float, configured: bool | None) -> dict[str, Any]:
        amount = float(value)
        if not math.isfinite(amount) or amount < 0:
            raise RuleBacktestExecutionModelUnsupportedError("invalid_cost_configuration")
        if configured is False and amount != 0.0:
            raise RuleBacktestExecutionModelUnsupportedError("conflicting_cost_configuration")
        explicitly_configured = bool(configured) if configured is not None else amount != 0.0
        state = (
            "explicit_non_zero"
            if explicitly_configured and amount != 0.0
            else "explicit_zero" if explicitly_configured else "unspecified"
        )
        return {
            "state": state,
            "bps_per_side": amount,
            "omitted_policy": "no_cost_applied",
            "application": "filled_side_exactly_once",
        }

    return {
        "fee": _item(fee_bps, fee_bps_configured),
        "slippage": _item(slippage_bps, slippage_bps_configured),
    }


def _terminal_liquidation_policy() -> dict[str, Any]:
    return {
        "supported": True,
        "policy_id": "window_end_close_liquidation_v1",
        "event_type": "terminal_liquidation",
        "fill_timing": "window_end_bar_close",
        "fill_price_basis": "close",
        "reason": "window_end_policy",
        "ordinary_strategy_signal": False,
    }


def _build_execution_model(
    *,
    model_id: str,
    timeframe: str,
    fee_bps: float,
    slippage_bps: float,
    fee_bps_configured: bool | None,
    slippage_bps_configured: bool | None,
) -> dict[str, Any]:
    normalized_timeframe = str(timeframe or "").strip().lower()
    if normalized_timeframe != "daily":
        raise RuleBacktestExecutionModelUnsupportedError(
            normalized_timeframe or "missing_timeframe"
        )
    if model_id not in _SUPPORTED_MODEL_IDS:
        raise RuleBacktestExecutionModelUnsupportedError(
            _KNOWN_MODEL_IDS.get(model_id, "unknown")
        )
    cost_configuration = _cost_configuration(
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        fee_bps_configured=fee_bps_configured,
        slippage_bps_configured=slippage_bps_configured,
    )
    terminal_policy = _terminal_liquidation_policy()
    shared = {
        "model_id": model_id,
        "version": "v1",
        "timeframe": normalized_timeframe,
        "fee_model": "bps_per_side",
        "fee_bps_per_side": float(fee_bps),
        "slippage_model": "bps_per_side",
        "slippage_bps_per_side": float(slippage_bps),
        "cost_configuration": cost_configuration,
        "capabilities": {
            "partial_fills_supported": False,
            "missing_required_price_state": "unfilled",
            "terminal_liquidation_supported": True,
        },
        "terminal_liquidation": terminal_policy,
    }
    if model_id == PERIODIC_RULE_BACKTEST_EXECUTION_MODEL_ID:
        return {
            **shared,
            "signal_evaluation_timing": "scheduled_before_session_open",
            "entry_timing": "same_session_open",
            "exit_timing": "terminal_liquidation_event",
            "entry_fill_price_basis": "open",
            "exit_fill_price_basis": "close",
            "position_sizing": "scheduled_fixed_accumulation",
            "market_rules": {
                "trading_day_execution": "available_bars_only",
                "missing_required_fill_price": "unfilled",
                "window_end_position_handling": "terminal_liquidation_event",
            },
        }
    return {
        **shared,
        "signal_evaluation_timing": "bar_close",
        "entry_timing": "next_bar_open",
        "exit_timing": "next_bar_open",
        "entry_fill_price_basis": "open",
        "exit_fill_price_basis": "open",
        "position_sizing": "single_position_full_notional",
        "market_rules": {
            "trading_day_execution": "available_bars_only",
            "missing_required_fill_price": "unfilled",
            "window_end_position_handling": "terminal_liquidation_event",
        },
    }


def build_current_rule_backtest_execution_model_metadata() -> dict[str, Any]:
    return _build_execution_model(
        model_id=CURRENT_RULE_BACKTEST_EXECUTION_MODEL_ID,
        timeframe="daily",
        fee_bps=0.0,
        slippage_bps=0.0,
        fee_bps_configured=False,
        slippage_bps_configured=False,
    )


def build_periodic_rule_backtest_execution_model_metadata() -> dict[str, Any]:
    return _build_execution_model(
        model_id=PERIODIC_RULE_BACKTEST_EXECUTION_MODEL_ID,
        timeframe="daily",
        fee_bps=0.0,
        slippage_bps=0.0,
        fee_bps_configured=False,
        slippage_bps_configured=False,
    )


def build_current_rule_backtest_execution_model_semantics() -> dict[str, Any]:
    return {
        "engine_identity": "canonical_registered_rule_backtest_execution",
        "cost_realism": "configured_bps_with_explicit_presence_state",
        "institutional_execution_realism": False,
        "market_impact_model": "not_modelled",
        "spread_simulation": "not_modelled",
        "partial_fills_supported": False,
        "halt_limit_up_limit_down_model": "not_modelled",
        "tax_model": "not_modelled",
        "stamp_duty_model": "not_modelled",
        "volume_participation_cap": "unavailable",
        "point_in_time_universe_guarantee": "unavailable",
        "adjusted_data_guarantee": "unavailable",
        "provider_calls_required": False,
        "live_provider_calls_required": False,
        "diagnostic_only": True,
        "readiness_only": True,
        "decision_grade": False,
    }


def build_current_rule_backtest_execution_model_guardrails() -> dict[str, Any]:
    return {
        "winner_promotion": False,
        "optimizer_executed": False,
        "parameter_sweep_executed": False,
        "provider_calls_executed": False,
        "silent_runtime_semantic_change_allowed": False,
        "future_semantic_changes_require_new_version": True,
        "future_versions_must_be_additive": True,
    }


def _registry_model_entry(model: Mapping[str, Any], *, posture: str) -> dict[str, Any]:
    return {
        **dict(model),
        "supported": True,
        "executable": True,
        "availability": "available",
        "posture": posture,
        "diagnostic_only": True,
        "readiness_only": True,
        "decision_grade": False,
        "provider_calls_required": False,
        "live_provider_calls_required": False,
    }


def build_rule_backtest_execution_model_registry_metadata() -> dict[str, Any]:
    default_model = build_current_rule_backtest_execution_model_metadata()
    periodic_model = build_periodic_rule_backtest_execution_model_metadata()
    return {
        "registry_version": "v2",
        "current_version": CURRENT_RULE_BACKTEST_EXECUTION_MODEL_VERSION,
        "default_version": DEFAULT_RULE_BACKTEST_EXECUTION_MODEL_VERSION,
        "default_model_id": CURRENT_RULE_BACKTEST_EXECUTION_MODEL_ID,
        "supported_versions": list(_SUPPORTED_VERSIONS),
        "default_model": default_model,
        "models": {
            CURRENT_RULE_BACKTEST_EXECUTION_MODEL_ID: _registry_model_entry(
                default_model,
                posture="current_default",
            ),
            PERIODIC_RULE_BACKTEST_EXECUTION_MODEL_ID: _registry_model_entry(
                periodic_model,
                posture="strategy_selected",
            ),
            FUTURE_RULE_BACKTEST_EXECUTION_MODEL_ID: {
                "model_id": FUTURE_RULE_BACKTEST_EXECUTION_MODEL_ID,
                "version": "v2",
                "supported": False,
                "executable": False,
                "availability": "unavailable",
                "posture": "future_fail_closed",
                "failure_policy": "fail_closed_before_execution",
                "diagnostic_only": True,
                "readiness_only": True,
                "decision_grade": False,
                "provider_calls_required": False,
                "live_provider_calls_required": False,
            },
        },
        "guardrails": {
            "unsupported_versions_fail_closed": True,
            "unsupported_versions_silently_downgraded": False,
            "unsupported_assumptions_fail_closed": True,
            "engine_math_changed": True,
            "fill_cost_model_changed": False,
            "fill_state_model_changed": True,
            "stored_result_semantics_changed": True,
            "provider_calls_executed": False,
            "decision_grade": False,
        },
    }


def validate_rule_backtest_execution_model_request(request_payload: Any) -> None:
    requested_version, _requested_model_id = _validate_request_payload(request_payload)
    if requested_version not in (None, DEFAULT_RULE_BACKTEST_EXECUTION_MODEL_VERSION):
        raise RuleBacktestExecutionModelUnsupportedError(requested_version)


def validate_rule_backtest_strategy_execution_contract(
    *,
    strategy_type: str,
    strategy_spec: Any,
    execution_model: Mapping[str, Any],
) -> None:
    """Reject strategy-embedded execution values that conflict with the registry."""

    if not isinstance(strategy_spec, Mapping) or not strategy_spec:
        return

    model_id = str(execution_model.get("model_id") or "").strip()
    if model_id not in _SUPPORTED_MODEL_IDS:
        raise RuleBacktestExecutionModelUnsupportedError("unknown")

    fee_bps = float(execution_model["fee_bps_per_side"])
    slippage_bps = float(execution_model["slippage_bps_per_side"])
    periodic = str(strategy_type or "") == "periodic_accumulation"
    if periodic:
        expected_values: dict[tuple[str, ...], Any] = {
            ("timeframe",): "daily",
            ("schedule", "frequency"): "daily",
            ("schedule", "timing"): "session_open",
            ("entry", "side"): "buy",
            ("entry", "price_basis"): "open",
            ("exit", "policy"): "close_at_end",
            ("exit", "price_basis"): "close",
            ("position_behavior", "accumulate"): True,
            ("costs", "fee_bps"): fee_bps,
            ("costs", "slippage_bps"): slippage_bps,
        }
        allowed_block_keys = {
            "schedule": {"frequency", "timing"},
            "entry": {"side", "price_basis", "order"},
            "exit": {"policy", "price_basis"},
            "position_behavior": {"accumulate", "cash_policy"},
            "costs": {"fee_bps", "slippage_bps"},
        }
    else:
        expected_values = {
            ("timeframe",): "daily",
            ("execution", "frequency"): "daily",
            ("execution", "signal_timing"): "bar_close",
            ("execution", "fill_timing"): "next_bar_open",
            ("position_behavior", "direction"): "long_only",
            ("position_behavior", "entry_sizing"): "all_in",
            ("position_behavior", "max_positions"): 1,
            ("position_behavior", "pyramiding"): False,
            ("end_behavior", "policy"): "liquidate_at_end",
            ("end_behavior", "price_basis"): "close",
            ("costs", "fee_bps"): fee_bps,
            ("costs", "slippage_bps"): slippage_bps,
        }
        allowed_block_keys = {
            "execution": {"frequency", "signal_timing", "fill_timing"},
            "position_behavior": {
                "direction",
                "entry_sizing",
                "max_positions",
                "pyramiding",
            },
            "end_behavior": {"policy", "price_basis"},
            "costs": {"fee_bps", "slippage_bps"},
        }

    issues: list[str] = []
    material_blocks = {
        "execution",
        "schedule",
        "entry",
        "exit",
        "position_behavior",
        "end_behavior",
        "costs",
    }
    for block_name in sorted(material_blocks):
        if block_name not in strategy_spec:
            continue
        block = strategy_spec.get(block_name)
        if not isinstance(block, Mapping):
            issues.append(f"strategy_spec.{block_name}")
            continue
        allowed_keys = allowed_block_keys.get(block_name, set())
        issues.extend(
            f"strategy_spec.{block_name}.{key}"
            for key in sorted(set(block) - allowed_keys)
        )

    def _nested_value(path: tuple[str, ...]) -> tuple[bool, Any]:
        current: Any = strategy_spec
        for key in path:
            if not isinstance(current, Mapping) or key not in current:
                return False, None
            current = current[key]
        return True, current

    for path, expected in expected_values.items():
        present, actual = _nested_value(path)
        if not present:
            continue
        if isinstance(expected, bool):
            matches = isinstance(actual, bool) and actual is expected
        elif isinstance(expected, int):
            matches = isinstance(actual, int) and not isinstance(actual, bool) and actual == expected
        elif isinstance(expected, float):
            matches = (
                isinstance(actual, (int, float))
                and not isinstance(actual, bool)
                and math.isfinite(float(actual))
                and float(actual) == expected
            )
        else:
            matches = actual == expected
        if not matches:
            issues.append(f"strategy_spec.{'.'.join(path)}")

    if issues:
        raise RuleBacktestExecutionModelUnsupportedError(
            str(execution_model.get("version") or "unknown"),
            unsupported_fields=issues,
        )


def audit_rule_backtest_execution_model_evidence(
    evidence: Any,
) -> list[str]:
    """Return deterministic reasons why stored execution evidence is not canonical."""

    if not isinstance(evidence, Mapping) or not evidence:
        return ["missing.execution_model"]

    payload = dict(evidence)
    model_id = str(payload.get("model_id") or "").strip()
    if not model_id:
        return ["missing.model_id"]
    if model_id not in _SUPPORTED_MODEL_IDS:
        return ["mismatch.model_id"]

    cost_configuration = payload.get("cost_configuration")
    cost_configuration = (
        dict(cost_configuration) if isinstance(cost_configuration, Mapping) else {}
    )
    fee_payload = cost_configuration.get("fee")
    slippage_payload = cost_configuration.get("slippage")
    fee_configuration = dict(fee_payload) if isinstance(fee_payload, Mapping) else {}
    slippage_configuration = (
        dict(slippage_payload) if isinstance(slippage_payload, Mapping) else {}
    )
    required_template = _build_execution_model(
        model_id=model_id,
        timeframe="daily",
        fee_bps=0.0,
        slippage_bps=0.0,
        fee_bps_configured=False,
        slippage_bps_configured=False,
    )

    issues: list[str] = []

    def _collect_missing(expected: Mapping[str, Any], actual: Mapping[str, Any], prefix: str = "") -> None:
        for key, expected_value in expected.items():
            path = f"{prefix}.{key}" if prefix else key
            if key not in actual or actual.get(key) is None:
                issues.append(f"missing.{path}")
                continue
            if isinstance(expected_value, Mapping):
                actual_value = actual.get(key)
                if not isinstance(actual_value, Mapping):
                    issues.append(f"mismatch.{path}")
                    continue
                _collect_missing(expected_value, actual_value, path)

    _collect_missing(required_template, payload)
    if issues:
        return sorted(set(issues))

    configuration_states = {"unspecified", "explicit_zero", "explicit_non_zero"}
    fee_state = str(fee_configuration.get("state") or "")
    slippage_state = str(slippage_configuration.get("state") or "")
    if fee_state not in configuration_states:
        issues.append("mismatch.cost_configuration.fee.state")
    if slippage_state not in configuration_states:
        issues.append("mismatch.cost_configuration.slippage.state")
    if issues:
        return sorted(set(issues))

    try:
        expected = _build_execution_model(
            model_id=model_id,
            timeframe=str(payload["timeframe"]),
            fee_bps=float(payload["fee_bps_per_side"]),
            slippage_bps=float(payload["slippage_bps_per_side"]),
            fee_bps_configured=fee_state != "unspecified",
            slippage_bps_configured=slippage_state != "unspecified",
        )
    except (TypeError, ValueError, RuleBacktestExecutionModelUnsupportedError):
        return ["mismatch.cost_configuration"]

    def _compare(expected_value: Any, actual_value: Any, path: str) -> None:
        if isinstance(expected_value, Mapping):
            if not isinstance(actual_value, Mapping):
                issues.append(f"mismatch.{path}")
                return
            unexpected = sorted(set(actual_value) - set(expected_value))
            issues.extend(
                f"unsupported.{path + '.' if path else ''}{key}"
                for key in unexpected
            )
            for key, nested_expected in expected_value.items():
                _compare(
                    nested_expected,
                    actual_value.get(key),
                    f"{path}.{key}" if path else key,
                )
            return
        if actual_value != expected_value:
            issues.append(f"mismatch.{path}")

    _compare(expected, payload, "")
    return sorted(set(issues))


def resolve_rule_backtest_execution_model_request(
    request_payload: Any,
    *,
    strategy_type: str = "rule_conditions",
    timeframe: str = "daily",
    fee_bps: float = 0.0,
    slippage_bps: float = 0.0,
    fee_bps_configured: bool | None = None,
    slippage_bps_configured: bool | None = None,
) -> dict[str, Any]:
    requested_version, requested_model_id = _validate_request_payload(request_payload)
    if requested_version not in (None, DEFAULT_RULE_BACKTEST_EXECUTION_MODEL_VERSION):
        raise RuleBacktestExecutionModelUnsupportedError(requested_version)

    selected_model_id = (
        PERIODIC_RULE_BACKTEST_EXECUTION_MODEL_ID
        if str(strategy_type or "rule_conditions") == "periodic_accumulation"
        else CURRENT_RULE_BACKTEST_EXECUTION_MODEL_ID
    )
    if requested_model_id is not None and requested_model_id != selected_model_id:
        raise RuleBacktestExecutionModelUnsupportedError(
            _KNOWN_MODEL_IDS.get(requested_model_id, "unknown")
        )

    execution_model = _build_execution_model(
        model_id=selected_model_id,
        timeframe=timeframe,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        fee_bps_configured=fee_bps_configured,
        slippage_bps_configured=slippage_bps_configured,
    )
    return {
        "requested_version": requested_version,
        "requested_model_id": requested_model_id,
        "resolved_version": DEFAULT_RULE_BACKTEST_EXECUTION_MODEL_VERSION,
        "model_id": selected_model_id,
        "supported": True,
        "executable": True,
        "execution_model": execution_model,
    }
