import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_SOURCE = REPO_ROOT / "scripts" / "release_gate_summary.sh"


def _run(cmd, cwd: Path, **kwargs):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, **kwargs)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "scripts").mkdir()
    shutil.copy2(SCRIPT_SOURCE, repo / "scripts" / "release_gate_summary.sh")
    (repo / "scripts" / "release_secret_scan.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (repo / "scripts" / "ci_gate_fast.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    _run(["git", "init", "-b", "main"], repo, check=True)
    _run(["git", "config", "user.email", "codex@example.com"], repo, check=True)
    _run(["git", "config", "user.name", "Codex Test"], repo, check=True)
    (repo / "README.md").write_text("initial\n", encoding="utf-8")
    _run(["git", "add", "README.md", "scripts"], repo, check=True)
    _run(["git", "commit", "-m", "initial"], repo, check=True)
    _run(["git", "update-ref", "refs/remotes/origin/main", "HEAD"], repo, check=True)
    return repo


def _summary(repo: Path, *args: str):
    return _run(["bash", "scripts/release_gate_summary.sh", *args], repo)


def test_release_gate_summary_prints_required_fields_on_clean_repo(tmp_path):
    repo = _init_repo(tmp_path)

    result = _summary(repo)

    assert result.returncode == 0
    assert "Current branch: main" in result.stdout
    assert "Ahead/behind vs origin/main: ahead 0, behind 0" in result.stdout
    assert "Worktree dirty: no" in result.stdout
    assert "scripts/release_secret_scan.sh: present" in result.stdout
    assert "scripts/ci_gate_fast.sh: present" in result.stdout
    assert "./scripts/release_secret_scan.sh" in result.stdout
    assert "./scripts/ci_gate_fast.sh" in result.stdout
    assert "./scripts/ci_gate.sh" in result.stdout
    assert "git diff --check origin/main..HEAD" in result.stdout
    assert "not a release approval tool" in result.stdout


def test_release_gate_summary_fails_on_dirty_repo_without_allow_dirty(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "scratch.txt").write_text("local\n", encoding="utf-8")

    result = _summary(repo)

    assert result.returncode == 1
    assert "Untracked files: 1" in result.stdout
    assert "Worktree dirty: yes" in result.stdout
    assert "scratch.txt" in result.stdout
    assert "Worktree is dirty" in result.stderr


def test_release_gate_summary_allows_dirty_repo_with_explicit_flag(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "scratch.txt").write_text("local\n", encoding="utf-8")

    result = _summary(repo, "--allow-dirty")

    assert result.returncode == 0
    assert "Untracked files: 1" in result.stdout
    assert "Worktree dirty: yes" in result.stdout
    assert "[PASS] release gate summary completed" in result.stdout
