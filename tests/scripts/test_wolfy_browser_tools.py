from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
from pathlib import Path

import pytest

from scripts.environment.browser import BrowserComponent, load_browser_contract
from scripts.environment.errors import EnvironmentFailure, OfflineMaterialUnavailable
from scripts.environment.identity import ToolchainIdentity
from scripts.environment.managed_tools import ManagedRgComponent
from scripts.environment.runtime import cleanup_run, create_run_context
from scripts.environment.snapshots import ensure_snapshot, sweep_interrupted_builds


TOOLCHAIN = ToolchainIdentity(
    os_name="Darwin",
    architecture="arm64",
    python_implementation="CPython",
    python_version="3.11.15",
    node_version="20.20.2",
    npm_version="10.8.2",
    install_mode="pip-hash-lock+npm-ci",
)


def completed(
    command: list[str], stdout: str = "", returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(command, returncode, stdout, "fixture error" if returncode else "")


def make_web_snapshot(tmp_path: Path, *, revision: str = "1208") -> Path:
    snapshot = tmp_path / "web-snapshot"
    core = snapshot / "node_modules" / "playwright-core"
    playwright = snapshot / "node_modules" / "playwright"
    core.mkdir(parents=True)
    playwright.mkdir(parents=True)
    (core / "package.json").write_text(json.dumps({"version": "1.58.2"}), encoding="utf-8")
    (core / "browsers.json").write_text(
        json.dumps(
            {
                "browsers": [
                    {
                        "name": "chromium",
                        "revision": revision,
                        "installByDefault": True,
                        "browserVersion": "145.0.7632.6",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (core / "cli.js").write_text("// fixture\n", encoding="utf-8")
    (playwright / "index.js").write_text("// fixture\n", encoding="utf-8")
    return snapshot


def make_browser_executable(snapshot: Path, *, revision: str = "1208") -> Path:
    executable = snapshot / f"chromium-{revision}" / "chrome-mac-arm64" / "chrome"
    executable.parent.mkdir(parents=True, exist_ok=True)
    if not executable.exists():
        executable.write_bytes(b"reviewed-chromium-executable")
        executable.chmod(0o700)
    return executable


def make_node_executable(tmp_path: Path) -> Path:
    executable = tmp_path / "managed" / "node"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text("node\n", encoding="utf-8")
    executable.chmod(0o700)
    return executable


def browser_runner(commands: list[list[str]]):
    def run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        browser_root = Path(kwargs["env"]["PLAYWRIGHT_BROWSERS_PATH"])
        if command[-2:] == ["install", "chromium"]:
            make_browser_executable(browser_root)
            return completed(command)
        executable = make_browser_executable(browser_root)
        return completed(
            command,
            json.dumps(
                {
                    "browserVersion": "145.0.7632.6",
                    "executablePath": str(executable),
                    "launchVerified": True,
                }
            ),
        )

    return run


def test_browser_contract_is_derived_from_reviewed_web_dependency_graph(tmp_path: Path) -> None:
    web_snapshot = make_web_snapshot(tmp_path)

    contract = load_browser_contract(web_snapshot, "a" * 64, TOOLCHAIN)

    assert contract.family == "chromium"
    assert contract.revision == "1208"
    assert contract.browser_version == "145.0.7632.6"
    assert contract.playwright_version == "1.58.2"
    assert contract.platform == "darwin-arm64"
    assert len(contract.input_fingerprint) == 64


def test_missing_browser_cannot_be_silently_skipped_offline(tmp_path: Path) -> None:
    component = BrowserComponent(
        make_web_snapshot(tmp_path),
        "a" * 64,
        TOOLCHAIN,
        node_executable=make_node_executable(tmp_path),
        command_runner=lambda command, **_kwargs: completed(command),
    )

    with pytest.raises(OfflineMaterialUnavailable) as raised:
        component.build(tmp_path / "browser", offline=True)

    assert raised.value.code == "offline_browser_snapshot_missing"


def test_online_browser_install_uses_reviewed_playwright_cli_and_launches_exact_revision(
    tmp_path: Path,
) -> None:
    commands: list[list[str]] = []
    web_snapshot = make_web_snapshot(tmp_path)
    destination = tmp_path / "browser"
    node_executable = make_node_executable(tmp_path)
    component = BrowserComponent(
        web_snapshot,
        "a" * 64,
        TOOLCHAIN,
        node_executable=node_executable,
        command_runner=browser_runner(commands),
    )

    component.build(destination, offline=False)
    installed = component.inspect(destination)

    assert commands[0] == [
        str(node_executable),
        str(web_snapshot / "node_modules" / "playwright-core" / "cli.js"),
        "install",
        "chromium",
    ]
    assert installed["family"] == "chromium"
    assert installed["revision"] == "1208"
    assert installed["platform"] == "darwin-arm64"
    assert installed["browserVersion"] == "145.0.7632.6"
    assert installed["launchVerified"] is True
    assert installed["executable"] == "chromium-1208/chrome-mac-arm64/chrome"
    assert installed["executableSha256"] == hashlib.sha256(
        b"reviewed-chromium-executable"
    ).hexdigest()
    assert str(tmp_path) not in json.dumps(installed, sort_keys=True)


def test_browser_snapshot_rejects_wrong_revision_even_when_executable_launches(tmp_path: Path) -> None:
    destination = tmp_path / "browser"
    wrong = make_browser_executable(destination, revision="1207")
    component = BrowserComponent(
        make_web_snapshot(tmp_path),
        "a" * 64,
        TOOLCHAIN,
        node_executable=make_node_executable(tmp_path),
        command_runner=lambda command, **_kwargs: completed(
            command,
            json.dumps(
                {
                    "browserVersion": "145.0.7632.6",
                    "executablePath": str(wrong),
                    "launchVerified": True,
                }
            ),
        ),
    )

    with pytest.raises(EnvironmentFailure) as raised:
        component.inspect(destination)

    assert raised.value.code == "browser_revision_mismatch"


def test_concurrent_browser_provisioning_builds_once_and_survives_interrupted_staging(
    tmp_path: Path,
) -> None:
    web_snapshot = make_web_snapshot(tmp_path)
    started = threading.Event()
    release = threading.Event()
    install_count = 0

    def runner(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        nonlocal install_count
        root = Path(kwargs["env"]["PLAYWRIGHT_BROWSERS_PATH"])
        if command[-2:] == ["install", "chromium"]:
            install_count += 1
            started.set()
            assert release.wait(timeout=5)
            make_browser_executable(root)
            return completed(command)
        executable = make_browser_executable(root)
        return completed(
            command,
            json.dumps(
                {
                    "browserVersion": "145.0.7632.6",
                    "executablePath": str(executable),
                    "launchVerified": True,
                }
            ),
        )

    component = BrowserComponent(
        web_snapshot,
        "a" * 64,
        TOOLCHAIN,
        node_executable=make_node_executable(tmp_path),
        command_runner=runner,
    )
    input_root = tmp_path / "snapshots" / "browser" / component.input_fingerprint
    interrupted = input_root / ".build-interrupted"
    interrupted.mkdir(parents=True)
    old = time.time() - 7200
    os.utime(interrupted, (old, old))
    assert sweep_interrupted_builds(
        tmp_path, "browser", component.input_fingerprint, older_than_seconds=60
    ) == 1
    results: list[Path] = []

    def ensure() -> None:
        results.append(
            ensure_snapshot(tmp_path, component, offline=False, lock_timeout=5).path
        )

    first = threading.Thread(target=ensure)
    second = threading.Thread(target=ensure)
    first.start()
    assert started.wait(timeout=2)
    second.start()
    release.set()
    first.join(timeout=5)
    second.join(timeout=5)

    assert install_count == 1
    assert len(results) == 2
    assert results[0] == results[1]
    assert results[0].is_dir()
    context = create_run_context(tmp_path, run_id="run-browser-cleanup")
    cleanup_run(context, success=True)
    assert results[0].is_dir()


def test_rg_is_copied_to_managed_snapshot_and_verified_by_content_identity(tmp_path: Path) -> None:
    host_rg = tmp_path / "host" / "rg"
    host_rg.parent.mkdir()
    host_rg.write_bytes(b"reviewed-rg-executable")
    host_rg.chmod(0o700)
    component = ManagedRgComponent(
        TOOLCHAIN,
        source_resolver=lambda _name: str(host_rg),
        command_runner=lambda command, **_kwargs: completed(command, "ripgrep 15.1.0\n"),
    )
    destination = tmp_path / "managed-rg"

    component.build(destination, offline=True)
    installed = component.inspect(destination)

    assert (destination / "rg").read_bytes() == b"reviewed-rg-executable"
    assert installed == {
        "executable": "rg",
        "executableSha256": hashlib.sha256(b"reviewed-rg-executable").hexdigest(),
        "platform": "darwin-arm64",
        "version": "15.1.0",
    }
    manifest = {"installed": installed}
    (destination / "rg").write_bytes(b"tampered")
    with pytest.raises(EnvironmentFailure) as raised:
        component.verify(destination, manifest)
    assert raised.value.code == "managed_rg_identity_mismatch"
