# -*- coding: utf-8 -*-
"""Integration tests for portfolio API endpoints (P0 PR1 scope)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
from fastapi.testclient import TestClient

# Keep this test runnable when optional LLM runtime deps are not installed.
try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.app import create_app
from src.config import Config
from src.services.portfolio_ibkr_sync_service import PortfolioIbkrSyncError
from src.services.portfolio_service import PortfolioService
from src.services.portfolio_service import PortfolioBusyError, PortfolioConflictError
from src.storage import DatabaseManager


def _reset_public_limiter_state_if_available() -> None:
    try:
        from api.middlewares.public_abuse_limiter import reset_public_api_abuse_limiter_state
    except ModuleNotFoundError:
        return
    reset_public_api_abuse_limiter_state()


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


SAFE_IMPORT_VALIDATION_MESSAGE = "Portfolio import request could not be processed."
SAFE_IMPORT_CONFLICT_MESSAGE = "Portfolio import conflicts with existing records."
SAFE_IMPORT_INTERNAL_MESSAGE = "Portfolio import is temporarily unavailable. Please retry later."
RAW_IMPORT_ERROR_MARKERS = (
    "raw-exception-text-must-not-leak",
    "Traceback (most recent call last)",
    "provider.example.invalid",
    "request_id=req-raw-must-not-leak",
    "account_label=vip-account-label-must-not-leak",
    "broker_ref=broker-ref-must-not-leak",
    "import_fingerprint=fp-raw-must-not-leak",
    "raw_provider_payload_marker",
)


def _raw_import_exception_text() -> str:
    return (
        "raw-exception-text-must-not-leak "
        "Traceback (most recent call last): provider stack "
        "https://provider.example.invalid/import?request_id=req-raw-must-not-leak "
        "account_label=vip-account-label-must-not-leak "
        "broker_ref=broker-ref-must-not-leak "
        "import_fingerprint=fp-raw-must-not-leak "
        "raw_provider_payload_marker"
    )


class PortfolioApiTestCase(unittest.TestCase):
    """Portfolio API contract tests for account/events/snapshot."""

    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "portfolio_api_test.db"
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
        app = create_app(static_dir=self.data_dir / "empty-static")
        self.client = TestClient(app)
        self.db = DatabaseManager.get_instance()

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
        self.db.save_daily_data(df, code=symbol, data_source="portfolio-api-test")

    @staticmethod
    def _json_text(response) -> str:
        return json.dumps(response.json(), ensure_ascii=False, sort_keys=True)

    def _assert_safe_import_error(
        self,
        response,
        *,
        status_code: int,
        error_code: str,
        message: str,
    ) -> None:
        self.assertEqual(response.status_code, status_code)
        payload = response.json()
        self.assertEqual(payload.get("error"), error_code)
        self.assertEqual(payload.get("code"), error_code)
        self.assertEqual(payload.get("message"), message)
        self.assertEqual(payload.get("status"), status_code)
        self.assertNotIn("detail", payload)
        response_text = self._json_text(response)
        for marker in RAW_IMPORT_ERROR_MARKERS:
            self.assertNotIn(marker, response_text)

    @staticmethod
    def _ibkr_flex_xml_bytes() -> bytes:
        xml_text = """<?xml version="1.0" encoding="UTF-8"?>
<FlexStatements>
  <FlexStatement accountId="U1234567" fromDate="2026-01-01" toDate="2026-01-31" currency="USD">
    <Trades>
      <Trade assetCategory="STK" symbol="AAPL" exchange="NASDAQ" currency="USD" tradeDate="2026-01-03" buySell="BUY" quantity="10" tradePrice="150" ibCommission="1.25" taxes="0" ibExecID="AAPL-1" description="AAPL BUY"/>
    </Trades>
    <CashTransactions>
      <CashTransaction reportDate="2026-01-02" currency="USD" amount="5000" description="Deposit"/>
    </CashTransactions>
  </FlexStatement>
</FlexStatements>
"""
        return xml_text.encode("utf-8")

    @staticmethod
    def _ibkr_sensitive_flex_xml_bytes() -> bytes:
        xml_text = """<?xml version="1.0" encoding="UTF-8"?>
<FlexStatements>
  <FlexStatement accountId="fixture-broker-account-ref-must-not-leak" fromDate="2026-01-01" toDate="2026-01-31" currency="USD">
    <Trades>
      <Trade assetCategory="STK" symbol="AAPL" exchange="NASDAQ" currency="USD" tradeDate="2026-01-03" buySell="BUY" quantity="10" tradePrice="150" ibCommission="1.25" taxes="0" ibExecID="fixture-execution-id-must-not-leak" orderID="fixture-order-id-must-not-leak" description="account_label=fixture-account-label-must-not-leak provider_url=synthetic_provider_url_must_not_leak import_fingerprint=synthetic_import_fingerprint_must_not_leak connection_name=synthetic_broker_connection_name_must_not_leak raw_payload_label=synthetic_raw_payload_label_must_not_leak import_file_label=synthetic_import_file_label_must_not_leak request_id=fixture-request-id-must-not-leak token=fixture-token-must-not-leak https://broker.example.invalid/path?token=fixture-url-token-must-not-leak"/>
    </Trades>
  </FlexStatement>
