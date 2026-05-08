# Release Review Report Renderer Guide

## Purpose

`scripts/release_review_report_render.py` renders an offline Markdown review report from the sanitized operator evidence bundle summary produced by `scripts/operator_evidence_bundle_check.py`.

The report is an operator review aid only. It preserves the release decision outside the tool and always states that manual operator review is required.

## Inputs

Required input:

```bash
python3 scripts/operator_evidence_bundle_check.py <sanitized-evidence-directory> > bundle-summary.json
```

Optional input:

- A future sanitized manifest/checksum summary JSON from `operator_evidence_manifest_check.py`.
- A release candidate label via `--release-candidate-label`.
- A release candidate SHA via `--release-candidate-sha`.

Example:

```bash
python3 scripts/release_review_report_render.py \
  bundle-summary.json \
  --manifest manifest-summary.json \
  --release-candidate-label rc-2026-05-08 \
  --release-candidate-sha 45c8a18114890e2abe3d503c82022be7ee3fb47c \
  > release-review-report.md
```

## Output

The Markdown report contains:

- release candidate label and SHA when supplied;
- evidence bundle status;
- category status table;
- blocking and needs-review summary;
- manifest/checksum summary when supplied;
- explicit manual review required statement;
- explicit non-approval statement.

Exit codes:

- `0`: bundle summary status is `complete-review-required`;
- `1`: bundle summary status is incomplete, rejected, or otherwise not ready for review closure;
- `2`: renderer input could not be read or sanitized rendering failed.

## Sanitization Boundary

The renderer only emits bounded summary fields:

- category labels;
- artifact filename labels;
- validator filename labels;
- status labels;
- reason-code summaries;
- supplied release candidate label and SHA;
- manifest/checksum summary labels.

It does not emit raw artifact bodies, full raw JSON, request or response payloads, stack traces, credentials, cookies, sessions, database URLs, provider secrets, or real user identifiers. Sensitive-looking input values are replaced with `[redacted]`.

## Scope Boundary

The renderer is offline only. It does not make network calls, read environment variables, inspect deployment state, read provider credentials, touch databases, mutate runtime configuration, or change launch acceptance plumbing.

It is intentionally separate from:

- `scripts/launch_acceptance_evidence.py`;
- `scripts/release_gate_summary.sh`;
- launch acceptance fixtures;
- launch readiness audit documents.
