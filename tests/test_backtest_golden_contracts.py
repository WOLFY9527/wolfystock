# -*- coding: utf-8 -*-
"""Golden fixture contract tests for public backtest DTO boundaries."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from api.v1.schemas.backtest import (
    RuleBacktestCompareResponse,
    RuleBacktestExecutionTraceExportResponse,
    RuleBacktestRobustnessEvidenceExportResponse,
    RuleBacktestRunResponse,
    RuleBacktestSupportBundleManifestResponse,
    RuleBacktestSupportExportIndexResponse,
    RuleBacktestUniverseJobDiagnostics,
    RuleBacktestUniverseResultsResponse,
)


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "backtest"
FORBIDDEN_PUBLIC_TERMS = (
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
)
RESULT_REQUIRED_KEYS = {
    "id",
    "code",
    "status",
    "strategy_text",
    "parsed_strategy",
    "trade_count",
    "total_return_pct",
    "benchmark_return_pct",
    "buy_and_hold_return_pct",
    "max_drawdown_pct",
    "win_rate_pct",
    "final_equity",
    "execution_model",
    "artifact_availability",
    "readback_integrity",
    "result_authority",
}
EXPORT_KEYS = [
    "support_bundle_manifest_json",
    "support_bundle_reproducibility_manifest_json",
    "execution_trace_json",
    "execution_trace_csv",
    "robustness_evidence_json",
]


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _iter_strings(item)
        return
    if isinstance(value, list):
        for item in value:
            yield from _iter_strings(item)
        return
    if isinstance(value, str):
        yield value


def _assert_iso_timestamp(value: str | None) -> None:
    assert value
    datetime.fromisoformat(value.replace("Z", "+00:00"))


def _assert_no_sensitive_public_payload(value: Any) -> None:
    public_text = "\n".join(_iter_strings(value)).lower()
    for term in FORBIDDEN_PUBLIC_TERMS:
        assert term not in public_text


def _assert_no_live_provider_authority(value: Any) -> None:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True).lower()
    assert '"source": "live"' not in serialized
    assert '"is_live": true' not in serialized
    assert '"live_provider_calls_executed": true' not in serialized
    assert '"providercalls": true' not in serialized
    assert "rerun" not in serialized
    assert "recalculate" not in serialized


def test_backtest_result_summary_golden_fixture_matches_public_readback_contract() -> None:
    payload = _load_fixture("rule_backtest_result_summary_dto.json")

    assert RESULT_REQUIRED_KEYS <= set(payload)
    result = RuleBacktestRunResponse(**payload).model_dump(by_alias=True)

    assert result["id"] == 7001
    assert result["code"] == "AAPL"
    assert result["status"] == "completed"
    _assert_iso_timestamp(result["run_at"])
    _assert_iso_timestamp(result["completed_at"])
    assert result["trade_count"] == 4
    assert result["total_return_pct"] == 12.4
    assert result["benchmark_return_pct"] == 8.1
    assert result["buy_and_hold_return_pct"] == 8.1
    assert result["max_drawdown_pct"] == 5.2
    assert result["win_rate_pct"] == 75.0
    assert result["final_equity"] == 112400.0
    assert result["summary"]["request"]["robustness_config"]["walk_forward"] == {
        "train_window": 36,
        "test_window": 18,
        "step": 9,
        "max_windows": 3,
    }
    assert result["summary"]["request"]["robustness_config"]["monte_carlo"] == {
        "simulation_count": 16,
        "seed": 4242,
        "noise_scale": 0.5,
    }
    assert result["summary"]["drawdown_regime_attribution"]["state"] == "unavailable"
    assert result["summary"]["drawdown_regime_attribution"]["source"] == "unavailable"
    assert result["summary"]["drawdown_regime_attribution"]["unavailable_reason"] == "stored_audit_rows_missing"
    assert result["robustness_analysis"]["seed"] == 4242
    assert result["robustness_analysis"]["configuration"]["walk_forward"] == {
        "train_window": 36,
        "test_window": 18,
        "step": 9,
        "max_windows": 3,
    }
    assert result["robustness_analysis"]["configuration"]["monte_carlo"] == {
        "simulation_count": 16,
        "seed": 4242,
        "noise_scale": 0.5,
    }

    strategy = result["parsed_strategy"]
    assert strategy["strategy_kind"] == "moving_average_crossover"
    assert strategy["strategy_spec"]["strategy_family"] == "moving_average_crossover"
    assert strategy["strategy_spec"]["symbol"] == "AAPL"

    execution_model = result["execution_model"]
    assert execution_model["signal_evaluation_timing"] == "bar_close"
    assert execution_model["entry_timing"] == "next_bar_open"
    assert execution_model["position_sizing"] == "single_position_full_notional"

    artifact_availability = result["artifact_availability"]
    assert artifact_availability["has_summary"] is True
    assert artifact_availability["has_metrics"] is True
    assert artifact_availability["has_execution_model"] is True
    assert artifact_availability["has_execution_trace"] is True

    readback_integrity = result["readback_integrity"]
    assert readback_integrity["integrity_level"] == "stored_complete"
    assert readback_integrity["used_legacy_fallback"] is False
    assert readback_integrity["used_live_storage_repair"] is False

    authority = result["result_authority"]
    assert authority["read_mode"] == "stored_first"
    assert authority["contract_version"] == "v1"
    assert {"summary", "metrics", "execution_model", "trade_rows", "execution_trace"} <= set(authority["domains"])
    assert authority["domains"]["metrics"]["source"] == "summary.metrics"
    assert authority["domains"]["execution_trace"]["state"] == "available"

    _assert_no_sensitive_public_payload(result)
    _assert_no_live_provider_authority(result)


def test_execution_trace_export_fixture_freezes_compact_public_trace_shape() -> None:
    payload = _load_fixture("rule_backtest_execution_trace_dto.json")

    trace = RuleBacktestExecutionTraceExportResponse(**payload).model_dump()

    assert trace["version"] == "v1"
    assert trace["source"] == "summary.execution_trace"
    assert trace["completeness"] == "complete"
    assert trace["missing_fields"] == []
    assert len(trace["trace_rows"]) == 3
    for row in trace["trace_rows"]:
        assert {"date", "event_type", "action", "signal_summary", "position", "total_portfolio_value"} <= set(row)
        assert "provider_response" not in row
        assert "request_headers" not in row

    rows_by_event = {row["event_type"]: row for row in trace["trace_rows"]}
    assert rows_by_event["action"]["action"] == "buy"
    assert rows_by_event["fallback"]["fallback"]["code"] == "open_missing_close_fallback"
    assert rows_by_event["anomaly"]["anomaly"]["code"] == "insufficient_next_bar_open"
    assert trace["fallback"]["run_fallback"] is False
    assert trace["fallback"]["trace_rebuilt"] is False
    assert trace["fallback"]["provider_authority"] == "none"

    _assert_no_sensitive_public_payload(trace)
    _assert_no_live_provider_authority(trace)


def test_robustness_evidence_export_fixture_freezes_stored_payload_shape() -> None:
    payload = _load_fixture("rule_backtest_robustness_evidence_dto.json")

    evidence = RuleBacktestRobustnessEvidenceExportResponse(**payload).model_dump()

    assert evidence["state"] == "research_prototype"
    assert evidence["profile"] == "single_symbol_fixture"
    assert evidence["source"] == "summary.robustness_analysis"
    assert evidence["seed"] == 4242
    assert evidence["configuration"]["walk_forward"] == {
        "train_window": 36,
        "test_window": 18,
        "step": 9,
        "max_windows": 3,
    }
    assert evidence["configuration"]["monte_carlo"] == {
        "simulation_count": 16,
        "seed": 4242,
        "noise_scale": 0.5,
    }

    _assert_no_sensitive_public_payload(evidence)
    _assert_no_live_provider_authority(evidence)


def test_export_index_and_support_bundle_fixtures_freeze_stored_first_export_boundary() -> None:
    export_index = RuleBacktestSupportExportIndexResponse(
        **_load_fixture("rule_backtest_export_index_dto.json")
    ).model_dump()
    manifest = RuleBacktestSupportBundleManifestResponse(
        **_load_fixture("rule_backtest_support_bundle_manifest_dto.json")
    ).model_dump()

    assert export_index["run_id"] == 7001
    assert export_index["status"] == "completed"
    assert [item["key"] for item in export_index["exports"]] == EXPORT_KEYS
    assert [item["payload_class"] for item in export_index["exports"]] == ["compact", "compact", "heavy", "heavy", "heavy"]
    for item in export_index["exports"]:
        assert item["delivery_mode"] == "api"
        assert item["endpoint_path"].startswith("/api/v1/backtest/rule/runs/7001/")
    assert export_index["exports"][0]["available"] is True
    assert export_index["exports"][1]["available"] is True
    assert export_index["exports"][2]["available"] is False
    assert export_index["exports"][2]["availability_reason"] == "execution_trace_rows_missing"
    assert export_index["exports"][3]["available"] is False
    assert export_index["exports"][3]["availability_reason"] == "execution_trace_rows_missing"
    assert export_index["exports"][4]["available"] is True
    assert export_index["exports"][4]["availability_reason"] == "stored_robustness_analysis_present"

    assert manifest["manifest_kind"] == "rule_backtest_support_bundle"
    assert manifest["run"]["id"] == export_index["run_id"]
    assert manifest["result_authority"]["read_mode"] == "stored_first"
    assert manifest["artifact_availability"]["has_summary"] is True
    assert manifest["readback_integrity"]["integrity_level"] == "stored_complete"
    assert manifest["artifact_counts"]["execution_trace_rows_count"] == 3
    assert not ({"trades", "equity_curve", "audit_rows", "execution_trace"} & set(manifest))

    _assert_no_sensitive_public_payload(export_index)
    _assert_no_sensitive_public_payload(manifest)
    _assert_no_live_provider_authority(export_index)
    _assert_no_live_provider_authority(manifest)


def test_compare_golden_fixture_is_stored_first_and_contains_no_recalculation_semantics() -> None:
    payload = _load_fixture("rule_backtest_compare_dto.json")

    compare = RuleBacktestCompareResponse(**payload).model_dump()

    assert compare["comparison_source"] == "stored_rule_backtest_runs"
    assert compare["read_mode"] == "stored_first"
    assert compare["requested_run_ids"] == [7001, 7002, 7999]
    assert compare["resolved_run_ids"] == [7001, 7002]
    assert compare["comparable_run_ids"] == [7001, 7002]
    assert compare["missing_run_ids"] == [7999]
    assert compare["comparison_summary"]["baseline"]["run_id"] == 7001
    assert compare["comparison_summary"]["baseline"]["selection_rule"] == "first_comparable_run_by_request_order"
    assert compare["market_code_comparison"]["relationship"] == "same_code"
    assert compare["period_comparison"]["relationship"] == "overlapping"
    assert compare["parameter_comparison"]["state"] == "same_family_comparable"
    assert compare["robustness_summary"]["overall_state"] == "partially_comparable"
    assert compare["comparison_profile"]["primary_profile"] == "same_strategy_parameter_variants"
    assert compare["comparison_highlights"]["highlights"]["total_return_pct"]["state"] == "limited_context_winner"
    assert len(compare["items"]) == 2
    assert compare["items"][0]["metadata"]["id"] == 7001
    assert compare["items"][1]["metadata"]["id"] == 7002
    for item in compare["items"]:
        assert item["metadata"]["status"] == "completed"
        assert item["result_authority"]["read_mode"] == "stored_first"
        assert {"trade_count", "total_return_pct", "max_drawdown_pct", "win_rate_pct", "final_equity"} <= set(
            item["metrics"]
        )

    _assert_no_sensitive_public_payload(compare)
    _assert_no_live_provider_authority(compare)


def test_compare_heatmap_golden_fixture_freezes_stored_compare_projection_vocabulary() -> None:
    heatmap = _load_fixture("rule_backtest_compare_heatmap_dto.json")

    assert heatmap["contract_kind"] == "rule_backtest_compare_heatmap_projection"
    assert heatmap["contract_version"] == "v1"
    assert heatmap["source"] == "stored_compare_projection"
    assert heatmap["read_mode"] == "stored_projection_only"

    authority = heatmap["authority"]
    assert authority["projection_basis"] == "stored_compare_payloads"
    assert authority["execution_mode"] == "no_reexecution"
    assert authority["execution_count"] == 0
    assert authority["provider_calls_executed"] is False
    assert authority["compare_payload_reused"] is True

    assert heatmap["source_run_ids"] == [7001, 7002, 7003]
    assert heatmap["requested_compare_run_ids"] == [7001, 7002, 7003, 7999]
    assert heatmap["resolved_compare_run_ids"] == [7001, 7002, 7003]
    assert heatmap["missing_run_ids"] == [7999]
    assert heatmap["metric_keys"] == ["total_return_pct", "max_drawdown_pct"]

    x_axis = heatmap["axes"]["x"]
    y_axis = heatmap["axes"]["y"]
    assert x_axis["axis_key"] == "strategy_spec.signal.fast_period"
    assert x_axis["values"] == [5, 10]
    assert y_axis["axis_key"] == "strategy_spec.signal.slow_period"
    assert y_axis["values"] == [20, 50, None]

    cells = heatmap["cells"]
    assert len(cells) == 4
    states = {(cell["x_value"], cell["y_value"]): cell["availability_state"] for cell in cells}
    assert states[(5, 20)] == "available"
    assert states[(10, 50)] == "available"
    assert states[(5, 50)] == "missing"
    assert states[(10, None)] == "ambiguous"

    available_cell = next(cell for cell in cells if cell["x_value"] == 5 and cell["y_value"] == 20)
    assert available_cell["source_run_ids"] == [7001]
    assert available_cell["metrics"]["total_return_pct"]["value"] == 12.4
    assert available_cell["metrics"]["max_drawdown_pct"]["value"] == 5.2

    missing_cell = next(cell for cell in cells if cell["availability_state"] == "missing")
    assert missing_cell["source_run_ids"] == []
    assert missing_cell["metrics"]["total_return_pct"]["state"] == "missing"
    assert missing_cell["metrics"]["max_drawdown_pct"]["state"] == "missing"

    ambiguous_cell = next(cell for cell in cells if cell["availability_state"] == "ambiguous")
    assert ambiguous_cell["source_run_ids"] == [7002, 7003]
    assert ambiguous_cell["metrics"]["total_return_pct"]["state"] == "ambiguous"
    assert ambiguous_cell["metrics"]["max_drawdown_pct"]["state"] == "ambiguous"

    forbidden_compact_terms = {"trades", "equity_curve", "audit_rows", "execution_trace", "provider_payload"}
    assert not forbidden_compact_terms & set(heatmap)

    _assert_no_sensitive_public_payload(heatmap)
    _assert_no_live_provider_authority(heatmap)


def test_universe_job_golden_fixtures_freeze_local_only_diagnostics_and_compact_rows() -> None:
    diagnostics = RuleBacktestUniverseJobDiagnostics(
        **_load_fixture("rule_backtest_universe_job_diagnostics_dto.json")
    ).model_dump()
    results = RuleBacktestUniverseResultsResponse(**_load_fixture("rule_backtest_universe_results_dto.json")).model_dump()

    assert diagnostics["job_id"] == 9001
    assert diagnostics["progress"]["status"] == "completed_with_failures"
    assert diagnostics["progress"]["total_count"] == 3
    assert diagnostics["progress"]["processed_count"] == 3
    assert diagnostics["progress"]["progress_pct"] == 100.0
    reasons = {item["reason_code"]: item for item in diagnostics["reason_summary"]}
    assert reasons["completed"]["count"] == 2
    assert reasons["blocked_missing_local_data"]["sample_symbols"] == ["ZZZ"]
    assert diagnostics["local_data_coverage"] == {
        "ready": 2,
        "partial": 0,
        "missing": 1,
        "insufficient_data": 0,
        "unknown": 0,
    }
    metadata = diagnostics["metadata"]
    assert metadata["local_only"] is True
    assert metadata["live_provider_calls_executed"] is False
    assert metadata["concurrency_enabled"] is False
    assert metadata["localDataCoverageState"] == "mixed"
    assert metadata["pointInTimeUniverse"] is False
    assert metadata["survivorshipBiasState"] == "uncontrolled"
    assert metadata["providerCalls"] is False
    assert metadata["professionalReadiness"]["overall_state"] == "research_prototype"
    assert metadata["professionalReadiness"]["professional_quant_ready"] is False

    assert results["job_id"] == diagnostics["job_id"]
    assert results["total"] == 3
    assert [item["symbol"] for item in results["items"]] == ["AAPL", "MSFT", "ZZZ"]
    for row in results["items"]:
        assert {
            "id",
            "job_id",
            "sequence_index",
            "symbol",
            "status",
            "reason_code",
            "runtime_ms",
            "metrics",
            "total_return_pct",
            "max_drawdown_pct",
            "win_rate_pct",
            "trades_count",
            "single_run_id",
        } <= set(row)
        assert "execution_trace" not in row
        assert "equity_curve" not in row
        assert "trades" not in row
    assert results["items"][0]["metrics"]["local_data_preflight"]["state"] == "ready"
    assert results["items"][2]["status"] == "skipped"
    assert results["items"][2]["reason_code"] == "blocked_missing_local_data"

    _assert_no_sensitive_public_payload(diagnostics)
    _assert_no_sensitive_public_payload(results)
    _assert_no_live_provider_authority(diagnostics)
    _assert_no_live_provider_authority(results)


def test_all_backtest_golden_fixtures_are_sanitized_and_explicitly_enumerated() -> None:
    fixture_paths = sorted(FIXTURE_DIR.glob("*.json"))

    assert {path.name for path in fixture_paths} == {
        "rule_backtest_compare_dto.json",
        "rule_backtest_compare_heatmap_dto.json",
        "rule_backtest_execution_trace_dto.json",
        "rule_backtest_export_index_dto.json",
        "rule_backtest_robustness_evidence_dto.json",
        "rule_backtest_result_summary_dto.json",
        "rule_backtest_support_bundle_manifest_dto.json",
        "rule_backtest_universe_job_diagnostics_dto.json",
        "rule_backtest_universe_results_dto.json",
    }
    for path in fixture_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        _assert_no_sensitive_public_payload(payload)
        _assert_no_live_provider_authority(payload)