</FlexStatements>
"""
        return xml_text.encode("utf-8")

    def test_account_event_snapshot_flow(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Main", "broker": "Demo", "market": "cn", "base_currency": "CNY"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]

        list_resp = self.client.get("/api/v1/portfolio/accounts")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(len(list_resp.json()["accounts"]), 1)

        cash_resp = self.client.post(
            "/api/v1/portfolio/cash-ledger",
            json={
                "account_id": account_id,
                "event_date": "2026-01-01",
                "direction": "in",
                "amount": 10000,
                "currency": "CNY",
            },
        )
        self.assertEqual(cash_resp.status_code, 200)

        trade_resp = self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "600519",
                "trade_date": "2026-01-02",
                "side": "buy",
                "quantity": 100,
                "price": 100,
                "fee": 0,
                "tax": 0,
                "market": "cn",
                "currency": "CNY",
            },
        )
        self.assertEqual(trade_resp.status_code, 200)
        self._save_close("600519", date(2026, 1, 3), 110.0)

        snapshot_resp = self.client.get(
            "/api/v1/portfolio/snapshot",
            params={"account_id": account_id, "as_of": "2026-01-03"},
        )
        self.assertEqual(snapshot_resp.status_code, 200)
        payload = snapshot_resp.json()
        self.assertEqual(payload["account_count"], 1)
        self.assertEqual(payload["cost_method"], "fifo")
        account_snapshot = payload["accounts"][0]
        self.assertAlmostEqual(account_snapshot["total_cash"], 0.0, places=6)
        self.assertAlmostEqual(account_snapshot["total_market_value"], 11000.0, places=6)
        self.assertAlmostEqual(account_snapshot["total_equity"], 11000.0, places=6)
        logs, total_logs = self.db.list_execution_log_sessions(stock_code="600519", limit=10)
        self.assertEqual(total_logs, 1)
        self.assertEqual(logs[0]["summary"]["meta"]["subsystem"], "portfolio")
        self.assertEqual(logs[0]["summary"]["meta"]["actor_type"], "admin")
        self.assertEqual(logs[0]["summary"]["business_event"]["symbol"], "600519")

        cash_logs, total_cash_logs = self.db.list_execution_log_sessions(task_id="portfolio:cash_ledger", limit=10)
        self.assertEqual(total_cash_logs, 1)
        self.assertEqual(cash_logs[0]["summary"]["portfolio_event"]["currency"], "CNY")

    def test_delete_empty_account_archives_and_returns_next_account(self) -> None:
        first_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Main", "broker": "Demo", "market": "cn", "base_currency": "CNY"},
        )
        second_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Spare", "broker": "Demo", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(first_resp.status_code, 200)
        self.assertEqual(second_resp.status_code, 200)
        first_id = first_resp.json()["id"]
        second_id = second_resp.json()["id"]

        delete_resp = self.client.delete(f"/api/v1/portfolio/accounts/{first_id}")
        self.assertEqual(delete_resp.status_code, 200)
        payload = delete_resp.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["deleted_account_id"], first_id)
        self.assertEqual(payload["delete_mode"], "soft")
        self.assertEqual(payload["next_account_id"], second_id)

        list_resp = self.client.get("/api/v1/portfolio/accounts")
        self.assertEqual([item["id"] for item in list_resp.json()["accounts"]], [second_id])
        inactive_resp = self.client.get("/api/v1/portfolio/accounts", params={"include_inactive": True})
        archived = [item for item in inactive_resp.json()["accounts"] if item["id"] == first_id][0]
        self.assertFalse(archived["is_active"])

    def test_delete_account_with_history_preserves_ledger_records(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "History", "broker": "Demo", "market": "cn", "base_currency": "CNY"},
        )
        keep_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Keep", "broker": "Demo", "market": "cn", "base_currency": "CNY"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]
        self.assertEqual(keep_resp.status_code, 200)
        trade_resp = self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "600519",
                "trade_date": "2026-01-02",
                "side": "buy",
                "quantity": 1,
                "price": 100,
                "market": "cn",
                "currency": "CNY",
            },
        )
        self.assertEqual(trade_resp.status_code, 200)

        delete_resp = self.client.delete(f"/api/v1/portfolio/accounts/{account_id}")
        self.assertEqual(delete_resp.status_code, 200)
        self.assertEqual(delete_resp.json()["delete_mode"], "soft")

        rows = PortfolioService().repo.list_trades(account_id, as_of=date(2026, 1, 3))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].symbol, "600519")

    def test_snapshot_api_returns_market_breakdown_for_multi_account_portfolio(self) -> None:
        cn_account = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "CN", "broker": "Demo", "market": "cn", "base_currency": "CNY"},
        )
        self.assertEqual(cn_account.status_code, 200)
        us_account = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "US", "broker": "Demo", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(us_account.status_code, 200)
        cn_id = cn_account.json()["id"]
        us_id = us_account.json()["id"]

        self.client.post(
            "/api/v1/portfolio/cash-ledger",
            json={
                "account_id": cn_id,
                "event_date": "2026-01-01",
                "direction": "in",
                "amount": 1000.0,
                "currency": "CNY",
            },
        )
        self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": cn_id,
                "symbol": "600519",
                "trade_date": "2026-01-01",
                "side": "buy",
                "quantity": 10,
                "price": 100.0,
                "market": "cn",
                "currency": "CNY",
            },
        )
        self.client.post(
            "/api/v1/portfolio/cash-ledger",
            json={
                "account_id": us_id,
                "event_date": "2026-01-01",
                "direction": "in",
                "amount": 100.0,
                "currency": "USD",
            },
        )
        self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": us_id,
                "symbol": "AAPL",
                "trade_date": "2026-01-01",
                "side": "buy",
                "quantity": 1,
                "price": 100.0,
                "market": "us",
                "currency": "USD",
            },
        )
        self._save_close("600519", date(2026, 1, 1), 100.0)
        self._save_close("AAPL", date(2026, 1, 1), 100.0)
        PortfolioService().repo.save_fx_rate(
            from_currency="USD",
            to_currency="CNY",
            rate_date=date(2026, 1, 1),
            rate=7.0,
            source="manual",
            is_stale=False,
        )

        snapshot_resp = self.client.get(
            "/api/v1/portfolio/snapshot",
            params={"as_of": "2026-01-01"},
        )
        self.assertEqual(snapshot_resp.status_code, 200)
        payload = snapshot_resp.json()
        self.assertEqual(payload["currency"], "CNY")
        self.assertEqual(
            payload["market_breakdown"],
            [
                {
                    "market": "cn",
                    "position_count": 1,
                    "total_market_value": 1000.0,
                    "weight_pct": 58.8235,
                },
                {
                    "market": "us",
                    "position_count": 1,
                    "total_market_value": 700.0,
                    "weight_pct": 41.1765,
                },
            ],
        )
        self.assertEqual(len(payload["fx_rates"]), 1)
        self.assertEqual(payload["fx_rates"][0]["from_currency"], "USD")
        self.assertEqual(payload["fx_rates"][0]["to_currency"], "CNY")
        self.assertAlmostEqual(payload["fx_rates"][0]["rate"], 7.0, places=6)
        self.assertEqual(payload["fx_rates"][0]["source"], "manual")
        self.assertFalse(payload["fx_rates"][0]["is_stale"])

    def test_snapshot_api_returns_backwards_compatible_analytics_payload(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Main", "broker": "Demo", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]
        self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "AAPL",
                "trade_date": "2026-01-01",
                "side": "buy",
                "quantity": 10,
                "price": 100.0,
                "market": "us",
                "currency": "USD",
            },
        )
        self._save_close("AAPL", date(2026, 1, 2), 130.0)

        snapshot_resp = self.client.get(
            "/api/v1/portfolio/snapshot",
            params={"as_of": "2026-01-02", "cost_method": "fifo"},
        )
        self.assertEqual(snapshot_resp.status_code, 200)
        payload = snapshot_resp.json()

        self.assertIn("total_market_value", payload)
        self.assertIn("accounts", payload)
        self.assertIn("analytics", payload)
        self.assertIn("pnl", payload["analytics"])
        self.assertIn("exposure", payload["analytics"])
        self.assertIn("risk", payload["analytics"])
        self.assertAlmostEqual(payload["analytics"]["pnl"]["unrealized"]["amount"], 300.0, places=6)
        self.assertEqual(payload["analytics"]["exposure"]["by_symbol"][0]["symbol"], "AAPL")
        self.assertEqual(payload["analytics"]["risk"]["largest_position"]["symbol"], "AAPL")

    def test_snapshot_lineage_marks_complete_price_fx_inputs_available(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "FX Complete", "broker": "Demo", "market": "global", "base_currency": "CNY"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]
        self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "AAPL",
                "trade_date": "2026-01-01",
                "side": "buy",
                "quantity": 2,
                "price": 100.0,
                "market": "us",
                "currency": "USD",
            },
        )
        self._save_close("AAPL", date(2026, 1, 2), 130.0)
        PortfolioService().repo.save_fx_rate(
            from_currency="USD",
            to_currency="CNY",
            rate_date=date(2026, 1, 2),
            rate=7.0,
            source="manual",
            is_stale=False,
        )

        snapshot_resp = self.client.get(
            "/api/v1/portfolio/snapshot",
            params={"account_id": account_id, "as_of": "2026-01-02", "cost_method": "fifo"},
        )
        self.assertEqual(snapshot_resp.status_code, 200)
        payload = snapshot_resp.json()

        self.assertIn("total_market_value", payload)
        self.assertIn("analytics", payload)
        self.assertEqual(payload["price_lineage"]["status"], "available")
        self.assertEqual(payload["price_lineage"]["score_authority"], "authoritative")
        self.assertEqual(payload["price_lineage"]["counts"]["available"], 1)
        self.assertEqual(payload["price_lineage"]["affected_symbols"]["available"], ["AAPL"])
        self.assertEqual(payload["price_lineage"]["last_updated_at"], "2026-01-02")
        self.assertEqual(payload["fx_lineage"]["status"], "available")
        self.assertEqual(payload["fx_lineage"]["score_authority"], "authoritative")
        self.assertEqual(payload["fx_lineage"]["counts"]["available"], 1)
        self.assertEqual(payload["fx_lineage"]["affected_currencies"]["available"], ["USD"])
        self.assertEqual(payload["valuation_snapshot_lineage"]["status"], "complete")
        self.assertEqual(payload["valuation_snapshot_lineage"]["score_authority"], "authoritative")
        self.assertTrue(payload["valuation_snapshot_lineage"]["metrics_ready"])
        self.assertEqual(payload["analytics_readiness"]["valuation"], "complete")
        self.assertEqual(payload["analytics_readiness"]["risk"], "available")
        self.assertEqual(payload["analytics_readiness"]["score_authority"], "authoritative")

    def test_snapshot_lineage_marks_missing_price_observation_only_without_hiding_fallback(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Price Gap", "broker": "Demo", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]
        self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "AAPL",
                "trade_date": "2026-01-01",
                "side": "buy",
                "quantity": 10,
                "price": 100.0,
                "market": "us",
                "currency": "USD",
            },
        )

        snapshot_resp = self.client.get(
            "/api/v1/portfolio/snapshot",
            params={"account_id": account_id, "as_of": "2026-01-02", "cost_method": "fifo"},
        )
        self.assertEqual(snapshot_resp.status_code, 200)
        payload = snapshot_resp.json()
        position = payload["accounts"][0]["positions"][0]

        self.assertTrue(position["is_price_fallback"])
        self.assertEqual(position["price_source"], "avg_cost_fallback")
        self.assertEqual(payload["price_lineage"]["status"], "missing")
        self.assertEqual(payload["price_lineage"]["score_authority"], "observation_only")
        self.assertEqual(payload["price_lineage"]["counts"]["missing"], 1)
        self.assertEqual(payload["price_lineage"]["affected_symbols"]["missing"], ["AAPL"])
        self.assertEqual(payload["valuation_snapshot_lineage"]["status"], "partial")
        self.assertEqual(payload["valuation_snapshot_lineage"]["score_authority"], "observation_only")
        self.assertEqual(payload["analytics_readiness"]["valuation"], "partial")
        self.assertEqual(payload["analytics_readiness"]["score_authority"], "observation_only")

    def test_snapshot_lineage_marks_missing_fx_partial_and_affected_currency(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "FX Gap", "broker": "Demo", "market": "global", "base_currency": "CNY"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]
        self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "AAPL",
                "trade_date": "2026-01-01",
                "side": "buy",
                "quantity": 2,
                "price": 100.0,
                "market": "us",
                "currency": "USD",
            },
        )
        self._save_close("AAPL", date(2026, 1, 2), 130.0)

        snapshot_resp = self.client.get(
            "/api/v1/portfolio/snapshot",
            params={"account_id": account_id, "as_of": "2026-01-02", "cost_method": "fifo"},
        )
        self.assertEqual(snapshot_resp.status_code, 200)
        payload = snapshot_resp.json()

        self.assertEqual(payload["price_lineage"]["status"], "available")
        self.assertEqual(payload["fx_lineage"]["status"], "missing")
        self.assertEqual(payload["fx_lineage"]["score_authority"], "observation_only")
        self.assertEqual(payload["fx_lineage"]["counts"]["missing"], 1)
        self.assertEqual(payload["fx_lineage"]["counts"]["fallback"], 1)
        self.assertEqual(payload["fx_lineage"]["affected_currencies"]["missing"], ["USD"])
        self.assertEqual(payload["fx_lineage"]["affected_currencies"]["fallback"], ["USD"])
        self.assertEqual(payload["valuation_snapshot_lineage"]["status"], "partial")
        self.assertIn("USD/CNY", payload["valuation_snapshot_lineage"]["blocked_by"]["fx_pairs"])
        self.assertEqual(payload["analytics_readiness"]["risk"], "partial")

    def test_snapshot_lineage_marks_stale_fx_partial_without_price_downgrade(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "FX Stale", "broker": "Demo", "market": "global", "base_currency": "CNY"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]
        self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "AAPL",
                "trade_date": "2026-01-01",
                "side": "buy",
                "quantity": 2,
                "price": 100.0,
                "market": "us",
                "currency": "USD",
            },
        )
        self._save_close("AAPL", date(2026, 1, 2), 130.0)
        PortfolioService().repo.save_fx_rate(
            from_currency="USD",
            to_currency="CNY",
            rate_date=date(2026, 1, 2),
            rate=7.0,
            source="manual",
            is_stale=True,
        )

        snapshot_resp = self.client.get(
            "/api/v1/portfolio/snapshot",
            params={"account_id": account_id, "as_of": "2026-01-02", "cost_method": "fifo"},
        )
        self.assertEqual(snapshot_resp.status_code, 200)
        payload = snapshot_resp.json()

        self.assertEqual(payload["price_lineage"]["status"], "available")
        self.assertEqual(payload["fx_lineage"]["status"], "stale")
        self.assertEqual(payload["fx_lineage"]["score_authority"], "observation_only")
        self.assertEqual(payload["fx_lineage"]["counts"]["stale"], 1)
        self.assertEqual(payload["fx_lineage"]["affected_currencies"]["stale"], ["USD"])
        self.assertEqual(payload["valuation_snapshot_lineage"]["status"], "partial")
        self.assertEqual(payload["analytics_readiness"]["score_authority"], "observation_only")

    def test_snapshot_and_risk_contract_distinguishes_no_account(self) -> None:
        snapshot_resp = self.client.get(
            "/api/v1/portfolio/snapshot",
            params={"as_of": "2026-01-02", "cost_method": "fifo"},
        )
        risk_resp = self.client.get(
            "/api/v1/portfolio/risk",
            params={"as_of": "2026-01-02", "cost_method": "fifo"},
        )

        self.assertEqual(snapshot_resp.status_code, 200)
        self.assertEqual(risk_resp.status_code, 200)
        snapshot = snapshot_resp.json()
        risk = risk_resp.json()
        self.assertEqual(snapshot["account_count"], 0)
        self.assertEqual(snapshot["data_status"], "no_account")
        self.assertEqual(snapshot["calculation_status"], "calculation_unavailable")
        self.assertFalse(snapshot["availability"]["metrics_ready"])
        self.assertEqual(snapshot["availability"]["reason"], "no_account")
        self.assertEqual(risk["data_status"], "no_account")
        self.assertEqual(risk["calculation_status"], "calculation_unavailable")
        self.assertFalse(risk["availability"]["metrics_ready"])
        self.assertEqual(risk["availability"]["reason"], "no_account")

    def test_snapshot_and_risk_contract_distinguishes_no_positions(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Empty", "broker": "Demo", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]

        snapshot_resp = self.client.get(
            "/api/v1/portfolio/snapshot",
            params={"account_id": account_id, "as_of": "2026-01-02", "cost_method": "fifo"},
        )
        risk_resp = self.client.get(
            "/api/v1/portfolio/risk",
            params={"account_id": account_id, "as_of": "2026-01-02", "cost_method": "fifo"},
        )

        self.assertEqual(snapshot_resp.status_code, 200)
        self.assertEqual(risk_resp.status_code, 200)
        snapshot = snapshot_resp.json()
        risk = risk_resp.json()
        self.assertEqual(snapshot["data_status"], "no_positions")
        self.assertEqual(snapshot["calculation_status"], "calculation_unavailable")
        self.assertEqual(snapshot["accounts"][0]["data_status"], "no_positions")
        self.assertFalse(snapshot["availability"]["metrics_ready"])
        self.assertEqual(snapshot["availability"]["reason"], "no_positions")
        self.assertEqual(risk["data_status"], "no_positions")
        self.assertEqual(risk["calculation_status"], "calculation_unavailable")
        self.assertFalse(risk["availability"]["metrics_ready"])
        self.assertEqual(risk["availability"]["reason"], "no_positions")

    def test_snapshot_and_risk_contract_marks_provider_unavailable_prices(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Provider Gap", "broker": "Demo", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]

        trade_resp = self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "AAPL",
                "trade_date": "2026-01-01",
                "side": "buy",
                "quantity": 10,
                "price": 100.0,
                "market": "us",
                "currency": "USD",
            },
        )
        self.assertEqual(trade_resp.status_code, 200)

        snapshot_resp = self.client.get(
            "/api/v1/portfolio/snapshot",
            params={"account_id": account_id, "as_of": "2026-01-02", "cost_method": "fifo"},
        )
        risk_resp = self.client.get(
            "/api/v1/portfolio/risk",
            params={"account_id": account_id, "as_of": "2026-01-02", "cost_method": "fifo"},
        )

        self.assertEqual(snapshot_resp.status_code, 200)
        self.assertEqual(risk_resp.status_code, 200)
        snapshot = snapshot_resp.json()
        risk = risk_resp.json()
        self.assertEqual(snapshot["data_status"], "provider_unavailable")
        self.assertEqual(snapshot["calculation_status"], "ready")
        self.assertEqual(snapshot["accounts"][0]["data_status"], "provider_unavailable")
        self.assertTrue(snapshot["availability"]["metrics_ready"])
        self.assertEqual(snapshot["availability"]["reason"], "provider_unavailable")
        self.assertEqual(risk["data_status"], "provider_unavailable")
        self.assertEqual(risk["calculation_status"], "ready")
        self.assertTrue(risk["availability"]["metrics_ready"])
        self.assertEqual(risk["availability"]["reason"], "provider_unavailable")

    def test_snapshot_api_exposes_position_price_fallback_metadata(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Main", "broker": "Demo", "market": "cn", "base_currency": "CNY"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]

        cash_resp = self.client.post(
            "/api/v1/portfolio/cash-ledger",
            json={
                "account_id": account_id,
                "event_date": "2026-01-01",
                "direction": "in",
                "amount": 10000,
                "currency": "CNY",
            },
        )
        self.assertEqual(cash_resp.status_code, 200)

        trade_resp = self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "600519",
                "trade_date": "2026-01-02",
                "side": "buy",
                "quantity": 10,
                "price": 100.0,
                "market": "cn",
                "currency": "CNY",
            },
        )
        self.assertEqual(trade_resp.status_code, 200)

        snapshot_resp = self.client.get(
            "/api/v1/portfolio/snapshot",
            params={"account_id": account_id, "as_of": "2026-01-02", "cost_method": "fifo"},
        )
        self.assertEqual(snapshot_resp.status_code, 200)

        position = snapshot_resp.json()["accounts"][0]["positions"][0]
        self.assertEqual(position["price_source"], "avg_cost_fallback")
        self.assertEqual(position["price_source_label"], "Average cost fallback")
        self.assertIsNone(position["price_as_of"])
        self.assertTrue(position["is_price_fallback"])
        self.assertEqual(position["price_fallback_reason"], "current_quote_unavailable")
        self.assertLess(position["valuation_confidence"], 0.5)

    def test_snapshot_invalid_cost_method_returns_400(self) -> None:
        resp = self.client.get("/api/v1/portfolio/snapshot", params={"cost_method": "bad"})
        self.assertEqual(resp.status_code, 400)
        detail = resp.json()
        self.assertEqual(detail.get("error"), "validation_error")

    def test_risk_api_returns_account_attribution_block(self) -> None:
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
                "event_date": "2026-01-01",
                "direction": "in",
                "amount": 1000,
                "currency": "CNY",
            },
        )
        self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "600519",
                "trade_date": "2026-01-01",
                "side": "buy",
                "quantity": 10,
                "price": 100,
                "market": "cn",
                "currency": "CNY",
            },
        )
        self._save_close("600519", date(2026, 1, 1), 100.0)

        risk_resp = self.client.get(
            "/api/v1/portfolio/risk",
            params={"account_id": account_id, "as_of": "2026-01-01", "cost_method": "fifo"},
        )
        self.assertEqual(risk_resp.status_code, 200)
        payload = risk_resp.json()
        self.assertIn("account_attribution", payload)
        self.assertIn("industry_attribution", payload)
        self.assertEqual(payload["account_attribution"]["top_accounts"][0]["account_id"], account_id)
        self.assertEqual(payload["account_attribution"]["top_accounts"][0]["equity_weight_pct"], 100.0)
        self.assertEqual(payload["industry_attribution"]["top_industries"][0]["weight_pct"], 100.0)

    def test_snapshot_api_returns_portfolio_attribution_block(self) -> None:
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
                "event_date": "2026-01-01",
                "direction": "in",
                "amount": 1000,
                "currency": "CNY",
            },
        )
        self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "600519",
                "trade_date": "2026-01-01",
                "side": "buy",
                "quantity": 10,
                "price": 100,
                "market": "cn",
                "currency": "CNY",
            },
        )
        self._save_close("600519", date(2026, 1, 1), 100.0)

        snapshot_resp = self.client.get(
            "/api/v1/portfolio/snapshot",
            params={"as_of": "2026-01-01", "cost_method": "fifo"},
        )
        self.assertEqual(snapshot_resp.status_code, 200)
        payload = snapshot_resp.json()
        self.assertIn("portfolio_attribution", payload)
        self.assertEqual(payload["portfolio_attribution"]["account_attribution"]["top_accounts"][0]["account_id"], account_id)
        self.assertEqual(payload["portfolio_attribution"]["industry_attribution"]["top_industries"][0]["weight_pct"], 100.0)

    def test_broker_connection_api_flow(self) -> None:
        account_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Global", "broker": "IBKR", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(account_resp.status_code, 200)
        account_id = account_resp.json()["id"]

        create_resp = self.client.post(
            "/api/v1/portfolio/broker-connections",
            json={
                "portfolio_account_id": account_id,
                "broker_type": "ibkr",
                "broker_name": "Interactive Brokers",
                "connection_name": "Primary IBKR",
                "broker_account_ref": "U1234567",
                "import_mode": "file",
                "status": "active",
                "sync_metadata": {"source": "flex"},
            },
        )
        self.assertEqual(create_resp.status_code, 200)
        created = create_resp.json()
        self.assertEqual(created["portfolio_account_id"], account_id)
        self.assertEqual(created["broker_type"], "ibkr")
        self.assertEqual(created["sync_metadata"], {"source": "flex"})
        self.assertRegex(created["portfolio_account_name"], r"^acct_[a-f0-9]{12}$")
        self.assertRegex(created["broker_account_ref"], r"^acct_[a-f0-9]{12}$")
        self.assertRegex(created["connection_name"], r"^conn_[a-f0-9]{12}$")

        list_resp = self.client.get("/api/v1/portfolio/broker-connections")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(len(list_resp.json()["connections"]), 1)
        self.assertRegex(list_resp.json()["connections"][0]["portfolio_account_name"], r"^acct_[a-f0-9]{12}$")

        update_resp = self.client.put(
            f"/api/v1/portfolio/broker-connections/{created['id']}",
            json={
                "connection_name": "IBKR Flex",
                "status": "disabled",
                "sync_metadata": {"source": "flex", "scope": "global"},
            },
        )
        self.assertEqual(update_resp.status_code, 200)
        updated = update_resp.json()
        self.assertRegex(updated["connection_name"], r"^conn_[a-f0-9]{12}$")
        self.assertEqual(updated["status"], "disabled")
        self.assertEqual(updated["sync_metadata"]["scope"], "global")

        duplicate_resp = self.client.post(
            "/api/v1/portfolio/broker-connections",
            json={
                "portfolio_account_id": account_id,
                "broker_type": "ibkr",
                "connection_name": "Duplicate Ref",
                "broker_account_ref": "U1234567",
                "sync_metadata": {},
            },
        )
        self.assertEqual(duplicate_resp.status_code, 409)
        detail = duplicate_resp.json()
        self.assertEqual(detail.get("error"), "conflict")

    def test_broker_connection_read_payload_redacts_sensitive_metadata(self) -> None:
        account_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={
                "name": "synthetic_account_label_must_not_leak",
                "broker": "IBKR",
                "market": "us",
                "base_currency": "USD",
            },
        )
        self.assertEqual(account_resp.status_code, 200)
        account_id = account_resp.json()["id"]
        raw_markers = (
            "synthetic_account_label_must_not_leak",
            "synthetic_provider_url_must_not_leak",
            "synthetic_import_fingerprint_must_not_leak",
            "synthetic_broker_connection_name_must_not_leak",
            "synthetic_raw_payload_label_must_not_leak",
            "synthetic_import_file_label_must_not_leak",
            "synthetic_request_id_must_not_leak",
            "SECRET_API_KEY",
            "SECRET_TOKEN",
            "bearer abc.def.ghi",
        )

        create_resp = self.client.post(
            "/api/v1/portfolio/broker-connections",
            json={
                "portfolio_account_id": account_id,
                "broker_type": "ibkr",
                "broker_name": "synthetic_broker_connection_name_must_not_leak",
                "connection_name": "synthetic_broker_connection_name_must_not_leak",
                "broker_account_ref": "synthetic_account_label_must_not_leak",
                "import_mode": "api",
                "status": "active",
                "sync_metadata": {
                    "source": "flex",
                    "provider_url": "https://broker.example.invalid/synthetic_provider_url_must_not_leak",
                    "import_fingerprint": "synthetic_import_fingerprint_must_not_leak",
                    "raw_payload_label": "synthetic_raw_payload_label_must_not_leak",
                    "import_file_label": "synthetic_import_file_label_must_not_leak",
                    "request_id": "synthetic_request_id_must_not_leak",
                    "api_key": "SECRET_API_KEY",
                    "nested": {"token": "SECRET_TOKEN", "ok": True},
                    "note": "bearer abc.def.ghi",
                },
            },
        )
        self.assertEqual(create_resp.status_code, 200)
        created = create_resp.json()
        self.assertRegex(created["portfolio_account_name"], r"^acct_[a-f0-9]{12}$")
        self.assertRegex(created["broker_name"], r"^broker_[a-f0-9]{12}$")
        self.assertRegex(created["connection_name"], r"^conn_[a-f0-9]{12}$")
        self.assertRegex(created["broker_account_ref"], r"^acct_[a-f0-9]{12}$")
        self.assertEqual(created["sync_metadata"]["source"], "flex")
        self.assertRegex(created["sync_metadata"]["provider_url"], r"^url_[a-f0-9]{12}$")
        self.assertRegex(created["sync_metadata"]["import_fingerprint"], r"^import_[a-f0-9]{12}$")
        self.assertRegex(created["sync_metadata"]["raw_payload_label"], r"^payload_[a-f0-9]{12}$")
        self.assertRegex(created["sync_metadata"]["import_file_label"], r"^file_[a-f0-9]{12}$")
        self.assertRegex(created["sync_metadata"]["request_id"], r"^req_[a-f0-9]{12}$")
        self.assertEqual(created["sync_metadata"]["api_key"], "***")
        self.assertEqual(created["sync_metadata"]["nested"]["token"], "***")
        for marker in raw_markers:
            self.assertNotIn(marker, self._json_text(create_resp))

        list_resp = self.client.get("/api/v1/portfolio/broker-connections")
        self.assertEqual(list_resp.status_code, 200)
        for marker in raw_markers:
            self.assertNotIn(marker, self._json_text(list_resp))

    def test_broker_import_preview_and_commit_redact_browser_artifact_identifiers(self) -> None:
        account_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Import Redaction", "broker": "IBKR", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(account_resp.status_code, 200)
        account_id = account_resp.json()["id"]
        fixture = self._ibkr_sensitive_flex_xml_bytes()
        raw_markers = (
            "fixture-broker-account-ref-must-not-leak",
            "fixture-execution-id-must-not-leak",
            "fixture-order-id-must-not-leak",
            "fixture-request-id-must-not-leak",
            "fixture-account-label-must-not-leak",
            "synthetic_provider_url_must_not_leak",
            "synthetic_import_fingerprint_must_not_leak",
            "synthetic_broker_connection_name_must_not_leak",
            "synthetic_raw_payload_label_must_not_leak",
            "synthetic_import_file_label_must_not_leak",
            "fixture-token-must-not-leak",
            "fixture-url-token-must-not-leak",
            "broker.example.invalid",
        )

        parse_resp = self.client.post(
            "/api/v1/portfolio/imports/parse",
            data={"broker": "ibkr"},
            files={"file": ("ibkr-sensitive-flex.xml", fixture, "application/xml")},
        )
        self.assertEqual(parse_resp.status_code, 200)
        parsed = parse_resp.json()
        self.assertRegex(parsed["metadata"]["broker_account_ref"], r"^acct_[a-f0-9]{12}$")
        self.assertRegex(parsed["metadata"]["file_fingerprint"], r"^file_[a-f0-9]{12}$")
        self.assertRegex(parsed["metadata"]["suggested_connection_name"], r"^conn_[a-f0-9]{12}$")
        self.assertRegex(parsed["records"][0]["trade_uid"], r"^trade_[a-f0-9]{12}$")
        self.assertRegex(parsed["records"][0]["dedup_hash"], r"^import_[a-f0-9]{12}$")
        self.assertRegex(parsed["records"][0]["note"], r"^(payload|url)_[a-f0-9]{12}$")

        commit_resp = self.client.post(
            "/api/v1/portfolio/imports/commit",
            data={"account_id": str(account_id), "broker": "ibkr", "dry_run": "false"},
            files={"file": ("ibkr-sensitive-flex.xml", fixture, "application/xml")},
        )
        self.assertEqual(commit_resp.status_code, 200)
        committed = commit_resp.json()
        self.assertRegex(committed["metadata"]["broker_account_ref"], r"^acct_[a-f0-9]{12}$")
        self.assertRegex(committed["metadata"]["file_fingerprint"], r"^file_[a-f0-9]{12}$")
        self.assertRegex(committed["metadata"]["suggested_connection_name"], r"^conn_[a-f0-9]{12}$")

        duplicate_resp = self.client.post(
            "/api/v1/portfolio/imports/commit",
            data={"account_id": str(account_id), "broker": "ibkr", "dry_run": "false"},
            files={"file": ("ibkr-sensitive-flex.xml", fixture, "application/xml")},
        )
        self.assertEqual(duplicate_resp.status_code, 200)
        duplicate = duplicate_resp.json()
        self.assertTrue(duplicate["duplicate_import"])
        self.assertRegex(duplicate["metadata"]["broker_account_ref"], r"^acct_[a-f0-9]{12}$")
        self.assertRegex(duplicate["metadata"]["file_fingerprint"], r"^file_[a-f0-9]{12}$")
        self.assertRegex(duplicate["metadata"]["suggested_connection_name"], r"^conn_[a-f0-9]{12}$")

        combined_text = (
            f"{self._json_text(parse_resp)}\n"
            f"{self._json_text(commit_resp)}\n"
            f"{self._json_text(duplicate_resp)}"
        )
        for marker in raw_markers:
            self.assertNotIn(marker, combined_text)

    def test_import_parse_errors_use_safe_envelopes_without_raw_exception_text(self) -> None:
        cases = (
            (
                "/api/v1/portfolio/imports/parse",
                "parse_import_file",
                "ibkr",
                "ibkr-flex.xml",
                "application/xml",
            ),
            (
                "/api/v1/portfolio/imports/csv/parse",
                "parse_trade_csv",
                "huatai",
                "huatai.csv",
                "text/csv",
            ),
        )

        for endpoint, method_name, broker, filename, content_type in cases:
            with self.subTest(endpoint=endpoint):
                with patch(
                    f"api.v1.endpoints.portfolio.PortfolioImportService.{method_name}",
                    side_effect=ValueError(_raw_import_exception_text()),
                ):
                    response = self.client.post(
                        endpoint,
                        data={"broker": broker},
                        files={"file": (filename, b"synthetic", content_type)},
                    )

                self._assert_safe_import_error(
                    response,
                    status_code=400,
                    error_code="validation_error",
                    message=SAFE_IMPORT_VALIDATION_MESSAGE,
                )

    def test_import_commit_conflicts_use_safe_envelopes_without_raw_broker_markers(self) -> None:
        account_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Conflict Import", "broker": "IBKR", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(account_resp.status_code, 200)
        account_id = account_resp.json()["id"]
        cases = (
            (
                "/api/v1/portfolio/imports/commit",
                "parse_import_file",
                "ibkr",
                "ibkr-flex.xml",
                "application/xml",
            ),
            (
                "/api/v1/portfolio/imports/csv/commit",
                "parse_trade_csv",
                "huatai",
                "huatai.csv",
                "text/csv",
            ),
        )

        for endpoint, parse_method_name, broker, filename, content_type in cases:
            with self.subTest(endpoint=endpoint):
                with patch(
                    f"api.v1.endpoints.portfolio.PortfolioImportService.{parse_method_name}",
                    return_value={"broker": broker},
                ), patch(
                    "api.v1.endpoints.portfolio.PortfolioImportService.commit_import_records",
                    side_effect=PortfolioConflictError(_raw_import_exception_text()),
                ):
                    response = self.client.post(
                        endpoint,
                        data={"account_id": str(account_id), "broker": broker, "dry_run": "false"},
                        files={"file": (filename, b"synthetic", content_type)},
                    )

                self._assert_safe_import_error(
                    response,
                    status_code=409,
                    error_code="conflict",
                    message=SAFE_IMPORT_CONFLICT_MESSAGE,
                )

    def test_import_internal_errors_use_safe_envelope_without_traceback_or_provider_url(self) -> None:
        with patch(
            "api.v1.endpoints.portfolio.PortfolioImportService.parse_import_file",
            side_effect=RuntimeError(_raw_import_exception_text()),
        ):
            response = self.client.post(
                "/api/v1/portfolio/imports/parse",
                data={"broker": "ibkr"},
                files={"file": ("ibkr-flex.xml", b"synthetic", "application/xml")},
            )

        self._assert_safe_import_error(
            response,
            status_code=500,
            error_code="internal_error",
            message=SAFE_IMPORT_INTERNAL_MESSAGE,
        )

    def test_csv_import_preview_and_commit_redact_trade_ids_and_fingerprints(self) -> None:
        account_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "CSV Import Redaction", "broker": "Huatai", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(account_resp.status_code, 200)
        account_id = account_resp.json()["id"]
        trade_uid = "fixture-order-id-must-not-leak"
        csv_text = (
            "成交日期,证券代码,买卖标志,成交数量,成交均价,手续费,印花税,币种,成交编号\n"
            f"2026-01-03,AAPL,买入,10,150,1.25,0,USD,{trade_uid}\n"
        )
        fixture = csv_text.encode("utf-8")

        parse_resp = self.client.post(
            "/api/v1/portfolio/imports/csv/parse",
            data={"broker": "huatai"},
            files={"file": ("huatai-sensitive.csv", fixture, "text/csv")},
        )
        self.assertEqual(parse_resp.status_code, 200)
        parsed = parse_resp.json()
        self.assertRegex(parsed["records"][0]["trade_uid"], r"^trade_[a-f0-9]{12}$")
        self.assertRegex(parsed["records"][0]["dedup_hash"], r"^import_[a-f0-9]{12}$")
        self.assertRegex(parsed["metadata"]["file_fingerprint"], r"^file_[a-f0-9]{12}$")

        commit_resp = self.client.post(
            "/api/v1/portfolio/imports/csv/commit",
            data={"account_id": str(account_id), "broker": "huatai", "dry_run": "true"},
            files={"file": ("huatai-sensitive.csv", fixture, "text/csv")},
        )
        self.assertEqual(commit_resp.status_code, 200)
        committed = commit_resp.json()
        self.assertTrue(committed["dry_run"])
        self.assertRegex(committed["metadata"]["file_fingerprint"], r"^file_[a-f0-9]{12}$")

        combined_text = f"{self._json_text(parse_resp)}\n{self._json_text(commit_resp)}"
        self.assertNotIn(trade_uid, combined_text)

    def test_generic_broker_import_endpoints_support_ibkr(self) -> None:
        account_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Global", "broker": "IBKR", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(account_resp.status_code, 200)
        account_id = account_resp.json()["id"]

        broker_list_resp = self.client.get("/api/v1/portfolio/imports/brokers")
        self.assertEqual(broker_list_resp.status_code, 200)
        brokers = {item["broker"] for item in broker_list_resp.json()["brokers"]}
        self.assertIn("ibkr", brokers)

        parse_resp = self.client.post(
            "/api/v1/portfolio/imports/parse",
            data={"broker": "ibkr"},
            files={"file": ("ibkr-flex.xml", self._ibkr_flex_xml_bytes(), "application/xml")},
        )
        self.assertEqual(parse_resp.status_code, 200)
        parsed = parse_resp.json()
        self.assertEqual(parsed["broker"], "ibkr")
        self.assertEqual(parsed["record_count"], 1)
        self.assertEqual(parsed["cash_record_count"], 1)
        self.assertRegex(parsed["metadata"]["broker_account_ref"], r"^acct_[a-f0-9]{12}$")
        self.assertNotIn("U1234567", self._json_text(parse_resp))

        commit_resp = self.client.post(
            "/api/v1/portfolio/imports/commit",
            data={"account_id": str(account_id), "broker": "ibkr", "dry_run": "false"},
            files={"file": ("ibkr-flex.xml", self._ibkr_flex_xml_bytes(), "application/xml")},
        )
        self.assertEqual(commit_resp.status_code, 200)
        committed = commit_resp.json()
        self.assertEqual(committed["inserted_count"], 1)
        self.assertEqual(committed["cash_inserted_count"], 1)
        self.assertIsNotNone(committed["broker_connection_id"])

    def test_ibkr_import_preview_reports_contract_without_creating_connection(self) -> None:
        account_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Preview", "broker": "IBKR", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(account_resp.status_code, 200)
        account_id = account_resp.json()["id"]

        before_connections = self.client.get(
            "/api/v1/portfolio/broker-connections",
            params={"portfolio_account_id": account_id},
        )
        self.assertEqual(before_connections.status_code, 200)
        self.assertEqual(before_connections.json()["connections"], [])

        preview_resp = self.client.post(
            "/api/v1/portfolio/imports/commit",
            data={"account_id": str(account_id), "broker": "ibkr", "dry_run": "true"},
            files={"file": ("ibkr-flex.xml", self._ibkr_flex_xml_bytes(), "application/xml")},
        )
        self.assertEqual(preview_resp.status_code, 200)
        preview = preview_resp.json()
        self.assertTrue(preview["dry_run"])
        self.assertTrue(preview["preview_only"])
        self.assertTrue(preview["requires_confirmation"])
        self.assertEqual(preview["accepted_count"], 2)
        self.assertEqual(preview["rejected_count"], 0)
        self.assertEqual(preview["account_mapping"]["status"], "will_create_on_confirm")
        self.assertEqual(preview["account_mapping"]["account_id"], account_id)
        self.assertEqual(preview["validation_checks"][0]["check"], "date_quantity_price")
        self.assertIn("currency_review", {item["check"] for item in preview["validation_checks"]})

        after_connections = self.client.get(
            "/api/v1/portfolio/broker-connections",
            params={"portfolio_account_id": account_id},
        )
        self.assertEqual(after_connections.status_code, 200)
        self.assertEqual(after_connections.json()["connections"], [])

    @patch("api.v1.endpoints.portfolio.PortfolioIbkrSyncService.sync_read_only_account_state")
    def test_ibkr_sync_endpoint_contract(self, sync_mock: MagicMock) -> None:
        account_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Global", "broker": "IBKR", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(account_resp.status_code, 200)
        account_id = account_resp.json()["id"]

        sync_mock.return_value = {
            "account_id": account_id,
            "broker_connection_id": 9,
            "broker_account_ref": "U1234567",
            "connection_name": "IBKR U1234567",
            "snapshot_date": "2026-04-15",
            "synced_at": "2026-04-15T09:00:00",
            "base_currency": "USD",
            "total_cash": 5000.0,
            "total_market_value": 1600.0,
            "total_equity": 6600.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 100.0,
            "position_count": 1,
            "cash_balance_count": 1,
            "fx_stale": False,
            "snapshot_overlay_active": True,
            "used_existing_connection": False,
            "api_base_url": "https://localhost:5000/v1/api",
            "verify_ssl": False,
            "warnings": [],
        }

        resp = self.client.post(
            "/api/v1/portfolio/sync/ibkr",
            json={
                "account_id": account_id,
                "session_token": "unit-test-session",
                "api_base_url": "https://localhost:5000",
                "verify_ssl": False,
            },
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertRegex(payload["broker_account_ref"], r"^acct_[a-f0-9]{12}$")
        self.assertRegex(payload["connection_name"], r"^conn_[a-f0-9]{12}$")
        self.assertRegex(payload["api_base_url"], r"^url_[a-f0-9]{12}$")
        self.assertNotIn("U1234567", self._json_text(resp))
        self.assertNotIn("https://localhost:5000", self._json_text(resp))
        self.assertTrue(payload["snapshot_overlay_active"])
        sync_mock.assert_called_once_with(
            account_id=account_id,
            broker_connection_id=None,
            broker_account_ref=None,
            session_token="unit-test-session",
            api_base_url="https://localhost:5000",
            verify_ssl=False,
        )

    @patch("api.v1.endpoints.portfolio.PortfolioIbkrSyncService.sync_read_only_account_state")
    def test_ibkr_sync_endpoint_ignores_display_handles_for_raw_matching(self, sync_mock: MagicMock) -> None:
        account_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Global", "broker": "IBKR", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(account_resp.status_code, 200)
        account_id = account_resp.json()["id"]

        sync_mock.return_value = {
            "account_id": account_id,
            "broker_connection_id": 9,
            "broker_account_ref": "synthetic_account_label_must_not_leak",
            "connection_name": "synthetic_broker_connection_name_must_not_leak",
            "snapshot_date": "2026-04-15",
            "synced_at": "2026-04-15T09:00:00",
            "base_currency": "USD",
            "total_cash": 5000.0,
            "total_market_value": 1600.0,
            "total_equity": 6600.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 100.0,
            "position_count": 1,
            "cash_balance_count": 1,
            "fx_stale": False,
            "snapshot_overlay_active": True,
            "used_existing_connection": True,
            "api_base_url": "https://broker.example.invalid/synthetic_provider_url_must_not_leak",
            "verify_ssl": False,
            "warnings": ["request_id=synthetic_request_id_must_not_leak"],
        }

        resp = self.client.post(
            "/api/v1/portfolio/sync/ibkr",
            json={
                "account_id": account_id,
                "broker_connection_id": 9,
                "broker_account_ref": "acct_123456789abc",
                "session_token": "unit-test-session",
                "api_base_url": "url_123456789abc",
                "verify_ssl": False,
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("synthetic_account_label_must_not_leak", self._json_text(resp))
        self.assertNotIn("synthetic_broker_connection_name_must_not_leak", self._json_text(resp))
        self.assertNotIn("synthetic_provider_url_must_not_leak", self._json_text(resp))
        self.assertNotIn("synthetic_request_id_must_not_leak", self._json_text(resp))
        sync_mock.assert_called_once_with(
            account_id=account_id,
            broker_connection_id=9,
            broker_account_ref=None,
            session_token="unit-test-session",
            api_base_url=None,
            verify_ssl=False,
        )

    @patch("api.v1.endpoints.portfolio.PortfolioIbkrSyncService.sync_read_only_account_state")
    def test_ibkr_sync_endpoint_surfaces_structured_session_error(self, sync_mock: MagicMock) -> None:
        account_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Global", "broker": "IBKR", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(account_resp.status_code, 200)
        account_id = account_resp.json()["id"]

        sync_mock.side_effect = PortfolioIbkrSyncError(
            code="ibkr_session_expired",
            message="当前 IBKR session 已失效、未授权或未连上可访问账户。",
            status_code=400,
        )

        resp = self.client.post(
            "/api/v1/portfolio/sync/ibkr",
            json={
                "account_id": account_id,
                "session_token": "expired-session",
            },
        )
        self.assertEqual(resp.status_code, 400)
        payload = resp.json()
        self.assertEqual(payload.get("error"), "ibkr_session_expired")
        self.assertEqual(payload.get("code"), "ibkr_session_expired")
        self.assertEqual(payload.get("message"), "当前 IBKR session 已失效、未授权或未连上可访问账户。")
        self.assertEqual(payload.get("status"), 400)

    @patch("api.v1.endpoints.portfolio.PortfolioIbkrSyncService.sync_read_only_account_state")
    def test_ibkr_sync_endpoint_sanitizes_secret_like_error_text(self, sync_mock: MagicMock) -> None:
        account_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Global", "broker": "IBKR", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(account_resp.status_code, 200)
        account_id = account_resp.json()["id"]

        sync_mock.side_effect = PortfolioIbkrSyncError(
            code="ibkr_session_expired",
            message="session_token=SECRET_SESSION_TOKEN was rejected",
            status_code=400,
        )

        resp = self.client.post(
            "/api/v1/portfolio/sync/ibkr",
            json={
                "account_id": account_id,
                "session_token": "SECRET_SESSION_TOKEN",
            },
        )
        self.assertEqual(resp.status_code, 400)
        text = self._json_text(resp)
        self.assertNotIn("SECRET_SESSION_TOKEN", text)
        self.assertNotIn("session_token", text)
        self.assertIn("Portfolio broker sync could not be processed.", text)

    @patch("api.v1.endpoints.portfolio.PortfolioIbkrSyncService.sync_read_only_account_state")
    def test_ibkr_sync_endpoint_surfaces_mapping_conflict(self, sync_mock: MagicMock) -> None:
        account_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Global", "broker": "IBKR", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(account_resp.status_code, 200)
        account_id = account_resp.json()["id"]

        sync_mock.side_effect = PortfolioIbkrSyncError(
            code="ibkr_account_mapping_conflict",
            message="该 broker account ref 已绑定到当前用户的另一持仓账户。",
            status_code=409,
        )

        resp = self.client.post(
            "/api/v1/portfolio/sync/ibkr",
            json={
                "account_id": account_id,
                "session_token": "unit-test-session",
                "broker_account_ref": "U1234567",
            },
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["error"], "ibkr_account_mapping_conflict")

    def test_duplicate_trade_uid_returns_409(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Main", "broker": "Demo", "market": "cn", "base_currency": "CNY"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]

        payload = {
            "account_id": account_id,
            "symbol": "600519",
            "trade_date": "2026-01-02",
            "side": "buy",
            "quantity": 10,
            "price": 100,
            "fee": 0,
            "tax": 0,
            "market": "cn",
            "currency": "CNY",
            "trade_uid": "dup-uid-1",
        }
        first = self.client.post("/api/v1/portfolio/trades", json=payload)
        self.assertEqual(first.status_code, 200)

        second = self.client.post("/api/v1/portfolio/trades", json=payload)
        self.assertEqual(second.status_code, 409)
        detail = second.json()
        self.assertEqual(detail.get("error"), "conflict")

    def test_oversell_trade_returns_409_with_business_error(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Main", "broker": "Demo", "market": "cn", "base_currency": "CNY"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]

        buy_resp = self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "600519",
                "trade_date": "2026-01-02",
                "side": "buy",
                "quantity": 10,
                "price": 100,
                "fee": 0,
                "tax": 0,
                "market": "cn",
                "currency": "CNY",
            },
        )
        self.assertEqual(buy_resp.status_code, 200)

        sell_resp = self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "600519",
                "trade_date": "2026-01-03",
                "side": "sell",
                "quantity": 20,
                "price": 90,
                "fee": 0,
                "tax": 0,
                "market": "cn",
                "currency": "CNY",
            },
        )
        self.assertEqual(sell_resp.status_code, 409)
        detail = sell_resp.json()
        self.assertEqual(detail.get("error"), "portfolio_oversell")
        self.assertIn("Oversell detected", detail.get("message", ""))

    def test_duplicate_full_close_sell_still_returns_conflict(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Main", "broker": "Demo", "market": "cn", "base_currency": "CNY"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]

        buy_resp = self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "600519",
                "trade_date": "2026-01-01",
                "side": "buy",
                "quantity": 10,
                "price": 100,
                "fee": 0,
                "tax": 0,
                "market": "cn",
                "currency": "CNY",
            },
        )
        self.assertEqual(buy_resp.status_code, 200)

        payload = {
            "account_id": account_id,
            "symbol": "600519",
            "trade_date": "2026-01-02",
            "side": "sell",
            "quantity": 10,
            "price": 90,
            "fee": 0,
            "tax": 0,
            "market": "cn",
            "currency": "CNY",
            "trade_uid": "dup-full-close-sell-1",
        }
        first_sell = self.client.post("/api/v1/portfolio/trades", json=payload)
        self.assertEqual(first_sell.status_code, 200)

        second_sell = self.client.post("/api/v1/portfolio/trades", json=payload)
        self.assertEqual(second_sell.status_code, 409)
        detail = second_sell.json()
        self.assertEqual(detail.get("error"), "conflict")
        self.assertIn("Duplicate trade_uid", detail.get("message", ""))

    def test_event_list_endpoints_and_filters(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Main", "broker": "Demo", "market": "cn", "base_currency": "CNY"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]

        cash_resp = self.client.post(
            "/api/v1/portfolio/cash-ledger",
            json={
                "account_id": account_id,
                "event_date": "2026-01-01",
                "direction": "in",
                "amount": 10000,
                "currency": "CNY",
            },
        )
        self.assertEqual(cash_resp.status_code, 200)

        trade_payload = {
            "account_id": account_id,
            "symbol": "600519",
            "side": "buy",
            "quantity": 10,
            "price": 100,
            "fee": 1,
            "tax": 0,
            "market": "cn",
            "currency": "CNY",
        }
        self.assertEqual(
            self.client.post("/api/v1/portfolio/trades", json={**trade_payload, "trade_date": "2026-01-02"}).status_code,
            200,
        )
        self.assertEqual(
            self.client.post("/api/v1/portfolio/trades", json={**trade_payload, "trade_date": "2026-01-03"}).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/portfolio/corporate-actions",
                json={
                    "account_id": account_id,
                    "symbol": "600519",
                    "effective_date": "2026-01-04",
                    "action_type": "cash_dividend",
                    "market": "cn",
                    "currency": "CNY",
                    "cash_dividend_per_share": 0.5,
                },
            ).status_code,
            200,
        )

        trades_resp = self.client.get(
            "/api/v1/portfolio/trades",
            params={"account_id": account_id, "page": 1, "page_size": 1},
        )
        self.assertEqual(trades_resp.status_code, 200)
        trades_payload = trades_resp.json()
        self.assertEqual(trades_payload["total"], 2)
        self.assertEqual(len(trades_payload["items"]), 1)
        self.assertEqual(trades_payload["items"][0]["trade_date"], "2026-01-03")

        cash_list_resp = self.client.get(
            "/api/v1/portfolio/cash-ledger",
            params={"account_id": account_id, "direction": "in"},
        )
        self.assertEqual(cash_list_resp.status_code, 200)
        cash_payload = cash_list_resp.json()
        self.assertEqual(cash_payload["total"], 1)
        self.assertEqual(cash_payload["items"][0]["direction"], "in")

        corp_list_resp = self.client.get(
            "/api/v1/portfolio/corporate-actions",
            params={"account_id": account_id, "action_type": "cash_dividend"},
        )
        self.assertEqual(corp_list_resp.status_code, 200)
        corp_payload = corp_list_resp.json()
        self.assertEqual(corp_payload["total"], 1)
        self.assertEqual(corp_payload["items"][0]["action_type"], "cash_dividend")

    def test_delete_event_endpoints_remove_records_and_allow_snapshot_recovery(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Main", "broker": "Demo", "market": "cn", "base_currency": "CNY"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]

        cash_resp = self.client.post(
            "/api/v1/portfolio/cash-ledger",
            json={
                "account_id": account_id,
                "event_date": "2026-01-01",
                "direction": "in",
                "amount": 10000,
                "currency": "CNY",
            },
        )
        trade_resp = self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "600519",
                "trade_date": "2026-01-02",
                "side": "buy",
                "quantity": 10,
                "price": 100,
                "fee": 0,
                "tax": 0,
                "market": "cn",
                "currency": "CNY",
            },
        )
        corp_resp = self.client.post(
            "/api/v1/portfolio/corporate-actions",
            json={
                "account_id": account_id,
                "symbol": "600519",
                "effective_date": "2026-01-03",
                "action_type": "cash_dividend",
                "market": "cn",
                "currency": "CNY",
                "cash_dividend_per_share": 1.0,
            },
        )
        self.assertEqual(cash_resp.status_code, 200)
        self.assertEqual(trade_resp.status_code, 200)
        self.assertEqual(corp_resp.status_code, 200)

        self._save_close("600519", date(2026, 1, 3), 100.0)
        snapshot_before = self.client.get(
            "/api/v1/portfolio/snapshot",
            params={"account_id": account_id, "as_of": "2026-01-03"},
        )
        self.assertEqual(snapshot_before.status_code, 200)
        self.assertEqual(snapshot_before.json()["accounts"][0]["positions"][0]["quantity"], 10.0)

        delete_trade = self.client.delete(f"/api/v1/portfolio/trades/{trade_resp.json()['id']}")
        self.assertEqual(delete_trade.status_code, 200)
        self.assertEqual(delete_trade.json()["deleted"], 1)

        snapshot_after_trade = self.client.get(
            "/api/v1/portfolio/snapshot",
            params={"account_id": account_id, "as_of": "2026-01-03"},
        )
        self.assertEqual(snapshot_after_trade.status_code, 200)
        self.assertEqual(snapshot_after_trade.json()["accounts"][0]["positions"], [])

        delete_cash = self.client.delete(f"/api/v1/portfolio/cash-ledger/{cash_resp.json()['id']}")
        self.assertEqual(delete_cash.status_code, 200)
        self.assertEqual(delete_cash.json()["deleted"], 1)

        delete_corp = self.client.delete(f"/api/v1/portfolio/corporate-actions/{corp_resp.json()['id']}")
        self.assertEqual(delete_corp.status_code, 200)
        self.assertEqual(delete_corp.json()["deleted"], 1)

        missing_trade = self.client.delete("/api/v1/portfolio/trades/999999")
        self.assertEqual(missing_trade.status_code, 404)

    def test_create_trade_busy_returns_409(self) -> None:
        with patch(
            "api.v1.endpoints.portfolio.PortfolioService.record_trade",
            side_effect=PortfolioBusyError("Portfolio ledger is busy; please retry shortly."),
        ):
            resp = self.client.post(
                "/api/v1/portfolio/trades",
                json={
                    "account_id": 1,
                    "symbol": "600519",
                    "trade_date": "2026-01-02",
                    "side": "buy",
                    "quantity": 10,
                    "price": 100,
                    "fee": 0,
                    "tax": 0,
                    "market": "cn",
                    "currency": "CNY",
                },
            )

        self.assertEqual(resp.status_code, 409)
        detail = resp.json()
        self.assertEqual(detail.get("error"), "portfolio_busy")

    def test_delete_trade_busy_returns_409(self) -> None:
        with patch(
            "api.v1.endpoints.portfolio.PortfolioService.delete_trade_event",
            side_effect=PortfolioBusyError("Portfolio ledger is busy; please retry shortly."),
        ):
            resp = self.client.delete("/api/v1/portfolio/trades/1")

        self.assertEqual(resp.status_code, 409)
        detail = resp.json()
        self.assertEqual(detail.get("error"), "portfolio_busy")

    def test_update_trade_recalculates_snapshot_and_returns_trade_payload(self) -> None:
        account_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Main", "broker": "Demo", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(account_resp.status_code, 200)
        account_id = account_resp.json()["id"]

        cash_resp = self.client.post(
            "/api/v1/portfolio/cash-ledger",
            json={
                "account_id": account_id,
                "event_date": "2026-01-01",
                "direction": "in",
                "amount": 5000,
                "currency": "USD",
            },
        )
        self.assertEqual(cash_resp.status_code, 200)

        trade_resp = self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "AAPL",
                "trade_date": "2026-01-02",
                "side": "buy",
                "quantity": 10,
                "price": 100,
                "market": "us",
                "currency": "USD",
            },
        )
        self.assertEqual(trade_resp.status_code, 200)
        trade_id = trade_resp.json()["id"]
        self._save_close("AAPL", date(2026, 1, 3), 125.0)

        update_resp = self.client.patch(
            f"/api/v1/portfolio/trades/{trade_id}",
            json={
                "quantity": 5,
                "price": 120,
            },
        )
        self.assertEqual(update_resp.status_code, 200)
        updated_payload = update_resp.json()
        self.assertEqual(updated_payload["id"], trade_id)
        self.assertEqual(updated_payload["quantity"], 5.0)
        self.assertEqual(updated_payload["price"], 120.0)
        self.assertTrue(updated_payload["is_active"])
        self.assertIsNone(updated_payload["voided_at"])

        snapshot_resp = self.client.get(
            "/api/v1/portfolio/snapshot",
            params={"account_id": account_id, "as_of": "2026-01-03"},
        )
        self.assertEqual(snapshot_resp.status_code, 200)
        account_snapshot = snapshot_resp.json()["accounts"][0]
        self.assertEqual(account_snapshot["positions"][0]["quantity"], 5.0)
        self.assertEqual(account_snapshot["positions"][0]["avg_cost"], 120.0)

    def test_update_trade_invalid_payload_returns_400_and_missing_trade_returns_404(self) -> None:
        missing_resp = self.client.patch("/api/v1/portfolio/trades/999999", json={"quantity": 5})
        self.assertEqual(missing_resp.status_code, 404)

        account_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Main", "broker": "Demo", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(account_resp.status_code, 200)
        trade_resp = self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_resp.json()["id"],
                "symbol": "AAPL",
                "trade_date": "2026-01-02",
                "side": "buy",
                "quantity": 10,
                "price": 100,
                "market": "us",
                "currency": "USD",
            },
        )
        self.assertEqual(trade_resp.status_code, 200)

        invalid_resp = self.client.patch(
            f"/api/v1/portfolio/trades/{trade_resp.json()['id']}",
            json={"quantity": 0},
        )
        self.assertEqual(invalid_resp.status_code, 422)

    def test_delete_trade_soft_voids_record_and_excludes_it_from_active_trade_list(self) -> None:
        account_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Main", "broker": "Demo", "market": "cn", "base_currency": "CNY"},
        )
        self.assertEqual(account_resp.status_code, 200)
        account_id = account_resp.json()["id"]
        trade_resp = self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "600519",
                "trade_date": "2026-01-02",
                "side": "buy",
                "quantity": 1,
                "price": 100,
                "market": "cn",
                "currency": "CNY",
            },
        )
        self.assertEqual(trade_resp.status_code, 200)
        trade_id = trade_resp.json()["id"]

        delete_resp = self.client.delete(f"/api/v1/portfolio/trades/{trade_id}")
        self.assertEqual(delete_resp.status_code, 200)
        self.assertEqual(delete_resp.json()["deleted"], 1)
        self.assertEqual(delete_resp.json()["delete_mode"], "soft")

        trade_list_resp = self.client.get("/api/v1/portfolio/trades", params={"account_id": account_id})
        self.assertEqual(trade_list_resp.status_code, 200)
        self.assertEqual(trade_list_resp.json()["items"], [])

        trade_list_all_resp = self.client.get(
            "/api/v1/portfolio/trades",
            params={"account_id": account_id, "include_voided": True},
        )
        self.assertEqual(trade_list_all_resp.status_code, 200)
        self.assertEqual(len(trade_list_all_resp.json()["items"]), 1)
        self.assertFalse(trade_list_all_resp.json()["items"][0]["is_active"])
        self.assertIsNotNone(trade_list_all_resp.json()["items"][0]["voided_at"])

    def test_create_cash_ledger_busy_returns_409(self) -> None:
        with patch(
            "api.v1.endpoints.portfolio.PortfolioService.record_cash_ledger",
            side_effect=PortfolioBusyError("Portfolio ledger is busy; please retry shortly."),
        ):
            resp = self.client.post(
                "/api/v1/portfolio/cash-ledger",
                json={
                    "account_id": 1,
                    "event_date": "2026-01-02",
                    "direction": "in",
                    "amount": 1000,
                    "currency": "CNY",
                },
            )

        self.assertEqual(resp.status_code, 409)
        detail = resp.json()
        self.assertEqual(detail.get("error"), "portfolio_busy")

    def test_delete_cash_ledger_busy_returns_409(self) -> None:
        with patch(
            "api.v1.endpoints.portfolio.PortfolioService.delete_cash_ledger_event",
            side_effect=PortfolioBusyError("Portfolio ledger is busy; please retry shortly."),
        ):
            resp = self.client.delete("/api/v1/portfolio/cash-ledger/1")

        self.assertEqual(resp.status_code, 409)
        detail = resp.json()
        self.assertEqual(detail.get("error"), "portfolio_busy")

    def test_create_corporate_action_busy_returns_409(self) -> None:
        with patch(
            "api.v1.endpoints.portfolio.PortfolioService.record_corporate_action",
            side_effect=PortfolioBusyError("Portfolio ledger is busy; please retry shortly."),
        ):
            resp = self.client.post(
                "/api/v1/portfolio/corporate-actions",
                json={
                    "account_id": 1,
                    "symbol": "600519",
                    "effective_date": "2026-01-02",
                    "action_type": "split_adjustment",
                    "market": "cn",
                    "currency": "CNY",
                    "split_ratio": 2.0,
                },
            )

        self.assertEqual(resp.status_code, 409)
        detail = resp.json()
        self.assertEqual(detail.get("error"), "portfolio_busy")

    def test_delete_corporate_action_busy_returns_409(self) -> None:
        with patch(
            "api.v1.endpoints.portfolio.PortfolioService.delete_corporate_action_event",
            side_effect=PortfolioBusyError("Portfolio ledger is busy; please retry shortly."),
        ):
            resp = self.client.delete("/api/v1/portfolio/corporate-actions/1")

        self.assertEqual(resp.status_code, 409)
        detail = resp.json()
        self.assertEqual(detail.get("error"), "portfolio_busy")

    def test_csv_broker_list_endpoint(self) -> None:
        resp = self.client.get("/api/v1/portfolio/imports/csv/brokers")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        brokers = {item["broker"] for item in payload["brokers"]}
        self.assertIn("huatai", brokers)
        self.assertIn("citic", brokers)
        self.assertIn("cmb", brokers)

    def test_event_list_invalid_page_size_returns_422(self) -> None:
        resp = self.client.get("/api/v1/portfolio/trades", params={"page_size": 101})
        self.assertEqual(resp.status_code, 422)


if __name__ == "__main__":
    unittest.main()
