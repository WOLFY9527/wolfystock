from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Callable

import pytest

from tests import test_config_snapshot_evidence_check as config_snapshot
from tests import test_manual_release_approval_evidence_check as manual_release
from tests import test_operator_evidence_bundle_check as bundle_check
from tests import test_operator_evidence_manifest_check as manifest_check
from tests import test_provider_operator_evidence_check as provider
from tests import test_quota_operator_evidence_check as quota
from tests import test_release_review_report_render as report_render
from tests import test_restore_pitr_operator_evidence_check as restore_pitr
from tests import test_security_operator_acceptance_check as security_acceptance
from tests import test_staging_ingress_operator_evidence_check as staging_ingress
from tests import test_ws2_sse_operator_decision_check as ws2_sse


REPO_ROOT = Path(__file__).resolve().parents[1]

SECRET_AND_RAW_VALUES = (
    "token=matrix-token-value-should-not-leak",
    "api_key=matrix-api-key-value-should-not-leak",
    "password=matrix-password-value-should-not-leak",
    "secret=matrix-secret-value-should-not-leak",
    "Be" "arer matrix-bearer-value-should-not-leak-123456",
    "session=matrix-session-value-should-not-leak",
    "cookie=matrix-cookie-value-should-not-leak",
    "-----BEGIN " "PRIVATE KEY-----matrix-private-key-value-should-not-leak-----END PRIVATE KEY-----",
    "postgresql://matrix_user:matrix-dsn-password-should-not-leak@db.example.invalid/wolfystock",
    "Auth" "orization: " "Be" "arer matrix-authorization-value-should-not-leak",
    "Set-Cookie: sid=matrix-set-cookie-value-should-not-leak",
    "matrix-raw-request-body-value-should-not-leak",
    "matrix-raw-response-body-value-should-not-leak",
    "matrix-raw-log-value-should-not-leak",
    "matrix-debug-payload-value-should-not-leak",
    "Traceback (most recent call last): matrix-traceback-value-should-not-leak",
    "stack trace matrix-stack-trace-value-should-not-leak",
    "../matrix-path-traversal-value-should-not-leak.json",
    "/etc/matrix-sensitive-path-value-should-not-leak",
)

LAUNCH_WORDING_VALUES = (
    "launch-approved matrix-launch-approved-value-should-not-leak",
    "production-ready matrix-production-ready-value-should-not-leak",
    "automatic-GO matrix-automatic-go-value-should-not-leak",
    "release-approved matrix-release-approved-value-should-not-leak",
)


def _adversarial_payload() -> dict[str, object]:
    return {
        "token": SECRET_AND_RAW_VALUES[0],
        "api_key": SECRET_AND_RAW_VALUES[1],
        "password": SECRET_AND_RAW_VALUES[2],
        "secret": SECRET_AND_RAW_VALUES[3],
        "bearer": SECRET_AND_RAW_VALUES[4],
        "session": SECRET_AND_RAW_VALUES[5],
        "cookie": SECRET_AND_RAW_VALUES[6],
        "private_key": SECRET_AND_RAW_VALUES[7],
        "dsn": SECRET_AND_RAW_VALUES[8],
        "headers": {
            "Authorization": SECRET_AND_RAW_VALUES[9],
            "Set-Cookie": SECRET_AND_RAW_VALUES[10],
        },
        "raw_request_body": SECRET_AND_RAW_VALUES[11],
        "raw_response_body": SECRET_AND_RAW_VALUES[12],
        "raw_log": SECRET_AND_RAW_VALUES[13],
        "debug_payload": SECRET_AND_RAW_VALUES[14],
        "traceback": SECRET_AND_RAW_VALUES[15],
        "stack_trace": SECRET_AND_RAW_VALUES[16],
        "pathTraversalAttempt": SECRET_AND_RAW_VALUES[17],
        "absoluteSensitivePath": SECRET_AND_RAW_VALUES[18],
    }


def _write_payload(tmp_path: Path, filename: str, payload: object) -> Path:
    path = tmp_path / filename
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout + result.stderr


def _assert_rejected_without_leaks(
    result: subprocess.CompletedProcess[str],
    raw_values: tuple[str, ...],
) -> None:
    combined = _combined_output(result)
    assert result.returncode != 0
    for raw_value in raw_values:
        assert raw_value not in combined


ValidatorRun = Callable[[Path, dict[str, object]], subprocess.CompletedProcess[str]]


