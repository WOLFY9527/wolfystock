# -*- coding: utf-8 -*-
"""Portfolio owner-isolation smoke coverage for public safety."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.app import create_app
from src.config import Config
from src.storage import (
    DatabaseManager,
    PortfolioAccount,
    PortfolioBrokerConnection,
    PortfolioCashLedger,
    PortfolioCorporateAction,
    PortfolioTrade,
)


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


class PortfolioOwnerIsolationApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "portfolio_owner_isolation.db"
        self.env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=600519",
                    "GEMINI_API_KEY=test",
                    "ADMIN_AUTH_ENABLED=true",
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

        self.app = create_app(static_dir=self.data_dir / "empty-static")
        self.admin_client = TestClient(self.app)
        self.alice_client = TestClient(self.app)
        self.bob_client = TestClient(self.app)
        self.db = DatabaseManager.get_instance()

        self._login_admin()
        self.alice_id = self._login_user(self.alice_client, "alice", "Alice")
        self.bob_id = self._login_user(self.bob_client, "bob", "Bob")

    def tearDown(self) -> None:
        self.admin_client.close()
        self.alice_client.close()
        self.bob_client.close()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def _login_admin(self) -> None:
        response = self.admin_client.post(
            "/api/v1/auth/login",
            json={"password": "admin-pass-123", "passwordConfirm": "admin-pass-123"},
        )
        self.assertEqual(response.status_code, 200)

    def _login_user(self, client: TestClient, username: str, display_name: str) -> str:
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": username,
                "displayName": display_name,
                "createUser": True,
                "password": "secret123",
                "passwordConfirm": "secret123",
            },
        )
        self.assertEqual(response.status_code, 200)
        row = self.db.get_app_user_by_username(username)
        self.assertIsNotNone(row)
        return str(row.id)

    @staticmethod
    def _json_text(response) -> str:
        return json.dumps(response.json(), ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _ibkr_flex_xml_bytes(symbol: str, exec_id: str, deposit: str = "5000") -> bytes:
        xml_text = f"""<?xml version="1.0" encoding="UTF-8"?>
<FlexStatements>
  <FlexStatement accountId="U1234567" fromDate="2026-01-01" toDate="2026-01-31" currency="USD">
    <Trades>
      <Trade assetCategory="STK" symbol="{symbol}" exchange="NASDAQ" currency="USD" tradeDate="2026-01-03" buySell="BUY" quantity="10" tradePrice="150" ibCommission="1.25" taxes="0" ibExecID="{exec_id}" description="{symbol} BUY"/>
    </Trades>
    <CashTransactions>
      <CashTransaction reportDate="2026-01-02" currency="USD" amount="{deposit}" description="Deposit"/>
    </CashTransactions>
  </FlexStatement>
