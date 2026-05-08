# Operator Evidence Local Workspace Guide

Date: 2026-05-08
Scope: local-only operator evidence workspace hygiene.

Use these repository-root directories for operator evidence files that should
stay on the local machine:

- `operator-evidence-local/`
- `evidence-artifacts-local/`
- `release-review-local/`

These paths are ignored by git so operators can hold real source material,
redacted copies, workflow outputs, and review drafts without accidental staging.
Do not place real evidence under `tests/fixtures/`, `docs/`, `scripts/`, or any
other tracked path.

## Suggested Local Layout

```text
operator-evidence-local/
  intake/
  sanitized/
evidence-artifacts-local/
  sanitizer-output/
release-review-local/
  workflow-output/
  archives/
```

The `intake/` area is for local operator source material only. Keep it out of
review bundles. The `sanitized/` and `sanitizer-output/` areas are for redacted
JSON files that are ready for offline validator checks. The `workflow-output/`
area is for bundle summaries, manifests, and Markdown review reports generated
from sanitized inputs.

## Sanitizer And Workflow Commands

Create a redacted copy of one JSON artifact:

```bash
python3 scripts/evidence_artifact_sanitize.py sanitize \
  --input operator-evidence-local/intake/<artifact>.json \
  --output evidence-artifacts-local/sanitizer-output/<artifact>.json
```

Scan a local artifact without writing an output file:

```bash
python3 scripts/evidence_artifact_sanitize.py scan \
  --input operator-evidence-local/intake/<artifact>.json \
  --fail-on-findings
```

Generate sanitized templates for a new review pack:

```bash
python3 scripts/operator_evidence_workflow_run.py init \
  --output-dir operator-evidence-local/sanitized
```

Run the offline workflow against sanitized artifacts:

```bash
python3 scripts/operator_evidence_workflow_run.py check \
  --artifact-dir operator-evidence-local/sanitized \
  --output-dir release-review-local/workflow-output
```

The workflow output is a review aid. It does not change runtime behavior and is
separate from shared launch acceptance scripts and fixtures.

## Creating Review-Safe Fixtures

Only commit synthetic or fully sanitized fixtures that are intentionally created
for tests. A review-safe fixture should:

- use fake identifiers and bounded reason codes;
- avoid secrets, cookies, sessions, DSNs, provider payloads, DB dumps, request
  or response bodies, private keys, and real user contact details;
- avoid copied operational logs or source evidence bodies;
- keep real operator artifacts only in the ignored local workspace directories;
- pass the relevant offline validator before review.

Before staging any fixture, confirm the path is outside the local workspace and
inspect it directly:

```bash
git check-ignore -v tests/fixtures/operator_evidence/sanitized_complete/<fixture>.json || true
git diff -- tests/fixtures/operator_evidence/sanitized_complete/<fixture>.json
```

If a sanitized fixture is created from a local source artifact, keep the source
artifact in `operator-evidence-local/` and commit only the intentionally
review-safe fixture under `tests/fixtures/operator_evidence/`.
