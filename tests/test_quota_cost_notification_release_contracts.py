# -*- coding: utf-8 -*-
"""Release safety contracts for quota, cost, and notification behavior."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from data_provider.base import DataFetcherManager
from src.services.llm_cost_ledger_service import LlmCostLedgerService
from src.services.notification_service import NotificationDeliveryClient, NotificationService
from src.services.quota_policy_service import QuotaPolicyService
from src.storage import DatabaseManager, LLMCostLedger, QuotaReservation, QuotaUsageWindow


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "quota_cost_notification_release_audit.py"


class FakeDeliveryClient(NotificationDeliveryClient):
    def __init__(self, *, fail: bool = False, failure_message: str = "mock webhook failure") -> None:
        self.fail = fail
        self.failure_message = failure_message
        self.webhook_calls: list[dict] = []

    def send_webhook(self, *, url: str, payload: dict, headers: dict | None = None, timeout: float = 5.0) -> None:
        self.webhook_calls.append({"url": url, "payload": payload, "headers": headers or {}, "timeout": timeout})
        if self.fail:
            raise RuntimeError(self.failure_message)


def _fresh_db() -> DatabaseManager:
    DatabaseManager.reset_instance()
    return DatabaseManager(db_url="sqlite:///:memory:")


def _counts(db: DatabaseManager) -> dict[str, int]:
    with db.session_scope() as session:
        return {
            "reservations": session.query(QuotaReservation).count(),
            "windows": session.query(QuotaUsageWindow).count(),
            "ledger": session.query(LLMCostLedger).count(),
        }


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("quota_cost_notification_release_audit", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_audit_cli_offline_outputs_bounded_json_contract() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--offline"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert set(payload) == {
        "schemaVersion",
        "status",
        "quotaPosture",
        "costPosture",
        "notificationPosture",
        "liveCallsExecuted",
        "notificationsSent",
        "manualReviewRequired",
    }
    assert payload["liveCallsExecuted"] is False
    assert payload["notificationsSent"] is False
    assert payload["manualReviewRequired"] is True
    assert payload["quotaPosture"]["dryRunNoSpend"] is True
    assert payload["costPosture"]["missingPricingPolicyNoSpend"] is True
    assert payload["notificationPosture"]["noChannelsNoSend"] is True
    assert payload["notificationPosture"]["dryRunNoSend"] is True
    assert payload["notificationPosture"]["deliveryCalls"] == 0
    payload_text = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
    for unsupported_claim in ("durable", "outbox", "retry", "exactly_once", "exactly-once"):
        assert unsupported_claim not in payload_text
    assert "must-not-leak" not in result.stdout.lower()


def test_audit_default_cli_remains_offline_without_live_paths() -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("live path should not be called by release audit")

    audit = _load_audit_module()
    with (
        patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
        patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
        patch("src.services.scanner_ai_service.ScannerAiInterpretationService.interpret_shortlist", side_effect=forbidden),
        patch("src.services.llm_cost_ledger_service.LlmCostLedgerService.preflight_invoice_reconciliation", side_effect=forbidden),
        patch("src.services.notification_service.NotificationService._deliver_to_channel", side_effect=forbidden),
        patch("src.services.notification_service.NotificationDeliveryClient.send_webhook", side_effect=forbidden),
        patch("src.services.notification_service.SystemNotificationService.send", side_effect=forbidden),
        patch("urllib.request.urlopen", side_effect=forbidden),
    ):
        payload = audit.run_offline_audit()

    assert payload["liveCallsExecuted"] is False
    assert payload["notificationsSent"] is False
    assert payload["notificationPosture"]["deliveryCalls"] == 0
    assert payload["quotaPosture"]["dryRunNoSpend"] is True
    assert payload["notificationPosture"]["dryRunNoSend"] is True


def test_quota_cost_contracts_are_dry_run_bounded_and_fail_safe() -> None:
    db = _fresh_db()
    quota = QuotaPolicyService(db=db)
    db.upsert_quota_policy(
        policy_key="negative-hard-limit",
        scope_type="user",
        daily_budget_units=-1,
        metadata={"daily_soft_limit_units": -5},
    )

    before = _counts(db)
    preflight = quota.classify_shadow_preflight(
        owner_user_id="owner-1",
        route_family="invalid-route-family",
        estimated_units=-100,
    )
    after = _counts(db)

    assert before == after
    assert preflight.route_family == "analysis"
    assert preflight.budget_alert.estimated_units == 1
    assert preflight.would_block is True
    assert preflight.reason_code == "budget_hard_limit_exceeded"

    cost = LlmCostLedgerService(db=db)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("live provider path should not be called by cost calculation")

    with (
        patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
        patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
        patch("src.services.scanner_ai_service.ScannerAiInterpretationService.interpret_shortlist", side_effect=forbidden),
    ):
        result = cost.calculate_cost(
            provider="missing-provider",
            model="missing-model",
            prompt_tokens=500,
            completion_tokens=250,
            route_family="analysis",
            call_type="analysis",
        )

    assert result.status == "pricing_unknown"
    assert result.total_cost_usd == 0
    assert _counts(db)["ledger"] == 0
    DatabaseManager.reset_instance()


def test_provider_retry_loop_is_bounded_by_configured_attempts() -> None:
    manager = DataFetcherManager.__new__(DataFetcherManager)
    calls = {"count": 0}

    def fake_timeout(_task, _remaining_seconds, _task_name):
        calls["count"] += 1
        return None, "provider failed", 0

    manager._get_fundamental_config = lambda: SimpleNamespace(fundamental_retry_max=3)
    manager._run_with_timeout = fake_timeout

    result, error, duration_ms = manager._run_with_retry(lambda: None, 10.0, "release-contract")

    assert result is None
    assert error == "provider failed"
    assert duration_ms == 0
    assert calls["count"] == 3

    calls["count"] = 0
    manager._get_fundamental_config = lambda: SimpleNamespace(fundamental_retry_max=-10)

    manager._run_with_retry(lambda: None, 10.0, "release-contract")

    assert calls["count"] == 1


def test_notification_contracts_do_not_send_on_no_channel_dry_run_or_failure() -> None:
    db = _fresh_db()
    delivery = FakeDeliveryClient()
    service = NotificationService(db=db, delivery_client=delivery)

    no_channel_event = service.emit_event(
        event_type="release.notification_safety",
        severity="warning",
        title="Release notification safety",
        message="No configured channel should stay local",
        payload={"dry_run": True},
        fingerprint="release:no-channel",
    )
    assert no_channel_event["delivery_status"] == "no_channels"
    assert delivery.webhook_calls == []

    channel = service.create_channel(
        name="release webhook dry-run",
        type="webhook",
        enabled=True,
        severity_min="warning",
        event_types=["release.notification_safety"],
        config={"webhook_url": "https://hooks.example.test/services/must-not-leak", "token": "must-not-leak"},
    )
    with (
        patch("src.services.notification_service.NotificationService._deliver_to_channel", side_effect=AssertionError("dry-run should not dispatch delivery")),
        patch("src.services.notification_service.NotificationDeliveryClient.send_webhook", side_effect=AssertionError("dry-run should not send webhook")),
        patch("src.services.notification_service.SystemNotificationService.send", side_effect=AssertionError("dry-run should not send system notification")),
    ):
        dry_run = service.test_channel(channel["id"], dry_run=True)
    assert dry_run["success"] is True
    assert dry_run["dry_run"] is True
    assert dry_run["target_summary"] == "webhook:configured"
    assert delivery.webhook_calls == []
    assert dry_run["channel"]["last_tested_at"] is not None
    assert dry_run["channel"]["last_sent_at"] is None
    assert dry_run["channel"]["last_triggered_at"] is None

    duplicate = service.emit_event(
        event_type="release.notification_safety",
        severity="warning",
        title="Repeated release notification safety",
        message="Repeated no-channel event should reuse the best-effort dedupe window",
        payload={"dry_run": True},
        fingerprint="release:no-channel",
    )
    assert duplicate["id"] == no_channel_event["id"]
    assert duplicate["deduped"] is True
    assert service.list_events(event_type="release.notification_safety")["total"] == 1
    assert delivery.webhook_calls == []

    failing = NotificationService(
        db=db,
        delivery_client=FakeDeliveryClient(
            fail=True,
            failure_message=(
                "Traceback token=must-not-leak password=must-not-leak "
                "email=operator@example.com https://hooks.example.test/services/must-not-leak"
            ),
        ),
    )
    failed_event = failing.emit_event(
        event_type="release.notification_safety",
        severity="critical",
        title="Release notification failure",
        message="Failure must not break core flow",
        payload={"token": "must-not-leak", "email_payload": "operator@example.com"},
        fingerprint="release:failed-send",
    )
    combined = f"{failed_event} {failing.list_channels()}"

    assert failed_event["delivery_status"] == "failed"
    assert "must-not-leak" not in combined
    assert "operator@example.com" not in combined
    assert "/services/must-not-leak" not in combined
    assert "Traceback" not in combined
    DatabaseManager.reset_instance()
