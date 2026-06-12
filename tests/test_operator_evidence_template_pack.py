from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "operator_evidence_template_pack.py"

EXPECTED_FILES = {
    "provider_operator_evidence.json",
    "provider_sla_licensing_evidence.json",
    "restore_pitr_operator_evidence.json",
    "security_operator_acceptance.json",
    "quota_budget_operator_evidence.json",
    "staging_ingress_operator_evidence.json",
    "ws2_sse_operator_decision_evidence.json",
    "config_snapshot_evidence.json",
    "manual_release_approval_review_record.json",
}

PLACEHOLDERS = {
    "<sanitized-operator-label>",
    "<staging-environment-label>",
    "<redacted-or-configured>",
    "<review-ticket-label>",
    "<release-candidate-sha>",
}

RBAC_FALLBACK_OFF_OPERATOR_PILOT_FIELDS = {
    "disableSwitchExplicit",
    "routeInventoryComplete",
    "coarseFallbackDisabledOrExceptionAccepted",
    "backendAdminRoutesExplicitCapabilities",
    "frontendAdminGatesCapabilityBased",
    "frontendAdminMissingCapabilitiesFailClosed",
    "explicitCapabilityPayloadsPassWithoutFallback",
    "legacyMissingCapabilityUsersFailClosed",
    "rollbackPlanRecorded",
    "auditEvidenceSanitized",
    "runtimeDefaultUnchanged",
}

