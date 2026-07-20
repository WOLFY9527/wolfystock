from __future__ import annotations

import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.environment.errors import EnvironmentFailure
from scripts.environment.python_artifacts import (
    ArtifactCandidate,
    build_projection,
    wheel_is_compatible,
)
from scripts.environment.python_lock import (
    LOCK_MANIFEST,
    LOCK_POLICY_VERSION,
    LOCK_SCHEMA_VERSION,
    RESOLVER_IMPLEMENTATION,
    RESOLVER_VERSION,
    check_python_lock,
    load_python_lock,
    normalized_content_hash,
    update_python_lock,
)


HASH_A = "a" * 64
HASH_B = "b" * 64
SUPPORTED_TARGETS = [
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
]
ROOT = Path(__file__).resolve().parents[2]


def lock_text(*records: tuple[str, str, str, str | None]) -> str:
    lines: list[str] = []
    for name, version, digest, marker in records:
        suffix = f" ; {marker}" if marker else ""
        lines.extend((f"{name}=={version}{suffix} \\", f"    --hash=sha256:{digest}"))
    return "\n".join(lines) + "\n"


def canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def target_identity(target: dict[str, object]) -> dict[str, str]:
    return {
        key: str(value)
        for key, value in target.items()
        if key != "profiles"
    }


def projection_key(target: dict[str, object], profile: str) -> str:
    version = str(target["pythonVersion"]).replace(".", "")
    return (
        f"{str(target['os']).lower()}-{str(target['architecture']).lower()}-"
        f"cpython{version}-{profile}"
    )


def projection_record(name: str, version: str, digest: str) -> dict[str, object]:
    normalized = name.replace("-", "_")
    return {
        "artifacts": [
            {
                "filename": f"{normalized}-{version}-py3-none-any.whl",
                "sha256": digest,
                "type": "wheel",
            }
        ],
        "name": name,
        "version": version,
    }


def target_projections() -> dict[str, object]:
    projections: dict[str, object] = {}
    for target in SUPPORTED_TARGETS:
        for profile in target["profiles"]:
            records = [projection_record("demo", "1.0", HASH_A)]
            if profile == "development":
                records.extend(
                    (
                        projection_record("pluggy", "1.5", HASH_A),
                        projection_record("pytest", "8.3", HASH_B),
                    )
                )
            payload = {
                "profile": profile,
                "records": records,
                "target": target_identity(target),
            }
            projections[projection_key(target, profile)] = {
                **payload,
                "projectionHash": canonical_hash(payload),
            }
    return projections


def write_manifest(root: Path, manifest: dict[str, object]) -> None:
    (root / LOCK_MANIFEST).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def refresh_projection_hash(projection: dict[str, object]) -> None:
    payload = {
        key: value for key, value in projection.items() if key != "projectionHash"
    }
    projection["projectionHash"] = canonical_hash(payload)


def resolver_identity(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        command, 0, f"{RESOLVER_IMPLEMENTATION} {RESOLVER_VERSION}\n", ""
    )


def fake_artifact_index(name: str, version: str) -> tuple[ArtifactCandidate, ...]:
    digest = HASH_B if name == "pytest" else HASH_A
    normalized = name.replace("-", "_")
    return (
        ArtifactCandidate(f"{normalized}-{version}-py3-none-any.whl", digest),
    )


def invalidate_arm64_projection(root: Path) -> None:
    manifest = json.loads((root / LOCK_MANIFEST).read_text(encoding="utf-8"))
    del manifest["targetProjections"]["linux-aarch64-cpython311-runtime"]
    write_manifest(root, manifest)


def unchanged_resolver(command: list[str]) -> subprocess.CompletedProcess[str]:
    if command == [RESOLVER_IMPLEMENTATION, "--version"]:
        return resolver_identity(command)
    output = Path(command[command.index("--output-file") + 1])
    assert output.is_file()
    return subprocess.CompletedProcess(command, 0, "", "")


def source_archive(pyproject: str) -> bytes:
    content = pyproject.encode()
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        info = tarfile.TarInfo("demo-1.0/pyproject.toml")
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))
    return stream.getvalue()


