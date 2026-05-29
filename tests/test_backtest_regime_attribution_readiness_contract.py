# -*- coding: utf-8 -*-
"""Fixture-only contract for backtest regime attribution readiness evidence."""

from __future__ import annotations

import json
from copy import deepcopy

from src.services.rule_backtest_support_exports import (
    build_regime_attribution_readiness_export,
)


def _assert_no_forbidden_semantics(payload: dict) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
    for forbidden in (
        '"diagnosticonly": false',
        '"enginereexecuted": true',
        '"mathchanged": true',
        '"attributionengineavailable": true',
        '"pnlcausalityavailable": true',
        '"decisiongrade": true',
        '"benchmarkattribution":',
        '"benchmarkattributionengine":',
        '"regimesourceversion":',
        '"tradetoregimejoinpolicy":',
        '"barsregimejoin":',
        '"bars_trades_equity_regime_join":',
        '"dailypnlbyregime":',
        '"dailypnlallocationpolicy":',
        '"holdingperiodallocationrules":',
        '"strategyexecutioncount":',
        '"optimizerexecuted": true',
        '"parametersweepexecuted": true',
        '"providercallsexecuted": true',
        "provider_backed",
        "winner",
    ):
        assert forbidden not in serialized, forbidden


def test_regime_attribution_readiness_stays_stored_projection_only_and_diagnostic() -> None:
    run = {
        "id": 678,
        "code": "600519",
        "status": "completed",
        "timeframe": "1d",
        "period_start": "2024-01-02",
        "period_end": "2024-04-30",
        "trade_count": 2,
        "total_return_pct": 6.2,
        "max_drawdown_pct": 4.4,
        "win_rate_pct": 50.0,
        "final_equity": 106200.0,
        "benchmark_mode": "manual",
        "benchmark_code": "000300",
        "trades": [
            {"entry_date": "2024-01-15", "exit_date": "2024-02-01", "net_pnl": 4200.0},
            {"entry_date": "2024-03-04", "exit_date": "2024-03-21", "net_pnl": 2000.0},
        ],
        "audit_rows": [
            {"date": "2024-01-15", "daily_pnl": 0.0, "drawdown_pct": 0.0},
            {"date": "2024-01-16", "daily_pnl": 850.0, "drawdown_pct": -1.1},
            {"date": "2024-03-05", "daily_pnl": -430.0, "drawdown_pct": -4.4},
        ],
        "daily_return_series": [
            {"date": "2024-01-15", "daily_return": 0.0},
            {"date": "2024-01-16", "daily_return": 0.0085},
            {"date": "2024-03-05", "daily_return": -0.0043},
        ],
        "summary": {
            "drawdown_regime_attribution": {
                "version": "v1",
                "source": "summary.drawdown_regime_attribution",
                "state": "available",
                "bucket_counts": {
                    "peak": {"count": 1, "share_pct": 33.3},
                    "shallow": {"count": 1, "share_pct": 33.3},
                    "moderate": {"count": 1, "share_pct": 33.3},
                },
                "contribution_summaries": {
                    "classified_rows": {"count": 3, "share_pct": 100.0},
                    "causality_note": (
                        "Observational only from stored audit-row drawdown depths. "
                        "No validated regime PnL attribution or benchmark causality."
                    ),
                },
            },
            "robustness_analysis": {
                "state": "research_prototype",
                "source": "summary.robustness_analysis",
            },
            "artifact_availability": {
                "version": "v1",
                "source": "summary.artifact_availability",
                "completeness": "complete",
                "has_trade_rows": True,
                "has_execution_trace": False,
            },
            "readback_integrity": {
                "integrity_level": "stored_complete",
            },
        },
        "data_quality": {
            "source": "local_us_parquet",
            "provider": "Local US Parquet",
            "authority_status": "allowed",
            "authority_source_type": "cache_snapshot",
            "authority_reason_codes": [],
            "dataset_version": "snapshot-20240529",
            "requested_start": "2024-01-02",
            "requested_end": "2024-04-30",
            "actual_start": "2024-01-02",
            "actual_end": "2024-04-30",
            "bar_count": 81,
        },
        "result_authority": {
            "contract_version": "v1",
            "read_mode": "stored_first",
            "domains": {
                "trade_rows": {
                    "source": "stored_rule_backtest_trades",
                    "completeness": "complete",
                    "state": "available",
                },
                "replay_payload": {
                    "source": "summary.visualization.audit_rows",
                    "completeness": "complete",
                    "state": "available",
                },
                "daily_return_series": {
                    "source": "summary.visualization.daily_return_series",
                    "completeness": "complete",
                    "state": "available",
                },
            },
        },
    }
    original = deepcopy(run)
    expected_drawdown = deepcopy(run["summary"]["drawdown_regime_attribution"])

    payload = build_regime_attribution_readiness_export(run)

    assert run == original
    assert payload["exportKind"] == "rule_backtest_regime_attribution_readiness"
    assert payload["version"] == "v1"
    assert payload["runId"] == 678
    assert payload["source"] == "stored_rule_backtest_readback_projection"
    assert payload["readMode"] == "stored_first"
    assert payload["storedFirst"] is True
    assert payload["diagnosticOnly"] is True
    assert payload["engineReexecuted"] is False
    assert payload["mathChanged"] is False
    assert payload["attributionEngineAvailable"] is False
    assert payload["pnlCausalityAvailable"] is False
    assert payload["runtimeEngineStatement"] == "not_a_runtime_attribution_engine"
    assert payload["mathSnapshot"] == {
        "trade_count": 2,
        "total_return_pct": 6.2,
        "max_drawdown_pct": 4.4,
        "win_rate_pct": 50.0,
        "final_equity": 106200.0,
    }
    assert "benchmark_return_pct" not in payload["mathSnapshot"]
    assert payload["limitations"] == [
        "diagnostic_readiness_projection_only",
        "not_a_runtime_attribution_engine",
        "no_market_regime_classification",
        "no_pnl_by_regime_allocation",
    ]

    evidence = payload["evidenceAvailability"]
    assert evidence["trades"] == {
        "available": True,
        "availabilityReason": "stored_trade_rows_present",
        "count": 2,
        "declaredCount": 2,
        "authority": {
            "available": True,
            "availabilityReason": "trade_rows_authority_available",
            "source": "stored_rule_backtest_trades",
            "completeness": "complete",
            "state": "available",
        },
    }
    assert evidence["dailyAudit"] == {
        "available": True,
        "availabilityReason": "stored_audit_rows_present",
        "count": 3,
        "rowsWithDailyPnl": 3,
        "dailyReturnSeriesCount": 3,
        "authority": {
            "available": True,
            "availabilityReason": "replay_payload_authority_available",
            "source": "summary.visualization.audit_rows",
            "completeness": "complete",
            "state": "available",
        },
    }

    drawdown = evidence["drawdownBucketSummary"]
    assert drawdown["available"] is True
    assert drawdown["availabilityReason"] == "stored_drawdown_bucket_summary_present"
    assert drawdown["source"] == expected_drawdown["source"]
    assert drawdown["state"] == expected_drawdown["state"]
    assert drawdown["bucketCount"] == len(expected_drawdown["bucket_counts"])
    assert drawdown["classifiedRows"] == expected_drawdown["contribution_summaries"]["classified_rows"]
    assert drawdown["causalityNote"] == expected_drawdown["contribution_summaries"]["causality_note"]

    support_artifacts = evidence["robustnessSupportArtifacts"]
    assert support_artifacts["available"] is True
    assert support_artifacts["robustnessAvailable"] is True
    assert support_artifacts["robustnessState"] == "research_prototype"
    assert support_artifacts["robustnessSource"] == "summary.robustness_analysis"
    assert support_artifacts["artifactAvailabilityAvailable"] is True
    assert support_artifacts["readbackIntegrityAvailable"] is True
    assert support_artifacts["readbackIntegrityLevel"] == "stored_complete"

    dataset_lineage = evidence["datasetLineage"]
    assert dataset_lineage["available"] is True
    assert dataset_lineage["availabilityReason"] == "dataset_lineage_present"
    assert dataset_lineage["lineage"] == {
        "source": "local_us_parquet",
        "provider": "Local US Parquet",
        "authority_status": "allowed",
        "authority_source_type": "cache_snapshot",
        "authority_reason_codes": [],
        "authority_reason_families": [],
        "authority_allowed": True,
        "degraded_fill_only": False,
        "requested_range": {"start": "2024-01-02", "end": "2024-04-30"},
        "actual_range": {"start": "2024-01-02", "end": "2024-04-30"},
        "bar_count": 81,
        "dataset_version": "snapshot-20240529",
    }

    result_authority = evidence["resultAuthority"]
    assert result_authority["available"] is True
    assert result_authority["availabilityReason"] == "result_authority_present"
    assert result_authority["contractVersion"] == "v1"
    assert result_authority["readMode"] == "stored_first"
    assert result_authority["domainStates"] == {
        "trade_rows": {
            "source": "stored_rule_backtest_trades",
            "completeness": "complete",
            "state": "available",
        },
        "replay_payload": {
            "source": "summary.visualization.audit_rows",
            "completeness": "complete",
            "state": "available",
        },
        "daily_return_series": {
            "source": "summary.visualization.daily_return_series",
            "completeness": "complete",
            "state": "available",
        },
    }

    assert [item["code"] for item in payload["gapReasons"]] == [
        "missing_date_level_market_regime_labels",
        "missing_regime_source_version",
        "missing_trade_to_regime_join_policy",
        "missing_daily_pnl_allocation_policy",
        "missing_holding_period_allocation_rules",
    ]

    _assert_no_forbidden_semantics(payload)
