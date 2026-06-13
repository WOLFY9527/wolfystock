#!/usr/bin/env python3
"""Render an offline sanitized operator evidence schema reference.

The reference is derived from the local operator template pack and validator
category metadata. It does not inspect runtime state, read environment values,
open evidence artifacts, call networks, or integrate with launch acceptance.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from operator_evidence_bundle_check import ARTIFACT_SPECS
    from operator_evidence_template_pack import TEMPLATE_SPECS, PLACEHOLDER_VALUES
    from config_snapshot_evidence_check import REQUIRED_FIELDS as CONFIG_SNAPSHOT_REQUIRED_FIELDS
    from manual_release_approval_evidence_check import REQUIRED_FIELDS as MANUAL_RELEASE_REQUIRED_FIELDS
    from notification_delivery_rehearsal_evidence_check import REQUIRED_TOP_LEVEL_FIELDS as NOTIFICATION_REHEARSAL_REQUIRED_FIELDS
    from provider_operator_evidence_check import REQUIRED_FIELDS as PROVIDER_REQUIRED_FIELDS
    from provider_sla_licensing_evidence_check import REQUIRED_FIELDS as PROVIDER_SLA_REQUIRED_FIELDS
    from quota_operator_evidence_check import REQUIRED_SECTIONS as QUOTA_REQUIRED_SECTIONS
    from restore_pitr_operator_evidence_check import REQUIRED_FIELDS as RESTORE_PITR_REQUIRED_FIELDS
    from security_operator_acceptance_check import REQUIRED_SECTIONS as SECURITY_REQUIRED_SECTIONS
    from staging_ingress_operator_evidence_check import REQUIRED_FIELDS as STAGING_INGRESS_REQUIRED_FIELDS
    from ws2_target_environment_evidence_check import REQUIRED_FIELDS as WS2_TARGET_ENV_REQUIRED_FIELDS
    from ws2_sse_operator_decision_check import REQUIRED_FIELDS as WS2_SSE_REQUIRED_FIELDS
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from scripts.operator_evidence_bundle_check import ARTIFACT_SPECS
    from scripts.operator_evidence_template_pack import TEMPLATE_SPECS, PLACEHOLDER_VALUES
    from scripts.config_snapshot_evidence_check import REQUIRED_FIELDS as CONFIG_SNAPSHOT_REQUIRED_FIELDS
    from scripts.manual_release_approval_evidence_check import REQUIRED_FIELDS as MANUAL_RELEASE_REQUIRED_FIELDS
    from scripts.notification_delivery_rehearsal_evidence_check import (
        REQUIRED_TOP_LEVEL_FIELDS as NOTIFICATION_REHEARSAL_REQUIRED_FIELDS,
    )
    from scripts.provider_operator_evidence_check import REQUIRED_FIELDS as PROVIDER_REQUIRED_FIELDS
    from scripts.provider_sla_licensing_evidence_check import REQUIRED_FIELDS as PROVIDER_SLA_REQUIRED_FIELDS
    from scripts.quota_operator_evidence_check import REQUIRED_SECTIONS as QUOTA_REQUIRED_SECTIONS
    from scripts.restore_pitr_operator_evidence_check import REQUIRED_FIELDS as RESTORE_PITR_REQUIRED_FIELDS
    from scripts.security_operator_acceptance_check import REQUIRED_SECTIONS as SECURITY_REQUIRED_SECTIONS
    from scripts.staging_ingress_operator_evidence_check import REQUIRED_FIELDS as STAGING_INGRESS_REQUIRED_FIELDS
    from scripts.ws2_target_environment_evidence_check import REQUIRED_FIELDS as WS2_TARGET_ENV_REQUIRED_FIELDS
    from scripts.ws2_sse_operator_decision_check import REQUIRED_FIELDS as WS2_SSE_REQUIRED_FIELDS


SCHEMA_VERSION = "wolfystock_operator_evidence_schema_reference_v1"
REFERENCE_TITLE = "Operator Evidence Schema Reference"
ADVISORY_VALIDATORS = {
    "ws2-target-environment": "ws2_target_environment_evidence_check.py",
    "ws2-sse": "ws2_sse_operator_decision_check.py",
    "config-snapshot": "config_snapshot_evidence_check.py",
    "manual-release-approval": "manual_release_approval_evidence_check.py",
}
REDACTION_NOTES = (
    "Use sanitized labels, bounded summaries, enum values, counts, booleans, "
    "timestamps, and review-ticket labels only.",
    "Keep credentials, raw logs, request or response bodies, runtime exception details, real "
    "service locations, personal identifiers, and provider payloads out of the reference and artifacts.",
)
REVIEW_POSTURE = {
    "manualReviewRequired": True,
    "releaseApproved": False,
    "publicLaunchReady": False,
}
REFERENCE_BOUNDARIES = {
    "targetEnvironmentObservationsRequired": True,
    "templatesAndSyntheticFixturesAcceptedProductionEvidence": False,
    "validatorsExecuteLiveActions": False,
    "acceptedReviewEvidenceApprovesPublicLaunch": False,
}
REQUIRED_FIELDS_BY_CATEGORY = {
    "provider": PROVIDER_REQUIRED_FIELDS,
    "provider-sla-licensing": PROVIDER_SLA_REQUIRED_FIELDS,
    "notification-delivery-rehearsal": NOTIFICATION_REHEARSAL_REQUIRED_FIELDS,
    "restore-pitr": RESTORE_PITR_REQUIRED_FIELDS,
    "security": ("schemaVersion", *SECURITY_REQUIRED_SECTIONS),
    "quota-budget": ("schemaVersion", *QUOTA_REQUIRED_SECTIONS),
    "staging-ingress": STAGING_INGRESS_REQUIRED_FIELDS,
    "ws2-target-environment": WS2_TARGET_ENV_REQUIRED_FIELDS,
    "ws2-sse": WS2_SSE_REQUIRED_FIELDS,
    "config-snapshot": CONFIG_SNAPSHOT_REQUIRED_FIELDS,
    "manual-release-approval": MANUAL_RELEASE_REQUIRED_FIELDS,
}


def _validator_names_by_category() -> dict[str, str]:
    names = {spec.category: spec.validator_name for spec in ARTIFACT_SPECS}
    names.update(ADVISORY_VALIDATORS)
    return names


def _collect_safe_examples(value: Any) -> list[str]:
    examples: list[str] = []
    if isinstance(value, dict):
        for key in sorted(value):
            examples.extend(_collect_safe_examples(value[key]))
    elif isinstance(value, list):
        for item in value:
            examples.extend(_collect_safe_examples(item))
    elif isinstance(value, str):
        if value in PLACEHOLDER_VALUES or value.startswith("<") and value.endswith(">"):
            examples.append(value)
    return examples


def _dedupe_preserving_order(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return tuple(deduped)


def build_reference() -> dict[str, Any]:
    validators = _validator_names_by_category()
    categories: list[dict[str, Any]] = []

    for spec in TEMPLATE_SPECS:
        template = spec.factory()
        required_fields = tuple(REQUIRED_FIELDS_BY_CATEGORY.get(spec.category, tuple(template.keys())))
        examples = _dedupe_preserving_order(_collect_safe_examples(template))
        categories.append(
            {
                "category": spec.category,
                "artifactFilename": spec.filename,
                "requiredTopLevelFields": list(required_fields),
                "safePlaceholderExamples": list(examples),
                "redactionNotes": list(REDACTION_NOTES),
                "validatorScript": validators[spec.category],
                "reviewPosture": dict(REVIEW_POSTURE),
            }
        )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "source": "operator_evidence_template_pack.py",
        "bundleCategorySource": "operator_evidence_bundle_check.py",
        "runtimeBehaviorChanged": False,
        "networkCallsExecuted": False,
        "rawArtifactBodiesIncluded": False,
        "reviewPosture": dict(REVIEW_POSTURE),
        "reviewBoundaries": dict(REFERENCE_BOUNDARIES),
        "categories": categories,
    }


def _markdown_list(values: list[str]) -> str:
    if not values:
        return "`<none>`"
    return ", ".join(f"`{value}`" for value in values)


def _markdown_field_chunks(values: list[str], *, chunk_size: int = 6) -> list[str]:
    if not values:
        return ["  - `<none>`"]
    return [
        "  - " + _markdown_list(values[index : index + chunk_size])
        for index in range(0, len(values), chunk_size)
    ]


def render_markdown(reference: dict[str, Any]) -> str:
    lines = [
        f"# {REFERENCE_TITLE}",
        "",
        "This offline reference is derived from the local operator evidence template pack and bundle checker category metadata.",
        "It is operator-facing review guidance only; manual review is required and releaseApproved=false.",
        "",
        "## Safety Posture",
        "",
        "- Runtime behavior changed: false",
        "- Network calls executed: false",
        "- Raw artifact bodies included: false",
        "- Manual review required: true",
        "- releaseApproved=false",
        "- publicLaunchReady=false",
        "- Sanitized operator artifacts must be filled from real target-environment observations.",
        "- Templates, synthetic fixtures, and local dry-run or preflight output are not accepted production evidence.",
        "- Validators do not execute live provider, network, DB, notification, or runtime actions.",
        "- Accepted review evidence still does not approve public launch without manual release review.",
        "",
        "## Categories",
        "",
    ]

    for entry in reference["categories"]:
        lines.extend(
            [
                f"### {entry['category']}",
                "",
                f"- Expected artifact filename: `{entry['artifactFilename']}`",
                f"- Validator script: `{entry['validatorScript']}`",
                "- Review posture: manual review required, releaseApproved=false",
                "- Required top-level fields:",
                *_markdown_field_chunks(entry["requiredTopLevelFields"]),
                f"- Safe placeholder examples: {_markdown_list(entry['safePlaceholderExamples'])}",
                f"- Redaction notes: {' '.join(entry['redactionNotes'])}",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def _write_json(path: Path, reference: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reference, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path: Path, reference: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(reference), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    render_parser = subparsers.add_parser("render", help="Render the sanitized schema reference.")
    render_parser.add_argument("--output", required=True, help="Markdown output path.")
    render_parser.add_argument("--json-output", help="Optional JSON output path.")
    args = parser.parse_args(argv)

    if args.command == "render":
        reference = build_reference()
        _write_markdown(Path(args.output), reference)
        if args.json_output:
            _write_json(Path(args.json_output), reference)
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
