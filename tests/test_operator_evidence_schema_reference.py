from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.operator_evidence_bundle_check import ARTIFACT_SPECS
from scripts.operator_evidence_template_pack import TEMPLATE_SPECS


SCRIPT = REPO_ROOT / "scripts" / "operator_evidence_schema_reference.py"
EXPECTED_CATEGORIES = [spec.category for spec in TEMPLATE_SPECS]
EXPECTED_FILENAMES = [spec.filename for spec in TEMPLATE_SPECS]
FORBIDDEN_MARKERS = (
    "launch-approved",
    "production-ready",
    "public launch go",
    "release-approved",
    "api_key",
    "password",
    "token",
    "cookie",
    "session",
    "stack trace",
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_render_creates_markdown_and_json_outputs(tmp_path: Path) -> None:
    md_path = tmp_path / "operator-evidence-schema-reference.md"
    json_path = tmp_path / "operator-evidence-schema-reference.json"

    result = _run("render", "--output", str(md_path), "--json-output", str(json_path))

    assert result.returncode == 0, result.stderr
    assert md_path.exists()
    assert json_path.exists()

    payload = _load_json(json_path)
    assert payload["schemaVersion"] == "wolfystock_operator_evidence_schema_reference_v1"
    assert payload["reviewPosture"] == {"manualReviewRequired": True, "releaseApproved": False}

    categories = payload["categories"]
    assert isinstance(categories, list)
    assert [entry["category"] for entry in categories] == EXPECTED_CATEGORIES
    assert [entry["artifactFilename"] for entry in categories] == EXPECTED_FILENAMES

    bundle_filenames = {spec.filename for spec in ARTIFACT_SPECS}
    assert bundle_filenames.issubset(set(EXPECTED_FILENAMES))

    markdown = md_path.read_text(encoding="utf-8")
    assert "releaseApproved=false" in markdown
    assert len(markdown.splitlines()) <= 220


def test_render_is_deterministic_and_sanitized(tmp_path: Path) -> None:
    md_path = tmp_path / "operator-evidence-schema-reference.md"
    json_path = tmp_path / "operator-evidence-schema-reference.json"

    first = _run("render", "--output", str(md_path), "--json-output", str(json_path))
    first_md = md_path.read_text(encoding="utf-8")
    first_json = json_path.read_text(encoding="utf-8")

    second = _run("render", "--output", str(md_path), "--json-output", str(json_path))
    second_md = md_path.read_text(encoding="utf-8")
    second_json = json_path.read_text(encoding="utf-8")

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert first_md == second_md
    assert first_json == second_json

    combined = f"{first_md}\n{first_json}".lower()
    for marker in FORBIDDEN_MARKERS:
        assert marker not in combined
    assert "automatic-go" not in combined
    assert "releaseapproved=true" not in combined


def test_render_output_mentions_required_fields_and_validator_names(tmp_path: Path) -> None:
    md_path = tmp_path / "operator-evidence-schema-reference.md"

    result = _run("render", "--output", str(md_path))

    assert result.returncode == 0, result.stderr
    markdown = md_path.read_text(encoding="utf-8")

    for spec in TEMPLATE_SPECS:
        assert spec.category in markdown
        assert spec.filename in markdown
    for validator_name in {
        "provider_operator_evidence_check.py",
        "provider_sla_licensing_evidence_check.py",
        "restore_pitr_operator_evidence_check.py",
        "security_operator_acceptance_check.py",
        "quota_operator_evidence_check.py",
        "staging_ingress_operator_evidence_check.py",
        "ws2_sse_operator_decision_check.py",
        "config_snapshot_evidence_check.py",
        "manual_release_approval_evidence_check.py",
    }:
        assert validator_name in markdown
