# Cost / Quota / Observability Audit Index

Status: Current
Owner domain: Cost, quota, LLM usage, provider budget, and observability
documentation index
Related docs: `docs/audits/public-launch-readiness-master.md`,
`docs/audits/public-launch-gap-register.md`,
`docs/audits/deployment-readiness-checklist.md`,
`docs/audits/markdown-consolidation-plan.md`,
`docs/audits/markdown-inventory.md`

Mode: docs-only navigation index. No audit files were moved, deleted,
archived, merged, or rewritten.

## Purpose

This index separates cost observability evidence from quota enforcement status.
Cost dashboards and ledgers are useful, but public launch remains **NO-GO**
until route-boundary quota and provider-circuit enforcement pilots are accepted.

## Current canonical docs

- `docs/audits/public-launch-readiness-master.md`: executive launch status for
  cost, quota, and provider-circuit enforcement.
- `docs/audits/public-launch-gap-register.md`: detailed blocker register for
  live quota enforcement, budget alerts, provider invoice reconciliation, and
  provider circuit enforcement.
- `docs/audits/deployment-readiness-checklist.md`: operational cost/quota and
  provider reliability gates.
- `docs/audits/admin-governance-cost-e2e-qa-runbook.md`: action-oriented admin
  governance and cost E2E QA runbook.
- `docs/audits/cost-system-final-qa-matrix.md`: current QA matrix for completed
  cost-system surfaces.
- `docs/audits/ws2-multi-user-runtime-cost-control-design.md`: architecture
  baseline for multi-user runtime, quotas, ledger observation, and provider
  circuits.

## Partial docs

- `docs/audits/cost-observability-design-index.md`: earlier cost design index;
  feeds this domain until consolidation is approved.
- `docs/audits/cost-observability-implementation-roadmap.md`: roadmap with
  implemented ledger/pricing pieces and future enforcement work.
- `docs/audits/duplicate-cost-admin-summary-api-design.md`: API contract for
  duplicate-cost summaries; complementary despite the filename.
- `docs/audits/duplicate-cost-admin-dashboard-frontend-ux-contract.md`:
  frontend UX contract for duplicate-cost dashboards.
- `docs/audits/llm-external-api-cost-audit.md`: LLM/provider external cost
  audit input.
- `docs/audits/llm-instrumentation-validation-plan.md`: validation plan for
  LLM instrumentation and safe cost labels.
- `docs/audits/llm-provider-duplicate-cost-metrics-design.md`: metric design
  for duplicate provider/LLM cost observation.

## Superseded docs

- None confirmed in this domain. The `duplicate-cost-*` filenames are
  confusing, but the markdown inventory classifies them as complementary
  API/UI contracts rather than true duplicate copies.

## Deferred docs

- `docs/audits/cost-observability-implementation-roadmap.md`: live
  route-boundary enforcement, billing-authoritative reconciliation, and broader
  budget UI remain deferred.
- `docs/audits/ws2-multi-user-runtime-cost-control-design.md`: WS2-R4 quota
  enforcement and WS2-R5 provider circuit enforcement remain future runtime
  work.

## Launch blockers related to this domain

See `docs/audits/public-launch-readiness-master.md` and
`docs/audits/public-launch-gap-register.md`.

- Live quota enforcement is not enabled on a route boundary.
- Budget burn-down alerts and user/admin warning surfaces remain future work.
- Provider invoice/export reconciliation is not accepted as
  billing-authoritative.
- Provider quota buckets and provider circuit enforcement are diagnostic or
  dry-run, not live controls.
- Public UI/admin labels must keep observability distinct from hard spend or
  provider controls.

## Hard-to-classify docs

- `docs/audits/cost-observability-design-index.md`: already uses index wording,
  but it predates this broader domain navigation pass.
- `docs/audits/duplicate-cost-admin-summary-api-design.md` and
  `docs/audits/duplicate-cost-admin-dashboard-frontend-ux-contract.md`: names
  imply duplicates, but content is split by API and frontend contract.
