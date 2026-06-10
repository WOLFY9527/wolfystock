# Storage Migration Readiness Report Helper

`scripts/storage_migration_readiness_report.py` emits a sanitized, report-only
JSON readiness snapshot for local/offline storage migration evidence. It is a
preflight aid only and does not approve PostgreSQL cutover, source-of-truth
migration, live quota enforcement, cleanup, or destructive repair.

## Usage

```bash
python scripts/storage_migration_readiness_report.py --sqlite-db /path/to/local.sqlite
python scripts/storage_migration_readiness_report.py --sqlite-db /path/to/local.sqlite --fail-on-risk
```

Optional evidence inputs are file-based only:

```bash
python scripts/storage_migration_readiness_report.py \
  --postgres-schema-evidence docs/architecture/postgresql-baseline-v1.sql \
  --restore-pitr-evidence tests/fixtures/operator_evidence/sanitized_complete/restore_pitr_operator_evidence.json
```

The helper does not connect to PostgreSQL and does not execute restore commands.

## Report Fields

The JSON includes:

- `readOnly=true`, `mutationsExecuted=false`, `cleanupExecuted=false`, and
  `migrationExecuted=false`.
- `sqlite`: inspected table names, missing table/column counts, and aggregate
  row counts for quota readiness tables.
- `quotaReadiness`: duplicate quota window identity counts, blank/default
  `window_identity_key` counts, duplicate non-null reservation idempotency hash
  counts, and terminal reservation/window counter mismatch aggregates.
- `postgres`: `not_provided`, `partial`, `present`, or `rejected` schema
  evidence state based on supplied sanitized text only.
- `restorePitr`: `not_provided`, `partial`, `present`, or `rejected` evidence
  state based on supplied sanitized text only.
- `backtestCleanupConstraints`: checklist evidence that leaf tables require
  parent joins before any future cleanup design.

## Sanitization Boundary

Output is allowlisted aggregate JSON. It does not include DB paths, DSNs,
tokens, secrets, raw payloads, row ids, owner ids, reservation ids, idempotency
hash values, or quota window identity values.

## Stop Rules

Stop and split a new task if readiness work needs schema changes, migrations,
runtime storage changes, duplicate cleanup/merge/delete/vacuum, live PostgreSQL
connections, restore execution, quota service changes, API changes, provider
runtime changes, auth/security changes, or frontend changes.
