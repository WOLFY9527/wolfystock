from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "security_mfa_operator_evidence_check.py"


def _section(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "environment": "staging-security",
        "operator": "security-operator",
        "observedAt": "2026-05-08T10:30:00Z",
        "outcome": "accepted",
        "evidenceRedactionVersion": "security_mfa_operator_redaction_v1",
        "sampledControlRefs": ["security-ticket-1425", "redaction-review"],
        "runtimeBehaviorChanged": False,
    }
    payload.update(overrides)
    return payload


def _artifact() -> dict[str, object]:
    return {
        "schemaVersion": "wolfystock_security_mfa_operator_evidence_v1",
        "artifactMode": "operator_sanitized",
        "mfaEnforcementPilot": _section(
            enabledByDefault=False,
            globalMfaRequired=False,
            pilotScope="narrow_admin_pilot",
            pilotAccountLabels=["admin-pilot-a", "admin-pilot-b"],
            pilotEvidenceRef="mfa-pilot-sanitized-evidence",
        ),
        "recoveryCodeDisplayOnce": _section(
            displayOnceVerified=True,
            plaintextStoredAfterDisplay=False,
            displayOnceEvidenceRef="recovery-display-once-review",
        ),
        "recoveryCodeHashConsumeOnce": _section(
            hashStorageVerified=True,
            consumeOnceVerified=True,
            replayDeniedVerified=True,
            hashConsumeEvidenceRef="recovery-hash-consume-review",
        ),
        "breakGlassPolicy": _section(
            policyState="explicitly_absent",
            breakGlassEnabledByDefault=False,
            evidenceRef="break-glass-policy-review",
        ),
        "rollbackPlan": _section(
            rollbackPlanPresent=True,
            rollbackSwitchIdentified=True,
            rollbackEvidenceRef="mfa-rollback-review",
        ),
        "sessionStaleReauth": _section(
            staleSessionDeniedVerified=True,
            recentReauthRequiredVerified=True,
            sessionEvidenceRef="session-reauth-review",
        ),
    }


