# WolfyStock Archive And Historical Evidence Index

This index explains where historical evidence lives and how to use it safely.
It does not move, delete, or reclassify tracked files.

## Rule

Historical evidence is useful for provenance, but it is not current authority
unless a current authority document explicitly points to it for the question at
hand.

Start current work from:

- [Docs Index](./DOCS_INDEX.md)
- [System Handbook](./WOLFYSTOCK_SYSTEM_HANDBOOK.md)
- [Audit Index](./audits/README.md)
- [Public Launch Readiness Master](./audits/public-launch-readiness-master.md)
- [Public Launch Gap Register](./audits/public-launch-gap-register.md)

## Current Archive Locations

| Location | Contents | Use |
| --- | --- | --- |
| `docs/audits/archive/` | Retired audit notes, consolidation plans, older launch/security/admin findings | Provenance only; do not use for current launch verdict |
| `docs/architecture/archive/audits/` | Older backend and backend/frontend audit reports | Historical architecture evidence |
| `docs/architecture/archive/multi-user-foundation/` | Multi-user foundation phase snapshots | Prior WS/multi-user design evidence |
| `docs/architecture/archive/phase-f/` | Phase F evidence plans and runbooks | Portfolio comparison/proof provenance |

## Active Indexes That Mention Archives

- [Audit Index](./audits/README.md): current audit navigation and explicit
  historical/superseded notes.
- [Public Launch Readiness Master](./audits/public-launch-readiness-master.md):
  launch verdict and warning not to treat archived audits as current launch
  control.
- [Public Launch Gap Register](./audits/public-launch-gap-register.md):
  current blocker register and source-doc list.
- [Provider/data/options index](./audits/index-provider-data-options.md)
- [Cost/quota/observability index](./audits/index-cost-quota-observability.md)
- [DB/WS2/deployment index](./audits/index-db-ws2-deployment.md)
- [Security/RBAC/MFA index](./audits/index-security-rbac-mfa.md)

## Historical Audit Files

Retained audit archive files currently include:

- `docs/audits/archive/final-pre-push-audit.md`
- `docs/audits/archive/markdown-inventory.md`
- `docs/audits/archive/markdown-consolidation-plan.md`
- `docs/audits/archive/release-integration-plan-main-ahead.md`
- `docs/audits/archive/admin-rbac-final-qa-report.md`
- `docs/audits/archive/security-admin-mfa-backend-foundation.md`
- `docs/audits/archive/wolfystock-final-admin-security-options-qa.md`
- `docs/audits/archive/db-index-migration-plan-auth-task-log.md`

Retained architecture archive files currently include:

- `docs/architecture/archive/audits/backend-final-audit-report.md`
- `docs/architecture/archive/audits/backend-frontend-global-audit-report.md`
- `docs/architecture/archive/multi-user-foundation/multi-user-foundation-phase0.md`
- `docs/architecture/archive/multi-user-foundation/multi-user-foundation-phase1.md`
- `docs/architecture/archive/multi-user-foundation/multi-user-foundation-phase2.md`
- `docs/architecture/archive/multi-user-foundation/multi-user-foundation-phase3.md`
- `docs/architecture/archive/phase-f/phase-f-cash-ledger-evidence-collection-runbook-2026-04-21.md`
- `docs/architecture/archive/phase-f/phase-f-cash-ledger-non-empty-evidence-collection-plan-2026-04-21.md`
- `docs/architecture/archive/phase-f/phase-f-corporate-actions-non-empty-evidence-collection-plan-2026-04-21.md`
- `docs/architecture/archive/phase-f/phase-f-trades-list-evidence-collection-runbook-2026-04-20.md`

## How To Use Historical Evidence

Use historical docs to answer:

- why a decision was made;
- which risks were already found;
- which files or docs were consolidated before;
- which validation commands existed at that point in time;
- what not to repeat in future cleanup tasks.

Do not use historical docs to claim:

- current launch readiness;
- current route migration completion;
- current API shape;
- current provider entitlement or freshness;
- current security/RBAC behavior;
- current portfolio/backtest accounting safety;
- current browser/UI acceptance.

For current claims, inspect current code/tests/docs and run current validation.

## Local Artifacts Are Not Archive Authority

The following local/ignored paths are not repository archive authority:

- `.claude/reviews/`
- `.codex/`
- `.codex-artifacts/`
- `reports/`
- `test-results/`
- `playwright-report/`
- `coverage/`
- `repo_archive/`
- `repo_trash/`

Do not cite them as current truth in PRs or final reports unless a task
explicitly asks for a local report artifact and the artifact is clearly labeled
as local evidence.

## Future Archive Cleanup

Archive moves, deletes, or consolidations require a separate explicit task.
Before moving or deleting tracked docs:

1. confirm current source-of-truth replacements;
2. search current references;
3. update links in current indexes;
4. run docs validation;
5. report what was moved/deleted and why;
6. keep launch and protected-domain authority unchanged unless explicitly
   scoped.
