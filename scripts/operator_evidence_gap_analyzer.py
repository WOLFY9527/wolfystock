#!/usr/bin/env python3
"""Analyze sanitized operator evidence gaps for manual review.

The analyzer reads a local directory of sanitized operator artifacts and emits a
bounded checklist of remaining human inputs. It does not call networks, read
environment values, inspect deployment state, print raw artifact bodies, mutate
runtime behavior, or connect to launch acceptance.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from evidence_safety import FORBIDDEN_APPROVAL_LABEL_PHRASES, UNSAFE_LABEL_MARKERS, path_label
    from operator_evidence_bundle_check import ARTIFACT_SPECS, build_bundle_summary
    from operator_evidence_schema_reference import REQUIRED_FIELDS_BY_CATEGORY
    from operator_evidence_template_pack import PLACEHOLDER_VALUES, TEMPLATE_TIMESTAMP
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from scripts.evidence_safety import FORBIDDEN_APPROVAL_LABEL_PHRASES, UNSAFE_LABEL_MARKERS, path_label
    from scripts.operator_evidence_bundle_check import ARTIFACT_SPECS, build_bundle_summary
    from scripts.operator_evidence_schema_reference import REQUIRED_FIELDS_BY_CATEGORY
    from scripts.operator_evidence_template_pack import PLACEHOLDER_VALUES, TEMPLATE_TIMESTAMP


SCHEMA_VERSION = "wolfystock_operator_evidence_gap_analyzer_v1"
EXIT_OK = 0
EXIT_GAPS_FOUND = 1
EXIT_USAGE_OR_IO = 2
MAX_ITEMS_PER_CATEGORY = 12
SAFE_FIELD_RE = re.compile(r"^[A-Za-z0-9_$][A-Za-z0-9_$.[\\]-]{0,95}$")
PLACEHOLDER_STRINGS = {
    *PLACEHOLDER_VALUES,
    TEMPLATE_TIMESTAMP,
    "0000000",
    "redacted-or-configured",
    "review-ticket-label",
    "sanitized-operator-label",
    "staging-environment-label",
}
UNSAFE_REASON_FRAGMENTS = (
    "approval",
    "credential",
    "debug",
    "payload",
    "raw",
    "secret",
    "sql",
    "token",
    "unsafe",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_field_label(field: str) -> str:
    lowered = field.lower()
    if any(marker in lowered for marker in (*UNSAFE_LABEL_MARKERS, *FORBIDDEN_APPROVAL_LABEL_PHRASES)):
        return "[redacted]"
    if not SAFE_FIELD_RE.fullmatch(field):
        return "[redacted]"
    return field


def _dedupe_limited(items: list[str], *, limit: int = MAX_ITEMS_PER_CATEGORY) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        label = str(item or "").strip()
        if not label or label in seen:
            continue
        seen.add(label)
        result.append(label)
        if len(result) >= limit:
            break
    return result


def _required_inputs_for_category(category: str) -> list[str]:
    return _dedupe_limited([str(field) for field in REQUIRED_FIELDS_BY_CATEGORY.get(category, ())])


def _is_placeholder_value(value: str) -> bool:
    stripped = value.strip()
    if stripped in PLACEHOLDER_STRINGS:
        return True
    if stripped.startswith("<") and stripped.endswith(">") and len(stripped) <= 120:
        return True
    return False


def _scan_value(value: Any, *, field: str = "$") -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            key_field = f"{field}.{key_text}" if field != "$" else key_text
            hits.extend(_scan_value(child, field=key_field))
        return hits

    if isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_scan_value(child, field=f"{field}[{index}]"))
        return hits

    if isinstance(value, str):
        if _is_placeholder_value(value):
            hits.append({"field": _safe_field_label(field), "reasonCode": "placeholder_requires_operator_input"})
    return hits


def _load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, "required_artifact_missing"
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, "artifact_read_failed"


def _reason_is_unsafe(reason: str) -> bool:
    lowered = reason.lower()
    return any(fragment in lowered for fragment in UNSAFE_REASON_FRAGMENTS)


def _missing_inputs(
    *,
    category: str,
    artifact_status: str,
    blocking_reasons: list[str],
    placeholder_hits: list[dict[str, str]],
) -> list[str]:
    if artifact_status == "missing":
        return _required_inputs_for_category(category)

    inputs: list[str] = []
    for hit in placeholder_hits:
        field = str(hit.get("field") or "")
        if field and field != "[redacted]":
            inputs.append(field)
        else:
            inputs.append(str(hit.get("reasonCode") or "unsafe_marker"))
    if artifact_status == "rejected":
        inputs.extend(blocking_reasons)
    return _dedupe_limited(inputs)


def _outcome_posture(*, artifact_status: str, missing_inputs: list[str], unsafe_hits: list[dict[str, str]]) -> str:
    if artifact_status == "missing" or missing_inputs and not unsafe_hits:
        return "missing-human-inputs"
    if unsafe_hits:
        return "unsafe-redaction-review-required"
    if artifact_status == "rejected":
        return "validator-review-required"
    if artifact_status == "needs-review":
        return "human-review-required"
    return "ready-for-human-review"


def _next_action(category: str, posture: str) -> str:
    if posture == "missing-human-inputs":
        return f"provide sanitized {category} artifact inputs and rerun the analyzer"
    if posture == "unsafe-redaction-review-required":
        return f"replace unsafe or placeholder-only {category} evidence with sanitized labels, then rerun"
    if posture == "validator-review-required":
        return f"review {category} validator reason codes and regenerate sanitized evidence"
    if posture == "human-review-required":
        return f"complete human review for {category} evidence outside this analyzer"
    return f"human reviewer should inspect {category} source evidence before any release decision"


def _artifact_by_category(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    artifacts = bundle.get("artifacts")
    if not isinstance(artifacts, list):
        return {}
    return {
        str(item.get("category")): item
        for item in artifacts
        if isinstance(item, dict) and item.get("category")
    }


def _analyze_category(artifact_dir: Path, spec_category: str, filename: str, bundle_item: dict[str, Any]) -> dict[str, Any]:
    payload, load_error = _load_json(artifact_dir / filename)
    blocking_reasons = bundle_item.get("blockingReasonSummaries")
    if not isinstance(blocking_reasons, list):
        blocking_reasons = []
    safe_reasons = _dedupe_limited([str(reason) for reason in blocking_reasons])

    unsafe_hits: list[dict[str, str]] = []
    if payload is not None and load_error is None:
        unsafe_hits = _scan_value(payload)
    for reason in safe_reasons:
        if _reason_is_unsafe(reason):
            unsafe_hits.append({"field": "[redacted]", "reasonCode": reason})
    unsafe_hits = [
        {"field": _safe_field_label(str(hit.get("field") or "[redacted]")), "reasonCode": str(hit.get("reasonCode") or "unsafe_marker")}
        for hit in unsafe_hits[:MAX_ITEMS_PER_CATEGORY]
    ]

    status = str(bundle_item.get("status") or ("rejected" if load_error else "needs-review"))
    missing_inputs = _missing_inputs(
        category=spec_category,
        artifact_status=status,
        blocking_reasons=safe_reasons,
        placeholder_hits=unsafe_hits,
    )
    posture = _outcome_posture(artifact_status=status, missing_inputs=missing_inputs, unsafe_hits=unsafe_hits)
    return {
        "category": spec_category,
        "status": status,
        "artifactLabel": path_label(Path(filename)),
        "missingRequiredHumanInputs": missing_inputs,
        "unsafePlaceholderHits": unsafe_hits,
        "outcomePosture": posture,
        "nextOperatorAction": _next_action(spec_category, posture),
    }


def analyze_artifact_dir(artifact_dir: Path) -> tuple[int, dict[str, Any]]:
    if not artifact_dir.is_dir():
        categories = []
        for spec in ARTIFACT_SPECS:
            missing_inputs = _required_inputs_for_category(spec.category)
            posture = "missing-human-inputs"
            categories.append(
                {
                    "category": spec.category,
                    "status": "missing",
                    "artifactLabel": spec.filename,
                    "missingRequiredHumanInputs": missing_inputs,
                    "unsafePlaceholderHits": [],
                    "outcomePosture": posture,
                    "nextOperatorAction": _next_action(spec.category, posture),
                }
            )
        return EXIT_GAPS_FOUND, _summary(artifact_dir, categories, gap_status="missing-inputs-review-required")

    bundle = build_bundle_summary(artifact_dir)
    bundle_by_category = _artifact_by_category(bundle)
    categories = [
        _analyze_category(
            artifact_dir,
            spec.category,
            spec.filename,
            bundle_by_category.get(spec.category, {}),
        )
        for spec in ARTIFACT_SPECS
    ]
    missing = any(category["status"] == "missing" for category in categories)
    unsafe = any(category["unsafePlaceholderHits"] for category in categories)
    rejected = any(category["status"] == "rejected" for category in categories)
    if missing:
        gap_status = "missing-inputs-review-required"
    elif unsafe:
        gap_status = "unsafe-review-required"
    elif rejected:
        gap_status = "validator-review-required"
    else:
        gap_status = "review-required"
    exit_code = EXIT_OK if gap_status == "review-required" else EXIT_GAPS_FOUND
    return exit_code, _summary(artifact_dir, categories, gap_status=gap_status)


def _summary(artifact_dir: Path, categories: list[dict[str, Any]], *, gap_status: str) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": _now_iso(),
        "artifactDirectoryLabel": path_label(artifact_dir),
        "gapStatus": gap_status,
        "manualReviewRequired": True,
        "releaseApproved": False,
        "launchApproved": False,
        "networkCallsExecuted": False,
        "rawArtifactBodiesIncluded": False,
        "runtimeBehaviorChanged": False,
        "categoriesAnalyzed": [category["category"] for category in categories],
        "categories": categories,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", required=True, type=Path, help="Directory containing sanitized operator evidence artifacts.")
    parser.add_argument("--output", required=True, type=Path, help="JSON output path for the bounded gap checklist.")
    args = parser.parse_args(argv)

    try:
        exit_code, summary = analyze_artifact_dir(args.artifact_dir)
        _write_json(args.output, summary)
    except OSError:
        print("[FAIL] operator evidence gap analyzer could not read or write local files", file=sys.stderr)
        return EXIT_USAGE_OR_IO

    print(f"[OK] operator evidence gap analyzer wrote {summary['gapStatus']}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
