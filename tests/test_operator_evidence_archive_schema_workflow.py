from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.operator_evidence_archive_pack import INDEX_SCHEMA_VERSION
from scripts.operator_evidence_bundle_check import ARTIFACT_SPECS
from scripts.operator_evidence_schema_reference import SCHEMA_VERSION
from scripts.operator_evidence_template_pack import TEMPLATE_SPECS


ARCHIVE_SCRIPT = REPO_ROOT / "scripts" / "operator_evidence_archive_pack.py"
SCHEMA_SCRIPT = REPO_ROOT / "scripts" / "operator_evidence_schema_reference.py"
SMOKE_SCRIPT = REPO_ROOT / "scripts" / "operator_evidence_workflow_smoke.py"
WORKFLOW_SCRIPT = REPO_ROOT / "scripts" / "operator_evidence_workflow_run.py"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "operator_evidence"
SANITIZED_FIXTURE = FIXTURE_ROOT / "sanitized_complete"
UNSAFE_FIXTURE = FIXTURE_ROOT / "unsafe_rejected"

WORKFLOW_OUTPUTS = {
    "bundle-summary.json",
    "evidence-manifest.json",
    "release-review-report.md",
}
EXPECTED_BUNDLE_STATUS = "complete-review-required"
FORBIDDEN_APPROVAL_PHRASES = (
    "launch-" + "approved",
    "production-" + "ready",
    "automatic-" + "go",
    "automatic " + "go",
    "public launch " + "go",
    "release-" + "approved",
)
UNSAFE_FIXTURE_VALUES = (
    "fixture-unsafe-api-key-value-should-not-leak",
    "fixture-unsafe-raw-response-value-should-not-leak",
)


def _run(script: Path, *args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *map(str, args)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={},
    )


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _assert_forbidden_text_absent(*values: str) -> None:
    combined = "\n".join(values)
    lowered = combined.lower()
    for phrase in FORBIDDEN_APPROVAL_PHRASES:
        assert phrase not in lowered
    for unsafe_value in UNSAFE_FIXTURE_VALUES:
        assert unsafe_value not in combined


