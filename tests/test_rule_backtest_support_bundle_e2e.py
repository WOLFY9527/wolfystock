# -*- coding: utf-8 -*-
"""HTTP E2E coverage for rule-backtest support bundle exports."""

from __future__ import annotations

import csv
import copy
import hashlib
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

import src.auth as auth  # noqa: E402
from api.app import create_app  # noqa: E402
from api.v1.schemas.backtest import (  # noqa: E402
    RuleBacktestSupportBundleManifestResponse,
    RuleBacktestSupportBundleReproducibilityManifestResponse,
)
from src.config import Config  # noqa: E402
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID  # noqa: E402
from src.services.rule_backtest_service import RuleBacktestService  # noqa: E402
from src.storage import DatabaseManager, StockDaily  # noqa: E402

EXPECTED_TRACE_EXPORT_JSON_KEYS = [
    "version",
    "source",
    "completeness",
    "missing_fields",
    "trace_rows",
    "assumptions",
    "execution_model",
    "execution_assumptions",
    "benchmark_summary",
    "fallback",
]

EXPECTED_TRACE_EXPORT_FIELD_LABELS = [
    "日期",
    "标的收盘价",
    "基准收盘价",
    "信号摘要",
    "动作",
    "成交价",
    "持股数",
    "现金",
    "持仓市值",
    "总资产",
    "当日盈亏",
    "当日收益率",
    "策略累计收益率",
    "基准累计收益率",
    "买入持有累计收益率",
    "仓位",
    "手续费",
    "滑点",
    "备注",
    "assumptions",
    "fallback",
]

SENSITIVE_EXPORT_KEY_TERMS = (
    "api_key",
    "apikey",
    "cookie",
    "credential",
    "order_payload",
    "password",
    "provider_payload",
    "payload_json",
    "raw_payload",
    "raw_provider",
    "secret",
    "session",
    "token",
)

RAW_PROVIDER_SENTINELS = (
    "BROKER_CREDENTIAL_SHOULD_NOT_LEAK",
    "ORDER_PAYLOAD_SHOULD_NOT_LEAK",
    "PLACE_ORDER_SHOULD_NOT_LEAK",
    "PROVIDER_CREDENTIAL_SHOULD_NOT_LEAK",
    "RAW_PROVIDER_PAYLOAD_SHOULD_NOT_LEAK",
    "SECRET_VALUE_SHOULD_NOT_LEAK",
    "TOKEN_VALUE_SHOULD_NOT_LEAK",
    "SESSION_VALUE_SHOULD_NOT_LEAK",
    "PASSWORD_VALUE_SHOULD_NOT_LEAK",
)

SYNTHETIC_SUPPORT_EXPORT_RAW_MARKERS = (
    "synthetic_cache_key",
    "synthetic_provider_url",
    "synthetic_request_id",
    "synthetic_stack_trace",
    "synthetic_debug_reason",
    "synthetic_execution_trace_detail",
)

FORBIDDEN_EXPORT_TEXT_MARKERS = (
    "broker_credentials",
    "brokerorderpayload",
    "execute_order",
    "guaranteed",
    "must buy",
    "must sell",
    "order_payload",
    "place_order",
    "provider_credentials",
    "submit_order",
    "buy now",
    "sell now",
    "稳赚",
    "必买",
    "下单",
)

FORBIDDEN_ROBUSTNESS_OPTIMIZER_TERMS = (
    "optimizer",
    "optimization",
    "parameter_tuning",
    "parameter tuning",
    "auto_tune",
    "auto-tune",
    "grid_search",
    "grid search",
    "winner",
    "winner_selection",
    "winner selection",
    "selected_parameters",
    "selected parameters",
    "trained_parameters",
    "trained parameters",
    "parameter_training",
    "parameter training",
    "training_score",
    "training score",
)


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


