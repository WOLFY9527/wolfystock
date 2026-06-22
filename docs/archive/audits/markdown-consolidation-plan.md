# Audit Markdown Consolidation Plan

> Historical evidence note
>
> Superseded for current audit navigation by `docs/audits/README.md` and for
> the current public launch verdict by
> `docs/audits/public-launch-readiness-master.md`. This file remains useful as
> a point-in-time consolidation plan only.

Status: Historical note
Owner domain: Documentation governance
Related docs: `docs/audits/archive/markdown-inventory.md`, `docs/audits/archive/final-pre-push-audit.md`

Mode: docs-only consolidation plan. No audit files, runbooks, product code,
tests, frontend code, `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`, or
`docs/CHANGELOG.md` were modified by this task.

## Inventory scope

- `docs/audits/*.md`: 70 files reviewed.
- `docs/codex/*.md`: 1 file reviewed.
- Conflict sentinels: `docs/audits/final-pre-push-audit.md` and
  `docs/audits/markdown-inventory.md` were absent, not dirty.
- Target file before this task: `docs/audits/markdown-consolidation-plan.md`
  was absent.

## Recommended final docs structure

Keep the final structure small and status-driven:

- `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`: canonical Codex task guard.
- `docs/audits/public-launch-gap-register.md`: launch blocker register and
  public-readiness source of truth.
- `docs/audits/deployment-readiness-checklist.md`: release-candidate checklist.
- `docs/audits/archive/release-integration-plan-main-ahead.md`: current main/ahead
  integration plan until the release branch is cut.
- `docs/audits/release-rollback-runbook.md`: operational rollback runbook.
- `docs/audits/admin-governance-cost-e2e-qa-runbook.md`: admin/cost release QA
  runbook.
- `docs/audits/provider-data-incident-runbook.md`: provider/data incident
  response runbook.
- `docs/audits/ci-postgres-gate-triage-guide.md`: CI/PostgreSQL triage runbook.
- `docs/audits/trading-no-advice-product-policy.md`: product safety policy.
- `docs/audits/data-quality-user-disclosure-policy.md`: data disclosure policy.
- `docs/audits/<domain>-archive-index.md`: future index files for archived or
  superseded design/audit evidence, created only after a separate move/delete
  approval.

## Keep standalone

These should remain independent because they are canonical, operational, or
active launch-readiness references:

- `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`
- `docs/audits/public-launch-gap-register.md`
- `docs/audits/deployment-readiness-checklist.md`
- `docs/audits/archive/release-integration-plan-main-ahead.md`
- `docs/audits/release-rollback-runbook.md`
- `docs/audits/admin-governance-cost-e2e-qa-runbook.md`
- `docs/audits/provider-data-incident-runbook.md`
- `docs/audits/ci-postgres-gate-triage-guide.md`
- `docs/audits/trading-no-advice-product-policy.md`
- `docs/audits/data-quality-user-disclosure-policy.md`
- `docs/audits/market-data-provider-upgrade-decision-matrix.md`
- `docs/audits/options-provider-adapter-contract.md`

## Merge candidates

Merge later into small domain indexes or readiness docs, preserving original
links until the merge is explicitly approved:

