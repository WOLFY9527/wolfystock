# DB Retention and Backup/Restore Drill Plan

Date: 2026-05-07
Mode: docs-only planning artifact. No runtime code, schema, migrations, tests, live database contents, provider behavior, auth behavior, cost behavior, portfolio/backtest logic, or storage implementation was changed or inspected.

## 1. Executive Summary

Current public multi-user deployment verdict for this slice: **NO-GO until retention tiers and restore drills are accepted and exercised**.

The current database readiness posture has improved through DB Index Batch A,
which covered the first production-critical auth/session and durable
task/progress lookup paths, and through a local dry-run PostgreSQL
backup/restore/PITR preflight that validates simulated metadata, backup
artifact presence, timestamp sanity, schema compatibility, PITR window/WAL
archive metadata, sanitized evidence output, and temp-only restore target
isolation. Batch B indexes, retention implementation, cleanup jobs,
PostgreSQL backup automation, and real isolated restore drill evidence remain
future work.

This plan defines the retention tiers, backup policy, restore drill scope, validation checklist, rollback/failure handling, and future Codex prompts needed before public onboarding. It is intentionally planning-only and does not authorize cleanup, migration, DB access, schema changes, or runtime behavior changes.

Public deployment blockers covered by this document:

- Retention tiers are not yet accepted for high-growth operational and user-owned tables.
- Backup policy is not yet proven for encrypted PostgreSQL production data.
- Local dry-run PostgreSQL restore/PITR evidence preflight exists, but real
  isolated PostgreSQL restore execution, staging restore smoke, encrypted
  backup infrastructure proof, and PITR execution evidence have not been
  produced.
- Post-restore smoke checks are not yet standardized across auth, task polling, admin logs, cost observability, and portfolio/backtest artifacts.

## 2. Scope and Non-goals

Included:

- Retention tier definitions for logs, tasks, LLM/cost rows, provider diagnostics, auth/session events, and large user artifacts.
- PostgreSQL production backup baseline.
- Restore drill runbook for local synthetic restore, staging restore, and point-in-time restore where supported.
- Data safety rules for secrets, credential rotation, and synthetic validation data.
- Verification checklist and failure/rollback plan.
- Future implementation prompts.

Excluded:

- No runtime code changes.
- No schema or migration changes.
- No database reads, writes, cleanup, export, restore, or row inspection.
- No `storage.py` changes.
- No provider, analysis, options, auth, cost, portfolio, scanner, or backtest behavior changes.
- No `ci_gate` requirement for this docs-only plan.

## 3. Retention Tiers

Retention must be preview-first. Every future cleanup implementation should support dry-run output before deletion: matched row counts, oldest/newest candidate rows, estimated bytes where production-safe, policy version, protected-row reasons, and whether actual delete is allowed.

