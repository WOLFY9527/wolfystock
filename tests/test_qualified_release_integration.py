from __future__ import annotations

import hashlib
import io
import json
import os
import sqlite3
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_SCRIPT = ROOT / "scripts" / "release_candidate.py"
SHA = "a" * 40
LOCK_HASH = "7a3c9f1c582c0efb5ae48ae4871cb4cae77db9c257558cbf9af2c454013a46f4"
AMD64_PROJECTION = "231e24f155659cde4c0474d1859f78ed8f76a63e311a0e02f5f60d59c7202d86"
ARM64_PROJECTION = "d79ef9a552f1298b9a241952c1a26298543fe4d836238aecbf6105bf75dd94ef"


def _run(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_release_runtime_fixture_assigns_explicit_super_admin_without_secret_output(tmp_path: Path) -> None:
    database_path = tmp_path / "release-browser.sqlite"
    env_path = tmp_path / "release.env"
    env_path.write_text(
        "\n".join(
            (
                "APP_ENV=test",
                "ADMIN_AUTH_ENABLED=true",
                f"DATABASE_PATH={database_path}",
                "POSTGRES_PHASE_A_URL=",
                "WOLFYSTOCK_RELEASE_ADMIN_USERNAME=admin",
                "WOLFYSTOCK_RELEASE_ADMIN_PASSWORD=release-admin-password",
                "WOLFYSTOCK_RELEASE_MEMBER_USERNAME=release-member",
                "WOLFYSTOCK_RELEASE_MEMBER_PASSWORD=release-member-password",
                "",
            )
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update(
        {
            "ADMIN_AUTH_ENABLED": "true",
            "APP_ENV": "test",
            "DATABASE_PATH": str(database_path),
            "ENV_FILE": str(env_path),
        }
    )

    command = [sys.executable, str(ROOT / "scripts" / "release_runtime_fixture.py")]
    first = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, check=False)
    second = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, check=False)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert "release-admin-password" not in first.stdout + first.stderr
    assert "release-member-password" not in first.stdout + first.stderr
    with sqlite3.connect(database_path) as connection:
        roles = connection.execute(
            "SELECT role_key FROM admin_user_roles WHERE user_id = ? ORDER BY role_key",
            ("bootstrap-admin",),
        ).fetchall()
    assert roles == [("super-admin",)]


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _environment_report() -> dict[str, object]:
    return {
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
                "inputHashes": {
                    "requirements.txt": "7" * 64,
                    "requirements-dev.txt": "8" * 64,
                },
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


def _lock_report() -> dict[str, object]:
    return {
        "status": "ok",
        "schemaVersion": "wolfystock_python_lock_v2",
        "policyVersion": "wolfystock_python_lock_policy_v2",
        "contentHash": LOCK_HASH,
        "inputHashes": {
            "requirements.txt": "7" * 64,
            "requirements-dev.txt": "8" * 64,
        },
        "resolver": {"implementation": "uv", "version": "0.11.19"},
        "targetProjections": {
            "linux-x86_64-cpython311-runtime": {"projectionHash": AMD64_PROJECTION},
            "linux-aarch64-cpython311-runtime": {"projectionHash": ARM64_PROJECTION},
        },
    }


def _write_oci_fixture(path: Path) -> dict[str, object]:
    platform_blobs = {
        platform: json.dumps(
            {"schemaVersion": 2, "config": {}, "layers": [], "annotations": {"test.platform": platform}},
            sort_keys=True,
        ).encode()
        for platform in ("linux/amd64", "linux/arm64")
    }
    descriptors = [
        {
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "digest": "sha256:" + hashlib.sha256(content).hexdigest(),
            "size": len(content),
            "platform": {"os": platform.split("/")[0], "architecture": platform.split("/")[1]},
        }
        for platform, content in platform_blobs.items()
    ]
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
        _tar_member(archive, "index.json", layout)
        _tar_member(archive, f"blobs/sha256/{index_digest.removeprefix('sha256:')}", image_index)
        for content in platform_blobs.values():
            digest = hashlib.sha256(content).hexdigest()
            _tar_member(archive, f"blobs/sha256/{digest}", content)
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


def _candidate_inputs(tmp_path: Path) -> tuple[list[str], dict[str, Path]]:
    artifact_dir = tmp_path / "candidate"
    artifact_dir.mkdir()
    artifacts = {
        "source.tar.gz": b"source",
        "web-static.tar.gz": b"web",
    }
    artifact_args: list[str] = []
    for name, content in artifacts.items():
        path = artifact_dir / name
        path.write_bytes(content)
        artifact_args.extend(("--artifact", f"{name}={path}"))
    docker_archive = artifact_dir / "docker-multiarch.oci.tar"
    image_evidence = _write_oci_fixture(docker_archive)
    artifact_args.extend(("--artifact", f"docker-multiarch.oci.tar={docker_archive}"))
    reports = {
        "environment": _write_json(tmp_path / "environment.json", _environment_report()),
        "lock": _write_json(tmp_path / "lock.json", _lock_report()),
        "web": _write_json(
            tmp_path / "web.json",
            {
                "ok": True,
                "errorCodes": [],
                "manifest": {
                    "contract": "wolfystock_web_build_artifact_v1",
                    "candidate": {"commit": SHA, "dirty": False},
                    "fingerprint": "b" * 64,
                    "assets": [{"path": "assets/index.js", "sha256": "c" * 64}],
                },
            },
        ),
        "image": _write_json(tmp_path / "image.json", image_evidence),
        "workflow": _write_json(
            tmp_path / "workflow.json",
            {
                "repository": "owner/repository",
                "workflowRef": "owner/repository/.github/workflows/release.yml@refs/heads/main",
                "workflowSha": SHA,
                "runId": "1234",
                "runAttempt": "1",
                "releaseTag": "v1.2.3",
                "tagObjectSha": "0" * 40,
            },
        ),
    }
    return artifact_args, reports


def _build_candidate(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    artifact_args, reports = _candidate_inputs(tmp_path)
    return _run(
        sys.executable,
        CANDIDATE_SCRIPT,
        "build",
        "--commit-sha",
        SHA,
        "--environment-evidence",
        reports["environment"],
        "--python-lock-report",
        reports["lock"],
        "--web-build-report",
        reports["web"],
        "--image-evidence",
        reports["image"],
        "--workflow-identity",
        reports["workflow"],
        "--output",
        tmp_path / "release-candidate.json",
        *artifact_args,
    )


def test_candidate_binds_environment_lock_web_workflow_and_multiarch_identities(tmp_path: Path) -> None:
    result = _build_candidate(tmp_path)

    assert result.returncode == 0, result.stderr
    candidate = json.loads((tmp_path / "release-candidate.json").read_text(encoding="utf-8"))
    verified = _run(
        sys.executable,
        CANDIDATE_SCRIPT,
        "verify",
        "--manifest",
        tmp_path / "release-candidate.json",
        "--artifact-dir",
        tmp_path / "candidate",
        "--expected-sha",
        SHA,
    )
    assert verified.returncode == 0, verified.stderr
    assert candidate["schemaVersion"] == "wolfystock_release_candidate_v2"
    assert candidate["environment"]["fingerprint"] == "1" * 64
    assert candidate["environment"]["components"]["python"] == {"input": "2" * 64, "installed": "3" * 64}
    assert candidate["environment"]["components"]["web"] == {"input": "4" * 64, "installed": "5" * 64}
    assert candidate["pythonLock"]["contentHash"] == LOCK_HASH
    assert candidate["pythonLock"]["dockerRuntimeProjections"] == {
        "linux/amd64": {
            "selectedProjection": "linux-x86_64-cpython311-runtime",
            "projectionHash": AMD64_PROJECTION,
        },
        "linux/arm64": {
            "selectedProjection": "linux-aarch64-cpython311-runtime",
            "projectionHash": ARM64_PROJECTION,
        },
    }
    assert candidate["web"]["lockSha256"] == "6" * 64
    assert candidate["web"]["artifactFingerprint"] == "b" * 64
    assert candidate["images"]["platforms"]["linux/amd64"]["digest"].startswith("sha256:")
    assert candidate["images"]["platforms"]["linux/arm64"]["digest"].startswith("sha256:")
    assert candidate["workflowIdentity"]["workflowSha"] == SHA
    assert set(candidate["artifactDigests"]) == {
        "source.tar.gz",
        "web-static.tar.gz",
        "docker-multiarch.oci.tar",
    }


@pytest.mark.parametrize("invalid_field", ["top_status", "network_used", "lock_mismatch", "environment_fingerprint"])
def test_candidate_rejects_invalid_environment_or_lock_identity(tmp_path: Path, invalid_field: str) -> None:
    artifact_args, reports = _candidate_inputs(tmp_path)
    environment = json.loads(reports["environment"].read_text(encoding="utf-8"))
    lock = json.loads(reports["lock"].read_text(encoding="utf-8"))
    if invalid_field == "top_status":
        environment["status"] = "ok"
    elif invalid_field == "network_used":
        environment["environmentEvidence"]["operational"]["bootstrapNetworkUsed"] = True
    elif invalid_field == "lock_mismatch":
        lock["contentHash"] = "0" * 64
    else:
        environment["environmentEvidence"]["environmentFingerprint"] = "missing"
    _write_json(reports["environment"], environment)
    _write_json(reports["lock"], lock)

    result = _run(
        sys.executable,
        CANDIDATE_SCRIPT,
        "build",
        "--commit-sha",
        SHA,
        "--environment-evidence",
        reports["environment"],
        "--python-lock-report",
        reports["lock"],
        "--web-build-report",
        reports["web"],
        "--image-evidence",
        reports["image"],
        "--workflow-identity",
        reports["workflow"],
        "--output",
        tmp_path / "release-candidate.json",
        *artifact_args,
    )

    assert result.returncode == 1
    assert "[NO-GO]" in result.stderr


def _tar_member(archive: tarfile.TarFile, name: str, content: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(content)
    archive.addfile(info, io.BytesIO(content))


def test_oci_inspection_records_exact_index_and_platform_digests(tmp_path: Path) -> None:
    platform_blobs = {
        platform: json.dumps(
            {"schemaVersion": 2, "config": {}, "layers": [], "annotations": {"test.platform": platform}},
            sort_keys=True,
        ).encode()
        for platform in ("linux/amd64", "linux/arm64")
    }
    platform_descriptors = []
    for platform_name, content in platform_blobs.items():
        os_name, architecture = platform_name.split("/")
        platform_descriptors.append(
            {
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "digest": "sha256:" + hashlib.sha256(content).hexdigest(),
                "size": len(content),
                "platform": {"os": os_name, "architecture": architecture},
            }
        )
    image_index = json.dumps({"schemaVersion": 2, "manifests": platform_descriptors}, sort_keys=True).encode()
    index_digest = "sha256:" + hashlib.sha256(image_index).hexdigest()
    layout_index = json.dumps(
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
    archive_path = tmp_path / "candidate.oci.tar"
    with tarfile.open(archive_path, "w") as archive:
        _tar_member(archive, "index.json", layout_index)
        _tar_member(archive, f"blobs/sha256/{index_digest.removeprefix('sha256:')}", image_index)
        for content in platform_blobs.values():
            digest = hashlib.sha256(content).hexdigest()
            _tar_member(archive, f"blobs/sha256/{digest}", content)

    output = tmp_path / "image-evidence.json"
    result = _run(
        sys.executable,
        CANDIDATE_SCRIPT,
        "inspect-image",
        "--archive",
        archive_path,
        "--source-reference",
        "ghcr.io/owner/repository@" + index_digest,
        "--output",
        output,
    )

    assert result.returncode == 0, result.stderr
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["indexDigest"] == index_digest
    assert evidence["sourceReference"] == "ghcr.io/owner/repository@" + index_digest
    assert set(evidence["platforms"]) == {"linux/amd64", "linux/arm64"}
    assert {item["digest"] for item in evidence["platforms"].values()} == {
        descriptor["digest"] for descriptor in platform_descriptors
    }


def test_release_workflows_use_managed_environment_and_digest_only_promotion() -> None:
    release_text = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    ci_text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    release_jobs = yaml.safe_load(release_text)["jobs"]

    assert "pip install" not in release_text
    assert "npm ci" not in release_text
    assert "npm install" not in release_text
    assert "requirements.txt" not in release_text
    assert "./wolfy lock python --check" in release_text
    assert "./wolfy bootstrap --ensure" in release_text
    assert "./wolfy qualify-env" in release_text
    assert "environmentEvidence" in release_text
    assert "bootstrapNetworkUsed" in release_text
    assert "linux/amd64,linux/arm64" in release_text
    assert "inspect-image" in release_text
    assert (
        "npm --prefix apps/dsa-web exec -- playwright test "
        "--config=apps/dsa-web/playwright.config.ts --project=release-real-runtime "
        "--reporter=json > output/release/raw/playwright.json"
    ) in release_text
    assert "playwright install chromium" not in release_text
    assert "PLAYWRIGHT_BROWSERS_PATH" not in release_text
    assert "PLAYWRIGHT_JSON_OUTPUT_NAME" not in release_text
    assert "PLAYWRIGHT_OUTPUT_DIR" not in release_text
    assert "scripts/release_runtime_fixture.py" in release_text
    assert "runtime_dir=\"$(mktemp -d)\"" in release_text
    assert "trap cleanup EXIT" in release_text
    assert "ADMIN_AUTH_ENABLED=false" in release_text
    assert "docker buildx imagetools create" in release_text
    promotion_text = json.dumps(release_jobs["promote-docker-multiarch"], sort_keys=True)
    assert "docker buildx build" not in promotion_text
    assert "npm run build" not in promotion_text
    assert "docker buildx imagetools create" in promotion_text

    assert "pip install" not in ci_text
    assert "npm ci" not in ci_text
    assert "./wolfy bootstrap --ensure" in ci_text
    assert (
        "./wolfy exec --profile test -- npm --prefix apps/dsa-web exec -- "
        "playwright test --project=chromium --project=chromium-mobile"
    ) in ci_text
    assert "playwright install chromium" not in ci_text
    assert "PLAYWRIGHT_BROWSERS_PATH" not in ci_text
    for command in (
        "npm --prefix apps/dsa-web test -- --maxWorkers=1",
        "npm --prefix apps/dsa-web run lint",
        "python scripts/web_build_artifact.py typecheck",
        "python scripts/web_build_artifact.py build",
    ):
        assert command in ci_text


def test_playwright_browser_install_survives_managed_run_cleanup(tmp_path: Path) -> None:
    from scripts.environment.runtime import cleanup_run, create_run_context

    cache_root = tmp_path / "cache"
    browser_snapshot = cache_root / "snapshots" / "browser" / ("a" * 64) / ("b" * 64)
    browser_snapshot.mkdir(parents=True)
    context = create_run_context(cache_root, run_id="run-browser-cleanup")

    cleanup_run(context, success=True)

    assert browser_snapshot.is_dir()
    assert not context.root.exists()
    manager = (ROOT / "scripts/environment/manager.py").read_text(encoding="utf-8")
    runtime = (ROOT / "scripts/environment/runtime.py").read_text(encoding="utf-8")
    playwright = (ROOT / "apps/dsa-web/playwright.config.ts").read_text(encoding="utf-8")
    assert "ensure_snapshot(" in manager
    assert "self._browser_component(web)" in manager
    assert '"WOLFYSTOCK_MANAGED_CHROMIUM_EXECUTABLE": str(browser_executable)' in runtime
    assert "executablePath: managedChromiumExecutable" in playwright
    assert "channel: 'chromium'" not in playwright


def test_release_runtime_evidence_requires_source_cwd_environment_and_asset_identity() -> None:
    browser = (ROOT / "apps/dsa-web/e2e/release-real-runtime.release.spec.ts").read_text(encoding="utf-8")
    harness = (ROOT / "scripts/uat_runtime_harness.py").read_text(encoding="utf-8")
    summary = (ROOT / "scripts/release_gate_summary.py").read_text(encoding="utf-8")
    environment_runtime = (ROOT / "scripts/environment/runtime.py").read_text(encoding="utf-8")

    assert "WOLFYSTOCK_RELEASE_CANDIDATE_SHA" in browser
    assert "WOLFYSTOCK_ENV_FINGERPRINT" in browser
    assert "runtimeCwd" in browser
    assert "assetFingerprint" in browser
    assert "environmentFingerprint" in harness
    assert "environmentFingerprint" in summary
    assert "WOLFYSTOCK_RELEASE_CANDIDATE_SHA" in environment_runtime
    assert "PLAYWRIGHT_JSON_OUTPUT_NAME" in environment_runtime
