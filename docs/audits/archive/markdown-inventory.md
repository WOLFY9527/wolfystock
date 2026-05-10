# Markdown Inventory

> Historical evidence note
>
> Superseded for current audit navigation by `docs/audits/README.md` and for
> the current public launch verdict by
> `docs/audits/public-launch-readiness-master.md`. This file remains useful as
> a point-in-time classification snapshot only.

Status: Historical note
Owner domain: Documentation governance
Related docs: `docs/audits/archive/markdown-consolidation-plan.md`, `docs/audits/archive/final-pre-push-audit.md`

Date: 2026-05-07
Branch checked: `main`
Mode: docs-only inventory. No markdown files were deleted or moved.

## Scope

- Tracked scope reviewed after the concurrent consolidation commit: 70 tracked
  `docs/audits/*.md` files and 1 tracked `docs/codex/*.md` file.
- New audit package files from this task: `docs/audits/archive/final-pre-push-audit.md` and this file.

## Classification Key

- `Keep standalone`: canonical, operational, current launch-readiness, or active policy.
- `Merge candidate`: useful content, but should roll into a domain index or readiness source later.
- `Archive/superseded candidate`: historical evidence or old plan; do not move without a separate cleanup task.
- `Stale/needs status header`: likely still useful, but needs `Active`, `Partially implemented`, `Superseded`, or `Historical evidence` before reuse.
- `Duplicate/possible conflict`: overlaps another doc enough that ownership should be clarified before push/cleanup.

## Inventory Table

