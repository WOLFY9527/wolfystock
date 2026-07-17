# -*- coding: utf-8 -*-
"""PR2 tests for portfolio CSV import, risk thresholds and FX stale fallback."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
from fastapi.testclient import TestClient

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.app import create_app
from api.deps import CurrentUser, get_current_user
from src.config import Config
from src.runtime.settings import PortfolioImportLimits
from src.services.portfolio_import_service import (
    PortfolioImportService,
    PortfolioImportUnavailableError,
)
from src.services.portfolio_risk_service import PortfolioRiskService
from src.services.portfolio_service import PortfolioBusyError, PortfolioOversellError, PortfolioService
from src.storage import DatabaseManager, PortfolioImportOperation


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


def _make_pr2_consumer_user() -> CurrentUser:
    return CurrentUser(
        user_id="portfolio-pr2-consumer",
        username="portfolio-pr2-consumer",
        display_name="Portfolio PR2 Consumer",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id="portfolio-pr2-session",
    )


class PortfolioPr2TestCase(unittest.TestCase):
    """End-to-end style tests for PR2 import, dedup, risk and fx behavior."""

    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        data_dir = Path(self.temp_dir.name)
        self.env_path = data_dir / ".env"
        self.db_path = data_dir / "portfolio_pr2_test.db"
        self._previous_admin_auth_enabled = os.environ.get("ADMIN_AUTH_ENABLED")
        self.env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=600519",
                    "GEMINI_API_KEY=test",
                    "ADMIN_AUTH_ENABLED=false",
                    "PORTFOLIO_RISK_CONCENTRATION_ALERT_PCT=70.0",
                    "PORTFOLIO_RISK_DRAWDOWN_ALERT_PCT=10.0",
                    "PORTFOLIO_RISK_STOP_LOSS_ALERT_PCT=25.0",
                    "PORTFOLIO_RISK_STOP_LOSS_NEAR_RATIO=0.8",
                    "PORTFOLIO_RISK_LOOKBACK_DAYS=365",
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
        self.db.create_or_update_app_user(
            user_id="portfolio-pr2-consumer",
            username="portfolio-pr2-consumer",
            display_name="Portfolio PR2 Consumer",
            role="user",
            password_hash="pbkdf2:portfolio-pr2-consumer",
            is_active=True,
        )
        self.service = PortfolioService(owner_id="portfolio-pr2-consumer")
        self.import_service = PortfolioImportService(portfolio_service=self.service)
        self.risk_service = PortfolioRiskService(portfolio_service=self.service)
        self._board_fetch_patcher = patch.object(PortfolioRiskService, "_fetch_belong_boards", return_value=[])
        self._board_fetch_patcher.start()
        self.app = create_app(static_dir=data_dir / "empty-static")
        self.app.dependency_overrides[get_current_user] = _make_pr2_consumer_user
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        if self._previous_admin_auth_enabled is None:
            os.environ.pop("ADMIN_AUTH_ENABLED", None)
        else:
            os.environ["ADMIN_AUTH_ENABLED"] = self._previous_admin_auth_enabled
        _reset_auth_globals()
        self._board_fetch_patcher.stop()
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
        self.db.save_daily_data(df, code=symbol, data_source="portfolio-pr2-test")

    @staticmethod
    def _csv_bytes(with_trade_uid: bool = True) -> bytes:
        if with_trade_uid:
            csv_text = (
                "成交日期,证券代码,买卖标志,成交数量,成交均价,成交编号,手续费,印花税\n"
                "2026-01-02,600519,买入,10,100,HT-001,1,0\n"
            )
        else:
            csv_text = (
                "成交日期,证券代码,买卖标志,成交数量,成交均价,手续费,印花税\n"
                "2026-01-02,600519,买入,10,100,1,0\n"
            )
        return csv_text.encode("utf-8")

    @staticmethod
    def _ibkr_flex_xml_bytes() -> bytes:
        xml_text = """<?xml version="1.0" encoding="UTF-8"?>
<FlexStatements>
  <FlexStatement accountId="U1234567" fromDate="2026-01-01" toDate="2026-01-31" currency="USD">
    <Trades>
      <Trade assetCategory="STK" symbol="AAPL" exchange="NASDAQ" currency="USD" tradeDate="2026-01-03" buySell="BUY" quantity="10" tradePrice="150" ibCommission="1.25" taxes="0" ibExecID="AAPL-1" description="AAPL BUY"/>
      <Trade assetCategory="STK" symbol="HK00700" exchange="SEHK" currency="HKD" tradeDate="2026-01-04" buySell="BUY" quantity="100" tradePrice="320" ibCommission="8.50" taxes="0" ibExecID="TENCENT-1" description="Tencent BUY"/>
    </Trades>
    <CashTransactions>
      <CashTransaction reportDate="2026-01-02" currency="USD" amount="5000" description="Deposit"/>
      <CashTransaction reportDate="2026-01-05" currency="HKD" amount="-25" description="Market data fee"/>
    </CashTransactions>
    <CorporateActions>
      <CorporateAction assetCategory="STK" symbol="AAPL" exchange="NASDAQ" currency="USD" reportDate="2026-01-10" description="2 for 1 split" ratio="2:1"/>
    </CorporateActions>
  </FlexStatement>
</FlexStatements>
"""
        return xml_text.encode("utf-8")

    @staticmethod
    def _ibkr_open_positions_xml_bytes() -> bytes:
        xml_text = """<?xml version="1.0" encoding="UTF-8"?>
<FlexStatements>
  <FlexStatement accountId="U7654321" fromDate="2026-02-01" toDate="2026-02-28" currency="USD">
    <OpenPositions>
      <OpenPosition assetCategory="STK" symbol="MSFT" exchange="NASDAQ" currency="USD" reportDate="2026-02-28" position="12" costBasisPrice="250"/>
    </OpenPositions>
  </FlexStatement>