</FlexStatements>
"""
        return xml_text.encode("utf-8")

    def _portfolio_counts(self) -> dict[str, int]:
        with self.db.get_session() as session:
            return {
                "accounts": session.query(PortfolioAccount).count(),
                "connections": session.query(PortfolioBrokerConnection).count(),
                "trades": session.query(PortfolioTrade).count(),
                "cash": session.query(PortfolioCashLedger).count(),
                "actions": session.query(PortfolioCorporateAction).count(),
            }

    def _assert_public_export_safe_text(self, text: str) -> None:
        forbidden = [
            "ALICE_SECRET_API_KEY",
            "ALICE_SECRET_TOKEN",
            "ALICE_SESSION_TOKEN",
            "ALICE_RAW_INTERNAL_SECRET",
            "BOB_SECRET_API_KEY",
            "BOB_SECRET_TOKEN",
            "BOB_SESSION_TOKEN",
            "broker_credentials",
            "brokerOrderPayload",
            "execute_order",
            "order_payload",
            "payload_json",
            "place_order",
            "raw_provider_payload",
            "submit_order",
            "sync_metadata_json",
        ]
        for needle in forbidden:
            self.assertNotIn(needle, text)

    def _create_account(self, client: TestClient, name: str) -> int:
        response = client.post(
            "/api/v1/portfolio/accounts",
            json={"name": name, "broker": "Demo", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(response.status_code, 200)
        return int(response.json()["id"])

    def _seed_activity(self, client: TestClient, account_id: int, symbol: str, trade_uid: str) -> int:
        cash = client.post(
            "/api/v1/portfolio/cash-ledger",
            json={
                "account_id": account_id,
                "event_date": "2026-01-01",
                "direction": "in",
                "amount": 10000,
                "currency": "USD",
            },
        )
        self.assertEqual(cash.status_code, 200)
        trade = client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": symbol,
                "trade_date": "2026-01-02",
                "side": "buy",
                "quantity": 10,
                "price": 100,
                "fee": 0,
                "tax": 0,
                "market": "us",
                "currency": "USD",
                "trade_uid": trade_uid,
            },
        )
        self.assertEqual(trade.status_code, 200)
        action = client.post(
            "/api/v1/portfolio/corporate-actions",
            json={
                "account_id": account_id,
                "symbol": symbol,
                "effective_date": "2026-01-03",
                "action_type": "cash_dividend",
                "market": "us",
                "currency": "USD",
                "cash_dividend_per_share": 0.1,
            },
        )
        self.assertEqual(action.status_code, 200)
        return int(trade.json()["id"])

    def test_user_read_paths_are_owner_scoped_and_read_only(self) -> None:
        alice_account = self._create_account(self.alice_client, "Alice Main")
        bob_account = self._create_account(self.bob_client, "Bob Main")
        alice_trade_id = self._seed_activity(self.alice_client, alice_account, "AAPL", "alice-trade-1")
        bob_trade_id = self._seed_activity(self.bob_client, bob_account, "MSFT", "bob-trade-1")
        bob_connection = self.bob_client.post(
            "/api/v1/portfolio/broker-connections",
            json={
                "portfolio_account_id": bob_account,
                "broker_type": "ibkr",
                "broker_name": "Interactive Brokers",
                "connection_name": "Bob IBKR",
                "broker_account_ref": "BOB-ACCOUNT-REF",
                "import_mode": "file",
                "status": "active",
                "sync_metadata": {"source": "flex"},
            },
        )
        self.assertEqual(bob_connection.status_code, 200)
        before = self._portfolio_counts()

        accounts = self.alice_client.get("/api/v1/portfolio/accounts")
        trades = self.alice_client.get("/api/v1/portfolio/trades", params={"page_size": 100})
        cash = self.alice_client.get("/api/v1/portfolio/cash-ledger", params={"page_size": 100})
        actions = self.alice_client.get("/api/v1/portfolio/corporate-actions", params={"page_size": 100})
        snapshot = self.alice_client.get("/api/v1/portfolio/snapshot", params={"as_of": "2026-01-03"})
        broker_connections = self.alice_client.get("/api/v1/portfolio/broker-connections")

        for response in (accounts, trades, cash, actions, snapshot, broker_connections):
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("MSFT", self._json_text(response))
            self.assertNotIn("BOB-ACCOUNT-REF", self._json_text(response))

        self.assertEqual([item["id"] for item in accounts.json()["accounts"]], [alice_account])
        self.assertEqual([item["id"] for item in trades.json()["items"]], [alice_trade_id])
        self.assertTrue(all(item["account_id"] == alice_account for item in cash.json()["items"]))
        self.assertTrue(all(item["account_id"] == alice_account for item in actions.json()["items"]))
        self.assertEqual(snapshot.json()["account_count"], 1)
        self.assertEqual(snapshot.json()["accounts"][0]["account_id"], alice_account)
        self.assertEqual(broker_connections.json()["connections"], [])
        self.assertEqual(self._portfolio_counts(), before)

        cross_owner_reads = [
            self.alice_client.get("/api/v1/portfolio/trades", params={"account_id": bob_account}),
            self.alice_client.get("/api/v1/portfolio/cash-ledger", params={"account_id": bob_account}),
            self.alice_client.get("/api/v1/portfolio/corporate-actions", params={"account_id": bob_account}),
            self.alice_client.get("/api/v1/portfolio/snapshot", params={"account_id": bob_account}),
            self.alice_client.get("/api/v1/portfolio/risk", params={"account_id": bob_account}),
            self.alice_client.delete(f"/api/v1/portfolio/trades/{bob_trade_id}"),
            self.alice_client.put(
                f"/api/v1/portfolio/broker-connections/{bob_connection.json()['id']}",
                json={"connection_name": "stolen"},
            ),
        ]
        for response in cross_owner_reads:
            self.assertIn(response.status_code, {400, 404})
            self.assertNotIn("MSFT", self._json_text(response))
            self.assertNotIn("BOB-ACCOUNT-REF", self._json_text(response))
        self.assertEqual(self._portfolio_counts(), before)

    def test_export_like_portfolio_reads_do_not_cross_owner_boundaries(self) -> None:
        alice_account = self._create_account(self.alice_client, "Alice Export")
        bob_account = self._create_account(self.bob_client, "Bob Export")
        self._seed_activity(self.alice_client, alice_account, "AAPL", "alice-export-trade")
        self._seed_activity(self.bob_client, bob_account, "MSFT", "bob-export-trade")
        alice_connection = self.alice_client.post(
            "/api/v1/portfolio/broker-connections",
            json={
                "portfolio_account_id": alice_account,
                "broker_type": "ibkr",
                "broker_name": "Interactive Brokers",
                "connection_name": "Alice IBKR",
                "broker_account_ref": "ALICE-ACCOUNT-REF",
                "import_mode": "api",
                "status": "active",
                "sync_metadata": {
                    "source": "flex",
                    "api_key": "ALICE_SECRET_API_KEY",
                    "nested": {
                        "token": "ALICE_SECRET_TOKEN",
                        "session_token": "ALICE_SESSION_TOKEN",
                        "secret": "ALICE_RAW_INTERNAL_SECRET",
                    },
                },
            },
        )
        self.assertEqual(alice_connection.status_code, 200)
        bob_connection = self.bob_client.post(
            "/api/v1/portfolio/broker-connections",
            json={
                "portfolio_account_id": bob_account,
                "broker_type": "ibkr",
                "broker_name": "Interactive Brokers",
                "connection_name": "Bob IBKR",
                "broker_account_ref": "BOB-ACCOUNT-REF",
                "import_mode": "api",
                "status": "active",
                "sync_metadata": {
                    "api_key": "BOB_SECRET_API_KEY",
                    "nested": {"token": "BOB_SECRET_TOKEN", "session_token": "BOB_SESSION_TOKEN"},
                },
            },
        )
        self.assertEqual(bob_connection.status_code, 200)
        before = self._portfolio_counts()

        export_reads = [
            self.alice_client.get("/api/v1/portfolio/accounts", params={"include_inactive": True}),
            self.alice_client.get("/api/v1/portfolio/trades", params={"page_size": 100}),
            self.alice_client.get("/api/v1/portfolio/cash-ledger", params={"page_size": 100}),
            self.alice_client.get("/api/v1/portfolio/corporate-actions", params={"page_size": 100}),
            self.alice_client.get("/api/v1/portfolio/snapshot", params={"as_of": "2026-01-03"}),
            self.alice_client.get("/api/v1/portfolio/broker-connections"),
        ]

        for response in export_reads:
            self.assertEqual(response.status_code, 200)
            text = self._json_text(response)
            self.assertNotIn("MSFT", text)
            self.assertNotIn("bob-export-trade", text)
            self.assertNotIn("BOB-ACCOUNT-REF", text)
            self.assertNotIn("ALICE_RAW_INTERNAL_SECRET", text)
            self._assert_public_export_safe_text(text)

        rejected_exports = [
            self.alice_client.get("/api/v1/portfolio/trades", params={"account_id": bob_account, "page_size": 100}),
            self.alice_client.get("/api/v1/portfolio/cash-ledger", params={"account_id": bob_account, "page_size": 100}),
            self.alice_client.get("/api/v1/portfolio/corporate-actions", params={"account_id": bob_account, "page_size": 100}),
            self.alice_client.get("/api/v1/portfolio/snapshot", params={"account_id": bob_account, "as_of": "2026-01-03"}),
            self.alice_client.get("/api/v1/portfolio/risk", params={"account_id": bob_account, "as_of": "2026-01-03"}),
            self.alice_client.put(
                f"/api/v1/portfolio/broker-connections/{bob_connection.json()['id']}",
                json={"connection_name": "stolen export"},
            ),
        ]
        for response in rejected_exports:
            self.assertIn(response.status_code, {400, 404})
            text = self._json_text(response)
            self.assertNotIn("MSFT", text)
            self.assertNotIn("bob-export-trade", text)
            self.assertNotIn("BOB-ACCOUNT-REF", text)
            self._assert_public_export_safe_text(text)
        self.assertEqual(self._portfolio_counts(), before)

    def test_import_idempotency_stays_with_authenticated_owner(self) -> None:
        alice_account = self._create_account(self.alice_client, "Alice Import")
        bob_account = self._create_account(self.bob_client, "Bob Import")

        rejected = self.alice_client.post(
            "/api/v1/portfolio/imports/commit",
            data={"account_id": str(bob_account), "broker": "ibkr", "dry_run": "false"},
            files={"file": ("ibkr-flex.xml", self._ibkr_flex_xml_bytes("MSFT", "BOB-EXEC-1"), "application/xml")},
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertNotIn("MSFT", self._json_text(rejected))

        first = self.bob_client.post(
            "/api/v1/portfolio/imports/commit",
            data={"account_id": str(bob_account), "broker": "ibkr", "dry_run": "false"},
            files={"file": ("ibkr-flex.xml", self._ibkr_flex_xml_bytes("MSFT", "BOB-EXEC-1"), "application/xml")},
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["account_id"], bob_account)
        self.assertEqual(first.json()["inserted_count"], 1)
        self.assertEqual(first.json()["cash_inserted_count"], 1)

        second = self.bob_client.post(
            "/api/v1/portfolio/imports/commit",
            data={"account_id": str(bob_account), "broker": "ibkr", "dry_run": "false"},
            files={"file": ("ibkr-flex.xml", self._ibkr_flex_xml_bytes("MSFT", "BOB-EXEC-1"), "application/xml")},
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["account_id"], bob_account)
        self.assertEqual(second.json()["inserted_count"], 0)

        alice_trades = self.alice_client.get("/api/v1/portfolio/trades", params={"account_id": alice_account})
        bob_trades = self.bob_client.get("/api/v1/portfolio/trades", params={"account_id": bob_account})
        self.assertEqual(alice_trades.status_code, 200)
        self.assertEqual(bob_trades.status_code, 200)
        self.assertEqual(alice_trades.json()["total"], 0)
        self.assertEqual(bob_trades.json()["total"], 1)
        self.assertNotIn("MSFT", self._json_text(alice_trades))


if __name__ == "__main__":
    unittest.main()
