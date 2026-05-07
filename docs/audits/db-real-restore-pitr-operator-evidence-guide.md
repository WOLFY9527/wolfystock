# Real Restore/PITR Operator Evidence Guide

Date: 2026-05-08
Mode: domain-local operator guide and offline validator contract. This does not change storage runtime, launch acceptance, PostgreSQL infrastructure, DuckDB runtime, portfolio accounting, backtest calculations, provider behavior, auth/RBAC, quota enforcement, scanner scoring, AI decisions, or notifications.

## Purpose

Real isolated PostgreSQL restore/PITR evidence remains a public-launch blocker until an operator runs an approved external drill and submits a sanitized artifact for review.

The local validator in `scripts/restore_pitr_operator_evidence_check.py` checks only the shape and sanitization posture of an externally produced JSON artifact. It does not execute `pg_restore`, `psql`, `dropdb`, `createdb`, Docker, migrations, network calls, or production database operations. Passing the validator means the artifact is suitable for domain review; it does not approve launch and is not integrated into the global launch acceptance matrix.

## Safe Operator Workflow

1. Provision an isolated restore target outside production storage.
2. Run the restore/PITR drill using the approved operator runbook and platform controls.
3. Capture only sanitized summaries:
   - drill id, environment, operator label, start/end timestamps;
   - sanitized backup artifact reference;
   - sanitized restore target label;
   - whether restore command execution occurred;
   - explicit `destructiveProductionCommandExecuted=false`;
   - PITR target timestamp;
   - verification query count/checksum summaries only;
   - observed RPO/RTO in seconds;
   - operator outcome;
   - evidence redaction version.
4. Remove or mask secrets, DSNs, hostnames with credentials, raw logs, stack traces, raw SQL, dumps, tokens, private keys, and production command text.
5. Run the offline validator locally against the sanitized JSON.
6. Attach the validator JSON output to the domain review packet, not to the launch acceptance matrix.

## Artifact Contract

Minimum accepted input shape:

```json
{
  "schemaVersion": "wolfystock_restore_pitr_operator_evidence_input_v1",
  "drillId": "restore-pitr-2026-05-08-001",
  "environment": "isolated-restore",
  "operator": "ops-oncall-sanitized",
  "startedAt": "2026-05-08T09:00:00Z",
  "completedAt": "2026-05-08T09:37:00Z",
  "backupArtifactRef": "backup-ref:sha256-0123456789abcdef",
  "restoreTarget": "restore-target:sandbox-pg-20260508",
  "restoreCommandExecuted": true,
  "destructiveProductionCommandExecuted": false,
  "pitrTargetTimestamp": "2026-05-08T08:45:00Z",
  "verificationQueries": [
    {
      "label": "auth-row-count",
      "resultKind": "count",
      "observedCount": 12,
      "expectedCount": 12,
      "checksum": "sha256:auth-count-fixture"
    }
  ],
  "rpoObservedSeconds": 420,
  "rtoObservedSeconds": 2220,
  "outcome": "accepted",
  "evidenceRedactionVersion": "restore-pitr-redaction-v1",
  "localGeneration": {
    "checkerRanRestoreCommands": false,
    "networkCallsEnabled": false,
    "productionStorageTouched": false,
    "productionSecretsRead": false,
    "rawLogsIncluded": false,
    "runtimeBehaviorChanged": false
  }
}
```

Allowed `environment` values:

- `isolated-restore`
- `staging-restore`
- `sandbox`

Allowed `outcome` values:

- `accepted`
- `rejected`
- `needs-review`

Only `outcome=accepted` can produce `finalStatus=EVIDENCE-READY`. `rejected` and `needs-review` remain `NO-GO` for this evidence slice.

## Offline Validation

Run:

```bash
python3 scripts/restore_pitr_operator_evidence_check.py \
  --artifact /path/to/sanitized-restore-pitr-evidence.json
```

The validator emits JSON with:

- `finalStatus`: `EVIDENCE-READY` or `NO-GO`;
- `launchApproved=false`;
- `databaseCommandsRunByValidator=false`;
- `runtimeBehaviorChanged=false`;
- per-check sanitized findings with paths and reason codes only.

The validator rejects artifacts with:

- production DSNs, URL credentials, passwords, tokens, cookies, private keys, or secret-like values;
- raw SQL dumps, raw query text, raw logs, raw payloads, raw responses, or stack traces;
- destructive production command markers;
- `destructiveProductionCommandExecuted=true`;
- missing explicit isolated/staging/sandbox environment;
- unsafe restore target labels;
- launch-approved, launch-go, release-approved, or bare `GO` claims;
- missing verification query summaries or non-count/checksum query evidence;
- missing or invalid RPO/RTO observations.

## Review Boundary

This kit is intentionally not wired into:

- `scripts/launch_acceptance_evidence.py`;
- `scripts/release_gate_summary.sh`;
- launch acceptance fixtures;
- launch acceptance readiness docs.

Domain reviewers may use the output as evidence that a sanitized external drill artifact is structurally reviewable. A separate launch acceptance update is required before this can affect the public-launch matrix.