</FlexStatements>
"""
        return xml_text.encode("utf-8")

    def test_import_dedup_trade_uid_and_hash(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]

        parsed_uid = self.import_service.parse_trade_csv(broker="huatai", content=self._csv_bytes(with_trade_uid=True))
        first_uid = self.import_service.commit_trade_records(
            account_id=aid,
            broker="huatai",
            records=parsed_uid["records"],
        )
        second_uid = self.import_service.commit_trade_records(
            account_id=aid,
            broker="huatai",
            records=parsed_uid["records"],
        )
        self.assertEqual(first_uid["inserted_count"], 1)
        self.assertEqual(second_uid["duplicate_count"], 1)

        parsed_hash = self.import_service.parse_trade_csv(
            broker="huatai",
            content=self._csv_bytes(with_trade_uid=False),
        )
        first_hash = self.import_service.commit_trade_records(
            account_id=aid,
            broker="huatai",
            records=parsed_hash["records"],
        )
        second_hash = self.import_service.commit_trade_records(
            account_id=aid,
            broker="huatai",
            records=parsed_hash["records"],
        )
        self.assertEqual(first_hash["inserted_count"], 0)
        self.assertEqual(first_hash["duplicate_count"], 1)
        self.assertEqual(second_hash["inserted_count"], 0)

    def test_import_side_parser_avoids_false_sell_match(self) -> None:
        csv_text = (
            "成交日期,证券代码,买卖标志,成交数量,成交均价,成交编号\n"
            "2026-01-02,600519,Asset Transfer,10,100,HT-002\n"
        )
        parsed = self.import_service.parse_trade_csv(
            broker="huatai",
            content=csv_text.encode("utf-8"),
        )
        self.assertEqual(parsed["record_count"], 0)

    def test_import_supported_broker_registry(self) -> None:
        items = self.import_service.list_supported_brokers()
        broker_map = {item["broker"]: item for item in items}
        self.assertIn("huatai", broker_map)
        self.assertIn("citic", broker_map)
        self.assertIn("cmb", broker_map)
        self.assertIn("ibkr", broker_map)
        self.assertIn("zhongxin", broker_map["citic"]["aliases"])
        self.assertIn("zhaoshang", broker_map["cmb"]["aliases"])
        self.assertIn("xml", broker_map["ibkr"]["file_extensions"])

    def test_import_preserves_leading_zero_symbol(self) -> None:
        csv_text = (
            "成交日期,证券代码,买卖标志,成交数量,成交均价,成交编号\n"
            "2026-01-02,000001,买入,10,100,HT-003\n"
        )
        parsed = self.import_service.parse_trade_csv(
            broker="huatai",
            content=csv_text.encode("utf-8"),
        )
        self.assertEqual(parsed["record_count"], 1)
        self.assertEqual(parsed["records"][0]["symbol"], "000001")

    def test_import_dry_run_counts_in_file_duplicates(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]
        csv_text = (
            "成交日期,证券代码,买卖标志,成交数量,成交均价,成交编号,手续费,印花税\n"
            "2026-01-02,600519,买入,10,100,HT-004,1,0\n"
            "2026-01-02,600519,买入,10,100,HT-004,1,0\n"
        )
        parsed = self.import_service.parse_trade_csv(
            broker="huatai",
            content=csv_text.encode("utf-8"),
        )
        result = self.import_service.commit_trade_records(
            account_id=aid,
            broker="huatai",
            records=parsed["records"],
            dry_run=True,
        )
        self.assertEqual(result["record_count"], 2)
        self.assertEqual(result["inserted_count"], 1)
        self.assertEqual(result["duplicate_count"], 1)

    def test_import_allows_identical_split_fills_without_trade_uid(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]
        csv_text = (
            "成交日期,证券代码,买卖标志,成交数量,成交均价,手续费,印花税\n"
            "2026-01-02,600519,买入,10,100,1,0\n"
            "2026-01-02,600519,买入,10,100,1,0\n"
        )
        parsed = self.import_service.parse_trade_csv(
            broker="huatai",
            content=csv_text.encode("utf-8"),
        )
        self.assertEqual(parsed["record_count"], 2)
        self.assertEqual(len({item["dedup_hash"] for item in parsed["records"]}), 2)

        first_commit = self.import_service.commit_trade_records(
            account_id=aid,
            broker="huatai",
            records=parsed["records"],
        )
        second_commit = self.import_service.commit_trade_records(
            account_id=aid,
            broker="huatai",
            records=parsed["records"],
        )

        self.assertEqual(first_commit["inserted_count"], 2)
        self.assertEqual(first_commit["duplicate_count"], 0)
        self.assertEqual(second_commit["inserted_count"], 0)
        self.assertEqual(second_commit["duplicate_count"], 2)

    def test_import_oversell_counts_failed_not_duplicate(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=10,
            price=100,
            market="cn",
            currency="CNY",
        )

        with self.assertRaises(PortfolioOversellError):
            self.import_service.commit_trade_records(
                account_id=aid,
                broker="huatai",
                records=[
                    {
                        "trade_date": "2026-01-02",
                        "symbol": "600519",
                        "side": "sell",
                        "quantity": 20,
                        "price": 90,
                        "fee": 0.0,
                        "tax": 0.0,
                        "trade_uid": "HT-SELL-001",
                        "dedup_hash": "oversell-hash-001",
                        "market": "cn",
                        "currency": "CNY",
                    }
                ],
            )

        self.assertEqual(
            self.service.list_trade_events(account_id=aid, page=1, page_size=20)["total"],
            1,
        )

    def test_import_busy_counts_failed_not_duplicate(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]

        with patch.object(
            self.import_service.portfolio_service,
            "_record_trade_in_session",
            side_effect=PortfolioBusyError("Portfolio ledger is busy; please retry shortly."),
        ):
            with self.assertRaises(PortfolioBusyError):
                self.import_service.commit_trade_records(
                    account_id=aid,
                    broker="huatai",
                    records=[
                        {
                            "trade_date": "2026-01-02",
                            "symbol": "600519",
                            "side": "buy",
                            "quantity": 10,
                            "price": 90,
                            "fee": 0.0,
                            "tax": 0.0,
                            "trade_uid": "HT-BUSY-001",
                            "dedup_hash": "busy-hash-001",
                            "market": "cn",
                            "currency": "CNY",
                        }
                    ],
                )

        self.assertEqual(
            self.service.list_trade_events(account_id=aid, page=1, page_size=20)["total"],
            0,
        )

    def test_ibkr_flex_parse_and_commit_with_repeat_import_protection(self) -> None:
        account = self.service.create_account(name="Global", broker="IBKR", market="us", base_currency="USD")
        aid = account["id"]
        self.service.repo.save_fx_rate(
            from_currency="HKD",
            to_currency="USD",
            rate_date=date(2026, 1, 1),
            rate=0.128,
            source="unit-test",
            is_stale=False,
        )

        parsed = self.import_service.parse_import_file(
            broker="ibkr",
            content=self._ibkr_flex_xml_bytes(),
        )
        self.assertEqual(parsed["broker"], "ibkr")
        self.assertEqual(parsed["record_count"], 2)
        self.assertEqual(parsed["cash_record_count"], 2)
        self.assertEqual(parsed["corporate_action_count"], 1)
        self.assertEqual(parsed["metadata"]["broker_account_ref"], "U1234567")

        result = self.import_service.commit_import_records(
            account_id=aid,
            broker="ibkr",
            parsed_payload=parsed,
        )
        self.assertEqual(result["inserted_count"], 2)
        self.assertEqual(result["cash_inserted_count"], 2)
        self.assertEqual(result["corporate_action_inserted_count"], 1)
        self.assertFalse(result["duplicate_import"])
        self.assertIsNotNone(result["broker_connection_id"])

        trades = self.service.list_trade_events(account_id=aid, page=1, page_size=20)
        self.assertEqual(len(trades["items"]), 2)
        self.assertEqual({item["market"] for item in trades["items"]}, {"us", "hk"})

        cash_entries = self.service.list_cash_ledger_events(account_id=aid, page=1, page_size=20)
        self.assertEqual(len(cash_entries["items"]), 2)
        self.assertEqual({item["currency"] for item in cash_entries["items"]}, {"USD", "HKD"})

        actions = self.service.list_corporate_action_events(account_id=aid, page=1, page_size=20)
        self.assertEqual(len(actions["items"]), 1)
        self.assertEqual(actions["items"][0]["action_type"], "split_adjustment")

        account_after_import = self.service.get_account(aid, include_inactive=True)
        self.assertIsNotNone(account_after_import)
        self.assertEqual(account_after_import["market"], "global")

        connections = self.service.list_broker_connections(portfolio_account_id=aid)
        self.assertEqual(len(connections), 1)
        self.assertEqual(connections[0]["broker_account_ref"], "U1234567")
        self.assertEqual(
            connections[0]["last_import_fingerprint"],
            parsed["metadata"]["file_fingerprint"],
        )

        repeat = self.import_service.commit_import_records(
            account_id=aid,
            broker="ibkr",
            parsed_payload=parsed,
        )
        self.assertTrue(repeat["duplicate_import"])
        self.assertEqual(repeat["inserted_count"], 0)
        self.assertEqual(repeat["cash_inserted_count"], 0)

    def test_ibkr_flex_preview_classifies_statement_and_record_currency_issues(self) -> None:
        account = self.service.create_account(name="Currency Preview", broker="IBKR", market="us", base_currency="USD")
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<FlexStatements><FlexStatement accountId="U-CURRENCY">
  <Trades>
    <Trade assetCategory="STK" symbol="AAPL" exchange="NASDAQ" tradeDate="2026-01-03" buySell="BUY" quantity="1" tradePrice="10" ibExecID="MISSING"/>
    <Trade assetCategory="STK" symbol="MSFT" exchange="NASDAQ" currency="EUR" tradeDate="2026-01-04" buySell="BUY" quantity="1" tradePrice="20" ibExecID="NO-FX"/>
  </Trades>
  <CashTransactions><CashTransaction reportDate="2026-01-05" currency="US D" amount="5" description="Malformed"/></CashTransactions>
  <CorporateActions><CorporateAction assetCategory="STK" symbol="AAPL" exchange="NASDAQ" currency="XYZ" reportDate="2026-01-06" description="2 for 1 split" ratio="2:1"/></CorporateActions>
  <OpenPositions><OpenPosition assetCategory="STK" symbol="GOOG" exchange="NASDAQ" reportDate="2026-01-31" position="1" costBasisPrice="30"/></OpenPositions>
</FlexStatement></FlexStatements>"""

        parsed = self.import_service.parse_import_file(broker="ibkr", content=xml)
        preview = self.import_service.commit_import_records(
            account_id=account["id"],
            broker="ibkr",
            parsed_payload=parsed,
            dry_run=True,
        )

        issues = {(item["scope"], item["reason"]) for item in preview["currency_issues"]}
        self.assertIn(("statement", "currency_missing"), issues)
        self.assertIn(("trade", "currency_missing"), issues)
        self.assertIn(("cash", "currency_malformed"), issues)
        self.assertIn(("corporate_action", "currency_unknown"), issues)
        self.assertIn(("trade", "currency_operationally_unsupported"), issues)
        self.assertIn(("open_position", "currency_missing"), issues)
        self.assertFalse(preview["requires_confirmation"])
        self.assertEqual(
            self.service.list_broker_connections(portfolio_account_id=account["id"]),
            [],
        )

        statement_cases = [
            ("US D", "currency_malformed"),
            ("XYZ", "currency_unknown"),
            ("EUR", "currency_operationally_unsupported"),
        ]
        for statement_currency, expected_reason in statement_cases:
            with self.subTest(statement_currency=statement_currency):
                statement_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<FlexStatements><FlexStatement accountId="U-STATEMENT" currency="{statement_currency}" toDate="2026-01-31">
  <Trades><Trade assetCategory="STK" symbol="AAPL" exchange="NASDAQ" currency="USD" tradeDate="2026-01-03" buySell="BUY" quantity="1" tradePrice="10" ibExecID="STATEMENT-{statement_currency}"/></Trades>
