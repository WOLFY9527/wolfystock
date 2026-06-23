# -*- coding: utf-8 -*-
"""Consumer-safe availability metadata for backtest response payloads."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

BACKTEST_NO_ADVICE_DISCLOSURE = (
    "Research diagnostic only; not personalized financial advice and not an executable instruction."
)
BACKTEST_EXECUTION_READINESS_CONTRACT_VERSION = "backtest_execution_readiness_v1"


def _clean_text(value: Any) -> Optional[str]:
    normalized = str(value or "").strip()
    return normalized or None


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _source_text(payload: Dict[str, Any]) -> str:
    diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), dict) else {}
    data_quality = payload.get("data_quality") if isinstance(payload.get("data_quality"), dict) else {}
    candidates = [
        payload.get("resolved_source"),
        payload.get("source"),
        diagnostics.get("source"),
        data_quality.get("source"),
        data_quality.get("authority_source_type"),
    ]
    return " ".join(str(item or "") for item in candidates).strip().lower()


def _source_indicates_fixture(payload: Dict[str, Any]) -> bool:
    source = _source_text(payload)
    return any(token in source for token in ("fixture", "example", "synthetic"))


def _source_indicates_cached(payload: Dict[str, Any]) -> bool:
    source = _source_text(payload)
    return any(token in source for token in ("cache", "cached", "stale"))


def _append_unique(items: List[str], value: Any) -> None:
    text = _clean_text(value)
    if text and text not in items:
        items.append(text)


def _data_sufficiency(payload: Dict[str, Any]) -> Dict[str, Any]:
    value = payload.get("data_sufficiency")
    return dict(value) if isinstance(value, dict) else {}


def _apply_sufficiency_contract(
    *,
    data_sufficiency: Dict[str, Any],
    data_status: str,
    calculation_status: str,
    sample_status: str,
    limitations: List[str],
) -> tuple[str, str, str]:
    status = str(data_sufficiency.get("status") or "").strip()
    calculation_state = str(data_sufficiency.get("calculation_state") or "").strip()
    if not status:
        return data_status, calculation_status, sample_status
    preserve_fixture_status = data_status == "fixture_or_example_data" and status in {
        "missing_adjustments",
        "stale_data",
        "missing_benchmark",
        "missing_factor_inputs",
    }
    if status != "sufficient":
        if not preserve_fixture_status:
            data_status = status
            sample_status = status
    if not preserve_fixture_status:
        if calculation_state == "not_available":
            calculation_status = "calculation_unavailable"
        elif calculation_state == "degraded":
            calculation_status = "degraded"
        elif calculation_state == "executable":
            calculation_status = "ready"
    for reason in data_sufficiency.get("missing_requirements") or []:
        _append_unique(limitations, f"missing input: {reason}")
    summary = data_sufficiency.get("consumer_summary")
    _append_unique(limitations, summary)
    return data_status, calculation_status, sample_status


def _reason_codes(payload: Dict[str, Any], data_sufficiency: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    for value in data_sufficiency.get("missing_requirements") or []:
        _append_unique(reasons, value)
    for value in data_sufficiency.get("blocked_reasons") or []:
        _append_unique(reasons, value)
    for value in data_sufficiency.get("degraded_reasons") or []:
        _append_unique(reasons, value)
    _append_unique(reasons, payload.get("no_result_reason"))
    return reasons


def build_execution_readiness_contract(
    payload: Dict[str, Any],
    *,
    data_status: Optional[str] = None,
    calculation_status: Optional[str] = None,
    sample_status: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a compact consumer-safe execution readiness projection."""

    data_sufficiency = _data_sufficiency(payload)
    input_states = data_sufficiency.get("input_states") if isinstance(data_sufficiency.get("input_states"), dict) else {}
    reason_codes = _reason_codes(payload, data_sufficiency)
    no_result_reason = str(payload.get("no_result_reason") or "").strip().lower()
    engine_state = str(payload.get("engine_state") or "").strip().lower()
    data_status = str(data_status or payload.get("data_status") or "").strip().lower()
    calculation_status = str(calculation_status or payload.get("calculation_status") or "").strip().lower()
    sample_status = str(sample_status or payload.get("sample_status") or "").strip().lower()
    benchmark_state = str(input_states.get("benchmark") or "").strip().lower() or (
        "missing" if "missing_benchmark" in reason_codes else "not_requested"
    )

    if engine_state == "disabled" or no_result_reason == "engine_disabled":
        state = "engine_disabled"
        result_contract_available = False
        engine_state = "disabled"
    elif no_result_reason in {"no_analysis_history", "no_samples", "no_samples_prepared"} or "samples_missing" in reason_codes:
        state = "no_samples"
        result_contract_available = False
        engine_state = engine_state or "enabled"
    elif any(item in reason_codes for item in ("provider_missing", "entitlement_required")):
        state = "data_disabled"
        result_contract_available = False
        engine_state = engine_state or "enabled"
    elif "insufficient_history" in reason_codes or no_result_reason in {"insufficient_history", "insufficient_data"}:
        state = "data_insufficient"
        result_contract_available = False
        engine_state = engine_state or "enabled"
    elif calculation_status == "ready":
        degraded = [
            item
            for item in reason_codes
            if item in {"missing_benchmark", "missing_adjustments", "stale_data", "missing_factor_inputs"}
        ]
        state = "degraded" if degraded else "executable"
        result_contract_available = True
        engine_state = engine_state or "enabled"
    elif data_sufficiency.get("calculation_state") == "degraded":
        state = "degraded"
        result_contract_available = True
        engine_state = engine_state or "enabled"
    elif calculation_status in {"insufficient_sample", "data_unavailable"}:
        state = "data_insufficient"
        result_contract_available = False
        engine_state = engine_state or "enabled"
    else:
        state = "calculation_unavailable"
        result_contract_available = False
        engine_state = engine_state or "enabled"

    return {
        "contract_version": BACKTEST_EXECUTION_READINESS_CONTRACT_VERSION,
        "state": state,
        "result_contract_available": result_contract_available,
        "engine_state": engine_state,
        "data_status": data_status or "unknown",
        "calculation_status": calculation_status or "unknown",
        "sample_status": sample_status or "unknown",
        "benchmark_state": benchmark_state or "unknown",
        "reason_codes": reason_codes,
        "observation_only": True,
        "consumer_safe": True,
        "no_advice_disclosure": BACKTEST_NO_ADVICE_DISCLOSURE,
    }


