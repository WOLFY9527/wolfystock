# -*- coding: utf-8 -*-
"""Registry and request gate for rule-backtest execution models."""

from __future__ import annotations

import re
from typing import Any, Mapping

DEFAULT_RULE_BACKTEST_EXECUTION_MODEL_VERSION = "v1"
CURRENT_RULE_BACKTEST_EXECUTION_MODEL_VERSION = DEFAULT_RULE_BACKTEST_EXECUTION_MODEL_VERSION
CURRENT_RULE_BACKTEST_EXECUTION_MODEL_ID = "rule_backtest_default_execution_model_v1"
UNSUPPORTED_EXECUTION_MODEL_ERROR = "unsupported_execution_model"
_SUPPORTED_VERSIONS = ("v1",)
_SUPPORTED_MODEL_IDS = {CURRENT_RULE_BACKTEST_EXECUTION_MODEL_ID: "v1"}
_SAFE_REQUESTED_VERSION = re.compile(r"[^a-z0-9_.:-]+")


class RuleBacktestExecutionModelUnsupportedError(ValueError):
    """Stable fail-closed request error for unsupported execution models."""

    def __init__(self, requested_version: str):
        self.requested_version = _sanitize_requested_version(requested_version)
        super().__init__("Unsupported rule backtest execution model. Current supported execution model is v1.")

    def to_error_detail(self) -> dict[str, Any]:
        return {
            "error": UNSUPPORTED_EXECUTION_MODEL_ERROR,
            "message": str(self),
            "requested_version": self.requested_version,
            "supported_versions": list(_SUPPORTED_VERSIONS),
        }


def _sanitize_requested_version(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "unknown"
    text = _SAFE_REQUESTED_VERSION.sub("_", text)[:48]
    return text or "unknown"


def _request_mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _requested_version_from_mapping(payload: Mapping[str, Any]) -> str | None:
    for key in ("version", "modelVersion", "executionModelVersion", "execution_model_version"):
        raw_value = payload.get(key)
        if raw_value:
            return _sanitize_requested_version(raw_value)

    for key in ("model_id", "modelId", "id", "executionModelId", "execution_model_id"):
        model_id = str(payload.get(key) or "").strip()
        if not model_id:
            continue
        if model_id in _SUPPORTED_MODEL_IDS:
            return _SUPPORTED_MODEL_IDS[model_id]
        if model_id == "rule_backtest_default_execution_model_v2":
            return "v2"
        return "unknown"
    return None


def build_current_rule_backtest_execution_model_metadata() -> dict[str, Any]:
    return {
        "model_id": CURRENT_RULE_BACKTEST_EXECUTION_MODEL_ID,
        "version": CURRENT_RULE_BACKTEST_EXECUTION_MODEL_VERSION,
        "timeframe": "daily",
        "signal_evaluation_timing": "bar_close",
        "entry_timing": "next_bar_open",
        "exit_timing": "next_bar_open",
        "entry_fill_price_basis": "open",
        "exit_fill_price_basis": "open",
        "position_sizing": "single_position_full_notional",
        "fee_model": "bps_per_side",
        "fee_bps_per_side": 0.0,
        "slippage_model": "bps_per_side",
        "slippage_bps_per_side": 0.0,
        "market_rules": {
            "trading_day_execution": "available_bars_only",
            "terminal_bar_fill_fallback": "same_bar_close",
            "window_end_position_handling": "force_flatten",
        },
    }


def build_current_rule_backtest_execution_model_semantics() -> dict[str, Any]:
    return {
        "engine_identity": "existing_rule_backtest_behavior",
        "cost_realism": "baseline_bps_assumptions_only_when_present",
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


def build_rule_backtest_execution_model_registry_metadata() -> dict[str, Any]:
    default_model = build_current_rule_backtest_execution_model_metadata()
    return {
        "registry_version": "v1",
        "current_version": CURRENT_RULE_BACKTEST_EXECUTION_MODEL_VERSION,
        "default_version": DEFAULT_RULE_BACKTEST_EXECUTION_MODEL_VERSION,
        "supported_versions": list(_SUPPORTED_VERSIONS),
        "default_model": default_model,
        "models": {
            "v1": {
                "model_id": CURRENT_RULE_BACKTEST_EXECUTION_MODEL_ID,
                "version": "v1",
                "supported": True,
                "executable": True,
                "availability": "available",
                "posture": "current_default",
                "diagnostic_only": True,
                "readiness_only": True,
                "decision_grade": False,
                "provider_calls_required": False,
                "live_provider_calls_required": False,
                "description": "Current deterministic rule backtest execution model.",
            },
            "v2": {
                "model_id": "rule_backtest_default_execution_model_v2",
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
                "description": "Reserved future execution model; not executable in this backend.",
            },
        },
        "guardrails": {
            "unsupported_versions_fail_closed": True,
            "unsupported_versions_silently_downgraded": False,
            "engine_math_changed": False,
            "fill_cost_model_changed": False,
            "stored_result_semantics_changed": False,
            "provider_calls_executed": False,
            "decision_grade": False,
        },
    }


def resolve_rule_backtest_execution_model_request(request_payload: Any) -> dict[str, Any]:
    requested_version: str | None
    if request_payload is None:
        requested_version = None
    elif isinstance(request_payload, str):
        requested_version = _sanitize_requested_version(request_payload)
    else:
        payload = _request_mapping(request_payload)
        if payload is None:
            requested_version = "unknown"
        elif not payload:
            requested_version = None
        else:
            requested_version = _requested_version_from_mapping(payload) or None

    if requested_version in (None, DEFAULT_RULE_BACKTEST_EXECUTION_MODEL_VERSION):
        return {
            "requested_version": requested_version,
            "resolved_version": DEFAULT_RULE_BACKTEST_EXECUTION_MODEL_VERSION,
            "model_id": CURRENT_RULE_BACKTEST_EXECUTION_MODEL_ID,
            "supported": True,
            "executable": True,
            "execution_model": build_current_rule_backtest_execution_model_metadata(),
        }

    raise RuleBacktestExecutionModelUnsupportedError(requested_version)
