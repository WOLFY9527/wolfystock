"""Strict consumer browser qualification is owned by one canonical runner.

`apps/dsa-web/scripts/run-consumer-frontend-browser-qualification.sh` is the
repository-owned entrypoint for strict consumer browser qualification. These
checks execute that runner so the qualified matrix cannot silently regress to a
weaker selection (strict mode dropped, a single project, or a partial spec).

Playwright itself is not launched here: the pytest offline policy projects a
credential-free child environment, so browser collection and execution stay
owned by `./wolfy exec --profile test` plus the canonical runner.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_APP = REPO_ROOT / "apps" / "dsa-web"
RUNNER = WEB_APP / "scripts" / "run-consumer-frontend-browser-qualification.sh"
QUALIFICATION_SPEC = WEB_APP / "e2e" / "consumer-frontend-browser-qualification.spec.ts"
TOPOLOGY_MANIFEST = REPO_ROOT / "validation" / "domain_test_topology.json"

SPEC_NAME = "consumer-frontend-browser-qualification.spec.ts"
SPEC_PATH = f"apps/dsa-web/e2e/{SPEC_NAME}"
EXPECTED_PROJECTS = ["chromium", "chromium-mobile"]
CASE_COUNT_PER_PROJECT = 65
CANONICAL_MARKER = "WOLFYSTOCK_CONSUMER_BROWSER_QUALIFICATION_CANONICAL"


def _run_runner(arguments: list[str], environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(environment or {})
    return subprocess.run(
        ["bash", str(RUNNER), *arguments],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _inventoried_qualification_cases() -> list[dict[str, str]]:
    manifest = json.loads(TOPOLOGY_MANIFEST.read_text(encoding="utf-8"))
    return [case for case in manifest["playwright"]["projectCases"] if case["spec"] == SPEC_PATH]


def test_canonical_runner_plan_forces_strict_mode_and_both_consumer_projects() -> None:
    # A weak ambient value is deliberately supplied: the runner owns the matrix,
    # so the resolved plan must still be strict and must keep both projects.
    result = _run_runner(
        ["--print-plan"],
        {
            "STRICT_CONSUMER_FRONTEND_QUALIFICATION": "0",
            CANONICAL_MARKER: "0",
        },
    )

    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["strict"] == "1"
    assert plan["canonical"] == "1"
    assert plan["spec"] == SPEC_NAME
    assert plan["projects"] == EXPECTED_PROJECTS


def test_machine_authority_resolves_to_canonical_runner_without_stale_e2e_alias() -> None:
    manifest = json.loads(TOPOLOGY_MANIFEST.read_text(encoding="utf-8"))
    expected_gate = (
        "./wolfy exec --profile test -- bash "
        "apps/dsa-web/scripts/run-consumer-frontend-browser-qualification.sh"
    )
    assert expected_gate in manifest["authoritativeGates"]
    assert "cd apps/dsa-web && npm run test:e2e" not in manifest["authoritativeGates"]
    assert RUNNER.exists() and os.access(RUNNER, os.X_OK)


def test_canonical_runner_assigns_strict_markers_instead_of_defaulting_them() -> None:
    content = RUNNER.read_text(encoding="utf-8")

    assert "STRICT_CONSUMER_FRONTEND_QUALIFICATION=1" in content
    assert f"{CANONICAL_MARKER}=1" in content
    # A defaulted expansion would let a caller-supplied value win.
    assert "${STRICT_CONSUMER_FRONTEND_QUALIFICATION:-" not in content
    assert f"${{{CANONICAL_MARKER}:-" not in content


def test_canonical_runner_rejects_caller_supplied_matrix_weakening_flags() -> None:
    weakening_arguments = (
        ["--project=chromium"],
        ["--grep=home"],
        ["--config=playwright.other.config.ts"],
        ["--workers=8"],
        [SPEC_NAME],
    )

    for arguments in weakening_arguments:
        result = _run_runner(arguments)
        assert result.returncode == 2, (arguments, result.stdout, result.stderr)
        assert result.stdout == "", arguments


def test_canonical_runner_selects_the_complete_inventoried_consumer_matrix() -> None:
    result = _run_runner(["--print-plan"])
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)

    cases = _inventoried_qualification_cases()
    inventoried_projects = sorted({case["project"] for case in cases})

    # The canonical runner must select exactly the inventoried consumer
    # qualification matrix: one spec, both consumer projects, 65 cases each.
    assert plan["spec"] == SPEC_NAME
    assert inventoried_projects == EXPECTED_PROJECTS
    assert sorted(plan["projects"]) == inventoried_projects
    assert len(cases) == CASE_COUNT_PER_PROJECT * len(EXPECTED_PROJECTS) == 130


def test_consumer_qualification_spec_fails_closed_without_strict_mode() -> None:
    content = QUALIFICATION_SPEC.read_text(encoding="utf-8")

    # The canonical marker alone must never qualify a weaker matrix, so the
    # spec throws at load time when strict mode is missing.
    assert CANONICAL_MARKER in content
    assert "canonicalQualification && !strictQualification" in content
    assert "STRICT_CONSUMER_FRONTEND_QUALIFICATION" in content
    assert "throw new Error(" in content