def write_lock_repository(root: Path) -> None:
    (root / "requirements.txt").write_text("demo>=1\n", encoding="utf-8")
    (root / "requirements-dev.txt").write_text(
        "-r requirements.txt\npytest>=8\n", encoding="utf-8"
    )
    lock_files = {
        "requirements-python311-runtime.lock": lock_text(("demo", "1.0", HASH_A, None)),
        "requirements-python311-dev.lock": lock_text(
            ("demo", "1.0", HASH_A, None),
            ("pluggy", "1.5", HASH_A, None),
            ("pytest", "8.3", HASH_B, None),
        ),
        "requirements-python312-runtime.lock": lock_text(("demo", "1.0", HASH_A, None)),
        "requirements-python312-dev.lock": lock_text(
            ("demo", "1.0", HASH_A, None),
            ("pluggy", "1.5", HASH_A, None),
            ("pytest", "8.3", HASH_B, None),
        ),
    }
    for name, content in lock_files.items():
        (root / name).write_text(content, encoding="utf-8")
    profiles = {}
    for profile, input_name in (
        ("runtime", "requirements.txt"),
        ("development", "requirements-dev.txt"),
    ):
        locks = {}
        for version in ("3.11", "3.12"):
            path = f"requirements-python{version.replace('.', '')}-{'dev' if profile == 'development' else profile}.lock"
            content = lock_files[path]
            locks[version] = {
                "distributionCount": 3 if profile == "development" else 1,
                "hashCount": 3 if profile == "development" else 1,
                "markerCount": 0,
                "path": path,
                "recordCount": 3 if profile == "development" else 1,
                "sha256": hashlib.sha256(content.encode()).hexdigest(),
            }
        profiles[profile] = {"input": input_name, "locks": locks}
    manifest = {
        "schemaVersion": LOCK_SCHEMA_VERSION,
        "policyVersion": LOCK_POLICY_VERSION,
        "resolver": {
            "implementation": RESOLVER_IMPLEMENTATION,
            "version": RESOLVER_VERSION,
        },
        "inputHashes": {
            "requirements-dev.txt": normalized_content_hash(root / "requirements-dev.txt"),
            "requirements.txt": normalized_content_hash(root / "requirements.txt"),
        },
        "profiles": profiles,
        "supportedTargets": SUPPORTED_TARGETS,
        "targetProjections": target_projections(),
    }
    write_manifest(root, manifest)


def test_unchanged_contract_is_current_and_byte_stable(tmp_path: Path) -> None:
    write_lock_repository(tmp_path)
    before = {path.name: path.read_bytes() for path in tmp_path.glob("requirements*.lock")}

    result = check_python_lock(
        tmp_path,
        resolver_runner=lambda command: subprocess.CompletedProcess(
            command, 0, f"{RESOLVER_IMPLEMENTATION} {RESOLVER_VERSION}\n", ""
        ),
    )

    assert result["status"] == "ok"
    assert result["resolver"] == {
        "implementation": RESOLVER_IMPLEMENTATION,
        "version": RESOLVER_VERSION,
    }
    assert before == {path.name: path.read_bytes() for path in tmp_path.glob("requirements*.lock")}


