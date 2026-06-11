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

## Restore/PITR Evidence Path

For PostgreSQL restore/PITR, keep three contracts separate:

- `scripts/backup_restore_drill_check.sh --real-restore-evidence` validates the
  snake_case `wolfystock_restore_drill_evidence_v1` artifact produced after an
  externally executed isolated restore/PITR drill.
- `scripts/restore_pitr_operator_evidence_check.py --artifact` validates the
  camelCase `wolfystock_restore_pitr_operator_evidence_input_v1` operator
  review artifact in the evidence bundle.
- `scripts/isolated_pg_restore_smoke.py --artifact` validates the separate
  isolated restore smoke wrapper contract and always keeps
  `publicLaunchReady=false`.

Recommended sequence:

1. Run the dry-run preflight with fresh synthetic or sanitized metadata and a
   temp-only restore target.
2. Have an operator execute the real isolated PostgreSQL restore/PITR drill
   outside this repo helper path.
3. Convert the operator observations into sanitized artifacts only.
4. Validate both the real-drill summary and operator evidence artifacts.
5. Attach the sanitized outputs to the release evidence bundle for manual
   review.

Generated restore/PITR templates are review placeholders only. They intentionally
start with `outcome=needs-review`, `restoreCommandExecuted=false`,
`publicLaunchReady=false`, and `launchApproved=false`; they should validate as
`NO-GO` until an operator fills them from a real isolated drill.

Do not capture raw DSNs, env values, backup paths, database dumps, raw SQL,
hostnames, user rows, stack traces, or command output. Use bounded labels,
counts, checksums, timestamps, and sanitized ticket references instead.

Validator success only means the sanitized artifact is ready for manual review.
It is not public launch approval, does not prove this tool executed a restore,
and does not close the `real_isolated_postgresql_restore_pitr` gate by itself.

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
python3 scripts/restore_pitr_operator_evidence_check.py \
  --artifact "$EVIDENCE_DIR/restore_pitr_operator_evidence.json"
python3 scripts/security_operator_acceptance_check.py "$EVIDENCE_DIR/security_operator_acceptance.json"
python3 scripts/restore_pitr_operator_evidence_check.py "$EVIDENCE_DIR/restore_pitr_operator_evidence.json"
python3 scripts/security_operator_acceptance_check.py --artifact "$EVIDENCE_DIR/security_operator_acceptance.json"
python3 scripts/quota_operator_evidence_check.py "$EVIDENCE_DIR/quota_budget_operator_evidence.json"
python3 scripts/staging_ingress_operator_evidence_check.py "$EVIDENCE_DIR/staging_ingress_operator_evidence.json"
```

For the security artifact, `rbacFallbackDisable` must be accepted only when the
sanitized record shows fallback disabled for the pilot, complete route
inventory, explicit backend capability classification, frontend fail-closed
capability gates, explicit allow, legacy/missing fail-closed denial, rollback,
sanitized audit evidence, and unchanged runtime defaults. This is pilot
evidence; it does not change the production/default fallback value or approve
public launch.

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

## Optional Review Support

Use these optional local-only helpers when reviewer coordination needs more than
the core validate-manifest-bundle-report flow:

```bash
python3 scripts/operator_evidence_gap_analyzer.py \
  --artifact-dir "$EVIDENCE_DIR" \
  --output "$EVIDENCE_DIR/operator-evidence-gap-summary.json"

python3 scripts/operator_evidence_bundle_diff.py diff \
  --before <previous-bundle-summary.json> \
  --after "$EVIDENCE_DIR/operator-evidence-bundle-summary.json" \
  --before-manifest <previous-manifest.json> \
  --after-manifest "$EVIDENCE_DIR/operator-evidence-manifest.json" \
  --output "$EVIDENCE_DIR/operator-evidence-review-diff.md"

python3 scripts/operator_evidence_archive_pack.py pack \
  --workflow-output-dir "$EVIDENCE_DIR" \
  --output-dir <archive-output-dir> \
  --label <sanitized-archive-label> \
  --include-manifest \
  --include-report
```

These helpers are review support only. They must not approve launch, read raw
operator records, or replace category validators plus manual review.

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
