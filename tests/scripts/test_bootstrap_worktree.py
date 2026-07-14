from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "bootstrap_worktree.sh"


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def worktree_fixture(tmp_path: Path) -> tuple[Path, Path]:
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    git("init", "--initial-branch=main", cwd=canonical)
    git("config", "user.name", "Bootstrap Test", cwd=canonical)
    git("config", "user.email", "bootstrap@example.test", cwd=canonical)

    (canonical / "scripts").mkdir()
    shutil.copy2(SCRIPT_PATH, canonical / "scripts" / "bootstrap_worktree.sh")
    (canonical / "apps" / "dsa-web").mkdir(parents=True)
    (canonical / "apps" / "dsa-web" / ".gitkeep").touch()
    (canonical / "README.md").write_text("fixture\n", encoding="utf-8")
    git("add", ".", cwd=canonical)
    git("commit", "-m", "fixture", cwd=canonical)

    linked = tmp_path / "linked"
    git("worktree", "add", "-b", "fixture-linked", str(linked), "HEAD", cwd=canonical)

    (canonical / ".venv").mkdir()
    (canonical / "apps" / "dsa-web" / "node_modules").mkdir(parents=True)
    return canonical, linked


def run_bootstrap(
    worktree: Path,
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command_env = os.environ.copy()
    command_env.pop("WORKTREE_BOOTSTRAP_ENV_FILE", None)
    command_env.pop("WORKTREE_BOOTSTRAP_ISOLATED", None)
    command_env.update(env or {})
    return subprocess.run(
        ["bash", "scripts/bootstrap_worktree.sh", *args],
        cwd=worktree,
        text=True,
        capture_output=True,
        check=False,
        env=command_env,
    )


def resolved(path: Path) -> Path:
    return path.resolve(strict=True)


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
    (linked / ".venv").symlink_to(wrong_target)

    result = run_bootstrap(linked, "--apply")

    assert result.returncode == 1
    assert "points somewhere else" in result.stderr
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

    assert result.returncode == 0, result.stderr
    assert resolved(linked / ".env") == env_file
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
    assert "isolated environment" in result.stdout
    assert "lockfile" in result.stdout
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
