# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "dev_start_backend.sh"


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT_PATH), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_dev_start_backend_help_runs_directly() -> None:
    result = run_script("--help")

    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert "--print-command" in result.stdout
    assert "--restart-port" in result.stdout


def test_dev_start_backend_print_command_handles_empty_extra_args() -> None:
    result = run_script("--print-command")

    assert result.returncode == 0
    assert "unbound variable" not in result.stderr
    assert "--serve-only" in result.stdout
    assert "--host 127.0.0.1 --port 8000" in result.stdout


def test_dev_start_backend_script_avoids_sourcing_env_and_prefers_repo_python() -> None:
    content = SCRIPT_PATH.read_text(encoding="utf-8")

    assert re.search(r'(^|\n)\s*(source|\.)\s+["\']?\.env(["\']|\s|$)', content) is None
    assert ".venv/bin/python" in content
    assert "main.py --serve-only" in content


def test_dev_start_backend_initializes_and_safely_expands_optional_args() -> None:
    content = SCRIPT_PATH.read_text(encoding="utf-8")

    init_match = re.search(r"^EXTRA_ARGS=\(\)$", content, re.MULTILINE)
    safe_expand_match = re.search(
        r'if\s+\(\(\s*\$\{#EXTRA_ARGS\[@\]\}\s*>\s*0\s*\)\);\s*then\s+'
        r'COMMAND\+=\("\$\{EXTRA_ARGS\[@\]\}"\)\s+fi',
        content,
        re.MULTILINE,
    )

    assert init_match is not None
    assert safe_expand_match is not None
    assert init_match.start() < safe_expand_match.start()


def test_dev_start_backend_script_avoids_secret_dump_patterns() -> None:
    content = SCRIPT_PATH.read_text(encoding="utf-8")

    for banned in ("printenv", "env |", "set -x"):
        assert banned not in content
