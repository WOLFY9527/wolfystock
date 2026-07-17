from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from scripts.environment.errors import EnvironmentFailure
from scripts.environment.manager import require_managed_python


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "bootstrap_worktree.sh"
CORE_PATH = REPO_ROOT / "scripts" / "worktree_preflight.py"
POWERSHELL_PATH = REPO_ROOT / "scripts" / "bootstrap_worktree.ps1"


def _load_preflight():
    spec = importlib.util.spec_from_file_location("worktree_preflight_delegate", CORE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_qualification_rejects_wrong_python_interpreter(tmp_path: Path) -> None:
    managed = tmp_path / ".venv" / "bin" / "python"
    managed.parent.mkdir(parents=True)
    managed.write_text("", encoding="utf-8")

    with pytest.raises(EnvironmentFailure, match="wrong_managed_interpreter"):
        require_managed_python(tmp_path, executable=tmp_path / "wrong" / "python")


def test_qualification_accepts_repository_python(tmp_path: Path) -> None:
    managed = tmp_path / ".venv" / "bin" / "python"
    managed.parent.mkdir(parents=True)
    managed.write_text("", encoding="utf-8")

    assert require_managed_python(tmp_path, executable=managed) == managed.resolve()


@pytest.mark.parametrize(
    ("arguments", "delegated"),
    [
        (["bootstrap", "--check"], ["env", "verify"]),
        (["bootstrap", "--apply"], ["bootstrap", "--ensure"]),
    ],
)
def test_python_compatibility_entrypoint_delegates_to_wolfy(
    monkeypatch: pytest.MonkeyPatch, arguments: list[str], delegated: list[str]
) -> None:
    module = _load_preflight()
    calls: list[list[str]] = []
    monkeypatch.setattr(module, "wolfy_main", lambda values: calls.append(values) or 0)

    assert module.main(arguments) == 0
    assert calls == [delegated]


def test_python_compatibility_entrypoint_rejects_obsolete_commands() -> None:
    module = _load_preflight()

    assert module.main(["fingerprint"]) == 2


def test_posix_entrypoint_is_a_thin_wolfy_delegate() -> None:
    content = SCRIPT_PATH.read_text(encoding="utf-8")

    assert '"${ROOT_DIR}/wolfy" env verify' in content
    assert '"${ROOT_DIR}/wolfy" bootstrap --ensure' in content
    for obsolete in ("worktree_preflight.py", "requirements.txt", "node_modules", "CANONICAL_ROOT"):
        assert obsolete not in content


def test_powershell_entrypoint_is_a_thin_wolfy_delegate() -> None:
    content = POWERSHELL_PATH.read_text(encoding="utf-8")

    assert "wolfy.ps1" in content
    assert "worktree_preflight.py" not in content
    assert "bootstrap" in content
    assert "verify" in content


def test_python_delegate_contains_no_environment_authority() -> None:
    content = CORE_PATH.read_text(encoding="utf-8")

    assert "environment.cli" in content
    for obsolete in ("hashlib", "subprocess", "node_modules", "requirements.txt", "symlink", "canonical"):
        assert obsolete not in content
