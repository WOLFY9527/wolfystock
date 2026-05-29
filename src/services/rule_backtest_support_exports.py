# -*- coding: utf-8 -*-
"""Pure projection helpers for stored rule-backtest support/export payloads."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from typing import Any, Callable, Mapping, Sequence

from src.services.backtest_walkforward_oos import build_walk_forward_oos_evidence_from_stored_robustness
from src.services.reason_code_vocabulary import classify_reason_codes

RULE_BACKTEST_EXECUTION_MODEL_METADATA_VERSION = "v1"
RULE_BACKTEST_EXECUTION_MODEL_EXPORT_KIND = "rule_backtest_execution_model_metadata"
_RULE_BACKTEST_EXECUTION_MODEL_V1 = {
    "model_id": "rule_backtest_default_execution_model_v1",
    "version": RULE_BACKTEST_EXECUTION_MODEL_METADATA_VERSION,
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
_RULE_BACKTEST_EXECUTION_MODEL_V1_SEMANTICS = {
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
_RULE_BACKTEST_EXECUTION_MODEL_V1_GUARDRAILS = {
    "winner_promotion": False,
    "optimizer_executed": False,
    "parameter_sweep_executed": False,
    "provider_calls_executed": False,
    "silent_runtime_semantic_change_allowed": False,
    "future_semantic_changes_require_new_version": True,
    "future_versions_must_be_additive": True,
}


def stringify_execution_trace_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


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
            export_row[label] = stringify_execution_trace_value(value)
        export_rows.append(export_row)
    return export_rows


def build_reproducibility_authority_summary(result_authority: Mapping[str, Any]) -> dict[str, Any]:
    domains = dict(result_authority.get("domains") or {})
    summarized_domains: dict[str, Any] = {}
    for domain_name, domain_payload in domains.items():
        domain = dict(domain_payload or {})
        summarized_domains[str(domain_name)] = {
            "source": domain.get("source"),
            "completeness": domain.get("completeness"),
            "state": domain.get("state"),
        }
    return {
        "contract_version": result_authority.get("contract_version"),
        "read_mode": result_authority.get("read_mode"),
        "domains": summarized_domains,
    }


def build_execution_assumptions_fingerprint(
    execution_assumptions_snapshot: Mapping[str, Any],
    execution_assumptions: Mapping[str, Any],
) -> dict[str, Any]:
    payload = dict(execution_assumptions_snapshot.get("payload") or execution_assumptions or {})
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "source": execution_assumptions_snapshot.get("source"),
        "completeness": execution_assumptions_snapshot.get("completeness"),
        "summary_text": payload.get("summary_text"),
        "hash_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest() if payload else None,
    }


def _mapping_payload(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, Mapping) else {}


def _text_or_unknown(value: Any) -> str:
    text = str(value or "").strip()
    return text or "unknown"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


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
        "run_timing": dict(run.get("run_timing") or {}),
        "run_diagnostics": dict(run.get("run_diagnostics") or {}),
        "artifact_availability": dict(run.get("artifact_availability") or {}),
        "readback_integrity": dict(run.get("readback_integrity") or {}),
        "result_authority": {
            "contract_version": result_authority.get("contract_version"),
            "read_mode": result_authority.get("read_mode"),
            "domains": dict(result_authority.get("domains") or {}),
        },
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
    return manifest


def build_support_bundle_reproducibility_manifest(run: Mapping[str, Any]) -> dict[str, Any]:
    result_authority = dict(run.get("result_authority") or {})
    execution_assumptions_snapshot = dict(run.get("execution_assumptions_snapshot") or {})
    execution_assumptions = dict(run.get("execution_assumptions") or {})
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
        "run_diagnostics": dict(run.get("run_diagnostics") or {}),
        "run_timing": dict(run.get("run_timing") or {}),
        "artifact_availability": dict(run.get("artifact_availability") or {}),
        "readback_integrity": dict(run.get("readback_integrity") or {}),
        "execution_assumptions_fingerprint": build_execution_assumptions_fingerprint(
            execution_assumptions_snapshot=execution_assumptions_snapshot,
            execution_assumptions=execution_assumptions,
        ),
        "result_authority": build_reproducibility_authority_summary(result_authority),
    }
    dataset_lineage = build_dataset_lineage_manifest(run)
    if dataset_lineage is not None:
        manifest["dataset_lineage"] = dataset_lineage
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
    }


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
        "version": execution_trace.get("version"),
        "source": execution_trace.get("source"),
        "completeness": execution_trace.get("completeness"),
        "missing_fields": list(execution_trace.get("missing_fields") or []),
        "trace_rows": export_rows,
        "assumptions": dict(execution_trace.get("assumptions_defaults") or {}),
        "execution_model": dict(execution_trace.get("execution_model") or {}),
        "execution_assumptions": dict(execution_trace.get("execution_assumptions") or {}),
        "benchmark_summary": dict(run.get("benchmark_summary") or {}),
        "fallback": dict(execution_trace.get("fallback") or {}),
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