def _status_contract(
    *,
    data_status: str,
    calculation_status: str,
    sample_status: str,
    source_window: Optional[Dict[str, Any]] = None,
    as_of: Optional[str] = None,
    limitations: Optional[List[str]] = None,
    execution_readiness: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "data_status": data_status,
        "calculation_status": calculation_status,
        "sample_status": sample_status,
        "source_window": dict(source_window or {}),
        "as_of": as_of,
        "limitations": list(limitations or []),
        "execution_readiness": dict(execution_readiness or {}),
        "no_advice_disclosure": BACKTEST_NO_ADVICE_DISCLOSURE,
    }


def build_performance_contract(payload: Dict[str, Any]) -> Dict[str, Any]:
    total = _safe_int(payload.get("total_evaluations"))
    completed = _safe_int(payload.get("completed_count"))
    insufficient = _safe_int(payload.get("insufficient_count"))
    computed_at = _clean_text(payload.get("computed_at"))
    source_window = {
        "scope": payload.get("scope"),
        "code": payload.get("code"),
        "eval_window_days": payload.get("eval_window_days"),
        "evaluation_window_trading_bars": payload.get("evaluation_window_trading_bars"),
        "completed_run_count": completed,
        "total_evaluations": total,
    }
    limitations: List[str] = []

    if total <= 0:
        data_status = "data_unavailable"
        calculation_status = "calculation_unavailable"
        sample_status = "data_unavailable"
        limitations.append("No completed backtest sample is available; performance metrics are unavailable.")
    elif completed <= 0 and insufficient > 0:
        data_status = "ready"
        calculation_status = "insufficient_sample"
        sample_status = "insufficient_sample"
        limitations.append("Backtest samples exist, but none completed with a sufficient evaluation window.")
    else:
        data_status = "ready"
        calculation_status = "ready"
        sample_status = "ready"

    if _source_indicates_fixture(payload):
        data_status = "fixture_or_example_data"
        limitations.append("Backtest data source is fixture or example data; metrics are not tradable evidence.")
    elif data_status == "ready" and _source_indicates_cached(payload):
        data_status = "stale_or_cached"
        limitations.append("Metrics are derived from stored or cached backtest outputs; verify freshness before research use.")

    data_status, calculation_status, sample_status = _apply_sufficiency_contract(
        data_sufficiency=_data_sufficiency(payload),
        data_status=data_status,
        calculation_status=calculation_status,
        sample_status=sample_status,
        limitations=limitations,
    )

    return _status_contract(
        data_status=data_status,
        calculation_status=calculation_status,
        sample_status=sample_status,
        source_window={key: value for key, value in source_window.items() if value is not None},
        as_of=computed_at,
        limitations=limitations,
        execution_readiness=build_execution_readiness_contract(
            payload,
            data_status=data_status,
            calculation_status=calculation_status,
            sample_status=sample_status,
        ),
    )


