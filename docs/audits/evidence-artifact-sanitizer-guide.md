# Evidence Artifact Sanitizer Guide

This guide covers `scripts/evidence_artifact_sanitize.py`, an offline helper for
turning one operator-provided JSON evidence artifact into a redacted review copy.

The sanitizer is a review-prep tool only. It does not produce a release
decision, does not call networks, does not read environment state, and does not
change launch acceptance inputs or gate scripts.

## Modes

Create a separate sanitized copy:

```bash
python3 scripts/evidence_artifact_sanitize.py sanitize \
  --input <artifact.json> \
  --output <sanitized.json>
```

Scan an artifact and print bounded findings without writing a copy:

```bash
python3 scripts/evidence_artifact_sanitize.py scan \
  --input <artifact.json>
```

Return a non-zero exit when findings are present:

```bash
python3 scripts/evidence_artifact_sanitize.py scan \
  --input <artifact.json> \
  --fail-on-findings
```

The default `sanitize` mode refuses to overwrite the source path. Use
`--in-place` only when an operator intentionally wants to replace the source
artifact with the redacted content:

```bash
python3 scripts/evidence_artifact_sanitize.py sanitize \
  --input <artifact.json> \
  --in-place
```

## Redaction Behavior

The sanitizer preserves safe JSON structure and safe scalar values. It replaces
unsafe scalar values with:

```text
<redacted>
```

Unsafe key families cause scalar descendants to be redacted while keeping the
container shape available for review. Findings use bounded field labels, reason
codes, and category counts; unsafe key labels and unsafe path labels are not
printed raw.

Finding categories include:

- `secret_marker`
- `private_key`
- `raw_body_or_log`
- `credential_url`
- `endpoint_url`
- `broker_order_identity`
- `account_metadata`
- `path_traversal`
- `approval_wording`

## Output Contract

`sanitize` writes only the sanitized artifact to the output path and prints a
summary JSON document to stdout. `scan` prints the same bounded summary without
writing an artifact.

The summary includes:

- `sanitizerStatus: needs-review`
- `runtimeBehaviorChanged: false`
- `networkCallsExecuted: false`
- `rawArtifactBodiesIncluded: false`
- sanitized findings only
- counts by finding category

The summary is intentionally not a launch acceptance artifact and should not be
wired into acceptance status generation.

## Follow-Up Validation

After producing a sanitized copy, run the relevant offline validator for that
artifact type when one exists. Examples:

```bash
python3 scripts/provider_operator_evidence_check.py <sanitized-provider-artifact.json>
python3 scripts/operator_evidence_manifest_check.py verify \
  --artifact-dir <sanitized-artifact-dir> \
  --manifest <manifest.json>
python3 scripts/operator_evidence_bundle_check.py <sanitized-artifact-dir>
```

A sanitized artifact may still need manual review or fail a type-specific
validator because the sanitizer redacts unsafe material; it is not a schema
repair tool.
