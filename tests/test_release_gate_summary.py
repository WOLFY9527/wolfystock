from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import yaml
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_SCRIPT = REPO_ROOT / "scripts" / "release_candidate.py"
SUMMARY_SCRIPT = REPO_ROOT / "scripts" / "release_gate_summary.py"
REQUIRED_GATES = (
    "backend-canonical",
    "authoritative-topology",
    "full-vitest",
    "frontend-lint",
    "frontend-typecheck",
    "production-build",
    "playwright-real-runtime",
    "runtime-uat",
    "auth-rbac",
    "operator-evidence",
    "secret-private-path-scan",
    "artifact-provenance",
)
REQUIRED_BROWSER_CASES = (
    "production startup readiness and static assets",
    "login logout and revoked session",
    "member admin boundary and portfolio read",
    "rollback error preserves portfolio state and exposes unavailable data",
)
LOCK_HASH = "7a3c9f1c582c0efb5ae48ae4871cb4cae77db9c257558cbf9af2c454013a46f4"
AMD64_PROJECTION = "231e24f155659cde4c0474d1859f78ed8f76a63e311a0e02f5f60d59c7202d86"
ARM64_PROJECTION = "d79ef9a552f1298b9a241952c1a26298543fe4d836238aecbf6105bf75dd94ef"


