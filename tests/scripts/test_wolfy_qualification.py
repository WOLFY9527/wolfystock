from __future__ import annotations

from scripts.environment.qualification import compare_findings, normalize_findings


def finding(identifier: str, *, blocker: bool = False, message: str = "detail") -> dict[str, object]:
    return {
        "id": identifier,
        "gate": "backend",
        "code": "assertion_failed",
        "severity": "high" if blocker else "medium",
        "releaseBlocker": blocker,
        "message": message,
        "line": 99,
    }


def test_baseline_comparison_reports_new_unchanged_and_removed_findings() -> None:
    result = compare_findings(
        baseline=[finding("removed"), finding("same", message="old terminal text")],
        current=[finding("same", message="new terminal text"), finding("new")],
        baseline_commit="a" * 40,
        evidence_fingerprint="b" * 64,
    )

    assert [item["id"] for item in result["newFindings"]] == ["new"]
    assert [item["id"] for item in result["unchangedFindings"]] == ["same"]
    assert [item["id"] for item in result["removedFindings"]] == ["removed"]
    assert result["status"] == "FAIL"


def test_historical_release_blocker_remains_blocking() -> None:
    blocker = finding("known-blocker", blocker=True)

    result = compare_findings(
        baseline=[blocker],
        current=[blocker],
        baseline_commit="a" * 40,
        evidence_fingerprint="b" * 64,
    )

    assert result["newFindings"] == []
    assert result["unchangedFindings"][0]["releaseBlocker"] is True
    assert result["status"] == "FAIL"
    assert result["releaseReady"] is False


def test_empty_current_findings_pass_only_with_explicit_baseline_identity() -> None:
    result = compare_findings(
        baseline=[finding("removed")],
        current=[],
        baseline_commit="a" * 40,
        evidence_fingerprint="b" * 64,
    )

    assert result["status"] == "PASS"
    assert result["releaseReady"] is True


def test_normalized_findings_drop_terminal_and_location_details() -> None:
    normalized = normalize_findings([finding("fixture", message="private terminal output")])

    assert normalized == [
        {
            "id": "fixture",
            "gate": "backend",
            "code": "assertion_failed",
            "severity": "medium",
            "releaseBlocker": False,
        }
    ]
