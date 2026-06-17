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


if __name__ == "__main__":
    unittest.main()
