from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "operator_evidence_gap_analyzer.py"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "operator_evidence"
SANITIZED_COMPLETE = FIXTURE_ROOT / "sanitized_complete"
UNSAFE_REJECTED = FIXTURE_ROOT / "unsafe_rejected"

EXPECTED_CATEGORIES = {
    "provider",
    "provider-sla-licensing",
    "notification-delivery-rehearsal",
    "restore-pitr",
    "security",
    "quota-budget",
    "staging-ingress",
    "ws2-sse",
    "config-snapshot",
    "manual-release-approval",
}
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
UNSAFE_FIXTURE_VALUES = (
    "fixture-unsafe-api-key-value-should-not-leak",
    "fixture-unsafe-raw-response-value-should-not-leak",
)


sys.path.insert(0, str(REPO_ROOT / "tests"))

from test_operator_evidence_bundle_check import _accepted_artifacts  # noqa: E402


def _write_artifacts(path: Path, artifacts: dict[str, object]) -> Path:
    path.mkdir(parents=True)
    for filename, payload in artifacts.items():
        (path / filename).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _run_analyzer(artifact_dir: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--artifact-dir",
            str(artifact_dir),
            "--output",
            str(output),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={},
    )


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _rendered(payload: object, *streams: str) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n".join(streams)


def _assert_bounded(text: str) -> None:
    assert len(text) <= 24_000
    for line in text.splitlines():
        assert len(line) <= 360


def _assert_no_unsafe_or_forbidden_text(text: str) -> None:
    lowered = text.lower()
    for phrase in FORBIDDEN_APPROVAL_PHRASES:
        assert phrase not in lowered
    for value in UNSAFE_FIXTURE_VALUES:
        assert value not in text


def test_complete_synthetic_fixture_produces_review_required_with_no_unsafe_leak(tmp_path: Path) -> None:
    artifact_dir = _write_artifacts(tmp_path / "complete", _accepted_artifacts())
    output = tmp_path / "gap-summary.json"

    result = _run_analyzer(artifact_dir, output)

    assert result.returncode == 0, result.stderr
    payload = _read_json(output)
    assert payload["manualReviewRequired"] is True
    assert payload["releaseApproved"] is False
    assert payload["launchApproved"] is False
    assert payload["networkCallsExecuted"] is False
    assert payload["rawArtifactBodiesIncluded"] is False
    assert payload["gapStatus"] == "review-required"
    assert {item["category"] for item in payload["categories"]} == EXPECTED_CATEGORIES
    assert all(item["missingRequiredHumanInputs"] == [] for item in payload["categories"])
    assert all(item["unsafePlaceholderHits"] == [] for item in payload["categories"])
    rendered = _rendered(payload, result.stdout, result.stderr)
    _assert_bounded(rendered)
    _assert_no_unsafe_or_forbidden_text(rendered)


def test_incomplete_fixture_reports_missing_inputs(tmp_path: Path) -> None:
    artifacts = _accepted_artifacts()
    artifacts.pop("quota_budget_operator_evidence.json")
    artifact_dir = _write_artifacts(tmp_path / "incomplete", artifacts)
    output = tmp_path / "gap-summary.json"

    result = _run_analyzer(artifact_dir, output)

    assert result.returncode == 1
    payload = _read_json(output)
    assert payload["gapStatus"] == "missing-inputs-review-required"
    quota = next(item for item in payload["categories"] if item["category"] == "quota-budget")
    assert quota["status"] == "missing"
    assert quota["outcomePosture"] == "missing-human-inputs"
    assert "quotaPilot" in quota["missingRequiredHumanInputs"]
    assert quota["nextOperatorAction"] == "provide sanitized quota-budget artifact inputs and rerun the analyzer"


def test_unsafe_values_are_redacted(tmp_path: Path) -> None:
    output = tmp_path / "gap-summary.json"

    result = _run_analyzer(UNSAFE_REJECTED, output)

    assert result.returncode == 1
    payload = _read_json(output)
    rendered = _rendered(payload, result.stdout, result.stderr)
    _assert_no_unsafe_or_forbidden_text(rendered)
    provider = next(item for item in payload["categories"] if item["category"] == "provider")
    assert provider["unsafePlaceholderHits"]
    assert all(hit["field"] == "[redacted]" for hit in provider["unsafePlaceholderHits"])
    assert "unsafe_marker" in provider["missingRequiredHumanInputs"]


def test_output_is_bounded_for_large_local_artifact(tmp_path: Path) -> None:
    artifact_dir = _write_artifacts(tmp_path / "large", _accepted_artifacts())
    large_provider = json.loads((artifact_dir / "provider_operator_evidence.json").read_text(encoding="utf-8"))
    large_provider["notes"] = "operator-note " * 5000
    (artifact_dir / "provider_operator_evidence.json").write_text(json.dumps(large_provider), encoding="utf-8")
    output = tmp_path / "gap-summary.json"

    result = _run_analyzer(artifact_dir, output)

    assert output.exists()
    rendered = _rendered(_read_json(output), result.stdout, result.stderr)
    _assert_bounded(rendered)


def test_output_contains_no_approval_wording(tmp_path: Path) -> None:
    output = tmp_path / "gap-summary.json"

    result = _run_analyzer(SANITIZED_COMPLETE, output)

    rendered = _rendered(_read_json(output), result.stdout, result.stderr)
    _assert_no_unsafe_or_forbidden_text(rendered)
