# Operator Evidence Dry-Run Handoff

Date: 2026-05-08
Scope: synthetic, offline operator evidence workflow rehearsal for handoff
between release operators and manual reviewers.

This handoff demonstrates the evidence workflow using synthetic fixtures only.
It is a rehearsal packet, not real operator evidence, not a release decision,
and not a substitute for the real operator runbook or manual review.

## Safety Boundary

- Use only synthetic fixture directories and local review output directories.
- Do not use real operator artifacts, real URLs, emails, tokens, cookies,
  sessions, DSNs, provider payloads, database dumps, raw logs,
  request/response bodies, private keys, or personal identifiers.
- Keep every output local to `<review-output-dir>` and do not edit launch
  acceptance fixtures, launch acceptance scripts, runtime code, or shared
  release-gate plumbing.
- Treat all successful statuses as review support only. `releaseApproved`
  remains `false`, `publicLaunchReady` remains `false`, and synthetic fixtures
  are not accepted production evidence.

## Placeholder Inputs

Use placeholder paths when rehearsing this workflow:

- `<artifact-dir>`: synthetic sanitized fixture directory.
- `<unsafe-artifact-dir>`: synthetic unsafe fixture directory expected to fail
  safely.
- `<review-output-dir>`: local directory for generated review outputs.
- `<previous-review-output-dir>`: optional earlier synthetic review output for
  diff rehearsal.
- `<archive-output-dir>`: local directory for archive-package output.

## Dry-Run Sequence

### 1. Workflow Smoke

Run the full synthetic smoke. The unsafe fixture should be rejected without
leaking raw values.

```bash
python3 scripts/operator_evidence_workflow_smoke.py \
  --artifact-dir <artifact-dir> \
  --unsafe-artifact-dir <unsafe-artifact-dir> \
  --output-dir <review-output-dir>/workflow-smoke
```

Expected safe posture:

- sanitized fixture status: `complete-review-required`
- unsafe fixture status: `rejected-no-go`
- `releaseApproved=false`
- `publicLaunchReady=false`

### 2. Schema Reference Render

Render the offline schema reference used by reviewers to understand expected
artifact shapes.

```bash
python3 scripts/operator_evidence_schema_reference.py render \
  --output <review-output-dir>/operator-evidence-schema-reference.md \
  --json-output <review-output-dir>/operator-evidence-schema-reference.json
```

Expected safe posture:

- local reference files only
- no runtime state, environment values, network calls, or evidence bodies read

### 3. Sanitizer Scan Example

Scan one synthetic artifact before review. Use `--fail-on-findings` when the
handoff should stop on unsafe markers.

```bash
python3 scripts/evidence_artifact_sanitize.py scan \
  --input <artifact-dir>/provider_operator_evidence.json \
  --fail-on-findings
```

Expected safe posture:

- clean synthetic artifact: no unsafe findings
- unsafe synthetic artifact: bounded findings only, then `rejected-no-go`

### 4. Manifest Create And Verify

Create a checksum manifest for the synthetic artifact directory, then verify it
before any review handoff.

```bash
python3 scripts/operator_evidence_manifest_check.py create \
  --artifact-dir <artifact-dir> \
  --output <review-output-dir>/evidence-manifest.json

python3 scripts/operator_evidence_manifest_check.py verify \
  --artifact-dir <artifact-dir> \
  --manifest <review-output-dir>/evidence-manifest.json
```

Expected safe posture:

- matching manifest: review can continue
- missing or tampered artifact: `incomplete-no-go`
- manifest output contains labels, sizes, checksums, and reason codes, not raw
  artifact bodies

### 5. Bundle Check And Review Report

Run the workflow runner against the synthetic artifact directory. This writes
the standard review outputs.

```bash
python3 scripts/operator_evidence_workflow_run.py check \
  --artifact-dir <artifact-dir> \
  --output-dir <review-output-dir>
```

Expected outputs:

- `<review-output-dir>/bundle-summary.json`
- `<review-output-dir>/evidence-manifest.json`
- `<review-output-dir>/release-review-report.md`

Expected safe posture:

- complete synthetic bundle: `complete-review-required`
- missing required synthetic artifact: `incomplete-no-go`
- validator rejection: `rejected-no-go`
- `releaseApproved=false`
- `publicLaunchReady=false`

If a summary already exists and only the report needs to be re-rendered:

```bash
python3 scripts/operator_evidence_workflow_run.py report \
  --bundle-summary <review-output-dir>/bundle-summary.json \
  --output <review-output-dir>/release-review-report.md
```

### 6. Bundle Diff

Compare two synthetic review summaries before handoff. Include manifests when
both runs produced them.

```bash
python3 scripts/operator_evidence_bundle_diff.py diff \
  --before <previous-review-output-dir>/bundle-summary.json \
  --after <review-output-dir>/bundle-summary.json \
  --before-manifest <previous-review-output-dir>/evidence-manifest.json \
  --after-manifest <review-output-dir>/evidence-manifest.json \
  --output <review-output-dir>/review-diff.md
```

Expected safe posture:

- diff output uses bounded status and reason-code summaries only
- checksum changes are listed by sanitized manifest labels only

### 7. Archive Pack

Package the synthetic workflow outputs for manual-review rehearsal.

```bash
python3 scripts/operator_evidence_archive_pack.py pack \
  --workflow-output-dir <review-output-dir> \
  --output-dir <archive-output-dir> \
  --label <sanitized-archive-label> \
  --include-manifest \
  --include-report
```

Expected safe posture:

- archive index records file labels, byte sizes, checksums, manual review
  posture, and `releaseApproved=false`
- source artifact bodies are not copied into the archive index

### 8. Review Report Handoff

Hand reviewers only the synthetic review outputs:

- `bundle-summary.json`
- `evidence-manifest.json`
- `release-review-report.md`
- `review-diff.md`, when a previous synthetic run was compared
- archive package directory, when packaging was rehearsed

Reviewer conclusion for this dry-run should stay one of:

- `complete-review-required`
- `incomplete-no-go`
- `rejected-no-go`

Do not convert this rehearsal into shared launch acceptance evidence. For real
operator collection, use
`docs/audits/operator-evidence-real-runbook.md` and
`docs/audits/operator-evidence-redaction-checklist.md`.
