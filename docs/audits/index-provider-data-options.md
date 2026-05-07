# Provider / Data / Options Audit Index

Status: Current
Owner domain: Provider, data quality, MarketCache, Data Pipeline, and Options
documentation index
Related docs: `docs/audits/public-launch-readiness-master.md`,
`docs/audits/public-launch-gap-register.md`,
`docs/audits/deployment-readiness-checklist.md`,
`docs/audits/markdown-consolidation-plan.md`,
`docs/audits/markdown-inventory.md`

Mode: docs-only navigation index. No audit files were moved, deleted,
archived, merged, or rewritten.

## Purpose

This index groups provider reliability, data quality, and Options evidence
without changing live provider ordering, fallback behavior, MarketCache,
Options, or Data Pipeline behavior.

## Current canonical docs

- `docs/audits/public-launch-readiness-master.md`: executive launch status for
  Provider, Options, and data-quality readiness.
- `docs/audits/public-launch-gap-register.md`: detailed blockers for provider
  entitlement/licensing, provider circuit enforcement, Options live adapters,
  and data-quality dashboard readiness.
- `docs/audits/deployment-readiness-checklist.md`: operational provider,
  Options, and Data Pipeline readiness gates.
- `docs/audits/provider-data-incident-runbook.md`: provider/data incident
  response runbook.
- `docs/audits/data-quality-user-disclosure-policy.md`: canonical user-facing
  data-quality and disclosure policy.
- `docs/audits/market-data-provider-upgrade-decision-matrix.md`: current
  provider upgrade and paid-pilot decision matrix.
- `docs/audits/options-provider-adapter-contract.md`: active Options provider
  adapter contract; live provider use remains disabled until approved.

## Partial docs

- `docs/audits/provider-fallback-budget-reporting-design.md`: provider fallback
  and quota-risk reporting design; should feed a provider readiness index.
- `docs/audits/provider-marketcache-instrumentation-validation-plan.md`:
  MarketCache/provider instrumentation validation plan.
- `docs/audits/ws2-provider-circuit-data-model-plan.md`: storage/API/dry-run
  provider circuit pieces exist, but live enforcement remains future.
- `docs/audits/ws2-provider-quota-circuit-breaker-policy-design.md`: active
  policy design; provider circuit enforcement is not live.
- `docs/audits/data-pipeline-r2-progressive-enrichment.md`: implementation
  summary for progressive enrichment; not a full launch-readiness contract.

## Superseded docs

- `docs/audits/options-lab-phase0-design.md`: historical Options design
  baseline; later provider adapter and readiness docs supersede launch posture.
- `docs/audits/wolfystock-final-admin-security-options-qa.md`: historical
  Options/Admin/Security QA evidence; not the current Options launch source.

## Deferred docs

- `docs/audits/options-provider-adapter-contract.md`: real-provider pilot and
  live credential use remain deferred until entitlement and staging evidence
  are accepted.
- `docs/audits/ws2-provider-quota-circuit-breaker-policy-design.md`: live
  provider circuit enforcement pilot remains deferred.
- `docs/audits/provider-marketcache-instrumentation-validation-plan.md`:
  dashboard/staging degraded evidence remains future work.

## Launch blockers related to this domain

See `docs/audits/public-launch-readiness-master.md` and
`docs/audits/public-launch-gap-register.md`.

- Provider entitlement, freshness, and licensing are not launch accepted across
  all public route families.
- Provider circuit diagnostics exist, but no runtime call site enforces a
  provider circuit policy.
- Operators still need launch-ready provider SLA/degraded dashboard evidence.
- Options Lab remains read-only and fixture/synthetic for production posture;
  real provider adapter and staged live-provider evidence are still required.
- Public Options decisioning must remain no-broker, no-order, no-advice, and
  analysis-only.

## Hard-to-classify docs

- `docs/audits/data-pipeline-r2-progressive-enrichment.md`: short
  implementation summary; useful context but not a canonical runbook or blocker
  register.
- `docs/audits/provider-fallback-budget-reporting-design.md` and
  `docs/audits/provider-marketcache-instrumentation-validation-plan.md`: both
  overlap on provider diagnostics and should stay separate until a future
  provider readiness index is explicitly approved.
