# -*- coding: utf-8 -*-
"""Guest analysis preview API coverage."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.app import create_app
from src.config import Config
from src.storage import AnalysisHistory, DatabaseManager, ExecutionLogSession


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


class PublicAnalysisPreviewApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "guest_preview.db"
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
        self.client = TestClient(self.app)
        self.db = DatabaseManager.get_instance()

    def tearDown(self) -> None:
        self.client.close()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def test_guest_preview_is_public_and_does_not_request_persistence(self) -> None:
        captured_query_ids: list[str] = []

        def _mock_analyze_stock(*args, **kwargs):
            captured_query_ids.append(str(kwargs["query_id"]))
            query_id = str(kwargs["query_id"])
            return {
                "query_id": query_id,
                "stock_code": "AAPL",
                "stock_name": "Apple",
                "report": {
                    "meta": {
                        "query_id": query_id,
                        "stock_code": "AAPL",
                        "stock_name": "Apple",
                        "report_type": "brief",
                        "report_language": "en",
                        "created_at": "2026-04-14T09:00:00+00:00",
                        "current_price": 188.2,
                        "change_pct": 1.8,
                        "model_used": "openai/gpt-5.4",
                    },
                    "summary": {
                        "analysis_summary": "Observation only while evidence and risk boundaries are reviewed.",
                        "operation_advice": "Observe only",
                        "trend_prediction": "Constructive but unconfirmed",
                        "sentiment_score": 74,
                        "sentiment_label": "Observation",
                    },
                    "strategy": {
                        "ideal_buy": "Key price area 184-186",
                        "stop_loss": "Risk boundary below 179",
                        "take_profit": "Upper observation area 195-198",
                    },
                    "details": {
                        "standard_report": {"should_not": "leak"},
                    },
                },
            }

        with patch(
            "api.v1.endpoints.analysis._raise_if_llm_model_unavailable",
            return_value=None,
        ), patch(
            "src.services.analysis_service.AnalysisService.analyze_stock",
            side_effect=_mock_analyze_stock,
        ) as analyze_stock:
            response = self.client.post(
                "/api/v1/analysis/preview",
                json={"stock_code": "AAPL", "stock_name": "Apple"},
            )

        self.assertEqual(response.status_code, 200)
        analyze_stock.assert_called_once()
        _, kwargs = analyze_stock.call_args
        self.assertEqual(kwargs["stock_code"], "AAPL")
        self.assertEqual(kwargs["report_type"], "brief")
        self.assertFalse(kwargs["send_notification"])
        self.assertFalse(kwargs["persist_history"])
        self.assertTrue(kwargs["query_id"].startswith("guest:"))
        self.assertTrue(self.client.cookies.get("wolfystock_guest_session"))
        self.assertRegex(kwargs["guest_bucket_hash"], r"^[a-f0-9]{64}$")
        self.assertNotIn(str(self.client.cookies.get("wolfystock_guest_session")), kwargs["guest_bucket_hash"])

        payload = response.json()
        self.assertEqual(payload["preview_scope"], "guest")
        self.assertEqual(payload["stock_code"], "AAPL")
        self.assertEqual(payload["stock_name"], "Apple")
        self.assertEqual(
            payload["report"]["summary"]["analysis_summary"],
            "研究摘要：公开预览仅保留观察性信息，完整研究需登录后查看。",
        )
        self.assertNotIn("details", payload["report"])
        self.assertEqual(payload["query_id"], captured_query_ids[0])
        public_values = "\n".join(
            str(value)
            for section in (
                payload["report"]["summary"],
                payload["report"].get("strategy") or {},
            )
            for value in section.values()
        ).lower()
        for forbidden in (
            "buy now",
            "sell now",
            "wait for pullback",
            "stop loss",
            "take profit",
            "target price",
            "trading advice",
            "investment advice",
        ):
            self.assertNotIn(forbidden, public_values)
        self.assertIn("observation", public_values)

        with self.db.get_session() as session:
            self.assertEqual(session.query(AnalysisHistory).count(), 0)
            log_row = session.query(ExecutionLogSession).filter_by(code="AAPL").one()
            log_summary = json.loads(log_row.summary_json or "{}")
            self.assertEqual(log_row.task_id, payload["query_id"])
            self.assertEqual(log_row.overall_status, "success")
            self.assertEqual(log_summary["meta"]["actor_role"], "guest")
            self.assertEqual(log_summary["meta"]["actor_type"], "guest")
            self.assertEqual(log_summary["meta"]["actor_session_id"], self.client.cookies.get("wolfystock_guest_session"))
            self.assertEqual(log_summary["business_event"]["symbol"], "AAPL")

    def test_guest_preview_uses_isolated_anonymous_session_ids_without_persisting_history(self) -> None:
        captured_query_ids: list[str] = []

        def _mock_analyze_stock(*args, **kwargs):
            captured_query_ids.append(str(kwargs["query_id"]))
            query_id = str(kwargs["query_id"])
            return {
                "query_id": query_id,
                "stock_code": "AAPL",
                "stock_name": "Apple",
                "report": {
                    "meta": {
                        "query_id": query_id,
                        "stock_code": "AAPL",
                        "stock_name": "Apple",
                        "report_type": "brief",
                        "report_language": "en",
                        "created_at": "2026-04-14T09:00:00+00:00",
                        "current_price": 188.2,
                        "change_pct": 1.8,
                        "model_used": "openai/gpt-5.4",
                    },
                    "summary": {
                        "analysis_summary": "Preview summary",
                        "operation_advice": "Observe only",
                        "trend_prediction": "Constructive but unconfirmed",
                        "sentiment_score": 74,
                        "sentiment_label": "Observation",
                    },
                    "strategy": {
                        "ideal_buy": "Key price area 184-186",
                        "stop_loss": "Risk boundary below 179",
                        "take_profit": "Upper observation area 195-198",
                    },
                    "details": {
                        "standard_report": {"should_not": "leak"},
                    },
                },
            }

        other_client = TestClient(self.app)
        try:
            with patch(
                "api.v1.endpoints.analysis._raise_if_llm_model_unavailable",
                return_value=None,
            ), patch(
                "src.services.analysis_service.AnalysisService.analyze_stock",
                side_effect=_mock_analyze_stock,
            ):
                first_response = self.client.post(
                    "/api/v1/analysis/preview",
                    json={"stock_code": "AAPL", "stock_name": "Apple"},
                )
                second_response = self.client.post(
                    "/api/v1/analysis/preview",
                    json={"stock_code": "AAPL", "stock_name": "Apple"},
                )
                third_response = other_client.post(
                    "/api/v1/analysis/preview",
                    json={"stock_code": "AAPL", "stock_name": "Apple"},
                )

            self.assertEqual(first_response.status_code, 200)
            self.assertEqual(second_response.status_code, 200)
            self.assertEqual(third_response.status_code, 200)
            self.assertEqual(len(captured_query_ids), 3)

            first_session = captured_query_ids[0].split(":")[1]
            second_session = captured_query_ids[1].split(":")[1]
            third_session = captured_query_ids[2].split(":")[1]

            self.assertEqual(first_session, second_session)
            self.assertNotEqual(first_session, third_session)
            self.assertEqual(self.client.cookies.get("wolfystock_guest_session"), first_session)
            self.assertEqual(other_client.cookies.get("wolfystock_guest_session"), third_session)

            with self.db.get_session() as session:
                self.assertEqual(session.query(AnalysisHistory).count(), 0)
        finally:
            other_client.close()

    def test_guest_preview_returns_actionable_model_unavailable_error_without_calling_analysis(self) -> None:
        with patch(
            "api.v1.endpoints.analysis._build_llm_model_unavailable_detail",
            return_value={
                "error": "llm_model_unavailable",
                "message": "配置的模型不可用。当前可用模型：openai/gpt-4.1-free, openai/gpt-4o-free",
                "configured_model": "openai/gpt-5-ghost",
                "available_models": ["openai/gpt-4.1-free", "openai/gpt-4o-free"],
            },
        ), patch("src.services.analysis_service.AnalysisService.analyze_stock") as analyze_stock:
            response = self.client.post(
                "/api/v1/analysis/preview",
                json={"stock_code": "AAPL", "stock_name": "Apple"},
            )

        self.assertEqual(response.status_code, 500)
        analyze_stock.assert_not_called()
        payload = response.json()
        detail = payload.get("detail", payload)
        self.assertEqual(detail["error"], "llm_model_unavailable")
        self.assertEqual(detail["message"], "公开分析预览暂时不可用，请稍后重试。")
        serialized = json.dumps(payload, ensure_ascii=False)
        for forbidden in (
            "openai/gpt-5-ghost",
            "openai/gpt-4.1-free",
            "openai/gpt-4o-free",
            "configured_model",
            "available_models",
            "LITELLM_MODEL",
            "LLM_CHANNELS",
            "LITELLM_CONFIG",
        ):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