| Domain | Proposed default retention | Long-lived summary / archive | Deletion posture | Public readiness note |
| --- | --- | --- | --- | --- |
| Admin logs | 365 days minimum for security/admin/audit events; 90-180 days for routine operational noise if separable | Monthly immutable audit summary, backup/restore drill events, admin write/deny/security aggregates | Security-sensitive events should be fail-closed and preserved longer than routine logs | Existing admin log retention/capacity cleanup is a foundation, but policy needs explicit production acceptance. |
| Execution logs | 90-180 days raw sessions/events; 30-90 days for verbose debug detail | Per-route/status/provider/model/channel aggregates for 1-2 years | Cleanup must preserve incident windows and security-relevant events | Needed for support/admin evidence without allowing logs to dominate storage. |
| Durable task states | 30-90 days for completed terminal task rows; 90-180 days for failed/canceled rows | Keep safe terminal summary, owner, status, timestamps, result pointer, sanitized reason code | Do not delete active/running/leased rows; stale cleanup must be separate from terminal retention | Batch A indexes exist; lifecycle cleanup remains future work. |
| Durable progress events | 7-14 days for completed tasks; 30 days for failed/debug samples | Compact terminal task timeline into bounded summary | Delete bulky replay events only after terminal summary is persisted and verified | Progress rows can grow faster than task state rows once polling/replay expands. |
| LLM usage/cost ledger | Raw usage/cost rows 90-180 days; pricing snapshots kept while referenced | Monthly owner/guest/route/model aggregates for 2+ years | Do not use retention as quota reconciliation; aggregate before cleanup | Cost observability is not quota enforcement. Public use needs clear labels and dry-run reports. |
| Provider circuit events/probes | Raw events/probes 30-90 days; longer for enforcement pilots or outages | Provider/route/reason daily aggregates for 1 year | Store bounded reason labels only; avoid raw URLs, payloads, stack traces, credentials, or query strings | Current provider circuit storage/diagnostics are observational/dry-run; runtime enforcement remains future work. |
| Sessions/auth events | Sessions expire per auth policy; revoked/expired sessions retained 30-90 days for audit; login/security events 365 days minimum | Account security aggregates, revocation history, MFA/reauth events when enabled | Do not retain raw session ids, cookies, passwords, password hashes, or recovery secrets in logs | Public readiness still depends on MFA and fail-closed security audit policy. |
| Portfolio artifacts | Source-of-truth accounting records indefinite by default; exports/import raw-ish payloads 30-180 days by size/sensitivity | User export archives and replay-safe normalized ledger snapshots | Do not TTL trades, cash ledger, corporate actions, holdings, positions, lots, daily snapshots, or FX records by default | Financial records need restore/replay correctness more than cleanup aggressiveness. |
| Backtest artifacts | Run summaries 1+ year; large exports/traces/artifacts 30-180 days by size | Strategy/run metadata and reproducibility inputs retained longer than generated files | Cleanup must not alter deterministic result history or user-visible completed run summaries without policy | Artifacts are a known growth surface and need size dashboards. |
| Scanner artifacts | User-visible runs/candidates 180-365 days; bulky diagnostics 30-90 days | Theme/profile/market aggregates and watchlist links | Watchlist items remain until user deletion; old candidate diagnostics can compact | Scanner rankings and deterministic selection are outside this plan. |
| Guest/cache metadata | 24 hours to 7 days | None unless abuse/security aggregate is needed | Keep guest and authenticated data isolated; avoid cross-user cache state | Guest retention must align with public preview and rate-limit posture. |
| Options future cache rows | Fixture data versioned with code; future live chain cache minutes/hours, not days | Provider entitlement/freshness metadata only | Do not store raw provider payloads unless explicitly approved and short-lived | Current Options Lab remains fixture/demo analysis, not live production data. |

Minimum implementation guardrails for future retention work:

- Use owner/domain-aware cleanup for user data.
- Keep financial source-of-truth records out of default TTL cleanup.
- Keep audit/security logs longer than operational debug logs.
- Separate raw rows from aggregate rows.
- Never treat cleanup as rollback.
- Add dry-run reports before enabling destructive cleanup.

## 4. Backup Policy

Production baseline:

- PostgreSQL should be the durable public multi-user store.
- SQLite remains local/dev/compatibility posture unless a separate cutover is approved.
- Backups must be encrypted at rest and in transit.
- Backup storage must be isolated from the primary DB host and primary service account.
- Restore credentials must be separate from runtime application credentials where the platform supports it.

Recommended policy:

| Area | Baseline policy |
| --- | --- |
| Frequency | Full backup daily; WAL/PITR or incremental backup at 15-minute RPO target where supported. |
| Retention duration | Daily backups for 14-30 days; weekly backups for 8-12 weeks; monthly backups for 12 months; longer only if compliance requires it. |
| Encryption | Provider-managed KMS or customer-managed KMS; encryption enforced for backup storage, transfer, and restore targets. |
| Access control | Least-privilege backup operator role; break-glass access documented; backup deletion requires elevated approval; application runtime role cannot delete backups. |
| Offsite copy | At least one cross-zone or cross-region copy outside the primary DB failure domain. |
| Integrity checks | Automated backup completion alerts, checksum or provider integrity status, and restore drill success evidence. |
| Secret handling | Backups may contain credential references or hashed auth material; do not print or export secret values in drill logs. |

