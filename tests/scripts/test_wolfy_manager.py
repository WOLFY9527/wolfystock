from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.environment.errors import EnvironmentFailure
from scripts.environment.manager import (
    EnvironmentManager,
    build_environment_evidence,
    combined_environment_fingerprint,
    link_worktree_environment,
    require_managed_python,
)
from scripts.environment.identity import ToolchainIdentity
from scripts.environment.snapshots import SnapshotResult
from scripts.environment.runtime import create_run_context
from tests.scripts.test_wolfy_python_lock import write_lock_repository


def snapshot(cache_root: Path, component: str, input_id: str, installed_id: str) -> SnapshotResult:
    path = cache_root / "snapshots" / component / input_id / installed_id
    path.mkdir(parents=True)
    (path / "provenance.json").write_text("{}\n", encoding="utf-8")
    if component == "web":
        (path / "node_modules").mkdir()
        (path / "node_modules" / "fixture.txt").write_text("web snapshot\n", encoding="utf-8")
    return SnapshotResult(
        component=component,
        path=path,
        input_fingerprint=input_id,
        installed_fingerprint=installed_id,
        network_used=False,
        reused=True,
    )


def tool_snapshots(cache_root: Path) -> tuple[SnapshotResult, SnapshotResult]:
    browser = snapshot(cache_root, "browser", "e" * 64, "f" * 64)
    rg = snapshot(cache_root, "tool-rg", "1" * 64, "2" * 64)
    return browser, rg


def make_root(tmp_path: Path) -> Path:
    root = tmp_path / "worktree"
    (root / "apps" / "dsa-web").mkdir(parents=True)
    return root


def make_dependency_root(tmp_path: Path) -> Path:
    root = make_root(tmp_path)
    write_lock_repository(root)
    (root / "apps" / "dsa-web" / "package.json").write_text('{"name":"fixture"}\n', encoding="utf-8")
    (root / "apps" / "dsa-web" / "package-lock.json").write_text(
        '{"name":"fixture","lockfileVersion":3,"packages":{}}\n', encoding="utf-8"
    )
    return root


def fixture_toolchain() -> ToolchainIdentity:
    return ToolchainIdentity("Darwin", "arm64", "CPython", "3.11.15", "20.20.2", "10.8.2", "fixture")


def test_linux_arm64_manager_selects_normalized_runtime_projection(
    tmp_path: Path,
) -> None:
    root = make_dependency_root(tmp_path)
    arm64 = ToolchainIdentity(
        "Linux", "arm64", "CPython", "3.11.15", "20.20.2", "10.8.2", "fixture"
    )
    aarch64 = ToolchainIdentity(
        "Linux", "aarch64", "CPython", "3.11.15", "20.20.2", "10.8.2", "fixture"
    )

    first = EnvironmentManager(root, cache_root=tmp_path / "cache-one", toolchain=arm64)
    second = EnvironmentManager(root, cache_root=tmp_path / "cache-two", toolchain=aarch64)

    assert first.python_lock.profile == second.python_lock.profile == "runtime"
    assert first.python_lock.target == second.python_lock.target
    assert first.python_lock.target["architecture"] == "aarch64"
    assert first.python_lock.projection_hash == second.python_lock.projection_hash


