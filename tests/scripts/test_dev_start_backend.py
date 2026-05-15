# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "dev_start_backend.sh"


def test_dev_start_backend_help_runs_directly() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--help"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert "--restart-port" in result.stdout


def test_dev_start_backend_script_avoids_sourcing_env_and_prefers_repo_python() -> None:
    content = SCRIPT_PATH.read_text(encoding="utf-8")

    assert re.search(r'(^|\n)\s*(source|\.)\s+["\']?\.env(["\']|\s|$)', content) is None
    assert ".venv/bin/python" in content
    assert "main.py --serve-only" in content


def test_dev_start_backend_script_avoids_secret_dump_patterns() -> None:
    content = SCRIPT_PATH.read_text(encoding="utf-8")

    for banned in ("printenv", "env |", "set -x"):
        assert banned not in content
