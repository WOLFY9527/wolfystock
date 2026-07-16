# -*- coding: utf-8 -*-
"""Focused API contract tests for additive portfolio diagnostics fields."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
from fastapi.testclient import TestClient

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.app import create_app
from src.config import Config
from src.storage import DatabaseManager


def _reset_public_limiter_state_if_available() -> None:
    try:
        from api.middlewares.public_abuse_limiter import reset_public_api_abuse_limiter_state
    except ModuleNotFoundError:
        return
    reset_public_api_abuse_limiter_state()


_ADMIN_DIAGNOSTIC_CAMEL_BOUNDARY_RE = re.compile(r"(?<!^)(?=[A-Z])")
_SNAPSHOT_SCHEMA_VERSION = "portfolio_snapshot_consumer_v1"
_RISK_SCHEMA_VERSION = "portfolio_risk_consumer_v1"
_NO_ADVICE_DISCLOSURE = (
    "Observation-only portfolio research context; not personalized financial advice and not an instruction."
)
_SAFETY_ENVELOPE_FIELDS = {
    "schemaVersion",
    "noAdviceDisclosure",
    "observationOnly",
    "decisionGrade",
    "consumerIssues",
    "evidenceGaps",
    "degradedInputs",
    "dataQuality",
    "freshnessStatus",
}
_EXPOSURE_RESEARCH_CONTEXT_FIELDS = {
    "dominantExposure",
    "concentrationContext",
    "currencyContext",
    "marketContext",
    "staleInputs",
    "evidenceGaps",
    "observationBoundary",
    "researchNextSteps",
}
_RISK_EXPOSURE_READINESS_FIELDS = {
    "contractVersion",
    "observationOnly",
    "decisionGrade",
    "noAdviceDisclosure",
    "freshnessStatus",
    "holdings",
    "exposureCategories",
    "benchmarkAvailability",
    "blockers",
}

_COUNT_STATE_FIELDS = {
    "accountCountState",
    "positionCountState",
}


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


class PortfolioApiDiagnosticsContractTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "portfolio_api_diag.db"
        self._previous_admin_auth_enabled = os.environ.get("ADMIN_AUTH_ENABLED")
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
        os.environ["ADMIN_AUTH_ENABLED"] = "false"
        Config.reset_instance()
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()
        self.client = TestClient(create_app(static_dir=self.data_dir / "empty-static"))

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        if self._previous_admin_auth_enabled is None:
            os.environ.pop("ADMIN_AUTH_ENABLED", None)
        else:
            os.environ["ADMIN_AUTH_ENABLED"] = self._previous_admin_auth_enabled
        _reset_auth_globals()
        _reset_public_limiter_state_if_available()
        self.temp_dir.cleanup()

    def _save_close(self, symbol: str, on_date: date, close: float) -> None:
        df = pd.DataFrame(
            [
                {
                    "date": on_date,
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": 1.0,
                    "amount": close,
                    "pct_chg": 0.0,
                }
            ]
        )
        self.db.save_daily_data(df, code=symbol, data_source="portfolio-api-diagnostics-test")

    @staticmethod
    def _json_text(payload: object) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def _assert_no_admin_diagnostic_keys(self, value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                self.assertNotEqual(key, "admin_diagnostics")
                self.assertFalse(str(key).startswith("admin_"), key)
                snake_key = _ADMIN_DIAGNOSTIC_CAMEL_BOUNDARY_RE.sub("_", str(key)).lower()
                self.assertFalse(snake_key.startswith("admin_"), key)
                self._assert_no_admin_diagnostic_keys(child)
            return
        if isinstance(value, list):
            for item in value:
                self._assert_no_admin_diagnostic_keys(item)

    def _assert_safety_envelope(
        self,
        payload: dict,
        *,
        schema_version: str,
        freshness_status: str,
    ) -> None:
        self.assertTrue(_SAFETY_ENVELOPE_FIELDS.issubset(payload.keys()))
        self.assertEqual(payload["schemaVersion"], schema_version)
        self.assertEqual(payload["noAdviceDisclosure"], _NO_ADVICE_DISCLOSURE)
        self.assertTrue(payload["observationOnly"])
        self.assertFalse(payload["decisionGrade"])
        self.assertEqual(payload["freshnessStatus"], freshness_status)
        self.assertEqual(payload["dataQuality"]["status"], payload["data_status"])
        self.assertEqual(payload["dataQuality"]["freshnessStatus"], freshness_status)
        self.assertEqual(payload["dataQuality"]["calculationStatus"], payload["calculation_status"])
        self.assertEqual(payload["dataQuality"]["metricsReady"], payload["availability"]["metrics_ready"])
        self.assertTrue(_COUNT_STATE_FIELDS.issubset(payload["dataQuality"]))
        self.assertTrue(payload["dataQuality"]["observationOnly"])
        self.assertFalse(payload["dataQuality"]["decisionGrade"])
        self.assertIsInstance(payload["consumerIssues"], list)
        self.assertIsInstance(payload["evidenceGaps"], list)
        self.assertIsInstance(payload["degradedInputs"], list)
        self.assertIn("benchmark_mapping", payload["evidenceGaps"])
        self.assertIn("factor_mapping", payload["evidenceGaps"])
        envelope_text = self._json_text({field: payload[field] for field in _SAFETY_ENVELOPE_FIELDS})
        for forbidden in (
            "buy now",
            "sell now",
            "place order",
            "submit order",
            "trade recommendation",
            "investment advice",
            "target price",
            "position sizing",
            "raw_payload",
            "debug",
            "traceback",
        ):
            self.assertNotIn(forbidden, envelope_text.lower())
        self._assert_no_admin_diagnostic_keys(payload)

    @staticmethod
    def _count_contract_payload(
        *,
        data_status: str,
        availability: dict,
        account_count: object = None,
    ) -> dict:
        return {
            "as_of": "2026-05-10",
            "account_id": None,
            "cost_method": "fifo",
            "currency": "USD",
            "account_count": account_count,
            "data_status": data_status,
            "calculation_status": (
                "calculation_unavailable"
                if data_status in {"no_account", "no_positions", "data_unavailable", "calculation_unavailable"}
                else "ready"
            ),
            "availability": {
                "status": data_status,
                "reason": data_status,
                "metrics_ready": data_status not in {"no_account", "no_positions", "data_unavailable"},
                **availability,
            },
            "benchmarkMappingState": "unmapped",
            "factorMappingState": "unmapped",
            "sourceAuthorityState": "manual",
            "fxFreshnessState": "live",
            "drawdown": {},
        }

    def _get_count_contract_payload(self, service_payload: dict) -> dict:
        with patch(
            "api.v1.endpoints.portfolio.PortfolioRiskService.get_risk_report",
            return_value=service_payload,
        ):
            response = self.client.get(
                "/api/v1/portfolio/risk",
                params={"as_of": "2026-05-10", "cost_method": "fifo"},
            )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _assert_readiness_count_contract_preserves_all_observation_states(self) -> None:
        cases = {
            "missing_count": {
                "payload": self._count_contract_payload(
                    data_status="ready",
                    availability={},
                ),
                "expected": (None, "unknown", None, "unknown", "missing"),
            },
            "missing_account_count": {
                "payload": self._count_contract_payload(
                    data_status="ready",
                    availability={"position_count": 2},
                ),
                "expected": (None, "unknown", 2, "observed_positive", "missing"),
            },
            "malformed_count": {
                "payload": self._count_contract_payload(
                    data_status="ready",
                    availability={"account_count": "one", "position_count": "not-a-count"},
                    account_count="also-not-a-count",
                ),
                "expected": (None, "unknown", None, "unknown", "missing"),
            },
            "explicit_real_zero": {
                "payload": self._count_contract_payload(
                    data_status="no_positions",
                    availability={"account_count": 1, "position_count": 0},
                    account_count=1,
                ),
                "expected": (1, "observed_positive", 0, "observed_zero", "missing"),
            },
            "unproven_zero": {
                "payload": self._count_contract_payload(
                    data_status="ready",
                    availability={"account_count": 0, "position_count": 0},
                    account_count=0,
                ),
                "expected": (None, "unknown", None, "unknown", "missing"),
            },
            "unavailable_provider": {
                "payload": self._count_contract_payload(
                    data_status="provider_unavailable",
                    availability={"account_count": 1},
                    account_count=1,
                ),
                "expected": (1, "observed_positive", None, "unavailable", "missing"),
            },
            "no_portfolio_account": {
                "payload": self._count_contract_payload(
                    data_status="no_account",
                    availability={"account_count": 0, "position_count": 0},
                    account_count=0,
                ),
                "expected": (0, "observed_zero", None, "not_applicable", "missing"),
            },
            "account_with_no_positions": {
                "payload": self._count_contract_payload(
                    data_status="no_positions",
                    availability={"account_count": 1, "position_count": 0},
                    account_count=1,
                ),
                "expected": (1, "observed_positive", 0, "observed_zero", "missing"),
            },
            "stale_cached_portfolio": {
                "payload": self._count_contract_payload(
                    data_status="stale_or_cached",
                    availability={"account_count": 1, "position_count": 2},
                    account_count=1,
                ),
                "expected": (1, "stale", 2, "stale", "stale"),
            },
            "valid_nonzero_count": {
                "payload": self._count_contract_payload(
                    data_status="ready",
                    availability={"account_count": 1, "position_count": 2},
                    account_count=1,
                ),
                "expected": (1, "observed_positive", 2, "observed_positive", "manual_only"),
            },
        }

        for case_name, case in cases.items():
            with self.subTest(case=case_name):
                payload = self._get_count_contract_payload(case["payload"])
                data_quality = payload["dataQuality"]
                (
                    expected_account,
                    expected_account_state,
                    expected_position,
                    expected_position_state,
                    expected_holdings,
                ) = case["expected"]
                self.assertEqual(data_quality["accountCount"], expected_account)
                self.assertEqual(data_quality["accountCountState"], expected_account_state)
                self.assertEqual(data_quality["positionCount"], expected_position)
                self.assertEqual(data_quality["positionCountState"], expected_position_state)
                self.assertEqual(payload["availability"]["account_count"], expected_account)
                self.assertEqual(payload["availability"]["account_count_state"], expected_account_state)
                self.assertEqual(payload["availability"]["position_count"], expected_position)
                self.assertEqual(payload["availability"]["position_count_state"], expected_position_state)
                self.assertEqual(payload["riskExposureReadiness"]["holdings"]["state"], expected_holdings)
                if expected_position_state in {"unknown", "unavailable", "not_applicable"}:
                    self.assertIn("portfolio_positions", payload["riskExposureReadiness"]["blockers"])
                json.dumps(payload, ensure_ascii=False, allow_nan=False)

    def _assert_exposure_research_context(
        self,
        payload: dict,
        *,
        expected_symbol: str | None = None,
    ) -> None:
        self.assertIn("exposureResearchContext", payload)
        context = payload["exposureResearchContext"]
        self.assertIsInstance(context, dict)
        self.assertTrue(_EXPOSURE_RESEARCH_CONTEXT_FIELDS.issubset(context.keys()))
        self.assertEqual(context["evidenceGaps"], payload["evidenceGaps"])
        self.assertIsInstance(context["staleInputs"], list)
        self.assertIsInstance(context["researchNextSteps"], list)
        self.assertGreaterEqual(len(context["researchNextSteps"]), 1)
        boundary = context["observationBoundary"]
        self.assertTrue(boundary["observationOnly"])
        self.assertFalse(boundary["decisionGrade"])
        self.assertFalse(boundary["accountingMutation"])
        self.assertFalse(boundary["portfolioMutation"])
        self.assertFalse(boundary["providerRoutingChanged"])
        self.assertFalse(boundary["externalProviderCallsAdded"])
        self.assertEqual(boundary["adviceBoundary"], "no_advice")
        self.assertIn("not personalized financial advice", boundary["message"].lower())
        dominant = context["dominantExposure"]
        self.assertIn(dominant["type"], {"position", "currency", "market", "none"})
        if expected_symbol is not None:
            self.assertEqual(dominant["type"], "position")
            self.assertEqual(dominant["symbol"], expected_symbol)
        self.assertIn("state", context["concentrationContext"])
        self.assertIn("fxFreshnessState", context["currencyContext"])
        self.assertIn("benchmarkMappingState", context["marketContext"])

        context_text = self._json_text(context)
        for forbidden in (
            "buy now",
            "sell now",
            "place order",
            "submit order",
            "trade recommendation",
            "investment advice",
            "target price",
            "position sizing",
            "raw_payload",
            "debug",
            "traceback",
        ):
            self.assertNotIn(forbidden, context_text.lower())

    def _assert_risk_exposure_readiness(
        self,
        payload: dict,
        *,
        holdings_state: str,
        benchmark_state: str = "not_configured",
    ) -> dict:
        self.assertIn("riskExposureReadiness", payload)
        readiness = payload["riskExposureReadiness"]
        self.assertTrue(_RISK_EXPOSURE_READINESS_FIELDS.issubset(readiness.keys()))
        self.assertEqual(readiness["contractVersion"], "portfolio_risk_exposure_readiness_v1")
        self.assertTrue(readiness["observationOnly"])
        self.assertFalse(readiness["decisionGrade"])
        self.assertEqual(readiness["noAdviceDisclosure"], _NO_ADVICE_DISCLOSURE)
        self.assertEqual(readiness["freshnessStatus"], payload["freshnessStatus"])
        self.assertEqual(readiness["holdings"]["state"], holdings_state)
        self.assertEqual(readiness["benchmarkAvailability"]["state"], benchmark_state)

        categories = readiness["exposureCategories"]
        for key in (
            "sectorExposure",
            "singleNameConcentration",
            "currencyExposure",
            "factorStyleExposure",
            "liquidityVolatilityExposure",
            "benchmarkComparison",
        ):
            self.assertIn(key, categories)
            self.assertIn(
                categories[key]["state"],
                {"available", "missing", "stale", "not_configured", "broker_disabled", "manual_only"},
                key,
            )

        readiness_text = self._json_text(readiness).lower()
        for forbidden in (
            "account_id",
            "accountid",
            "broker_account",
            "brokeraccount",
            "session",
            "token",
            "sync_metadata",
            "api_base_url",
            "ibkr",
            "var",
            "beta",
            "drawdown",
            "sector_weight",
            "currency_weight",
            "buy now",
            "sell now",
            "rebalance",
            "trim",
            "add position",
            "target price",
            "stop loss",
            "position sizing",
        ):
            self.assertNotIn(forbidden, readiness_text)
        self._assert_no_admin_diagnostic_keys(readiness)
        return readiness

    def test_snapshot_endpoint_exposes_optional_diagnostics_fields(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Main", "broker": "Demo", "market": "cn", "base_currency": "CNY"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]

        self.client.post(
            "/api/v1/portfolio/cash-ledger",
            json={
                "account_id": account_id,
                "event_date": "2026-05-10",
                "direction": "in",
                "amount": 1000.0,
                "currency": "CNY",
            },
        )
        self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "600519",
                "trade_date": "2026-05-10",
                "side": "buy",
                "quantity": 10.0,
                "price": 100.0,
                "market": "cn",
                "currency": "CNY",
            },
        )
        self._save_close("600519", date(2026, 5, 10), 100.0)

        response = self.client.get(
            "/api/v1/portfolio/snapshot",
            params={"account_id": account_id, "as_of": "2026-05-10", "cost_method": "fifo"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertIn("riskDiagnostics", payload)
        self.assertIn("portfolioRiskEvidence", payload)
        self.assertIn("confidenceCap", payload)
        self.assertIn("sourceAuthorityState", payload)
        self.assertIn("fxFreshnessState", payload)
        self.assertEqual(payload["data_status"], "ready")
        self._assert_safety_envelope(
            payload,
            schema_version=_SNAPSHOT_SCHEMA_VERSION,
            freshness_status="ready",
        )
        self._assert_exposure_research_context(payload, expected_symbol="600519")
        self._assert_risk_exposure_readiness(payload, holdings_state="manual_only")

        cached_response = self.client.get(
            "/api/v1/portfolio/snapshot",
            params={"account_id": account_id, "as_of": "2026-05-10", "cost_method": "fifo"},
        )
        self.assertEqual(cached_response.status_code, 200)
        cached_payload = cached_response.json()
        self.assertEqual(cached_payload["data_status"], "stale_or_cached")
        self._assert_safety_envelope(
            cached_payload,
            schema_version=_SNAPSHOT_SCHEMA_VERSION,
            freshness_status="stale_or_cached",
        )
        self._assert_exposure_research_context(cached_payload, expected_symbol="600519")
        cached_readiness = self._assert_risk_exposure_readiness(cached_payload, holdings_state="stale")
        self.assertEqual(cached_readiness["exposureCategories"]["singleNameConcentration"]["state"], "stale")
        self.assertTrue(
            any(item.get("section") == "freshness" for item in cached_payload["degradedInputs"]),
            cached_payload["degradedInputs"],
        )

    def test_risk_endpoint_exposes_optional_diagnostics_fields(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "US", "broker": "Demo", "market": "us", "base_currency": "CNY"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]

        self.client.post(
            "/api/v1/portfolio/cash-ledger",
            json={
                "account_id": account_id,
                "event_date": "2026-05-10",
                "direction": "in",
                "amount": 1000.0,
                "currency": "USD",
            },
        )
        self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "AAPL",
                "trade_date": "2026-05-10",
                "side": "buy",
                "quantity": 1.0,
                "price": 100.0,
                "market": "us",
                "currency": "USD",
            },
        )
        self._save_close("AAPL", date(2026, 5, 10), 100.0)

        response = self.client.get(
            "/api/v1/portfolio/risk",
            params={"account_id": account_id, "as_of": "2026-05-10", "cost_method": "fifo"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertIn("riskDiagnostics", payload)
        self.assertIn("portfolioRiskEvidence", payload)
        self.assertIn("confidenceCap", payload)
        self.assertIn("benchmarkMappingState", payload)
        self.assertIn("factorMappingState", payload)
        self.assertIn("sectorSourceProvenance", payload)
        self.assertTrue(payload["sectorSourceProvenance"]["diagnosticOnly"])
        self.assertTrue(payload["sectorSourceProvenance"]["observationOnly"])
        self.assertFalse(payload["sectorSourceProvenance"]["authorityGrant"])
        self.assertFalse(payload["sectorSourceProvenance"]["decisionGrade"])
        self.assertEqual(
            payload["sectorSourceProvenance"]["items"][0]["classificationState"],
            "non_cn_not_applicable",
        )
        self._assert_safety_envelope(
            payload,
            schema_version=_RISK_SCHEMA_VERSION,
            freshness_status="provider_unavailable",
        )
        self._assert_exposure_research_context(payload, expected_symbol="AAPL")
        readiness = self._assert_risk_exposure_readiness(payload, holdings_state="manual_only")
        self.assertEqual(readiness["exposureCategories"]["sectorExposure"]["state"], "missing")
        self.assertEqual(readiness["exposureCategories"]["currencyExposure"]["state"], "missing")
        self.assertIn("benchmark_mapping", readiness["blockers"])

    def test_snapshot_readiness_exposes_missing_holdings_without_fake_metrics(self) -> None:
        self._assert_readiness_count_contract_preserves_all_observation_states()

        no_account_response = self.client.get(
            "/api/v1/portfolio/snapshot",
            params={"as_of": "2026-05-10", "cost_method": "fifo"},
        )
        self.assertEqual(no_account_response.status_code, 200)
        no_account_payload = no_account_response.json()
        self.assertEqual(no_account_payload["data_status"], "no_account")
        self.assertEqual(no_account_payload["dataQuality"]["accountCount"], 0)
        self.assertEqual(no_account_payload["dataQuality"]["accountCountState"], "observed_zero")
        self.assertIsNone(no_account_payload["dataQuality"]["positionCount"])
        self.assertEqual(no_account_payload["dataQuality"]["positionCountState"], "not_applicable")

        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Empty", "broker": "Manual", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]

        response = self.client.get(
            "/api/v1/portfolio/snapshot",
            params={"account_id": account_id, "as_of": "2026-05-10", "cost_method": "fifo"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self._assert_safety_envelope(
            payload,
            schema_version=_SNAPSHOT_SCHEMA_VERSION,
            freshness_status="no_positions",
        )
        readiness = self._assert_risk_exposure_readiness(payload, holdings_state="missing")
        self.assertEqual(payload["dataQuality"]["accountCount"], 1)
        self.assertEqual(payload["dataQuality"]["accountCountState"], "observed_positive")
        self.assertEqual(payload["dataQuality"]["positionCount"], 0)
        self.assertEqual(payload["dataQuality"]["positionCountState"], "observed_zero")
        self.assertEqual(readiness["exposureCategories"]["singleNameConcentration"]["state"], "missing")
        self.assertEqual(readiness["exposureCategories"]["currencyExposure"]["state"], "missing")
        self.assertIn("portfolio_positions", readiness["blockers"])

    def test_snapshot_readiness_marks_broker_disabled_without_leaking_broker_internals(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Disabled Link", "broker": "IBKR", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]

        broker_resp = self.client.post(
            "/api/v1/portfolio/broker-connections",
            json={
                "portfolio_account_id": account_id,
                "broker_type": "ibkr",
                "broker_name": "Interactive Brokers",
                "connection_name": "raw_connection_name_must_not_leak",
                "broker_account_ref": "raw-account-ref-must-not-leak",
                "import_mode": "api",
                "status": "disabled",
                "sync_metadata": {
                    "session_token": "raw-session-token-must-not-leak",
                    "api_base_url": "https://broker.example.invalid/raw-url-must-not-leak",
                },
            },
        )
        self.assertEqual(broker_resp.status_code, 200)

        response = self.client.get(
            "/api/v1/portfolio/snapshot",
            params={"account_id": account_id, "as_of": "2026-05-10", "cost_method": "fifo"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        readiness = self._assert_risk_exposure_readiness(payload, holdings_state="broker_disabled")
        self.assertEqual(readiness["exposureCategories"]["benchmarkComparison"]["state"], "not_configured")
        self.assertNotIn("raw_connection_name_must_not_leak", self._json_text(readiness))
        self.assertNotIn("raw-session-token-must-not-leak", self._json_text(readiness))

    def test_risk_endpoint_provider_lookup_failure_stays_bounded_and_contract_compatible(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "CN", "broker": "Demo", "market": "cn", "base_currency": "CNY"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]

        self.client.post(
            "/api/v1/portfolio/cash-ledger",
            json={
                "account_id": account_id,
                "event_date": "2026-05-10",
                "direction": "in",
                "amount": 1000.0,
                "currency": "CNY",
            },
        )
        self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "600519",
                "trade_date": "2026-05-10",
                "side": "buy",
                "quantity": 10.0,
                "price": 100.0,
                "market": "cn",
                "currency": "CNY",
            },
        )
        self._save_close("600519", date(2026, 5, 10), 100.0)

        with patch(
            "src.services.portfolio_risk_service.PortfolioRiskService._fetch_belong_boards",
            side_effect=ValueError("provider lookup failed"),
        ):
            response = self.client.get(
                "/api/v1/portfolio/risk",
                params={"account_id": account_id, "as_of": "2026-05-10", "cost_method": "fifo"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertIn("riskDiagnostics", payload)
        self.assertIn("portfolioRiskEvidence", payload)
        self.assertIn("confidenceCap", payload)
        self.assertEqual(payload["industry_attribution"]["top_industries"][0]["industry"], "UNCLASSIFIED")
        self.assertEqual(payload["sector_concentration"]["top_sectors"][0]["sector"], "UNCLASSIFIED")
        self.assertEqual(payload["industry_attribution"]["coverage"]["failed_count"], 1)
        self.assertEqual(payload["sector_concentration"]["coverage"]["failed_count"], 1)
        self.assertIn("provider lookup failed", payload["industry_attribution"]["errors"][0])
        self.assertIn("provider lookup failed", payload["sector_concentration"]["errors"][0])
        self.assertIn("sectorSourceProvenance", payload)
        self.assertTrue(payload["sectorSourceProvenance"]["diagnosticOnly"])
        self.assertTrue(payload["sectorSourceProvenance"]["observationOnly"])
        self.assertFalse(payload["sectorSourceProvenance"]["authorityGrant"])
        self.assertFalse(payload["sectorSourceProvenance"]["accountingMutation"])
        self.assertFalse(payload["sectorSourceProvenance"]["providerRoutingChanged"])
        self.assertFalse(payload["sectorSourceProvenance"]["externalProviderCallsAdded"])
        self.assertFalse(payload["sectorSourceProvenance"]["marketCacheMutation"])
        self.assertEqual(payload["sectorSourceProvenance"]["summary"]["lookupFailureCount"], 1)
        self.assertEqual(
            payload["sectorSourceProvenance"]["items"][0]["classificationState"],
            "lookup_failure",
        )
        self.assertEqual(payload["sectorSourceProvenance"]["items"][0]["industryLabel"], "UNCLASSIFIED")
        self.assertFalse(payload["sectorSourceProvenance"]["items"][0]["authorityGrant"])
        self._assert_safety_envelope(
            payload,
            schema_version=_RISK_SCHEMA_VERSION,
            freshness_status="ready",
        )
        self._assert_exposure_research_context(payload, expected_symbol="600519")


if __name__ == "__main__":
    unittest.main()