</FlexStatement></FlexStatements>""".encode("utf-8")
                statement_parsed = self.import_service.parse_import_file(
                    broker="ibkr",
                    content=statement_xml,
                )
                statement_preview = self.import_service.commit_import_records(
                    account_id=account["id"],
                    broker="ibkr",
                    parsed_payload=statement_parsed,
                    dry_run=True,
                )
                self.assertIn(
                    ("statement", expected_reason),
                    {
                        (item["scope"], item["reason"])
                        for item in statement_preview["currency_issues"]
                    },
                )

        missing_record_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<FlexStatements><FlexStatement accountId="U-MISSING-RECORDS" currency="USD" toDate="2026-01-31">
  <CashTransactions><CashTransaction reportDate="2026-01-05" amount="5" description="Missing"/></CashTransactions>
  <CorporateActions><CorporateAction assetCategory="STK" symbol="AAPL" exchange="NASDAQ" reportDate="2026-01-06" description="2 for 1 split" ratio="2:1"/></CorporateActions>
  <OpenPositions><OpenPosition assetCategory="STK" symbol="MSFT" exchange="NASDAQ" reportDate="2026-01-31" position="2" costBasisPrice="20"/></OpenPositions>
</FlexStatement></FlexStatements>"""
        missing_parsed = self.import_service.parse_import_file(
            broker="ibkr",
            content=missing_record_xml,
        )
        missing_preview = self.import_service.commit_import_records(
            account_id=account["id"],
            broker="ibkr",
            parsed_payload=missing_parsed,
            dry_run=True,
        )
        missing_scopes = {
            item["scope"]
            for item in missing_preview["currency_issues"]
            if item["reason"] == "currency_missing"
        }
        self.assertTrue({"cash", "corporate_action", "open_position"}.issubset(missing_scopes))

    def test_ibkr_flex_currency_gate_is_all_or_nothing_and_corrected_retry_is_idempotent(self) -> None:
        account = self.service.create_account(name="Currency Gate", broker="IBKR", market="global", base_currency="USD")
        invalid_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<FlexStatements><FlexStatement accountId="U-GATE" currency="USD" fromDate="2026-01-01" toDate="2026-01-31">
  <Trades><Trade assetCategory="STK" symbol="AAPL" exchange="NASDAQ" currency="USD" tradeDate="2026-01-03" buySell="BUY" quantity="1" tradePrice="10" ibExecID="GATE-1"/></Trades>
  <CashTransactions><CashTransaction reportDate="2026-01-05" currency="XYZ" amount="5" description="Invalid"/></CashTransactions>
  <CorporateActions><CorporateAction assetCategory="STK" symbol="AAPL" exchange="NASDAQ" currency="USD" reportDate="2026-01-06" description="2 for 1 split" ratio="2:1"/></CorporateActions>
</FlexStatement></FlexStatements>"""
        invalid = self.import_service.parse_import_file(broker="ibkr", content=invalid_xml)

        with self.assertRaisesRegex(ValueError, "ibkr_currency_invalid"):
            self.import_service.commit_import_records(
                account_id=account["id"],
                broker="ibkr",
                parsed_payload=invalid,
            )

        self.assertEqual(self.service.list_trade_events(account_id=account["id"], page=1, page_size=20)["total"], 0)
        self.assertEqual(self.service.list_cash_ledger_events(account_id=account["id"], page=1, page_size=20)["total"], 0)
        self.assertEqual(self.service.list_corporate_action_events(account_id=account["id"], page=1, page_size=20)["total"], 0)
        self.assertEqual(self.service.list_broker_connections(portfolio_account_id=account["id"]), [])

        no_fx_xml = invalid_xml.replace(b'currency="XYZ"', b'currency="EUR"')
        no_fx = self.import_service.parse_import_file(broker="ibkr", content=no_fx_xml)
        with self.assertRaisesRegex(ValueError, "ibkr_fx_unavailable"):
            self.import_service.commit_import_records(
                account_id=account["id"],
                broker="ibkr",
                parsed_payload=no_fx,
            )
        self.assertEqual(self.service.list_trade_events(account_id=account["id"], page=1, page_size=20)["total"], 0)
        self.assertEqual(self.service.list_cash_ledger_events(account_id=account["id"], page=1, page_size=20)["total"], 0)
        self.assertEqual(self.service.list_corporate_action_events(account_id=account["id"], page=1, page_size=20)["total"], 0)
        self.assertEqual(self.service.list_broker_connections(portfolio_account_id=account["id"]), [])

        corrected_xml = invalid_xml.replace(b'currency="XYZ"', b'currency="USD"')
        corrected = self.import_service.parse_import_file(broker="ibkr", content=corrected_xml)
        first = self.import_service.commit_import_records(
            account_id=account["id"],
            broker="ibkr",
            parsed_payload=corrected,
        )
        repeat = self.import_service.commit_import_records(
            account_id=account["id"],
            broker="ibkr",
            parsed_payload=corrected,
        )

        self.assertEqual(first["inserted_count"], 1)
        self.assertEqual(first["cash_inserted_count"], 1)
        self.assertEqual(first["corporate_action_inserted_count"], 1)
        self.assertTrue(repeat["duplicate_import"])
        self.assertEqual(self.service.list_trade_events(account_id=account["id"], page=1, page_size=20)["total"], 1)
        self.assertEqual(self.service.list_cash_ledger_events(account_id=account["id"], page=1, page_size=20)["total"], 1)
        self.assertEqual(self.service.list_corporate_action_events(account_id=account["id"], page=1, page_size=20)["total"], 1)

    @staticmethod
    def _ibkr_atomicity_xml_bytes(*, operation: str, cash_amount: int = 5000) -> bytes:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<FlexStatements>
  <FlexStatement accountId="U-ATOMIC" fromDate="2026-01-01" toDate="2026-01-31" currency="USD">
    <Trades>
      <Trade assetCategory="STK" symbol="AAPL" exchange="NASDAQ" currency="USD" tradeDate="2026-01-03" buySell="BUY" quantity="1" tradePrice="10" ibExecID="{operation}-BUY"/>
    </Trades>
    <CashTransactions>
      <CashTransaction reportDate="2026-01-02" currency="USD" amount="{cash_amount}" description="Deposit {operation}"/>
    </CashTransactions>
    <CorporateActions>
      <CorporateAction assetCategory="STK" symbol="AAPL" exchange="NASDAQ" currency="USD" reportDate="2026-01-10" description="2 for 1 split {operation}" ratio="2:1"/>
    </CorporateActions>
  </FlexStatement>
</FlexStatements>
""".encode("utf-8")

    def test_ibkr_failure_on_later_trade_rolls_back_entire_import(self) -> None:
        account = self.service.create_account(
            name="Atomic Import",
            broker="IBKR",
            market="us",
            base_currency="USD",
        )
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<FlexStatements>
  <FlexStatement accountId="U-ROLLBACK" fromDate="2026-01-01" toDate="2026-01-31" currency="USD">
    <Trades>
      <Trade assetCategory="STK" symbol="AAPL" exchange="NASDAQ" currency="USD" tradeDate="2026-01-03" buySell="BUY" quantity="1" tradePrice="10" ibExecID="ROLLBACK-BUY-US"/>
      <Trade assetCategory="STK" symbol="HK00700" exchange="SEHK" currency="HKD" tradeDate="2026-01-03" buySell="BUY" quantity="1" tradePrice="20" ibExecID="ROLLBACK-BUY-HK"/>
      <Trade assetCategory="STK" symbol="AAPL" exchange="NASDAQ" currency="USD" tradeDate="2026-01-04" buySell="SELL" quantity="2" tradePrice="11" ibExecID="ROLLBACK-SELL"/>
    </Trades>
    <CashTransactions>
      <CashTransaction reportDate="2026-01-02" currency="USD" amount="5000" description="Deposit"/>
    </CashTransactions>
    <CorporateActions>
      <CorporateAction assetCategory="STK" symbol="AAPL" exchange="NASDAQ" currency="USD" reportDate="2026-01-10" description="2 for 1 split" ratio="2:1"/>
    </CorporateActions>
  </FlexStatement>