def build_standard_run_contract(payload: Dict[str, Any]) -> Dict[str, Any]:
    processed = _safe_int(payload.get("processed"))
    completed = _safe_int(payload.get("completed"))
    insufficient = _safe_int(payload.get("insufficient"))
    source_window = {
        "code": payload.get("code"),
        "eval_window_days": payload.get("eval_window_days") or payload.get("evaluation_window_trading_bars"),
        "evaluation_window_trading_bars": payload.get("evaluation_window_trading_bars"),
        "latest_prepared_sample_date": payload.get("latest_prepared_sample_date"),
        "latest_eligible_sample_date": payload.get("latest_eligible_sample_date"),
    }
    limitations: List[str] = []
    _append_unique(limitations, payload.get("no_result_message"))
    _append_unique(limitations, payload.get("excluded_recent_message"))

    no_result_reason = str(payload.get("no_result_reason") or "").strip().lower()
    if no_result_reason == "engine_disabled":
        data_status = "engine_disabled"
        calculation_status = "engine_disabled"
        sample_status = "engine_disabled"
        limitations.append("Backtest engine is disabled; no result contract was produced.")
    elif processed <= 0:
        data_status = "data_unavailable"
        calculation_status = "calculation_unavailable"
        sample_status = "data_unavailable"
        limitations.append("No eligible backtest candidates were processed; performance metrics are unavailable.")
    elif completed <= 0 and insufficient > 0:
        data_status = "data_unavailable"
        calculation_status = "insufficient_sample"
        sample_status = "insufficient_sample"
        limitations.append("Processed backtest candidates lack a sufficient market data window; performance metrics are unavailable.")
    else:
        data_status = "ready"
        calculation_status = "ready"
        sample_status = "ready"

    if _source_indicates_fixture(payload):
        data_status = "fixture_or_example_data"
        limitations.append("Backtest data source is fixture or example data; metrics are not tradable evidence.")
    elif data_status == "ready" and _source_indicates_cached(payload):
        data_status = "stale_or_cached"
        limitations.append("Backtest response is based on stored or cached data.")

    data_status, calculation_status, sample_status = _apply_sufficiency_contract(
        data_sufficiency=_data_sufficiency(payload),
        data_status=data_status,
        calculation_status=calculation_status,
        sample_status=sample_status,
        limitations=limitations,
    )

    return _status_contract(
        data_status=data_status,
        calculation_status=calculation_status,
        sample_status=sample_status,
        source_window={key: value for key, value in source_window.items() if value is not None},
        as_of=_clean_text(payload.get("run_at") or payload.get("completed_at")),
        limitations=limitations,
        execution_readiness=build_execution_readiness_contract(
            payload,
            data_status=data_status,
            calculation_status=calculation_status,
            sample_status=sample_status,
        ),
    )


def build_standard_result_contract(payload: Dict[str, Any]) -> Dict[str, Any]:
    eval_status = str(payload.get("eval_status") or "").strip().lower()
    data_quality = payload.get("data_quality") if isinstance(payload.get("data_quality"), dict) else {}
    limitations: List[str] = []
    for warning in data_quality.get("warnings") or []:
        if isinstance(warning, dict):
            _append_unique(limitations, warning.get("message") or warning.get("code"))
        else:
            _append_unique(limitations, warning)

    if eval_status == "completed":
        data_status = "ready"
        calculation_status = "ready"
        sample_status = "ready"
    elif eval_status == "insufficient_data":
        data_status = "data_unavailable"
        calculation_status = "insufficient_sample"
        sample_status = "insufficient_sample"
        limitations.append("Forward market data window is insufficient; performance metrics are unavailable.")
    else:
        data_status = "data_unavailable"
        calculation_status = "calculation_unavailable"
        sample_status = "data_unavailable"
        limitations.append("Backtest calculation did not complete; performance metrics are unavailable.")

    if _source_indicates_fixture(payload):
        data_status = "fixture_or_example_data"
        limitations.append("Backtest data source is fixture or example data; metrics are not tradable evidence.")
    elif data_status == "ready" and _source_indicates_cached(payload):
        data_status = "stale_or_cached"
        limitations.append("Backtest result is based on stored or cached data.")

    data_status, calculation_status, sample_status = _apply_sufficiency_contract(
        data_sufficiency=_data_sufficiency(payload),
        data_status=data_status,
        calculation_status=calculation_status,
        sample_status=sample_status,
        limitations=limitations,
    )

    return _status_contract(
        data_status=data_status,
        calculation_status=calculation_status,
        sample_status=sample_status,
        source_window={
            key: value
            for key, value in {
                "code": payload.get("code"),
                "analysis_date": payload.get("analysis_date"),
                "eval_window_days": payload.get("eval_window_days"),
                "evaluation_window_trading_bars": payload.get("evaluation_window_trading_bars"),
            }.items()
            if value is not None
        },
        as_of=_clean_text(payload.get("evaluated_at")),
        limitations=limitations,
        execution_readiness=build_execution_readiness_contract(
            payload,
            data_status=data_status,
            calculation_status=calculation_status,
            sample_status=sample_status,
        ),
    )