Targets before public onboarding:

- RPO: 15 minutes or better for public production.
- RTO: 60 minutes or better for first public tier.
- Restore drill cadence: monthly until launch readiness, then quarterly after two consecutive clean drills.
- Alerting: backup missing/failed, PITR window broken, offsite copy missing, restore drill overdue.

## 5. Restore Drill Runbook

Drills must restore into isolated environments. Do not restore over production as a test.

### 5.1 Local Synthetic Restore

Purpose: verify the runbook and application smoke checks without production data.

Inputs:

- Synthetic PostgreSQL dump or disposable backup artifact.
- Synthetic users, sessions, task rows, logs, LLM/cost rows, provider circuit events, scanner/backtest rows, and portfolio fixtures.
- No real provider credentials, broker credentials, API keys, cookies, session ids, password hashes, prompts, provider payloads, or user content.

Procedure:

1. Provision an isolated local PostgreSQL instance or disposable container.
2. Restore the synthetic backup into a new database.
3. Apply only already-approved migrations/indexes for the target release candidate.
4. Boot the app against the restored database using synthetic env values.
5. Run the verification checklist in Section 7.
6. Destroy the local restore target after evidence is captured.

Pass criteria:

- App boots successfully.
- Synthetic auth/session/task/log/cost/provider/scanner/backtest/portfolio rows are readable through intended paths.
- No secrets or production identifiers appear in logs or evidence.

### 5.2 Staging Restore

Purpose: prove an operational restore can support public-readiness smoke checks in a staging topology.

Inputs:

- Production-like backup artifact from staging or sanitized production-derived backup if approved.
- Staging credentials rotated for the restored target.
- Synthetic or anonymized smoke users and data.

Procedure:

1. Provision an isolated staging restore target in a separate DB instance.
2. Restore the backup without modifying the active staging or production DB.
3. Rotate app credentials and revoke any restored runtime secrets before application boot.
4. Point one staging app instance at the restore target.
5. Confirm HTTPS/reverse proxy access where relevant, while keeping backend `:8000` private.
6. Run post-restore verification checks and record PASS/FAIL evidence.
7. Tear down or quarantine the restore target according to the data handling policy.

Pass criteria:

- Restore target supports auth login, task status/polling, admin logs, cost dashboard, and artifact reads.
- Owner isolation checks pass against synthetic/anonymized users.
- Backup/restore drill evidence does not expose secret values or real private data.

### 5.3 Point-in-time Restore

Purpose: prove recovery to a specific timestamp before a bad migration, cleanup job, or incident.

Supported only if the production PostgreSQL platform provides WAL archiving/PITR or equivalent managed restore points.

Procedure:

1. Select a synthetic incident timestamp in staging.
2. Create known pre-incident and post-incident marker rows using synthetic data.
3. Restore to a timestamp after the pre-incident marker and before the post-incident marker.
4. Verify the pre-incident marker exists and the post-incident marker does not.
5. Run the same application smoke checks as staging restore.

Pass criteria:

- PITR timestamp behavior matches expectation.
- Indexes and constraints remain present after restore.
- App and admin smoke checks pass without using production secrets.

## 6. Data Safety Rules

Backup and restore evidence must avoid sensitive values wherever possible.

Required rules:

- Do not print `.env` values, provider credentials, broker credentials, webhook URLs, private keys, cookies, raw session ids, API keys, passwords, password hashes, TOTP secrets, recovery codes, raw prompts, raw provider payloads, raw LLM responses, or stack traces containing private data.
- Use synthetic users and anonymized/synthetic smoke data for drills.
- Use bounded reason codes and labels for provider/auth/task failures.
- Mask notification targets, broker handles, account references, and user identifiers in drill evidence.
- Rotate application DB credentials after restoring a backup into staging.
- Rotate or revoke any provider/broker/webhook credentials if a restore target could contain usable secret material.
- Destroy or access-lock restore targets after the drill.
- Store drill reports in docs or deployment evidence only after confirming they contain no sensitive values.

