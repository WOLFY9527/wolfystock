# WolfyStock Archive And Historical Evidence Index

This index explains where historical evidence lives and how to use it safely.
Archived docs preserve provenance only. They are not current launch, frontend,
provider, security, portfolio, backtest, or API authority unless a current
authority document explicitly points to them for that specific question.

Start current work from:

- [Docs Index](./DOCS_INDEX.md)
- [System Handbook](./WOLFYSTOCK_SYSTEM_HANDBOOK.md)
- [AI Maintenance Manual](./WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md)
- [Audit Index](./audits/README.md)
- [File Governance Taxonomy](./architecture/file-governance-taxonomy.md)

## Current Archive Locations

| Location | Contents | Use |
| --- | --- | --- |
| `docs/audits/archive/` | Retired audit notes, consolidation plans, older launch/security/admin findings | Provenance only; do not use for current launch verdict |
| `docs/audits/archive/frontend/` | Retired frontend DOM, CSS, route, bundle, scroll, and old launch UX reports | Historical UI evidence only; current visual authority lives in `docs/codex/` and `docs/design/` |
| `docs/qa/archive/` | Point-in-time QA reports | QA provenance only |
| `docs/design/archive/old-ui/` | Transitional UI replacement notes | Historical migration context only |
| `docs/architecture/archive/audits/` | Older backend and backend/frontend audit reports | Historical architecture evidence |
| `docs/architecture/archive/multi-user-foundation/` | Multi-user foundation phase snapshots | Prior WS/multi-user design evidence |
| `docs/architecture/archive/phase-f/` | Phase F evidence plans and runbooks | Portfolio comparison/proof provenance |

## Historical Audit Files

Retained audit archive files include:

- `docs/audits/archive/final-pre-push-audit.md`
- `docs/audits/archive/markdown-inventory.md`
- `docs/audits/archive/markdown-consolidation-plan.md`
- `docs/audits/archive/release-integration-plan-main-ahead.md`
- `docs/audits/archive/admin-rbac-final-qa-report.md`
- `docs/audits/archive/security-admin-mfa-backend-foundation.md`
- `docs/audits/archive/wolfystock-final-admin-security-options-qa.md`
- `docs/audits/archive/db-index-migration-plan-auth-task-log.md`

Archived frontend audit evidence includes:

- `docs/audits/archive/frontend/frontend-launch-ux-round2-review.md`
- `docs/audits/archive/frontend/wolfystock-backtest-dom-verification.md`
- `docs/audits/archive/frontend/wolfystock-bundle-composition-report.md`
- `docs/audits/archive/frontend/wolfystock-chat-dom-verification.md`
- `docs/audits/archive/frontend/wolfystock-chinese-form-label-review.md`
- `docs/audits/archive/frontend/wolfystock-corrected-scroll-proof.md`
- `docs/audits/archive/frontend/wolfystock-css-cleanup-closure-report.md`
- `docs/audits/archive/frontend/wolfystock-echarts-chart-workspace-audit.md`
- `docs/audits/archive/frontend/wolfystock-global-codebase-audit.md`
- `docs/audits/archive/frontend/wolfystock-phase0-bundle-design-inventory.md`
- `docs/audits/archive/frontend/wolfystock-post-batch-integration-qa.md`
- `docs/audits/archive/frontend/wolfystock-product-command-card-owner-audit.md`
- `docs/audits/archive/frontend/wolfystock-scanner-dom-verification.md`
- `docs/audits/archive/frontend/wolfystock-scrollarea-custom-scrollbar-owner-inventory.md`
- `docs/audits/archive/frontend/wolfystock-scrollbar-dom-verification.md`

Archived QA reports include:

- `docs/qa/archive/full-stack-usability-audit-2026-05-01.md`
- `docs/qa/archive/wolfystock-duckdb-admin-control-surface-qa.md`
- `docs/qa/archive/wolfystock-portfolio-populated-holdings-qa.md`

Archived design-transition notes include:

- `docs/design/archive/old-ui/WOLFYSTOCK_FRONTEND_UI_DOC_REPLACEMENT_MAP.md`

Retained architecture archive files include:

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

Before moving or deleting tracked docs:

1. confirm current source-of-truth replacements;
2. search current references by full path and basename;
3. update links in active indexes and current docs;
4. run docs validation;
5. report what was moved/deleted and why;
6. keep launch and protected-domain authority unchanged unless explicitly
   scoped.