</FlexStatements>"""
        self.service.repo.save_fx_rate(
            from_currency="HKD",
            to_currency="USD",
            rate_date=date(2026, 1, 1),
            rate=0.128,
            source="unit-test",
            is_stale=False,
        )
        parsed = self.import_service.parse_import_file(broker="ibkr", content=xml)

        with self.assertRaises(PortfolioOversellError):
            self.import_service.commit_import_records(
                account_id=account["id"],
                broker="ibkr",
                parsed_payload=parsed,
            )

        self.assertEqual(self.service.get_account(account["id"], include_inactive=True)["market"], "us")
        self.assertEqual(self.service.list_trade_events(account_id=account["id"], page=1, page_size=20)["total"], 0)
        self.assertEqual(self.service.list_cash_ledger_events(account_id=account["id"], page=1, page_size=20)["total"], 0)
        self.assertEqual(self.service.list_corporate_action_events(account_id=account["id"], page=1, page_size=20)["total"], 0)
        self.assertEqual(self.service.list_broker_connections(portfolio_account_id=account["id"]), [])

    def test_ibkr_parser_rejection_prevents_valid_prefix_commit(self) -> None:
        account = self.service.create_account(
            name="Parser Rejection",
            broker="IBKR",
            market="us",
            base_currency="USD",
        )
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<FlexStatements>
  <FlexStatement accountId="U-PARSER-REJECT" currency="USD" toDate="2026-01-31">
    <Trades>
      <Trade assetCategory="STK" symbol="AAPL" exchange="NASDAQ" currency="USD" tradeDate="2026-01-03" buySell="BUY" quantity="1" tradePrice="10" ibExecID="VALID-PREFIX"/>
      <Trade assetCategory="STK" symbol="MSFT" exchange="NASDAQ" currency="USD" tradeDate="2026-01-04" buySell="BUY" quantity="1" ibExecID="INVALID-LATER"/>
    </Trades>
    <CashTransactions>
      <CashTransaction reportDate="2026-01-02" currency="USD" amount="5000" description="Deposit"/>
    </CashTransactions>
  </FlexStatement>
</FlexStatements>"""
        parsed = self.import_service.parse_import_file(broker="ibkr", content=xml)
        self.assertEqual(parsed["record_count"], 1)
        self.assertEqual(parsed["skipped_count"], 1)

        with self.assertRaises(ValueError):
            self.import_service.commit_import_records(
                account_id=account["id"],
                broker="ibkr",
                parsed_payload=parsed,
            )

        self.assertEqual(self.service.list_trade_events(account_id=account["id"], page=1, page_size=20)["total"], 0)
        self.assertEqual(self.service.list_cash_ledger_events(account_id=account["id"], page=1, page_size=20)["total"], 0)
        self.assertEqual(self.service.list_broker_connections(portfolio_account_id=account["id"]), [])

        seed_account = self.service.create_account(
            name="Open Position Parser Rejection",
            broker="IBKR",
            market="us",
            base_currency="USD",
        )
        open_position_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<FlexStatements>
  <FlexStatement accountId="U-SEED-REJECT" currency="USD" toDate="2026-01-31">
    <OpenPositions>
      <OpenPosition assetCategory="STK" symbol="MSFT" exchange="NASDAQ" currency="USD" reportDate="2026-01-31" position="1" costBasisPrice="10"/>
      <OpenPosition assetCategory="STK" symbol="AAPL" exchange="NASDAQ" currency="USD" reportDate="2026-01-31" position="1"/>
    </OpenPositions>
  </FlexStatement>
