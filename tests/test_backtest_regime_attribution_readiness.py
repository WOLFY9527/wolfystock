# -*- coding: utf-8 -*-
"""Focused tests for rule-backtest regime attribution readiness exports."""

from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

from api.v1.endpoints.backtest import get_rule_backtest_regime_attribution_readiness_json  # noqa: E402
from api.v1.schemas.backtest import RuleBacktestRegimeAttributionReadinessExportResponse  # noqa: E402
from src.services.rule_backtest_service import RuleBacktestService  # noqa: E402
from src.services.rule_backtest_support_exports import (  # noqa: E402
    build_regime_attribution_readiness_export,
    build_support_export_index,
)


FORBIDDEN_ATTRIBUTION_SEMANTICS = (
    "optimizer",
    "optimization",
    "winner",
    "winner_selection",
    "winner selection",
    "training",
    "trained",
    "decision-grade",
    "decision_grade",
)


class BacktestRegimeAttributionReadinessTestCase(unittest.TestCase):
    @staticmethod
    def _sample_run() -> dict:
        artifact_availability = {
            "version": "v1",
            "source": "summary.artifact_availability",
            "completeness": "complete",
            "has_trade_rows": True,
            "has_execution_trace": True,
        }
        result_authority = {
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
                "execution_trace": {
                    "source": "summary.execution_trace",
                    "completeness": "complete",
                    "state": "available",
                },
            },
        }
        drawdown_summary = {
            "version": "v1",
            "source": "summary.visualization.audit_rows",
            "state": "available",
            "bucket_counts": {
                "peak": {"count": 1, "share_pct": 50.0},
                "shallow": {"count": 1, "share_pct": 50.0},
            },
            "contribution_summaries": {
                "classified_rows": {"count": 2, "share_pct": 100.0},
                "causality_note": "Observational only from stored audit-row drawdown depths. No PnL or return causality.",
            },
        }
        return {
            "id": 123,
            "code": "600519",
            "status": "completed",
            "timeframe": "daily",
            "period_start": "2024-01-01",
            "period_end": "2024-01-05",
            "trade_count": 1,
            "total_return_pct": 3.25,
            "max_drawdown_pct": 1.5,
            "win_rate_pct": 100.0,
            "final_equity": 103250.0,
            "trades": [
                {
                    "entry_date": "2024-01-02",
                    "exit_date": "2024-01-05",
                    "net_pnl": 3250.0,
                    "fees": 0.0,
                    "slippage": 0.0,
                }
            ],
            "audit_rows": [
                {"date": "2024-01-02", "daily_pnl": 0.0, "drawdown_pct": 0.0},
                {"date": "2024-01-03", "daily_pnl": 1250.0, "drawdown_pct": -1.5},
            ],
            "daily_return_series": [
                {"date": "2024-01-02", "daily_return": 0.0},
                {"date": "2024-01-03", "daily_return": 0.0125},
            ],
            "summary": {
                "drawdown_regime_attribution": drawdown_summary,
                "robustness_analysis": {
                    "state": "research_prototype",
                    "source": "summary.robustness_analysis",
                },
                "artifact_availability": artifact_availability,
                "readback_integrity": {"integrity_level": "stored_complete"},
            },
            "drawdown_regime_attribution": drawdown_summary,
            "robustness_analysis": {
                "state": "research_prototype",
                "source": "summary.robustness_analysis",
            },
            "artifact_availability": artifact_availability,
            "readback_integrity": {"integrity_level": "stored_complete"},
            "data_quality": {
                "source": "local_us_parquet",
                "provider": "Local US Parquet",
                "authority_status": "allowed",
                "authority_source_type": "cache_snapshot",
                "dataset_version": "unknown",
                "bar_count": 24,
            },
            "result_authority": result_authority,
            "raw_provider_payload": "RAW_PROVIDER_PAYLOAD_SHOULD_NOT_LEAK",
        }

    def _assert_no_forbidden_attribution_semantics(self, payload: dict) -> None:
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
        for needle in FORBIDDEN_ATTRIBUTION_SEMANTICS:
            self.assertNotIn(needle, serialized, needle)
        self.assertNotIn("RAW_PROVIDER_PAYLOAD_SHOULD_NOT_LEAK".lower(), serialized)

    def test_projection_reports_diagnostic_only_readiness_and_gaps_without_mutating_math(self) -> None:
        run = self._sample_run()
        before_math = {
            key: copy.deepcopy(run[key])
            for key in ("total_return_pct", "max_drawdown_pct", "win_rate_pct", "final_equity", "trades")
        }

        payload = build_regime_attribution_readiness_export(run)

        self.assertEqual(
            before_math,
            {
                key: run[key]
                for key in ("total_return_pct", "max_drawdown_pct", "win_rate_pct", "final_equity", "trades")
            },
        )
        self.assertEqual(payload["exportKind"], "rule_backtest_regime_attribution_readiness")
        self.assertEqual(payload["runId"], 123)
        self.assertEqual(payload["readMode"], "stored_first")
        self.assertTrue(payload["storedFirst"])
        self.assertTrue(payload["diagnosticOnly"])
        self.assertFalse(payload["engineReexecuted"])
        self.assertFalse(payload["mathChanged"])
        self.assertFalse(payload["attributionEngineAvailable"])
        self.assertFalse(payload["pnlCausalityAvailable"])
        self.assertEqual(payload["runtimeEngineStatement"], "not_a_runtime_attribution_engine")

        evidence = payload["evidenceAvailability"]
        self.assertTrue(evidence["trades"]["available"])
        self.assertEqual(evidence["trades"]["count"], 1)
        self.assertTrue(evidence["dailyAudit"]["available"])
        self.assertEqual(evidence["dailyAudit"]["count"], 2)
        self.assertTrue(evidence["drawdownBucketSummary"]["available"])
        self.assertEqual(evidence["drawdownBucketSummary"]["state"], "available")
        self.assertTrue(evidence["robustnessSupportArtifacts"]["available"])
        self.assertTrue(evidence["datasetLineage"]["available"])
        self.assertTrue(evidence["resultAuthority"]["available"])

        gap_codes = [item["code"] for item in payload["gapReasons"]]
        self.assertEqual(
            gap_codes,
            [
                "missing_date_level_market_regime_labels",
                "missing_regime_source_version",
                "missing_trade_to_regime_join_policy",
                "missing_daily_pnl_allocation_policy",
                "missing_holding_period_allocation_rules",
            ],
        )
        self.assertEqual(payload["mathSnapshot"]["total_return_pct"], 3.25)
        self.assertEqual(payload["mathSnapshot"]["max_drawdown_pct"], 1.5)
        self._assert_no_forbidden_attribution_semantics(payload)

    def test_service_readiness_getter_uses_stored_readback_without_engine_rerun(self) -> None:
        service = object.__new__(RuleBacktestService)
        service.get_run = MagicMock(return_value=self._sample_run())

        with patch.object(
            RuleBacktestService,
            "run_backtest",
            side_effect=AssertionError("readiness export must not run the backtest engine"),
        ), patch.object(
            RuleBacktestService,
            "_build_robustness_analysis",
            side_effect=AssertionError("readiness export must not recompute robustness"),
        ), patch.object(
            RuleBacktestService,
            "_build_drawdown_regime_attribution_payload",
            side_effect=AssertionError("readiness export must use readback projection only"),
        ):
            payload = service.get_regime_attribution_readiness_export(123)

        service.get_run.assert_called_once_with(123)
        self.assertTrue(payload["diagnosticOnly"])
        self.assertFalse(payload["engineReexecuted"])
        self.assertFalse(payload["mathChanged"])

    def test_service_readiness_getter_returns_not_found_for_missing_run(self) -> None:
        service = object.__new__(RuleBacktestService)
        service.get_run = MagicMock(return_value=None)

        with self.assertRaisesRegex(ValueError, "Run 404 not found"):
            service.get_regime_attribution_readiness_export(404)

        service.get_run.assert_called_once_with(404)

    def test_endpoint_returns_additive_readiness_response_model(self) -> None:
        service = MagicMock()
        service.get_regime_attribution_readiness_export.return_value = (
            build_regime_attribution_readiness_export(self._sample_run())
        )

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = get_rule_backtest_regime_attribution_readiness_json(123, db_manager=MagicMock())

        self.assertIsInstance(response, RuleBacktestRegimeAttributionReadinessExportResponse)
        payload = response.model_dump()
        self.assertTrue(payload["diagnosticOnly"])
        self.assertFalse(payload["engineReexecuted"])
        self.assertFalse(payload["mathChanged"])
        self.assertFalse(payload["attributionEngineAvailable"])
        self.assertFalse(payload["pnlCausalityAvailable"])
        self.assertEqual(payload["gapReasons"][0]["code"], "missing_date_level_market_regime_labels")
        service.get_regime_attribution_readiness_export.assert_called_once_with(123)

    def test_endpoint_maps_missing_readiness_run_to_not_found(self) -> None:
        service = MagicMock()
        service.get_regime_attribution_readiness_export.side_effect = ValueError("Run 404 not found.")

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            with self.assertRaises(HTTPException) as ctx:
                get_rule_backtest_regime_attribution_readiness_json(404, db_manager=MagicMock())

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail["error"], "not_found")

    def test_support_export_index_discovers_readiness_export(self) -> None:
        payload = build_support_export_index(self._sample_run())

        self.assertEqual(
            [item["key"] for item in payload["exports"]],
            [
                "support_bundle_manifest_json",
                "support_bundle_reproducibility_manifest_json",
                "execution_trace_json",
                "execution_trace_csv",
                "robustness_evidence_json",
                "regime_attribution_readiness_json",
            ],
        )
        readiness_item = payload["exports"][-1]
        self.assertTrue(readiness_item["available"])
        self.assertEqual(readiness_item["availability_reason"], "run_exists_readiness_projection_available")
        self.assertEqual(readiness_item["payload_class"], "compact")
        self.assertEqual(
            readiness_item["endpoint_path"],
            "/api/v1/backtest/rule/runs/123/regime-attribution-readiness.json",
        )


if __name__ == "__main__":
    unittest.main()
