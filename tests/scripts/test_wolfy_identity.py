from __future__ import annotations

from dataclasses import replace
import subprocess
from pathlib import Path

import pytest

from scripts.environment.identity import ToolchainIdentity, calculate_environment_identity, detect_toolchain


@pytest.fixture
def dependency_repo(tmp_path: Path) -> Path:
    (tmp_path / "apps" / "dsa-web").mkdir(parents=True)
    (tmp_path / "requirements.txt").write_text("runtime-package==1.0\n", encoding="utf-8")
    (tmp_path / "requirements-dev.txt").write_text("-r requirements.txt\npytest==8.0\n", encoding="utf-8")
    for name in (
        "requirements-lock.json",
        "requirements-python311-runtime.lock",
        "requirements-python311-dev.lock",
        "requirements-python312-runtime.lock",
        "requirements-python312-dev.lock",
    ):
        (tmp_path / name).write_text(f"{name}\n", encoding="utf-8")
    (tmp_path / "apps" / "dsa-web" / "package.json").write_text(
        '{"name":"fixture","devDependencies":{"vite":"1.0.0"}}\n', encoding="utf-8"
    )
    (tmp_path / "apps" / "dsa-web" / "package-lock.json").write_text(
        '{"name":"fixture","lockfileVersion":3,"packages":{}}\n', encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def toolchain() -> ToolchainIdentity:
    return ToolchainIdentity(
        os_name="Darwin",
        architecture="arm64",
        python_implementation="CPython",
        python_version="3.11.15",
        node_version="20.20.2",
        npm_version="10.8.2",
        install_mode="pip-requirements+npm-ci",
    )


def test_identical_manifests_and_toolchains_produce_identical_fingerprints(
    dependency_repo: Path, toolchain: ToolchainIdentity
) -> None:
    first = calculate_environment_identity(dependency_repo, toolchain)
    second = calculate_environment_identity(dependency_repo, toolchain)

    assert first == second
    assert set(first.manifest_hashes) == {
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-lock.json",
        "requirements-python311-runtime.lock",
        "requirements-python311-dev.lock",
        "requirements-python312-runtime.lock",
        "requirements-python312-dev.lock",
        "apps/dsa-web/package.json",
        "apps/dsa-web/package-lock.json",
    }


def test_lockfile_content_change_produces_new_web_and_combined_fingerprints(
    dependency_repo: Path, toolchain: ToolchainIdentity
) -> None:
    before = calculate_environment_identity(dependency_repo, toolchain)
    lock = dependency_repo / "apps" / "dsa-web" / "package-lock.json"
    lock.write_text(lock.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    after = calculate_environment_identity(dependency_repo, toolchain)

    assert after.python_input_fingerprint == before.python_input_fingerprint
    assert after.web_input_fingerprint != before.web_input_fingerprint
    assert after.combined_input_fingerprint != before.combined_input_fingerprint


def test_python_lock_content_change_produces_new_python_and_combined_fingerprints(
    dependency_repo: Path, toolchain: ToolchainIdentity
) -> None:
    before = calculate_environment_identity(dependency_repo, toolchain)
    lock = dependency_repo / "requirements-python311-dev.lock"
    lock.write_text(lock.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")
    after = calculate_environment_identity(dependency_repo, toolchain)

    assert after.python_input_fingerprint != before.python_input_fingerprint
    assert after.web_input_fingerprint == before.web_input_fingerprint
    assert after.combined_input_fingerprint != before.combined_input_fingerprint


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("os_name", "Linux"),
        ("architecture", "x86_64"),
        ("python_implementation", "PyPy"),
        ("python_version", "3.11.14"),
        ("node_version", "20.20.1"),
        ("npm_version", "10.8.1"),
    ],
)
def test_platform_or_toolchain_change_produces_new_environment_fingerprint(
    dependency_repo: Path,
    toolchain: ToolchainIdentity,
    field: str,
    value: str,
) -> None:
    before = calculate_environment_identity(dependency_repo, toolchain)
    after = calculate_environment_identity(dependency_repo, replace(toolchain, **{field: value}))

    assert after.combined_input_fingerprint != before.combined_input_fingerprint


def test_missing_authoritative_python_input_fails_closed(
    dependency_repo: Path, toolchain: ToolchainIdentity
) -> None:
    (dependency_repo / "requirements-dev.txt").unlink()

    with pytest.raises(ValueError, match="requirements-dev.txt"):
        calculate_environment_identity(dependency_repo, toolchain)


def test_toolchain_detection_strips_node_and_npm_execution_modifiers(monkeypatch: pytest.MonkeyPatch) -> None:
    environments: list[dict[str, str]] = []

    def runner(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        environments.append(kwargs["env"])
        output = "v20.20.2\n" if command[-2:] == ["node", "--version"] else "10.8.2\n"
        return subprocess.CompletedProcess(command, 0, output, "")

    monkeypatch.setenv("NODE_OPTIONS", "--require /tmp/untrusted-hook.js")
    monkeypatch.setenv("npm_config_registry", "https://registry.example.invalid")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example.invalid")
    monkeypatch.setattr("scripts.environment.identity.subprocess.run", runner)

    identity = detect_toolchain()

    assert identity.node_version == "20.20.2"
    assert identity.npm_version == "10.8.2"
    for environment in environments:
        assert "NODE_OPTIONS" not in environment
        assert "npm_config_registry" not in environment
        assert "HTTPS_PROXY" not in environment
        assert environment["npm_config_userconfig"] != environment["npm_config_globalconfig"]
        assert environment["npm_config_userconfig"].endswith("user.npmrc")
