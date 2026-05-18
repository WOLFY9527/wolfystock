# Audit Index

Status: active audit navigation.

Use this file to find current launch, safety, domain, and operator evidence.
Historical point-in-time reports now live in archive lanes and should not be
treated as current authority unless a current doc explicitly cites them.

## Current Launch Authority

Current public launch status: **NO-GO**.

- `public-launch-readiness-master.md`: executive launch verdict and cross-domain readiness summary.
- `public-launch-gap-register.md`: detailed blocker register and recommended next tasks.
- `public-launch-blocker-burndown.md`: active blocker tracker only.
- `deployment-readiness-checklist.md`: release-candidate operational checklist and final gate requirements.
- `launch-acceptance-evidence-pack.md`: sanitized launch evidence contract, not acceptance by itself.
- `incident-response-audit-evidence-pack.md`: incident response evidence contract, not acceptance by itself.
- `known-test-warnings-register.md`: accepted warning inventory that must not be confused with launch acceptance.

## Current Domain Indexes

- `index-security-rbac-mfa.md`: security, RBAC, role-governance, and MFA.
- `index-db-ws2-deployment.md`: database readiness, WS2 runtime, and deployment.
- `index-cost-quota-observability.md`: cost, quota, provider budget, and observability.
- `index-provider-data-options.md`: provider, data-quality, and Options readiness.

## Current Supporting Audits And Runbooks

Security and public-safety:

- `auth-rbac-release-security-guide.md`
- `admin-rbac-capability-model-design.md`
- `admin-rbac-r5-coarse-fallback-removal-plan.md`
- `admin-role-governance-plan.md`
- `production-security-hardening-audit.md`
- `security-mfa-secret-storage-hardening-plan.md`
- `security-password-kdf-upgrade-plan.md`
- `backtest-portfolio-public-safety-audit.md`
- `trading-no-advice-product-policy.md`

Provider, data quality, and Options:

- `provider-data-freshness-reliability-guide.md`
- `provider-data-incident-runbook.md`
- `market-data-provider-upgrade-decision-matrix.md`
- `data-quality-user-disclosure-policy.md`
- `data-pipeline-r2-progressive-enrichment.md`
- `options-provider-adapter-contract.md`
- `options-lab-phase0-design.md`
- `scanner-ai-interpretation-cache-design.md`
- `guest-preview-reuse-design.md`
- `backtest-quant-capability-audit.md`

Database, WS2, deployment, and gates:

- `db-production-readiness-index-retention-audit.md`
- `db-retention-backup-restore-drill-plan.md`
- `db-index-batch-b-execution-provider-cost-plan.md`
- `ws2-multi-instance-smoke-test-design.md`
- `ws2-multi-user-runtime-cost-control-design.md`
- `ci-gate-usage.md`
- `ci-postgres-gate-triage-guide.md`
- `staging-integration-smoke-guide.md`
- `release-rollback-runbook.md`

Cost, quota, LLM, and observability:

- `cost-observability-design-index.md`
- `cost-observability-implementation-roadmap.md`
- `cost-system-final-qa-matrix.md`
- `duplicate-cost-admin-summary-api-design.md`
- `duplicate-cost-admin-dashboard-frontend-ux-contract.md`
- `llm-external-api-cost-audit.md`
- `llm-instrumentation-validation-plan.md`
- `llm-provider-duplicate-cost-metrics-design.md`
- `llm-report-output-cache-design.md`
- `quota-cost-notification-release-guide.md`
- `ws2-provider-circuit-data-model-plan.md`
- `ws2-provider-quota-circuit-breaker-policy-design.md`

Admin data and governance designs:

- `admin-data-schema-inventory.md`
- `admin-data-governance-next-phase-design.md`
- `admin-data-control-center-design.md`
- `admin-data-control-center-frontend-ux-contract.md`
- `admin-user-directory-api-design.md`
- `admin-user-activity-timeline-api-design.md`
- `admin-governance-cost-e2e-qa-runbook.md`
- `admin-role-management-ui-design.md`

Frontend guidance retained as current code-support material:

- `frontend-information-density-and-guidance-standard.md`
- `frontend-guided-information-system.md`
- `frontend-guided-disclosure-primitives.md`
- `frontend-domain-education-copy-pack.md`
- `frontend-ux-density-audit-harness.md`
- `wolfystock-css-ownership-inventory.md`
- `wolfystock-css-selector-usage-verification.md`
- `wolfystock-frontend-design-conformance-audit.md`

The three `wolfystock-*` frontend support files above are retained because
current CSS deletion and design-check guidance still cites them. They are not
current visual source-of-truth; Reflect-Linear docs in `docs/codex/` and
`docs/design/` win for frontend design work.

## Operator Evidence

- `operator-evidence-real-runbook.md`
- `operator-evidence-dry-run-handoff.md`
- `operator-evidence-redaction-checklist.md`
- `evidence-artifact-sanitizer-guide.md`
- `public-api-abuse-limiter-operator-note.md`

## Archive Pointers

- `docs/audits/archive/`: historical audit and consolidation notes.
- `docs/audits/archive/backtest/`: archived backtest helper maintenance evidence
  and machine-readable audit bundles.
- `docs/audits/archive/frontend/`: retired frontend DOM, CSS, bundle, route, and old launch UX reports.
- `docs/qa/archive/`: point-in-time QA reports retained for provenance.
- `docs/architecture/archive/`: historical architecture and Phase F evidence.
- `docs/design/archive/old-ui/`: transitional UI replacement notes, not active design authority.

Use `docs/ARCHIVE_INDEX.md` for the archive inventory and safe-use rules.

## Reuse Warning

For current GO/NO-GO, launch, frontend visual, provider, security, portfolio,
backtest, or API claims, start from active docs, current source, and current
validation. Do not cite archived audits, stale screenshots, local artifacts, or
old route proofs as current acceptance evidence.
