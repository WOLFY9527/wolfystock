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

    status = _text_or_unknown(data_quality.get("authority_status")).lower()
    if status == "allowed":
        return True
    if status in {"degraded_fill_only", "rejected"}:
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
        ],
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