## 7. Verification Checklist

Required post-restore checks:

| Check | Expected evidence |
| --- | --- |
| Row counts | Table/domain counts for auth sessions, durable tasks, progress events, execution/admin logs, LLM/cost rows, provider events/probes, scanner/backtest artifacts, and portfolio fixtures match expected synthetic counts or approved anonymized count ranges. |
| Index presence | Batch A indexes exist; Batch B indexes are explicitly marked future until implemented; no expected production index is missing after restore. |
| App boot | App starts against the restored DB and readiness reports storage as available. |
| Auth login | Synthetic user login succeeds; revoked/expired synthetic session behavior matches policy; owner isolation remains intact. |
| Analysis status/poll | Synthetic durable task status and progress polling return expected terminal state and replay sequence. |
| Admin logs | Admin log list, detail, storage summary, and retention dry-run preview work without exposing raw secrets. |
| Cost dashboard | Read-only LLM/cost summary renders expected synthetic owner/guest/route/model aggregates; it is labeled observability, not enforcement. |
| Provider diagnostics | Provider circuit/probe diagnostics show bounded labels and no raw provider payloads, URLs, credentials, or stack traces. |
| Scanner/backtest | Synthetic scanner and backtest runs/artifacts are readable; cleanup candidates are only previewed. |
| Portfolio replay | Synthetic portfolio account, trades, cash ledger, holdings, daily snapshot, and FX data produce expected totals. |
| Backup metadata | Backup timestamp, restore target, RPO/RTO result, operator, and evidence location are recorded with no secret values. |

Suggested result format:

```text
Restore drill date:
Source backup timestamp:
Restore target:
RPO observed:
RTO observed:
Synthetic/anonymized data only: yes/no
Secrets printed in evidence: no
Checks passed:
Checks failed:
Blockers:
Rollback/follow-up:
```

### 7.1 Production-like Preflight Before a Real Drill

Before any staging or production-adjacent restore drill, run the local dry-run
preflight with simulated metadata and a temp-only restore target:

```bash
scripts/backup_restore_drill_check.sh \
  --metadata tests/fixtures/ops/backup_restore_preflight_metadata.json \
  --restore-target /tmp/wolfystock-restore-drill/restored.sqlite \
  --max-age-hours 99999
```

For launch evidence, operators should replace the fixture with freshly generated
synthetic or sanitized metadata. The metadata must include:

- `backup_id`
- `created_at`
- `artifact_path`
- `schema_version=backup_restore_preflight_v1`
- `application_schema_version=wolfystock_ops_readiness_v1`
- `database_engine=postgresql`
- `source_environment` set to `synthetic`, `sanitized`, or `anonymized`
- `pitr.target_time`
- `pitr.window_start`
- `pitr.window_end`
- `pitr.wal_archive_path`
- `pitr.restore_point_label`

The preflight is intentionally dry-run only. It verifies backup artifact
presence, timestamp freshness, metadata/application schema compatibility, PITR
target-within-window metadata, WAL/archive marker presence, optional local
safe-test DSN hygiene, sanitized output, and restore target isolation; it
refuses missing or stale metadata, non-temp restore targets, production-like
paths/DSNs, and any real restore by default. Passing this preflight does not
prove that PostgreSQL backup, encryption, PITR, or restore infrastructure
works. It only produces safe launch readiness evidence that the drill inputs and
isolation plan are coherent before running a real isolated restore.

## 8. Rollback and Failure Plan

If backup creation fails:

- Treat public deployment as blocked.
- Keep current runtime serving unchanged.
- Alert operators and record the failed backup timestamp.
- Do not run migrations, cleanup jobs, or public onboarding until a fresh backup succeeds.

If restore fails:

- Keep production unchanged.
- Quarantine the restore target for diagnosis.
- Capture sanitized error category, backup id/timestamp, restore target type, and phase where failure occurred.
- Do not expose restored staging app to public testers.
- Re-run from a known-good backup after root cause is fixed.

