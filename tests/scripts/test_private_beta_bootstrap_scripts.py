from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SCRIPT = REPO_ROOT / "scripts" / "dev-start-frontend.ps1"
BACKEND_SCRIPT = REPO_ROOT / "scripts" / "dev-start-backend.ps1"
SEED_SCRIPT = REPO_ROOT / "scripts" / "seed-uat-consumer-test-accounts.ps1"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_windows_frontend_start_script_pins_current_worktree_and_port() -> None:
    content = _read(FRONTEND_SCRIPT)

    assert "apps\\dsa-web" in content
    assert "npm run dev -- --host $BindHost --port $Port --strictPort" in content
    assert "Get-NetTCPConnection -State Listen -LocalPort $LocalPort" in content
    assert "Refusing to start Vite while port $Port is occupied" in content
    assert "Repo path" in content
    assert "Branch" in content
    assert "HEAD" in content
    assert "URL" in content


def test_windows_backend_start_script_prefers_repo_venv_and_existing_entrypoint() -> None:
    content = _read(BACKEND_SCRIPT)

    repo_python_index = content.index(".venv\\Scripts\\python.exe")
    fallback_python_index = content.index("$pythonBin = 'python'")
    assert repo_python_index < fallback_python_index
    assert "main.py" in content
    assert "'--serve-only'" in content
    assert "src.config.setup_env()" in content
    assert "Repo path" in content
    assert "Branch" in content
    assert "HEAD" in content
    assert "URL" in content


def test_windows_uat_consumer_seed_wrapper_blocks_production_and_reuses_seed_script() -> None:
    content = _read(SEED_SCRIPT)

    assert ".venv\\Scripts\\python.exe" in content
    assert "scripts\\seed_uat_consumer_test_accounts.py" in content
    assert "is_production_mode" in content
    assert "Refusing to seed UAT consumer accounts in production mode" in content
    assert "uat_consumer_test" in content
    assert "webuat_consumer" in content
    assert "Role:       user only" in content