class RuleBacktestSupportBundleE2ETestCase(unittest.TestCase):
    @staticmethod
    def _error_code(response) -> str | None:
        payload = response.json()
        detail = payload.get("detail") if isinstance(payload, dict) else None
        if isinstance(detail, dict):
            return detail.get("error")
        if isinstance(payload, dict):
            return payload.get("error")
        return None

    def setUp(self) -> None:
        self._old_admin_auth_enabled = os.environ.get("ADMIN_AUTH_ENABLED")
        os.environ["ADMIN_AUTH_ENABLED"] = "false"
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "rule_backtest_support_bundle_e2e.db"
        self.env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=600519",
                    "GEMINI_API_KEY=test",
                    "ADMIN_AUTH_ENABLED=false",
                    f"DATABASE_PATH={self.db_path}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.db_path)

        Config.reset_instance()
        DatabaseManager.reset_instance()
        self._history_fetch_patch = patch(
            "src.services.rule_backtest_service.fetch_daily_history_with_local_us_fallback",
            return_value=(None, None),
        )
        self._history_fetch_patch.start()

        self.app = create_app(static_dir=self.data_dir / "empty-static")
        self.client = TestClient(self.app)
        self.db = DatabaseManager.get_instance()

        with self.db.get_session() as session:
            closes = [
                10,
                10.2,
                10.1,
                10.5,
                11.0,
                11.6,
                11.8,
                11.2,
                10.8,
                10.2,
                9.9,
                10.3,
                10.9,
                11.4,
                11.9,
                12.1,
                11.7,
                11.1,
                10.7,
                10.4,
                10.8,
                11.3,
                11.8,
                12.2,
            ]
            for index, close in enumerate(closes):
                session.add(
                    StockDaily(
                        code="600519",
                        date=date(2024, 1, 1).fromordinal(date(2024, 1, 1).toordinal() + index),
                        open=close - 0.1,
                        high=close + 0.2,
                        low=close - 0.3,
                        close=float(close),
                        data_source="local_us_parquet",
                    )
                )
            session.commit()

    def tearDown(self) -> None:
        self._history_fetch_patch.stop()
        self.client.close()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        if self._old_admin_auth_enabled is None:
            os.environ.pop("ADMIN_AUTH_ENABLED", None)
        else:
            os.environ["ADMIN_AUTH_ENABLED"] = self._old_admin_auth_enabled
        _reset_auth_globals()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def _run_completed_backtest(
        self,
        *,
        fee_bps: float = 0.0,
        slippage_bps: float = 0.0,
    ) -> tuple[RuleBacktestService, dict]:
        service = RuleBacktestService(self.db, owner_id=BOOTSTRAP_ADMIN_USER_ID)
        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                fee_bps=fee_bps,
                slippage_bps=slippage_bps,
                confirmed=True,
            )
        return service, response

    def _run_insufficient_history_backtest(self) -> tuple[RuleBacktestService, dict]:
        service = RuleBacktestService(self.db, owner_id=BOOTSTRAP_ADMIN_USER_ID)
        with patch.object(service, "_ensure_market_history", return_value=0), patch.object(
            service,
            "_get_llm_adapter",
            return_value=None,
        ):
            response = service.run_backtest(
                code="NODATA",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                start_date="2024-01-01",
                end_date="2024-01-31",
                lookback_bars=20,
                fee_bps=1.5,
                slippage_bps=2.5,
                confirmed=True,
            )
        return service, response

    def _assert_export_payload_is_sanitized(self, payload: object) -> None:
        payload = self._payload_without_allowed_oos_authority_flags(payload)
        payload = self._payload_without_allowed_execution_model_guardrails(payload)
        payload = self._payload_without_allowed_oos_parameter_readiness_guardrails(payload)
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        for sentinel in RAW_PROVIDER_SENTINELS:
            self.assertNotIn(sentinel, serialized)
        for marker in SYNTHETIC_SUPPORT_EXPORT_RAW_MARKERS:
            self.assertNotIn(marker, serialized)
        normalized = serialized.lower()
        for marker in FORBIDDEN_EXPORT_TEXT_MARKERS:
            self.assertNotIn(marker.lower(), normalized)
        for marker in FORBIDDEN_ROBUSTNESS_OPTIMIZER_TERMS:
            self.assertNotIn(marker.lower(), normalized)

        def walk(value: object, path: tuple[str, ...] = ()) -> None:
            if isinstance(value, dict):
                for key, nested in value.items():
                    normalized_key = str(key).lower()
                    if not (normalized_key == "provider" and path == ("dataset_lineage",)):
                        for forbidden in SENSITIVE_EXPORT_KEY_TERMS:
                            self.assertNotIn(forbidden, normalized_key)
                    walk(nested, (*path, str(key)))
            elif isinstance(value, list):
                for nested in value:
                    walk(nested, path)

        walk(payload)

    def _assert_robustness_payload_avoids_optimizer_semantics(self, payload: dict) -> None:
        normalized_payload = self._payload_without_allowed_oos_authority_flags(payload)
        serialized = json.dumps(normalized_payload, ensure_ascii=False, sort_keys=True).lower()
        for needle in FORBIDDEN_ROBUSTNESS_OPTIMIZER_TERMS:
            self.assertNotIn(needle, serialized)

    def _assert_robustness_payload_is_stored_evidence_contract(self, payload: dict) -> None:
        self.assertEqual(payload["source"], "summary.robustness_analysis")
        metadata = dict(payload.get("contract_metadata") or {})
        self.assertTrue(metadata.get("diagnostic_only"))
        self.assertFalse(metadata.get("parameter_selection_executed"))
        self.assertFalse(metadata.get("parameter_sweep_executed"))
        self.assertFalse(metadata.get("provider_calls_executed"))
        self.assertFalse(metadata.get("portfolio_allocation_backtest_executed"))
        self.assertFalse(metadata.get("professional_quant_readiness_claimed"))
        self.assertFalse(metadata.get("walk_forward_validation_claimed"))
        self.assertEqual(
            metadata.get("input_strategy_policy"),
            "reuse_input_strategy_without_parameter_search",
        )

        monte_carlo = dict(payload["monte_carlo"])
        monte_carlo_paths = list(monte_carlo["paths"])
        self.assertEqual(monte_carlo["state"], "available")
        self.assertEqual(monte_carlo["simulation_count"], len(monte_carlo_paths))
        self.assertGreater(monte_carlo["simulation_count"], 0)
        self.assertEqual(
            [path["simulation_index"] for path in monte_carlo_paths],
            list(range(1, monte_carlo["simulation_count"] + 1)),
        )
        self.assertTrue(all(path["state"] in {"completed", "no_result"} for path in monte_carlo_paths))
        self.assertTrue(all(isinstance(path.get("metrics"), dict) for path in monte_carlo_paths))
        self.assertIsInstance(monte_carlo["aggregate_metrics"], dict)
        self.assertIsInstance(monte_carlo["diagnostics"], list)

        stress_tests = dict(payload["stress_tests"])
        stress_scenarios = list(stress_tests["scenarios"])
        self.assertEqual(stress_tests["state"], "available")
        self.assertEqual(stress_tests["scenario_count"], len(stress_scenarios))
        self.assertEqual(
            [scenario["scenario_key"] for scenario in stress_scenarios],
            payload["configuration"]["stress_tests"]["scenario_keys"],
        )
        self.assertIn(
            stress_tests["worst_scenario"]["scenario_key"],
            {scenario["scenario_key"] for scenario in stress_scenarios},
        )
        self.assertIsInstance(stress_tests["diagnostics"], list)

        oos_evidence = dict(payload["walk_forward_oos_evidence"])
        self.assertEqual(oos_evidence["read_mode"], "stored_first")
        self.assertTrue(oos_evidence["diagnostic_only"])
        self.assertFalse(oos_evidence["decision_grade"])
        self.assertEqual(
            oos_evidence["authority"]["input_mode"],
            "stored_robustness_analysis_walk_forward",
        )
        self.assertEqual(oos_evidence["authority"]["adapter_execution_count"], 0)
        self.assertEqual(oos_evidence["authority"]["new_strategy_execution_count"], 0)
        self.assertFalse(oos_evidence["authority"]["provider_calls_executed"])
        self.assertFalse(oos_evidence["authority"]["engine_math_changed"])
        self.assertFalse(oos_evidence["authority"]["strategy_parameters_mutated"])
        self.assertFalse(oos_evidence["authority"]["optimizer_executed"])
        self.assertFalse(oos_evidence["authority"]["parameter_sweep_executed"])
        self._assert_robustness_payload_avoids_optimizer_semantics(payload)

    @staticmethod
    def _payload_without_allowed_oos_authority_flags(payload: object) -> object:
        normalized = copy.deepcopy(payload)
        if isinstance(normalized, dict):
            evidence_candidates = [normalized.get("walk_forward_oos_evidence")]
            oos_readiness = normalized.get("oos_readiness")
            if isinstance(oos_readiness, dict):
                evidence_candidates.append(oos_readiness.get("evidence"))
            for evidence in evidence_candidates:
                if isinstance(evidence, dict):
                    authority = evidence.get("authority")
                    if isinstance(authority, dict):
                        for key in ("optimizer_executed", "parameter_sweep_executed"):
                            if authority.get(key) is False:
                                authority.pop(key)
        return normalized

    @staticmethod
    def _payload_without_allowed_execution_model_guardrails(payload: object) -> object:
        normalized = copy.deepcopy(payload)
        if (
            isinstance(normalized, dict)
            and normalized.get("export_kind") == "rule_backtest_execution_model_metadata"
        ):
            guardrails = normalized.get("guardrails")
            if isinstance(guardrails, dict):
                for key in ("optimizer_executed", "parameter_sweep_executed", "winner_promotion"):
                    if guardrails.get(key) is False:
                        guardrails.pop(key)
        return normalized

    @staticmethod
    def _payload_without_allowed_oos_parameter_readiness_guardrails(payload: object) -> object:
        normalized = copy.deepcopy(payload)
        if (
            isinstance(normalized, dict)
            and normalized.get("export_kind") == "rule_backtest_oos_parameter_readiness"
        ):
            guardrails = normalized.get("guardrails")
            if isinstance(guardrails, dict):
                for key in ("optimizer_executed", "parameter_sweep_executed", "winner_promotion"):
                    if guardrails.get(key) is False:
                        guardrails.pop(key)
            limitations = normalized.get("limitations")
            if isinstance(limitations, list):
                normalized["limitations"] = [
                    item
                    for item in limitations
                    if item not in {"no_optimizer_execution", "no_winner_promotion"}
                ]
        return normalized

    def _fetch_support_bundle_surface(self, run_id: int, *, expect_oos_export: bool = True) -> dict:
        export_index_response = self.client.get(f"/api/v1/backtest/rule/runs/{run_id}/export-index")
        self.assertEqual(export_index_response.status_code, 200)
        export_index = export_index_response.json()

        self.assertEqual(export_index["run_id"], run_id)
        expected_keys = [
            "support_bundle_manifest_json",
            "support_bundle_reproducibility_manifest_json",
            "execution_trace_json",
            "execution_trace_csv",
            "robustness_evidence_json",
            "regime_attribution_readiness_json",
            "execution_model_metadata_json",
        ]
        expected_contracts = [
            ("json", "application/json", "api", "compact"),
            ("json", "application/json", "api", "compact"),
            ("json", "application/json", "api", "heavy"),
            ("csv", "text/csv", "api", "heavy"),
            ("json", "application/json", "api", "heavy"),
            ("json", "application/json", "api", "compact"),
            ("json", "application/json", "api", "compact"),
        ]
        if expect_oos_export:
            expected_keys.append("oos_parameter_readiness_json")
            expected_contracts.append(("json", "application/json", "api", "compact"))
        self.assertEqual([item["key"] for item in export_index["exports"]], expected_keys)
        self.assertEqual(
            [
                (item["format"], item["media_type"], item["delivery_mode"], item["payload_class"])
                for item in export_index["exports"]
            ],
            expected_contracts,
        )

        manifest_response = self.client.get(export_index["exports"][0]["endpoint_path"])
        reproducibility_response = self.client.get(export_index["exports"][1]["endpoint_path"])
        self.assertEqual(manifest_response.status_code, 200)
        self.assertEqual(reproducibility_response.status_code, 200)

        manifest = manifest_response.json()
        reproducibility = reproducibility_response.json()

        return {
            "export_index": export_index,
            "manifest": manifest,
            "reproducibility": reproducibility,
            "manifest_content_type": manifest_response.headers.get("content-type", ""),
            "reproducibility_content_type": reproducibility_response.headers.get("content-type", ""),
        }

    def _assert_service_http_support_bundle_parity(
        self,
        *,
        service: RuleBacktestService,
        run_id: int,
        payloads: dict,
        trace_available: bool,
    ) -> None:
        self.assertEqual(service.get_support_export_index(run_id), payloads["export_index"])
        service_manifest = service.get_support_bundle_manifest(run_id)
        service_reproducibility = service.get_support_bundle_reproducibility_manifest(run_id)
        self.assertEqual(
            RuleBacktestSupportBundleManifestResponse.model_validate(service_manifest).model_dump(
                mode="json"
            ),
            payloads["manifest"],
        )
        self.assertEqual(
            RuleBacktestSupportBundleReproducibilityManifestResponse.model_validate(
                service_reproducibility
            ).model_dump(mode="json"),
            payloads["reproducibility"],
        )
        self.assertEqual(
            service_manifest["dataset_manifest_identity"],
            service_reproducibility["dataset_manifest_identity"],
        )
        self.assertEqual(
            service_manifest["dataset_reproducibility_manifest"],
            service_reproducibility["dataset_reproducibility_manifest"],
        )

        trace_json_path = payloads["export_index"]["exports"][2]["endpoint_path"]
        trace_csv_path = payloads["export_index"]["exports"][3]["endpoint_path"]
        robustness_path = payloads["export_index"]["exports"][4]["endpoint_path"]
        readiness_path = payloads["export_index"]["exports"][5]["endpoint_path"]
        execution_model_metadata_path = payloads["export_index"]["exports"][6]["endpoint_path"]
        oos_parameter_readiness_path = payloads["export_index"]["exports"][7]["endpoint_path"]
        trace_json_response = self.client.get(trace_json_path)
        trace_csv_response = self.client.get(trace_csv_path)
        robustness_response = self.client.get(robustness_path)
        readiness_response = self.client.get(readiness_path)
        execution_model_metadata_response = self.client.get(execution_model_metadata_path)
        oos_parameter_readiness_response = self.client.get(oos_parameter_readiness_path)
        self.assertEqual(readiness_response.status_code, 200)
        self.assertEqual(
            service.get_regime_attribution_readiness_export(run_id),
            readiness_response.json(),
        )
        self.assertEqual(execution_model_metadata_response.status_code, 200)
        self.assertEqual(oos_parameter_readiness_response.status_code, 200)
        self.assertEqual(
            service.get_oos_parameter_readiness_export(run_id),
            oos_parameter_readiness_response.json(),
        )

        if trace_available:
            self.assertEqual(service.get_execution_trace_export_json(run_id), trace_json_response.json())
            self.assertEqual(
                service.get_execution_trace_export_csv_text(run_id),
                trace_csv_response.text,
            )
        else:
            with self.assertRaisesRegex(ValueError, "has no audit rows to export"):
                service.get_execution_trace_export_json(run_id)
            with self.assertRaisesRegex(ValueError, "has no audit rows to export"):
                service.get_execution_trace_export_csv_text(run_id)

        robustness_available = payloads["export_index"]["exports"][4]["available"]
        if robustness_available:
            service_payload = service.get_robustness_evidence_export_json(run_id)
            http_payload = robustness_response.json()
            self.assertEqual(http_payload["state"], service_payload["state"])
            self.assertEqual(http_payload["seed"], service_payload["seed"])
            self.assertEqual(http_payload["configuration"], service_payload["configuration"])
            self.assertEqual(http_payload["walk_forward"], service_payload["walk_forward"])
            self.assertEqual(http_payload["monte_carlo"], service_payload["monte_carlo"])
            self.assertEqual(http_payload["stress_tests"], service_payload["stress_tests"])
            self.assertEqual(http_payload["diagnostics"], service_payload["diagnostics"])
            self.assertEqual(
                http_payload["walk_forward_oos_evidence"],
                service_payload["walk_forward_oos_evidence"],
            )
            self.assertEqual(
                service_payload["walk_forward_oos_evidence"]["contract_kind"],
                "backtest_walk_forward_oos_diagnostic_evidence",
            )
            self.assertIn("profile", http_payload)
            self.assertIn("source", http_payload)
            self.assertIsNone(http_payload["profile"])
            self.assertEqual(http_payload["source"], "summary.robustness_analysis")
            self._assert_robustness_payload_is_stored_evidence_contract(service_payload)
            self._assert_robustness_payload_is_stored_evidence_contract(http_payload)
            self._assert_robustness_payload_avoids_optimizer_semantics(service_payload)
            self._assert_robustness_payload_avoids_optimizer_semantics(http_payload)
        else:
            with self.assertRaisesRegex(ValueError, "has no stored robustness evidence to export"):
                service.get_robustness_evidence_export_json(run_id)

        execution_model_metadata = execution_model_metadata_response.json()
        stored_run = service.get_run(run_id)
        assert stored_run is not None
        self.assertEqual(execution_model_metadata["source"], "run.execution_model")
        self.assertEqual(execution_model_metadata["read_mode"], "stored_first")
        self.assertEqual(
            execution_model_metadata["execution_model"],
            stored_run["execution_model"],
        )
        self.assertEqual(
            execution_model_metadata["execution_model"]["model_id"],
            "rule_backtest_default_execution_model_v1",
        )
        self.assertEqual(execution_model_metadata["execution_model"]["version"], "v1")
        self.assertEqual(
            execution_model_metadata["semantics"]["engine_identity"],
            "canonical_registered_rule_backtest_execution",
        )
        self.assertFalse(execution_model_metadata["semantics"]["institutional_execution_realism"])
        self.assertFalse(execution_model_metadata["semantics"]["decision_grade"])
        self.assertFalse(execution_model_metadata["semantics"]["provider_calls_required"])
        self.assertFalse(execution_model_metadata["semantics"]["live_provider_calls_required"])
        self.assertEqual(
            execution_model_metadata["guardrails"]["future_semantic_changes_require_new_version"],
            True,
        )
        oos_parameter_readiness = oos_parameter_readiness_response.json()
        self.assertEqual(oos_parameter_readiness["export_kind"], "rule_backtest_oos_parameter_readiness")
        self.assertEqual(oos_parameter_readiness["read_mode"], "stored_first")
        self.assertTrue(oos_parameter_readiness["diagnostic_only"])
        self.assertFalse(oos_parameter_readiness["decision_grade"])
        self.assertIn(oos_parameter_readiness["overall_state"], {"partial", "unavailable"})
        self.assertEqual(
            oos_parameter_readiness["oos_readiness"]["source"],
            "stored_robustness_analysis.walk_forward",
        )
        self.assertEqual(
            oos_parameter_readiness["oos_readiness"]["evidence"]["contract_kind"],
            "backtest_walk_forward_oos_diagnostic_evidence",
        )
        self.assertEqual(oos_parameter_readiness["parameter_readiness"]["state"], "unavailable")
        self.assertEqual(
            oos_parameter_readiness["parameter_readiness"]["availability_reason"],
            "stored_compare_summary_missing",
        )
        self.assertIsNone(oos_parameter_readiness["parameter_readiness"]["evidence"])
        self.assertFalse(oos_parameter_readiness["guardrails"]["provider_calls_executed"])
        self.assertFalse(oos_parameter_readiness["guardrails"]["optimizer_executed"])
        self.assertFalse(oos_parameter_readiness["guardrails"]["parameter_sweep_executed"])
        self.assertFalse(oos_parameter_readiness["guardrails"]["winner_promotion"])

    def _assert_support_bundle_surface(
        self,
        *,
        run_id: int,
        trace_available: bool,
    ) -> dict:
        payloads = self._fetch_support_bundle_surface(run_id)
        export_index = payloads["export_index"]
        manifest = payloads["manifest"]
        reproducibility = payloads["reproducibility"]

        self.assertEqual(manifest["run"]["id"], run_id)
        self.assertEqual(reproducibility["run"]["id"], run_id)
        self.assertEqual(manifest["run"]["status"], export_index["status"])
        self.assertEqual(reproducibility["run"]["status"], export_index["status"])
        self.assertEqual(manifest["manifest_kind"], "rule_backtest_support_bundle")
        self.assertEqual(
            reproducibility["manifest_kind"],
            "rule_backtest_reproducibility_manifest",
        )
        self.assertEqual(manifest["run_timing"], reproducibility["run_timing"])
        self.assertEqual(manifest["run_diagnostics"], reproducibility["run_diagnostics"])
        self.assertEqual(manifest["artifact_availability"], reproducibility["artifact_availability"])
        self.assertEqual(manifest["readback_integrity"], reproducibility["readback_integrity"])
        self.assertEqual(
            manifest["result_authority"]["contract_version"],
            reproducibility["result_authority"]["contract_version"],
        )
        self.assertEqual(
            manifest["result_authority"]["read_mode"],
            reproducibility["result_authority"]["read_mode"],
        )
        self.assertEqual(manifest["result_authority"]["read_mode"], "stored_first")
        self.assertEqual(
            reproducibility["result_authority"]["domains"],
            {
                domain_name: {
                    "source": domain_payload["source"],
                    "completeness": domain_payload["completeness"],
                    "state": domain_payload["state"],
                }
                for domain_name, domain_payload in manifest["result_authority"]["domains"].items()
            },
        )
        self.assertEqual(
            reproducibility["execution_assumptions_fingerprint"]["source"],
            manifest["result_authority"]["domains"]["execution_assumptions_snapshot"]["source"],
        )
        self.assertEqual(
            reproducibility["execution_assumptions_fingerprint"]["completeness"],
            manifest["result_authority"]["domains"]["execution_assumptions_snapshot"]["completeness"],
        )
        self.assertEqual(
            [item["endpoint_path"] for item in export_index["exports"]],
            [
                f"/api/v1/backtest/rule/runs/{run_id}/support-bundle-manifest",
                f"/api/v1/backtest/rule/runs/{run_id}/support-bundle-reproducibility-manifest",
                f"/api/v1/backtest/rule/runs/{run_id}/execution-trace.json",
                f"/api/v1/backtest/rule/runs/{run_id}/execution-trace.csv",
                f"/api/v1/backtest/rule/runs/{run_id}/robustness-evidence.json",
                f"/api/v1/backtest/rule/runs/{run_id}/regime-attribution-readiness.json",
                f"/api/v1/backtest/rule/runs/{run_id}/execution-model-metadata.json",
                f"/api/v1/backtest/rule/runs/{run_id}/oos-parameter-readiness.json",
            ],
        )
        self.assertTrue(
            payloads["manifest_content_type"].startswith(export_index["exports"][0]["media_type"])
        )
        self.assertTrue(
            payloads["reproducibility_content_type"].startswith(
                export_index["exports"][1]["media_type"]
            )
        )

        trace_json_path = export_index["exports"][2]["endpoint_path"]
        trace_csv_path = export_index["exports"][3]["endpoint_path"]
        robustness_path = export_index["exports"][4]["endpoint_path"]
        readiness_path = export_index["exports"][5]["endpoint_path"]
        execution_model_metadata_path = export_index["exports"][6]["endpoint_path"]
        oos_parameter_readiness_path = export_index["exports"][7]["endpoint_path"]
        trace_json_response = self.client.get(trace_json_path)
        trace_csv_response = self.client.get(trace_csv_path)
        robustness_response = self.client.get(robustness_path)
        readiness_response = self.client.get(readiness_path)
        execution_model_metadata_response = self.client.get(execution_model_metadata_path)
        oos_parameter_readiness_response = self.client.get(oos_parameter_readiness_path)
        self.assertTrue(export_index["exports"][5]["available"])
        self.assertEqual(
            export_index["exports"][5]["availability_reason"],
            "run_exists_readiness_projection_available",
        )
        self.assertTrue(export_index["exports"][6]["available"])
        self.assertEqual(
            export_index["exports"][6]["availability_reason"],
            "run_exists_execution_model_metadata_projection_available",
        )
        self.assertTrue(export_index["exports"][7]["available"])
        self.assertEqual(
            export_index["exports"][7]["availability_reason"],
            "run_exists_oos_parameter_readiness_projection_available",
        )
        self.assertEqual(readiness_response.status_code, 200)
        self.assertEqual(execution_model_metadata_response.status_code, 200)
        self.assertEqual(oos_parameter_readiness_response.status_code, 200)
        self.assertTrue(
            readiness_response.headers.get("content-type", "").startswith(
                export_index["exports"][5]["media_type"]
            )
        )
        self.assertTrue(
            execution_model_metadata_response.headers.get("content-type", "").startswith(
                export_index["exports"][6]["media_type"]
            )
        )
        self.assertTrue(
            oos_parameter_readiness_response.headers.get("content-type", "").startswith(
                export_index["exports"][7]["media_type"]
            )
        )
        payloads["regime_attribution_readiness"] = readiness_response.json()
        payloads["execution_model_metadata"] = execution_model_metadata_response.json()
        payloads["oos_parameter_readiness"] = oos_parameter_readiness_response.json()
        self.assertTrue(payloads["regime_attribution_readiness"]["diagnosticOnly"])
        self.assertFalse(payloads["regime_attribution_readiness"]["engineReexecuted"])
        self.assertFalse(payloads["regime_attribution_readiness"]["mathChanged"])
        self.assertFalse(payloads["regime_attribution_readiness"]["attributionEngineAvailable"])
        self.assertFalse(payloads["regime_attribution_readiness"]["pnlCausalityAvailable"])
        self.assertEqual(
            payloads["execution_model_metadata"]["execution_model"]["model_id"],
            "rule_backtest_default_execution_model_v1",
        )
        self.assertEqual(payloads["execution_model_metadata"]["execution_model"]["version"], "v1")
        self.assertEqual(
            payloads["execution_model_metadata"]["semantics"]["cost_realism"],
            "configured_bps_with_explicit_presence_state",
        )
        self.assertFalse(payloads["execution_model_metadata"]["semantics"]["decision_grade"])
        self.assertFalse(
            payloads["execution_model_metadata"]["semantics"]["institutional_execution_realism"]
        )
        self.assertEqual(
            payloads["execution_model_metadata"]["guardrails"]["provider_calls_executed"],
            False,
        )
        self.assertEqual(
            payloads["oos_parameter_readiness"]["export_kind"],
            "rule_backtest_oos_parameter_readiness",
        )
        self.assertEqual(payloads["oos_parameter_readiness"]["read_mode"], "stored_first")
        self.assertTrue(payloads["oos_parameter_readiness"]["diagnostic_only"])
        self.assertFalse(payloads["oos_parameter_readiness"]["decision_grade"])
        self.assertIn(payloads["oos_parameter_readiness"]["overall_state"], {"partial", "unavailable"})
        self.assertEqual(
            payloads["oos_parameter_readiness"]["oos_readiness"]["source"],
            "stored_robustness_analysis.walk_forward",
        )
        self.assertEqual(
            payloads["oos_parameter_readiness"]["parameter_readiness"]["state"],
            "unavailable",
        )
        self.assertEqual(
            payloads["oos_parameter_readiness"]["parameter_readiness"]["availability_reason"],
            "stored_compare_summary_missing",
        )
        self.assertIsNone(payloads["oos_parameter_readiness"]["parameter_readiness"]["evidence"])

        if trace_available:
            self.assertTrue(export_index["exports"][2]["available"])
            self.assertTrue(export_index["exports"][3]["available"])
            self.assertEqual(
                export_index["exports"][2]["availability_reason"],
                "execution_trace_rows_present",
            )
            self.assertEqual(
                export_index["exports"][3]["availability_reason"],
                "execution_trace_rows_present",
            )
            self.assertEqual(trace_json_response.status_code, 200)
            self.assertEqual(trace_csv_response.status_code, 200)
            self.assertTrue(
                trace_json_response.headers.get("content-type", "").startswith(
                    export_index["exports"][2]["media_type"]
                )
            )
            self.assertTrue(
                trace_csv_response.headers.get("content-type", "").startswith(
                    export_index["exports"][3]["media_type"]
                )
            )
            self.assertIn(
                f'rule-backtest-{run_id}-execution-trace.csv',
                trace_csv_response.headers.get("content-disposition", ""),
            )

            trace_json = trace_json_response.json()
            trace_csv_rows = list(csv.DictReader(trace_csv_response.text.splitlines()))
            self.assertEqual(list(trace_json.keys()), EXPECTED_TRACE_EXPORT_JSON_KEYS)
            self.assertEqual(
                reproducibility["result_authority"]["domains"]["execution_trace"]["source"],
                trace_json["source"],
            )
            self.assertEqual(
                reproducibility["result_authority"]["domains"]["execution_trace"]["completeness"],
                trace_json["completeness"],
            )
            self.assertEqual(
                list(trace_json["trace_rows"][0].keys()),
                EXPECTED_TRACE_EXPORT_FIELD_LABELS,
            )
            self.assertEqual(
                trace_csv_response.text.splitlines()[0].split(","),
                EXPECTED_TRACE_EXPORT_FIELD_LABELS,
            )
            self.assertEqual(
                len(trace_json["trace_rows"]),
                manifest["artifact_counts"]["execution_trace_rows_count"],
            )
            self.assertEqual(len(trace_json["trace_rows"]), len(trace_csv_rows))
            self.assertEqual(
                trace_json["benchmark_summary"].get("requested_mode"),
                manifest["run"]["benchmark_mode"],
            )
            self.assertEqual(
                trace_json["source"],
                manifest["result_authority"]["domains"]["execution_trace"]["source"],
            )
            payloads["trace_json"] = trace_json
            payloads["trace_csv_rows"] = trace_csv_rows
        else:
            self.assertFalse(export_index["exports"][2]["available"])
            self.assertFalse(export_index["exports"][3]["available"])
            self.assertEqual(
                export_index["exports"][2]["availability_reason"],
                "execution_trace_rows_missing",
            )
            self.assertEqual(
                export_index["exports"][3]["availability_reason"],
                "execution_trace_rows_missing",
            )
            self.assertEqual(trace_json_response.status_code, 409)
            self.assertEqual(trace_csv_response.status_code, 409)
            self.assertEqual(self._error_code(trace_json_response), "export_unavailable")
            self.assertEqual(self._error_code(trace_csv_response), "export_unavailable")
            self.assertTrue(
                trace_json_response.headers.get("content-type", "").startswith("application/json")
            )
            self.assertTrue(
                trace_csv_response.headers.get("content-type", "").startswith("application/json")
            )
            self.assertEqual(
                reproducibility["result_authority"]["domains"]["execution_trace"]["source"],
                "unavailable",
            )
            self.assertEqual(
                reproducibility["result_authority"]["domains"]["execution_trace"]["completeness"],
                "unavailable",
            )
            self.assertEqual(
                reproducibility["result_authority"]["domains"]["execution_trace"]["state"],
                "unavailable",
            )

        robustness_available = export_index["exports"][4]["available"]
        if robustness_available:
            self.assertEqual(
                export_index["exports"][4]["availability_reason"],
                "stored_robustness_analysis_present",
            )
            self.assertEqual(robustness_response.status_code, 200)
            self.assertTrue(
                robustness_response.headers.get("content-type", "").startswith(
                    export_index["exports"][4]["media_type"]
                )
            )
            payloads["robustness"] = robustness_response.json()
            self._assert_robustness_payload_is_stored_evidence_contract(payloads["robustness"])
            self._assert_robustness_payload_avoids_optimizer_semantics(payloads["robustness"])
        else:
            self.assertEqual(
                export_index["exports"][4]["availability_reason"],
                "stored_robustness_analysis_missing",
            )
            self.assertEqual(robustness_response.status_code, 409)
            self.assertEqual(self._error_code(robustness_response), "export_unavailable")
            self.assertTrue(
                robustness_response.headers.get("content-type", "").startswith("application/json")
            )

        return payloads

    def test_support_bundle_e2e_stored_first_surface_is_coherent(self) -> None:
        service, response = self._run_completed_backtest()

        payloads = self._assert_support_bundle_surface(
            run_id=int(response["id"]),
            trace_available=True,
        )
        self._assert_service_http_support_bundle_parity(
            service=service,
            run_id=int(response["id"]),
            payloads=payloads,
            trace_available=True,
        )

        self.assertEqual(
            payloads["manifest"]["artifact_availability"]["source"],
            "summary.artifact_availability",
        )
        self.assertEqual(
            payloads["trace_json"]["benchmark_summary"],
            response["benchmark_summary"],
        )
        self.assertEqual(
            payloads["reproducibility"]["execution_assumptions_fingerprint"]["summary_text"],
            response["execution_assumptions_snapshot"]["payload"].get("summary_text"),
        )
        self.assertEqual(
            payloads["reproducibility"]["execution_assumptions_fingerprint"]["hash_sha256"],
            hashlib.sha256(
                json.dumps(
                    response["execution_assumptions_snapshot"]["payload"],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        )
        self.assertEqual(payloads["manifest"]["dataset_lineage"], payloads["reproducibility"]["dataset_lineage"])
        self.assertEqual(payloads["manifest"]["dataset_lineage"]["source"], "local_us_parquet")
        self.assertEqual(payloads["manifest"]["dataset_lineage"]["provider"], "Local US Parquet")
        self.assertEqual(payloads["manifest"]["dataset_lineage"]["authority_status"], "allowed")
        self.assertEqual(payloads["manifest"]["dataset_lineage"]["authority_source_type"], "cache_snapshot")
        self.assertEqual(payloads["manifest"]["dataset_lineage"]["authority_reason_codes"], [])
        self.assertTrue(payloads["manifest"]["dataset_lineage"]["authority_allowed"])
        self.assertFalse(payloads["manifest"]["dataset_lineage"]["degraded_fill_only"])
        self.assertEqual(payloads["manifest"]["dataset_lineage"]["dataset_version"], "unknown")
        self.assertGreater(payloads["manifest"]["dataset_lineage"]["bar_count"], 0)
        self.assertTrue(payloads["manifest"]["artifact_availability"]["has_trade_rows"])
        self.assertTrue(payloads["manifest"]["artifact_availability"]["has_execution_trace"])
        self.assertFalse(payloads["manifest"]["readback_integrity"]["used_live_storage_repair"])
        self.assertGreater(payloads["manifest"]["artifact_counts"]["execution_trace_rows_count"], 0)

    def test_support_bundle_e2e_robustness_evidence_readback_uses_stored_payload_without_recompute(self) -> None:
        service, response = self._run_completed_backtest()
        stored_robustness = dict(response["robustness_analysis"])

        with patch.object(
            RuleBacktestService,
            "_build_robustness_analysis",
            side_effect=AssertionError("robustness export must not recompute robustness_analysis"),
        ), patch.object(
            RuleBacktestService,
            "_build_monte_carlo_analysis",
            side_effect=AssertionError("robustness export must not recompute monte_carlo"),
        ), patch.object(
            RuleBacktestService,
            "_build_stress_test_analysis",
            side_effect=AssertionError("robustness export must not recompute stress_tests"),
        ), patch.object(
            RuleBacktestService,
            "_run_robustness_backtest",
            side_effect=AssertionError("robustness export must not run robustness backtests"),
        ):
            payloads = self._assert_support_bundle_surface(
                run_id=int(response["id"]),
                trace_available=True,
            )
            self._assert_service_http_support_bundle_parity(
                service=service,
                run_id=int(response["id"]),
                payloads=payloads,
                trace_available=True,
            )

        robustness_payload = payloads["robustness"]
        self.assertEqual(robustness_payload["configuration"], stored_robustness["configuration"])
        self.assertEqual(robustness_payload["monte_carlo"], stored_robustness["monte_carlo"])
        self.assertEqual(robustness_payload["stress_tests"], stored_robustness["stress_tests"])
        self.assertEqual(robustness_payload["diagnostics"], stored_robustness["diagnostics"])
        self._assert_robustness_payload_is_stored_evidence_contract(robustness_payload)

    def test_support_bundle_e2e_projects_authority_reason_families_for_local_cache_lineage(self) -> None:
        service, response = self._run_completed_backtest()
        run_row = service.repo.get_run(response["id"])
        assert run_row is not None

        summary = json.loads(run_row.summary_json)
        data_quality = dict(summary.get("data_quality") or {})
        data_quality["authority_reason_codes"] = [
            "proxy_source_not_reproducible",
            "totally_new_reason_code",
        ]
        summary["data_quality"] = data_quality
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        payloads = self._assert_support_bundle_surface(
            run_id=int(response["id"]),
            trace_available=True,
        )

        lineage = payloads["manifest"]["dataset_lineage"]
        self.assertEqual(lineage["source"], "local_us_parquet")
        self.assertEqual(lineage["authority_source_type"], "cache_snapshot")
        self.assertEqual(
            lineage["authority_reason_codes"],
            ["proxy_source_not_reproducible", "totally_new_reason_code"],
        )
        self.assertEqual(
            lineage["authority_reason_families"],
            [
                {
                    "raw_code": "proxy_source_not_reproducible",
                    "family": "reproducibility_degraded",
                    "scope": "backtest_authority",
                },
                {
                    "raw_code": "totally_new_reason_code",
                    "family": "unclassified",
                    "scope": None,
                },
            ],
        )
        self.assertEqual(lineage, payloads["reproducibility"]["dataset_lineage"])
        self.assertGreater(payloads["manifest"]["artifact_counts"]["execution_trace_rows_count"], 0)

    def test_support_bundle_e2e_live_storage_repair_preserves_http_contract(self) -> None:
        service, response = self._run_completed_backtest()
        deleted = service.repo.delete_trades_by_run_ids([response["id"]])
        self.assertGreater(deleted, 0)

        payloads = self._assert_support_bundle_surface(
            run_id=int(response["id"]),
            trace_available=True,
        )
        self._assert_service_http_support_bundle_parity(
            service=service,
            run_id=int(response["id"]),
            payloads=payloads,
            trace_available=True,
        )

        self.assertEqual(
            payloads["manifest"]["artifact_availability"]["source"],
            "summary.artifact_availability+live_storage_repair",
        )
        self.assertFalse(payloads["manifest"]["artifact_availability"]["has_trade_rows"])
        self.assertEqual(payloads["manifest"]["artifact_counts"]["trade_rows_count"], 0)
        self.assertTrue(payloads["manifest"]["readback_integrity"]["used_live_storage_repair"])
        self.assertTrue(payloads["manifest"]["readback_integrity"]["has_summary_storage_drift"])
        self.assertEqual(payloads["manifest"]["readback_integrity"]["drift_domains"], ["trade_rows"])
        self.assertEqual(payloads["manifest"]["readback_integrity"]["integrity_level"], "drift_repaired")

    def test_support_bundle_e2e_missing_trace_closes_trace_exports(self) -> None:
        service, response = self._run_completed_backtest()
        run_row = service.repo.get_run(response["id"])
        assert run_row is not None

        summary = json.loads(run_row.summary_json)
        summary["execution_trace"] = {}
        summary["visualization"] = dict(summary.get("visualization") or {})
        summary["visualization"]["audit_rows"] = []
        summary["visualization"]["daily_return_series"] = []
        summary["visualization"]["exposure_curve"] = []
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        payloads = self._assert_support_bundle_surface(
            run_id=int(response["id"]),
            trace_available=False,
        )
        self._assert_service_http_support_bundle_parity(
            service=service,
            run_id=int(response["id"]),
            payloads=payloads,
            trace_available=False,
        )

        self.assertFalse(payloads["manifest"]["artifact_availability"]["has_execution_trace"])
        self.assertEqual(payloads["manifest"]["artifact_counts"]["execution_trace_rows_count"], 0)
        self.assertEqual(
            payloads["manifest"]["result_authority"]["domains"]["execution_trace"]["source"],
            "unavailable",
        )

    def test_support_bundle_e2e_report_export_safety_smoke(self) -> None:
        service, response = self._run_completed_backtest(fee_bps=1.5, slippage_bps=2.5)
        run_row = service.repo.get_run(response["id"])
        assert run_row is not None

        summary = json.loads(run_row.summary_json)
        execution_trace = dict(summary.get("execution_trace") or {})
        trace_rows = list(execution_trace.get("rows") or [])
        if trace_rows:
            first_row = dict(trace_rows[0] or {})
            first_row.update(
                {
                    "synthetic_execution_trace_detail": "synthetic_execution_trace_detail",
                    "notes": "synthetic_debug_reason",
                    "fallback": {
                        "code": "open_missing_close_fallback",
                        "applied": True,
                        "authority": "stored_trace_row",
                        "synthetic_provider_url": "synthetic_provider_url",
                    },
                    "assumptions_defaults": {
                        "summary_text": "row assumptions",
                        "synthetic_cache_key": "synthetic_cache_key",
                    },
                }
            )
            trace_rows[0] = first_row
            execution_trace["rows"] = trace_rows
        execution_trace["missing_fields"] = ["synthetic_debug_reason"]
        execution_trace["assumptions_defaults"] = {
            **dict(execution_trace.get("assumptions_defaults") or {}),
            "synthetic_cache_key": "synthetic_cache_key",
        }
        execution_trace["execution_model"] = {
            **dict(execution_trace.get("execution_model") or {}),
            "synthetic_provider_url": "synthetic_provider_url",
        }
        execution_trace["execution_assumptions"] = {
            **dict(execution_trace.get("execution_assumptions") or {}),
            "synthetic_request_id": "synthetic_request_id",
        }
        execution_trace["fallback"] = {
            **dict(execution_trace.get("fallback") or {}),
            "synthetic_execution_trace_detail": "synthetic_execution_trace_detail",
        }
        summary["execution_trace"] = execution_trace

        run_timing = dict(summary.get("run_timing") or {})
        run_timing["synthetic_request_id"] = "synthetic_request_id"
        summary["run_timing"] = run_timing

        run_diagnostics = dict(summary.get("run_diagnostics") or {})
        run_diagnostics["synthetic_debug_reason"] = "synthetic_debug_reason"
        summary["run_diagnostics"] = run_diagnostics

        artifact_availability = dict(summary.get("artifact_availability") or {})
        artifact_availability["synthetic_cache_key"] = "synthetic_cache_key"
        summary["artifact_availability"] = artifact_availability

        readback_integrity = dict(summary.get("readback_integrity") or {})
        readback_integrity["synthetic_stack_trace"] = "synthetic_stack_trace"
        summary["readback_integrity"] = readback_integrity

        result_authority = dict(summary.get("result_authority") or {})
        domains = dict(result_authority.get("domains") or {})
        execution_trace_authority = dict(domains.get("execution_trace") or {})
        execution_trace_authority["synthetic_provider_url"] = "synthetic_provider_url"
        execution_trace_authority[
            "synthetic_execution_trace_detail"
        ] = "synthetic_execution_trace_detail"
        domains["execution_trace"] = execution_trace_authority
        result_authority["domains"] = domains
        summary["result_authority"] = result_authority

        benchmark_summary = dict(summary.get("benchmark_summary") or {})
        benchmark_summary["synthetic_stack_trace"] = "synthetic_stack_trace"
        summary["benchmark_summary"] = benchmark_summary

        data_quality = dict(summary.get("data_quality") or {})
        data_quality["synthetic_cache_key"] = "synthetic_cache_key"
        data_quality["authority_reason_codes"] = list(data_quality.get("authority_reason_codes") or []) + [
            "synthetic_debug_reason"
        ]
        summary["data_quality"] = data_quality

        summary.update(
            {
                "raw_provider_payload": "RAW_PROVIDER_PAYLOAD_SHOULD_NOT_LEAK",
                "provider_payload": {"token": "TOKEN_VALUE_SHOULD_NOT_LEAK"},
                "payload_json": {"session": "SESSION_VALUE_SHOULD_NOT_LEAK"},
                "broker_credentials": {"api_key": "BROKER_CREDENTIAL_SHOULD_NOT_LEAK"},
                "provider_credentials": {"api_key": "PROVIDER_CREDENTIAL_SHOULD_NOT_LEAK"},
                "brokerOrderPayload": {"endpoint": "/api/v1/broker/orders"},
                "order_payload": "ORDER_PAYLOAD_SHOULD_NOT_LEAK",
                "place_order": "PLACE_ORDER_SHOULD_NOT_LEAK",
                "secret": "SECRET_VALUE_SHOULD_NOT_LEAK",
                "password": "PASSWORD_VALUE_SHOULD_NOT_LEAK",
            }
        )
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        payloads = self._assert_support_bundle_surface(
            run_id=int(response["id"]),
            trace_available=True,
        )

        self._assert_export_payload_is_sanitized(payloads["export_index"])
        self._assert_export_payload_is_sanitized(payloads["manifest"])
        self._assert_export_payload_is_sanitized(payloads["reproducibility"])
        self._assert_export_payload_is_sanitized(payloads["trace_json"])
        self._assert_export_payload_is_sanitized(payloads["trace_csv_rows"])
        self._assert_export_payload_is_sanitized(payloads["regime_attribution_readiness"])
        self._assert_export_payload_is_sanitized(payloads["execution_model_metadata"])
        self._assert_export_payload_is_sanitized(payloads["oos_parameter_readiness"])

        trace_execution_model = payloads["trace_json"]["execution_model"]
        self.assertEqual(trace_execution_model["signal_evaluation_timing"], "bar_close")
        self.assertEqual(trace_execution_model["entry_timing"], "next_bar_open")
        self.assertEqual(trace_execution_model["entry_fill_price_basis"], "open")
        self.assertEqual(trace_execution_model["fee_bps_per_side"], 1.5)
        self.assertEqual(trace_execution_model["slippage_bps_per_side"], 2.5)

        trace_assumptions = payloads["trace_json"]["execution_assumptions"]
        self.assertEqual(trace_assumptions["entry_fill_timing"], "next_bar_open")
        self.assertEqual(trace_assumptions["fee_model"]["commission_bps"], 1.5)
        self.assertEqual(trace_assumptions["slippage_model"]["slippage_bps"], 2.5)
        self.assertIn("run_fallback", payloads["trace_json"]["fallback"])
        self.assertIn("trace_rebuilt", payloads["trace_json"]["fallback"])
        self.assertEqual(
            payloads["manifest"]["result_authority"]["domains"]["execution_trace"]["source"],
            "summary.execution_trace",
        )
        self.assertEqual(
            payloads["reproducibility"]["result_authority"]["domains"]["execution_trace"],
            {
                "source": "summary.execution_trace",
                "completeness": "complete",
                "state": "available",
            },
        )

    def test_support_bundle_e2e_insufficient_history_export_surface_is_sanitized(self) -> None:
        _, response = self._run_insufficient_history_backtest()

        payloads = self._fetch_support_bundle_surface(
            int(response["id"]),
            expect_oos_export=False,
        )
        export_index = payloads["export_index"]
        trace_json_response = self.client.get(export_index["exports"][2]["endpoint_path"])
        trace_csv_response = self.client.get(export_index["exports"][3]["endpoint_path"])

        self.assertEqual(payloads["manifest"]["run"]["no_result_reason"], "insufficient_history")
        self.assertEqual(payloads["manifest"]["run"]["trade_count"], 0)
        self.assertEqual(payloads["manifest"]["artifact_counts"]["execution_trace_rows_count"], 0)
        self.assertEqual(trace_json_response.status_code, 409)
        self.assertEqual(trace_csv_response.status_code, 409)
        self.assertEqual(self._error_code(trace_json_response), "export_unavailable")
        self.assertEqual(self._error_code(trace_csv_response), "export_unavailable")
        self.assertFalse(export_index["exports"][2]["available"])
        self.assertFalse(export_index["exports"][3]["available"])
        self.assertNotIn(
            "oos_parameter_readiness_json",
            [item["key"] for item in export_index["exports"]],
        )
        self.assertEqual(
            export_index["exports"][2]["availability_reason"],
            "execution_trace_rows_missing",
        )
        self.assertEqual(
            export_index["exports"][3]["availability_reason"],
            "execution_trace_rows_missing",
        )
        self._assert_export_payload_is_sanitized(payloads["export_index"])
        self._assert_export_payload_is_sanitized(payloads["manifest"])
        self._assert_export_payload_is_sanitized(payloads["reproducibility"])
        self._assert_export_payload_is_sanitized(trace_json_response.json())
        self._assert_export_payload_is_sanitized(trace_csv_response.json())