| File | Classification | Notes |
| --- | --- | --- |
| `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md` | Keep standalone | Canonical Codex task guard. Keep as the operating contract. |
| `docs/audits/admin-data-control-center-design.md` | Merge candidate | Fold into an admin data/governance index after current implementation status is marked. |
| `docs/audits/admin-data-control-center-frontend-ux-contract.md` | Merge candidate | Complements admin data UX contracts; preserve redaction rules. |
| `docs/audits/admin-data-governance-next-phase-design.md` | Stale/needs status header | Large design with partial implementation overlap; add status before reuse. |
| `docs/audits/admin-data-schema-inventory.md` | Merge candidate | Useful schema reference; should feed admin data index. |
| `docs/audits/admin-governance-cost-e2e-qa-runbook.md` | Keep standalone | Action-oriented release QA runbook. |
| `docs/audits/admin-rbac-capability-model-design.md` | Stale/needs status header | Earlier RBAC design; later R3/R4 docs supersede parts while R5 remains active. |
| `docs/audits/archive/admin-rbac-final-qa-report.md` | Archive/superseded candidate | Historical QA evidence; keep until launch docs cite the accepted result. |
| `docs/audits/admin-rbac-r5-coarse-fallback-removal-plan.md` | Keep standalone | Active future R5 plan and launch blocker input. |
| `docs/audits/admin-role-governance-plan.md` | Keep standalone | Active governance plan for role/capability assignment. |
| `docs/audits/admin-role-management-ui-design.md` | Merge candidate | Pair with role governance plan once implementation scope opens. |
| `docs/audits/admin-user-activity-timeline-api-design.md` | Stale/needs status header | Has implementation notes; confirm current API/frontend state before reuse. |
| `docs/audits/admin-user-directory-api-design.md` | Stale/needs status header | Has implementation notes; confirm current API/frontend state before reuse. |
| `docs/audits/backtest-portfolio-public-safety-audit.md` | Keep standalone | Active launch-risk input for financial-domain owner isolation and regressions. |
| `docs/audits/ci-postgres-gate-triage-guide.md` | Keep standalone | Action-oriented CI/PostgreSQL triage runbook. |
| `docs/audits/cost-observability-design-index.md` | Merge candidate | Should become or feed a consolidated cost observability index. |
| `docs/audits/cost-observability-implementation-roadmap.md` | Stale/needs status header | Several ledger/pricing pieces appear implemented; enforcement remains future. |
| `docs/audits/cost-system-final-qa-matrix.md` | Keep standalone | Active cost/quota QA matrix and public launch blocker input. |
| `docs/audits/data-pipeline-r2-progressive-enrichment.md` | Archive/superseded candidate | Short implementation summary; absorb into data pipeline status docs later. |
| `docs/audits/data-quality-user-disclosure-policy.md` | Keep standalone | Canonical data disclosure policy. |
| `docs/audits/db-index-batch-b-execution-provider-cost-plan.md` | Stale/needs status header | Recent smoke coverage landed; status should distinguish smoke from real migration. |
| `docs/audits/archive/db-index-migration-plan-auth-task-log.md` | Archive/superseded candidate | Batch A appears implemented; keep as historical index plan until cited. |
| `docs/audits/db-production-readiness-index-retention-audit.md` | Merge candidate | Feed DB readiness index; still useful launch blocker evidence. |
| `docs/audits/db-retention-backup-restore-drill-plan.md` | Keep standalone | Active backup/restore and retention blocker plan. |
| `docs/audits/deployment-readiness-checklist.md` | Keep standalone | Operational go/no-go checklist for public multi-user readiness. |
| `docs/audits/duplicate-cost-admin-dashboard-frontend-ux-contract.md` | Duplicate/possible conflict | Complementary UI contract; fold under cost observability index. |
| `docs/audits/duplicate-cost-admin-summary-api-design.md` | Duplicate/possible conflict | Complementary API contract; fold under cost observability index. |
| `docs/audits/guest-preview-reuse-design.md` | Merge candidate | Reuse/cache design; keep disabled-default constraints. |
| `docs/audits/llm-external-api-cost-audit.md` | Merge candidate | Feed cost observability/security index. |
| `docs/audits/llm-instrumentation-validation-plan.md` | Merge candidate | Feed cost/LLM observability index. |
| `docs/audits/llm-provider-duplicate-cost-metrics-design.md` | Merge candidate | Feed duplicate-cost/cost observability index. |
| `docs/audits/llm-report-output-cache-design.md` | Merge candidate | Feed reuse/cache design index; preserve force-refresh and scope rules. |
| `docs/audits/archive/markdown-consolidation-plan.md` | Duplicate/possible conflict | Newly tracked consolidation plan; overlaps this inventory, so reconcile source-of-truth ownership later. |
| `docs/audits/market-data-provider-upgrade-decision-matrix.md` | Keep standalone | Active provider decision matrix. |
| `docs/audits/options-lab-phase0-design.md` | Archive/superseded candidate | Historical Options design baseline; later R1/R2/provider docs supersede parts. |
| `docs/audits/options-provider-adapter-contract.md` | Keep standalone | Active Options provider adapter contract; live provider remains disabled. |
| `docs/audits/production-security-hardening-audit.md` | Stale/needs status header | Several mitigations landed after this audit; reconcile before reuse. |
| `docs/audits/provider-data-incident-runbook.md` | Keep standalone | Operational provider/data incident runbook. |
| `docs/audits/public-launch-gap-register.md` | Keep standalone | Current launch blocker register and public-readiness source of truth. |
| `docs/audits/archive/release-integration-plan-main-ahead.md` | Keep standalone | Current integration plan until the ahead train is pushed or branched. |
| `docs/audits/release-rollback-runbook.md` | Keep standalone | Operational rollback runbook. |
| `docs/audits/scanner-ai-interpretation-cache-design.md` | Merge candidate | Feed reuse/cache design index; scanner AI stays additive. |
| `docs/audits/archive/security-admin-mfa-backend-foundation.md` | Archive/superseded candidate | Backend scaffold summary; production storage plan is newer and active. |
| `docs/audits/security-mfa-secret-storage-hardening-plan.md` | Keep standalone | Active production MFA storage blocker plan. |
| `docs/audits/security-password-kdf-upgrade-plan.md` | Stale/needs status header | Phase 3D appears implemented; MFA dependencies remain separate. |
| `docs/audits/trading-no-advice-product-policy.md` | Keep standalone | Canonical trading/no-advice product policy. |
| `docs/audits/wolfystock-backtest-dom-verification.md` | Merge candidate | Chronological DOM evidence for CSS cleanup; keep until indexed. |
| `docs/audits/wolfystock-bundle-composition-report.md` | Stale/needs status header | Older visual/bundle evidence; needs current status. |
| `docs/audits/wolfystock-chat-dom-verification.md` | Merge candidate | Chronological DOM evidence for CSS cleanup; keep until indexed. |
| `docs/audits/wolfystock-chinese-form-label-review.md` | Merge candidate | Feed frontend visual/i18n audit index. |
| `docs/audits/wolfystock-corrected-scroll-proof.md` | Stale/needs status header | Useful evidence but tied to corrected/mock-limited state. |
| `docs/audits/wolfystock-css-cleanup-closure-report.md` | Keep standalone | Active CSS cleanup governance summary. |
| `docs/audits/wolfystock-css-ownership-inventory.md` | Keep standalone | Active CSS selector ownership reference. |
| `docs/audits/wolfystock-css-selector-usage-verification.md` | Merge candidate | CSS deletion-trial evidence; preserve until indexed. |
| `docs/audits/wolfystock-echarts-chart-workspace-audit.md` | Stale/needs status header | Older frontend audit; needs current-route status. |
| `docs/audits/archive/wolfystock-final-admin-security-options-qa.md` | Archive/superseded candidate | Historical QA evidence; cite from launch docs if accepted. |
| `docs/audits/wolfystock-frontend-design-conformance-audit.md` | Stale/needs status header | Older route/browser evidence; note auth/mock limits before reuse. |
| `docs/audits/wolfystock-global-codebase-audit.md` | Stale/needs status header | Large global audit; split or status-mark before use. |
| `docs/audits/wolfystock-phase0-bundle-design-inventory.md` | Archive/superseded candidate | Earlier inventory largely superseded by later bundle/DOM/CSS reports. |
| `docs/audits/wolfystock-post-batch-integration-qa.md` | Archive/superseded candidate | Historical QA report. |
| `docs/audits/wolfystock-product-command-card-owner-audit.md` | Merge candidate | CSS/DOM owner evidence; preserve until selector index exists. |
| `docs/audits/wolfystock-scanner-dom-verification.md` | Merge candidate | Chronological DOM evidence; note prior dirty CSS limitation if reused. |
| `docs/audits/wolfystock-scrollarea-custom-scrollbar-owner-inventory.md` | Merge candidate | CSS/scrollbar ownership evidence. |
| `docs/audits/wolfystock-scrollbar-dom-verification.md` | Merge candidate | CSS/scrollbar DOM evidence. |
| `docs/audits/ws2-multi-instance-smoke-test-design.md` | Keep standalone | Active public-launch blocker design until executable smoke exists. |
| `docs/audits/ws2-multi-user-runtime-cost-control-design.md` | Keep standalone | Active WS2/cost/runtime architecture baseline. |
| `docs/audits/ws2-provider-circuit-data-model-plan.md` | Stale/needs status header | Storage/API/dry-run notes exist; live enforcement remains future. |
| `docs/audits/ws2-provider-quota-circuit-breaker-policy-design.md` | Keep standalone | Active provider circuit policy design; enforcement not live. |

## High-Priority Recommendations

1. Keep `public-launch-gap-register.md` as the blocker register, `deployment-readiness-checklist.md` as the operational checklist, and `release-integration-plan-main-ahead.md` as the current ahead-train integration plan.
2. Add status headers before moving or archiving any large design docs.
3. Create domain indexes before deletion or movement: admin data, RBAC/security, cost/quota, DB readiness, provider/MarketCache, reuse/cache, frontend visual, CSS/DOM.
4. Leave CSS/DOM reports in place until a selector index captures final rendered status and route evidence.
5. Reconcile `docs/audits/archive/markdown-consolidation-plan.md` with this inventory
   before a future docs cleanup, because both classify the same markdown set.