| Target | Candidates |
| --- | --- |
| Admin data/governance index | `admin-data-control-center-design.md`, `admin-data-control-center-frontend-ux-contract.md`, `admin-data-governance-next-phase-design.md`, `admin-data-schema-inventory.md`, `admin-user-directory-api-design.md`, `admin-user-activity-timeline-api-design.md` |
| Admin RBAC/security governance index | `admin-rbac-capability-model-design.md`, `admin-rbac-r5-coarse-fallback-removal-plan.md`, `admin-rbac-final-qa-report.md`, `admin-role-governance-plan.md`, `admin-role-management-ui-design.md` |
| Cost observability index | `cost-observability-design-index.md`, `cost-observability-implementation-roadmap.md`, `cost-system-final-qa-matrix.md`, `duplicate-cost-admin-summary-api-design.md`, `duplicate-cost-admin-dashboard-frontend-ux-contract.md`, `llm-external-api-cost-audit.md`, `llm-instrumentation-validation-plan.md`, `llm-provider-duplicate-cost-metrics-design.md` |
| DB readiness index | `db-production-readiness-index-retention-audit.md`, `db-index-migration-plan-auth-task-log.md`, `db-index-batch-b-execution-provider-cost-plan.md`, `db-retention-backup-restore-drill-plan.md`, `ws2-multi-instance-smoke-test-design.md`, `ws2-multi-user-runtime-cost-control-design.md` |
| Provider/MarketCache readiness index | `ws2-provider-circuit-data-model-plan.md`, `ws2-provider-quota-circuit-breaker-policy-design.md` |
| Security hardening index | `production-security-hardening-audit.md`, `security-password-kdf-upgrade-plan.md`, `security-admin-mfa-backend-foundation.md`, `security-mfa-secret-storage-hardening-plan.md` |
| Reuse/cache design index | `guest-preview-reuse-design.md`, `llm-report-output-cache-design.md`, `scanner-ai-interpretation-cache-design.md` |
| Frontend visual audit index | `wolfystock-frontend-design-conformance-audit.md`, `wolfystock-global-codebase-audit.md`, `wolfystock-phase0-bundle-design-inventory.md`, `wolfystock-bundle-composition-report.md`, `wolfystock-echarts-chart-workspace-audit.md`, `wolfystock-product-command-card-owner-audit.md`, `wolfystock-chinese-form-label-review.md` |
| CSS/DOM verification index | `wolfystock-css-cleanup-closure-report.md`, `wolfystock-css-ownership-inventory.md`, `wolfystock-css-selector-usage-verification.md`, `wolfystock-scrollarea-custom-scrollbar-owner-inventory.md`, `wolfystock-scrollbar-dom-verification.md`, `wolfystock-corrected-scroll-proof.md`, `wolfystock-scanner-dom-verification.md`, `wolfystock-backtest-dom-verification.md`, `wolfystock-chat-dom-verification.md` |

## Archive or superseded candidates

Do not move or delete these in this task. Mark them as candidates only:

- `db-index-migration-plan-auth-task-log.md`: Batch A has an implementation
  note; keep as historical plan unless Batch A details are still needed.
- `admin-rbac-capability-model-design.md`: R3/R3b/R4A/R4B are implemented or
  QA-covered in later docs; keep as historical design baseline.
- `security-password-kdf-upgrade-plan.md`: later implementation notes indicate
  Phase 3D and related follow-ups changed status.
- `production-security-hardening-audit.md`: includes later implementation
  notes; should become either a security index input or archive evidence.
- `wolfystock-phase0-bundle-design-inventory.md`: earlier inventory that is
  largely superseded by later bundle/composition and DOM/CSS reports.
- `wolfystock-post-batch-integration-qa.md` and
  `wolfystock-final-admin-security-options-qa.md`: keep as historical QA
  evidence; archive after launch-readiness docs cite the accepted result.
- `data-pipeline-r2-progressive-enrichment.md`,
  `security-admin-mfa-backend-foundation.md`, and
  `options-provider-adapter-contract.md`: short implementation summaries that
  can be absorbed into domain indexes after their runtime feature docs exist.

## Stale or needs status header

Add a compact status header later before moving anything. The header should
state `Active`, `Partially implemented`, `Superseded`, or `Historical evidence`.

- Large design docs with partial implementation notes:
  `admin-data-governance-next-phase-design.md`,
  `admin-user-directory-api-design.md`,
  `admin-user-activity-timeline-api-design.md`,
  `admin-rbac-capability-model-design.md`,
  `security-password-kdf-upgrade-plan.md`,
  `production-security-hardening-audit.md`.
- Docs blocked by older unrelated dirty state or older browser evidence:
  `admin-rbac-final-qa-report.md`, `wolfystock-corrected-scroll-proof.md`.
- Older read-only visual audits that need a current-route status marker before
  reuse: `wolfystock-global-codebase-audit.md`,
  `wolfystock-frontend-design-conformance-audit.md`,
  `wolfystock-phase0-bundle-design-inventory.md`,
  `wolfystock-echarts-chart-workspace-audit.md`,
  `wolfystock-bundle-composition-report.md`.

## Duplicate or possible conflicts

- `duplicate-cost-admin-summary-api-design.md` and
  `duplicate-cost-admin-dashboard-frontend-ux-contract.md` should be folded
  under the cost observability index. They are complementary API/UI contracts,
  not true duplicates, but their filenames read like duplicate copies.
