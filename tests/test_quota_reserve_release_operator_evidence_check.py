# -*- coding: utf-8 -*-
"""Offline quota reserve/release operator evidence validator tests."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "quota_reserve_release_operator_evidence_check.py"


SECTION_IDS = (
    "configSnapshot",
    "successReserveRelease",
    "reserveFailureFailOpen",
    "analysisFailureFinallyRelease",
    "releaseFailureFailOpen",
    "executionLogMetadataSafety",
    "quotaWindowBeforeAfter",
    "costLedgerReservationEvidence",
    "rollbackProof",
)


def _valid_artifact() -> dict[str, object]:
    return {
        "schemaVersion": "wolfystock_quota_reserve_release_operator_evidence_v1",
        "evidenceScope": "internal_private_beta",
        "advisoryMode": True,
        "sections": {
            "configSnapshot": {
                "enabledByDefault": False,
                "ownerAllowlistConfigured": True,
                "publicGlobalEnablement": False,
                "routeLabel": "sync_single_stock_only",
                "advisoryMode": True,
            },
            "successReserveRelease": {
                "sourceScope": "synthetic",
                "routeLabel": "sync_single_stock_only",
                "reserveAttempted": True,
                "reserveSucceeded": True,
                "releaseAttempted": True,
                "releaseSucceeded": True,
                "analysisCompleted": True,
                "responseShapeChanged": False,
            },
            "reserveFailureFailOpen": {
                "routeLabel": "sync_single_stock_only",
                "reserveAttempted": True,
                "reserveSucceeded": False,
                "analysisProceeded": True,
                "requestBlocked": False,
                "consumeAttempted": False,
                "failOpen": True,
            },
            "analysisFailureFinallyRelease": {
                "routeLabel": "sync_single_stock_only",
                "reserveSucceeded": True,
                "analysisSucceeded": False,
                "releaseAttempted": True,
                "releaseFromFinally": True,
                "releaseSucceeded": True,
                "responseShapeChanged": False,
            },
            "releaseFailureFailOpen": {
                "routeLabel": "sync_single_stock_only",
                "releaseAttempted": True,
                "releaseSucceeded": False,
                "warningRecorded": True,
                "requestBlocked": False,
                "consumeAttempted": False,
                "failOpen": True,
            },
            "executionLogMetadataSafety": {
                "boundedMetadataOnly": True,
                "rawReservationIdAbsent": True,
                "idempotencyMaterialAbsent": True,
                "rawOwnerOrRequestAbsent": True,
                "rawProviderOrExceptionAbsent": True,
            },
            "quotaWindowBeforeAfter": {
                "before": {
                    "reserved_units": 4,
                    "consumed_units": 12,
                    "request_count": 7,
                },
                "after": {
                    "reserved_units": 4,
                    "consumed_units": 12,
                    "request_count": 8,
                },
                "aggregateOnly": True,
                "reservedUnitsLeaked": False,
            },
            "costLedgerReservationEvidence": {
                "routeLabel": "sync_single_stock_only",
                "ledgerFieldAvailable": True,
                "routeReservationIdPropagated": False,
                "routeEstimatedUnitsOnly": True,
                "billingAuthoritativeActualProviderCost": False,
                "terminalTransitionOwner": "route_pilot_estimated_units",
                "exactOnceActualCostConsumeAccepted": False,
                "rawReservationIdAbsent": True,
                "runtimeBehaviorChanged": False,
                "publicLaunchApproval": False,
            },
            "rollbackProof": {
                "pilotDisabled": True,
                "ownerRemovedFromAllowlist": False,
                "routeOutOfScope": True,
                "responseShapeChanged": False,
            },
        },
    }


def _write_json(tmp_path: Path, payload: object, name: str = "quota-reserve-release.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run_validator(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _stdout_json(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return json.loads(result.stdout)


def _reason_codes(payload: dict[str, object]) -> set[str]:
    return {str(finding["reasonCode"]) for finding in payload["findings"]}  # type: ignore[index]


def test_valid_sanitized_artifact_passes(tmp_path: Path) -> None:
    path = _write_json(tmp_path, _valid_artifact())

    result = _run_validator(path)

    assert result.returncode == 0
    payload = _stdout_json(result)
    assert payload["status"] == "pass"
    assert payload["finalStatus"] == "EVIDENCE-READY"
    assert payload["advisoryOnly"] is True
    assert payload["launchApproved"] is False
    assert payload["liveQuotaEnforcementApproved"] is False
    assert payload["consumeWiringApproved"] is False
    assert payload["runtimeBehaviorChanged"] is False
    assert payload["networkCallsExecutedByValidator"] is False
    assert payload["runtimeApisCalledByValidator"] is False
    assert payload["storageAccessedByValidator"] is False
    assert {category["id"] for category in payload["categories"]} == set(SECTION_IDS)  # type: ignore[index]


def test_directory_of_sanitized_artifacts_passes_when_categories_are_complete(tmp_path: Path) -> None:
    artifact = _valid_artifact()
    sections = artifact["sections"]
    assert isinstance(sections, dict)
    first = {"schemaVersion": artifact["schemaVersion"], "sections": dict(list(sections.items())[:4])}
    second = {"schemaVersion": artifact["schemaVersion"], "sections": dict(list(sections.items())[4:])}
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    _write_json(evidence_dir, first, "part-a.json")
    _write_json(evidence_dir, second, "part-b.json")

    result = _run_validator(evidence_dir)

    assert result.returncode == 0
    payload = _stdout_json(result)
    assert payload["status"] == "pass"
    assert payload["artifacts"]["jsonArtifactsChecked"] == 2  # type: ignore[index]


def test_missing_required_sections_fail(tmp_path: Path) -> None:
    artifact = _valid_artifact()
    sections = artifact["sections"]
    assert isinstance(sections, dict)
    sections.pop("rollbackProof")
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    assert payload["status"] == "fail"
    assert "missing_required_category" in _reason_codes(payload)


def test_raw_reservation_id_fails_without_echoing_value(tmp_path: Path) -> None:
    raw_value = "qres_should_not_echo"
    artifact = _valid_artifact()
    sections = artifact["sections"]
    assert isinstance(sections, dict)
    section = sections["successReserveRelease"]
    assert isinstance(section, dict)
    section["reservation_id"] = raw_value
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    assert raw_value not in result.stdout
    assert raw_value not in result.stderr
    assert "raw_reservation_identifier_forbidden" in _reason_codes(_stdout_json(result))


def test_raw_identifier_values_fail_without_echoing(tmp_path: Path) -> None:
    raw_reservation_ref = "qres_value_should_not_echo"
    raw_idempotency_ref = "quota:analysis_sync_single_stock:v1"
    raw_window_ref = "window_identity_key:unsafe"
    artifact = _valid_artifact()
    sections = artifact["sections"]
    assert isinstance(sections, dict)
    success = sections["successReserveRelease"]
    quota_window = sections["quotaWindowBeforeAfter"]
    assert isinstance(success, dict)
    assert isinstance(quota_window, dict)
    success["sanitizedRef"] = raw_reservation_ref
    success["diagnosticCode"] = raw_idempotency_ref
    quota_window["windowSummaryRef"] = raw_window_ref
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert raw_reservation_ref not in combined_output
    assert raw_idempotency_ref not in combined_output
    assert raw_window_ref not in combined_output
    reason_codes = _reason_codes(_stdout_json(result))
    assert "raw_reservation_identifier_forbidden" in reason_codes
    assert "idempotency_material_forbidden" in reason_codes
    assert "window_identity_key_forbidden" in reason_codes


def test_idempotency_key_and_hash_fail(tmp_path: Path) -> None:
    idempotency_key = "quota:analysis_sync_single_stock:v1|owner:pilot-user"
    idempotency_hash = "sha256:unsafe"
    artifact = _valid_artifact()
    sections = artifact["sections"]
    assert isinstance(sections, dict)
    section = sections["reserveFailureFailOpen"]
    assert isinstance(section, dict)
    section["idempotency_key"] = idempotency_key
    section["idempotency_hash"] = idempotency_hash
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert idempotency_key not in combined_output
    assert idempotency_hash not in combined_output
    reason_codes = _reason_codes(_stdout_json(result))
    assert "idempotency_material_forbidden" in reason_codes


def test_owner_allowlist_value_fails(tmp_path: Path) -> None:
    allowlist_value = "pilot-owner-001"
    artifact = _valid_artifact()
    sections = artifact["sections"]
    assert isinstance(sections, dict)
    section = sections["configSnapshot"]
    assert isinstance(section, dict)
    section["ownerAllowlistValues"] = [allowlist_value]
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    assert allowlist_value not in result.stdout + result.stderr
    assert "owner_allowlist_values_forbidden" in _reason_codes(_stdout_json(result))


def test_request_headers_cookie_token_body_and_raw_user_text_fail_without_echoing(tmp_path: Path) -> None:
    auth_marker = "opaque-auth-marker-should-not-echo"
    raw_user_text = "please analyze my private position"
    artifact = _valid_artifact()
    sections = artifact["sections"]
    assert isinstance(sections, dict)
    section = sections["executionLogMetadataSafety"]
    assert isinstance(section, dict)
    section["requestHeaders"] = {"Authorization": auth_marker, "Cookie": "opaque-cookie-marker"}
    section["rawRequestBody"] = {"original_query": raw_user_text}
    section["rawUserText"] = raw_user_text
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert auth_marker not in combined_output
    assert raw_user_text not in combined_output
    reason_codes = _reason_codes(_stdout_json(result))
    assert "raw_request_context_forbidden" in reason_codes
    assert "raw_user_text_forbidden" in reason_codes


def test_provider_payload_raw_exception_and_stack_trace_fail(tmp_path: Path) -> None:
    provider_payload = "raw-provider-response"
    raw_exception = "Exception: provider failure"
    stack_trace = "Traceback (most recent call last):\n  File \"x.py\", line 1"
    artifact = _valid_artifact()
    sections = artifact["sections"]
    assert isinstance(sections, dict)
    section = sections["releaseFailureFailOpen"]
    assert isinstance(section, dict)
    section["providerPayload"] = {"model": provider_payload}
    section["rawExceptionText"] = raw_exception
    section["stackTrace"] = stack_trace
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert provider_payload not in combined_output
    assert raw_exception not in combined_output
    assert stack_trace not in combined_output
    reason_codes = _reason_codes(_stdout_json(result))
    assert "provider_or_model_payload_forbidden" in reason_codes
    assert "raw_exception_or_stack_trace_forbidden" in reason_codes


def test_row_level_reservation_list_fails(tmp_path: Path) -> None:
    artifact = _valid_artifact()
    sections = artifact["sections"]
    assert isinstance(sections, dict)
    section = sections["quotaWindowBeforeAfter"]
    assert isinstance(section, dict)
    section["reservationRows"] = [
        {"status": "reserved", "reserved_units": 1},
        {"status": "released", "reserved_units": 0},
    ]
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    assert "row_level_reservation_data_forbidden" in _reason_codes(_stdout_json(result))


def test_aggregate_only_quota_window_summary_passes(tmp_path: Path) -> None:
    artifact = _valid_artifact()
    sections = artifact["sections"]
    assert isinstance(sections, dict)
    section = sections["quotaWindowBeforeAfter"]
    assert isinstance(section, dict)
    section["before"] = {"reserved_units": 9, "consumed_units": 24, "request_count": 12}
    section["after"] = {"reserved_units": 9, "consumed_units": 24, "request_count": 13}
    section["countsByStatus"] = {"reserved": 0, "released": 1, "failed": 0}
    section["countsByReason"] = {"release_completed": 1}
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 0
    payload = _stdout_json(result)
    assert payload["checks"]["quotaWindowAggregateOnly"] is True  # type: ignore[index]


def test_cost_ledger_reservation_evidence_requires_no_billing_authority_claim(tmp_path: Path) -> None:
    artifact = _valid_artifact()
    sections = artifact["sections"]
    assert isinstance(sections, dict)
    section = sections["costLedgerReservationEvidence"]
    assert isinstance(section, dict)
    section["billingAuthoritativeActualProviderCost"] = True
    section["publicLaunchApproval"] = True
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    reason_codes = _reason_codes(_stdout_json(result))
    assert "billing_authority_claim_forbidden" in reason_codes
    assert "public_launch_approval_forbidden" in reason_codes


def test_script_does_not_import_or_call_runtime_quota_storage_route_modules() -> None:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    forbidden_import_prefixes = (
        "api.",
        "api.v1.",
        "aiohttp",
        "httpx",
        "requests",
        "scripts.",
        "src.storage",
        "src.services.quota_policy_service",
        "src.services.llm_cost_ledger_service",
        "src.services.execution_log_service",
        "data_provider.",
        "urllib.request",
    )
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    allowed_helper_modules = {"evidence_safety", "scripts.evidence_safety"}
    forbidden_exact_modules = {prefix.rstrip(".") for prefix in forbidden_import_prefixes}
    forbidden_modules = [
        module
        for module in imported_modules
        if module not in allowed_helper_modules
        if module in forbidden_exact_modules or any(module.startswith(prefix) for prefix in forbidden_import_prefixes)
    ]
    assert not forbidden_modules

    forbidden_call_names = {
        "reserve_quota",
        "release_reservation",
        "consume_reservation",
        "QuotaPolicyService",
    }
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called_names.add(node.func.attr)

    assert called_names.isdisjoint(forbidden_call_names)


def test_script_reuses_shared_evidence_safety_helpers() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in {"evidence_safety", "scripts.evidence_safety"}:
            imported_names.update(alias.name for alias in node.names)

    assert {"compact_key", "finding", "read_json_document", "scan_json_tree"}.issubset(imported_names)
    assert "def _scan_json_tree(" not in source
    assert "def _join_path(" not in source
    assert "def _compact_key(" not in source