def _run(*args: object, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def _write_oci_fixture(path: Path) -> dict[str, object]:
    platform_blobs = {
        platform: json.dumps(
            {"schemaVersion": 2, "config": {}, "layers": [], "annotations": {"test.platform": platform}},
            sort_keys=True,
        ).encode()
        for platform in ("linux/amd64", "linux/arm64")
    }
    descriptors = []
    for platform, content in platform_blobs.items():
        os_name, architecture = platform.split("/")
        descriptors.append(
            {
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "digest": "sha256:" + hashlib.sha256(content).hexdigest(),
                "size": len(content),
                "platform": {"os": os_name, "architecture": architecture},
            }
        )
    image_index = json.dumps({"schemaVersion": 2, "manifests": descriptors}, sort_keys=True).encode()
    index_digest = "sha256:" + hashlib.sha256(image_index).hexdigest()
    layout = json.dumps(
        {
            "schemaVersion": 2,
            "manifests": [
                {
                    "mediaType": "application/vnd.oci.image.index.v1+json",
                    "digest": index_digest,
                    "size": len(image_index),
                }
            ],
        },
        sort_keys=True,
    ).encode()
    with tarfile.open(path, "w") as archive:
        for name, content in [
            ("index.json", layout),
            (f"blobs/sha256/{index_digest.removeprefix('sha256:')}", image_index),
            *[
                (f"blobs/sha256/{hashlib.sha256(content).hexdigest()}", content)
                for content in platform_blobs.values()
            ],
        ]:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return {
        "schemaVersion": "wolfystock_oci_image_index_v1",
        "archiveSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "indexDigest": index_digest,
        "sourceReference": "ghcr.io/owner/repository@" + index_digest,
        "platforms": {
            platform: {"digest": descriptor["digest"]}
            for platform, descriptor in zip(platform_blobs, descriptors, strict=True)
        },
    }


def _build_candidate(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    artifact_dir = tmp_path / "candidate"
    artifact_dir.mkdir()
    for name, content in {
        "source.tar.gz": b"source-candidate",
        "web-static.tar.gz": b"web-candidate",
    }.items():
        (artifact_dir / name).write_bytes(content)
    image_evidence = _write_oci_fixture(artifact_dir / "docker-multiarch.oci.tar")
    manifest_path = artifact_dir / "release-candidate.json"
    artifact_args = [
        value
        for path in sorted(artifact_dir.iterdir())
        for value in ("--artifact", f"{path.name}={path}")
    ]
    environment = {
        "status": "PASS",
        "environmentEvidence": {
            "schemaVersion": "wolfystock_environment_evidence_v1",
            "environmentFingerprint": "1" * 64,
            "componentFingerprints": {
                "python": {"input": "2" * 64, "installed": "3" * 64},
                "web": {"input": "4" * 64, "installed": "5" * 64},
            },
            "manifestHashes": {"apps/dsa-web/package-lock.json": "6" * 64},
            "pythonLock": {
                "schemaVersion": "wolfystock_python_lock_v2",
                "policyVersion": "wolfystock_python_lock_policy_v2",
                "contentHash": LOCK_HASH,
                "inputHashes": {"requirements.txt": "7" * 64, "requirements-dev.txt": "8" * 64},
                "selectedTarget": {
                    "os": "Linux",
                    "architecture": "x86_64",
                    "implementation": "CPython",
                    "pythonVersion": "3.11",
                    "abi": "cp311",
                    "platform": "manylinux_2_36_x86_64",
                },
                "selectedProfile": "development",
                "selectedProjection": "linux-x86_64-cpython311-development",
                "selectedProjectionHash": "9" * 64,
                "resolver": {"implementation": "uv", "version": "0.11.19"},
                "hashVerification": True,
            },
            "operational": {"bootstrapNetworkUsed": False, "runId": "qualify-test"},
        },
    }
    lock = {
        "status": "ok",
        "schemaVersion": "wolfystock_python_lock_v2",
        "policyVersion": "wolfystock_python_lock_policy_v2",
        "contentHash": LOCK_HASH,
        "inputHashes": {"requirements.txt": "7" * 64, "requirements-dev.txt": "8" * 64},
        "resolver": {"implementation": "uv", "version": "0.11.19"},
        "targetProjections": {
            "linux-x86_64-cpython311-runtime": {"projectionHash": AMD64_PROJECTION},
            "linux-aarch64-cpython311-runtime": {"projectionHash": ARM64_PROJECTION},
        },
    }
    reports = {
        "environment.json": environment,
        "lock.json": lock,
        "web.json": {
            "ok": True,
            "errorCodes": [],
            "manifest": {
                "contract": "wolfystock_web_build_artifact_v1",
                "candidate": {"commit": "a" * 40, "dirty": False},
                "fingerprint": "f" * 64,
                "assets": [{"path": "assets/index.js", "sha256": "e" * 64}],
            },
        },
        "image.json": image_evidence,
        "workflow.json": {
            "repository": "owner/repository",
            "workflowRef": "owner/repository/.github/workflows/release.yml@refs/heads/main",
            "workflowSha": "a" * 40,
            "runId": "123",
            "runAttempt": "1",
            "releaseTag": "v1.2.3",
            "tagObjectSha": "0" * 40,
        },
    }
    for name, payload in reports.items():
        (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")
    result = _run(
        sys.executable,
        CANDIDATE_SCRIPT,
        "build",
        "--commit-sha",
        "a" * 40,
        "--output",
        manifest_path,
        "--environment-evidence",
        tmp_path / "environment.json",
        "--python-lock-report",
        tmp_path / "lock.json",
        "--web-build-report",
        tmp_path / "web.json",
        "--image-evidence",
        tmp_path / "image.json",
        "--workflow-identity",
        tmp_path / "workflow.json",
        *artifact_args,
    )
    assert result.returncode == 0, result.stderr
    return manifest_path, artifact_dir, json.loads(manifest_path.read_text(encoding="utf-8"))


def _gate_details(gate_id: str, candidate: dict[str, object]) -> dict[str, object]:
    if gate_id == "playwright-real-runtime":
        return {
            "project": "release-real-runtime",
            "mockedRouteSuites": 0,
            "retriesObserved": 0,
            "requiredCases": list(REQUIRED_BROWSER_CASES),
            "firstAttempt": {
                "total": len(REQUIRED_BROWSER_CASES),
                "passed": len(REQUIRED_BROWSER_CASES),
                "failed": 0,
                "skipped": 0,
            },
        }
    if gate_id == "runtime-uat":
        return {
            "contract": "wolfystock_uat_runtime_harness_v1",
            "candidateSha": "a" * 40,
            "environmentFingerprint": "1" * 64,
            "runtimeCwd": "$WORKTREE",
            "assetFingerprint": "f" * 64,
            "summaryStatus": "PASS",
            "exitCode": 0,
            "requiredChecks": {
                name: "PASS"
                for name in (
                    "localBuild",
                    "runtimeBundle",
                    "publicRoutes",
                    "runtimeAuthMode",
                    "authenticatedRoutes",
                    "adminOpsStatus",
                    "surfaceReadiness",
                )
            },
        }
    if gate_id == "secret-private-path-scan":
        return {
            "scanSchema": "wolfystock_release_secret_scan_v1",
            "scanMode": "candidate",
            "scannedCommit": "a" * 40,
            "fileCount": 17,
            "privatePathScan": "PASS",
        }
    if gate_id == "auth-rbac":
        return {
            "auditStatus": "manual_review_required",
            "surfaceCount": 1,
            "riskyFindingCount": 0,
            "manualReviewRequired": True,
            "networkCallsExecuted": False,
        }
    if gate_id == "operator-evidence":
        return {
            "bundleSchema": "wolfystock_operator_evidence_bundle_summary_v1",
            "bundleStatus": "complete-review-required",
            "releaseCandidateSha": "a" * 40,
            "environment": "release-approval",
        }
    if gate_id == "artifact-provenance":
        artifacts = candidate["artifacts"]
        assert isinstance(artifacts, list)
        return {
            "provenanceAttested": True,
            "artifactDigests": {str(item["name"]): str(item["sha256"]) for item in artifacts},
            "imageIndexDigest": candidate["images"]["indexDigest"],
            "imagePlatformDigests": {
                platform: details["digest"]
                for platform, details in candidate["images"]["platforms"].items()
            },
        }
    if gate_id == "production-build":
        return {
            "artifactContract": "wolfystock_web_build_artifact_v1",
            "artifactCandidateSha": "a" * 40,
            "artifactFingerprint": "f" * 64,
            "assetCount": 1,
        }
    return {"commandExitCode": 0}


def _write_evidence(evidence_dir: Path, candidate: dict[str, object], *, omit: str | None = None) -> None:
    evidence_dir.mkdir()
    for gate_id in REQUIRED_GATES:
        if gate_id == omit:
            continue
        payload = {
            "schemaVersion": "wolfystock_release_gate_evidence_v2",
            "gateId": gate_id,
            "status": "PASS",
            "candidateSha": candidate["commitSha"],
            "candidateDigest": candidate["candidateDigest"],
            "environmentFingerprint": candidate["environment"]["fingerprint"],
            "pythonLockContentHash": candidate["pythonLock"]["contentHash"],
            "imageIndexDigest": candidate["images"]["indexDigest"],
            "imagePlatformDigests": {
                platform: details["digest"]
                for platform, details in candidate["images"]["platforms"].items()
            },
            "details": _gate_details(gate_id, candidate),
        }
        (evidence_dir / f"{gate_id}.json").write_text(
            json.dumps(payload, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _qualify(manifest: Path, evidence_dir: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return _run(
        sys.executable,
        SUMMARY_SCRIPT,
        "qualify",
        "--candidate",
        manifest,
        "--evidence-dir",
        evidence_dir,
        "--environment-evidence",
        manifest.parent.parent / "environment.json",
        "--python-lock-report",
        manifest.parent.parent / "lock.json",
        "--output",
        output,
    )


def test_release_gate_summary_prints_required_fields_on_clean_repo(tmp_path):
    manifest, artifact_dir, candidate = _build_candidate(tmp_path)
    evidence_dir = tmp_path / "evidence"
    qualification = tmp_path / "qualification.json"
    _write_evidence(evidence_dir, candidate)

    verify_candidate = _run(
        sys.executable,
        CANDIDATE_SCRIPT,
        "verify",
        "--manifest",
        manifest,
        "--artifact-dir",
        artifact_dir,
        "--expected-sha",
        "a" * 40,
    )
    result = _qualify(manifest, evidence_dir, qualification)

    assert verify_candidate.returncode == 0, verify_candidate.stderr
    assert result.returncode == 0, result.stderr
    summary = json.loads(qualification.read_text(encoding="utf-8"))
    assert summary["schemaVersion"] == "wolfystock_release_qualification_v2"
    assert summary["finalStatus"] == "GO"
    assert summary["releaseApproved"] is True
    assert summary["candidateSha"] == "a" * 40
    assert summary["candidateDigest"] == candidate["candidateDigest"]
    assert summary["qualificationDigest"]
    assert [gate["gateId"] for gate in summary["gates"]] == list(REQUIRED_GATES)
    assert all(gate["status"] == "PASS" for gate in summary["gates"])


def test_release_gate_summary_go_no_go_json_keeps_launch_blocked(tmp_path):
    manifest, _artifact_dir, candidate = _build_candidate(tmp_path)
    evidence_dir = tmp_path / "evidence"
    qualification = tmp_path / "qualification.json"
    _write_evidence(evidence_dir, candidate, omit="runtime-uat")
    (evidence_dir / "frontend-lint.json").write_text("{malformed", encoding="utf-8")

    result = _qualify(manifest, evidence_dir, qualification)

    assert result.returncode == 1
    summary = json.loads(qualification.read_text(encoding="utf-8"))
    assert summary["finalStatus"] == "NO-GO"
    assert summary["releaseApproved"] is False
    gates = {gate["gateId"]: gate for gate in summary["gates"]}
    assert gates["runtime-uat"]["status"] == "MISSING"
    assert gates["frontend-lint"]["status"] == "MALFORMED"

    malformed_sources = {
        "secret-private-path-scan": {
            "status": "PASS",
            "scannedCommit": "a" * 40,
            "fileCount": 1,
            "privatePathScan": "PASS",
        },
        "runtime-uat": {
            "contract": "wolfystock_uat_runtime_harness_v1",
            "status": "PASS",
            "source": {"gitSha": "b" * 40},
            "run": {"sha": "b" * 40},
            "smokeReport": {
                "summaryStatus": "PASS",
                "exitCode": 0,
                "checks": {
                    name: "PASS" if name == "runtimeBundle" else {"status": "PASS"}
                    for name in (
                        "localBuild",
                        "runtimeBundle",
                        "publicRoutes",
                        "runtimeAuthMode",
                        "authenticatedRoutes",
                        "adminOpsStatus",
                        "surfaceReadiness",
                    )
                },
            },
        },
        "production-build": {"ok": True, "errorCodes": [], "manifest": {}},
    }
    for gate_id, payload in malformed_sources.items():
        source = tmp_path / f"{gate_id}-source.json"
        evidence = tmp_path / f"{gate_id}-evidence.json"
        source.write_text(json.dumps(payload), encoding="utf-8")
        record = _run(
            sys.executable,
            SUMMARY_SCRIPT,
            "record",
            "--candidate",
            manifest,
            "--gate-id",
            gate_id,
            "--source-report",
            source,
            "--output",
            evidence,
        )
        assert record.returncode == 1
        assert not evidence.exists()
        assert "[NO-GO]" in record.stderr
        assert "Traceback" not in record.stderr


@pytest.mark.parametrize("gate_id", REQUIRED_GATES)
def test_each_required_gate_failure_blocks_qualification(tmp_path: Path, gate_id: str) -> None:
    manifest, _artifact_dir, candidate = _build_candidate(tmp_path)
    evidence_dir = tmp_path / "evidence"
    qualification = tmp_path / "qualification.json"
    _write_evidence(evidence_dir, candidate)
    evidence = json.loads((evidence_dir / f"{gate_id}.json").read_text(encoding="utf-8"))
    evidence["status"] = "FAIL"
    (evidence_dir / f"{gate_id}.json").write_text(json.dumps(evidence), encoding="utf-8")

    result = _qualify(manifest, evidence_dir, qualification)

    assert result.returncode == 1
    summary = json.loads(qualification.read_text(encoding="utf-8"))
    selected = next(item for item in summary["gates"] if item["gateId"] == gate_id)
    assert selected["status"] == "FAIL"
    assert summary["releaseApproved"] is False


@pytest.mark.parametrize("status", ["FAIL", "SKIPPED", "CANCELLED", "NEUTRAL", "UNKNOWN", "NOT-RUN", "MISSING"])
def test_non_pass_gate_states_never_qualify(tmp_path: Path, status: str) -> None:
    manifest, _artifact_dir, candidate = _build_candidate(tmp_path)
    evidence_dir = tmp_path / "evidence"
    qualification = tmp_path / "qualification.json"
    _write_evidence(evidence_dir, candidate)
    path = evidence_dir / "backend-canonical.json"
    evidence = json.loads(path.read_text(encoding="utf-8"))
    evidence["status"] = status
    path.write_text(json.dumps(evidence), encoding="utf-8")

    result = _qualify(manifest, evidence_dir, qualification)

    assert result.returncode == 1
    summary = json.loads(qualification.read_text(encoding="utf-8"))
    assert summary["finalStatus"] == "NO-GO"
    assert summary["releaseApproved"] is False


@pytest.mark.parametrize(
    "field",
    [
        "candidateSha",
        "candidateDigest",
        "environmentFingerprint",
        "pythonLockContentHash",
        "imageIndexDigest",
        "imagePlatformDigests",
    ],
)
def test_gate_identity_mismatch_blocks_qualification(tmp_path: Path, field: str) -> None:
    manifest, _artifact_dir, candidate = _build_candidate(tmp_path)
    evidence_dir = tmp_path / "evidence"
    qualification = tmp_path / "qualification.json"
    _write_evidence(evidence_dir, candidate)
    path = evidence_dir / "backend-canonical.json"
    evidence = json.loads(path.read_text(encoding="utf-8"))
    evidence[field] = {} if field == "imagePlatformDigests" else "mismatch"
    path.write_text(json.dumps(evidence), encoding="utf-8")

    result = _qualify(manifest, evidence_dir, qualification)

    assert result.returncode == 1
    summary = json.loads(qualification.read_text(encoding="utf-8"))
    selected = next(item for item in summary["gates"] if item["gateId"] == "backend-canonical")
    assert selected["status"] == "FAIL"
    assert any(field in reason for reason in selected["reasonCodes"])


def test_release_gate_summary_completed_foundation_evidence_stays_non_approving(tmp_path):
    manifest, _artifact_dir, _candidate = _build_candidate(tmp_path)
    report = tmp_path / "playwright.json"
    evidence = tmp_path / "browser-evidence.json"
    report.write_text(
        json.dumps(
            {
                "suites": [
                    {
                        "specs": [
                            {
                                "title": title,
                                "tests": [
                                    {
                                        "projectName": "release-real-runtime",
                                        "status": "skipped" if index == 0 else "expected",
                                        "results": [
                                            {
                                                "retry": 1 if index == 1 else 0,
                                                "status": "skipped" if index == 0 else "passed",
                                            }
                                        ],
                                    }
                                ],
                            }
                            for index, title in enumerate(REQUIRED_BROWSER_CASES)
                        ]
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = _run(
        sys.executable,
        SUMMARY_SCRIPT,
        "record",
        "--candidate",
        manifest,
        "--gate-id",
        "playwright-real-runtime",
        "--source-report",
        report,
        "--browser-spec",
        REPO_ROOT / "apps/dsa-web/e2e/release-real-runtime.release.spec.ts",
        "--output",
        evidence,
    )

    assert result.returncode == 1
    assert not evidence.exists()
    assert "skip" in result.stderr.lower()
    assert "retry" in result.stderr.lower()

    operator_report = tmp_path / "operator-report.json"
    operator_report.write_text(
        json.dumps(
            {
                "schemaVersion": "wolfystock_operator_evidence_bundle_summary_v1",
                "bundleStatus": "complete-review-required",
            }
        ),
        encoding="utf-8",
    )
    operator_dir = tmp_path / "operator-evidence"
    operator_dir.mkdir()
    manual_review = operator_dir / "manual_release_approval_review_record.json"
    manual_review.write_text(
        json.dumps({"releaseCandidateSha": "b" * 40}),
        encoding="utf-8",
    )
    operator_evidence = tmp_path / "operator-evidence.json"
    operator_result = _run(
        sys.executable,
        SUMMARY_SCRIPT,
        "record",
        "--candidate",
        manifest,
        "--gate-id",
        "operator-evidence",
        "--source-report",
        operator_report,
        "--operator-evidence-dir",
        operator_dir,
        "--output",
        operator_evidence,
    )

    assert operator_result.returncode == 1
    assert not operator_evidence.exists()
    assert "candidate_sha_mismatch" in operator_result.stderr

    manual_review.write_text(
        json.dumps({"releaseCandidateSha": "a" * 40}),
        encoding="utf-8",
    )
    operator_result = _run(
        sys.executable,
        SUMMARY_SCRIPT,
        "record",
        "--candidate",
        manifest,
        "--gate-id",
        "operator-evidence",
        "--source-report",
        operator_report,
        "--operator-evidence-dir",
        operator_dir,
        "--detail",
        "environment=release-approval",
        "--output",
        operator_evidence,
    )
    assert operator_result.returncode == 0, operator_result.stderr

    auth_report = tmp_path / "auth-report.json"
    auth_report.write_text("{}", encoding="utf-8")
    auth_evidence = tmp_path / "auth-evidence.json"
    auth_result = _run(
        sys.executable,
        SUMMARY_SCRIPT,
        "record",
        "--candidate",
        manifest,
        "--gate-id",
        "auth-rbac",
        "--source-report",
        auth_report,
        "--output",
        auth_evidence,
    )

    assert auth_result.returncode == 1
    assert not auth_evidence.exists()
    assert "auth_rbac_audit_not_pass" in auth_result.stderr

    auth_report.write_text(
        json.dumps(
            {
                "auditStatus": "manual_review_required",
                "surfacesChecked": [{"label": "private-api", "status": "pass"}],
                "riskyFindings": [],
                "manualReviewRequired": True,
                "networkCallsExecuted": False,
            }
        ),
        encoding="utf-8",
    )
    auth_result = _run(
        sys.executable,
        SUMMARY_SCRIPT,
        "record",
        "--candidate",
        manifest,
        "--gate-id",
        "auth-rbac",
        "--source-report",
        auth_report,
        "--output",
        auth_evidence,
    )
    assert auth_result.returncode == 0, auth_result.stderr


def test_release_gate_summary_fails_on_dirty_repo_without_allow_dirty(tmp_path):
    manifest, artifact_dir, candidate = _build_candidate(tmp_path)
    evidence_dir = tmp_path / "evidence"
    qualification = tmp_path / "qualification.json"
    _write_evidence(evidence_dir, candidate)
    assert _qualify(manifest, evidence_dir, qualification).returncode == 0
    (artifact_dir / "source.tar.gz").write_bytes(b"tampered")

    result = _run(
        sys.executable,
        SUMMARY_SCRIPT,
        "verify-promotion",
        "--candidate",
        manifest,
        "--qualification",
        qualification,
        "--artifact-dir",
        artifact_dir,
        "--expected-sha",
        "a" * 40,
    )

    assert result.returncode == 1
    assert "artifact_digest_mismatch" in result.stderr

    (artifact_dir / "source.tar.gz").write_bytes(b"source-candidate")
    tampered_qualification = json.loads(qualification.read_text(encoding="utf-8"))
    tampered_qualification["gates"].append("malformed-extra-gate")
    tampered_qualification.pop("qualificationDigest")
    tampered_qualification["qualificationDigest"] = hashlib.sha256(
        json.dumps(
            tampered_qualification,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    qualification.write_text(json.dumps(tampered_qualification), encoding="utf-8")
    malformed_qualification = _run(
        sys.executable,
        SUMMARY_SCRIPT,
        "verify-promotion",
        "--candidate",
        manifest,
        "--qualification",
        qualification,
        "--artifact-dir",
        artifact_dir,
        "--expected-sha",
        "a" * 40,
    )
    assert malformed_qualification.returncode == 1
    assert "qualification_required_gates_not_pass" in malformed_qualification.stderr

    empty_dir = tmp_path / "empty-candidate"
    empty_dir.mkdir()
    for name in (
        "source.tar.gz",
        "web-static.tar.gz",
        "docker-multiarch.oci.tar",
    ):
        (empty_dir / name).write_bytes(b"" if name == "source.tar.gz" else b"candidate")
    empty_result = _run(
        sys.executable,
        CANDIDATE_SCRIPT,
        "build",
        "--commit-sha",
        "a" * 40,
        "--output",
        empty_dir / "release-candidate.json",
        "--environment-evidence",
        tmp_path / "environment.json",
        "--python-lock-report",
        tmp_path / "lock.json",
        "--web-build-report",
        tmp_path / "web.json",
        "--image-evidence",
        tmp_path / "image.json",
        "--workflow-identity",
        tmp_path / "workflow.json",
        *[
            value
            for path in sorted(empty_dir.iterdir())
            for value in ("--artifact", f"{path.name}={path}")
        ],
    )
    assert empty_result.returncode == 1
    assert "artifact_empty:source.tar.gz" in empty_result.stderr


def test_release_gate_summary_allows_dirty_repo_with_explicit_flag(tmp_path):
    release_workflow = REPO_ROOT / ".github/workflows/release.yml"
    legacy_workflows = (
        "create-release.yml",
        "desktop-release.yml",
        "docker-publish.yml",
        "ghcr-dockerhub.yml",
    )
    assert release_workflow.is_file()
    assert all(not (REPO_ROOT / ".github/workflows" / name).exists() for name in legacy_workflows)
    assert not (REPO_ROOT / "scripts/release_gate_summary.sh").exists()
    assert SUMMARY_SCRIPT.is_file()

    release_text = release_workflow.read_text(encoding="utf-8")
    jobs = yaml.safe_load(release_text)["jobs"]
    qualification_steps = jobs["qualification"]["steps"]
    gate_step_names = {
        step.get("name", "").removeprefix("Gate - ")
        for step in qualification_steps
        if isinstance(step, dict) and str(step.get("name", "")).startswith("Gate - ")
    }
    assert set(REQUIRED_GATES) == gate_step_names
    for job_id in ("promote-github-release", "promote-docker-multiarch"):
        needs = jobs[job_id]["needs"]
        needs = [needs] if isinstance(needs, str) else needs
        assert "promotion-ready" in needs
        job_text = json.dumps(jobs[job_id], sort_keys=True)
        assert "docker buildx build" not in job_text
        assert "build-all" not in job_text
        assert "npm run build" not in job_text
    for job_id in ("promotion-ready", "promote-github-release"):
        checkout = next(
            step
            for step in jobs[job_id]["steps"]
            if isinstance(step, dict) and str(step.get("uses", "")).startswith("actions/checkout@")
        )
        assert checkout.get("with", {}).get("ref") == "${{ needs.identity.outputs.sha }}"
    assert "candidateDigest" in release_text
    assert "verify-promotion" in release_text
    assert "docker buildx imagetools create" in release_text
    assert "immutable image destination already exists" in release_text
    assert "--operator-evidence-dir output/release/operator-evidence" in release_text
    assert "npm --prefix apps/dsa-web test -- --maxWorkers=1" in release_text

    ci_text = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "npm --prefix apps/dsa-web test -- --maxWorkers=1" in ci_text
    assert "npm --prefix apps/dsa-web run lint" in ci_text
    assert "python scripts/web_build_artifact.py typecheck" in ci_text
    assert "python scripts/web_build_artifact.py build" in ci_text
    assert "needs.changes.outputs.frontend" not in ci_text

    playwright_text = (REPO_ROOT / "apps/dsa-web/playwright.config.ts").read_text(encoding="utf-8")
    browser_spec = REPO_ROOT / "apps/dsa-web/e2e/release-real-runtime.release.spec.ts"
    assert "name: 'release-real-runtime'" in playwright_text
    assert "retries: 0" in playwright_text
    assert "release-real-runtime.release.spec.ts" in playwright_text
    assert browser_spec.is_file()
    spec_text = browser_spec.read_text(encoding="utf-8")
    assert ".route(" not in spec_text
    for title in REQUIRED_BROWSER_CASES:
        assert title in spec_text
