# -*- coding: utf-8 -*-
"""Admin user activity timeline API contract tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from api.v1.schemas.admin_activity import AdminActivityResponse
from src.auth import is_auth_enabled
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID
from src.storage import AnalysisHistory, DatabaseManager


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
    )


class AdminUserActivityApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "admin_user_activity.db"
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")

        from api.v1.endpoints import admin_users

        self.app = FastAPI()
        self.app.include_router(admin_users.router, prefix="/api/v1/admin")
        self.client = TestClient(self.app)
        self.now = datetime.now()
        self._seed_users_and_activity()

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        DatabaseManager.reset_instance()
        self.temp_dir.cleanup()

    def _seed_users_and_activity(self) -> None:
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
            display_name="Alice",
            role="user",
            password_hash="pbkdf2:user-secret-hash",
            is_active=True,
        )
        self.db.create_or_update_app_user(
            user_id="user-2",
            username="bob",
            display_name="Bob",
            role="user",
            password_hash="pbkdf2:bob-secret-hash",
            is_active=True,
        )
        with self.db.get_session() as session:
            session.add_all(
                [
                    AnalysisHistory(
                        owner_id="user-1",
                        query_id="raw-query-user-1",
                        code="AAPL",
                        name="Apple",
                        report_type="standard",
                        analysis_summary="Safe summary with token=secret-token-value",
                        raw_result="RAW_RESULT_SHOULD_NOT_LEAK",
                        news_content="NEWS_CONTENT_SHOULD_NOT_LEAK",
                        context_snapshot="CONTEXT_SNAPSHOT_SHOULD_NOT_LEAK",
                        created_at=self.now - timedelta(hours=1),
                    ),
                    AnalysisHistory(
                        owner_id="user-2",
                        query_id="raw-query-user-2",
                        code="MSFT",
                        name="Microsoft",
                        report_type="standard",
                        analysis_summary="Other user summary",
                        raw_result="OTHER_RAW_RESULT_SHOULD_NOT_LEAK",
                        news_content="OTHER_NEWS_CONTENT_SHOULD_NOT_LEAK",
                        context_snapshot="OTHER_CONTEXT_SNAPSHOT_SHOULD_NOT_LEAK",
                        created_at=self.now - timedelta(hours=1),
                    ),
                ]
            )
            session.commit()

        self.db.create_execution_log_session(
            session_id="raw-exec-session-user-1",
            task_id="analysis-user-1",
            query_id="raw-query-user-1",
            code="AAPL",
            name="Apple",
            overall_status="completed",
            truth_level="actual",
            summary={
                "business_event": {
                    "category": "analysis",
                    "type": "analysis.completed",
                    "status": "success",
                    "userId": "user-1",
                    "summary": "Completed AAPL request Authorization: Bearer raw-token-value",
                    "requestId": "raw-request-id-user-1",
                }
            },
            started_at=self.now - timedelta(minutes=30),
        )
        self.db.append_execution_log_event(
            session_id="raw-exec-session-user-1",
            phase="analysis",
            step="completed",
            target="AAPL",
            status="completed",
            truth_level="actual",
            message="stack_trace=RAW_STACK_TRACE request_body=RAW_REQUEST_BODY",
            detail={
                "category": "analysis",
                "event_name": "AnalysisCompleted",
                "api_key": "raw-api-key",
                "provider_payload": "RAW_PROVIDER_PAYLOAD",
            },
            event_at=self.now - timedelta(minutes=30),
        )
        self.db.finalize_execution_log_session(
            session_id="raw-exec-session-user-1",
            overall_status="completed",
            truth_level="actual",
            summary={
                "business_event": {
                    "category": "analysis",
                    "type": "analysis.completed",
                    "status": "success",
                    "userId": "user-1",
                    "summary": "Completed AAPL request Authorization: Bearer raw-token-value",
                    "requestId": "raw-request-id-user-1",
                }
            },
            ended_at=self.now - timedelta(minutes=29),
        )

    def _as_admin(self) -> None:
        self.app.dependency_overrides[get_current_user] = _admin_user

    def _as_user(self) -> None:
        self.app.dependency_overrides[get_current_user] = _regular_user

    @staticmethod
    def _json_text(response) -> str:
        return json.dumps(response.json(), ensure_ascii=False)

    def test_admin_required_for_activity_routes(self) -> None:
        unauthenticated = self.client.get("/api/v1/admin/users/user-1/activity")
        self.assertEqual(unauthenticated.status_code, 401 if is_auth_enabled() else 200)

        self._as_user()
        forbidden = self.client.get("/api/v1/admin/activity")
        self.assertEqual(forbidden.status_code, 403)

    def test_user_targeted_timeline_is_scoped_and_redacted(self) -> None:
        self._as_admin()
        response = self.client.get(
            "/api/v1/admin/users/user-1/activity",
            params={"include_admin": "false", "include_system": "false", "limit": 20},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["total"], 1)
        self.assertTrue(all(item["targetUser"]["id"] == "user-1" for item in payload["items"]))
        self.assertIn("analysis", {item["family"] for item in payload["items"]})

        text = self._json_text(response)
        self.assertIn("AAPL", text)
        self.assertNotIn("MSFT", text)
        self.assertNotIn("raw-exec-session-user-1", text)
        self.assertNotIn("raw-request-id-user-1", text)
        self.assertNotIn("raw-token-value", text)
        self.assertNotIn("pbkdf2:user-secret-hash", text)
        self.assertNotIn("RAW_RESULT_SHOULD_NOT_LEAK", text)
        self.assertNotIn("NEWS_CONTENT_SHOULD_NOT_LEAK", text)
        self.assertNotIn("CONTEXT_SNAPSHOT_SHOULD_NOT_LEAK", text)
        self.assertNotIn("RAW_PROVIDER_PAYLOAD", text)
        self.assertNotIn("RAW_STACK_TRACE", text)
        self.assertNotIn("RAW_REQUEST_BODY", text)

    def test_global_timeline_filters_and_limit_validation(self) -> None:
        self._as_admin()
        response = self.client.get(
            "/api/v1/admin/activity",
            params={"target_user": "user-1", "family": "analysis", "status": "success", "entity_type": "analysis_history"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["total"], 1)
        self.assertTrue(all(item["targetUser"]["id"] == "user-1" for item in payload["items"]))
        self.assertTrue(all(item["family"] == "analysis" for item in payload["items"]))

        over_limit = self.client.get("/api/v1/admin/activity", params={"limit": 101})
        self.assertEqual(over_limit.status_code, 422)

    def test_user_route_rejects_mismatched_target_user_filter(self) -> None:
        self._as_admin()
        response = self.client.get("/api/v1/admin/users/user-1/activity", params={"target_user": "user-2"})
        self.assertEqual(response.status_code, 400)

    def test_endpoint_validates_service_read_models_into_api_schema(self) -> None:
        self._as_admin()
        service_items = [
            {
                "id": "sha256:event-1",
                "timestamp": self.now.isoformat(),
                "actor": {"type": "user", "user_id": "user-1"},
                "target_user": {"id": "user-1", "label": None},
                "family": "analysis",
                "action": "analysis.completed",
                "entity": {
                    "type": "analysis_history",
                    "id_hash": "sha256:entity-1",
                    "label": "AAPL standard",
                    "symbol": "AAPL",
                    "source_table": "analysis_history",
                },
                "status": "success",
                "outcome": "ok",
                "request_id_hash": "sha256:request-1",
                "session_id_hash": None,
                "source": {"kind": "analysis_history", "table": "analysis_history", "confidence": "confirmed"},
                "redacted_metadata": {"reportType": "standard"},
                "log_links": [],
            }
        ]

        with patch("api.v1.endpoints.admin_users.AdminActivityService.list_activity", return_value=(service_items, 1)):
            response = self.client.get("/api/v1/admin/users/user-1/activity")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            AdminActivityResponse.model_validate(payload).model_dump(by_alias=True),
            payload,
        )
        self.assertEqual(payload["items"][0]["actor"]["userId"], "user-1")
        self.assertEqual(payload["items"][0]["targetUser"]["id"], "user-1")
        self.assertEqual(payload["items"][0]["entity"]["idHash"], "sha256:entity-1")
        self.assertEqual(payload["items"][0]["source"]["kind"], "analysis_history")


if __name__ == "__main__":
    unittest.main()