UNSAFE_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer ",
    "cookie",
    "database_url",
    "debug_payload",
    "debug_trace",
    "dsn",
    "password",
    "private_key",
    "provider_payload",
    "raw_log",
    "raw_payload",
    "raw_request",
    "raw_response",
    "request_body",
    "response_body",
    "session",
    "set-cookie",
    "stack trace",
    "token",
    "traceback",
    "webhook",
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _stdout_json(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return json.loads(result.stdout)


def _walk_strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        strings: list[str] = []
        for key, child in value.items():
            strings.append(str(key))
            strings.extend(_walk_strings(child))
        return strings
    if isinstance(value, list):
        strings = []
        for child in value:
            strings.extend(_walk_strings(child))
        return strings
    if isinstance(value, str):
        return [value]
    return []


def test_all_templates_generated(tmp_path: Path) -> None:
    result = _run(str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert {path.name for path in tmp_path.glob("*.json")} == EXPECTED_FILES
    security_template = _load(tmp_path / "security_operator_acceptance.json")
    assert RBAC_FALLBACK_OFF_OPERATOR_PILOT_FIELDS.issubset(
        security_template["rbacFallbackDisable"]
    )

    combined = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.glob("*.json"))
    for placeholder in PLACEHOLDERS:
        assert placeholder in combined


def test_single_category_generation_writes_only_that_template(tmp_path: Path) -> None:
    result = _run("--category", "ws2-sse", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert {path.name for path in tmp_path.glob("*.json")} == {
        "ws2_sse_operator_decision_evidence.json"
    }


def test_stdout_mode_prints_sanitized_templates_without_writing(tmp_path: Path) -> None:
    result = _run("--stdout", "--category", "config-snapshot", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert list(tmp_path.iterdir()) == []
    payload = _stdout_json(result)
    assert set(payload) == {"config_snapshot_evidence.json"}
    assert payload["config_snapshot_evidence.json"]["outcome"] == "needs-review"


def test_restore_pitr_template_is_review_only_and_not_launch_ready(tmp_path: Path) -> None:
    result = _run("--stdout", "--category", "restore-pitr", str(tmp_path))

    assert result.returncode == 0, result.stderr
    payload = _stdout_json(result)["restore_pitr_operator_evidence.json"]
    assert payload["evidenceMode"] == "local-synthetic-preflight"
    assert payload["outcome"] == "needs-review"
    assert payload["restoreCommandExecuted"] is False
    assert payload["reviewOnly"] is True
    assert payload["publicLaunchReady"] is False
    assert payload["launchApproved"] is False
    assert payload["restoreExecutionSummary"]["localOnlyDryRun"] is True
    assert payload["sanitizedArtifactReferences"][0]["kind"] == "validator-output"
    assert payload["localGeneration"]["checkerRanRestoreCommands"] is False
    assert payload["localGeneration"]["productionSecretsRead"] is False


def test_existing_files_are_not_overwritten_without_force(tmp_path: Path) -> None:
    existing = tmp_path / "provider_operator_evidence.json"
    existing.write_text('{"kept": true}', encoding="utf-8")

    result = _run("--category", "provider", str(tmp_path))

    assert result.returncode == 1
    assert _load(existing) == {"kept": True}

    forced = _run("--force", "--category", "provider", str(tmp_path))

    assert forced.returncode == 0, forced.stderr
    assert _load(existing)["outcome"] == "needs-review"


def test_generated_templates_contain_no_unsafe_markers(tmp_path: Path) -> None:
    result = _run(str(tmp_path))

    assert result.returncode == 0, result.stderr
    for path in tmp_path.glob("*.json"):
        payload = _load(path)
        text = "\n".join(_walk_strings(payload)).lower()
        assert "://" not in text
        assert "@" not in text
        for marker in UNSAFE_MARKERS:
            assert marker not in text


def test_generated_templates_are_validator_safe_or_review_only(tmp_path: Path) -> None:
    result = _run(str(tmp_path))

    assert result.returncode == 0, result.stderr

    bundle_result = subprocess.run(
        [sys.executable, "scripts/operator_evidence_bundle_check.py", str(tmp_path)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert bundle_result.returncode == 0, bundle_result.stderr
    bundle = json.loads(bundle_result.stdout)
    assert bundle["bundleStatus"] == "complete-review-required"
    assert {artifact["status"] for artifact in bundle["artifacts"]} == {"needs-review"}

    direct_checks: list[tuple[list[str], str, str]] = [
        (
            ["scripts/provider_operator_evidence_check.py", str(tmp_path / "provider_operator_evidence.json")],
            "status",
            "pass",
        ),
        (
            [
                "scripts/provider_sla_licensing_evidence_check.py",
                str(tmp_path / "provider_sla_licensing_evidence.json"),
            ],
            "status",
            "pass",
        ),
        (
            [
                "scripts/restore_pitr_operator_evidence_check.py",
                "--artifact",
                str(tmp_path / "restore_pitr_operator_evidence.json"),
            ],
            "finalStatus",
            "NO-GO",
        ),
        (
            [
                "scripts/security_operator_acceptance_check.py",
                "--artifact",
                str(tmp_path / "security_operator_acceptance.json"),
            ],
            "finalStatus",
            "NO-GO",
        ),
        (
            ["scripts/quota_operator_evidence_check.py", str(tmp_path / "quota_budget_operator_evidence.json")],
            "finalStatus",
            "REJECTED",
        ),
        (
            [
                "scripts/staging_ingress_operator_evidence_check.py",
                str(tmp_path / "staging_ingress_operator_evidence.json"),
            ],
            "status",
            "pass",
        ),
        (
            [
                "scripts/ws2_sse_operator_decision_check.py",
                str(tmp_path / "ws2_sse_operator_decision_evidence.json"),
            ],
            "status",
            "pass",
        ),
        (
            ["scripts/config_snapshot_evidence_check.py", str(tmp_path / "config_snapshot_evidence.json")],
            "status",
            "pass",
        ),
        (
            [
                "scripts/manual_release_approval_evidence_check.py",
                "--artifact",
                str(tmp_path / "manual_release_approval_review_record.json"),
            ],
            "manualReviewStatus",
            "needs-review",
        ),
    ]
    for command, status_key, expected_status in direct_checks:
        check = subprocess.run(
            [sys.executable, *command],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        payload = json.loads(check.stdout)
        assert payload[status_key] == expected_status
        assert _unsafe_reason_codes(payload) == set()


def _unsafe_reason_codes(value: Any) -> set[str]:
    unsafe_fragments = (
        "credential",
        "debug",
        "email",
        "payload",
        "raw",
        "secret",
        "sensitive",
        "stack",
        "trace",
        "url",
    )
    reason_codes: set[str] = set()
    if isinstance(value, dict):
        reason = value.get("reasonCode")
        if isinstance(reason, str) and any(fragment in reason for fragment in unsafe_fragments):
            reason_codes.add(reason)
        for child in value.values():
            reason_codes.update(_unsafe_reason_codes(child))
    elif isinstance(value, list):
        for child in value:
            reason_codes.update(_unsafe_reason_codes(child))
    return reason_codes