def test_migration_replaces_legacy_dependencies_only_after_snapshots_exist(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    cache_root = tmp_path / "cache"
    python = snapshot(cache_root, "python", "a" * 64, "b" * 64)
    web = snapshot(cache_root, "web", "c" * 64, "d" * 64)
    browser, rg = tool_snapshots(cache_root)
    (root / ".venv").mkdir()
    (root / ".venv" / "legacy.txt").write_text("usable legacy", encoding="utf-8")
    (root / "apps" / "dsa-web" / "node_modules").mkdir()

    pointer = link_worktree_environment(
        root, cache_root, python, web, browser, rg, combined_fingerprint="e" * 64
    )

    assert (root / ".venv").resolve() == python.path
    assert (root / "apps" / "dsa-web" / "node_modules").resolve() == web.path / "node_modules"
    assert any(path.name.startswith("python-") for path in (cache_root / "legacy").iterdir())
    assert json.loads(pointer.read_text(encoding="utf-8"))["combinedFingerprint"] == "e" * 64


def test_missing_replacement_snapshot_leaves_legacy_environment_untouched(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    cache_root = tmp_path / "cache"
    python = SnapshotResult("python", tmp_path / "missing", "a" * 64, "b" * 64, False, True)
    web = snapshot(cache_root, "web", "c" * 64, "d" * 64)
    browser, rg = tool_snapshots(cache_root)
    (root / ".venv").mkdir()
    marker = root / ".venv" / "legacy.txt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(EnvironmentFailure, match="replacement_snapshot_missing"):
        link_worktree_environment(
            root, cache_root, python, web, browser, rg, combined_fingerprint="e" * 64
        )

    assert marker.read_text(encoding="utf-8") == "keep"


def test_worktree_links_never_target_canonical_mutable_dependencies(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    canonical = tmp_path / "canonical"
    (canonical / ".venv").mkdir(parents=True)
    (canonical / "apps" / "dsa-web" / "node_modules").mkdir(parents=True)
    cache_root = tmp_path / "cache"
    python = snapshot(cache_root, "python", "a" * 64, "b" * 64)
    web = snapshot(cache_root, "web", "c" * 64, "d" * 64)
    browser, rg = tool_snapshots(cache_root)

    link_worktree_environment(
        root, cache_root, python, web, browser, rg, combined_fingerprint="e" * 64
    )
    shutil.rmtree(canonical)

    assert (root / ".venv" / "provenance.json").is_file()
    assert (root / "apps" / "dsa-web" / "node_modules" / "fixture.txt").is_file()
    assert ((root / "apps" / "dsa-web" / "node_modules").resolve().parent / "provenance.json").is_file()
    assert not (root / ".venv").resolve().is_relative_to(canonical)


def test_multiple_worktrees_share_snapshots_but_not_run_state(tmp_path: Path) -> None:
    first_root = make_root(tmp_path / "first")
    second_root = make_root(tmp_path / "second")
    cache_root = tmp_path / "cache"
    python = snapshot(cache_root, "python", "a" * 64, "b" * 64)
    web = snapshot(cache_root, "web", "c" * 64, "d" * 64)
    browser, rg = tool_snapshots(cache_root)

    link_worktree_environment(
        first_root, cache_root, python, web, browser, rg, combined_fingerprint="e" * 64
    )
    link_worktree_environment(
        second_root, cache_root, python, web, browser, rg, combined_fingerprint="e" * 64
    )
    first_run = create_run_context(cache_root, run_id="run-first-worktree")
    second_run = create_run_context(cache_root, run_id="run-second-worktree")

    assert (first_root / ".venv").resolve() == (second_root / ".venv").resolve() == python.path
    assert (first_root / "apps" / "dsa-web" / "node_modules").resolve() == web.path / "node_modules"
    assert (second_root / "apps" / "dsa-web" / "node_modules").resolve() == web.path / "node_modules"
    assert set(first_run.mutable_paths).isdisjoint(second_run.mutable_paths)


def test_wrong_active_python_cannot_qualify_managed_environment(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    managed = root / ".venv" / "bin" / "python"
    managed.parent.mkdir(parents=True)
    managed.write_text("", encoding="utf-8")

    with pytest.raises(EnvironmentFailure, match="wrong_managed_interpreter"):
        require_managed_python(root, executable=tmp_path / "wrong" / "python")


def test_environment_evidence_redacts_cache_paths_and_credentials(tmp_path: Path) -> None:
    private_cache = tmp_path / "Users" / "private-owner" / "cache"
    python = snapshot(private_cache, "python", "a" * 64, "b" * 64)
    web = snapshot(private_cache, "web", "c" * 64, "d" * 64)
    browser, rg = tool_snapshots(private_cache)
    browser_executable = browser.path / "chromium-1208" / "chrome-mac-arm64" / "chrome"
    browser_executable.parent.mkdir(parents=True)
    browser_executable.write_text("browser\n", encoding="utf-8")
    (rg.path / "rg").write_text("rg\n", encoding="utf-8")

    evidence = build_environment_evidence(
        combined_fingerprint="e" * 64,
        python=python,
        web=web,
        browser=browser,
        rg=rg,
        browser_identity={
            "browserVersion": "145.0.7632.6",
            "executable": "chromium-1208/chrome-mac-arm64/chrome",
            "executableSha256": "3" * 64,
            "family": "chromium",
            "launchVerified": True,
            "platform": "darwin-arm64",
            "playwrightVersion": "1.58.2",
            "revision": "1208",
        },
        rg_identity={
            "executable": "rg",
            "executableSha256": "4" * 64,
            "platform": "darwin-arm64",
            "version": "15.1.0",
        },
        manifest_hashes={"requirements.txt": "f" * 64},
        python_lock_evidence={
            "schemaVersion": "wolfystock_python_lock_v1",
            "contentHash": "1" * 64,
            "hashVerification": True,
        },
        toolchain={"pythonVersion": "3.11.15", "credential": "must-not-appear"},
        run_id="run-evidence",
        network_used=False,
        verified_at="2026-07-17T00:00:00Z",
    )
    encoded = json.dumps(evidence, sort_keys=True)

    assert str(tmp_path) not in encoded
    assert "private-owner" not in encoded
    assert "must-not-appear" not in encoded
    assert evidence["snapshots"]["python"].startswith("$CACHE/")
    assert evidence["browser"]["revision"] == "1208"
    assert evidence["browser"]["launchVerified"] is True
    assert evidence["browser"]["executable"].startswith("$CACHE/")
    assert evidence["managedTools"]["rg"]["executable"].startswith("$CACHE/")
    assert evidence["environmentIdentity"]["bootstrapImplementationVersion"] == "wolfystock_bootstrap_v7"
    assert evidence["pythonLock"]["contentHash"] == "1" * 64
    assert evidence["pythonLock"]["hashVerification"] is True


@pytest.mark.parametrize(
    ("component_name", "field", "replacement"),
    [
        ("python", "installedFingerprint", "f" * 64),
        ("web", "snapshot", "$CACHE/snapshots/web/wrong/snapshot"),
        ("browser", "installedFingerprint", "9" * 64),
        ("rg", "installedFingerprint", "8" * 64),
    ],
)
def test_verify_rejects_pointer_component_identity_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    component_name: str,
    field: str,
    replacement: str,
) -> None:
    root = make_dependency_root(tmp_path)
    cache_root = tmp_path / "cache"
    manager = EnvironmentManager(root, cache_root=cache_root, toolchain=fixture_toolchain())
    python = snapshot(cache_root, "python", manager.identity.python_input_fingerprint, "b" * 64)
    web = snapshot(cache_root, "web", manager.identity.web_input_fingerprint, "d" * 64)
    browser, rg = tool_snapshots(cache_root)
    combined = combined_environment_fingerprint(manager.identity, python, web, browser, rg)
    pointer_path = link_worktree_environment(
        root, cache_root, python, web, browser, rg, combined_fingerprint=combined
    )
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    pointer["components"][component_name][field] = replacement
    pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
    components = (
        SimpleNamespace(name="python", input_fingerprint=manager.identity.python_input_fingerprint),
        SimpleNamespace(name="web", input_fingerprint=manager.identity.web_input_fingerprint),
    )
    monkeypatch.setattr(manager, "_components", lambda: components)
    monkeypatch.setattr(
        manager,
        "_browser_component",
        lambda _web: SimpleNamespace(name="browser", input_fingerprint="e" * 64),
    )
    monkeypatch.setattr(
        manager,
        "_rg_component",
        lambda: SimpleNamespace(name="tool-rg", input_fingerprint="1" * 64),
    )
    monkeypatch.setattr(
        "scripts.environment.manager.verify_cached_snapshot",
        lambda path, _component: {"installedFingerprint": path.name},
    )

    with pytest.raises(EnvironmentFailure) as raised:
        manager.verify()
    assert raised.value.code == "worktree_pointer_mismatch"


@pytest.mark.skipif(os.name == "nt", reason="POSIX cache permissions")
def test_existing_environment_cache_permissions_are_restricted(tmp_path: Path) -> None:
    root = make_dependency_root(tmp_path)
    cache_root = tmp_path / "cache"
    cache_root.mkdir(mode=0o777)
    cache_root.chmod(0o777)

    EnvironmentManager(root, cache_root=cache_root, toolchain=fixture_toolchain())

    assert stat.S_IMODE(cache_root.stat().st_mode) == 0o700


def test_linking_environment_keeps_tracked_git_state_clean(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    (root / ".gitignore").write_text("/.venv\n/apps/dsa-web/node_modules\n/.wolfy/\n", encoding="utf-8")
    (root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "--initial-branch=main"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "-qm", "fixture"],
        cwd=root,
        check=True,
    )
    cache_root = tmp_path / "cache"
    python = snapshot(cache_root, "python", "a" * 64, "b" * 64)
    web = snapshot(cache_root, "web", "c" * 64, "d" * 64)
    browser, rg = tool_snapshots(cache_root)

    link_worktree_environment(
        root, cache_root, python, web, browser, rg, combined_fingerprint="e" * 64
    )

    status = subprocess.run(["git", "status", "--porcelain"], cwd=root, text=True, capture_output=True, check=True)
    assert status.stdout == ""
