from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "bootstrap_worktree.sh"
CORE_PATH = REPO_ROOT / "scripts" / "worktree_preflight.py"
POWERSHELL_PATH = REPO_ROOT / "scripts" / "bootstrap_worktree.ps1"


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def git_output(*args: str, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


@pytest.fixture
def worktree_fixture(tmp_path: Path) -> tuple[Path, Path]:
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    git("init", "--initial-branch=main", cwd=canonical)
    git("config", "user.name", "Bootstrap Test", cwd=canonical)
    git("config", "user.email", "bootstrap@example.test", cwd=canonical)

    (canonical / "scripts").mkdir()
    shutil.copy2(SCRIPT_PATH, canonical / "scripts" / "bootstrap_worktree.sh")
    shutil.copy2(CORE_PATH, canonical / "scripts" / "worktree_preflight.py")
    (canonical / "apps" / "dsa-web").mkdir(parents=True)
    (canonical / "requirements.txt").write_text("fixture-package==1.0\n", encoding="utf-8")
    (canonical / "apps" / "dsa-web" / "package.json").write_text(
        '{"name":"fixture-web","version":"1.0.0","dependencies":{"echarts":"^6.1.0"}}\n',
        encoding="utf-8",
    )
    (canonical / "apps" / "dsa-web" / "package-lock.json").write_text(
        '{"name":"fixture-web","lockfileVersion":3,"packages":{"":{"name":"fixture-web","version":"1.0.0","dependencies":{"echarts":"^6.1.0"}},"node_modules/echarts":{"version":"6.1.0","integrity":"sha512-fixture"}}}\n',
        encoding="utf-8",
    )
    (canonical / "README.md").write_text("fixture\n", encoding="utf-8")
    (canonical / ".gitattributes").write_text("*.sh text eol=lf\n", encoding="utf-8")
    git("add", ".", cwd=canonical)
    git("commit", "-m", "fixture", cwd=canonical)

    linked = tmp_path / "linked"
    git("worktree", "add", "-b", "fixture-linked", str(linked), "HEAD", cwd=canonical)

    (canonical / ".venv").mkdir()
    (canonical / ".venv" / "pyvenv.cfg").write_text("version = 3.12.1\n", encoding="utf-8")
    python_metadata = canonical / ".venv" / "Lib" / "site-packages" / "fixture-1.0.dist-info"
    python_metadata.mkdir(parents=True)
    (python_metadata / "METADATA").write_text("Name: fixture\nVersion: 1.0\n", encoding="utf-8")
    (canonical / "apps" / "dsa-web" / "node_modules").mkdir(parents=True)
    echarts = canonical / "apps" / "dsa-web" / "node_modules" / "echarts"
    echarts.mkdir()
    (echarts / "package.json").write_text('{"name":"echarts","version":"6.1.0"}\n', encoding="utf-8")
    return canonical, linked


def run_bootstrap(
    worktree: Path,
    *args: str,
    env: dict[str, str] | None = None,
    absolute_script: bool = False,
) -> subprocess.CompletedProcess[str]:
    command_env = os.environ.copy()
    command_env.pop("WORKTREE_BOOTSTRAP_ENV_FILE", None)
    command_env.pop("WORKTREE_BOOTSTRAP_ISOLATED", None)
    command_env.update(env or {})
    if os.name == "nt" and env:
        forwarded = [name for name in env if name.startswith("WORKTREE_BOOTSTRAP_")]
        if forwarded:
            existing = [name for name in command_env.get("WSLENV", "").split(":") if name]
            command_env["WSLENV"] = ":".join(dict.fromkeys([*existing, *forwarded]))
    return subprocess.run(
        [
            sys.executable,
            str(CORE_PATH) if absolute_script else "scripts/worktree_preflight.py",
            "bootstrap",
            *args,
        ],
        cwd=worktree,
        text=True,
        capture_output=True,
        check=False,
        env=command_env,
    )


def resolved(path: Path) -> Path:
    return path.resolve(strict=True)


def add_lock_package(
    canonical: Path,
    lock_path: str,
    *,
    version: str = "1.0.0",
    optional: bool = False,
    os_constraints: list[str] | None = None,
    cpu_constraints: list[str] | None = None,
) -> None:
    lock_path_file = canonical / "apps" / "dsa-web" / "package-lock.json"
    lock = json.loads(lock_path_file.read_text(encoding="utf-8"))
    entry: dict[str, object] = {"version": version, "integrity": "sha512-fixture"}
    if optional:
        entry["optional"] = True
    if os_constraints is not None:
        entry["os"] = os_constraints
    if cpu_constraints is not None:
        entry["cpu"] = cpu_constraints
    lock["packages"][lock_path] = entry
    lock_path_file.write_text(json.dumps(lock), encoding="utf-8")


def write_installed_package(canonical: Path, lock_path: str, *, version: str = "1.0.0") -> None:
    package_json = canonical / "apps" / "dsa-web" / lock_path / "package.json"
    package_json.parent.mkdir(parents=True, exist_ok=True)
    package_json.write_text(
        json.dumps({"name": lock_path.removeprefix("node_modules/"), "version": version}),
        encoding="utf-8",
    )


def installed_npm_manifest(
    canonical: Path, monkeypatch: pytest.MonkeyPatch, *, os_name: str = "darwin", cpu: str = "arm64"
) -> dict[str, object]:
    import scripts.worktree_preflight as preflight

    monkeypatch.setattr(preflight, "npm_platform", lambda: {"os": os_name, "cpu": cpu}, raising=False)
    monkeypatch.setattr(
        preflight,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, '{"dependencies":{}}', ""),
    )
    return preflight.installed_npm_manifest(canonical)


