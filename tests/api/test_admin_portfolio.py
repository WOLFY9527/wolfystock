# -*- coding: utf-8 -*-
"""Admin portfolio visibility API contract tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID
from src.storage import (
    AppUser,
    DatabaseManager,
    ExecutionLogSession,
    PortfolioAccount,
    PortfolioBrokerConnection,
    PortfolioBrokerSyncCashBalance,
    PortfolioBrokerSyncPosition,
    PortfolioBrokerSyncState,
    PortfolioCashLedger,
    PortfolioCorporateAction,
    PortfolioDailySnapshot,
    PortfolioPosition,
    PortfolioTrade,
)


def _admin_user() -> CurrentUser:
    return CurrentUser(
        user_id=BOOTSTRAP_ADMIN_USER_ID,
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id="admin-session-raw",
    )


def _regular_user() -> CurrentUser:
    return CurrentUser(
        user_id="user-1",
        username="alice",
        display_name="Alice",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id="user-session-raw",
    )


class AdminPortfolioApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "admin_portfolio.db"
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")

        from api.v1.endpoints import admin_portfolio

        self.app = FastAPI()
        self.app.include_router(admin_portfolio.router, prefix="/api/v1/admin")
        self.client = TestClient(self.app)
        self.now = datetime.now()
        self._seed_data()

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        DatabaseManager.reset_instance()
        self.temp_dir.cleanup()

    def _seed_data(self) -> None:
        self.db.create_or_update_app_user(
            user_id=BOOTSTRAP_ADMIN_USER_ID,
            username="admin",
            display_name="Admin",
            role="admin",
            password_hash="pbkdf2:admin-secret-hash",
            is_active=True,
        )
        self.db.create_or_update_app_user(
            user_id="user-1",
            username="alice",
            display_name="Alice Analyst",
            role="user",
            password_hash="pbkdf2:user-secret-hash",
            is_active=True,
        )
        self.db.create_or_update_app_user(
            user_id="user-2",
            username="bob",
            display_name="Bob Other",
            role="user",
            password_hash="pbkdf2:other-secret-hash",
            is_active=True,
        )
        with self.db.get_session() as session:
            account_a = PortfolioAccount(
                owner_id="user-1",
                name="Alice Main",
                broker="IBKR",
                market="us",
                base_currency="USD",
                is_active=True,
                created_at=self.now - timedelta(days=5),
                updated_at=self.now - timedelta(days=1),
            )
            account_b = PortfolioAccount(
                owner_id="user-2",
                name="Bob Main",
                broker="IBKR",
                market="us",
                base_currency="USD",
                is_active=True,
            )
            session.add_all([account_a, account_b])
            session.flush()
            self.account_a_id = int(account_a.id)
            self.account_b_id = int(account_b.id)

            connection_a = PortfolioBrokerConnection(
                owner_id="user-1",
                portfolio_account_id=self.account_a_id,
                broker_type="ibkr",
                broker_name="Interactive Brokers",
                connection_name="Alice IBKR",
                broker_account_ref="RAW-BROKER-SECRET-ACCOUNT-123456",
                import_mode="api",
                status="active",
                last_imported_at=self.now - timedelta(days=2),
                last_import_source="ibkr_flex_xml",
                last_import_fingerprint="raw-import-fingerprint-secret",
                sync_metadata_json='{"api_key": "SECRET_API_KEY", "raw": {"token": "SECRET_TOKEN"}}',
                created_at=self.now - timedelta(days=5),
                updated_at=self.now - timedelta(days=1),
            )
            connection_b = PortfolioBrokerConnection(
                owner_id="user-2",
                portfolio_account_id=self.account_b_id,
                broker_type="ibkr",
                broker_name="Interactive Brokers",
                connection_name="Bob IBKR",
                broker_account_ref="BOB-RAW-BROKER-ACCOUNT",
                import_mode="api",
                status="active",
            )
            session.add_all([connection_a, connection_b])
            session.flush()
            self.connection_a_id = int(connection_a.id)
            self.connection_b_id = int(connection_b.id)

            session.add_all(
                [
                    PortfolioBrokerSyncState(
                        owner_id="user-1",
                        broker_connection_id=self.connection_a_id,
                        portfolio_account_id=self.account_a_id,
                        broker_type="ibkr",
                        broker_account_ref="RAW-BROKER-SECRET-ACCOUNT-123456",
                        sync_source="api",
                        sync_status="success",
                        snapshot_date=date(2026, 5, 5),
                        synced_at=self.now - timedelta(hours=3),
                        base_currency="USD",
                        total_cash=1000.0,
                        total_market_value=2500.0,
                        total_equity=3500.0,
                        realized_pnl=120.0,
                        unrealized_pnl=300.0,
                        fx_stale=False,
                        payload_json='{"token": "SECRET_TOKEN", "positions": [{"raw": true}]}',
                    ),
                    PortfolioBrokerSyncState(
                        owner_id="user-2",
                        broker_connection_id=self.connection_b_id,
                        portfolio_account_id=self.account_b_id,
                        broker_type="ibkr",
                        broker_account_ref="BOB-RAW-BROKER-ACCOUNT",
                        sync_source="api",
                        sync_status="success",
                        snapshot_date=date(2026, 5, 5),
                        synced_at=self.now - timedelta(hours=2),
                        base_currency="USD",
                        total_cash=9999.0,
                        total_market_value=9999.0,
                        total_equity=19998.0,
                        realized_pnl=0.0,
                        unrealized_pnl=0.0,
                        fx_stale=False,
                        payload_json='{"token": "BOB_SECRET_TOKEN"}',
                    ),
                    PortfolioBrokerSyncPosition(
                        owner_id="user-1",
                        broker_connection_id=self.connection_a_id,
                        portfolio_account_id=self.account_a_id,
                        broker_position_ref="RAW-POSITION-SECRET",
                        symbol="AAPL",
                        market="us",
                        currency="USD",
                        quantity=10.0,
                        avg_cost=150.0,
                        last_price=180.0,
                        market_value_base=1800.0,
                        unrealized_pnl_base=300.0,
                        valuation_currency="USD",
                        payload_json='{"secret": "POSITION_SECRET"}',
                    ),
                    PortfolioBrokerSyncPosition(
                        owner_id="user-2",
                        broker_connection_id=self.connection_b_id,
                        portfolio_account_id=self.account_b_id,
                        broker_position_ref="BOB-POSITION-SECRET",
                        symbol="MSFT",
                        market="us",
                        currency="USD",
                        quantity=99.0,
                        avg_cost=1.0,
                        last_price=2.0,
                        market_value_base=198.0,
                        unrealized_pnl_base=99.0,
                        valuation_currency="USD",
                        payload_json='{"secret": "BOB_POSITION_SECRET"}',
                    ),
                    PortfolioBrokerSyncCashBalance(
                        owner_id="user-1",
                        broker_connection_id=self.connection_a_id,
                        portfolio_account_id=self.account_a_id,
                        currency="USD",
                        amount=1000.0,
                        amount_base=1000.0,
                    ),
                    PortfolioTrade(
                        account_id=self.account_a_id,
                        trade_uid="alice-trade-secret-uid",
                        symbol="AAPL",
                        market="us",
                        currency="USD",
                        trade_date=date(2026, 5, 1),
                        side="buy",
                        quantity=10.0,
                        price=150.0,
                        fee=1.0,
                        tax=0.0,
                        note="raw note with SECRET_TOKEN",
                        dedup_hash="raw-dedup-secret",
                        is_active=True,
                    ),
                    PortfolioCashLedger(
                        account_id=self.account_a_id,
                        event_date=date(2026, 5, 2),
                        direction="in",
                        amount=1000.0,
                        currency="USD",
                        note="cash secret note",
                    ),
                    PortfolioCorporateAction(
                        account_id=self.account_a_id,
                        symbol="AAPL",
                        market="us",
                        currency="USD",
                        effective_date=date(2026, 5, 3),
                        action_type="cash_dividend",
                        cash_dividend_per_share=0.24,
                        note="corporate secret note",
                    ),
                    PortfolioDailySnapshot(
                        account_id=self.account_a_id,
                        snapshot_date=date(2026, 5, 5),
                        cost_method="fifo",
                        base_currency="USD",
                        total_cash=1000.0,
                        total_market_value=1800.0,
                        total_equity=2800.0,
                        unrealized_pnl=300.0,
                        realized_pnl=120.0,
                        fx_stale=False,
                        payload='{"secret": "SNAPSHOT_SECRET"}',
                    ),
                    PortfolioPosition(
                        account_id=self.account_a_id,
                        cost_method="fifo",
                        symbol="AAPL",
                        market="us",
                        currency="USD",
                        quantity=10.0,
                        avg_cost=150.0,
                        total_cost=1500.0,
                        last_price=180.0,
                        market_value_base=1800.0,
                        unrealized_pnl_base=300.0,
                        valuation_currency="USD",
                    ),
                ]
            )
            session.commit()

    def _as_admin(self) -> None:
        self.app.dependency_overrides[get_current_user] = _admin_user

    def _as_user(self) -> None:
        self.app.dependency_overrides[get_current_user] = _regular_user

    @staticmethod
    def _json_text(response) -> str:
        return json.dumps(response.json(), ensure_ascii=False, sort_keys=True)

    def _count(self, model) -> int:
        from sqlalchemy import func, select

        with self.db.get_session() as session:
            return int(session.execute(select(func.count()).select_from(model)).scalar() or 0)

    def _portfolio_counts(self) -> dict[str, int]:
        return {
            "accounts": self._count(PortfolioAccount),
            "connections": self._count(PortfolioBrokerConnection),
            "states": self._count(PortfolioBrokerSyncState),
            "positions": self._count(PortfolioBrokerSyncPosition),
            "cash": self._count(PortfolioCashLedger),
            "trades": self._count(PortfolioTrade),
            "actions": self._count(PortfolioCorporateAction),
        }

    def _assert_safe_json(self, response) -> None:
        text = self._json_text(response)
        forbidden = [
            "RAW-BROKER-SECRET-ACCOUNT-123456",
            "RAW-POSITION-SECRET",
            "raw-import-fingerprint-secret",
            "raw-dedup-secret",
            "alice-trade-secret-uid",
            "SECRET_TOKEN",
            "SECRET_API_KEY",
            "POSITION_SECRET",
            "SNAPSHOT_SECRET",
            "sync_metadata_json",
            "payload_json",
            "payloadJson",
            "password_hash",
            "admin-session-raw",
            "user-session-raw",
        ]
        for needle in forbidden:
            self.assertNotIn(needle, text)

    def _assert_audit_event(self, action: str) -> None:
        with self.db.get_session() as session:
            rows = (
                session.query(ExecutionLogSession)
                .filter(ExecutionLogSession.task_id == action)
                .all()
            )
        self.assertEqual(len(rows), 1)
        text = json.dumps(rows[0].summary_json, ensure_ascii=False)
        self.assertIn("user-1", text)
        self.assertIn("admin", text)
        self.assertNotIn("SECRET_TOKEN", text)
        self.assertNotIn("RAW-BROKER-SECRET-ACCOUNT-123456", text)
        self.assertNotIn("sync_metadata_json", text)
        self.assertNotIn("payload_json", text)

    def test_admin_required_for_portfolio_visibility(self) -> None:
        unauthenticated = self.client.get("/api/v1/admin/users/user-1/portfolio-summary")
        self.assertEqual(unauthenticated.status_code, 401)

        self._as_user()
        forbidden = self.client.get("/api/v1/admin/users/user-1/portfolio-summary")
        self.assertEqual(forbidden.status_code, 403)

    def test_missing_target_user_returns_404(self) -> None:
        self._as_admin()
        response = self.client.get("/api/v1/admin/users/missing-user/portfolio-summary")
        self.assertEqual(response.status_code, 404)

    def test_portfolio_summary_returns_target_user_safe_aggregates_and_audit(self) -> None:
        self._as_admin()
        before = self._portfolio_counts()

        response = self.client.get("/api/v1/admin/users/user-1/portfolio-summary")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["userId"], "user-1")
        self.assertEqual(payload["accountCount"], 1)
        self.assertEqual(payload["activeAccountCount"], 1)
        self.assertEqual(payload["ledgerCounts"], {"trades": 1, "cashEvents": 1, "corporateActions": 1})
        self.assertEqual(payload["brokerSyncSummary"]["connections"], 1)
        self.assertEqual(payload["brokerSyncSummary"]["statuses"], {"success": 1})
        self.assertEqual(payload["totalEquity"]["amount"], 3500.0)
        self.assertEqual(self._portfolio_counts(), before)
        self._assert_safe_json(response)
        self._assert_audit_event("admin_portfolio.summary_viewed")

    def test_holdings_are_target_user_only_and_safe(self) -> None:
        self._as_admin()
        response = self.client.get("/api/v1/admin/users/user-1/holdings", params={"limit": 200})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["symbol"], "AAPL")
        self.assertEqual(payload["items"][0]["accountId"], self.account_a_id)
        self.assertNotIn("MSFT", self._json_text(response))
        self.assertRegex(payload["items"][0]["brokerAccountHandle"], r"^acct_[a-f0-9]{12}$")
        self._assert_safe_json(response)
        self._assert_audit_event("admin_portfolio.holdings_viewed")

    def test_account_detail_validates_account_owner_and_excludes_raw_payloads(self) -> None:
        self._as_admin()
        wrong_account = self.client.get(f"/api/v1/admin/users/user-1/portfolio/accounts/{self.account_b_id}")
        self.assertEqual(wrong_account.status_code, 404)

        response = self.client.get(f"/api/v1/admin/users/user-1/portfolio/accounts/{self.account_a_id}")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["userId"], "user-1")
        self.assertEqual(payload["account"]["id"], self.account_a_id)
        self.assertEqual(payload["brokerConnections"][0]["brokerAccountHandle"], payload["account"]["brokerAccountHandle"])
        self.assertEqual(payload["syncState"]["status"], "success")
        self._assert_safe_json(response)
        self._assert_audit_event("admin_portfolio.account_detail_viewed")

    def test_portfolio_activity_returns_safe_rows_and_does_not_trigger_mutations_or_refresh(self) -> None:
        self._as_admin()
        before = self._portfolio_counts()

        with patch("src.services.portfolio_ibkr_sync_service.PortfolioIbkrSyncService.sync_read_only_account_state", side_effect=AssertionError("sync called")), patch(
            "src.services.portfolio_import_service.PortfolioImportService.commit_import_records",
            side_effect=AssertionError("import commit called"),
        ), patch("src.services.fx_rate_service.FxRateService.fetch_rate", side_effect=AssertionError("fx refresh called")):
            response = self.client.get("/api/v1/admin/users/user-1/portfolio-activity", params={"limit": 200})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 3)
        self.assertEqual(payload["summary"], {"trades": 1, "cashEvents": 1, "corporateActions": 1})
        self.assertEqual({item["type"] for item in payload["items"]}, {"trade", "cash", "corporate_action"})
        self.assertEqual(self._portfolio_counts(), before)
        self._assert_safe_json(response)
        self._assert_audit_event("admin_portfolio.activity_viewed")


if __name__ == "__main__":
    unittest.main()
