from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "operator_evidence_bundle_diff.py"

FORBIDDEN_PHRASES = (
    "launch-approved",
    "production-ready",
    "automatic-go",
    "automatic go",
    "public launch go",
)


def _bundle_summary(
    *,
    bundle_status: str = "complete-review-required",
    statuses: dict[str, str] | None = None,
    reasons: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    category_statuses = statuses or {
        "provider": "accepted",
        "restore-pitr": "accepted",
        "security": "accepted",
    }
    reason_map = reasons or {}
    return {
        "schemaVersion": "wolfystock_operator_evidence_bundle_summary_v1",
        "generatedAt": "2026-05-08T10:30:00+00:00",
        "artifactDirectoryLabel": "operator-bundle-20260508",
        "bundleStatus": bundle_status,
        "runtimeBehaviorChanged": False,
        "networkCallsExecutedByValidator": False,
        "rawArtifactBodiesIncluded": False,
        "artifacts": [
            {
                "category": category,
                "pathLabel": f"{category}.json",
                "status": status,
                "validatorName": f"{category}_check.py",
                "blockingReasonSummaries": reason_map.get(category, []),
            }
            for category, status in category_statuses.items()
        ],
        "advisories": [],
    }


def _manifest(entries: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schemaVersion": "wolfystock_operator_evidence_manifest_v1",
        "generatedAt": "2026-05-08T10:30:00+00:00",
        "artifactDirectoryLabel": "operator-bundle-20260508",
        "entries": entries,
    }


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run_diff(
    tmp_path: Path,
    before: dict[str, object],
    after: dict[str, object],
    *,
    before_manifest: dict[str, object] | None = None,
    after_manifest: dict[str, object] | None = None,
    output: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    args = [
        sys.executable,
        str(SCRIPT),
        "diff",
        "--before",
        str(_write_json(tmp_path / "before-summary.json", before)),
        "--after",
        str(_write_json(tmp_path / "after-summary.json", after)),
    ]
    if before_manifest is not None:
        args.extend(["--before-manifest", str(_write_json(tmp_path / "before-manifest.json", before_manifest))])
    if after_manifest is not None:
        args.extend(["--after-manifest", str(_write_json(tmp_path / "after-manifest.json", after_manifest))])
    if output is not None:
        args.extend(["--output", str(output)])
    return subprocess.run(args, cwd=REPO_ROOT, text=True, capture_output=True, check=False)


def _assert_forbidden_phrases_absent(markdown: str) -> None:
    lowered = markdown.lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in lowered


def test_improved_bundle_shows_resolved_blockers(tmp_path: Path) -> None:
    before = _bundle_summary(
        bundle_status="rejected-no-go",
        statuses={"provider": "accepted", "restore-pitr": "rejected", "security": "needs-review"},
        reasons={"restore-pitr": ["operator_outcome_is_accepted:fail"], "security": ["manual_review_required"]},
    )
    after = _bundle_summary(
        statuses={"provider": "accepted", "restore-pitr": "accepted", "security": "accepted"},
    )

    result = _run_diff(tmp_path, before, after)

    assert result.returncode == 0
    assert "Blocking count: `2` -> `0` (`-2`)" in result.stdout
    assert "restore-pitr: `rejected` -> `accepted`" in result.stdout
    assert "security: `needs-review` -> `accepted`" in result.stdout
    assert "Manual operator review is required before any release decision." in result.stdout
    assert "This diff is informational only and does not approve launch, deployment, or production operation." in result.stdout
    _assert_forbidden_phrases_absent(result.stdout)


def test_regression_bundle_shows_new_blockers(tmp_path: Path) -> None:
    before = _bundle_summary(statuses={"provider": "accepted", "restore-pitr": "accepted"})
    after = _bundle_summary(
        bundle_status="rejected-no-go",
        statuses={"provider": "accepted", "restore-pitr": "rejected", "quota-budget": "missing"},
        reasons={"restore-pitr": ["validator_rejected_artifact"], "quota-budget": ["required_artifact_missing"]},
    )

    result = _run_diff(tmp_path, before, after)

    assert result.returncode == 0
    assert "Added categories: `quota-budget`" in result.stdout
    assert "Blocking count: `0` -> `2` (`+2`)" in result.stdout
    assert "restore-pitr: `accepted` -> `rejected`" in result.stdout
    assert "quota-budget: `missing`; reasons: required_artifact_missing" in result.stdout
    _assert_forbidden_phrases_absent(result.stdout)


def test_manifest_checksum_change_is_summarized_without_raw_content(tmp_path: Path) -> None:
    before_manifest = _manifest(
        [
            {
                "category": "provider",
                "fileLabel": "provider_operator_evidence.json",
                "sha256": "a" * 64,
                "byteSize": 101,
                "generatedAt": "2026-05-08T10:30:00+00:00",
                "validatorName": "provider_operator_evidence_check.py",
            }
        ]
    )
    after_manifest = _manifest(
        [
            {
                "category": "provider",
                "fileLabel": "provider_operator_evidence.json",
                "sha256": "b" * 64,
                "byteSize": 202,
                "generatedAt": "2026-05-08T10:35:00+00:00",
                "validatorName": "provider_operator_evidence_check.py",
                "rawBody": "secret-artifact-body-should-not-leak",
            }
        ]
    )

    result = _run_diff(
        tmp_path,
        _bundle_summary(),
        _bundle_summary(),
        before_manifest=before_manifest,
        after_manifest=after_manifest,
    )

    assert result.returncode == 0
    assert "provider_operator_evidence.json: checksum changed" in result.stdout
    assert "secret-artifact-body-should-not-leak" not in result.stdout
    assert "rawBody" not in result.stdout
    assert "a" * 64 not in result.stdout
    assert "b" * 64 not in result.stdout


def test_unsafe_marker_values_are_redacted(tmp_path: Path) -> None:
    unsafe_value = "raw-secret-token=sk-live-should-not-leak"
    before = _bundle_summary(statuses={"provider": "accepted"})
    after = _bundle_summary(
        bundle_status="rejected-no-go",
        statuses={unsafe_value: "rejected"},
        reasons={unsafe_value: [unsafe_value, "stack trace contains password"]},
    )

    result = _run_diff(tmp_path, before, after)

    assert result.returncode == 0
    assert unsafe_value not in result.stdout
    assert "stack trace" not in result.stdout.lower()
    assert "password" not in result.stdout.lower()
    assert "[redacted]" in result.stdout


def test_output_never_uses_approval_wording_and_output_file_matches_stdout(tmp_path: Path) -> None:
    output = tmp_path / "review-diff.md"

    result = _run_diff(
        tmp_path,
        _bundle_summary(),
        _bundle_summary(bundle_status="complete-review-required"),
        output=output,
    )

    assert result.returncode == 0
    assert output.read_text(encoding="utf-8") == result.stdout
    _assert_forbidden_phrases_absent(result.stdout)
