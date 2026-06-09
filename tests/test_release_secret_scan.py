import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_SOURCE = REPO_ROOT / "scripts" / "release_secret_scan.sh"
COLLECTOR_SOURCE = REPO_ROOT / "scripts" / "validation_changed_files.py"


def _run(cmd, cwd: Path, **kwargs):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, **kwargs)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "scripts").mkdir()
    shutil.copy2(SCRIPT_SOURCE, repo / "scripts" / "release_secret_scan.sh")
    shutil.copy2(COLLECTOR_SOURCE, repo / "scripts" / "validation_changed_files.py")

    _run(["git", "init", "-b", "main"], repo, check=True)
    _run(["git", "config", "user.email", "codex@example.com"], repo, check=True)
    _run(["git", "config", "user.name", "Codex Test"], repo, check=True)
    (repo / "README.md").write_text("initial\n", encoding="utf-8")
    _run(["git", "add", "README.md", "scripts/release_secret_scan.sh"], repo, check=True)
    _run(["git", "commit", "-m", "initial"], repo, check=True)
    _run(["git", "update-ref", "refs/remotes/origin/main", "HEAD"], repo, check=True)
    return repo


def _scan(repo: Path, *args: str):
    return _run(["bash", "scripts/release_secret_scan.sh", *args], repo)


def test_release_secret_scan_flags_worktree_api_key(tmp_path):
    repo = _init_repo(tmp_path)
    key_value = "sk-" + ("A" * 40)
    (repo / "config.txt").write_text(f"OPENAI_API_KEY={key_value}\n", encoding="utf-8")

    result = _scan(repo)

    assert result.returncode == 1
    assert "config.txt:1" in result.stdout
    assert "OpenAI-style API key" in result.stdout
    assert key_value not in result.stdout
    assert key_value not in result.stderr


def test_release_secret_scan_allows_env_example_placeholders(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / ".env.example").write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=",
                "DISCORD_BOT_TOKEN=your-discord-bot-token",
                "ADMIN_PASSWORD=changeme",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = _scan(repo)

    assert result.returncode == 0
    assert "No high-confidence secret patterns" in result.stdout
    assert "secret-like credential assignment" not in result.stdout