- `admin-data-control-center-design.md`,
  `admin-data-control-center-frontend-ux-contract.md`,
  `admin-user-directory-api-design.md`, and
  `admin-user-activity-timeline-api-design.md` overlap on admin user IA,
  route contracts, redaction, and audit expectations.
- `ws2-provider-quota-circuit-breaker-policy-design.md` and
  `ws2-provider-circuit-data-model-plan.md` overlap on provider diagnostics,
  quota/circuit vocabulary, and future dashboard readiness.
- `deployment-readiness-checklist.md`, `public-launch-gap-register.md`, and
  `release-integration-plan-main-ahead.md` overlap on launch readiness. Keep
  all three for now, but define one source-of-truth responsibility per file.
- CSS/DOM reports intentionally overlap as evidence for deletion trials. Treat
  them as chronological proof, not conflicting guidance, until a CSS/DOM index
  captures final selector status.

## Independent runbooks

These should remain independent runbooks because they are action-oriented:

- `admin-governance-cost-e2e-qa-runbook.md`
- `provider-data-incident-runbook.md`
- `ci-postgres-gate-triage-guide.md`
- `release-rollback-runbook.md`

## Launch-readiness docs to merge later

Merge only after the next release-candidate gate confirms current status:

- `public-launch-gap-register.md`
- `deployment-readiness-checklist.md`
- `release-integration-plan-main-ahead.md`
- `production-security-hardening-audit.md`
- `db-production-readiness-index-retention-audit.md`
- `db-retention-backup-restore-drill-plan.md`
- `backtest-portfolio-public-safety-audit.md`
- `cost-system-final-qa-matrix.md`
- `admin-rbac-final-qa-report.md`
- `wolfystock-final-admin-security-options-qa.md`

Recommended result: keep `public-launch-gap-register.md` as the blocker
register, keep `deployment-readiness-checklist.md` as the operational checklist,
and archive older one-off QA reports after their evidence is linked.

## Plan docs now partially or fully implemented

These need implementation-status reconciliation before archive or merge:

- `db-index-migration-plan-auth-task-log.md`: Batch A appears implemented;
  later Batch B plan remains active.
- `db-index-batch-b-execution-provider-cost-plan.md`: recent commits indicate
  Batch B smoke coverage landed, but the doc still marks runtime/schema work
  deferred.
- `admin-rbac-capability-model-design.md`: R3/R3b/R4A/R4B are represented by
  later implementation and QA docs; R5 remains planned.
- `admin-rbac-r5-coarse-fallback-removal-plan.md`: still active as future R5.
- `admin-user-directory-api-design.md` and
  `admin-user-activity-timeline-api-design.md`: implementation notes exist;
  confirm frontend coverage before marking active.
- `security-password-kdf-upgrade-plan.md`: Phase 3D is implemented; later MFA
  dependencies remain active.
- `security-admin-mfa-backend-foundation.md` and
  `security-mfa-secret-storage-hardening-plan.md`: backend scaffold exists,
  production secret storage remains planned.
- `ws2-provider-quota-circuit-breaker-policy-design.md` and
  `ws2-provider-circuit-data-model-plan.md`: storage/dry-run pieces appear
  implemented; live enforcement remains future.
- `cost-observability-implementation-roadmap.md`: ledger/pricing/foundation
  pieces appear implemented; billing-authoritative enforcement remains future.
- `data-pipeline-r2-progressive-enrichment.md`: implementation summary, not an
  active plan.

## Next consolidation sequence

1. Add status headers only, starting with launch-readiness and security docs.
2. Create domain index files without moving originals.
3. Update launch-readiness docs to link domain indexes instead of duplicating
   plan text.
4. In a later explicitly approved cleanup task, move superseded one-off evidence
   into an archive folder or leave in place with `Historical evidence` headers.
5. Only after links are stable, consider deleting or moving files in a separate
   task with a fresh inventory and `git status --short` check.

## Validation plan

Required docs-only validation for this plan:

```bash
git diff --check -- docs/audits/markdown-consolidation-plan.md
git status --short
```

Markdown sanity check, if available:

```bash
npx markdownlint-cli2 docs/audits/markdown-consolidation-plan.md
```

No `ci_gate` is required because this task creates one docs-only planning file.
