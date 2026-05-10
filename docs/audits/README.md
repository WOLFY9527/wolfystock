# Audit Index

Date: 2026-05-08
Branch checked: `main`
Mode: docs-only audit navigation cleanup. No source code, tests, scripts,
frontend files, production configs, or market-rotation files are changed by
this index.

## Current launch status

Current public launch status: **NO-GO**.

Do not treat historical notes, point-in-time audits, or archived candidates as
the current launch decision. The canonical launch verdict lives in
`docs/audits/public-launch-readiness-master.md` and the detailed blocker
register lives in `docs/audits/public-launch-gap-register.md`.

## Canonical current docs

Use this file as the audit navigation entry point. For current launch posture,
use the launch-control docs below; do not infer launch status from archived
notes, fixture examples, or a single product-capability changelog entry.

- `docs/audits/public-launch-readiness-master.md`: executive launch verdict and
  cross-domain readiness summary.
- `docs/audits/public-launch-gap-register.md`: detailed blocker register and
  recommended next tasks by domain.
- `docs/audits/deployment-readiness-checklist.md`: release-candidate
  operational checklist and final gate requirements.
- `docs/audits/public-launch-blocker-burndown.md`: short-form blocker tracker
  for active launch gaps only.
- `docs/audits/launch-acceptance-evidence-pack.md`: sanitized operator
  acceptance evidence contract and review matrix for launch review. It is not
  accepted operator evidence by itself.
- `docs/audits/incident-response-audit-evidence-pack.md`: sanitized incident
  response and auditability evidence contract for launch review. It is not
  accepted operator evidence by itself.
- `docs/audits/operator-evidence-real-runbook.md`: concise offline workflow
  and current source of truth for collecting sanitized real operator evidence,
  running validator/tool commands, creating a manifest, rendering a review
  report, and handing it to manual reviewers.
- `docs/audits/operator-evidence-dry-run-handoff.md`: synthetic-fixture-only
  dry-run handoff sequence for rehearsing the offline evidence workflow without
  touching launch acceptance plumbing or runtime behavior.
- `docs/audits/operator-evidence-redaction-checklist.md`: pre-handoff checklist
  for removing secrets, sessions, raw payloads, DB material, logs, personal
  identifiers, and unsafe approval wording from evidence packets.
- `docs/audits/release-rollback-runbook.md`: rollback instructions for a
  reviewed release candidate.
- `docs/audits/known-test-warnings-register.md`: accepted warning inventory
  that must not be confused with launch acceptance.

## Current product capability notes

- Market Rotation Radar is now a read-only product capability with
  `/api/v1/market/rotation-radar` and `/zh/market/rotation-radar` coverage. It
  is not a launch blocker, not operator launch evidence, and not a substitute
  for provider entitlement/freshness acceptance. Current launch status remains
  governed by the launch-control docs above.

## Evidence packs and operational runbooks

- `docs/audits/backtest-portfolio-public-safety-audit.md`,
  `docs/audits/production-security-hardening-audit.md`,
  `docs/audits/cost-system-final-qa-matrix.md`: current supporting evidence for
  public-safety, security-hardening, and cost-system readiness.
- `docs/audits/admin-governance-cost-e2e-qa-runbook.md`,
  `docs/audits/operator-evidence-dry-run-handoff.md`,
  `docs/audits/operator-evidence-real-runbook.md`,
  `docs/audits/operator-evidence-redaction-checklist.md`,
  `docs/audits/provider-data-incident-runbook.md`,
  `docs/audits/ci-gate-usage.md`,
  `docs/audits/ci-postgres-gate-triage-guide.md`: operator runbooks and gate
  usage notes.
- `docs/audits/db-retention-backup-restore-drill-plan.md`,
  `docs/audits/ws2-multi-instance-smoke-test-design.md`: active evidence plans
  for backup/restore and WS2 multi-instance proof that still remain launch
  blockers until exercised.

## Open NO-GO blockers

- Global MFA enforcement is not globally accepted or enabled.
- RBAC coarse-fallback default and full code-path removal remain pending.
- Real provider credentials, live provider calls, and provider-circuit
  enforcement are not active by default.
- Live quota enforcement is not globally active.
- Real isolated PostgreSQL restore and PITR execution remain pending unless
  accepted sanitized evidence is supplied.
- WS2 multi-instance smoke and process-local SSE limitation proof remain open.
- Final clean full `./scripts/ci_gate.sh` is still required before any launch
  tag or launch approval.

## Domain index documents

- `docs/audits/index-security-rbac-mfa.md`: security, RBAC, role-governance,
  and MFA audit index.
- `docs/audits/index-db-ws2-deployment.md`: database readiness, WS2 runtime,
  and deployment audit index.
- `docs/audits/index-cost-quota-observability.md`: cost, quota, provider
  budget, and observability audit index.
- `docs/audits/index-provider-data-options.md`: provider, data-quality, and
  Options/decision-readiness audit index.

## Domain-specific audits and designs

