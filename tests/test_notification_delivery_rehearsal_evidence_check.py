# -*- coding: utf-8 -*-
"""Offline notification delivery rehearsal evidence validator tests."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from tests.helpers.cli_validator import make_cli_validator, stdout_json as _stdout_json


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "notification_delivery_rehearsal_evidence_check.py"
VALID_FIXTURE = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "notification_delivery_rehearsal"
    / "accepted.synthetic.valid.json"
)
INVALID_FIXTURE = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "notification_delivery_rehearsal"
    / "unsafe.synthetic.invalid.json"
)
_write_json, _run_validator = make_cli_validator(
    SCRIPT,
    cwd=REPO_ROOT,
    artifact_name="notification-delivery-rehearsal-evidence.json",
)


def _proof(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "dryRunOnly": True,
        "noOutboundSent": True,
        "deliveryClientPatchedOrDisabled": True,
        "providerCallsExecuted": False,
        "checkerNetworkCallsEnabled": False,
        "outcome": "accepted",
    }
    payload.update(overrides)
    return payload


def _channel_mapping(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "routeLabel": "admin-notification-rehearsal",
        "channelLabel": "ops-channel-alpha",
        "ownerLabel": "owner-label-alpha",
        "channelType": "email",
        "mappingSourceLabel": "review-ticket-label",
    }
    payload.update(overrides)
    return payload


def _ownership(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "ownerLabel": "owner-label-alpha",
        "channelLabel": "ops-channel-alpha",
        "ownershipEvidenceLabel": "review-ticket-label",
        "recipientLabel": "recipient-label-alpha",
        "manualApprovalRequired": True,
        "rawRecipientIdIncluded": False,
    }
    payload.update(overrides)
    return payload


def _failure_case(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "caseLabel": "delivery-timeout-synthetic",
        "routeLabel": "admin-notification-rehearsal",
        "sanitizedReasonCode": "synthetic_delivery_timeout",
        "coreFlowContinues": True,
        "rawNotificationBodyIncluded": False,
        "providerPayloadIncluded": False,
        "stackTraceIncluded": False,
    }
    payload.update(overrides)
    return payload


def _artifact(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schemaVersion": "wolfystock_notification_delivery_rehearsal_evidence_v1",
        "mode": "offline-sanitized-rehearsal",
        "environment": "staging",
        "operator": "notification-ops-operator",
        "observedAt": "2026-05-08T10:30:00Z",
        "dryRunNoSendProof": _proof(),
        "channelMappingSummary": {
            "mappingComplete": True,
            "routes": [_channel_mapping()],
        },
        "recipientChannelOwnershipEvidence": {
            "sanitizedLabelsOnly": True,
            "owners": [_ownership()],
        },
        "failurePathAuditSummary": {
            "failurePathsAudited": True,
            "cases": [_failure_case()],
        },
        "outboundSafety": {
            "outboundDisabledByDefault": True,
            "externalProviderCallsByChecker": False,
            "manualApprovalRequiredForRealDelivery": True,
            "realDeliveryRehearsalApproved": False,
            "runtimeNotificationBehaviorChanged": False,
            "releaseApproved": False,
            "publicLaunchReady": False,
        },
        "outcome": "accepted",
        "evidenceRedactionVersion": "notification_delivery_rehearsal_redaction_v1",
        "notes": "Sanitized dry-run evidence for manual review.",
    }
    payload.update(overrides)
    return payload


def test_accepts_sanitized_offline_notification_delivery_rehearsal(tmp_path: Path) -> None:
    path = _write_json(tmp_path, _artifact())

    result = _run_validator(path)

    assert result.returncode == 0
    payload = _stdout_json(result)
    assert payload["status"] == "pass"
    assert payload["finalStatus"] == "EVIDENCE-READY"
    assert payload["releaseApproved"] is False
    assert payload["publicLaunchReady"] is False
    assert payload["networkCallsExecutedByValidator"] is False
    assert payload["outboundNotificationsSentByValidator"] is False
    assert payload["runtimeNotificationBehaviorChanged"] is False
    assert payload["manualApprovalRequiredForRealDelivery"] is True
    assert payload["acceptedCategories"] == [
        "dry-run/no-send proof",
        "channel mapping summary",
        "recipient/channel ownership evidence",
        "failure-path audit summary",
        "outbound disabled/default-off posture",
    ]
    assert payload["rejectedCategories"] == []


def test_fixture_pair_documents_valid_and_rejected_synthetic_artifacts() -> None:
    valid = _run_validator(VALID_FIXTURE)
    invalid = _run_validator(INVALID_FIXTURE)

    assert valid.returncode == 0
    assert _stdout_json(valid)["finalStatus"] == "EVIDENCE-READY"
    assert invalid.returncode == 1
    rejected = _stdout_json(invalid)
    assert rejected["finalStatus"] == "REJECTED"
    assert rejected["releaseApproved"] is False
    assert rejected["publicLaunchReady"] is False


def test_rejects_raw_recipients_urls_tokens_payloads_and_traces_without_leaking(tmp_path: Path) -> None:
    unsafe_email = "operator@example.com"
    unsafe_phone = "+1 415-555-0100"
    unsafe_url = "https://hooks.example.test/services/raw/path"
    unsafe_token = "sk-" + ("A" * 40)
    unsafe_body = "raw notification body with private data"
    unsafe_trace = "Traceback (most recent call last): hidden"
    artifact = _artifact(
        channelMappingSummary={
            "mappingComplete": True,
            "routes": [
                _channel_mapping(
                    channelLabel=unsafe_email,
                    recipientPhone=unsafe_phone,
                    webhookUrl=unsafe_url,
                    token=unsafe_token,
                )
            ],
        },
        recipientChannelOwnershipEvidence={
            "sanitizedLabelsOnly": True,
            "owners": [
                _ownership(
                    recipientLabel=unsafe_email,
                    rawRecipientId="user-123",
                )
            ],
        },
        failurePathAuditSummary={
            "failurePathsAudited": True,
            "cases": [
                _failure_case(
                    rawNotificationBody=unsafe_body,
                    stackTrace=unsafe_trace,
                )
            ],
        },
    )
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    for unsafe in (unsafe_email, unsafe_phone, unsafe_url, unsafe_token, unsafe_body, unsafe_trace):
        assert unsafe not in combined_output
    reason_codes = {finding["reasonCode"] for finding in _stdout_json(result)["findings"]}
    assert {
        "unsafe_contact_value",
        "unsafe_url_value",
        "unsafe_secret_marker",
        "raw_recipient_id_forbidden",
        "raw_notification_body_forbidden",
        "stack_trace_forbidden",
    }.issubset(reason_codes)


def test_rejects_outbound_live_provider_and_public_launch_claims(tmp_path: Path) -> None:
    artifact = deepcopy(_artifact())
    artifact["dryRunNoSendProof"] = _proof(
        dryRunOnly=False,
        noOutboundSent=False,
        providerCallsExecuted=True,
        checkerNetworkCallsEnabled=True,
    )
    artifact["outboundSafety"] = {
        "outboundDisabledByDefault": False,
        "externalProviderCallsByChecker": True,
        "manualApprovalRequiredForRealDelivery": False,
        "realDeliveryRehearsalApproved": True,
        "runtimeNotificationBehaviorChanged": True,
        "releaseApproved": True,
        "publicLaunchReady": True,
    }
    artifact["notes"] = "release-approved GO for public launch"
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    assert payload["releaseApproved"] is False
    assert payload["publicLaunchReady"] is False
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert {
        "dry_run_no_send_required",
        "external_provider_or_network_call_forbidden",
        "outbound_disabled_by_default_required",
        "manual_approval_required",
        "real_delivery_approval_not_launch_evidence",
        "runtime_notification_behavior_change_forbidden",
        "release_approval_forbidden",
        "public_launch_ready_forbidden",
        "launch_approval_claim_forbidden",
    }.issubset(reason_codes)


def test_missing_required_evidence_categories_are_rejected(tmp_path: Path) -> None:
    artifact = deepcopy(_artifact())
    artifact.pop("failurePathAuditSummary")
    ownership = artifact["recipientChannelOwnershipEvidence"]
    assert isinstance(ownership, dict)
    ownership["owners"] = []
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    assert payload["status"] == "fail"
    reason_codes = {finding["reasonCode"] for finding in payload["findings"]}
    assert "missing_required_category" in reason_codes
    assert "recipient_channel_ownership_missing" in reason_codes
    assert "failure-path audit summary" in payload["rejectedCategories"]
