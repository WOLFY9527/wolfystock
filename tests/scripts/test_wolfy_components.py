from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.environment.components import PythonComponent, WebComponent, _normalize_distribution_records
from scripts.environment.errors import EnvironmentFailure, OfflineMaterialUnavailable
from scripts.environment.identity import ToolchainIdentity


TOOLCHAIN = ToolchainIdentity(
    os_name="Darwin",
    architecture="arm64",
    python_implementation="CPython",
    python_version="3.11.15",
    node_version="20.20.2",
    npm_version="10.8.2",
    install_mode="pip-requirements+npm-ci",
)


def completed(command: list[str], stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(command, returncode, stdout, "fixture error" if returncode else "")


def lock_contract(tmp_path: Path, *, version: str = "1.0") -> SimpleNamespace:
    path = tmp_path / "requirements-python311-dev.lock"
    path.write_text(f"fixture=={version} --hash=sha256:{'a' * 64}\n", encoding="utf-8")
    return SimpleNamespace(
        lock_path=path,
        distributions={"fixture": frozenset({version})},
        hash_verification=True,
        artifact_hashes={"fixture": frozenset({"a" * 64})},
        artifact_files={"fixture-1.0-py3-none-any.whl": "a" * 64},
        build_requirements={},
        content_hash="c" * 64,
        profile="development",
        target={
            "architecture": "arm64",
            "implementation": "CPython",
            "os": "Darwin",
            "pythonVersion": "3.11",
        },
    )


def make_python_snapshot(tmp_path: Path) -> Path:
    snapshot = tmp_path / "python-snapshot"
    python = snapshot / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_bytes(b"fixture-python")
    metadata = snapshot / "lib" / "python3.11" / "site-packages" / "fixture-1.0.dist-info"
    metadata.mkdir(parents=True)
    (metadata / "METADATA").write_text("Name: fixture\nVersion: 1.0\n", encoding="utf-8")
    (metadata / "RECORD").write_text("fixture.py,,\n", encoding="utf-8")
    (metadata.parent / "fixture.py").write_text("VALUE = 1\n", encoding="utf-8")
    return snapshot


def python_runner(snapshot: Path, *, broken_import: bool = False):
    def run(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        if "-I" in command:
            assert "-B" in command
        if command[-2:] == ["-m", "pip"]:
            raise AssertionError("unexpected incomplete pip command")
        if "check" in command:
            return completed(command, "No broken requirements found.\n")
        if "list" in command:
            return completed(command, '[{"name":"fixture","version":"1.0"}]\n')
        probe = {
            "implementation": "CPython",
            "version": "3.11.15",
            "prefix": str(snapshot),
            "basePrefix": "/bootstrap",
            "imports": {"fastapi": not broken_import, "pytest": True, "sqlalchemy": True},
        }
        return completed(command, json.dumps(probe))

    return run


def test_broken_python_import_is_detected(tmp_path: Path) -> None:
    snapshot = make_python_snapshot(tmp_path)
    component = PythonComponent(
        tmp_path,
        "a" * 64,
        TOOLCHAIN,
        lock_contract=lock_contract(tmp_path),
        artifact_cache_root=tmp_path / "artifact-cache",
        command_runner=python_runner(snapshot, broken_import=True),
    )

    with pytest.raises(EnvironmentFailure, match="python_critical_import_failed"):
        component.inspect(snapshot)


def test_python_metadata_change_is_detected_against_provenance(tmp_path: Path) -> None:
    snapshot = make_python_snapshot(tmp_path)
    component = PythonComponent(
        tmp_path,
        "a" * 64,
        TOOLCHAIN,
        lock_contract=lock_contract(tmp_path),
        artifact_cache_root=tmp_path / "artifact-cache",
        command_runner=python_runner(snapshot),
    )
    state = component.inspect(snapshot)
    manifest = {"installed": state}
    metadata = next(snapshot.glob("**/*.dist-info/METADATA"))
    metadata.write_text("Name: fixture\nVersion: 2.0\n", encoding="utf-8")

    with pytest.raises(EnvironmentFailure, match="python_installed_identity_mismatch"):
        component.verify(snapshot, manifest)


def test_python_installed_file_change_is_detected_against_provenance(tmp_path: Path) -> None:
    snapshot = make_python_snapshot(tmp_path)
    component = PythonComponent(
        tmp_path,
        "a" * 64,
        TOOLCHAIN,
        lock_contract=lock_contract(tmp_path),
        artifact_cache_root=tmp_path / "artifact-cache",
        command_runner=python_runner(snapshot),
    )
    manifest = {"installed": component.inspect(snapshot)}
    installed_file = next(snapshot.glob("**/site-packages/fixture.py"))
    installed_file.write_text("VALUE = 2\n", encoding="utf-8")

    with pytest.raises(EnvironmentFailure, match="python_installed_identity_mismatch"):
        component.verify(snapshot, manifest)


def test_python_record_normalization_removes_temporary_console_script_hashes(tmp_path: Path) -> None:
    snapshot = make_python_snapshot(tmp_path)
    record = next(snapshot.glob("**/*.dist-info/RECORD"))
    record.write_text(
        "../../../bin/fixture,sha256=random-build-path-hash,123\nfixture.py,sha256=stable,10\n",
        encoding="utf-8",
    )

    _normalize_distribution_records(snapshot)

    assert record.read_text(encoding="utf-8") == (
        "../../../bin/fixture,,\nfixture.py,sha256=stable,10\n"
    )


def test_python_promotion_rewrites_full_prefix_and_prompt_identity(tmp_path: Path) -> None:
    temporary = make_python_snapshot(tmp_path)
    temporary = temporary.rename(tmp_path / ".build-fixture")
    final = tmp_path / ("f" * 64)
    activate = temporary / "bin" / "activate"
    activate.write_text(f"VIRTUAL_ENV={temporary}\nPROMPT=({temporary.name})\n", encoding="utf-8")
    config = temporary / "pyvenv.cfg"
    config.write_text(f"command = python -m venv {temporary}\n", encoding="utf-8")
    component = PythonComponent(
        tmp_path,
        "a" * 64,
        TOOLCHAIN,
        lock_contract=lock_contract(tmp_path),
        artifact_cache_root=tmp_path / "artifact-cache",
        command_runner=python_runner(temporary),
    )

    component.prepare_promotion(temporary, final)

    assert str(temporary) not in activate.read_text(encoding="utf-8")
    assert temporary.name not in activate.read_text(encoding="utf-8")
    assert str(final) in activate.read_text(encoding="utf-8")
    assert str(final) in config.read_text(encoding="utf-8")


def test_offline_wheel_index_preserves_conflicting_cache_material(tmp_path: Path) -> None:
    cache = tmp_path / "artifact-cache"
    contract = lock_contract(tmp_path)
    component = PythonComponent(
        tmp_path,
        "a" * 64,
        TOOLCHAIN,
        lock_contract=contract,
        artifact_cache_root=cache,
        command_runner=lambda command, **_kwargs: completed(command),
    )

    directory = component._artifact_directory()
    arguments = component._locked_artifact_arguments()

    assert directory == cache / ("c" * 64) / "darwin-arm64-cpython311-development"
    assert arguments == ["--no-index", "--find-links", str(directory)]


@pytest.mark.parametrize("offline", [False, True])
def test_python_build_installs_only_from_selected_hashed_lock(tmp_path: Path, offline: bool) -> None:
    destination = tmp_path / "snapshot"
    cache = tmp_path / "artifact-cache"
    contract = lock_contract(tmp_path)
    commands: list[list[str]] = []

    def runner(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[:4] == [sys.executable, "-I", "-B", "-m"] and "venv" in command:
            python = destination / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_bytes(b"fixture-python")
            (destination / "lib" / "python3.11" / "site-packages").mkdir(parents=True)
        if command[-3:] == ["pip", "cache", "dir"]:
            return completed(command, str(cache))
        return completed(command)

    component = PythonComponent(
        tmp_path,
        "a" * 64,
        TOOLCHAIN,
        lock_contract=contract,
        artifact_cache_root=cache,
        command_runner=runner,
    )
    before = contract.lock_path.read_bytes()

    component.build(destination, offline=offline)

    install = next(command for command in commands if "install" in command)
    downloads = [command for command in commands if "download" in command]
    assert "--require-hashes" in install
    assert "--no-deps" in install
    assert "--no-index" in install
    assert "--find-links" in install
    assert install[install.index("-r") + 1] == str(contract.lock_path)
    assert len(downloads) == (0 if offline else 1)
    if downloads:
        assert "--require-hashes" in downloads[0]
        assert "--no-deps" in downloads[0]
        assert downloads[0][downloads[0].index("-r") + 1] == str(contract.lock_path)
    assert "requirements.txt" not in " ".join(install)
    assert "requirements-dev.txt" not in " ".join(install)
    assert contract.lock_path.read_bytes() == before


def test_python_installed_distribution_must_match_selected_lock(tmp_path: Path) -> None:
    snapshot = make_python_snapshot(tmp_path)

    def runner(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        if "check" in command:
            return completed(command, "No broken requirements found.\n")
        if "list" in command:
            return completed(command, '[{"name":"fixture","version":"2.0"}]\n')
        return python_runner(snapshot)(command)

    component = PythonComponent(
        tmp_path,
        "a" * 64,
        TOOLCHAIN,
        lock_contract=lock_contract(tmp_path),
        artifact_cache_root=tmp_path / "artifact-cache",
        command_runner=runner,
    )

    with pytest.raises(EnvironmentFailure) as raised:
        component.inspect(snapshot)

    assert raised.value.code == "python_locked_distribution_mismatch"


@pytest.mark.parametrize("offline", [False, True])
def test_python_artifact_hash_mismatch_is_never_retried_as_resolution(
    tmp_path: Path, offline: bool
) -> None:
    destination = tmp_path / "snapshot"
    cache = tmp_path / "artifact-cache"

    def runner(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        if "venv" in command:
            python = destination / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_bytes(b"fixture-python")
            (destination / "lib" / "python3.11" / "site-packages").mkdir(parents=True)
            return completed(command)
        if command[-3:] == ["pip", "cache", "dir"]:
            return completed(command, str(cache))
        return subprocess.CompletedProcess(
            command,
            1,
            "",
            "THESE PACKAGES DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE",
        )

    component = PythonComponent(
        tmp_path,
        "a" * 64,
        TOOLCHAIN,
        lock_contract=lock_contract(tmp_path),
        artifact_cache_root=cache,
        command_runner=runner,
    )

    with pytest.raises(EnvironmentFailure) as raised:
        component.build(destination, offline=offline)

    assert raised.value.code == "python_locked_artifact_hash_mismatch"


def test_missing_offline_locked_artifact_has_bounded_reason(tmp_path: Path) -> None:
    destination = tmp_path / "snapshot"
    cache = tmp_path / "artifact-cache"

    def runner(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        if "venv" in command:
            python = destination / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_bytes(b"fixture-python")
            return completed(command)
        if command[-3:] == ["pip", "cache", "dir"]:
            return completed(command, str(cache))
        return subprocess.CompletedProcess(
            command,
            1,
            "",
            "No matching distribution found for fixture==1.0",
        )

    component = PythonComponent(
        tmp_path,
        "a" * 64,
        TOOLCHAIN,
        lock_contract=lock_contract(tmp_path),
        artifact_cache_root=cache,
        command_runner=runner,
    )

    with pytest.raises(OfflineMaterialUnavailable) as raised:
        component.build(destination, offline=True)

    assert raised.value.code == "offline_python_locked_artifact_missing"


def test_locked_setuptools_is_installed_before_source_builds(tmp_path: Path) -> None:
    destination = tmp_path / "snapshot"
    cache = tmp_path / "artifact-cache"
    contract = lock_contract(tmp_path)
    contract.distributions = {
        **contract.distributions,
        "setuptools": frozenset({"82.0.1"}),
    }
    contract.artifact_hashes = {
        **contract.artifact_hashes,
        "setuptools": frozenset({"b" * 64}),
    }
    contract.artifact_files = {
        **contract.artifact_files,
        "setuptools-82.0.1-py3-none-any.whl": "b" * 64,
    }
    contract.build_requirements = {"setuptools": "82.0.1"}
    commands: list[list[str]] = []
    backend_requirements = ""

    def runner(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        nonlocal backend_requirements
        commands.append(command)
        if "venv" in command:
            python = destination / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_bytes(b"fixture-python")
            (destination / "lib" / "python3.11" / "site-packages").mkdir(parents=True)
        if "install" in command and "-r" in command:
            requirements = Path(command[command.index("-r") + 1])
            if requirements != contract.lock_path:
                backend_requirements = requirements.read_text(encoding="utf-8")
        return completed(command)

    component = PythonComponent(
        tmp_path,
        "a" * 64,
        TOOLCHAIN,
        lock_contract=contract,
        artifact_cache_root=cache,
        command_runner=runner,
    )

    component.build(destination, offline=True)

    backend = next(
        command
        for command in commands
        if "install" in command
        and "-r" in command
        and Path(command[command.index("-r") + 1]) != contract.lock_path
    )
    install = next(
        command
        for command in commands
        if "install" in command
        and "-r" in command
        and Path(command[command.index("-r") + 1]) == contract.lock_path
    )
    assert commands.index(backend) < commands.index(install)
    assert backend_requirements == (
        f"setuptools==82.0.1 \\\n    --hash=sha256:{'b' * 64}\n"
    )
    assert "--no-deps" in backend
    assert "--require-hashes" in backend
    assert "--no-build-isolation" in backend
    assert "--no-build-isolation" in install


def test_locked_source_build_uses_managed_scripts_on_path(tmp_path: Path) -> None:
    destination = tmp_path / "snapshot"
    contract = lock_contract(tmp_path)
    install_path = ""

    def runner(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        nonlocal install_path
        if "venv" in command:
            python = destination / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_bytes(b"fixture-python")
            (destination / "lib" / "python3.11" / "site-packages").mkdir(parents=True)
        if "-r" in command:
            install_path = kwargs["env"]["PATH"]
        return completed(command)

    component = PythonComponent(
        tmp_path,
        "a" * 64,
        TOOLCHAIN,
        lock_contract=contract,
        artifact_cache_root=tmp_path / "artifact-cache",
        command_runner=runner,
    )

    component.build(destination, offline=True)

    assert install_path.split(os.pathsep, maxsplit=1)[0] == str(destination / "bin")


def test_tampered_cached_artifact_is_rejected_before_install(tmp_path: Path) -> None:
    destination = tmp_path / "snapshot"
    cache = tmp_path / "artifact-cache"
    contract = lock_contract(tmp_path)

    def runner(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        if "venv" in command:
            python = destination / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_bytes(b"fixture-python")
            (destination / "lib" / "python3.11" / "site-packages").mkdir(parents=True)
        return completed(command)

    component = PythonComponent(
        tmp_path,
        "a" * 64,
        TOOLCHAIN,
        lock_contract=contract,
        artifact_cache_root=cache,
        command_runner=runner,
    )
    directory = component._artifact_directory()
    directory.mkdir(parents=True)
    artifact = directory / "fixture-1.0-py3-none-any.whl"
    artifact.write_bytes(b"tampered")
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() not in contract.artifact_hashes["fixture"]

    with pytest.raises(EnvironmentFailure) as raised:
        component.build(destination, offline=True)

    assert raised.value.code == "python_locked_artifact_hash_mismatch"


def test_missing_offline_build_backend_is_an_artifact_miss(tmp_path: Path) -> None:
    destination = tmp_path / "snapshot"
    contract = lock_contract(tmp_path)
    contract.distributions = {
        **contract.distributions,
        "setuptools": frozenset({"82.0.1"}),
    }
    contract.artifact_hashes = {
        **contract.artifact_hashes,
        "setuptools": frozenset({"b" * 64}),
    }
    contract.artifact_files = {
        **contract.artifact_files,
        "setuptools-82.0.1-py3-none-any.whl": "b" * 64,
    }
    contract.build_requirements = {"setuptools": "82.0.1"}

    def runner(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        if "venv" in command:
            python = destination / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_bytes(b"fixture-python")
            return completed(command)
        if (
            "install" in command
            and "-r" in command
            and Path(command[command.index("-r") + 1]) != contract.lock_path
        ):
            return subprocess.CompletedProcess(command, 1, "", "No matching distribution found")
        return completed(command)

    component = PythonComponent(
        tmp_path,
        "a" * 64,
        TOOLCHAIN,
        lock_contract=contract,
        artifact_cache_root=tmp_path / "artifact-cache",
        command_runner=runner,
    )

    with pytest.raises(OfflineMaterialUnavailable) as raised:
        component.build(destination, offline=True)

    assert raised.value.code == "offline_python_locked_artifact_missing"


def make_web_repo(tmp_path: Path) -> tuple[Path, Path]:
    web = tmp_path / "apps" / "dsa-web"
    web.mkdir(parents=True)
    lock = {
        "name": "fixture",
        "lockfileVersion": 3,
        "packages": {
            "": {"name": "fixture"},
            "node_modules/vite": {"version": "7.0.0"},
            "node_modules/rollup": {"version": "4.0.0"},
        },
    }
    (web / "package-lock.json").write_text(json.dumps(lock), encoding="utf-8")
    (web / "package.json").write_text('{"name":"fixture"}', encoding="utf-8")
    snapshot = tmp_path / "web-snapshot"
    (snapshot / "node_modules").mkdir(parents=True)
    (snapshot / "package-lock.json").write_text(json.dumps(lock), encoding="utf-8")
    (snapshot / "package.json").write_text('{"name":"fixture"}', encoding="utf-8")
    for name, version in (("vite", "7.0.0"), ("rollup", "4.0.0")):
        package = snapshot / "node_modules" / name
        package.mkdir(parents=True)
        (package / "package.json").write_text(json.dumps({"name": name, "version": version}), encoding="utf-8")
        (package / "index.js").write_text(f"export const version = '{version}'\n", encoding="utf-8")
    return tmp_path, snapshot


def test_missing_transitive_web_dependency_is_detected(tmp_path: Path) -> None:
    root, snapshot = make_web_repo(tmp_path)
    (snapshot / "node_modules" / "rollup" / "package.json").unlink()
    component = WebComponent(
        root,
        "b" * 64,
        TOOLCHAIN,
        command_runner=lambda command, **_kwargs: completed(command, '{"dependencies":{}}'),
    )

    with pytest.raises(EnvironmentFailure, match="web_dependency_missing:node_modules/rollup"):
        component.inspect(snapshot)


def test_web_dependency_tree_command_failure_is_rejected(tmp_path: Path) -> None:
    root, snapshot = make_web_repo(tmp_path)
    component = WebComponent(
        root,
        "b" * 64,
        TOOLCHAIN,
        command_runner=lambda command, **_kwargs: completed(command, returncode=1),
    )

    with pytest.raises(EnvironmentFailure, match="web_dependency_tree_invalid"):
        component.inspect(snapshot)


def test_web_installed_file_change_is_detected_against_provenance(tmp_path: Path) -> None:
    root, snapshot = make_web_repo(tmp_path)
    component = WebComponent(
        root,
        "b" * 64,
        TOOLCHAIN,
        command_runner=lambda command, **_kwargs: completed(command, '{"dependencies":{}}'),
    )
    manifest = {"installed": component.inspect(snapshot)}
    (snapshot / "node_modules" / "vite" / "index.js").write_text("corrupt\n", encoding="utf-8")

    with pytest.raises(EnvironmentFailure, match="web_installed_identity_mismatch"):
        component.verify(snapshot, manifest)
