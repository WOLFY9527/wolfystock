from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

DOC_PATHS = (
    REPO_ROOT / "docs" / "audits" / "operator-evidence-dry-run-handoff.md",
    REPO_ROOT / "docs" / "audits" / "operator-evidence-real-runbook.md",
    REPO_ROOT / "docs" / "audits" / "operator-evidence-redaction-checklist.md",
    REPO_ROOT / "scripts" / "README.md",
)

EXPECTED_OFFLINE_CLI_SCRIPTS = (
    "scripts/operator_evidence_preflight.py",
    "scripts/operator_evidence_workflow_smoke.py",
    "scripts/operator_evidence_workflow_run.py",
    "scripts/operator_evidence_schema_reference.py",
    "scripts/operator_evidence_archive_pack.py",
    "scripts/operator_evidence_gap_analyzer.py",
    "scripts/operator_evidence_bundle_diff.py",
    "scripts/evidence_artifact_sanitize.py",
)

FORBIDDEN_APPROVAL_PHRASES = (
    "launch-approved",
    "production-ready",
    "automatic-go",
    "automatic go",
    "public launch go",
)

ABSOLUTE_LOCAL_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.-])/(?:Users|tmp|private|var/folders)/[^\s`\"']+"
)
REAL_URL_PATTERN = re.compile(r"\bhttps?://[^\s`\"']+", re.IGNORECASE)
URL_CREDENTIAL_PATTERN = re.compile(
    r"\b[a-z][a-z0-9+.-]*://[^\s<>\"'`]+:[^\s<>\"'`@]+@[^\s<>\"'`]+",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9_]{24,}|"
    r"(?:AKIA|ASIA)[0-9A-Z]{16})(?![A-Za-z0-9_])"
)
UNSAFE_PLACEHOLDER_PATTERN = re.compile(
    r"(<[^>\n]*(?:secret|token|password|credential|cookie|session|dsn|"
    r"database[-_ ]?url|private[-_ ]?key|provider[-_ ]?payload|raw[-_ ]?log|"
    r"request[-_ ]?body|response[-_ ]?body|email|webhook|url)[^>\n]*>"
    r"|\{\{[^}\n]*(?:secret|token|password|credential|cookie|session|dsn|"
    r"database[-_ ]?url|private[-_ ]?key|provider[-_ ]?payload|raw[-_ ]?log|"
    r"request[-_ ]?body|response[-_ ]?body|email|webhook|url)[^}\n]*\}\})",
    re.IGNORECASE,
)
SCRIPT_REF_PATTERN = re.compile(
    r"(?:scripts/|tests/)?[A-Za-z0-9_./-]+(?:\.py|\.sh)\b"
)
PYTHON_SCRIPT_COMMAND_PATTERN = re.compile(
    r"(?:^|\s)python3\s+(scripts/[A-Za-z0-9_./-]+\.py)\b"
)
FENCE_PATTERN = re.compile(r"```([A-Za-z0-9_-]*)\n(.*?)```", re.DOTALL)


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _read(path: Path) -> str:
    assert path.exists(), f"Expected docs target is missing: {_relative(path)}"
    return path.read_text(encoding="utf-8")


def _fenced_blocks(path: Path) -> list[tuple[int, str, str]]:
    text = _read(path)
    blocks: list[tuple[int, str, str]] = []
    for match in FENCE_PATTERN.finditer(text):
        line_number = text.count("\n", 0, match.start()) + 1
        blocks.append((line_number, match.group(1).lower(), match.group(2)))
    return blocks


def _referenced_script_paths(path: Path) -> set[str]:
    scripts: set[str] = set()
    for match in SCRIPT_REF_PATTERN.finditer(_read(path)):
        script = match.group(0)
        if script.startswith("tests/"):
            scripts.add(script)
            continue
        if not script.startswith("scripts/"):
            script = f"scripts/{script}"
        scripts.add(script)
    return scripts


def _command_script_paths(path: Path) -> set[str]:
    scripts: set[str] = set()
    for _line_number, lang, block in _fenced_blocks(path):
        if lang and lang not in {"bash", "sh", "shell", "text"}:
            continue
        scripts.update(PYTHON_SCRIPT_COMMAND_PATTERN.findall(block))
    return scripts


def _run_help(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / script), "--help"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={},
    )


def _assert_bounded_output(text: str, script: str) -> None:
    assert len(text) <= 16_000, script
    for line in text.splitlines():
        assert len(line) <= 320, script


def _assert_no_forbidden_approval_wording(text: str, label: str) -> None:
    lowered = text.lower()
    for phrase in FORBIDDEN_APPROVAL_PHRASES:
        assert phrase not in lowered, label


def test_operator_evidence_docs_reference_existing_scripts() -> None:
    missing: list[str] = []

    for path in DOC_PATHS:
        for script in sorted(_referenced_script_paths(path)):
            if not (REPO_ROOT / script).exists():
                missing.append(f"{_relative(path)} references missing {script}")

    for script in EXPECTED_OFFLINE_CLI_SCRIPTS:
        if not (REPO_ROOT / script).exists():
            missing.append(f"expected offline CLI is missing: {script}")

    assert not missing, "Missing operator evidence script references:\n" + "\n".join(missing)


def test_operator_evidence_command_scripts_support_safe_help() -> None:
    scripts = set(EXPECTED_OFFLINE_CLI_SCRIPTS)
    for path in DOC_PATHS:
        scripts.update(_command_script_paths(path))

    failures: list[str] = []
    for script in sorted(scripts):
        result = _run_help(script)
        combined = result.stdout + result.stderr
        if result.returncode != 0:
            failures.append(f"{script} --help exited {result.returncode}")
            continue
        try:
            _assert_bounded_output(combined, script)
            _assert_no_forbidden_approval_wording(combined, script)
        except AssertionError as exc:
            failures.append(str(exc) or script)
        if "traceback" in combined.lower():
            failures.append(f"{script} --help printed traceback")

    assert not failures, "Unsafe operator evidence CLI help output:\n" + "\n".join(failures)


def test_operator_evidence_command_examples_use_safe_placeholders() -> None:
    findings: list[str] = []

    for path in DOC_PATHS:
        for line_number, lang, block in _fenced_blocks(path):
            if lang and lang not in {"bash", "sh", "shell"}:
                continue
            label = f"{_relative(path)}:{line_number}"
            checks = (
                ("absolute local path", ABSOLUTE_LOCAL_PATH_PATTERN),
                ("real URL", REAL_URL_PATTERN),
                ("URL credentials", URL_CREDENTIAL_PATTERN),
                ("secret-looking value", SECRET_VALUE_PATTERN),
                ("unsafe placeholder", UNSAFE_PLACEHOLDER_PATTERN),
            )
            for reason, pattern in checks:
                if pattern.search(block):
                    findings.append(f"{label} [{reason}]")
            _assert_no_forbidden_approval_wording(block, label)

    assert not findings, "Unsafe operator evidence command examples:\n" + "\n".join(findings)
