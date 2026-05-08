from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

CLI_SCRIPTS = (
    "scripts/evidence_artifact_sanitize.py",
    "scripts/operator_evidence_template_pack.py",
    "scripts/operator_evidence_manifest_check.py",
    "scripts/operator_evidence_bundle_check.py",
    "scripts/operator_evidence_workflow_run.py",
    "scripts/operator_evidence_workflow_smoke.py",
    "scripts/operator_evidence_archive_pack.py",
    "scripts/operator_evidence_bundle_diff.py",
    "scripts/operator_evidence_schema_reference.py",
    "scripts/operator_evidence_preflight.py",
    "scripts/release_review_report_render.py",
)
MISSING_REQUIRED_ARG_SCRIPTS = tuple(
    script for script in CLI_SCRIPTS if script != "scripts/operator_evidence_workflow_smoke.py"
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
UNSAFE_VALUE = "token=cli-contract-secret-value-should-not-leak"


def _run(script: str, *args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / script), *map(str, args)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={},
    )


def _combined(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout + result.stderr


def _assert_bounded_output(text: str) -> None:
    assert len(text) <= 16_000
    for line in text.splitlines():
        assert len(line) <= 320


def _assert_no_forbidden_approval_wording(text: str) -> None:
    lowered = text.lower()
    for phrase in FORBIDDEN_APPROVAL_PHRASES:
        assert phrase not in lowered


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _bundle_summary(status: str = "complete-review-required") -> dict[str, object]:
    return {
        "schemaVersion": "wolfystock_operator_evidence_bundle_summary_v1",
        "generatedAt": "2026-05-08T10:30:00+00:00",
        "artifactDirectoryLabel": "operator-bundle",
        "bundleStatus": status,
        "runtimeBehaviorChanged": False,
        "networkCallsExecutedByValidator": False,
        "rawArtifactBodiesIncluded": False,
        "artifacts": [
            {
                "category": "provider",
                "pathLabel": "provider_operator_evidence.json",
                "status": "accepted",
                "validatorName": "provider_operator_evidence_check.py",
                "blockingReasonSummaries": [],
            }
        ],
        "advisories": [],
    }


def _workflow_output(path: Path) -> Path:
    path.mkdir(parents=True)
    _write_json(path / "bundle-summary.json", _bundle_summary())
    _write_json(
        path / "evidence-manifest.json",
        {
            "schemaVersion": "wolfystock_operator_evidence_manifest_v1",
            "generatedAt": "2026-05-08T10:30:00+00:00",
            "artifactDirectoryLabel": "operator-bundle",
            "entries": [],
        },
    )
    (path / "release-review-report.md").write_text(
        "# Offline Release Review Report\n\nManual operator review is required before any release decision.\n",
        encoding="utf-8",
    )
    return path


def test_evidence_cli_help_is_successful_bounded_and_free_of_forbidden_approval_wording() -> None:
    for script in CLI_SCRIPTS:
        result = _run(script, "--help")
        combined = _combined(result)

        assert result.returncode == 0, script
        _assert_bounded_output(combined)
        _assert_no_forbidden_approval_wording(combined)
        assert "traceback" not in combined.lower()


def test_evidence_cli_missing_required_args_fail_with_bounded_operator_errors() -> None:
    for script in MISSING_REQUIRED_ARG_SCRIPTS:
        result = _run(script)
        combined = _combined(result)

        assert result.returncode != 0, script
        _assert_bounded_output(combined)
        _assert_no_forbidden_approval_wording(combined)
        assert "traceback" not in combined.lower()


def test_sanitizer_missing_unsafe_input_label_does_not_leak_raw_value(tmp_path: Path) -> None:
    missing = tmp_path / f"{UNSAFE_VALUE}.json"

    result = _run(
        "scripts/evidence_artifact_sanitize.py",
        "scan",
        "--input",
        missing,
        "--fail-on-findings",
    )

    combined = _combined(result)
    assert result.returncode != 0
    assert UNSAFE_VALUE not in combined
    _assert_bounded_output(combined)


def test_manifest_missing_unsafe_manifest_label_does_not_leak_raw_value(tmp_path: Path) -> None:
    artifact_dir = tmp_path / f"artifacts-{UNSAFE_VALUE}"
    manifest = tmp_path / f"manifest-{UNSAFE_VALUE}.json"

    result = _run(
        "scripts/operator_evidence_manifest_check.py",
        "verify",
        "--artifact-dir",
        artifact_dir,
        "--manifest",
        manifest,
    )

    combined = _combined(result)
    assert result.returncode != 0
    assert UNSAFE_VALUE not in combined
    _assert_bounded_output(combined)


def test_bundle_check_missing_unsafe_artifact_dir_label_does_not_leak_raw_value(tmp_path: Path) -> None:
    artifact_dir = tmp_path / f"bundle-{UNSAFE_VALUE}"

    result = _run("scripts/operator_evidence_bundle_check.py", artifact_dir)

    combined = _combined(result)
    assert result.returncode != 0
    assert UNSAFE_VALUE not in combined
    _assert_bounded_output(combined)


def test_workflow_report_unsafe_bundle_status_does_not_leak_raw_value(tmp_path: Path) -> None:
    bundle_summary = _write_json(
        tmp_path / "bundle-summary.json",
        _bundle_summary(status=f"rejected-no-go-{UNSAFE_VALUE}"),
    )

    result = _run(
        "scripts/operator_evidence_workflow_run.py",
        "report",
        "--bundle-summary",
        bundle_summary,
        "--output",
        tmp_path / "review.md",
    )

    combined = _combined(result) + (tmp_path / "review.md").read_text(encoding="utf-8")
    assert result.returncode != 0
    assert UNSAFE_VALUE not in combined
    _assert_bounded_output(combined)


def test_workflow_smoke_success_uses_bounded_output_dir_label(tmp_path: Path) -> None:
    output_dir = tmp_path / f"smoke-{UNSAFE_VALUE}"

    result = _run(
        "scripts/operator_evidence_workflow_smoke.py",
        "--output-dir",
        output_dir,
        "--skip-unsafe-check",
    )

    combined = _combined(result)
    assert result.returncode == 0, result.stderr
    assert UNSAFE_VALUE not in combined
    assert "smokeStatus=pass" in combined
    _assert_bounded_output(combined)
    _assert_no_forbidden_approval_wording(combined)


def test_successful_cli_paths_keep_review_required_non_approval_language(tmp_path: Path) -> None:
    sanitizer_input = _write_json(tmp_path / "artifact.json", {"operatorConclusion": "needs-review"})
    sanitizer_output = tmp_path / "artifact.sanitized.json"
    sanitizer = _run(
        "scripts/evidence_artifact_sanitize.py",
        "sanitize",
        "--input",
        sanitizer_input,
        "--output",
        sanitizer_output,
    )
    template = _run("scripts/operator_evidence_template_pack.py", "--stdout", "--category", "config-snapshot")
    workflow_init = _run("scripts/operator_evidence_workflow_run.py", "init", "--output-dir", tmp_path / "templates")

    bundle_path = _write_json(tmp_path / "bundle-summary.json", _bundle_summary())
    before_path = _write_json(tmp_path / "before-summary.json", _bundle_summary())
    after_path = _write_json(tmp_path / "after-summary.json", _bundle_summary())
    report = _run("scripts/release_review_report_render.py", bundle_path)
    diff = _run("scripts/operator_evidence_bundle_diff.py", "diff", "--before", before_path, "--after", after_path)

    schema_output = tmp_path / "schema.md"
    schema = _run("scripts/operator_evidence_schema_reference.py", "render", "--output", schema_output)

    workflow_output = _workflow_output(tmp_path / "workflow-output")
    archive = _run(
        "scripts/operator_evidence_archive_pack.py",
        "pack",
        "--workflow-output-dir",
        workflow_output,
        "--output-dir",
        tmp_path / "archive",
    )

    results = (sanitizer, template, workflow_init, report, diff, schema, archive)
    for result in results:
        assert result.returncode == 0, result.stderr
    combined = (
        "".join(_combined(result) for result in results)
        + sanitizer_output.read_text(encoding="utf-8")
        + schema_output.read_text(encoding="utf-8")
        + (tmp_path / "archive" / "archive-index.json").read_text(encoding="utf-8")
    )
    assert "needs-review" in combined
    assert "manual review required" in combined.lower()
    assert "releaseApproved=false" in combined
    assert "releaseApproved" in combined
    _assert_no_forbidden_approval_wording(combined)
    _assert_bounded_output(combined)
