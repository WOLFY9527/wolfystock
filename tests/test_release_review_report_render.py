from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "release_review_report_render.py"


FORBIDDEN_PHRASES = (
    "launch-approved",
    "production-ready",
    "automatic-go",
    "automatic go",
)


def _bundle_summary(*, status: str, artifact_statuses: dict[str, str] | None = None) -> dict[str, object]:
    statuses = artifact_statuses or {
        "provider": "accepted",
        "restore-pitr": "accepted",
        "security": "needs-review",
    }
    return {
        "schemaVersion": "wolfystock_operator_evidence_bundle_summary_v1",
        "generatedAt": "2026-05-08T10:30:00+00:00",
        "artifactDirectoryLabel": "operator-bundle-20260508",
        "bundleStatus": status,
        "runtimeBehaviorChanged": False,
        "networkCallsExecutedByValidator": False,
        "rawArtifactBodiesIncluded": False,
        "artifacts": [
            {
                "category": category,
                "pathLabel": f"{category}.json",
                "status": artifact_status,
                "validatorName": f"{category}_check.py",
                "blockingReasonSummaries": (
                    ["manual_operator_review_required"] if artifact_status == "needs-review" else []
                ),
            }
            for category, artifact_status in statuses.items()
        ],
        "advisories": [
            {
                "category": "unknown-extra-artifact",
                "pathLabel": "unexpected.json",
                "status": "needs-review",
                "validatorName": "operator_evidence_bundle_check.py",
                "blockingReasonSummaries": ["unknown_artifact_not_validated"],
            }
        ],
    }


def _manifest_summary() -> dict[str, object]:
    return {
        "schemaVersion": "wolfystock_operator_evidence_manifest_summary_v1",
        "manifestStatus": "needs-review",
        "artifactCount": 3,
        "checksumAlgorithm": "sha256",
        "checksumStatus": "complete",
        "blockingReasonSummaries": ["manifest_manual_review_required"],
    }


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run_renderer(
    tmp_path: Path,
    bundle: dict[str, object],
    *,
    manifest: dict[str, object] | None = None,
    label: str | None = None,
    sha: str | None = None,
) -> subprocess.CompletedProcess[str]:
    bundle_path = _write_json(tmp_path / "bundle-summary.json", bundle)
    args = [sys.executable, str(SCRIPT), str(bundle_path)]
    if manifest is not None:
        args.extend(["--manifest", str(_write_json(tmp_path / "manifest-summary.json", manifest))])
    if label is not None:
        args.extend(["--release-candidate-label", label])
    if sha is not None:
        args.extend(["--release-candidate-sha", sha])
    return subprocess.run(args, cwd=REPO_ROOT, text=True, capture_output=True, check=False)


def _assert_forbidden_phrases_absent(markdown: str) -> None:
    lowered = markdown.lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in lowered


def test_complete_review_required_summary_renders_manual_review_report(tmp_path: Path) -> None:
    result = _run_renderer(
        tmp_path,
        _bundle_summary(status="complete-review-required"),
        manifest=_manifest_summary(),
        label="rc-2026-05-08",
        sha="45c8a18114890e2abe3d503c82022be7ee3fb47c",
    )

    assert result.returncode == 0
    assert "# Offline Release Review Report" in result.stdout
    assert "rc-2026-05-08" in result.stdout
    assert "45c8a18114890e2abe3d503c82022be7ee3fb47c" in result.stdout
    assert "complete-review-required" in result.stdout
    assert "| provider | accepted | provider.json | provider_check.py | none |" in result.stdout
    assert "Manual operator review is required before any release decision." in result.stdout
    assert "This report is informational only and does not approve launch." in result.stdout
    assert "manifest_manual_review_required" in result.stdout
    _assert_forbidden_phrases_absent(result.stdout)


def test_incomplete_bundle_renders_no_go_style_language(tmp_path: Path) -> None:
    result = _run_renderer(
        tmp_path,
        _bundle_summary(
            status="incomplete-no-go",
            artifact_statuses={
                "provider": "accepted",
                "quota-budget": "missing",
            },
        ),
    )

    assert result.returncode == 1
    assert "Bundle status: **incomplete-no-go**" in result.stdout
    assert "Current operator review posture: **NO-GO - incomplete evidence bundle**." in result.stdout
    assert "missing" in result.stdout
    _assert_forbidden_phrases_absent(result.stdout)


def test_rejected_bundle_renders_blocking_language(tmp_path: Path) -> None:
    result = _run_renderer(
        tmp_path,
        _bundle_summary(
            status="rejected-no-go",
            artifact_statuses={
                "restore-pitr": "rejected",
                "security": "accepted",
            },
        ),
    )

    assert result.returncode == 1
    assert "Current operator review posture: **NO-GO - blocking evidence rejection present**." in result.stdout
    assert "| restore-pitr | rejected | restore-pitr.json | restore-pitr_check.py | none |" in result.stdout
    _assert_forbidden_phrases_absent(result.stdout)


def test_unsafe_markers_in_input_are_not_emitted(tmp_path: Path) -> None:
    unsafe_value = "raw-secret-token=sk-live-should-not-leak"
    bundle = _bundle_summary(status="rejected-no-go")
    artifacts = bundle["artifacts"]
    assert isinstance(artifacts, list)
    artifacts.append(
        {
            "category": unsafe_value,
            "pathLabel": "../session-cookie-dump.json",
            "status": "rejected",
            "validatorName": "traceback_secret_validator.py",
            "blockingReasonSummaries": [unsafe_value, "stack trace contains password"],
        }
    )

    result = _run_renderer(tmp_path, bundle)

    assert result.returncode == 1
    assert unsafe_value not in result.stdout
    assert "session-cookie" not in result.stdout
    assert "traceback" not in result.stdout.lower()
    assert "password" not in result.stdout.lower()
    assert "[redacted]" in result.stdout
    _assert_forbidden_phrases_absent(result.stdout)


def test_report_never_says_approval_phrases(tmp_path: Path) -> None:
    result = _run_renderer(
        tmp_path,
        _bundle_summary(
            status="complete-review-required",
            artifact_statuses={
                "provider": "accepted",
                "security": "accepted",
            },
        ),
    )

    assert result.returncode == 0
    _assert_forbidden_phrases_absent(result.stdout)
