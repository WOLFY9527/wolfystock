# Database Operations

> Status: Canonical runbook
> Scope: repository-owned database diagnostics, PostgreSQL baseline artifacts, Phase F configuration, and DuckDB local analytics
> Audience: maintainers and operators; not a migration authorization

Database migrations, production DSNs, persistence semantics, owner isolation,
transactions, cash ledgers, and portfolio accounting are protected by
[`AGENTS.md`](../../AGENTS.md). The source, schema tests, and executable scripts
remain authoritative.

## PostgreSQL Baseline

[`docs/architecture/postgresql-baseline-v1.sql`](../architecture/postgresql-baseline-v1.sql)
is a design-phase baseline artifact. It is not wired into runtime and does not
perform a migration. Historical OHLCV and benchmark bodies remain in their
reviewed storage owners unless a separately authorized migration changes that
contract.

Do not execute the SQL against a real database based on this document alone.
Use the migration/bootstrap owner and its tests for any scoped implementation.

## Database Doctor

The repository doctor is read-only unless its command explicitly says
otherwise:

```bash
python scripts/database_doctor.py --help
python scripts/database_doctor_smoke.py --help
```

Start by checking the sanitized classification, likely store, and listed
read-first files. Do not infer that an empty database, unreachable database,
schema mismatch, corrupt database, or disabled bridge are the same condition.
Do not substitute a different DSN or production path to make a diagnostic
green.

### Troubleshooting

- `sqlite_primary_path_issue`: inspect `src/storage.py` and `src/config.py`.
- `config_issue`: inspect the applicable runtime settings and store owner.
- `schema_bootstrap_issue`: inspect `src/postgres_schema_bootstrap.py`.
- `pg_bridge_init_issue`: inspect `src/postgres_store_utils.py`.
- `domain_business_path_issue`: inspect the named domain service and store.

Run focused database-doctor tests before making a broader persistence claim.

### Phase F Configuration

Phase F cash-ledger and corporate-action comparisons are allowlist-gated. An
enabled comparison with an empty account allowlist skips comparison work; it
does not mean zero differences or a successful comparison. Preserve
owner/account isolation and never widen the allowlist through documentation or
diagnostic defaults.

## DuckDB Diagnostic Boundary

DuckDB is an optional diagnostic analytics capability. It is not a production
readiness claim and does not replace protected runtime, provider, scanner,
backtest, or portfolio semantics.

Run only one DuckDB init/ingest/build action at a time during local smoke.
Concurrent production operation requires a separately reviewed single-flight
ownership design, explicit permissions, bounded inputs, cleanup, and
deterministic comparison evidence. A missing database, an empty database, a
corrupt/unreadable database, a permissions failure, and a schema mismatch must
remain distinct.

## Cleanup And Rollback

Delete only task-owned temporary databases or explicitly configured local
cache artifacts. Never remove a broad data directory, another worktree's data,
or production material from a generic cleanup instruction. Roll back code or
schema changes at the smallest reviewed owner boundary and re-run the same
focused evidence command.
