# -*- coding: utf-8 -*-
"""Focused API contract tests for additive portfolio diagnostics fields."""

from __future__ import annotations

from decimal import Decimal
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
from pydantic import ValidationError

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.app import create_app
from api.v1.endpoints.portfolio import _build_import_parse_response
from api.v1.schemas.portfolio import (
    PortfolioCashLedgerCreateRequest,
    PortfolioCorporateActionCreateRequest,
    PortfolioAccountSnapshot,
    PortfolioExposureItem,
    PortfolioFxRateItem,
    PortfolioHistorySnapshotItem,
    PortfolioIbkrSyncResponse,
    PortfolioLiveFxRateResponse,
    PortfolioImportCashEntryItem,
    PortfolioImportCorporateActionItem,
    PortfolioImportTradeItem,
    PortfolioPnlMetric,
    PortfolioPositionItem,
    PortfolioSnapshotResponse,
    PortfolioTradeCreateRequest,
    PortfolioTradeUpdateRequest,
)
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


class PortfolioExactWireContractTestCase(unittest.TestCase):
    def test_openapi_exact_decimal_schema_excludes_binary_float(self) -> None:
        app_schema = create_app().openapi()
        components = app_schema["components"]["schemas"]
        trade_quantity_schema = components["PortfolioTradeCreateRequest"]["properties"][
            "quantity"
        ]
        sync_properties = components["PortfolioIbkrSyncResponse"]["properties"]
        import_trade_properties = components["PortfolioImportTradeItem"]["properties"]
        import_cash_properties = components["PortfolioImportCashEntryItem"]["properties"]
        import_corporate_action_properties = components["PortfolioImportCorporateActionItem"]["properties"]

        self.assertEqual(
            {branch["type"] for branch in trade_quantity_schema["anyOf"]},
            {"integer", "string"},
        )
        self.assertNotIn(
            "number",
            {branch["type"] for branch in trade_quantity_schema["anyOf"]},
        )
        integer_branch = next(
            branch for branch in trade_quantity_schema["anyOf"] if branch["type"] == "integer"
        )
        self.assertEqual(integer_branch["exclusiveMinimum"], 0.0)

        for properties, field_names in (
            (import_trade_properties, ("quantity", "price", "fee", "tax")),
            (import_cash_properties, ("amount",)),
            (import_corporate_action_properties, ("cash_dividend_per_share", "split_ratio")),
        ):
            for field_name in field_names:
                with self.subTest(import_field=field_name):
                    field_schema = properties[field_name]
                    schema_types = (
                        {field_schema["type"]}
                        if "type" in field_schema
                        else {
                            branch.get("type")
                            for branch in field_schema.get("anyOf", [])
                            if isinstance(branch, dict)
                        }
                    )
                    self.assertIn("string", schema_types)
                    self.assertNotIn("number", schema_types)

        validation_schema = PortfolioIbkrSyncResponse.model_json_schema(mode="validation")
        for field_name in (
            "total_cash",
            "total_market_value",
            "total_equity",
            "realized_pnl",
            "unrealized_pnl",
        ):
            with self.subTest(field=field_name):
                self.assertEqual(sync_properties[field_name]["type"], "string")
                self.assertEqual(
                    {
                        branch["type"]
                        for branch in validation_schema["properties"][field_name]["anyOf"]
                    },
                    {"integer", "string"},
                )

    def test_ibkr_sync_response_uses_base_currency_precision_and_rejects_float(self) -> None:
        payload = {
            "account_id": 1,
            "broker_connection_id": 1,
            "broker_account_ref": "ref",
            "connection_name": "name",
            "snapshot_date": "2026-01-01",
            "synced_at": "2026-01-01T00:00:00Z",
            "base_currency": "USD",
            "total_cash": "1234567890123456.12",
            "total_market_value": "0.00",
            "total_equity": "0.00",
            "realized_pnl": "0.00",
            "unrealized_pnl": "0.00",
            "position_count": 0,
            "cash_balance_count": 0,
            "fx_stale": False,
            "snapshot_overlay_active": True,
            "used_existing_connection": True,
            "api_base_url": "https://example.invalid",
            "verify_ssl": True,
        }

        response = PortfolioIbkrSyncResponse(**payload)

        self.assertEqual(response.total_cash, Decimal("1234567890123456.12"))
        self.assertEqual(
            response.model_dump(mode="json")["total_cash"],
            "1234567890123456.12",
        )
        with self.assertRaises(ValidationError):
            PortfolioIbkrSyncResponse(**{**payload, "total_cash": 0.1})
        with self.assertRaises(ValidationError):
            PortfolioIbkrSyncResponse(**{**payload, "total_cash": "1.001"})

    def test_trade_request_preserves_canonical_decimal_text_and_rejects_float(self) -> None:
        payload = {
            "account_id": 1,
            "symbol": "AAPL",
            "trade_date": "2026-01-01",
            "side": "buy",
            "quantity": "9007199254740993.12345678",
            "price": "1234567890123456.12345678",
            "fee": "0.01",
            "tax": "0.00",
            "market": "us",
            "currency": "USD",
        }

        request = PortfolioTradeCreateRequest(**payload)

        self.assertEqual(request.quantity, Decimal("9007199254740993.12345678"))
        self.assertEqual(request.price, Decimal("1234567890123456.12345678"))
        self.assertEqual(request.fee, Decimal("0.01"))
        self.assertEqual(request.tax, Decimal("0.00"))
        self.assertEqual(request.model_dump(mode="json")["quantity"], "9007199254740993.12345678")
        with self.assertRaises(ValidationError):
            PortfolioTradeCreateRequest(**{**payload, "quantity": 0.1})

    def test_import_preview_response_preserves_decimal_text_and_rejects_float(self) -> None:
        response = _build_import_parse_response(
            {
                "broker": "csv",
                "record_count": 1,
                "skipped_count": 0,
                "error_count": 0,
                "records": [
                    {
                        "trade_date": "2026-01-01",
                        "symbol": "AAPL",
                        "side": "buy",
                        "quantity": "9007199254740993.12345678",
                        "price": "1234567890123456.12345678",
                        "fee": "0.00000001",
                        "tax": "0.00000001",
                        "dedup_hash": "import-preview",
                    }
                ],
                "cash_record_count": 1,
                "cash_entries": [
                    {
                        "event_date": "2026-01-01",
                        "direction": "in",
                        "amount": "1234567890123456.12345678",
                        "currency": "USD",
                    }
                ],
                "corporate_action_count": 1,
                "corporate_actions": [
                    {
                        "effective_date": "2026-01-01",
                        "symbol": "AAPL",
                        "market": "us",
                        "currency": "USD",
                        "action_type": "cash_dividend",
                        "cash_dividend_per_share": "0.00000001",
                        "split_ratio": "2.00000000",
                    }
                ],
            }
        ).model_dump(mode="json")

        self.assertEqual(response["records"][0]["quantity"], "9007199254740993.12345678")
        self.assertEqual(response["records"][0]["price"], "1234567890123456.12345678")
        self.assertEqual(response["records"][0]["fee"], "0.00000001")
        self.assertEqual(response["records"][0]["tax"], "0.00000001")
        self.assertEqual(response["cash_entries"][0]["amount"], "1234567890123456.12345678")
        self.assertEqual(
            response["corporate_actions"][0]["cash_dividend_per_share"],
            "0.00000001",
        )
        self.assertEqual(response["corporate_actions"][0]["split_ratio"], "2.00000000")

        with self.assertRaises(ValidationError):
            PortfolioImportTradeItem(
                trade_date="2026-01-01",
                symbol="AAPL",
                side="buy",
                quantity=0.1,
                price="1",
                fee="0",
                tax="0",
                dedup_hash="float",
            )
        with self.assertRaises(ValidationError):
            PortfolioImportCashEntryItem(
                event_date="2026-01-01",
                direction="in",
                amount=0.1,
                currency="USD",
            )
        with self.assertRaises(ValidationError):
            PortfolioImportCorporateActionItem(
                effective_date="2026-01-01",
                symbol="AAPL",
                market="us",
                currency="USD",
                action_type="split_adjustment",
                split_ratio=0.1,
            )

    def test_remaining_event_requests_preserve_decimal_transport_and_reject_float(self) -> None:
        trade_update = PortfolioTradeUpdateRequest(
            quantity="9007199254740993.12345678",
            price="1234567890123456.12345678",
            fee="0.01",
            tax="0.00",
        )
        cash = PortfolioCashLedgerCreateRequest(
            account_id=1,
            event_date="2026-01-01",
            direction="in",
            amount="1234567890123456.12",
            currency="USD",
        )
        corporate_action = PortfolioCorporateActionCreateRequest(
            account_id=1,
            symbol="AAPL",
            effective_date="2026-01-01",
            action_type="cash_dividend",
            market="us",
            currency="USD",
            cash_dividend_per_share="0.01",
        )

        self.assertEqual(trade_update.quantity, Decimal("9007199254740993.12345678"))
        self.assertEqual(trade_update.model_dump(mode="json")["price"], "1234567890123456.12345678")
        self.assertEqual(cash.model_dump(mode="json")["amount"], "1234567890123456.12")
        self.assertEqual(corporate_action.cash_dividend_per_share, Decimal("0.01"))
        with self.assertRaises(ValidationError):
            PortfolioTradeUpdateRequest(quantity=0.1)
        with self.assertRaises(ValidationError):
            PortfolioCashLedgerCreateRequest(
                account_id=1,
                event_date="2026-01-01",
                direction="in",
                amount=0.1,
            )
        with self.assertRaises(ValidationError):
            PortfolioCorporateActionCreateRequest(
                account_id=1,
                symbol="AAPL",
                effective_date="2026-01-01",
                action_type="split_adjustment",
                split_ratio=0.1,
            )

    def test_snapshot_history_and_fx_responses_preserve_contextual_decimal_text(self) -> None:
        position = PortfolioPositionItem(
            symbol="AAPL",
            market="us",
            currency="USD",
            quantity="9007199254740993.12345678",
            avg_cost="0.00000001",
            total_cost="1234567890123456.12",
            last_price="0.00000001",
            market_value_base="1234567890123456.12",
            unrealized_pnl_base="0.00",
            valuation_currency="USD",
        )
        account = PortfolioAccountSnapshot(
            account_id=1,
            account_name="Main",
            market="us",
            base_currency="USD",
            as_of="2026-01-01",
            cost_method="fifo",
            total_cash="1234567890123456.12",
            total_market_value="0.00",
            total_equity="1234567890123456.12",
            realized_pnl="0.00",
            unrealized_pnl="0.00",
            fee_total="0.00",
            tax_total="0.00",
            fx_stale=False,
            positions=[position],
        )
        history = PortfolioHistorySnapshotItem(
            account_id=1,
            snapshot_date="2026-01-01",
            cost_method="fifo",
            base_currency="USD",
            total_cash="1234567890123456.12",
            total_market_value="0.00",
            total_equity="1234567890123456.12",
            realized_pnl="0.00",
            unrealized_pnl="0.00",
            fee_total="0.00",
            tax_total="0.00",
            fx_stale=False,
        )
        fx_snapshot = PortfolioFxRateItem(
            from_currency="USD",
            to_currency="CNY",
            rate="7.24680000",
            source="manual",
            is_stale=False,
            source_direction="direct",
        )
        live_fx = PortfolioLiveFxRateResponse(
            base_currency="USD",
            quote_currency="CNY",
            rate="7.24680000",
            provider="frankfurter",
            fetched_at="2026-01-01T00:00:00Z",
            cache_hit=False,
            stale=False,
        )

        self.assertEqual(position.model_dump(mode="json")["quantity"], "9007199254740993.12345678")
        self.assertEqual(account.model_dump(mode="json")["total_cash"], "1234567890123456.12")
        self.assertEqual(history.model_dump(mode="json")["total_equity"], "1234567890123456.12")
        self.assertEqual(fx_snapshot.model_dump(mode="json")["rate"], "7.24680000")
        self.assertEqual(live_fx.model_dump(mode="json")["rate"], "7.24680000")

        with self.assertRaises(ValidationError):
            PortfolioPositionItem(**{**position.model_dump(), "quantity": 0.1})
        with self.assertRaises(ValidationError):
            PortfolioAccountSnapshot(**{**account.model_dump(), "total_cash": 0.1})
        with self.assertRaises(ValidationError):
            PortfolioHistorySnapshotItem(**{**history.model_dump(), "total_equity": 0.1})
        with self.assertRaises(ValidationError):
            PortfolioFxRateItem(**{**fx_snapshot.model_dump(), "rate": 0.1})
        with self.assertRaises(ValidationError):
            PortfolioLiveFxRateResponse(**{**live_fx.model_dump(), "rate": 0.1})

    def test_snapshot_analytics_money_preserves_canonical_decimal_text_and_rejects_float(self) -> None:
        high_value = "1234567890123456.12"
        pnl_payload = {
            "amount": high_value,
            "amount_display": f"USD {high_value}",
            "percent": 1.0,
            "currency": "USD",
            "fx_status": "live",
        }
        exposure_payload = {
            "key": "AAPL",
            "label": "AAPL",
            "market_value": high_value,
            "display_value": high_value,
            "display_currency": "USD",
            "percent": 100.0,
            "fx_status": "live",
            "native_value": high_value,
            "native_currency": "USD",
            "unrealized_pnl": "0.01",
        }

        pnl = PortfolioPnlMetric(**pnl_payload)
        exposure = PortfolioExposureItem(**exposure_payload)
        pnl_json = pnl.model_dump(mode="json")
        exposure_json = exposure.model_dump(mode="json")

        with self.subTest(model="pnl", field="amount"):
            self.assertIsInstance(pnl_json["amount"], str)
            self.assertEqual(pnl_json["amount"], high_value)
        for field_name, expected in (
            ("market_value", high_value),
            ("display_value", high_value),
            ("native_value", high_value),
            ("unrealized_pnl", "0.01"),
        ):
            with self.subTest(model="exposure", field=field_name):
                self.assertIsInstance(exposure_json[field_name], str)
                self.assertEqual(exposure_json[field_name], expected)

        with self.subTest(model="pnl", float_field="amount"):
            with self.assertRaises(ValidationError):
                PortfolioPnlMetric(**{**pnl_payload, "amount": 0.1})
        for field_name in ("market_value", "display_value", "native_value", "unrealized_pnl"):
            with self.subTest(model="exposure", float_field=field_name):
                with self.assertRaises(ValidationError):
                    PortfolioExposureItem(**{**exposure_payload, field_name: 0.1})

    def test_snapshot_truth_money_preserves_canonical_decimal_text_and_rejects_float(self) -> None:
        high_value = "1234567890123456.12"
        payload = {
            "as_of": "2026-01-01",
            "cost_method": "fifo",
            "currency": "USD",
            "account_count": 1,
            "total_cash": high_value,
            "total_market_value": "0.00",
            "total_equity": high_value,
            "realized_pnl": "0.00",
            "unrealized_pnl": "0.00",
            "fee_total": "0.00",
            "tax_total": "0.00",
            "fx_stale": False,
            "portfolio_truth": {
                "state": "fully_valued_nonzero",
                "account_state": "holdings_present",
                "valuation_state": "fully_valued",
                "value_semantics": "authoritative_total",
                "authoritative_total": high_value,
                "covered_subtotal": None,
                "account_count": 1,
                "position_count": 1,
            },
        }

        snapshot = PortfolioSnapshotResponse(**payload)
        self.assertEqual(snapshot.model_dump(mode="json")["portfolio_truth"]["authoritative_total"], high_value)

        with self.assertRaises(ValidationError):
            PortfolioSnapshotResponse(
                **{
                    **payload,
                    "portfolio_truth": {
                        **payload["portfolio_truth"],
                        "authoritative_total": 0.1,
                    },
                }
            )

    def test_snapshot_schema_cannot_reexpose_non_authoritative_numeric_totals(self) -> None:
        payload = {
            "as_of": "2026-01-01",
            "cost_method": "fifo",
            "currency": "CNY",
            "account_count": 1,
            "total_cash": "100.00",
            "total_market_value": "200.00",
            "total_equity": "300.00",
            "realized_pnl": "10.00",
            "unrealized_pnl": "20.00",
            "fee_total": "1.00",
            "tax_total": "2.00",
            "fx_stale": False,
            "portfolio_truth": {
                "state": "valuation_unavailable",
                "account_state": "holdings_present",
                "valuation_state": "unavailable",
                "value_semantics": "unavailable",
                "authoritative_total": None,
                "covered_subtotal": None,
                "account_count": 1,
                "position_count": 1,
            },
            "accounts": [
                {
                    "account_id": 1,
                    "account_name": "CNY",
                    "market": "us",
                    "base_currency": "CNY",
                    "as_of": "2026-01-01",
                    "cost_method": "fifo",
                    "total_cash": "100.00",
                    "total_market_value": "200.00",
                    "total_equity": "300.00",
                    "realized_pnl": "10.00",
                    "unrealized_pnl": "20.00",
                    "fee_total": "1.00",
                    "tax_total": "2.00",
                    "fx_stale": False,
                    "availability": {
                        "valuation": {"state": "unavailable"},
                        "performance": {"calculation_state": "unavailable"},
                    },
                    "positions": [],
                }
            ],
        }

        snapshot = PortfolioSnapshotResponse(**payload)
        public = snapshot.model_dump(mode="json")
        for field_name in (
            "total_cash",
            "total_market_value",
            "total_equity",
            "realized_pnl",
            "unrealized_pnl",
            "fee_total",
            "tax_total",
        ):
            self.assertIsNone(public[field_name])
            self.assertIsNone(public["accounts"][0][field_name])


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

    def _save_close(self, symbol: str, on_date: date, close: Decimal) -> None:
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
            "portfolio_truth": {
                "state": "no_account",
                "account_state": "no_account",
                "valuation_state": "not_applicable",
                "value_semantics": "not_applicable",
                "authoritative_total": None,
                "covered_subtotal": None,
                "account_count": 0,
                "position_count": 0,
            },
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
                "amount": "1000.00",
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
                "quantity": "10.00000000",
                "price": "100.00000000",
                "market": "cn",
                "currency": "CNY",
            },
        )
        self._save_close("600519", date(2026, 5, 10), Decimal("100.00"))

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
                "amount": "1000.00",
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
                "quantity": "1.00000000",
                "price": "100.00000000",
                "market": "us",
                "currency": "USD",
            },
        )
        self._save_close("AAPL", date(2026, 5, 10), Decimal("100.00"))

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
                "amount": "1000.00",
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
                "quantity": "10.00000000",
                "price": "100.00000000",
                "market": "cn",
                "currency": "CNY",
            },
        )
        self._save_close("600519", date(2026, 5, 10), Decimal("100.00"))

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


