from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _run_isolated_pytest(
    tmp_path: Path,
    source: str,
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (tmp_path / "test_destructive_sample.py").write_text(source, encoding="utf-8")
    command_env = os.environ.copy()
    command_env.update(env or {})
    command_env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(ROOT), command_env.get("PYTHONPATH"))))
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "tests.destructive_postgres",
            "test_destructive_sample.py",
            *args,
        ],
        cwd=tmp_path,
        env=command_env,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def test_inherited_dsn_alone_skips_destructive_test_body(tmp_path: Path) -> None:
    marker = tmp_path / "body-ran"
    result = _run_isolated_pytest(
        tmp_path,
        f"""
import pathlib
import pytest

@pytest.mark.destructive_postgres
def test_destructive_body():
    pathlib.Path({str(marker)!r}).write_text("unsafe", encoding="utf-8")
""",
        env={
            "POSTGRES_PHASE_A_REAL_DSN": (
                "postgresql://inherited:secret@127.0.0.1:55432/"
                "wolfystock_destructive_test_fixture"
            )
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 skipped" in result.stdout
    assert not marker.exists()


def test_explicit_opt_in_refuses_unsafe_or_ambiguous_identity() -> None:
    from tests.destructive_postgres import DestructivePostgresPolicyError, qualify_target

    with pytest.raises(DestructivePostgresPolicyError, match="disposable database"):
        qualify_target(
            dsn=(
                "postgresql://user:secret@127.0.0.1:5432/"
                "wolfystock_destructive_test_production"
            ),
            allowed_target="127.0.0.1:5432/wolfystock_destructive_test_production",
            audit_id="T506",
        )

    with pytest.raises(DestructivePostgresPolicyError, match="exact target identity"):
        qualify_target(
            dsn="postgresql://user:secret@127.0.0.1:55432/wolfystock_destructive_test_a",
            allowed_target="127.0.0.1:55432/wolfystock_destructive_test_b",
            audit_id="T506",
        )


def test_mocked_disposable_target_generates_run_scoped_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.destructive_postgres import qualify_target

    monkeypatch.setattr("tests.destructive_postgres.secrets.token_hex", lambda _: "0123456789abcdef")
    target = qualify_target(
        dsn="postgresql://user:secret@localhost:55432/wolfystock_destructive_test_fixture",
        allowed_target="localhost:55432/wolfystock_destructive_test_fixture",
        audit_id="T506",
    )

    assert target.identity == "localhost:55432/wolfystock_destructive_test_fixture"
    assert target.schema == "wolfystock_run_0123456789abcdef"
    assert "secret" not in target.audit_record()
    assert target.schema in target.scoped_dsn


def test_destructive_qualification_with_zero_nodes_fails(tmp_path: Path) -> None:
    result = _run_isolated_pytest(
        tmp_path,
        "def test_non_destructive():\n    assert True\n",
        "--allow-destructive-postgres",
        "-m",
        "destructive_postgres",
        "--destructive-postgres-audit",
        "T506",
        "--destructive-postgres-target",
        "localhost:55432/wolfystock_destructive_test_fixture",
        env={
            "POSTGRES_PHASE_A_REAL_DSN": (
                "postgresql://user:secret@localhost:55432/"
                "wolfystock_destructive_test_fixture"
            )
        },
    )

    assert result.returncode != 0
    assert "zero destructive PostgreSQL nodes" in (result.stdout + result.stderr)
