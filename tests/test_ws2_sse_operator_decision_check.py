from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ws2_sse_operator_decision_check.py"


def _artifact(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "artifactVersion": "wolfystock_ws2_sse_operator_decision_evidence_v1",
        "environment": "staging",
        "operator": "ws2-topology-ops",
        "observedAt": "2026-05-08T10:30:00Z",
        "topologyMode": "polling-fallback",
        "sseBroadcastScope": "process-local",
        "pollingFallbackAccepted": True,
        "multiInstanceRiskAccepted": False,
        "userImpactSummary": "Cross-instance status relies on durable owner-scoped polling while SSE remains process-local.",
        "rollbackOrMitigationSummary": "Keep polling fallback documented and avoid multi-instance SSE launch claims until external broadcast is designed.",
        "outcome": "accepted",
        "evidenceRedactionVersion": "ws2_sse_operator_decision_redaction_v1",
    }
    payload.update(overrides)
    return payload


def _write_json(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "ws2-sse-operator-decision.json"
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


def test_accepts_polling_fallback_decision(tmp_path: Path) -> None:
    path = _write_json(tmp_path, _artifact())

    result = _run_validator(path)

    assert result.returncode == 0
    payload = _stdout_json(result)
    assert payload["status"] == "pass"
    assert payload["advisoryOnly"] is True
    assert payload["launchAcceptanceIntegrated"] is False
    assert payload["runtimeBehaviorChanged"] is False
    assert payload["networkCallsExecutedByValidator"] is False
    assert payload["artifact"]["topologyMode"] == "polling-fallback"
    assert payload["artifact"]["outcome"] == "accepted"


def test_accepts_single_instance_limitation_decision(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path,
        _artifact(
            topologyMode="single-instance-sse",
            pollingFallbackAccepted=False,
            multiInstanceRiskAccepted=True,
            userImpactSummary=(
                "Operator accepts process-local SSE only for a single-instance topology; "
                "multi-instance broadcast is not claimed."
            ),
            rollbackOrMitigationSummary=(
                "Scale down to one app instance or switch users to durable polling fallback "
                "if more than one process is required."
            ),
        ),
    )

    result = _run_validator(path)

    assert result.returncode == 0
    payload = _stdout_json(result)
    assert payload["status"] == "pass"
    assert payload["artifact"]["topologyMode"] == "single-instance-sse"
    assert payload["artifact"]["multiInstanceRiskAccepted"] is True


def test_rejects_unsafe_multi_instance_sse_acceptance(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path,
        _artifact(
            topologyMode="single-instance-sse",
            pollingFallbackAccepted=False,
            multiInstanceRiskAccepted=True,
            userImpactSummary="Accepted multi-instance SSE broadcast-safe topology for all users.",
            rollbackOrMitigationSummary="No fallback needed because SSE works across instances.",
        ),
    )

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    assert payload["status"] == "fail"
    assert {
        finding["reasonCode"] for finding in payload["findings"]
    } >= {"multi_instance_sse_acceptance_forbidden"}


def test_missing_topology_fields_are_rejected(tmp_path: Path) -> None:
    artifact = _artifact()
    artifact.pop("topologyMode")
    artifact.pop("sseBroadcastScope")
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    missing_fields = {
        finding["field"]
        for finding in payload["findings"]
        if finding["reasonCode"] == "missing_required_field"
    }
    assert {"topologyMode", "sseBroadcastScope"}.issubset(missing_fields)
    assert {
        finding["reasonCode"] for finding in payload["findings"]
    } >= {"accepted_outcome_requires_explicit_topology_mode"}


def test_secret_and_debug_markers_are_rejected_without_echoing_values(tmp_path: Path) -> None:
    secret_value = "raw-secret-value-should-not-print"
    artifact = _artifact(
        operatorNotes={
            "sessionCookie": secret_value,
            "debugTrace": "Traceback (most recent call last): sanitized",
        },
        userImpactSummary="Operator pasted cookie and stack trace markers by mistake.",
    )
    path = _write_json(tmp_path, artifact)

    result = _run_validator(path)

    assert result.returncode == 1
    assert secret_value not in result.stdout
    assert secret_value not in result.stderr
    payload = _stdout_json(result)
    assert {
        finding["reasonCode"] for finding in payload["findings"]
    } >= {"secret_or_cookie_marker_forbidden", "raw_debug_or_trace_marker_forbidden"}


def test_launch_approved_claims_are_rejected(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path,
        _artifact(
            launchApproved=True,
            userImpactSummary="Launch-approved. GO for public launch.",
        ),
    )

    result = _run_validator(path)

    assert result.returncode == 1
    payload = _stdout_json(result)
    assert {
        finding["reasonCode"] for finding in payload["findings"]
    } >= {"launch_approval_claim_forbidden"}