If post-restore validation fails:

- Mark the drill failed even if the DB restore command succeeded.
- Keep public deployment as **NO-GO**.
- Classify failure by domain: auth, durable tasks, logs, cost, provider diagnostics, scanner/backtest, portfolio, indexes, or app boot.
- Do not use retention cleanup to repair restore inconsistencies.
- If the failure follows a migration/index change, roll back application deployment to last-good commit/image and restore DB only when data correctness requires it.

If retention cleanup later deletes too much:

- Stop cleanup jobs immediately.
- Preserve affected backup and WAL/PITR window.
- Decide whether to restore whole DB, restore selected tables into a side database for manual recovery, or replay from application-level exports.
- Rotate credentials if restored copies contain secret-bearing material.
- Produce an incident report before re-enabling cleanup.

## 9. Recommended Future Codex Prompts

### Retention Dry-run Report

```text
Task: Implement a docs-backed retention dry-run report only.

Repo: /Users/yehengli/daily_stock_analysis on main.

Scope: add a non-destructive report path for high-growth DB domains: admin logs, execution logs, durable task states, durable progress events, LLM usage/cost ledger, provider circuit events/probes, auth/session events, scanner/backtest artifacts, guest/cache metadata, and portfolio artifact candidates.

Hard constraints: dry-run only; no deletion; no runtime provider/auth/cost/portfolio/scanner/backtest behavior changes; no secrets or DB contents printed beyond counts, oldest/newest timestamps, estimated bytes where safe, and protected-row reasons.

Validation: focused tests for the report helper and docs diff checks.
```

### Backup Restore Smoke Script

```text
Task: Add a synthetic backup/restore smoke script for PostgreSQL public-readiness drills.

Repo: /Users/yehengli/daily_stock_analysis on main.

Scope: create a script that restores a synthetic PostgreSQL backup into an isolated target and runs post-restore checks for row counts, Batch A index presence, app boot readiness, synthetic auth login, durable task status/poll, admin logs, cost dashboard, provider diagnostics, scanner/backtest artifacts, and portfolio replay.

Hard constraints: synthetic/anonymized data only; no production DB access; no secrets printed; no restore over production; no runtime behavior changes.

Validation: script unit/smoke tests with disposable local DB or documented skip when PostgreSQL is unavailable.
```

### Batch B Indexes

```text
Task: Implement DB Index Batch B as additive indexes only.

Repo: /Users/yehengli/daily_stock_analysis on main.

Read first: docs/audits/db-index-migration-plan-auth-task-log.md and docs/audits/db-retention-backup-restore-drill-plan.md.

Scope: add the next owner/status/time/admin drilldown indexes for execution/admin logs, LLM usage/cost observability, scanner/backtest artifacts, and portfolio read projections where documented and query-plan justified.

Hard constraints: additive indexes only; preserve SQLite/local compatibility; no retention cleanup; no quota enforcement; no provider/cache behavior change; no portfolio accounting change; no scanner/backtest calculation change; no Options Lab change; no RBAC route change.

Validation: migration smoke, query-plan checks where available, focused tests, and docs/changelog update.
```

## 10. Acceptance Checklist

This plan is accepted when:

- Retention tiers are reviewed and either approved or adjusted by domain owners.
- PostgreSQL backup frequency, encryption, access control, offsite copy, and retention duration are approved.
- Local synthetic restore drill passes.
- Staging restore drill passes.
- PITR drill passes or the production platform limitation is explicitly documented.
- Verification checklist evidence is captured without secrets.
- Public deployment checklist is updated from **NO-GO** only after drills and retention dry-run reports pass.

## 11. Validation for This Document

Required docs-only validation:

```bash
git diff -- docs/audits/db-retention-backup-restore-drill-plan.md docs/CHANGELOG.md
git diff --check -- docs/audits/db-retention-backup-restore-drill-plan.md docs/CHANGELOG.md
```

No `ci_gate` is required for this docs-only planning pass.
