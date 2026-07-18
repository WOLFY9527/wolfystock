# -*- coding: utf-8 -*-
"""Pure projection helpers for stored rule-backtest support/export payloads."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from typing import Any, Callable, Mapping, Sequence

from src.services.backtest_parameter_stability import build_parameter_stability_evidence_from_compare_summary
from src.services.backtest_walkforward_oos import build_walk_forward_oos_evidence_from_stored_robustness
from src.services.rule_backtest_execution_model_registry import (
    CURRENT_RULE_BACKTEST_EXECUTION_MODEL_VERSION,
    build_current_rule_backtest_execution_model_guardrails,
    build_current_rule_backtest_execution_model_metadata,
    build_current_rule_backtest_execution_model_semantics,
    build_rule_backtest_execution_model_registry_metadata,
)
from src.services.reason_code_vocabulary import classify_reason_codes

RULE_BACKTEST_EXECUTION_MODEL_METADATA_VERSION = CURRENT_RULE_BACKTEST_EXECUTION_MODEL_VERSION
RULE_BACKTEST_EXECUTION_MODEL_EXPORT_KIND = "rule_backtest_execution_model_metadata"
RULE_BACKTEST_OOS_PARAMETER_READINESS_VERSION = "v1"
RULE_BACKTEST_OOS_PARAMETER_READINESS_EXPORT_KIND = "rule_backtest_oos_parameter_readiness"
_RULE_BACKTEST_EXECUTION_MODEL_V1 = build_current_rule_backtest_execution_model_metadata()
_RULE_BACKTEST_EXECUTION_MODEL_V1_SEMANTICS = build_current_rule_backtest_execution_model_semantics()
_RULE_BACKTEST_EXECUTION_MODEL_V1_GUARDRAILS = build_current_rule_backtest_execution_model_guardrails()
_RULE_BACKTEST_OOS_PARAMETER_READINESS_GUARDRAILS = {
    "engine_reexecuted": False,
    "strategy_execution_count": 0,
    "optimizer_executed": False,
    "parameter_sweep_executed": False,
    "provider_calls_executed": False,
    "winner_promotion": False,
    "engine_math_changed": False,
}
_SUPPORT_EXPORT_RAW_MARKERS = (
    "synthetic_cache_key",
    "synthetic_provider_url",
    "synthetic_request_id",
    "synthetic_stack_trace",
    "synthetic_debug_reason",
    "synthetic_execution_trace_detail",
)
_SUPPORT_EXPORT_FORBIDDEN_TEXT_MARKERS = _SUPPORT_EXPORT_RAW_MARKERS + (
    "authorization",
    "bearer ",
    "cookie",
    "set-cookie",
    "session_id",
    "api_key",
    "access_token",
    "refresh_token",
    "password",
    "credential",
    "raw_provider_payload",
    "raw_payload",
    "provider_payload",
    "request_body",
    "response_body",
    "stack_trace",
    "traceback",
    "http://",
    "https://",
)
_SPREADSHEET_FORMULA_PREFIXES = {"=", "+", "-", "@"}
_SUPPORT_RUN_TIMING_KEYS = {
    "cancelled_at",
    "created_at",
    "failed_at",
    "started_at",
    "finished_at",
    "last_updated_at",
    "queue_duration_seconds",
    "run_duration_seconds",
}
_SUPPORT_RUN_DIAGNOSTICS_KEYS = {
    "current_status",
    "terminal_status",
    "reason_code",
    "message",
    "last_transition_at",
    "last_transition_message",
    "last_non_terminal_status",
}
_SUPPORT_ARTIFACT_AVAILABILITY_KEYS = {
    "version",
    "source",
    "completeness",
    "has_summary",
    "has_parsed_strategy",
    "has_metrics",
    "has_execution_model",
    "has_comparison",
    "has_trade_rows",
    "has_equity_curve",
    "has_execution_trace",
    "has_run_diagnostics",
    "has_run_timing",
}
_SUPPORT_READBACK_INTEGRITY_KEYS = {
    "version",
    "source",
    "completeness",
    "used_legacy_fallback",
    "used_live_storage_repair",
    "has_summary_storage_drift",
    "drift_domains",
    "missing_summary_fields",
    "integrity_level",
}
_SUPPORT_DATASET_MANIFEST_IDENTITY_KEYS = {
    "manifest_id",
    "content_hash",
    "schema_version",
    "state",
    "fail_closed",
}
_SUPPORT_RESULT_AUTHORITY_DOMAIN_NAMES = {
    "summary",
    "parsed_strategy",
    "metrics",
    "execution_model",
    "execution_assumptions_snapshot",
    "comparison",
    "replay_payload",
    "audit_rows",
    "daily_return_series",
    "exposure_curve",
    "trade_rows",
    "equity_curve",
    "execution_trace",
}
_SUPPORT_RESULT_AUTHORITY_DOMAIN_KEYS = {"source", "completeness", "state", "missing", "missing_kind"}
_TRACE_EXECUTION_MODEL_KEYS = {
    "model_id",
    "version",
    "timeframe",
    "signal_evaluation_timing",
    "entry_timing",
    "exit_timing",
    "entry_fill_price_basis",
    "exit_fill_price_basis",
    "position_sizing",
    "fee_model",
    "fee_bps_per_side",
    "slippage_model",
    "slippage_bps_per_side",
    "cost_configuration",
    "capabilities",
    "terminal_liquidation",
    "market_rules",
}
_TRACE_MARKET_RULE_KEYS = {
    "trading_day_execution",
    "missing_required_fill_price",
    "window_end_position_handling",
}
_TRACE_EXECUTION_ASSUMPTION_KEYS = {
    "summary_text",
    "timeframe",
    "indicator_price_basis",
    "signal_evaluation_timing",
    "entry_fill_timing",
    "exit_fill_timing",
    "default_fill_price_basis",
    "position_sizing",
    "fee_model",
    "fee_bps_per_side",
    "slippage_model",
    "slippage_bps_per_side",
    "benchmark_method",
    "benchmark_price_basis",
    "engine",
    "signal_timing",
    "fill_timing",
    "fill_price",
    "allow_same_day_exit",
    "allow_fractional_shares",
    "lot_size",
    "volume_participation_limit",
    "partial_fill_supported",
    "no_fill_supported",
    "open_missing_behavior",
    "terminal_position_behavior",
    "terminal_liquidation",
    "limit_up_down_handling",
    "halt_handling",
    "short_selling",
    "market_rules",
    "warnings",
    "fill_model",
}
_TRACE_FEE_MODEL_KEYS = {
    "type",
    "configuration_state",
    "commission_bps",
    "min_commission",
    "tax_bps",
    "sec_fee",
}
_TRACE_SLIPPAGE_MODEL_KEYS = {"type", "configuration_state", "slippage_bps"}
_TRACE_COST_CONFIGURATION_KEYS = {"fee", "slippage"}
_TRACE_COST_ITEM_KEYS = {"state", "bps_per_side", "omitted_policy", "application"}
_TRACE_CAPABILITY_KEYS = {
    "partial_fills_supported",
    "missing_required_price_state",
    "terminal_liquidation_supported",
}
_TRACE_TERMINAL_LIQUIDATION_KEYS = {
    "supported",
    "policy_id",
    "event_type",
    "fill_timing",
    "fill_price_basis",
    "reason",
    "ordinary_strategy_signal",
}
_TRACE_WARNING_KEYS = {"code", "severity", "message"}
_TRACE_BENCHMARK_SUMMARY_KEYS = {
    "label",
    "code",
    "method",
    "requested_mode",
    "resolved_mode",
    "normalized_base",
    "price_basis",
    "start_date",
    "end_date",
    "start_price",
    "end_price",
    "return_pct",
    "auto_resolved",
    "fallback_used",
    "unavailable_reason",
}
_TRACE_FALLBACK_KEYS = {"run_fallback", "trace_rebuilt", "provider_authority", "note"}
_TRACE_ROW_NESTED_KEYS = {
    "code",
    "applied",
    "authority",
    "note",
    "state",
    "severity",
    "message",
    "summary_text",
}


def stringify_execution_trace_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _starts_with_spreadsheet_formula_prefix(value: str) -> bool:
    for char in value:
        codepoint = ord(char)
        if codepoint <= 0x20 or 0x7F <= codepoint <= 0x9F:
            continue
        return char in _SPREADSHEET_FORMULA_PREFIXES
    return False


def _formula_safe_csv_cell_value(value: Any) -> Any:
    if isinstance(value, str) and _starts_with_spreadsheet_formula_prefix(value):
        return f"'{value}"
    return value


def _support_export_text_is_unsafe(value: Any) -> bool:
    text = str(value or "").lower()
    return any(marker in text for marker in _SUPPORT_EXPORT_FORBIDDEN_TEXT_MARKERS)


def _safe_export_scalar(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text or _support_export_text_is_unsafe(text):
            return None
        return text
    return None


def _safe_export_string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    result: list[str] = []
    for item in value:
        safe_item = _safe_export_scalar(item)
        if isinstance(safe_item, str) and safe_item:
            result.append(safe_item)
    return result


def _safe_export_mapping(
    value: Any,
    allowed_keys: set[str],
    *,
    list_keys: set[str] | None = None,
) -> dict[str, Any]:
    payload = _mapping_payload(value)
    list_keys = list_keys or set()
    result: dict[str, Any] = {}
    for key in allowed_keys:
        if key not in payload:
            continue
        if key in list_keys:
            result[key] = _safe_export_string_list(payload.get(key))
            continue
        result[key] = _safe_export_scalar(payload.get(key))
    return result


def _safe_export_nested_mapping(value: Any, allowed_keys: set[str]) -> dict[str, Any]:
    payload = _mapping_payload(value)
    result: dict[str, Any] = {}
    for key in allowed_keys:
        if key not in payload:
            continue
        safe_value = _safe_export_scalar(payload.get(key))
        if safe_value is not None:
            result[key] = safe_value
    return result


def _safe_trace_row_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _safe_export_nested_mapping(value, _TRACE_ROW_NESTED_KEYS)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        safe_items = [_safe_trace_row_value(item) for item in value]
        return [item for item in safe_items if item not in ({}, None, "")]
    return _safe_export_scalar(value)


def _safe_trace_export_section(value: Any, allowed_keys: set[str]) -> dict[str, Any]:
    payload = _mapping_payload(value)
    result: dict[str, Any] = {}
    for key in allowed_keys:
        if key not in payload:
            continue
        if key == "market_rules":
            result[key] = _safe_export_mapping(payload.get(key), _TRACE_MARKET_RULE_KEYS)
        elif key == "fee_model":
            result[key] = _safe_export_mapping(payload.get(key), _TRACE_FEE_MODEL_KEYS)
        elif key == "slippage_model":
            result[key] = _safe_export_mapping(payload.get(key), _TRACE_SLIPPAGE_MODEL_KEYS)
        elif key == "cost_configuration":
            cost_configuration = _mapping_payload(payload.get(key))
            result[key] = {
                item_key: _safe_export_mapping(
                    cost_configuration.get(item_key),
                    _TRACE_COST_ITEM_KEYS,
                )
                for item_key in _TRACE_COST_CONFIGURATION_KEYS
                if item_key in cost_configuration
            }
        elif key == "capabilities":
            result[key] = _safe_export_mapping(payload.get(key), _TRACE_CAPABILITY_KEYS)
        elif key == "terminal_liquidation":
            result[key] = _safe_export_mapping(
                payload.get(key),
                _TRACE_TERMINAL_LIQUIDATION_KEYS,
            )
        elif key == "warnings":
            result[key] = [
                _safe_export_mapping(item, _TRACE_WARNING_KEYS)
                for item in _list_payload(payload.get(key))
                if isinstance(item, Mapping)
            ]
        else:
            result[key] = _safe_export_scalar(payload.get(key))
    return result


def _safe_result_authority_domain(
    value: Any,
    *,
    include_missing: bool,
) -> dict[str, Any]:
    payload = _mapping_payload(value)
    allowed_keys = (
        _SUPPORT_RESULT_AUTHORITY_DOMAIN_KEYS
        if include_missing
        else {"source", "completeness", "state"}
    )
    result = _safe_export_mapping(
        payload,
        allowed_keys,
        list_keys={"missing"},
    )
    for key in ("source", "completeness", "state"):
        if key in allowed_keys and key not in result:
            result[key] = "unknown"
    if include_missing:
        result.setdefault("missing", [])
        result.setdefault("missing_kind", "fields")
    return result


def _safe_result_authority_payload(
    result_authority: Mapping[str, Any],
    *,
    include_missing: bool,
) -> dict[str, Any]:
    domains = _mapping_payload(result_authority.get("domains"))
    safe_domains: dict[str, Any] = {}
    for domain_name in _SUPPORT_RESULT_AUTHORITY_DOMAIN_NAMES:
        if domain_name not in domains:
            continue
        safe_domains[domain_name] = _safe_result_authority_domain(
            domains.get(domain_name),
            include_missing=include_missing,
        )
    return {
        "contract_version": _safe_export_scalar(result_authority.get("contract_version")),
        "read_mode": _safe_export_scalar(result_authority.get("read_mode")),
        "domains": safe_domains,
    }


def build_execution_trace_export_rows(
    execution_trace: Mapping[str, Any],
    trace_export_columns: Sequence[tuple[str, str]],
    *,
    action_formatter: Callable[[str], str],
) -> list[dict[str, str]]:
    rows = list(execution_trace.get("rows") or [])
    export_rows: list[dict[str, str]] = []
    for row in rows:
        export_row: dict[str, str] = {}
        for key, label in trace_export_columns:
            value = row.get(key)
            if key == "action_display":
                value = value or action_formatter(str(row.get("event_type") or row.get("action") or "hold"))
            safe_value = _safe_trace_row_value(value)
            export_row[label] = stringify_execution_trace_value(_formula_safe_csv_cell_value(safe_value))
        export_rows.append(export_row)
    return export_rows


def build_reproducibility_authority_summary(result_authority: Mapping[str, Any]) -> dict[str, Any]:
    return _safe_result_authority_payload(result_authority, include_missing=False)


def build_execution_assumptions_fingerprint(
    execution_assumptions_snapshot: Mapping[str, Any],
    execution_assumptions: Mapping[str, Any],
) -> dict[str, Any]:
    payload = _safe_trace_export_section(
        execution_assumptions_snapshot.get("payload") or execution_assumptions or {},
        _TRACE_EXECUTION_ASSUMPTION_KEYS,
    )
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "source": _safe_export_scalar(execution_assumptions_snapshot.get("source")),
        "completeness": _safe_export_scalar(execution_assumptions_snapshot.get("completeness")),
        "summary_text": _safe_export_scalar(payload.get("summary_text")),
        "hash_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest() if payload else None,
    }


def _mapping_payload(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, Mapping) else {}


def _text_or_unknown(value: Any) -> str:
    text = str(value or "").strip()
    if not text or _support_export_text_is_unsafe(text):
        return "unknown"
    return text


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [
        text
        for item in value
        if (text := str(item or "").strip()) and not _support_export_text_is_unsafe(text)
    ]


def _authority_allowed_value(data_quality: Mapping[str, Any]) -> bool | None:
    explicit = data_quality.get("authority_allowed")
    if isinstance(explicit, bool):
        return explicit

    if "source_authority_unknown" in _string_list(data_quality.get("authority_reason_codes")):
        return False

    status = _text_or_unknown(data_quality.get("authority_status")).lower()
    if status == "allowed":
        return True
    if status in {"degraded_fill_only", "rejected", "unknown"}:
        return False
    return None


def _degraded_fill_only_value(data_quality: Mapping[str, Any]) -> bool:
    explicit = data_quality.get("degraded_fill_only")
    if isinstance(explicit, bool):
        return explicit
    return _text_or_unknown(data_quality.get("authority_status")).lower() == "degraded_fill_only"


def _readiness_dataset_version(readiness: Mapping[str, Any]) -> Any:
    for key in ("dataset_version", "datasetVersion"):
        if readiness.get(key):
            return readiness.get(key)
    categories = _mapping_payload(readiness.get("categories"))
    reproducibility = _mapping_payload(categories.get("reproducibility"))
    details = _mapping_payload(reproducibility.get("details"))
    return details.get("dataset_version") or details.get("datasetVersion")


def _date_range_payload(data_quality: Mapping[str, Any], prefix: str) -> dict[str, Any]:
    start = data_quality.get(f"{prefix}_start") or data_quality.get(f"{prefix}_start_date")
    end = data_quality.get(f"{prefix}_end") or data_quality.get(f"{prefix}_end_date")
    return {"start": start, "end": end}


def _authority_reason_families(reason_codes: Sequence[str]) -> list[dict[str, Any]]:
    return [
        {
            "raw_code": item.raw_code,
            "family": item.family,
            "scope": item.scope,
        }
        for item in classify_reason_codes(reason_codes)
    ]


def build_dataset_lineage_manifest(run: Mapping[str, Any]) -> dict[str, Any] | None:
    data_quality = _mapping_payload(run.get("data_quality"))
    if not data_quality:
        return None

    readiness = _mapping_payload(
        run.get("professionalReadiness") or run.get("professional_readiness")
    )
    dataset_version = data_quality.get("dataset_version") or _readiness_dataset_version(readiness)
    authority_reason_codes = _string_list(data_quality.get("authority_reason_codes"))
    return {
        "source": _text_or_unknown(data_quality.get("source")),
        "provider": _text_or_unknown(data_quality.get("provider")),
        "authority_status": _text_or_unknown(data_quality.get("authority_status")),
        "authority_source_type": _text_or_unknown(data_quality.get("authority_source_type")),
        "authority_reason_codes": authority_reason_codes,
        "authority_reason_families": _authority_reason_families(authority_reason_codes),
        "authority_allowed": _authority_allowed_value(data_quality),
        "degraded_fill_only": _degraded_fill_only_value(data_quality),
        "requested_range": _date_range_payload(data_quality, "requested"),
        "actual_range": _date_range_payload(data_quality, "actual"),
        "bar_count": data_quality.get("bar_count"),
        "dataset_version": _text_or_unknown(dataset_version),
    }


def build_support_bundle_manifest(run: Mapping[str, Any]) -> dict[str, Any]:
    execution_trace = dict(run.get("execution_trace") or {})
    result_authority = dict(run.get("result_authority") or {})
    dataset_manifest = _mapping_payload(run.get("dataset_reproducibility_manifest"))
    manifest = {
        "manifest_version": "v1",
        "manifest_kind": "rule_backtest_support_bundle",
        "run": {
            "id": run.get("id"),
            "code": run.get("code"),
            "status": run.get("status"),
            "status_message": run.get("status_message"),
            "run_at": run.get("run_at"),
            "completed_at": run.get("completed_at"),
            "strategy_hash": run.get("strategy_hash"),
            "timeframe": run.get("timeframe"),
            "lookback_bars": run.get("lookback_bars"),
            "period_start": run.get("period_start"),
            "period_end": run.get("period_end"),
            "benchmark_mode": run.get("benchmark_mode"),
            "benchmark_code": run.get("benchmark_code"),
            "trade_count": run.get("trade_count"),
            "total_return_pct": run.get("total_return_pct"),
            "sharpe_ratio": run.get("sharpe_ratio"),
            "max_drawdown_pct": run.get("max_drawdown_pct"),
            "final_equity": run.get("final_equity"),
            "no_result_reason": run.get("no_result_reason"),
            "no_result_message": run.get("no_result_message"),
        },
        "run_timing": _safe_export_mapping(run.get("run_timing"), _SUPPORT_RUN_TIMING_KEYS),
        "run_diagnostics": _safe_export_mapping(
            run.get("run_diagnostics"),
            _SUPPORT_RUN_DIAGNOSTICS_KEYS,
        ),
        "artifact_availability": _safe_export_mapping(
            run.get("artifact_availability"),
            _SUPPORT_ARTIFACT_AVAILABILITY_KEYS,
        ),
        "readback_integrity": _safe_export_mapping(
            run.get("readback_integrity"),
            _SUPPORT_READBACK_INTEGRITY_KEYS,
            list_keys={"drift_domains", "missing_summary_fields"},
        ),
        "result_authority": _safe_result_authority_payload(result_authority, include_missing=True),
        "dataset_manifest_identity": _safe_export_mapping(
            run.get("dataset_manifest_identity"),
            _SUPPORT_DATASET_MANIFEST_IDENTITY_KEYS,
        ),
        "artifact_counts": {
            "status_history_count": len(list(run.get("status_history") or [])),
            "warning_count": len(list(run.get("warnings") or [])),
            "trade_rows_count": len(list(run.get("trades") or [])),
            "equity_curve_points": len(list(run.get("equity_curve") or [])),
            "audit_rows_count": len(list(run.get("audit_rows") or [])),
            "daily_return_series_count": len(list(run.get("daily_return_series") or [])),
            "exposure_curve_count": len(list(run.get("exposure_curve") or [])),
            "execution_trace_rows_count": len(list(execution_trace.get("rows") or [])),
        },
    }
    dataset_lineage = build_dataset_lineage_manifest(run)
    if dataset_lineage is not None:
        manifest["dataset_lineage"] = dataset_lineage
    if dataset_manifest:
        manifest["dataset_reproducibility_manifest"] = dataset_manifest
    return manifest


def build_support_bundle_reproducibility_manifest(run: Mapping[str, Any]) -> dict[str, Any]:
    result_authority = dict(run.get("result_authority") or {})
    execution_assumptions_snapshot = dict(run.get("execution_assumptions_snapshot") or {})
    execution_assumptions = dict(run.get("execution_assumptions") or {})
    dataset_manifest = _mapping_payload(run.get("dataset_reproducibility_manifest"))
    manifest = {
        "manifest_version": "v1",
        "manifest_kind": "rule_backtest_reproducibility_manifest",
        "run": {
            "id": run.get("id"),
            "code": run.get("code"),
            "status": run.get("status"),
            "run_at": run.get("run_at"),
            "completed_at": run.get("completed_at"),
            "strategy_hash": run.get("strategy_hash"),
            "timeframe": run.get("timeframe"),
            "lookback_bars": run.get("lookback_bars"),
            "period_start": run.get("period_start"),
            "period_end": run.get("period_end"),
            "benchmark_mode": run.get("benchmark_mode"),
            "benchmark_code": run.get("benchmark_code"),
        },
        "run_diagnostics": _safe_export_mapping(
            run.get("run_diagnostics"),
            _SUPPORT_RUN_DIAGNOSTICS_KEYS,
        ),
        "run_timing": _safe_export_mapping(run.get("run_timing"), _SUPPORT_RUN_TIMING_KEYS),
        "artifact_availability": _safe_export_mapping(
            run.get("artifact_availability"),
            _SUPPORT_ARTIFACT_AVAILABILITY_KEYS,
        ),
        "readback_integrity": _safe_export_mapping(
            run.get("readback_integrity"),
            _SUPPORT_READBACK_INTEGRITY_KEYS,
            list_keys={"drift_domains", "missing_summary_fields"},
        ),
        "execution_assumptions_fingerprint": build_execution_assumptions_fingerprint(
            execution_assumptions_snapshot=execution_assumptions_snapshot,
            execution_assumptions=execution_assumptions,
        ),
        "result_authority": build_reproducibility_authority_summary(result_authority),
        "dataset_manifest_identity": _safe_export_mapping(
            run.get("dataset_manifest_identity"),
            _SUPPORT_DATASET_MANIFEST_IDENTITY_KEYS,
        ),
    }
    dataset_lineage = build_dataset_lineage_manifest(run)
    if dataset_lineage is not None:
        manifest["dataset_lineage"] = dataset_lineage
    if dataset_manifest:
        manifest["dataset_reproducibility_manifest"] = dataset_manifest
    return manifest


REGIME_ATTRIBUTION_READINESS_GAP_REASONS: list[dict[str, str]] = [
    {
        "code": "missing_date_level_market_regime_labels",
        "message": "Date-level market regime labels are not stored on the run.",
    },
    {
        "code": "missing_regime_source_version",
        "message": "No regime source or version is stored for reproducible attribution.",
    },
    {
        "code": "missing_trade_to_regime_join_policy",
        "message": "No policy exists for joining trades to market regime labels.",
    },
    {
        "code": "missing_daily_pnl_allocation_policy",
        "message": "No policy exists for allocating daily PnL across regimes.",
    },
    {
        "code": "missing_holding_period_allocation_rules",
        "message": "No rules exist for assigning multi-day holding periods to regimes.",
    },
]


def _list_payload(value: Any) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return list(value)


def _summary_payload(run: Mapping[str, Any]) -> dict[str, Any]:
    return _mapping_payload(run.get("summary"))


def _first_mapping_payload(*values: Any) -> dict[str, Any]:
    for value in values:
        payload = _mapping_payload(value)
        if payload:
            return payload
    return {}


def _availability_payload(
    *,
    available: bool,
    available_reason: str,
    missing_reason: str,
    **extra: Any,
) -> dict[str, Any]:
    payload = {
        "available": bool(available),
        "availabilityReason": available_reason if available else missing_reason,
    }
    payload.update(extra)
    return payload


def _domain_summary(result_authority: Mapping[str, Any], domain_name: str) -> dict[str, Any]:
    domains = _mapping_payload(result_authority.get("domains"))
    domain = _mapping_payload(domains.get(domain_name))
    if not domain:
        return {
            "available": False,
            "availabilityReason": f"{domain_name}_authority_missing",
        }

    state = _text_or_unknown(domain.get("state"))
    completeness = _text_or_unknown(domain.get("completeness"))
    source = _text_or_unknown(domain.get("source"))
    available = state == "available" and completeness != "unavailable" and source != "unavailable"
    return _availability_payload(
        available=available,
        available_reason=f"{domain_name}_authority_available",
        missing_reason=f"{domain_name}_authority_unavailable",
        source=source,
        completeness=completeness,
        state=state,
    )


def _trades_evidence(run: Mapping[str, Any], result_authority: Mapping[str, Any]) -> dict[str, Any]:
    trades = _list_payload(run.get("trades"))
    trade_count = len(trades)
    if not trade_count:
        declared_count = run.get("trade_count")
        try:
            trade_count = int(declared_count or 0)
        except (TypeError, ValueError):
            trade_count = 0
    domain = _domain_summary(result_authority, "trade_rows")
    available = bool(_list_payload(run.get("trades")))
    return _availability_payload(
        available=available,
        available_reason="stored_trade_rows_present",
        missing_reason="stored_trade_rows_missing",
        count=len(_list_payload(run.get("trades"))),
        declaredCount=trade_count,
        authority=domain,
    )


def _daily_audit_evidence(run: Mapping[str, Any], result_authority: Mapping[str, Any]) -> dict[str, Any]:
    audit_rows = _list_payload(run.get("audit_rows"))
    daily_return_series = _list_payload(run.get("daily_return_series"))
    rows_with_daily_pnl = sum(
        1
        for row in audit_rows
        if isinstance(row, Mapping) and row.get("daily_pnl") is not None
    )
    return _availability_payload(
        available=bool(audit_rows),
        available_reason="stored_audit_rows_present",
        missing_reason="stored_audit_rows_missing",
        count=len(audit_rows),
        rowsWithDailyPnl=rows_with_daily_pnl,
        dailyReturnSeriesCount=len(daily_return_series),
        authority=_domain_summary(result_authority, "replay_payload"),
    )


def _drawdown_bucket_evidence(run: Mapping[str, Any]) -> dict[str, Any]:
    summary = _summary_payload(run)
    drawdown_payload = _first_mapping_payload(
        run.get("drawdown_regime_attribution"),
        summary.get("drawdown_regime_attribution"),
    )
    if not drawdown_payload:
        return _availability_payload(
            available=False,
            available_reason="stored_drawdown_bucket_summary_present",
            missing_reason="stored_drawdown_bucket_summary_missing",
            state="unavailable",
        )

    bucket_counts = _mapping_payload(drawdown_payload.get("bucket_counts"))
    contribution_summaries = _mapping_payload(drawdown_payload.get("contribution_summaries"))
    classified_rows = _mapping_payload(contribution_summaries.get("classified_rows"))
    state = _text_or_unknown(drawdown_payload.get("state"))
    available = state != "unavailable" and bool(bucket_counts)
    return _availability_payload(
        available=available,
        available_reason="stored_drawdown_bucket_summary_present",
        missing_reason="stored_drawdown_bucket_summary_unavailable",
        source=_text_or_unknown(drawdown_payload.get("source")),
        state=state,
        bucketCount=len(bucket_counts),
        classifiedRows=dict(classified_rows),
        causalityNote=contribution_summaries.get("causality_note"),
    )


def _robustness_support_evidence(run: Mapping[str, Any]) -> dict[str, Any]:
    summary = _summary_payload(run)
    robustness_payload = _first_mapping_payload(
        summary.get("robustness_analysis"),
        run.get("robustness_analysis"),
    )
    artifact_availability = _first_mapping_payload(
        run.get("artifact_availability"),
        summary.get("artifact_availability"),
    )
    readback_integrity = _first_mapping_payload(
        run.get("readback_integrity"),
        summary.get("readback_integrity"),
    )
    return _availability_payload(
        available=bool(robustness_payload or artifact_availability or readback_integrity),
        available_reason="stored_support_artifacts_present",
        missing_reason="stored_support_artifacts_missing",
        robustnessAvailable=bool(robustness_payload),
        robustnessState=robustness_payload.get("state"),
        robustnessSource=robustness_payload.get("source"),
        artifactAvailabilityAvailable=bool(artifact_availability),
        readbackIntegrityAvailable=bool(readback_integrity),
        readbackIntegrityLevel=readback_integrity.get("integrity_level"),
    )


def _dataset_lineage_evidence(run: Mapping[str, Any]) -> dict[str, Any]:
    dataset_lineage = build_dataset_lineage_manifest(run)
    if dataset_lineage is None:
        return _availability_payload(
            available=False,
            available_reason="dataset_lineage_present",
            missing_reason="dataset_lineage_missing",
        )
    return _availability_payload(
        available=True,
        available_reason="dataset_lineage_present",
        missing_reason="dataset_lineage_missing",
        lineage=dataset_lineage,
    )


def _result_authority_evidence(result_authority: Mapping[str, Any]) -> dict[str, Any]:
    domains = _mapping_payload(result_authority.get("domains"))
    domain_states = {
        str(name): {
            "source": _mapping_payload(payload).get("source"),
            "completeness": _mapping_payload(payload).get("completeness"),
            "state": _mapping_payload(payload).get("state"),
        }
        for name, payload in domains.items()
    }
    return _availability_payload(
        available=bool(result_authority),
        available_reason="result_authority_present",
        missing_reason="result_authority_missing",
        contractVersion=result_authority.get("contract_version"),
        readMode=result_authority.get("read_mode"),
        domainStates=domain_states,
    )


def build_regime_attribution_readiness_export(run: Mapping[str, Any]) -> dict[str, Any]:
    """Build a bounded diagnostic readiness projection from stored run readback data."""

    result_authority = _mapping_payload(run.get("result_authority"))
    return {
        "exportKind": "rule_backtest_regime_attribution_readiness",
        "version": "v1",
        "runId": int(run.get("id") or 0),
        "code": run.get("code"),
        "status": run.get("status"),
        "timeframe": run.get("timeframe"),
        "period": {
            "start": run.get("period_start") or run.get("start_date"),
            "end": run.get("period_end") or run.get("end_date"),
        },
        "source": "stored_rule_backtest_readback_projection",
        "readMode": "stored_first",
        "storedFirst": True,
        "diagnosticOnly": True,
        "engineReexecuted": False,
        "mathChanged": False,
        "attributionEngineAvailable": False,
        "pnlCausalityAvailable": False,
        "runtimeEngineStatement": "not_a_runtime_attribution_engine",
        "mathSnapshot": {
            "trade_count": run.get("trade_count"),
            "total_return_pct": run.get("total_return_pct"),
            "max_drawdown_pct": run.get("max_drawdown_pct"),
            "win_rate_pct": run.get("win_rate_pct"),
            "final_equity": run.get("final_equity"),
        },
        "evidenceAvailability": {
            "trades": _trades_evidence(run, result_authority),
            "dailyAudit": _daily_audit_evidence(run, result_authority),
            "drawdownBucketSummary": _drawdown_bucket_evidence(run),
            "robustnessSupportArtifacts": _robustness_support_evidence(run),
            "datasetLineage": _dataset_lineage_evidence(run),
            "resultAuthority": _result_authority_evidence(result_authority),
        },
        "gapReasons": [dict(item) for item in REGIME_ATTRIBUTION_READINESS_GAP_REASONS],
        "limitations": [
            "diagnostic_readiness_projection_only",
            "not_a_runtime_attribution_engine",
            "no_market_regime_classification",
            "no_pnl_by_regime_allocation",
        ],
    }


def resolve_stored_robustness_evidence_payload(run: Mapping[str, Any]) -> dict[str, Any]:
    summary = dict(run.get("summary") or {}) if isinstance(run.get("summary"), dict) else {}
    summary_payload = summary.get("robustness_analysis")
    if isinstance(summary_payload, dict) and summary_payload:
        return _with_walk_forward_oos_evidence(summary_payload, run)

    run_payload = run.get("robustness_analysis")
    if isinstance(run_payload, dict) and run_payload:
        return _with_walk_forward_oos_evidence(run_payload, run)

    return {}


def _with_walk_forward_oos_evidence(
    robustness_payload: Mapping[str, Any],
    run: Mapping[str, Any],
) -> dict[str, Any]:
    payload = dict(robustness_payload)
    payload["walk_forward_oos_evidence"] = build_walk_forward_oos_evidence_from_stored_robustness(
        payload,
        run_metadata=run,
    )
    return payload


def build_support_export_index(run: Mapping[str, Any]) -> dict[str, Any]:
    resolved_run_id = int(run.get("id") or 0)
    trace_rows = list((dict(run.get("execution_trace") or {})).get("rows") or [])
    trace_available = bool(trace_rows)
    trace_reason = "execution_trace_rows_present" if trace_available else "execution_trace_rows_missing"
    robustness_evidence = resolve_stored_robustness_evidence_payload(run)
    robustness_available = bool(robustness_evidence)
    robustness_reason = (
        "stored_robustness_analysis_present"
        if robustness_available
        else "stored_robustness_analysis_missing"
    )
    return {
        "run_id": resolved_run_id,
        "status": str(run.get("status") or ""),
        "exports": [
            {
                "key": "support_bundle_manifest_json",
                "available": True,
                "availability_reason": "run_exists",
                "format": "json",
                "media_type": "application/json",
                "delivery_mode": "api",
                "endpoint_path": f"/api/v1/backtest/rule/runs/{resolved_run_id}/support-bundle-manifest",
                "payload_class": "compact",
            },
            {
                "key": "support_bundle_reproducibility_manifest_json",
                "available": True,
                "availability_reason": "run_exists",
                "format": "json",
                "media_type": "application/json",
                "delivery_mode": "api",
                "endpoint_path": f"/api/v1/backtest/rule/runs/{resolved_run_id}/support-bundle-reproducibility-manifest",
                "payload_class": "compact",
            },
            {
                "key": "execution_trace_json",
                "available": trace_available,
                "availability_reason": trace_reason,
                "format": "json",
                "media_type": "application/json",
                "delivery_mode": "api",
                "endpoint_path": f"/api/v1/backtest/rule/runs/{resolved_run_id}/execution-trace.json",
                "payload_class": "heavy",
            },
            {
                "key": "execution_trace_csv",
                "available": trace_available,
                "availability_reason": trace_reason,
                "format": "csv",
                "media_type": "text/csv",
                "delivery_mode": "api",
                "endpoint_path": f"/api/v1/backtest/rule/runs/{resolved_run_id}/execution-trace.csv",
                "payload_class": "heavy",
            },
            {
                "key": "robustness_evidence_json",
                "available": robustness_available,
                "availability_reason": robustness_reason,
                "format": "json",
                "media_type": "application/json",
                "delivery_mode": "api",
                "endpoint_path": f"/api/v1/backtest/rule/runs/{resolved_run_id}/robustness-evidence.json",
                "payload_class": "heavy",
            },
            {
                "key": "regime_attribution_readiness_json",
                "available": True,
                "availability_reason": "run_exists_readiness_projection_available",
                "format": "json",
                "media_type": "application/json",
                "delivery_mode": "api",
                "endpoint_path": f"/api/v1/backtest/rule/runs/{resolved_run_id}/regime-attribution-readiness.json",
                "payload_class": "compact",
            },
            {
                "key": "execution_model_metadata_json",
                "available": True,
                "availability_reason": "run_exists_execution_model_metadata_projection_available",
                "format": "json",
                "media_type": "application/json",
                "delivery_mode": "api",
                "endpoint_path": f"/api/v1/backtest/rule/runs/{resolved_run_id}/execution-model-metadata.json",
                "payload_class": "compact",
            },
            {
                "key": "oos_parameter_readiness_json",
                "available": True,
                "availability_reason": "run_exists_oos_parameter_readiness_projection_available",
                "format": "json",
                "media_type": "application/json",
                "delivery_mode": "api",
                "endpoint_path": f"/api/v1/backtest/rule/runs/{resolved_run_id}/oos-parameter-readiness.json",
                "payload_class": "compact",
            },
        ],
    }


def build_execution_model_metadata_export(run: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "export_kind": RULE_BACKTEST_EXECUTION_MODEL_EXPORT_KIND,
        "version": RULE_BACKTEST_EXECUTION_MODEL_METADATA_VERSION,
        "run_id": int(run.get("id") or 0),
        "code": run.get("code"),
        "status": run.get("status"),
        "timeframe": run.get("timeframe") or _RULE_BACKTEST_EXECUTION_MODEL_V1["timeframe"],
        "source": "stored_rule_backtest_execution_model_v1_projection",
        "read_mode": "stored_first_projection",
        "execution_model": dict(_RULE_BACKTEST_EXECUTION_MODEL_V1),
        "semantics": dict(_RULE_BACKTEST_EXECUTION_MODEL_V1_SEMANTICS),
        "guardrails": dict(_RULE_BACKTEST_EXECUTION_MODEL_V1_GUARDRAILS),
        "registry": build_rule_backtest_execution_model_registry_metadata(),
    }


def build_oos_parameter_readiness_export(
    run: Mapping[str, Any],
    *,
    compare_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    oos_readiness = _build_oos_readiness_section(run)
    parameter_readiness = _build_parameter_readiness_section(compare_payload)
    return {
        "export_kind": RULE_BACKTEST_OOS_PARAMETER_READINESS_EXPORT_KIND,
        "version": RULE_BACKTEST_OOS_PARAMETER_READINESS_VERSION,
        "run_id": int(run.get("id") or 0),
        "code": run.get("code"),
        "status": run.get("status"),
        "timeframe": run.get("timeframe"),
        "source": "stored_rule_backtest_support_projection",
        "read_mode": "stored_first",
        "stored_first": True,
        "diagnostic_only": True,
        "decision_grade": False,
        "overall_state": _combine_readiness_states(
            str(oos_readiness.get("state") or "unavailable"),
            str(parameter_readiness.get("state") or "unavailable"),
        ),
        "oos_readiness": oos_readiness,
        "parameter_readiness": parameter_readiness,
        "guardrails": dict(_RULE_BACKTEST_OOS_PARAMETER_READINESS_GUARDRAILS),
        "limitations": [
            "diagnostic_readiness_projection_only",
            "not_a_runtime_oos_or_parameter_stability_engine",
            "no_strategy_execution",
            "no_optimizer_execution",
            "no_parameter_sweep_execution",
            "no_winner_promotion",
            "no_provider_calls",
        ],
    }


def _build_oos_readiness_section(run: Mapping[str, Any]) -> dict[str, Any]:
    robustness_payload = resolve_stored_robustness_evidence_payload(run)
    oos_evidence = dict(robustness_payload.get("walk_forward_oos_evidence") or {}) if robustness_payload else {}
    if not oos_evidence:
        return {
            "state": "unavailable",
            "source": "stored_robustness_analysis_missing",
            "read_mode": "stored_first",
            "availability_reason": "stored_robustness_analysis_missing",
            "diagnostic_only": True,
            "decision_grade": False,
            "evidence": None,
        }

    evidence_state = str(oos_evidence.get("state") or "diagnostic_unavailable")
    return {
        "state": _normalize_readiness_state(evidence_state),
        "evidence_state": evidence_state,
        "source": oos_evidence.get("source") or "stored_robustness_analysis.walk_forward",
        "read_mode": oos_evidence.get("read_mode") or "stored_first",
        "availability_reason": _oos_availability_reason(evidence_state),
        "diagnostic_only": bool(oos_evidence.get("diagnostic_only", True)),
        "decision_grade": bool(oos_evidence.get("decision_grade", False)),
        "evidence": oos_evidence,
    }


def _build_parameter_readiness_section(compare_payload: Mapping[str, Any] | None) -> dict[str, Any]:
    evidence, projection_source = _resolve_parameter_readiness_evidence(compare_payload)
    if not evidence:
        return {
            "state": "unavailable",
            "source": "compare_summary_unavailable",
            "read_mode": "stored_first",
            "projection_source": "stored_first_no_compare_summary",
            "availability_reason": "stored_compare_summary_missing",
            "diagnostic_only": True,
            "decision_grade": False,
            "evidence": None,
        }

    evidence_state = str(evidence.get("state") or "diagnostic_unavailable")
    return {
        "state": _normalize_readiness_state(evidence_state),
        "evidence_state": evidence_state,
        "source": evidence.get("source") or "stored_compare_summary",
        "read_mode": evidence.get("read_mode") or "stored_first",
        "projection_source": projection_source,
        "availability_reason": _parameter_availability_reason(
            projection_source=projection_source,
            state=evidence_state,
        ),
        "diagnostic_only": bool(evidence.get("diagnostic_only", True)),
        "decision_grade": bool(evidence.get("decision_grade", False)),
        "evidence": evidence,
    }


def _resolve_parameter_readiness_evidence(
    compare_payload: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], str]:
    payload = dict(compare_payload or {})
    direct_evidence = payload.get("parameter_stability_evidence")
    if isinstance(direct_evidence, Mapping) and dict(direct_evidence):
        return dict(direct_evidence), "caller_supplied_parameter_stability_evidence"

    if _looks_like_compare_payload(payload):
        return (
            build_parameter_stability_evidence_from_compare_summary(payload),
            "caller_supplied_compare_summary",
        )

    return {}, "stored_first_no_compare_summary"


def _looks_like_compare_payload(payload: Mapping[str, Any]) -> bool:
    return any(
        key in payload
        for key in (
            "requested_run_ids",
            "resolved_run_ids",
            "missing_run_ids",
            "items",
            "parameter_comparison",
            "heatmap_projection",
        )
    )


def _normalize_readiness_state(state: str) -> str:
    normalized = str(state or "").strip().lower()
    if normalized == "available":
        return "available"
    if normalized == "partial":
        return "partial"
    return "unavailable"


def _combine_readiness_states(oos_state: str, parameter_state: str) -> str:
    states = {_normalize_readiness_state(oos_state), _normalize_readiness_state(parameter_state)}
    if states == {"available"}:
        return "available"
    if "available" in states or "partial" in states:
        return "partial"
    return "unavailable"


def _oos_availability_reason(state: str) -> str:
    normalized = _normalize_readiness_state(state)
    if normalized == "available":
        return "stored_walk_forward_oos_evidence_present"
    if normalized == "partial":
        return "stored_walk_forward_oos_evidence_partial"
    return "stored_walk_forward_oos_evidence_missing"


def _parameter_availability_reason(*, projection_source: str, state: str) -> str:
    normalized = _normalize_readiness_state(state)
    if normalized == "unavailable":
        if projection_source == "caller_supplied_parameter_stability_evidence":
            return "caller_supplied_parameter_stability_evidence_unavailable"
        if projection_source == "caller_supplied_compare_summary":
            return "caller_supplied_compare_summary_unavailable"
        return "stored_compare_summary_missing"
    if projection_source == "caller_supplied_parameter_stability_evidence":
        return "caller_supplied_parameter_stability_evidence_present"
    return "caller_supplied_compare_summary_present"


def build_execution_trace_export_json_payload(
    run: Mapping[str, Any],
    trace_export_columns: Sequence[tuple[str, str]],
    *,
    action_formatter: Callable[[str], str],
) -> dict[str, Any]:
    execution_trace = dict(run.get("execution_trace") or {})
    export_rows = build_execution_trace_export_rows(
        execution_trace,
        trace_export_columns,
        action_formatter=action_formatter,
    )
    if not export_rows:
        raise ValueError(f"Run {run.get('id')} has no audit rows to export.")

    return {
        "version": _safe_export_scalar(execution_trace.get("version")),
        "source": _safe_export_scalar(execution_trace.get("source")),
        "completeness": _safe_export_scalar(execution_trace.get("completeness")),
        "missing_fields": _safe_export_string_list(execution_trace.get("missing_fields")),
        "trace_rows": export_rows,
        "assumptions": _safe_trace_export_section(
            execution_trace.get("assumptions_defaults"),
            _TRACE_EXECUTION_ASSUMPTION_KEYS,
        ),
        "execution_model": _safe_trace_export_section(
            execution_trace.get("execution_model"),
            _TRACE_EXECUTION_MODEL_KEYS,
        ),
        "execution_assumptions": _safe_trace_export_section(
            execution_trace.get("execution_assumptions"),
            _TRACE_EXECUTION_ASSUMPTION_KEYS,
        ),
        "benchmark_summary": _safe_trace_export_section(
            run.get("benchmark_summary"),
            _TRACE_BENCHMARK_SUMMARY_KEYS,
        ),
        "fallback": _safe_trace_export_section(execution_trace.get("fallback"), _TRACE_FALLBACK_KEYS),
    }


def build_execution_trace_export_csv_text(
    run: Mapping[str, Any],
    trace_export_columns: Sequence[tuple[str, str]],
    *,
    action_formatter: Callable[[str], str],
) -> str:
    execution_trace = dict(run.get("execution_trace") or {})
    export_rows = build_execution_trace_export_rows(
        execution_trace,
        trace_export_columns,
        action_formatter=action_formatter,
    )
    if not export_rows:
        raise ValueError(f"Run {run.get('id')} has no audit rows to export.")

    fieldnames = [label for _, label in trace_export_columns]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(export_rows)
    return buffer.getvalue()