def test_update_is_byte_identical_when_resolution_is_unchanged(tmp_path: Path) -> None:
    write_lock_repository(tmp_path)
    before = {
        path.name: path.read_bytes()
        for path in tmp_path.glob("requirements*.*")
    }

    def resolver(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command == [RESOLVER_IMPLEMENTATION, "--version"]:
            return subprocess.CompletedProcess(
                command, 0, f"{RESOLVER_IMPLEMENTATION} {RESOLVER_VERSION}\n", ""
            )
        output = Path(command[command.index("--output-file") + 1])
        assert output.is_file()
        return subprocess.CompletedProcess(command, 0, "", "")

    result = update_python_lock(tmp_path, resolver_runner=resolver)

    assert result["directChanges"] == []
    assert result["transitiveChanges"] == []
    assert before == {
        path.name: path.read_bytes()
        for path in tmp_path.glob("requirements*.*")
    }


def test_target_projection_regeneration_is_deterministic(tmp_path: Path) -> None:
    generated: list[bytes] = []
    for name in ("first", "second"):
        root = tmp_path / name
        root.mkdir()
        write_lock_repository(root)
        invalidate_arm64_projection(root)

        update_python_lock(
            root,
            resolver_runner=unchanged_resolver,
            artifact_index=fake_artifact_index,
            artifact_reader=lambda _candidate: pytest.fail("wheel projection read source"),
        )
        generated.append((root / LOCK_MANIFEST).read_bytes())

    assert generated[0] == generated[1]


def test_every_direct_requirement_maps_to_exact_hashed_pins(tmp_path: Path) -> None:
    write_lock_repository(tmp_path)

    contract = load_python_lock(
        tmp_path,
        os_name="Darwin",
        architecture="arm64",
        python_version="3.11.15",
        profile="development",
    )

    assert contract.direct_requirements == frozenset({"demo", "pytest"})
    assert contract.distributions == {"demo": frozenset({"1.0"}), "pluggy": frozenset({"1.5"}), "pytest": frozenset({"8.3"})}
    assert contract.hash_count == 3
    assert contract.hash_verification is True
    assert contract.lock_path.name == "requirements-python311-dev.lock"


def test_every_supported_projection_selects_one_reviewed_parquet_wheel() -> None:
    manifest = json.loads((ROOT / LOCK_MANIFEST).read_text(encoding="utf-8"))
    parquet_engines = {"pyarrow", "fastparquet"}

    for projection_name, projection in manifest["targetProjections"].items():
        records = {record["name"]: record for record in projection["records"]}
        assert set(records) & parquet_engines == {"pyarrow"}, projection_name

        engine = records["pyarrow"]
        assert engine["version"] == "25.0.0", projection_name
        assert "sourceBuild" not in engine, projection_name
        assert engine["artifacts"], projection_name
        assert all(
            artifact["type"] == "wheel" for artifact in engine["artifacts"]
        ), projection_name
        assert all(
            len(artifact["sha256"]) == 64 for artifact in engine["artifacts"]
        ), projection_name


@pytest.mark.parametrize(
    ("mutation", "reason_code"),
    [
        (lambda root: (root / "requirements.txt").write_text("demo>=2\n", encoding="utf-8"), "python_lock_input_drift"),
        (
            lambda root: (root / "requirements-python311-dev.lock").write_text(
                "demo>=1\n", encoding="utf-8"
            ),
            "python_lock_content_drift",
        ),
        (
            lambda root: (root / "requirements-python311-dev.lock").write_text(
                "demo==1.0\n", encoding="utf-8"
            ),
            "python_lock_content_drift",
        ),
    ],
)
def test_corrupt_or_stale_contract_fails_closed(tmp_path: Path, mutation, reason_code: str) -> None:
    write_lock_repository(tmp_path)
    mutation(tmp_path)

    with pytest.raises(EnvironmentFailure) as raised:
        load_python_lock(
            tmp_path,
            os_name="Darwin",
            architecture="arm64",
            python_version="3.11.15",
            profile="development",
        )

    assert raised.value.code == reason_code


def test_missing_pin_or_hash_is_rejected_after_reviewed_hash_is_updated(tmp_path: Path) -> None:
    write_lock_repository(tmp_path)
    path = tmp_path / "requirements-python311-dev.lock"
    path.write_text("demo>=1\n", encoding="utf-8")
    manifest = json.loads((tmp_path / LOCK_MANIFEST).read_text(encoding="utf-8"))
    manifest["profiles"]["development"]["locks"]["3.11"]["sha256"] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    (tmp_path / LOCK_MANIFEST).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    with pytest.raises(EnvironmentFailure) as raised:
        load_python_lock(
            tmp_path,
            os_name="Darwin",
            architecture="arm64",
            python_version="3.11.15",
            profile="development",
        )

    assert raised.value.code == "python_lock_pin_incomplete"


def test_non_normalized_lock_format_is_rejected(tmp_path: Path) -> None:
    write_lock_repository(tmp_path)
    path = tmp_path / "requirements-python311-dev.lock"
    path.write_text("# unreviewed annotation\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    manifest = json.loads((tmp_path / LOCK_MANIFEST).read_text(encoding="utf-8"))
    manifest["profiles"]["development"]["locks"]["3.11"]["sha256"] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    (tmp_path / LOCK_MANIFEST).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    with pytest.raises(EnvironmentFailure) as raised:
        load_python_lock(
            tmp_path,
            os_name="Darwin",
            architecture="arm64",
            python_version="3.11.15",
            profile="development",
        )

    assert raised.value.code == "python_lock_not_normalized"


def test_manifest_rejects_unreviewed_fields(tmp_path: Path) -> None:
    write_lock_repository(tmp_path)
    path = tmp_path / LOCK_MANIFEST
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["unreviewedSource"] = "https://packages.example.test/simple"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(EnvironmentFailure) as raised:
        load_python_lock(
            tmp_path,
            os_name="Darwin",
            architecture="arm64",
            python_version="3.11.15",
            profile="development",
        )

    assert raised.value.code == "python_lock_manifest_invalid"


@pytest.mark.parametrize(
    "unsafe_text",
    [
        "--index-url https://user:secret@example.test/simple\n",
        "demo @ file:///Users/example/private/demo.whl\n",
        "# generated at 2026-07-17T10:00:00Z\n",
    ],
)
def test_lock_rejects_credentials_private_paths_and_timestamps(
    tmp_path: Path, unsafe_text: str
) -> None:
    write_lock_repository(tmp_path)
    path = tmp_path / "requirements-python311-dev.lock"
    path.write_text(unsafe_text + lock_text(("demo", "1.0", HASH_A, None)), encoding="utf-8")
    manifest = json.loads((tmp_path / LOCK_MANIFEST).read_text(encoding="utf-8"))
    manifest["profiles"]["development"]["locks"]["3.11"]["sha256"] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    (tmp_path / LOCK_MANIFEST).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    with pytest.raises(EnvironmentFailure) as raised:
        load_python_lock(
            tmp_path,
            os_name="Darwin",
            architecture="arm64",
            python_version="3.11.15",
            profile="development",
        )

    assert raised.value.code == "python_lock_unsafe_content"


def test_unsupported_platform_or_python_fails_explicitly(tmp_path: Path) -> None:
    write_lock_repository(tmp_path)

    with pytest.raises(EnvironmentFailure) as raised:
        load_python_lock(
            tmp_path,
            os_name="Linux",
            architecture="aarch64",
            python_version="3.13.0",
            profile="development",
        )

    assert raised.value.code == "python_lock_target_unsupported"


def test_unsupported_python_implementation_fails_explicitly(tmp_path: Path) -> None:
    write_lock_repository(tmp_path)

    with pytest.raises(EnvironmentFailure) as raised:
        load_python_lock(
            tmp_path,
            os_name="Darwin",
            architecture="arm64",
            python_version="3.11.15",
            python_implementation="PyPy",
            profile="development",
        )

    assert raised.value.code == "python_lock_target_unsupported"


def test_supported_environment_markers_select_exact_platform_projection(tmp_path: Path) -> None:
    write_lock_repository(tmp_path)
    path = tmp_path / "requirements-python311-dev.lock"
    path.write_text(
        path.read_text(encoding="utf-8")
        + lock_text(
            ("colorama", "0.4.6", HASH_A, "sys_platform == 'win32'"),
            ("uvloop", "0.22.1", HASH_B, "sys_platform != 'win32'"),
        ),
        encoding="utf-8",
    )
    manifest = json.loads((tmp_path / LOCK_MANIFEST).read_text(encoding="utf-8"))
    metadata = manifest["profiles"]["development"]["locks"]["3.11"]
    metadata.update(
        {
            "distributionCount": 5,
            "hashCount": 5,
            "markerCount": 2,
            "recordCount": 5,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    )
    for projection in manifest["targetProjections"].values():
        if (
            projection["profile"] != "development"
            or projection["target"]["pythonVersion"] != "3.11"
        ):
            continue
        record = (
            projection_record("colorama", "0.4.6", HASH_A)
            if projection["target"]["os"] == "Windows"
            else projection_record("uvloop", "0.22.1", HASH_B)
        )
        projection["records"].append(record)
        projection["records"].sort(key=lambda item: item["name"])
        refresh_projection_hash(projection)
    (tmp_path / LOCK_MANIFEST).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    macos = load_python_lock(
        tmp_path,
        os_name="Darwin",
        architecture="arm64",
        python_version="3.11.15",
        profile="development",
    )
    windows = load_python_lock(
        tmp_path,
        os_name="Windows",
        architecture="AMD64",
        python_version="3.11.15",
        profile="development",
    )

    assert "uvloop" in macos.distributions and "colorama" not in macos.distributions
    assert "colorama" in windows.distributions and "uvloop" not in windows.distributions


@pytest.mark.parametrize(
    ("os_name", "architecture", "python_version"),
    [
        ("Darwin", "arm64", "3.11.15"),
        ("Darwin", "arm64", "3.12.11"),
        ("Windows", "AMD64", "3.11.15"),
        ("Windows", "AMD64", "3.12.11"),
    ],
)
def test_non_linux_targets_select_reviewed_portable_litellm(
    os_name: str, architecture: str, python_version: str
) -> None:
    contract = load_python_lock(
        ROOT,
        os_name=os_name,
        architecture=architecture,
        python_version=python_version,
        profile="runtime",
    )

    assert contract.distributions["litellm"] == frozenset({"1.91.3"})
    assert {"litellm", "tiktoken", "httpx"} <= contract.direct_requirements
    assert "openai" not in contract.direct_requirements
    assert contract.distributions["openai"] == frozenset({"2.46.0"})


def test_resolver_version_drift_fails_explicit_check(tmp_path: Path) -> None:
    write_lock_repository(tmp_path)

    with pytest.raises(EnvironmentFailure) as raised:
        check_python_lock(
            tmp_path,
            resolver_runner=lambda command: subprocess.CompletedProcess(
                command, 0, f"{RESOLVER_IMPLEMENTATION} 99.0.0\n", ""
            ),
        )

    assert raised.value.code == "python_lock_resolver_drift"


def test_lock_content_change_changes_contract_identity(tmp_path: Path) -> None:
    write_lock_repository(tmp_path)
    first = load_python_lock(
        tmp_path,
        os_name="Darwin",
        architecture="arm64",
        python_version="3.11.15",
        profile="development",
    )
    path = tmp_path / "requirements-python311-dev.lock"
    path.write_text(path.read_text(encoding="utf-8").replace("pluggy==1.5", "pluggy==1.6"), encoding="utf-8")
    manifest = json.loads((tmp_path / LOCK_MANIFEST).read_text(encoding="utf-8"))
    manifest["profiles"]["development"]["locks"]["3.11"]["sha256"] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    for projection in manifest["targetProjections"].values():
        if (
            projection["profile"] != "development"
            or projection["target"]["pythonVersion"] != "3.11"
        ):
            continue
        pluggy = next(
            record for record in projection["records"] if record["name"] == "pluggy"
        )
        pluggy.update(projection_record("pluggy", "1.6", HASH_A))
        refresh_projection_hash(projection)
    (tmp_path / LOCK_MANIFEST).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    second = load_python_lock(
        tmp_path,
        os_name="Darwin",
        architecture="arm64",
        python_version="3.11.15",
        profile="development",
    )

    assert first.content_hash != second.content_hash


def test_update_reports_direct_and_transitive_changes_separately(tmp_path: Path) -> None:
    write_lock_repository(tmp_path)

    def resolver(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command == [RESOLVER_IMPLEMENTATION, "--version"]:
            return subprocess.CompletedProcess(command, 0, f"{RESOLVER_IMPLEMENTATION} {RESOLVER_VERSION}\n", "")
        assert command[1:3] == ["--no-config", "pip"]
        output = Path(command[command.index("--output-file") + 1])
        profile = "dev" if "requirements-dev.txt" in command else "runtime"
        records = [("demo", "2.0", HASH_A, None)]
        if profile == "dev":
            records.extend((("pluggy", "1.6", HASH_A, None), ("pytest", "8.3", HASH_B, None)))
        output.write_text(lock_text(*records), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    result = update_python_lock(
        tmp_path,
        resolver_runner=resolver,
        artifact_index=fake_artifact_index,
        artifact_reader=lambda _candidate: pytest.fail("wheel projection read source"),
    )

    assert {item["name"] for item in result["directChanges"]} == {"demo"}
    assert {item["name"] for item in result["transitiveChanges"]} == {"pluggy"}
    assert len(result["directChanges"]) == 4
    assert len(result["transitiveChanges"]) == 2
    assert {item["profile"] for item in result["transitiveChanges"]} == {"development"}
    assert {item["pythonVersion"] for item in result["transitiveChanges"]} == {"3.11", "3.12"}
    assert result["status"] == "updated"
    assert check_python_lock(tmp_path, resolver_runner=resolver)["status"] == "ok"


def test_t505_docker_platform_matrix_is_represented_by_runtime_lock_targets(
    tmp_path: Path,
) -> None:
    write_lock_repository(tmp_path)

    result = check_python_lock(tmp_path, resolver_runner=resolver_identity)
    docker_platforms = {
        "linux/arm64" if target["architecture"] == "aarch64" else "linux/amd64"
        for target in result["supportedTargets"]
        if target["os"] == "Linux"
        and target["pythonVersion"] == "3.11"
        and "runtime" in target["profiles"]
    }

    assert docker_platforms == {"linux/amd64", "linux/arm64"}


@pytest.mark.parametrize(
    "filename",
    [
        "demo-1.0-cp311-cp311-manylinux_2_5_x86_64.whl",
        "demo-1.0-cp311-cp311-manylinux1_x86_64.whl",
    ],
)
def test_linux_x86_64_accepts_compatible_legacy_manylinux_wheels(
    filename: str,
) -> None:
    assert wheel_is_compatible(filename, target_identity(SUPPORTED_TARGETS[0]))


@pytest.mark.parametrize(
    ("filename", "compatible"),
    [
        ("demo-1.0-cp311-cp311-macosx_11_0_arm64.whl", False),
        ("demo-1.0-cp312-cp312-macosx_11_0_arm64.whl", True),
    ],
)
def test_cpython312_artifact_compatibility_uses_explicit_target_abi(
    filename: str, compatible: bool
) -> None:
    assert wheel_is_compatible(filename, target_identity(SUPPORTED_TARGETS[5])) is compatible


def test_artifact_requires_python_is_evaluated_against_static_target() -> None:
    candidate = ArtifactCandidate(
        "demo-1.0-cp311-cp311-manylinux_2_17_aarch64.whl",
        HASH_A,
        requires_python=">=3.12",
    )

    with pytest.raises(EnvironmentFailure) as raised:
        build_projection(
            profile="runtime",
            target=target_identity(SUPPORTED_TARGETS[1]),
            records=(SimpleNamespace(name="demo", hashes=(HASH_A,)),),
            distributions={"demo": frozenset({"1.0"})},
            artifact_index=lambda _name, _version: (candidate,),
            artifact_reader=lambda _candidate: pytest.fail("unexpected source read"),
        )

    assert raised.value.code == "python_lock_artifact_missing"


@pytest.mark.parametrize("architecture", ["arm64", "aarch64"])
def test_linux_arm64_aliases_select_one_reviewed_runtime_target(
    tmp_path: Path, architecture: str
) -> None:
    write_lock_repository(tmp_path)

    contract = load_python_lock(
        tmp_path,
        os_name="Linux",
        architecture=architecture,
        python_version="3.11.15",
        profile="runtime",
    )

    assert contract.target == target_identity(SUPPORTED_TARGETS[1])
    assert contract.projection_hash == contract.evidence()["selectedProjectionHash"]


def mutate_arm64_runtime_projection(
    root: Path, mutation
) -> None:
    manifest = json.loads((root / LOCK_MANIFEST).read_text(encoding="utf-8"))
    key = "linux-aarch64-cpython311-runtime"
    projection = manifest["targetProjections"][key]
    mutation(projection)
    refresh_projection_hash(projection)
    write_manifest(root, manifest)


@pytest.mark.parametrize(
    "filename",
    [
        "demo-1.0-cp311-cp311-manylinux_2_17_x86_64.whl",
        "demo-1.0-cp311-cp311-macosx_11_0_arm64.whl",
    ],
)
def test_linux_arm64_rejects_incompatible_wheel_projection(
    tmp_path: Path, filename: str
) -> None:
    write_lock_repository(tmp_path)
    mutate_arm64_runtime_projection(
        tmp_path,
        lambda projection: projection["records"][0]["artifacts"][0].update(
            {"filename": filename}
        ),
    )

    with pytest.raises(EnvironmentFailure) as raised:
        load_python_lock(
            tmp_path,
            os_name="Linux",
            architecture="aarch64",
            python_version="3.11.15",
            profile="runtime",
        )

    assert raised.value.code == "python_lock_artifact_incompatible"


def test_linux_arm64_missing_artifact_fails_lock_check(tmp_path: Path) -> None:
    write_lock_repository(tmp_path)
    mutate_arm64_runtime_projection(
        tmp_path,
        lambda projection: projection["records"][0].update({"artifacts": []}),
    )

    with pytest.raises(EnvironmentFailure) as raised:
        check_python_lock(tmp_path, resolver_runner=resolver_identity)

    assert raised.value.code == "python_lock_artifact_missing"


def test_linux_arm64_missing_source_build_backend_fails_before_install(
    tmp_path: Path,
) -> None:
    write_lock_repository(tmp_path)

    def use_unreviewed_source(projection: dict[str, object]) -> None:
        projection["records"][0]["artifacts"] = [
            {
                "filename": "demo-1.0.tar.gz",
                "sha256": HASH_A,
                "type": "sdist",
            }
        ]

    mutate_arm64_runtime_projection(tmp_path, use_unreviewed_source)

    with pytest.raises(EnvironmentFailure) as raised:
        load_python_lock(
            tmp_path,
            os_name="Linux",
            architecture="aarch64",
            python_version="3.11.15",
            profile="runtime",
        )

    assert raised.value.code == "python_lock_source_build_unlocked"


def test_lock_update_rejects_fake_index_without_linux_arm64_artifact(
    tmp_path: Path,
) -> None:
    write_lock_repository(tmp_path)
    invalidate_arm64_projection(tmp_path)
    before = {
        path.name: path.read_bytes() for path in tmp_path.glob("requirements*.*")
    }

    def x86_only_index(name: str, version: str) -> tuple[ArtifactCandidate, ...]:
        digest = HASH_B if name == "pytest" else HASH_A
        normalized = name.replace("-", "_")
        return (
            ArtifactCandidate(
                f"{normalized}-{version}-cp311-cp311-manylinux_2_17_x86_64.whl",
                digest,
            ),
        )

    with pytest.raises(EnvironmentFailure) as raised:
        update_python_lock(
            tmp_path,
            resolver_runner=unchanged_resolver,
            artifact_index=x86_only_index,
            artifact_reader=lambda _candidate: pytest.fail("unexpected source read"),
        )

    assert raised.value.code == "python_lock_artifact_missing"
    assert before == {
        path.name: path.read_bytes() for path in tmp_path.glob("requirements*.*")
    }


def test_lock_update_rejects_fake_arm64_source_with_unlocked_backend(
    tmp_path: Path,
) -> None:
    write_lock_repository(tmp_path)
    invalidate_arm64_projection(tmp_path)
    archive = source_archive(
        '[build-system]\nrequires = ["hatchling==1.0"]\n'
        'build-backend = "hatchling.build"\n'
    )

    def source_index(name: str, version: str) -> tuple[ArtifactCandidate, ...]:
        digest = HASH_B if name == "pytest" else HASH_A
        normalized = name.replace("-", "_")
        return (
            ArtifactCandidate(
                f"{normalized}-{version}-cp311-cp311-manylinux_2_17_x86_64.whl",
                digest,
            ),
            ArtifactCandidate(f"{normalized}-{version}.tar.gz", digest),
        )

    with pytest.raises(EnvironmentFailure) as raised:
        update_python_lock(
            tmp_path,
            resolver_runner=unchanged_resolver,
            artifact_index=source_index,
            artifact_reader=lambda _candidate: archive,
        )

    assert raised.value.code == "python_lock_source_build_unlocked"


def test_linux_arm64_selected_distributions_have_compatible_hashed_artifacts() -> None:
    contract = load_python_lock(
        ROOT,
        os_name="Linux",
        architecture="aarch64",
        python_version="3.11.0",
        profile="runtime",
    )

    assert set(contract.artifact_hashes) == set(contract.distributions)
    assert all(contract.artifact_hashes.values())
    assert contract.hash_count == sum(map(len, contract.artifact_hashes.values()))
    assert "openai" not in contract.direct_requirements
    assert contract.distributions["openai"] == frozenset({"2.46.0"})


def test_macos_x86_cryptography_source_backend_is_exact_locked() -> None:
    contract = load_python_lock(
        ROOT,
        os_name="Darwin",
        architecture="x86_64",
        python_version="3.11.0",
        profile="runtime",
    )

    assert contract.distributions["cryptography"] == frozenset({"49.0.0"})
    assert {"pip", "setuptools", "maturin"} <= contract.direct_requirements
    assert contract.build_requirements["maturin"] == "1.10.2"
    assert contract.build_requirements["setuptools"] == "82.0.1"
    assert contract.source_build_count >= 1


def test_linux_arm64_online_and_offline_projection_identities_are_equal(
    tmp_path: Path,
) -> None:
    write_lock_repository(tmp_path)

    online = load_python_lock(
        tmp_path,
        os_name="Linux",
        architecture="arm64",
        python_version="3.11.15",
        profile="runtime",
    )
    offline = load_python_lock(
        tmp_path,
        os_name="Linux",
        architecture="aarch64",
        python_version="3.11.15",
        profile="runtime",
    )

    assert online.projection_hash == offline.projection_hash
    assert online.distributions == offline.distributions
    assert online.artifact_hashes == offline.artifact_hashes


def test_linux_arm64_projection_contributes_to_canonical_lock_content_hash(
    tmp_path: Path,
) -> None:
    write_lock_repository(tmp_path)
    first = load_python_lock(
        tmp_path,
        os_name="Linux",
        architecture="aarch64",
        python_version="3.11.15",
        profile="runtime",
    )
    mutate_arm64_runtime_projection(
        tmp_path,
        lambda projection: projection["records"][0]["artifacts"][0].update(
            {"filename": "demo-1.0-py2.py3-none-any.whl"}
        ),
    )

    second = load_python_lock(
        tmp_path,
        os_name="Linux",
        architecture="aarch64",
        python_version="3.11.15",
        profile="runtime",
    )

    assert first.content_hash != second.content_hash
    assert first.projection_hash != second.projection_hash


def test_supported_target_matrix_change_requires_reviewed_lock_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_lock_repository(tmp_path)
    from scripts.environment import python_lock

    changed = (*python_lock.SUPPORTED_TARGETS, {**python_lock.SUPPORTED_TARGETS[-1]})
    monkeypatch.setattr(python_lock, "SUPPORTED_TARGETS", changed)

    with pytest.raises(EnvironmentFailure) as raised:
        check_python_lock(tmp_path, resolver_runner=resolver_identity)

    assert raised.value.code == "python_lock_target_drift"


def test_environment_evidence_reports_normalized_linux_arm64_target(
    tmp_path: Path,
) -> None:
    write_lock_repository(tmp_path)

    evidence = load_python_lock(
        tmp_path,
        os_name="Linux",
        architecture="arm64",
        python_version="3.11.15",
        profile="runtime",
    ).evidence()

    assert evidence["selectedTarget"] == target_identity(SUPPORTED_TARGETS[1])
    assert evidence["selectedProfile"] == "runtime"
    assert evidence["selectedProjection"] == "linux-aarch64-cpython311-runtime"
