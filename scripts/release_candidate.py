#!/usr/bin/env python3
"""Build and verify the qualified immutable release-candidate graph."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tarfile
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "wolfystock_release_candidate_v2"
IMAGE_SCHEMA_VERSION = "wolfystock_oci_image_index_v1"
ENVIRONMENT_SCHEMA_VERSION = "wolfystock_environment_evidence_v1"
PYTHON_LOCK_SCHEMA_VERSION = "wolfystock_python_lock_v2"
PYTHON_LOCK_POLICY_VERSION = "wolfystock_python_lock_policy_v2"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
OCI_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
REQUIRED_ARTIFACT_NAMES = {
    "source.tar.gz",
    "web-static.tar.gz",
    "docker-multiarch.oci.tar",
}
DOCKER_RUNTIME_PROJECTIONS = {
    "linux/amd64": "linux-x86_64-cpython311-runtime",
    "linux/arm64": "linux-aarch64-cpython311-runtime",
}


def canonical_digest(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _object(value: Any, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(code)
    return value


def _digest(value: Any, code: str) -> str:
    if not isinstance(value, str) or DIGEST_RE.fullmatch(value) is None:
        raise ValueError(code)
    return value


def _oci_digest(value: Any, code: str) -> str:
    if not isinstance(value, str) or OCI_DIGEST_RE.fullmatch(value) is None:
        raise ValueError(code)
    return value


def parse_assignment(raw: str, *, label: str) -> tuple[str, str]:
    if "=" not in raw:
        raise ValueError(f"{label}_must_use_name_equals_value")
    name, value = raw.split("=", 1)
    name = name.strip()
    value = value.strip()
    if not NAME_RE.fullmatch(name) or not value:
        raise ValueError(f"invalid_{label}")
    return name, value


def _artifacts(artifact_specs: Sequence[str]) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for raw in artifact_specs:
        name, raw_path = parse_assignment(raw, label="artifact")
        if name in seen_names:
            raise ValueError("duplicate_artifact_name")
        path = Path(raw_path)
        if not path.is_file():
            raise ValueError(f"artifact_missing:{name}")
        size = path.stat().st_size
        if size <= 0:
            raise ValueError(f"artifact_empty:{name}")
        seen_names.add(name)
        artifacts.append({"name": name, "path": name, "size": size, "sha256": file_digest(path)})
    missing = sorted(REQUIRED_ARTIFACT_NAMES - seen_names)
    unexpected = sorted(seen_names - REQUIRED_ARTIFACT_NAMES)
    if missing:
        raise ValueError("required_artifacts_missing:" + ",".join(missing))
    if unexpected:
        raise ValueError("unexpected_release_artifacts:" + ",".join(unexpected))
    return sorted(artifacts, key=lambda item: item["name"])


def _environment_identity(report: Any) -> dict[str, Any]:
    wrapper = _object(report, "environment_report_not_object")
    if wrapper.get("status") != "PASS":
        raise ValueError("environment_qualification_not_pass")
    evidence = _object(wrapper.get("environmentEvidence"), "environment_evidence_missing")
    if evidence.get("schemaVersion") != ENVIRONMENT_SCHEMA_VERSION:
        raise ValueError("environment_evidence_schema_mismatch")
    fingerprint = _digest(evidence.get("environmentFingerprint"), "environment_fingerprint_invalid")
    operational = _object(evidence.get("operational"), "environment_operational_evidence_missing")
    if operational.get("bootstrapNetworkUsed") is not False:
        raise ValueError("qualification_bootstrap_network_used")
    components = _object(evidence.get("componentFingerprints"), "component_fingerprints_missing")
    normalized_components: dict[str, dict[str, str]] = {}
    for name in ("python", "web"):
        component = _object(components.get(name), f"{name}_component_fingerprint_missing")
        normalized_components[name] = {
            "input": _digest(component.get("input"), f"{name}_input_fingerprint_invalid"),
            "installed": _digest(component.get("installed"), f"{name}_installed_fingerprint_invalid"),
        }
    manifest_hashes = _object(evidence.get("manifestHashes"), "environment_manifest_hashes_missing")
    web_lock = _digest(manifest_hashes.get("apps/dsa-web/package-lock.json"), "web_lock_hash_invalid")
    python_lock = _object(evidence.get("pythonLock"), "environment_python_lock_missing")
    if python_lock.get("schemaVersion") != PYTHON_LOCK_SCHEMA_VERSION:
        raise ValueError("environment_python_lock_schema_mismatch")
    if python_lock.get("policyVersion") != PYTHON_LOCK_POLICY_VERSION:
        raise ValueError("environment_python_lock_policy_mismatch")
    if python_lock.get("hashVerification") is not True:
        raise ValueError("environment_python_hash_verification_not_pass")
    selected_target = _object(python_lock.get("selectedTarget"), "selected_python_target_missing")
    required_target_fields = ("os", "architecture", "implementation", "pythonVersion", "abi", "platform")
    if any(not isinstance(selected_target.get(field), str) or not selected_target[field] for field in required_target_fields):
        raise ValueError("selected_python_target_invalid")
    selected_profile = python_lock.get("selectedProfile")
    selected_projection = python_lock.get("selectedProjection")
    resolver = _object(python_lock.get("resolver"), "environment_python_resolver_missing")
    if not isinstance(selected_profile, str) or not selected_profile:
        raise ValueError("selected_python_profile_invalid")
    if not isinstance(selected_projection, str) or not selected_projection:
        raise ValueError("selected_python_projection_invalid")
    if resolver != {"implementation": "uv", "version": "0.11.19"}:
        raise ValueError("environment_python_resolver_mismatch")
    return {
        "evidence": wrapper,
        "evidenceDigest": canonical_digest(wrapper),
        "fingerprint": fingerprint,
        "components": normalized_components,
        "webLockSha256": web_lock,
        "pythonLock": {
            "schemaVersion": python_lock["schemaVersion"],
            "policyVersion": python_lock["policyVersion"],
            "contentHash": _digest(python_lock.get("contentHash"), "environment_python_lock_hash_invalid"),
            "inputHashes": _validated_input_hashes(python_lock.get("inputHashes")),
            "selectedTarget": dict(sorted(selected_target.items())),
            "selectedProfile": selected_profile,
            "selectedProjection": selected_projection,
            "selectedProjectionHash": _digest(
                python_lock.get("selectedProjectionHash"), "selected_python_projection_hash_invalid"
            ),
            "resolver": resolver,
            "hashVerification": True,
        },
    }


def _validated_input_hashes(value: Any) -> dict[str, str]:
    values = _object(value, "python_lock_input_hashes_missing")
    expected = {"requirements.txt", "requirements-dev.txt"}
    if set(values) != expected:
        raise ValueError("python_lock_input_hashes_invalid")
    return {name: _digest(values[name], f"python_lock_input_hash_invalid:{name}") for name in sorted(values)}


def _python_lock_identity(report: Any) -> dict[str, Any]:
    lock = _object(report, "python_lock_report_not_object")
    if lock.get("status") != "ok":
        raise ValueError("python_lock_check_not_ok")
    if lock.get("schemaVersion") != PYTHON_LOCK_SCHEMA_VERSION:
        raise ValueError("python_lock_schema_mismatch")
    if lock.get("policyVersion") != PYTHON_LOCK_POLICY_VERSION:
        raise ValueError("python_lock_policy_mismatch")
    resolver = _object(lock.get("resolver"), "python_lock_resolver_missing")
    if resolver != {"implementation": "uv", "version": "0.11.19"}:
        raise ValueError("python_lock_resolver_mismatch")
    projections = _object(lock.get("targetProjections"), "python_target_projections_missing")
    docker_projections: dict[str, dict[str, str]] = {}
    for platform, selected in DOCKER_RUNTIME_PROJECTIONS.items():
        projection = _object(projections.get(selected), f"docker_projection_missing:{platform}")
        docker_projections[platform] = {
            "selectedProjection": selected,
            "projectionHash": _digest(projection.get("projectionHash"), f"docker_projection_hash_invalid:{platform}"),
        }
    return {
        "schemaVersion": lock["schemaVersion"],
        "policyVersion": lock["policyVersion"],
        "contentHash": _digest(lock.get("contentHash"), "python_lock_content_hash_invalid"),
        "inputHashes": _validated_input_hashes(lock.get("inputHashes")),
        "resolver": resolver,
        "dockerRuntimeProjections": docker_projections,
    }


def _workflow_identity(report: Any, commit_sha: str) -> dict[str, str]:
    workflow = _object(report, "workflow_identity_not_object")
    required = ("repository", "workflowRef", "workflowSha", "runId", "runAttempt", "releaseTag", "tagObjectSha")
    if any(not isinstance(workflow.get(field), str) or not workflow[field] for field in required):
        raise ValueError("workflow_identity_incomplete")
    if workflow["workflowSha"] != commit_sha:
        raise ValueError("workflow_candidate_sha_mismatch")
    if SHA_RE.fullmatch(workflow["tagObjectSha"]) is None:
        raise ValueError("workflow_tag_object_invalid")
    if re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", workflow["releaseTag"]) is None:
        raise ValueError("workflow_release_tag_invalid")
    if re.fullmatch(r"[0-9]+", workflow["runId"]) is None or re.fullmatch(r"[0-9]+", workflow["runAttempt"]) is None:
        raise ValueError("workflow_run_identity_invalid")
    if ".github/workflows/release.yml@" not in workflow["workflowRef"]:
        raise ValueError("workflow_ref_invalid")
    return {field: workflow[field] for field in required}


def _web_identity(report: Any, commit_sha: str, web_lock_sha256: str) -> dict[str, Any]:
    wrapper = _object(report, "web_build_report_not_object")
    manifest = _object(wrapper.get("manifest"), "web_build_manifest_missing")
    candidate = _object(manifest.get("candidate"), "web_build_candidate_missing")
    assets = manifest.get("assets")
    if (
        wrapper.get("ok") is not True
        or wrapper.get("errorCodes") != []
        or manifest.get("contract") != "wolfystock_web_build_artifact_v1"
        or candidate.get("commit") != commit_sha
        or candidate.get("dirty") is not False
        or not isinstance(assets, list)
        or not assets
    ):
        raise ValueError("web_build_identity_not_qualified")
    return {
        "lockSha256": web_lock_sha256,
        "artifactContract": manifest["contract"],
        "artifactFingerprint": _digest(manifest.get("fingerprint"), "web_artifact_fingerprint_invalid"),
        "assetCount": len(assets),
        "buildReportDigest": canonical_digest(wrapper),
    }


def _image_identity(report: Any, docker_archive_sha256: str) -> dict[str, Any]:
    image = _object(report, "image_evidence_not_object")
    if image.get("schemaVersion") != IMAGE_SCHEMA_VERSION:
        raise ValueError("image_evidence_schema_mismatch")
    if image.get("archiveSha256") != docker_archive_sha256:
        raise ValueError("image_archive_digest_mismatch")
    platforms = _object(image.get("platforms"), "image_platforms_missing")
    if set(platforms) != set(DOCKER_RUNTIME_PROJECTIONS):
        raise ValueError("image_platform_set_mismatch")
    index_digest = _oci_digest(image.get("indexDigest"), "image_index_digest_invalid")
    source_reference = image.get("sourceReference")
    if not isinstance(source_reference, str) or not source_reference.endswith("@" + index_digest):
        raise ValueError("image_source_reference_invalid")
    normalized: dict[str, dict[str, str]] = {}
    for platform in sorted(platforms):
        details = _object(platforms[platform], f"image_platform_invalid:{platform}")
        normalized[platform] = {"digest": _oci_digest(details.get("digest"), f"image_digest_invalid:{platform}")}
    return {
        "schemaVersion": image["schemaVersion"],
        "archiveSha256": docker_archive_sha256,
        "indexDigest": index_digest,
        "sourceReference": source_reference,
        "platforms": normalized,
        "evidenceDigest": canonical_digest(image),
    }


def _assert_lock_match(environment: Mapping[str, Any], lock: Mapping[str, Any]) -> None:
    selected = environment["pythonLock"]
    for field in ("schemaVersion", "policyVersion", "contentHash", "inputHashes", "resolver"):
        if selected[field] != lock[field]:
            raise ValueError(f"environment_python_lock_mismatch:{field}")


def _validated_candidate_lock(value: Any) -> dict[str, Any]:
    lock = _object(value, "candidate_python_lock_missing")
    if lock.get("schemaVersion") != PYTHON_LOCK_SCHEMA_VERSION:
        raise ValueError("candidate_python_lock_schema_mismatch")
    if lock.get("policyVersion") != PYTHON_LOCK_POLICY_VERSION:
        raise ValueError("candidate_python_lock_policy_mismatch")
    normalized = {
        "schemaVersion": lock["schemaVersion"],
        "policyVersion": lock["policyVersion"],
        "contentHash": _digest(lock.get("contentHash"), "candidate_python_lock_hash_invalid"),
        "inputHashes": _validated_input_hashes(lock.get("inputHashes")),
        "resolver": _object(lock.get("resolver"), "candidate_python_resolver_missing"),
        "dockerRuntimeProjections": _object(
            lock.get("dockerRuntimeProjections"), "candidate_docker_projections_missing"
        ),
    }
    if normalized["resolver"] != {"implementation": "uv", "version": "0.11.19"}:
        raise ValueError("candidate_python_resolver_mismatch")
    projections = normalized["dockerRuntimeProjections"]
    if set(projections) != set(DOCKER_RUNTIME_PROJECTIONS):
        raise ValueError("candidate_docker_projection_set_mismatch")
    for platform, selected in DOCKER_RUNTIME_PROJECTIONS.items():
        projection = _object(projections[platform], f"candidate_docker_projection_invalid:{platform}")
        if projection.get("selectedProjection") != selected:
            raise ValueError(f"candidate_docker_projection_name_mismatch:{platform}")
        _digest(projection.get("projectionHash"), f"candidate_docker_projection_hash_invalid:{platform}")
    return normalized


def build_manifest(
    *,
    commit_sha: str,
    artifact_specs: Sequence[str],
    environment_report: Any,
    python_lock_report: Any,
    web_build_report: Any,
    image_evidence: Any,
    workflow_report: Any,
) -> dict[str, Any]:
    sha = commit_sha.strip().lower()
    if SHA_RE.fullmatch(sha) is None:
        raise ValueError("invalid_commit_sha")
    artifacts = _artifacts(artifact_specs)
    artifact_digests = {item["name"]: item["sha256"] for item in artifacts}
    environment = _environment_identity(environment_report)
    python_lock = _python_lock_identity(python_lock_report)
    _assert_lock_match(environment, python_lock)
    web = _web_identity(web_build_report, sha, environment["webLockSha256"])
    images = _image_identity(image_evidence, artifact_digests["docker-multiarch.oci.tar"])
    manifest: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "commitSha": sha,
        "workflowIdentity": _workflow_identity(workflow_report, sha),
        "environment": {
            "evidence": environment["evidence"],
            "evidenceDigest": environment["evidenceDigest"],
            "fingerprint": environment["fingerprint"],
            "components": environment["components"],
            "selectedPython": environment["pythonLock"],
        },
        "pythonLock": python_lock,
        "web": web,
        "images": images,
        "artifacts": artifacts,
        "artifactDigests": artifact_digests,
        "applicationDigests": {
            "backendSource": artifact_digests["source.tar.gz"],
            "frontendArchive": artifact_digests["web-static.tar.gz"],
            "frontendBuild": web["artifactFingerprint"],
            "containerIndex": images["indexDigest"],
        },
    }
    manifest["candidateDigest"] = canonical_digest(manifest)
    return manifest


def validate_manifest(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return ["candidate_manifest_not_object"]
    errors: list[str] = []
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("candidate_schema_mismatch")
    if not isinstance(payload.get("commitSha"), str) or SHA_RE.fullmatch(payload["commitSha"]) is None:
        errors.append("candidate_sha_invalid")
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        errors.append("candidate_artifacts_invalid")
        artifacts = []
    names: list[str] = []
    digest_map: dict[str, str] = {}
    for item in artifacts:
        if not isinstance(item, dict):
            errors.append("candidate_artifact_invalid")
            continue
        name = item.get("name") if isinstance(item.get("name"), str) else ""
        names.append(name)
        if name not in REQUIRED_ARTIFACT_NAMES or item.get("path") != name:
            errors.append(f"candidate_artifact_path_invalid:{name or 'unknown'}")
        if not isinstance(item.get("sha256"), str) or DIGEST_RE.fullmatch(item["sha256"]) is None:
            errors.append(f"candidate_artifact_digest_invalid:{name or 'unknown'}")
        else:
            digest_map[name] = item["sha256"]
        if type(item.get("size")) is not int or item["size"] <= 0:
            errors.append(f"candidate_artifact_size_invalid:{name or 'unknown'}")
    if names != sorted(REQUIRED_ARTIFACT_NAMES):
        errors.append("candidate_artifact_set_or_order_invalid")
    if payload.get("artifactDigests") != digest_map:
        errors.append("candidate_artifact_digest_map_mismatch")
    environment = payload.get("environment")
    python_lock = payload.get("pythonLock")
    images = payload.get("images")
    web = payload.get("web")
    workflow = payload.get("workflowIdentity")
    try:
        if not isinstance(environment, dict):
            raise ValueError("candidate_environment_missing")
        normalized_environment = _environment_identity(environment.get("evidence"))
        if environment.get("evidenceDigest") != normalized_environment["evidenceDigest"]:
            errors.append("candidate_environment_evidence_digest_mismatch")
        if environment.get("fingerprint") != normalized_environment["fingerprint"]:
            errors.append("candidate_environment_fingerprint_mismatch")
        if environment.get("components") != normalized_environment["components"]:
            errors.append("candidate_environment_components_mismatch")
        if environment.get("selectedPython") != normalized_environment["pythonLock"]:
            errors.append("candidate_selected_python_mismatch")
        normalized_lock = _validated_candidate_lock(python_lock)
        _assert_lock_match(normalized_environment, normalized_lock)
        if normalized_lock != python_lock:
            errors.append("candidate_python_lock_not_canonical")
        normalized_web = _object(web, "candidate_web_missing")
        if normalized_web.get("lockSha256") != normalized_environment["webLockSha256"]:
            errors.append("candidate_web_lock_mismatch")
        _digest(normalized_web.get("artifactFingerprint"), "candidate_web_fingerprint_invalid")
        image_payload = dict(_object(images, "candidate_images_missing"))
        observed_image_evidence_digest = image_payload.pop("evidenceDigest", None)
        normalized_image = _image_identity(image_payload, digest_map.get("docker-multiarch.oci.tar", ""))
        if observed_image_evidence_digest != normalized_image["evidenceDigest"]:
            errors.append("candidate_image_evidence_digest_mismatch")
        if normalized_image != images:
            errors.append("candidate_image_identity_not_canonical")
        _workflow_identity(workflow, payload.get("commitSha", ""))
        expected_applications = {
            "backendSource": digest_map.get("source.tar.gz"),
            "frontendArchive": digest_map.get("web-static.tar.gz"),
            "frontendBuild": normalized_web.get("artifactFingerprint"),
            "containerIndex": normalized_image.get("indexDigest"),
        }
        if payload.get("applicationDigests") != expected_applications:
            errors.append("candidate_application_digests_mismatch")
    except ValueError as exc:
        errors.append(str(exc))
    digest_payload = dict(payload)
    observed_digest = digest_payload.pop("candidateDigest", None)
    if observed_digest != canonical_digest(digest_payload):
        errors.append("candidate_digest_mismatch")
    return sorted(set(errors))


def load_manifest(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    errors = validate_manifest(payload)
    if errors:
        raise ValueError(";".join(errors))
    return payload


def verify_artifacts(payload: dict[str, Any], artifact_dir: Path) -> list[str]:
    errors: list[str] = []
    for item in payload["artifacts"]:
        path = artifact_dir / item["path"]
        if not path.is_file():
            errors.append(f"artifact_missing:{item['name']}")
            continue
        if path.stat().st_size != item["size"] or file_digest(path) != item["sha256"]:
            errors.append(f"artifact_digest_mismatch:{item['name']}")
    image_archive = artifact_dir / "docker-multiarch.oci.tar"
    if image_archive.is_file():
        try:
            observed = inspect_oci_archive(
                image_archive,
                source_reference=payload["images"]["sourceReference"],
            )
            expected = dict(payload["images"])
            expected.pop("evidenceDigest", None)
            if observed != expected:
                errors.append("image_archive_identity_mismatch")
        except (KeyError, OSError, ValueError, tarfile.TarError):
            errors.append("image_archive_identity_unreadable")
    return errors


def verify_environment(payload: dict[str, Any], environment_report: Any, python_lock_report: Any) -> list[str]:
    errors: list[str] = []
    try:
        environment = _environment_identity(environment_report)
        lock = _python_lock_identity(python_lock_report)
        _assert_lock_match(environment, lock)
        expected_environment = payload["environment"]
        comparisons = {
            "environment_fingerprint_mismatch": (environment["fingerprint"], expected_environment["fingerprint"]),
            "environment_components_mismatch": (environment["components"], expected_environment["components"]),
            "selected_python_mismatch": (environment["pythonLock"], expected_environment["selectedPython"]),
            "python_lock_identity_mismatch": (lock, payload["pythonLock"]),
        }
        errors.extend(code for code, values in comparisons.items() if values[0] != values[1])
    except (KeyError, ValueError) as exc:
        errors.append(str(exc))
    return errors


def _tar_json(archive: tarfile.TarFile, name: str) -> tuple[bytes, dict[str, Any]]:
    members = [member for member in archive.getmembers() if member.name == name]
    if len(members) != 1 or not members[0].isfile() or members[0].size > 32 * 1024 * 1024:
        raise ValueError(f"oci_member_invalid:{name}")
    handle = archive.extractfile(members[0])
    if handle is None:
        raise ValueError(f"oci_member_unreadable:{name}")
    content = handle.read()
    return content, _object(json.loads(content), f"oci_json_invalid:{name}")


def _descriptor_blob(archive: tarfile.TarFile, descriptor: Mapping[str, Any]) -> tuple[bytes, dict[str, Any]]:
    digest = _oci_digest(descriptor.get("digest"), "oci_descriptor_digest_invalid")
    content, payload = _tar_json(archive, "blobs/sha256/" + digest.removeprefix("sha256:"))
    if hashlib.sha256(content).hexdigest() != digest.removeprefix("sha256:"):
        raise ValueError("oci_descriptor_digest_mismatch")
    if descriptor.get("size") != len(content):
        raise ValueError("oci_descriptor_size_mismatch")
    return content, payload


def inspect_oci_archive(path: Path, *, source_reference: str) -> dict[str, Any]:
    with tarfile.open(path, "r:*") as archive:
        _layout_content, layout = _tar_json(archive, "index.json")
        descriptors = layout.get("manifests")
        if not isinstance(descriptors, list) or len(descriptors) != 1 or not isinstance(descriptors[0], dict):
            raise ValueError("oci_layout_root_index_ambiguous")
        root_descriptor = descriptors[0]
        _index_content, image_index = _descriptor_blob(archive, root_descriptor)
        platform_descriptors = image_index.get("manifests")
        if not isinstance(platform_descriptors, list):
            raise ValueError("oci_platform_descriptors_missing")
        platforms: dict[str, dict[str, str]] = {}
        for descriptor in platform_descriptors:
            if not isinstance(descriptor, dict):
                raise ValueError("oci_platform_descriptor_invalid")
            platform = descriptor.get("platform")
            if not isinstance(platform, dict):
                raise ValueError("oci_platform_identity_missing")
            os_name = platform.get("os")
            architecture = platform.get("architecture")
            if (os_name, architecture) == ("unknown", "unknown"):
                continue
            key = f"{os_name}/{architecture}"
            if key not in DOCKER_RUNTIME_PROJECTIONS or key in platforms:
                raise ValueError(f"oci_platform_identity_invalid:{key}")
            _descriptor_blob(archive, descriptor)
            platforms[key] = {"digest": _oci_digest(descriptor.get("digest"), "oci_platform_digest_invalid")}
        if set(platforms) != set(DOCKER_RUNTIME_PROJECTIONS):
            raise ValueError("oci_required_platforms_missing")
    index_digest = _oci_digest(root_descriptor.get("digest"), "oci_index_digest_invalid")
    if not source_reference.endswith("@" + index_digest):
        raise ValueError("oci_source_reference_digest_mismatch")
    return {
        "schemaVersion": IMAGE_SCHEMA_VERSION,
        "archiveSha256": file_digest(path),
        "indexDigest": index_digest,
        "sourceReference": source_reference,
        "platforms": dict(sorted(platforms.items())),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect = subparsers.add_parser("inspect-image")
    inspect.add_argument("--archive", type=Path, required=True)
    inspect.add_argument("--source-reference", required=True)
    inspect.add_argument("--output", type=Path, required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--commit-sha", required=True)
    build.add_argument("--artifact", action="append", default=[])
    build.add_argument("--environment-evidence", type=Path, required=True)
    build.add_argument("--python-lock-report", type=Path, required=True)
    build.add_argument("--web-build-report", type=Path, required=True)
    build.add_argument("--image-evidence", type=Path, required=True)
    build.add_argument("--workflow-identity", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--artifact-dir", type=Path)
    verify.add_argument("--expected-sha")
    verify.add_argument("--environment-evidence", type=Path)
    verify.add_argument("--python-lock-report", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        if args.command == "inspect-image":
            evidence = inspect_oci_archive(args.archive, source_reference=args.source_reference)
            write_json(args.output, evidence)
            print(json.dumps({"indexDigest": evidence["indexDigest"], "platforms": sorted(evidence["platforms"])}))
            return 0
        if args.command == "build":
            payload = build_manifest(
                commit_sha=args.commit_sha,
                artifact_specs=args.artifact,
                environment_report=_load_json(args.environment_evidence),
                python_lock_report=_load_json(args.python_lock_report),
                web_build_report=_load_json(args.web_build_report),
                image_evidence=_load_json(args.image_evidence),
                workflow_report=_load_json(args.workflow_identity),
            )
            write_json(args.output, payload)
            print(json.dumps({"candidateDigest": payload["candidateDigest"], "commitSha": payload["commitSha"]}))
            return 0

        payload = load_manifest(args.manifest)
        errors: list[str] = []
        if args.expected_sha and payload["commitSha"] != args.expected_sha.strip().lower():
            errors.append("candidate_sha_mismatch")
        if args.artifact_dir:
            errors.extend(verify_artifacts(payload, args.artifact_dir))
        if bool(args.environment_evidence) != bool(args.python_lock_report):
            errors.append("qualification_environment_inputs_incomplete")
        elif args.environment_evidence and args.python_lock_report:
            errors.extend(
                verify_environment(payload, _load_json(args.environment_evidence), _load_json(args.python_lock_report))
            )
        if errors:
            raise ValueError(";".join(sorted(set(errors))))
        print(json.dumps({"candidateDigest": payload["candidateDigest"], "commitSha": payload["commitSha"]}))
        return 0
    except (OSError, ValueError, json.JSONDecodeError, tarfile.TarError) as exc:
        print(f"[NO-GO] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
