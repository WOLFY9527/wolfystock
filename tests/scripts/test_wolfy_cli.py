from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from scripts.environment.cli import _execute


ROOT = Path(__file__).resolve().parents[2]
WOLFY = ROOT / "wolfy"
WOLFY_POWERSHELL = ROOT / "wolfy.ps1"
CLI = ROOT / "scripts" / "wolfy.py"
SERVICE_ENTRYPOINT = ROOT / "scripts" / "wolfy_service.py"
BOOTSTRAP_SH = ROOT / "scripts" / "bootstrap_worktree.sh"
BOOTSTRAP_PS1 = ROOT / "scripts" / "bootstrap_worktree.ps1"
PREFLIGHT = ROOT / "scripts" / "worktree_preflight.py"
CI_GATES = (ROOT / "scripts" / "ci_gate.sh", ROOT / "scripts" / "ci_gate_fast.sh")


def test_root_launchers_select_supported_bootstrap_without_using_mutable_worktree_dependencies() -> None:
    posix = WOLFY.read_text(encoding="utf-8")
    powershell = WOLFY_POWERSHELL.read_text(encoding="utf-8")

    assert "python3.11" in posix
    assert "WOLFYSTOCK_BOOTSTRAP_PYTHON" in posix
    assert ".venv" not in posix
    assert "scripts/wolfy.py" in posix
    assert "3.11" in powershell
    assert "Get-Command py" in powershell
    assert "-3.11" in powershell
    assert "scripts/wolfy.py" in powershell.replace("\\", "/")


def test_cli_help_exposes_single_canonical_command_surface() -> None:
    result = subprocess.run(
        [sys.executable, str(CLI), "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "WOLFYSTOCK_SKIP_INTERPRETER_CHECK": "1"},
    )

    assert result.returncode == 0, result.stderr
    for command in ("bootstrap", "env", "exec", "qualify-env", "dev"):
        assert command in result.stdout


def test_existing_worktree_entrypoints_are_thin_wolfy_delegates() -> None:
    shell = BOOTSTRAP_SH.read_text(encoding="utf-8")
    powershell = BOOTSTRAP_PS1.read_text(encoding="utf-8")
    preflight = PREFLIGHT.read_text(encoding="utf-8")

    assert "wolfy" in shell
    assert "worktree_preflight.py" not in shell
    assert "wolfy.ps1" in powershell
    assert "environment.cli" in preflight
    for forbidden in ("hashlib", "node_modules", "requirements.txt", "canonical"):
        assert forbidden not in preflight


def test_local_backend_gates_delegate_to_hermetic_test_profile() -> None:
    for path in CI_GATES:
        content = path.read_text(encoding="utf-8")
        assert "WOLFYSTOCK_TEST_RUN_ID" in content
        assert 'wolfy" exec --profile test -- bash' in content


def test_managed_service_entrypoint_resolves_repository_without_pythonpath() -> None:
    content = SERVICE_ENTRYPOINT.read_text(encoding="utf-8")

    assert "Path(__file__).resolve().parents[1]" in content
    assert "sys.path.insert" in content
    assert "PYTHONPATH" not in content


def test_qualify_env_rejects_implicit_or_mismatched_baseline_identity(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    baseline.write_text(
        json.dumps(
            {
                "schemaVersion": "wolfystock_qualification_findings_v1",
                "commit": "a" * 40,
                "checkoutClean": False,
                "environmentFingerprint": "b" * 64,
                "findings": [],
            }
        ),
        encoding="utf-8",
    )
    current.write_text("[]\n", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "qualify-env",
            "--baseline-commit",
            "a" * 40,
            "--baseline-evidence",
            str(baseline),
            "--findings",
            str(current),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "WOLFYSTOCK_SKIP_INTERPRETER_CHECK": "1", "WOLFYSTOCK_TEST_FAKE_ENVIRONMENT": "1"},
    )

    assert result.returncode == 1
    payload = json.loads(result.stderr)
    assert payload["reasonCode"] == "baseline_checkout_not_clean"

    baseline.write_text(
        json.dumps(
            {
                "schemaVersion": "wolfystock_qualification_findings_v1",
                "commit": "short",
                "checkoutClean": True,
                "environmentFingerprint": "b" * 64,
                "findings": [],
            }
        ),
        encoding="utf-8",
    )
    invalid_commit = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "qualify-env",
            "--baseline-commit",
            "short",
            "--baseline-evidence",
            str(baseline),
            "--findings",
            str(current),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=os.environ.copy(),
    )
    assert invalid_commit.returncode == 1
    assert json.loads(invalid_commit.stderr)["reasonCode"] == "baseline_commit_invalid"


def test_failed_exec_retains_run_scoped_environment_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    observed: dict[str, object] = {}

    class Manager:
        cache_root = tmp_path / "cache"

        def verify(self, *, run_id=None):
            observed["runId"] = run_id
            return SimpleNamespace(
                combined_fingerprint="e" * 64,
                evidence={
                    "schemaVersion": "wolfystock_environment_evidence_v1",
                    "environmentFingerprint": "e" * 64,
                    "operational": {"runId": run_id},
                },
            )

    def child(command, **kwargs):
        observed["environment"] = kwargs["env"]
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setenv("ALPACA_API_KEY", "must-not-be-recorded")
    monkeypatch.setattr("scripts.environment.cli.secrets.token_hex", lambda _count: "a" * 16)
    monkeypatch.setattr("scripts.environment.cli.shutil.which", lambda _name: "/managed/node/bin/node")
    monkeypatch.setattr("scripts.environment.cli.managed_python_path", lambda _root: Path("/managed/bin/python"))
    monkeypatch.setattr("scripts.environment.cli.subprocess.run", child)

    result = _execute(tmp_path, Manager(), SimpleNamespace(child_command=["--", "fixture-command"]))

    run_id = "run-" + "a" * 16
    evidence_path = Manager.cache_root / "runs" / "failed" / run_id / "services" / "environment-evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert result == 1
    assert observed["runId"] == run_id
    assert evidence["operational"]["runId"] == run_id
    assert "must-not-be-recorded" not in evidence_path.read_text(encoding="utf-8")
    assert "ALPACA_API_KEY" not in observed["environment"]
