from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.provider_operator_evidence_check import validate_provider_operator_evidence


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "evidence_artifact_sanitize.py"
REDACTED = "<redacted>"


def _write_json(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "operator-artifact.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _sanitize(tmp_path: Path, payload: object) -> tuple[subprocess.CompletedProcess[str], Path]:
    source = _write_json(tmp_path, payload)
    output = tmp_path / "sanitized.json"
    result = _run("sanitize", "--input", source, "--output", output)
    return result, output


def _combined(result: subprocess.CompletedProcess[str], output: Path | None = None) -> str:
    text = result.stdout + result.stderr
    if output and output.exists():
        text += output.read_text(encoding="utf-8")
    return text


def test_secret_markers_are_redacted_and_not_emitted(tmp_path: Path) -> None:
    raw_secret = "api_key=operator-secret-value-should-not-leak"

    result, output = _sanitize(tmp_path, {"providerName": "tradier", "notes": raw_secret})

    assert result.returncode == 0
    sanitized = json.loads(output.read_text(encoding="utf-8"))
    assert sanitized["notes"] == REDACTED
    assert raw_secret not in _combined(result, output)
    summary = json.loads(result.stdout)
    assert summary["summary"]["countsByCategory"]["secret_marker"] == 1


def test_raw_request_and_response_body_markers_are_redacted(tmp_path: Path) -> None:
    raw_request = "raw-request-body-value-should-not-leak"
    raw_response = "raw-response-body-value-should-not-leak"

    result, output = _sanitize(
        tmp_path,
        {
            "raw_request_body": {"body": raw_request},
            "response": f"raw response payload {raw_response}",
        },
    )

    assert result.returncode == 0
    sanitized = json.loads(output.read_text(encoding="utf-8"))
    assert sanitized["raw_request_body"]["body"] == REDACTED
    assert sanitized["response"] == REDACTED
    combined = _combined(result, output)
    assert raw_request not in combined
    assert raw_response not in combined
    assert "raw_request_body" not in result.stdout


def test_path_traversal_and_credential_urls_are_redacted(tmp_path: Path) -> None:
    traversal = "../operator-secrets.json"
    credential_url = "https://user:pass@example.invalid/internal"

    result, output = _sanitize(tmp_path, {"fileLabel": traversal, "callback": credential_url})

    assert result.returncode == 0
    sanitized = json.loads(output.read_text(encoding="utf-8"))
    assert sanitized["fileLabel"] == REDACTED
    assert sanitized["callback"] == REDACTED
    combined = _combined(result, output)
    assert traversal not in combined
    assert credential_url not in combined


def test_approval_wording_is_redacted_without_emitting_raw_phrase(tmp_path: Path) -> None:
    wording = "public " + "launch " + "GO" + " for this artifact"

    result, output = _sanitize(tmp_path, {"operatorConclusion": wording})

    assert result.returncode == 0
    assert json.loads(output.read_text(encoding="utf-8"))["operatorConclusion"] == REDACTED
    combined = _combined(result, output).lower()
    assert wording.lower() not in combined
    assert json.loads(result.stdout)["summary"]["countsByCategory"]["approval_wording"] == 1


def test_scan_mode_exits_non_zero_with_fail_on_findings_without_leaks(tmp_path: Path) -> None:
    raw_secret = "Be" "arer scan-secret-value-should-not-leak"
    source = _write_json(tmp_path, {"notes": raw_secret})

    result = _run("scan", "--input", source, "--fail-on-findings")

    assert result.returncode == 1
    assert raw_secret not in _combined(result)
    summary = json.loads(result.stdout)
    assert summary["mode"] == "scan"
    assert summary["summary"]["totalFindings"] == 1


def test_sanitized_output_can_reach_review_state_through_provider_validator(tmp_path: Path) -> None:
    payload = {
        "providerName": "tradier",
        "environment": "staging",
        "operator": "provider-ops",
        "observedAt": "2026-05-08T10:30:00Z",
        "probeMode": "manual_provider_probe",
        "networkCallsEnabled": False,
        "credentialPresence": "redacted",
        "circuitState": {"state": "closed", "summary": "No forced circuit override recorded."},
        "fallbackState": {"state": "unchanged", "summary": "Runtime fallback policy was observed only."},
        "outcome": "needs-review",
        "evidenceRedactionVersion": "provider_operator_redaction_v1",
        "notes": "token=provider-note-value-should-not-leak",
    }

    result, output = _sanitize(tmp_path, payload)

    assert result.returncode == 0
    validator_summary = validate_provider_operator_evidence(json.loads(output.read_text(encoding="utf-8")))
    assert validator_summary["status"] == "pass"
    assert validator_summary["artifact"]["outcome"] == "needs-review"