def build_rule_run_contract(payload: Dict[str, Any]) -> Dict[str, Any]:
    status = str(payload.get("status") or "").strip().lower()
    data_quality = payload.get("data_quality") if isinstance(payload.get("data_quality"), dict) else {}
    result_authority = payload.get("result_authority") if isinstance(payload.get("result_authority"), dict) else {}
    readback_integrity = payload.get("readback_integrity") if isinstance(payload.get("readback_integrity"), dict) else {}
    metrics_state = str(
        ((result_authority.get("domains") or {}).get("metrics") or {}).get("state")
        or ""
    ).strip().lower()
    metrics_completeness = str(result_authority.get("metrics_completeness") or "").strip().lower()
    no_result_reason = str(payload.get("no_result_reason") or "").strip().lower()
    bar_count = _safe_int(data_quality.get("bar_count"))
    limitations: List[str] = []

    _append_unique(limitations, payload.get("no_result_message"))
    for warning in data_quality.get("warnings") or []:
        if isinstance(warning, dict):
            _append_unique(limitations, warning.get("message") or warning.get("code"))
        else:
            _append_unique(limitations, warning)
    for field in result_authority.get("metrics_missing_fields") or []:
        _append_unique(limitations, f"metric field unavailable: {field}")
    if readback_integrity.get("used_legacy_fallback"):
        limitations.append("Some response fields were derived from legacy stored run columns.")
    if readback_integrity.get("used_live_storage_repair"):
        limitations.append("Some response fields were repaired from stored artifacts during readback.")

    if status != "completed":
        calculation_status = "calculation_unavailable"
        sample_status = "calculation_unavailable"
        limitations.append(f"status {status or 'unknown'}")
    elif no_result_reason in {"insufficient_history", "insufficient_data"} or bar_count <= 0:
        calculation_status = "insufficient_sample"
        sample_status = "insufficient_sample"
    elif metrics_state in {"unavailable", "empty"} or metrics_completeness in {"unavailable", "empty"}:
        calculation_status = "calculation_unavailable"
        sample_status = "ready"
    else:
        calculation_status = "ready"
        sample_status = "ready"

    if bar_count <= 0 and calculation_status != "ready":
        data_status = "data_unavailable"
    else:
        data_status = "ready"

    if _source_indicates_fixture(payload):
        data_status = "fixture_or_example_data"
        limitations.append("Backtest data source is fixture or example data; metrics are not tradable evidence.")
    elif data_status == "ready" and _source_indicates_cached(payload):
        data_status = "stale_or_cached"
        limitations.append("Backtest response is based on stored or cached data.")

    data_status, calculation_status, sample_status = _apply_sufficiency_contract(
        data_sufficiency=_data_sufficiency(payload),
        data_status=data_status,
        calculation_status=calculation_status,
        sample_status=sample_status,
        limitations=limitations,
    )

    source_window = {
        "code": payload.get("code"),
        "requested_start": payload.get("start_date") or data_quality.get("requested_start"),
        "requested_end": payload.get("end_date") or data_quality.get("requested_end"),
        "actual_start": data_quality.get("actual_start"),
        "actual_end": data_quality.get("actual_end"),
        "period_start": payload.get("period_start"),
        "period_end": payload.get("period_end"),
        "lookback_bars": payload.get("lookback_bars"),
        "bar_count": data_quality.get("bar_count"),
    }
    return _status_contract(
        data_status=data_status,
        calculation_status=calculation_status,
        sample_status=sample_status,
        source_window={key: value for key, value in source_window.items() if value is not None},
        as_of=_clean_text(payload.get("completed_at") or payload.get("run_at")),
        limitations=limitations,
        execution_readiness=build_execution_readiness_contract(
            payload,
            data_status=data_status,
            calculation_status=calculation_status,
            sample_status=sample_status,
        ),
    )