def test_apply_discovers_canonical_main_worktree_and_creates_dependency_links(
    worktree_fixture: tuple[Path, Path],
) -> None:
    canonical, linked = worktree_fixture

    result = run_bootstrap(linked, "--apply")

    assert result.returncode == 0, result.stderr
    assert resolved(linked / ".venv") == canonical / ".venv"
    assert resolved(linked / "apps" / "dsa-web" / "node_modules") == (
        canonical / "apps" / "dsa-web" / "node_modules"
    )


def test_absolute_script_invocation_targets_the_current_linked_worktree(
    worktree_fixture: tuple[Path, Path],
) -> None:
    canonical, linked = worktree_fixture

    result = run_bootstrap(linked, "--apply", absolute_script=True)

    assert result.returncode == 0, result.stderr
    assert resolved(linked / ".venv") == canonical / ".venv"
    assert resolved(linked / "apps" / "dsa-web" / "node_modules") == (
        canonical / "apps" / "dsa-web" / "node_modules"
    )


def test_check_is_read_only_without_changing_shared_git_metadata(
    worktree_fixture: tuple[Path, Path],
) -> None:
    canonical, linked = worktree_fixture
    common_dir = Path(git_output("rev-parse", "--git-common-dir", cwd=linked))
    exclude_path = common_dir / "info" / "exclude"
    before = exclude_path.read_bytes()

    result = run_bootstrap(linked, "--check")

    assert result.returncode == 0, result.stderr
    assert "would link" in result.stdout
    assert exclude_path.read_bytes() == before
    assert not (canonical / ".venv").is_symlink()


def test_apply_does_not_change_shared_git_metadata(
    worktree_fixture: tuple[Path, Path],
) -> None:
    _, linked = worktree_fixture
    common_dir = Path(git_output("rev-parse", "--git-common-dir", cwd=linked))
    exclude_path = common_dir / "info" / "exclude"

    first = run_bootstrap(linked, "--apply")
    after_first = exclude_path.read_bytes()
    second = run_bootstrap(linked, "--apply")

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert after_first == exclude_path.read_bytes()


def test_check_fails_fast_when_canonical_dependency_is_missing_without_mutation(
    worktree_fixture: tuple[Path, Path],
) -> None:
    canonical, linked = worktree_fixture
    shutil.rmtree(canonical / "apps" / "dsa-web" / "node_modules")

    result = run_bootstrap(linked, "--check")

    assert result.returncode == 1
    assert "apps/dsa-web/node_modules" in result.stderr
    assert not (linked / ".venv").exists()
    assert not (linked / "apps" / "dsa-web" / "node_modules").exists()


