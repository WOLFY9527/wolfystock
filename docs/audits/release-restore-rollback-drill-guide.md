# Release Restore/Rollback Drill Guide

Date: 2026-05-09
Mode: offline operator-review drill package. This does not change runtime code,
frontend UI, production database behavior, DuckDB runtime, portfolio/backtest
calculations, scanner/provider/AI logic, notification routing, launch
acceptance shared files, or release secret scanning.

## Purpose

Use `scripts/release_restore_rollback_drill.py` to validate that a release
candidate has an operator-reviewed restore and rollback packet before a launch
night decision. The CLI is offline and advisory. It validates sanitized labels
and plan notes, emits bounded JSON, and keeps release approval external.

It does not:

- connect to production databases;
- read secret values or environment files;
- run migrations;
- restore databases;
- delete files;
- send notifications;
- make network calls;
- approve a release.

## Offline Command

Default empty offline check:

```bash
python3 scripts/release_restore_rollback_drill.py --offline
```

This returns `drillStatus=NO-GO`, `manualReviewRequired=true`, and
`releaseApproved=false` until an operator supplies a sanitized artifact.

Validate a sanitized operator packet:

```bash
python3 scripts/release_restore_rollback_drill.py \
  --offline \
  --artifact path/to/sanitized-release-restore-rollback-drill.json
```

## Sanitized Artifact Shape

Minimum accepted input:

```json
{
  "schemaVersion": "wolfystock_release_restore_rollback_drill_input_v1",
  "backupLabel": "backup-ref-20260509-main",
  "restoreDrillLabel": "restore-drill-20260509-isolated",
  "rollbackOwnerLabel": "release-rollback-owner",
  "releaseCandidateLabel": "rc-main-ff199f88",
  "rpoRtoNotes": "rpo-15m-rto-60m-reviewed",
  "frontendRollbackPlan": "manual-route-withdrawal-and-ui-revert-reviewed",
  "backendRollbackPlan": "manual-service-revert-after-diff-review",
  "databaseRollbackRestorePlan": "manual-isolated-restore-review-before-db-action",
  "adminAuthRecoveryNote": "admin-reauth-and-break-glass-review-recorded",
  "operatorAssertions": {
    "productionDbConnected": false,
    "secretsRead": false,
    "migrationsRun": false,
    "databasesRestored": false,
    "filesDeleted": false,
    "notificationsSent": false,
    "networkCallsMade": false,
    "destructiveOperationsExecuted": false
  }
}
```

The fields are labels and summaries only. Do not include raw commands, DSNs,
URLs, file paths, SQL, logs, payloads, stack traces, private data, or secret
material. If more detail is needed, store it in the operator system of record
and reference it here with a sanitized ticket or evidence label.

## CLI Output Contract

The CLI emits bounded JSON with these required top-level fields:

- `drillStatus`
- `restoreReady`
- `rollbackReady`
- `destructiveOperationsExecuted=false`
- `networkCallsExecuted=false`
- `manualReviewRequired=true`
- `releaseApproved=false`

`drillStatus=REVIEW-READY` means the sanitized packet is structurally ready
for operator review. It is not a deployment decision and does not override the
manual release process.

`drillStatus=NO-GO` means the packet is missing required fields, contains
unsafe markers, or claims behavior that this offline package cannot validate.

## Launch-Night Operator Checklist

Before the release window:

- Confirm the release candidate label and commit under review.
- Confirm the latest backup label is recorded by the backup platform.
- Confirm the most recent restore/PITR drill label is isolated from production.
- Confirm RPO/RTO notes are current for this release window.
- Confirm frontend rollback ownership and route-withdrawal plan.
- Confirm backend rollback ownership and smallest reviewed revert/disable path.
- Confirm database rollback/restore plan separates application rollback from
  database restore.
- Confirm admin/auth recovery note covers reauth, admin access, and emergency
  operator access without exposing secret values.
- Confirm release secret scan evidence is clean or blocked with an owner.

During the release window:

- Keep restore, rollback, and admin/auth decisions operator-approved and
  recorded outside this CLI.
- Do not run database restore, migration rollback, destructive cleanup, or
  notification commands from this drill package.
- If an incident touches schema, data writes, auth, admin access, or portfolio
  records, pause release action and use the dedicated runbook for that domain.
- Re-run this CLI only against sanitized labels after the operator packet is
  updated.

Abort or rollback review:

- Verify whether the incident is frontend-only, backend runtime, database,
  auth/admin, or documentation-only.
- Prefer the smallest reviewed rollback path for the impacted domain.
- Never use retention cleanup as rollback.
- Never restore over production as a drill.
- Never print secret values, raw SQL, raw logs, raw provider payloads, session
  ids, cookies, private keys, or production database contents in evidence.

Evidence handoff:

- Attach the CLI JSON output to the release review packet.
- Keep `releaseApproved=false` in the evidence output.
- Record any actual release decision in the manual release approval process.
- Keep launch acceptance shared files unchanged unless a separate task
  explicitly authorizes integration.

## Review Boundary

This guide and CLI are intentionally domain-local. They do not update:

- `scripts/launch_acceptance_evidence.py`;
- `scripts/release_gate_summary.sh`;
- launch acceptance fixtures;
- `scripts/release_secret_scan.sh`;
- frontend page or component files.

Rollback for this package is reverting the commit that adds
`scripts/release_restore_rollback_drill.py`,
`tests/test_release_restore_rollback_drill.py`, and this guide.
