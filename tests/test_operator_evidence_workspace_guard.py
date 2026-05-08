from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

LOCAL_ONLY_WORKSPACE_PATHS = (
    "operator-evidence-local/provider/sanitized-review.json",
    "evidence-artifacts-local/operator-intake/redacted-copy.json",
    "release-review-local/workflow-output/bundle-summary.json",
)

TRACKABLE_FIXTURE_PATHS = (
    "tests/fixtures/operator_evidence/sanitized_complete/security_operator_acceptance.json",
    "tests/fixtures/operator_evidence/unsafe_rejected/provider_operator_evidence.json",
)


def _check_ignore(*paths: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "check-ignore", "--stdin"],
        input="\n".join(paths) + "\n",
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _check_ignore_no_index(path: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "check-ignore", "--no-index", path],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_local_operator_evidence_workspace_paths_are_ignored() -> None:
    result = _check_ignore(*LOCAL_ONLY_WORKSPACE_PATHS)

    assert result.returncode == 0, result.stderr
    assert set(result.stdout.splitlines()) == set(LOCAL_ONLY_WORKSPACE_PATHS)


def test_committed_operator_evidence_fixtures_remain_trackable() -> None:
    tracked = subprocess.run(
        ["git", "ls-files", *TRACKABLE_FIXTURE_PATHS],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert tracked.returncode == 0, tracked.stderr
    assert set(tracked.stdout.splitlines()) == set(TRACKABLE_FIXTURE_PATHS)

    for path in TRACKABLE_FIXTURE_PATHS:
        result = _check_ignore_no_index(path)
        assert result.returncode == 1, result.stdout
