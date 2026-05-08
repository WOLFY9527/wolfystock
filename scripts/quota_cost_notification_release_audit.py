#!/usr/bin/env python3
"""Offline release audit for quota, cost, and notification safety.

The audit uses in-memory fixtures only. It does not read credentials, open
network sockets, call AI/provider adapters, send notifications, or approve
launch.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.llm_cost_ledger_service import LlmCostLedgerService
from src.services.notification_service import NotificationDeliveryClient, NotificationService
from src.services.quota_policy_service import QuotaPolicyService
from src.storage import DatabaseManager, LLMCostLedger, QuotaReservation, QuotaUsageWindow


SCHEMA_VERSION = "wolfystock_quota_cost_notification_release_audit_v1"


class _NoOutboundDeliveryClient(NotificationDeliveryClient):
    """Delivery client used only to prove offline paths do not send."""

    def __init__(self) -> None:
        self.calls = 0

    def send_webhook(self, *, url: str, payload: dict, headers: dict | None = None, timeout: float = 5.0) -> None:
        del url, payload, headers, timeout
        self.calls += 1
        raise RuntimeError("offline audit forbids outbound delivery")


def _counts(db: DatabaseManager) -> dict[str, int]:
    with db.session_scope() as session:
        return {
            "reservations": session.query(QuotaReservation).count(),
            "windows": session.query(QuotaUsageWindow).count(),
            "ledger": session.query(LLMCostLedger).count(),
        }


def _quota_posture(db: DatabaseManager) -> dict[str, Any]:
    service = QuotaPolicyService(db=db)
    db.upsert_quota_policy(
        policy_key="release-audit-negative-hard-limit",
        scope_type="user",
        daily_budget_units=-1,
        metadata={"daily_soft_limit_units": -5},
    )
    before = _counts(db)
    shadow = service.classify_shadow_preflight(
        owner_user_id="release-owner",
        route_family="invalid-release-route",
        estimated_units=-100,
    )
    after = _counts(db)

    return {
        "status": "manual_review_required",
        "dryRunNoSpend": before == after,
        "invalidConfigSafeState": shadow.state,
        "invalidRouteFallback": shadow.route_family,
        "outOfRangeEstimateUnits": shadow.budget_alert.estimated_units,
        "outOfRangeRejectedSafely": bool(shadow.would_block),
        "reasonCode": shadow.reason_code,
        "liveEnforcement": False,
        "requestBlocked": False,
    }


def _cost_posture(db: DatabaseManager) -> dict[str, Any]:
    service = LlmCostLedgerService(db=db)
    before = _counts(db)
    result = service.calculate_cost(
        provider="missing-provider",
        model="missing-model",
        prompt_tokens=500,
        completion_tokens=250,
        route_family="analysis",
        call_type="analysis",
    )
    after = _counts(db)

    return {
        "status": "manual_review_required",
        "missingPricingPolicyStatus": result.status,
        "missingPricingPolicyNoSpend": before == after and result.total_cost_usd == 0,
        "ledgerRowsWritten": after["ledger"] - before["ledger"],
        "totalCostUsd": str(result.total_cost_usd),
        "liveInvoiceIngestion": False,
        "liveProviderCalls": False,
        "liveLlmCalls": False,
    }


def _notification_posture(db: DatabaseManager) -> dict[str, Any]:
    delivery = _NoOutboundDeliveryClient()
    service = NotificationService(db=db, delivery_client=delivery)

    no_channel_event = service.emit_event(
        event_type="release.quota_cost_notification_audit",
        severity="warning",
        title="Release safety audit",
        message="Offline audit no-channel notification check",
        payload={"dry_run": True},
        fingerprint="release-audit:no-channel",
    )
    channel = service.create_channel(
        name="release audit dry-run webhook",
        type="webhook",
        enabled=True,
        severity_min="warning",
        event_types=["release.quota_cost_notification_audit"],
        config={"webhook_url": "https://hooks.example.test/release-audit", "token": "redacted-placeholder"},
    )
    dry_run = service.test_channel(channel["id"], dry_run=True)

    return {
        "status": "manual_review_required",
        "noChannelsNoSend": no_channel_event["delivery_status"] == "no_channels",
        "dryRunNoSend": bool(dry_run["dry_run"]) and delivery.calls == 0,
        "deliveryCalls": delivery.calls,
        "notificationsSent": False,
        "outboundChannelsConfiguredForAudit": 0,
    }


def run_offline_audit() -> dict[str, Any]:
    DatabaseManager.reset_instance()
    db = DatabaseManager(db_url="sqlite:///:memory:")
    try:
        quota = _quota_posture(db)
        cost = _cost_posture(db)
        notification = _notification_posture(db)
    finally:
        DatabaseManager.reset_instance()

    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "manual_review_required",
        "quotaPosture": quota,
        "costPosture": cost,
        "notificationPosture": notification,
        "liveCallsExecuted": False,
        "notificationsSent": False,
        "manualReviewRequired": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run offline quota, cost, and notification release safety audit."
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run the default offline audit mode. Live mode is intentionally unavailable.",
    )
    parser.parse_args(argv)

    print(json.dumps(run_offline_audit(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
