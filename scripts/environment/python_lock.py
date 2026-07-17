from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from .errors import EnvironmentFailure
from .python_artifacts import (
    ArtifactIndex,
    ArtifactReader,
    LockedArtifact,
    ProjectionValidation,
    build_projection,
    pypi_artifact_index,
    read_artifact,
    validate_projection,
)


LOCK_SCHEMA_VERSION = "wolfystock_python_lock_v2"
LOCK_POLICY_VERSION = "wolfystock_python_lock_policy_v2"
LOCK_MANIFEST = "requirements-lock.json"
RESOLVER_IMPLEMENTATION = "uv"
RESOLVER_VERSION = "0.11.19"
REQUIREMENT_INPUTS = ("requirements.txt", "requirements-dev.txt")
PYTHON_VERSIONS = ("3.11", "3.12")
PROFILE_INPUTS = {
    "runtime": "requirements.txt",
    "development": "requirements-dev.txt",
}
LOCK_PATHS = {
    ("runtime", "3.11"): "requirements-python311-runtime.lock",
    ("development", "3.11"): "requirements-python311-dev.lock",
    ("runtime", "3.12"): "requirements-python312-runtime.lock",
    ("development", "3.12"): "requirements-python312-dev.lock",
}
SUPPORTED_TARGETS = (
    {
        "abi": "cp311",
        "architecture": "x86_64",
        "implementation": "CPython",
        "os": "Linux",
        "platform": "manylinux_2_36_x86_64",
        "profiles": ["runtime", "development"],
        "pythonVersion": "3.11",
    },
    {
        "abi": "cp311",
        "architecture": "aarch64",
        "implementation": "CPython",
        "os": "Linux",
        "platform": "manylinux_2_36_aarch64",
        "profiles": ["runtime"],
        "pythonVersion": "3.11",
    },
    {
        "abi": "cp311",
        "architecture": "arm64",
        "implementation": "CPython",
        "os": "Darwin",
        "platform": "macosx_15_0_arm64",
        "profiles": ["runtime", "development"],
        "pythonVersion": "3.11",
    },
    {
        "abi": "cp311",
        "architecture": "x86_64",
        "implementation": "CPython",
        "os": "Darwin",
        "platform": "macosx_15_0_x86_64",
        "profiles": ["runtime", "development"],
        "pythonVersion": "3.11",
    },
    {
        "abi": "cp311",
        "architecture": "AMD64",
        "implementation": "CPython",
        "os": "Windows",
        "platform": "win_amd64",
        "profiles": ["runtime", "development"],
        "pythonVersion": "3.11",
    },
    {
        "abi": "cp312",
        "architecture": "arm64",
        "implementation": "CPython",
        "os": "Darwin",
        "platform": "macosx_15_0_arm64",
        "profiles": ["runtime", "development"],
        "pythonVersion": "3.12",
    },
    {
        "abi": "cp312",
        "architecture": "x86_64",
        "implementation": "CPython",
        "os": "Darwin",
        "platform": "macosx_15_0_x86_64",
        "profiles": ["runtime", "development"],
        "pythonVersion": "3.12",
    },
    {
        "abi": "cp312",
        "architecture": "AMD64",
        "implementation": "CPython",
        "os": "Windows",
        "platform": "win_amd64",
        "profiles": ["runtime", "development"],
        "pythonVersion": "3.12",
    },
)

ResolverRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")
_PIN_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)==(?P<version>[^\s;]+)"
    r"(?:\s*;\s*(?P<marker>.+))?$"
)
_HASH_RE = re.compile(r"(?:^|\s)--hash=sha256:([0-9a-f]{64})(?=\s|$)")
_UNSAFE_PATTERNS = (
    re.compile(r"--(?:extra-)?index-url|--find-links", re.IGNORECASE),
    re.compile(r"\bhttps?://[^\s/@:]+:[^\s/@]+@", re.IGNORECASE),
    re.compile(r"(?:^|\s)[A-Za-z][A-Za-z0-9+.-]*\+?(?:https?|file)://", re.IGNORECASE),
    re.compile(r"(?:^|\s)[A-Za-z0-9_.-]+\s*@\s*(?:https?|file)://", re.IGNORECASE),
    re.compile(r"(?:^|[\s=])/(?:Users|home|private|var/folders)/"),
    re.compile(r"(?:^|[\s=])[A-Za-z]:[\\/]"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?\b"),
)


@dataclass(frozen=True)
class LockedRecord:
    name: str
    version: str
    hashes: tuple[str, ...]
    marker: str | None


@dataclass(frozen=True)
class ParsedLock:
    distributions: dict[str, frozenset[str]]
    record_count: int
    hash_count: int
    marker_count: int
    records: tuple[LockedRecord, ...]


@dataclass(frozen=True)
class PythonLockContract:
    profile: str
    target: dict[str, str]
    lock_path: Path
    content_hash: str
    input_hashes: dict[str, str]
    direct_requirements: frozenset[str]
    distributions: dict[str, frozenset[str]]
    artifacts: dict[str, tuple[LockedArtifact, ...]]
    artifact_hashes: dict[str, frozenset[str]]
    artifact_files: dict[str, str]
    build_requirements: dict[str, str]
    hash_count: int
    hash_verification: bool
    projection: str
    projection_hash: str
    source_build_count: int
    resolver: dict[str, str]
    lock_files: dict[str, str]

    def evidence(self) -> dict[str, Any]:
        return {
            "schemaVersion": LOCK_SCHEMA_VERSION,
            "policyVersion": LOCK_POLICY_VERSION,
            "contentHash": self.content_hash,
            "inputHashes": dict(sorted(self.input_hashes.items())),
            "resolver": dict(self.resolver),
            "selectedTarget": dict(self.target),
            "selectedProfile": self.profile,
            "selectedLock": self.lock_path.name,
            "selectedProjection": self.projection,
            "selectedProjectionHash": self.projection_hash,
            "lockedDistributionCount": len(self.distributions),
            "artifactCount": self.hash_count,
            "sourceBuildCount": self.source_build_count,
            "hashCount": self.hash_count,
            "hashVerification": self.hash_verification,
        }


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_content_hash(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise EnvironmentFailure("python_lock_input_invalid", f"unable to read {path.name}") from exc
    normalized = "\n".join(line.rstrip() for line in text.splitlines()) + "\n"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _normalized_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _manifest_targets() -> list[dict[str, Any]]:
    return [
        {key: list(value) if key == "profiles" else value for key, value in target.items()}
        for target in SUPPORTED_TARGETS
    ]


def _target_identity(target: dict[str, Any]) -> dict[str, str]:
    return {
        key: str(value)
        for key, value in target.items()
        if key != "profiles"
    }


def _normalized_architecture(os_name: str, architecture: str) -> str:
    aliases = {
        "Darwin": {
            "aarch64": "arm64",
            "amd64": "x86_64",
            "arm64": "arm64",
            "x64": "x86_64",
            "x86_64": "x86_64",
        },
        "Linux": {
            "aarch64": "aarch64",
            "amd64": "x86_64",
            "arm64": "aarch64",
            "x64": "x86_64",
            "x86_64": "x86_64",
        },
        "Windows": {
            "amd64": "AMD64",
            "x64": "AMD64",
            "x86_64": "AMD64",
        },
    }
    return aliases.get(os_name, {}).get(architecture.casefold(), architecture)


def _target_contract(
    os_name: str,
    architecture: str,
    python_version: str,
    python_implementation: str,
) -> dict[str, Any]:
    version = ".".join(python_version.split(".")[:2])
    normalized_architecture = _normalized_architecture(os_name, architecture)
    matches = [
        target
        for target in SUPPORTED_TARGETS
        if target["os"] == os_name
        and target["architecture"] == normalized_architecture
        and target["implementation"] == python_implementation
        and target["pythonVersion"] == version
    ]
    if len(matches) != 1:
        raise EnvironmentFailure(
            "python_lock_target_unsupported",
            f"unsupported Python lock target: {os_name}/{architecture}/{python_implementation}-{version}",
        )
    return matches[0]


def _projection_key(target: dict[str, str], profile: str) -> str:
    version = target["pythonVersion"].replace(".", "")
    return (
        f"{target['os'].lower()}-{target['architecture'].lower()}-"
        f"cpython{version}-{profile}"
    )


def bootstrap_profile_for_target(
    *,
    os_name: str,
    architecture: str,
    python_version: str,
    python_implementation: str = "CPython",
) -> str:
    target = _target_contract(
        os_name, architecture, python_version, python_implementation
    )
    profiles = target["profiles"]
    return "development" if "development" in profiles else str(profiles[0])


def _requirement_lines(path: Path) -> Iterable[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise EnvironmentFailure("python_lock_input_invalid", f"unable to read {path.name}") from exc
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            yield line


def _direct_requirements(root: Path, input_name: str, seen: set[str] | None = None) -> frozenset[str]:
    visited = seen or set()
    if input_name in visited:
        raise EnvironmentFailure("python_lock_input_invalid", "recursive requirement include detected")
    visited.add(input_name)
    names: set[str] = set()
    for line in _requirement_lines(root / input_name):
        if line.startswith(("-r ", "--requirement ")):
            included = line.split(maxsplit=1)[1]
            if Path(included).name != included or included not in REQUIREMENT_INPUTS:
                raise EnvironmentFailure("python_lock_input_invalid", "requirement include is not authoritative")
            names.update(_direct_requirements(root, included, visited.copy()))
            continue
        if line.startswith("-") or " @ " in line:
            raise EnvironmentFailure("python_lock_input_invalid", "unsupported direct requirement syntax")
        match = _NAME_RE.match(line)
        if match is None:
            raise EnvironmentFailure("python_lock_input_invalid", "direct requirement name is invalid")
        names.add(_normalized_name(match.group(0)))
    return frozenset(names)


def _logical_lock_lines(text: str) -> Iterable[str]:
    current = ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        continuation = stripped.endswith("\\")
        segment = stripped[:-1].rstrip() if continuation else stripped
        current = f"{current} {segment}".strip()
        if not continuation:
            yield current
            current = ""
    if current:
        raise EnvironmentFailure("python_lock_partial", "Python lock ends with a partial record")


def _parse_lock(path: Path) -> ParsedLock:
    try:
        data = path.read_bytes()
        text = data.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise EnvironmentFailure("python_lock_missing", f"Python lock is unreadable: {path.name}") from exc
    if any(pattern.search(text) for pattern in _UNSAFE_PATTERNS):
        raise EnvironmentFailure("python_lock_unsafe_content", "Python lock contains unsafe source material")
    lines = text.splitlines()
    if (
        b"\r" in data
        or not text.endswith("\n")
        or text.endswith("\n\n")
        or any(line != line.rstrip() or line.lstrip().startswith("#") for line in lines)
    ):
        raise EnvironmentFailure(
            "python_lock_not_normalized", "Python lock is not in reviewed normalized form"
        )
    distributions: dict[str, set[str]] = {}
    record_count = 0
    hash_count = 0
    marker_count = 0
    records: list[LockedRecord] = []
    for line in _logical_lock_lines(text):
        hash_marker = line.find(" --hash=")
        requirement = line if hash_marker < 0 else line[:hash_marker].rstrip()
        match = _PIN_RE.fullmatch(requirement)
        if match is None:
            raise EnvironmentFailure("python_lock_pin_incomplete", "every locked distribution must use an exact pin")
        hashes = _HASH_RE.findall(line)
        if not hashes:
            raise EnvironmentFailure("python_lock_hash_incomplete", "every locked distribution must include a SHA-256 hash")
        if hashes != sorted(set(hashes)):
            raise EnvironmentFailure("python_lock_not_normalized", "Python lock hashes are not normalized")
        residual = _HASH_RE.sub("", line[hash_marker:] if hash_marker >= 0 else "").strip()
        if residual:
            raise EnvironmentFailure("python_lock_partial", "Python lock contains unsupported install options")
        name = _normalized_name(match.group("name"))
        distributions.setdefault(name, set()).add(match.group("version"))
        records.append(
            LockedRecord(
                name=name,
                version=match.group("version"),
                hashes=tuple(hashes),
                marker=match.group("marker"),
            )
        )
        record_count += 1
        hash_count += len(hashes)
        marker_count += int(bool(match.group("marker")))
    if not distributions:
        raise EnvironmentFailure("python_lock_empty", "Python lock contains no distributions")
    return ParsedLock(
        distributions={name: frozenset(versions) for name, versions in sorted(distributions.items())},
        record_count=record_count,
        hash_count=hash_count,
        marker_count=marker_count,
        records=tuple(records),
    )


def _marker_environment(target: dict[str, str], python_version: str) -> dict[str, str]:
    return {
        "implementation_name": "cpython",
        "implementation_version": python_version,
        "os_name": "nt" if target["os"] == "Windows" else "posix",
        "platform_machine": target["architecture"],
        "platform_python_implementation": "CPython",
        "platform_release": "",
        "platform_system": target["os"],
        "platform_version": "",
        "python_full_version": python_version,
        "python_version": target["pythonVersion"],
        "sys_platform": {"Darwin": "darwin", "Linux": "linux", "Windows": "win32"}[
            target["os"]
        ],
    }


def _select_lock(parsed: ParsedLock, target: dict[str, str], python_version: str) -> ParsedLock:
    try:
        from pip._vendor.packaging.markers import Marker
    except ImportError as exc:
        raise EnvironmentFailure(
            "python_lock_marker_engine_unavailable", "pip marker evaluation is unavailable"
        ) from exc
    environment = _marker_environment(target, python_version)
    selected = tuple(
        record
        for record in parsed.records
        if record.marker is None or Marker(record.marker).evaluate(environment)
    )
    distributions: dict[str, set[str]] = {}
    for record in selected:
        distributions.setdefault(record.name, set()).add(record.version)
    ambiguous = sorted(name for name, versions in distributions.items() if len(versions) != 1)
    if ambiguous:
        raise EnvironmentFailure(
            "python_lock_target_ambiguous",
            "target selects multiple versions for: " + ",".join(ambiguous),
        )
    return ParsedLock(
        distributions={name: frozenset(versions) for name, versions in sorted(distributions.items())},
        record_count=len(selected),
        hash_count=sum(len(record.hashes) for record in selected),
        marker_count=sum(record.marker is not None for record in selected),
        records=selected,
    )


def _read_manifest(root: Path) -> dict[str, Any]:
    path = root / LOCK_MANIFEST
    try:
        text = path.read_text(encoding="utf-8")
        payload = json.loads(text)
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise EnvironmentFailure("python_lock_manifest_invalid", "Python lock manifest is missing or invalid") from exc
    if not isinstance(payload, dict):
        raise EnvironmentFailure("python_lock_manifest_invalid", "Python lock manifest must be an object")
    if text != json.dumps(payload, indent=2, sort_keys=True) + "\n":
        raise EnvironmentFailure(
            "python_lock_not_normalized", "Python lock manifest is not canonical JSON"
        )
    return payload


def _validate_manifest(
    root: Path, manifest: dict[str, Any]
) -> tuple[dict[tuple[str, str], ParsedLock], dict[str, ProjectionValidation]]:
    if set(manifest) != {
        "inputHashes",
        "policyVersion",
        "profiles",
        "resolver",
        "schemaVersion",
        "supportedTargets",
        "targetProjections",
    }:
        raise EnvironmentFailure("python_lock_manifest_invalid", "Python lock manifest fields are invalid")
    if manifest.get("schemaVersion") != LOCK_SCHEMA_VERSION or manifest.get("policyVersion") != LOCK_POLICY_VERSION:
        raise EnvironmentFailure("python_lock_schema_drift", "Python lock schema or policy version drifted")
    if manifest.get("resolver") != {
        "implementation": RESOLVER_IMPLEMENTATION,
        "version": RESOLVER_VERSION,
    }:
        raise EnvironmentFailure("python_lock_resolver_drift", "reviewed resolver identity drifted")
    expected_targets = _manifest_targets()
    if manifest.get("supportedTargets") != expected_targets:
        raise EnvironmentFailure("python_lock_target_drift", "supported Python target matrix drifted")
    expected_inputs = {name: normalized_content_hash(root / name) for name in REQUIREMENT_INPUTS}
    if manifest.get("inputHashes") != dict(sorted(expected_inputs.items())):
        raise EnvironmentFailure("python_lock_input_drift", "requirement inputs changed without a reviewed lock update")
    profiles = manifest.get("profiles")
    if not isinstance(profiles, dict) or set(profiles) != set(PROFILE_INPUTS):
        raise EnvironmentFailure("python_lock_manifest_invalid", "Python lock profiles are incomplete")
    parsed: dict[tuple[str, str], ParsedLock] = {}
    for profile, input_name in PROFILE_INPUTS.items():
        profile_data = profiles.get(profile)
        if (
            not isinstance(profile_data, dict)
            or set(profile_data) != {"input", "locks"}
            or profile_data.get("input") != input_name
        ):
            raise EnvironmentFailure("python_lock_manifest_invalid", "Python lock profile input is invalid")
        locks = profile_data.get("locks")
        if not isinstance(locks, dict) or set(locks) != set(PYTHON_VERSIONS):
            raise EnvironmentFailure("python_lock_manifest_invalid", "Python lock version coverage is incomplete")
        direct = _direct_requirements(root, input_name)
        for version in PYTHON_VERSIONS:
            metadata = locks.get(version)
            expected_path = LOCK_PATHS[(profile, version)]
            if (
                not isinstance(metadata, dict)
                or set(metadata)
                != {
                    "distributionCount",
                    "hashCount",
                    "markerCount",
                    "path",
                    "recordCount",
                    "sha256",
                }
                or metadata.get("path") != expected_path
            ):
                raise EnvironmentFailure("python_lock_manifest_invalid", "Python lock path is invalid")
            path = root / expected_path
            if not path.is_file() or metadata.get("sha256") != _file_hash(path):
                raise EnvironmentFailure("python_lock_content_drift", "reviewed Python lock content changed")
            record = _parse_lock(path)
            expected_counts = {
                "distributionCount": len(record.distributions),
                "hashCount": record.hash_count,
                "markerCount": record.marker_count,
                "recordCount": record.record_count,
            }
            if any(metadata.get(key) != value for key, value in expected_counts.items()):
                raise EnvironmentFailure("python_lock_manifest_invalid", "Python lock summary does not match content")
            missing = sorted(direct - set(record.distributions))
            if missing:
                raise EnvironmentFailure(
                    "python_lock_direct_requirement_missing",
                    "direct requirements are absent from Python lock: " + ",".join(missing),
                )
            parsed[(profile, version)] = record
    projection_payload = manifest.get("targetProjections")
    expected_projection_keys = {
        _projection_key(_target_identity(target), profile)
        for target in SUPPORTED_TARGETS
        for profile in target["profiles"]
    }
    if (
        not isinstance(projection_payload, dict)
        or set(projection_payload) != expected_projection_keys
    ):
        raise EnvironmentFailure(
            "python_lock_projection_drift", "target artifact projection matrix drifted"
        )
    projections: dict[str, ProjectionValidation] = {}
    for target_contract in SUPPORTED_TARGETS:
        target = _target_identity(target_contract)
        version = target["pythonVersion"]
        for profile in target_contract["profiles"]:
            selected = _select_lock(parsed[(profile, version)], target, version + ".0")
            key = _projection_key(target, profile)
            projections[key] = validate_projection(
                projection_payload[key],
                profile=profile,
                target=target,
                records=selected.records,
                distributions=selected.distributions,
            )
    return parsed, projections


def _target(
    os_name: str,
    architecture: str,
    python_version: str,
    python_implementation: str,
    profile: str,
) -> dict[str, str]:
    target = _target_contract(os_name, architecture, python_version, python_implementation)
    if profile not in target["profiles"]:
        version = ".".join(python_version.split(".")[:2])
        raise EnvironmentFailure(
            "python_lock_target_unsupported",
            f"unsupported Python lock target/profile: "
            f"{os_name}/{architecture}/{python_implementation}-{version}/{profile}",
        )
    return _target_identity(target)


def _content_hash(root: Path, manifest: dict[str, Any]) -> str:
    lock_hashes = {
        path: _file_hash(root / path)
        for path in sorted(set(LOCK_PATHS.values()))
    }
    return _canonical_hash(
        {
            "manifestSha256": _file_hash(root / LOCK_MANIFEST),
            "lockFiles": lock_hashes,
            "policyVersion": LOCK_POLICY_VERSION,
        }
    )


def load_python_lock(
    root: Path,
    *,
    os_name: str,
    architecture: str,
    python_version: str,
    python_implementation: str = "CPython",
    profile: str,
) -> PythonLockContract:
    root = root.resolve(strict=True)
    if profile not in PROFILE_INPUTS:
        raise EnvironmentFailure("python_lock_profile_invalid", "unsupported Python lock profile")
    target = _target(
        os_name, architecture, python_version, python_implementation, profile
    )
    manifest = _read_manifest(root)
    parsed, projections = _validate_manifest(root, manifest)
    version = target["pythonVersion"]
    selected = _select_lock(parsed[(profile, version)], target, python_version)
    lock_path = root / LOCK_PATHS[(profile, version)]
    projection_key = _projection_key(target, profile)
    projection = projections[projection_key]
    selected_artifacts = {
        name: projection.artifacts[name]
        for name in selected.distributions
        if name in projection.artifacts
    }
    if set(selected_artifacts) != set(selected.distributions):
        raise EnvironmentFailure(
            "python_lock_artifact_missing",
            "target projection omits a marker-selected distribution",
        )
    selected_hash_count = sum(len(artifacts) for artifacts in selected_artifacts.values())
    selected_source_build_count = sum(
        any(artifact.artifact_type == "sdist" for artifact in artifacts)
        for artifacts in selected_artifacts.values()
    )
    return PythonLockContract(
        profile=profile,
        target=target,
        lock_path=lock_path,
        content_hash=_content_hash(root, manifest),
        input_hashes=dict(manifest["inputHashes"]),
        direct_requirements=_direct_requirements(root, PROFILE_INPUTS[profile]),
        distributions=selected.distributions,
        artifacts=selected_artifacts,
        artifact_hashes={
            name: frozenset(artifact.sha256 for artifact in artifacts)
            for name, artifacts in selected_artifacts.items()
        },
        artifact_files={
            artifact.filename: artifact.sha256
            for artifacts in selected_artifacts.values()
            for artifact in artifacts
        },
        build_requirements=projection.build_requirements,
        hash_count=selected_hash_count,
        hash_verification=True,
        projection=projection_key,
        projection_hash=projection.projection_hash,
        source_build_count=selected_source_build_count,
        resolver=dict(manifest["resolver"]),
        lock_files={path: _file_hash(root / path) for path in sorted(set(LOCK_PATHS.values()))},
    )


def _default_resolver_runner(root: Path) -> ResolverRunner:
    def run(command: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                command,
                cwd=root,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
                timeout=900,
                env={key: value for key, value in os.environ.items() if key in {"HOME", "LANG", "LC_ALL", "PATH", "SSL_CERT_FILE"}},
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise EnvironmentFailure("python_lock_resolver_unavailable", "reviewed Python resolver is unavailable") from exc

    return run


def _verify_resolver(runner: ResolverRunner) -> None:
    result = runner([RESOLVER_IMPLEMENTATION, "--version"])
    identity = result.stdout.strip().split()
    if result.returncode != 0 or identity[:2] != [RESOLVER_IMPLEMENTATION, RESOLVER_VERSION]:
        raise EnvironmentFailure("python_lock_resolver_drift", "reviewed resolver version is unavailable")


def check_python_lock(
    root: Path,
    *,
    resolver_runner: ResolverRunner | None = None,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    runner = resolver_runner or _default_resolver_runner(root)
    _verify_resolver(runner)
    manifest = _read_manifest(root)
    parsed, projections = _validate_manifest(root, manifest)
    return {
        "status": "ok",
        "schemaVersion": LOCK_SCHEMA_VERSION,
        "policyVersion": LOCK_POLICY_VERSION,
        "contentHash": _content_hash(root, manifest),
        "inputHashes": dict(manifest["inputHashes"]),
        "resolver": dict(manifest["resolver"]),
        "locks": {
            f"{profile}-python{version}": {
                "distributionCount": len(record.distributions),
                "hashCount": record.hash_count,
                "markerCount": record.marker_count,
                "path": LOCK_PATHS[(profile, version)],
                "recordCount": record.record_count,
            }
            for (profile, version), record in sorted(parsed.items())
        },
        "supportedTargets": _manifest_targets(),
        "targetProjections": {
            key: {
                "artifactCount": projection.hash_count,
                "projectionHash": projection.projection_hash,
                "sourceBuildCount": projection.source_build_count,
            }
            for key, projection in sorted(projections.items())
        },
    }


def _changes(
    before: dict[str, frozenset[str]], after: dict[str, frozenset[str]]
) -> list[dict[str, Any]]:
    changed: list[dict[str, Any]] = []
    for name in sorted(set(before) | set(after)):
        old = sorted(before.get(name, frozenset()))
        new = sorted(after.get(name, frozenset()))
        if old == new:
            continue
        kind = "added" if not old else "removed" if not new else "changed"
        changed.append({"name": name, "change": kind, "before": old, "after": new})
    return changed


def _lock_changes(
    before: dict[tuple[str, str], ParsedLock],
    after: dict[tuple[str, str], ParsedLock],
    direct_names: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    direct: list[dict[str, Any]] = []
    transitive: list[dict[str, Any]] = []
    for profile, version in sorted(LOCK_PATHS):
        old = before.get((profile, version))
        current = after[(profile, version)]
        changes = _changes(
            old.distributions if old else {},
            current.distributions,
        )
        for change in changes:
            item = {**change, "profile": profile, "pythonVersion": version}
            (direct if change["name"] in direct_names else transitive).append(item)
    return direct, transitive


def _build_target_projections(
    records: dict[tuple[str, str], ParsedLock],
    *,
    artifact_index: ArtifactIndex,
    artifact_reader: ArtifactReader,
) -> dict[str, object]:
    index_cache: dict[tuple[str, str], tuple[Any, ...]] = {}
    source_cache: dict[str, bytes] = {}

    def cached_index(name: str, version: str) -> tuple[Any, ...]:
        key = (name, version)
        if key not in index_cache:
            index_cache[key] = tuple(artifact_index(name, version))
        return index_cache[key]

    def cached_reader(candidate: Any) -> bytes:
        if candidate.sha256 not in source_cache:
            source_cache[candidate.sha256] = artifact_reader(candidate)
        return source_cache[candidate.sha256]

    projections: dict[str, object] = {}
    for target_contract in SUPPORTED_TARGETS:
        target = _target_identity(target_contract)
        version = target["pythonVersion"]
        for profile in target_contract["profiles"]:
            selected = _select_lock(records[(profile, version)], target, version + ".0")
            key = _projection_key(target, profile)
            projections[key] = build_projection(
                profile=profile,
                target=target,
                records=selected.records,
                distributions=selected.distributions,
                artifact_index=cached_index,
                artifact_reader=cached_reader,
            )
    return projections


def _new_manifest(
    root: Path,
    records: dict[tuple[str, str], ParsedLock],
    stage: Path,
    target_projections: dict[str, object],
) -> dict[str, Any]:
    profiles: dict[str, Any] = {}
    for profile, input_name in PROFILE_INPUTS.items():
        locks: dict[str, Any] = {}
        for version in PYTHON_VERSIONS:
            path_name = LOCK_PATHS[(profile, version)]
            parsed = records[(profile, version)]
            locks[version] = {
                "distributionCount": len(parsed.distributions),
                "hashCount": parsed.hash_count,
                "markerCount": parsed.marker_count,
                "path": path_name,
                "recordCount": parsed.record_count,
                "sha256": _file_hash(stage / path_name),
            }
        profiles[profile] = {"input": input_name, "locks": locks}
    return {
        "schemaVersion": LOCK_SCHEMA_VERSION,
        "policyVersion": LOCK_POLICY_VERSION,
        "resolver": {"implementation": RESOLVER_IMPLEMENTATION, "version": RESOLVER_VERSION},
        "inputHashes": {
            name: normalized_content_hash(root / name) for name in sorted(REQUIREMENT_INPUTS)
        },
        "profiles": profiles,
        "supportedTargets": _manifest_targets(),
        "targetProjections": target_projections,
    }


def update_python_lock(
    root: Path,
    *,
    resolver_runner: ResolverRunner | None = None,
    artifact_index: ArtifactIndex | None = None,
    artifact_reader: ArtifactReader | None = None,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    runner = resolver_runner or _default_resolver_runner(root)
    _verify_resolver(runner)
    for input_name in REQUIREMENT_INPUTS:
        normalized_content_hash(root / input_name)
    old_manifest: dict[str, Any] | None = None
    old_manifest_valid = False
    try:
        old_manifest = _read_manifest(root)
        _validate_manifest(root, old_manifest)
        old_manifest_valid = True
    except EnvironmentFailure:
        pass
    old_records: dict[tuple[str, str], ParsedLock] = {}
    for key, path_name in LOCK_PATHS.items():
        path = root / path_name
        if path.is_file():
            old_records[key] = _parse_lock(path)
    with tempfile.TemporaryDirectory(prefix="wolfystock-python-lock-") as temporary:
        stage = Path(temporary)
        new_records: dict[tuple[str, str], ParsedLock] = {}
        for profile, input_name in PROFILE_INPUTS.items():
            for version in PYTHON_VERSIONS:
                path_name = LOCK_PATHS[(profile, version)]
                output = stage / path_name
                existing = root / path_name
                if existing.is_file():
                    shutil.copyfile(existing, output)
                command = [
                    RESOLVER_IMPLEMENTATION,
                    "--no-config",
                    "pip",
                    "compile",
                    "--universal",
                    "--python-version",
                    version,
                    "--generate-hashes",
                    "--no-header",
                    "--no-annotate",
                    "--no-sources",
                    "--no-python-downloads",
                    "--resolution",
                    "highest",
                    "--prerelease",
                    "disallow",
                    "--fork-strategy",
                    "requires-python",
                    "--output-file",
                    str(output),
                    input_name,
                ]
                result = runner(command)
                if result.returncode != 0:
                    raise EnvironmentFailure(
                        "python_lock_resolution_failed",
                        f"Python lock resolution failed for {profile}/CPython-{version}",
                    )
                new_records[(profile, version)] = _parse_lock(output)
        lock_files_unchanged = all(
            (root / path_name).is_file()
            and _file_hash(root / path_name) == _file_hash(stage / path_name)
            for path_name in sorted(set(LOCK_PATHS.values()))
        )
        if old_manifest_valid and lock_files_unchanged and old_manifest is not None:
            target_projections = dict(old_manifest["targetProjections"])
        else:
            target_projections = _build_target_projections(
                new_records,
                artifact_index=artifact_index or pypi_artifact_index,
                artifact_reader=artifact_reader or read_artifact,
            )
        manifest = _new_manifest(root, new_records, stage, target_projections)
        manifest_path = stage / LOCK_MANIFEST
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        direct_names = set().union(
            *(_direct_requirements(root, input_name) for input_name in REQUIREMENT_INPUTS)
        )
        direct_changes, transitive_changes = _lock_changes(
            old_records, new_records, direct_names
        )
        for path_name in (*sorted(set(LOCK_PATHS.values())), LOCK_MANIFEST):
            staged = root / f".{path_name}.wolfy-lock-update"
            shutil.copyfile(stage / path_name, staged)
            os.replace(staged, root / path_name)
    checked_manifest = _read_manifest(root)
    _validate_manifest(root, checked_manifest)
    previous_projection_hashes = {
        key: value.get("projectionHash")
        for key, value in (old_manifest or {}).get("targetProjections", {}).items()
        if isinstance(value, dict)
    }
    current_projection_hashes = {
        key: value["projectionHash"]
        for key, value in checked_manifest["targetProjections"].items()
    }
    projection_changes = [
        {
            "projection": key,
            "before": previous_projection_hashes.get(key),
            "after": current_projection_hashes.get(key),
        }
        for key in sorted(set(previous_projection_hashes) | set(current_projection_hashes))
        if previous_projection_hashes.get(key) != current_projection_hashes.get(key)
    ]
    return {
        "status": "updated",
        "schemaVersion": LOCK_SCHEMA_VERSION,
        "policyVersion": LOCK_POLICY_VERSION,
        "contentHash": _content_hash(root, checked_manifest),
        "resolver": {"implementation": RESOLVER_IMPLEMENTATION, "version": RESOLVER_VERSION},
        "directChanges": direct_changes,
        "targetProjectionChanges": projection_changes,
        "transitiveChanges": transitive_changes,
    }
