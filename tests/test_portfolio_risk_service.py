# -*- coding: utf-8 -*-
"""Focused integration tests for additive portfolio risk diagnostics."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from src.config import Config
from src.services.portfolio_risk_service import PortfolioRiskService
from src.services.portfolio_service import PortfolioService
from src.storage import DatabaseManager


class PortfolioRiskServiceDiagnosticsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._template_dir = tempfile.TemporaryDirectory()
        cls._template_db_path = Path(cls._template_dir.name) / "portfolio_risk_schema.db"
        cls._template_database_sha256: str | None = None
        cls._previous_environment = {
            key: os.environ.get(key)
            for key in ("ENV_FILE", "DATABASE_PATH", "ADMIN_AUTH_ENABLED")
        }
        cls.addClassCleanup(cls._cleanup_class_resources)

    @staticmethod
    def _write_environment_file(env_path: Path, db_path: Path) -> None:
        env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=600519",
                    "GEMINI_API_KEY=test",
                    "ADMIN_AUTH_ENABLED=false",
                    f"DATABASE_PATH={db_path}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _activate_environment(env_path: Path, db_path: Path) -> None:
        os.environ["ENV_FILE"] = str(env_path)
        os.environ["DATABASE_PATH"] = str(db_path)
        os.environ["ADMIN_AUTH_ENABLED"] = "false"

    @classmethod
    def _restore_previous_environment(cls) -> None:
        for key, value in cls._previous_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    @staticmethod
    def _database_sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @classmethod
    def _cleanup_class_resources(cls) -> None:
        template_identity_error = None
        if cls._template_database_sha256 is not None:
            actual_sha256 = cls._database_sha256(cls._template_db_path)
            if actual_sha256 != cls._template_database_sha256:
                template_identity_error = (
                    "portfolio risk schema template changed: "
                    f"expected {cls._template_database_sha256}, got {actual_sha256}"
                )

        DatabaseManager.reset_instance()
        Config.reset_instance()
        cls._restore_previous_environment()
        cls._template_dir.cleanup()
        if template_identity_error is not None:
            raise AssertionError(template_identity_error)

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_path = Path(self.temp_dir.name) / ".env"
        self.db_path = Path(self.temp_dir.name) / "portfolio_risk_diag.db"
        self.addCleanup(self.temp_dir.cleanup)
        self.addCleanup(self._restore_previous_environment)
        self.addCleanup(Config.reset_instance)
        self.addCleanup(DatabaseManager.reset_instance)
        self._write_environment_file(self.env_path, self.db_path)
        if self._template_database_sha256 is not None:
            self.assertEqual(
                self._database_sha256(self._template_db_path),
                self._template_database_sha256,
            )
            shutil.copyfile(self._template_db_path, self.db_path)

        self._activate_environment(self.env_path, self.db_path)
        Config.reset_instance()
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()
        if self._template_database_sha256 is None:
            self.db._engine.dispose()
            shutil.copyfile(self.db_path, self._template_db_path)
            type(self)._template_database_sha256 = self._database_sha256(
                self._template_db_path
            )
        self.assertEqual(
            self._database_sha256(self.db_path),
            self._template_database_sha256,
        )
        self.service = PortfolioService()
        self.risk_service = PortfolioRiskService(portfolio_service=self.service)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self._restore_previous_environment()
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
        self.db.save_daily_data(df, code=symbol, data_source="portfolio-risk-diagnostics-test")

    def test_risk_report_includes_additive_diagnostics(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 5, 10),
            direction="in",
            amount=2000.0,
            currency="CNY",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 5, 10),
            side="buy",
            quantity=10.0,
            price=100.0,
            market="cn",
            currency="CNY",
        )
        self._save_close("600519", date(2026, 5, 10), 100.0)

        report = self.risk_service.get_risk_report(account_id=aid, as_of=date(2026, 5, 10), cost_method="fifo")

        self.assertEqual(report["concentration"]["top_positions"][0]["symbol"], "600519")
        self.assertIn("riskDiagnostics", report)
        self.assertIn("portfolioRiskEvidence", report)
        self.assertEqual(report["sourceAuthorityState"], "manual")
        self.assertIn("holdingsLineage", report["riskDiagnostics"])
        self.assertIn("confidenceCap", report)

    def test_fx_fallback_caps_confidence_without_changing_risk_values(self) -> None:
        account = self.service.create_account(name="US", broker="Demo", market="us", base_currency="CNY")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 5, 10),
            direction="in",
            amount=1000.0,
            currency="USD",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="AAPL",
            trade_date=date(2026, 5, 10),
            side="buy",
            quantity=1.0,
            price=100.0,
            market="us",
            currency="USD",
        )
        self._save_close("AAPL", date(2026, 5, 10), 100.0)

        snapshot = self.service.get_portfolio_snapshot(
            account_id=aid,
            as_of=date(2026, 5, 10),
            cost_method="fifo",
        )
        report = self.risk_service.get_risk_report(account_id=aid, as_of=date(2026, 5, 10), cost_method="fifo")

        position = snapshot["accounts"][0]["positions"][0]
        self.assertEqual(position["market_value_native"], 100.0)
        self.assertEqual(position["display_fx_status"], "unavailable")
        self.assertEqual(report["concentration"]["top_positions"][0]["market_value_base"], 0.0)
        self.assertEqual(report["availability"]["valuation"]["state"], "unavailable")
        self.assertEqual(report["fxFreshnessState"], "unavailable")
        self.assertLessEqual(report["confidenceCap"]["value"], 40)
        self.assertIn("FX 汇率缺失", report["confidenceCap"]["limitation_labels"])


if __name__ == "__main__":
    unittest.main()
