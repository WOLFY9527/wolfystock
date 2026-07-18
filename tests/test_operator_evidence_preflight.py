from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "operator_evidence_preflight.py"
SANITIZED_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "operator_evidence" / "sanitized_complete"
UNSAFE_FIXTURE_VALUES = (
    "fixture-unsafe-api-key-value-should-not-leak",
    "fixture-unsafe-raw-response-value-should-not-leak",
    "token=preflight-secret-value-should-not-leak",
)
FORBIDDEN_APPROVAL_PHRASES = (
    "launch-approved",
    "production-ready",
    "automatic-go",
    "automatic go",
    "public launch go",
    "go for launch",
    "approved for launch",
    "release-approved",
)


def _run_preflight(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={},
    )


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("operator_evidence_preflight", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _combined(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout + result.stderr


def _assert_bounded_output(text: str) -> None:
    assert len(text) <= 20_000
    for line in text.splitlines():
        assert len(line) <= 360


def _assert_no_forbidden_or_raw_values(text: str) -> None:
    lowered = text.lower()
    for phrase in FORBIDDEN_APPROVAL_PHRASES:
        assert phrase not in lowered
    for unsafe_value in UNSAFE_FIXTURE_VALUES:
        assert unsafe_value not in text
    assert "rawArtifactBodiesIncluded\": true" not in text
    assert "traceback" not in lowered


def test_synthetic_preflight_passes_with_review_required_non_approval_summary() -> None:
    result = _run_preflight("--synthetic")

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["schemaVersion"] == "wolfystock_operator_evidence_preflight_v1"
    assert summary["preflightStatus"] == "preflight-pass-review-required"
    assert summary["manualReviewRequired"] is True
    assert summary["releaseApproved"] is False
    assert summary["launchApproved"] is False
    assert summary["runtimeBehaviorChanged"] is False
    assert summary["networkCallsExecuted"] is False
    assert summary["rawArtifactBodiesIncluded"] is False
    assert {check["id"] for check in summary["checks"]} == {
        "workflow-smoke",
        "docs-safety-guard",
        "evidence-gap-analysis",
        "fixture-pack-validation",
    }
    assert {check["status"] for check in summary["checks"]} == {"pass"}
    _assert_bounded_output(result.stdout)
    _assert_no_forbidden_or_raw_values(_combined(result))


def test_artifact_dir_mode_adds_local_workflow_check_without_approving_launch() -> None:
    result = _run_preflight("--synthetic", "--artifact-dir", SANITIZED_FIXTURE)

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["preflightStatus"] == "preflight-pass-review-required"
    assert summary["releaseApproved"] is False
    assert summary["launchApproved"] is False
    assert "local-artifact-workflow" in {check["id"] for check in summary["checks"]}
    assert all(check["status"] == "pass" for check in summary["checks"])
    _assert_bounded_output(result.stdout)
    _assert_no_forbidden_or_raw_values(_combined(result))


def test_preflight_failure_summary_is_bounded_and_does_not_echo_command_output(tmp_path: Path) -> None:
    module = _load_module()
    check = module.CheckSpec(
        check_id="forced-failure",
        command=(
            sys.executable,
            "-c",
            "import sys; print('token=preflight-secret-value-should-not-leak'); sys.exit(7)",
        ),
    )

    exit_code, summary = module.run_preflight((check,), temp_root=tmp_path)

    rendered = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)
    assert exit_code == 1
    assert summary["preflightStatus"] == "preflight-fail-review-required"
    assert summary["releaseApproved"] is False
    assert summary["launchApproved"] is False
    assert summary["checks"] == [
        {
            "id": "forced-failure",
            "status": "fail",
            "exitCode": 7,
            "failureSummary": "exit_code_7",
        }
    ]
    _assert_bounded_output(rendered)
    _assert_no_forbidden_or_raw_values(rendered)


def test_preflight_requires_synthetic_acknowledgement() -> None:
    result = _run_preflight()

    assert result.returncode != 0
    _assert_bounded_output(_combined(result))
    _assert_no_forbidden_or_raw_values(_combined(result))
