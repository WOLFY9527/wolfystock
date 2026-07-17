from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.environment.components import PythonComponent, WebComponent, _normalize_distribution_records
from scripts.environment.errors import EnvironmentFailure
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
    component = PythonComponent(tmp_path, "a" * 64, TOOLCHAIN, command_runner=python_runner(snapshot, broken_import=True))

    with pytest.raises(EnvironmentFailure, match="python_critical_import_failed"):
        component.inspect(snapshot)


def test_python_metadata_change_is_detected_against_provenance(tmp_path: Path) -> None:
    snapshot = make_python_snapshot(tmp_path)
    component = PythonComponent(tmp_path, "a" * 64, TOOLCHAIN, command_runner=python_runner(snapshot))
    state = component.inspect(snapshot)
    manifest = {"installed": state}
    metadata = next(snapshot.glob("**/*.dist-info/METADATA"))
    metadata.write_text("Name: fixture\nVersion: 2.0\n", encoding="utf-8")

    with pytest.raises(EnvironmentFailure, match="python_installed_identity_mismatch"):
        component.verify(snapshot, manifest)


def test_python_installed_file_change_is_detected_against_provenance(tmp_path: Path) -> None:
    snapshot = make_python_snapshot(tmp_path)
    component = PythonComponent(tmp_path, "a" * 64, TOOLCHAIN, command_runner=python_runner(snapshot))
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
    component = PythonComponent(tmp_path, "a" * 64, TOOLCHAIN, command_runner=python_runner(temporary))

    component.prepare_promotion(temporary, final)

    assert str(temporary) not in activate.read_text(encoding="utf-8")
    assert temporary.name not in activate.read_text(encoding="utf-8")
    assert str(final) in activate.read_text(encoding="utf-8")
    assert str(final) in config.read_text(encoding="utf-8")


def test_offline_wheel_index_preserves_conflicting_cache_material(tmp_path: Path) -> None:
    cache = tmp_path / "pip-cache"
    first = cache / "wheels" / "one" / "fixture-1.0-py3-none-any.whl"
    second = cache / "wheels" / "two" / "fixture-1.0-py3-none-any.whl"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    destination = tmp_path / "build"
    destination.mkdir()

    def runner(command, **_kwargs):
        return completed(command, str(cache))

    component = PythonComponent(tmp_path, "a" * 64, TOOLCHAIN, command_runner=runner)

    arguments = component._offline_wheel_arguments(destination)
    index = destination / ".offline-wheels" / "index.html"
    content = index.read_text(encoding="utf-8")

    assert arguments == ["--find-links", index.as_uri()]
    assert first.as_uri() in content
    assert second.as_uri() in content


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