def test_apply_is_idempotent_for_existing_correct_links(
    worktree_fixture: tuple[Path, Path],
) -> None:
    _, linked = worktree_fixture

    first = run_bootstrap(linked, "--apply")
    targets_before = {
        path: os.readlink(path)
        for path in (
            linked / ".venv",
            linked / "apps" / "dsa-web" / "node_modules",
        )
    }
    second = run_bootstrap(linked, "--apply")

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert targets_before == {path: os.readlink(path) for path in targets_before}
    assert "already linked" in second.stdout


@pytest.mark.parametrize(
    ("conflict_name", "is_directory"),
    [
        (".venv", False),
        ("apps/dsa-web/node_modules", False),
        (".venv", True),
    ],
)
def test_apply_refuses_to_replace_real_conflict_nodes(
    worktree_fixture: tuple[Path, Path], conflict_name: str, is_directory: bool
) -> None:
    _, linked = worktree_fixture
    conflict = linked / conflict_name
    conflict.parent.mkdir(parents=True, exist_ok=True)
    if is_directory:
        conflict.mkdir()
    else:
        conflict.write_text("keep\n", encoding="utf-8")

    result = run_bootstrap(linked, "--apply")

    assert result.returncode == 1
    assert "refusing to replace" in result.stderr.lower()
    if is_directory:
        assert conflict.is_dir()
    else:
        assert conflict.read_text(encoding="utf-8") == "keep\n"
    assert not (linked / ".venv").is_symlink()
    assert not (linked / "apps" / "dsa-web" / "node_modules").is_symlink()


def test_apply_refuses_symlink_that_points_to_another_target(
    worktree_fixture: tuple[Path, Path], tmp_path: Path
) -> None:
    _, linked = worktree_fixture
    wrong_target = tmp_path / "wrong-venv"
    wrong_target.mkdir()
    try:
        (linked / ".venv").symlink_to(wrong_target)
    except OSError:
        # This is the expected Windows non-admin capability limitation. A real
        # directory is still a conflicting mutable destination and must fail.
        (linked / ".venv").mkdir()

    result = run_bootstrap(linked, "--apply")

    assert result.returncode == 1
    assert "not the qualified canonical dependency link" in result.stderr
    if (linked / ".venv").is_symlink():
        assert resolved(linked / ".venv") == wrong_target
    assert not (linked / "apps" / "dsa-web" / "node_modules").exists()


def test_apply_links_explicit_external_env_file_without_printing_its_contents(
    worktree_fixture: tuple[Path, Path], tmp_path: Path
) -> None:
    _, linked = worktree_fixture
    env_file = tmp_path / "developer.env"
    secret = "TOP_SECRET_DO_NOT_PRINT"
    env_file.write_text(f"TOKEN={secret}\n", encoding="utf-8")

    result = run_bootstrap(
        linked,
        "--apply",
        env={"WORKTREE_BOOTSTRAP_ENV_FILE": str(env_file)},
    )

    if result.returncode == 0:
        assert resolved(linked / ".env") == env_file
    else:
        assert "Windows Developer Mode or symlink privilege" in result.stderr
    assert secret not in result.stdout
    assert secret not in result.stderr


def test_check_is_read_only_and_reports_planned_links(
    worktree_fixture: tuple[Path, Path],
) -> None:
    _, linked = worktree_fixture

    result = run_bootstrap(linked, "--check")

    assert result.returncode == 0, result.stderr
    assert "would link" in result.stdout
    assert not (linked / ".venv").exists()
    assert not (linked / "apps" / "dsa-web" / "node_modules").exists()


def test_isolated_environment_opt_out_makes_no_links(
    worktree_fixture: tuple[Path, Path],
) -> None:
    _, linked = worktree_fixture

    result = run_bootstrap(linked, "--apply", env={"WORKTREE_BOOTSTRAP_ISOLATED": "1"})

    assert result.returncode == 0, result.stderr
    assert "shared dependency reuse skipped" in result.stdout
    assert not (linked / ".venv").exists()
    assert not (linked / "apps" / "dsa-web" / "node_modules").exists()


def test_bootstrap_does_not_link_runtime_products(worktree_fixture: tuple[Path, Path]) -> None:
    _, linked = worktree_fixture

    result = run_bootstrap(linked, "--apply")

    assert result.returncode == 0, result.stderr
    for runtime_product in (
        "dist",
        "apps/dsa-web/dist",
        ".pytest_cache",
        ".cache",
        "coverage",
        ".coverage",
        "data",
        "data/app.db",
        "logs",
        "logs/app.log",
        "app.pid",
        "app.lock",
    ):
        assert not (linked / runtime_product).is_symlink()
        assert not (linked / runtime_product).exists()