def test_archive_packager_and_schema_reference_cover_offline_workflow(tmp_path: Path) -> None:
    workflow_dir = tmp_path / "workflow"
    archive_dir = tmp_path / "archive"
    schema_md = tmp_path / "schema" / "operator-evidence-schema-reference.md"
    schema_json = tmp_path / "schema" / "operator-evidence-schema-reference.json"

    smoke = _run(SMOKE_SCRIPT, "--output-dir", workflow_dir)

    assert smoke.returncode == 0, smoke.stderr
    assert {path.name for path in workflow_dir.iterdir()} == WORKFLOW_OUTPUTS
    assert "smokeStatus=pass" in smoke.stdout
    assert "unsafeFixtureStatus=rejected-safely" in smoke.stdout

    bundle = _read_json(workflow_dir / "bundle-summary.json")
    manifest = _read_json(workflow_dir / "evidence-manifest.json")
    report = (workflow_dir / "release-review-report.md").read_text(encoding="utf-8")
    assert bundle["bundleStatus"] == EXPECTED_BUNDLE_STATUS
    assert bundle["runtimeBehaviorChanged"] is False
    assert bundle["networkCallsExecutedByValidator"] is False
    assert bundle["rawArtifactBodiesIncluded"] is False
    assert manifest["artifactDirectoryLabel"] == SANITIZED_FIXTURE.name
    assert report.count("Manual operator review is required") >= 1

    pack = _run(
        ARCHIVE_SCRIPT,
        "pack",
        "--workflow-output-dir",
        workflow_dir,
        "--output-dir",
        archive_dir,
        "--label",
        "operator-evidence-regression",
        "--include-manifest",
        "--include-report",
    )

    assert pack.returncode == 0, pack.stderr
    assert {path.name for path in archive_dir.iterdir()} == {
        "archive-index.json",
        *WORKFLOW_OUTPUTS,
    }
    index = _read_json(archive_dir / "archive-index.json")
    assert index["schemaVersion"] == INDEX_SCHEMA_VERSION
    assert index["manualReviewRequired"] is True
    assert index["releaseApproved"] is False
    assert index["reviewStatus"] == EXPECTED_BUNDLE_STATUS
    assert {item["fileLabel"] for item in index["includedFiles"]} == WORKFLOW_OUTPUTS
    assert all(set(item) == {"byteSize", "fileLabel", "sha256"} for item in index["includedFiles"])

    schema = _run(SCHEMA_SCRIPT, "render", "--output", schema_md, "--json-output", schema_json)

    assert schema.returncode == 0, schema.stderr
    schema_payload = _read_json(schema_json)
    schema_markdown = schema_md.read_text(encoding="utf-8")
    assert schema_payload["schemaVersion"] == SCHEMA_VERSION
    assert schema_payload["reviewPosture"] == {"manualReviewRequired": True, "releaseApproved": False}
    assert schema_payload["runtimeBehaviorChanged"] is False
    assert schema_payload["networkCallsExecuted"] is False
    assert schema_payload["rawArtifactBodiesIncluded"] is False

    category_entries = schema_payload["categories"]
    assert isinstance(category_entries, list)
    assert [entry["category"] for entry in category_entries] == [spec.category for spec in TEMPLATE_SPECS]
    assert [entry["artifactFilename"] for entry in category_entries] == [spec.filename for spec in TEMPLATE_SPECS]
    expected_template_filenames = {spec.filename for spec in TEMPLATE_SPECS}
    expected_bundle_filenames = {spec.filename for spec in ARTIFACT_SPECS}
    assert expected_bundle_filenames.issubset(expected_template_filenames)
    assert {entry["artifactFilename"] for entry in category_entries} == expected_template_filenames
    for spec in ARTIFACT_SPECS:
        entry = next(item for item in category_entries if item["category"] == spec.category)
        assert entry["artifactFilename"] == spec.filename
        assert entry["validatorScript"] == spec.validator_name
        assert f"`{spec.filename}`" in schema_markdown

    _assert_forbidden_text_absent(
        smoke.stdout,
        smoke.stderr,
        pack.stdout,
        pack.stderr,
        json.dumps(index, ensure_ascii=False, sort_keys=True),
        schema_markdown,
        json.dumps(schema_payload, ensure_ascii=False, sort_keys=True),
    )


def test_unsafe_fixture_workflow_cannot_create_review_valid_archive(tmp_path: Path) -> None:
    workflow_dir = tmp_path / "unsafe-workflow"
    archive_dir = tmp_path / "unsafe-archive"

    workflow = _run(
        WORKFLOW_SCRIPT,
        "check",
        "--artifact-dir",
        UNSAFE_FIXTURE,
        "--output-dir",
        workflow_dir,
    )

    assert workflow.returncode != 0
    assert WORKFLOW_OUTPUTS.issubset({path.name for path in workflow_dir.iterdir()})
    unsafe_bundle = _read_json(workflow_dir / "bundle-summary.json")
    assert unsafe_bundle["bundleStatus"] != EXPECTED_BUNDLE_STATUS

    pack = _run(
        ARCHIVE_SCRIPT,
        "pack",
        "--workflow-output-dir",
        workflow_dir,
        "--output-dir",
        archive_dir,
        "--include-manifest",
        "--include-report",
    )

    assert pack.returncode == 0, pack.stderr
    index = _read_json(archive_dir / "archive-index.json")
    assert index["releaseApproved"] is False
    assert index["manualReviewRequired"] is True
    assert index["reviewStatus"] != EXPECTED_BUNDLE_STATUS
    _assert_forbidden_text_absent(
        workflow.stdout,
        workflow.stderr,
        pack.stdout,
        pack.stderr,
        json.dumps(index, ensure_ascii=False, sort_keys=True),
    )
