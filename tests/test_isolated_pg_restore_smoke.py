from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "isolated_pg_restore_smoke.py"


def _run_helper(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _output(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def _valid_artifact() -> dict:
    return {
        "schemaVersion": "wolfystock_isolated_pg_restore_smoke_input_v1",
        "isolatedTargetLabel": "isolated-pg-restore-smoke-20260611",
        "restoreTimestamp": "2026-06-11T03:10:00Z",
        "pitrTargetTimestamp": "2026-06-11T03:00:00Z",
        "sourceEnvironment": "synthetic",
        "restoreEvidence": {
            "status": "pass",
            "artifactRef": "backup-ref:sha256-restore-smoke",
            "restoreExecuted": True,
        },
        "pitrEvidence": {
            "status": "pass",
            "artifactRef": "pitr-ref:sha256-wal-window",
            "pitrExecuted": True,
        },
        "appBootReadinessSmoke": {
            "status": "pass",
            "evidenceRef": "readiness-ref:smoke-pass",
        },
        "ownerIsolationSmoke": {
            "status": "pass",
            "evidenceRef": "owner-isolation-ref:smoke-pass",
        },
        "checksumManifestRefs": [
            "sha256:restore-smoke-manifest",
            "manifest-ref:restore-smoke-summary",
        ],
        "noSecretConfirmation": True,
        "teardownQuarantineConfirmation": {
            "status": "pass",
            "evidenceRef": "quarantine-ref:restored-target-locked",
        },
        "blockers": [],
    }


def test_default_dry_run_outputs_no_network_no_db_no_launch_ready() -> None:
    result = _run_helper()

    assert result.returncode == 0
    payload = _output(result)
    assert payload["mode"] == "dry-run"
    assert payload["finalStatus"] == "DRY-RUN"
    assert payload["dryRun"] is True
    assert payload["networkCallsEnabled"] is False
    assert payload["databaseCommandsRunByValidator"] is False
    assert payload["restoreCommandsRunByValidator"] is False
    assert payload["productionStorageTouched"] is False
    assert payload["publicLaunchReady"] is False
    assert payload["checks"][0]["id"] == "dry_run_no_artifact_supplied"


def test_script_does_not_import_network_db_or_restore_runners() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    for forbidden in (
        "import socket",
        "import urllib",
        "import subprocess",
        "import psycopg",
        "import psycopg2",
        "from sqlalchemy",
        "os.environ",
        "subprocess.",
    ):
        assert forbidden not in source


def test_valid_sanitized_evidence_passes_but_public_launch_remains_false(tmp_path: Path) -> None:
    artifact = tmp_path / "isolated-pg-restore-smoke.json"
    artifact.write_text(json.dumps(_valid_artifact()), encoding="utf-8")

    result = _run_helper("--artifact", str(artifact))

    assert result.returncode == 0
    payload = _output(result)
    assert payload["schemaVersion"] == "wolfystock_isolated_pg_restore_smoke_v1"
    assert payload["finalStatus"] == "EVIDENCE-READY"
    assert payload["publicLaunchReady"] is False
    assert payload["databaseCommandsRunByValidator"] is False
    assert payload["artifactSummary"] == {
        "isolatedTargetLabel": "isolated-pg-restore-smoke-20260611",
        "sourceEnvironment": "synthetic",
        "hasPitrTargetTimestamp": True,
        "checksumManifestRefCount": 2,
    }
    assert {check["status"] for check in payload["checks"]} == {"pass"}


def test_missing_restore_or_pitr_evidence_returns_no_go(tmp_path: Path) -> None:
    payload = _valid_artifact()
    del payload["pitrEvidence"]
    payload["pitrTargetTimestamp"] = ""
    artifact = tmp_path / "missing-pitr-evidence.json"
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_helper("--artifact", str(artifact))

    assert result.returncode == 1
    output = _output(result)
    assert output["finalStatus"] == "NO-GO"
    checks = {check["id"]: check for check in output["checks"]}
    assert checks["restore_and_pitr_evidence_present"]["status"] == "fail"
    assert checks["restore_timestamps_are_valid"]["status"] == "fail"
    assert output["publicLaunchReady"] is False


def test_raw_dsn_token_or_path_fails_redaction_without_echoing(tmp_path: Path) -> None:
    raw_dsn = "postgresql://" + "restore_user:redacted-password@" + "prod.example.invalid:5432/wolfystock_prod"
    raw_token = "access_token=" + "plain-text-token"
    raw_path = "/var/" + "lib/postgresql/prod.dump"
    raw_host = "prod." + "db.example.invalid"
    credential_url = "https://" + "restore-user:restore-pass@" + "db.example.invalid/restore"
    payload = _valid_artifact()
    payload["operatorNotes"] = {
        "rawDsn": raw_dsn,
        "tokenHint": raw_token,
        "backupPath": raw_path,
        "hostLabel": raw_host,
        "credentialUrl": credential_url,
    }
    artifact = tmp_path / "unsafe-restore-evidence.json"
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_helper("--artifact", str(artifact))

    combined_output = result.stdout + result.stderr
    assert result.returncode == 1
    assert raw_dsn not in combined_output
    assert raw_token not in combined_output
    assert raw_path not in combined_output
    assert raw_host not in combined_output
    assert credential_url not in combined_output
    output = _output(result)
    checks = {check["id"]: check for check in output["checks"]}
    assert checks["artifact_contains_no_raw_dsn_secret_or_path_values"]["status"] == "fail"
    assert checks["artifact_contains_no_raw_dsn_secret_or_path_values"]["evidence"]["findingValuesIncluded"] is False


def test_production_looking_target_without_isolated_marker_fails(tmp_path: Path) -> None:
    payload = _valid_artifact()
    payload["isolatedTargetLabel"] = "production-primary-restore"
    artifact = tmp_path / "production-target-evidence.json"
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    result = _run_helper("--artifact", str(artifact))

    assert result.returncode == 1
    output = _output(result)
    checks = {check["id"]: check for check in output["checks"]}
    assert checks["restore_target_is_explicitly_isolated"]["status"] == "fail"
    assert output["publicLaunchReady"] is False