- Security and admin governance:
  `admin-rbac-capability-model-design.md`,
  `admin-rbac-r5-coarse-fallback-removal-plan.md`,
  `admin-role-governance-plan.md`,
  `admin-role-management-ui-design.md`,
  `security-mfa-secret-storage-hardening-plan.md`,
  `security-password-kdf-upgrade-plan.md`,
  `admin-data-control-center-design.md`,
  `admin-data-control-center-frontend-ux-contract.md`,
  `admin-data-governance-next-phase-design.md`,
  `admin-data-schema-inventory.md`,
  `admin-user-activity-timeline-api-design.md`,
  `admin-user-directory-api-design.md`.
- Provider, data quality, and Options:
  `data-pipeline-r2-progressive-enrichment.md`,
  `data-quality-user-disclosure-policy.md`,
  `guest-preview-reuse-design.md`,
  `market-data-provider-upgrade-decision-matrix.md`,
  `options-lab-phase0-design.md`,
  `options-provider-adapter-contract.md`,
  `provider-data-freshness-reliability-guide.md`,
  `scanner-ai-interpretation-cache-design.md`,
  `trading-no-advice-product-policy.md`,
  `ws2-provider-circuit-data-model-plan.md`,
  `ws2-provider-quota-circuit-breaker-policy-design.md`,
  `llm-report-output-cache-design.md`.
- Cost, quota, and observability:
  `cost-observability-design-index.md`,
  `cost-observability-implementation-roadmap.md`,
  `duplicate-cost-admin-dashboard-frontend-ux-contract.md`,
  `duplicate-cost-admin-summary-api-design.md`,
  `llm-external-api-cost-audit.md`,
  `llm-instrumentation-validation-plan.md`,
  `llm-provider-duplicate-cost-metrics-design.md`,
  `ws2-multi-user-runtime-cost-control-design.md`.
  The `duplicate-cost-*` files are complementary API/UI contracts, not current
  archive candidates.
- DB, retention, and deployment:
  `db-index-batch-b-execution-provider-cost-plan.md`,
  `db-production-readiness-index-retention-audit.md`,
  `ws2-multi-instance-smoke-test-design.md`,
  `db-retention-backup-restore-drill-plan.md`.
- WolfyStock frontend, DOM, and UX evidence:
  `wolfystock-backtest-dom-verification.md`,
  `wolfystock-bundle-composition-report.md`,
  `wolfystock-chat-dom-verification.md`,
  `wolfystock-chinese-form-label-review.md`,
  `wolfystock-corrected-scroll-proof.md`,
  `wolfystock-css-cleanup-closure-report.md`,
  `wolfystock-css-ownership-inventory.md`,
  `wolfystock-css-selector-usage-verification.md`,
  `wolfystock-echarts-chart-workspace-audit.md`,
  `wolfystock-frontend-design-conformance-audit.md`,
  `wolfystock-global-codebase-audit.md`,
  `wolfystock-phase0-bundle-design-inventory.md`,
  `wolfystock-post-batch-integration-qa.md`,
  `wolfystock-product-command-card-owner-audit.md`,
  `wolfystock-scanner-dom-verification.md`,
  `wolfystock-scrollarea-custom-scrollbar-owner-inventory.md`,
  `wolfystock-scrollbar-dom-verification.md`.

Completed pre-closure CSS/DOM pass notes are consolidated into
`wolfystock-css-cleanup-closure-report.md`. Prefer the closure report plus the
retained route-specific DOM proofs above over older pass-by-pass audit history.

Operator evidence wrappers were similarly consolidated: prefer
`operator-evidence-real-runbook.md`,
`operator-evidence-dry-run-handoff.md`, and
`operator-evidence-redaction-checklist.md` over older per-tool or per-category
guide documents.

Release review reporting, rollback rehearsal, and restore/PITR launch
procedures are likewise governed by the retained current runbooks:
`operator-evidence-real-runbook.md` for bundle/report rendering,
`release-rollback-runbook.md` for rollback decisioning and rehearsal evidence,
and `db-retention-backup-restore-drill-plan.md` plus
`deployment-readiness-checklist.md` for restore/PITR readiness. Do not treat
older single-purpose release drill or renderer guides as separate launch
control sources of truth.

## Historical and superseded notes

- Archived historical notes now live under `docs/audits/archive/`:
  `final-pre-push-audit.md`, `markdown-inventory.md`,
  `markdown-consolidation-plan.md`,
  `release-integration-plan-main-ahead.md`.
- Older supporting evidence and superseded foundations now live under
  `docs/audits/archive/`: `admin-rbac-final-qa-report.md`,
  `security-admin-mfa-backend-foundation.md`,
  `wolfystock-final-admin-security-options-qa.md`,
  `db-index-migration-plan-auth-task-log.md`.
- Current launch-control and operator docs remain canonical at the top level of
  `docs/audits/`. Historical links from active docs now point to the archived
  locations.

## Reuse warning

Use historical notes only as supporting evidence. For any current GO/NO-GO,
release, or public-launch claim, start from:

- `docs/audits/README.md`
- `docs/audits/public-launch-readiness-master.md`
- `docs/audits/public-launch-gap-register.md`
- `docs/audits/deployment-readiness-checklist.md`