def test_release_secret_scan_allows_frontend_e2e_state_placeholders(tmp_path):
    repo = _init_repo(tmp_path)
    fixture = repo / "apps" / "dsa-web" / "e2e" / "fixtures" / "adminAuth.ts"
    fixture.parent.mkdir(parents=True)
    fixture.write_text(
        "\n".join(
            [
                "export const adminAuthFixture = {",
                "  credential_state: 'missing_credentials',",
                "  credentials_present: false,",
                "  password_state: 'set',",
                "};",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = _scan(repo)

    assert result.returncode == 0
    assert "No high-confidence secret patterns" in result.stdout


def test_release_secret_scan_allows_checked_in_admin_auth_fixture(tmp_path):
    repo = _init_repo(tmp_path)
    fixture = repo / "apps" / "dsa-web" / "e2e" / "fixtures" / "adminAuth.ts"
    fixture.parent.mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "apps" / "dsa-web" / "e2e" / "fixtures" / "adminAuth.ts", fixture)

    result = _scan(repo)

    assert result.returncode == 0
    assert "No high-confidence secret patterns" in result.stdout


def test_release_secret_scan_flags_staged_password_assignment(tmp_path):
    repo = _init_repo(tmp_path)
    password_value = "correct-" + "horse"
    (repo / "release.config").write_text(f"ADMIN_PASSWORD={password_value}\n", encoding="utf-8")
    _run(["git", "add", "release.config"], repo, check=True)

    result = _scan(repo)

    assert result.returncode == 1
    assert "release.config:1" in result.stdout
    assert "non-empty password assignment" in result.stdout
    assert password_value not in result.stdout
    assert password_value not in result.stderr


def test_release_secret_scan_flags_frontend_e2e_password_assignment(tmp_path):
    repo = _init_repo(tmp_path)
    password_value = "correct-" + "horse"
    fixture = repo / "apps" / "dsa-web" / "e2e" / "fixtures" / "adminAuth.ts"
    fixture.parent.mkdir(parents=True)
    fixture.write_text(f"export const admin_password = '{password_value}';\n", encoding="utf-8")

    result = _scan(repo)

    assert result.returncode == 1
    assert "apps/dsa-web/e2e/fixtures/adminAuth.ts:1" in result.stdout
    assert "non-empty password assignment" in result.stdout
    assert password_value not in result.stdout
    assert password_value not in result.stderr


def test_release_secret_scan_flags_frontend_e2e_api_key_assignment(tmp_path):
    repo = _init_repo(tmp_path)
    key_value = "sk-" + ("B" * 40)
    fixture = repo / "apps" / "dsa-web" / "e2e" / "fixtures" / "adminAuth.ts"
    fixture.parent.mkdir(parents=True)
    fixture.write_text(f"export const openaiApiKey = '{key_value}';\n", encoding="utf-8")

    result = _scan(repo)

    assert result.returncode == 1
    assert "apps/dsa-web/e2e/fixtures/adminAuth.ts:1" in result.stdout
    assert "OpenAI-style API key" in result.stdout
    assert key_value not in result.stdout
    assert key_value not in result.stderr


def test_release_secret_scan_flags_committed_branch_bearer_token(tmp_path):
    repo = _init_repo(tmp_path)
    token_value = "tok_" + ("b" * 32)
    (repo / "docs.md").write_text(f"Authorization: Bearer {token_value}\n", encoding="utf-8")
    _run(["git", "add", "docs.md"], repo, check=True)
    _run(["git", "commit", "-m", "add docs"], repo, check=True)

    result = _scan(repo)

    assert result.returncode == 1
    assert "docs.md:1" in result.stdout
    assert "bearer token" in result.stdout
    assert token_value not in result.stdout
    assert token_value not in result.stderr


def test_release_secret_scan_local_only_skips_committed_branch_changes(tmp_path):
    repo = _init_repo(tmp_path)
    token_value = "tok_" + ("c" * 32)
    (repo / "docs.md").write_text(f"Authorization: Bearer {token_value}\n", encoding="utf-8")
    _run(["git", "add", "docs.md"], repo, check=True)
    _run(["git", "commit", "-m", "add docs"], repo, check=True)

    default_result = _scan(repo)
    local_only_result = _scan(repo, "--local-only")

    assert default_result.returncode == 1
    assert local_only_result.returncode == 0
    assert "local-only" in local_only_result.stdout


def test_release_secret_scan_files_from_scans_only_listed_files(tmp_path):
    repo = _init_repo(tmp_path)
    key_value = "sk-" + ("C" * 40)
    (repo / "safe.txt").write_text("SAFE_VALUE=example\n", encoding="utf-8")
    (repo / "secret.txt").write_text(f"OPENAI_API_KEY={key_value}\n", encoding="utf-8")
    file_list = repo / "files.txt"
    file_list.write_text("safe.txt\n", encoding="utf-8")

    result = _scan(repo, "--files-from", str(file_list))

    assert result.returncode == 0
    assert "files-from" in result.stdout
    assert key_value not in result.stdout
    assert key_value not in result.stderr


def test_release_secret_scan_files_from_skips_generated_static_paths(tmp_path):
    repo = _init_repo(tmp_path)
    key_value = "sk-" + ("D" * 40)
    generated = repo / "generated" / "config.txt"
    generated.parent.mkdir()
    generated.write_text(f"OPENAI_API_KEY={key_value}\n", encoding="utf-8")
    file_list = repo / "files.txt"
    file_list.write_text("generated/config.txt\n", encoding="utf-8")

    result = _scan(repo, "--files-from", str(file_list))

    assert result.returncode == 0
    assert key_value not in result.stdout
    assert key_value not in result.stderr
