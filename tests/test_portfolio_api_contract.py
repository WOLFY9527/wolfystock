# -*- coding: utf-8 -*-
"""Focused API contract tests for additive portfolio diagnostics fields."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

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
        self.db = DatabaseManager.get_instance()
        self.client = TestClient(create_app(static_dir=self.data_dir / "empty-static"))

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
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


if __name__ == "__main__":
    unittest.main()
