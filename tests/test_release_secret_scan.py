import json
import io
import shutil
import subprocess
import tarfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_SOURCE = REPO_ROOT / "scripts" / "release_secret_scan.sh"
COLLECTOR_SOURCE = REPO_ROOT / "scripts" / "validation_changed_files.py"
CANDIDATE_SCANNER_SOURCE = REPO_ROOT / "scripts" / "release_secret_scan_candidate.py"


def _run(cmd, cwd: Path, **kwargs):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, **kwargs)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "scripts").mkdir()
    shutil.copy2(SCRIPT_SOURCE, repo / "scripts" / "release_secret_scan.sh")
    shutil.copy2(COLLECTOR_SOURCE, repo / "scripts" / "validation_changed_files.py")
    shutil.copy2(CANDIDATE_SCANNER_SOURCE, repo / "scripts" / "release_secret_scan_candidate.py")

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
    workflow = repo / ".github" / "workflows" / "unsafe.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("env:\n  GH_TOKEN: ${{ 'hardcoded-token-123456' }}\n", encoding="utf-8")

    result = _scan(repo)

    assert result.returncode == 1
    assert "config.txt:1" in result.stdout
    assert "OpenAI-style API key" in result.stdout
    assert ".github/workflows/unsafe.yml:2" in result.stdout
    assert "secret-like credential assignment" in result.stdout
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
    workflow = repo / ".github" / "workflows" / "release.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        "env:\n  GH_TOKEN: ${{ github.token }}\n  DOCKERHUB_TOKEN: ${{ secrets.DOCKERHUB_TOKEN }}\n",
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
    workflow = repo / ".github" / "workflows" / "release.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        "env:\n  GH_TOKEN: ${{ github.token }}\n  DOCKERHUB_TOKEN: ${{ secrets.DOCKERHUB_TOKEN }}\n",
        encoding="utf-8",
    )

    result = _scan(repo)

    assert result.returncode == 0
    assert "No high-confidence secret patterns" in result.stdout

    _run(["git", "add", str(fixture.relative_to(repo)), str(workflow.relative_to(repo))], repo, check=True)
    _run(["git", "commit", "-m", "add safe fixture"], repo, check=True)
    evidence_path = repo / "scan-evidence.json"
    candidate_result = _scan(repo, "--candidate-ref", "HEAD", "--evidence", str(evidence_path))

    assert candidate_result.returncode == 0, candidate_result.stderr
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schemaVersion"] == "wolfystock_release_secret_scan_v1"
    assert evidence["mode"] == "candidate"
    assert evidence["scannedCommit"] == _run(["git", "rev-parse", "HEAD"], repo, check=True).stdout.strip()
    assert evidence["fileCount"] > 0
    assert evidence["status"] == "PASS"


def test_release_secret_scan_rejects_private_paths_in_generated_evidence(tmp_path):
    repo = _init_repo(tmp_path)
    evidence_root = repo / "generated-evidence"
    evidence_root.mkdir()
    (evidence_root / "qualification.json").write_text(
        json.dumps({"status": "PASS", "runtimeCwd": "/Users/private/worktree"}),
        encoding="utf-8",
    )

    result = _scan(repo, "--candidate-ref", "HEAD", "--evidence-root", str(evidence_root))

    assert result.returncode == 1
    assert "generated-evidence/qualification.json" in result.stdout
    assert "private absolute path" in result.stdout


def test_release_secret_scan_rejects_credentials_inside_candidate_archive(tmp_path):
    repo = _init_repo(tmp_path)
    evidence_root = repo / "generated-evidence"
    evidence_root.mkdir()
    archive_path = evidence_root / "source.tar.gz"
    secret = "sk-" + ("Q" * 40)
    content = f"OPENAI_API_KEY={secret}\n".encode()
    with tarfile.open(archive_path, "w:gz") as archive:
        info = tarfile.TarInfo("source/config.env")
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))

    result = _scan(repo, "--candidate-ref", "HEAD", "--evidence-root", str(evidence_root))

    assert result.returncode == 1
    assert "source.tar.gz!source/config.env" in result.stdout
    assert "OpenAI-style API key" in result.stdout
    assert secret not in result.stdout


def test_release_secret_scan_treats_only_topology_test_ids_as_reviewed_fixture_data(tmp_path):
    repo = _init_repo(tmp_path)
    topology = repo / "validation" / "domain_test_topology.json"
    topology.parent.mkdir()
    example_key = "AKIA" + "IOSFODNN7EXAMPLE"
    payload = {
        "backend": {
            "tests": [
                {"id": f"tests/test_safe_error.py::test_redacts[{example_key}]"},
            ],
        },
        "playwright": {
            "projectCases": [
                {
                    "id": (
                        "chromium::apps/dsa-web/e2e/no-secret.spec.ts::"
                        "no-secret surfaces :: credentials remain redacted"
                    ),
                },
            ],
        },
    }
    topology.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    fixture_result = _scan(repo)

    assert fixture_result.returncode == 0, fixture_result.stdout + fixture_result.stderr

    payload["credential"] = "hardcoded-token-123456"
    topology.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    credential_result = _scan(repo)

    assert credential_result.returncode == 1
    assert "secret-like credential assignment" in credential_result.stdout


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

    candidate_result = _scan(repo, "--candidate-ref", "HEAD")

    assert candidate_result.returncode == 1
    assert "bearer token" in candidate_result.stdout
    assert token_value not in candidate_result.stdout
    assert token_value not in candidate_result.stderr


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

    assert result.returncode == 1
    assert "zero files" in result.stderr.lower()
    assert key_value not in result.stdout
    assert key_value not in result.stderr