def _write_json(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "security-mfa-operator-evidence.json"
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
    summary = payload["summary"]
    assert isinstance(summary, dict)
    counts = summary["countsByReasonCode"]
    assert isinstance(counts, dict)
    return set(counts)


def _all_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(str(key))
            keys.update(_all_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(_all_keys(child))
    return keys


def test_valid_sanitized_mfa_operator_artifact_passes(tmp_path: Path) -> None:
    result = _run_validator(_write_json(tmp_path, _artifact()))

    assert result.returncode == 0
    payload = _stdout_json(result)
    assert payload["schemaVersion"] == "wolfystock_security_mfa_operator_evidence_summary_v1"
    assert payload["status"] == "pass"
    assert payload["finalStatus"] == "EVIDENCE-READY"
    assert payload["offlineOnly"] is True
    assert payload["networkCallsExecutedByValidator"] is False
    assert payload["runtimeBehaviorChanged"] is False
    assert payload["authRuntimeBehaviorChanged"] is False
    assert payload["globalMfaEnabledByValidator"] is False
    assert payload["rawSecretsIncluded"] is False
    assert payload["checks"]["requiredCategoriesPresent"] is True
    assert payload["checks"]["mfaPilotDisabledOrNarrow"] is True
    assert payload["checks"]["recoveryCodeDisplayOnceEvidencePresent"] is True
    assert payload["checks"]["recoveryCodeHashConsumeOnceEvidencePresent"] is True
    assert payload["checks"]["breakGlassPolicyRecorded"] is True
    assert payload["checks"]["rollbackPlanEvidencePresent"] is True
    assert payload["checks"]["sessionStaleReauthEvidencePresent"] is True
    assert payload["checks"]["sensitiveValuesAbsent"] is True
    assert payload["summary"]["findingCount"] == 0
    assert payload["summary"]["countsByReasonCode"] == {}
    assert "findings" not in payload
    assert {"field", "path", "value"}.isdisjoint(_all_keys(payload))


def test_missing_recovery_code_proof_fails(tmp_path: Path) -> None:
    artifact = deepcopy(_artifact())
    artifact.pop("recoveryCodeHashConsumeOnce")

    result = _run_validator(_write_json(tmp_path, artifact))

    assert result.returncode == 1
    payload = _stdout_json(result)
    reason_codes = _reason_codes(payload)
    assert "missing_required_category" in reason_codes
    assert payload["checks"]["recoveryCodeHashConsumeOnceEvidencePresent"] is False


def test_raw_totp_secret_fails_without_echoing_value(tmp_path: Path) -> None:
    raw_secret = "JBSWY3DPEHPK3PXP"
    artifact = deepcopy(_artifact())
    artifact["mfaEnforcementPilot"]["totpSecret"] = raw_secret

    result = _run_validator(_write_json(tmp_path, artifact))

    assert result.returncode == 1
    assert raw_secret not in result.stdout + result.stderr
    payload = _stdout_json(result)
    reason_codes = _reason_codes(payload)
    assert "raw_totp_secret_forbidden" in reason_codes
    assert payload["rawSecretsIncluded"] is False


def test_raw_recovery_code_fails_without_echoing_value(tmp_path: Path) -> None:
    raw_recovery_code = "ABCD-EFGH-IJKL"
    artifact = deepcopy(_artifact())
    artifact["recoveryCodeDisplayOnce"]["recoveryCode"] = raw_recovery_code

    result = _run_validator(_write_json(tmp_path, artifact))

    assert result.returncode == 1
    assert raw_recovery_code not in result.stdout + result.stderr
    reason_codes = _reason_codes(_stdout_json(result))
    assert "raw_recovery_code_forbidden" in reason_codes


def test_raw_session_cookie_and_token_fail_without_echoing_values(tmp_path: Path) -> None:
    raw_session = "session-id=session-value-should-not-leak"
    raw_cookie = "Set-Cookie: wolfy_session=cookie-value-should-not-leak; HttpOnly"
    raw_token = "Be" "arer token-value-should-not-leak-123456"
    artifact = deepcopy(_artifact())
    artifact["sessionStaleReauth"]["sessionId"] = raw_session
    artifact["sessionStaleReauth"]["cookieHeader"] = raw_cookie
    artifact["sessionStaleReauth"]["token"] = raw_token

    result = _run_validator(_write_json(tmp_path, artifact))

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert raw_session not in combined_output
    assert raw_cookie not in combined_output
    assert raw_token not in combined_output
    reason_codes = _reason_codes(_stdout_json(result))
    assert "raw_session_cookie_or_token_forbidden" in reason_codes


def test_global_mfa_approval_wording_without_pilot_evidence_fails(tmp_path: Path) -> None:
    artifact = deepcopy(_artifact())
    artifact["mfaEnforcementPilot"] = _section(
        enabledByDefault=True,
        globalMfaRequired=True,
        pilotScope="global",
        pilotAccountLabels=[],
        notes="global MFA approved for all production users",
    )

    result = _run_validator(_write_json(tmp_path, artifact))

    assert result.returncode == 1
    payload = _stdout_json(result)
    reason_codes = _reason_codes(payload)
    assert "global_mfa_rollout_not_allowed" in reason_codes
    assert "global_mfa_approval_claim_forbidden" in reason_codes
    assert payload["checks"]["mfaPilotDisabledOrNarrow"] is False


def test_output_remains_sanitized_for_multiple_raw_values(tmp_path: Path) -> None:
    raw_values = (
        "admin@example.com",
        "password=secret-password-should-not-leak",
        "mfa_recovery_codes_hash=pbkdf2_sha256$600000$rawhash",
        "WOLFYSTOCK_MFA_SECRET_ENCRYPTION_KEY=env-secret-should-not-leak",
        "Traceback (most recent call last): stack-secret-should-not-leak",
    )
    artifact = deepcopy(_artifact())
    artifact["adversarial"] = {
        "email": raw_values[0],
        "password": raw_values[1],
        "mfaRecoveryCodesHash": raw_values[2],
        "envSecretValue": raw_values[3],
        "stackTrace": raw_values[4],
    }

    result = _run_validator(_write_json(tmp_path, artifact))

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    for raw_value in raw_values:
        assert raw_value not in combined_output
    payload = _stdout_json(result)
    reason_codes = _reason_codes(payload)
    assert {
        "unmasked_email_forbidden",
        "raw_password_or_hash_forbidden",
        "env_secret_value_forbidden",
        "stack_trace_forbidden",
    }.issubset(reason_codes)
    assert "findings" not in payload
    assert {"field", "path", "value"}.isdisjoint(_all_keys(payload))


def test_validator_remains_offline_by_static_import_boundary() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    forbidden_snippets = (
        "from src.auth",
        "import src.auth",
        "DatabaseManager",
        "requests",
        "httpx",
        "socket",
        "os.environ",
        "uvicorn",
        "server:app",
    )
    for snippet in forbidden_snippets:
        assert snippet not in source