def _run_provider(tmp_path: Path, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return provider._run_validator(provider._write_json(tmp_path, payload))


def _run_restore_pitr(tmp_path: Path, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return restore_pitr._run_helper("--artifact", str(_write_payload(tmp_path, "restore-pitr.json", payload)))


def _run_security(tmp_path: Path, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return security_acceptance._run_helper(_write_payload(tmp_path, "security-acceptance.json", payload))


def _run_quota(tmp_path: Path, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return quota._run_validator(quota._write_json(tmp_path, payload))


def _run_staging_ingress(tmp_path: Path, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return staging_ingress._run_validator(staging_ingress._write_json(tmp_path, payload))


def _run_ws2_sse(tmp_path: Path, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return ws2_sse._run_validator(ws2_sse._write_json(tmp_path, payload))


def _run_config_snapshot(tmp_path: Path, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return config_snapshot._run_validator(config_snapshot._write_json(tmp_path, payload))


def _run_manual_release(tmp_path: Path, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return manual_release._run_validator(manual_release._write_json(tmp_path, payload))


VALIDATOR_CASES: tuple[tuple[str, Callable[[], dict[str, object]], ValidatorRun], ...] = (
    ("provider", provider._artifact, _run_provider),
    ("restore-pitr", restore_pitr._accepted_artifact, _run_restore_pitr),
    ("security", security_acceptance._accepted_artifact, _run_security),
    ("quota-budget", quota._artifact, _run_quota),
    ("staging-ingress", staging_ingress._artifact, _run_staging_ingress),
    ("ws2-sse", ws2_sse._artifact, _run_ws2_sse),
    ("config-snapshot", config_snapshot._artifact, _run_config_snapshot),
    ("manual-release", manual_release._artifact, _run_manual_release),
)


@pytest.mark.parametrize(("name", "factory", "runner"), VALIDATOR_CASES)
def test_offline_validators_reject_secret_raw_and_path_markers_without_leaking_values(
    tmp_path: Path,
    name: str,
    factory: Callable[[], dict[str, object]],
    runner: ValidatorRun,
) -> None:
    payload = factory()
    payload["adversarialMatrix"] = _adversarial_payload()

    result = runner(tmp_path, payload)

    _assert_rejected_without_leaks(result, SECRET_AND_RAW_VALUES), name


@pytest.mark.parametrize(("name", "factory", "runner"), VALIDATOR_CASES)
@pytest.mark.parametrize("wording", LAUNCH_WORDING_VALUES)
def test_offline_validators_reject_launch_approval_wording_without_leaking_values(
    tmp_path: Path,
    name: str,
    factory: Callable[[], dict[str, object]],
    runner: ValidatorRun,
    wording: str,
) -> None:
    payload = factory()
    payload["operatorConclusion"] = wording

    result = runner(tmp_path, payload)

    _assert_rejected_without_leaks(result, (wording,))
    assert "launch" in _combined_output(result).lower(), name


def test_manifest_verifier_redacts_artifact_bodies_and_path_traversal_attempts(tmp_path: Path) -> None:
    artifact_dir = manifest_check._write_artifact_dir(tmp_path, unsafe_value=SECRET_AND_RAW_VALUES[0])
    manifest = tmp_path / "manifest.json"
    assert manifest_check._create_manifest(artifact_dir, manifest).returncode == 0

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["entries"].append(
        {
            "category": "provider",
            "fileLabel": "../matrix-manifest-traversal-value-should-not-leak.json",
            "sha256": "0" * 64,
            "byteSize": 1,
            "generatedAt": "2026-05-08T00:00:00+00:00",
            "rawBody": SECRET_AND_RAW_VALUES[1],
        }
    )
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    result = manifest_check._verify_manifest(artifact_dir, manifest)

    _assert_rejected_without_leaks(
        result,
        (
            SECRET_AND_RAW_VALUES[0],
            SECRET_AND_RAW_VALUES[1],
            "../matrix-manifest-traversal-value-should-not-leak.json",
        ),
    )
    summary = json.loads(result.stdout)
    assert summary["rawArtifactBodiesIncluded"] is False
    reason_codes = {finding["reasonCode"] for finding in summary["findings"]}
    assert {"path_traversal_rejected", "unsafe_manifest_field"}.issubset(reason_codes)


def test_bundle_checker_summary_redacts_raw_artifact_bodies(tmp_path: Path) -> None:
    artifacts = bundle_check._accepted_artifacts()
    artifacts["provider_operator_evidence.json"] = bundle_check._provider_artifact(
        api_key=SECRET_AND_RAW_VALUES[1],
        raw_request_body=SECRET_AND_RAW_VALUES[11],
        notes=LAUNCH_WORDING_VALUES[3],
    )

    result = bundle_check._run_checker(bundle_check._write_bundle(tmp_path, artifacts))

    _assert_rejected_without_leaks(
        result,
        (
            SECRET_AND_RAW_VALUES[1],
            SECRET_AND_RAW_VALUES[11],
            LAUNCH_WORDING_VALUES[3],
        ),
    )
    summary = json.loads(result.stdout)
    assert summary["rawArtifactBodiesIncluded"] is False
    provider_summary = next(artifact for artifact in summary["artifacts"] if artifact["category"] == "provider")
    assert provider_summary["status"] == "rejected"


def test_review_report_renderer_redacts_unsafe_marker_values(tmp_path: Path) -> None:
    bundle = report_render._bundle_summary(status="rejected-no-go")
    bundle["artifactDirectoryLabel"] = "release-approved matrix-report-directory-should-not-leak"
    bundle["artifacts"].append(
        {
            "category": SECRET_AND_RAW_VALUES[1],
            "pathLabel": "../token-matrix-report-path-value-should-not-leak.json",
            "status": "rejected",
            "validatorName": "traceback-secret-validator.py",
            "blockingReasonSummaries": [
                SECRET_AND_RAW_VALUES[9],
                LAUNCH_WORDING_VALUES[1],
                LAUNCH_WORDING_VALUES[3],
            ],
        }
    )
    manifest = report_render._manifest_summary()
    manifest["blockingReasonSummaries"] = [SECRET_AND_RAW_VALUES[10], LAUNCH_WORDING_VALUES[2]]

    result = report_render._run_renderer(tmp_path, bundle, manifest=manifest)

    assert result.returncode == 1
    combined = _combined_output(result)
    for raw_value in (
        SECRET_AND_RAW_VALUES[1],
        SECRET_AND_RAW_VALUES[9],
        SECRET_AND_RAW_VALUES[10],
        LAUNCH_WORDING_VALUES[1],
        LAUNCH_WORDING_VALUES[2],
        LAUNCH_WORDING_VALUES[3],
        "../token-matrix-report-path-value-should-not-leak.json",
    ):
        assert raw_value not in combined
    assert "[redacted]" in result.stdout
