from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "operator_evidence_archive_pack.py"

FORBIDDEN_APPROVAL_PHRASES = (
    "launch-" + "approved",
    "production-" + "ready",
    "automatic-" + "go",
    "automatic " + "go",
    "public launch " + "go",
)
RAW_BODY_SENTINEL = "SENTINEL_RAW_BODY_VALUE_NEVER_ARCHIVED_20260508"


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _bundle_summary(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schemaVersion": "wolfystock_operator_evidence_bundle_summary_v1",
        "generatedAt": "2026-05-08T10:30:00+00:00",
        "artifactDirectoryLabel": "operator-bundle-20260508",
        "bundleStatus": "complete-review-required",
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
    payload.update(overrides)
    return payload


def _workflow_output(path: Path, *, include_report: bool = True, include_manifest: bool = True) -> Path:
    path.mkdir(parents=True)
    _write_json(path / "bundle-summary.json", _bundle_summary())
    if include_manifest:
        _write_json(
            path / "evidence-manifest.json",
            {
                "schemaVersion": "wolfystock_operator_evidence_manifest_v1",
                "generatedAt": "2026-05-08T10:30:00+00:00",
                "artifactDirectoryLabel": "operator-bundle-20260508",
                "entries": [],
            },
        )
    if include_report:
        (path / "release-review-report.md").write_text(
            "# Offline Release Review Report\n\nManual operator review is required before any release decision.\n",
            encoding="utf-8",
        )
    return path


def _run_pack(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={},
    )


def _read_index(output_dir: Path) -> dict[str, Any]:
    return json.loads((output_dir / "archive-index.json").read_text(encoding="utf-8"))


def _assert_forbidden_approval_phrases_absent(text: str) -> None:
    lowered = text.lower()
    for phrase in FORBIDDEN_APPROVAL_PHRASES:
        assert phrase not in lowered


def test_pack_copies_known_workflow_outputs_and_indexes_hashes(tmp_path: Path) -> None:
    workflow_output = _workflow_output(tmp_path / "workflow-output")
    (workflow_output / "review-diff.md").write_text(
        "# Offline Evidence Bundle Review Diff\n\nManual operator review is required.\n",
        encoding="utf-8",
    )
    archive_dir = tmp_path / "archive"

    result = _run_pack(
        "pack",
        "--workflow-output-dir",
        workflow_output,
        "--output-dir",
        archive_dir,
        "--label",
        "operator-evidence-20260508",
        "--include-manifest",
        "--include-report",
    )

    assert result.returncode == 0, result.stderr
    assert {path.name for path in archive_dir.iterdir()} == {
        "archive-index.json",
        "bundle-summary.json",
        "evidence-manifest.json",
        "release-review-report.md",
        "review-diff.md",
    }
    index = _read_index(archive_dir)
    assert index["archiveLabel"] == "operator-evidence-20260508"
    assert index["manualReviewRequired"] is True
    assert index["releaseApproved"] is False
    assert index["reviewStatus"] == "complete-review-required"
    included = {item["fileLabel"]: item for item in index["includedFiles"]}
    assert set(included) == {
        "bundle-summary.json",
        "evidence-manifest.json",
        "release-review-report.md",
        "review-diff.md",
    }
    for item in included.values():
        assert item["byteSize"] > 0
        assert len(item["sha256"]) == 64


def test_pack_rejects_raw_artifact_source_dirs(tmp_path: Path) -> None:
    source_dir = tmp_path / "sanitized-artifacts"
    source_dir.mkdir()
    _write_json(source_dir / "provider_operator_evidence.json", {"operatorOutcome": "accepted"})
    archive_dir = tmp_path / "archive"

    result = _run_pack("pack", "--workflow-output-dir", source_dir, "--output-dir", archive_dir)

    assert result.returncode != 0
    assert "source_artifact_dir_rejected" in result.stderr
    assert not (archive_dir / "archive-index.json").exists()


def test_pack_rejects_path_traversal(tmp_path: Path) -> None:
    workflow_output = _workflow_output(tmp_path / "workflow-output")
    archive_dir = tmp_path / "archive"

    result = _run_pack(
        "pack",
        "--workflow-output-dir",
        workflow_output,
        "--output-dir",
        archive_dir,
        "--label",
        "../operator-evidence",
    )

    assert result.returncode != 0
    assert "unsafe_label" in result.stderr
    assert not (archive_dir / "archive-index.json").exists()


def test_pack_rejects_unknown_raw_json_outputs(tmp_path: Path) -> None:
    workflow_output = _workflow_output(tmp_path / "workflow-output")
    _write_json(workflow_output / "raw-provider-payload.json", {"rawResponseBody": RAW_BODY_SENTINEL})

    result = _run_pack("pack", "--workflow-output-dir", workflow_output, "--output-dir", tmp_path / "archive")

    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "unknown_json_output_rejected" in combined
    assert RAW_BODY_SENTINEL not in combined


def test_archive_index_does_not_leak_raw_body_values(tmp_path: Path) -> None:
    workflow_output = _workflow_output(tmp_path / "workflow-output", include_report=False, include_manifest=False)
    _write_json(
        workflow_output / "bundle-summary.json",
        _bundle_summary(rawArtifactBodyForTest=RAW_BODY_SENTINEL),
    )
    archive_dir = tmp_path / "archive"

    result = _run_pack("pack", "--workflow-output-dir", workflow_output, "--output-dir", archive_dir)

    assert result.returncode == 0, result.stderr
    index_text = (archive_dir / "archive-index.json").read_text(encoding="utf-8")
    assert RAW_BODY_SENTINEL not in index_text
    assert "rawArtifactBodyForTest" not in index_text


def test_pack_never_emits_approval_wording(tmp_path: Path) -> None:
    workflow_output = _workflow_output(tmp_path / "workflow-output")
    archive_dir = tmp_path / "archive"

    result = _run_pack(
        "pack",
        "--workflow-output-dir",
        workflow_output,
        "--output-dir",
        archive_dir,
        "--include-manifest",
        "--include-report",
    )

    assert result.returncode == 0, result.stderr
    combined = (
        result.stdout
        + result.stderr
        + (archive_dir / "archive-index.json").read_text(encoding="utf-8")
        + (archive_dir / "release-review-report.md").read_text(encoding="utf-8")
    )
    _assert_forbidden_approval_phrases_absent(combined)
