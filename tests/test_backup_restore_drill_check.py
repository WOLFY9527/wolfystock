import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_SOURCE = REPO_ROOT / "scripts" / "backup_restore_drill_check.sh"


def _run(cmd, cwd: Path, **kwargs):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, **kwargs)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "scripts").mkdir()
    (repo / "tests").mkdir()
    shutil.copy2(SCRIPT_SOURCE, repo / "scripts" / "backup_restore_drill_check.sh")
    (repo / "tests" / "test_backup_restore_drill_smoke.py").write_text(
        "# disposable restore smoke placeholder\n",
        encoding="utf-8",
    )

    _run(["git", "init", "-b", "main"], repo, check=True)
    _run(["git", "config", "user.email", "codex@example.com"], repo, check=True)
    _run(["git", "config", "user.name", "Codex Test"], repo, check=True)
    (repo / "README.md").write_text("initial\n", encoding="utf-8")
    _run(["git", "add", "README.md", "scripts", "tests"], repo, check=True)
    _run(["git", "commit", "-m", "initial"], repo, check=True)
    return repo


def _drill_check(repo: Path, *args: str, **kwargs):
    return _run(["bash", "scripts/backup_restore_drill_check.sh", *args], repo, **kwargs)


def test_backup_restore_drill_check_prints_required_commands(tmp_path):
    repo = _init_repo(tmp_path)

    result = _drill_check(repo)

    assert result.returncode == 0
    assert "Local-only backup/restore release drill checklist" in result.stdout
    assert "tests/test_backup_restore_drill_smoke.py: present" in result.stdout
    assert "python3 -m pytest tests/test_backup_restore_drill_smoke.py -q" in result.stdout
    assert "bash -n scripts/backup_restore_drill_check.sh" in result.stdout
    assert "not proof of production restore success" in result.stdout
    assert "No production DB, migration, PostgreSQL, or backup infrastructure action is performed" in result.stdout


def test_backup_restore_drill_check_rejects_unsafe_db_path(tmp_path):
    repo = _init_repo(tmp_path)

    result = _drill_check(repo, "--db-path", "/var/lib/postgresql/prod/wolfystock.sqlite")

    assert result.returncode == 1
    assert "[FAIL] Unsafe DB path refused" in result.stderr
    assert "/var/lib/postgresql/prod/wolfystock.sqlite" in result.stderr


def test_backup_restore_drill_check_does_not_mutate_files(tmp_path):
    repo = _init_repo(tmp_path)

    before = _run(["git", "status", "--short"], repo, check=True).stdout
    result = _drill_check(repo, "--db-path", str(tmp_path / "scratch" / "restore.sqlite"))
    after = _run(["git", "status", "--short"], repo, check=True).stdout

    assert result.returncode == 0
    assert before == ""
    assert after == ""
