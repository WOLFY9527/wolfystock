# -*- coding: utf-8 -*-
"""Admin duplicate-cost summary API contract tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID
from src.services.llm_instrumentation import (
    emit_llm_event,
    emit_market_cache_event,
    emit_provider_event,
    emit_scanner_ai_event,
    reset_llm_event_counters,
    snapshot_llm_event_counters,
)
from src.storage import DatabaseManager
from src.services.llm_cost_ledger_service import LlmCostLedgerService


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
        admin_capabilities=("cost:observability:read",),
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


def _admin_without_cost_capability() -> CurrentUser:
    return CurrentUser(
        user_id=BOOTSTRAP_ADMIN_USER_ID,
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=("users:read",),
    )


class AdminCostSummaryApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        reset_llm_event_counters()
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "admin_cost.db"
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")

        from api.v1.endpoints import admin_cost

        self.app = FastAPI()
        self.app.include_router(admin_cost.router, prefix="/api/v1/admin")
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        reset_llm_event_counters()
        DatabaseManager.reset_instance()
        self.temp_dir.cleanup()

    def _as_admin(self) -> None:
        self.app.dependency_overrides[get_current_user] = _admin_user

    def _as_user(self) -> None:
        self.app.dependency_overrides[get_current_user] = _regular_user

    def _as_admin_without_cost_capability(self) -> None:
        self.app.dependency_overrides[get_current_user] = _admin_without_cost_capability

    @staticmethod
    def _json_text(payload) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def _seed_counters(self) -> None:
        emit_llm_event(
            "llm_call_started",
            call_type="analysis",
            provider="gemini",
            model_family="gemini/gemini-2.5-flash",
            route="analysis",
            raw_prompt="do not leak this prompt",
        )
        emit_llm_event(
            "llm_integrity_retry",
            call_type="analysis",
            report_type="standard",
            language="zh-CN",
            retry_reason="JSON parse failed",
            stack_trace="Traceback should not leak",
        )
        emit_provider_event(
            "provider_cache_hit",
            provider="fmp",
            provider_category="fundamentals",
            market="US",
            cache_key_hash="ABCDEF1234567890",
            url="https://provider.example.com/path?apikey=secret",
        )
        emit_provider_event(
            "provider_cache_miss",
            provider="fmp",
            provider_category="fundamentals",
            market="US",
            cache_key_hash="ABCDEF1234567890",
            raw_cache_key="AAPL:fundamentals",
        )
        emit_provider_event(
            "provider_fallback_attempt",
            provider_category="fundamentals",
            market="US",
            fallback_depth=1,
            retry_reason_bucket="timeout from raw URL",
        )
        emit_provider_event(
            "provider_duplicate_candidate_observed",
            provider="fmp",
            provider_category="fundamentals",
            market="US",
            cache_key_hash="ABCDEF1234567890",
        )
        emit_market_cache_event(
            "market_cache_hit",
            panel_key="indices",
            endpoint_family="market_overview",
            cache_key_hash="0011223344556677",
        )
        emit_market_cache_event(
            "market_cache_stale_served",
            panel_key="indices",
            endpoint_family="market_overview",
            cache_key_hash="0011223344556677",
        )
        emit_scanner_ai_event(
            "scanner_ai_interpretation_started",
            market="CN",
            profile="cn_preopen_v1",
            rank_bucket="top_3",
            top_n=3,
            candidate_hash="FACEBEEF1234",
            raw_candidate_payload={"symbol": "600001"},
        )
        emit_scanner_ai_event(
            "scanner_ai_duplicate_candidate_observed",
            market="CN",
            profile="cn_preopen_v1",
            candidate_hash="FACEBEEF1234",
        )

    def test_duplicate_summary_requires_cost_observability_capability(self) -> None:
        response = self.client.get("/api/v1/admin/cost/duplicate-summary")
        self.assertEqual(response.status_code, 401)

        self._as_user()
        forbidden = self.client.get("/api/v1/admin/cost/duplicate-summary")
        self.assertEqual(forbidden.status_code, 403)

        self._as_admin_without_cost_capability()
        missing_capability = self.client.get("/api/v1/admin/cost/duplicate-summary")
        self.assertEqual(missing_capability.status_code, 403)
        self.assertEqual(missing_capability.json()["detail"]["error"], "admin_capability_required")
        denial_text = missing_capability.text.lower()
        for forbidden_marker in ("cost:observability:read", "raw-session", "cookie", "token", "secret", ".env"):
            self.assertNotIn(forbidden_marker, denial_text)

    def test_summary_returns_safe_sections_and_metadata(self) -> None:
        self._as_admin()
        self._seed_counters()
        before_snapshot = snapshot_llm_event_counters()

        with patch("src.services.duplicate_cost_summary_service.DatabaseManager.get_instance", return_value=self.db):
            response = self.client.get("/api/v1/admin/cost/duplicate-summary")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["metadata"]["readOnly"], True)
        self.assertEqual(payload["metadata"]["noExternalCalls"], True)
        self.assertEqual(payload["metadata"]["countersSource"], "process_local")
        self.assertEqual(payload["metadata"]["exactness"], "observational_not_billing")
        self.assertIn("process_local_counters", payload["metadata"]["dataSources"])
        self.assertEqual(payload["summary"]["llmCalls"], 1)
        self.assertEqual(payload["summary"]["estimatedDuplicateCandidates"], 2)
        self.assertEqual(payload["summary"]["providerCacheHits"], 1)
        self.assertEqual(payload["summary"]["providerCacheMisses"], 1)
        self.assertEqual(payload["summary"]["marketCacheHits"], 1)
        self.assertEqual(payload["summary"]["marketCacheStaleServed"], 1)
        self.assertIn("byCallType", payload["llm"])
        self.assertIn("cacheEfficiency", payload["providers"])
        self.assertIn("byPanelKey", payload["marketCache"])
        self.assertIn("interpretations", payload["scannerAi"])
        self.assertEqual(snapshot_llm_event_counters(), before_snapshot)

    def test_response_does_not_expose_unsafe_fields_or_raw_values(self) -> None:
        self._as_admin()
        self._seed_counters()

        with patch("src.services.duplicate_cost_summary_service.DatabaseManager.get_instance", return_value=self.db):
            response = self.client.get("/api/v1/admin/cost/duplicate-summary")

        text = self._json_text(response.json()).lower()
        blocked = [
            "raw_prompt",
            "do not leak",
            "raw_cache_key",
            "aapl:fundamentals",
            "raw_candidate_payload",
            "600001",
            "apikey",
            "secret",
            "traceback",
            "provider.example.com",
        ]
        for value in blocked:
            self.assertNotIn(value, text)

    def test_area_filter_and_limit_are_bounded(self) -> None:
        self._as_admin()
        self._seed_counters()

        with patch("src.services.duplicate_cost_summary_service.DatabaseManager.get_instance", return_value=self.db):
            llm_only = self.client.get(
                "/api/v1/admin/cost/duplicate-summary",
                params={"area": "llm", "bucket": "day", "window": "7d", "limit": 1},
            )
            invalid_area = self.client.get("/api/v1/admin/cost/duplicate-summary", params={"area": "portfolio"})
            over_limit = self.client.get("/api/v1/admin/cost/duplicate-summary", params={"limit": 201})
            invalid_window = self.client.get("/api/v1/admin/cost/duplicate-summary", params={"window": "365d"})

        self.assertEqual(llm_only.status_code, 200)
        payload = llm_only.json()
        self.assertEqual(payload["window"]["bucket"], "day")
        self.assertEqual(payload["metadata"]["requestedArea"], "llm")
        self.assertLessEqual(len(payload["llm"]["byCallType"]), 1)
        self.assertEqual(invalid_area.status_code, 400)
        self.assertEqual(over_limit.status_code, 422)
        self.assertEqual(invalid_window.status_code, 400)

    def test_endpoint_does_not_call_runtime_or_external_work(self) -> None:
        self._as_admin()
        self._seed_counters()

        def forbidden(*_args, **_kwargs):
            raise AssertionError("forbidden runtime work was called")

        with (
            patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
            patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
            patch("src.services.scanner_ai_service.ScannerAiInterpretationService.interpret_shortlist", side_effect=forbidden),
            patch("src.services.duplicate_cost_summary_service.DatabaseManager.get_instance", return_value=self.db),
        ):
            response = self.client.get("/api/v1/admin/cost/duplicate-summary")

        self.assertEqual(response.status_code, 200)

    def test_llm_ledger_summary_returns_read_only_safe_rollups(self) -> None:
        self._as_admin()
        self.db.upsert_model_pricing_policy(
            policy_key="sample-openai-mini",
            provider="openai",
            model="openai/gpt-4o-mini",
            pricing_unit="per_1m_tokens",
            input_price_per_1m=0.1,
            cached_input_price_per_1m=0.05,
            output_price_per_1m=0.4,
            currency="USD",
        )
        service = LlmCostLedgerService(db=self.db)
        service.reconcile_usage(
            owner_user_id="user-a",
            route_family="analysis",
            call_type="analysis",
            provider="openai",
            model="openai/gpt-4o-mini",
            prompt_tokens=1_000,
            completion_tokens=1_000,
            total_tokens=2_000,
            metadata={"prompt": "do not leak", "safe_label": "ok"},
        )

        with patch("src.services.llm_cost_ledger_service.DatabaseManager.get_instance", return_value=self.db):
            response = self.client.get("/api/v1/admin/cost/llm-ledger-summary")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["metadata"]["readOnly"], True)
        self.assertEqual(payload["metadata"]["liveEnforcement"], False)
        self.assertEqual(payload["total"]["totalTokens"], 2_000)
        self.assertEqual(payload["byUser"][0]["dimensions"]["owner_user_id"], "user-a")
        self.assertEqual(payload["byProviderModel"][0]["dimensions"]["provider"], "openai")
        text = self._json_text(payload).lower()
        self.assertNotIn("do not leak", text)
        self.assertNotIn("secret", text)

    def test_llm_ledger_summary_requires_cost_observability_capability(self) -> None:
        response = self.client.get("/api/v1/admin/cost/llm-ledger-summary")
        self.assertEqual(response.status_code, 401)

        self._as_user()
        forbidden = self.client.get("/api/v1/admin/cost/llm-ledger-summary")
        self.assertEqual(forbidden.status_code, 403)

        self._as_admin_without_cost_capability()
        missing_capability = self.client.get("/api/v1/admin/cost/llm-ledger-summary")
        self.assertEqual(missing_capability.status_code, 403)
        self.assertEqual(missing_capability.json()["detail"]["error"], "admin_capability_required")

    def test_model_pricing_policies_returns_read_only_sanitized_rows(self) -> None:
        self._as_admin()
        self.db.upsert_model_pricing_policy(
            policy_key="active-openai-mini",
            provider="openai",
            model="openai/gpt-4o-mini",
            pricing_unit="per_1m_tokens",
            input_price_per_1m=0.1,
            cached_input_price_per_1m=0.05,
            output_price_per_1m=0.4,
            currency="USD",
            source_label="OpenAI pricing page",
            source_url="https://openai.com/api/pricing/?token=secret",
            metadata={"api_key": "should-not-leak", "notes": "safe"},
            active=True,
        )
        self.db.upsert_model_pricing_policy(
            policy_key="inactive-deepseek-chat",
            provider="deepseek",
            model="deepseek/deepseek-chat",
            pricing_unit="per_1m_tokens",
            input_price_per_1m=0.05,
            cached_input_price_per_1m=None,
            output_price_per_1m=0.2,
            currency="USD",
            source_label="DeepSeek pricing page",
            source_url="file:///tmp/unsafe",
            metadata={"raw_provider_payload": "should-not-leak"},
            active=False,
        )

        with patch("api.v1.endpoints.admin_cost.DatabaseManager.get_instance", return_value=self.db):
            response = self.client.get("/api/v1/admin/cost/model-pricing-policies")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["metadata"]["readOnly"], True)
        self.assertEqual(payload["metadata"]["noExternalCalls"], True)
        self.assertEqual(payload["metadata"]["liveEnforcement"], False)
        self.assertEqual(payload["metadata"]["manualMaintenance"], True)
        self.assertEqual(payload["activeCount"], 1)
        self.assertEqual(len(payload["policies"]), 2)
        active = payload["policies"][0]
        inactive = payload["policies"][1]
        self.assertEqual(active["provider"], "openai")
        self.assertEqual(active["model"], "openai/gpt-4o-mini")
        self.assertEqual(active["inputPricePer1m"], "0.10000000")
        self.assertEqual(active["cachedInputPricePer1m"], "0.05000000")
        self.assertEqual(active["outputPricePer1m"], "0.40000000")
        self.assertEqual(active["sourceUrl"], "https://openai.com/api/pricing/?token=***")
        self.assertEqual(inactive["active"], False)
        self.assertIsNone(inactive["sourceUrl"])
        text = self._json_text(payload).lower()
        self.assertNotIn("should-not-leak", text)
        self.assertNotIn("policy_key", text)
        self.assertNotIn("metadata_json", text)
        self.assertNotIn("token=secret", text)

    def test_model_pricing_policies_requires_cost_observability_capability(self) -> None:
        response = self.client.get("/api/v1/admin/cost/model-pricing-policies")
        self.assertEqual(response.status_code, 401)

        self._as_user()
        forbidden = self.client.get("/api/v1/admin/cost/model-pricing-policies")
        self.assertEqual(forbidden.status_code, 403)

        self._as_admin_without_cost_capability()
        missing_capability = self.client.get("/api/v1/admin/cost/model-pricing-policies")
        self.assertEqual(missing_capability.status_code, 403)
        self.assertEqual(missing_capability.json()["detail"]["error"], "admin_capability_required")


if __name__ == "__main__":
    unittest.main()
