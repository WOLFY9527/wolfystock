from __future__ import annotations

from typing import Any, Iterable


DELTA_SCHEMA = "wolfystock_baseline_delta_v1"


def _normalized_key(finding: dict[str, Any]) -> tuple[object, ...]:
    return (
        finding.get("id"),
        finding.get("gate"),
        finding.get("code"),
        finding.get("severity"),
        finding.get("releaseBlocker") is True,
    )


def _normalized_finding(finding: dict[str, Any]) -> dict[str, Any]:
    fields = ("id", "gate", "code", "severity")
    if any(not isinstance(finding.get(field), str) or not finding[field] for field in fields):
        raise ValueError("qualification finding identity fields must be non-empty strings")
    if type(finding.get("releaseBlocker")) is not bool:
        raise ValueError("qualification finding releaseBlocker must be boolean")
    return {field: finding[field] for field in (*fields, "releaseBlocker")}


def _indexed(findings: Iterable[dict[str, Any]]) -> dict[tuple[object, ...], dict[str, Any]]:
    return {_normalized_key(item): _normalized_finding(item) for item in findings}


def normalize_findings(findings: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = _indexed(findings)
    return [indexed[key] for key in sorted(indexed)]


def compare_findings(
    *,
    baseline: Iterable[dict[str, Any]],
    current: Iterable[dict[str, Any]],
    baseline_commit: str,
    evidence_fingerprint: str,
) -> dict[str, Any]:
    baseline_index = _indexed(baseline)
    current_index = _indexed(current)
    baseline_keys = set(baseline_index)
    current_keys = set(current_index)
    new = [current_index[key] for key in sorted(current_keys - baseline_keys)]
    unchanged = [current_index[key] for key in sorted(current_keys & baseline_keys)]
    removed = [baseline_index[key] for key in sorted(baseline_keys - current_keys)]
    blockers = [item for item in (*new, *unchanged) if item["releaseBlocker"]]
    passed = not new and not blockers
    return {
        "schemaVersion": DELTA_SCHEMA,
        "baselineCommit": baseline_commit,
        "environmentFingerprint": evidence_fingerprint,
        "status": "PASS" if passed else "FAIL",
        "releaseReady": passed,
        "newFindings": new,
        "unchangedFindings": unchanged,
        "removedFindings": removed,
    }
