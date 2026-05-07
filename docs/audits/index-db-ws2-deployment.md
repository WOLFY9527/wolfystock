# DB / WS2 / Deployment Audit Index

Status: Current
Owner domain: Database readiness, WS2 runtime, and deployment documentation
index
Related docs: `docs/audits/public-launch-readiness-master.md`,
`docs/audits/public-launch-gap-register.md`,
`docs/audits/deployment-readiness-checklist.md`,
`docs/audits/archive/markdown-consolidation-plan.md`,
`docs/audits/archive/markdown-inventory.md`

Mode: docs-only navigation index. No runtime DB, WS2, deployment, or restore
behavior is changed by this index.

## Purpose

This index groups database production readiness, WS2 multi-instance runtime,
and release/deployment evidence. It does not authorize migration, cleanup,
restore, deployment, or runtime cutover work.

## Current canonical docs

- `docs/audits/public-launch-readiness-master.md`: executive launch status for
  DB, WS2, deployment, backup, and rollback readiness.
- `docs/audits/public-launch-gap-register.md`: detailed blockers for
  backup/restore, retention tiers, staging smoke, WS2 smoke, process-local SSE,
  and worker deployment model.
- `docs/audits/deployment-readiness-checklist.md`: release-candidate
  operational checklist and final go/no-go gate.
- `docs/audits/archive/release-integration-plan-main-ahead.md`: archived
  point-in-time main/ahead integration plan for the earlier local-ahead train.
- `docs/audits/release-rollback-runbook.md`: operational rollback runbook.
- `docs/audits/ci-postgres-gate-triage-guide.md`: CI/PostgreSQL triage runbook.
- `docs/audits/db-retention-backup-restore-drill-plan.md`: active backup,
  restore, retention, and drill plan.
- `docs/audits/ws2-multi-instance-smoke-test-design.md`: active design for the
  required synthetic multi-instance smoke.

## Partial docs

- `docs/audits/db-production-readiness-index-retention-audit.md`: DB readiness
  audit and launch blocker evidence; useful until accepted index/retention
  contracts land.
- `docs/audits/db-index-batch-b-execution-provider-cost-plan.md`: partial Batch
  B plan; smoke scaffold checks existing foundations while runtime/schema work
  remains deferred.
- `docs/audits/ws2-multi-user-runtime-cost-control-design.md`: WS2 architecture
  baseline with several foundation notes; multi-instance cutover and live
  enforcement remain future work.

## Superseded docs

- `docs/audits/archive/db-index-migration-plan-auth-task-log.md`: Batch A appears
  implemented; keep as historical plan unless Batch A detail is needed.

## Deferred docs

- `docs/audits/db-index-batch-b-execution-provider-cost-plan.md`: future
  runtime/schema migration and query-plan validation.
- `docs/audits/db-retention-backup-restore-drill-plan.md`: actual retention
  dry-runs and backup/restore drills remain deferred until exercised.
- `docs/audits/ws2-multi-instance-smoke-test-design.md`: executable smoke
  implementation and staging evidence remain deferred.
- `docs/audits/ws2-multi-user-runtime-cost-control-design.md`: external queue,
  multi-instance cutover, external SSE/progress replay, quota enforcement, and
  provider circuit enforcement remain future work.

## Launch blockers related to this domain

See `docs/audits/public-launch-readiness-master.md` and
`docs/audits/public-launch-gap-register.md`.

- Backup/restore drill, PITR target, encrypted backup policy, and post-restore
  smoke evidence are missing.
- Retention tiers remain undefined for several high-growth operational and
  user-owned domains.
- Staging public-readiness smoke through HTTPS reverse proxy is not accepted.
- WS2 executable synthetic smoke does not yet prove API A submit, worker lease,
  API B durable read, polling replay, retry/failure safety, and owner isolation.
- Process-local SSE remains the default and must not be represented as
  cross-instance reliable until external replay/cutover exists.
- Worker deployment topology, lease recovery, heartbeat, queue depth, and
  rollback evidence remain incomplete.

## Hard-to-classify docs

- `docs/audits/db-index-batch-b-execution-provider-cost-plan.md`: marked partial
  because it includes a non-destructive smoke scaffold but still defers
  runtime/schema work.
- `docs/audits/ws2-multi-user-runtime-cost-control-design.md`: spans runtime,
  cost, provider circuit, cache, and deployment concerns; this index links it
  for WS2/deployment while the cost index links it for quota/ledger context.