def test_rejects_stale_echarts_before_links_or_heavy_validation(
    worktree_fixture: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    canonical, linked = worktree_fixture
    optional_foreign = "node_modules/@esbuild/aix-ppc64"
    optional_current = "node_modules/optional-current-platform"
    required_current = "node_modules/required-current-platform"
    required_wrong_version = "node_modules/required-wrong-version"
    required_invalid_metadata = "node_modules/required-invalid-metadata"

    add_lock_package(
        canonical,
        optional_foreign,
        version="0.27.2",
        optional=True,
        os_constraints=["aix"],
        cpu_constraints=["ppc64"],
    )
    assert optional_foreign not in installed_npm_manifest(canonical, monkeypatch)["packages"]

    add_lock_package(canonical, optional_current, optional=True, os_constraints=["darwin"], cpu_constraints=["arm64"])
    assert optional_current not in installed_npm_manifest(canonical, monkeypatch)["packages"]

    write_installed_package(canonical, optional_current)
    manifest = installed_npm_manifest(canonical, monkeypatch)
    assert manifest["packages"][optional_current] == "1.0.0"
    assert manifest["integrity"][optional_current] == "sha512-fixture"

    for lock_path, os_constraints, cpu_constraints in (
        ("node_modules/incompatible-os", ["aix"], None),
        ("node_modules/incompatible-cpu", None, ["ppc64"]),
    ):
        add_lock_package(canonical, lock_path, os_constraints=os_constraints, cpu_constraints=cpu_constraints)
        assert lock_path not in installed_npm_manifest(canonical, monkeypatch)["packages"]

    import scripts.worktree_preflight as preflight

    add_lock_package(canonical, required_wrong_version)
    write_installed_package(canonical, required_wrong_version, version="2.0.0")
    with pytest.raises(preflight.PreflightError, match="lockfile requires 1.0.0, installed 2.0.0"):
        installed_npm_manifest(canonical, monkeypatch)
    write_installed_package(canonical, required_wrong_version)

    add_lock_package(canonical, required_invalid_metadata)
    invalid_package_json = canonical / "apps" / "dsa-web" / required_invalid_metadata / "package.json"
    invalid_package_json.parent.mkdir(parents=True)
    invalid_package_json.write_text('{"name":"required-invalid-metadata"}', encoding="utf-8")
    with pytest.raises(preflight.PreflightError, match="installed npm package metadata is invalid"):
        installed_npm_manifest(canonical, monkeypatch)

    add_lock_package(canonical, required_current, os_constraints=["darwin"], cpu_constraints=["arm64"])
    with pytest.raises(preflight.PreflightError, match=f"installed npm package is missing: {required_current}"):
        installed_npm_manifest(canonical, monkeypatch)

    package_json = canonical / "apps" / "dsa-web" / "node_modules" / "echarts" / "package.json"
    package_json.write_text('{"name":"echarts","version":"5.6.0"}\n', encoding="utf-8")

    result = run_bootstrap(linked, "--check")

    assert result.returncode == 1
    assert "lockfile requires 6.1.0, installed 5.6.0" in result.stderr
    assert not (linked / ".venv").exists()
    assert not (linked / "apps" / "dsa-web" / "node_modules").exists()


def test_rejects_linked_manifest_mismatch_without_mutation(
    worktree_fixture: tuple[Path, Path],
) -> None:
    _, linked = worktree_fixture
    (linked / "requirements.txt").write_text("fixture-package==2.0\n", encoding="utf-8")

    result = run_bootstrap(linked, "--check")

    assert result.returncode == 1
    assert "dependency manifests differ" in result.stderr
    assert not (linked / ".venv").exists()


def test_fingerprint_output_is_deterministic(worktree_fixture: tuple[Path, Path]) -> None:
    canonical, _ = worktree_fixture
    command = ["python", str(CORE_PATH), "fingerprint", "--root", str(canonical)]
    first = subprocess.run(command, text=True, capture_output=True, check=False)
    second = subprocess.run(command, text=True, capture_output=True, check=False)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert first.stdout == second.stdout


@pytest.mark.parametrize(
    ("value", "host", "expected"),
    [
        (r"C:\\repo\\.git", "Windows", "C:"),
        ("/c/repo/.git", "Windows", "C:"),
        (r"C:\\repo\\.git", "Linux", "/mnt/c/repo/.git"),
        ("/srv/repo/.git", "Linux", "/srv/repo/.git"),
    ],
)
def test_normalize_git_path_cross_platform(value: str, host: str, expected: str, monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.worktree_preflight as preflight

    if host == "Linux" and value.startswith("C:"):
        monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    path = preflight.normalized_git_path_text(value, host=host)

    assert path.replace("\\", "/").startswith(expected)


@pytest.mark.parametrize("value", ["", "relative/.git", "gitdir: ../broken"])
def test_normalize_git_path_rejects_malformed_pointers(value: str) -> None:
    import scripts.worktree_preflight as preflight

    with pytest.raises(preflight.PreflightError):
        preflight.normalized_git_path_text(value)


@pytest.mark.parametrize(
    ("env", "executable", "expected"),
    [
        ({"MSYSTEM": "MINGW64"}, r"C:\\Program Files\\Git\\usr\\bin\\bash.exe", "msys"),
        ({"WSL_DISTRO_NAME": "Ubuntu"}, r"C:\\Windows\\System32\\bash.exe", "wsl"),
        ({}, r"/usr/bin/bash", "posix"),
    ],
)
def test_detect_shell_flavor_uses_explicit_environment_or_capability(
    env: dict[str, str], executable: str, expected: str
) -> None:
    import scripts.worktree_preflight as preflight

    assert preflight.detect_shell_flavor(executable=executable, environ=env, platform_name="Linux") == expected


@pytest.mark.parametrize(
    ("flavor", "expected"),
    [("msys", "/c/Users/test/repo"), ("wsl", "/mnt/c/Users/test/repo"), ("posix", r"C:\\Users\\test\\repo")],
)
def test_windows_to_posix_path_is_deterministic(flavor: str, expected: str) -> None:
    import scripts.worktree_preflight as preflight

    assert preflight.windows_to_posix_path(r"C:\\Users\\test\\repo", shell_flavor=flavor) == expected


def test_powershell_entrypoint_delegates_to_the_shared_core() -> None:
    content = POWERSHELL_PATH.read_text(encoding="utf-8")
    assert "worktree_preflight.py" in content
    assert "bootstrap" in content


def test_posix_entrypoint_delegates_to_the_shared_core() -> None:
    content = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "worktree_preflight.py" in content
    assert "python3" in content


def test_entrypoints_run_shared_core_in_isolated_mode() -> None:
    env = os.environ.copy()
    env["WORKTREE_BOOTSTRAP_ISOLATED"] = "1"
    if os.name == "nt":
        existing = [name for name in env.get("WSLENV", "").split(":") if name]
        env["WSLENV"] = ":".join(dict.fromkeys([*existing, "WORKTREE_BOOTSTRAP_ISOLATED"]))
    import scripts.worktree_preflight as preflight

    bash_executable = shutil.which("bash") or ""
    shell_flavor = preflight.detect_shell_flavor(executable=bash_executable, environ=env)
    posix_script = preflight.windows_to_posix_path(str(SCRIPT_PATH), shell_flavor=shell_flavor) if os.name == "nt" else str(SCRIPT_PATH)
    posix = subprocess.run(["bash", posix_script, "--check"], text=True, capture_output=True, env=env, check=False)
    assert posix.returncode == 0, posix.stderr
    assert "shared dependency reuse skipped" in posix.stdout
    powershell_executable = shutil.which("pwsh")
    if not powershell_executable:
        return
    powershell = subprocess.run(
        [powershell_executable, "-NoProfile", "-File", str(POWERSHELL_PATH), "-Check"],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert powershell.returncode == 0, powershell.stderr
    assert "shared dependency reuse skipped" in powershell.stdout


def test_link_capabilities_do_not_require_privileged_probe() -> None:
    import scripts.worktree_preflight as preflight

    capabilities = preflight.symlink_capabilities()
    assert capabilities["symlink_api"]
    assert isinstance(capabilities["junction_fallback"], bool)