class PortfolioFxRateHttpContractTestCase(unittest.TestCase):
    """HTTP behavioral coverage for the UI-consumed portfolio FX rate routes.

    ``portfolioApi.getFxRate`` reads the cached rate through
    ``GET /api/v1/portfolio/fx-rate`` while ``portfolioApi.refreshFxRate`` mutates the
    provider cache through ``POST /api/v1/portfolio/fx-rate/refresh``. These tests pin
    the authenticated-member boundary, the shared response contract, and the
    read-versus-refresh distinction.
    """

    READ_URL = "/api/v1/portfolio/fx-rate"
    REFRESH_URL = "/api/v1/portfolio/fx-rate/refresh"

    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "portfolio_fx_rate_contract.db"
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
        self.db = DatabaseManager.get_instance()

        self.app = create_app(static_dir=self.data_dir / "empty-static")
        self.client = TestClient(self.app)
        self.anonymous_client = TestClient(self.app)

        login = self.client.post(
            "/api/v1/auth/login",
            json={"password": "fx-rate-admin-pass", "passwordConfirm": "fx-rate-admin-pass"},
        )
        self.assertEqual(login.status_code, 200, login.text)

    def tearDown(self) -> None:
        self.client.close()
        self.anonymous_client.close()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        _reset_auth_globals()
        _reset_public_limiter_state_if_available()
        self.temp_dir.cleanup()

    @staticmethod
    def _rate_payload(*, cache_hit: bool, stale: bool, provider: str = "frankfurter") -> dict:
        return {
            "base_currency": "USD",
            "quote_currency": "CNY",
            "rate": "7.12345678",
            "provider": provider,
            "fetched_at": "2026-09-14T05:00:00",
            "cache_hit": cache_hit,
            "stale": stale,
        }

    def _assert_fx_rate_contract(self, payload: dict, *, cache_hit: bool, stale: bool) -> None:
        # Field names asserted in snake_case exactly as the UI's toCamelCase<PortfolioLiveFxRateResponse> consumes them.
        self.assertEqual(payload["base_currency"], "USD")
        self.assertEqual(payload["quote_currency"], "CNY")
        self.assertEqual(payload["rate"], "7.12345678")
        self.assertEqual(payload["provider"], "frankfurter")
        self.assertEqual(payload["fetched_at"], "2026-09-14T05:00:00")
        self.assertIs(payload["cache_hit"], cache_hit)
        self.assertIs(payload["stale"], stale)
        self.assertIsNone(payload.get("error"))

    def test_fx_rate_routes_require_authenticated_member(self) -> None:
        anonymous_read = self.anonymous_client.get(
            self.READ_URL,
            params={"base": "USD", "quote": "CNY"},
        )
        anonymous_refresh = self.anonymous_client.post(
            self.REFRESH_URL,
            params={"base": "USD", "quote": "CNY"},
        )

        self.assertEqual(anonymous_read.status_code, 401, anonymous_read.text)
        self.assertEqual(anonymous_refresh.status_code, 401, anonymous_refresh.text)

    def test_cached_read_returns_contract_without_force_refresh(self) -> None:
        service = MagicMock()
        service.fetch_rate.return_value = self._rate_payload(cache_hit=True, stale=False)

        with patch("api.v1.endpoints.portfolio.default_fx_rate_service", service):
            response = self.client.get(self.READ_URL, params={"base": "USD", "quote": "CNY"})

        self.assertEqual(response.status_code, 200, response.text)
        self._assert_fx_rate_contract(response.json(), cache_hit=True, stale=False)
        service.fetch_rate.assert_called_once_with("USD", "CNY")

    def test_refresh_is_a_distinct_force_refresh_mutation(self) -> None:
        service = MagicMock()
        service.fetch_rate.return_value = self._rate_payload(cache_hit=False, stale=False)

        with patch("api.v1.endpoints.portfolio.default_fx_rate_service", service):
            response = self.client.post(self.REFRESH_URL, params={"base": "USD", "quote": "CNY"})

        self.assertEqual(response.status_code, 200, response.text)
        self._assert_fx_rate_contract(response.json(), cache_hit=False, stale=False)
        service.fetch_rate.assert_called_once_with("USD", "CNY", force_refresh=True)

    def test_fx_rate_routes_require_bounded_base_and_quote_params(self) -> None:
        missing_quote = self.client.get(self.READ_URL, params={"base": "USD"})
        short_base = self.client.get(self.READ_URL, params={"base": "US", "quote": "CNY"})
        oversized_quote = self.client.get(self.READ_URL, params={"base": "USD", "quote": "C" * 9})

        self.assertEqual(missing_quote.status_code, 422, missing_quote.text)
        self.assertEqual(short_base.status_code, 422, short_base.text)
        self.assertEqual(oversized_quote.status_code, 422, oversized_quote.text)

    def test_fx_rate_maps_unsupported_pair_to_bounded_validation_error(self) -> None:
        service = MagicMock()
        service.fetch_rate.side_effect = ValueError(
            "currency code is unsupported for the Portfolio FX policy"
        )

        with patch("api.v1.endpoints.portfolio.default_fx_rate_service", service):
            read_response = self.client.get(self.READ_URL, params={"base": "USD", "quote": "CNY"})
            refresh_response = self.client.post(
                self.REFRESH_URL,
                params={"base": "USD", "quote": "CNY"},
            )

        for response in (read_response, refresh_response):
            self.assertEqual(response.status_code, 400, response.text)
            # Portfolio errors use a flat consumer-safe envelope rather than a
            # "detail" wrapper, so the UI reads the code from the top level.
            payload = response.json()
            self.assertEqual(payload["error"], "validation_error")
            self.assertEqual(payload["code"], "validation_error")
            self.assertEqual(payload["status"], 400)
            self.assertNotIn("Traceback", response.text)
            self.assertNotIn("provider_url", response.text)

    def test_fx_rate_surfaces_stale_provider_fallback_without_leaking_exception_text(self) -> None:
        service = MagicMock()
        stale_payload = self._rate_payload(cache_hit=True, stale=True)
        stale_payload["error"] = "provider unavailable"
        service.fetch_rate.return_value = stale_payload

        with patch("api.v1.endpoints.portfolio.default_fx_rate_service", service):
            response = self.client.get(self.READ_URL, params={"base": "USD", "quote": "CNY"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["cache_hit"], True)
        self.assertEqual(payload["stale"], True)
        self.assertEqual(payload["error"], "provider unavailable")


if __name__ == "__main__":
    unittest.main()
