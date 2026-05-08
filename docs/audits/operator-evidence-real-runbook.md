# Operator Evidence Real Runbook

Date: 2026-05-08
Scope: offline collection of sanitized operator evidence for manual review.

This runbook turns real operator observations into sanitized local artifacts.
It does not change launch acceptance plumbing, fixtures, scripts, tests, or
runtime behavior. A clean local result means the evidence packet is ready for
manual review only.

## Preparation

1. Work from the repository root:

```bash
cd path/to/daily_stock_analysis
git status --short
```

2. Create a private ignored working directory for local evidence files:

```bash
export EVIDENCE_DIR=operator-evidence-local/sanitized
mkdir -p "$EVIDENCE_DIR"
```

3. Confirm the operator has separate access to the real operational records.
Do not paste raw records into this repo, generated templates, validator output,
or review reports.

## Generate Templates

Generate the full offline template set:

```bash
python3 scripts/operator_evidence_template_pack.py "$EVIDENCE_DIR"
```

For one category, use:

```bash
python3 scripts/operator_evidence_template_pack.py \
  --category provider "$EVIDENCE_DIR"
```

The generator creates placeholders only. The generated files are not real
evidence until an operator replaces placeholders with sanitized summaries.

## Fill Sanitized Artifacts

Fill each template from the operator's real records using only:

- bounded labels;
- enum/status values;
- counts and timestamps;
- safe ticket or review references;
- short sanitized summaries.

Do not include raw logs, payload bodies, credential-bearing locations, personal
identifiers, cookies, sessions, DSNs, provider payloads, database dumps, private
keys, or raw tracebacks. Use
`docs/audits/operator-evidence-redaction-checklist.md` before validation.

The bundle checker currently treats these files as required:

- `provider_operator_evidence.json`
- `restore_pitr_operator_evidence.json`
- `security_operator_acceptance.json`
- `quota_budget_operator_evidence.json`
- `staging_ingress_operator_evidence.json`

Other generated artifacts, such as config snapshot, WS2/SSE, and manual review
record files, remain useful review attachments but may be reported as advisory
by the bundle checker.

## Run Validators

Run the domain validators for every artifact collected:

```bash
python3 scripts/provider_operator_evidence_check.py "$EVIDENCE_DIR/provider_operator_evidence.json"
python3 scripts/restore_pitr_operator_evidence_check.py "$EVIDENCE_DIR/restore_pitr_operator_evidence.json"
python3 scripts/security_operator_acceptance_check.py "$EVIDENCE_DIR/security_operator_acceptance.json"
python3 scripts/quota_operator_evidence_check.py "$EVIDENCE_DIR/quota_budget_operator_evidence.json"
python3 scripts/staging_ingress_operator_evidence_check.py "$EVIDENCE_DIR/staging_ingress_operator_evidence.json"
```

If present, also validate advisory artifacts:

```bash
python3 scripts/ws2_sse_operator_decision_check.py "$EVIDENCE_DIR/ws2_sse_operator_decision_evidence.json"
python3 scripts/config_snapshot_evidence_check.py "$EVIDENCE_DIR/config_snapshot_evidence.json"
python3 scripts/manual_release_approval_evidence_check.py \
  --artifact "$EVIDENCE_DIR/manual_release_approval_review_record.json"
```

Fix only the sanitized artifact content when a validator rejects an artifact.
Do not change validator code for evidence collection.

## Manifest

Create a checksum manifest after validators pass or return only review-required
statuses:

```bash
python3 scripts/operator_evidence_manifest_check.py create \
  --artifact-dir "$EVIDENCE_DIR" \
  --output "$EVIDENCE_DIR/operator-evidence-manifest.json"
```

Verify the manifest before handoff:

```bash
python3 scripts/operator_evidence_manifest_check.py verify \
  --artifact-dir "$EVIDENCE_DIR" \
  --manifest "$EVIDENCE_DIR/operator-evidence-manifest.json"
```

If verification fails, preserve the failing packet for review notes, regenerate
or repair the sanitized artifacts from the real records, and create a new
manifest.

## Bundle And Report

Aggregate required artifacts:

```bash
python3 scripts/operator_evidence_bundle_check.py "$EVIDENCE_DIR" \
  > "$EVIDENCE_DIR/operator-evidence-bundle-summary.json"
```

Render the manual review report:

```bash
python3 scripts/release_review_report_render.py \
  "$EVIDENCE_DIR/operator-evidence-bundle-summary.json" \
  --manifest "$EVIDENCE_DIR/operator-evidence-manifest.json" \
  --release-candidate-label <review-candidate-label> \
  --release-candidate-sha <release-candidate-sha> \
  > "$EVIDENCE_DIR/operator-evidence-review-report.md"
```

The report is informational. It must not be edited into a launch decision.

## Manual Review Handoff

Provide reviewers with:

- the sanitized artifact directory;
- validator command output or captured status summaries;
- `operator-evidence-manifest.json`;
- manifest verification result;
- `operator-evidence-bundle-summary.json`;
- `operator-evidence-review-report.md`;
- the redaction checklist result.

Reviewers must decide whether evidence is acceptable, whether advisory artifacts
need follow-up, and whether a separate scoped task should integrate accepted
evidence into shared launch artifacts.

## Rejection And Rollback

If evidence is rejected:

1. Do not alter launch acceptance files or runtime behavior.
2. Record the rejection reason in the review tracker using sanitized wording.
3. Move the rejected packet to a private review archive or delete it under the
   operator's retention policy.
4. Regenerate templates only if the artifact shape was wrong.
5. Re-collect sanitized summaries from the real records.
6. Re-run validators, recreate the manifest, verify it, aggregate the bundle,
   and render a fresh review report.
