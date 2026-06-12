"""Shared test helpers for subprocess-backed evidence validators."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Callable, cast


WriteJson = Callable[[Path, object], Path]
RunValidator = Callable[[Path], subprocess.CompletedProcess[str]]


def write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def run_validator(script: Path, artifact_path: Path, *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), str(artifact_path)],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def stdout_json(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return cast(dict[str, object], json.loads(result.stdout))


def make_cli_validator(script: Path, *, cwd: Path, artifact_name: str) -> tuple[WriteJson, RunValidator]:
    def write_tmp_json(tmp_path: Path, payload: object) -> Path:
        return write_json(tmp_path / artifact_name, payload)

    def run_cli_validator(path: Path) -> subprocess.CompletedProcess[str]:
        return run_validator(script, path, cwd=cwd)

    return write_tmp_json, run_cli_validator