</FlexStatements>"""
        seed_parsed = self.import_service.parse_import_file(
            broker="ibkr",
            content=open_position_xml,
        )
        self.assertEqual(seed_parsed["record_count"], 1)
        self.assertEqual(seed_parsed["skipped_count"], 1)

        with self.assertRaises(ValueError):
            self.import_service.commit_import_records(
                account_id=seed_account["id"],
                broker="ibkr",
                parsed_payload=seed_parsed,
            )

        self.assertEqual(
            self.service.list_trade_events(
                account_id=seed_account["id"],
                page=1,
                page_size=20,
            )["total"],
            0,
        )
        self.assertEqual(
            self.service.list_broker_connections(
                portfolio_account_id=seed_account["id"],
            ),
            [],
        )

    def test_ibkr_persistence_failure_rolls_back_entire_import(self) -> None:
        account = self.service.create_account(
            name="Injected Failure",
            broker="IBKR",
            market="us",
            base_currency="USD",
        )
        parsed = self.import_service.parse_import_file(
            broker="ibkr",
            content=self._ibkr_atomicity_xml_bytes(operation="INJECT"),
        )

        with patch.object(
            self.service.repo,
            "add_cash_ledger_in_session",
            side_effect=RuntimeError("fault-injected cash persistence failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.import_service.commit_import_records(
                    account_id=account["id"],
                    broker="ibkr",
                    parsed_payload=parsed,
                )

        self.assertEqual(self.service.list_trade_events(account_id=account["id"], page=1, page_size=20)["total"], 0)
        self.assertEqual(self.service.list_cash_ledger_events(account_id=account["id"], page=1, page_size=20)["total"], 0)
        self.assertEqual(self.service.list_corporate_action_events(account_id=account["id"], page=1, page_size=20)["total"], 0)
        self.assertEqual(self.service.list_broker_connections(portfolio_account_id=account["id"]), [])

    def test_ibkr_historical_replay_does_not_duplicate_cash_or_actions(self) -> None:
        account = self.service.create_account(
            name="Historical Replay",
            broker="IBKR",
            market="us",
            base_currency="USD",
        )
        payload_a = self.import_service.parse_import_file(
            broker="ibkr",
            content=self._ibkr_atomicity_xml_bytes(operation="A", cash_amount=100),
        )
        payload_b = self.import_service.parse_import_file(
            broker="ibkr",
            content=self._ibkr_atomicity_xml_bytes(operation="B", cash_amount=200),
        )

        first_a = self.import_service.commit_import_records(
            account_id=account["id"],
            broker="ibkr",
            parsed_payload=payload_a,
        )
        first_b = self.import_service.commit_import_records(
            account_id=account["id"],
            broker="ibkr",
            parsed_payload=payload_b,
        )
        replay_a = self.import_service.commit_import_records(
            account_id=account["id"],
            broker="ibkr",
            parsed_payload=payload_a,
        )

        self.assertFalse(first_a["duplicate_import"])
        self.assertFalse(first_b["duplicate_import"])
        self.assertTrue(replay_a["duplicate_import"])
        self.assertEqual(self.service.list_trade_events(account_id=account["id"], page=1, page_size=20)["total"], 1)
        self.assertEqual(self.service.list_cash_ledger_events(account_id=account["id"], page=1, page_size=20)["total"], 2)
        self.assertEqual(self.service.list_corporate_action_events(account_id=account["id"], page=1, page_size=20)["total"], 2)

    def test_ibkr_completion_failure_rolls_back_fingerprint_and_children(self) -> None:
        account = self.service.create_account(
            name="Completion Failure",
            broker="IBKR",
            market="us",
            base_currency="USD",
        )
        parsed = self.import_service.parse_import_file(
            broker="ibkr",
            content=self._ibkr_atomicity_xml_bytes(operation="COMPLETE"),
        )

        with patch.object(
            self.service.repo,
            "add_completed_import_operation_in_session",
            side_effect=RuntimeError("fault-injected completion failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.import_service.commit_import_records(
                    account_id=account["id"],
                    broker="ibkr",
                    parsed_payload=parsed,
                )

        self.assertEqual(self.service.list_trade_events(account_id=account["id"], page=1, page_size=20)["total"], 0)
        self.assertEqual(self.service.list_cash_ledger_events(account_id=account["id"], page=1, page_size=20)["total"], 0)
        self.assertEqual(self.service.list_corporate_action_events(account_id=account["id"], page=1, page_size=20)["total"], 0)
        self.assertEqual(self.service.list_broker_connections(portfolio_account_id=account["id"]), [])
        with self.db.get_session() as session:
            self.assertEqual(session.query(PortfolioImportOperation).count(), 0)

    def test_concurrent_duplicate_ibkr_import_has_one_complete_winner(self) -> None:
        account = self.service.create_account(
            name="Concurrent Replay",
            broker="IBKR",
            market="us",
            base_currency="USD",
        )
        parsed = self.import_service.parse_import_file(
            broker="ibkr",
            content=self._ibkr_atomicity_xml_bytes(operation="CONCURRENT"),
        )

        def commit() -> dict:
            importer = PortfolioImportService(
                portfolio_service=PortfolioService(owner_id="portfolio-pr2-consumer")
            )
            return importer.commit_import_records(
                account_id=account["id"],
                broker="ibkr",
                parsed_payload=parsed,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = [future.result() for future in (executor.submit(commit), executor.submit(commit))]

        self.assertEqual(sorted(item["duplicate_import"] for item in results), [False, True])
        self.assertEqual(self.service.list_trade_events(account_id=account["id"], page=1, page_size=20)["total"], 1)
        self.assertEqual(self.service.list_cash_ledger_events(account_id=account["id"], page=1, page_size=20)["total"], 1)
        self.assertEqual(self.service.list_corporate_action_events(account_id=account["id"], page=1, page_size=20)["total"], 1)
        connections = self.service.list_broker_connections(portfolio_account_id=account["id"])
        self.assertEqual(len(connections), 1)
        self.assertEqual(
            connections[0]["last_import_fingerprint"],
            parsed["metadata"]["file_fingerprint"],
        )
        with self.db.get_session() as session:
            operations = session.query(PortfolioImportOperation).all()
        self.assertEqual(len(operations), 1)
        self.assertEqual(operations[0].status, "completed")

    def test_broker_parser_capacity_is_bounded(self) -> None:
        limits = PortfolioImportLimits(
            max_upload_bytes=4096,
            max_csv_rows=10,
            max_csv_cells=100,
            max_csv_cell_chars=1024,
            max_xml_nodes=100,
            max_xml_depth=10,
            parse_timeout_seconds=1.0,
            parse_concurrency=1,
        )
        importer = PortfolioImportService(
            portfolio_service=self.service,
            limits=limits,
        )
        started = Event()
        release = Event()
        expected = {
            "broker": "ibkr",
            "record_count": 0,
            "skipped_count": 0,
            "error_count": 0,
            "records": [],
            "cash_record_count": 0,
            "cash_entries": [],
            "corporate_action_count": 0,
            "corporate_actions": [],
            "warnings": [],
            "metadata": {"file_fingerprint": "0" * 64},
            "errors": [],
        }

        def blocked_parser(**_kwargs) -> dict:
            started.set()
            release.wait(timeout=1.0)
            return expected

        with patch.object(importer, "parse_import_file", side_effect=blocked_parser):
            with ThreadPoolExecutor(max_workers=1) as executor:
                first = executor.submit(
                    importer.parse_uploaded_file,
                    broker="ibkr",
                    content=self._ibkr_atomicity_xml_bytes(operation="CAPACITY"),
                    filename="capacity.xml",
                    content_type="application/xml",
                )
                self.assertTrue(started.wait(timeout=1.0))
                with self.assertRaises(PortfolioImportUnavailableError):
                    importer.parse_uploaded_file(
                        broker="ibkr",
                        content=self._ibkr_atomicity_xml_bytes(operation="CAPACITY"),
                        filename="capacity.xml",
                        content_type="application/xml",
                    )
                release.set()
                self.assertEqual(first.result(), expected)

    def test_ibkr_open_positions_seed_when_trades_absent(self) -> None:
        account = self.service.create_account(name="Global", broker="IBKR", market="us", base_currency="USD")
        aid = account["id"]

        parsed = self.import_service.parse_import_file(
            broker="ibkr",
            content=self._ibkr_open_positions_xml_bytes(),
        )
        self.assertEqual(parsed["record_count"], 1)
        self.assertTrue(parsed["metadata"]["open_position_seeded"])

        result = self.import_service.commit_import_records(
            account_id=aid,
            broker="ibkr",
            parsed_payload=parsed,
        )
        self.assertEqual(result["inserted_count"], 1)
        trades = self.service.list_trade_events(account_id=aid, page=1, page_size=20)
        self.assertEqual(trades["items"][0]["symbol"], "MSFT")
        self.assertIn("open_position_seed", trades["items"][0]["note"] or "")

    def test_ibkr_import_rejects_malformed_xml(self) -> None:
        with self.assertRaises(ValueError):
            self.import_service.parse_import_file(
                broker="ibkr",
                content=b"<broken-xml",
            )

    def test_global_account_snapshot_and_risk_use_account_base_currency(self) -> None:
        account = self.service.create_account(name="Global", broker="IBKR", market="global", base_currency="USD")
        aid = account["id"]

        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 2, 1),
            direction="in",
            amount=10000.0,
            currency="USD",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="AAPL",
            trade_date=date(2026, 2, 1),
            side="buy",
            quantity=1,
            price=150.0,
            currency="USD",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="HK00700",
            trade_date=date(2026, 2, 1),
            side="buy",
            quantity=10,
            price=320.0,
            currency="HKD",
        )
        self._save_close("AAPL", date(2026, 2, 1), 150.0)
        self._save_close("HK00700", date(2026, 2, 1), 320.0)
        self.service.repo.save_fx_rate(
            from_currency="HKD",
            to_currency="USD",
            rate_date=date(2026, 2, 1),
            rate=0.128,
            source="manual",
            is_stale=False,
        )

        snapshot = self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 2, 1), cost_method="fifo")
        self.assertEqual(snapshot["currency"], "USD")
        self.assertEqual(snapshot["accounts"][0]["market"], "global")
        self.assertEqual({item["market"] for item in snapshot["accounts"][0]["positions"]}, {"us", "hk"})

        report = self.risk_service.get_risk_report(account_id=aid, as_of=date(2026, 2, 1), cost_method="fifo")
        self.assertEqual(report["currency"], "USD")
        positions = {item["symbol"]: item for item in report["concentration"]["top_positions"]}
        self.assertAlmostEqual(positions["HK00700"]["market_value_base"], 409.6, places=4)

    def test_risk_threshold_boundary(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=20000,
            currency="CNY",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=100,
            price=100,
            market="cn",
            currency="CNY",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="000001",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=100,
            price=20,
            market="cn",
            currency="CNY",
        )

        self._save_close("600519", date(2026, 1, 1), 100.0)
        self._save_close("000001", date(2026, 1, 1), 20.0)
        self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 1), cost_method="fifo")

        self._save_close("600519", date(2026, 1, 2), 70.0)
        self._save_close("000001", date(2026, 1, 2), 20.0)
        report = self.risk_service.get_risk_report(account_id=aid, as_of=date(2026, 1, 2), cost_method="fifo")

        self.assertTrue(report["concentration"]["alert"])
        self.assertTrue(report["drawdown"]["alert"])
        self.assertTrue(report["stop_loss"]["near_alert"])
        self.assertGreaterEqual(report["stop_loss"]["triggered_count"], 1)
        self.assertAlmostEqual(report["thresholds"]["drawdown_alert_pct"], 10.0, places=6)

    def test_risk_drawdown_backfills_snapshot_window_on_first_call(self) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=20000,
            currency="CNY",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=100,
            price=100,
            market="cn",
            currency="CNY",
        )
        self._save_close("600519", date(2026, 1, 1), 100.0)
        self._save_close("600519", date(2026, 1, 2), 70.0)

        report = self.risk_service.get_risk_report(account_id=aid, as_of=date(2026, 1, 2), cost_method="fifo")
        self.assertGreaterEqual(report["drawdown"]["series_points"], 2)
        self.assertGreater(report["drawdown"]["max_drawdown_pct"], 10.0)
        self.assertTrue(report["drawdown"]["alert"])

    def test_concentration_uses_cny_normalized_exposure(self) -> None:
        cn_account = self.service.create_account(name="CN", broker="Demo", market="cn", base_currency="CNY")
        us_account = self.service.create_account(name="US", broker="Demo", market="us", base_currency="USD")
        cn_id = cn_account["id"]
        us_id = us_account["id"]

        self.service.record_cash_ledger(
            account_id=cn_id,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=1000.0,
            currency="CNY",
        )
        self.service.record_trade(
            account_id=cn_id,
            symbol="600519",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=10,
            price=100,
            market="cn",
            currency="CNY",
        )

        self.service.record_cash_ledger(
            account_id=us_id,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=100.0,
            currency="USD",
        )
        self.service.record_trade(
            account_id=us_id,
            symbol="AAPL",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=1,
            price=100,
            market="us",
            currency="USD",
        )
        self._save_close("600519", date(2026, 1, 1), 100.0)
        self._save_close("AAPL", date(2026, 1, 1), 100.0)
        self.service.repo.save_fx_rate(
            from_currency="USD",
            to_currency="CNY",
            rate_date=date(2026, 1, 1),
            rate=7.0,
            source="manual",
            is_stale=False,
        )
        self.service.get_portfolio_snapshot(as_of=date(2026, 1, 1), cost_method="fifo")

        report = self.risk_service.get_risk_report(as_of=date(2026, 1, 1), cost_method="fifo")
        positions = {item["symbol"]: item for item in report["concentration"]["top_positions"]}
        self.assertIn("AAPL", positions)
        self.assertAlmostEqual(positions["AAPL"]["market_value_base"], 700.0, places=6)

    def test_account_attribution_uses_normalized_total_equity_across_accounts(self) -> None:
        cn_account = self.service.create_account(name="CN", broker="Demo", market="cn", base_currency="CNY")
        us_account = self.service.create_account(name="US", broker="Demo", market="us", base_currency="USD")
        cn_id = cn_account["id"]
        us_id = us_account["id"]

        self.service.record_cash_ledger(
            account_id=cn_id,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=1000.0,
            currency="CNY",
        )
        self.service.record_trade(
            account_id=cn_id,
            symbol="600519",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=10,
            price=100,
            market="cn",
            currency="CNY",
        )

        self.service.record_cash_ledger(
            account_id=us_id,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=100.0,
            currency="USD",
        )
        self.service.record_trade(
            account_id=us_id,
            symbol="AAPL",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=1,
            price=100,
            market="us",
            currency="USD",
        )
        self._save_close("600519", date(2026, 1, 1), 100.0)
        self._save_close("AAPL", date(2026, 1, 1), 100.0)
        self.service.repo.save_fx_rate(
            from_currency="USD",
            to_currency="CNY",
            rate_date=date(2026, 1, 1),
            rate=7.0,
            source="manual",
            is_stale=False,
        )

        report = self.risk_service.get_risk_report(as_of=date(2026, 1, 1), cost_method="fifo")

        self.assertIn("account_attribution", report)
        self.assertEqual(report["account_attribution"]["total_equity"], 1700.0)
        self.assertEqual(report["account_attribution"]["total_market_value"], 1700.0)
        self.assertEqual(
            report["account_attribution"]["top_accounts"],
            [
                {
                    "account_id": cn_id,
                    "account_name": "CN",
                    "market": "cn",
                    "total_equity_base": 1000.0,
                    "equity_weight_pct": 58.8235,
                    "total_market_value_base": 1000.0,
                    "market_value_weight_pct": 58.8235,
                    "fx_stale": False,
                },
                {
                    "account_id": us_id,
                    "account_name": "US",
                    "market": "us",
                    "total_equity_base": 700.0,
                    "equity_weight_pct": 41.1765,
                    "total_market_value_base": 700.0,
                    "market_value_weight_pct": 41.1765,
                    "fx_stale": False,
                },
            ],
        )

    @patch.object(PortfolioRiskService, "_fetch_belong_boards", return_value=[{"name": "白酒", "type": "行业"}])
    def test_risk_report_exposes_industry_attribution_without_changing_existing_blocks(self, _mock_fetch) -> None:
        cn_account = self.service.create_account(name="CN", broker="Demo", market="cn", base_currency="CNY")
        us_account = self.service.create_account(name="US", broker="Demo", market="us", base_currency="USD")
        cn_id = cn_account["id"]
        us_id = us_account["id"]

        self.service.record_cash_ledger(
            account_id=cn_id,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=1000.0,
            currency="CNY",
        )
        self.service.record_trade(
            account_id=cn_id,
            symbol="600519",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=10,
            price=100.0,
            market="cn",
            currency="CNY",
        )
        self.service.record_cash_ledger(
            account_id=us_id,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=100.0,
            currency="USD",
        )
        self.service.record_trade(
            account_id=us_id,
            symbol="AAPL",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=1,
            price=100.0,
            market="us",
            currency="USD",
        )
        self._save_close("600519", date(2026, 1, 1), 100.0)
        self._save_close("AAPL", date(2026, 1, 1), 100.0)
        self.service.repo.save_fx_rate(
            from_currency="USD",
            to_currency="CNY",
            rate_date=date(2026, 1, 1),
            rate=7.0,
            source="manual",
            is_stale=False,
        )

        report = self.risk_service.get_risk_report(as_of=date(2026, 1, 1), cost_method="fifo")

        self.assertEqual(report["concentration"]["top_weight_pct"], 58.8235)
        self.assertFalse(report["stop_loss"]["near_alert"])
        self.assertEqual(
            report["industry_attribution"]["top_industries"],
            [
                {
                    "industry": "白酒",
                    "market_value_base": 1000.0,
                    "weight_pct": 58.8235,
                    "symbol_count": 1,
                },
                {
                    "industry": "UNCLASSIFIED",
                    "market_value_base": 700.0,
                    "weight_pct": 41.1765,
                    "symbol_count": 1,
                },
            ],
        )

    @patch.object(PortfolioRiskService, "_fetch_belong_boards", return_value=[{"name": "白酒", "type": "行业"}])
    def test_snapshot_persists_and_exposes_portfolio_attribution(self, _mock_fetch) -> None:
        cn_account = self.service.create_account(name="CN", broker="Demo", market="cn", base_currency="CNY")
        us_account = self.service.create_account(name="US", broker="Demo", market="us", base_currency="USD")
        cn_id = cn_account["id"]
        us_id = us_account["id"]

        self.service.record_cash_ledger(
            account_id=cn_id,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=1000.0,
            currency="CNY",
        )
        self.service.record_trade(
            account_id=cn_id,
            symbol="600519",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=10,
            price=100.0,
            market="cn",
            currency="CNY",
        )
        self.service.record_cash_ledger(
            account_id=us_id,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=100.0,
            currency="USD",
        )
        self.service.record_trade(
            account_id=us_id,
            symbol="AAPL",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=1,
            price=100.0,
            market="us",
            currency="USD",
        )
        self._save_close("600519", date(2026, 1, 1), 100.0)
        self._save_close("AAPL", date(2026, 1, 1), 100.0)
        self.service.repo.save_fx_rate(
            from_currency="USD",
            to_currency="CNY",
            rate_date=date(2026, 1, 1),
            rate=7.0,
            source="manual",
            is_stale=False,
        )

        snapshot = self.service.get_portfolio_snapshot(as_of=date(2026, 1, 1), cost_method="fifo")
        cached_cn = self.service.repo.get_cached_snapshot_bundle(
            account_id=cn_id,
            snapshot_date=date(2026, 1, 1),
            cost_method="fifo",
        )

        self.assertEqual(snapshot["portfolio_attribution"]["account_attribution"]["top_accounts"][0]["account_id"], cn_id)
        self.assertEqual(
            snapshot["portfolio_attribution"]["industry_attribution"]["top_industries"],
            [
                {
                    "industry": "白酒",
                    "market_value_base": 1000.0,
                    "weight_pct": 58.8235,
                    "symbol_count": 1,
                },
                {
                    "industry": "UNCLASSIFIED",
                    "market_value_base": 700.0,
                    "weight_pct": 41.1765,
                    "symbol_count": 1,
                },
            ],
        )
        self.assertIsNotNone(cached_cn)
        cached_payload = json.loads(cached_cn["snapshot"].payload)
        self.assertEqual(
            cached_payload["industry_attribution"]["top_industries"],
            [
                {
                    "industry": "白酒",
                    "market_value_base": 1000.0,
                    "weight_pct": 100.0,
                    "symbol_count": 1,
                }
            ],
        )

    def test_snapshot_exposes_market_breakdown_across_multi_account_portfolio(self) -> None:
        cn_account = self.service.create_account(name="CN", broker="Demo", market="cn", base_currency="CNY")
        us_account = self.service.create_account(name="US", broker="Demo", market="us", base_currency="USD")
        cn_id = cn_account["id"]
        us_id = us_account["id"]

        self.service.record_cash_ledger(
            account_id=cn_id,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=1000.0,
            currency="CNY",
        )
        self.service.record_trade(
            account_id=cn_id,
            symbol="600519",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=10,
            price=100.0,
            market="cn",
            currency="CNY",
        )

        self.service.record_cash_ledger(
            account_id=us_id,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=100.0,
            currency="USD",
        )
        self.service.record_trade(
            account_id=us_id,
            symbol="AAPL",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=1,
            price=100.0,
            market="us",
            currency="USD",
        )

        self._save_close("600519", date(2026, 1, 1), 100.0)
        self._save_close("AAPL", date(2026, 1, 1), 100.0)
        self.service.repo.save_fx_rate(
            from_currency="USD",
            to_currency="CNY",
            rate_date=date(2026, 1, 1),
            rate=7.0,
            source="manual",
            is_stale=False,
        )

        snapshot = self.service.get_portfolio_snapshot(as_of=date(2026, 1, 1), cost_method="fifo")

        self.assertEqual(snapshot["currency"], "CNY")
        self.assertEqual(
            snapshot["market_breakdown"],
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

    def test_sector_concentration_uses_unclassified_for_non_cn(self) -> None:
        us_account = self.service.create_account(name="US", broker="Demo", market="us", base_currency="USD")
        us_id = us_account["id"]
        self.service.record_cash_ledger(
            account_id=us_id,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=100.0,
            currency="USD",
        )
        self.service.record_trade(
            account_id=us_id,
            symbol="AAPL",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=1,
            price=100,
            market="us",
            currency="USD",
        )
        self._save_close("AAPL", date(2026, 1, 1), 100.0)
        report = self.risk_service.get_risk_report(account_id=us_id, as_of=date(2026, 1, 1), cost_method="fifo")
        self.assertIn("sector_concentration", report)
        sectors = report["sector_concentration"]["top_sectors"]
        self.assertTrue(len(sectors) >= 1)
        self.assertEqual(sectors[0]["sector"], "UNCLASSIFIED")

    @patch.object(PortfolioRiskService, "_fetch_belong_boards", return_value=[{"name": "白酒", "type": "行业"}])
    def test_sector_concentration_cn_board_mapping(self, _mock_fetch) -> None:
        account = self.service.create_account(name="Main", broker="Demo", market="cn", base_currency="CNY")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=10000.0,
            currency="CNY",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="600519",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=100,
            price=100,
            market="cn",
            currency="CNY",
        )
        self._save_close("600519", date(2026, 1, 1), 100.0)
        report = self.risk_service.get_risk_report(account_id=aid, as_of=date(2026, 1, 1), cost_method="fifo")
        sectors = report["sector_concentration"]["top_sectors"]
        self.assertTrue(len(sectors) >= 1)
        self.assertEqual(sectors[0]["sector"], "白酒")

    def test_snapshot_does_not_trigger_online_fx_refresh(self) -> None:
        account = self.service.create_account(name="US", broker="Demo", market="us", base_currency="CNY")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=1000.0,
            currency="USD",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="AAPL",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=1,
            price=100,
            market="us",
            currency="USD",
        )
        self._save_close("AAPL", date(2026, 1, 1), 100.0)
        self.service.repo.save_fx_rate(
            from_currency="USD",
            to_currency="CNY",
            rate_date=date(2026, 1, 1),
            rate=7.0,
            source="manual",
            is_stale=False,
        )

        with patch.object(PortfolioService, "_fetch_fx_rate_from_yfinance", side_effect=AssertionError("should not call")):
            self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 1), cost_method="fifo")

    def test_snapshot_cache_refreshes_after_fx_rate_update(self) -> None:
        account = self.service.create_account(name="US", broker="Demo", market="us", base_currency="CNY")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=1000.0,
            currency="USD",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="AAPL",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=1,
            price=100,
            market="us",
            currency="USD",
        )
        self._save_close("AAPL", date(2026, 1, 1), 100.0)
        self.service.repo.save_fx_rate(
            from_currency="USD",
            to_currency="CNY",
            rate_date=date(2026, 1, 1),
            rate=7.0,
            source="manual",
            is_stale=False,
        )

        first = self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 1), cost_method="fifo")
        self.service.repo.save_fx_rate(
            from_currency="USD",
            to_currency="CNY",
            rate_date=date(2026, 1, 1),
            rate=8.0,
            source="manual",
            is_stale=False,
        )
        second = self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 1), cost_method="fifo")

        self.assertAlmostEqual(first["accounts"][0]["total_market_value"], 700.0, places=6)
        self.assertAlmostEqual(second["accounts"][0]["total_market_value"], 800.0, places=6)
        self.assertAlmostEqual(first["accounts"][0]["total_cash"], 6300.0, places=6)
        self.assertAlmostEqual(second["accounts"][0]["total_cash"], 7200.0, places=6)

    def test_irrelevant_fx_rate_update_does_not_invalidate_warm_snapshot_cache(self) -> None:
        account = self.service.create_account(name="US", broker="Demo", market="us", base_currency="CNY")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=1000.0,
            currency="USD",
        )
        self.service.record_trade(
            account_id=aid,
            symbol="AAPL",
            trade_date=date(2026, 1, 1),
            side="buy",
            quantity=1,
            price=100,
            market="us",
            currency="USD",
        )
        self._save_close("AAPL", date(2026, 1, 1), 100.0)
        self.service.repo.save_fx_rate(
            from_currency="USD",
            to_currency="CNY",
            rate_date=date(2026, 1, 1),
            rate=7.0,
            source="manual",
            is_stale=False,
        )
        self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 1), cost_method="fifo")
        self.service.repo.save_fx_rate(
            from_currency="EUR",
            to_currency="CNY",
            rate_date=date(2026, 1, 1),
            rate=8.1,
            source="manual",
            is_stale=False,
        )

        with patch.object(
            self.service,
            "_build_account_snapshot",
            side_effect=AssertionError("irrelevant FX update should not invalidate warm cache"),
        ):
            second = self.service.get_portfolio_snapshot(account_id=aid, as_of=date(2026, 1, 1), cost_method="fifo")

        self.assertAlmostEqual(second["accounts"][0]["total_market_value"], 700.0, places=6)
        self.assertAlmostEqual(second["accounts"][0]["total_cash"], 6300.0, places=6)

    def test_fx_refresh_fallback_marks_stale(self) -> None:
        account = self.service.create_account(name="US", broker="Demo", market="us", base_currency="CNY")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=1000.0,
            currency="USD",
        )
        self.service.repo.save_fx_rate(
            from_currency="USD",
            to_currency="CNY",
            rate_date=date(2026, 1, 1),
            rate=7.0,
            source="manual",
            is_stale=False,
        )

        with patch.object(PortfolioService, "_fetch_fx_rate_from_yfinance", return_value=None):
            summary = self.service.refresh_fx_rates(account_id=aid, as_of=date(2026, 1, 2))

        self.assertEqual(summary["pair_count"], 1)
        self.assertEqual(summary["updated_count"], 0)
        self.assertEqual(summary["stale_count"], 1)
        latest = self.service.repo.get_latest_fx_rate(
            from_currency="USD",
            to_currency="CNY",
            as_of=date(2026, 1, 2),
        )
        self.assertIsNotNone(latest)
        self.assertTrue(bool(latest.is_stale))
        self.assertAlmostEqual(float(latest.rate), 7.0, places=6)

    def test_fx_refresh_disabled_returns_real_pair_count_without_fetching(self) -> None:
        account = self.service.create_account(name="US", broker="Demo", market="us", base_currency="CNY")
        aid = account["id"]
        self.service.record_cash_ledger(
            account_id=aid,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=1000.0,
            currency="USD",
        )

        disabled_config = SimpleNamespace(portfolio_fx_update_enabled=False)
        with patch("src.services.portfolio_service.get_config", return_value=disabled_config) as get_config_mock, patch.object(
            PortfolioService,
            "_fetch_fx_rate_from_yfinance",
            side_effect=AssertionError("should not call"),
        ), patch.object(self.service.repo, "save_fx_rate", wraps=self.service.repo.save_fx_rate) as save_fx_rate_mock:
            summary = self.service.refresh_fx_rates(account_id=aid, as_of=date(2026, 1, 2))

        self.assertFalse(summary["refresh_enabled"])
        self.assertEqual(summary["disabled_reason"], "portfolio_fx_update_disabled")
        self.assertEqual(summary["pair_count"], 1)
        self.assertEqual(summary["updated_count"], 0)
        self.assertEqual(summary["stale_count"], 0)
        self.assertEqual(summary["error_count"], 0)
        get_config_mock.assert_called_once()
        save_fx_rate_mock.assert_not_called()

    def test_fx_refresh_disabled_skips_invalid_currency_rows(self) -> None:
        account = self.service.create_account(name="US", broker="Demo", market="us", base_currency="CNY")
        aid = account["id"]

        disabled_config = SimpleNamespace(portfolio_fx_update_enabled=False)
        invalid_row = SimpleNamespace(currency="")
        valid_row = SimpleNamespace(currency="USD")
        with patch("src.services.portfolio_service.get_config", return_value=disabled_config), patch.object(
            self.service.repo,
            "list_trades",
            return_value=[invalid_row, valid_row],
        ), patch.object(
            self.service.repo,
            "list_cash_ledger",
            return_value=[],
        ), patch.object(
            PortfolioService,
            "_fetch_fx_rate_from_yfinance",
            side_effect=AssertionError("should not call"),
        ):
            summary = self.service.refresh_fx_rates(account_id=aid, as_of=date(2026, 1, 2))

        self.assertFalse(summary["refresh_enabled"])
        self.assertEqual(summary["pair_count"], 1)
        self.assertEqual(summary["updated_count"], 0)
        self.assertEqual(summary["stale_count"], 0)
        self.assertEqual(summary["error_count"], 0)

    def test_fx_refresh_endpoint_returns_disabled_status_fields(self) -> None:
        account = self.service.create_account(name="US", broker="Demo", market="us", base_currency="CNY")
        account_id = account["id"]
        self.service.record_cash_ledger(
            account_id=account_id,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=1000.0,
            currency="USD",
        )

        disabled_config = SimpleNamespace(portfolio_fx_update_enabled=False)
        with patch("src.services.portfolio_service.get_config", return_value=disabled_config), patch.object(
            PortfolioService,
            "_fetch_fx_rate_from_yfinance",
            side_effect=AssertionError("should not call"),
        ):
            response = self.client.post(
                "/api/v1/portfolio/fx/refresh",
                params={"account_id": account_id, "as_of": "2026-01-02"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["refresh_enabled"])
        self.assertEqual(payload["disabled_reason"], "portfolio_fx_update_disabled")
        self.assertEqual(payload["pair_count"], 1)
        self.assertEqual(payload["updated_count"], 0)
        self.assertEqual(payload["stale_count"], 0)
        self.assertEqual(payload["error_count"], 0)

    def test_fx_refresh_endpoint_returns_enabled_status_fields(self) -> None:
        account = self.service.create_account(name="US", broker="Demo", market="us", base_currency="CNY")
        account_id = account["id"]
        self.service.record_cash_ledger(
            account_id=account_id,
            event_date=date(2026, 1, 1),
            direction="in",
            amount=1000.0,
            currency="USD",
        )

        with patch.object(PortfolioService, "_fetch_fx_rate_from_yfinance", return_value=None):
            response = self.client.post(
                "/api/v1/portfolio/fx/refresh",
                params={"account_id": account_id, "as_of": "2026-01-02"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["refresh_enabled"])
        self.assertIsNone(payload["disabled_reason"])
        self.assertEqual(payload["pair_count"], 1)
        self.assertEqual(payload["updated_count"], 0)
        self.assertEqual(payload["stale_count"], 0)
        self.assertEqual(payload["error_count"], 1)

    def test_import_and_risk_endpoints(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Main", "broker": "Demo", "market": "cn", "base_currency": "CNY"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]

        import_resp = self.client.post(
            "/api/v1/portfolio/imports/csv/commit",
            data={"account_id": str(account_id), "broker": "huatai", "dry_run": "false"},
            files={"file": ("huatai.csv", self._csv_bytes(with_trade_uid=True), "text/csv")},
        )
        self.assertEqual(import_resp.status_code, 200)
        self.assertEqual(import_resp.json()["inserted_count"], 1)

        self._save_close("600519", date(2026, 1, 2), 95.0)
        self.service.get_portfolio_snapshot(account_id=account_id, as_of=date(2026, 1, 2), cost_method="fifo")
        risk_resp = self.client.get(
            "/api/v1/portfolio/risk",
            params={"account_id": account_id, "as_of": "2026-01-02", "cost_method": "fifo"},
        )
        self.assertEqual(risk_resp.status_code, 200)
        payload = risk_resp.json()
        self.assertEqual(payload["cost_method"], "fifo")
        self.assertIn("concentration", payload)
        self.assertIn("sector_concentration", payload)
        self.assertIn("drawdown", payload)
        self.assertIn("stop_loss", payload)


if __name__ == "__main__":
    unittest.main()
